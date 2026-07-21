# modules/empresas/empresas_repository.py
# -*- coding: utf-8 -*-

from modules.db import get_db

from . import empresas_queries as q


def get_connection():
    return get_db()


def list_empresas(filters):
    conn = get_connection()

    params = []
    where = []

    if filters["q"]:
        where.append(
            "("
            "razon_social LIKE ? "
            "OR ruc LIKE ? "
            "OR email LIKE ? "
            "OR telefono LIKE ? "
            "OR rep_nacionalidad LIKE ? "
            "OR usuario_sap LIKE ?"
            ")"
        )
        like = f"%{filters['q']}%"
        params.extend([like, like, like, like, like, like])

    if filters["activo"] in ("0", "1"):
        where.append("activo = ?")
        params.append(int(filters["activo"]))

    sql = q.SQL_SELECT_EMPRESAS_LISTA_BASE

    if where:
        sql += " WHERE " + " AND ".join(where)

    sql += " ORDER BY razon_social ASC"

    return conn.execute(sql, params).fetchall()


def get_empresa_by_id(empresa_id):
    conn = get_connection()
    cur = conn.cursor()
    return cur.execute(q.SQL_SELECT_EMPRESA_BY_ID, (empresa_id,)).fetchone()


def insert_empresa(data):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(q.SQL_INSERT_EMPRESA, (
        data["razon_social"],
        data["ruc"],
        data["direccion"],
        data["telefono"],
        data["email"],
        data["sitio_web"],
        data["rep_nombre"],
        data["rep_identificacion"],
        data["rep_nacionalidad"],
        data["usuario_sap"],
        data["activo"],
    ))

    cur.execute(q.SQL_SCOPE_IDENTITY)
    row = cur.fetchone()
    conn.commit()

    return row[0] if row else None


def update_empresa(empresa_id, data):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(q.SQL_UPDATE_EMPRESA, (
        data["razon_social"],
        data["ruc"],
        data["direccion"],
        data["telefono"],
        data["email"],
        data["sitio_web"],
        data["rep_nombre"],
        data["rep_identificacion"],
        data["rep_nacionalidad"],
        data["usuario_sap"],
        data["activo"],
        empresa_id,
    ))

    conn.commit()
    return empresa_id


def delete_empresa(empresa_id):
    conn = get_connection()
    conn.execute(q.SQL_DELETE_EMPRESA, (empresa_id,))
    conn.commit()