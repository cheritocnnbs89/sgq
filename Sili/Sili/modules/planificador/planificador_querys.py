# modules/planificador/planificador_querys.py
# -*- coding: utf-8 -*-
"""
Sentencias SQL del módulo Planificador.
Los nombres de tabla se importan desde planificador_constants.py.
planificador_repository.py importa estas constantes y las ejecuta.
"""

from .planificador_constants import (
    TBL_SOLICITUDES,
    TBL_CONFIG,
    TBL_GRUPOS,
    TBL_LOGS,
    TBL_TIPO_FLAGS,
    TBL_NOTIFY_INAPP,
    TBL_USUARIOS,
    TBL_DEPARTAMENTOS,
    TBL_PUESTOS,
    TBL_PARAM_VALUES,
    TBL_PARAM_GROUPS,
)

# ──────────────────────────────────────────────
# Solicitudes – lectura
# ──────────────────────────────────────────────

SQL_GET_ALL_SOLICITUDES = f"""
    SELECT s.*
    FROM {TBL_SOLICITUDES} s
    WHERE {{where}}
    ORDER BY s.fecha DESC, s.hora_inicio
"""

SQL_GET_SOLICITUDES_BY_TIPOS = f"""
    SELECT s.*
    FROM {TBL_SOLICITUDES} s
    WHERE s.activo = 1
      AND s.tipo IN ({{placeholders_t}})
      AND s.estado IN ({{placeholders_e}})
      {{where_extra}}
    ORDER BY s.fecha DESC, s.hora_inicio
"""

SQL_GET_MIS_SOLICITUDES = f"""
    SELECT s.*
    FROM {TBL_SOLICITUDES} s
    WHERE {{where}}
    ORDER BY s.fecha DESC, s.hora_inicio
"""

SQL_GET_SOLICITUD_BY_ID = f"""
    SELECT *
    FROM {TBL_SOLICITUDES}
    WHERE id = ? AND activo = 1
"""

SQL_GET_CALENDAR_SOLICITUDES = f"""
    SELECT id, tipo, area_solicitante, descripcion, lugar_destino,
           fecha, hora_inicio, hora_fin, estado, prioridad,
           solicitante_nombre
    FROM {TBL_SOLICITUDES}
    WHERE activo = 1
      AND estado IN ('APROBADA', 'PENDIENTE_APROBACION', 'COMPLETADA')
      AND fecha BETWEEN ? AND ?
    ORDER BY fecha, hora_inicio
"""

SQL_GET_SOLICITUDES_PENDIENTE_GERENTE = f"""
    SELECT s.*
    FROM {TBL_SOLICITUDES} s
    WHERE s.activo = 1
      AND s.tipo IN ({{placeholders}})
      AND s.estado = 'PENDIENTE_APROBACION_GERENTE'
      AND s.gerente_id = ?
      {{where_extra}}
    ORDER BY s.fecha DESC, s.hora_inicio
"""

SQL_GET_SOLICITUDES_PENDIENTES_MISMO_TIPO = f"""
    SELECT id, area_solicitante, lugar_destino, fecha, descripcion, solicitante_nombre
    FROM {TBL_SOLICITUDES}
    WHERE tipo = ?
      AND estado = 'PENDIENTE_COORDINACION'
      AND id != ?
      AND activo = 1
    ORDER BY fecha, area_solicitante
"""

SQL_GET_SOLICITUDES_DEL_GRUPO = f"""
    SELECT id, tipo, area_solicitante, lugar_destino, fecha,
           hora_inicio, hora_fin, estado, solicitante_nombre, solicitante_id
    FROM {TBL_SOLICITUDES}
    WHERE grupo_id = ? AND activo = 1
    ORDER BY id
"""

SQL_GET_SOLICITUDES_PARA_REPORTE = f"""
    SELECT
        s.id                                       AS [N° Solicitud],
        s.tipo                                     AS [Tipo],
        s.area_solicitante                         AS [Área Solicitante],
        COALESCE(s.ciudad,'')                      AS [Ciudad],
        s.descripcion                              AS [Descripción],
        s.lugar_destino                            AS [Lugar / Destino],
        COALESCE(s.detalle_direccion,'')           AS [Detalle Dirección],
        s.contacto                                 AS [Contacto],
        s.prioridad                                AS [Prioridad],
        CONVERT(VARCHAR,s.fecha,23)                AS [Fecha],
        s.hora_inicio                              AS [Hora Inicio],
        s.hora_fin                                 AS [Hora Fin],
        s.estado                                   AS [Estado],
        s.solicitante_nombre                       AS [Solicitante],
        s.coordinador_nombre                       AS [Coordinador],
        s.aprobador_nombre                         AS [Aprobador],
        s.observacion_coordinador                  AS [Obs. Coordinador],
        s.observacion_aprobador                    AS [Obs. Aprobador],
        CONVERT(VARCHAR,s.fecha_creacion,120)      AS [Fecha Creación],
        CONVERT(VARCHAR,s.fecha_actualizacion,120) AS [Última Actualización]
    FROM {TBL_SOLICITUDES} s
    WHERE {{where}}
    ORDER BY s.fecha DESC, s.hora_inicio
"""

