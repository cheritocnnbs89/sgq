# modules/parametros_generales/parameters_querys.py
# -*- coding: utf-8 -*-

from .parameters_constants import (
    TABLA_PARAM_GROUPS,
    TABLA_PARAM_VALUES,
)

SQL_SELECT_ALL_GROUPS = f"""
SELECT id, nombre
FROM {TABLA_PARAM_GROUPS}
ORDER BY nombre
"""

SQL_SELECT_ALL_VALUES = f"""
SELECT
    id,
    group_id,
    nombre,
    valor,
    parent_id,
    COALESCE(activo, 1) AS activo,
    COALESCE(orden, 0) AS orden
FROM {TABLA_PARAM_VALUES}
ORDER BY COALESCE(orden, 0), nombre
"""

SQL_SELECT_GROUP_BY_ID = f"""
SELECT id, nombre
FROM {TABLA_PARAM_GROUPS}
WHERE id = ?
"""

SQL_SELECT_VALUES_BY_GROUP_ID = f"""
SELECT
    id,
    group_id,
    nombre,
    valor,
    parent_id,
    COALESCE(activo, 1) AS activo,
    COALESCE(orden, 0) AS orden
FROM {TABLA_PARAM_VALUES}
WHERE group_id = ?
ORDER BY
    COALESCE(activo, 1) DESC,
    COALESCE(orden, 0),
    nombre
"""

SQL_SELECT_ACTIVE_VALUES_BY_GROUP_ID = f"""
SELECT
    id,
    group_id,
    nombre,
    valor,
    parent_id,
    COALESCE(activo, 1) AS activo,
    COALESCE(orden, 0) AS orden
FROM {TABLA_PARAM_VALUES}
WHERE group_id = ?
  AND COALESCE(activo, 1) = 1
ORDER BY COALESCE(orden, 0), nombre
"""

SQL_INSERT_GROUP = f"""
INSERT INTO {TABLA_PARAM_GROUPS}(nombre)
VALUES (?)
"""

SQL_UPDATE_GROUP = f"""
UPDATE {TABLA_PARAM_GROUPS}
SET nombre = ?
WHERE id = ?
"""

SQL_DELETE_VALUES_BY_GROUP_ID = f"""
UPDATE {TABLA_PARAM_VALUES}
SET activo = 0
WHERE group_id = ?
"""

SQL_DELETE_GROUP_BY_ID = f"""
DELETE FROM {TABLA_PARAM_GROUPS}
WHERE id = ?
"""

SQL_INSERT_VALUE = f"""
INSERT INTO {TABLA_PARAM_VALUES}(
    group_id,
    nombre,
    valor,
    parent_id,
    activo,
    orden
)
VALUES (?, ?, ?, ?, ?, ?)
"""

SQL_SELECT_VALUE_WITH_GROUP = f"""
SELECT
    pv.id,
    pv.group_id,
    pv.nombre,
    pv.valor,
    pv.parent_id,
    COALESCE(pv.activo, 1) AS activo,
    COALESCE(pv.orden, 0) AS orden,
    pg.nombre AS grupo_nombre
FROM {TABLA_PARAM_VALUES} pv
JOIN {TABLA_PARAM_GROUPS} pg
  ON pg.id = pv.group_id
WHERE pv.id = ?
  AND pv.group_id = ?
"""

SQL_UPDATE_VALUE = f"""
UPDATE {TABLA_PARAM_VALUES}
SET
    nombre = ?,
    valor = ?,
    parent_id = ?,
    activo = ?,
    orden = ?
WHERE id = ?
  AND group_id = ?
"""

SQL_DELETE_VALUE_BY_ID_AND_GROUP_ID = f"""
UPDATE {TABLA_PARAM_VALUES}
SET activo = 0
WHERE id = ?
  AND group_id = ?
"""

SQL_SELECT_VALUE_NAMES_BY_GROUP_ID = f"""
SELECT nombre
FROM {TABLA_PARAM_VALUES}
WHERE group_id = ?
  AND COALESCE(activo, 1) = 1
"""

SQL_INSERT_MANY_VALUES = f"""
INSERT INTO {TABLA_PARAM_VALUES}(
    group_id,
    nombre,
    valor,
    parent_id,
    activo,
    orden
)
VALUES (?, ?, ?, NULL, 1, 0)
"""