# modules/parametros_generales/parameters_security.py
# -*- coding: utf-8 -*-

from __future__ import annotations


def raw_conn(conn):
    return getattr(conn, "_conn", conn)


def is_sqlserver_conn(conn) -> bool:
    raw = raw_conn(conn)
    mod = getattr(raw.__class__, "__module__", "").lower()
    name = getattr(raw.__class__, "__name__", "").lower()
    text = f"{mod} {name}"
    return "pyodbc" in text or "odbc" in text


def table_exists(conn, table_name: str) -> bool:
    cur = conn.cursor()

    if is_sqlserver_conn(conn):
        cur.execute("""
            SELECT 1
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = ?
        """, (table_name,))
        return cur.fetchone() is not None

    cur.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
    """, (table_name,))
    return cur.fetchone() is not None


def normalize_required_text(value) -> str:
    return (value or "").strip()


def normalize_csv_separator(value) -> str:
    sep = (value or "").strip()
    return sep if sep else ","


def is_duplicate_error_message(exc: Exception) -> bool:
    msg = str(exc).lower()
    return (
        "unique" in msg
        or "duplicate" in msg
        or "duplic" in msg
        or "uq_" in msg
    )