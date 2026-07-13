# modules/reclamos/routes_reclamos_querys.py
# -*- coding: utf-8 -*-
"""
Sentencias SQL para el modulo de reclamos/oportunidades de mejora.
Cada constante corresponde a un execute() en routes_reclamos.py.
"""

from .routes_reclamos_constants import *


# -- _GET_SPONSORS_BY_PROCESO --
SQL__GET_SPONSORS_BY_PROCESO_SEL_1 = f"""

        SELECT
            u.id AS usuario_id,
            UPPER(LTRIM(RTRIM(COALESCE(pv.valor, '')))) AS tipo_sponsor
        FROM {T_PARAM_VALUES} pv
        JOIN {T_PARAM_GROUPS} pg ON pg.id = pv.group_id
        JOIN {T_USUARIOS} u
          ON LTRIM(RTRIM(u.identificacion)) = LTRIM(RTRIM(pv.nombre))
        WHERE pg.nombre = 'RECL_PROCESO_SPONSOR'
          AND COALESCE(pv.activo, 1) = 1
          AND pv.parent_id = ?
          AND UPPER(LTRIM(RTRIM(COALESCE(pv.valor, '')))) IN ('PRINCIPAL', 'BACKUP')
          AND COALESCE(u.disabled, 0) = 0
        ORDER BY
          CASE UPPER(LTRIM(RTRIM(COALESCE(pv.valor, ''))))
            WHEN 'PRINCIPAL' THEN 1
            WHEN 'BACKUP' THEN 2
            ELSE 9
          END,
          COALESCE(pv.orden, 0),
          pv.id
"""


# -- _CAN_UPLOAD_CARTA_CLIENTE --
SQL__CAN_UPLOAD_CARTA_CLIENTE_SEL_1 = f"""

        SELECT TOP 1
            COALESCE(d.nombre, '') AS departamento_nombre,
            COALESCE(p.nombre, '') AS puesto_nombre
        FROM {T_USUARIOS} u
        LEFT JOIN {T_DEPARTAMENTOS} d
          ON d.id = u.departamento_id
        LEFT JOIN {T_PUESTOS} p
          ON p.id = u.puesto_id
        WHERE u.id = ?
"""


# -- _USUARIO_ES_SPONSOR_DEL_PROCESO --
SQL__USUARIO_ES_SPONSOR_DEL_PROCESO_SEL_1 = f"""

        SELECT TOP 1 1 AS ok
        FROM {T_PARAM_VALUES} pv
        JOIN {T_PARAM_GROUPS} pg
          ON pg.id = pv.group_id
        JOIN {T_USUARIOS} u
          ON LTRIM(RTRIM(u.identificacion)) = LTRIM(RTRIM(pv.nombre))
        WHERE pg.nombre = 'RECL_PROCESO_SPONSOR'
          AND COALESCE(pv.activo, 1) = 1
          AND pv.parent_id = ?
          AND u.id = ?
          AND COALESCE(u.disabled, 0) = 0
          AND UPPER(LTRIM(RTRIM(COALESCE(pv.valor, '')))) IN ('PRINCIPAL', 'BACKUP')
"""


# -- _FETCH_RECL_PROCESOS --
SQL__FETCH_RECL_PROCESOS_SEL_1 = f"""

        SELECT
            pv.id,
            pv.nombre,
            pv.valor,
            pv.orden
        FROM {T_PARAM_VALUES} pv
        JOIN {T_PARAM_GROUPS} pg ON pg.id = pv.group_id
        WHERE pg.nombre = 'RECL_PROCESO'
          AND COALESCE(pv.activo, 1) = 1
          AND pv.parent_id IS NULL
        ORDER BY COALESCE(pv.orden, 0), pv.valor, pv.nombre
"""


# -- _GET_SPONSOR_PRINCIPAL_BY_PROCESO --
SQL__GET_SPONSOR_PRINCIPAL_BY_PROCESO_SEL_1 = f"""

        SELECT TOP 1
            u.id AS usuario_id
        FROM {T_PARAM_VALUES} pv
        JOIN {T_PARAM_GROUPS} pg ON pg.id = pv.group_id
        JOIN {T_USUARIOS} u
          ON LTRIM(RTRIM(u.identificacion)) = LTRIM(RTRIM(pv.nombre))
        WHERE pg.nombre = 'RECL_PROCESO_SPONSOR'
          AND COALESCE(pv.activo, 1) = 1
          AND pv.parent_id = ?
          AND UPPER(LTRIM(RTRIM(COALESCE(pv.valor, '')))) = 'PRINCIPAL'
          AND COALESCE(u.disabled, 0) = 0
        ORDER BY COALESCE(pv.orden, 0), pv.id
"""


# -- _TABLE_EXISTS --
SQL__TABLE_EXISTS_SEL_1 = """

            SELECT 1
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = ?
"""

SQL__TABLE_EXISTS_SEL_2 = """

        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
"""


# -- _COL_NAMES --
SQL__COL_NAMES_SEL_1 = """

                SELECT COLUMN_NAME AS name
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = ?
"""


# -- _CAN_EXPORT_ALL_RECLAMOS --
SQL__CAN_EXPORT_ALL_RECLAMOS_SEL_1 = f"""

            SELECT TOP 1
                UPPER(LTRIM(RTRIM(COALESCE(p.nombre,'')))) AS puesto_nombre
            FROM {T_USUARIOS} u
            LEFT JOIN {T_PUESTOS} p ON p.id = u.puesto_id
            WHERE u.id = ?
"""

SQL__CAN_EXPORT_ALL_RECLAMOS_SEL_2 = f"""

            SELECT TOP 1
                UPPER(TRIM(COALESCE(p.nombre,''))) AS puesto_nombre
            FROM {T_USUARIOS} u
            LEFT JOIN {T_PUESTOS} p ON p.id = u.puesto_id
            WHERE u.id = ?
"""


# -- _PUEDE_GESTIONAR_IMPUTADO_ACCION --
SQL__PUEDE_GESTIONAR_IMPUTADO_ACCION_SEL_1 = f"""

            SELECT TOP 1
                a.id,
                a.imputacion_id,
                a.reclamo_id,
                a.tipo,
                COALESCE(a.activo, 1) AS accion_activa,
                COALESCE(a.cumplido, 0) AS cumplido,
                ri.imputado_id,
                COALESCE(ri.estado_asignacion, '') AS estado_asignacion
            FROM {T_RECLAMO_IMPUTADO_ACCIONES} a
            JOIN {T_RECLAMO_IMPUTADOS} ri
              ON ri.id = a.imputacion_id
            WHERE a.id = ?
"""


# -- _CAN_VIEW_ALL_RECLAMOS --
SQL__CAN_VIEW_ALL_RECLAMOS_SEL_1 = f"""

                SELECT TOP 1
                    d.nombre AS departamento_nombre,
                    p.nombre AS puesto_nombre
                FROM {T_USUARIOS} u
                LEFT JOIN {T_DEPARTAMENTOS} d ON d.id = u.departamento_id
                LEFT JOIN {T_PUESTOS} p ON p.id = u.puesto_id
                WHERE u.id = ?
"""

SQL__CAN_VIEW_ALL_RECLAMOS_SEL_2 = f"""

                SELECT
                    d.nombre AS departamento_nombre,
                    p.nombre AS puesto_nombre
                FROM {T_USUARIOS} u
                LEFT JOIN {T_DEPARTAMENTOS} d ON d.id = u.departamento_id
                LEFT JOIN {T_PUESTOS} p ON p.id = u.puesto_id
                WHERE u.id = ?
                LIMIT 1
"""


# -- _CAN_VIEW_ALL_RECLAMOS_SN_SPONSOR --
SQL__CAN_VIEW_ALL_RECLAMOS_SN_SPONSOR_SEL_1 = f"""

                SELECT
                    COALESCE(d.nombre, '') AS departamento_nombre,
                    COALESCE(p.nombre, '') AS puesto_nombre
                FROM {T_USUARIOS} u
                LEFT JOIN {T_DEPARTAMENTOS} d ON d.id = u.departamento_id
                LEFT JOIN {T_PUESTOS} p ON p.id = u.puesto_id
                WHERE u.id = ?
                LIMIT 1
"""


# -- _ES_MIEMBRO_EQUIPO_RECLAMO --
SQL__ES_MIEMBRO_EQUIPO_RECLAMO_SEL_1 = f"""

        SELECT TOP 1 1 AS ok
        FROM {T_RECLAMO_EQUIPO_RESPUESTAS}
        WHERE reclamo_id = ?
          AND usuario_id = ?
          AND activo = 1
"""


# -- _NOTIFY_SPONSOR_RESPUESTA_EQUIPO --
SQL__NOTIFY_SPONSOR_RESPUESTA_EQUIPO_SEL_1 = f"""

        SELECT TOP 1
            ri.id AS imputacion_id,
            ri.reclamo_id,
            ri.imputado_id,
            r.proceso_id,
            r.codigo,
            r.tipo_reclamo,
            r.tipo_tramite,
            r.cliente_nombre,
            r.proceso_text,
            r.observacion,
            r.antecedente,
            COALESCE(um.nombre_completo, um.username) AS miembro_nombre,
            um.username AS miembro_username,

            eq.creado_at AS fecha_asignacion_miembro,
            rre.created_at AS fecha_respuesta_miembro

        FROM {T_RECLAMO_IMPUTADOS} ri
        JOIN {T_RECLAMOS} r
          ON r.id = ri.reclamo_id

        LEFT JOIN {T_USUARIOS} um
          ON um.id = ?

        LEFT JOIN {T_RECLAMO_EQUIPO_RESPUESTAS} eq
          ON eq.reclamo_id = ri.reclamo_id
         AND eq.imputacion_id = ri.id
         AND eq.usuario_id = ?

        LEFT JOIN {T_RECLAMO_RESPUESTAS_EQUIPO} rre
          ON rre.reclamo_id = ri.reclamo_id
         AND rre.imputacion_id = ri.id
         AND rre.miembro_id = ?

        WHERE ri.id = ?
"""

SQL__NOTIFY_SPONSOR_RESPUESTA_EQUIPO_SEL_2 = f"""

            SELECT
                u.id AS sponsor_id,
                COALESCE(u.nombre_completo, u.username) AS sponsor_nombre,
                u.username AS sponsor_username,
                u.email AS sponsor_email,
                UPPER(LTRIM(RTRIM(COALESCE(pv.valor, '')))) AS tipo_sponsor
            FROM {T_PARAM_VALUES} pv
            JOIN {T_PARAM_GROUPS} pg
              ON pg.id = pv.group_id
            JOIN {T_USUARIOS} u
              ON LTRIM(RTRIM(u.identificacion)) = LTRIM(RTRIM(pv.nombre))
            WHERE pg.nombre = 'RECL_PROCESO_SPONSOR'
              AND COALESCE(pv.activo, 1) = 1
              AND pv.parent_id = ?
              AND UPPER(LTRIM(RTRIM(COALESCE(pv.valor, '')))) IN ('PRINCIPAL', 'BACKUP')
              AND COALESCE(u.disabled, 0) = 0
              AND u.email IS NOT NULL
              AND LTRIM(RTRIM(u.email)) <> ''
            ORDER BY
              CASE UPPER(LTRIM(RTRIM(COALESCE(pv.valor, ''))))
                WHEN 'PRINCIPAL' THEN 1
                WHEN 'BACKUP' THEN 2
                ELSE 9
              END,
              COALESCE(pv.orden, 0),
              pv.id
"""

