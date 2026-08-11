# -*- coding: utf-8 -*-
"""Pantalla de Tipos de Obligación del módulo Obligaciones (Corrección de
arquitectura #8, 2026-08-07). Vive en el menú bajo Configuraciones ->
Parámetros Generales (mismo lugar que Frecuencias), pero el código/tabla son
propios de este módulo (oblig_tipos_obligacion) -- no reutiliza
modules/parametros_generales por dentro. Comparte el Blueprint
`obligaciones_bp` de routes_obligaciones.py (mismo prefijo /obligaciones).
Clonado 1:1 del patrón de routes_obligaciones_frecuencias.py."""

from flask import render_template, request, redirect, url_for, flash, abort

from modules.auth.routes_auth import require_login, require_permission

from .routes_obligaciones import obligaciones_bp
from .obligaciones_constants import ACTIVE_KEY_TIPOS, PERM_CONFIG
from . import obligaciones_services as service


@obligaciones_bp.route("/tipos", endpoint="lista_tipos")
@require_login
@require_permission(PERM_CONFIG, "ver")
def lista_tipos():
    tipos = service.list_tipos_todos()
    return render_template(
        "obligaciones/obligaciones_tipos.html",
        tipos=tipos,
        active_page=ACTIVE_KEY_TIPOS,
    )


@obligaciones_bp.route("/tipos/nuevo", methods=["GET", "POST"], endpoint="nuevo_tipo")
@require_login
@require_permission(PERM_CONFIG, "crear")
def nuevo_tipo():
    # 2026-08-11: catalogo completo de entidades para el checklist -- un tipo
    # nuevo arranca sin ninguna marcada (entidad_ids_seleccionadas vacio).
    entidades_todas = service.list_entidades_todas()

    if request.method == "POST":
        result = service.guardar_tipo(None, request.form)
        flash(*result["flash"])

        if result["ok"]:
            return redirect(url_for("obligaciones.lista_tipos"))

        return render_template(
            "obligaciones/obligaciones_tipo_form.html",
            tipo=result.get("data", {}),
            mode="new",
            active_page=ACTIVE_KEY_TIPOS,
            entidades_todas=entidades_todas,
            entidad_ids_seleccionadas=[int(v) for v in request.form.getlist("entidades") if v.strip()],
        )

    return render_template(
        "obligaciones/obligaciones_tipo_form.html",
        tipo={},
        mode="new",
        active_page=ACTIVE_KEY_TIPOS,
        entidades_todas=entidades_todas,
        entidad_ids_seleccionadas=[],
    )


@obligaciones_bp.route("/tipos/<int:tipo_id>/editar", methods=["GET", "POST"], endpoint="editar_tipo")
@require_login
@require_permission(PERM_CONFIG, "editar")
def editar_tipo(tipo_id):
    tipo = service.get_tipo_detalle(tipo_id)
    if not tipo:
        abort(404)

    # 2026-08-11: catalogo completo de entidades + cuales ya estan vinculadas
    # a este tipo -- usado para premarcar los checkboxes.
    entidades_todas = service.list_entidades_todas()

    if request.method == "POST":
        result = service.guardar_tipo(tipo_id, request.form)
        flash(*result["flash"])

        if result["ok"]:
            return redirect(url_for("obligaciones.lista_tipos"))

        return render_template(
            "obligaciones/obligaciones_tipo_form.html",
            tipo=result.get("data", tipo),
            mode="edit",
            tipo_id=tipo_id,
            active_page=ACTIVE_KEY_TIPOS,
            entidades_todas=entidades_todas,
            entidad_ids_seleccionadas=[int(v) for v in request.form.getlist("entidades") if v.strip()],
        )

    entidad_ids_seleccionadas = service.list_entidad_ids_por_tipo(tipo_id)
    return render_template(
        "obligaciones/obligaciones_tipo_form.html",
        tipo=tipo,
        mode="edit",
        tipo_id=tipo_id,
        active_page=ACTIVE_KEY_TIPOS,
        entidades_todas=entidades_todas,
        entidad_ids_seleccionadas=entidad_ids_seleccionadas,
    )


@obligaciones_bp.route("/tipos/<int:tipo_id>/toggle", methods=["POST"], endpoint="toggle_tipo")
@require_login
@require_permission(PERM_CONFIG, "editar")
def toggle_tipo(tipo_id):
    tipo = service.get_tipo_detalle(tipo_id)
    if not tipo:
        abort(404)
    nuevo_estado = not bool(tipo["activo"])
    result = service.toggle_tipo_activo(tipo_id, nuevo_estado)
    flash(*result["flash"])
    return redirect(url_for("obligaciones.lista_tipos"))
