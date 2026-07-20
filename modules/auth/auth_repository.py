from __future__ import annotations

from flask import current_app

from ..db import get_db
from . import auth_querys as q


def obtener_conexion_segura():
    from flask import g
    for _ in range(2):
        try:
            conn = get_db()
            conn.execute("SELECT 1")
            return conn
        except Exception:
            try:
                g.pop('db', None)
            except Exception:
                pass
    return get_db()

def insertar_auditoria_seguridad(
    usuario_id,
    username,
    evento,
    resultado,
    detalle,
    ip,
    user_agent,
    actor_usuario_id,
    fecha_evento,
):
    conn = obtener_conexion_segura()
    cur = conn.cursor()
    cur.execute(q.SQL_INSERT_AUDITORIA_SEGURIDAD, (
        usuario_id,
        username,
        evento,
        resultado,
        detalle,
        ip,
        user_agent,
        actor_usuario_id,
        fecha_evento,
    ))
    conn.commit()


def obtener_usuario_por_username(username: str):
    conn = obtener_conexion_segura()
    cur = conn.cursor()
    cur.execute(q.SQL_SELECT_USUARIO_POR_USERNAME, (username,))
    return cur.fetchone()


def obtener_estado_autenticacion_usuario(username: str):
    conn = obtener_conexion_segura()
    cur = conn.cursor()
    cur.execute(q.SQL_SELECT_ESTADO_AUTENTICACION_USUARIO, (username,))
    return cur.fetchone()


def obtener_usuario_para_login_fallido(username: str):
    conn = obtener_conexion_segura()
    cur = conn.cursor()
    cur.execute(q.SQL_SELECT_USUARIO_LOGIN_FALLIDO, (username,))
    return cur.fetchone()

def actualizar_login_fallido(
    user_id: int,
    nuevos_intentos: int,
    fecha_evento: str,
    ip: str | None,
    bloquear: bool,
    fecha_bloqueo: str | None,
    motivo_bloqueo: str | None,
):
    db = get_db()
    cur = db.cursor()

    bloquear_int = 1 if bloquear else 0

    cur.execute(q.SQL_UPDATE_LOGIN_FALLIDO, (
        nuevos_intentos,     # failed_attempts = ?
        fecha_evento,        # fecha_ultimo_intento_fallido = ?
        ip,                  # ip_ultimo_intento_fallido = ?
        bloquear_int,        # disabled CASE WHEN ? = 1
        bloquear_int,        # fecha_bloqueo CASE WHEN ? = 1
        fecha_bloqueo,       # THEN ?
        bloquear_int,        # motivo_bloqueo CASE WHEN ? = 1
        motivo_bloqueo,      # THEN ?
        user_id,             # WHERE id = ?
    ))

    db.commit()


def resetear_intentos_fallidos(user_id: int):
    conn = obtener_conexion_segura()
    cur = conn.cursor()
    cur.execute(q.SQL_RESETEAR_INTENTOS_FALLIDOS, (user_id,))
    conn.commit()


def registrar_login_exitoso(user_id: int, fecha: str, ip: str, ua: str):
    conn = obtener_conexion_segura()
    cur = conn.cursor()
    cur.execute(q.SQL_REGISTRAR_LOGIN_EXITOSO, (fecha, ip, ua, user_id))
    conn.commit()


def actualizar_password_hash_por_id(user_id: int, nuevo_hash: str):
    conn = obtener_conexion_segura()
    cur = conn.cursor()
    cur.execute(q.SQL_UPDATE_PASSWORD_POR_ID, (nuevo_hash, user_id))
    conn.commit()


def obtener_email_usuario_por_id(user_id: int):
    conn = obtener_conexion_segura()
    cur = conn.cursor()
    cur.execute(q.SQL_SELECT_EMAIL_USUARIO_POR_ID, (user_id,))
    return cur.fetchone()


def obtener_datos_correo_bloqueo(username: str):
    conn = obtener_conexion_segura()
    cur = conn.cursor()
    cur.execute(q.SQL_SELECT_DATOS_CORREO_BLOQUEO, (username,))
    return cur.fetchone()


def obtener_usuario_por_username_o_email(identificador: str):
    conn = obtener_conexion_segura()
    cur = conn.cursor()
    cur.execute(q.SQL_SELECT_USUARIO_POR_USERNAME_O_EMAIL, (identificador, identificador))
    return cur.fetchone()


def insertar_reset_token(user_id: int, code: str, expires_at: str, attempts_left: int):
    conn = obtener_conexion_segura()
    cur = conn.cursor()
    cur.execute(q.SQL_INSERT_RESET_TOKEN, (user_id, code, expires_at, attempts_left))
    row = cur.fetchone()
    conn.commit()
    return row["id"] if row and "id" in row.keys() else row[0]


