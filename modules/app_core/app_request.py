# modules/app_core/app_request.py
# ==========================================================
# Configuración de Request y límites de carga de la app.
# Aquí se centralizan ajustes globales del request HTTP.
# ==========================================================

from flask import Request


class MyRequest(Request):
    # ------------------------------------------------------
    # Permite mayor cantidad de partes en formularios.
    # Útil para formularios largos o con muchos campos.
    # ------------------------------------------------------
    max_form_parts = 5000


def configure_request_settings(app):
    # ------------------------------------------------------
    # URL pública base de la aplicación.
    # Puede servir para generación de links absolutos.
    # ------------------------------------------------------
    app.config["PUBLIC_BASE_URL"] = "http://127.0.0.1:5000"

    # ------------------------------------------------------
    # Ruta del navegador Chrome usada por procesos auxiliares.
    # ------------------------------------------------------
    app.config["CHROME_PATH"] = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

    # ------------------------------------------------------
    # Tamaño máximo permitido por request.
    # ------------------------------------------------------
    app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024

    # ------------------------------------------------------
    # Memoria máxima para parsear formularios.
    # ------------------------------------------------------
    app.config["MAX_FORM_MEMORY_SIZE"] = 64 * 1024 * 1024