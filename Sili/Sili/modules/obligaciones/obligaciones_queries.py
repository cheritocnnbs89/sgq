# -*- coding: utf-8 -*-

from .obligaciones_constants import (
    TABLA_OBLIGACIONES,
    TABLA_EVIDENCIAS,
    TABLA_HISTORIAL,
    TABLA_ALERTAS,
    TABLA_USUARIOS,
    TABLA_DEPARTAMENTOS,
    TABLA_PUESTOS,
    TABLA_EMPRESAS,
    TABLA_TERCEROS,
    TABLA_PARAM_GROUPS,
    TABLA_PARAM_VALUES,
    TABLA_FRECUENCIAS,
    TABLA_FRECUENCIA_NOTIFICACIONES,
    TABLA_NOTIFICACION_DESTINATARIOS,
)

SQL_SCOPE_IDENTITY = "SELECT CAST(SCOPE_IDENTITY() AS INT)"

# ------------------------------------------------------------
# SELECT base con JOINs -- reutilizado por Consultas e Historial
# 2026-07-15 (Correccion #3): tipo -> param_values, frecuencia -> tabla
# propia oblig_frecuencias (antes param_values), entidad -> terceros.
# ------------------------------------------------------------
SQL_SELECT_JOIN_BASE = f"""
SELECT
    o.id,
    o.tipo_id,       t.nombre  AS tipo_nombre,
    o.empresa_id,    e.razon_social AS empresa_nombre,
    o.descripcion,
    o.entidad_id,    en.nombre AS entidad_nombre,
    o.departamento_id, d.nombre AS departamento_nombre,
    o.puesto_id,       p.nombre AS puesto_nombre,
    o.usuario_id,      u.username AS usuario_username, u.nombre_completo AS usuario_nombre,
    o.fecha_vencimiento,
    o.frecuencia_id, fr.nombre AS frecuencia_nombre,
    fr.recalculo_tipo AS frecuencia_recalculo_tipo,
    fr.recalculo_cantidad AS frecuencia_recalculo_cantidad,
    o.estado,
    o.comentario,
    o.activa,
    o.creado_por,
    o.creado_en,
    o.modificado_en,
    (
        SELECT STRING_AGG(ev.nombre_archivo, ', ')
        FROM {TABLA_EVIDENCIAS} ev
        WHERE ev.obligacion_id = o.id
    ) AS evidencias
FROM {TABLA_OBLIGACIONES} o
JOIN {TABLA_PARAM_VALUES} t  ON t.id  = o.tipo_id
JOIN {TABLA_EMPRESAS}     e  ON e.id  = o.empresa_id
JOIN {TABLA_TERCEROS}     en ON en.id = o.entidad_id
JOIN {TABLA_FRECUENCIAS}  fr ON fr.id = o.frecuencia_id
LEFT JOIN {TABLA_DEPARTAMENTOS} d ON d.id = o.departamento_id
LEFT JOIN {TABLA_PUESTOS}       p ON p.id = o.puesto_id
JOIN {TABLA_USUARIOS} u ON u.id = o.usuario_id
"""

SQL_GET_OBLIGACION_BY_ID = SQL_SELECT_JOIN_BASE + " WHERE o.id = ? "

SQL_GET_OBLIGACION_RAW_BY_ID = f"SELECT * FROM {TABLA_OBLIGACIONES} WHERE id = ?"

SQL_INSERT_OBLIGACION = f"""
INSERT INTO {TABLA_OBLIGACIONES} (
    tipo_id, empresa_id, descripcion, entidad_id,
    departamento_id, puesto_id, usuario_id,
    fecha_vencimiento, frecuencia_id, estado, comentario,
    activa, creado_por, creado_en
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, GETDATE())
"""

SQL_UPDATE_OBLIGACION = f"""
UPDATE {TABLA_OBLIGACIONES}
SET tipo_id = ?, empresa_id = ?, descripcion = ?, entidad_id = ?,
    fecha_vencimiento = ?, frecuencia_id = ?, comentario = ?,
    modificado_en = GETDATE()
WHERE id = ?
"""

SQL_SOFT_DELETE_OBLIGACION = f"""
UPDATE {TABLA_OBLIGACIONES} SET activa = 0, modificado_en = GETDATE() WHERE id = ?
"""

SQL_HARD_DELETE_OBLIGACION = f"DELETE FROM {TABLA_OBLIGACIONES} WHERE id = ?"

