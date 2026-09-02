# modules/planificador/planificador_repository.py
# -*- coding: utf-8 -*-
"""
Acceso a datos del módulo Planificador.
Las sentencias SQL están en planificador_querys.py;
las constantes de dominio en planificador_constants.py.
"""

from modules.db import get_db
from .planificador_constants import (
    PARAM_GROUP_TIPOS, TIPOS_SOLICITUD_DEFAULT,
    ROL_COORDINADOR, ROL_APROBADOR, ROL_MOTORIZADO, ROL_GERENTE_PRESUPUESTO, ROLES_GERENTE,
    PARAM_GROUP_TIPOS_GASTO, TIPOS_GASTO_DEFAULT, SEMAFORO_AMARILLO_PCT,
    PARAM_GROUP_MOTIVOS_VUELO, MOTIVOS_VUELO_DEFAULT,
)
from .planificador_querys import (
    SQL_GET_ALL_SOLICITUDES,
    SQL_GET_SOLICITUDES_BY_TIPOS,
    SQL_GET_MIS_SOLICITUDES,
    SQL_GET_SOLICITUD_BY_ID,
    SQL_GET_CALENDAR_SOLICITUDES,
    SQL_GET_SOLICITUDES_PENDIENTE_GERENTE,
    SQL_GET_SOLICITUDES_PENDIENTES_MISMO_TIPO,
    SQL_GET_SOLICITUDES_DEL_GRUPO,
    SQL_GET_SOLICITUDES_PARA_REPORTE,
    SQL_CHECK_HORARIO_OCUPADO,
    SQL_GET_FECHA_SOLICITUD,
    SQL_INSERT_SOLICITUD,
    SQL_UPDATE_REAGENDAR,
    SQL_UPDATE_COORDINAR,
    SQL_UPDATE_COORDINAR_GRUPO,
    SQL_UPDATE_APROBAR,
    SQL_UPDATE_RECHAZAR,
    SQL_UPDATE_COMPLETAR,
    SQL_UPDATE_PONER_PENDIENTE_GERENTE,
    SQL_UPDATE_APROBAR_GERENTE,
    SQL_UPDATE_RECHAZAR_GERENTE,
    SQL_UPDATE_ELIMINAR_SOLICITUD,
    SQL_INSERT_GRUPO,
    SQL_GET_ALL_CONFIG,
    SQL_GET_CONFIG_FOR_USER,
    SQL_UPSERT_CONFIG,
    SQL_DELETE_CONFIG,
    SQL_GET_ROLES_PARA_TIPO,
    SQL_GET_ADMINS_CON_TELEFONO,
    SQL_GET_TIPOS_SOLICITUD,
    SQL_GET_TIPO_FLAGS,
    SQL_GET_ALL_TIPO_FLAGS,
    SQL_UPSERT_TIPO_FLAGS,
    SQL_GET_VUELO_FLAGS,
    SQL_GET_VUELOS_PARA_AUTO_CONFIRMAR,
    SQL_GET_VUELOS_PARA_AUTO_LIQUIDAR,
    SQL_SET_COTIZACION_HOSPEDAJE,
    SQL_GET_ALL_ROL_FLAGS,
    SQL_GET_ROLES_AUTOAPROBAR_JEFE_VUELO,
    SQL_UPSERT_ROL_FLAGS,
    SQL_GET_USUARIOS_FOR_SELECT,
    SQL_GET_DEPARTAMENTOS,
    SQL_GET_USUARIO_DEPARTAMENTO,
    SQL_GET_EMAIL_BY_USUARIO_ID,
    SQL_GET_ROL_USUARIO,
    SQL_SET_PENALIZACION,
    SQL_CHECK_DUPLICADO_SOLICITUD,
    SQL_GET_CIUDAD_USUARIO,
    SQL_GET_JEFE_USUARIO,
    SQL_GET_JEFE_NOMBRE_BATCH,
    SQL_GET_USUARIO_JERARQUIA,
    SQL_UPDATE_TELEGRAM_CHAT_ID,
    SQL_GET_MOTORIZADOS_IDS_EMAILS,
    SQL_GET_MOTORIZADOS_EMAIL,
    SQL_GET_TELEGRAM_CHAT_IDS_PARA_TIPO,
    SQL_GET_MOTORIZADOS_TELEGRAM_STATUS,
    SQL_INSERT_SOLICITUD_LOG,
    SQL_GET_SOLICITUD_LOGS,
    SQL_INSERT_NOTIFY_INAPP,
    SQL_VUELO_APROBAR_JEFE_OK,
    SQL_VUELO_COTIZAR,
    SQL_VUELO_APROBAR_GG,
    SQL_VUELO_RECHAZAR_GG,
    SQL_VUELO_COMPLETAR,
    SQL_GET_MOTIVOS_VUELO,
    SQL_GET_SOLICITUDES_PENDIENTE_JEFE,
    SQL_GET_SOLICITUDES_PENDIENTE_GG_VUELO,
    SQL_UPDATE_COORDINAR_VUELO,
    SQL_REAGENDAR_VUELO_A_JEFE,
    SQL_GET_TIPOS_GASTO,
    SQL_GET_PRESUPUESTO_CC,
    SQL_UPSERT_PRESUPUESTO,
    SQL_GET_SALDO_PRESUPUESTO,
    SQL_GET_SALDO_ANUAL_PRESUPUESTO,
    SQL_ADD_EJECUTADO,
    SQL_VUELO_MARCAR_REALIZADO,
    SQL_VUELO_LIQUIDAR,
    SQL_EJECUTAR_PRESUPUESTO_VUELO,
    SQL_GET_EMPRESA_BY_USUARIO,
    SQL_GET_VUELOS_COORDINADAS_SIN_LIQUIDAR,
    SQL_VOUCHER_APROBAR_JEFE_OK,
    SQL_VOUCHER_ITEM_INSERT,
    SQL_VOUCHER_ITEMS_BY_SOLICITUD,
    SQL_VOUCHER_ITEM_BY_ID,
    SQL_VOUCHER_ITEM_BY_SECUENCIAL,
    SQL_VOUCHER_ITEM_SET_DATOS_REALES,
    SQL_VOUCHER_ITEM_ENTREGAR,
    SQL_VOUCHER_ITEM_CONFIRMAR,
    SQL_VOUCHER_ITEM_LIQUIDAR,
    SQL_VOUCHER_ITEM_NO_UTILIZADO,
    SQL_VOUCHER_ITEMS_PENDIENTES_RECORDATORIO_3D,
    SQL_VOUCHER_ITEMS_PENDIENTES_RECORDATORIO_6D,
    SQL_VOUCHER_ITEM_MARCAR_RECORDATORIO1,
    SQL_VOUCHER_ITEM_MARCAR_RECORDATORIO2,
    SQL_VOUCHER_SOLICITUD_A_CONFIRMACION,
    SQL_VOUCHER_SOLICITUD_A_LIQUIDACION,
    SQL_VOUCHER_SOLICITUD_COMPLETAR,
    SQL_VOUCHER_IND_KPI,
    SQL_VOUCHER_IND_POR_USUARIO,
    SQL_VOUCHER_IND_POR_DEPARTAMENTO,
    SQL_VOUCHER_IND_TENDENCIA_MENSUAL,
    SQL_VOUCHER_IND_TOP_RUTAS,
    SQL_VOUCHER_IND_PEND_CONFIRMACION_DETALLE,
)


# ──────────────────────────────────────────────
# Solicitudes – lectura
# ──────────────────────────────────────────────

