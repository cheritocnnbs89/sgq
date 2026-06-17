# modules/planificador/planificador_repository.py
# -*- coding: utf-8 -*-
"""Acceso directo a base de datos para el módulo Planificador."""

from modules.db import get_db
from .planificador_constants import (
    PARAM_GROUP_TIPOS, TIPOS_SOLICITUD_DEFAULT,
    ROL_COORDINADOR, ROL_APROBADOR, ROL_MOTORIZADO, ROLES_GERENTE,
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

    sql = f"""
        SELECT s.*
        FROM planificador_solicitudes s
        WHERE {' AND '.join(where)}
        ORDER BY s.fecha DESC, s.hora_inicio
    """
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

    sql = f"""
        SELECT s.*
        FROM planificador_solicitudes s
        WHERE s.activo = 1
          AND s.tipo IN ({placeholders_t})
          AND s.estado IN ({placeholders_e})
          {where_extra}
        ORDER BY s.fecha DESC, s.hora_inicio
    """
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

    sql = f"""
        SELECT s.*
        FROM planificador_solicitudes s
        WHERE {' AND '.join(where)}
        ORDER BY s.fecha DESC, s.hora_inicio
    """
    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    return rows


def get_solicitud_by_id(solicitud_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM planificador_solicitudes WHERE id = ? AND activo = 1",
        (solicitud_id,)
    )
    row = cur.fetchone()
    conn.close()
    return row


def get_calendar_solicitudes(fecha_desde, fecha_hasta):
    """Devuelve solicitudes aprobadas para mostrar en calendario."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, tipo, area_solicitante, descripcion, lugar_destino,
               fecha, hora_inicio, hora_fin, estado, prioridad,
               solicitante_nombre
        FROM planificador_solicitudes
        WHERE activo = 1
          AND estado IN ('APROBADA', 'PENDIENTE_APROBACION', 'COMPLETADA')
          AND fecha BETWEEN ? AND ?
        ORDER BY fecha, hora_inicio
    """, (fecha_desde, fecha_hasta))
    rows = cur.fetchall()
    conn.close()
    return rows


# ──────────────────────────────────────────────
# Solicitudes – escritura
# ──────────────────────────────────────────────

def crear_solicitud(data):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO planificador_solicitudes
            (tipo, area_solicitante, descripcion, lugar_destino, detalle_direccion,
             contacto, prioridad, fecha, estado, solicitante_id, solicitante_nombre,
             ciudad)
        OUTPUT INSERTED.id
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDIENTE_COORDINACION', ?, ?, ?)
    """, (
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
    """
    Reagenda la solicitud a una nueva fecha y la devuelve a PENDIENTE_COORDINACION
    para que el coordinador asigne nuevamente el horario.
    """
    conn = get_db()
    cur  = conn.cursor()
    # Leer fecha anterior para el log
    cur.execute("SELECT fecha FROM planificador_solicitudes WHERE id = ? AND activo = 1",
                (solicitud_id,))
    row_prev = cur.fetchone()
    fecha_anterior = str(row_prev[0]) if row_prev else "—"

    cur.execute("""
        UPDATE planificador_solicitudes SET
            fecha              = ?,
            estado             = 'PENDIENTE_COORDINACION',
            hora_inicio        = NULL,
            hora_fin           = NULL,
            coordinador_id     = NULL,
            coordinador_nombre = NULL,
            observacion_coordinador = NULL,
            fecha_actualizacion = GETDATE()
        WHERE id = ? AND activo = 1
    """, (nueva_fecha, solicitud_id))
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
    cur.execute("""
        UPDATE planificador_solicitudes SET
            hora_inicio = ?,
            hora_fin = ?,
            observacion_coordinador = ?,
            coordinador_id = ?,
            coordinador_nombre = ?,
            estado = 'PENDIENTE_APROBACION',
            fecha_actualizacion = GETDATE()
        WHERE id = ? AND activo = 1
    """, (hora_inicio, hora_fin, observacion, coordinador_id, coordinador_nombre, solicitud_id))
    conn.commit()
    conn.close()
    insert_solicitud_log(solicitud_id, "COORDINADA", coordinador_id, coordinador_nombre,
                         f"Horario asignado: {hora_inicio} – {hora_fin}. Obs: {observacion or '—'}")


# ──────────────────────────────────────────────
# Grupos de coordinación
# ──────────────────────────────────────────────

def get_solicitudes_pendientes_mismo_tipo(tipo: str, exclude_id: int):
    """Devuelve otras solicitudes PENDIENTE_COORDINACION del mismo tipo."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, area_solicitante, lugar_destino, fecha, descripcion, solicitante_nombre
        FROM planificador_solicitudes
        WHERE tipo = ?
          AND estado = 'PENDIENTE_COORDINACION'
          AND id != ?
          AND activo = 1
        ORDER BY fecha, area_solicitante
    """, (tipo, exclude_id))
    rows = cur.fetchall()
    conn.close()
    return rows


def crear_grupo_coordinacion(tipo: str, fecha: str, hora_inicio: str,
                              hora_fin: str, coordinador_id: int,
                              coordinador_nombre: str, observacion: str):
    """Crea un registro de grupo de coordinación y devuelve su id."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO planificador_grupos
            (tipo, fecha, hora_inicio, hora_fin,
             coordinador_id, coordinador_nombre, observacion)
        OUTPUT INSERTED.id
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (tipo, fecha, hora_inicio, hora_fin,
          coordinador_id, coordinador_nombre, observacion))
    row = cur.fetchone()
    conn.commit()
    conn.close()
    return row[0] if row else None


