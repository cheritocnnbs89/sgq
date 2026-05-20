# modules/users/user_repository.py
# -*- coding: utf-8 -*-
# ==========================================================
# Acceso a datos del módulo de usuarios.
# Aquí viven helpers DB, cargas de combos y distribución CC.
# Adaptado para SQL Server.
# ==========================================================

from .user_queries import (
    SQL_INSERT_USUARIO,
    SQL_TABLE_EXISTS,
    SQL_CREATE_USUARIOS_CC,
    SQL_SELECT_ROLES,
    SQL_SELECT_CENTROS_COSTO,
    SQL_SELECT_USER_CC_DIST,
    SQL_SELECT_VALID_CC_IDS,
    SQL_DELETE_USER_CC_DIST,
    SQL_INSERT_USER_CC_DIST,
    SQL_SELECT_USUARIO_EDIT,
    SQL_SELECT_DEPARTAMENTOS,
    SQL_SELECT_AREAS_ACTIVAS,
    SQL_SELECT_PUESTOS_ACTIVOS,
    SQL_SELECT_EMPRESAS_ACTIVAS,
    SQL_SELECT_JEFES_ACTIVOS,
    SQL_SELECT_EMPRESAS_ACTIVAS_PLAIN,
    SQL_SELECT_USUARIOS_LIST_JEFES,
    SQL_SELECT_USUARIO_DELETE,
    SQL_DELETE_USUARIO_CC_BY_USER,
    SQL_DELETE_USUARIO_BY_ID,
    SQL_SELECT_USERS_REPORT,
    SQL_INSERT_DEPARTAMENTO,
    SQL_SELECT_DEPARTAMENTOS_LIST,
    SQL_SELECT_DEPARTAMENTO_BY_ID,
    SQL_UPDATE_DEPARTAMENTO,
    SQL_DELETE_DEPARTAMENTO,
    SQL_INSERT_AREA,
    SQL_SELECT_AREAS_LIST,
    SQL_SELECT_ORGANIGRAMA,
    SQL_SELECT_IDENT_TO_ID,
    SQL_SELECT_EMAIL_TO_ID,
    SQL_SELECT_DEPARTAMENTOS_MAP,
    SQL_SELECT_PUESTOS_MAP,
    SQL_SELECT_USUARIO_BY_USERNAME,
    SQL_SELECT_USUARIO_BY_EMAIL,
    SQL_INSERT_PUESTO_IF_NOT_EXISTS,
    SQL_SELECT_PUESTO_BY_NAME,
    SQL_UPDATE_USUARIO_CON_PASSWORD,
    SQL_UPDATE_USUARIO_SIN_PASSWORD,
    SQL_UPDATE_USUARIO_BULK_BY_ID,
    SQL_UPDATE_USUARIO_SET_JEFE,
    SQL_UPDATE_USUARIO_SET_JEFE_NULL,
    USERS_DELETE_CHECKS,
)
from .user_constants import CC_GROUP_ID


def table_exists(cur, table: str) -> bool:
    cur.execute(SQL_TABLE_EXISTS, (table,))
    return cur.fetchone() is not None


def column_exists(cur, table: str, column: str) -> bool:
    sql = """
        SELECT 1
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = ?
          AND COLUMN_NAME = ?
    """
    cur.execute(sql, (table, column))
    return cur.fetchone() is not None


def get_roles_from_db(conn, fallback_roles: list[str]):
    cur = conn.cursor()
    try:
        cur.execute(SQL_SELECT_ROLES)
        rows = cur.fetchall()
        roles = [
            (r["nombre"] or "").strip().lower()
            for r in rows if (r["nombre"] or "").strip()
        ]

        seen = set()
        roles_norm = []
        for r in roles:
            if r not in seen:
                seen.add(r)
                roles_norm.append(r)

        return roles_norm if roles_norm else list(fallback_roles)

    except Exception:
        return list(fallback_roles)


def ensure_usuarios_cc_schema(conn):
    cur = conn.cursor()
    cur.execute(SQL_CREATE_USUARIOS_CC)
    conn.commit()


def load_centros_costo_from_params(conn):
    cur = conn.cursor()
    cur.execute(SQL_SELECT_CENTROS_COSTO, (CC_GROUP_ID,))
    return cur.fetchall()


def load_user_cc_dist(conn, user_id: int):
    cur = conn.cursor()
    cur.execute(SQL_SELECT_USER_CC_DIST, (CC_GROUP_ID, user_id))
    return [dict(r) for r in cur.fetchall()]