SQL_CHECK_HORARIO_OCUPADO = f"""
    SELECT TOP 1 id
    FROM {TBL_SOLICITUDES}
    WHERE tipo = ?
      AND fecha = ?
      AND activo = 1
      AND estado NOT IN ('RECHAZADA','COMPLETADA')
      AND hora_inicio IS NOT NULL
      AND hora_fin   IS NOT NULL
      {{excl}}
      AND hora_inicio < ?
      AND hora_fin   > ?
"""

SQL_GET_FECHA_SOLICITUD = f"""
    SELECT fecha
    FROM {TBL_SOLICITUDES}
    WHERE id = ? AND activo = 1
"""

# ──────────────────────────────────────────────
# Solicitudes – escritura
# ──────────────────────────────────────────────

SQL_INSERT_SOLICITUD = f"""
    INSERT INTO {TBL_SOLICITUDES}
        (tipo, area_solicitante, descripcion, lugar_destino, detalle_direccion,
         contacto, prioridad, fecha, estado, solicitante_id, solicitante_nombre,
         ciudad)
    OUTPUT INSERTED.id
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDIENTE_COORDINACION', ?, ?, ?)
"""

SQL_UPDATE_REAGENDAR = f"""
    UPDATE {TBL_SOLICITUDES} SET
        fecha                   = ?,
        estado                  = 'PENDIENTE_COORDINACION',
        hora_inicio             = NULL,
        hora_fin                = NULL,
        coordinador_id          = NULL,
        coordinador_nombre      = NULL,
        observacion_coordinador = NULL,
        fecha_actualizacion     = GETDATE()
    WHERE id = ? AND activo = 1
"""

SQL_UPDATE_COORDINAR = f"""
    UPDATE {TBL_SOLICITUDES} SET
        hora_inicio             = ?,
        hora_fin                = ?,
        observacion_coordinador = ?,
        coordinador_id          = ?,
        coordinador_nombre      = ?,
        estado                  = 'PENDIENTE_APROBACION',
        fecha_actualizacion     = GETDATE()
    WHERE id = ? AND activo = 1
"""

SQL_UPDATE_COORDINAR_GRUPO = f"""
    UPDATE {TBL_SOLICITUDES} SET
        hora_inicio             = ?,
        hora_fin                = ?,
        observacion_coordinador = ?,
        coordinador_id          = ?,
        coordinador_nombre      = ?,
        grupo_id                = ?,
        estado                  = 'PENDIENTE_APROBACION',
        fecha_actualizacion     = GETDATE()
    WHERE id = ? AND activo = 1
"""

SQL_UPDATE_APROBAR = f"""
    UPDATE {TBL_SOLICITUDES} SET
        estado                = 'APROBADA',
        aprobador_id          = ?,
        aprobador_nombre      = ?,
        observacion_aprobador = ?,
        fecha_actualizacion   = GETDATE()
    WHERE id = ? AND activo = 1
"""

SQL_UPDATE_RECHAZAR = f"""
    UPDATE {TBL_SOLICITUDES} SET
        estado                = 'RECHAZADA',
        aprobador_id          = ?,
        aprobador_nombre      = ?,
        observacion_aprobador = ?,
        fecha_actualizacion   = GETDATE()
    WHERE id = ? AND activo = 1
"""

SQL_UPDATE_COMPLETAR = f"""
    UPDATE {TBL_SOLICITUDES} SET
        estado              = 'COMPLETADA',
        fecha_actualizacion = GETDATE()
    WHERE id = ? AND activo = 1
"""

SQL_UPDATE_PONER_PENDIENTE_GERENTE = f"""
    UPDATE {TBL_SOLICITUDES} SET
        estado              = 'PENDIENTE_APROBACION_GERENTE',
        gerente_id          = ?,
        gerente_nombre      = ?,
        fecha_actualizacion = GETDATE()
    WHERE id = ? AND activo = 1
"""

SQL_UPDATE_APROBAR_GERENTE = f"""
    UPDATE {TBL_SOLICITUDES} SET
        estado = 'APROBADA',
        observacion_aprobador = COALESCE(
            CASE WHEN observacion_aprobador IS NOT NULL AND observacion_aprobador <> ''
                 THEN observacion_aprobador + ' | Gerente: ' + ?
                 ELSE ?
            END, ?),
        fecha_actualizacion = GETDATE()
    WHERE id = ? AND activo = 1
"""

