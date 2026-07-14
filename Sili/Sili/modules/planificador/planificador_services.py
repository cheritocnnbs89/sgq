# modules/planificador/planificador_services.py
# -*- coding: utf-8 -*-
"""Lógica de negocio para el módulo Planificador."""

from flask import session
from . import planificador_repository as repo
from .planificador_constants import (
    ROL_COORDINADOR, ROL_APROBADOR, ROL_MOTORIZADO, ROL_GERENTE_PRESUPUESTO,
    ROLES_ADMIN, ROLES_GERENTE, ESTADOS,
    ESTADOS_RESERVADAS, ESTADOS_COORDINADAS, ESTADOS_POR_COMPLETAR, ESTADOS_ATENDIDAS,
)


def debe_autoaprobar_jefe_vuelo(rol_usuario, roles_autoaprobar):
    """True si el rol del solicitante está configurado para saltar la
    aprobación del jefe directo en solicitudes de Vuelo."""
    if not rol_usuario or not roles_autoaprobar:
        return False
    rol_norm = rol_usuario.strip().lower()
    return rol_norm in {r.strip().lower() for r in roles_autoaprobar}


def get_user_context(usuario_id, rol):
    """
    Devuelve qué tipos puede coordinar/aprobar el usuario actual.
    """
    config_rows = repo.get_config_for_user(usuario_id)
    tipos_coordinador = [r["tipo"] for r in config_rows if r["rol_config"] == ROL_COORDINADOR]
    tipos_aprobador   = [r["tipo"] for r in config_rows if r["rol_config"] == ROL_APROBADOR]
    tipos_motorizado  = [r["tipo"] for r in config_rows if r["rol_config"] == ROL_MOTORIZADO]
    tipos_gg_vuelo    = [r["tipo"] for r in config_rows if r["rol_config"] == ROL_GERENTE_PRESUPUESTO]
    es_admin          = rol in ROLES_ADMIN
    es_gerente        = rol.lower() in ROLES_GERENTE if rol else False
    return {
        "tipos_coordinador": tipos_coordinador,
        "tipos_aprobador":   tipos_aprobador,
        "tipos_motorizado":  tipos_motorizado,
        "tipos_gg_vuelo":    tipos_gg_vuelo,
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
            ["PENDIENTE_COORDINACION", "PENDIENTE_INFO_VUELO", "PENDIENTE_LIQUIDACION"],
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
    # Gerentes ven solicitudes PENDIENTE_APROBACION_GERENTE (flujo general)
    if ctx.get("es_gerente"):
        todos_tipos = repo.get_tipos_solicitud()
        if todos_tipos:
            extra += repo.get_solicitudes_pendiente_gerente_para_usuario(
                ctx["user_id"], todos_tipos, filters
            )

    # Jefe directo: ve Vuelo en PENDIENTE_APROBACION_JEFE donde gerente_id = este usuario
    extra += repo.get_solicitudes_pendiente_jefe(ctx["user_id"], filters)

    # GG de Vuelos: ve PENDIENTE_APROBACION_GG_VUELO para los tipos que tiene configurado
    if ctx.get("tipos_gg_vuelo"):
        extra += repo.get_solicitudes_pendiente_gg_vuelo(ctx["tipos_gg_vuelo"], filters)

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
    if solicitud.get("tipo") == "Vuelo":
        return False  # Vuelo usa puede_completar_vuelo, no coordinar normal
    if _fecha_es_pasada(solicitud.get("fecha")):
        return False
    return ctx["es_admin"] or solicitud["tipo"] in ctx["tipos_coordinador"]


def puede_aprobar(solicitud, usuario_id, ctx):
    return (
        ctx["es_admin"]
        or solicitud["tipo"] in ctx["tipos_aprobador"]
    ) and solicitud["estado"] == "PENDIENTE_APROBACION"


def puede_completar(solicitud, usuario_id, ctx):
    if solicitud.get("tipo") == "Vuelo":
        return False  # Vuelo usa puede_completar_vuelo
    return (
        ctx["es_admin"]
        or solicitud["tipo"] in ctx["tipos_coordinador"]
        or solicitud["tipo"] in ctx["tipos_aprobador"]
        or solicitud["tipo"] in ctx.get("tipos_motorizado", [])
    ) and solicitud["estado"] == "APROBADA"


def puede_aprobar_jefe_vuelo(solicitud, usuario_id, ctx):
    """Jefe directo aprueba/rechaza solicitud de Vuelo recién creada."""
    if solicitud.get("estado") != "PENDIENTE_APROBACION_JEFE":
        return False
    if ctx["es_admin"]:
        return True
    return solicitud.get("gerente_id") == usuario_id


def puede_aprobar_gg_vuelo(solicitud, usuario_id, ctx):
    """GG de Vuelos aprueba cuando no hay presupuesto."""
    if solicitud.get("estado") != "PENDIENTE_APROBACION_GG_VUELO":
        return False
    if ctx["es_admin"]:
        return True
    return solicitud.get("tipo") in ctx.get("tipos_gg_vuelo", [])


def puede_cotizar_vuelo(solicitud, usuario_id, ctx):
    """Coordinador ingresa el valor cotizado del pasaje (pasa a aprobación GG)."""
    if solicitud.get("tipo") != "Vuelo":
        return False
    if solicitud.get("estado") != "PENDIENTE_COORDINACION":
        return False
    return ctx["es_admin"] or solicitud.get("tipo") in ctx["tipos_coordinador"]


def puede_completar_vuelo(solicitud, usuario_id, ctx):
    """Coordinador registra info del vuelo y adjuntos (pasa a COORDINADA)."""
    if solicitud.get("tipo") != "Vuelo":
        return False
    if solicitud.get("estado") != "PENDIENTE_INFO_VUELO":
        return False
    return ctx["es_admin"] or solicitud.get("tipo") in ctx["tipos_coordinador"]


def puede_marcar_realizado_vuelo(solicitud, usuario_id, ctx):
    """Solicitante confirma que realizó el vuelo (pasa a PENDIENTE_LIQUIDACION)."""
    if solicitud.get("tipo") != "Vuelo":
        return False
    if solicitud.get("estado") != "COORDINADA":
        return False
    es_solicitante = solicitud.get("solicitante_id") == usuario_id
    return ctx["es_admin"] or es_solicitante


def puede_liquidar_vuelo(solicitud, usuario_id, ctx):
    """Coordinador ingresa costos reales por tipo de gasto (pasa a COMPLETADA)."""
    if solicitud.get("tipo") != "Vuelo":
        return False
    if solicitud.get("estado") != "PENDIENTE_LIQUIDACION":
        return False
    es_coordinador = solicitud.get("tipo") in ctx["tipos_coordinador"]
    return ctx["es_admin"] or es_coordinador


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


def puede_eliminar(solicitud, usuario_id, ctx):
    """
    Reglas:
    - COMPLETADA: nadie puede eliminar.
    - COORDINADA / PENDIENTE_LIQUIDACION: solo admin.
    - Admin: puede en cualquier otro estado.
    - Coordinador: puede si estado NO es APROBADA ni COMPLETADA.
    - Aprobador: puede si estado NO es COMPLETADA.
    - Solicitante (usuario normal): solo si estado es PENDIENTE_COORDINACION y es su propia solicitud.
    """
    estado = solicitud["estado"]
    if estado == "COMPLETADA":
        return False
    if estado in ("COORDINADA", "PENDIENTE_LIQUIDACION"):
        return ctx["es_admin"]
    if ctx["es_admin"]:
        return True
    if solicitud["tipo"] in ctx["tipos_coordinador"]:
        return estado not in ("APROBADA", "COMPLETADA")
    if solicitud["tipo"] in ctx["tipos_aprobador"]:
        return estado != "COMPLETADA"
    # Usuario normal: solo la propia solicitud en PENDIENTE_COORDINACION
    if solicitud.get("solicitante_id") == usuario_id:
        return estado == "PENDIENTE_COORDINACION"
    return False


def puede_reagendar(solicitud, usuario_id, ctx):
    """El coordinador asignado (o admin) puede reagendar solicitudes activas no iniciadas."""
    if solicitud["estado"] in ("COMPLETADA", "RECHAZADA", "COORDINADA", "PENDIENTE_LIQUIDACION"):
        return False
    return ctx["es_admin"] or solicitud["tipo"] in ctx["tipos_coordinador"]


def agrupar_por_seccion(rows):
    """Divide las filas en cuatro secciones para mostrar en la tabla."""
    def _va_en_reservadas(r):
        if r.get("estado") not in ESTADOS_RESERVADAS:
            return False
        # El Gerente de Presupuesto ya la ve (accionable) en "Por aprobar";
        # no aporta verla también pasivamente en "Reservadas".
        if r.get("estado") == "PENDIENTE_APROBACION_GG_VUELO" and r.get("puede_aprobar_gg_vuelo"):
            return False
        return True

    reservadas     = [r for r in rows if _va_en_reservadas(r)]
    coordinadas    = [r for r in rows if r.get("estado") in ESTADOS_COORDINADAS]
    por_completar  = [r for r in rows if r.get("estado") in ESTADOS_POR_COMPLETAR]
    atendidas      = [r for r in rows if r.get("estado") in ESTADOS_ATENDIDAS]
    return reservadas, coordinadas, por_completar, atendidas


def puede_ver_detalle_completo(ctx):
    return (ctx["es_admin"] or ctx["tipos_coordinador"] or ctx["tipos_aprobador"]
            or ctx.get("es_gerente", False))


def estado_label(estado):
    return ESTADOS.get(estado, estado)


def estado_badge_class(estado):
    return {
        "PENDIENTE_APROBACION_JEFE":     "bg-warning text-dark",
        "PENDIENTE_APROBACION_GG_VUELO": "bg-orange text-dark",
        "PENDIENTE_COORDINACION":        "bg-warning text-dark",
        "PENDIENTE_INFO_VUELO":          "bg-warning text-dark",
        "PENDIENTE_APROBACION":          "bg-info text-dark",
        "PENDIENTE_APROBACION_GERENTE":  "bg-primary",
        "APROBADA":                      "bg-success",
        "RECHAZADA":                     "bg-danger",
        "COMPLETADA":                    "bg-dark",
    }.get(estado, "bg-secondary")
