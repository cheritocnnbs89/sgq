# modules/planificador/planificador_querys.py
# -*- coding: utf-8 -*-
"""
Sentencias SQL del módulo Planificador.
Los nombres de tabla se importan desde planificador_constants.py.
planificador_repository.py importa estas constantes y las ejecuta.
"""

from .planificador_constants import (
    TBL_SOLICITUDES,
    TBL_CONFIG,
    TBL_GRUPOS,
    TBL_LOGS,
    TBL_TIPO_FLAGS,
    TBL_ROL_FLAGS,
    TBL_VOUCHER_ITEMS,
    TBL_NOTIFY_INAPP,
    TBL_USUARIOS,
    TBL_DEPARTAMENTOS,
    TBL_PUESTOS,
    TBL_PARAM_VALUES,
    TBL_PARAM_GROUPS,
    TBL_PRESUPUESTO,
)

# ──────────────────────────────────────────────
# Solicitudes – lectura
# ──────────────────────────────────────────────

SQL_GET_ALL_SOLICITUDES = f"""
    SELECT s.*
    FROM {TBL_SOLICITUDES} s
    WHERE {{where}}
    ORDER BY s.fecha DESC, s.hora_inicio
"""

SQL_GET_SOLICITUDES_BY_TIPOS = f"""
    SELECT s.*
    FROM {TBL_SOLICITUDES} s
    WHERE s.activo = 1
      AND s.tipo IN ({{placeholders_t}})
      AND s.estado IN ({{placeholders_e}})
      {{where_extra}}
    ORDER BY s.fecha DESC, s.hora_inicio
"""

SQL_GET_MIS_SOLICITUDES = f"""
    SELECT s.*
    FROM {TBL_SOLICITUDES} s
    WHERE {{where}}
    ORDER BY s.fecha DESC, s.hora_inicio
"""

SQL_GET_SOLICITUD_BY_ID = f"""
    SELECT *
    FROM {TBL_SOLICITUDES}
    WHERE id = ? AND activo = 1
"""

SQL_GET_CALENDAR_SOLICITUDES = f"""
    SELECT id, tipo, area_solicitante, descripcion, lugar_destino,
           fecha, hora_inicio, hora_fin, estado, prioridad,
           solicitante_nombre
    FROM {TBL_SOLICITUDES}
    WHERE activo = 1
      AND estado IN ('APROBADA', 'COORDINADA', 'PENDIENTE_LIQUIDACION', 'PENDIENTE_APROBACION', 'COMPLETADA')
      AND fecha BETWEEN ? AND ?
    ORDER BY fecha, hora_inicio
"""

SQL_GET_SOLICITUDES_PENDIENTE_GERENTE = f"""
    SELECT s.*
    FROM {TBL_SOLICITUDES} s
    WHERE s.activo = 1
      AND s.tipo IN ({{placeholders}})
      AND s.estado = 'PENDIENTE_APROBACION_GERENTE'
      AND s.gerente_id = ?
      {{where_extra}}
    ORDER BY s.fecha DESC, s.hora_inicio
"""

SQL_GET_SOLICITUDES_PENDIENTES_MISMO_TIPO = f"""
    SELECT id, area_solicitante, lugar_destino, fecha, descripcion, solicitante_nombre
    FROM {TBL_SOLICITUDES}
    WHERE tipo = ?
      AND estado = 'PENDIENTE_COORDINACION'
      AND id != ?
      AND activo = 1
    ORDER BY fecha, area_solicitante
"""

SQL_GET_SOLICITUDES_DEL_GRUPO = f"""
    SELECT id, tipo, area_solicitante, lugar_destino, fecha,
           hora_inicio, hora_fin, estado, solicitante_nombre, solicitante_id
    FROM {TBL_SOLICITUDES}
    WHERE grupo_id = ? AND activo = 1
    ORDER BY id
"""

SQL_GET_SOLICITUDES_PARA_REPORTE = f"""
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
        cc.nombre                                  AS [Centro de Costo],
        pres.presupuestado                         AS [Presupuesto Total (Año)],
        pres.ejecutado                             AS [Valor Consumido (Año)],
        s.costo_real                               AS [Gasto Realizado],
        s.penalizacion                             AS penalizacion,
        s.cotizacion_hospedaje                     AS cotizacion_hospedaje,
        CONVERT(VARCHAR,s.fecha_creacion,120)      AS [Fecha Creación],
        CONVERT(VARCHAR,s.fecha_actualizacion,120) AS [Última Actualización]
    FROM {TBL_SOLICITUDES} s
    LEFT JOIN {TBL_USUARIOS} su ON su.id = s.solicitante_id
    LEFT JOIN {TBL_PARAM_VALUES} cc ON cc.id = s.centro_costo_id
    LEFT JOIN (
        SELECT centro_costo_id, empresa_id,
               SUM(monto_presupuestado) AS presupuestado,
               SUM(monto_ejecutado)     AS ejecutado
        FROM {TBL_PRESUPUESTO}
        WHERE tipo_gasto = N'Ticket aéreo' AND anio = YEAR(GETDATE())
        GROUP BY centro_costo_id, empresa_id
    ) pres ON pres.centro_costo_id = s.centro_costo_id AND pres.empresa_id = su.empresa_id
    WHERE {{where}}
    ORDER BY s.fecha DESC, s.hora_inicio
"""

SQL_CHECK_HORARIO_OCUPADO = f"""
    SELECT TOP 1 id
    FROM {TBL_SOLICITUDES}
    WHERE tipo = ?
      AND fecha = ?
      AND activo = 1
      AND estado NOT IN ('RECHAZADA','COMPLETADA')
      AND hora_inicio IS NOT NULL
      AND hora_fin   IS NOT NULL
      {{excl}}
      AND hora_inicio < ?
      AND hora_fin   > ?
"""

SQL_GET_FECHA_SOLICITUD = f"""
    SELECT fecha
    FROM {TBL_SOLICITUDES}
    WHERE id = ? AND activo = 1
"""

# ──────────────────────────────────────────────
# Solicitudes – escritura
# ──────────────────────────────────────────────

