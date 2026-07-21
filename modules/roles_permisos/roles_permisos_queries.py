# -*- coding: utf-8 -*-

from .roles_permisos_constants import (
    TABLA_ROLES,
    TABLA_OPCIONES,
    TABLA_ROLES_PERMISOS,
    TABLA_PERMISOS_LEGACY,
)

SQL_TABLE_EXISTS = """
SELECT 1
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_NAME = ?
"""

SQL_SELECT_ROLES = f"""
SELECT nombre
FROM {TABLA_ROLES}
ORDER BY nombre
"""

SQL_SELECT_ROLE_BY_NAME_CASE_INSENSITIVE = f"""
SELECT TOP 1 id, nombre
FROM {TABLA_ROLES}
WHERE LOWER(nombre) = LOWER(?)
ORDER BY nombre
"""

SQL_INSERT_ROLE = f"""
INSERT INTO {TABLA_ROLES} (nombre)
VALUES (?)
"""

SQL_SELECT_OPCIONES = f"""
SELECT id, nombre
FROM {TABLA_OPCIONES}
ORDER BY nombre
"""

SQL_SELECT_OPCIONES_NOMBRE = f"""
SELECT nombre
FROM {TABLA_OPCIONES}
ORDER BY nombre
"""

SQL_SELECT_OPCION_BY_NAME = f"""
SELECT TOP 1 id, nombre
FROM {TABLA_OPCIONES}
WHERE nombre = ?
"""

SQL_INSERT_OPCION = f"""
INSERT INTO {TABLA_OPCIONES} (nombre)
VALUES (?)
"""

SQL_SELECT_PERMISOS_BY_ROL_ID = f"""
SELECT
    o.nombre AS opcion,
    ISNULL(rp.ver, 0) AS ver,
    ISNULL(rp.crear, 0) AS crear,
    ISNULL(rp.editar, 0) AS editar,
    ISNULL(rp.eliminar, 0) AS eliminar,
    ISNULL(rp.exportar, 0) AS exportar,
    ISNULL(rp.aprobar, 0) AS aprobar
FROM {TABLA_OPCIONES} o
LEFT JOIN {TABLA_ROLES_PERMISOS} rp
    ON rp.opcion_id = o.id
   AND rp.rol_id = ?
ORDER BY o.nombre
"""

SQL_DELETE_ROLES_PERMISOS_BY_ROL_ID = f"""
DELETE FROM {TABLA_ROLES_PERMISOS}
WHERE rol_id = ?
"""

SQL_INSERT_ROL_PERMISO = f"""
INSERT INTO {TABLA_ROLES_PERMISOS}
(
    rol_id,
    opcion_id,
    ver,
    crear,
    editar,
    eliminar,
    exportar,
    aprobar
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
"""

SQL_DELETE_PERMISOS_LEGACY_BY_ROL = f"""
DELETE FROM {TABLA_PERMISOS_LEGACY}
WHERE rol = ?
"""

SQL_INSERT_PERMISOS_LEGACY_FROM_ROL = f"""
INSERT INTO {TABLA_PERMISOS_LEGACY}
(
    rol,
    opcion,
    ver,
    crear,
    editar,
    eliminar,
    exportar,
    aprobar
)
SELECT
    r.nombre,
    o.nombre,
    rp.ver,
    rp.crear,
    rp.editar,
    rp.eliminar,
    rp.exportar,
    rp.aprobar
FROM {TABLA_ROLES_PERMISOS} rp
INNER JOIN {TABLA_ROLES} r
    ON r.id = rp.rol_id
INNER JOIN {TABLA_OPCIONES} o
    ON o.id = rp.opcion_id
WHERE r.nombre = ?
"""

SQL_SELECT_PERMISOS_LEGACY = f"""
SELECT
    rol,
    opcion,
    ISNULL(ver, 0) AS ver,
    ISNULL(crear, 0) AS crear,
    ISNULL(editar, 0) AS editar,
    ISNULL(eliminar, 0) AS eliminar,
    ISNULL(exportar, 0) AS exportar,
    ISNULL(aprobar, 0) AS aprobar
FROM {TABLA_PERMISOS_LEGACY}
"""

SQL_INSERT_ROL_PERMISO_IF_NOT_EXISTS = f"""
IF NOT EXISTS (
    SELECT 1
    FROM {TABLA_ROLES_PERMISOS}
    WHERE rol_id = ? AND opcion_id = ?
)
BEGIN
    INSERT INTO {TABLA_ROLES_PERMISOS}
    (
        rol_id,
        opcion_id,
        ver,
        crear,
        editar,
        eliminar,
        exportar,
        aprobar
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
END
ELSE
BEGIN
    UPDATE {TABLA_ROLES_PERMISOS}
    SET
        ver = ?,
        crear = ?,
        editar = ?,
        eliminar = ?,
        exportar = ?,
        aprobar = ?
    WHERE rol_id = ? AND opcion_id = ?
END
"""