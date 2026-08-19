# modules/cartera/routes_cartera.py
# -*- coding: utf-8 -*-
#
# Primera versión: solo lectura sobre cartera_facturas (la llena el
# pipeline de rutina/rutina/cartera/ vía SAP, no este módulo).
# A futuro: ficha de gestión de cobro, notificaciones, maestro de
# clientes — ver claude/analisis-dias-credito.md en el proyecto "Días de
# Credito" para el resto del roadmap.

from flask import Blueprint, render_template

from modules.auth.routes_auth import require_login, require_permission

from .cartera_constants import ACTIVE_KEY, PERM_BASE
from . import cartera_services as service

cartera_bp = Blueprint("cartera", __name__, url_prefix="/cartera")


@cartera_bp.route("/", endpoint="lista_facturas")
@require_login
@require_permission(PERM_BASE, "ver")
def lista_facturas():
    rows, filters = service.list_facturas()
    resumen = service.get_resumen()

    return render_template(
        "cartera/cartera_lista.html",
        rows=rows,
        f=filters,
        resumen=resumen,
        active_page=ACTIVE_KEY,
    )


def register_cartera_routes(app):
    app.register_blueprint(cartera_bp)