SQL_UPDATE_RECHAZAR_GERENTE = f"""
    UPDATE {TBL_SOLICITUDES} SET
        estado                = 'RECHAZADA',
        aprobador_id          = ?,
        aprobador_nombre      = ?,
        observacion_aprobador = ?,
        fecha_actualizacion   = GETDATE()
    WHERE id = ? AND activo = 1
"""

SQL_UPDATE_ELIMINAR_SOLICITUD = f"""
    UPDATE {TBL_SOLICITUDES}
       SET activo               = 0,
           eliminado_por_id     = ?,
           eliminado_por_nombre = ?,
           fecha_eliminacion    = GETDATE()
     WHERE id = ?
"""

# ──────────────────────────────────────────────
# Grupos de coordinación
# ──────────────────────────────────────────────

SQL_INSERT_GRUPO = f"""
    INSERT INTO {TBL_GRUPOS}
        (tipo, fecha, hora_inicio, hora_fin,
         coordinador_id, coordinador_nombre, observacion)
    OUTPUT INSERTED.id
    VALUES (?, ?, ?, ?, ?, ?, ?)
"""

# ──────────────────────────────────────────────
# Configuración coordinadores / aprobadores
# ──────────────────────────────────────────────

SQL_GET_ALL_CONFIG = f"""
    SELECT *
    FROM {TBL_CONFIG}
    WHERE activo = 1
    ORDER BY tipo, rol_config, usuario_nombre
"""

SQL_GET_CONFIG_FOR_USER = f"""
    SELECT tipo, rol_config
    FROM {TBL_CONFIG}
    WHERE usuario_id = ? AND activo = 1
"""

SQL_UPSERT_CONFIG = f"""
    IF NOT EXISTS (
        SELECT 1 FROM {TBL_CONFIG}
        WHERE tipo = ? AND usuario_id = ? AND rol_config = ?
    )
        INSERT INTO {TBL_CONFIG} (tipo, usuario_id, usuario_nombre, rol_config)
        VALUES (?, ?, ?, ?)
    ELSE
        UPDATE {TBL_CONFIG} SET activo = 1, usuario_nombre = ?
        WHERE tipo = ? AND usuario_id = ? AND rol_config = ?
"""

SQL_DELETE_CONFIG = f"""
    UPDATE {TBL_CONFIG} SET activo = 0 WHERE id = ?
"""

SQL_GET_ROLES_PARA_TIPO = f"""
    SELECT pc.usuario_id, pc.usuario_nombre, pc.rol_config, u.email
    FROM {TBL_CONFIG} pc
    LEFT JOIN {TBL_USUARIOS} u ON u.id = pc.usuario_id AND u.disabled = 0
    WHERE pc.tipo = ? AND pc.activo = 1
"""

# ──────────────────────────────────────────────
# Tipos de solicitud
# ──────────────────────────────────────────────

SQL_GET_TIPOS_SOLICITUD = f"""
    SELECT pv.nombre
    FROM {TBL_PARAM_VALUES} pv
    JOIN {TBL_PARAM_GROUPS} pg ON pg.id = pv.group_id
    WHERE pg.nombre = ?
      AND pv.activo = 1
    ORDER BY pv.orden, pv.nombre
"""

# ──────────────────────────────────────────────
# Tipo flags
# ──────────────────────────────────────────────

SQL_GET_TIPO_FLAGS = f"""
    SELECT requiere_aprobacion_gerente
    FROM {TBL_TIPO_FLAGS}
    WHERE tipo = ?
"""

SQL_GET_ALL_TIPO_FLAGS = f"""
    SELECT tipo, requiere_aprobacion_gerente
    FROM {TBL_TIPO_FLAGS}
"""

SQL_UPSERT_TIPO_FLAGS = f"""
    IF EXISTS (SELECT 1 FROM {TBL_TIPO_FLAGS} WHERE tipo = ?)
        UPDATE {TBL_TIPO_FLAGS}
           SET requiere_aprobacion_gerente = ?
         WHERE tipo = ?
    ELSE
        INSERT INTO {TBL_TIPO_FLAGS} (tipo, requiere_aprobacion_gerente)
        VALUES (?, ?)
"""

# ──────────────────────────────────────────────
# Usuarios y catálogos
# ──────────────────────────────────────────────

SQL_GET_USUARIOS_FOR_SELECT = f"""
    SELECT id,
           COALESCE(nombre_completo, username) AS nombre,
           username
    FROM {TBL_USUARIOS}
    WHERE disabled = 0
    ORDER BY nombre_completo, username
"""