SQL_COUNT_HISTORIAL_BY_OBLIGACION = f"""
SELECT COUNT(*) FROM {TABLA_HISTORIAL} WHERE obligacion_id = ?
"""

SQL_COUNT_ALERTAS_BY_OBLIGACION = f"""
SELECT COUNT(*) FROM {TABLA_ALERTAS} WHERE obligacion_id = ?
"""

SQL_MARCAR_CUMPLIDA = f"""
UPDATE {TABLA_OBLIGACIONES}
SET estado = ?, activa = 0, modificado_en = GETDATE()
WHERE id = ?
"""

# ------------------------------------------------------------
# Perfil de usuario (departamento_id / puesto_id / email / jefe)
# ------------------------------------------------------------
SQL_GET_USUARIO_PERFIL = f"""
SELECT id, username, email, rol, departamento_id, puesto_id, jefe_id, nombre_completo
FROM {TABLA_USUARIOS}
WHERE id = ?
"""

SQL_GET_USUARIO_BY_USERNAME = f"""
SELECT id, username, email, rol, departamento_id, puesto_id, jefe_id, nombre_completo
FROM {TABLA_USUARIOS}
WHERE LOWER(username) = LOWER(?)
"""

SQL_GET_USUARIOS_A_CARGO = f"""
SELECT id, username, nombre_completo
FROM {TABLA_USUARIOS}
WHERE jefe_id = ?
ORDER BY username
"""

SQL_LIST_USUARIOS_COMBO = f"""
SELECT id, username, nombre_completo
FROM {TABLA_USUARIOS}
WHERE COALESCE(disabled, 0) = 0
ORDER BY username
"""

# ------------------------------------------------------------
# Historial (audit trail por campo)
# ------------------------------------------------------------
SQL_INSERT_HISTORIAL = f"""
INSERT INTO {TABLA_HISTORIAL} (
    obligacion_id, campo, valor_anterior, valor_nuevo, comentario, modificado_por, modificado_en
)
VALUES (?, ?, ?, ?, ?, ?, GETDATE())
"""

# ------------------------------------------------------------
# Evidencias
# ------------------------------------------------------------
SQL_INSERT_EVIDENCIA = f"""
INSERT INTO {TABLA_EVIDENCIAS} (
    obligacion_id, nombre_archivo, ruta, tipo_archivo, tamanio_bytes, subido_por, subido_en
)
VALUES (?, ?, ?, ?, ?, ?, GETDATE())
"""

SQL_LIST_EVIDENCIAS_BY_OBLIGACION = f"""
SELECT id, nombre_archivo, ruta, tipo_archivo, tamanio_bytes, subido_por, subido_en
FROM {TABLA_EVIDENCIAS}
WHERE obligacion_id = ?
ORDER BY subido_en DESC
"""

# 2026-07-13 (T8): usada por el endpoint autenticado de descarga
SQL_GET_EVIDENCIA_BY_ID = f"""
SELECT id, obligacion_id, nombre_archivo, ruta, tipo_archivo, tamanio_bytes, subido_por, subido_en
FROM {TABLA_EVIDENCIAS}
WHERE id = ? AND obligacion_id = ?
"""

# ------------------------------------------------------------
# Lookups -- Tipos (param_values) y Entidades (terceros)
# 2026-07-14 (Ronda 2): reemplaza oblig_tipos/oblig_entidades. Ya no hay
# CRUD propio -- Tipos se gestiona desde parametros_generales, Entidades
# desde /terceros (ver "Corrección de arquitectura #2").
# ------------------------------------------------------------
SQL_GET_GROUP_ID_BY_NOMBRE = f"SELECT id FROM {TABLA_PARAM_GROUPS} WHERE nombre = ?"

SQL_LIST_PARAM_VALUES_ACTIVOS_POR_GRUPO = f"""
SELECT id, nombre, valor
FROM {TABLA_PARAM_VALUES}
WHERE group_id = ? AND parent_id IS NULL AND activo = 1
ORDER BY orden, nombre
"""

SQL_LIST_ENTIDADES_ACTIVAS = f"""
SELECT id, nombre
FROM {TABLA_TERCEROS}
WHERE COALESCE(activo, 1) = 1
ORDER BY nombre
"""

