# modules/scheduler/scheduler_queries.py
# ==========================================================
# Queries SQL del scheduler.
# Aquí se centralizan los SQL reutilizables del módulo.
# ==========================================================

from modules.scheduler.scheduler_constants import (
    TB_NOTIFY_QUEUE,
    TB_NOTIFY_TEMPLATES,
    TB_NOTIFY_USER_PREFS,
    TB_NOTIFY_INAPP,
    TB_GASTOS_TARJETA,
    TB_USUARIOS,
    TB_TAREAS,
    TB_PLAN_TAREAS,
    TB_PLAN_RESPONSABLES,
    TB_PLAN_CHECKS,
    TB_DEPARTAMENTOS,
    TB_TERCEROS,
    TB_RECLAMO_IMPUTADOS,
    TB_RECLAMOS,
    TB_PUESTOS,
)

SQL_CREATE_NOTIFY_QUEUE = f"""
  CREATE TABLE IF NOT EXISTS {TB_NOTIFY_QUEUE}(
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER,
    tarea_id      INTEGER,
    tipo          TEXT NOT NULL,
    fecha_obj     DATE,
    canal         TEXT NOT NULL,
    estado        TEXT NOT NULL DEFAULT 'pending',
    scheduled_at  TEXT,
    sent_at       TEXT,
    error_msg     TEXT,
    template_key  TEXT,
    payload_json  TEXT
  )
"""

SQL_CREATE_NOTIFY_TEMPLATES = f"""
  CREATE TABLE IF NOT EXISTS {TB_NOTIFY_TEMPLATES}(
    key     TEXT PRIMARY KEY,
    tipo    TEXT NOT NULL,
    subject TEXT NOT NULL,
    html    TEXT NOT NULL,
    text    TEXT
  )
"""

SQL_CREATE_NOTIFY_USER_PREFS = f"""
  CREATE TABLE IF NOT EXISTS {TB_NOTIFY_USER_PREFS}(
    user_id       INTEGER PRIMARY KEY,
    email_on      INTEGER DEFAULT 1,
    inapp_on      INTEGER DEFAULT 1,
    slack_on      INTEGER DEFAULT 0,
    slack_webhook TEXT,
    quiet_start   TEXT,
    quiet_end     TEXT,
    daily_time    TEXT,
    weekly_dow    TEXT,
    weekly_time   TEXT
  )
"""

SQL_CREATE_NOTIFY_INAPP = f"""
  CREATE TABLE IF NOT EXISTS {TB_NOTIFY_INAPP}(
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    title      TEXT NOT NULL,
    body       TEXT NOT NULL,
    created_at TEXT NOT NULL,
    is_read    INTEGER NOT NULL DEFAULT 0
  )
"""

SQL_DELETE_NOTIFY_QUEUE_NON_GASTO_DUPLICATES = f"""
    DELETE FROM {TB_NOTIFY_QUEUE}
     WHERE tipo NOT LIKE 'gasto_%'
       AND id NOT IN (
            SELECT MAX(id)
              FROM {TB_NOTIFY_QUEUE}
             WHERE tipo NOT LIKE 'gasto_%'
             GROUP BY user_id, tipo, fecha_obj, canal
       )
"""

SQL_CREATE_UQ_NOTIFY_QUEUE_ONCE = f"""
    CREATE UNIQUE INDEX IF NOT EXISTS uq_notify_queue_once
    ON {TB_NOTIFY_QUEUE}(user_id, tipo, fecha_obj, canal)
    WHERE tipo NOT LIKE 'gasto_%'
"""

SQL_CREATE_IX_NOTIFY_QUEUE_PENDING = f"""
  CREATE INDEX IF NOT EXISTS ix_notify_queue_pending
  ON {TB_NOTIFY_QUEUE}(estado, scheduled_at)
"""

SQL_CREATE_UQ_NOTIFY_HOY = f"""
    CREATE UNIQUE INDEX IF NOT EXISTS uq_notify_hoy
    ON {TB_NOTIFY_QUEUE}(user_id, fecha_obj, canal, tipo)
    WHERE tipo='hoy'
"""