def get_all_solicitudes(filters=None):
    filters = filters or {}
    conn = get_db()
    cur = conn.cursor()

    where = ["s.activo = 1"]
    params = []

    if filters.get("estado"):
        where.append("s.estado = ?")
        params.append(filters["estado"])
    if filters.get("tipo"):
        where.append("s.tipo = ?")
        params.append(filters["tipo"])
    if filters.get("area"):
        where.append("s.area_solicitante = ?")
        params.append(filters["area"])
    if filters.get("fecha_desde"):
        where.append("s.fecha >= ?")
        params.append(filters["fecha_desde"])
    if filters.get("fecha_hasta"):
        where.append("s.fecha <= ?")
        params.append(filters["fecha_hasta"])
    if filters.get("solicitante_id"):
        where.append("s.solicitante_id = ?")
        params.append(filters["solicitante_id"])

    sql = SQL_GET_ALL_SOLICITUDES.format(where=" AND ".join(where))
    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    return rows


def get_solicitudes_by_tipos(tipos, estados, filters=None):
    """Obtiene solicitudes de determinados tipos y estados (para coordinador/aprobador)."""
    if not tipos:
        return []
    filters = filters or {}
    conn = get_db()
    cur = conn.cursor()

    placeholders_t = ",".join(["?" for _ in tipos])
    placeholders_e = ",".join(["?" for _ in estados])
    params = list(tipos) + list(estados)

    where_extra = ""
    if filters.get("fecha_desde"):
        where_extra += " AND s.fecha >= ?"
        params.append(filters["fecha_desde"])
    if filters.get("fecha_hasta"):
        where_extra += " AND s.fecha <= ?"
        params.append(filters["fecha_hasta"])

    sql = SQL_GET_SOLICITUDES_BY_TIPOS.format(
        placeholders_t=placeholders_t,
        placeholders_e=placeholders_e,
        where_extra=where_extra,
    )
    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    return rows


def get_mis_solicitudes(solicitante_id, filters=None):
    filters = filters or {}
    conn = get_db()
    cur = conn.cursor()

    where = ["s.activo = 1", "s.solicitante_id = ?"]
    params = [solicitante_id]

    if filters.get("estado"):
        where.append("s.estado = ?")
        params.append(filters["estado"])
    if filters.get("tipo"):
        where.append("s.tipo = ?")
        params.append(filters["tipo"])
    if filters.get("fecha_desde"):
        where.append("s.fecha >= ?")
        params.append(filters["fecha_desde"])
    if filters.get("fecha_hasta"):
        where.append("s.fecha <= ?")
        params.append(filters["fecha_hasta"])

    sql = SQL_GET_MIS_SOLICITUDES.format(where=" AND ".join(where))
    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    return rows


def get_solicitud_by_id(solicitud_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_GET_SOLICITUD_BY_ID, (solicitud_id,))
    row = cur.fetchone()
    conn.close()
    return row


def get_calendar_solicitudes(fecha_desde, fecha_hasta):
    """Devuelve solicitudes aprobadas para mostrar en calendario."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_GET_CALENDAR_SOLICITUDES, (fecha_desde, fecha_hasta))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_solicitudes_pendiente_gerente_para_usuario(gerente_id: int, tipos, filters=None):
    if not tipos:
        return []
    filters = filters or {}
    conn = get_db()
    cur = conn.cursor()
    placeholders = ",".join(["?" for _ in tipos])
    params = list(tipos) + [gerente_id]
    where_extra = ""
    if filters.get("fecha_desde"):
        where_extra += " AND s.fecha >= ?"
        params.append(filters["fecha_desde"])
    if filters.get("fecha_hasta"):
        where_extra += " AND s.fecha <= ?"
        params.append(filters["fecha_hasta"])
    sql = SQL_GET_SOLICITUDES_PENDIENTE_GERENTE.format(
        placeholders=placeholders,
        where_extra=where_extra,
    )
    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    return rows


def get_solicitudes_pendientes_mismo_tipo(tipo: str, exclude_id: int):
    """Devuelve otras solicitudes PENDIENTE_COORDINACION del mismo tipo."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_GET_SOLICITUDES_PENDIENTES_MISMO_TIPO, (tipo, exclude_id))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_solicitudes_del_grupo(grupo_id: int):
    """Devuelve todas las solicitudes activas de un grupo de coordinación."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_GET_SOLICITUDES_DEL_GRUPO, (grupo_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_solicitudes_para_reporte(filters=None, usuario_id=None, ctx=None):
    """
    ctx (de get_user_context) acota qué filas puede descargar cada usuario:
    - admin: todas.
    - coordinador/aprobador/motorizado/gerente de presupuesto de un tipo: todas
      las solicitudes de ese tipo (no solo las pendientes de su acción).
    - usuario normal: solo sus propias solicitudes.
    """
    filters = filters or {}
    conn = get_db()
    cur = conn.cursor()
    where = ["s.activo = 1"]
    params = []
    if filters.get("estado"):
        where.append("s.estado = ?")
        params.append(filters["estado"])
    if filters.get("tipo"):
        where.append("s.tipo = ?")
        params.append(filters["tipo"])
    if filters.get("fecha_desde"):
        where.append("s.fecha >= ?")
        params.append(filters["fecha_desde"])
    if filters.get("fecha_hasta"):
        where.append("s.fecha <= ?")
        params.append(filters["fecha_hasta"])

    if ctx is not None and not ctx.get("es_admin"):
        tipos_gestionados = list(dict.fromkeys(
            ctx.get("tipos_coordinador", []) + ctx.get("tipos_aprobador", []) +
            ctx.get("tipos_motorizado", [])  + ctx.get("tipos_gg_vuelo", [])
        ))
        scope_parts = ["s.solicitante_id = ?"]
        scope_params = [usuario_id]
        if tipos_gestionados:
            placeholders = ",".join("?" * len(tipos_gestionados))
            scope_parts.append(f"s.tipo IN ({placeholders})")
            scope_params += tipos_gestionados
        where.append("(" + " OR ".join(scope_parts) + ")")
        params += scope_params

    sql = SQL_GET_SOLICITUDES_PARA_REPORTE.format(where=" AND ".join(where))
    cur.execute(sql, params)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    conn.close()
    return cols, rows


def check_horario_ocupado(tipo, fecha, hora_inicio, hora_fin, exclude_id=None):
    conn = get_db()
    cur = conn.cursor()
    params = [tipo, fecha]
    excl = " AND id != ?" if exclude_id else ""
    if exclude_id:
        params.append(exclude_id)
    params += [hora_fin, hora_inicio]
    sql = SQL_CHECK_HORARIO_OCUPADO.format(excl=excl)
    cur.execute(sql, params)
    row = cur.fetchone()
    conn.close()
    return row is not None


# ──────────────────────────────────────────────
# Solicitudes – escritura
# ──────────────────────────────────────────────

def crear_solicitud(data):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_INSERT_SOLICITUD, (
        data["tipo"], data["area_solicitante"], data["descripcion"],
        data["lugar_destino"], data.get("detalle_direccion", ""),
        data.get("contacto", ""),
        data.get("prioridad", "Normal"), data["fecha"],
        data.get("estado", "PENDIENTE_COORDINACION"),
        data["solicitante_id"], data["solicitante_nombre"],
        data.get("ciudad", ""),
        data.get("presupuesto_base_cero"),
        data.get("fecha_retorno"),
        data.get("punto_salida"),
        data.get("punto_destino"),
        data.get("requiere_hospedaje", 0),
        data.get("orden_servicio"),
        data.get("centro_costo_id"),
        data.get("requiere_aprobacion_presupuesto", 0),
        data.get("gerente_id"),
        data.get("gerente_nombre"),
        data.get("motivo_vuelo"),
        data.get("numero_vouchers"),
    ))
    row = cur.fetchone()
    conn.commit()
    sid = row[0] if row else None
    if sid:
        insert_solicitud_log(sid, "CREADA", data["solicitante_id"],
                             data["solicitante_nombre"],
                             f"Solicitud creada. Tipo: {data['tipo']} · Fecha: {data['fecha']}")
    return sid


def reagendar_solicitud(solicitud_id: int, nueva_fecha: str,
                        coordinador_id: int, coordinador_nombre: str, motivo: str,
                        nuevo_estado: str = "PENDIENTE_COORDINACION"):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_GET_FECHA_SOLICITUD, (solicitud_id,))
    row_prev = cur.fetchone()
    fecha_anterior = str(row_prev[0]) if row_prev else "—"
    cur.execute(SQL_UPDATE_REAGENDAR, (nueva_fecha, nuevo_estado, solicitud_id))
    conn.commit()
    conn.close()
    insert_solicitud_log(
        solicitud_id, "REAGENDADA", coordinador_id, coordinador_nombre,
        f"Fecha anterior: {fecha_anterior} → Nueva fecha: {nueva_fecha}. Motivo: {motivo or '—'}"
    )


def aprobar_jefe_vuelo(solicitud_id: int, jefe_id: int, jefe_nombre: str, obs: str) -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_VUELO_APROBAR_JEFE_OK, (jefe_id, jefe_nombre, obs or "", solicitud_id))
    conn.commit()
    insert_solicitud_log(solicitud_id, "APROBADA_JEFE", jefe_id, jefe_nombre,
                         "Jefe aprueba vuelo. Pasa al coordinador para cotizar.")


def rechazar_vuelo(solicitud_id: int, usuario_id: int, usuario_nombre: str, obs: str) -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_UPDATE_RECHAZAR, (usuario_id, usuario_nombre, obs or "", solicitud_id))
    conn.commit()
    insert_solicitud_log(solicitud_id, "RECHAZADA", usuario_id, usuario_nombre,
                         f"Solicitud rechazada. Motivo: {obs or '—'}")


def cotizar_vuelo(solicitud_id: int, coordinador_id: int, coordinador_nombre: str,
                  valor_cotizado: str, obs: str = "") -> None:
    """Coordinador ingresa el valor cotizado del pasaje → pasa a aprobación GG."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_VUELO_COTIZAR,
               (valor_cotizado, obs or "", coordinador_id, coordinador_nombre, solicitud_id))
    conn.commit()
    insert_solicitud_log(solicitud_id, "COTIZADA", coordinador_id, coordinador_nombre,
                         f"Coordinador cotiza el pasaje: {valor_cotizado}. Pasa a aprobación del Gerente General.")