SQL__NOTIFY_SPONSOR_RESPUESTA_EQUIPO_SEL_3 = f"""

            SELECT
                u.id AS sponsor_id,
                COALESCE(u.nombre_completo, u.username) AS sponsor_nombre,
                u.username AS sponsor_username,
                u.email AS sponsor_email,
                'PRINCIPAL' AS tipo_sponsor
            FROM {T_RECLAMO_IMPUTADOS} ri
            JOIN {T_USUARIOS} u
              ON u.id = ri.imputado_id
            WHERE ri.id = ?
              AND COALESCE(u.disabled, 0) = 0
              AND u.email IS NOT NULL
              AND LTRIM(RTRIM(u.email)) <> ''
"""


# -- _GET_RESPUESTA_EQUIPO_ACCIONES_FULL --
SQL__GET_RESPUESTA_EQUIPO_ACCIONES_FULL_SEL_1 = f"""

        SELECT
            a.id,
            a.tipo,
            a.descripcion,
            a.fecha_compromiso,
            COALESCE(a.orden, 1) AS orden,
            COALESCE(a.requiere_evidencia, 0) AS requiere_evidencia,
            COALESCE(a.cumplido, 0) AS cumplido,
            COALESCE(a.fecha_cumplimiento, '') AS fecha_cumplimiento,
            COALESCE(a.observacion_cumplimiento, '') AS observacion_cumplimiento
        FROM {T_RECLAMO_RESPUESTA_EQUIPO_ACCIONES} a
        WHERE a.respuesta_equipo_id = ?
          AND COALESCE(a.activo, 1) = 1
        ORDER BY
            CASE a.tipo
                WHEN 'CAUSA' THEN 1
                WHEN 'CONTROL' THEN 2
                WHEN 'CORRECTIVA' THEN 3
                ELSE 9
            END,
            COALESCE(a.orden, 1),
            a.id
"""

SQL__GET_RESPUESTA_EQUIPO_ACCIONES_FULL_SEL_2 = f"""

            SELECT
                e.id,
                e.filename,
                e.original_name,
                COALESCE(e.content_type, '') AS content_type,
                COALESCE(e.size_bytes, 0) AS size_bytes,
                COALESCE(e.created_at, '') AS created_at
            FROM {T_RECLAMO_RESPUESTA_EQUIPO_ACCION_EVIDENCIAS} e
            WHERE e.accion_id = ?
              AND COALESCE(e.activo, 1) = 1
            ORDER BY e.id
"""


# -- _NOTIFY_RECLAMO_ADJUNTOS_CHANGE --
SQL__NOTIFY_RECLAMO_ADJUNTOS_CHANGE_SEL_1 = f"""

        SELECT codigo, creado_por
        FROM {T_RECLAMOS}
        WHERE id = ?
"""


# -- _SAVE_RESPUESTA_EQUIPO_ACCIONES --
SQL__SAVE_RESPUESTA_EQUIPO_ACCIONES_UPD_1 = f"""

        UPDATE {T_RECLAMO_RESPUESTA_EQUIPO_ACCIONES}
        SET activo = 0,
            updated_at = ?,
            updated_by = ?
        WHERE respuesta_equipo_id = ?
          AND activo = 1
"""

SQL__SAVE_RESPUESTA_EQUIPO_ACCIONES_INS_2 = f"""

                INSERT INTO {T_RECLAMO_RESPUESTA_EQUIPO_ACCIONES} (
                    respuesta_equipo_id,
                    reclamo_id,
                    imputacion_id,
                    miembro_id,
                    tipo,
                    descripcion,
                    fecha_compromiso,
                    orden,
                    requiere_evidencia,
                    activo,
                    created_at,
                    created_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
"""


# -- _GET_RESPUESTA_EQUIPO_ACCIONES --
SQL__GET_RESPUESTA_EQUIPO_ACCIONES_SEL_1 = f"""

        SELECT id, tipo, descripcion, fecha_compromiso, orden,
               requiere_evidencia, cumplido, fecha_cumplimiento
        FROM {T_RECLAMO_RESPUESTA_EQUIPO_ACCIONES}
        WHERE respuesta_equipo_id = ?
          AND activo = 1
        ORDER BY tipo, orden, id
"""


# -- _GET_IMPUTADO_ACCIONES_FULL --
SQL__GET_IMPUTADO_ACCIONES_FULL_SEL_1 = f"""

        SELECT
            a.id,
            a.tipo,
            a.descripcion,
            a.fecha_compromiso,
            COALESCE(a.orden, 1) AS orden,
            COALESCE(a.requiere_evidencia, 0) AS requiere_evidencia,
            COALESCE(a.cumplido, 0) AS cumplido,
            COALESCE(a.fecha_cumplimiento, '') AS fecha_cumplimiento,
            COALESCE(a.observacion_cumplimiento, '') AS observacion_cumplimiento
        FROM {T_RECLAMO_IMPUTADO_ACCIONES} a
        WHERE a.imputacion_id = ?
          AND COALESCE(a.activo, 1) = 1
        ORDER BY
            CASE a.tipo
                WHEN 'CAUSA' THEN 1
                WHEN 'CONTROL' THEN 2
                WHEN 'CORRECTIVA' THEN 3
                ELSE 9
            END,
            COALESCE(a.orden, 1),
            a.id
"""

SQL__GET_IMPUTADO_ACCIONES_FULL_SEL_2 = f"""

            SELECT
                e.id,
                e.filename,
                e.original_name,
                COALESCE(e.content_type, '') AS content_type,
                COALESCE(e.size_bytes, 0) AS size_bytes,
                COALESCE(e.created_at, '') AS created_at
            FROM {T_RECLAMO_ACCION_EVIDENCIAS} e
            WHERE e.accion_id = ?
              AND COALESCE(e.activo, 1) = 1
            ORDER BY e.id
"""


# -- _PUEDE_GESTIONAR_EQUIPO --
SQL__PUEDE_GESTIONAR_EQUIPO_SEL_1 = f"""

        SELECT TOP 1 1 AS ok
        FROM {T_RECLAMOS} r
        JOIN {T_RECLAMO_IMPUTADOS} ri
          ON ri.reclamo_id = r.id
        WHERE r.id = ?
          AND ri.estado_asignacion = 'aprobado'
          AND (
                ri.imputado_id = ?
                OR EXISTS (
                    SELECT 1
                    FROM {T_PARAM_VALUES} pv
                    JOIN {T_PARAM_GROUPS} pg
                      ON pg.id = pv.group_id
                    JOIN {T_USUARIOS} u
                      ON LTRIM(RTRIM(u.identificacion)) = LTRIM(RTRIM(pv.nombre))
                    WHERE pg.nombre = 'RECL_PROCESO_SPONSOR'
                      AND COALESCE(pv.activo, 1) = 1
                      AND pv.parent_id = r.proceso_id
                      AND u.id = ?
                      AND COALESCE(u.disabled, 0) = 0
                      AND UPPER(LTRIM(RTRIM(COALESCE(pv.valor, '')))) IN ('PRINCIPAL', 'BACKUP')
                )
          )
"""


# -- _PUEDE_VER_EQUIPO --
SQL__PUEDE_VER_EQUIPO_SEL_1 = f"""

        SELECT TOP 1 1 AS ok
        FROM {T_RECLAMO_EQUIPO_RESPUESTAS} er
        WHERE er.reclamo_id = ?
          AND er.usuario_id = ?
          AND COALESCE(er.activo, 1) = 1
"""

SQL__PUEDE_VER_EQUIPO_SEL_2 = f"""

        SELECT TOP 1 1 AS ok
        FROM {T_RECLAMOS} r
        WHERE r.id = ?
          AND r.creado_por = ?
"""


# -- FETCH_PRODUCTOS --
SQL_FETCH_PRODUCTOS_SEL_1 = f"""

        SELECT id, nombre
        FROM {T_PRODUCTOS}
        WHERE COALESCE(activo, 1) = 1
        ORDER BY nombre
"""


# -- FETCH_USUARIOS_IMPUTABLES --
SQL_FETCH_USUARIOS_IMPUTABLES_SEL_1 = f"""
        SELECT
            u.id,
            u.username,
            COALESCE(u.nombre_completo, u.username) AS nombre_completo,
            d.nombre AS departamento_nombre,
            COALESCE(j.nombre_completo, j.username) AS jefe_nombre,
            u.empresa_id,
            u.jefe_id
        FROM {T_USUARIOS} u
        LEFT JOIN {T_DEPARTAMENTOS} d ON d.id = u.departamento_id
        LEFT JOIN {T_USUARIOS} j ON j.id = u.jefe_id          -- 👈 jefe desde la misma tabla
        WHERE COALESCE(u.disabled, 0) = 0
        and u.identificacion not in ('40623','0911946630','0923577688','0929626729','1307590834'   ,'40736','0902507805','1714868211')
    """


# -- _ENSURE_PARAM_GROUP --
SQL__ENSURE_PARAM_GROUP_SEL_1 = f"""

        SELECT TOP 1 id
        FROM {T_PARAM_GROUPS}
        WHERE nombre = ?
"""


# -- _ENSURE_PARAM_VALUE --
SQL__ENSURE_PARAM_VALUE_SEL_1 = f"""

        SELECT id
        FROM {T_PARAM_VALUES}
        WHERE group_id = ? AND nombre = ?
"""

SQL__ENSURE_PARAM_VALUE_UPD_2 = f"""

            UPDATE {T_PARAM_VALUES}
               SET valor = ?,
                   orden = ?,
                   activo = ?
             WHERE id = ?
"""

SQL__ENSURE_PARAM_VALUE_INS_3 = f"""

            INSERT INTO {T_PARAM_VALUES}(group_id, nombre, valor, orden, activo)
            VALUES (?, ?, ?, ?, ?)
"""


# -- _FETCH_PARAM_VALUES --
SQL__FETCH_PARAM_VALUES_SEL_1 = f"""

        SELECT pv.id, pv.nombre, pv.valor, pv.orden
        FROM {T_PARAM_VALUES} pv
        JOIN {T_PARAM_GROUPS} pg ON pg.id = pv.group_id
        WHERE pg.nombre = ?
          AND COALESCE(pv.activo, 1) = 1
        ORDER BY pv.orden, pv.valor, pv.nombre
"""


# -- _CAN_EDIT_EQUIPO --
SQL__CAN_EDIT_EQUIPO_SEL_1 = f"""

        SELECT responsable_id, colaborador_id
        FROM {T_RECLAMO_EQUIPO}
        WHERE id = ?
"""


# -- FETCH_REGIONES --
SQL_FETCH_REGIONES_SEL_1 = f"""

        SELECT id, nombre
        FROM {T_REGIONES}
        WHERE COALESCE(activo,1) = 1
        ORDER BY orden, nombre
"""


# -- FETCH_PROVINCIAS --
SQL_FETCH_PROVINCIAS_SEL_1 = f"""

            SELECT id, nombre
            FROM {T_PROVINCIAS}
            WHERE region_id = ? AND COALESCE(activo,1)=1
            ORDER BY orden, nombre
"""

SQL_FETCH_PROVINCIAS_SEL_2 = f"""

            SELECT id, nombre
            FROM {T_PROVINCIAS}
            WHERE COALESCE(activo,1)=1
            ORDER BY orden, nombre
"""


# -- FETCH_CANTONES --
SQL_FETCH_CANTONES_SEL_1 = f"""

            SELECT id, nombre
            FROM {T_CANTONES}
            WHERE provincia_id = ? AND COALESCE(activo,1)=1
            ORDER BY orden, nombre
"""

SQL_FETCH_CANTONES_SEL_2 = f"""

            SELECT id, nombre
            FROM {T_CANTONES}
            WHERE COALESCE(activo,1)=1
            ORDER BY orden, nombre
"""