def save_user_cc_dist(conn, user_id: int, cc_ids: list[str], cc_pcts: list[str]):
    items = []

    for cc_raw, pct_raw in zip(cc_ids, cc_pcts):
        cc_raw = (cc_raw or "").strip()
        pct_raw = (pct_raw or "").strip()

        if not cc_raw:
            continue

        try:
            cc_id = int(cc_raw)
        except ValueError:
            continue

        try:
            pct = float(pct_raw.replace(",", ".")) if pct_raw else 0.0
        except ValueError:
            pct = 0.0

        items.append((cc_id, pct))

    cur = conn.cursor()

    if not items:
        cur.execute(SQL_DELETE_USER_CC_DIST, (user_id,))
        return True, None

    cur.execute(SQL_SELECT_VALID_CC_IDS, (CC_GROUP_ID,))
    valid_ids = {int(r["id"]) for r in cur.fetchall()}

    for cc_id, _ in items:
        if cc_id not in valid_ids:
            return False, f"Centro de costo inválido (id={cc_id}). Revise Parametrización (grupo Centro de Costo)."

    total = sum(p for _, p in items)

    if abs(total - 100.0) > 0.01:
        return False, f"La distribución de centros de costo debe sumar 100%. Actualmente suma: {total:.2f}%"

    cur.execute(SQL_DELETE_USER_CC_DIST, (user_id,))

    for cc_id, pct in items:
        cur.execute(SQL_INSERT_USER_CC_DIST, (user_id, cc_id, pct))

    return True, None


def get_usuario_for_edit(conn, user_id: int):
    cur = conn.cursor()
    cur.execute(SQL_SELECT_USUARIO_EDIT, (user_id,))
    return cur.fetchone()


def load_user_form_combos(conn):
    cur = conn.cursor()

    cur.execute(SQL_SELECT_DEPARTAMENTOS)
    departamentos = cur.fetchall()

    cur.execute(SQL_SELECT_AREAS_ACTIVAS)
    areas = cur.fetchall()

    cur.execute(SQL_SELECT_PUESTOS_ACTIVOS)
    puestos = cur.fetchall()

    cur.execute(SQL_SELECT_EMPRESAS_ACTIVAS)
    empresas = cur.fetchall()

    cur.execute(SQL_SELECT_JEFES_ACTIVOS)
    jefes = cur.fetchall()

    return departamentos, areas, puestos, empresas, jefes


def load_empresas_for_nuevo_usuario(conn):
    cur = conn.cursor()
    cur.execute(SQL_SELECT_EMPRESAS_ACTIVAS_PLAIN)
    return cur.fetchall()


def load_jefes_for_list(conn):
    cur = conn.cursor()
    cur.execute(SQL_SELECT_USUARIOS_LIST_JEFES)
    return cur.fetchall()


def get_usuario_for_delete(conn, user_id: int):
    cur = conn.cursor()
    cur.execute(SQL_SELECT_USUARIO_DELETE, (user_id,))
    return cur.fetchone()


def check_user_delete_dependencies(conn, user_id: int):
    cur = conn.cursor()
    total_usos = 0
    detalles = []

    for tabla, columna, label in USERS_DELETE_CHECKS:
        try:
            if not table_exists(cur, tabla):
                continue

            if not column_exists(cur, tabla, columna):
                continue

            sql = f"SELECT COUNT(*) AS c FROM {tabla} WHERE {columna} = ?"
            cur.execute(sql, (user_id,))
            row = cur.fetchone()

            c = int(row["c"] or 0) if row else 0

            if c:
                total_usos += c
                detalles.append(f"{c} {label}")

        except Exception:
            continue

    return total_usos, detalles


def delete_usuario_safe(conn, user_id: int):
    cur = conn.cursor()

    if table_exists(cur, "usuarios_cc") and column_exists(cur, "usuarios_cc", "usuario_id"):
        cur.execute(SQL_DELETE_USUARIO_CC_BY_USER, (user_id,))

    cur.execute(SQL_DELETE_USUARIO_BY_ID, (user_id,))


def update_usuario_con_password(conn, params):
    """
    Actualiza usuario incluyendo contraseña.

    El tuple params debe coincidir con SQL_UPDATE_USUARIO_CON_PASSWORD.

    Orden esperado después del cambio:
    ...
    jefe_id,
    tiene_caja_chica,
    tipo_caja_chica,
    codigo_sap,
    user_id
    """
    cur = conn.cursor()
    cur.execute(SQL_UPDATE_USUARIO_CON_PASSWORD, params)


def update_usuario_sin_password(conn, params):
    """
    Actualiza usuario sin cambiar contraseña.

    El tuple params debe coincidir con SQL_UPDATE_USUARIO_SIN_PASSWORD.

    Orden esperado después del cambio:
    ...
    jefe_id,
    tiene_caja_chica,
    tipo_caja_chica,
    codigo_sap,
    user_id
    """
    cur = conn.cursor()
    cur.execute(SQL_UPDATE_USUARIO_SIN_PASSWORD, params)


def username_exists(conn, username: str) -> bool:
    cur = conn.cursor()
    cur.execute(SQL_SELECT_USUARIO_BY_USERNAME, (username.lower(),))
    return cur.fetchone() is not None


