# modules/users/user_queries.py
# ==========================================================
# SQL del módulo de usuarios.
# Solo define consultas y DDL reutilizables.
# Adaptado para SQL Server.
# ==========================================================

from modules.users.user_constants import (
    TB_USUARIOS,
    TB_DEPARTAMENTOS,
    TB_ROLES,
    TB_AREAS,
    TB_PUESTOS,
    TB_EMPRESAS,
    TB_PARAM_VALUES,
    TB_USUARIOS_CC,
    TB_RECLAMOS,
    TB_RECLAMO_RESPUESTAS,
    TB_GASTOS_TARJETA,
    TB_TAREAS,
    CC_GROUP_ID,
)

SQL_TABLE_EXISTS = """
    SELECT 1
    FROM sys.tables
    WHERE name = ?
"""

SQL_CREATE_USUARIOS_CC = f"""
    IF OBJECT_ID('{TB_USUARIOS_CC}', 'U') IS NULL
    BEGIN
        CREATE TABLE {TB_USUARIOS_CC} (
            usuario_id INT NOT NULL,
            centro_costo_id INT NOT NULL,
            porcentaje DECIMAL(18,2) NOT NULL,
            CONSTRAINT PK_{TB_USUARIOS_CC} PRIMARY KEY (usuario_id, centro_costo_id)
        )
    END
"""

SQL_SELECT_ROLES = f"""
    SELECT nombre
    FROM {TB_ROLES}
    ORDER BY nombre
"""

SQL_SELECT_CENTROS_COSTO = f"""
    SELECT
        pv.id,
        pv.nombre,
        COALESCE(pv.valor,'') AS valor,
        COALESCE(pv.orden,1)  AS orden
    FROM {TB_PARAM_VALUES} pv
    WHERE pv.group_id = ?
      AND COALESCE(pv.activo,1) = 1
    ORDER BY COALESCE(pv.orden,1), pv.nombre
"""

SQL_SELECT_USER_CC_DIST = f"""
    SELECT
        uc.centro_costo_id AS cc_id,
        uc.porcentaje      AS pct,
        COALESCE(pv.nombre,'') AS cc_nombre
    FROM {TB_USUARIOS_CC} uc
    LEFT JOIN {TB_PARAM_VALUES} pv
           ON pv.id = uc.centro_costo_id
          AND pv.group_id = ?
    WHERE uc.usuario_id = ?
    ORDER BY COALESCE(pv.orden,1), pv.nombre, uc.centro_costo_id
"""

SQL_SELECT_VALID_CC_IDS = f"""
    SELECT id
    FROM {TB_PARAM_VALUES}
    WHERE group_id = ?
      AND COALESCE(activo,1) = 1
"""

SQL_DELETE_USER_CC_DIST = f"""
    DELETE FROM {TB_USUARIOS_CC}
    WHERE usuario_id=?
"""

SQL_INSERT_USER_CC_DIST = f"""
    INSERT INTO {TB_USUARIOS_CC}(usuario_id, centro_costo_id, porcentaje)
    VALUES (?,?,?)
"""

SQL_SELECT_USUARIO_EDIT = f"""
    SELECT id, username, email, rol, departamento_id, disabled, cuenta_contable_id,
        nombre_completo, identificacion, sexo,
        fecha_nacimiento, fecha_ingreso,
        provincia, ciudad, direccion,
        empresa_id, area_id, puesto_id,
        tarjeta_alias, tarjeta_last4,
        fecha_registro,
        jefe_id, tiene_caja_chica, tipo_caja_chica, codigo_sap
    FROM {TB_USUARIOS}
    WHERE id=?
"""

SQL_SELECT_DEPARTAMENTOS = f"""
    SELECT id, nombre
    FROM {TB_DEPARTAMENTOS}
    ORDER BY nombre
"""

SQL_SELECT_AREAS_ACTIVAS = f"""
    SELECT id, nombre
    FROM {TB_AREAS}
    WHERE COALESCE(activo,1)=1
    ORDER BY nombre
"""

