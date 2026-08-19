# modules/cartera/cartera_repository.py
# -*- coding: utf-8 -*-

from modules.db import get_db

from . import cartera_queries as q


def get_connection():
    return get_db()


def _build_periodo_where(filters, cuenta=None):
    """Arma el WHERE de año/mes (sobre fecha_factura) y, opcionalmente,
    de cuenta — en ese orden, para que coincida con el orden de los ?
    que arma cada caller."""
    where = []
    params = []

    if filters.get("anio"):
        where.append("YEAR(fecha_factura) = ?")
        params.append(filters["anio"])

    if filters.get("mes"):
        where.append("MONTH(fecha_factura) = ?")
        params.append(filters["mes"])

    if cuenta:
        where.append("cuenta = ?")
        params.append(cuenta)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    return where_sql, params


def list_anios_disponibles():
    conn = get_connection()
    rows = conn.execute(q.SQL_SELECT_ANIOS_DISPONIBLES).fetchall()
    return [int(r["anio"]) for r in rows if r["anio"] is not None]


def list_ranking_clientes(filters):
    conn = get_connection()
    where_sql, where_params = _build_periodo_where(filters)

    sql = q.sql_ranking_clientes(where_sql)
    params = [filters["dias_umbral"]] + where_params

    return conn.execute(sql, params).fetchall()


def get_cliente_metricas(cuenta, filters):
    conn = get_connection()
    where_sql, where_params = _build_periodo_where(filters, cuenta=cuenta)

    sql = q.sql_cliente_metricas(where_sql)
    params = [filters["dias_umbral"]] + where_params

    cur = conn.cursor()
    return cur.execute(sql, params).fetchone()


def list_facturas_cliente(cuenta, filters):
    conn = get_connection()
    where_sql, where_params = _build_periodo_where(filters, cuenta=cuenta)

    sql = q.sql_facturas_cliente(where_sql)
    return conn.execute(sql, where_params).fetchall()


def get_factura_resumen(doc_facturacion):
    conn = get_connection()
    cur = conn.cursor()
    return cur.execute(q.SQL_SELECT_FACTURA_RESUMEN, (doc_facturacion,)).fetchone()


def list_cobros_factura(doc_facturacion):
    conn = get_connection()
    return conn.execute(q.SQL_SELECT_COBROS_FACTURA, (doc_facturacion,)).fetchall()
