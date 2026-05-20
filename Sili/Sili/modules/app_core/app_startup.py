from flask import g
from modules.db import init_db, get_db


def run_startup_tasks(app):
    with app.app_context():
        init_db()
        conn = get_db()
        conn.execute("SELECT 1")
        conn.commit()
        g.pop("db", None)