def coordinar_solicitudes_grupo(ids: list, grupo_id: int, coordinador_id: int,
                                 coordinador_nombre: str, hora_inicio: str,
                                 hora_fin: str, observacion: str):
    """Coordina múltiples solicitudes asignándoles el mismo grupo y horario."""
    conn = get_db()
    cur = conn.cursor()
    for sid in ids:
        cur.execute("""
            UPDATE planificador_solicitudes SET
                hora_inicio             = ?,
                hora_fin                = ?,
                observacion_coordinador = ?,
                coordinador_id          = ?,
                coordinador_nombre      = ?,
                grupo_id                = ?,
                estado                  = 'PENDIENTE_APROBACION',
                fecha_actualizacion     = GETDATE()
            WHERE id = ? AND activo = 1
        """, (hora_inicio, hora_fin, observacion,
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


def get_solicitudes_del_grupo(grupo_id: int):
    """Devuelve todas las solicitudes activas de un grupo de coordinación."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, tipo, area_solicitante, lugar_destino, fecha,
               hora_inicio, hora_fin, estado, solicitante_nombre, solicitante_id
        FROM planificador_solicitudes
        WHERE grupo_id = ? AND activo = 1
        ORDER BY id
    """, (grupo_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def aprobar_solicitud(solicitud_id, aprobador_id, aprobador_nombre, observacion):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE planificador_solicitudes SET
            estado = 'APROBADA',
            aprobador_id = ?,
            aprobador_nombre = ?,
            observacion_aprobador = ?,
            fecha_actualizacion = GETDATE()
        WHERE id = ? AND activo = 1
    """, (aprobador_id, aprobador_nombre, observacion, solicitud_id))
    conn.commit()
    conn.close()
    insert_solicitud_log(solicitud_id, "APROBADA", aprobador_id, aprobador_nombre,
                         f"Aprobada. Obs: {observacion or '—'}")


def rechazar_solicitud(solicitud_id, aprobador_id, aprobador_nombre, observacion):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE planificador_solicitudes SET
            estado = 'RECHAZADA',
            aprobador_id = ?,
            aprobador_nombre = ?,
            observacion_aprobador = ?,
            fecha_actualizacion = GETDATE()
        WHERE id = ? AND activo = 1
    """, (aprobador_id, aprobador_nombre, observacion, solicitud_id))
    conn.commit()
    conn.close()
    insert_solicitud_log(solicitud_id, "RECHAZADA", aprobador_id, aprobador_nombre,
                         f"Rechazada. Motivo: {observacion or '—'}")


def completar_solicitud(solicitud_id, usuario_id: int = None, usuario_nombre: str = ""):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE planificador_solicitudes SET
            estado = 'COMPLETADA',
            fecha_actualizacion = GETDATE()
        WHERE id = ? AND activo = 1
    """, (solicitud_id,))
    conn.commit()
    conn.close()
    insert_solicitud_log(solicitud_id, "COMPLETADA", usuario_id, usuario_nombre,
                         "Marcada como completada.")


# ──────────────────────────────────────────────
# Configuración coordinadores / aprobadores
# ──────────────────────────────────────────────

def get_all_config():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM planificador_config
        WHERE activo = 1
        ORDER BY tipo, rol_config, usuario_nombre
    """)
    rows = cur.fetchall()
    conn.close()
    return rows


def get_config_for_user(usuario_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT tipo, rol_config
        FROM planificador_config
        WHERE usuario_id = ? AND activo = 1
    """, (usuario_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def insert_config(tipo, usuario_id, usuario_nombre, rol_config):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM planificador_config
            WHERE tipo = ? AND usuario_id = ? AND rol_config = ?
        )
        INSERT INTO planificador_config (tipo, usuario_id, usuario_nombre, rol_config)
        VALUES (?, ?, ?, ?)
        ELSE
        UPDATE planificador_config SET activo = 1, usuario_nombre = ?
        WHERE tipo = ? AND usuario_id = ? AND rol_config = ?
    """, (tipo, usuario_id, rol_config, tipo, usuario_id, usuario_nombre, rol_config,
          usuario_nombre, tipo, usuario_id, rol_config))
    conn.commit()
    conn.close()


def delete_config(config_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE planificador_config SET activo = 0 WHERE id = ?",
        (config_id,)
    )
    conn.commit()
    conn.close()


def get_usuarios_for_select():
    """Devuelve lista de usuarios activos para el select de configuración."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id,
               COALESCE(nombre_completo, username) AS nombre,
               username
        FROM usuarios
        WHERE disabled = 0
        ORDER BY nombre_completo, username
    """)
    rows = cur.fetchall()
    conn.close()
    return rows


