from flask import g
from modules.db import init_db, get_db


def run_startup_tasks(app):
    with app.app_context():
        init_db()
        conn = get_db()
        conn.execute("SELECT 1")
        conn.commit()

        try:
            from modules.planificador.planificador_repository import ensure_presupuesto_schema
            ensure_presupuesto_schema()
        except Exception:
            pass

        g.pop("db", None)