def aprobar_gg_vuelo(solicitud_id: int, gg_id: int, gg_nombre: str, obs: str) -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_VUELO_APROBAR_GG, (gg_id, gg_nombre, obs or "", solicitud_id))
    conn.commit()
    insert_solicitud_log(solicitud_id, "APROBADA_GG", gg_id, gg_nombre,
                         f"GG aprueba la cotización del vuelo. Pasa al coordinador para info del vuelo. {obs or ''}")


def rechazar_gg_vuelo(solicitud_id: int, gg_id: int, gg_nombre: str, obs: str) -> None:
    """GG rechaza la cotización → vuelve al coordinador para recotizar (no es rechazo final)."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_VUELO_RECHAZAR_GG, (gg_id, gg_nombre, obs or "", solicitud_id))
    conn.commit()
    insert_solicitud_log(solicitud_id, "COTIZACION_RECHAZADA_GG", gg_id, gg_nombre,
                         f"GG rechaza la cotización del vuelo. Vuelve al coordinador. Motivo: {obs or '—'}")


def completar_vuelo(solicitud_id: int, coordinador_id: int, coordinador_nombre: str,
                    obs: str, hora_inicio: str = None, hora_fin: str = None) -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_VUELO_COMPLETAR,
                (coordinador_id, coordinador_nombre,
                 hora_inicio or None, hora_fin or None,
                 obs or "", solicitud_id))
    conn.commit()
    insert_solicitud_log(solicitud_id, "COMPLETADA", coordinador_id, coordinador_nombre,
                         f"Coordinador registra gestión. Obs: {obs or '—'}")


def get_cc_nombre(cc_id: int) -> str | None:
    if not cc_id:
        return None
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT nombre, valor FROM param_values WHERE id = ?", (cc_id,))
    row = cur.fetchone()
    if not row:
        return None
    return f"{row[1] or ''} — {row[0]}" if row[1] else row[0]


def get_empresa_by_usuario(usuario_id: int) -> int | None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_GET_EMPRESA_BY_USUARIO, (usuario_id,))
    row = cur.fetchone()
    return row[0] if row else None


def marcar_realizado_vuelo(solicitud_id: int, usuario_id: int, usuario_nombre: str) -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_VUELO_MARCAR_REALIZADO, (solicitud_id,))
    conn.commit()
    insert_solicitud_log(solicitud_id, "PENDIENTE_LIQUIDACION", usuario_id, usuario_nombre,
                         "Solicitante confirmó realización del vuelo. Pendiente de liquidación de costos.")


def liquidar_vuelo(solicitud_id: int, liquidador_id: int, liquidador_nombre: str,
                   costo_real: float, notas: str) -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_VUELO_LIQUIDAR, (costo_real, notas or "", solicitud_id))
    conn.commit()
    insert_solicitud_log(solicitud_id, "COMPLETADA", liquidador_id, liquidador_nombre,
                         f"Liquidación de vuelo. Costo: ${costo_real:.2f}. {notas or ''}")


def deducir_presupuesto_vuelo(empresa_id: int, cc_id: int, tipo_gasto: str,
                               anio: int, mes: int, costo: float) -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_EJECUTAR_PRESUPUESTO_VUELO,
                (empresa_id, cc_id, tipo_gasto, anio, mes,
                 costo,
                 empresa_id, cc_id, tipo_gasto, anio, mes,
                 empresa_id, cc_id, tipo_gasto, anio, mes, costo))
    conn.commit()


def aprobar_jefe_voucher(solicitud_id: int, jefe_id: int, jefe_nombre: str, obs: str) -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_VOUCHER_APROBAR_JEFE_OK, (jefe_id, jefe_nombre, obs or "", solicitud_id))
    conn.commit()
    insert_solicitud_log(solicitud_id, "APROBADA_JEFE", jefe_id, jefe_nombre,
                         "Jefe aprueba voucher. El coordinador debe entregar los vouchers con su secuencial.")


def rechazar_jefe_voucher(solicitud_id: int, usuario_id: int, usuario_nombre: str, obs: str) -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_UPDATE_RECHAZAR, (usuario_id, usuario_nombre, obs or "", solicitud_id))
    conn.commit()
    insert_solicitud_log(solicitud_id, "RECHAZADA", usuario_id, usuario_nombre,
                         f"Solicitud de voucher rechazada. Motivo: {obs or '—'}")


def crear_voucher_items(solicitud_id: int, vouchers: list[dict]) -> list[int]:
    """Crea un item por cada voucher solicitado (numero 1..N) con su origen/destino.

    `vouchers` es una lista de dicts [{"origen": str, "destino": str}, ...],
    en el orden en que deben numerarse (1..N).
    """
    conn = get_db()
    cur = conn.cursor()
    ids = []
    for n, v in enumerate(vouchers or [], start=1):
        cur.execute(SQL_VOUCHER_ITEM_INSERT, (
            solicitud_id, n,
            (v.get("origen") or "").strip(),
            (v.get("destino") or "").strip(),
        ))
        row = cur.fetchone()
        if row:
            ids.append(row[0])
    conn.commit()
    return ids


def get_voucher_items(solicitud_id: int) -> list:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_VOUCHER_ITEMS_BY_SOLICITUD, (solicitud_id,))
    return [dict(r) for r in cur.fetchall()]


def get_voucher_item_by_id(item_id: int) -> dict | None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_VOUCHER_ITEM_BY_ID, (item_id,))
    row = cur.fetchone()
    return dict(row) if row else None


def get_voucher_item_by_secuencial(secuencial: str) -> dict | None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_VOUCHER_ITEM_BY_SECUENCIAL, (secuencial,))
    row = cur.fetchone()
    return dict(row) if row else None


def set_voucher_item_datos_reales(item_id: int, origen_real: str, destino_real: str) -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_VOUCHER_ITEM_SET_DATOS_REALES, (origen_real or "", destino_real or "", item_id))
    conn.commit()


def entregar_voucher_items(solicitud_id: int, secuenciales: dict,
                            coordinador_id: int, coordinador_nombre: str) -> None:
    """secuenciales: {item_id: secuencial}. Registra el secuencial de cada item y
    pasa la solicitud a PENDIENTE_CONFIRMACION_VOUCHER."""
    conn = get_db()
    cur = conn.cursor()
    for item_id, secuencial in secuenciales.items():
        cur.execute(SQL_VOUCHER_ITEM_ENTREGAR,
                   (secuencial, coordinador_id, coordinador_nombre, item_id))
    cur.execute(SQL_VOUCHER_SOLICITUD_A_CONFIRMACION,
               (coordinador_id, coordinador_nombre, solicitud_id))
    conn.commit()
    insert_solicitud_log(
        solicitud_id, "PENDIENTE_CONFIRMACION_VOUCHER", coordinador_id, coordinador_nombre,
        f"Coordinador entregó {len(secuenciales)} voucher(s) con sus secuenciales."
    )


def confirmar_voucher_item(item_id: int, solicitud_id: int, usuario_id: int, usuario_nombre: str,
                           adjunto_original: str, adjunto_guardado: str, adjunto_tamano: int,
                           observacion: str) -> bool:
    """Confirma un item individual. Si con este ya quedan todos confirmados,
    pasa la solicitud a PENDIENTE_LIQUIDACION_VOUCHER. Devuelve True si la
    solicitud completa quedó lista para liquidar."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_VOUCHER_ITEM_CONFIRMAR,
               (adjunto_original, adjunto_guardado, adjunto_tamano, observacion or "", item_id))
    conn.commit()
    insert_solicitud_log(solicitud_id, "VOUCHER_ITEM_CONFIRMADO", usuario_id, usuario_nombre,
                         f"Solicitante confirmó voucher item #{item_id} (secuencial adjunto).")
    # insert_solicitud_log cierra la conexión de g.db al terminar: hay que
    # reobtenerla (get_db() reconecta sola) antes de seguir usando cur/conn.
    conn = get_db()
    cur = conn.cursor()

    items = get_voucher_items(solicitud_id)
    todos_confirmados = bool(items) and all(i.get("confirmado_usuario") for i in items)
    if todos_confirmados:
        cur.execute(SQL_VOUCHER_SOLICITUD_A_LIQUIDACION, (solicitud_id,))
        conn.commit()
        insert_solicitud_log(solicitud_id, "PENDIENTE_LIQUIDACION_VOUCHER", usuario_id, usuario_nombre,
                             "Todos los vouchers fueron confirmados. Pendiente liquidación del coordinador.")
    return todos_confirmados