# ------------------------------------------------------------
# Frecuencias -- CRUD propio (2026-07-15, Corrección de arquitectura #3)
# ------------------------------------------------------------
SQL_LIST_FRECUENCIAS_ACTIVAS = f"""
SELECT id, nombre, recalculo_tipo, recalculo_cantidad, activo
FROM {TABLA_FRECUENCIAS}
WHERE COALESCE(activo, 1) = 1
ORDER BY nombre
"""

SQL_GET_FRECUENCIA_BY_ID = f"""
SELECT id, nombre, recalculo_tipo, recalculo_cantidad, activo
FROM {TABLA_FRECUENCIAS}
WHERE id = ?
"""

SQL_INSERT_FRECUENCIA = f"""
INSERT INTO {TABLA_FRECUENCIAS} (nombre, recalculo_tipo, recalculo_cantidad, activo, creado_en)
OUTPUT INSERTED.id
VALUES (?, ?, ?, 1, GETDATE())
"""

SQL_UPDATE_FRECUENCIA = f"""
UPDATE {TABLA_FRECUENCIAS} SET nombre = ?, recalculo_tipo = ?, recalculo_cantidad = ? WHERE id = ?
"""

SQL_SOFT_DELETE_FRECUENCIA = f"UPDATE {TABLA_FRECUENCIAS} SET activo = 0 WHERE id = ?"

# ------------------------------------------------------------
# Notificaciones de una frecuencia (hasta 5, orden 1-5)
# ------------------------------------------------------------
SQL_INSERT_NOTIFICACION = f"""
INSERT INTO {TABLA_FRECUENCIA_NOTIFICACIONES} (
    frecuencia_id, orden, tipo_trigger, dias_antes, dia_fijo_mes, activo
)
OUTPUT INSERTED.id
VALUES (?, ?, ?, ?, ?, 1)
"""

SQL_DELETE_NOTIFICACIONES_POR_FRECUENCIA = f"""
DELETE FROM {TABLA_FRECUENCIA_NOTIFICACIONES} WHERE frecuencia_id = ?
"""

SQL_DELETE_DESTINATARIOS_POR_FRECUENCIA = f"""
DELETE FROM {TABLA_NOTIFICACION_DESTINATARIOS}
WHERE notificacion_id IN (SELECT id FROM {TABLA_FRECUENCIA_NOTIFICACIONES} WHERE frecuencia_id = ?)
"""

# ------------------------------------------------------------
# Destinatarios de una notificación
# ------------------------------------------------------------
SQL_INSERT_DESTINATARIO = f"""
INSERT INTO {TABLA_NOTIFICACION_DESTINATARIOS} (notificacion_id, usuario_id) VALUES (?, ?)
"""

SQL_LIST_NOTIFICACIONES_CON_DESTINATARIOS_POR_FRECUENCIA = f"""
SELECT n.id AS notificacion_id, n.orden, n.tipo_trigger, n.dias_antes, n.dia_fijo_mes,
       d.usuario_id, u.email AS usuario_email
FROM {TABLA_FRECUENCIA_NOTIFICACIONES} n
LEFT JOIN {TABLA_NOTIFICACION_DESTINATARIOS} d ON d.notificacion_id = n.id
LEFT JOIN {TABLA_USUARIOS} u ON u.id = d.usuario_id
WHERE n.frecuencia_id = ? AND COALESCE(n.activo, 1) = 1
ORDER BY n.orden
"""

# ------------------------------------------------------------
# Scheduler -- Tarea A (marcar atrasadas)
# ------------------------------------------------------------
SQL_MARCAR_ATRASADAS = f"""
SELECT id FROM {TABLA_OBLIGACIONES}
WHERE fecha_vencimiento < CAST(GETDATE() AS DATE)
  AND estado NOT IN ('cumplido', 'cumplido_fuera_plazo', 'atrasado')
  AND activa = 1
"""

SQL_UPDATE_ESTADO_ATRASADO = f"""
UPDATE {TABLA_OBLIGACIONES} SET estado = 'atrasado', modificado_en = GETDATE() WHERE id = ?
"""

