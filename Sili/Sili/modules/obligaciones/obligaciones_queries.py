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
    TABLA_FRECUENCIAS,
    TABLA_FRECUENCIA_NOTIFICACIONES,
    TABLA_NOTIFICACION_DESTINATARIOS,
    TABLA_TIPO_ENTIDAD,
    TABLA_TIPOS,
    TABLA_ENTIDADES,
    TABLA_SOLICITUDES_EDICION,
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
    o.estatus,
    o.comentario,
    o.activa,
    o.creado_por,
    o.creado_en,
    o.modificado_en,
    o.edicion_habilitada,
    CASE WHEN EXISTS (
        SELECT 1 FROM oblig_solicitudes_edicion se WHERE se.obligacion_id = o.id AND se.estado = 'pendiente'
    ) THEN 1 ELSE 0 END AS tiene_solicitud_pendiente,
    (
        SELECT STRING_AGG(ev.nombre_archivo, ', ')
        FROM {TABLA_EVIDENCIAS} ev
        WHERE ev.obligacion_id = o.id
    ) AS evidencias
FROM {TABLA_OBLIGACIONES} o
JOIN {TABLA_TIPOS}     t  ON t.id  = o.tipo_id
JOIN {TABLA_EMPRESAS}  e  ON e.id  = o.empresa_id
JOIN {TABLA_ENTIDADES} en ON en.id = o.entidad_id
JOIN {TABLA_FRECUENCIAS}  fr ON fr.id = o.frecuencia_id
LEFT JOIN {TABLA_DEPARTAMENTOS} d ON d.id = o.departamento_id
LEFT JOIN {TABLA_PUESTOS}       p ON p.id = o.puesto_id
JOIN {TABLA_USUARIOS} u ON u.id = o.usuario_id
"""

SQL_GET_OBLIGACION_BY_ID = SQL_SELECT_JOIN_BASE + " WHERE o.id = ? "

SQL_GET_OBLIGACION_RAW_BY_ID = f"SELECT * FROM {TABLA_OBLIGACIONES} WHERE id = ?"

# 2026-07-21: columna `comentario` retirada del INSERT/UPDATE (campo eliminado
# del formulario). La columna sigue existiendo en la tabla, sin usarse.
SQL_INSERT_OBLIGACION = f"""
INSERT INTO {TABLA_OBLIGACIONES} (
    tipo_id, empresa_id, descripcion, entidad_id,
    departamento_id, puesto_id, usuario_id,
    fecha_vencimiento, frecuencia_id, estatus,
    activa, creado_por, creado_en
)
OUTPUT INSERTED.id
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, GETDATE())
"""

SQL_UPDATE_OBLIGACION = f"""
UPDATE {TABLA_OBLIGACIONES}
SET tipo_id = ?, empresa_id = ?, descripcion = ?, entidad_id = ?,
    fecha_vencimiento = ?, frecuencia_id = ?,
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
SET estatus = ?, activa = 0, modificado_en = GETDATE()
WHERE id = ?
"""

# 2026-08-15: Punto 9 -- si el usuario tiene jefe_id, el cumplimiento queda
# pendiente de aprobación (activa=1 -- sigue "por cumplir" en pastel/dashboard,
# decisión de Matías; aprobado_por_jefe NULL = pendiente). Si NO tiene jefe_id
# (nadie que pueda aprobar), se auto-aprueba igual que antes.
# 2026-08-17: estatus pasa a 'pendiente_aprobacion' (no cumplido/cumplido_fuera_plazo
# todavia -- confundia en Consultas, ver estatus_pendiente_destino) -- el estatus
# final ya calculado (a tiempo/fuera de plazo) se guarda en estatus_pendiente_destino
# hasta que el jefe apruebe.
SQL_MARCAR_CUMPLIDA_PENDIENTE_JEFE = f"""
UPDATE {TABLA_OBLIGACIONES}
SET estatus = 'pendiente_aprobacion', estatus_pendiente_destino = ?,
    activa = 1, aprobado_por_jefe = NULL, modificado_en = GETDATE()
WHERE id = ?
"""

SQL_MARCAR_CUMPLIDA_AUTOAPROBADA = f"""
UPDATE {TABLA_OBLIGACIONES}
SET estatus = ?, activa = 0, aprobado_por_jefe = 1, modificado_en = GETDATE()
WHERE id = ?
"""

SQL_LIST_PENDIENTES_APROBACION_JEFE = f"""
SELECT o.id, o.descripcion, o.estatus, o.estatus_pendiente_destino, o.fecha_vencimiento, o.modificado_en,
       u.id AS usuario_id, u.username AS usuario_username, u.nombre_completo AS usuario_nombre
