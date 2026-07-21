# -*- coding: utf-8 -*-

from .roles_permisos_queries import (
    SQL_TABLE_EXISTS,
    SQL_SELECT_ROLES,
    SQL_SELECT_ROLE_BY_NAME_CASE_INSENSITIVE,
    SQL_INSERT_ROLE,
    SQL_SELECT_OPCIONES,
    SQL_SELECT_OPCIONES_NOMBRE,
    SQL_SELECT_OPCION_BY_NAME,
    SQL_INSERT_OPCION,
    SQL_SELECT_PERMISOS_BY_ROL_ID,
    SQL_DELETE_ROLES_PERMISOS_BY_ROL_ID,
    SQL_INSERT_ROL_PERMISO,
    SQL_DELETE_PERMISOS_LEGACY_BY_ROL,
    SQL_INSERT_PERMISOS_LEGACY_FROM_ROL,
    SQL_SELECT_PERMISOS_LEGACY,
    SQL_INSERT_ROL_PERMISO_IF_NOT_EXISTS,
)
from .roles_permisos_constants import TABLA_PERMISOS_LEGACY


def table_exists(conn, table_name: str) -> bool:
    cur = conn.cursor()
    cur.execute(SQL_TABLE_EXISTS, (table_name,))
    return cur.fetchone() is not None


def get_roles(conn):
    cur = conn.cursor()
    cur.execute(SQL_SELECT_ROLES)
    return cur.fetchall()


def get_role_by_name_case_insensitive(conn, role_name: str):
    cur = conn.cursor()
    cur.execute(SQL_SELECT_ROLE_BY_NAME_CASE_INSENSITIVE, (role_name,))
    return cur.fetchone()


def insert_role(conn, role_name: str):
    cur = conn.cursor()
    cur.execute(SQL_INSERT_ROLE, (role_name,))
    conn.commit()


def get_or_create_role(conn, role_name: str):
    row = get_role_by_name_case_insensitive(conn, role_name)
    if row:
        return row

    insert_role(conn, role_name)
    return get_role_by_name_case_insensitive(conn, role_name)


def get_opciones(conn):
    cur = conn.cursor()
    cur.execute(SQL_SELECT_OPCIONES)
    return cur.fetchall()


def get_opciones_nombre(conn):
    cur = conn.cursor()
    cur.execute(SQL_SELECT_OPCIONES_NOMBRE)
    return cur.fetchall()


def get_opcion_by_name(conn, opcion_name: str):
    cur = conn.cursor()
    cur.execute(SQL_SELECT_OPCION_BY_NAME, (opcion_name,))
    return cur.fetchone()


def insert_opcion(conn, opcion_name: str):
    cur = conn.cursor()
    cur.execute(SQL_INSERT_OPCION, (opcion_name,))
    conn.commit()


def get_or_create_opcion(conn, opcion_name: str):
    row = get_opcion_by_name(conn, opcion_name)
    if row:
        return row

    insert_opcion(conn, opcion_name)
    return get_opcion_by_name(conn, opcion_name)


def get_permisos_by_rol_id(conn, rol_id: int):
    cur = conn.cursor()
    cur.execute(SQL_SELECT_PERMISOS_BY_ROL_ID, (rol_id,))
    return cur.fetchall()


def delete_roles_permisos_by_rol_id(conn, rol_id: int):
    cur = conn.cursor()
    cur.execute(SQL_DELETE_ROLES_PERMISOS_BY_ROL_ID, (rol_id,))


def insert_rol_permiso(
    conn,
    rol_id: int,
    opcion_id: int,
    ver: int,
    crear: int,
    editar: int,
    eliminar: int,
    exportar: int,
    aprobar: int,
):
    cur = conn.cursor()
    cur.execute(
        SQL_INSERT_ROL_PERMISO,
        (
            rol_id,
            opcion_id,
            ver,
            crear,
            editar,
            eliminar,
            exportar,
            aprobar,
        ),
    )


def sync_legacy_permisos(conn, role_name: str):
    if not table_exists(conn, TABLA_PERMISOS_LEGACY):
        return

    cur = conn.cursor()
    cur.execute(SQL_DELETE_PERMISOS_LEGACY_BY_ROL, (role_name,))
    cur.execute(SQL_INSERT_PERMISOS_LEGACY_FROM_ROL, (role_name,))
    conn.commit()


def get_legacy_permisos(conn):
    if not table_exists(conn, TABLA_PERMISOS_LEGACY):
        return []

    cur = conn.cursor()
    cur.execute(SQL_SELECT_PERMISOS_LEGACY)
    return cur.fetchall()


def upsert_rol_permiso_from_legacy(
    conn,
    rol_id: int,
    opcion_id: int,
    ver: int,
    crear: int,
    editar: int,
    eliminar: int,
    exportar: int,
    aprobar: int,
):
    cur = conn.cursor()
    cur.execute(
        SQL_INSERT_ROL_PERMISO_IF_NOT_EXISTS,
        (
            rol_id,
            opcion_id,
            rol_id,
            opcion_id,
            ver,
            crear,
            editar,
            eliminar,
            exportar,
            aprobar,
            ver,
            crear,
            editar,
            eliminar,
            exportar,
            aprobar,
            rol_id,
            opcion_id,
        ),
    )