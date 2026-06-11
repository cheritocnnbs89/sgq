# app.py
# -*- coding: utf-8 -*-

# ==========================================================
# Archivo principal de la aplicación Flask.
# Su responsabilidad es orquestar la creación de la app
# y delegar funcionalidades complementarias a app_core.
# ==========================================================
  
import os
from pathlib import Path
from flask import Flask, render_template
from flask_wtf.csrf import CSRFProtect
from jinja2 import ChoiceLoader, FileSystemLoader

from modules.config import configure_app
from modules.db import init_app as db_init_app
from modules.security import init_security

from modules.app_core.app_request import MyRequest, configure_request_settings
from modules.app_core.app_perf import register_perf_hooks
from modules.app_core.app_errors import register_error_handlers
from modules.app_core.app_startup import run_startup_tasks
from modules.app_core.app_routes import register_all_routes
from modules.app_core.app_menu import register_context_processors
from modules.app_core.app_gateway import register_gateway
from modules.app_core.app_logging import (
    configure_app_logging,
    attach_file_logger, 
    log_registered_routes,
)
from modules.app_core.app_scheduler import start_scheduler_if_enabled, start_email_poller_if_enabled


# ----------------------------------------------------------
# Extensión global CSRF para proteger formularios y requests
# sensibles de la aplicación.
# ----------------------------------------------------------
csrf = CSRFProtect()


def create_app():
    # ------------------------------------------------------
    # Crea la instancia principal Flask.
    # ------------------------------------------------------
    app = Flask(__name__, static_folder="static", template_folder="templates")

    # ------------------------------------------------------
    # Permite buscar templates tanto en templates/ como en
    # la raíz del proyecto, respetando tu lógica actual.
    # ------------------------------------------------------
    app.jinja_loader = ChoiceLoader([
        app.jinja_loader,
        FileSystemLoader(str(Path(app.root_path).parent))
    ])

    # ------------------------------------------------------
    # Configura la clase Request personalizada.
    # ------------------------------------------------------
    app.request_class = MyRequest

    # ------------------------------------------------------
    # Carga configuración base de la aplicación.
    # Aquí también se cargan las variables de WhatsApp desde .env
    # mediante modules/config.py.
    # ------------------------------------------------------
    configure_app(app)

    # ------------------------------------------------------
    # Carga límites de request y valores globales auxiliares.
    # ------------------------------------------------------
    configure_request_settings(app)

    # ------------------------------------------------------
    # Inicializa extensiones y capa de seguridad.
    # ------------------------------------------------------
    csrf.init_app(app)
    db_init_app(app)
    init_security(app)

    # ------------------------------------------------------
    # Hooks globales de monitoreo.
    # ------------------------------------------------------
    register_perf_hooks(app)

    # ------------------------------------------------------
    # Manejo centralizado de errores comunes.
    # ------------------------------------------------------
    register_error_handlers(app)

    # ------------------------------------------------------
    # Tareas de arranque: DB, gastos, menú y permisos.
    # ------------------------------------------------------
    run_startup_tasks(app)

    # ------------------------------------------------------
    # Registro de blueprints y endpoints funcionales existentes.
    # ------------------------------------------------------
    register_all_routes(app)


    # ------------------------------------------------------
    # WHATSAPP CLOUD API - NUEVO
    #
    # Registro del webhook de WhatsApp.
    #
    # Este blueprint expone:
    #
    #   GET  /whatsapp/webhook
    #        Meta usa este endpoint para validar el webhook.
    #
    #   POST /whatsapp/webhook
    #        Meta enviará aquí los mensajes recibidos por WhatsApp.
    #
    # IMPORTANTE:
    # Se usa url_prefix="/whatsapp" porque dentro del blueprint
    # la ruta está definida como "/webhook".
    #
    # Resultado final:
    #   /whatsapp + /webhook = /whatsapp/webhook
    #
    # También se exime de CSRF porque Meta enviará requests externas
    # y no tendrá token CSRF de nuestra aplicación.
    # ------------------------------------------------------
    from modules.whatsapp.webhook import whatsapp_bp

    app.register_blueprint(whatsapp_bp, url_prefix="/whatsapp")
    csrf.exempt(whatsapp_bp)

    # ------------------------------------------------------
    # Inyección de menú y helpers de permisos para templates.
    # ------------------------------------------------------
    import modules.app_core.app_menu as app_menu_mod

    print(">>> APP_MENU IMPORTADO DESDE:", app_menu_mod.__file__, flush=True)
    print(">>> REGISTER_CONTEXT_PROCESSORS:", register_context_processors, flush=True)

    register_context_processors(app)

    print(">>> REGISTER_CONTEXT_PROCESSORS EJECUTADO", flush=True)

    # ------------------------------------------------------
    # Activación del gateway de enmascaramiento de rutas GET.
    # ------------------------------------------------------
    register_gateway(app)

    # ------------------------------------------------------
    # Configuración del logging principal.
    # ------------------------------------------------------
    configure_app_logging(app)

    # ------------------------------------------------------
    # Arranque opcional del scheduler.
    # ------------------------------------------------------
    print(">>> Intentando arrancar scheduler...")
    start_scheduler_if_enabled(app)
    print(">>> Scheduler llamado")

    # ------------------------------------------------------
    # Poller de correos soporteti@quimpac.com.ec (cada 2 min)
    # ------------------------------------------------------
    start_email_poller_if_enabled(app)

    # ------------------------------------------------------
    # Registro de rutas cargadas al iniciar.
    # ------------------------------------------------------
    log_registered_routes(app)

    # ------------------------------------------------------
    # Ruta sencilla para vista BI.
    # ------------------------------------------------------
    @app.route("/bi")
    def bi():
        return render_template("BI.html")

    # ------------------------------------------------------
    # Endpoint para recibir reportes CSP.
    # ------------------------------------------------------
    import json
    import logging

    @app.route("/csp-report", methods=["POST"])
    @csrf.exempt
    def csp_report():
        logger = logging.getLogger(__name__)

        raw = request.get_data(as_text=True)
        logger.warning("CSP content-type: %s", request.content_type)
        logger.warning("CSP raw report: %s", raw)

        try:
            data = json.loads(raw) if raw else None
        except Exception:
            data = None

        logger.warning("CSP parsed report: %s", data)

        return "", 204

    return app