SQL_SELECT_PUESTOS_ACTIVOS = f"""
    SELECT id, nombre
    FROM {TB_PUESTOS}
    WHERE COALESCE(activo,1)=1
    ORDER BY nombre
"""

SQL_SELECT_EMPRESAS_ACTIVAS = f"""
    SELECT id, razon_social
    FROM {TB_EMPRESAS}
    WHERE COALESCE(activo,1)=1
    ORDER BY razon_social
"""

SQL_SELECT_JEFES_ACTIVOS = f"""
    SELECT id, username, nombre_completo
    FROM {TB_USUARIOS}
    WHERE disabled = 0
    ORDER BY username
"""

SQL_SELECT_EMPRESAS_ACTIVAS_PLAIN = f"""
    SELECT id, razon_social
    FROM {TB_EMPRESAS}
    WHERE activo = 1
    ORDER BY razon_social ASC
"""

SQL_SELECT_USUARIOS_LIST_JEFES = f"""
    SELECT id, username, nombre_completo
    FROM {TB_USUARIOS}
    WHERE disabled = 0
    ORDER BY username
"""

SQL_SELECT_USUARIO_DELETE = f"""
    SELECT id, username, rol, COALESCE(nombre_completo,'') AS nombre_completo
    FROM {TB_USUARIOS}
    WHERE id = ?
"""

SQL_SELECT_COUNT_BY_DYNAMIC_COLUMN = "SELECT COUNT(*) AS c FROM {table} WHERE {column} = ?"

SQL_DELETE_USUARIO_CC_BY_USER = f"""
    DELETE FROM {TB_USUARIOS_CC}
    WHERE usuario_id = ?
"""

SQL_DELETE_USUARIO_BY_ID = f"""
    DELETE FROM {TB_USUARIOS}
    WHERE id = ?
"""

SQL_INSERT_USUARIO = f"""
    INSERT INTO {TB_USUARIOS}(
        username, password, email, rol,
        departamento_id, disabled,
        failed_attempts, password_changed_at,
        nombre_completo, identificacion, sexo,
        fecha_nacimiento, fecha_ingreso,
        provincia, ciudad, direccion,
        empresa_id, area_id, puesto_id,
        tarjeta_alias, tarjeta_last4,
        fecha_registro,
        jefe_id, tiene_caja_chica, tipo_caja_chica
    )
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
"""

SQL_SELECT_USERS_REPORT = f"""
    SELECT
        u.id,
        u.username,
        COALESCE(u.nombre_completo, '')     AS nombre_completo,
        COALESCE(u.identificacion, '')      AS identificacion,
        COALESCE(u.email, '')               AS email,
        COALESCE(u.rol, '')                 AS rol,
        COALESCE(d.nombre, 'Sin depto')     AS departamento,
        COALESCE(a.nombre, '')              AS area,
        COALESCE(p.nombre, '')              AS puesto,
        COALESCE(e.razon_social, '')        AS empresa,
        COALESCE(u.sexo, '')                AS sexo,
        COALESCE(u.fecha_nacimiento, '')    AS fecha_nacimiento,
        COALESCE(u.fecha_ingreso, '')       AS fecha_ingreso,
        COALESCE(u.provincia, '')           AS provincia,
        COALESCE(u.ciudad, '')              AS ciudad,
        COALESCE(u.direccion, '')           AS direccion,
        COALESCE(j.username, '')            AS jefe_username,
        COALESCE(j.nombre_completo, '')     AS jefe_nombre,
        COALESCE(u.fecha_registro, '')      AS fecha_registro,
        COALESCE(u.tarjeta_alias, '')       AS tarjeta_alias,
        COALESCE(u.tarjeta_last4, '')       AS tarjeta_last4,
        COALESCE(u.tiene_caja_chica, 0)     AS tiene_caja_chica,
        COALESCE(u.tipo_caja_chica, 'NINGUNA') AS tipo_caja_chica,
        COALESCE(u.disabled, 0)             AS disabled
    FROM {TB_USUARIOS} u
    LEFT JOIN {TB_DEPARTAMENTOS} d ON d.id = u.departamento_id
    LEFT JOIN {TB_AREAS} a          ON a.id = u.area_id
    LEFT JOIN {TB_PUESTOS} p        ON p.id = u.puesto_id
    LEFT JOIN {TB_EMPRESAS} e       ON e.id = u.empresa_id
    LEFT JOIN {TB_USUARIOS} j       ON j.id = u.jefe_id
    ORDER BY d.nombre, a.nombre, u.nombre_completo
"""