SQL_INSERT_SOLICITUD = f"""
    INSERT INTO {TBL_SOLICITUDES}
        (tipo, area_solicitante, descripcion, lugar_destino, detalle_direccion,
         contacto, prioridad, fecha, estado, solicitante_id, solicitante_nombre,
         ciudad, presupuesto_base_cero,
         fecha_retorno, punto_salida, punto_destino,
         requiere_hospedaje, orden_servicio, centro_costo_id,
         requiere_aprobacion_presupuesto,
         gerente_id, gerente_nombre, motivo_vuelo,
         numero_vouchers)
    OUTPUT INSERTED.id
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?,
            ?)
"""

SQL_UPDATE_REAGENDAR = f"""
    UPDATE {TBL_SOLICITUDES} SET
        fecha                   = ?,
        estado                  = ?,
        hora_inicio             = NULL,
        hora_fin                = NULL,
        coordinador_id          = NULL,
        coordinador_nombre      = NULL,
        observacion_coordinador = NULL,
        fecha_actualizacion     = GETDATE()
    WHERE id = ? AND activo = 1
"""

# ── Vuelo: aprobación jefe directo → siempre pasa a cotización del coordinador
SQL_VUELO_APROBAR_JEFE_OK = f"""
    UPDATE {TBL_SOLICITUDES} SET
        estado                = 'PENDIENTE_COORDINACION',
        aprobador_id          = ?,
        aprobador_nombre      = ?,
        observacion_aprobador = ?,
        fecha_actualizacion   = GETDATE()
    WHERE id = ? AND activo = 1
"""

# ── Vuelo: coordinador ingresa el valor cotizado del pasaje → pasa a aprobación GG
SQL_VUELO_COTIZAR = f"""
    UPDATE {TBL_SOLICITUDES} SET
        estado                  = 'PENDIENTE_APROBACION_GG_VUELO',
        datos_ticket            = ?,
        observacion_coordinador = ?,
        coordinador_id          = ?,
        coordinador_nombre      = ?,
        fecha_actualizacion     = GETDATE()
    WHERE id = ? AND activo = 1
"""

# ── Vuelo: GG aprueba la cotización → coordinador debe ingresar info del vuelo
SQL_VUELO_APROBAR_GG = f"""
    UPDATE {TBL_SOLICITUDES} SET
        estado                = 'PENDIENTE_INFO_VUELO',
        aprobador_id          = ?,
        aprobador_nombre      = ?,
        observacion_aprobador = ?,
        fecha_actualizacion   = GETDATE()
    WHERE id = ? AND activo = 1
"""

# ── Vuelo: GG rechaza la cotización → vuelve al coordinador para recotizar
SQL_VUELO_RECHAZAR_GG = f"""
    UPDATE {TBL_SOLICITUDES} SET
        estado                = 'PENDIENTE_COORDINACION',
        aprobador_id          = ?,
        aprobador_nombre      = ?,
        observacion_aprobador = ?,
        fecha_actualizacion   = GETDATE()
    WHERE id = ? AND activo = 1
"""

# ── Vuelo: coordinador registra gestión y completa
SQL_VUELO_COMPLETAR = f"""
    UPDATE {TBL_SOLICITUDES} SET
        estado                  = 'COORDINADA',
        coordinador_id          = ?,
        coordinador_nombre      = ?,
        hora_inicio             = ?,
        hora_fin                = ?,
        observacion_coordinador = ?,
        fecha_actualizacion     = GETDATE()
    WHERE id = ? AND activo = 1
"""

SQL_VUELO_MARCAR_REALIZADO = f"""
    UPDATE {TBL_SOLICITUDES} SET
        estado              = 'PENDIENTE_LIQUIDACION',
        fecha_actualizacion = GETDATE()
    WHERE id = ? AND activo = 1
"""

SQL_VUELO_LIQUIDAR = f"""
    UPDATE {TBL_SOLICITUDES} SET
        estado               = 'COMPLETADA',
        costo_real           = ?,
        notas_liquidacion    = ?,
        fecha_actualizacion  = GETDATE()
    WHERE id = ? AND activo = 1
"""

# ── Voucher: aprobación jefe directo → el coordinador debe entregar los vouchers (con secuencial)
SQL_VOUCHER_APROBAR_JEFE_OK = f"""
    UPDATE {TBL_SOLICITUDES} SET
        estado                = 'PENDIENTE_ENTREGA_VOUCHER',
        aprobador_id          = ?,
        aprobador_nombre      = ?,
        observacion_aprobador = ?,
        fecha_actualizacion   = GETDATE()
    WHERE id = ? AND activo = 1
"""

# ── Voucher: jefe rechaza → fin del flujo (reutiliza SQL_UPDATE_RECHAZAR, igual que Vuelo)

# ── Voucher: items individuales (uno por voucher solicitado) ──────────────

SQL_VOUCHER_ITEM_INSERT = f"""
    INSERT INTO {TBL_VOUCHER_ITEMS} (solicitud_id, numero, origen, destino)
    OUTPUT INSERTED.id
    VALUES (?, ?, ?, ?)
"""

SQL_VOUCHER_ITEMS_BY_SOLICITUD = f"""
    SELECT * FROM {TBL_VOUCHER_ITEMS}
    WHERE solicitud_id = ?
    ORDER BY numero ASC
"""

SQL_VOUCHER_ITEM_BY_ID = f"""
    SELECT * FROM {TBL_VOUCHER_ITEMS} WHERE id = ?
"""

SQL_VOUCHER_ITEM_BY_SECUENCIAL = f"""
    SELECT TOP 1 * FROM {TBL_VOUCHER_ITEMS} WHERE secuencial = ?
"""

# Datos reales (origen/destino) que reporta el proveedor de taxis en la
# carga masiva de costos — columnas nuevas, ver DDL entregado aparte.
SQL_VOUCHER_ITEM_SET_DATOS_REALES = f"""
    UPDATE {TBL_VOUCHER_ITEMS} SET
        origen_real  = ?,
        destino_real = ?
    WHERE id = ?
"""

