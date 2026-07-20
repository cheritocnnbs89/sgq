# modules/gastos/gastos_queries.py

from .gastos_constants import (
    TABLE_ARCHIVOS,
    TABLE_DETALLE,
    TABLE_FACTURAS_XML,
    TABLE_FACTURAS_XML_DET,
    TABLE_GASTOS,
    TABLE_TERCEROS, 
    TABLE_USUARIOS,
)

# =========================
# GASTOS
# =========================

SQL_GET_GASTO_BY_ID = f"""
SELECT g.*
FROM {TABLE_GASTOS} g
WHERE g.id = ?
"""

SQL_LIST_GASTOS = f"""
SELECT g.*
FROM {TABLE_GASTOS} g
ORDER BY COALESCE(g.fecha, g.created_at) DESC, g.id DESC
"""

SQL_INSERT_GASTO = f"""
INSERT INTO {TABLE_GASTOS} (
    fecha,
    usuario_id,
    motivo,
    total
)
VALUES (?, ?, ?, ?)
"""

SQL_UPDATE_GASTO = f"""
UPDATE {TABLE_GASTOS}
SET
    fecha = ?,
    motivo = ?,
    total = ?
WHERE id = ?
"""

SQL_DELETE_GASTO = f"""
DELETE FROM {TABLE_GASTOS}
WHERE id = ?
"""

# =========================
# DETALLE
# =========================

SQL_GET_DETALLE_BY_GASTO_ID = f"""
SELECT d.*
FROM {TABLE_DETALLE} d
WHERE d.gasto_id = ?
ORDER BY d.id ASC
"""

SQL_INSERT_DETALLE = f"""
INSERT INTO {TABLE_DETALLE} (
    gasto_id,
    descripcion,
    subtotal,
    iva,
    total
)
VALUES (?, ?, ?, ?, ?)
"""

SQL_DELETE_DETALLE_BY_GASTO_ID = f"""
DELETE FROM {TABLE_DETALLE}
WHERE gasto_id = ?
"""

# =========================
# ARCHIVOS
# =========================

SQL_GET_ARCHIVOS_BY_GASTO_ID = f"""
SELECT a.*
FROM {TABLE_ARCHIVOS} a
WHERE a.gasto_id = ?
ORDER BY a.id ASC
"""

# =========================
# FACTURAS XML
# =========================

SQL_GET_FACTURA_XML_BY_ID = f"""
SELECT f.*
FROM {TABLE_FACTURAS_XML} f
WHERE f.id = ?
"""

SQL_SEARCH_FACTURAS_XML_BASE = f"""
SELECT
    f.*,
    CASE
        WHEN EXISTS (
            SELECT 1
            FROM {TABLE_TERCEROS} t
            WHERE t.tipo = 'P'
              AND t.activo = 1
              AND TRIM(t.identificacion) = TRIM(f.ruc_emisor)
        ) THEN 1
        ELSE 0
    END AS proveedor_ok
FROM {TABLE_FACTURAS_XML} f
WHERE f.estado = ?
ORDER BY f.id DESC
LIMIT ?
"""

SQL_FACTURA_XML_ESTA_USADA = f"""
SELECT 1
FROM {TABLE_GASTOS} g
WHERE g.factura_xml_id = ?
LIMIT 1
"""

SQL_UPDATE_FACTURA_XML_ESTADO = f"""
UPDATE {TABLE_FACTURAS_XML}
SET estado = ?
WHERE id = ?
"""

SQL_EXISTS_FACTURA_XML = f"""
SELECT TOP 1 id
FROM {TABLE_FACTURAS_XML}
WHERE clave_acceso = ?
"""

SQL_INSERT_FACTURA_XML = f"""
INSERT INTO {TABLE_FACTURAS_XML} (
    clave_acceso, numero_autorizacion, tipo_comprobante, cod_doc,
    fecha_emision, fecha_autorizacion,
    ruc_emisor, razon_social_emisor,
    ruc_cliente, razon_social_cliente,
    estab, pto_emi, secuencial,
    subtotal, descuento, iva, total, moneda,
    base_iva, iva_tarifa, subtotal_0, subtotal_15, propina,
    estado, archivo
)
OUTPUT INSERTED.id
VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
"""

SQL_INSERT_FACTURA_XML_DET = f"""
INSERT INTO {TABLE_FACTURAS_XML_DET} (
    factura_id, codigo_principal, descripcion,
    cantidad, precio_unitario, descuento,
    base_imponible, iva, total_linea
)
VALUES (?,?,?,?,?,?,?,?,?)
"""

# =========================
# USUARIOS / APOYO
# =========================

SQL_GET_USUARIO_BY_ID = f"""
SELECT u.*
FROM {TABLE_USUARIOS} u
WHERE u.id = ?
"""

SQL_GET_USUARIO_BY_USERNAME = f"""
SELECT u.*
FROM {TABLE_USUARIOS} u
WHERE LOWER(u.username) = LOWER(?)
LIMIT 1
"""

SQL_GET_GASTO_OWNER = f"""
SELECT
    g.id,
    g.usuario_id,
    u.username
FROM {TABLE_GASTOS} g
LEFT JOIN {TABLE_USUARIOS} u
    ON u.id = g.usuario_id
WHERE g.id = ?
"""

SQL_GET_ADMIN_EMAILS = f"""
SELECT DISTINCT email
FROM {TABLE_USUARIOS}
WHERE LOWER(LTRIM(RTRIM(COALESCE(rol,'')))) = 'admin'
  AND COALESCE(disabled,0)=0
  AND LTRIM(RTRIM(COALESCE(email,''))) <> ''
"""