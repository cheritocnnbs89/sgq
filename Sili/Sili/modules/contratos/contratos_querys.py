from __future__ import annotations

from .contratos_constants import (
    TABLA_CONTRATOS,
    TABLA_GARANTIAS,
    TABLA_CONTRATO_ARCHIVOS,
    TABLA_USUARIOS,
    TABLA_TERCEROS,
    TABLA_DEPARTAMENTOS,
    DIAS_AVISO_VENCIMIENTO_GARANTIA,

)

SQL_GARANTIAS_REPORTE_BASE = f"""
SELECT
    g.id AS garantia_id,
    g.contrato_id,
    g.tipo AS garantia_tipo,
    g.compania_emisora,
    g.monto_poliza,
    g.fecha_suscripcion AS garantia_fecha_suscripcion,
    g.fecha_vencimiento AS garantia_fecha_vencimiento,
    g.fecha_vencimiento_actual,
    g.vigencia_dias,
    g.estado AS garantia_estado,
    g.fecha_renovacion,
    g.requiere_renovacion,
    g.status_interno AS garantia_status_interno,
    g.observaciones AS garantia_observaciones,
    g.creado_at AS garantia_creado_at,
    g.actualizado_at AS garantia_actualizado_at,
    COALESCE(g.aprobado_jefe,0) AS garantia_aprobado_jefe,
    COALESCE(g.aprobado,0) AS garantia_aprobado,
    COALESCE(g.aprob_gf,0) AS garantia_aprob_gf,

    c.id AS contrato_id_real,
    c.anio,
    c.pedido,
    c.proveedor,
    c.objeto,
    c.valor_contrato,
    c.valor_anticipo,
    c.tipo_pp,
    c.fecha_suscripcion AS contrato_fecha_suscripcion,
    c.fecha_terminacion AS contrato_fecha_terminacion,
    c.plazo_dias,
    c.cronograma_pagos,
    c.fecha_entrega_compras,
    c.fecha_firma_gerencia,
    c.fecha_entrega_finanzas_sumilla,
    c.fecha_entrega_originales_fin,
    c.fechas_pago_anticipo,
    c.fecha_entrega_pedido,
    c.status_interno AS contrato_status_interno,
    c.observaciones AS contrato_observaciones,
    COALESCE(c.aprobado_jefe,0) AS contrato_aprobado_jefe,
    COALESCE(c.aprobado,0) AS contrato_aprobado,
    COALESCE(c.aprob_gf,0) AS contrato_aprob_gf
FROM {TABLA_GARANTIAS} g
JOIN {TABLA_CONTRATOS} c ON c.id = g.contrato_id
WHERE COALESCE(g.disabled,0)=0
  AND COALESCE(c.disabled,0)=0
"""


SQL_GARANTIAS_VENCEN_EN_DIAS = f"""
SELECT
    g.id AS garantia_id,
    g.contrato_id,
    g.tipo AS garantia_tipo,
    g.compania_emisora,
    g.monto_poliza,
    g.fecha_suscripcion AS garantia_fecha_suscripcion,
    g.fecha_vencimiento AS garantia_fecha_vencimiento,
    g.fecha_vencimiento_actual,
    g.vigencia_dias,
    g.estado AS garantia_estado,
    g.fecha_renovacion,
    g.requiere_renovacion,
    g.status_interno AS garantia_status_interno,
    g.observaciones AS garantia_observaciones,

    c.id AS contrato_id_real,
    c.pedido,
    c.proveedor,
    c.objeto,
    c.valor_contrato,
    c.valor_anticipo,
    c.fecha_suscripcion AS contrato_fecha_suscripcion,
    c.fecha_terminacion AS contrato_fecha_terminacion,
    c.usuario_solicitante_id,
    c.usuario_compras_id,
    c.usuario_compras_nombre,
    c.aprobado_jefe_por,

    DATEDIFF(
        DAY,
        CAST(GETDATE() AS date),
        CAST(g.fecha_vencimiento AS date)
    ) AS dias_para_vencer
FROM {TABLA_GARANTIAS} g
JOIN {TABLA_CONTRATOS} c ON c.id = g.contrato_id
WHERE COALESCE(g.disabled,0)=0
  AND COALESCE(c.disabled,0)=0
  AND g.fecha_vencimiento IS NOT NULL
   
  AND COALESCE(g.estado,'') NOT IN ('Liberada', 'Anulada')
ORDER BY g.fecha_vencimiento ASC, g.id DESC
"""