def get_tipos_solicitud():
    """
    Lee los tipos de solicitud desde param_values (grupo PLANIFICADOR_TIPOS).
    Si no hay datos configurados devuelve el fallback hardcodeado.
    Retorna una lista de strings con los nombres de los tipos.
    """
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("""
        SELECT pv.nombre
        FROM param_values pv
        JOIN param_groups pg ON pg.id = pv.group_id
        WHERE pg.nombre = ?
          AND pv.activo = 1
        ORDER BY pv.orden, pv.nombre
    """, (PARAM_GROUP_TIPOS,))
    rows = cur.fetchall()
    conn.close()
    tipos = [r[0] for r in rows if r[0]]
    return tipos if tipos else list(TIPOS_SOLICITUD_DEFAULT)


def get_departamentos():
    """Devuelve todos los departamentos."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, nombre
        FROM departamentos
        ORDER BY nombre
    """)
    rows = cur.fetchall()
    conn.close()
    return rows


def get_usuario_departamento(usuario_id):
    """Devuelve el departamento del usuario: {'dept_id': ..., 'dept_nombre': ...}."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT d.id, d.nombre
        FROM usuarios u
        LEFT JOIN departamentos d ON d.id = u.departamento_id
        WHERE u.id = ?
    """, (usuario_id,))
    row = cur.fetchone()
    conn.close()
    if row and row[0]:
        return {"dept_id": row[0], "dept_nombre": row[1] or ""}
    return {"dept_id": None, "dept_nombre": ""}


def get_email_by_usuario_id(usuario_id):
    """Devuelve el email de un usuario."""
    if not usuario_id:
        return None
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT email FROM usuarios WHERE id = ? AND disabled = 0",
        (usuario_id,)
    )
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def check_horario_ocupado(tipo, fecha, hora_inicio, hora_fin, exclude_id=None):
    """
    Verifica si existe OTRO registro del mismo tipo en el mismo fecha/horario.
    Retorna True si hay conflicto (ocupado), False si está libre.
    Tipos diferentes SÍ pueden solaparse.
    """
    conn = get_db()
    cur  = conn.cursor()
    params = [tipo, fecha]
    excl   = " AND id != ?" if exclude_id else ""
    if exclude_id:
        params.append(exclude_id)
    params += [hora_fin, hora_inicio]

    cur.execute(f"""
        SELECT TOP 1 id
        FROM planificador_solicitudes
        WHERE tipo = ?
          AND fecha = ?
          AND activo = 1
          AND estado NOT IN ('RECHAZADA','COMPLETADA')
          AND hora_inicio IS NOT NULL
          AND hora_fin   IS NOT NULL
          {excl}
          AND hora_inicio < ?
          AND hora_fin   > ?
    """, params)
    row = cur.fetchone()
    conn.close()
    return row is not None


