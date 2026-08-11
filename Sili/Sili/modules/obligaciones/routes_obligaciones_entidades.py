# -*- coding: utf-8 -*-
"""Pantalla de Entidades Reguladoras del módulo Obligaciones (Corrección de
arquitectura #8, 2026-08-07). Vive en el menú bajo Configuraciones ->
Parámetros Generales (mismo lugar que Frecuencias/Tipos), pero el código/tabla
son propios de este módulo (oblig_entidades_reguladoras) -- no reutiliza
modules/parametros_generales ni modules/routes_terceros.py por dentro.
Comparte el Blueprint `obligaciones_bp` de routes_obligaciones.py (mismo
prefijo /obligaciones). Clonado 1:1 del patrón de routes_obligaciones_frecuencias.py."""

from flask import render_template, request, redirect, url_for, flash, abort

from modules.auth.routes_auth import require_login, require_permission

from .routes_obligaciones import obligaciones_bp
from .obligaciones_constants import ACTIVE_KEY_ENTIDADES, PERM_CONFIG
from . import obligaciones_services as service


@obligaciones_bp.route("/entidades", endpoint="lista_entidades")
@require_login
@require_permission(PERM_CONFIG, "ver")
def lista_entidades():
    entidades = service.list_entidades_todas()
    return render_template(
        "obligaciones/obligaciones_entidades.html",
        entidades=entidades,
        active_page=ACTIVE_KEY_ENTIDADES,
    )


@obligaciones_bp.route("/entidades/nueva", methods=["GET", "POST"], endpoint="nueva_entidad")
@require_login
@require_permission(PERM_CONFIG, "crear")
def nueva_entidad():
    if request.method == "POST":
        result = service.guardar_entidad(None, request.form)
        flash(*result["flash"])

        if result["ok"]:
            return redirect(url_for("obligaciones.lista_entidades"))

        return render_template(
            "obligaciones/obligaciones_entidad_form.html",
            entidad=result.get("data", {}),
            mode="new",
            active_page=ACTIVE_KEY_ENTIDADES,
        )

    return render_template(
        "obligaciones/obligaciones_entidad_form.html",
        entidad={},
        mode="new",
        active_page=ACTIVE_KEY_ENTIDADES,
    )


@obligaciones_bp.route(
    "/entidades/<int:entidad_id>/editar", methods=["GET", "POST"], endpoint="editar_entidad"
)
@require_login
@require_permission(PERM_CONFIG, "editar")
def editar_entidad(entidad_id):
    entidad = service.get_entidad_detalle(entidad_id)
    if not entidad:
        abort(404)

    if request.method == "POST":
        result = service.guardar_entidad(entidad_id, request.form)
        flash(*result["flash"])

        if result["ok"]:
            return redirect(url_for("obligaciones.lista_entidades"))

        return render_template(
            "obligaciones/obligaciones_entidad_form.html",
            entidad=result.get("data", entidad),
            mode="edit",
            entidad_id=entidad_id,
            active_page=ACTIVE_KEY_ENTIDADES,
        )

    return render_template(
        "obligaciones/obligaciones_entidad_form.html",
        entidad=entidad,
        mode="edit",
        entidad_id=entidad_id,
        active_page=ACTIVE_KEY_ENTIDADES,
    )


@obligaciones_bp.route("/entidades/<int:entidad_id>/toggle", methods=["POST"], endpoint="toggle_entidad")
@require_login
@require_permission(PERM_CONFIG, "editar")
def toggle_entidad(entidad_id):
    entidad = service.get_entidad_detalle(entidad_id)
    if not entidad:
        abort(404)
    nuevo_estado = not bool(entidad["activo"])
    result = service.toggle_entidad_activo(entidad_id, nuevo_estado)
    flash(*result["flash"])
    return redirect(url_for("obligaciones.lista_entidades"))