SQL_CREATE_UQ_NOTIFY_GASTO_EVENT = f"""
    CREATE UNIQUE INDEX IF NOT EXISTS uq_notify_gasto_event
    ON {TB_NOTIFY_QUEUE}(user_id, gasto_id, area, tipo, canal)
    WHERE tipo LIKE 'gasto_%'
"""

SQL_SELECT_PLAN_USERS_HOY = f"""
  DECLARE @dow INT = DATEPART(WEEKDAY, GETDATE());
  DECLARE @dow_monday_zero INT =
      CASE @dow
        WHEN 2 THEN 0
        WHEN 3 THEN 1
        WHEN 4 THEN 2
        WHEN 5 THEN 3
        WHEN 6 THEN 4
        WHEN 7 THEN 5
        WHEN 1 THEN 6
      END;

  SELECT DISTINCT u.id AS user_id, u.username
  FROM {TB_PLAN_TAREAS} t
  JOIN {TB_PLAN_RESPONSABLES} r ON r.id = t.responsable_id
  JOIN {TB_USUARIOS} u ON LOWER(u.username) = LOWER(r.nombre)
  WHERE t.activo = 1
    AND (
         t.frecuencia = 'Diario'
      OR (t.frecuencia = 'Semanal' AND (t.dia_semana IS NULL OR t.dia_semana = @dow_monday_zero))
      OR (t.frecuencia = 'Mensual' AND (t.dia_mes IS NULL OR t.dia_mes = DAY(GETDATE())))
    );
"""










SQL_SELECT_NOTIFY_PENDING_IDS = f"""
    SELECT TOP 100 id
      FROM {TB_NOTIFY_QUEUE}
     WHERE estado = 'pending'
       AND (scheduled_at IS NULL OR scheduled_at <= GETDATE())
     ORDER BY id
"""

SQL_SELECT_NOTIFY_ROW = f"""
  SELECT q.*, u.email, u.username,
         COALESCE(p.email_on,1)  AS email_on,
         COALESCE(p.inapp_on,1)  AS inapp_on,
         COALESCE(p.slack_on,0)  AS slack_on,
         p.slack_webhook, p.quiet_start, p.quiet_end,
         nt.subject, nt.html, nt.text
    FROM {TB_NOTIFY_QUEUE} q
    JOIN {TB_USUARIOS} u ON u.id = q.user_id
    LEFT JOIN {TB_NOTIFY_USER_PREFS} p ON p.user_id = q.user_id
    LEFT JOIN {TB_NOTIFY_TEMPLATES} nt ON nt.[key] = q.template_key
   WHERE q.id=?
"""

SQL_SELECT_TASKS_FOR_USER_BY_DATE = f"""
  SELECT
    t.id, t.nombre, t.frecuencia,
    d.nombre AS departamento,
    r.nombre AS responsable,
    CASE WHEN EXISTS (
      SELECT 1 FROM {TB_PLAN_CHECKS} c
      WHERE c.tarea_id = t.id AND c.fecha = ?
    ) THEN 1 ELSE 0 END AS hecha
  FROM {TB_PLAN_TAREAS} t
  JOIN {TB_PLAN_RESPONSABLES} r ON r.id = t.responsable_id
  JOIN {TB_USUARIOS} u ON LOWER(u.username) = LOWER(r.nombre)
  LEFT JOIN {TB_DEPARTAMENTOS} d ON d.id = t.departamento_id
  WHERE t.activo = 1
    AND (
      t.frecuencia = 'Diario'
      OR (
        t.frecuencia = 'Semanal'
        AND (t.dia_semana IS NULL OR t.dia_semana = ((CAST(strftime('%w', ?) AS INTEGER) + 6) % 7))
      )
      OR (
        t.frecuencia = 'Mensual'
        AND (t.dia_mes IS NULL OR t.dia_mes = CAST(strftime('%d', ?) AS INTEGER))
      )
    )
    AND u.id = ?
  ORDER BY d.nombre, t.nombre
"""