# -- _GENERATE_CODIGO_RECLAMO --
SQL__GENERATE_CODIGO_RECLAMO_SEL_1 = f"""

        SELECT TOP 1 codigo 
                FROM {T_RECLAMOS}
        WHERE codigo LIKE 'RECL%'
        ORDER BY id DESC
"""


# -- _GUESS_APROBADOR_FOR_USER2 --
SQL__GUESS_APROBADOR_FOR_USER2_SEL_1 = f"""

        SELECT departamento_id, LOWER(rol) AS rol
        FROM {T_USUARIOS}
        WHERE id = ?
"""


# -- _GUESS_APROBADOR_FOR_USER --
SQL__GUESS_APROBADOR_FOR_USER_SEL_1 = f"""

        SELECT jefe_id, departamento_id
        FROM {T_USUARIOS}
        WHERE id = ?
"""

SQL__GUESS_APROBADOR_FOR_USER_SEL_2 = f"""

            SELECT id
            FROM {T_USUARIOS}
            WHERE id = ?
              AND COALESCE(disabled, 0) = 0
"""


# -- _GET_USER_BASIC --
SQL__GET_USER_BASIC_SEL_1 = f"""

        SELECT id, username, email, rol, departamento_id, nombre_completo
        FROM {T_USUARIOS}
        WHERE id = ?
"""


# -- _NOTIFY_COLABORADOR_ASIGNADO --
SQL__NOTIFY_COLABORADOR_ASIGNADO_SEL_1 = f"""

        SELECT TOP 1 id, fecha_reclamo, tipo_reclamo, tipo_tramite,
               cliente_nombre, proceso_text, material_desc,
               fecha_pedido, factura, guia_remision,
               antecedente, observacion
        FROM {T_RECLAMOS}
        WHERE codigo = ?
"""


# -- _get_param_int_by_id (nested, cur2, sqlserver) --
SQL__GET_PARAM_INT_BY_ID_SEL_SS = f"""
                    SELECT TOP 1 valor
                    FROM {T_PARAM_VALUES}
                    WHERE id = ? AND activo = 1
                """

# -- _get_param_int_by_id (nested, cur2, sqlite) --
SQL__GET_PARAM_INT_BY_ID_SEL_SL = f"""
                    SELECT TOP 1valor
                    FROM {T_PARAM_VALUES}
                    WHERE id = ? AND activo = 1

                """

# -- _get_gerente_general_email (nested, cur2, sqlserver) --
SQL__GET_GERENTE_GENERAL_EMAIL_SEL_SS = f"""
                    SELECT TOP 1 email
                    FROM {T_USUARIOS}
                    WHERE LOWER(LTRIM(RTRIM(rol))) = 'gerente general'
                    AND email IS NOT NULL
                    AND LTRIM(RTRIM(email)) <> ''
                """

# -- _get_gerente_general_email (nested, cur2, sqlite) --
SQL__GET_GERENTE_GENERAL_EMAIL_SEL_SL = f"""
                    SELECT  TOP 1 email
                    FROM {T_USUARIOS}
                    WHERE LOWER(TRIM(rol)) = 'gerente general'
                    AND email IS NOT NULL
                    AND TRIM(email) <> ''

                """

# -- _notify_gg_if_needed (nested, cur2, sqlserver) --
SQL__NOTIFY_GG_IF_NEEDED_SEL_SS = f"""
                    SELECT r.id, r.codigo, r.fecha_reclamo, COALESCE(r.cliente_nombre,'') AS cliente_nombre
                    FROM {T_RECLAMOS} r
                    WHERE COALESCE(r.gg_notificado,0) = 0
                    AND r.id IN (
                            SELECT ri.reclamo_id
                            FROM {T_RECLAMO_IMPUTADOS} ri
                            WHERE ri.estado_asignacion = 'aprobado'
                            AND ri.estado_respuesta = 'sin_respuesta'
                    )
                    AND DATEDIFF(
                            DAY,
                            CAST(TRY_CONVERT(date, r.fecha_reclamo) AS date),
                            CAST(GETDATE() AS date)
                    ) >= ?
                    ORDER BY r.id DESC
                """

# -- _notify_gg_if_needed (nested, cur2, sqlite) --
SQL__NOTIFY_GG_IF_NEEDED_SEL_SL = f"""
                    SELECT r.id, r.codigo, r.fecha_reclamo, COALESCE(r.cliente_nombre,'') AS cliente_nombre
                    FROM {T_RECLAMOS} r
                    WHERE COALESCE(r.gg_notificado,0) = 0
                    AND r.id IN (
                            SELECT ri.reclamo_id
                            FROM {T_RECLAMO_IMPUTADOS} ri
                            WHERE ri.estado_asignacion = 'aprobado'
                            AND ri.estado_respuesta = 'sin_respuesta'
                    )
                    AND (
                            CAST(julianday('now') - julianday(substr(r.fecha_reclamo,1,10)) AS INTEGER) >= ?
                    )
                    ORDER BY r.id DESC
                """

SQL__NOTIFY_COLABORADOR_ASIGNADO_SEL_2 = f"""

                SELECT STUFF((
                    SELECT ', ' + COALESCE(u.username, '')
                    FROM {T_RECLAMO_IMPUTADOS} ri
                    JOIN {T_USUARIOS} u ON u.id = ri.imputado_id
                    WHERE ri.reclamo_id = ?
                    FOR XML PATH(''), TYPE
                ).value('.', 'NVARCHAR(MAX)'), 1, 2, '') AS lista
"""

SQL__NOTIFY_COLABORADOR_ASIGNADO_SEL_3 = f"""

                    SELECT GROUP_CONCAT(u.username, ', ') AS lista
                    FROM {T_RECLAMO_IMPUTADOS} ri
                    JOIN {T_USUARIOS} u ON u.id = ri.imputado_id
                    WHERE ri.reclamo_id = ?
"""


# -- _NOTIFY_COLABORADOR_APORTE_RECHAZADO --
SQL__NOTIFY_COLABORADOR_APORTE_RECHAZADO_SEL_1 = f"""

        SELECT DISTINCT
            u.id,
            COALESCE(u.nombre_completo, u.username) AS nombre,
            u.username,
            u.email
        FROM {T_USUARIOS} u
        LEFT JOIN {T_DEPARTAMENTOS} d
          ON d.id = u.departamento_id
        LEFT JOIN {T_PUESTOS} p
          ON p.id = u.puesto_id
        WHERE COALESCE(u.disabled, 0) = 0
          AND u.email IS NOT NULL
          AND LTRIM(RTRIM(u.email)) <> ''
          AND (
                LOWER(LTRIM(RTRIM(COALESCE(d.nombre, '')))) = 'servicio al cliente'
                OR UPPER(LTRIM(RTRIM(COALESCE(p.nombre, '')))) LIKE '%SERVICIO AL CLIENTE%'
          )
"""


# -- _SAVE_ADJUNTOS_FOR_RECLAMO --
SQL__SAVE_ADJUNTOS_FOR_RECLAMO_SEL_1 = f"""

        SELECT COUNT(*) AS c
        FROM {T_RECLAMO_ADJUNTOS}
        WHERE reclamo_id = ?
"""

SQL__SAVE_ADJUNTOS_FOR_RECLAMO_INS_2 = f"""

            INSERT INTO {T_RECLAMO_ADJUNTOS}(
                reclamo_id, filename, original_name,
                content_type, size_bytes,
                creado_por, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
"""


# -- _NOTIFY_APROBADOR_IMPUTACION --
SQL__NOTIFY_APROBADOR_IMPUTACION_SEL_1 = f"""

            SELECT STRING_AGG(CAST(u.username AS VARCHAR(MAX)), ', ') AS lista
            FROM {T_RECLAMO_IMPUTADOS} ri
            JOIN {T_USUARIOS} u ON u.id = ri.imputado_id
            WHERE ri.reclamo_id = ?
"""


# -- _GET_SPONSOR_EMAILS_BY_RECLAMO --
SQL__GET_SPONSOR_EMAILS_BY_RECLAMO_SEL_1 = f"""

        SELECT
            x.id,
            x.nombre,
            x.username,
            x.email,
            x.tipo_sponsor
        FROM (
            SELECT
                u.id,
                COALESCE(u.nombre_completo, u.username) AS nombre,
                u.username,
                u.email,
                UPPER(LTRIM(RTRIM(COALESCE(pv.valor, '')))) AS tipo_sponsor,
                CASE UPPER(LTRIM(RTRIM(COALESCE(pv.valor, ''))))
                    WHEN 'PRINCIPAL' THEN 1
                    WHEN 'BACKUP' THEN 2
                    ELSE 9
                END AS orden_sponsor,
                ROW_NUMBER() OVER (
                    PARTITION BY u.email
                    ORDER BY
                        CASE UPPER(LTRIM(RTRIM(COALESCE(pv.valor, ''))))
                            WHEN 'PRINCIPAL' THEN 1
                            WHEN 'BACKUP' THEN 2
                            ELSE 9
                        END,
                        pv.id
                ) AS rn
            FROM {T_RECLAMOS} r
            JOIN {T_PARAM_VALUES} pv
              ON pv.parent_id = r.proceso_id
            JOIN {T_PARAM_GROUPS} pg
              ON pg.id = pv.group_id
            JOIN {T_USUARIOS} u
              ON LTRIM(RTRIM(u.identificacion)) = LTRIM(RTRIM(pv.nombre))
            WHERE r.codigo = ?
              AND pg.nombre = 'RECL_PROCESO_SPONSOR'
              AND COALESCE(pv.activo, 1) = 1
              AND UPPER(LTRIM(RTRIM(COALESCE(pv.valor, '')))) IN ('PRINCIPAL', 'BACKUP')
              AND COALESCE(u.disabled, 0) = 0
              AND u.email IS NOT NULL
              AND LTRIM(RTRIM(u.email)) <> ''
        ) x
        WHERE x.rn = 1
        ORDER BY x.orden_sponsor, x.id
"""


# -- REGISTER_RECLAMOS_ROUTES --
SQL_REGISTER_RECLAMOS_ROUTES_SEL_1 = f"""

            SELECT TOP 1 id
            FROM {T_PARAM_GROUPS}
            WHERE nombre = 'RECL_SUBTIPO'
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_2 = f"""

            SELECT
                id,
                nombre,
                valor,
                orden
            FROM {T_PARAM_VALUES}
            WHERE group_id = ?
            AND COALESCE(activo, 1) = 1
            AND COALESCE(parent_id, 0) = ?
            ORDER BY
            COALESCE(orden, 0),
            valor
"""

SQL_REGISTER_RECLAMOS_ROUTES_INS_3 = f"""

                    INSERT INTO {T_RECLAMO_EQUIPO_ACCIONES} (
                        equipo_id, tipo, descripcion, fecha_compromiso, created_at, created_by
                    ) VALUES (?, ?, ?, ?, ?, ?)
