# modules/app_core/app_errors.py
# ==========================================================
# Handlers globales de error de la aplicación.
# Centraliza errores comunes como CSRF y payload grande.
# ==========================================================

from flask import flash, redirect, url_for
from flask_wtf.csrf import CSRFError
from werkzeug.exceptions import RequestEntityTooLarge


def register_error_handlers(app):
    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        # --------------------------------------------------
        # Maneja requests inválidos por token CSRF faltante,
        # inválido o expirado.
        # --------------------------------------------------
        flash(
            "La sesión del formulario expiró o la solicitud no es válida. Intente nuevamente.",
            "warning"
        )
        return redirect(url_for("login")), 400

    @app.errorhandler(RequestEntityTooLarge)
    def handle_413(e):
        # --------------------------------------------------
        # Maneja cargas excesivas de archivos o formularios.
        # --------------------------------------------------
        flash(
            "La carga de archivos XML excede el límite permitido. "
            "Por favor súbelos en varios grupos más pequeños.",
            "warning"
        )
        return redirect(url_for("facturas_xml_list"))