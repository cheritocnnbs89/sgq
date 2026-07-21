# -*- coding: utf-8 -*-
"""Pantalla de Tipos del modulo Obligaciones (Correccion de arquitectura #4,
2026-07-20). Vive en el menu bajo Configuraciones (mismo submenu que
Frecuencias), pero -- a diferencia de Frecuencias -- los DATOS siguen en
param_groups/param_values (tabla compartida de SGQ), acotados siempre a
TIPOS_GROUP_ID (5796, "Obligaciones - Tipos"). Antes esta pantalla vivia en
modules/parametros_generales/ con el permiso generico 'parametros', lo que
le daba a admin_obligaciones acceso a los 18 grupos de otros modulos --
ver PLAN.md. Ahora la ruta y el permiso ('obligaciones') son propios de este
modulo; el codigo que lee/escribe param_values se REUSA de
modules/parametros_generales/parameters_services.py (ya acepta group_id como
parametro generico) -- no se duplica esa logica."""

from flask import render_template, request, redirect, url_for, flash, abort

from modules.auth.routes_auth import require_login, require_permission

from .routes_obligaciones import obligaciones_bp
from .obligaciones_constants import ACTIVE_KEY_TIPOS, PERM_CONFIG, TIPOS_GROUP_ID
from modules.parametros_generales import parameters_services as param_service


@obligaciones_bp.route("/tipos", endpoint="lista_tipos")
@require_login
@require_permission(PERM_CONFIG, "ver")
def lista_tipos():
    tipos = param_service.obtener_arbol_valores(TIPOS_GROUP_ID)
    return render_template(
        "obligaciones/obligaciones_tipos.html",
        tipos=tipos,
        active_page=ACTIVE_KEY_TIPOS,
    )


@obligaciones_bp.route("/tipos/nuevo", methods=["GET", "POST"], endpoint="nuevo_tipo")
@require_login
@require_permission(PERM_CONFIG, "crear")
def nuevo_tipo():
    if request.method == "POST":
        result = param_service.crear_valor(
            group_id=TIPOS_GROUP_ID,
            nombre_raw=request.form.get("nombre"),
            valor_raw=None,
        )
        flash(*result["flash"])

        if result["ok"]:
            return redirect(url_for("obligaciones.lista_tipos"))

        return render_template(
            "obligaciones/obligaciones_tipo_form.html",
            tipo={"nombre": request.form.get("nombre", "")},
            mode="new",
            active_page=ACTIVE_KEY_TIPOS,
        )

    return render_template(
        "obligaciones/obligaciones_tipo_form.html",
        tipo={},
        mode="new",
        active_page=ACTIVE_KEY_TIPOS,
    )


@obligaciones_bp.route("/tipos/<int:tipo_id>/editar", methods=["GET", "POST"], endpoint="editar_tipo")
@require_login
@require_permission(PERM_CONFIG, "editar")
def editar_tipo(tipo_id):
    item = param_service.obtener_item(TIPOS_GROUP_ID, tipo_id)
    if not item:
        abort(404)

    if request.method == "POST":
        result = param_service.editar_valor(
            group_id=TIPOS_GROUP_ID,
            item_id=tipo_id,
            nombre_raw=request.form.get("nombre"),
            valor_raw=None,
        )
        flash(*result["flash"])

        if result.get("not_found"):
            abort(404)

        if result["ok"]:
            return redirect(url_for("obligaciones.lista_tipos"))

        return render_template(
            "obligaciones/obligaciones_tipo_form.html",
            tipo=result.get("item", item),
            mode="edit",
            tipo_id=tipo_id,
            active_page=ACTIVE_KEY_TIPOS,
        )

    return render_template(
        "obligaciones/obligaciones_tipo_form.html",
        tipo=item,
        mode="edit",
        tipo_id=tipo_id,
        active_page=ACTIVE_KEY_TIPOS,
    )


@obligaciones_bp.route("/tipos/<int:tipo_id>/eliminar", methods=["POST"], endpoint="eliminar_tipo")
@require_login
@require_permission(PERM_CONFIG, "eliminar")
def eliminar_tipo(tipo_id):
    result = param_service.eliminar_valor(TIPOS_GROUP_ID, tipo_id)
    flash(*result["flash"])
    return redirect(url_for("obligaciones.lista_tipos"))