"""

SQL_REGISTER_RECLAMOS_ROUTES_UPD_4 = f"""

            UPDATE {T_RECLAMO_EQUIPO}
            SET
                respuesta_causa      = ?,
                respuesta_preventiva = ?,
                respuesta_correctiva = ?,
                fecha_respuesta      = COALESCE(fecha_respuesta, ?)
            WHERE id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_5 = f"""

            SELECT id, tipo, descripcion, fecha_compromiso
            FROM {T_RECLAMO_EQUIPO_ACCIONES}
            WHERE equipo_id = ?
            ORDER BY id ASC
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_6 = f"""

            SELECT TOP 1 respuesta_causa, respuesta_preventiva, respuesta_correctiva
            FROM {T_RECLAMO_EQUIPO}
            WHERE id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_7 = f"""

                SELECT TOP 1 id
                FROM {T_RECLAMO_IMPUTADOS}
                WHERE reclamo_id = ?
                ORDER BY id DESC
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_8 = f"""

                SELECT
                    er.id AS equipo_id,
                    er.id AS id,                 -- por compatibilidad si tu front usa "id"
                    er.reclamo_id,
                    NULL AS imputacion_id,
                    er.usuario_id,
                    er.puede_responder,
                    er.activo,
                    er.creado_por,
                    er.creado_at,
                    u.username,
                    COALESCE(u.nombre_completo, u.username) AS nombre,
                    u.rol AS rol,
                    d.nombre AS departamento,
                    0 AS tiene_respuesta,
                    NULL AS fecha_respuesta,
                    NULL AS respuesta_id
                FROM {T_RECLAMO_EQUIPO_RESPUESTAS} er
                JOIN {T_USUARIOS} u ON er.usuario_id = u.id
                LEFT JOIN {T_DEPARTAMENTOS} d ON u.departamento_id = d.id
                WHERE er.reclamo_id = ?
                AND er.activo = 1
                ORDER BY nombre
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_9 = f"""

                SELECT
                    er.id AS equipo_id,
                    er.id AS id,                 -- por compatibilidad
                    er.reclamo_id,
                    er.imputacion_id,
                    er.usuario_id,
                    u.username,
                    COALESCE(u.nombre_completo, u.username) AS nombre,
                    er.puede_responder,
                    er.activo,
                    u.rol AS rol,
                    d.nombre AS departamento,

                    CASE WHEN rrmax.id IS NULL THEN 0 ELSE 1 END AS tiene_respuesta,
                    rre.created_at AS fecha_respuesta,
                    rrmax.id AS respuesta_id

                FROM {T_RECLAMO_EQUIPO_RESPUESTAS} er
                JOIN {T_USUARIOS} u ON u.id = er.usuario_id
                LEFT JOIN {T_DEPARTAMENTOS} d ON d.id = u.departamento_id

                LEFT JOIN (
                    SELECT MAX(id) AS id, reclamo_id, imputacion_id, miembro_id
                    FROM {T_RECLAMO_RESPUESTAS_EQUIPO}
                    WHERE activo = 1
                    GROUP BY reclamo_id, imputacion_id, miembro_id
                ) rrmax
                ON rrmax.reclamo_id   = er.reclamo_id
                AND rrmax.imputacion_id = er.imputacion_id
                AND rrmax.miembro_id    = er.usuario_id

                LEFT JOIN {T_RECLAMO_RESPUESTAS_EQUIPO} rre
                ON rre.id = rrmax.id

                WHERE er.reclamo_id = ?
                AND er.imputacion_id = ?
                AND er.activo = 1

                ORDER BY nombre
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_10 = f"""

            SELECT TOP 1 id
            FROM {T_USUARIOS}
            WHERE id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_11 = f"""

                SELECT TOP 1 id
                FROM {T_RECLAMO_IMPUTADOS}
                WHERE reclamo_id = ?
                AND imputado_id = ?
                ORDER BY id DESC
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_12 = f"""

            SELECT TOP 1 1 AS ok
            FROM {T_RECLAMO_IMPUTADOS}
            WHERE id = ?
            AND reclamo_id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_INS_13 = f"""

            INSERT INTO {T_RECLAMO_EQUIPO_RESPUESTAS} (
                reclamo_id,
                imputacion_id,
                usuario_id,
                puede_responder,
                activo,
                creado_por,
                creado_at
            )
            VALUES (?, ?, ?, 1, 1, ?, ?)
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_14 = f"""

                SELECT TOP 1 codigo
                FROM {T_RECLAMOS}
                WHERE id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_15 = f"""

                SELECT TOP 1
                    username,
                    nombre_completo
                FROM {T_USUARIOS}
                WHERE id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_16 = f"""

                SELECT TOP 1 imputacion_id
                FROM {T_RECLAMO_EQUIPO_RESPUESTAS}
                WHERE reclamo_id = ?
                AND usuario_id = ?
                AND activo = 1
                ORDER BY id DESC
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_17 = f"""

            SELECT TOP 1 1 AS ok
            FROM {T_RECLAMO_EQUIPO_RESPUESTAS}
            WHERE reclamo_id = ?
            AND imputacion_id = ?
            AND usuario_id = ?
            AND activo = 1
            AND puede_responder = 1
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_18 = f"""

            SELECT TOP 1 id
            FROM {T_RECLAMO_RESPUESTAS_EQUIPO}
            WHERE reclamo_id = ?
            AND imputacion_id = ?
            AND miembro_id = ?
            AND activo = 1
            ORDER BY id DESC