def marcar_voucher_no_utilizado(item_id: int, solicitud_id: int, usuario_id: int,
                                usuario_nombre: str, observacion: str) -> dict:
    """El solicitante marca un voucher como no utilizado: cuenta como
    confirmado (con costo $0, sin liquidación pendiente). Si con este ya
    quedan todos confirmados, pasa a PENDIENTE_LIQUIDACION_VOUCHER; si además
    ya estaban todos con costo (p.ej. todos no utilizados), completa la
    solicitud directamente. Devuelve {todos_confirmados, completada, costo_total}."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_VOUCHER_ITEM_NO_UTILIZADO, (observacion or "", item_id))
    conn.commit()
    insert_solicitud_log(solicitud_id, "VOUCHER_ITEM_NO_UTILIZADO", usuario_id, usuario_nombre,
                         f"Solicitante marcó el voucher item #{item_id} como no utilizado. "
                         f"Motivo: {observacion or '—'}")
    # insert_solicitud_log cierra la conexión de g.db al terminar: hay que
    # reobtenerla (get_db() reconecta sola) antes de seguir usando cur/conn.
    conn = get_db()
    cur = conn.cursor()

    items = get_voucher_items(solicitud_id)
    todos_confirmados = bool(items) and all(i.get("confirmado_usuario") for i in items)
    if not todos_confirmados:
        return {"todos_confirmados": False, "completada": False, "costo_total": 0.0}

    cur.execute(SQL_VOUCHER_SOLICITUD_A_LIQUIDACION, (solicitud_id,))
    conn.commit()
    insert_solicitud_log(solicitud_id, "PENDIENTE_LIQUIDACION_VOUCHER", usuario_id, usuario_nombre,
                         "Todos los vouchers fueron confirmados. Pendiente liquidación del coordinador.")
    conn = get_db()
    cur = conn.cursor()

    todos_liquidados = all(i.get("costo") is not None for i in items)
    if not todos_liquidados:
        return {"todos_confirmados": True, "completada": False, "costo_total": 0.0}

    costo_total = round(sum(float(i["costo"]) for i in items), 2)
    cur.execute(SQL_VOUCHER_SOLICITUD_COMPLETAR, (costo_total, solicitud_id))
    conn.commit()
    insert_solicitud_log(solicitud_id, "COMPLETADA", usuario_id, usuario_nombre,
                         f"Todos los vouchers quedaron confirmados (ninguno requería liquidación). "
                         f"Costo total: ${costo_total:.2f}")
    return {"todos_confirmados": True, "completada": True, "costo_total": costo_total}


def liquidar_voucher_item(item_id: int, solicitud_id: int, coordinador_id: int,
                          coordinador_nombre: str, costo: float) -> tuple[bool, float]:
    """Liquida un item individual. Si con este ya quedan todos liquidados,
    completa la solicitud y devuelve (True, costo_total_sumado)."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_VOUCHER_ITEM_LIQUIDAR, (costo, coordinador_id, coordinador_nombre, item_id))
    conn.commit()
    insert_solicitud_log(solicitud_id, "VOUCHER_ITEM_LIQUIDADO", coordinador_id, coordinador_nombre,
                         f"Coordinador liquidó voucher item #{item_id}: ${costo:.2f}")
    # insert_solicitud_log cierra la conexión de g.db al terminar: hay que
    # reobtenerla (get_db() reconecta sola) antes de seguir usando cur/conn.
    conn = get_db()
    cur = conn.cursor()

    items = get_voucher_items(solicitud_id)
    todos_liquidados = bool(items) and all(i.get("costo") is not None for i in items)
    if not todos_liquidados:
        return False, 0.0

    costo_total = round(sum(float(i["costo"]) for i in items), 2)
    cur.execute(SQL_VOUCHER_SOLICITUD_COMPLETAR, (costo_total, solicitud_id))
    conn.commit()
    insert_solicitud_log(solicitud_id, "COMPLETADA", coordinador_id, coordinador_nombre,
                         f"Todos los vouchers liquidados. Costo total: ${costo_total:.2f}")
    return True, costo_total