SQL_UPDATE_JEFE_MASIVO_BASE = f"""
    UPDATE {TB_USUARIOS}
    SET jefe_id=?
    WHERE id IN ({{placeholders}})
"""

SQL_INSERT_DEPARTAMENTO = f"""
    INSERT INTO {TB_DEPARTAMENTOS} (nombre)
    VALUES (?)
"""

SQL_SELECT_DEPARTAMENTOS_LIST = f"""
    SELECT id, nombre
    FROM {TB_DEPARTAMENTOS}
    ORDER BY nombre
"""

SQL_SELECT_DEPARTAMENTO_BY_ID = f"""
    SELECT id, nombre
    FROM {TB_DEPARTAMENTOS}
    WHERE id=?
"""

SQL_UPDATE_DEPARTAMENTO = f"""
    UPDATE {TB_DEPARTAMENTOS}
    SET nombre=?
    WHERE id=?
"""

SQL_DELETE_DEPARTAMENTO = f"""
    DELETE FROM {TB_DEPARTAMENTOS}
    WHERE id=?
"""

SQL_INSERT_AREA = f"""
    INSERT INTO {TB_AREAS}(nombre)
    VALUES (?)
"""

SQL_SELECT_AREAS_LIST = f"""
    SELECT id,nombre,activo
    FROM {TB_AREAS}
    ORDER BY nombre
"""

SQL_SELECT_ORGANIGRAMA = f"""
    SELECT
        u.id,
        COALESCE(u.nombre_completo, u.username) AS nombre,
        COALESCE(u.identificacion, '')         AS identificacion,
        COALESCE(u.rol, '')                    AS rol,
        COALESCE(d.nombre, 'Sin departamento') AS departamento,
        COALESCE(j.nombre_completo, j.username) AS jefe_nombre
    FROM {TB_USUARIOS} u
    LEFT JOIN {TB_DEPARTAMENTOS} d ON d.id = u.departamento_id
    LEFT JOIN {TB_USUARIOS} j ON j.id = u.jefe_id
    WHERE COALESCE(u.disabled, 0) = 0
    ORDER BY departamento, nombre
"""

SQL_SELECT_IDENT_TO_ID = f"""
    SELECT id, LOWER(LTRIM(RTRIM(identificacion))) AS ced
    FROM {TB_USUARIOS}
    WHERE identificacion IS NOT NULL
"""

SQL_SELECT_EMAIL_TO_ID = f"""
    SELECT id, LOWER(LTRIM(RTRIM(email))) AS em
    FROM {TB_USUARIOS}
    WHERE email IS NOT NULL
"""

SQL_SELECT_DEPARTAMENTOS_MAP = f"""
    SELECT id, nombre
    FROM {TB_DEPARTAMENTOS}
"""

SQL_SELECT_PUESTOS_MAP = f"""
    SELECT id, nombre
    FROM {TB_PUESTOS}
"""

SQL_SELECT_USUARIO_BY_USERNAME = f"""
    SELECT TOP 1 1
    FROM {TB_USUARIOS}
    WHERE LOWER(username)=LOWER(?)
"""

SQL_SELECT_USUARIO_BY_EMAIL = f"""
    SELECT TOP 1 1
    FROM {TB_USUARIOS}
    WHERE LOWER(email)=LOWER(?)
"""

