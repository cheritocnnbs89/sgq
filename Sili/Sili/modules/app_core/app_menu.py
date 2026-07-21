# modules/app_core/app_menu.py
# ==========================================================
# Soporte de menú dinámico y permisos por rol.
# Construye permisos, sincroniza opciones e inyecta helpers
# para que los templates puedan validar acceso.
# ==========================================================

from flask import session, current_app, g
from modules.db import get_db

try:
    from modules.menu import fetch_menu_tree
    from modules.menu import sync_permissions_from_menu
except Exception:
    def fetch_menu_tree(conn, permissions, active_page=None, is_admin=False):
        return []

    def sync_permissions_from_menu(conn):
        return None


def _row_to_dict(row, cursor=None):
    if row is None:
        return None

    if isinstance(row, dict):
        return row

    if hasattr(row, "_asdict"):
        return row._asdict()

    if cursor is not None and cursor.description:
        columns = [col[0] for col in cursor.description]
        return dict(zip(columns, row))

    try:
        return dict(row)
    except Exception:
        return None


def _rows_to_dicts(rows, cursor=None):
    if not rows:
        return []
    return [_row_to_dict(row, cursor) for row in rows]


def _get_conn_safe():
    for _ in range(2):
        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
            return conn
        except Exception:
            try:
                g.pop("db", None)
            except Exception:
                pass
    return get_db()


def build_permissions(conn, role_name: str) -> dict:
    if not role_name:
        return {}

    cur = conn.cursor()

    cur.execute("""
        SELECT
            o.nombre AS opcion,
            COALESCE(rp.ver, 0) AS ver,
            COALESCE(rp.crear, 0) AS crear,
            COALESCE(rp.editar, 0) AS editar,
            COALESCE(rp.eliminar, 0) AS eliminar,
            COALESCE(rp.exportar, 0) AS exportar,
            COALESCE(rp.aprobar, 0) AS aprobar
        FROM dbo.roles_permisos rp
        INNER JOIN dbo.roles r
            ON r.id = rp.rol_id
        INNER JOIN dbo.opciones o
            ON o.id = rp.opcion_id
        WHERE LOWER(r.nombre) = LOWER(?)
    """, (role_name,))
    rows = _rows_to_dicts(cur.fetchall(), cur)

    if rows:
        return {
            row["opcion"]: {
                "ver": bool(row["ver"]),
                "crear": bool(row["crear"]),
                "editar": bool(row["editar"]),
                "eliminar": bool(row["eliminar"]),
                "exportar": bool(row["exportar"]),
                "aprobar": bool(row["aprobar"]),
            }
            for row in rows
        }

    try:
        cur.execute("""
            SELECT
                opcion,
                COALESCE(ver, 0) AS ver,
                COALESCE(crear, 0) AS crear,
                COALESCE(editar, 0) AS editar,
                COALESCE(eliminar, 0) AS eliminar,
                COALESCE(exportar, 0) AS exportar,
                COALESCE(aprobar, 0) AS aprobar
            FROM dbo.permisos
            WHERE LOWER(rol) = LOWER(?)
        """, (role_name,))
        rows = _rows_to_dicts(cur.fetchall(), cur)

        return {
            row["opcion"]: {
                "ver": bool(row["ver"]),
                "crear": bool(row["crear"]),
                "editar": bool(row["editar"]),
                "eliminar": bool(row["eliminar"]),
                "exportar": bool(row["exportar"]),
                "aprobar": bool(row["aprobar"]),
            }
            for row in rows
        }
    except Exception:
        return {}


def register_context_processors(app):
    @app.context_processor
    def inject_menu():
        role_name = (session.get("rol") or "").strip()
        is_admin = str(role_name).lower() == "admin" or bool(session.get("is_admin"))

        try:
            conn = _get_conn_safe()
            cur = conn.cursor()

            permissions = build_permissions(conn, role_name)
            session["permissions"] = permissions

            cur.execute("""
                SELECT
                    COUNT(*) AS c,
                    ISNULL(MAX(id), 0) AS mx
                FROM dbo.menu_items
            """)
            row = _row_to_dict(cur.fetchone(), cur) or {"c": 0, "mx": 0}

            rev = f"{row['c']}-{row['mx']}"

            if session.get("menu_rev") != rev:
                session["menu_rev"] = rev
                session.pop("permissions", None)

            permissions = session.get("permissions") or build_permissions(conn, role_name)
            session["permissions"] = permissions

            menu_tree = fetch_menu_tree(
                conn,
                permissions,
                active_page=session.get("active_page"),
                is_admin=is_admin
            )

            return dict(menu_tree=menu_tree)

        except Exception as e:
            current_app.logger.exception("inject_menu error: %s", e)
            return dict(menu_tree=[])

    @app.context_processor
    def inject_perm_helpers():
        def has_perm(opcion: str, accion: str = "ver") -> bool:
            role = (session.get("rol") or "").lower()
            if role == "admin" or bool(session.get("is_admin")):
                return True

            perms = session.get("permissions") or {}
            permiso = perms.get(opcion) or next(
                (value for key, value in perms.items() if key.lower() == opcion.lower()),
                {}
            )
            return bool(permiso.get(accion))

        return dict(has_permission=has_perm, has_perm=has_perm)