def get_voucher_items_pendientes_recordatorio_3d() -> list[dict]:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_VOUCHER_ITEMS_PENDIENTES_RECORDATORIO_3D)
    return [dict(r) for r in cur.fetchall()]


def get_voucher_items_pendientes_recordatorio_6d() -> list[dict]:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_VOUCHER_ITEMS_PENDIENTES_RECORDATORIO_6D)
    return [dict(r) for r in cur.fetchall()]


def marcar_voucher_recordatorio1_enviado(item_id: int) -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_VOUCHER_ITEM_MARCAR_RECORDATORIO1, (item_id,))
    conn.commit()


def marcar_voucher_recordatorio2_enviado(item_id: int) -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_VOUCHER_ITEM_MARCAR_RECORDATORIO2, (item_id,))
    conn.commit()


def get_vuelos_coordinadas_sin_liquidar() -> list:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_GET_VUELOS_COORDINADAS_SIN_LIQUIDAR)
    return cur.fetchall()


def get_solicitudes_pendiente_jefe(jefe_id: int, filters: dict | None = None) -> list:
    filters = filters or {}
    where_extra = ""
    params_extra = []
    if filters.get("fecha_desde"):
        where_extra += " AND s.fecha >= ?"
        params_extra.append(filters["fecha_desde"])
    if filters.get("fecha_hasta"):
        where_extra += " AND s.fecha <= ?"
        params_extra.append(filters["fecha_hasta"])
    sql = SQL_GET_SOLICITUDES_PENDIENTE_JEFE.format(where_extra=where_extra)
    conn = get_db()
    cur = conn.cursor()
    cur.execute(sql, [jefe_id] + params_extra)
    return cur.fetchall()


def get_solicitudes_pendiente_gg_vuelo(tipos: list, filters: dict | None = None) -> list:
    if not tipos:
        return []
    filters = filters or {}
    where_extra = ""
    params_extra = []
    if filters.get("fecha_desde"):
        where_extra += " AND s.fecha >= ?"
        params_extra.append(filters["fecha_desde"])
    if filters.get("fecha_hasta"):
        where_extra += " AND s.fecha <= ?"
        params_extra.append(filters["fecha_hasta"])
    placeholders = ",".join(["?"] * len(tipos))
    sql = SQL_GET_SOLICITUDES_PENDIENTE_GG_VUELO.format(
        placeholders=placeholders, where_extra=where_extra
    )
    conn = get_db()
    cur = conn.cursor()
    cur.execute(sql, tipos + params_extra)
    return cur.fetchall()


def coordinar_solicitud(solicitud_id, coordinador_id, coordinador_nombre,
                        hora_inicio, hora_fin, observacion):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_UPDATE_COORDINAR,
                (hora_inicio, hora_fin, observacion,
                 coordinador_id, coordinador_nombre, solicitud_id))
    conn.commit()
    conn.close()
    insert_solicitud_log(solicitud_id, "COORDINADA", coordinador_id, coordinador_nombre,
                         f"Horario asignado: {hora_inicio} – {hora_fin}. Obs: {observacion or '—'}")


def coordinar_vuelo(solicitud_id: int, coordinador_id: int, coordinador_nombre: str,
                    hora_inicio: str, hora_fin: str,
                    datos_ticket: str, datos_hotel: str, observacion: str) -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_UPDATE_COORDINAR_VUELO,
                (hora_inicio, hora_fin,
                 datos_ticket or None, datos_hotel or None, observacion or None,
                 coordinador_id, coordinador_nombre, solicitud_id))
    conn.commit()
    insert_solicitud_log(solicitud_id, "COORDINADA_VUELO", coordinador_id, coordinador_nombre,
                         f"Horario: {hora_inicio}–{hora_fin}. "
                         f"Ticket: {datos_ticket[:80] if datos_ticket else '—'}. "
                         f"Hotel: {'Sí' if datos_hotel else 'No'}.")


def reagendar_vuelo_a_jefe(solicitud_id: int, nueva_fecha: str, nueva_fecha_retorno: str | None,
                            coordinador_id: int, coordinador_nombre: str, motivo: str) -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_GET_FECHA_SOLICITUD, (solicitud_id,))
    row_prev = cur.fetchone()
    fecha_anterior = str(row_prev[0]) if row_prev else "—"
    cur.execute(SQL_REAGENDAR_VUELO_A_JEFE, (nueva_fecha, nueva_fecha_retorno, solicitud_id))
    conn.commit()
    insert_solicitud_log(solicitud_id, "REPROGRAMADA_VUELO", coordinador_id, coordinador_nombre,
                         f"Fecha anterior: {fecha_anterior} → Nueva: {nueva_fecha}"
                         f"{' / regreso ' + nueva_fecha_retorno if nueva_fecha_retorno else ''}. "
                         f"Motivo: {motivo or '—'}. Vuelve a aprobación del jefe.")


def crear_grupo_coordinacion(tipo: str, fecha: str, hora_inicio: str,
                              hora_fin: str, coordinador_id: int,
                              coordinador_nombre: str, observacion: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_INSERT_GRUPO,
                (tipo, fecha, hora_inicio, hora_fin,
                 coordinador_id, coordinador_nombre, observacion))
    row = cur.fetchone()
    conn.commit()
    conn.close()
    return row[0] if row else None


def coordinar_solicitudes_grupo(ids: list, grupo_id: int, coordinador_id: int,
                                 coordinador_nombre: str, hora_inicio: str,
                                 hora_fin: str, observacion: str):
    conn = get_db()
    cur = conn.cursor()
    for sid in ids:
        cur.execute(SQL_UPDATE_COORDINAR_GRUPO,
                    (hora_inicio, hora_fin, observacion,
                     coordinador_id, coordinador_nombre,
                     grupo_id, sid))
    conn.commit()
    conn.close()
    n = len(ids)
    for sid in ids:
        insert_solicitud_log(
            sid, "COORDINADA", coordinador_id, coordinador_nombre,
            f"Horario asignado: {hora_inicio} – {hora_fin}. "
            f"Grupo de {n} solicitudes (grupo #{grupo_id}). Obs: {observacion or '—'}"
        )


def aprobar_solicitud(solicitud_id, aprobador_id, aprobador_nombre, observacion):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_UPDATE_APROBAR,
                (aprobador_id, aprobador_nombre, observacion, solicitud_id))
    conn.commit()
    conn.close()
    insert_solicitud_log(solicitud_id, "APROBADA", aprobador_id, aprobador_nombre,
                         f"Aprobada. Obs: {observacion or '—'}")


def rechazar_solicitud(solicitud_id, aprobador_id, aprobador_nombre, observacion):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_UPDATE_RECHAZAR,
                (aprobador_id, aprobador_nombre, observacion, solicitud_id))
    conn.commit()
    conn.close()
    insert_solicitud_log(solicitud_id, "RECHAZADA", aprobador_id, aprobador_nombre,
                         f"Rechazada. Motivo: {observacion or '—'}")


def completar_solicitud(solicitud_id, usuario_id: int = None, usuario_nombre: str = ""):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_UPDATE_COMPLETAR, (solicitud_id,))
    conn.commit()
    conn.close()
    insert_solicitud_log(solicitud_id, "COMPLETADA", usuario_id, usuario_nombre,
                         "Marcada como completada.")


def poner_pendiente_gerente(solicitud_id: int, gerente_id: int, gerente_nombre: str) -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_UPDATE_PONER_PENDIENTE_GERENTE,
                (gerente_id, gerente_nombre, solicitud_id))
    conn.commit()
    conn.close()