SQL_VOUCHER_ITEM_ENTREGAR = f"""
    UPDATE {TBL_VOUCHER_ITEMS} SET
        secuencial            = ?,
        entregado_at          = GETDATE(),
        entregado_por_id      = ?,
        entregado_por_nombre  = ?
    WHERE id = ?
"""

SQL_VOUCHER_ITEM_CONFIRMAR = f"""
    UPDATE {TBL_VOUCHER_ITEMS} SET
        adjunto_nombre_original = ?,
        adjunto_nombre_guardado = ?,
        adjunto_tamano          = ?,
        observacion_usuario     = ?,
        confirmado_usuario      = 1,
        confirmado_at           = GETDATE()
    WHERE id = ?
"""

SQL_VOUCHER_ITEM_LIQUIDAR = f"""
    UPDATE {TBL_VOUCHER_ITEMS} SET
        costo               = ?,
        liquidado_at         = GETDATE(),
        liquidado_por_id     = ?,
        liquidado_por_nombre = ?
    WHERE id = ?
"""

# El solicitante marca el voucher como no utilizado: cuenta como confirmado
# (costo=0, sin adjunto obligatorio) para que no bloquee ni la etapa de
# confirmación ni la de liquidación de los demás vouchers de la solicitud.
SQL_VOUCHER_ITEM_NO_UTILIZADO = f"""
    UPDATE {TBL_VOUCHER_ITEMS} SET
        no_utilizado            = 1,
        observacion_usuario     = ?,
        confirmado_usuario      = 1,
        confirmado_at           = GETDATE(),
        costo                   = 0,
        liquidado_at            = GETDATE(),
        liquidado_por_nombre    = 'No utilizado (marcado por el solicitante)'
    WHERE id = ?
"""

# ── Voucher: recordatorio/escalamiento de confirmación pendiente ──────────
# Columnas nuevas necesarias en planificador_voucher_items (ver DDL entregado
# aparte): recordatorio1_enviado_at, recordatorio2_enviado_at.

SQL_VOUCHER_ITEMS_PENDIENTES_RECORDATORIO_3D = f"""
    SELECT vi.id, vi.solicitud_id, vi.numero, vi.origen, vi.destino, vi.entregado_at,
           s.solicitante_id, s.solicitante_nombre, s.area_solicitante, s.fecha
    FROM {TBL_VOUCHER_ITEMS} vi
    JOIN {TBL_SOLICITUDES} s ON s.id = vi.solicitud_id AND s.activo = 1
    WHERE vi.secuencial IS NOT NULL
      AND COALESCE(vi.confirmado_usuario, 0) = 0
      AND vi.recordatorio1_enviado_at IS NULL
      AND vi.entregado_at IS NOT NULL
      AND DATEDIFF(day, vi.entregado_at, GETDATE()) >= 3
"""

SQL_VOUCHER_ITEMS_PENDIENTES_RECORDATORIO_6D = f"""
    SELECT vi.id, vi.solicitud_id, vi.numero, vi.origen, vi.destino, vi.entregado_at,
           s.solicitante_id, s.solicitante_nombre, s.area_solicitante, s.fecha
    FROM {TBL_VOUCHER_ITEMS} vi
    JOIN {TBL_SOLICITUDES} s ON s.id = vi.solicitud_id AND s.activo = 1
    WHERE vi.secuencial IS NOT NULL
      AND COALESCE(vi.confirmado_usuario, 0) = 0
      AND vi.recordatorio2_enviado_at IS NULL
      AND vi.entregado_at IS NOT NULL
      AND DATEDIFF(day, vi.entregado_at, GETDATE()) >= 6
"""

SQL_VOUCHER_ITEM_MARCAR_RECORDATORIO1 = f"""
    UPDATE {TBL_VOUCHER_ITEMS} SET recordatorio1_enviado_at = GETDATE() WHERE id = ?
"""

SQL_VOUCHER_ITEM_MARCAR_RECORDATORIO2 = f"""
    UPDATE {TBL_VOUCHER_ITEMS} SET recordatorio2_enviado_at = GETDATE() WHERE id = ?
"""

# ── Voucher: transiciones del estado de la solicitud padre ────────────────

SQL_VOUCHER_SOLICITUD_A_CONFIRMACION = f"""
    UPDATE {TBL_SOLICITUDES} SET
        estado               = 'PENDIENTE_CONFIRMACION_VOUCHER',
        coordinador_id        = ?,
        coordinador_nombre    = ?,
        fecha_actualizacion   = GETDATE()
    WHERE id = ? AND activo = 1
"""

SQL_VOUCHER_SOLICITUD_A_LIQUIDACION = f"""
    UPDATE {TBL_SOLICITUDES} SET
        estado               = 'PENDIENTE_LIQUIDACION_VOUCHER',
        fecha_actualizacion  = GETDATE()
    WHERE id = ? AND activo = 1
"""

SQL_VOUCHER_SOLICITUD_COMPLETAR = f"""
    UPDATE {TBL_SOLICITUDES} SET
        estado               = 'COMPLETADA',
        costo_real           = ?,
        fecha_actualizacion  = GETDATE()
    WHERE id = ? AND activo = 1
"""

# NOTA: el esquema de planificador_voucher_items (incluyendo columnas
# origen/destino) se gestiona directamente en SQL Server, no desde código.
# No agregar aquí constantes de CREATE TABLE / ALTER TABLE.

SQL_EJECUTAR_PRESUPUESTO_VUELO = f"""
    IF EXISTS (
        SELECT 1 FROM {TBL_PRESUPUESTO}
        WHERE empresa_id=? AND centro_costo_id=? AND tipo_gasto=? AND anio=? AND mes=?
    )
        UPDATE {TBL_PRESUPUESTO}
           SET monto_ejecutado = monto_ejecutado + ?
         WHERE empresa_id=? AND centro_costo_id=? AND tipo_gasto=? AND anio=? AND mes=?
    ELSE
        INSERT INTO {TBL_PRESUPUESTO}
            (empresa_id, centro_costo_id, tipo_gasto, anio, mes, monto_presupuestado, monto_ejecutado)
        VALUES (?, ?, ?, ?, ?, 0, ?)
"""