def get_roles_para_tipo(tipo: str) -> dict:
    """
    Devuelve {coordinadores, aprobadores, motorizados} como listas de
    dicts {id, nombre, email} para el tipo dado.
    """
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("""
        SELECT pc.usuario_id, pc.usuario_nombre, pc.rol_config, u.email
        FROM planificador_config pc
        LEFT JOIN usuarios u ON u.id = pc.usuario_id AND u.disabled = 0
        WHERE pc.tipo = ? AND pc.activo = 1
    """, (tipo,))
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
    """Devuelve motorizados configurados para el tipo."""
    return get_roles_para_tipo(tipo)["motorizados"]


def get_solicitudes_para_reporte(filters=None):
    """Devuelve todas las solicitudes para el reporte (sin columnas de IDs internos)."""
    filters = filters or {}
    conn = get_db()
    cur  = conn.cursor()
    where  = ["s.activo = 1"]
    params = []
    if filters.get("estado"):
        where.append("s.estado = ?"); params.append(filters["estado"])
    if filters.get("tipo"):
        where.append("s.tipo = ?"); params.append(filters["tipo"])
    if filters.get("fecha_desde"):
        where.append("s.fecha >= ?"); params.append(filters["fecha_desde"])
    if filters.get("fecha_hasta"):
        where.append("s.fecha <= ?"); params.append(filters["fecha_hasta"])
    sql = f"""
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
            CONVERT(VARCHAR,s.fecha_creacion,120)      AS [Fecha Creación],
            CONVERT(VARCHAR,s.fecha_actualizacion,120) AS [Última Actualización]
        FROM planificador_solicitudes s
        WHERE {' AND '.join(where)}
        ORDER BY s.fecha DESC, s.hora_inicio
    """
    cur.execute(sql, params)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    conn.close()
    return cols, rows