# ==========================================================
# Instancia WSGI principal de la aplicación.
# ==========================================================
app = create_app()

# ----------------------------------------------------------
# Alias build_only para compatibilidad con url_for.
# ----------------------------------------------------------
app.add_url_rule(
    "/reembolsos/gastos/nuevo",
    endpoint="nuevo_gasto",
    build_only=True
)

app.add_url_rule(
    "/reembolsos/gastos/<int:gasto_id>/editar",
    endpoint="editar_gasto",
    build_only=True
)

# ----------------------------------------------------------
# Configuración por defecto de carpetas de carga XML masiva.
# ----------------------------------------------------------
app.config.setdefault(
    "XML_BULK_FOLDER",
    r"C:\Sili\uploads\xml_masivos_pendientes"
)

app.config.setdefault(
    "XML_BULK_PROCESADOS",
    r"C:\Sili\uploads\xml_masivos_procesados"
)

# ----------------------------------------------------------
# Habilita logger a archivo rotativo.
# ----------------------------------------------------------
attach_file_logger(app)


# ==========================================================
# Punto de entrada local para desarrollo o ejecución directa.
# ==========================================================
if __name__ == "__main__":
    with app.app_context():
        print("\n== Rutas registradas ==")
        for r in app.url_map.iter_rules():
            print(r.endpoint, "->", r.rule, "  methods=", r.methods)

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False,
        threaded=True
    )