SQL_GET_EMPRESA_BY_USUARIO = f"""
    SELECT empresa_id FROM {TBL_USUARIOS} WHERE id = ?
"""

SQL_GET_VUELOS_COORDINADAS_SIN_LIQUIDAR = f"""
    SELECT s.id, s.area_solicitante, s.fecha, s.coordinador_id, s.coordinador_nombre,
           u.email AS coordinador_email
    FROM {TBL_SOLICITUDES} s
    LEFT JOIN {TBL_USUARIOS} u ON u.id = s.coordinador_id
    WHERE s.activo = 1
      AND s.tipo   = 'Vuelo'
      AND s.estado = 'COORDINADA'
      AND s.fecha_actualizacion < DATEADD(day, -3, GETDATE())
"""

# ── Solicitudes en PENDIENTE_APROBACION_JEFE para un gerente_id
SQL_GET_SOLICITUDES_PENDIENTE_JEFE = f"""
    SELECT s.*
    FROM {TBL_SOLICITUDES} s
    WHERE s.activo = 1
      AND s.estado = 'PENDIENTE_APROBACION_JEFE'
      AND s.gerente_id = ?
      {{where_extra}}
    ORDER BY s.fecha DESC
"""

# ── Solicitudes en PENDIENTE_APROBACION_GG_VUELO para tipos del GG
SQL_GET_SOLICITUDES_PENDIENTE_GG_VUELO = f"""
    SELECT s.*
    FROM {TBL_SOLICITUDES} s
    WHERE s.activo = 1
      AND s.estado = 'PENDIENTE_APROBACION_GG_VUELO'
      AND s.tipo IN ({{placeholders}})
      {{where_extra}}
    ORDER BY s.fecha DESC
"""

SQL_UPDATE_COORDINAR = f"""
    UPDATE {TBL_SOLICITUDES} SET
        hora_inicio             = ?,
        hora_fin                = ?,
        observacion_coordinador = ?,
        coordinador_id          = ?,
        coordinador_nombre      = ?,
        estado                  = 'PENDIENTE_APROBACION',
        fecha_actualizacion     = GETDATE()
    WHERE id = ? AND activo = 1
"""

SQL_UPDATE_COORDINAR_GRUPO = f"""
    UPDATE {TBL_SOLICITUDES} SET
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

SQL_UPDATE_COORDINAR_VUELO = f"""
    UPDATE {TBL_SOLICITUDES} SET
        hora_inicio             = ?,
        hora_fin                = ?,
        datos_ticket            = ?,
        datos_hotel             = ?,
        observacion_coordinador = ?,
        coordinador_id          = ?,
        coordinador_nombre      = ?,
        estado                  = 'COORDINADA',
        fecha_actualizacion     = GETDATE()
    WHERE id = ? AND activo = 1
"""

SQL_REAGENDAR_VUELO_A_JEFE = f"""
    UPDATE {TBL_SOLICITUDES} SET
        fecha                  = ?,
        fecha_retorno          = ?,
        hora_inicio            = NULL,
        hora_fin               = NULL,
        datos_ticket           = NULL,
        datos_hotel            = NULL,
        aprobador_id           = NULL,
        aprobador_nombre       = NULL,
        observacion_aprobador  = NULL,
        coordinador_id         = NULL,
        coordinador_nombre     = NULL,
        observacion_coordinador = NULL,
        estado                 = 'PENDIENTE_APROBACION_JEFE',
        fecha_actualizacion    = GETDATE()
    WHERE id = ? AND activo = 1
"""

SQL_UPDATE_APROBAR = f"""
    UPDATE {TBL_SOLICITUDES} SET
        estado                = 'APROBADA',
        aprobador_id          = ?,
        aprobador_nombre      = ?,
        observacion_aprobador = ?,
        fecha_actualizacion   = GETDATE()
    WHERE id = ? AND activo = 1
"""

SQL_UPDATE_RECHAZAR = f"""
    UPDATE {TBL_SOLICITUDES} SET
        estado                = 'RECHAZADA',
        aprobador_id          = ?,
        aprobador_nombre      = ?,
        observacion_aprobador = ?,
        fecha_actualizacion   = GETDATE()
    WHERE id = ? AND activo = 1
"""

SQL_UPDATE_COMPLETAR = f"""
    UPDATE {TBL_SOLICITUDES} SET
        estado              = 'COMPLETADA',
        fecha_actualizacion = GETDATE()
    WHERE id = ? AND activo = 1
"""

SQL_UPDATE_PONER_PENDIENTE_GERENTE = f"""
    UPDATE {TBL_SOLICITUDES} SET
        estado              = 'PENDIENTE_APROBACION_GERENTE',
        gerente_id          = ?,
        gerente_nombre      = ?,
        fecha_actualizacion = GETDATE()
    WHERE id = ? AND activo = 1
"""

SQL_UPDATE_APROBAR_GERENTE = f"""
    UPDATE {TBL_SOLICITUDES} SET
        estado = 'APROBADA',
        observacion_aprobador = COALESCE(
            CASE WHEN observacion_aprobador IS NOT NULL AND observacion_aprobador <> ''
                 THEN observacion_aprobador + ' | Gerente: ' + ?
                 ELSE ?
            END, ?),
        fecha_actualizacion = GETDATE()
    WHERE id = ? AND activo = 1
"""

SQL_UPDATE_RECHAZAR_GERENTE = f"""
    UPDATE {TBL_SOLICITUDES} SET
        estado                = 'RECHAZADA',
        aprobador_id          = ?,
        aprobador_nombre      = ?,
        observacion_aprobador = ?,
        fecha_actualizacion   = GETDATE()
    WHERE id = ? AND activo = 1
"""

SQL_UPDATE_ELIMINAR_SOLICITUD = f"""
    UPDATE {TBL_SOLICITUDES}
       SET activo               = 0,
           eliminado_por_id     = ?,
           eliminado_por_nombre = ?,
           fecha_eliminacion    = GETDATE()
     WHERE id = ?