"""

SQL_REGISTER_RECLAMOS_ROUTES_UPD_19 = f"""

                UPDATE {T_RECLAMO_RESPUESTAS_EQUIPO}
                SET metodo_analisis = ?,
                    causa = ?,
                    preventiva = ?,
                    correctiva = ?,
                    fecha_causa = ?,
                    fecha_preventiva = ?,
                    fecha_correctiva = ?,
                    fish_metodo = ?,
                    fish_maquinas = ?,
                    fish_materiales = ?,
                    fish_personas = ?,
                    fish_entorno = ?,
                    fish_medicion = ?,
                    why1 = ?,
                    why2 = ?,
                    why3 = ?,
                    why4 = ?,
                    why5 = ?,
                    created_at = ?,
                    created_by = ?
                WHERE id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_INS_20 = f"""

                INSERT INTO {T_RECLAMO_RESPUESTAS_EQUIPO} (
                    reclamo_id,
                    imputacion_id,
                    miembro_id,
                    metodo_analisis,
                    causa,
                    preventiva,
                    correctiva,
                    fecha_causa,
                    fecha_preventiva,
                    fecha_correctiva,
                    fish_metodo,
                    fish_maquinas,
                    fish_materiales,
                    fish_personas,
                    fish_entorno,
                    fish_medicion,
                    why1,
                    why2,
                    why3,
                    why4,
                    why5,
                    activo,
                    created_by,
                    created_at
                )
                OUTPUT inserted.id
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_21 = f"""

            SELECT TOP 1 1 AS ok
            FROM {T_USUARIOS}
            WHERE id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_22 = f"""

                SELECT TOP 1 usuario_id
                FROM {T_RECLAMO_EQUIPO_RESPUESTAS}
                WHERE id = ?
                AND reclamo_id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_23 = f"""

            SELECT TOP 1
                r.id AS reclamo_id,
                r.proceso_id,
                ri.id AS imputacion_id,
                ri.imputado_id
            FROM {T_RECLAMOS} r
            JOIN {T_RECLAMO_IMPUTADOS} ri
            ON ri.reclamo_id = r.id
            WHERE r.id = ?
            AND ri.id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_24 = f"""

            SELECT TOP 1 1 AS ok
            FROM {T_RECLAMO_EQUIPO_RESPUESTAS}
            WHERE reclamo_id = ?
            AND imputacion_id = ?
            AND usuario_id = ?
            AND activo = 1
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_25 = f"""

            SELECT TOP 1
                rre.*,
                COALESCE(u.nombre_completo, u.username) AS miembro_nombre,
                u.username AS miembro_username
            FROM {T_RECLAMO_RESPUESTAS_EQUIPO} rre
            JOIN {T_USUARIOS} u
            ON u.id = rre.miembro_id
            WHERE rre.reclamo_id = ?
            AND rre.imputacion_id = ?
            AND rre.miembro_id = ?
            AND rre.activo = 1
            ORDER BY rre.id DESC
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_26 = f"""

            SELECT
                re.id,
                u.nombre_completo AS miembro_nombre,
                u.username AS miembro_username,
                re.causa,
                re.preventiva,
                re.correctiva,
                re.created_at
            FROM {T_RECLAMO_RESPUESTAS_EQUIPO} re
            JOIN {T_USUARIOS} u
            ON u.id = re.miembro_id
            WHERE re.imputacion_id = ?
            ORDER BY re.created_at DESC
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_27 = f"""

            SELECT TOP 1 reclamo_id
            FROM {T_RECLAMO_IMPUTADOS}
            WHERE id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_UPD_28 = f"""

                UPDATE {T_RECLAMO_RESPUESTAS_EQUIPO}
                SET
                    metodo_analisis = ?,
                    causa = ?,
                    preventiva = ?,
                    correctiva = ?,
                    fecha_causa = ?,
                    fecha_preventiva = ?,
                    fecha_correctiva = ?,
                    fish_metodo = ?,
                    fish_maquinas = ?,
                    fish_materiales = ?,
                    fish_personas = ?,
                    fish_entorno = ?,
                    fish_medicion = ?,
                    why1 = ?, why2 = ?, why3 = ?, why4 = ?, why5 = ?
                WHERE id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_INS_29 = f"""

                INSERT INTO {T_RECLAMO_RESPUESTAS_EQUIPO} (
                    reclamo_id, imputacion_id, miembro_id,
                    metodo_analisis,
                    causa, preventiva, correctiva,
                    fecha_causa, fecha_preventiva, fecha_correctiva,
                    fish_metodo, fish_maquinas, fish_materiales,
                    fish_personas, fish_entorno, fish_medicion,
                    why1, why2, why3, why4, why5,
                    activo, created_by
                )
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_30 = f"""

                    SELECT TOP 1 id
                    FROM {T_RECLAMO_RESPUESTAS_EQUIPO}
                    WHERE reclamo_id = ?
                    AND imputacion_id = ?
                    AND miembro_id = ?
                    ORDER BY id DESC
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_31 = f"""

            SELECT
                re.*,
                r.codigo,
                r.proceso_id,
                r.id AS reclamo_id,
                u_col.username AS colaborador_username
            FROM {T_RECLAMO_EQUIPO} re
            JOIN {T_RECLAMOS} r
            ON r.id = re.reclamo_id
            LEFT JOIN {T_USUARIOS} u_col
            ON u_col.id = re.colaborador_id
            WHERE re.id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_UPD_32 = f"""

                UPDATE {T_RECLAMO_EQUIPO}
                SET estado = 'aprobado',
                    fecha_aprobacion = ?,
                    motivo_rechazo = NULL,
                    fecha_rechazo = NULL
                WHERE id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_UPD_33 = f"""

                UPDATE {T_RECLAMO_EQUIPO}
                SET estado = 'rechazado',
                    fecha_rechazo = ?,
                    motivo_rechazo = ?,
                    fecha_aprobacion = NULL
                WHERE id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_UPD_34 = f"""

            UPDATE {T_RECLAMO_EQUIPO_RESPUESTAS}
            SET activo = 0
            WHERE id = ? AND reclamo_id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_35 = f"""

            SELECT TOP 1
                u.id,
                u.nombre_completo,
                u.username,
                d.nombre AS departamento_nombre,
                j.nombre_completo AS jefe_nombre
            FROM {T_USUARIOS} u
            LEFT JOIN {T_DEPARTAMENTOS} d ON d.id = u.departamento_id
            LEFT JOIN {T_USUARIOS} j ON j.id = u.jefe_id
            WHERE u.identificacion = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_36 = f"""

            SELECT TOP 1 ri.imputado_id, r.codigo
            FROM {T_RECLAMOS} r
            LEFT JOIN {T_RECLAMO_IMPUTADOS} ri ON ri.reclamo_id = r.id
            WHERE r.id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_37 = f"""

                SELECT 1
                FROM {T_RECLAMO_EQUIPO}
                WHERE reclamo_id = ? AND colaborador_id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_INS_38 = f"""

                INSERT INTO {T_RECLAMO_EQUIPO}(
                    reclamo_id, responsable_id, colaborador_id,
                    estado, fecha_asignacion
                ) VALUES (?,?,?,?,?)
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_39 = f"""

            SELECT
                r.id,
                r.codigo,
                r.fecha_creacion,
                r.cliente_nombre,
                r.proceso_text,
                r.material_desc,
                r.observacion,
                r.procede,
                r.estado_global
            FROM {T_RECLAMOS} r
            WHERE r.id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_40 = f"""

            SELECT
                u.username,
                ri.respuesta_causa,
                ri.respuesta_preventiva,
                ri.respuesta_correctiva
            FROM {T_RECLAMO_IMPUTADOS} ri
            JOIN {T_USUARIOS} u ON u.id = ri.imputado_id
            WHERE ri.reclamo_id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_41 = f"""

            SELECT
                u.id,
                COALESCE(u.nombre_completo, u.username) AS nombre,
                u.username,
                u.rol,
                d.nombre AS departamento
            FROM {T_USUARIOS} u
            LEFT JOIN {T_DEPARTAMENTOS} d ON d.id = u.departamento_id
            WHERE COALESCE(u.disabled,0)=0
            AND u.id NOT IN (
                SELECT usuario_id
                FROM {T_RECLAMO_EQUIPO_RESPUESTAS}
                WHERE reclamo_id = ? AND activo = 1
            )
            ORDER BY nombre
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_42 = f"""

            SELECT re.*, r.codigo,
                   u_resp.username AS responsable_username,
                   u_col.username  AS colaborador_username
            FROM {T_RECLAMO_EQUIPO} re
            JOIN {T_RECLAMOS} r       ON r.id = re.reclamo_id
            LEFT JOIN {T_USUARIOS} u_resp ON u_resp.id = re.responsable_id
            LEFT JOIN {T_USUARIOS} u_col  ON u_col.id  = re.colaborador_id
            WHERE re.id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_UPD_43 = f"""

            UPDATE {T_RECLAMO_EQUIPO}
            SET respuesta_causa      = ?,
                respuesta_preventiva = ?,
                respuesta_correctiva = ?,
                fecha_respuesta      = ?,
                estado               = 'respondido'
            WHERE id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_44 = f"""

        SELECT
            ri.id AS imputacion_id,
            COALESCE(u.nombre_completo, u.username) AS imputado_nombre,
            u.username AS imputado_username,

            CASE
                WHEN ri.estado_asignacion = 'pend_aprobacion' THEN 'Pendiente aceptación del responsable'
                WHEN ri.estado_asignacion = 'rechazado' THEN 'Imputación rechazada'
                WHEN ri.estado_asignacion = 'aprobado' AND ri.estado_respuesta = 'sin_respuesta' THEN 'Pendiente respuesta del imputado'
                WHEN ri.estado_asignacion = 'aprobado' AND ri.estado_respuesta = 'pendiente_jefe' THEN 'Respuesta pendiente de aprobación'
                WHEN ri.estado_asignacion = 'aprobado' AND ri.estado_respuesta = 'aprobada' THEN 'Cerrado'
                WHEN ri.estado_asignacion = 'aprobado' AND ri.estado_respuesta = 'rechazada' THEN 'Respuesta rechazada'
                ELSE COALESCE(ri.estado_asignacion,'') || '/' || COALESCE(ri.estado_respuesta,'')
            END AS estado_imputacion,

            COALESCE(ri.respuesta_causa, '')      AS causa,
            COALESCE(ri.respuesta_preventiva, '') AS preventiva,
            COALESCE(ri.respuesta_correctiva, '') AS correctiva,

            -- ✅ FECHAS (las que ya agregaste)
            COALESCE(ri.fecha_causa,'')           AS fecha_causa,
            COALESCE(ri.fecha_preventiva,'')      AS fecha_preventiva,
            COALESCE(ri.fecha_correctiva,'')      AS fecha_correctiva,

            -- ✅ PARA EL OJO (diagrama)
            COALESCE(ri.metodo_analisis,'')       AS metodo_analisis,
            COALESCE(ri.why1,'')                  AS why1,
            COALESCE(ri.why2,'')                  AS why2,
            COALESCE(ri.why3,'')                  AS why3,
            COALESCE(ri.why4,'')                  AS why4,
            COALESCE(ri.why5,'')                  AS why5,
            COALESCE(ri.fish_metodo,'')           AS fish_metodo,
            COALESCE(ri.fish_maquinas,'')         AS fish_maquinas,
            COALESCE(ri.fish_materiales,'')       AS fish_materiales,
            COALESCE(ri.fish_personas,'')         AS fish_personas,
            COALESCE(ri.fish_entorno,'')          AS fish_entorno,
            COALESCE(ri.fish_medicion,'')         AS fish_medicion

        FROM {T_RECLAMO_IMPUTADOS} ri
        LEFT JOIN {T_USUARIOS} u ON u.id = ri.imputado_id
        WHERE ri.reclamo_id = ?
        ORDER BY imputado_nombre, imputado_username
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_45 = f"""

            SELECT
                'imputado' AS origen,
                ri.id AS imputacion_id,
                NULL AS respuesta_equipo_id,
                NULL AS miembro_id,

                COALESCE(u.nombre_completo, u.username) AS nombre,
                u.username AS username,

                CASE
                    WHEN ri.estado_asignacion = 'pend_aprobacion'
                        THEN 'Pendiente aceptación del responsable'
                    WHEN ri.estado_asignacion = 'rechazado'
                        THEN 'Imputación rechazada'
                    WHEN ri.estado_asignacion = 'aprobado'
                        AND COALESCE(ri.estado_respuesta, '') = 'sin_respuesta'
                        THEN 'Pendiente respuesta del imputado'
                    WHEN ri.estado_asignacion = 'aprobado'
                        AND COALESCE(ri.estado_respuesta, '') = 'pendiente_jefe'
                        THEN 'Respuesta pendiente de aprobación'
                    WHEN ri.estado_asignacion = 'aprobado'
                        AND COALESCE(ri.estado_respuesta, '') = 'aprobada'
                        THEN 'Cerrado'
                    WHEN ri.estado_asignacion = 'aprobado'
                        AND COALESCE(ri.estado_respuesta, '') = 'rechazada'
                        THEN 'Respuesta rechazada'
                    ELSE COALESCE(ri.estado_asignacion, '') + '/' + COALESCE(ri.estado_respuesta, '')
                END AS estado,

                COALESCE(ri.metodo_analisis, '') AS metodo_analisis,
                COALESCE(ri.why1, '') AS why1,
                COALESCE(ri.why2, '') AS why2,
                COALESCE(ri.why3, '') AS why3,
                COALESCE(ri.why4, '') AS why4,
                COALESCE(ri.why5, '') AS why5,

                COALESCE(ri.fish_metodo, '') AS fish_metodo,
                COALESCE(ri.fish_maquinas, '') AS fish_maquinas,
                COALESCE(ri.fish_materiales, '') AS fish_materiales,
                COALESCE(ri.fish_personas, '') AS fish_personas,
                COALESCE(ri.fish_entorno, '') AS fish_entorno,
                COALESCE(ri.fish_medicion, '') AS fish_medicion,

                COALESCE(ri.respuesta_causa, '') AS respuesta_causa,
                COALESCE(ri.respuesta_preventiva, '') AS respuesta_preventiva,
                COALESCE(ri.respuesta_correctiva, '') AS respuesta_correctiva,

                COALESCE(ri.fecha_causa, '') AS fecha_causa,
                COALESCE(ri.fecha_preventiva, '') AS fecha_preventiva,
                COALESCE(ri.fecha_correctiva, '') AS fecha_correctiva,

                COALESCE(ri.estado_asignacion, '') AS estado_asignacion_raw,
                COALESCE(ri.estado_respuesta, '') AS estado_respuesta_raw

            FROM {T_RECLAMO_IMPUTADOS} ri
            LEFT JOIN {T_USUARIOS} u ON u.id = ri.imputado_id
            WHERE ri.reclamo_id = ?
            ORDER BY COALESCE(u.nombre_completo, u.username), ri.id
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_46 = f"""

            SELECT
                'equipo' AS origen,
                rre.imputacion_id,
                rre.id AS respuesta_equipo_id,
                rre.miembro_id,

                COALESCE(u.nombre_completo, u.username) AS nombre,
                u.username AS username,
                'Aporte de equipo' AS estado,

                COALESCE(rre.metodo_analisis, '') AS metodo_analisis,
                COALESCE(rre.why1, '') AS why1,
                COALESCE(rre.why2, '') AS why2,
                COALESCE(rre.why3, '') AS why3,
                COALESCE(rre.why4, '') AS why4,
                COALESCE(rre.why5, '') AS why5,

                COALESCE(rre.fish_metodo, '') AS fish_metodo,
                COALESCE(rre.fish_maquinas, '') AS fish_maquinas,
                COALESCE(rre.fish_materiales, '') AS fish_materiales,
                COALESCE(rre.fish_personas, '') AS fish_personas,
                COALESCE(rre.fish_entorno, '') AS fish_entorno,
                COALESCE(rre.fish_medicion, '') AS fish_medicion,

                COALESCE(rre.causa, '') AS causa,
                COALESCE(rre.preventiva, '') AS preventiva,
                COALESCE(rre.correctiva, '') AS correctiva,

                COALESCE(rre.fecha_causa, '') AS fecha_causa,
                COALESCE(rre.fecha_preventiva, '') AS fecha_preventiva,
                COALESCE(rre.fecha_correctiva, '') AS fecha_correctiva

            FROM {T_RECLAMO_RESPUESTAS_EQUIPO} rre
            LEFT JOIN {T_USUARIOS} u ON u.id = rre.miembro_id
            WHERE rre.reclamo_id = ?
            AND COALESCE(rre.activo, 1) = 1
            ORDER BY COALESCE(u.nombre_completo, u.username), rre.id
"""

SQL_REGISTER_RECLAMOS_ROUTES_UPD_47 = f"""

            UPDATE {T_RECLAMO_RESPUESTA_EQUIPO_ACCIONES}
            SET
                cumplido = ?,
                fecha_cumplimiento = ?,
                updated_at = CURRENT_TIMESTAMP,
                updated_by = ?
            WHERE id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_48 = f"""

            SELECT TOP 1
                e.id,
                e.accion_id,
                e.filename,
                e.original_name,
                COALESCE(e.content_type, '') AS content_type,
                COALESCE(e.activo, 1) AS activo
            FROM {T_RECLAMO_RESPUESTA_EQUIPO_ACCION_EVIDENCIAS} e
            WHERE e.id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_49 = f"""

            SELECT TOP 1
                e.id,
                e.accion_id,
                e.filename,
                e.original_name,
                COALESCE(e.content_type, '') AS content_type,
                rea.respuesta_equipo_id,
                rre.reclamo_id,
                rre.imputacion_id,
                rre.miembro_id
            FROM {T_RECLAMO_RESPUESTA_EQUIPO_ACCION_EVIDENCIAS} e
            INNER JOIN {T_RECLAMO_RESPUESTA_EQUIPO_ACCIONES} rea
                ON rea.id = e.accion_id
            INNER JOIN {T_RECLAMO_RESPUESTAS_EQUIPO} rre
                ON rre.id = rea.respuesta_equipo_id
            WHERE e.id = ?
            AND COALESCE(e.activo, 1) = 1
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_50 = f"""

            SELECT TOP 1 1 AS ok
            FROM {T_RECLAMO_IMPUTADOS}
            WHERE id = ?
            AND reclamo_id = ?
            AND imputado_id = ?
            AND estado_asignacion = 'aprobado'
