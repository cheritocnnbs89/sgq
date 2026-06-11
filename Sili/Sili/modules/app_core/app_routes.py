# modules/app_core/app_routes.py
# ==========================================================
# Registro centralizado de blueprints y funciones register_*.
# Mantiene limpio el app.py y conserva el patrón tolerante
# que ya usas para módulos opcionales.
# ==========================================================

def register_all_routes(app):
    # ------------------------------------------------------
    # Imports tolerantes para que la app no falle completa
    # si algún módulo opcional no carga.
    # ------------------------------------------------------
    try:
        from modules.auth.routes_auth import register_auth_routes
    except Exception:
        register_auth_routes = None

    try:
        from modules import routes_reclamos
    except Exception:
        routes_reclamos = None

    try:
        from modules.users.user_http import register_user_routes
    except Exception:
        register_user_routes = None

    from modules.routes_tareas import register_task_routes
    try:
        from modules.routes_tareas import register_task_routes
    except Exception:
        register_task_routes = None

    try:
        from modules.routes_email_bandeja import register_bandeja_routes
    except Exception:
        register_bandeja_routes = None

    try:
        from modules.routes_gastos_tarjeta import register_gastos_routes
    except Exception:
        register_gastos_routes = None

    try:
        from modules.routes_config import register_config_routes, register_seguridad_routes
    except Exception:
        register_config_routes = None
        register_seguridad_routes = None

 
        

    try:
        from modules.roles_permisos import register_roles_permisos_routes
    except Exception:
        register_roles_permisos_routes = None

    from modules.routes_parametros_generales import register_parametros_generales_routes
    try:
        from modules.routes_parametros_generales import register_parametros_generales_routes
    except Exception:
        register_parametros_generales_routes = None

    try:
        from modules.routes_terceros import register_terceros_routes
    except Exception:
        register_terceros_routes = None

    try:
        from modules.routes_aliases import register_aliases
    except Exception:
        register_aliases = None

    try:
        from modules.routes_terceros_api import register_terceros_api
    except Exception:
        register_terceros_api = None

    try:
        from modules.routes_param_api import register_param_api
    except Exception:
        register_param_api = None

    try:
        from modules.xml_bp import xml_bp
    except Exception:
        xml_bp = None

    try:
        from modules.routes_planilla_mensual import planilla_bp
    except Exception:
        planilla_bp = None

    try:
        from modules.routes_notifications import notif_bp
    except Exception:
        notif_bp = None

    try:
        from modules.empresas import register_empresas_routes
    except Exception:
        register_empresas_routes = None

    try:
        from modules.routes_puestos import register_puestos_routes
    except Exception:
        register_puestos_routes = None

    from modules.routes_menu import menu_bp
    try:
        from modules.routes_menu import menu_bp
    except Exception:
        menu_bp = None

    

    # ------------------------------------------------------
    # Contratos se sigue importando directo como en tu app.py.
    # ------------------------------------------------------
    try:
        from modules.planificador import register_planificador_routes
    except Exception:
        register_planificador_routes = None

    try:
        from modules.contratos import register_contratos_routes
    except Exception:
        register_contratos_routes = None

    try:
        from modules.telegram_webhook import register_telegram_routes
    except Exception:
        register_telegram_routes = None

    # ------------------------------------------------------
    # Registro de blueprints simples.
    # ------------------------------------------------------
    if planilla_bp:
        app.register_blueprint(planilla_bp)

    if notif_bp:
        app.register_blueprint(notif_bp)

    if xml_bp:
        app.register_blueprint(xml_bp, url_prefix="/xml")

    if menu_bp:
        app.register_blueprint(menu_bp)

    if register_empresas_routes:
        try:
            register_empresas_routes(app)
        except Exception as e:
            app.logger.exception("Fallo register_empresas_routes: %s", e)

    # ------------------------------------------------------
    # Registro de módulos basados en función register_*.
    # ------------------------------------------------------
    if register_auth_routes:
        try:
            register_auth_routes(app)
        except Exception as e:
            app.logger.exception("Fallo register_auth_routes: %s", e)

    if register_user_routes:
        try:
            register_user_routes(app)
        except Exception as e:
            app.logger.exception("Fallo register_user_routes: %s", e)

    if register_task_routes:
        try:
            register_task_routes(app)
        except Exception as e:
            app.logger.exception("Fallo register_task_routes: %s", e)

    if register_bandeja_routes:
        try:
            register_bandeja_routes(app)
        except Exception as e:
            app.logger.exception("Fallo register_bandeja_routes: %s", e)

    if register_gastos_routes:
        try:
            register_gastos_routes(app)
        except Exception as e:
            app.logger.exception("Fallo register_gastos_routes: %s", e)

    if register_config_routes:
        try:
            register_config_routes(app)
        except Exception as e:
            app.logger.exception("Fallo register_config_routes: %s", e)

    if register_seguridad_routes: 
        try:
            register_seguridad_routes(app)
        except Exception as e:
            app.logger.exception("Fallo register_seguridad_routes: %s", e)

    if routes_reclamos:
        try:
            routes_reclamos.register_reclamos_routes(app)
        except Exception as e:
            app.logger.exception("Fallo register_reclamos_routes: %s", e)

    if register_roles_permisos_routes:
        try:
            register_roles_permisos_routes(app)
        except Exception as e:
            app.logger.exception("Fallo register_roles_permisos_routes: %s", e)

    if register_parametros_generales_routes:
        try:
            register_parametros_generales_routes(app)
        except Exception as e:
            app.logger.exception("Fallo register_parametros_generales_routes: %s", e)

    if register_terceros_routes:
        try:
            register_terceros_routes(app)
        except Exception as e:
            app.logger.exception("Fallo register_terceros_routes: %s", e)

    if register_terceros_api:
        try:
            register_terceros_api(app)
        except Exception as e:
            app.logger.exception("Fallo register_terceros_api: %s", e)

    if register_param_api:
        try:
            register_param_api(app)
        except Exception as e:
            app.logger.exception("Fallo register_param_api: %s", e)

    if register_aliases:
        try:
            register_aliases(app)
        except Exception as e:
            app.logger.exception("Fallo register_aliases: %s", e)

    if register_puestos_routes:
        try:
            if "puestos" in app.view_functions:
                f = app.view_functions["puestos"]
                app.logger.error(
                    "YA EXISTE endpoint 'puestos' definido en %s.%s",
                    getattr(f, "__module__", "?"),
                    getattr(f, "__name__", "?")
                )
            register_puestos_routes(app)
        except Exception as e:
            app.logger.exception("Fallo register_puestos_routes: %s", e)

    # ------------------------------------------------------
    # Registro del blueprint de contratos.
    # ------------------------------------------------------
    if register_planificador_routes:
        try:
            register_planificador_routes(app)
        except Exception as e:
            app.logger.exception("Fallo register_planificador_routes: %s", e)

    if register_contratos_routes:
        try:
            register_contratos_routes(app)
        except Exception as e:
            app.logger.exception("Fallo register_contratos_routes: %s", e)

    if register_telegram_routes:
        try:
            register_telegram_routes(app)
        except Exception as e:
            app.logger.exception("Fallo register_telegram_routes: %s", e)

    # ------------------------------------------------------
    # Ruta HOME de respaldo cuando no exista una explícita.
    # ------------------------------------------------------
    if "/" not in app.view_functions:
        from flask import redirect, render_template, url_for
        from modules.app_core.app_gateway import template_exists

        @app.route("/")
        def _home():
            for cand in ("login", "auth.login", "dashboard"):
                if cand in app.view_functions:
                    return redirect(url_for(cand))

            return (
                render_template("errors/404.html")
                if template_exists("errors/404.html")
                else ("No hay ruta de inicio definida. Crea 'login' o 'dashboard'.", 404)
            )