"""

# ──────────────────────────────────────────────
# Grupos de coordinación
# ──────────────────────────────────────────────

SQL_INSERT_GRUPO = f"""
    INSERT INTO {TBL_GRUPOS}
        (tipo, fecha, hora_inicio, hora_fin,
         coordinador_id, coordinador_nombre, observacion)
    OUTPUT INSERTED.id
    VALUES (?, ?, ?, ?, ?, ?, ?)
"""

# ──────────────────────────────────────────────
# Configuración coordinadores / aprobadores
# ──────────────────────────────────────────────

SQL_GET_ALL_CONFIG = f"""
    SELECT *
    FROM {TBL_CONFIG}
    WHERE activo = 1
    ORDER BY tipo, rol_config, usuario_nombre
"""

SQL_GET_CONFIG_FOR_USER = f"""
    SELECT tipo, rol_config
    FROM {TBL_CONFIG}
    WHERE usuario_id = ? AND activo = 1
"""

SQL_UPSERT_CONFIG = f"""
    IF NOT EXISTS (
        SELECT 1 FROM {TBL_CONFIG}
        WHERE tipo = ? AND usuario_id = ? AND rol_config = ?
    )
        INSERT INTO {TBL_CONFIG} (tipo, usuario_id, usuario_nombre, rol_config)
        VALUES (?, ?, ?, ?)
    ELSE
        UPDATE {TBL_CONFIG} SET activo = 1, usuario_nombre = ?
        WHERE tipo = ? AND usuario_id = ? AND rol_config = ?
"""

SQL_DELETE_CONFIG = f"""
    UPDATE {TBL_CONFIG} SET activo = 0 WHERE id = ?
"""

SQL_GET_ROLES_PARA_TIPO = f"""
    SELECT pc.usuario_id, pc.usuario_nombre, pc.rol_config, u.email, u.telefono
    FROM {TBL_CONFIG} pc
    LEFT JOIN {TBL_USUARIOS} u ON u.id = pc.usuario_id AND u.disabled = 0
    WHERE pc.tipo = ? AND pc.activo = 1
"""

SQL_GET_ADMINS_CON_TELEFONO = f"""
    SELECT id, nombre_completo, telefono
    FROM {TBL_USUARIOS}
    WHERE rol = 'admin'
      AND disabled = 0
      AND telefono IS NOT NULL
      AND LTRIM(RTRIM(telefono)) <> ''
"""

# ──────────────────────────────────────────────
# Tipos de solicitud
# ──────────────────────────────────────────────

SQL_GET_TIPOS_SOLICITUD = f"""
    SELECT pv.nombre
    FROM {TBL_PARAM_VALUES} pv
    JOIN {TBL_PARAM_GROUPS} pg ON pg.id = pv.group_id
    WHERE pg.nombre = ?
      AND pv.activo = 1
    ORDER BY pv.orden, pv.nombre
"""

# ──────────────────────────────────────────────
# Motivos de solicitud de Vuelo
# ──────────────────────────────────────────────

SQL_GET_MOTIVOS_VUELO = f"""
    SELECT pv.nombre
    FROM {TBL_PARAM_VALUES} pv
    JOIN {TBL_PARAM_GROUPS} pg ON pg.id = pv.group_id
    WHERE pg.nombre = ?
      AND pv.activo = 1
    ORDER BY pv.orden, pv.nombre
"""

# ──────────────────────────────────────────────
# Tipo flags
# ──────────────────────────────────────────────

SQL_GET_TIPO_FLAGS = f"""
    SELECT requiere_aprobacion_gerente,
           COALESCE(auto_confirmar_vuelo, 0) AS auto_confirmar_vuelo,
           COALESCE(auto_liquidar_vuelo,  0) AS auto_liquidar_vuelo
    FROM {TBL_TIPO_FLAGS}
    WHERE tipo = ?
"""

SQL_GET_ALL_TIPO_FLAGS = f"""
    SELECT tipo,
           requiere_aprobacion_gerente,
           COALESCE(auto_confirmar_vuelo, 0) AS auto_confirmar_vuelo,
           COALESCE(auto_liquidar_vuelo,  0) AS auto_liquidar_vuelo
    FROM {TBL_TIPO_FLAGS}
"""

SQL_UPSERT_TIPO_FLAGS = f"""
    IF EXISTS (SELECT 1 FROM {TBL_TIPO_FLAGS} WHERE tipo = ?)
        UPDATE {TBL_TIPO_FLAGS}
           SET requiere_aprobacion_gerente = ?,
               auto_confirmar_vuelo        = ?,
               auto_liquidar_vuelo         = ?
         WHERE tipo = ?
    ELSE
        INSERT INTO {TBL_TIPO_FLAGS} (tipo, requiere_aprobacion_gerente, auto_confirmar_vuelo, auto_liquidar_vuelo)
        VALUES (?, ?, ?, ?)
"""

SQL_GET_VUELO_FLAGS = f"""
    SELECT COALESCE(auto_confirmar_vuelo, 0) AS auto_confirmar_vuelo,
           COALESCE(auto_liquidar_vuelo,  0) AS auto_liquidar_vuelo
    FROM {TBL_TIPO_FLAGS}
    WHERE tipo = 'Vuelo'
"""

SQL_GET_VUELOS_PARA_AUTO_CONFIRMAR = f"""
    SELECT id, solicitante_id, solicitante_nombre, coordinador_id, coordinador_nombre,
           area_solicitante, fecha, datos_ticket, cotizacion_hospedaje
    FROM {TBL_SOLICITUDES}
    WHERE tipo = 'Vuelo'
      AND estado = 'COORDINADA'
      AND COALESCE(fecha_retorno, fecha) < CAST(GETDATE() AS DATE)
"""

SQL_GET_VUELOS_PARA_AUTO_LIQUIDAR = f"""
    SELECT id, solicitante_id, solicitante_nombre, coordinador_id, coordinador_nombre,
           area_solicitante, fecha, datos_ticket, cotizacion_hospedaje, centro_costo_id
    FROM {TBL_SOLICITUDES}
    WHERE tipo = 'Vuelo'
      AND estado = 'PENDIENTE_LIQUIDACION'
      AND COALESCE(fecha_retorno, fecha) < CAST(GETDATE() AS DATE)
