# modules/planificador/planificador_querys.py
# -*- coding: utf-8 -*-
"""
Sentencias SQL del módulo Planificador.
Este módulo centraliza todas las queries; planificador_repository.py
las importa y ejecuta — nunca escribe SQL directamente.
"""

# ──────────────────────────────────────────────
# Solicitudes – lectura
# ──────────────────────────────────────────────

SQL_GET_ALL_SOLICITUDES = """
    SELECT s.*
    FROM planificador_solicitudes s
    WHERE {where}
    ORDER BY s.fecha DESC, s.hora_inicio
"""

SQL_GET_SOLICITUDES_BY_TIPOS = """
    SELECT s.*
    FROM planificador_solicitudes s
    WHERE s.activo = 1
      AND s.tipo IN ({placeholders_t})
      AND s.estado IN ({placeholders_e})
      {where_extra}
    ORDER BY s.fecha DESC, s.hora_inicio
"""

SQL_GET_MIS_SOLICITUDES = """
    SELECT s.*
    FROM planificador_solicitudes s
    WHERE {where}
    ORDER BY s.fecha DESC, s.hora_inicio
"""

SQL_GET_SOLICITUD_BY_ID = """
    SELECT *
    FROM planificador_solicitudes
    WHERE id = ? AND activo = 1
"""

SQL_GET_CALENDAR_SOLICITUDES = """
    SELECT id, tipo, area_solicitante, descripcion, lugar_destino,
           fecha, hora_inicio, hora_fin, estado, prioridad,
           solicitante_nombre
    FROM planificador_solicitudes
    WHERE activo = 1
      AND estado IN ('APROBADA', 'PENDIENTE_APROBACION', 'COMPLETADA')
      AND fecha BETWEEN ? AND ?
    ORDER BY fecha, hora_inicio
"""

SQL_GET_SOLICITUDES_PENDIENTE_GERENTE = """
    SELECT s.*
    FROM planificador_solicitudes s
    WHERE s.activo = 1
      AND s.tipo IN ({placeholders})
      AND s.estado = 'PENDIENTE_APROBACION_GERENTE'
      AND s.gerente_id = ?
      {where_extra}
    ORDER BY s.fecha DESC, s.hora_inicio
"""

SQL_GET_SOLICITUDES_PENDIENTES_MISMO_TIPO = """
    SELECT id, area_solicitante, lugar_destino, fecha, descripcion, solicitante_nombre
    FROM planificador_solicitudes
    WHERE tipo = ?
      AND estado = 'PENDIENTE_COORDINACION'
      AND id != ?
      AND activo = 1
    ORDER BY fecha, area_solicitante
"""

SQL_GET_SOLICITUDES_DEL_GRUPO = """
    SELECT id, tipo, area_solicitante, lugar_destino, fecha,
           hora_inicio, hora_fin, estado, solicitante_nombre, solicitante_id
    FROM planificador_solicitudes
    WHERE grupo_id = ? AND activo = 1
    ORDER BY id
"""

SQL_GET_SOLICITUDES_PARA_REPORTE = """
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
    FROM planificador_solicitudes s
    WHERE {where}
    ORDER BY s.fecha DESC, s.hora_inicio
"""

SQL_CHECK_HORARIO_OCUPADO = """
    SELECT TOP 1 id
    FROM planificador_solicitudes
    WHERE tipo = ?
      AND fecha = ?
      AND activo = 1
      AND estado NOT IN ('RECHAZADA','COMPLETADA')
      AND hora_inicio IS NOT NULL
      AND hora_fin   IS NOT NULL
      {excl}
      AND hora_inicio < ?
      AND hora_fin   > ?
"""

SQL_GET_FECHA_SOLICITUD = """
    SELECT fecha
    FROM planificador_solicitudes
    WHERE id = ? AND activo = 1
"""

# ──────────────────────────────────────────────
# Solicitudes – escritura
# ──────────────────────────────────────────────

SQL_INSERT_SOLICITUD = """
    INSERT INTO planificador_solicitudes
        (tipo, area_solicitante, descripcion, lugar_destino, detalle_direccion,
         contacto, prioridad, fecha, estado, solicitante_id, solicitante_nombre,
         ciudad)
    OUTPUT INSERTED.id
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDIENTE_COORDINACION', ?, ?, ?)
"""

SQL_UPDATE_REAGENDAR = """
    UPDATE planificador_solicitudes SET
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

SQL_UPDATE_COORDINAR = """
    UPDATE planificador_solicitudes SET
        hora_inicio             = ?,
        hora_fin                = ?,
        observacion_coordinador = ?,
        coordinador_id          = ?,
        coordinador_nombre      = ?,
        estado                  = 'PENDIENTE_APROBACION',
        fecha_actualizacion     = GETDATE()
    WHERE id = ? AND activo = 1
"""

SQL_UPDATE_COORDINAR_GRUPO = """
    UPDATE planificador_solicitudes SET
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