def email_exists(conn, email: str) -> bool:
    cur = conn.cursor()
    cur.execute(SQL_SELECT_USUARIO_BY_EMAIL, (email.lower(),))
    return cur.fetchone() is not None


def insert_usuario(conn, params):
    """
    Inserta usuario.

    El tuple params debe coincidir con SQL_INSERT_USUARIO.

    Orden esperado después del cambio:
    ...
    jefe_id,
    tiene_caja_chica,
    tipo_caja_chica
    """
    cur = conn.cursor()
    cur.execute(SQL_INSERT_USUARIO, params)

    # SQL Server
    cur.execute("SELECT SCOPE_IDENTITY() AS id")
    row = cur.fetchone()

    if row and row["id"] is not None:
        return int(row["id"])

    return None


def get_users_report_rows(conn):
    cur = conn.cursor()
    cur.execute(SQL_SELECT_USERS_REPORT)
    return cur.fetchall()


def update_jefe_masivo(conn, jefe_id: int, ids: list[int]):
    cur = conn.cursor()

    placeholders = ",".join("?" for _ in ids)

    sql = f"""
        UPDATE usuarios
        SET jefe_id = ?
        WHERE id IN ({placeholders})
    """

    params = [int(jefe_id)] + [int(x) for x in ids]
    cur.execute(sql, params)


def insert_departamento(conn, nombre: str):
    cur = conn.cursor()
    cur.execute(SQL_INSERT_DEPARTAMENTO, (nombre,))


def get_departamentos_list(conn):
    cur = conn.cursor()
    cur.execute(SQL_SELECT_DEPARTAMENTOS_LIST)
    return cur.fetchall()


def get_departamento_by_id(conn, dep_id: int):
    cur = conn.cursor()
    cur.execute(SQL_SELECT_DEPARTAMENTO_BY_ID, (dep_id,))
    return cur.fetchone()


def update_departamento(conn, dep_id: int, nombre: str):
    cur = conn.cursor()
    cur.execute(SQL_UPDATE_DEPARTAMENTO, (nombre, dep_id))


def delete_departamento(conn, dep_id: int):
    cur = conn.cursor()
    cur.execute(SQL_DELETE_DEPARTAMENTO, (dep_id,))


def insert_area(conn, nombre: str):
    cur = conn.cursor()
    cur.execute(SQL_INSERT_AREA, (nombre,))


def get_areas_list(conn):
    cur = conn.cursor()
    cur.execute(SQL_SELECT_AREAS_LIST)
    return cur.fetchall()


def get_organigrama_rows(conn):
    cur = conn.cursor()
    cur.execute(SQL_SELECT_ORGANIGRAMA)
    return [dict(r) for r in cur.fetchall()]


def load_bulk_maps(conn):
    cur = conn.cursor()

    cur.execute(SQL_SELECT_IDENT_TO_ID)
    ident_to_id = {}

    for row in cur.fetchall():
        if row["ced"]:
            ident_to_id[row["ced"]] = row["id"]

    cur.execute(SQL_SELECT_EMAIL_TO_ID)
    email_to_id = {}

    for row in cur.fetchall():
        if row["em"]:
            email_to_id[row["em"]] = row["id"]

    cur.execute(SQL_SELECT_DEPARTAMENTOS_MAP)
    dep_map = {}

    for row in cur.fetchall():
        dep_name_key = (row["nombre"] or "").strip().lower()
        if dep_name_key:
            dep_map[dep_name_key] = row["id"]

    cur.execute(SQL_SELECT_PUESTOS_MAP)
    puesto_map = {}

    for row in cur.fetchall():
        keyp = (row["nombre"] or "").strip().lower()
        if keyp and keyp not in puesto_map:
            puesto_map[keyp] = row["id"]

    return ident_to_id, email_to_id, dep_map, puesto_map


def insert_puesto_if_missing(conn, puesto_nombre: str):
    cur = conn.cursor()

    cur.execute(
        SQL_INSERT_PUESTO_IF_NOT_EXISTS,
        (puesto_nombre, puesto_nombre, puesto_nombre)
    )

    cur.execute(SQL_SELECT_PUESTO_BY_NAME, (puesto_nombre,))
    row = cur.fetchone()

    return row["id"] if row else None


def update_usuario_bulk_by_id(conn, params):
    cur = conn.cursor()
    cur.execute(SQL_UPDATE_USUARIO_BULK_BY_ID, params)


def update_usuario_set_jefe(conn, jefe_user_id: int, user_id: int):
    cur = conn.cursor()
    cur.execute(SQL_UPDATE_USUARIO_SET_JEFE, (jefe_user_id, user_id))


def update_usuario_set_jefe_null(conn, user_id: int):
    cur = conn.cursor()
    cur.execute(SQL_UPDATE_USUARIO_SET_JEFE_NULL, (user_id,))