SQL_SELECT_OVERDUE_TASKS = f"""
    SELECT t.id, t.titulo, t.fecha_fin, t.estado, t.notificado,
           u.id AS user_id, u.username AS username, u.email AS user_email
      FROM {TB_TAREAS} t
      JOIN {TB_USUARIOS} u ON t.usuario_id = u.id
     WHERE t.estado != 'Terminado'
       AND COALESCE(t.notificado,0)=0
       AND datetime(t.fecha_fin) < datetime('now')
"""

SQL_SELECT_DAILY_REPORT_TASKS = f"""
    SELECT t.id, t.titulo, t.descripcion, t.estado, t.fecha_creacion,
           t.fecha_inicio, t.fecha_fin, u.username AS usuario
      FROM {TB_TAREAS} t
      JOIN {TB_USUARIOS} u ON t.usuario_id = u.id
     WHERE date(t.fecha_creacion) = ?
     ORDER BY t.id
"""

SQL_SELECT_ADMIN_EMAILS = f"""
    SELECT email
    FROM {TB_USUARIOS}
    WHERE rol='admin'
"""

SQL_SELECT_OM_CANDIDATOS = f"""
    SELECT
        ri.id AS imputacion_id,
        ri.reclamo_id,
        ri.imputado_id AS sponsor_id,

        COALESCE(ri.estado_asignacion, '') AS estado_asignacion,
        COALESCE(ri.estado_respuesta, '') AS estado_respuesta,

        ri.om_notif_d4_at,
        ri.om_notif_d5_at,
        ri.om_notif_d9_at,
        ri.om_notif_d10_at,

        r.codigo,
        COALESCE(r.cliente_nombre, '') AS cliente,
        COALESCE(r.proceso_text, '') AS proceso,
        COALESCE(r.observacion, '') AS observacion,
        CONVERT(date, r.fecha_creacion) AS fecha_base,

        DATEDIFF(day, CONVERT(date, r.fecha_creacion), CONVERT(date, GETDATE())) AS dias

    FROM {TB_RECLAMO_IMPUTADOS} ri
    JOIN {TB_RECLAMOS} r ON r.id = ri.reclamo_id
    WHERE ri.estado_asignacion = 'aprobado'
      AND COALESCE(LTRIM(RTRIM(ri.estado_respuesta)), 'sin_respuesta') = 'sin_respuesta'
      AND r.fecha_creacion IS NOT NULL
      AND CONVERT(date, r.fecha_creacion) >= '2026-03-13'
"""


SQL_SELECT_USER_CONTACT = f"""
    SELECT top 1
        id,
        COALESCE(
            NULLIF(TRIM(nombre_completo), ''),
            NULLIF(TRIM(username), ''),
            'Usuario'
        ) AS nombre,
        COALESCE(TRIM(username), '') AS username,
        COALESCE(TRIM(email), '') AS email
    FROM {TB_USUARIOS}
    WHERE id = ?
      AND COALESCE(disabled, 0) = 0
    
"""

SQL_SELECT_GERENTE_GENERAL_IDS = f"""
    SELECT id
    FROM {TB_USUARIOS}
    WHERE LOWER(TRIM(rol)) = 'gerente general'
      AND COALESCE(disabled,0)=0
    ORDER BY id
"""

SQL_SELECT_SC_IDS_JOIN_DEPARTAMENTOS = f"""
    SELECT u.id
    FROM {TB_USUARIOS} u
    JOIN {TB_DEPARTAMENTOS} d ON d.id = u.departamento_id
    WHERE LOWER(TRIM(COALESCE(d.nombre,''))) = 'servicio al cliente'
      AND COALESCE(u.disabled,0)=0
"""

SQL_SELECT_SC_IDS_USUARIO_DEPARTAMENTO = f"""
    SELECT id
    FROM {TB_USUARIOS}
    WHERE LOWER(TRIM(COALESCE(departamento,''))) = 'servicio al cliente'
      AND COALESCE(disabled,0)=0
"""

