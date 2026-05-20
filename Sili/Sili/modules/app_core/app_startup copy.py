# modules/app_core/app_startup.py
# ==========================================================
# Tareas de arranque de la aplicación.
# Inicializa esquema principal, componentes auxiliares,
# gastos y estructuras de menú/permisos.
# ==========================================================

from flask import g

from modules.db import init_db, get_db
from modules.app_core.app_menu import sync_permissions_from_menu


def run_startup_tasks(app):
    # ------------------------------------------------------
    # Ejecuta inicializaciones al arrancar la app.
    # Mantiene la lógica actual de tu app.py.
    # ------------------------------------------------------
    with app.app_context():
        # --------------------------------------------------
        # Inicializa el esquema base de la base de datos.
        # --------------------------------------------------
        init_db()

        # --------------------------------------------------
        # Inicializa estructuras auxiliares del módulo gastos.
        # --------------------------------------------------
        from modules import gastos_helpers as gh

        g.pop("db", None)
        gh.ensure_gastos_schema()
        g.pop("db", None)

        g.pop("db", None)
        gh.ensure_gastos_detalle_schema()
        g.pop("db", None)

        g.pop("db", None)
        conn = get_db()
        gh.ensure_proveedor_fk(conn)
        conn.commit()
        g.pop("db", None)

        # --------------------------------------------------
        # Inicializa estructuras del menú y sincroniza
        # permisos desde menu_items.
        # --------------------------------------------------
        try:
            from Sili.modules.routes_menu import (
                ensure_menu_schema,
                seed_menu_if_empty,
                ensure_admin_full_perms,
            )

            conn = get_db()
            ensure_menu_schema(conn)
            seed_menu_if_empty(conn)
            sync_permissions_from_menu(conn)
            ensure_admin_full_perms(conn)
            conn.commit()

        except Exception as e:
            app.logger.exception("Init menú/permisos falló: %s", e)