SQL_GET_DEPARTAMENTOS = f"""
    SELECT id, nombre
    FROM {TBL_DEPARTAMENTOS}
    ORDER BY nombre
"""

SQL_GET_USUARIO_DEPARTAMENTO = f"""
    SELECT d.id, d.nombre
    FROM {TBL_USUARIOS} u
    LEFT JOIN {TBL_DEPARTAMENTOS} d ON d.id = u.departamento_id
    WHERE u.id = ?
"""

SQL_GET_EMAIL_BY_USUARIO_ID = f"""
    SELECT email FROM {TBL_USUARIOS} WHERE id = ? AND disabled = 0
"""

SQL_GET_CIUDAD_USUARIO = f"""
    SELECT COALESCE(ciudad, '') FROM {TBL_USUARIOS} WHERE id = ?
"""

SQL_GET_JEFE_USUARIO = f"""
    SELECT jefe_id FROM {TBL_USUARIOS} WHERE id = ? AND COALESCE(disabled,0) = 0
"""

SQL_GET_USUARIO_JERARQUIA = f"""
    SELECT id, COALESCE(nombre_completo, username) AS nombre,
           email, jefe_id, LOWER(COALESCE(rol,'')) AS rol
    FROM {TBL_USUARIOS}
    WHERE id = ? AND COALESCE(disabled,0) = 0
"""

SQL_UPDATE_TELEGRAM_CHAT_ID = f"""
    UPDATE {TBL_USUARIOS} SET telegram_chat_id = ? WHERE id = ?
"""

SQL_GET_MOTORIZADOS_IDS_EMAILS = f"""
    SELECT DISTINCT u.id, u.email
    FROM {TBL_USUARIOS} u
    JOIN {TBL_PUESTOS} p ON p.id = u.puesto_id
    WHERE u.disabled = 0
      AND (p.nombre LIKE '%MOTORIZADO%' OR p.nombre LIKE '%SERVICIOS VARIOS%')
"""

SQL_GET_MOTORIZADOS_EMAIL = f"""
    SELECT DISTINCT u.email
    FROM {TBL_USUARIOS} u
    JOIN {TBL_PUESTOS} p ON p.id = u.puesto_id
    WHERE u.disabled = 0
      AND u.email IS NOT NULL
      AND u.email <> ''
      AND (
          p.nombre LIKE '%MOTORIZADO%'
          OR p.nombre LIKE '%SERVICIOS VARIOS%'
      )
"""

# ──────────────────────────────────────────────
# Telegram
# ──────────────────────────────────────────────

SQL_GET_TELEGRAM_CHAT_IDS_PARA_TIPO = f"""
    SELECT pc.usuario_id,
           pc.usuario_nombre,
           u.telegram_chat_id
    FROM {TBL_CONFIG} pc
    JOIN {TBL_USUARIOS} u ON u.id = pc.usuario_id AND u.disabled = 0
    WHERE pc.tipo      = ?
      AND pc.rol_config = 'MOTORIZADO'
      AND pc.activo    = 1
      AND u.telegram_chat_id IS NOT NULL
      AND u.telegram_chat_id <> ''
"""

SQL_GET_MOTORIZADOS_TELEGRAM_STATUS = f"""
    SELECT pc.usuario_id,
           pc.usuario_nombre,
           pc.tipo,
           u.email,
           u.telegram_chat_id
    FROM {TBL_CONFIG} pc
    LEFT JOIN {TBL_USUARIOS} u ON u.id = pc.usuario_id
    WHERE pc.rol_config = 'MOTORIZADO'
      AND pc.activo     = 1
    ORDER BY pc.tipo, pc.usuario_nombre
"""

# ──────────────────────────────────────────────
# Logs de trazabilidad
# ──────────────────────────────────────────────

SQL_INSERT_SOLICITUD_LOG = f"""
    INSERT INTO {TBL_LOGS}
        (solicitud_id, accion, usuario_id, usuario_nombre, detalle, fecha_log)
    VALUES (?, ?, ?, ?, ?, GETDATE())
"""

SQL_GET_SOLICITUD_LOGS = f"""
    SELECT accion, usuario_nombre, detalle,
           CONVERT(VARCHAR, fecha_log, 120) AS fecha_log
    FROM {TBL_LOGS}
    WHERE solicitud_id = ?
    ORDER BY fecha_log ASC
"""

# ──────────────────────────────────────────────
# Notificaciones in-app
# ──────────────────────────────────────────────

SQL_INSERT_NOTIFY_INAPP = f"""
    INSERT INTO {TBL_NOTIFY_INAPP} (user_id, title, body, created_at, is_read)
    VALUES (?, ?, ?, ?, 0)
"""