# ------------------------------------------------------------
# Scheduler -- Tarea B (alertas)
# 2026-07-15 (Correccion #3): los destinatarios ya no son usuario+jefe fijo --
# se resuelven por notificacion via oblig_notificacion_destinatarios.
# ------------------------------------------------------------
SQL_LIST_OBLIGACIONES_ACTIVAS_CON_FECHA = f"""
SELECT o.id, o.frecuencia_id, o.fecha_vencimiento, o.estado, o.usuario_id
FROM {TABLA_OBLIGACIONES} o
WHERE o.activa = 1
  AND o.fecha_vencimiento IS NOT NULL
  AND o.estado NOT IN ('cumplido', 'cumplido_fuera_plazo')
"""

SQL_ALERTA_YA_ENVIADA = f"""
SELECT 1 FROM {TABLA_ALERTAS}
WHERE obligacion_id = ? AND tipo_alerta = ? AND periodo = ?
"""

SQL_INSERT_ALERTA_ENVIADA = f"""
INSERT INTO {TABLA_ALERTAS} (obligacion_id, tipo_alerta, periodo, enviada_en)
VALUES (?, ?, ?, GETDATE())
"""

# ------------------------------------------------------------
# Dashboard -- agregados
# Bases SIN where fijo (patron SILI-PATRONES SS-FILTROS): el
# repository arma el WHERE dinamico (visibilidad por rol + filtros)
# y lo concatena antes del GROUP BY cuando corresponde.
# ------------------------------------------------------------
SQL_DASHBOARD_COUNT_BASE = f"SELECT COUNT(*) FROM {TABLA_OBLIGACIONES} o"

SQL_DASHBOARD_CUMPLIDAS_BASE = f"""
SELECT
    SUM(CASE WHEN o.estado = 'cumplido' THEN 1 ELSE 0 END) AS a_tiempo,
    SUM(CASE WHEN o.estado = 'cumplido_fuera_plazo' THEN 1 ELSE 0 END) AS fuera_plazo
FROM {TABLA_OBLIGACIONES} o
"""

SQL_DASHBOARD_POR_ESTADO_SELECT = f"""
SELECT
    CASE WHEN o.activa = 1 AND o.estado <> 'atrasado' THEN 'activa' ELSE o.estado END AS estado,
    COUNT(*) AS total
FROM {TABLA_OBLIGACIONES} o
"""
SQL_DASHBOARD_POR_ESTADO_GROUP_BY = (
    " GROUP BY CASE WHEN o.activa = 1 AND o.estado <> 'atrasado' THEN 'activa' ELSE o.estado END"
)

SQL_DASHBOARD_POR_TIPO_SELECT = f"""
SELECT t.nombre AS etiqueta, COUNT(*) AS total
FROM {TABLA_OBLIGACIONES} o
JOIN {TABLA_PARAM_VALUES} t ON t.id = o.tipo_id
"""
SQL_DASHBOARD_POR_TIPO_GROUP_BY = " GROUP BY t.nombre"

SQL_DASHBOARD_POR_EMPRESA_SELECT = f"""
SELECT e.razon_social AS etiqueta, COUNT(*) AS total
FROM {TABLA_OBLIGACIONES} o
JOIN {TABLA_EMPRESAS} e ON e.id = o.empresa_id
"""
SQL_DASHBOARD_POR_EMPRESA_GROUP_BY = " GROUP BY e.razon_social"

# Igual que POR_EMPRESA pero desglosado tambien por estado (para el grafico
# de barras agrupadas del dashboard, replica del PBIX de referencia).
SQL_DASHBOARD_POR_EMPRESA_ESTADO_SELECT = f"""
SELECT
    e.razon_social AS empresa,
    CASE WHEN o.activa = 1 AND o.estado <> 'atrasado' THEN 'activa' ELSE o.estado END AS estado,
    COUNT(*) AS total
FROM {TABLA_OBLIGACIONES} o
JOIN {TABLA_EMPRESAS} e ON e.id = o.empresa_id
"""
SQL_DASHBOARD_POR_EMPRESA_ESTADO_GROUP_BY = (
    " GROUP BY e.razon_social, "
    "CASE WHEN o.activa = 1 AND o.estado <> 'atrasado' THEN 'activa' ELSE o.estado END"
)

SQL_DASHBOARD_POR_FRECUENCIA_SELECT = f"""
SELECT fr.nombre AS etiqueta, COUNT(*) AS total
FROM {TABLA_OBLIGACIONES} o
JOIN {TABLA_FRECUENCIAS} fr ON fr.id = o.frecuencia_id
"""
SQL_DASHBOARD_POR_FRECUENCIA_GROUP_BY = " GROUP BY fr.nombre"