def aprobar_por_gerente(solicitud_id: int, gerente_id: int,
                        gerente_nombre: str, observacion: str = "") -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_UPDATE_APROBAR_GERENTE,
                (observacion, observacion, observacion, solicitud_id))
    conn.commit()
    conn.close()
    insert_solicitud_log(solicitud_id, "APROBADA_GERENTE", gerente_id, gerente_nombre,
                         f"Aprobación gerencial. Obs: {observacion or '—'}")


def rechazar_por_gerente(solicitud_id: int, gerente_id: int,
                          gerente_nombre: str, observacion: str) -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_UPDATE_RECHAZAR_GERENTE,
                (gerente_id, gerente_nombre, observacion, solicitud_id))
    conn.commit()
    conn.close()
    insert_solicitud_log(solicitud_id, "RECHAZADA_GERENTE", gerente_id, gerente_nombre,
                         f"Rechazada por gerente. Motivo: {observacion or '—'}")


def delete_solicitud(solicitud_id: int,
                     eliminado_por_id=None,
                     eliminado_por_nombre: str = "") -> None:
    """
    Eliminación lógica: marca activo=0 y guarda quién/cuándo eliminó.
    El registro permanece en la base para auditoría.
    """
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_UPDATE_ELIMINAR_SOLICITUD,
                (eliminado_por_id, eliminado_por_nombre or "", solicitud_id))
    conn.commit()
    conn.close()


# ──────────────────────────────────────────────
# Configuración coordinadores / aprobadores
# ──────────────────────────────────────────────

def get_all_config():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_GET_ALL_CONFIG)
    rows = cur.fetchall()
    conn.close()
    return rows


def get_config_for_user(usuario_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_GET_CONFIG_FOR_USER, (usuario_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def insert_config(tipo, usuario_id, usuario_nombre, rol_config):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_UPSERT_CONFIG,
                (tipo, usuario_id, rol_config,
                 tipo, usuario_id, usuario_nombre, rol_config,
                 usuario_nombre, tipo, usuario_id, rol_config))
    conn.commit()
    conn.close()


def delete_config(config_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_DELETE_CONFIG, (config_id,))
    conn.commit()
    conn.close()


def get_roles_para_tipo(tipo: str) -> dict:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_GET_ROLES_PARA_TIPO, (tipo,))
    rows = cur.fetchall()
    conn.close()
    coordinadores, aprobadores, motorizados, gerentes_presupuesto = [], [], [], []
    for r in rows:
        entry = {"id": r[0], "nombre": r[1], "email": r[3], "telefono": r[4]}
        if   r[2] == ROL_COORDINADOR:         coordinadores.append(entry)
        elif r[2] == ROL_APROBADOR:           aprobadores.append(entry)
        elif r[2] == ROL_MOTORIZADO:          motorizados.append(entry)
        elif r[2] == ROL_GERENTE_PRESUPUESTO: gerentes_presupuesto.append(entry)
    return {"coordinadores":        coordinadores,
            "aprobadores":          aprobadores,
            "motorizados":          motorizados,
            "gerentes_presupuesto": gerentes_presupuesto}


def get_coordinadores_aprobadores_para_tipo(tipo):
    """Compatibilidad: retorna (coordinadores, aprobadores)."""
    d = get_roles_para_tipo(tipo)
    return d["coordinadores"], d["aprobadores"]


def get_motorizados_para_tipo(tipo: str):
    return get_roles_para_tipo(tipo)["motorizados"]


def get_admins_con_telefono() -> list:
    """Usuarios con rol admin, activos, con teléfono registrado (para copia WhatsApp)."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(SQL_GET_ADMINS_CON_TELEFONO)
        rows = cur.fetchall()
        conn.close()
        return [{"id": r[0], "nombre": r[1], "telefono": r[2]} for r in rows]
    except Exception:
        return []


def get_gerentes_presupuesto_para_tipo(tipo: str):
    """Usuarios configurados con rol GERENTE_PRESUPUESTO para el tipo (ej. Vuelo)."""
    return get_roles_para_tipo(tipo)["gerentes_presupuesto"]


# ──────────────────────────────────────────────
# Tipos de solicitud y flags
# ──────────────────────────────────────────────

def get_tipos_solicitud():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_GET_TIPOS_SOLICITUD, (PARAM_GROUP_TIPOS,))
    rows = cur.fetchall()
    conn.close()
    tipos = [r[0] for r in rows if r[0]]
    return tipos if tipos else list(TIPOS_SOLICITUD_DEFAULT)


def get_motivos_vuelo():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_GET_MOTIVOS_VUELO, (PARAM_GROUP_MOTIVOS_VUELO,))
    rows = cur.fetchall()
    conn.close()
    motivos = [r[0] for r in rows if r[0]]
    return motivos if motivos else list(MOTIVOS_VUELO_DEFAULT)


def get_tipo_flags(tipo: str) -> dict:
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(SQL_GET_TIPO_FLAGS, (tipo,))
        row = cur.fetchone()
        conn.close()
        if row:
            return {
                "requiere_aprobacion_gerente": bool(row[0]),
                "auto_confirmar_vuelo":        bool(row[1]),
                "auto_liquidar_vuelo":         bool(row[2]),
            }
    except Exception:
        pass
    return {"requiere_aprobacion_gerente": False, "auto_confirmar_vuelo": False, "auto_liquidar_vuelo": False}


def get_all_tipo_flags() -> dict:
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(SQL_GET_ALL_TIPO_FLAGS)
        rows = cur.fetchall()
        conn.close()
        return {r[0]: {
            "requiere_aprobacion_gerente": bool(r[1]),
            "auto_confirmar_vuelo":        bool(r[2]),
            "auto_liquidar_vuelo":         bool(r[3]),
        } for r in rows}
    except Exception:
        return {}


def set_tipo_flags(tipo: str, requiere_aprobacion_gerente: bool,
                   auto_confirmar_vuelo: bool = False,
                   auto_liquidar_vuelo: bool = False) -> None:
    conn = get_db()
    cur = conn.cursor()
    b = lambda v: 1 if v else 0
    cur.execute(SQL_UPSERT_TIPO_FLAGS, (
        tipo, b(requiere_aprobacion_gerente), b(auto_confirmar_vuelo), b(auto_liquidar_vuelo), tipo,
        tipo, b(requiere_aprobacion_gerente), b(auto_confirmar_vuelo), b(auto_liquidar_vuelo),
    ))
    conn.commit()
    conn.close()


def get_vuelo_flags() -> dict:
    """Flags globales del tipo Vuelo (auto_confirmar, auto_liquidar)."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(SQL_GET_VUELO_FLAGS)
        row = cur.fetchone()
        conn.close()
        if row:
            return {"auto_confirmar_vuelo": bool(row[0]), "auto_liquidar_vuelo": bool(row[1])}
    except Exception:
        pass
    return {"auto_confirmar_vuelo": False, "auto_liquidar_vuelo": False}


def get_vuelos_para_auto_confirmar() -> list:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_GET_VUELOS_PARA_AUTO_CONFIRMAR)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_vuelos_para_auto_liquidar() -> list:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_GET_VUELOS_PARA_AUTO_LIQUIDAR)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def set_cotizacion_hospedaje(solicitud_id: int, valor: float) -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_SET_COTIZACION_HOSPEDAJE, (valor, solicitud_id))
    conn.commit()