SQL_INSERT_PUESTO_IF_NOT_EXISTS = f"""
    IF NOT EXISTS (
        SELECT 1
        FROM {TB_PUESTOS}
        WHERE LOWER(nombre)=LOWER(?)
    )
    BEGIN
        INSERT INTO {TB_PUESTOS}(nombre, codigo, activo)
        VALUES (?, ?, 1)
    END
"""

SQL_SELECT_PUESTO_BY_NAME = f"""
    SELECT TOP 1 id
    FROM {TB_PUESTOS}
    WHERE LOWER(nombre)=LOWER(?)
"""

SQL_UPDATE_USUARIO_CON_PASSWORD = f"""
    UPDATE {TB_USUARIOS}
    SET username=?, email=?, rol=?, departamento_id=?, password=?,
        disabled=?, cuenta_contable_id=?, password_changed_at=?,
        nombre_completo=?, identificacion=?, sexo=?,
        fecha_nacimiento=?, fecha_ingreso=?,
        provincia=?, ciudad=?, direccion=?,
        empresa_id=?, area_id=?, puesto_id=?,
        tarjeta_alias=?, tarjeta_last4=?,
        jefe_id=?, tiene_caja_chica=?, tipo_caja_chica=?, codigo_sap=?
    WHERE id=?
"""

SQL_UPDATE_USUARIO_SIN_PASSWORD = f"""
    UPDATE {TB_USUARIOS}
    SET username=?, email=?, rol=?, departamento_id=?,
        disabled=?, cuenta_contable_id=?,
        nombre_completo=?, identificacion=?, sexo=?,
        fecha_nacimiento=?, fecha_ingreso=?,
        provincia=?, ciudad=?, direccion=?,
        empresa_id=?, area_id=?, puesto_id=?,
        tarjeta_alias=?, tarjeta_last4=?,
        jefe_id=?, tiene_caja_chica=?, tipo_caja_chica=?, codigo_sap=?
    WHERE id=?
"""

SQL_UPDATE_USUARIO_BULK_BY_ID = f"""
    UPDATE {TB_USUARIOS}
    SET
        email            = ?,
        nombre_completo  = ?,
        identificacion   = ?,
        sexo             = ?,
        fecha_nacimiento = ?,
        fecha_ingreso    = ?,
        provincia        = ?,
        ciudad           = ?,
        direccion        = ?,
        departamento_id  = ?,
        puesto_id        = ?
    WHERE id = ?
"""

SQL_UPDATE_USUARIO_SET_JEFE = f"""
    UPDATE {TB_USUARIOS}
    SET jefe_id = ?
    WHERE id = ?
"""

SQL_UPDATE_USUARIO_SET_JEFE_NULL = f"""
    UPDATE {TB_USUARIOS}
    SET jefe_id = NULL
    WHERE id = ?
"""

USERS_DELETE_CHECKS = [
    (TB_RECLAMOS, "creado_por", "OM/Reclamos creados"),
    (TB_RECLAMOS, "jefe_id", "asignado como jefe"),
    (TB_RECLAMO_RESPUESTAS, "usuario_id", "respuestas en reclamos"),
    (TB_GASTOS_TARJETA, "usuario_id", "gastos ingresados"),
    (TB_GASTOS_TARJETA, "aprobado_ga_por", "aprobaciones GA"),
    (TB_GASTOS_TARJETA, "aprobado_gf_por", "aprobaciones GF"),
    (TB_GASTOS_TARJETA, "aprobado_gg_por", "aprobaciones GG"),
    (TB_TAREAS, "creado_por", "tareas creadas"),
    (TB_TAREAS, "asignado_a", "tareas asignadas"),
    (TB_USUARIOS, "jefe_id", "usuarios que lo tienen como jefe"),
    (TB_USUARIOS_CC, "usuario_id", "distribución de centros de costo"),
]