SQL_USUARIOS_COMBO = f"""
SELECT
    u.id,
    u.nombre_completo AS nombre,
    COALESCE(d.nombre, '') AS departamento
FROM {TABLA_USUARIOS} u
LEFT JOIN {TABLA_DEPARTAMENTOS} d ON d.id = u.departamento_id
WHERE COALESCE(u.disabled, 0) = 0
  AND TRIM(COALESCE(u.nombre_completo, '')) <> ''
ORDER BY u.nombre_completo
"""

SQL_PROVEEDORES_COMBO = f"""
SELECT id, nombre
FROM {TABLA_TERCEROS}
WHERE tipo = 'P' AND COALESCE(activo, 1) = 1
ORDER BY nombre
"""

SQL_PROVEEDOR_ACTIVO_POR_ID = f"""
SELECT nombre
FROM {TABLA_TERCEROS}
WHERE id=? AND tipo='P' AND COALESCE(activo,1)=1
"""

SQL_PROVEEDOR_ID_POR_NOMBRE = f"""
SELECT id
FROM {TABLA_TERCEROS}
WHERE tipo='P' AND COALESCE(activo,1)=1 AND nombre=?
"""

SQL_USUARIO_NOMBRE_POR_ID = f"""
SELECT TOP 1 COALESCE(nombre_completo, username) AS nombre
FROM {TABLA_USUARIOS}
WHERE id=?
"""

SQL_USUARIO_EMAIL_POR_ID = f"""
SELECT TOP 1 email
FROM {TABLA_USUARIOS}
WHERE id=?
"""

SQL_USUARIO_EMAIL_POR_USERNAME_O_EMAIL = f"""
SELECT TOP 1 email
FROM {TABLA_USUARIOS}
WHERE LOWER(username)=? OR LOWER(email)=?
ORDER BY id DESC
"""

SQL_PGALLEGOS_EMAIL = f"""
SELECT TOP 1 email
FROM {TABLA_USUARIOS}
WHERE LOWER(username) IN ('pgallegos','p.gallegos','paul gallegos','p gallegos','pablo gallegos')
ORDER BY id DESC
"""

SQL_USUARIO_EXISTE_POR_ID = f"""
SELECT TOP 1 1 AS ok
FROM {TABLA_USUARIOS}
WHERE id=?
"""

SQL_CONTRATO_EXISTE_POR_ID = f"""
SELECT TOP 1 1 AS ok
FROM {TABLA_CONTRATOS}
WHERE id=?
"""

SQL_GARANTIA_EXISTE_POR_ID = f"""
SELECT TOP 1 1 AS ok
FROM {TABLA_GARANTIAS}
WHERE id=?
"""

SQL_CONTRATO_POR_ID = f"""
SELECT *
FROM {TABLA_CONTRATOS}
WHERE id=?
"""

SQL_GARANTIA_POR_ID_ACTIVA = f"""
SELECT
    g.*,
    COALESCE(g.aprobado_jefe,0) AS aprobado_jefe,
    COALESCE(g.aprobado,0) AS aprobado,
    COALESCE(g.aprob_gf,0) AS aprob_gf
FROM {TABLA_GARANTIAS} g
WHERE g.id=? AND COALESCE(g.disabled,0)=0
"""

SQL_GARANTIA_ESTADO_APROBACIONES = f"""
SELECT aprobado_jefe, aprobado, aprob_gf
FROM {TABLA_GARANTIAS}
WHERE id=?
"""

SQL_CONTRATO_ESTADO_APROBACIONES = f"""
SELECT aprobado_jefe, aprobado, aprob_gf
FROM {TABLA_CONTRATOS}
WHERE id=?
"""