def get_all_rol_flags() -> dict:
    """rol -> True/False (autoaprueba_jefe_vuelo)."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(SQL_GET_ALL_ROL_FLAGS)
        rows = cur.fetchall()
        conn.close()
        return {r[0]: bool(r[1]) for r in rows}
    except Exception:
        return {}


def get_roles_autoaprobar_jefe_vuelo() -> list:
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(SQL_GET_ROLES_AUTOAPROBAR_JEFE_VUELO)
        rows = cur.fetchall()
        conn.close()
        return [r[0] for r in rows]
    except Exception:
        return []


def set_rol_flags(rol: str, autoaprueba_jefe_vuelo: bool) -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_UPSERT_ROL_FLAGS,
                (rol, 1 if autoaprueba_jefe_vuelo else 0, rol,
                 rol, 1 if autoaprueba_jefe_vuelo else 0))
    conn.commit()
    conn.close()


# ──────────────────────────────────────────────
# Usuarios y catálogos
# ──────────────────────────────────────────────

def get_usuarios_for_select():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_GET_USUARIOS_FOR_SELECT)
    rows = cur.fetchall()
    conn.close()
    return rows


def get_departamentos():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_GET_DEPARTAMENTOS)
    rows = cur.fetchall()
    conn.close()
    return rows


def get_usuario_departamento(usuario_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_GET_USUARIO_DEPARTAMENTO, (usuario_id,))
    row = cur.fetchone()
    conn.close()
    if row and row[0]:
        return {"dept_id": row[0], "dept_nombre": row[1] or ""}
    return {"dept_id": None, "dept_nombre": ""}


def get_email_by_usuario_id(usuario_id):
    if not usuario_id:
        return None
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_GET_EMAIL_BY_USUARIO_ID, (usuario_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def set_penalizacion(solicitud_id: int, penalizacion: float) -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_SET_PENALIZACION, (penalizacion, solicitud_id))
    conn.commit()


def check_solicitud_duplicada(usuario_id: int, tipo: str, fecha: str, fecha_retorno: str | None):
    """Devuelve el dict de la solicitud conflictiva o None si no hay duplicado."""
    fecha_fin = fecha_retorno or fecha
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_CHECK_DUPLICADO_SOLICITUD, (usuario_id, tipo, fecha_fin, fecha))
    row = cur.fetchone()
    return dict(row) if row else None


def get_rol_usuario(usuario_id: int) -> str | None:
    if not usuario_id:
        return None
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_GET_ROL_USUARIO, (usuario_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def get_ciudad_usuario(usuario_id: int) -> str:
    if not usuario_id:
        return ""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(SQL_GET_CIUDAD_USUARIO, (usuario_id,))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else ""
    except Exception:
        return ""


def get_gerente_del_usuario(usuario_id: int):
    """Devuelve el jefe directo (jefe_id) del usuario, sin importar su rol."""
    if not usuario_id:
        return None
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_GET_JEFE_USUARIO, (usuario_id,))
    row = cur.fetchone()
    if not row or not row[0]:
        return None
    jefe_id = row[0]
    cur.execute(SQL_GET_USUARIO_JERARQUIA, (jefe_id,))
    j = cur.fetchone()
    if not j:
        return None
    return {"id": j[0], "nombre": j[1], "email": j[2]}


def get_motorizados_ids_and_emails():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_GET_MOTORIZADOS_IDS_EMAILS)
    rows = cur.fetchall()
    conn.close()
    return [{"id": r[0], "email": r[1]} for r in rows]


def get_motorizados_email():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_GET_MOTORIZADOS_EMAIL)
    rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows if r[0]]


def update_usuario_telegram_chat_id(usuario_id: int, chat_id: str) -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_UPDATE_TELEGRAM_CHAT_ID, (chat_id or None, usuario_id))
    conn.commit()
    conn.close()


# ──────────────────────────────────────────────
# Telegram
# ──────────────────────────────────────────────

def get_telegram_chat_ids_para_tipo(tipo: str) -> list:
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(SQL_GET_TELEGRAM_CHAT_IDS_PARA_TIPO, (tipo,))
        rows = cur.fetchall()
        conn.close()
        return [{"id": r[0], "nombre": r[1], "chat_id": r[2]} for r in rows]
    except Exception:
        return []


def get_motorizados_telegram_status() -> list:
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(SQL_GET_MOTORIZADOS_TELEGRAM_STATUS)
        rows = cur.fetchall()
        conn.close()
        return rows
    except Exception:
        return []


# ──────────────────────────────────────────────
# Logs de trazabilidad
# ──────────────────────────────────────────────

def insert_solicitud_log(solicitud_id: int, accion: str,
                         usuario_id, usuario_nombre: str, detalle: str = "") -> None:
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(SQL_INSERT_SOLICITUD_LOG,
                    (solicitud_id, accion, usuario_id, usuario_nombre or "", detalle or ""))
        conn.commit()
        conn.close()
    except Exception:
        pass


def get_solicitud_logs(solicitud_id: int):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(SQL_GET_SOLICITUD_LOGS, (solicitud_id,))
        rows = cur.fetchall()
        conn.close()
        return rows
    except Exception:
        return []


# ──────────────────────────────────────────────
# Notificaciones in-app
# ──────────────────────────────────────────────

def insert_notify_inapp(user_id: int, title: str, body: str) -> None:
    from datetime import datetime
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_INSERT_NOTIFY_INAPP,
                (user_id, title, body,
                 datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")))
    conn.commit()
    conn.close()


# ──────────────────────────────────────────────
# Presupuesto
# ──────────────────────────────────────────────

def get_tipos_gasto() -> list[str]:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_GET_TIPOS_GASTO, (PARAM_GROUP_TIPOS_GASTO,))
    rows = [r[0] for r in cur.fetchall()]
    return rows if rows else TIPOS_GASTO_DEFAULT


def get_presupuesto_cc(empresa_id: int, cc_id: int, tipo_gasto: str, anio: int) -> list[dict]:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_GET_PRESUPUESTO_CC, (empresa_id, cc_id, tipo_gasto, anio))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    by_mes = {r["mes"]: r for r in rows}
    return [
        by_mes.get(m, {"mes": m, "monto_presupuestado": 0, "monto_ejecutado": 0})
        for m in range(1, 13)
    ]


def upsert_presupuesto(empresa_id: int, cc_id: int, tipo_gasto: str,
                       anio: int, mes: int, monto: float) -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_UPSERT_PRESUPUESTO, (
        empresa_id, cc_id, tipo_gasto, anio, mes,
        monto,
        empresa_id, cc_id, tipo_gasto, anio, mes,
        empresa_id, cc_id, tipo_gasto, anio, mes, monto,
    ))
    conn.commit()
    conn.close()


def get_saldo_presupuesto(empresa_id: int, cc_id: int, tipo_gasto: str,
                          anio: int, mes: int) -> dict:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_GET_SALDO_PRESUPUESTO, (empresa_id, cc_id, tipo_gasto, anio, mes))
    row = cur.fetchone()
    if not row:
        return {"presupuestado": 0, "ejecutado": 0, "pct": 0, "semaforo": "verde"}
    presupuestado = float(row[0])
    ejecutado = float(row[1])
    pct = (ejecutado / presupuestado * 100) if presupuestado > 0 else 0
    if pct >= 100:
        semaforo = "rojo"
    elif pct >= SEMAFORO_AMARILLO_PCT:
        semaforo = "amarillo"
    else:
        semaforo = "verde"
    return {"presupuestado": presupuestado, "ejecutado": ejecutado,
            "pct": round(pct, 1), "semaforo": semaforo}


def get_saldo_anual_presupuesto(empresa_id: int, cc_id: int, tipo_gasto: str,
                                anio: int) -> dict:
    """Saldo acumulado del año entero (para indicador de vuelos)."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_GET_SALDO_ANUAL_PRESUPUESTO, (empresa_id, cc_id, tipo_gasto, anio))
    row = cur.fetchone()
    if not row:
        return {"presupuestado": 0, "ejecutado": 0, "pct": 0, "semaforo": "verde"}
    presupuestado = float(row[0])
    ejecutado = float(row[1])
    pct = (ejecutado / presupuestado * 100) if presupuestado > 0 else 0
    if pct >= 100:
        semaforo = "rojo"
    elif pct >= SEMAFORO_AMARILLO_PCT:
        semaforo = "amarillo"
    else:
        semaforo = "verde"
    return {"presupuestado": presupuestado, "ejecutado": ejecutado,
            "pct": round(pct, 1), "semaforo": semaforo}