FROM {TABLA_OBLIGACIONES} o
JOIN {TABLA_USUARIOS} u ON u.id = o.usuario_id
WHERE o.activa = 1
  AND o.estatus = 'pendiente_aprobacion'
  AND o.aprobado_por_jefe IS NULL
  AND u.jefe_id = ?
ORDER BY o.modificado_en ASC
"""

# 2026-08-17: estatus final (cumplido/cumplido_fuera_plazo) sale de la columna
# estatus_pendiente_destino guardada al momento de marcar cumplida -- no se
# recalcula, ya se decidio "a tiempo/fuera de plazo" contra la fecha real de
# cumplimiento, no contra la fecha en que el jefe aprueba.
SQL_APROBAR_CUMPLIMIENTO_JEFE = f"""
UPDATE {TABLA_OBLIGACIONES}
SET estatus = estatus_pendiente_destino, estatus_pendiente_destino = NULL,
    activa = 0, aprobado_por_jefe = 1, jefe_aprobador_id = ?, fecha_aprobacion_jefe = GETDATE()
WHERE id = ? AND aprobado_por_jefe IS NULL
"""

SQL_RECHAZAR_CUMPLIMIENTO_JEFE = f"""
UPDATE {TABLA_OBLIGACIONES}
SET estatus = ?, estatus_pendiente_destino = NULL, activa = 1, aprobado_por_jefe = 0, jefe_aprobador_id = ?,
    fecha_aprobacion_jefe = GETDATE(), motivo_rechazo_jefe = ?
WHERE id = ? AND aprobado_por_jefe IS NULL
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

# 2026-08-14: gerente_obligaciones -- "jefe del jefe", alcance 2 niveles
# (subordinados directos del gerente + subordinados de esos subordinados).
SQL_GET_USUARIOS_A_CARGO_2NIVELES = f"""
SELECT id, username, nombre_completo
FROM {TABLA_USUARIOS}
WHERE jefe_id = ? OR jefe_id IN (SELECT id FROM {TABLA_USUARIOS} WHERE jefe_id = ?)
ORDER BY username
"""

