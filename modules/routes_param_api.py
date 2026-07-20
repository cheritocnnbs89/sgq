# modules/routes_param_api.py
from flask import request, jsonify
from modules.db import get_db


def _find_group_id_by_name(conn, *names):
    """
    Intenta resolver un group_id por lista de nombres:
    1) exacto
    2) luego LIKE
    Compatible con SQL Server.
    """
    cur = conn.cursor()

    for name in names:
        cur.execute(
            """
            SELECT TOP 1 id
            FROM param_groups
            WHERE LOWER(LTRIM(RTRIM(nombre))) = LOWER(LTRIM(RTRIM(?)))
            """,
            (name,)
        )
        row = cur.fetchone()
        if row:
            try:
                return row["id"]
            except Exception:
                return row[0]

    for name in names:
        cur.execute(
            """
            SELECT TOP 1 id
            FROM param_groups
            WHERE LOWER(COALESCE(nombre, '')) LIKE LOWER(?)
            """,
            (f"%{name}%",)
        )
        row = cur.fetchone()
        if row:
            try:
                return row["id"]
            except Exception:
                return row[0]

    return None


def _search_param_values(conn, group_id, q, limit=50):
    """
    Devuelve [{id, nombre, valor}] del grupo dado (filtro por q opcional).
    Compatible con SQL Server.
    """
    if not group_id:
        return []

    try:
        limit = int(limit)
    except Exception:
        limit = 50

    limit = max(1, min(limit, 50))

    cur = conn.cursor()

    if q:
        like = f"%{q.lower()}%"
        cur.execute(
            f"""
            SELECT TOP {limit} id, nombre, valor
            FROM param_values
            WHERE group_id = ?
              AND (
                    LOWER(COALESCE(nombre, '')) LIKE ?
                 OR LOWER(COALESCE(CAST(valor AS NVARCHAR(MAX)), '')) LIKE ?
              )
            ORDER BY nombre
            """,
            (group_id, like, like)
        )
    else:
        cur.execute(
            f"""
            SELECT TOP {limit} id, nombre, valor
            FROM param_values
            WHERE group_id = ?
            ORDER BY nombre
            """,
            (group_id,)
        )

    items = []
    for r in cur.fetchall():
        try:
            items.append({
                "id": r["id"],
                "nombre": r["nombre"],
                "valor": r["valor"],
            })
        except Exception:
            items.append({
                "id": r[0],
                "nombre": r[1],
                "valor": r[2],
            })

    return items


def register_param_api(app):
    # --- búsqueda por group_id explícito ---
    @app.get("/api/param/grupo/<int:group_id>/search", endpoint="api_param_search")
    def api_param_search(group_id):
        q = (request.args.get("q") or "").strip()
        try:
            limit = int(request.args.get("limit", "50"))
        except ValueError:
            limit = 50

        conn = get_db()
        try:
            items = _search_param_values(conn, group_id, q, limit=limit)
        finally:
            conn.close()

        return jsonify(items)

    # --- motivos (grupo por nombre, fallback id=1) ---
    @app.get("/api/param/motivos/search", endpoint="api_param_motivos")
    def api_param_motivos():
        q = (request.args.get("q") or "").strip()

        try:
            limit = int(request.args.get("limit", "3"))
        except ValueError:
            limit = 3

        limit = max(1, min(limit, 50))

        conn = get_db()
        try:
            gid = _find_group_id_by_name(
                conn,
                "Motivo Gasto",
                "Motivos",
                "Motivo"
            ) or 1

            items = _search_param_values(conn, gid, q, limit=limit)
        finally:
            conn.close()

        return jsonify(items)

    # --- centros de costo ---
    def _resolve_centros_group_id(conn):
        # Permite override por querystring
        override = (
            request.args.get("group_id")
            or request.args.get("padre")
            or request.args.get("parent_id")
        )
        if override and str(override).isdigit():
            return int(override)

        # Busca por nombre (variantes) y legacy
        gid = _find_group_id_by_name(
            conn,
            "Centro de Costo",
            "Centro de costo",
            "Centros de Costo",
            "Centros de costo"
        )
        if gid:
            return gid

        gid = _find_group_id_by_name(
            conn,
            "Cuenta contable",
            "Cuenta Contable"
        )
        if gid:
            return gid

        # Último recurso: id legacy conocido
        return 7

    # Alias sin /search para evitar 404 en pruebas manuales
    @app.get("/api/param/centros", endpoint="api_param_centros_alias")
    def api_param_centros_alias():
        return api_param_centros()

    # Ruta “oficial” usada por url_for('api_param_centros')
    @app.get("/api/param/centros/search", endpoint="api_param_centros")
    def api_param_centros():
        q = (request.args.get("q") or "").strip()

        try:
            limit = int(request.args.get("limit", "50"))
        except ValueError:
            limit = 50

        conn = get_db()
        try:
            gid = _resolve_centros_group_id(conn)
            items = _search_param_values(conn, gid, q, limit=limit)
        finally:
            conn.close()

        return jsonify(items)