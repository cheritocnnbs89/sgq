# modules/cartera/cartera_repository.py
# -*- coding: utf-8 -*-

from modules.db import get_db

from . import cartera_queries as q


def get_connection():
    return get_db()


def list_facturas(filters):
    conn = get_connection()

    params = []
    where = []

    if filters["q"]:
        where.append(
            "("
            "cuenta LIKE ? "
            "OR nombre_cliente LIKE ? "
            "OR doc_facturacion LIKE ? "
            "OR referencia LIKE ? "
            "OR num_documento_origen LIKE ?"
            ")"
        )
        like = f"%{filters['q']}%"
        params.extend([like, like, like, like, like])

    if filters["estado"] in ("Abierta", "Pagada"):
        where.append("estado = ?")
        params.append(filters["estado"])

    if filters["solo_demoradas"]:
        where.append("dias_totales_guia_pago > ?")
        params.append(filters["dias_umbral"])

    sql = q.SQL_SELECT_CARTERA_FACTURAS_BASE

    if where:
        sql += " WHERE " + " AND ".join(where)

    # Abiertas primero (son las que hay que gestionar), y dentro de cada
    # grupo las más demoradas arriba.
    sql += """
        ORDER BY
            CASE WHEN estado = 'Abierta' THEN 0 ELSE 1 END,
            ISNULL(dias_totales_guia_pago, -1) DESC
    """

    return conn.execute(sql, params).fetchall()


def get_resumen():
    conn = get_connection()
    cur = conn.cursor()
    return cur.execute(q.SQL_SELECT_CARTERA_RESUMEN).fetchone()
