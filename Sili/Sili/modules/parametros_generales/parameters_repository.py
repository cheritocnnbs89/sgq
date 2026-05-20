# modules/parametros_generales/parameters_repository.py
# -*- coding: utf-8 -*-

from __future__ import annotations

from ..db import get_db
from .parameters_constants import (
    TABLA_PARAM_GROUPS,
    TABLA_PARAM_VALUES,
)
from .parameters_security import (
    is_sqlserver_conn,
    table_exists,
)
from . import parameters_querys as q


def ensure_param_tables():
    """
    En SQL Server no crea tablas en runtime.
    Solo valida que existan.
    En SQLite sí permite autocrear para desarrollo local.
    """
    conn = get_db()

    if is_sqlserver_conn(conn):
        faltantes = []

        if not table_exists(conn, TABLA_PARAM_GROUPS):
            faltantes.append(TABLA_PARAM_GROUPS)

        if not table_exists(conn, TABLA_PARAM_VALUES):
            faltantes.append(TABLA_PARAM_VALUES)

        if faltantes:
            raise RuntimeError(
                "Faltan tablas de parámetros en SQL Server: " + ", ".join(faltantes)
            )
        return

    cur = conn.cursor()

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLA_PARAM_GROUPS}(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE
        )
    """)

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLA_PARAM_VALUES}(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            nombre TEXT NOT NULL,
            valor TEXT,
            activo INTEGER NOT NULL DEFAULT 1,
            orden INTEGER NOT NULL DEFAULT 0,
            parent_id INTEGER NULL,
            FOREIGN KEY(group_id) REFERENCES {TABLA_PARAM_GROUPS}(id)
        )
    """)

    conn.commit()


def fetch_all_groups():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(q.SQL_SELECT_ALL_GROUPS)
    return cur.fetchall()


def fetch_all_values():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(q.SQL_SELECT_ALL_VALUES)
    return cur.fetchall()


def fetch_group_by_id(group_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(q.SQL_SELECT_GROUP_BY_ID, (group_id,))
    return cur.fetchone()


def fetch_values_by_group_id(group_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(q.SQL_SELECT_VALUES_BY_GROUP_ID, (group_id,))
    return cur.fetchall()


def insert_group(nombre: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(q.SQL_INSERT_GROUP, (nombre,))
    conn.commit()


def update_group(group_id: int, nombre: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(q.SQL_UPDATE_GROUP, (nombre, group_id))
    conn.commit()


def delete_group(group_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(q.SQL_DELETE_VALUES_BY_GROUP_ID, (group_id,))
    cur.execute(q.SQL_DELETE_GROUP_BY_ID, (group_id,))
    conn.commit()


def insert_value(
    group_id: int,
    nombre: str,
    valor: str | None,
    parent_id: int | None = None,
    activo: int = 1,
    orden: int = 1,
):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        q.SQL_INSERT_VALUE,
        (
            group_id,
            nombre,
            valor,
            parent_id,
            activo,
            orden,
        )
    )
    conn.commit()


def fetch_value_with_group(item_id: int, group_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(q.SQL_SELECT_VALUE_WITH_GROUP, (item_id, group_id))
    return cur.fetchone()


def update_value(
    item_id: int,
    group_id: int,
    nombre: str,
    valor: str | None,
    parent_id: int | None = None,
    activo: int = 1,
    orden: int = 1,
):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        q.SQL_UPDATE_VALUE,
        (
            nombre,
            valor,
            parent_id,
            activo,
            orden,
            item_id,
            group_id,
        )
    )
    conn.commit()


def delete_value(item_id: int, group_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(q.SQL_DELETE_VALUE_BY_ID_AND_GROUP_ID, (item_id, group_id))
    conn.commit()


def fetch_existing_value_names_by_group_id(group_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(q.SQL_SELECT_VALUE_NAMES_BY_GROUP_ID, (group_id,))
    return cur.fetchall()


def insert_many_values(rows_to_insert: list[tuple]):
    conn = get_db()
    cur = conn.cursor()
    cur.executemany(q.SQL_INSERT_MANY_VALUES, rows_to_insert)
    conn.commit()


def rollback():
    conn = get_db()
    conn.rollback()