SQL_LIST_USUARIOS_COMBO = f"""
SELECT DISTINCT u.id, u.username, u.nombre_completo
FROM {TABLA_USUARIOS} u
JOIN roles r ON LOWER(r.nombre) = LOWER(u.rol)
JOIN roles_permisos rp ON rp.rol_id = r.id
JOIN opciones o ON o.id = rp.opcion_id AND o.nombre = 'obligaciones'
WHERE COALESCE(u.disabled, 0) = 0 AND rp.ver = 1
ORDER BY u.username
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
# Tipos y Entidades Reguladoras -- CRUD propio (2026-08-07, Correccion de
# arquitectura #8). Mismo patron que Frecuencias mas abajo.
# ------------------------------------------------------------
SQL_LIST_TIPOS_ACTIVOS = f"""
SELECT id, nombre, activo, orden
FROM {TABLA_TIPOS}
WHERE activo = 1
ORDER BY orden, nombre
"""

SQL_LIST_TIPOS_TODOS = f"""
SELECT id, nombre, activo, orden
FROM {TABLA_TIPOS}
ORDER BY orden, nombre
"""

SQL_GET_TIPO_BY_ID = f"SELECT id, nombre, activo, orden FROM {TABLA_TIPOS} WHERE id = ?"

SQL_INSERT_TIPO = f"""
INSERT INTO {TABLA_TIPOS} (nombre, activo, orden)
OUTPUT INSERTED.id
VALUES (?, 1, ?)
"""

SQL_UPDATE_TIPO = f"UPDATE {TABLA_TIPOS} SET nombre = ?, orden = ? WHERE id = ?"

SQL_TOGGLE_TIPO_ACTIVO = f"UPDATE {TABLA_TIPOS} SET activo = ? WHERE id = ?"

# Combo de Entidad en formularios y filtros (solo activas).
SQL_LIST_ENTIDADES_ACTIVAS = f"""
SELECT id, nombre
FROM {TABLA_ENTIDADES}
WHERE activo = 1
ORDER BY orden, nombre
"""

SQL_LIST_ENTIDADES_TODAS = f"""
SELECT id, nombre, activo, orden
FROM {TABLA_ENTIDADES}
ORDER BY orden, nombre
"""

SQL_GET_ENTIDAD_BY_ID = f"SELECT id, nombre, activo, orden FROM {TABLA_ENTIDADES} WHERE id = ?"

SQL_INSERT_ENTIDAD = f"""
INSERT INTO {TABLA_ENTIDADES} (nombre, activo, orden)
OUTPUT INSERTED.id
VALUES (?, 1, ?)
"""

SQL_UPDATE_ENTIDAD = f"UPDATE {TABLA_ENTIDADES} SET nombre = ?, orden = ? WHERE id = ?"

SQL_TOGGLE_ENTIDAD_ACTIVO = f"UPDATE {TABLA_ENTIDADES} SET activo = ? WHERE id = ?"

# 2026-07-27: Entidades filtradas por Tipo (oblig_tipo_entidad, muchos a
# muchos) -- usado por el endpoint AJAX /obligaciones/api/entidades.
SQL_LIST_ENTIDADES_POR_TIPO = f"""
SELECT en.id, en.nombre
FROM {TABLA_ENTIDADES} en
JOIN {TABLA_TIPO_ENTIDAD} te ON te.entidad_id = en.id
WHERE te.tipo_id = ? AND en.activo = 1
ORDER BY en.nombre
"""

# 2026-08-11: ids de entidad vinculados a un Tipo -- usado por el form de
# Tipos para premarcar los checkboxes al editar.
SQL_LIST_ENTIDAD_IDS_POR_TIPO = f"""
SELECT entidad_id FROM {TABLA_TIPO_ENTIDAD} WHERE tipo_id = ?
"""

# 2026-08-11: borra TODOS los vinculos de un Tipo antes de regrabar los
# elegidos en el form (guardar_tipo hace delete + insert en la misma
# transaccion, nunca deja huecos a mitad de camino).
SQL_DELETE_TIPO_ENTIDAD_BY_TIPO = f"""
DELETE FROM {TABLA_TIPO_ENTIDAD} WHERE tipo_id = ?
"""

SQL_INSERT_TIPO_ENTIDAD = f"""
INSERT INTO {TABLA_TIPO_ENTIDAD} (tipo_id, entidad_id) VALUES (?, ?)
"""

# 2026-07-21: combo Empresa de los filtros (Consultas + Historial) -- solo
# empresas que tienen al menos una obligacion, no el catalogo completo.
SQL_LIST_EMPRESAS_CON_OBLIGACIONES = f"""
SELECT DISTINCT e.id, e.razon_social
FROM {TABLA_OBLIGACIONES} o
JOIN {TABLA_EMPRESAS} e ON e.id = o.empresa_id
ORDER BY e.razon_social
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
# 2026-07-22: tipo_destinatario -- 'fijo' usa usuario_id; 'creador'/'jefe'/
# 'gerente' guardan usuario_id NULL y se resuelven al enviar.
SQL_INSERT_DESTINATARIO = f"""
INSERT INTO {TABLA_NOTIFICACION_DESTINATARIOS} (notificacion_id, usuario_id, tipo_destinatario)
VALUES (?, ?, ?)
"""

SQL_LIST_NOTIFICACIONES_CON_DESTINATARIOS_POR_FRECUENCIA = f"""
SELECT n.id AS notificacion_id, n.orden, n.tipo_trigger, n.dias_antes, n.dia_fijo_mes,
       d.usuario_id, d.tipo_destinatario, u.email AS usuario_email
FROM {TABLA_FRECUENCIA_NOTIFICACIONES} n
LEFT JOIN {TABLA_NOTIFICACION_DESTINATARIOS} d ON d.notificacion_id = n.id
LEFT JOIN {TABLA_USUARIOS} u ON u.id = d.usuario_id
WHERE n.frecuencia_id = ? AND COALESCE(n.activo, 1) = 1
ORDER BY n.orden
"""

# 2026-07-22: emails de los usuarios con rol admin_obligaciones -- copia del
# aviso de cadena de jefe rota al crear/editar una obligación.
SQL_LIST_ADMIN_OBLIGACIONES_EMAILS = f"""
SELECT email
FROM {TABLA_USUARIOS}
WHERE LOWER(rol) = 'admin_obligaciones'
  AND COALESCE(disabled, 0) = 0
  AND email IS NOT NULL AND LTRIM(RTRIM(email)) <> ''
"""

# ------------------------------------------------------------
# Scheduler -- Tarea A (marcar atrasadas)
# ------------------------------------------------------------
SQL_MARCAR_ATRASADAS = f"""
SELECT id FROM {TABLA_OBLIGACIONES}
WHERE fecha_vencimiento < CAST(GETDATE() AS DATE)
  AND estatus NOT IN ('cumplido', 'cumplido_fuera_plazo', 'atrasado')
  AND activa = 1
"""