def insert_notify_inapp(user_id: int, title: str, body: str) -> None:
    """Inserta una notificación in-app para el usuario."""
    from datetime import datetime
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("""
        INSERT INTO notify_inapp (user_id, title, body, created_at, is_read)
        VALUES (?, ?, ?, ?, 0)
    """, (user_id, title, body, datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")))
    conn.commit()
    conn.close()


def get_motorizados_ids_and_emails():
    """Devuelve lista de {id, email} de usuarios con puesto MOTORIZADO/SERVICIOS VARIOS."""
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("""
        SELECT DISTINCT u.id, u.email
        FROM usuarios u
        JOIN puestos p ON p.id = u.puesto_id
        WHERE u.disabled = 0
          AND (p.nombre LIKE '%MOTORIZADO%' OR p.nombre LIKE '%SERVICIOS VARIOS%')
    """)
    rows = cur.fetchall()
    conn.close()
    return [{"id": r[0], "email": r[1]} for r in rows]


def get_solicitudes_pendiente_gerente_para_usuario(gerente_id: int, tipos, filters=None):
    """
    Devuelve solicitudes en estado PENDIENTE_APROBACION_GERENTE donde
    el gerente_id coincida con el usuario dado (o todas si es admin).
    """
    if not tipos:
        return []
    filters = filters or {}
    conn = get_db()
    cur  = conn.cursor()
    placeholders = ",".join(["?" for _ in tipos])
    params = list(tipos) + [gerente_id]
    where_extra = ""
    if filters.get("fecha_desde"):
        where_extra += " AND s.fecha >= ?"
        params.append(filters["fecha_desde"])
    if filters.get("fecha_hasta"):
        where_extra += " AND s.fecha <= ?"
        params.append(filters["fecha_hasta"])
    sql = f"""
        SELECT s.*
        FROM planificador_solicitudes s
        WHERE s.activo = 1
          AND s.tipo IN ({placeholders})
          AND s.estado = 'PENDIENTE_APROBACION_GERENTE'
          AND s.gerente_id = ?
          {where_extra}
        ORDER BY s.fecha DESC, s.hora_inicio
    """
    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    return rows


def get_tipo_flags(tipo: str) -> dict:
    """Devuelve flags de configuración para un tipo de solicitud."""
    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute(
            "SELECT requiere_aprobacion_gerente FROM planificador_tipo_flags WHERE tipo = ?",
            (tipo,)
        )
        row = cur.fetchone()
        conn.close()
        if row:
            return {"requiere_aprobacion_gerente": bool(row[0])}
    except Exception:
        pass
    return {"requiere_aprobacion_gerente": False}


def get_all_tipo_flags() -> dict:
    """Devuelve dict {tipo: {requiere_aprobacion_gerente: bool}}."""
    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("SELECT tipo, requiere_aprobacion_gerente FROM planificador_tipo_flags")
        rows = cur.fetchall()
        conn.close()
        return {r[0]: {"requiere_aprobacion_gerente": bool(r[1])} for r in rows}
    except Exception:
        # Tabla aún no existe (se crea en ensure_tables al arrancar)
        return {}


def set_tipo_flags(tipo: str, requiere_aprobacion_gerente: bool) -> None:
    """Crea o actualiza los flags de un tipo."""
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("""
        IF EXISTS (SELECT 1 FROM planificador_tipo_flags WHERE tipo = ?)
            UPDATE planificador_tipo_flags
               SET requiere_aprobacion_gerente = ?
             WHERE tipo = ?
        ELSE
            INSERT INTO planificador_tipo_flags (tipo, requiere_aprobacion_gerente)
            VALUES (?, ?)
    """, (tipo, 1 if requiere_aprobacion_gerente else 0, tipo,
          tipo, 1 if requiere_aprobacion_gerente else 0))
    conn.commit()
    conn.close()


def get_gerente_del_usuario(usuario_id: int):
    """
    Sube la cadena jefe_id del usuario hasta encontrar el primer usuario
    cuyo rol sea uno de ROLES_GERENTE. Retorna {id, nombre, email} o None.
    """
    if not usuario_id:
        return None
    conn = get_db()
    cur  = conn.cursor()

    cur.execute(
        "SELECT jefe_id FROM usuarios WHERE id = ? AND COALESCE(disabled,0) = 0",
        (usuario_id,)
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return None

    jefe_id = row[0]
    seen = set()

    while jefe_id and jefe_id not in seen:
        seen.add(jefe_id)
        cur.execute("""
            SELECT id, COALESCE(nombre_completo, username) AS nombre,
                   email, jefe_id, LOWER(COALESCE(rol,'')) AS rol
            FROM usuarios
            WHERE id = ? AND COALESCE(disabled,0) = 0
        """, (jefe_id,))
        j = cur.fetchone()
        if not j:
            break

        jrol     = (j[4] or "").lower()
        next_id  = j[3]
        result   = {"id": j[0], "nombre": j[1], "email": j[2]}

        if jrol in ROLES_GERENTE:
            conn.close()
            return result
        jefe_id = next_id

    conn.close()
    return None


def poner_pendiente_gerente(solicitud_id: int, gerente_id: int, gerente_nombre: str) -> None:
    """Cambia estado a PENDIENTE_APROBACION_GERENTE y guarda el gerente asignado."""
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("""
        UPDATE planificador_solicitudes SET
            estado = 'PENDIENTE_APROBACION_GERENTE',
            gerente_id     = ?,
            gerente_nombre = ?,
            fecha_actualizacion = GETDATE()
        WHERE id = ? AND activo = 1
    """, (gerente_id, gerente_nombre, solicitud_id))
    conn.commit()
    conn.close()


def aprobar_por_gerente(solicitud_id: int, gerente_id: int,
                        gerente_nombre: str, observacion: str = "") -> None:
    """El gerente aprueba finalmente la solicitud."""
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("""
        UPDATE planificador_solicitudes SET
            estado = 'APROBADA',
            observacion_aprobador = COALESCE(
                CASE WHEN observacion_aprobador IS NOT NULL AND observacion_aprobador <> ''
                     THEN observacion_aprobador + ' | Gerente: ' + ?
                     ELSE ?
                END, ?),
            fecha_actualizacion = GETDATE()
        WHERE id = ? AND activo = 1
    """, (observacion, observacion, observacion, solicitud_id))
    conn.commit()
    conn.close()
    insert_solicitud_log(solicitud_id, "APROBADA_GERENTE", gerente_id, gerente_nombre,
                         f"Aprobación gerencial. Obs: {observacion or '—'}")


def rechazar_por_gerente(solicitud_id: int, gerente_id: int,
                          gerente_nombre: str, observacion: str) -> None:
    """El gerente rechaza la solicitud."""
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("""
        UPDATE planificador_solicitudes SET
            estado = 'RECHAZADA',
            aprobador_id     = ?,
            aprobador_nombre = ?,
            observacion_aprobador = ?,
            fecha_actualizacion = GETDATE()
        WHERE id = ? AND activo = 1
    """, (gerente_id, gerente_nombre, observacion, solicitud_id))
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
    cur  = conn.cursor()
    cur.execute("""
        UPDATE planificador_solicitudes
           SET activo               = 0,
               eliminado_por_id     = ?,
               eliminado_por_nombre = ?,
               fecha_eliminacion    = GETDATE()
         WHERE id = ?
    """, (eliminado_por_id, eliminado_por_nombre or "", solicitud_id))
    conn.commit()
    conn.close()


def insert_solicitud_log(solicitud_id: int, accion: str,
                         usuario_id, usuario_nombre: str, detalle: str = "") -> None:
    """Registra una acción en el historial de trazabilidad de la solicitud."""
    try:
        from datetime import datetime
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("""
            INSERT INTO planificador_solicitud_logs
                (solicitud_id, accion, usuario_id, usuario_nombre, detalle, fecha_log)
            VALUES (?, ?, ?, ?, ?, GETDATE())
        """, (solicitud_id, accion, usuario_id, usuario_nombre or "", detalle or ""))
        conn.commit()
        conn.close()
    except Exception:
        pass  # No interrumpir el flujo principal si falla el log


def get_solicitud_logs(solicitud_id: int):
    """Devuelve el historial de acciones de una solicitud, ordenado por fecha ascendente."""
    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("""
            SELECT accion, usuario_nombre, detalle,
                   CONVERT(VARCHAR, fecha_log, 120) AS fecha_log
            FROM planificador_solicitud_logs
            WHERE solicitud_id = ?
            ORDER BY fecha_log ASC
        """, (solicitud_id,))
        rows = cur.fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def get_ciudad_usuario(usuario_id: int) -> str:
    """Devuelve el campo ciudad del usuario (vacío si no existe)."""
    if not usuario_id:
        return ""
    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("SELECT COALESCE(ciudad, '') FROM usuarios WHERE id = ?", (usuario_id,))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else ""
    except Exception:
        return ""


def get_motorizados_email():
    """Devuelve emails de usuarios con puesto que contenga 'MOTORIZADO' o 'SERVICIOS VARIOS'."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT u.email
        FROM usuarios u
        JOIN puestos p ON p.id = u.puesto_id
        WHERE u.disabled = 0
          AND u.email IS NOT NULL
          AND u.email <> ''
          AND (
              p.nombre LIKE '%MOTORIZADO%'
              OR p.nombre LIKE '%SERVICIOS VARIOS%'
          )
    """)
    rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows if r[0]]


def get_telegram_chat_ids_para_tipo(tipo: str) -> list[dict]:
    """
    Devuelve lista de {id, nombre, telegram_chat_id} de usuarios MOTORIZADOS
    configurados para el tipo dado que tengan telegram_chat_id registrado.
    """
    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("""
            SELECT pc.usuario_id,
                   pc.usuario_nombre,
                   u.telegram_chat_id
            FROM planificador_config pc
            JOIN usuarios u ON u.id = pc.usuario_id AND u.disabled = 0
            WHERE pc.tipo     = ?
              AND pc.rol_config = 'MOTORIZADO'
              AND pc.activo    = 1
              AND u.telegram_chat_id IS NOT NULL
              AND u.telegram_chat_id <> ''
        """, (tipo,))
        rows = cur.fetchall()
        conn.close()
        return [{"id": r[0], "nombre": r[1], "chat_id": r[2]} for r in rows]
    except Exception:
        return []


def get_motorizados_telegram_status() -> list:
    """
    Devuelve todos los usuarios configurados como MOTORIZADO con su estado Telegram.
    Incluye: usuario_id, usuario_nombre, tipo, email, telegram_chat_id (o None).
    """
    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("""
            SELECT pc.usuario_id,
                   pc.usuario_nombre,
                   pc.tipo,
                   u.email,
                   u.telegram_chat_id
            FROM planificador_config pc
            LEFT JOIN usuarios u ON u.id = pc.usuario_id
            WHERE pc.rol_config = 'MOTORIZADO'
              AND pc.activo     = 1
            ORDER BY pc.tipo, pc.usuario_nombre
        """)
        rows = cur.fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def update_usuario_telegram_chat_id(usuario_id: int, chat_id: str) -> None:
    """Guarda el telegram_chat_id de un usuario (usado desde admin profile)."""
    conn = get_db()
    cur  = conn.cursor()
    cur.execute(
        "UPDATE usuarios SET telegram_chat_id = ? WHERE id = ?",
        (chat_id or None, usuario_id)
    )
    conn.commit()
    conn.close()
