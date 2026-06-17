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
    ROL_COORDINADOR, ROL_APROBADOR, ROL_MOTORIZADO, ROLES_GERENTE,
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
    SQL_GET_TIPOS_SOLICITUD,
    SQL_GET_TIPO_FLAGS,
    SQL_GET_ALL_TIPO_FLAGS,
    SQL_UPSERT_TIPO_FLAGS,
    SQL_GET_USUARIOS_FOR_SELECT,
    SQL_GET_DEPARTAMENTOS,
    SQL_GET_USUARIO_DEPARTAMENTO,
    SQL_GET_EMAIL_BY_USUARIO_ID,
    SQL_GET_CIUDAD_USUARIO,
    SQL_GET_JEFE_USUARIO,
    SQL_GET_USUARIO_JERARQUIA,
    SQL_UPDATE_TELEGRAM_CHAT_ID,
    SQL_GET_MOTORIZADOS_IDS_EMAILS,
    SQL_GET_MOTORIZADOS_EMAIL,
    SQL_GET_TELEGRAM_CHAT_IDS_PARA_TIPO,
    SQL_GET_MOTORIZADOS_TELEGRAM_STATUS,
    SQL_INSERT_SOLICITUD_LOG,
    SQL_GET_SOLICITUD_LOGS,
    SQL_INSERT_NOTIFY_INAPP,
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


def get_solicitudes_para_reporte(filters=None):
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
        data["solicitante_id"], data["solicitante_nombre"],
        data.get("ciudad", ""),
    ))
    row = cur.fetchone()
    conn.commit()
    sid = row[0] if row else None
    conn.close()
    if sid:
        insert_solicitud_log(sid, "CREADA", data["solicitante_id"],
                             data["solicitante_nombre"],
                             f"Solicitud creada. Tipo: {data['tipo']} · Fecha: {data['fecha']}")
    return sid


def reagendar_solicitud(solicitud_id: int, nueva_fecha: str,
                        coordinador_id: int, coordinador_nombre: str, motivo: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_GET_FECHA_SOLICITUD, (solicitud_id,))
    row_prev = cur.fetchone()
    fecha_anterior = str(row_prev[0]) if row_prev else "—"
    cur.execute(SQL_UPDATE_REAGENDAR, (nueva_fecha, solicitud_id))
    conn.commit()
    conn.close()
    insert_solicitud_log(
        solicitud_id, "REAGENDADA", coordinador_id, coordinador_nombre,
        f"Fecha anterior: {fecha_anterior} → Nueva fecha: {nueva_fecha}. Motivo: {motivo or '—'}"
    )


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
    coordinadores, aprobadores, motorizados = [], [], []
    for r in rows:
        entry = {"id": r[0], "nombre": r[1], "email": r[3]}
        if   r[2] == ROL_COORDINADOR: coordinadores.append(entry)
        elif r[2] == ROL_APROBADOR:   aprobadores.append(entry)
        elif r[2] == ROL_MOTORIZADO:  motorizados.append(entry)
    return {"coordinadores": coordinadores,
            "aprobadores":   aprobadores,
            "motorizados":   motorizados}


def get_coordinadores_aprobadores_para_tipo(tipo):
    """Compatibilidad: retorna (coordinadores, aprobadores)."""
    d = get_roles_para_tipo(tipo)
    return d["coordinadores"], d["aprobadores"]


def get_motorizados_para_tipo(tipo: str):
    return get_roles_para_tipo(tipo)["motorizados"]


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


def get_tipo_flags(tipo: str) -> dict:
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(SQL_GET_TIPO_FLAGS, (tipo,))
        row = cur.fetchone()
        conn.close()
        if row:
            return {"requiere_aprobacion_gerente": bool(row[0])}
    except Exception:
        pass
    return {"requiere_aprobacion_gerente": False}


def get_all_tipo_flags() -> dict:
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(SQL_GET_ALL_TIPO_FLAGS)
        rows = cur.fetchall()
        conn.close()
        return {r[0]: {"requiere_aprobacion_gerente": bool(r[1])} for r in rows}
    except Exception:
        return {}


def set_tipo_flags(tipo: str, requiere_aprobacion_gerente: bool) -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_UPSERT_TIPO_FLAGS,
                (tipo, 1 if requiere_aprobacion_gerente else 0, tipo,
                 tipo, 1 if requiere_aprobacion_gerente else 0))
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
    if not usuario_id:
        return None
    conn = get_db()
    cur = conn.cursor()
    cur.execute(SQL_GET_JEFE_USUARIO, (usuario_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return None

    jefe_id = row[0]
    seen = set()

    while jefe_id and jefe_id not in seen:
        seen.add(jefe_id)
        cur.execute(SQL_GET_USUARIO_JERARQUIA, (jefe_id,))
        j = cur.fetchone()
        if not j:
            break
        jrol    = (j[4] or "").lower()
        next_id = j[3]
        result  = {"id": j[0], "nombre": j[1], "email": j[2]}
        if jrol in ROLES_GERENTE:
            conn.close()
            return result
        jefe_id = next_id

    conn.close()
    return None


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