SQL_INSERT_CONTRATO = f"""
INSERT INTO {TABLA_CONTRATOS} (
    anio, pedido, proveedor, objeto, valor_contrato, valor_anticipo,
    tipo_pp,
    fecha_suscripcion, fecha_terminacion, plazo_dias, cronograma_pagos,
    fecha_entrega_compras, fecha_firma_gerencia, fecha_entrega_finanzas_sumilla,
    fecha_entrega_originales_fin, fechas_pago_anticipo, fecha_entrega_pedido,
    observaciones, status_interno,
    usuario_solicitante_id, usuario_compras_nombre,
    usuario_compras_id, departamento_id, creado_por, actualizado_at
)
OUTPUT inserted.id
VALUES (?,?,?,?,?,?,?,
        ?,?,?,?,?,?,
        ?,?,?,?,
        ?,?,
        ?,?,
        ?, ?, ?, GETDATE())
"""

SQL_UPDATE_CONTRATO = f"""
UPDATE {TABLA_CONTRATOS}
SET anio=?, pedido=?, proveedor=?, objeto=?, valor_contrato=?, valor_anticipo=?,
    fecha_suscripcion=?, fecha_terminacion=?, plazo_dias=?, cronograma_pagos=?,
    fecha_entrega_compras=?, fecha_firma_gerencia=?, fecha_entrega_finanzas_sumilla=?,
    fecha_entrega_originales_fin=?, fechas_pago_anticipo=?, fecha_entrega_pedido=?,
    observaciones=?, usuario_solicitante_id=?, usuario_compras_id=?,
    actualizado_at=GETDATE()
WHERE id=?
"""

SQL_SOFT_DELETE_CONTRATO = f"""
UPDATE {TABLA_CONTRATOS}
SET disabled=1, actualizado_at=GETDATE()
WHERE id=?
"""

SQL_UPDATE_FINANZAS_CONTRATO = f"""
UPDATE {TABLA_CONTRATOS}
SET con_penalizacion   = ?,
    monto_penalizacion = ?,
    garantia_liberada  = ?,
    actualizado_at     = GETDATE()
WHERE id = ?
"""

SQL_USUARIO_DEPT_NOMBRE_POR_ID = f"""
SELECT TOP 1 COALESCE(d.nombre, '') AS dept_nombre
FROM {TABLA_USUARIOS} u
LEFT JOIN {TABLA_DEPARTAMENTOS} d ON d.id = u.departamento_id
WHERE u.id = ?
"""

SQL_INSERT_GARANTIA = f"""
INSERT INTO {TABLA_GARANTIAS} (
    contrato_id, tipo, compania_emisora, monto_poliza,
    fecha_suscripcion, fecha_vencimiento, fecha_vencimiento_actual,
    vigencia_dias, estado, fecha_renovacion, requiere_renovacion,
    status_interno, observaciones, actualizado_at
)
OUTPUT inserted.id
VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,GETDATE())
"""

SQL_UPDATE_GARANTIA = f"""
UPDATE {TABLA_GARANTIAS}
SET tipo=?, compania_emisora=?, monto_poliza=?,
    fecha_suscripcion=?, fecha_vencimiento=?, fecha_vencimiento_actual=?,
    vigencia_dias=?, estado=?, fecha_renovacion=?, requiere_renovacion=?,
    status_interno=?, observaciones=?, actualizado_at=GETDATE()
WHERE id=?
"""

SQL_SOFT_DELETE_GARANTIA = f"""
UPDATE {TABLA_GARANTIAS}
SET disabled=1, actualizado_at=GETDATE()
WHERE id=?
"""

SQL_ARCHIVOS_POR_CONTRATO_ID = f"""
SELECT id, filename, original_name, uploaded_at
FROM {TABLA_CONTRATO_ARCHIVOS}
WHERE contrato_id=?
ORDER BY id DESC
"""

SQL_ARCHIVOS_POR_CONTRATO_ID_ASC = f"""
SELECT id, filename, original_name, uploaded_at
FROM {TABLA_CONTRATO_ARCHIVOS}
WHERE contrato_id=?
ORDER BY id
"""

