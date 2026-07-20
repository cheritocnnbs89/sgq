# modules/empresas/routes_empresas.py
# -*- coding: utf-8 -*-

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from pyodbc import IntegrityError

from modules.auth.routes_auth import require_login, require_permission

from .empresas_constants import ACTIVE_KEY, PERM_BASE
from . import empresas_services as service

empresas_bp = Blueprint("empresas", __name__, url_prefix="/empresas")


@empresas_bp.route("/", endpoint="lista_empresas")
@require_login
@require_permission(PERM_BASE, "ver")
def lista_empresas():
    rows, filters = service.list_empresas()

    return render_template(
        "empresas/empresas_lista.html",
        rows=rows,
        f=filters,
        active_page=ACTIVE_KEY,
    )


@empresas_bp.route("/nueva", methods=["GET", "POST"], endpoint="nueva_empresa")
@require_login
@require_permission(PERM_BASE, "crear")
def nueva_empresa():
    if request.method == "POST":
        data = service.normalize_empresa_form(request.form)
        is_valid, error_message = service.validate_empresa_data(data)

        if not is_valid:
            flash(error_message, "warning")
            return render_template(
                "empresas/empresas_form.html",
                data=data,
                mode="new",
                active_page=ACTIVE_KEY,
            )

        try:
            service.create_empresa(data)
            flash("Empresa creada correctamente.", "success")
            return redirect(url_for("empresas.lista_empresas"))
        except IntegrityError:
            flash("El RUC ya existe. Verifique.", "danger")
            return render_template(
                "empresas/empresas_form.html",
                data=data,
                mode="new",
                active_page=ACTIVE_KEY,
            )

    return render_template(
        "empresas/empresas_form.html",
        data={},
        mode="new",
        active_page=ACTIVE_KEY,
    )


@empresas_bp.route("/<int:empresa_id>/editar", methods=["GET", "POST"], endpoint="editar_empresa")
@require_login
@require_permission(PERM_BASE, "editar")
def editar_empresa(empresa_id):
    row = service.get_empresa(empresa_id)

    if not row:
        abort(404)

    if request.method == "POST":
        data = service.normalize_empresa_form(request.form)
        is_valid, error_message = service.validate_empresa_data(data)

        if not is_valid:
            flash(error_message, "warning")
            return render_template(
                "empresas/empresas_form.html",
                data=data,
                mode="edit",
                active_page=ACTIVE_KEY,
            )

        try:
            service.update_empresa(empresa_id, data)
            flash("Empresa actualizada.", "success")
            return redirect(url_for("empresas.lista_empresas"))
        except IntegrityError:
            flash("El RUC ya existe en otra empresa.", "danger")
            return render_template(
                "empresas/empresas_form.html",
                data=data,
                mode="edit",
                active_page=ACTIVE_KEY,
            )

    return render_template(
        "empresas/empresas_form.html",
        data=row,
        mode="edit",
        active_page=ACTIVE_KEY,
    )


@empresas_bp.route("/<int:empresa_id>/eliminar", methods=["POST"], endpoint="eliminar_empresa")
@require_login
@require_permission(PERM_BASE, "eliminar")
def eliminar_empresa(empresa_id):
    service.delete_empresa(empresa_id)
    flash("Empresa eliminada.", "success")
    return redirect(url_for("empresas.lista_empresas"))


def register_empresas_routes(app):
    app.register_blueprint(empresas_bp)