SQL_UPDATE_ESTATUS_ATRASADO = f"""
UPDATE {TABLA_OBLIGACIONES} SET estatus = 'atrasado', modificado_en = GETDATE() WHERE id = ?
"""

# ------------------------------------------------------------
# Scheduler -- Tarea B (alertas)
# 2026-07-15 (Correccion #3): los destinatarios ya no son usuario+jefe fijo --
# se resuelven por notificacion via oblig_notificacion_destinatarios.
# ------------------------------------------------------------
SQL_LIST_OBLIGACIONES_ACTIVAS_CON_FECHA = f"""
SELECT o.id, o.frecuencia_id, o.fecha_vencimiento, o.estatus, o.usuario_id, o.creado_por
FROM {TABLA_OBLIGACIONES} o
WHERE o.activa = 1
  AND o.fecha_vencimiento IS NOT NULL
  AND o.estatus NOT IN ('cumplido', 'cumplido_fuera_plazo')
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
    SUM(CASE WHEN o.estatus = 'cumplido' THEN 1 ELSE 0 END) AS a_tiempo,
    SUM(CASE WHEN o.estatus = 'cumplido_fuera_plazo' THEN 1 ELSE 0 END) AS fuera_plazo
FROM {TABLA_OBLIGACIONES} o
"""

# 2026-07-30: nueva query fusiona estatus a 3 categorias para doughnut, reemplaza
# SQL_DASHBOARD_POR_ESTATUS_SELECT -- esta queda sin uso (no se borra por si se revierte).
SQL_DASHBOARD_POR_ESTATUS_SELECT = f"""
SELECT
    CASE WHEN o.activa = 1 AND o.estatus <> 'atrasado' THEN 'activa' ELSE o.estatus END AS estatus,
    COUNT(*) AS total
FROM {TABLA_OBLIGACIONES} o
"""
SQL_DASHBOARD_POR_ESTATUS_GROUP_BY = (
    " GROUP BY CASE WHEN o.activa = 1 AND o.estatus <> 'atrasado' THEN 'activa' ELSE o.estatus END"
)

# 2026-08-05: SQL_DASHBOARD_POR_ESTATUS_FUNDIDO_SELECT/GROUP_BY eliminados -- sin
# consumidor tras borrar chartEstado (pedido Matias, sesion revision pendientes).

# 2026-08-07: JOIN contra TABLA_TIPOS (antes param_values, Correccion #8).
SQL_DASHBOARD_POR_TIPO_SELECT = f"""
SELECT t.nombre AS etiqueta, COUNT(*) AS total
FROM {TABLA_OBLIGACIONES} o
JOIN {TABLA_TIPOS} t ON t.id = o.tipo_id
"""
SQL_DASHBOARD_POR_TIPO_GROUP_BY = " GROUP BY t.nombre"

# "Por estatus (empresas)" -- barra apilada por empresa (2026-07-27, pedido de
# Matias reemplaza el combinado 2026-07-21). estatus_fundido junta cumplido +
# cumplido_fuera_plazo en "cumplida" -- 3 categorias fijas por barra:
# cumplida / atrasada / por_presentar.
SQL_DASHBOARD_POR_ESTATUS_TOTAL_SELECT = f"""
SELECT
    e.razon_social AS empresa,
    CASE
        WHEN o.estatus IN ('cumplido', 'cumplido_fuera_plazo') THEN 'cumplida'
        WHEN o.estatus = 'atrasado' THEN 'atrasada'
        ELSE 'por_presentar'
    END AS estatus,
    COUNT(*) AS total
FROM {TABLA_OBLIGACIONES} o
JOIN {TABLA_EMPRESAS} e ON e.id = o.empresa_id
"""
SQL_DASHBOARD_POR_ESTATUS_TOTAL_GROUP_BY = (
    " GROUP BY e.razon_social, "
    "CASE WHEN o.estatus IN ('cumplido', 'cumplido_fuera_plazo') THEN 'cumplida' "
    "WHEN o.estatus = 'atrasado' THEN 'atrasada' ELSE 'por_presentar' END"
)

