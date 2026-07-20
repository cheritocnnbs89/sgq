# -*- coding: utf-8 -*-
"""Pantalla de Frecuencias del módulo Obligaciones (Corrección de
arquitectura #3, 2026-07-15). Vive en el menú bajo Configuraciones ->
Parámetros Generales (pedido de Matías), pero el código/tablas son propios
de este módulo -- no reutiliza modules/parametros_generales por dentro,
solo comparte la ubicación de menú. Comparte el Blueprint `obligaciones_bp`
de routes_obligaciones.py (mismo prefijo /obligaciones)."""

from flask import render_template, request, redirect, url_for, flash, abort, session

from modules.auth.routes_auth import require_login, require_permission

from .routes_obligaciones import obligaciones_bp
from .obligaciones_constants import (
    ACTIVE_KEY_FRECUENCIAS,
    PERM_CONFIG,
    RECALCULO_LABELS,
    TRIGGER_LABELS,
    MAX_NOTIFICACIONES_POR_FRECUENCIA,
)
from . import obligaciones_services as service

_FORM_EXTRA_CTX = {
    "recalculo_labels": RECALCULO_LABELS,
    "trigger_labels": TRIGGER_LABELS,
    "max_notif": MAX_NOTIFICACIONES_POR_FRECUENCIA,
}


def _notif_map(notificaciones):
    """Normaliza la lista de notificaciones (venga de get_frecuencia_detalle
    -- destinatarios=[{usuario_id, email}] -- o de un POST fallido --
    destinatarios=[usuario_id, ...]) a un dict indexado por `orden`, para que
    el template solo tenga que hacer `notif_map.get(i)` por cada bloque 1-5."""
    out = {}
    for n in notificaciones or []:
        ids = set()
        for d in n.get("destinatarios") or []:
            ids.add(d["usuario_id"] if isinstance(d, dict) else d)
        out[n["orden"]] = {
            "tipo_trigger":     n.get("tipo_trigger"),
            "dias_antes":       n.get("dias_antes"),
            "dia_fijo_mes":     n.get("dia_fijo_mes"),
            "destinatario_ids": ids,
        }
    return out


@obligaciones_bp.route("/frecuencias", endpoint="lista_frecuencias")
@require_login
@require_permission(PERM_CONFIG, "ver")
def lista_frecuencias():
    frecuencias = service.list_frecuencias()
    return render_template(
        "obligaciones/obligaciones_frecuencias.html",
        frecuencias=frecuencias,
        active_page=ACTIVE_KEY_FRECUENCIAS,
    )


@obligaciones_bp.route("/frecuencias/nueva", methods=["GET", "POST"], endpoint="nueva_frecuencia")
@require_login
@require_permission(PERM_CONFIG, "crear")
def nueva_frecuencia():
    usuarios = service.get_usuarios_combo()

    if request.method == "POST":
        result = service.guardar_frecuencia_completa(None, request.form)
        flash(*result["flash"])

        if result["ok"]:
            return redirect(url_for("obligaciones.lista_frecuencias"))

        return render_template(
            "obligaciones/obligaciones_frecuencia_form.html",
            frecuencia=result.get("data", {}),
            notif_map=_notif_map(result.get("notificaciones", [])),
            usuarios=usuarios,
            mode="new",
            active_page=ACTIVE_KEY_FRECUENCIAS,
            **_FORM_EXTRA_CTX,
        )

    return render_template(
        "obligaciones/obligaciones_frecuencia_form.html",
        frecuencia={},
        notif_map={},
        usuarios=usuarios,
        mode="new",
        active_page=ACTIVE_KEY_FRECUENCIAS,
        **_FORM_EXTRA_CTX,
    )


@obligaciones_bp.route(
    "/frecuencias/<int:frecuencia_id>/editar", methods=["GET", "POST"], endpoint="editar_frecuencia"
)
@require_login
@require_permission(PERM_CONFIG, "editar")
def editar_frecuencia(frecuencia_id):
    detalle = service.get_frecuencia_detalle(frecuencia_id)
    if not detalle:
        abort(404)

    usuarios = service.get_usuarios_combo()

    if request.method == "POST":
        result = service.guardar_frecuencia_completa(frecuencia_id, request.form)
        flash(*result["flash"])

        if result["ok"]:
            return redirect(url_for("obligaciones.lista_frecuencias"))

        return render_template(
            "obligaciones/obligaciones_frecuencia_form.html",
            frecuencia=result.get("data", detalle["frecuencia"]),
            notif_map=_notif_map(result.get("notificaciones", detalle["notificaciones"])),
            usuarios=usuarios,
            mode="edit",
            frecuencia_id=frecuencia_id,
            active_page=ACTIVE_KEY_FRECUENCIAS,
            **_FORM_EXTRA_CTX,
        )

    return render_template(
        "obligaciones/obligaciones_frecuencia_form.html",
        frecuencia=detalle["frecuencia"],
        notif_map=_notif_map(detalle["notificaciones"]),
        usuarios=usuarios,
        mode="edit",
        frecuencia_id=frecuencia_id,
        active_page=ACTIVE_KEY_FRECUENCIAS,
        **_FORM_EXTRA_CTX,
    )


@obligaciones_bp.route(
    "/frecuencias/<int:frecuencia_id>/eliminar", methods=["POST"], endpoint="eliminar_frecuencia"
)
@require_login
@require_permission(PERM_CONFIG, "eliminar")
def eliminar_frecuencia(frecuencia_id):
    result = service.eliminar_frecuencia(frecuencia_id)
    flash(*result["flash"])
    return redirect(url_for("obligaciones.lista_frecuencias"))