"""

SQL_SET_COTIZACION_HOSPEDAJE = f"""
    UPDATE {TBL_SOLICITUDES} SET cotizacion_hospedaje = ? WHERE id = ?
"""

# ──────────────────────────────────────────────
# Roles que auto-aprueban el paso de aprobación del jefe directo (Vuelo)
# ──────────────────────────────────────────────

SQL_GET_ALL_ROL_FLAGS = f"""
    SELECT rol, autoaprueba_jefe_vuelo
    FROM {TBL_ROL_FLAGS}
"""

SQL_GET_ROLES_AUTOAPROBAR_JEFE_VUELO = f"""
    SELECT rol
    FROM {TBL_ROL_FLAGS}
    WHERE autoaprueba_jefe_vuelo = 1
"""

SQL_UPSERT_ROL_FLAGS = f"""
    IF EXISTS (SELECT 1 FROM {TBL_ROL_FLAGS} WHERE rol = ?)
        UPDATE {TBL_ROL_FLAGS}
           SET autoaprueba_jefe_vuelo = ?
         WHERE rol = ?
    ELSE
        INSERT INTO {TBL_ROL_FLAGS} (rol, autoaprueba_jefe_vuelo)
        VALUES (?, ?)
"""

# ──────────────────────────────────────────────
# Usuarios y catálogos
# ──────────────────────────────────────────────

SQL_GET_USUARIOS_FOR_SELECT = f"""
    SELECT id,
           COALESCE(nombre_completo, username) AS nombre,
           username
    FROM {TBL_USUARIOS}
    WHERE disabled = 0
    ORDER BY nombre_completo, username
"""

SQL_GET_DEPARTAMENTOS = f"""
    SELECT id, nombre
    FROM {TBL_DEPARTAMENTOS}
    ORDER BY nombre
"""

SQL_GET_USUARIO_DEPARTAMENTO = f"""
    SELECT d.id, d.nombre
    FROM {TBL_USUARIOS} u
    LEFT JOIN {TBL_DEPARTAMENTOS} d ON d.id = u.departamento_id
    WHERE u.id = ?
"""

SQL_GET_EMAIL_BY_USUARIO_ID = f"""
    SELECT email FROM {TBL_USUARIOS} WHERE id = ? AND disabled = 0
"""

SQL_GET_ROL_USUARIO = f"""
    SELECT rol FROM {TBL_USUARIOS} WHERE id = ?
"""

SQL_GET_CIUDAD_USUARIO = f"""
    SELECT COALESCE(ciudad, '') FROM {TBL_USUARIOS} WHERE id = ?
"""

SQL_GET_JEFE_USUARIO = f"""
    SELECT jefe_id FROM {TBL_USUARIOS} WHERE id = ? AND COALESCE(disabled,0) = 0
"""

SQL_GET_JEFE_NOMBRE_BATCH = f"""
    SELECT u.id AS solicitante_id,
           COALESCE(j.nombre_completo, j.username, '') AS jefe_nombre,
           COALESCE(j.username, '') AS jefe_username
    FROM {TBL_USUARIOS} u
    LEFT JOIN {TBL_USUARIOS} j ON j.id = u.jefe_id AND COALESCE(j.disabled,0) = 0
    WHERE u.id IN ({{placeholders}})
"""

SQL_GET_USUARIO_JERARQUIA = f"""
    SELECT id, COALESCE(nombre_completo, username) AS nombre,
           email, jefe_id, LOWER(COALESCE(rol,'')) AS rol
    FROM {TBL_USUARIOS}
    WHERE id = ? AND COALESCE(disabled,0) = 0
"""

SQL_UPDATE_TELEGRAM_CHAT_ID = f"""
    UPDATE {TBL_USUARIOS} SET telegram_chat_id = ? WHERE id = ?
"""

SQL_GET_MOTORIZADOS_IDS_EMAILS = f"""
    SELECT DISTINCT u.id, u.email
    FROM {TBL_USUARIOS} u
    JOIN {TBL_PUESTOS} p ON p.id = u.puesto_id
    WHERE u.disabled = 0
      AND (p.nombre LIKE '%MOTORIZADO%' OR p.nombre LIKE '%SERVICIOS VARIOS%')
"""

SQL_GET_MOTORIZADOS_EMAIL = f"""
    SELECT DISTINCT u.email
    FROM {TBL_USUARIOS} u
    JOIN {TBL_PUESTOS} p ON p.id = u.puesto_id
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

SQL_GET_TELEGRAM_CHAT_IDS_PARA_TIPO = f"""
    SELECT pc.usuario_id,
           pc.usuario_nombre,
           u.telegram_chat_id
    FROM {TBL_CONFIG} pc
    JOIN {TBL_USUARIOS} u ON u.id = pc.usuario_id AND u.disabled = 0
    WHERE pc.tipo      = ?
      AND pc.rol_config = 'MOTORIZADO'
      AND pc.activo    = 1
      AND u.telegram_chat_id IS NOT NULL
      AND u.telegram_chat_id <> ''
"""

SQL_GET_MOTORIZADOS_TELEGRAM_STATUS = f"""
    SELECT pc.usuario_id,
           pc.usuario_nombre,
           pc.tipo,
           u.email,
           u.telegram_chat_id
    FROM {TBL_CONFIG} pc
    LEFT JOIN {TBL_USUARIOS} u ON u.id = pc.usuario_id
    WHERE pc.rol_config = 'MOTORIZADO'
      AND pc.activo     = 1
    ORDER BY pc.tipo, pc.usuario_nombre
"""

# ──────────────────────────────────────────────
# Logs de trazabilidad
# ──────────────────────────────────────────────

SQL_INSERT_SOLICITUD_LOG = f"""
    INSERT INTO {TBL_LOGS}
        (solicitud_id, accion, usuario_id, usuario_nombre, detalle, fecha_log)
    VALUES (?, ?, ?, ?, ?, GETDATE())
"""