# 2026-08-14: desglose del pastel (Punto 4) al hacer click en una seccion --
# 3 tablas (Tipo / Entidad / Area), cada una con id+nombre+total, filtradas a
# la seccion clickeada. id incluido para que el click de una fila navegue a
# Consultas ya filtrado (Punto 5).
SQL_DESGLOSE_POR_TIPO_SELECT = f"""
SELECT t.id, t.nombre AS etiqueta, COUNT(*) AS total
FROM {TABLA_OBLIGACIONES} o
JOIN {TABLA_TIPOS} t ON t.id = o.tipo_id
"""
SQL_DESGLOSE_POR_TIPO_GROUP_BY = " GROUP BY t.id, t.nombre ORDER BY total DESC"

SQL_DESGLOSE_POR_ENTIDAD_SELECT = f"""
SELECT en.id, en.nombre AS etiqueta, COUNT(*) AS total
FROM {TABLA_OBLIGACIONES} o
JOIN {TABLA_ENTIDADES} en ON en.id = o.entidad_id
"""
SQL_DESGLOSE_POR_ENTIDAD_GROUP_BY = " GROUP BY en.id, en.nombre ORDER BY total DESC"

SQL_DESGLOSE_POR_AREA_SELECT = """
SELECT a.id, a.nombre AS etiqueta, COUNT(*) AS total
FROM oblig_obligaciones o
JOIN departamentos d ON d.id = o.departamento_id
JOIN areas a ON a.id = d.area_id
"""
SQL_DESGLOSE_POR_AREA_GROUP_BY = " GROUP BY a.id, a.nombre ORDER BY total DESC"

# ------------------------------------------------------------
# 2026-08-14: Punto 8 -- solicitud de autorizacion para editar obligacion cumplida
# ------------------------------------------------------------
SQL_INSERT_SOLICITUD_EDICION = f"""
INSERT INTO {TABLA_SOLICITUDES_EDICION} (obligacion_id, solicitante_id, motivo, estado)
OUTPUT INSERTED.id
VALUES (?, ?, ?, 'pendiente')
"""

SQL_GET_SOLICITUD_PENDIENTE_BY_OBLIGACION = f"""
SELECT id FROM {TABLA_SOLICITUDES_EDICION}
WHERE obligacion_id = ? AND estado = 'pendiente'
"""

SQL_GET_SOLICITUD_BY_ID = f"""
SELECT s.id, s.obligacion_id, s.solicitante_id, s.motivo, s.estado,
       s.resuelto_por, s.fecha_solicitud, s.fecha_resolucion,
       o.descripcion AS obligacion_descripcion,
       u.email AS solicitante_email, u.nombre_completo AS solicitante_nombre
FROM {TABLA_SOLICITUDES_EDICION} s
JOIN {TABLA_OBLIGACIONES} o ON o.id = s.obligacion_id
JOIN {TABLA_USUARIOS} u ON u.id = s.solicitante_id
WHERE s.id = ?
"""

SQL_LIST_SOLICITUDES_PENDIENTES = f"""
SELECT s.id, s.obligacion_id, s.motivo, s.fecha_solicitud,
       o.descripcion AS obligacion_descripcion,
       u.username AS solicitante_username, u.nombre_completo AS solicitante_nombre
FROM {TABLA_SOLICITUDES_EDICION} s
JOIN {TABLA_OBLIGACIONES} o ON o.id = s.obligacion_id
JOIN {TABLA_USUARIOS} u ON u.id = s.solicitante_id
WHERE s.estado = 'pendiente'
ORDER BY s.fecha_solicitud ASC
"""

SQL_RESOLVER_SOLICITUD = f"""
UPDATE {TABLA_SOLICITUDES_EDICION}
SET estado = ?, resuelto_por = ?, fecha_resolucion = GETDATE()
WHERE id = ? AND estado = 'pendiente'
"""

SQL_HABILITAR_EDICION_OBLIGACION = f"""
UPDATE {TABLA_OBLIGACIONES} SET edicion_habilitada = 1 WHERE id = ?
"""

SQL_DESHABILITAR_EDICION_OBLIGACION = f"""
UPDATE {TABLA_OBLIGACIONES} SET edicion_habilitada = 0 WHERE id = ?
"""

# 2026-08-14: emails de rol admin + admin_obligaciones (distinto del existente
# SQL_LIST_ADMIN_OBLIGACIONES_EMAILS que es solo admin_obligaciones -- Punto 8
# pide notificar a AMBOS roles, decision explicita de Matias).
SQL_LIST_ADMIN_Y_ADMIN_OBLIGACIONES_EMAILS = f"""
SELECT email
FROM {TABLA_USUARIOS}
WHERE LOWER(rol) IN ('admin', 'admin_obligaciones')
  AND COALESCE(disabled, 0) = 0
  AND email IS NOT NULL AND LTRIM(RTRIM(email)) <> ''
"""