"""

SQL_REGISTER_RECLAMOS_ROUTES_INS_51 = f"""

            INSERT INTO {T_RECLAMO_RESPUESTA_EQUIPO_ACCION_EVIDENCIAS} (
                accion_id,
                filename,
                original_name,
                content_type,
                size_bytes,
                creado_por,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_52 = f"""

            SELECT
                a.id,
                a.tipo,
                a.descripcion,
                a.fecha_compromiso,
                a.cumplido,
                a.fecha_cumplimiento,
                a.requiere_evidencia,

                COUNT(e.id) AS evidencias
            FROM {T_RECLAMO_RESPUESTA_EQUIPO_ACCIONES} a
            LEFT JOIN {T_RECLAMO_RESPUESTA_EQUIPO_ACCION_EVIDENCIAS} e
                ON e.accion_id = a.id
                AND e.activo = 1
            WHERE a.respuesta_equipo_id = ?
            AND a.activo = 1
            GROUP BY a.id
            ORDER BY a.orden
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_53 = f"""

                SELECT p.nombre
                FROM {T_USUARIOS} u
                LEFT JOIN {T_PUESTOS} p ON p.id = u.puesto_id
                WHERE u.id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_54 = f"""

                SELECT 1
                FROM {T_PARAM_VALUES} pv
                JOIN {T_PARAM_GROUPS} pg ON pg.id = pv.group_id
                WHERE pg.nombre = 'RECL_MATERIAL'
                  AND pv.nombre = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_55 = f"""

            SELECT COALESCE(MAX(pv.orden), 0) + 1 AS next_ord
            FROM {T_PARAM_VALUES} pv
            JOIN {T_PARAM_GROUPS} pg ON pg.id = pv.group_id
            WHERE pg.nombre = 'RECL_MATERIAL'
"""

SQL_REGISTER_RECLAMOS_ROUTES_INS_56 = f"""

            INSERT INTO {T_PARAM_VALUES} (group_id, nombre, valor, activo, orden)
            VALUES (?, ?, ?, 1, ?)
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_57 = f"""

                SELECT TOP 1 valor
                FROM {T_PARAM_VALUES}
                WHERE id = ?
                AND COALESCE(activo, 1) = 1
"""

SQL_REGISTER_RECLAMOS_ROUTES_INS_58 = f"""

            INSERT INTO {T_RECLAMOS}(
                codigo, fecha_reclamo, fecha_creacion,
                cliente_id, cliente_nombre, cliente_identificacion,
                cliente_direccion, cliente_contacto, cliente_email, cliente_telefono,
                region_id, provincia_id, canton_id,
                tipo_tramite, tipo_reclamo,
                proceso_id, proceso_text, antecedente,
                fecha_pedido, factura, guia_remision,
                material_id, material_desc,
                persona_atendio, persona_atendio_cedula,
                fecha_ofrec_entrega, fecha_entrega,
                observacion,
                procede,
                requiere_carta_cliente,
                carta_cliente_notif_at,
                creado_por,
                estado_global
            )
            OUTPUT INSERTED.id
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
"""

SQL_REGISTER_RECLAMOS_ROUTES_INS_59 = f"""

                INSERT INTO {T_RECLAMO_IMPUTADOS}(
                    reclamo_id,
                    imputado_id,
                    aprobador_id,
                    estado_asignacion,
                    estado_respuesta
                )
                VALUES(?,?,?,?,?)
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_60 = f"""

            
            SELECT ri.*, r.codigo, r.creado_por, r.proceso_id,
                   u_imp.username AS imputado_username,
                   u_imp.id AS imputado_uid
            FROM {T_RECLAMO_IMPUTADOS} ri
            JOIN {T_RECLAMOS} r ON r.id = ri.reclamo_id
            LEFT JOIN {T_USUARIOS} u_imp ON u_imp.id = ri.imputado_id
            WHERE ri.id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_UPD_61 = f"""

                UPDATE {T_RECLAMO_IMPUTADOS}
                SET estado_asignacion='aprobado',
                    fecha_aprobacion_asignacion=?,
                    motivo_rechazo_asignacion=NULL,
                    fecha_rechazo_asignacion=NULL
                WHERE id=?
"""

SQL_REGISTER_RECLAMOS_ROUTES_UPD_62 = f"""

                UPDATE {T_RECLAMO_IMPUTADOS}
                SET estado_asignacion='rechazado',
                    fecha_rechazo_asignacion=?,
                    motivo_rechazo_asignacion=?
                WHERE id=?
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_63 = f"""

            SELECT a.id,
                a.reclamo_id,
                a.filename,
                a.original_name,
                r.codigo,
                r.creado_por
            FROM {T_RECLAMO_ADJUNTOS} a
            JOIN {T_RECLAMOS} r ON r.id = a.reclamo_id
            WHERE a.id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_64 = f"""

            SELECT
                a.id,
                a.original_name,
                a.content_type,
                a.size_bytes,
                a.created_at,
                a.creado_por,
                COALESCE(u.nombre_completo, u.username) AS cargado_por
            FROM {T_RECLAMO_ADJUNTOS} a
            LEFT JOIN {T_USUARIOS} u
                ON u.id = a.creado_por
            WHERE a.reclamo_id = ?
            ORDER BY a.id
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_65 = f"""

            SELECT
                id, reclamo_id, filename, original_name,
                content_type
            FROM {T_RECLAMO_ADJUNTOS}
            WHERE id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_66 = f"""

            SELECT
                ri.*,
                r.id          AS reclamo_id,
                r.codigo      AS codigo,
                r.creado_por  AS creado_por,
                r.proceso_id  AS proceso_id,

                u_apr.username AS aprobador_username,
                u_apr.id       AS aprobador_uid,

                u_imp.username AS imputado_username,

                u_cre.email    AS creador_email,
                u_cre.username AS creador_username,
                u_cre.nombre_completo AS creador_nombre

            FROM {T_RECLAMO_IMPUTADOS} ri
            JOIN {T_RECLAMOS} r          ON r.id = ri.reclamo_id
            LEFT JOIN {T_USUARIOS} u_imp ON u_imp.id = ri.imputado_id
            LEFT JOIN {T_USUARIOS} u_apr ON u_apr.id = ri.aprobador_id
            LEFT JOIN {T_USUARIOS} u_cre ON u_cre.id = r.creado_por
            WHERE ri.id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_UPD_67 = f"""

            UPDATE {T_RECLAMO_IMPUTADOS}
            SET metodo_analisis            = ?,
                respuesta_causa            = ?,
                fecha_causa                = ?,
                respuesta_preventiva       = ?,
                fecha_preventiva           = ?,
                respuesta_correctiva       = ?,
                fecha_correctiva           = ?,
                why1                       = ?,
                why2                       = ?,
                why3                       = ?,
                why4                       = ?,
                why5                       = ?,
                fish_metodo                = ?,
                fish_maquinas              = ?,
                fish_materiales            = ?,
                fish_personas              = ?,
                fish_entorno               = ?,
                fish_medicion              = ?,
                fecha_respuesta_imputado   = ?,
                estado_respuesta           = 'aprobada',
                fecha_aprobacion_respuesta = ?,
                motivo_rechazo_respuesta   = NULL,
                fecha_rechazo_respuesta    = NULL,
                visible_creador            = 1
            WHERE id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_UPD_68 = f"""

            UPDATE {T_RECLAMO_IMPUTADO_ACCIONES}
            SET activo = 0,
                updated_at = ?,
                updated_by = ?
            WHERE imputacion_id = ?
            AND reclamo_id = ?
            AND COALESCE(activo,1) = 1
"""

SQL_REGISTER_RECLAMOS_ROUTES_INS_69 = f"""

                    INSERT INTO {T_RECLAMO_IMPUTADO_ACCIONES} (
                        imputacion_id,
                        reclamo_id,
                        tipo,
                        descripcion,
                        fecha_compromiso,
                        orden,
                        requiere_evidencia,
                        cumplido,
                        fecha_cumplimiento,
                        created_at,
                        created_by,
                        updated_at,
                        updated_by,
                        activo,
                        observacion_cumplimiento
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, 0, NULL, ?, ?, ?, ?, 1, '')
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_70 = f"""

            SELECT COUNT(*) AS pend
            FROM {T_RECLAMO_IMPUTADOS}
            WHERE reclamo_id = ?
            AND estado_asignacion = 'aprobado'
            AND COALESCE(TRIM(estado_respuesta),'') <> 'aprobada'
"""

SQL_REGISTER_RECLAMOS_ROUTES_UPD_71 = f"""

                UPDATE {T_RECLAMOS}
                SET estado_global = 'cerrado'
                WHERE id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_72 = f"""

            SELECT id, codigo, COALESCE(LOWER(TRIM(estado_global)), '') AS estado_global
            FROM {T_RECLAMOS}
            WHERE id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_DEL_73 = f"""

                DELETE FROM {T_RECLAMO_EQUIPO_ACCIONES}
                WHERE equipo_id IN (
                    SELECT id FROM {T_RECLAMO_EQUIPO_RESPUESTAS} WHERE reclamo_id = ?
                )
"""

SQL_REGISTER_RECLAMOS_ROUTES_UPD_74 = f"""

                UPDATE {T_RECLAMO_IMPUTADOS}
                SET estado_respuesta='aprobada',
                    fecha_aprobacion_respuesta=?,
                    motivo_rechazo_respuesta=NULL,
                    fecha_rechazo_respuesta=NULL,
                    visible_creador=1
                WHERE id=?
"""

SQL_REGISTER_RECLAMOS_ROUTES_UPD_75 = f"""

                UPDATE {T_RECLAMO_IMPUTADOS}
                SET estado_respuesta='rechazada',
                    fecha_rechazo_respuesta=?,
                    motivo_rechazo_respuesta=?,
                    fecha_aprobacion_respuesta=NULL
                WHERE id=?
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_76 = f"""

            SELECT
                COUNT(*) AS total_om,
                SUM(CASE WHEN estado_global LIKE 'CERR%' THEN 1 ELSE 0 END) AS cerradas,
                SUM(CASE WHEN estado_global LIKE 'RECHA%' THEN 1 ELSE 0 END) AS rechazadas,
                SUM(CASE WHEN estado_global LIKE 'PEND%' THEN 1 ELSE 0 END) AS pendientes,
                SUM(CASE WHEN estado_global LIKE 'EN RESP%' THEN 1 ELSE 0 END) AS en_respuesta
            FROM {T_RECLAMOS}
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_77 = f"""

            SELECT
                strftime('%Y-%m', fecha_reclamo) AS ym,
                COUNT(*) AS total_mes
            FROM {T_RECLAMOS}
            WHERE fecha_reclamo >= date('now', '-6 months')
            GROUP BY ym
            ORDER BY ym
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_78 = f"""

            SELECT
                estado_global AS estado,
                COUNT(*) AS total
            FROM {T_RECLAMOS}
            GROUP BY estado_global
            ORDER BY total DESC
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_79 = f"""

                SELECT
                    COALESCE(tipo_reclamo, 'SIN TIPO') AS tipo_reclamo,
                    AVG(
                        CAST(
                            DATEDIFF(
                                DAY,
                                TRY_CONVERT(datetime, fecha_reclamo),
                                COALESCE(TRY_CONVERT(datetime, fecha_cierre), GETDATE())
                            ) AS FLOAT
                        )
                    ) AS dias_promedio,
                    COUNT(*) AS total
                FROM {T_RECLAMOS}
                WHERE TRY_CONVERT(datetime, fecha_reclamo) IS NOT NULL
                GROUP BY COALESCE(tipo_reclamo, 'SIN TIPO')
                HAVING COUNT(*) >= 3
                ORDER BY dias_promedio DESC
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_80 = f"""

                SELECT
                    tipo_reclamo,
                    AVG(
                        JULIANDAY(COALESCE(fecha_cierre, DATE('now')))
                        - JULIANDAY(fecha_reclamo)
                    ) AS dias_promedio,
                    COUNT(*) AS total
                FROM {T_RECLAMOS}
                WHERE fecha_reclamo IS NOT NULL
                GROUP BY tipo_reclamo
                HAVING total >= 3
                ORDER BY dias_promedio DESC
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_81 = f"""

                SELECT TOP 10
                    COALESCE(u.nombre_completo, u.username, 'SIN USUARIO') AS imputado,
                    COUNT(*) AS total_om,
                    SUM(CASE WHEN ri.estado_imputacion LIKE 'CERR%' THEN 1 ELSE 0 END) AS cerradas,
                    SUM(CASE WHEN ri.estado_imputacion LIKE 'APROB%' THEN 1 ELSE 0 END) AS aprobadas,
                    SUM(CASE WHEN ri.estado_imputacion LIKE 'RECHA%' THEN 1 ELSE 0 END) AS rechazadas
                FROM {T_RECLAMO_IMPUTADOS} ri
                JOIN {T_USUARIOS} u ON u.id = ri.imputado_id
                GROUP BY u.id, COALESCE(u.nombre_completo, u.username, 'SIN USUARIO')
                ORDER BY COUNT(*) DESC
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_82 = f"""

                SELECT top 10
                    u.nombre_completo AS imputado,
                    COUNT(*) AS total_om,
                    SUM(CASE WHEN ri.estado_imputacion LIKE 'CERR%' THEN 1 ELSE 0 END) AS cerradas,
                    SUM(CASE WHEN ri.estado_imputacion LIKE 'APROB%' THEN 1 ELSE 0 END) AS aprobadas,
                    SUM(CASE WHEN ri.estado_imputacion LIKE 'RECHA%' THEN 1 ELSE 0 END) AS rechazadas
                FROM {T_RECLAMO_IMPUTADOS} ri
                JOIN {T_USUARIOS} u ON u.id = ri.imputado_id
                GROUP BY u.id, u.nombre_completo
                ORDER BY total_om DESC
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_83 = f"""

                SELECT TOP 10
                    COALESCE(cliente_nombre, 'SIN CLIENTE') AS cliente,
                    COUNT(*) AS total_om
                FROM {T_RECLAMOS}
                GROUP BY COALESCE(cliente_nombre, 'SIN CLIENTE')
                ORDER BY COUNT(*) DESC
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_84 = f"""

                SELECT TOP 10
                    cliente_nombre AS cliente,
                    COUNT(*) AS total_om
                FROM {T_RECLAMOS}
                GROUP BY cliente_nombre
                ORDER BY total_om DESC
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_85 = f"""

            SELECT
                COALESCE(proceso_text, 'SIN PROCESO') AS proceso,
                COUNT(*) AS total_om
            FROM {T_RECLAMOS}
            GROUP BY COALESCE(proceso_text, 'SIN PROCESO')
            ORDER BY COUNT(*) DESC
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_86 = f"""

            SELECT
                COALESCE(d.nombre, 'SIN DEPARTAMENTO') AS departamento,
                COUNT(DISTINCT r.id) AS total_om,
                SUM(CASE WHEN r.estado_global LIKE 'CERR%' THEN 1 ELSE 0 END) AS cerradas,
                SUM(CASE WHEN r.estado_global LIKE 'CERR%' THEN 0 ELSE 1 END) AS abiertas
            FROM {T_RECLAMOS} r
            LEFT JOIN {T_USUARIOS} u   ON u.id = r.creado_por
            LEFT JOIN {T_DEPARTAMENTOS} d ON d.id = u.departamento_id
            GROUP BY d.nombre
            ORDER BY total_om DESC
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_87 = f"""

            SELECT DISTINCT COALESCE(d.nombre, 'SIN DEPARTAMENTO') AS depto
            FROM {T_RECLAMOS} r
            LEFT JOIN {T_USUARIOS} u ON u.id = r.creado_por
            LEFT JOIN {T_DEPARTAMENTOS} d ON d.id = u.departamento_id
            ORDER BY depto
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_88 = f"""

            SELECT COALESCE(NULLIF(LTRIM(RTRIM(r.proceso_text)), ''), 'SIN PROCESO') AS proceso_text
            FROM {T_RECLAMOS} r
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_89 = f"""

            SELECT TOP 1
                r.id AS reclamo_id,
                r.codigo,
                r.proceso_id,
                ri.id AS imputacion_id,
                ri.imputado_id,
                ri.estado_asignacion
            FROM {T_RECLAMOS} r
            JOIN {T_RECLAMO_IMPUTADOS} ri
            ON ri.reclamo_id = r.id
            WHERE r.id = ?
            AND ri.id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_90 = f"""

            SELECT TOP 1 1 AS ok
            FROM {T_RECLAMO_EQUIPO_RESPUESTAS}
            WHERE reclamo_id = ?
            AND imputacion_id = ?
            AND usuario_id = ?
            AND COALESCE(activo, 1) = 1
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_91 = f"""

            SELECT TOP 1 id
            FROM {T_RECLAMO_RESPUESTAS_EQUIPO}
            WHERE reclamo_id = ?
            AND imputacion_id = ?
            AND miembro_id = ?
            AND COALESCE(activo, 1) = 1
            ORDER BY id DESC
"""

SQL_REGISTER_RECLAMOS_ROUTES_UPD_92 = f"""

                UPDATE {T_RECLAMO_RESPUESTAS_EQUIPO}
                SET estado_revision = 'APROBADA',
                    revision_by = ?,
                    revision_at = ?
                WHERE reclamo_id = ?
                AND imputacion_id = ?
                AND miembro_id = ?
                AND COALESCE(activo, 1) = 1
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_93 = f"""

            SELECT TOP 1
                r.id AS reclamo_id,
                r.codigo,
                r.proceso_id,
                ri.id AS imputacion_id,
                ri.imputado_id,
                ri.estado_asignacion,
                COALESCE(u_imp.nombre_completo, u_imp.username) AS sponsor_nombre,
                COALESCE(u_miembro.nombre_completo, u_miembro.username) AS miembro_nombre
            FROM {T_RECLAMOS} r
            JOIN {T_RECLAMO_IMPUTADOS} ri
            ON ri.reclamo_id = r.id
            LEFT JOIN {T_USUARIOS} u_imp
            ON u_imp.id = ri.imputado_id
            LEFT JOIN {T_USUARIOS} u_miembro
            ON u_miembro.id = ?
            WHERE r.id = ?
            AND ri.id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_UPD_94 = f"""

                UPDATE {T_RECLAMO_RESPUESTAS_EQUIPO}
                SET estado_revision = 'RECHAZADA',
                    motivo_rechazo = ?,
                    revision_by = ?,
                    revision_at = ?
                WHERE reclamo_id = ?
                AND imputacion_id = ?
                AND miembro_id = ?
                AND COALESCE(activo, 1) = 1
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_95 = f"""

            SELECT TOP 1
                id,
                COALESCE(cumplido, 0) AS cumplido
            FROM {T_RECLAMO_RESPUESTA_EQUIPO_ACCIONES}
            WHERE id = ?
            AND COALESCE(activo, 1) = 1
"""

SQL_REGISTER_RECLAMOS_ROUTES_UPD_96 = f"""

            UPDATE {T_RECLAMO_RESPUESTA_EQUIPO_ACCIONES}
            SET
                observacion_cumplimiento = ?,
                updated_at = CURRENT_TIMESTAMP,
                updated_by = ?
            WHERE id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_97 = f"""

            SELECT TOP 1
                e.id,
                e.accion_id,
                e.filename,
                COALESCE(e.activo, 1) AS evidencia_activa,
                COALESCE(a.cumplido, 0) AS accion_cumplida
            FROM {T_RECLAMO_RESPUESTA_EQUIPO_ACCION_EVIDENCIAS} e
            JOIN {T_RECLAMO_RESPUESTA_EQUIPO_ACCIONES} a
            ON a.id = e.accion_id
            WHERE e.id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_UPD_98 = f"""

            UPDATE {T_RECLAMO_RESPUESTA_EQUIPO_ACCION_EVIDENCIAS}
            SET activo = 0
            WHERE id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_99 = f"""

            SELECT TOP 1
                ri.id,
                ri.reclamo_id,
                ri.imputado_id,
                ri.metodo_analisis,
                ri.why1, ri.why2, ri.why3, ri.why4, ri.why5,
                ri.fish_metodo, ri.fish_maquinas, ri.fish_materiales,
                ri.fish_personas, ri.fish_entorno, ri.fish_medicion
            FROM {T_RECLAMO_IMPUTADOS} ri
            WHERE ri.id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_UPD_100 = f"""

            UPDATE {T_RECLAMO_IMPUTADO_ACCIONES}
            SET
                observacion_cumplimiento = ?,
                updated_at = CURRENT_TIMESTAMP,
                updated_by = ?
            WHERE id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_UPD_101 = f"""

            UPDATE {T_RECLAMO_IMPUTADO_ACCIONES}
            SET
                cumplido = 1,
                fecha_cumplimiento = ?,
                updated_at = CURRENT_TIMESTAMP,
                updated_by = ?
            WHERE id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_INS_102 = f"""

            INSERT INTO {T_RECLAMO_ACCION_EVIDENCIAS} (
                accion_id,
                filename,
                original_name,
                content_type,
                size_bytes,
                creado_por,
                created_at,
                activo
            )
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 1)
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_103 = f"""

            SELECT
                e.id,
                e.accion_id,
                e.filename,
                COALESCE(e.activo, 1) AS evidencia_activa,
                COALESCE(a.cumplido, 0) AS accion_cumplida,
                a.imputacion_id,
                a.reclamo_id
            FROM {T_RECLAMO_ACCION_EVIDENCIAS} e
            JOIN {T_RECLAMO_IMPUTADO_ACCIONES} a
            ON a.id = e.accion_id
            WHERE e.id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_UPD_104 = f"""

            UPDATE {T_RECLAMO_ACCION_EVIDENCIAS}
            SET
                activo = 0,
                created_at = created_at
            WHERE id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_105 = f"""

            SELECT
                e.id,
                e.accion_id,
                e.filename,
                e.original_name,
                e.content_type,
                e.size_bytes,
                COALESCE(e.activo, 1) AS evidencia_activa
            FROM {T_RECLAMO_ACCION_EVIDENCIAS} e
            WHERE e.id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_106 = f"""

            SELECT TOP 1
                u.id,
                COALESCE(u.nombre_completo, u.username) AS nombre,
                u.username,
                COALESCE(d.nombre, '') AS departamento,
                COALESCE(j.nombre_completo, j.username, '') AS jefe
            FROM {T_PARAM_VALUES} pv
            JOIN {T_PARAM_GROUPS} pg ON pg.id = pv.group_id
            JOIN {T_USUARIOS} u
            ON LTRIM(RTRIM(u.identificacion)) = LTRIM(RTRIM(pv.nombre))
            LEFT JOIN {T_DEPARTAMENTOS} d ON d.id = u.departamento_id
            LEFT JOIN {T_USUARIOS} j ON j.id = u.jefe_id
            WHERE pg.nombre = 'RECL_PROCESO_SPONSOR'
            AND COALESCE(pv.activo, 1) = 1
            AND pv.parent_id = ?
            AND UPPER(LTRIM(RTRIM(COALESCE(pv.valor, '')))) = 'PRINCIPAL'
            AND COALESCE(u.disabled, 0) = 0
            ORDER BY COALESCE(pv.orden, 0), pv.id
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_107 = f"""

            SELECT
                u.id,
                COALESCE(u.nombre_completo, u.username) AS nombre,
                u.username,
                pv.valor AS tipo
            FROM {T_PARAM_VALUES} pv
            JOIN {T_PARAM_GROUPS} pg ON pg.id = pv.group_id
            JOIN {T_USUARIOS} u
            ON LTRIM(RTRIM(u.identificacion)) = LTRIM(RTRIM(pv.nombre))
            WHERE pg.nombre = 'RECL_PROCESO_SPONSOR'
            AND COALESCE(pv.activo, 1) = 1
            AND pv.parent_id = ?
            AND UPPER(LTRIM(RTRIM(COALESCE(pv.valor, '')))) IN ('PRINCIPAL', 'BACKUP')
            AND COALESCE(u.disabled, 0) = 0
            ORDER BY
            CASE UPPER(LTRIM(RTRIM(COALESCE(pv.valor, ''))))
                WHEN 'PRINCIPAL' THEN 1
                WHEN 'BACKUP' THEN 2
                ELSE 9
            END,
            COALESCE(pv.orden, 0),
            pv.id
"""

SQL_REGISTER_RECLAMOS_ROUTES_SEL_108 = f"""

            SELECT TOP 1
                id,
                codigo,
                COALESCE(requiere_carta_cliente, 0) AS requiere_carta_cliente,
                COALESCE(LOWER(LTRIM(RTRIM(estado_global))), '') AS estado_global,
                carta_cliente_notif_at
            FROM {T_RECLAMOS}
            WHERE id = ?
"""

SQL_REGISTER_RECLAMOS_ROUTES_UPD_109 = f"""

            UPDATE {T_RECLAMOS}
            SET carta_cliente_notif_at = GETDATE()
            WHERE id = ?
"""


# -- validacion_creador --
SQL_VALIDAR_CREADOR_SEL_BASE = f"""
    SELECT TOP 1
        r.id,
        r.codigo,
        r.creado_por,
        r.proceso_id,
        r.estado_global,
        r.validacion_creador,
        COALESCE(r.proceso_text, '') AS proceso_text
    FROM {T_RECLAMOS} r
    WHERE r.id = ?
"""

SQL_VALIDAR_CREADOR_SEL_IMPUTADOS = f"""
    SELECT
        ri.id        AS imputacion_id,
        ri.imputado_id,
        u.email      AS imputado_email,
        COALESCE(u.nombre_completo, u.username) AS imputado_nombre
    FROM {T_RECLAMO_IMPUTADOS} ri
    JOIN {T_USUARIOS} u ON u.id = ri.imputado_id
    WHERE ri.reclamo_id = ?
      AND COALESCE(u.disabled, 0) = 0
"""

SQL_VALIDAR_CREADOR_SEL_EQUIPO = f"""
    SELECT
        er.usuario_id,
        u.email      AS miembro_email,
        COALESCE(u.nombre_completo, u.username) AS miembro_nombre
    FROM {T_RECLAMO_EQUIPO_RESPUESTAS} er
    JOIN {T_USUARIOS} u ON u.id = er.usuario_id
    WHERE er.reclamo_id = ?
      AND COALESCE(er.activo, 1) = 1
      AND COALESCE(u.disabled, 0) = 0
      AND u.email IS NOT NULL
      AND LTRIM(RTRIM(u.email)) <> ''
"""

SQL_VALIDAR_CREADOR_SEL_SAC = f"""
    SELECT DISTINCT
        u.id AS usuario_id,
        u.email,
        COALESCE(u.nombre_completo, u.username) AS nombre
    FROM {T_USUARIOS} u
    LEFT JOIN {T_DEPARTAMENTOS} d ON d.id = u.departamento_id
    LEFT JOIN {T_PUESTOS} p       ON p.id = u.puesto_id
    WHERE COALESCE(u.disabled, 0) = 0
      AND u.email IS NOT NULL
      AND LTRIM(RTRIM(u.email)) <> ''
      AND (
            UPPER(LTRIM(RTRIM(COALESCE(d.nombre, '')))) = 'SERVICIO AL CLIENTE'
         OR UPPER(LTRIM(RTRIM(COALESCE(p.nombre, '')))) LIKE '%SERVICIO AL CLIENTE%'
      )
"""

SQL_VALIDAR_CREADOR_UPD_ESTADO = f"""
    UPDATE {T_RECLAMOS}
    SET validacion_creador = ?,
        estado_global      = ?
    WHERE id = ?
"""

SQL_VALIDAR_CREADOR_UPD_IMPUTACION = f"""
    UPDATE {T_RECLAMO_IMPUTADOS}
    SET estado_respuesta = 'sin_respuesta'
    WHERE reclamo_id = ?
      AND estado_asignacion = 'aprobado'
"""

SQL_VALIDAR_CREADOR_SEL_SPONSORS = f"""
    SELECT
        u.id          AS sponsor_id,
        COALESCE(u.nombre_completo, u.username) AS sponsor_nombre,
        u.email       AS sponsor_email,
        UPPER(LTRIM(RTRIM(COALESCE(pv.valor, '')))) AS tipo_sponsor
    FROM {T_PARAM_VALUES} pv
    JOIN {T_PARAM_GROUPS} pg  ON pg.id = pv.group_id
    JOIN {T_USUARIOS} u
      ON LTRIM(RTRIM(u.identificacion)) = LTRIM(RTRIM(pv.nombre))
    WHERE pg.nombre = 'RECL_PROCESO_SPONSOR'
      AND COALESCE(pv.activo, 1) = 1
      AND pv.parent_id = ?
      AND UPPER(LTRIM(RTRIM(COALESCE(pv.valor, '')))) IN ('PRINCIPAL', 'BACKUP')
      AND COALESCE(u.disabled, 0) = 0
      AND u.email IS NOT NULL
      AND LTRIM(RTRIM(u.email)) <> ''
"""


# -- RECLAMOS_ACCIONES_PENDIENTES_EVIDENCIA --
SQL__RECLAMOS_ACCIONES_PENDIENTES_EVIDENCIA_SEL_1 = f"""
                    SELECT
                        a.id,
                        a.tipo,
                        a.descripcion,
                        a.fecha_compromiso,
                        CASE
                            WHEN a.fecha_compromiso < CAST(GETDATE() AS DATE) THEN 'vencida'
                            ELSE 'proxima'
                        END AS estado_fecha,
                        NULL AS miembro_nombre
                    FROM {T_RECLAMO_IMPUTADO_ACCIONES} a
                    WHERE a.imputacion_id = ?
                      AND COALESCE(a.activo, 1) = 1
                      AND a.tipo = 'CORRECTIVA'
                      AND COALESCE(a.cumplido, 0) = 0
                      AND a.fecha_compromiso IS NOT NULL
                      AND a.fecha_compromiso <= DATEADD(DAY, 5, CAST(GETDATE() AS DATE))
                      AND NOT EXISTS (
                          SELECT 1 FROM {T_RECLAMO_ACCION_EVIDENCIAS} e
                          WHERE e.accion_id = a.id AND COALESCE(e.activo, 1) = 1
                      )
                    ORDER BY a.fecha_compromiso ASC
                """

SQL__RECLAMOS_ACCIONES_PENDIENTES_EVIDENCIA_SEL_2 = f"""
                    SELECT
                        a.id,
                        a.tipo,
                        a.descripcion,
                        a.fecha_compromiso,
                        CASE
                            WHEN a.fecha_compromiso < CAST(GETDATE() AS DATE) THEN 'vencida'
                            ELSE 'proxima'
                        END AS estado_fecha,
                        u_m.nombre_completo AS miembro_nombre
                    FROM {T_RECLAMO_RESPUESTA_EQUIPO_ACCIONES} a
                    LEFT JOIN {T_RECLAMO_RESPUESTAS_EQUIPO} re ON re.id = a.respuesta_equipo_id
                    LEFT JOIN {T_USUARIOS} u_m ON u_m.id = re.miembro_id
                    WHERE a.reclamo_id = ?
                      AND COALESCE(a.activo, 1) = 1
                      AND a.tipo = 'CORRECTIVA'
                      AND COALESCE(a.cumplido, 0) = 0
                      AND a.fecha_compromiso IS NOT NULL
                      AND a.fecha_compromiso <= DATEADD(DAY, 5, CAST(GETDATE() AS DATE))
                      AND NOT EXISTS (
                          SELECT 1 FROM {T_RECLAMO_RESPUESTA_EQUIPO_ACCION_EVIDENCIAS} e
                          WHERE e.accion_id = a.id AND COALESCE(e.activo, 1) = 1
                      )
                      AND NOT EXISTS (
                          SELECT 1 FROM {T_RECLAMO_ACCION_EVIDENCIAS} e2
                          WHERE e2.accion_id = a.id AND COALESCE(e2.activo, 1) = 1
                      )
                    ORDER BY a.fecha_compromiso ASC
                """


# -- RECLAMOS_EDITAR_PROCESO --
SQL__RECLAMOS_EDITAR_PROCESO_SEL_1 = f"SELECT valor FROM {T_PARAM_VALUES} WHERE id = ?"

SQL__RECLAMOS_EDITAR_PROCESO_SEL_2 = f"SELECT id, codigo FROM {T_RECLAMOS} WHERE id = ?"

SQL__RECLAMOS_EDITAR_PROCESO_UPD_3 = f"UPDATE {T_RECLAMOS} SET proceso_id = ?, proceso_text = ? WHERE id = ?"

SQL__RECLAMOS_EDITAR_PROCESO_SEL_4 = f"""SELECT u.id AS usuario_id
                       FROM {T_PARAM_VALUES} pv
                       JOIN {T_PARAM_GROUPS} pg ON pg.id = pv.group_id
                       JOIN {T_USUARIOS} u ON LTRIM(RTRIM(u.identificacion)) = LTRIM(RTRIM(pv.nombre))
                       WHERE pg.nombre = 'RECL_PROCESO_SPONSOR'
                         AND COALESCE(pv.activo, 1) = 1
                         AND pv.parent_id = ?
                         AND UPPER(LTRIM(RTRIM(COALESCE(pv.valor, '')))) IN ('PRINCIPAL', 'BACKUP')
                         AND COALESCE(u.disabled, 0) = 0"""

SQL__RECLAMOS_EDITAR_PROCESO_SEL_5 = f"""SELECT DISTINCT u.id AS usuario_id
                   FROM {T_PARAM_VALUES} pv
                   JOIN {T_PARAM_GROUPS} pg ON pg.id = pv.group_id
                   JOIN {T_USUARIOS} u ON LTRIM(RTRIM(u.identificacion)) = LTRIM(RTRIM(pv.nombre))
                   WHERE pg.nombre = 'RECL_PROCESO_SPONSOR'
                     AND COALESCE(pv.activo, 1) = 1
                     AND UPPER(LTRIM(RTRIM(COALESCE(pv.valor, '')))) IN ('PRINCIPAL', 'BACKUP')
                     AND COALESCE(u.disabled, 0) = 0"""

SQL__RECLAMOS_EDITAR_PROCESO_SEL_6 = f"SELECT imputado_id FROM {T_RECLAMO_IMPUTADOS} WHERE reclamo_id = ? AND COALESCE(activo, 1) = 1"

SQL__RECLAMOS_EDITAR_PROCESO_UPD_7 = f"""UPDATE {T_RECLAMO_IMPUTADOS}
                        SET activo = 0
                        WHERE reclamo_id = ?
                          AND imputado_id IN ({{placeholders}})
                          AND COALESCE(activo, 1) = 1"""

SQL__RECLAMOS_EDITAR_PROCESO_SEL_8 = f"""SELECT STUFF((
                       SELECT DISTINCT ', ' + COALESCE(u.username, '')
                       FROM {T_RECLAMO_IMPUTADOS} ri
                       LEFT JOIN {T_USUARIOS} u ON u.id = ri.imputado_id
                       WHERE ri.reclamo_id = ?
                         AND COALESCE(ri.activo, 1) = 1
                       FOR XML PATH(''), TYPE
                   ).value('.', 'NVARCHAR(MAX)'), 1, 2, '') AS imputados_resumen"""

