# modules/planificador/planificador_services.py
# -*- coding: utf-8 -*-
"""Lógica de negocio para el módulo Planificador."""

from flask import session
from . import planificador_repository as repo
from .planificador_constants import (
    ROL_COORDINADOR, ROL_APROBADOR, ROL_MOTORIZADO,
    ROLES_ADMIN, ROLES_GERENTE, ESTADOS,
    ESTADOS_RESERVADAS, ESTADOS_COORDINADAS, ESTADOS_ATENDIDAS,
)


def get_user_context(usuario_id, rol):
    """
    Devuelve qué tipos puede coordinar/aprobar el usuario actual.
    """
    config_rows = repo.get_config_for_user(usuario_id)
    tipos_coordinador = [r["tipo"] for r in config_rows if r["rol_config"] == ROL_COORDINADOR]
    tipos_aprobador   = [r["tipo"] for r in config_rows if r["rol_config"] == ROL_APROBADOR]
    tipos_motorizado  = [r["tipo"] for r in config_rows if r["rol_config"] == ROL_MOTORIZADO]
    es_admin          = rol in ROLES_ADMIN
    es_gerente        = rol.lower() in ROLES_GERENTE if rol else False
    return {
        "tipos_coordinador": tipos_coordinador,
        "tipos_aprobador":   tipos_aprobador,
        "tipos_motorizado":  tipos_motorizado,
        "es_admin":          es_admin,
        "es_gerente":        es_gerente,
        "user_id":           usuario_id,
    }


def get_solicitudes_for_user(usuario_id, rol, filters=None):
    """
    Devuelve las solicitudes visibles para el usuario según su rol.
    """
    ctx = get_user_context(usuario_id, rol)

    if ctx["es_admin"]:
        return repo.get_all_solicitudes(filters)

    # Reúne solicitudes propias + solicitudes que el usuario debe gestionar
    propias = repo.get_mis_solicitudes(usuario_id, filters)
    ids_propias = {r["id"] for r in propias}

    extra = []
    if ctx["tipos_coordinador"]:
        extra += repo.get_solicitudes_by_tipos(
            ctx["tipos_coordinador"],
            ["PENDIENTE_COORDINACION"],
            filters
        )
    if ctx["tipos_aprobador"]:
        extra += repo.get_solicitudes_by_tipos(
            ctx["tipos_aprobador"],
            ["PENDIENTE_APROBACION"],
            filters
        )
    # Motorizado: ve las solicitudes APROBADAS de sus tipos para poder completarlas
    if ctx["tipos_motorizado"]:
        extra += repo.get_solicitudes_by_tipos(
            ctx["tipos_motorizado"],
            ["APROBADA"],
            filters
        )
    # Gerentes ven solicitudes pendientes de su aprobación
    if ctx.get("es_gerente"):
        todos_tipos = repo.get_tipos_solicitud()
        if todos_tipos:
            extra += repo.get_solicitudes_pendiente_gerente_para_usuario(
                ctx["user_id"], todos_tipos, filters
            )

    # Merge sin duplicados
    seen = set(ids_propias)
    merged = list(propias)
    for r in extra:
        if r["id"] not in seen:
            seen.add(r["id"])
            merged.append(r)

    merged.sort(key=lambda r: (str(r["fecha"]) if r["fecha"] else "", r["hora_inicio"] or ""))
    merged.reverse()
    return merged


def _fecha_es_pasada(fecha_val) -> bool:
    """Devuelve True si la fecha de la solicitud es anterior a hoy."""
    from datetime import date, datetime
    hoy = date.today()
    if fecha_val is None:
        return False
    if hasattr(fecha_val, "date"):           # datetime → date
        return fecha_val.date() < hoy
    if isinstance(fecha_val, date):
        return fecha_val < hoy
    try:                                      # string "YYYY-MM-DD"
        return datetime.strptime(str(fecha_val)[:10], "%Y-%m-%d").date() < hoy
    except Exception:
        return False


def puede_coordinar(solicitud, usuario_id, ctx):
    if solicitud["estado"] != "PENDIENTE_COORDINACION":
        return False
    if _fecha_es_pasada(solicitud.get("fecha")):
        return False          # fecha pasada → solo se puede reagendar
    return ctx["es_admin"] or solicitud["tipo"] in ctx["tipos_coordinador"]


def puede_aprobar(solicitud, usuario_id, ctx):
    return (
        ctx["es_admin"]
        or solicitud["tipo"] in ctx["tipos_aprobador"]
    ) and solicitud["estado"] == "PENDIENTE_APROBACION"


def puede_completar(solicitud, usuario_id, ctx):
    return (
        ctx["es_admin"]
        or solicitud["tipo"] in ctx["tipos_coordinador"]
        or solicitud["tipo"] in ctx["tipos_aprobador"]
        or solicitud["tipo"] in ctx.get("tipos_motorizado", [])
    ) and solicitud["estado"] == "APROBADA"


def puede_aprobar_gerente(solicitud, usuario_id, ctx):
    """El gerente asignado (o admin) puede aprobar PENDIENTE_APROBACION_GERENTE."""
    if solicitud["estado"] != "PENDIENTE_APROBACION_GERENTE":
        return False
    if ctx["es_admin"]:
        return True
    # El gerente asignado a la solicitud
    try:
        g_id = solicitud["gerente_id"]
    except (KeyError, TypeError):
        g_id = None
    if g_id and g_id == usuario_id:
        return True
    # Cualquier usuario con rol gerente también puede aprobar
    return ctx.get("es_gerente", False)


def puede_reagendar(solicitud, usuario_id, ctx):
    """El coordinador asignado (o admin) puede reagendar cualquier solicitud activa."""
    if solicitud["estado"] in ("COMPLETADA", "RECHAZADA"):
        return False
    return ctx["es_admin"] or solicitud["tipo"] in ctx["tipos_coordinador"]


def agrupar_por_seccion(rows):
    """Divide las filas en tres secciones para mostrar en la tabla."""
    reservadas  = [r for r in rows if r.get("estado") in ESTADOS_RESERVADAS]
    coordinadas = [r for r in rows if r.get("estado") in ESTADOS_COORDINADAS]
    atendidas   = [r for r in rows if r.get("estado") in ESTADOS_ATENDIDAS]
    return reservadas, coordinadas, atendidas


def puede_ver_detalle_completo(ctx):
    return (ctx["es_admin"] or ctx["tipos_coordinador"] or ctx["tipos_aprobador"]
            or ctx.get("es_gerente", False))


def estado_label(estado):
    return ESTADOS.get(estado, estado)


def estado_badge_class(estado):
    return {
        "PENDIENTE_COORDINACION":       "bg-warning text-dark",
        "PENDIENTE_APROBACION":         "bg-info text-dark",
        "PENDIENTE_APROBACION_GERENTE": "bg-primary",
        "APROBADA":                     "bg-success",
        "RECHAZADA":                    "bg-danger",
        "COMPLETADA":                   "bg-dark",
    }.get(estado, "bg-secondary")
