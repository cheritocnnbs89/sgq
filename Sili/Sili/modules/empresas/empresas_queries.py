# modules/empresas/empresas_queries.py
# -*- coding: utf-8 -*-

from .empresas_constants import TABLA_EMPRESAS


SQL_SELECT_EMPRESAS_LISTA_BASE = f"""
SELECT
    id,
    razon_social,
    ruc,
    email,
    telefono,
    rep_nacionalidad,
    usuario_sap,
    activo
FROM {TABLA_EMPRESAS}
"""

SQL_SELECT_EMPRESA_BY_ID = f"""
SELECT *
FROM {TABLA_EMPRESAS}
WHERE id = ?
"""

SQL_INSERT_EMPRESA = f"""
INSERT INTO {TABLA_EMPRESAS}
(
    razon_social,
    ruc,
    direccion,
    telefono,
    email,
    sitio_web,
    rep_nombre,
    rep_identificacion,
    rep_nacionalidad,
    usuario_sap,
    activo,
    created_at
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
"""

SQL_SCOPE_IDENTITY = """
SELECT CAST(SCOPE_IDENTITY() AS INT)
"""

SQL_UPDATE_EMPRESA = f"""
UPDATE {TABLA_EMPRESAS} SET
    razon_social = ?,
    ruc = ?,
    direccion = ?,
    telefono = ?,
    email = ?,
    sitio_web = ?,
    rep_nombre = ?,
    rep_identificacion = ?,
    rep_nacionalidad = ?,
    usuario_sap = ?,
    activo = ?,
    updated_at = CURRENT_TIMESTAMP
WHERE id = ?
"""

SQL_DELETE_EMPRESA = f"""
DELETE FROM {TABLA_EMPRESAS}
WHERE id = ?
"""