SQL_ARCHIVO_POR_ID = f"""
SELECT id, contrato_id, filename, original_name
FROM {TABLA_CONTRATO_ARCHIVOS}
WHERE id=?
"""

SQL_INSERT_ARCHIVO_CONTRATO = f"""
INSERT INTO {TABLA_CONTRATO_ARCHIVOS} (contrato_id, filename, original_name, uploaded_at)
VALUES (?, ?, ?, GETDATE())
"""

SQL_LISTA_CONTRATOS_BASE = f"""
SELECT TOP 300
    c.id, c.pedido, c.proveedor, c.objeto, c.valor_contrato, c.tipo_pp,
    c.fecha_suscripcion, c.fecha_terminacion, c.status_interno,
    COALESCE(c.aprobado_jefe,0) AS aprobado_jefe,
    COALESCE(c.aprobado,0) AS aprobado,
    COALESCE(c.aprob_gf,0) AS aprob_gf,
    (
        SELECT COUNT(1)
        FROM {TABLA_CONTRATO_ARCHIVOS} a
        WHERE a.contrato_id = c.id
    ) AS adjuntos_cnt
FROM {TABLA_CONTRATOS} c
WHERE COALESCE(c.disabled,0)=0
"""

SQL_LISTA_GARANTIAS_BASE = f"""
SELECT TOP 300
    g.id, g.contrato_id, g.tipo, g.monto_poliza, g.estado,
    g.fecha_suscripcion, g.fecha_vencimiento, g.requiere_renovacion,
    g.status_interno,
    COALESCE(g.aprobado_jefe,0) AS aprobado_jefe,
    COALESCE(g.aprobado,0) AS aprobado,
    COALESCE(g.aprob_gf,0) AS aprob_gf,
    c.pedido, c.proveedor, c.objeto, c.valor_contrato
FROM {TABLA_GARANTIAS} g
JOIN {TABLA_CONTRATOS} c ON c.id = g.contrato_id
WHERE COALESCE(g.disabled,0)=0
  AND COALESCE(c.disabled,0)=0
"""

SQL_LISTA_CONTRATOS_APROBADOS_JEFE = f"""
SELECT TOP {{top_n}}
    id,
    pedido,
    proveedor
FROM {TABLA_CONTRATOS}
WHERE COALESCE(disabled,0)=0
  AND COALESCE(aprobado_jefe,0)=1
ORDER BY id DESC
"""

SQL_LISTA_CONTRATOS_APROBADOS_SIN_GARANTIA = f"""
SELECT TOP {{top_n}} c.id, c.pedido, c.proveedor
FROM {TABLA_CONTRATOS} c
LEFT JOIN (
    SELECT DISTINCT contrato_id
    FROM {TABLA_GARANTIAS}
    WHERE COALESCE(disabled,0)=0
) g ON g.contrato_id = c.id
WHERE COALESCE(c.disabled,0)=0
  AND COALESCE(c.aprobado_jefe,0)=1
  AND g.contrato_id IS NULL
ORDER BY c.id DESC
"""

SQL_CONTRATO_MINIMO_POR_ID = f"""
SELECT TOP 1 id, pedido, proveedor
FROM {TABLA_CONTRATOS}
WHERE id=?
"""

SQL_CONTRATO_MINIMO_ACTIVO_POR_ID = f"""
SELECT TOP 1 id, pedido, proveedor
FROM {TABLA_CONTRATOS}
WHERE id=? AND COALESCE(disabled,0)=0
"""

SQL_TOGGLE_APROBACION_JEFE_CONTRATO = f"""
UPDATE {TABLA_CONTRATOS}
SET aprobado_jefe=?,
    aprobado_jefe_por=?,
    aprobado_jefe_en=GETDATE(),
    status_interno=?,
    actualizado_at=GETDATE()
WHERE id=?
"""

SQL_TOGGLE_APROBACION_JEFE_GARANTIA = f"""
UPDATE {TABLA_GARANTIAS}
SET aprobado_jefe=?,
    aprobado_jefe_por=?,
    aprobado_jefe_en=GETDATE(),
    status_interno=?,
    actualizado_at=GETDATE()
WHERE id=?
"""