def obtener_reset_token_por_id(token_id: int):
    conn = obtener_conexion_segura()
    cur = conn.cursor()
    cur.execute(q.SQL_SELECT_RESET_TOKEN_POR_ID, (token_id,))
    return cur.fetchone()


def marcar_reset_token_usado(token_id: int):
    conn = obtener_conexion_segura()
    cur = conn.cursor()
    cur.execute(q.SQL_MARCAR_RESET_TOKEN_USADO, (token_id,))
    conn.commit()


def actualizar_intentos_reset_token(token_id: int, attempts_left: int):
    conn = obtener_conexion_segura()
    cur = conn.cursor()
    cur.execute(q.SQL_UPDATE_RESET_TOKEN_INTENTOS, (attempts_left, token_id))
    conn.commit()


def bloquear_usuario_por_intentos_codigo(user_id: int, fecha_bloqueo: str, motivo_bloqueo: str):
    conn = obtener_conexion_segura()
    cur = conn.cursor()
    cur.execute(q.SQL_BLOQUEAR_USUARIO_POR_INTENTOS_CODIGO, (
        fecha_bloqueo,
        motivo_bloqueo,
        user_id,
    ))
    conn.commit()


def actualizar_password_por_recuperacion(user_id: int, nuevo_hash: str, fecha_cambio: str):
    conn = obtener_conexion_segura()
    cur = conn.cursor()
    cur.execute(q.SQL_ACTUALIZAR_PASSWORD_POR_RECUPERACION, (
        nuevo_hash,
        fecha_cambio,
        user_id,
    ))
    conn.commit()


def actualizar_password_usuario(user_id: int, nuevo_hash: str, fecha_cambio: str):
    conn = obtener_conexion_segura()
    cur = conn.cursor()
    cur.execute(q.SQL_ACTUALIZAR_PASSWORD_USUARIO, (
        nuevo_hash,
        fecha_cambio,
        user_id,
    ))
    conn.commit()


def obtener_permisos_por_rol(role_name: str) -> dict:
    if not role_name:
        return {}

    conn = obtener_conexion_segura()
    cur = conn.cursor()

    cur.execute(q.SQL_SELECT_PERMISOS_ROL_ACTUAL, (role_name,))
    filas = cur.fetchall()
    if filas:
        return {
            fila["opcion"]: {
                "ver": bool(fila["ver"]),
                "crear": bool(fila["crear"]),
                "editar": bool(fila["editar"]),
                "eliminar": bool(fila["eliminar"]),
                "exportar": bool(fila["exportar"]),
                "aprobar": bool(fila["aprobar"]),
            }
            for fila in filas
        }

    try:
        cur.execute(q.SQL_SELECT_PERMISOS_ROL_LEGACY, (role_name,))
        filas = cur.fetchall()
        return {
            fila["opcion"]: {
                "ver": bool(fila["ver"]),
                "crear": bool(fila["crear"]),
                "editar": bool(fila["editar"]),
                "eliminar": bool(fila["eliminar"]),
                "exportar": bool(fila["exportar"]),
                "aprobar": bool(fila["aprobar"]),
            }
            for fila in filas
        }
    except Exception as exc:
        current_app.logger.warning("No se pudieron cargar permisos legacy para %s: %s", role_name, exc)
        return {}
    

def obtener_usuario_por_id(user_id: int):
    conn = obtener_conexion_segura()
    cur = conn.cursor()
    cur.execute(q.SQL_SELECT_USUARIO_POR_ID, (user_id,))
    return cur.fetchone()


def insertar_login_mfa_token(user_id: int, code_hash: str, expires_at: str, attempts_left: int):
    conn = obtener_conexion_segura()
    cur = conn.cursor()
    #cur.execute(q.SQL_INSERT_LOGIN_MFA_TOKEN, (user_id, code_hash, expires_at, attempts_left))
    cur.execute(q.SQL_INSERT_LOGIN_MFA_TOKEN, (user_id, code_hash, expires_at, attempts_left))
    row = cur.fetchone()
    conn.commit()
    return row["id"] if row and "id" in row.keys() else row[0]


def obtener_login_mfa_token_por_id(token_id: int):
    conn = obtener_conexion_segura()
    cur = conn.cursor()
    cur.execute(q.SQL_SELECT_LOGIN_MFA_TOKEN_POR_ID, (token_id,))
    return cur.fetchone()


def marcar_login_mfa_token_usado(token_id: int):
    conn = obtener_conexion_segura()
    cur = conn.cursor()
    cur.execute(q.SQL_MARCAR_LOGIN_MFA_TOKEN_USADO, (token_id,))
    conn.commit()


def actualizar_intentos_login_mfa_token(token_id: int, attempts_left: int):
    conn = obtener_conexion_segura()
    cur = conn.cursor()
    cur.execute(q.SQL_UPDATE_LOGIN_MFA_TOKEN_INTENTOS, (attempts_left, token_id))
    conn.commit()