SQL_GET_SOLICITUD_LOGS = f"""
    SELECT accion, usuario_nombre, detalle,
           CONVERT(VARCHAR, fecha_log, 120) AS fecha_log
    FROM {TBL_LOGS}
    WHERE solicitud_id = ?
    ORDER BY fecha_log ASC
"""

# ──────────────────────────────────────────────
# Notificaciones in-app
# ──────────────────────────────────────────────

SQL_INSERT_NOTIFY_INAPP = f"""
    INSERT INTO {TBL_NOTIFY_INAPP} (user_id, title, body, created_at, is_read)
    VALUES (?, ?, ?, ?, 0)
"""

# ──────────────────────────────────────────────
# Presupuesto por CC / empresa / tipo de gasto
# ──────────────────────────────────────────────

# NOTA: el esquema de planificador_presupuesto se gestiona directamente en
# SQL Server, no desde código. No agregar aquí constantes de CREATE TABLE.

SQL_GET_TIPOS_GASTO = f"""
    SELECT pv.nombre
    FROM {TBL_PARAM_VALUES} pv
    JOIN {TBL_PARAM_GROUPS} pg ON pg.id = pv.group_id
    WHERE pg.nombre = ?
      AND pv.activo = 1
    ORDER BY pv.orden, pv.nombre
"""

SQL_GET_PRESUPUESTO_GRID = f"""
    SELECT
        e.id   AS empresa_id,
        e.razon_social AS empresa_nombre,
        pv.id  AS centro_costo_id,
        pv.nombre AS centro_costo_nombre,
        p.tipo_gasto,
        p.mes,
        p.monto_presupuestado,
        p.monto_ejecutado
    FROM empresas e
    JOIN {TBL_USUARIOS} u ON u.empresa_id = e.id
    JOIN param_values pv  ON pv.id = u.cuenta_contable_id
    LEFT JOIN {TBL_PRESUPUESTO} p
           ON p.empresa_id      = e.id
          AND p.centro_costo_id = pv.id
          AND p.tipo_gasto      = ?
          AND p.anio            = ?
    WHERE e.activo = 1
      AND u.disabled = 0
      AND (? IS NULL OR e.id = ?)
    GROUP BY e.id, e.razon_social, pv.id, pv.nombre,
             p.tipo_gasto, p.mes, p.monto_presupuestado, p.monto_ejecutado
    ORDER BY e.razon_social, pv.nombre, p.mes
"""

SQL_GET_PRESUPUESTO_CC = f"""
    SELECT mes, monto_presupuestado, monto_ejecutado
    FROM {TBL_PRESUPUESTO}
    WHERE empresa_id = ? AND centro_costo_id = ? AND tipo_gasto = ? AND anio = ?
"""

SQL_UPSERT_PRESUPUESTO = f"""
    IF EXISTS (
        SELECT 1 FROM {TBL_PRESUPUESTO}
        WHERE empresa_id=? AND centro_costo_id=? AND tipo_gasto=? AND anio=? AND mes=?
    )
        UPDATE {TBL_PRESUPUESTO}
           SET monto_presupuestado = ?
         WHERE empresa_id=? AND centro_costo_id=? AND tipo_gasto=? AND anio=? AND mes=?
    ELSE
        INSERT INTO {TBL_PRESUPUESTO}
            (empresa_id, centro_costo_id, tipo_gasto, anio, mes, monto_presupuestado, monto_ejecutado)
        VALUES (?, ?, ?, ?, ?, ?, 0)
"""

SQL_GET_SALDO_PRESUPUESTO = f"""
    SELECT
        COALESCE(SUM(monto_presupuestado), 0) AS presupuestado,
        COALESCE(SUM(monto_ejecutado), 0)     AS ejecutado
    FROM {TBL_PRESUPUESTO}
    WHERE empresa_id      = ?
      AND centro_costo_id = ?
      AND tipo_gasto      = ?
      AND anio            = ?
      AND mes             = ?
"""

SQL_GET_SALDO_ANUAL_PRESUPUESTO = f"""
    SELECT
        COALESCE(SUM(monto_presupuestado), 0) AS presupuestado,
        COALESCE(SUM(monto_ejecutado), 0)     AS ejecutado
    FROM {TBL_PRESUPUESTO}
    WHERE empresa_id      = ?
      AND centro_costo_id = ?
      AND tipo_gasto      = ?
      AND anio            = ?
"""

SQL_ADD_EJECUTADO = f"""
    UPDATE {TBL_PRESUPUESTO}
       SET monto_ejecutado = monto_ejecutado + ?
     WHERE empresa_id=? AND centro_costo_id=? AND tipo_gasto=? AND anio=? AND mes=?
"""

SQL_SET_PENALIZACION = f"""
    UPDATE {TBL_SOLICITUDES} SET penalizacion = ? WHERE id = ?
"""

SQL_CHECK_DUPLICADO_SOLICITUD = f"""
    SELECT TOP 1 id, estado, CONVERT(varchar(10), fecha, 23) AS fecha_str,
                  CONVERT(varchar(10), fecha_retorno, 23) AS fecha_retorno_str
    FROM {TBL_SOLICITUDES}
    WHERE solicitante_id = ?
      AND tipo           = ?
      AND activo         = 1
      AND estado NOT IN ('RECHAZADA', 'COMPLETADA')
      AND (
            fecha         <= ?
        AND (fecha_retorno IS NULL OR fecha_retorno >= ?)
      )
"""

# ══════════════════════════════════════════════════════════════
# Indicadores — Voucher
# Filtro de área opcional vía el truco (? = '' OR s.area_solicitante = ?)
# para no armar SQL dinámico; fecha_desde/fecha_hasta siempre se envían.
# ══════════════════════════════════════════════════════════════