SQL_TOGGLE_APROBACION_CONTRATO = f"""
UPDATE {TABLA_CONTRATOS}
SET aprobado=?, aprobado_por=?, aprobado_en=GETDATE(), actualizado_at=GETDATE()
WHERE id=?
"""

SQL_TOGGLE_APROBACION_GARANTIA = f"""
UPDATE {TABLA_GARANTIAS}
SET aprobado=?, aprobado_por=?, aprobado_en=GETDATE(), actualizado_at=GETDATE()
WHERE id=?
"""

SQL_TOGGLE_APROBACION_GF_CONTRATO = f"""
UPDATE {TABLA_CONTRATOS}
SET aprob_gf=?, actualizado_at=GETDATE()
WHERE id=?
"""

SQL_TOGGLE_APROBACION_GF_GARANTIAS_POR_CONTRATO = f"""
UPDATE {TABLA_GARANTIAS}
SET aprob_gf=?, actualizado_at=GETDATE()
WHERE contrato_id=?
"""

SQL_EXISTE_GARANTIA_APROBADA_ACTIVA_POR_CONTRATO = f"""
SELECT TOP 1 1 AS ok
FROM {TABLA_GARANTIAS}
WHERE contrato_id = ?
  AND COALESCE(disabled,0)=0
  AND COALESCE(aprobado,0)=1
"""

SQL_DETALLE_GARANTIA_FRAGMENT = f"""
SELECT
    g.id,
    g.contrato_id,
    g.tipo,
    COALESCE(g.monto_poliza,0) AS monto_poliza,
    g.estado,
    g.fecha_suscripcion,
    g.fecha_vencimiento,
    g.requiere_renovacion,
    g.status_interno,
    g.compania_emisora AS compania_emisora,
    g.observaciones AS observaciones,
    g.fecha_renovacion AS fecha_renovacion,
    '' AS fecha_vencimiento_actualizado,
    COALESCE(g.aprobado_jefe,0) AS aprobado_jefe,
    COALESCE(g.aprobado,0) AS aprobado,
    COALESCE(g.aprob_gf,0) AS aprob_gf,
    c.pedido AS pedido,
    c.proveedor AS proveedor,
    c.objeto AS objeto,
    c.valor_contrato AS valor_contrato
FROM {TABLA_GARANTIAS} g
JOIN {TABLA_CONTRATOS} c ON c.id = g.contrato_id
WHERE g.id = ?
"""

SQL_APROBACION_LISTA_BASE = f"""
SELECT TOP 400
    c.id AS contrato_id, c.pedido, c.proveedor, c.objeto, c.valor_contrato,
    c.tipo_pp, c.fecha_suscripcion, c.fecha_terminacion,
    c.aprobado AS contrato_aprobado,
    COALESCE(c.aprob_gf,0) AS c_aprob_gf,
    g.id AS garantia_id, g.tipo AS garantia_tipo, g.estado AS garantia_estado,
    g.fecha_vencimiento, g.aprobado AS garantia_aprobado,
    COALESCE(g.requiere_renovacion,0) AS requiere_renovacion
FROM {TABLA_CONTRATOS} c
JOIN {TABLA_GARANTIAS} g
    ON g.contrato_id = c.id
   AND COALESCE(g.disabled,0)=0
WHERE COALESCE(c.disabled,0)=0
  AND (
        (COALESCE(c.aprobado,0)=1 AND COALESCE(g.aprobado,0)=1)
        OR
        (
          (COALESCE(c.aprobado_jefe,0)=1 OR c.status_interno='Aprobado')
          AND
          (COALESCE(g.aprobado_jefe,0)=1 OR g.status_interno='Aprobado')
        )
      )
"""