SQL_SELECT_SC_IDS_PUESTO = f"""
    SELECT u.id
    FROM {TB_USUARIOS} u
    LEFT JOIN {TB_PUESTOS} p ON p.id = u.puesto_id
    WHERE UPPER(TRIM(COALESCE(p.nombre,''))) LIKE '%SERVICIO AL CLIENTE%'
      AND COALESCE(u.disabled,0)=0
"""

SQL_SELECT_GASTOS_WARN = f"""
    SELECT
        g.id,
        g.created_at,
        g.fecha,
        g.motivo,
        g.usuario_id,
        COALESCE(g.ga_aprobado,0) AS ga_aprobado,
        COALESCE(g.gg_aprobado,0) AS gg_aprobado,
        COALESCE(g.gf_aprobado,0) AS gf_aprobado,
        TRIM(COALESCE(g.sap_contabilizacion,'')) AS sap_contabilizacion,
        COALESCE(g.inactivo,0) AS inactivo,
        g.warn_sent_at
    FROM {TB_GASTOS_TARJETA} g
    WHERE COALESCE(g.inactivo,0)=0
      AND TRIM(COALESCE(g.sap_contabilizacion,''))=''
      AND COALESCE(g.ga_aprobado,0)=0
      AND COALESCE(g.gg_aprobado,0)=0
      AND COALESCE(g.gf_aprobado,0)=0
      AND g.warn_sent_at IS NULL
      AND date(g.created_at,'localtime') <= date('now','localtime','-6 day')
      AND date(g.created_at,'localtime') >  date('now','localtime','-7 day')
    ORDER BY date(g.created_at) ASC, g.id ASC
"""

SQL_SELECT_GASTOS_EXPIRE = f"""
    SELECT g.*
    FROM {TB_GASTOS_TARJETA} g
    WHERE COALESCE(g.inactivo,0)=0
      AND TRIM(COALESCE(g.sap_contabilizacion,''))=''
      AND COALESCE(g.ga_aprobado,0)=0
      AND COALESCE(g.gg_aprobado,0)=0
      AND COALESCE(g.gf_aprobado,0)=0
      AND date(g.created_at,'localtime') <= date('now','localtime','-7 day')
    ORDER BY date(g.created_at) ASC, g.id ASC
"""



SQL_SELECT_OM_ACCIONES_SEGUIMIENTO = """
    SELECT
        a.id AS accion_id,
        a.reclamo_id,
        a.imputacion_id,
        a.tipo,
        a.descripcion,
        CAST(a.fecha_compromiso AS date) AS fecha_compromiso,
        COALESCE(a.cumplido, 0) AS cumplido,

        a.notif_15d_at,
        a.notif_10d_at,
        a.notif_5d_at,
        a.notif_0d_at,
        a.notif_overdue_at,
        a.notif_overdue_last_date,

        r.codigo,
        r.fecha_reclamo,
        r.cliente_nombre,
        r.proceso_text,
        r.observacion,
        r.creado_por AS creador_id,
        r.estado_global,

        ri.imputado_id AS sponsor_id,
        COALESCE(u_imp.nombre_completo, u_imp.username, '') AS sponsor_nombre,

        DATEDIFF(day, CAST(GETDATE() AS date), CAST(a.fecha_compromiso AS date)) AS dias_restantes

    FROM reclamo_imputado_acciones a
    JOIN reclamos r ON r.id = a.reclamo_id
    JOIN reclamo_imputados ri ON ri.id = a.imputacion_id
    LEFT JOIN usuarios u_imp ON u_imp.id = ri.imputado_id

    WHERE COALESCE(a.activo, 1) = 1
      AND COALESCE(a.cumplido, 0) = 0
      AND UPPER(COALESCE(a.tipo, '')) IN ('CONTROL', 'CORRECTIVA')
      AND TRY_CONVERT(date, a.fecha_compromiso) IS NOT NULL
      AND CAST(a.fecha_compromiso AS date) > '2000-01-01'
      AND LOWER(LTRIM(RTRIM(COALESCE(r.estado_global, '')))) = 'cerrado'
"""


