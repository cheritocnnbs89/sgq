from .auth_constants import (
    TABLA_USUARIOS,
    TABLA_AUDITORIA_SEGURIDAD,
    TABLA_RESET_TOKENS,
    TABLA_LOGIN_MFA_TOKENS,
)

SQL_INSERT_AUDITORIA_SEGURIDAD = f"""
    INSERT INTO {TABLA_AUDITORIA_SEGURIDAD}
    (
        usuario_id,
        username,
        evento,
        resultado,
        detalle,
        ip,
        user_agent,
        actor_usuario_id,
        fecha_evento
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

SQL_SELECT_USUARIO_POR_USERNAME = f"""
    SELECT
        id,
        username,
        rol,
        departamento_id,
        email,
        COALESCE(disabled, 0) AS disabled,
        COALESCE(failed_attempts, 0) AS failed_attempts,
        fecha_bloqueo,
        motivo_bloqueo,
        password
    FROM {TABLA_USUARIOS}
    WHERE LOWER(username)=LOWER(?)
"""



SQL_SELECT_USUARIO_POR_ID = f"""
    SELECT
        id,
        username,
        rol,
        departamento_id,
        email,
        COALESCE(disabled, 0) AS disabled,
        COALESCE(failed_attempts, 0) AS failed_attempts,
        fecha_bloqueo,
        motivo_bloqueo,
        password
    FROM {TABLA_USUARIOS}
    WHERE id = ?
"""


SQL_SELECT_ESTADO_AUTENTICACION_USUARIO = f"""
    SELECT
        id,
        username,
        email,
        rol,
        departamento_id,
        COALESCE(disabled, 0) AS disabled,
        COALESCE(failed_attempts, 0) AS failed_attempts,
        fecha_ultimo_acceso,
        ip_ultimo_acceso,
        ua_ultimo_acceso,
        fecha_ultimo_intento_fallido,
        ip_ultimo_intento_fallido,
        fecha_bloqueo,
        motivo_bloqueo,
        password
    FROM {TABLA_USUARIOS}
    WHERE LOWER(username)=LOWER(?)
"""

SQL_SELECT_USUARIO_LOGIN_FALLIDO = f"""
    SELECT id,
           username,
           email,
           COALESCE(disabled,0) AS disabled,
           COALESCE(failed_attempts,0) AS failed_attempts,
           fecha_ultimo_intento_fallido,
           ip_ultimo_intento_fallido,
           fecha_bloqueo,
           motivo_bloqueo
    FROM {TABLA_USUARIOS}
    WHERE LOWER(username)=LOWER(?)
"""

SQL_UPDATE_LOGIN_FALLIDO = f"""
UPDATE {TABLA_USUARIOS}
SET
    failed_attempts = ?,
    fecha_ultimo_intento_fallido = ?,
    ip_ultimo_intento_fallido = ?,
    disabled = CASE WHEN ? = 1 THEN 1 ELSE disabled END,
    fecha_bloqueo = CASE WHEN ? = 1 THEN ? ELSE fecha_bloqueo END,
    motivo_bloqueo = CASE WHEN ? = 1 THEN ? ELSE motivo_bloqueo END
WHERE id = ?
"""

SQL_RESETEAR_INTENTOS_FALLIDOS = f"""
    UPDATE {TABLA_USUARIOS}
    SET failed_attempts = 0,
        fecha_ultimo_intento_fallido = NULL,
        ip_ultimo_intento_fallido = NULL,
        fecha_bloqueo = NULL,
        motivo_bloqueo = NULL
    WHERE id = ?
"""

SQL_REGISTRAR_LOGIN_EXITOSO = f"""
    UPDATE {TABLA_USUARIOS}
    SET fecha_ultimo_acceso = ?,
        ip_ultimo_acceso = ?,
        ua_ultimo_acceso = ?
    WHERE id = ?
"""

SQL_UPDATE_PASSWORD_POR_ID = f"""
    UPDATE {TABLA_USUARIOS}
    SET password = ?
    WHERE id = ?
"""

SQL_SELECT_EMAIL_USUARIO_POR_ID = f"""
    SELECT email
    FROM {TABLA_USUARIOS}
    WHERE id = ?
"""

SQL_SELECT_DATOS_CORREO_BLOQUEO = f"""
    SELECT id, username, email, fecha_bloqueo, motivo_bloqueo
    FROM {TABLA_USUARIOS}
    WHERE LOWER(username)=LOWER(?)