SQL_LISTA_CONTRATOS_APROBADOS_PARA_GARANTIA = f"""
SELECT TOP {{top_n}}
    c.id,
    c.pedido,
    c.proveedor
FROM {TABLA_CONTRATOS} c
OUTER APPLY (
    SELECT TOP 1
        g.fecha_vencimiento,
        g.requiere_renovacion
    FROM {TABLA_GARANTIAS} g
    WHERE g.contrato_id = c.id
      AND COALESCE(g.disabled,0)=0
    ORDER BY g.id DESC
) ug
WHERE COALESCE(c.disabled,0)=0
  AND COALESCE(c.aprobado_jefe,0)=1
  AND (
        ug.fecha_vencimiento IS NULL
        OR (
            COALESCE(ug.requiere_renovacion,0)=1
            AND CAST(ug.fecha_vencimiento AS date) < CAST(GETDATE() AS date)
        )
      )
ORDER BY c.id DESC
"""


SQL_NOTIFY_TEMPLATE_GARANTIA_VENCE_15_EXISTS = """
SELECT TOP 1 1 AS ok
FROM dbo.notify_templates
WHERE [key] = ?
"""

SQL_NOTIFY_TEMPLATE_GARANTIA_VENCE_15_INSERT = """
INSERT INTO dbo.notify_templates ([key], [subject], html, [text], tipo)
VALUES (?, ?, ?, ?, ?)
"""

SQL_USUARIO_ID_POR_EMAIL = """
SELECT TOP 1 id
FROM usuarios
WHERE LOWER(email) = LOWER(?)
  AND COALESCE(disabled, 0) = 0
ORDER BY id DESC
"""

SQL_GARANTIAS_VENCEN_EN_15_DIAS = f"""
SELECT
    g.id AS garantia_id,
    g.contrato_id,
    g.tipo AS garantia_tipo,
    g.compania_emisora,
    g.monto_poliza,
    g.fecha_suscripcion AS garantia_fecha_suscripcion,
    g.fecha_vencimiento AS garantia_fecha_vencimiento,
    g.fecha_vencimiento_actual,
    g.vigencia_dias,
    g.estado AS garantia_estado,
    g.fecha_renovacion,
    g.requiere_renovacion,
    g.status_interno AS garantia_status_interno,
    g.observaciones AS garantia_observaciones,

    c.id AS contrato_id_real,
    c.pedido,
    c.proveedor,
    c.objeto,
    c.valor_contrato,
    c.valor_anticipo,
    c.fecha_suscripcion AS contrato_fecha_suscripcion,
    c.fecha_terminacion AS contrato_fecha_terminacion,
    c.usuario_solicitante_id,
    c.usuario_compras_id,
    c.usuario_compras_nombre,
    c.aprobado_jefe_por,

    DATEDIFF(
        DAY,
        CAST(GETDATE() AS date),
        CAST(g.fecha_vencimiento AS date)
    ) AS dias_para_vencer
FROM garantias g
JOIN contratos c ON c.id = g.contrato_id
WHERE COALESCE(g.disabled,0)=0
  AND COALESCE(c.disabled,0)=0
  AND g.fecha_vencimiento IS NOT NULL
  AND CAST(g.fecha_vencimiento AS date) = DATEADD(DAY, 15, CAST(GETDATE() AS date))
  AND COALESCE(g.estado,'') NOT IN ('Liberada', 'Anulada')
ORDER BY g.fecha_vencimiento ASC, g.id DESC
"""

SQL_NOTIFY_QUEUE_EXISTS_BY_EVENT = """
SELECT TOP 1 1 AS ok
FROM dbo.notify_queue
WHERE user_id = ?
  AND template_key = ?
  AND event_key = ?
"""

SQL_NOTIFY_QUEUE_INSERT_GARANTIA = """
INSERT INTO dbo.notify_queue (
    user_id,
    tarea_id,
    tipo,
    fecha_obj,
    canal,
    template_key,
    payload_json,
    estado,
    scheduled_at,
    sent_at,
    error_msg,
    gasto_id,
    area,
    event_key,
    comentario
)
VALUES (
    ?,
    NULL,
    ?,
    ?,
    ?,
    ?,
    ?,
    'pending',
    GETDATE(),
    NULL,
    NULL,
    NULL,
    ?,
    ?,
    NULL
)
"""