SQL_UPDATE_APROBAR = """
    UPDATE planificador_solicitudes SET
        estado                = 'APROBADA',
        aprobador_id          = ?,
        aprobador_nombre      = ?,
        observacion_aprobador = ?,
        fecha_actualizacion   = GETDATE()
    WHERE id = ? AND activo = 1
"""

SQL_UPDATE_RECHAZAR = """
    UPDATE planificador_solicitudes SET
        estado                = 'RECHAZADA',
        aprobador_id          = ?,
        aprobador_nombre      = ?,
        observacion_aprobador = ?,
        fecha_actualizacion   = GETDATE()
    WHERE id = ? AND activo = 1
"""

SQL_UPDATE_COMPLETAR = """
    UPDATE planificador_solicitudes SET
        estado              = 'COMPLETADA',
        fecha_actualizacion = GETDATE()
    WHERE id = ? AND activo = 1
"""

SQL_UPDATE_PONER_PENDIENTE_GERENTE = """
    UPDATE planificador_solicitudes SET
        estado              = 'PENDIENTE_APROBACION_GERENTE',
        gerente_id          = ?,
        gerente_nombre      = ?,
        fecha_actualizacion = GETDATE()
    WHERE id = ? AND activo = 1
"""

SQL_UPDATE_APROBAR_GERENTE = """
    UPDATE planificador_solicitudes SET
        estado = 'APROBADA',
        observacion_aprobador = COALESCE(
            CASE WHEN observacion_aprobador IS NOT NULL AND observacion_aprobador <> ''
                 THEN observacion_aprobador + ' | Gerente: ' + ?
                 ELSE ?
            END, ?),
        fecha_actualizacion = GETDATE()
    WHERE id = ? AND activo = 1
"""

SQL_UPDATE_RECHAZAR_GERENTE = """
    UPDATE planificador_solicitudes SET
        estado                = 'RECHAZADA',
        aprobador_id          = ?,
        aprobador_nombre      = ?,
        observacion_aprobador = ?,
        fecha_actualizacion   = GETDATE()
    WHERE id = ? AND activo = 1
"""

SQL_UPDATE_ELIMINAR_SOLICITUD = """
    UPDATE planificador_solicitudes
       SET activo               = 0,
           eliminado_por_id     = ?,
           eliminado_por_nombre = ?,
           fecha_eliminacion    = GETDATE()
     WHERE id = ?
"""

# ──────────────────────────────────────────────
# Grupos de coordinación
# ──────────────────────────────────────────────

SQL_INSERT_GRUPO = """
    INSERT INTO planificador_grupos
        (tipo, fecha, hora_inicio, hora_fin,
         coordinador_id, coordinador_nombre, observacion)
    OUTPUT INSERTED.id
    VALUES (?, ?, ?, ?, ?, ?, ?)
"""

# ──────────────────────────────────────────────
# Configuración coordinadores / aprobadores
# ──────────────────────────────────────────────

SQL_GET_ALL_CONFIG = """
    SELECT *
    FROM planificador_config
    WHERE activo = 1
    ORDER BY tipo, rol_config, usuario_nombre
"""

SQL_GET_CONFIG_FOR_USER = """
    SELECT tipo, rol_config
    FROM planificador_config
    WHERE usuario_id = ? AND activo = 1
"""

SQL_UPSERT_CONFIG = """
    IF NOT EXISTS (
        SELECT 1 FROM planificador_config
        WHERE tipo = ? AND usuario_id = ? AND rol_config = ?
    )
        INSERT INTO planificador_config (tipo, usuario_id, usuario_nombre, rol_config)
        VALUES (?, ?, ?, ?)
    ELSE
        UPDATE planificador_config SET activo = 1, usuario_nombre = ?
        WHERE tipo = ? AND usuario_id = ? AND rol_config = ?
"""

SQL_DELETE_CONFIG = """
    UPDATE planificador_config SET activo = 0 WHERE id = ?
"""

SQL_GET_ROLES_PARA_TIPO = """
    SELECT pc.usuario_id, pc.usuario_nombre, pc.rol_config, u.email
    FROM planificador_config pc
    LEFT JOIN usuarios u ON u.id = pc.usuario_id AND u.disabled = 0
    WHERE pc.tipo = ? AND pc.activo = 1
"""

# ──────────────────────────────────────────────
# Tipos de solicitud
# ──────────────────────────────────────────────

SQL_GET_TIPOS_SOLICITUD = """
    SELECT pv.nombre
    FROM param_values pv
    JOIN param_groups pg ON pg.id = pv.group_id
    WHERE pg.nombre = ?
      AND pv.activo = 1
    ORDER BY pv.orden, pv.nombre
"""

# ──────────────────────────────────────────────
# Tipo flags
# ──────────────────────────────────────────────

SQL_GET_TIPO_FLAGS = """
    SELECT requiere_aprobacion_gerente
    FROM planificador_tipo_flags
    WHERE tipo = ?
"""