"""

SQL_SELECT_USUARIO_POR_USERNAME_O_EMAIL = f"""
    SELECT id, username, email, COALESCE(disabled,0) AS disabled,
           COALESCE(failed_attempts,0) AS failed_attempts,
           fecha_bloqueo, motivo_bloqueo
    FROM {TABLA_USUARIOS}
    WHERE LOWER(username)=LOWER(?) OR LOWER(email)=LOWER(?)
"""

SQL_INSERT_RESET_TOKEN = f"""
    INSERT INTO {TABLA_RESET_TOKENS}
    (user_id, code, expires_at, attempts_left, used)
    OUTPUT INSERTED.id
    VALUES (?, ?, ?, ?, 0)
""" 

SQL_SELECT_RESET_TOKEN_POR_ID = f"""
    SELECT id, user_id, code, expires_at, attempts_left, used
    FROM {TABLA_RESET_TOKENS}
    WHERE id=?
"""

SQL_MARCAR_RESET_TOKEN_USADO = f"""
    UPDATE {TABLA_RESET_TOKENS}
    SET used=1
    WHERE id=?
"""

SQL_UPDATE_RESET_TOKEN_INTENTOS = f"""
    UPDATE {TABLA_RESET_TOKENS}
    SET attempts_left=?
    WHERE id=?
"""

SQL_INSERT_LOGIN_MFA_TOKEN = f"""
    INSERT INTO {TABLA_LOGIN_MFA_TOKENS}
    (user_id, code_hash, expires_at, attempts_left, used)
    OUTPUT INSERTED.id
    VALUES (?, ?, ?, ?, 0)
"""

SQL_SELECT_LOGIN_MFA_TOKEN_POR_ID = f"""
    SELECT id, user_id, code_hash, expires_at, attempts_left, used
    FROM {TABLA_LOGIN_MFA_TOKENS}
    WHERE id = ?
"""

SQL_MARCAR_LOGIN_MFA_TOKEN_USADO = f"""
    UPDATE {TABLA_LOGIN_MFA_TOKENS}
    SET used = 1
    WHERE id = ?
"""

SQL_UPDATE_LOGIN_MFA_TOKEN_INTENTOS = f"""
    UPDATE {TABLA_LOGIN_MFA_TOKENS}
    SET attempts_left = ?
    WHERE id = ?
"""

SQL_BLOQUEAR_USUARIO_POR_INTENTOS_CODIGO = f"""
    UPDATE {TABLA_USUARIOS}
    SET disabled=1,
        fecha_bloqueo=?,
        motivo_bloqueo=?
    WHERE id=?
"""

SQL_ACTUALIZAR_PASSWORD_POR_RECUPERACION = f"""
    UPDATE {TABLA_USUARIOS}
    SET password=?,
        disabled=0,
        failed_attempts=0,
        fecha_ultimo_intento_fallido=NULL,
        ip_ultimo_intento_fallido=NULL,
        fecha_bloqueo=NULL,
        motivo_bloqueo=NULL,
        password_changed_at=?
    WHERE id=?
"""

SQL_ACTUALIZAR_PASSWORD_USUARIO = f"""
    UPDATE {TABLA_USUARIOS}
    SET password=?,
        password_changed_at=?
    WHERE id=?
"""
 

SQL_SELECT_PERMISOS_ROL_ACTUAL = """
    SELECT o.nombre AS opcion,
           COALESCE(rp.ver,0)       AS ver,
           COALESCE(rp.crear,0)     AS crear,
           COALESCE(rp.editar,0)    AS editar,
           COALESCE(rp.eliminar,0)  AS eliminar,
           COALESCE(rp.exportar,0)  AS exportar,
           COALESCE(rp.aprobar,0)   AS aprobar
    FROM {TABLA_ROLES_PERMISOS} rp
    JOIN {TABLA_ROLES}    r ON r.id = rp.rol_id
    JOIN {TABLA_OPCIONES} o ON o.id = rp.opcion_id
    WHERE LOWER(r.nombre) = LOWER(?)
"""

SQL_SELECT_PERMISOS_ROL_LEGACY = """
    SELECT opcion,
           COALESCE(ver,0) ver, COALESCE(crear,0) crear,
           COALESCE(editar,0) editar, COALESCE(eliminar,0) eliminar,
           COALESCE(exportar,0) exportar, COALESCE(aprobar,0) aprobar
    FROM {TABLA_PERMISOS} 
    WHERE LOWER(rol) = LOWER(?)
"""