def add_ejecutado(empresa_id: int, cc_id: int, tipo_gasto: str,
                  anio: int, mes: int, monto: float) -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_ADD_EJECUTADO, (monto, empresa_id, cc_id, tipo_gasto, anio, mes))
    conn.commit()


def get_centros_costo_con_presupuesto(empresa_id: int, anio: int) -> list[dict]:
    """Retorna CCs distintos que tienen presupuesto registrado para la empresa+año."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(f"""
        SELECT DISTINCT p.centro_costo_id, pv.nombre AS centro_costo_nombre
        FROM planificador_presupuesto p
        JOIN param_values pv ON pv.id = p.centro_costo_id
        WHERE p.empresa_id = ? AND p.anio = ?
        ORDER BY pv.nombre
    """, (empresa_id, anio))
    return [dict(r) for r in cur.fetchall()]


def get_cc_usuario(usuario_id: int) -> dict | None:
    """Retorna el centro de costo del usuario marcado como exclusivo de
    Planificador/Boletos de avión (usuarios_cc.es_boletos_aereos = 1).

    Ya no se elige por "mayor porcentaje": ese campo se fuerza siempre a 0
    en los CC marcados como boletos aéreos, así que el criterio ahora es
    explícito (el checkbox en la ficha del usuario), no un heurístico.
    """
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT TOP 1
            uc.centro_costo_id,
            pv.valor    AS cc_codigo,
            pv.nombre   AS cc_nombre,
            u.empresa_id
        FROM usuarios_cc uc
        JOIN usuarios u   ON u.id  = uc.usuario_id
        JOIN param_values pv ON pv.id = uc.centro_costo_id
        WHERE uc.usuario_id = ?
          AND uc.es_boletos_aereos = 1
        ORDER BY uc.centro_costo_id
    """, (usuario_id,))
    row = cur.fetchone()
    if not row:
        return None
    return {
        "cc_id":      row[0],
        "cc_codigo":  row[1] or "",
        "cc_nombre":  row[2],
        "empresa_id": row[3],
    }


# ──────────────────────────────────────────────
# Adjuntos de solicitudes
# ──────────────────────────────────────────────

def get_adjuntos(solicitud_id: int) -> list[dict]:
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, nombre_original, nombre_guardado, tamano, subido_por_nombre, fecha_subida
            FROM planificador_adjuntos
            WHERE solicitud_id = ?
            ORDER BY fecha_subida
        """, (solicitud_id,))
        return [dict(r) for r in cur.fetchall()]
    except Exception:
        return []


def insert_adjunto(solicitud_id: int, nombre_original: str, nombre_guardado: str,
                   tamano: int, subido_por_id: int, subido_por_nombre: str) -> int:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO planificador_adjuntos
            (solicitud_id, nombre_original, nombre_guardado, tamano,
             subido_por_id, subido_por_nombre, fecha_subida)
        OUTPUT INSERTED.id
        VALUES (?, ?, ?, ?, ?, ?, GETDATE())
    """, (solicitud_id, nombre_original, nombre_guardado, tamano,
          subido_por_id, subido_por_nombre))
    row = cur.fetchone()
    conn.commit()
    return row[0] if row else None


def get_adjunto_by_id(adjunto_id: int) -> dict | None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.id, a.solicitud_id, a.nombre_original, a.nombre_guardado,
               a.tamano, a.subido_por_id, a.subido_por_nombre, a.fecha_subida,
               s.estado
        FROM planificador_adjuntos a
        JOIN planificador_solicitudes s ON s.id = a.solicitud_id
        WHERE a.id = ?
    """, (adjunto_id,))
    row = cur.fetchone()
    return dict(row) if row else None


def delete_adjunto(adjunto_id: int) -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM planificador_adjuntos WHERE id = ?", (adjunto_id,))
    conn.commit()


def get_jefe_nombre_batch(solicitante_ids: list) -> dict:
    """Retorna {solicitante_id: {"nombre": jefe_nombre, "username": jefe_username}}
    para una lista de IDs."""
    if not solicitante_ids:
        return {}
    conn = get_db()
    cur = conn.cursor()
    placeholders = ",".join(["?" for _ in solicitante_ids])
    sql = SQL_GET_JEFE_NOMBRE_BATCH.format(placeholders=placeholders)
    cur.execute(sql, solicitante_ids)
    result = {}
    for r in cur.fetchall():
        try:
            result[r["solicitante_id"]] = {
                "nombre": r["jefe_nombre"] or "",
                "username": r["jefe_username"] or "",
            }
        except Exception:
            result[r[0]] = {"nombre": r[1] or "", "username": r[2] or ""}
    return result


# ──────────────────────────────────────────────
# Indicadores — Voucher
# ──────────────────────────────────────────────

def get_voucher_indicadores_kpi(fecha_desde: str, fecha_hasta: str, area: str = "") -> dict:
    conn = get_db()
    cur = conn.cursor()
    area = area or ""
    cur.execute(SQL_VOUCHER_IND_KPI, (fecha_desde, fecha_hasta, area, area))
    row = cur.fetchone()
    return dict(row) if row else {}


def get_voucher_indicadores_por_usuario(fecha_desde: str, fecha_hasta: str, area: str = "") -> list[dict]:
    conn = get_db()
    cur = conn.cursor()
    area = area or ""
    cur.execute(SQL_VOUCHER_IND_POR_USUARIO, (fecha_desde, fecha_hasta, area, area))
    return [dict(r) for r in cur.fetchall()]


def get_voucher_indicadores_por_departamento(fecha_desde: str, fecha_hasta: str, area: str = "") -> list[dict]:
    conn = get_db()
    cur = conn.cursor()
    area = area or ""
    cur.execute(SQL_VOUCHER_IND_POR_DEPARTAMENTO, (fecha_desde, fecha_hasta, area, area))
    return [dict(r) for r in cur.fetchall()]


def get_voucher_indicadores_tendencia_mensual(fecha_desde: str, fecha_hasta: str, area: str = "") -> list[dict]:
    conn = get_db()
    cur = conn.cursor()
    area = area or ""
    cur.execute(SQL_VOUCHER_IND_TENDENCIA_MENSUAL, (fecha_desde, fecha_hasta, area, area))
    return [dict(r) for r in cur.fetchall()]


def get_voucher_indicadores_top_rutas(fecha_desde: str, fecha_hasta: str, area: str = "") -> list[dict]:
    conn = get_db()
    cur = conn.cursor()
    area = area or ""
    cur.execute(SQL_VOUCHER_IND_TOP_RUTAS, (fecha_desde, fecha_hasta, area, area))
    return [dict(r) for r in cur.fetchall()]


def get_voucher_indicadores_pend_confirmacion_detalle(fecha_desde: str, fecha_hasta: str,
                                                        area: str = "") -> list[dict]:
    conn = get_db()
    cur = conn.cursor()
    area = area or ""
    cur.execute(SQL_VOUCHER_IND_PEND_CONFIRMACION_DETALLE, (fecha_desde, fecha_hasta, area, area))
    return [dict(r) for r in cur.fetchall()]