SQL_GET_ALL_TIPO_FLAGS = """
    SELECT tipo, requiere_aprobacion_gerente
    FROM planificador_tipo_flags
"""

SQL_UPSERT_TIPO_FLAGS = """
    IF EXISTS (SELECT 1 FROM planificador_tipo_flags WHERE tipo = ?)
        UPDATE planificador_tipo_flags
           SET requiere_aprobacion_gerente = ?
         WHERE tipo = ?
    ELSE
        INSERT INTO planificador_tipo_flags (tipo, requiere_aprobacion_gerente)
        VALUES (?, ?)
"""

# ──────────────────────────────────────────────
# Usuarios y catálogos
# ──────────────────────────────────────────────

SQL_GET_USUARIOS_FOR_SELECT = """
    SELECT id,
           COALESCE(nombre_completo, username) AS nombre,
           username
    FROM usuarios
    WHERE disabled = 0
    ORDER BY nombre_completo, username
"""

SQL_GET_DEPARTAMENTOS = """
    SELECT id, nombre
    FROM departamentos
    ORDER BY nombre
"""

SQL_GET_USUARIO_DEPARTAMENTO = """
    SELECT d.id, d.nombre
    FROM usuarios u
    LEFT JOIN departamentos d ON d.id = u.departamento_id
    WHERE u.id = ?
"""

SQL_GET_EMAIL_BY_USUARIO_ID = """
    SELECT email FROM usuarios WHERE id = ? AND disabled = 0
"""

SQL_GET_CIUDAD_USUARIO = """
    SELECT COALESCE(ciudad, '') FROM usuarios WHERE id = ?
"""

SQL_GET_JEFE_USUARIO = """
    SELECT jefe_id FROM usuarios WHERE id = ? AND COALESCE(disabled,0) = 0
"""

SQL_GET_USUARIO_JERARQUIA = """
    SELECT id, COALESCE(nombre_completo, username) AS nombre,
           email, jefe_id, LOWER(COALESCE(rol,'')) AS rol
    FROM usuarios
    WHERE id = ? AND COALESCE(disabled,0) = 0
"""

SQL_UPDATE_TELEGRAM_CHAT_ID = """
    UPDATE usuarios SET telegram_chat_id = ? WHERE id = ?
"""

SQL_GET_MOTORIZADOS_IDS_EMAILS = """
    SELECT DISTINCT u.id, u.email
    FROM usuarios u
    JOIN puestos p ON p.id = u.puesto_id
    WHERE u.disabled = 0
      AND (p.nombre LIKE '%MOTORIZADO%' OR p.nombre LIKE '%SERVICIOS VARIOS%')
"""

SQL_GET_MOTORIZADOS_EMAIL = """
    SELECT DISTINCT u.email
    FROM usuarios u
    JOIN puestos p ON p.id = u.puesto_id
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

SQL_GET_TELEGRAM_CHAT_IDS_PARA_TIPO = """
    SELECT pc.usuario_id,
           pc.usuario_nombre,
           u.telegram_chat_id
    FROM planificador_config pc
    JOIN usuarios u ON u.id = pc.usuario_id AND u.disabled = 0
    WHERE pc.tipo      = ?
      AND pc.rol_config = 'MOTORIZADO'
      AND pc.activo    = 1
      AND u.telegram_chat_id IS NOT NULL
      AND u.telegram_chat_id <> ''
"""

SQL_GET_MOTORIZADOS_TELEGRAM_STATUS = """
    SELECT pc.usuario_id,
           pc.usuario_nombre,
           pc.tipo,
           u.email,
           u.telegram_chat_id
    FROM planificador_config pc
    LEFT JOIN usuarios u ON u.id = pc.usuario_id
    WHERE pc.rol_config = 'MOTORIZADO'
      AND pc.activo     = 1
    ORDER BY pc.tipo, pc.usuario_nombre
"""

# ──────────────────────────────────────────────
# Logs de trazabilidad
# ──────────────────────────────────────────────

SQL_INSERT_SOLICITUD_LOG = """
    INSERT INTO planificador_solicitud_logs
        (solicitud_id, accion, usuario_id, usuario_nombre, detalle, fecha_log)
    VALUES (?, ?, ?, ?, ?, GETDATE())
"""

SQL_GET_SOLICITUD_LOGS = """
    SELECT accion, usuario_nombre, detalle,
           CONVERT(VARCHAR, fecha_log, 120) AS fecha_log
    FROM planificador_solicitud_logs
    WHERE solicitud_id = ?
    ORDER BY fecha_log ASC
"""

# ──────────────────────────────────────────────
# Notificaciones in-app
# ──────────────────────────────────────────────

SQL_INSERT_NOTIFY_INAPP = """
    INSERT INTO notify_inapp (user_id, title, body, created_at, is_read)
    VALUES (?, ?, ?, ?, 0)
"""