SQL_VOUCHER_IND_KPI = f"""
    SELECT
        COUNT(DISTINCT s.id)                                              AS total_solicitudes,
        COUNT(vi.id)                                                      AS total_vouchers,
        SUM(CASE WHEN COALESCE(vi.no_utilizado,0)=1 THEN 1 ELSE 0 END)    AS no_utilizados,
        SUM(CASE WHEN COALESCE(vi.no_utilizado,0)=0
                  AND COALESCE(vi.confirmado_usuario,0)=1 THEN 1 ELSE 0 END) AS confirmados,
        SUM(CASE WHEN vi.secuencial IS NULL THEN 1 ELSE 0 END)            AS pend_entrega,
        SUM(CASE WHEN vi.secuencial IS NOT NULL
                  AND COALESCE(vi.confirmado_usuario,0)=0 THEN 1 ELSE 0 END) AS pend_confirmacion,
        SUM(CASE WHEN vi.recordatorio2_enviado_at IS NOT NULL
                  AND COALESCE(vi.confirmado_usuario,0)=0 THEN 1 ELSE 0 END) AS escalados,
        SUM(CASE WHEN vi.costo IS NOT NULL THEN vi.costo ELSE 0 END)      AS costo_total,
        AVG(CASE WHEN vi.costo IS NOT NULL
                  AND COALESCE(vi.no_utilizado,0)=0 THEN vi.costo END)    AS costo_promedio
    FROM {TBL_VOUCHER_ITEMS} vi
    JOIN {TBL_SOLICITUDES} s ON s.id = vi.solicitud_id
    WHERE s.tipo = 'Voucher' AND s.activo = 1
      AND s.fecha BETWEEN ? AND ?
      AND (? = '' OR s.area_solicitante = ?)
"""

SQL_VOUCHER_IND_POR_USUARIO = f"""
    SELECT TOP 15
        s.solicitante_id, s.solicitante_nombre,
        COUNT(DISTINCT s.id) AS num_solicitudes,
        COUNT(vi.id)         AS num_vouchers,
        SUM(CASE WHEN vi.costo IS NOT NULL THEN vi.costo ELSE 0 END) AS costo_total
    FROM {TBL_VOUCHER_ITEMS} vi
    JOIN {TBL_SOLICITUDES} s ON s.id = vi.solicitud_id
    WHERE s.tipo = 'Voucher' AND s.activo = 1
      AND s.fecha BETWEEN ? AND ?
      AND (? = '' OR s.area_solicitante = ?)
    GROUP BY s.solicitante_id, s.solicitante_nombre
    ORDER BY num_vouchers DESC
"""

SQL_VOUCHER_IND_POR_DEPARTAMENTO = f"""
    SELECT
        COALESCE(NULLIF(LTRIM(RTRIM(s.area_solicitante)),''), 'Sin área') AS area,
        COUNT(DISTINCT s.id) AS num_solicitudes,
        COUNT(vi.id)         AS num_vouchers,
        SUM(CASE WHEN vi.costo IS NOT NULL THEN vi.costo ELSE 0 END) AS costo_total
    FROM {TBL_VOUCHER_ITEMS} vi
    JOIN {TBL_SOLICITUDES} s ON s.id = vi.solicitud_id
    WHERE s.tipo = 'Voucher' AND s.activo = 1
      AND s.fecha BETWEEN ? AND ?
      AND (? = '' OR s.area_solicitante = ?)
    GROUP BY s.area_solicitante
    ORDER BY costo_total DESC
"""

SQL_VOUCHER_IND_TENDENCIA_MENSUAL = f"""
    SELECT
        YEAR(s.fecha) AS anio, MONTH(s.fecha) AS mes,
        COUNT(vi.id) AS num_vouchers,
        SUM(CASE WHEN vi.costo IS NOT NULL THEN vi.costo ELSE 0 END) AS costo_total
    FROM {TBL_VOUCHER_ITEMS} vi
    JOIN {TBL_SOLICITUDES} s ON s.id = vi.solicitud_id
    WHERE s.tipo = 'Voucher' AND s.activo = 1
      AND s.fecha BETWEEN ? AND ?
      AND (? = '' OR s.area_solicitante = ?)
    GROUP BY YEAR(s.fecha), MONTH(s.fecha)
    ORDER BY anio, mes
"""

SQL_VOUCHER_IND_TOP_RUTAS = f"""
    SELECT TOP 10
        vi.origen, vi.destino,
        COUNT(*) AS cantidad,
        AVG(CASE WHEN vi.costo IS NOT NULL THEN vi.costo END) AS costo_promedio
    FROM {TBL_VOUCHER_ITEMS} vi
    JOIN {TBL_SOLICITUDES} s ON s.id = vi.solicitud_id
    WHERE s.tipo = 'Voucher' AND s.activo = 1
      AND s.fecha BETWEEN ? AND ?
      AND (? = '' OR s.area_solicitante = ?)
      AND vi.origen IS NOT NULL AND LTRIM(RTRIM(vi.origen)) <> ''
      AND vi.destino IS NOT NULL AND LTRIM(RTRIM(vi.destino)) <> ''
    GROUP BY vi.origen, vi.destino
    ORDER BY cantidad DESC
"""

# Detalle (drill-down) de vouchers entregados y aún sin confirmar por el
# solicitante, para el acordeón Departamento -> Usuario -> Voucher de la
# tarjeta "Pend. confirmación".
SQL_VOUCHER_IND_PEND_CONFIRMACION_DETALLE = f"""
    SELECT
        COALESCE(NULLIF(LTRIM(RTRIM(s.area_solicitante)),''), 'Sin área') AS area,
        s.solicitante_nombre,
        s.id AS solicitud_id,
        vi.numero, vi.secuencial, vi.origen, vi.destino, vi.entregado_at,
        DATEDIFF(day, vi.entregado_at, GETDATE()) AS dias_pendiente
    FROM {TBL_VOUCHER_ITEMS} vi
    JOIN {TBL_SOLICITUDES} s ON s.id = vi.solicitud_id
    WHERE s.tipo = 'Voucher' AND s.activo = 1
      AND s.fecha BETWEEN ? AND ?
      AND (? = '' OR s.area_solicitante = ?)
      AND vi.secuencial IS NOT NULL
      AND COALESCE(vi.confirmado_usuario,0) = 0
    ORDER BY area, s.solicitante_nombre, dias_pendiente DESC
"""
