# modules/casos_legales/casos_legales_repository.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime

from modules.db import get_db, get_config_value
from .casos_legales_constants import (
    CONFIG_GESTORES_PREFIX, ESTADO_ABIERTO, ESTADO_CERRADO,
)


def _rows(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


# ── Casos ────────────────────────────────────────────────────

def crear_caso(tipo, tipo_tramite, estudio_juridico, observacion,
               fecha_tramite, fecha_fin_tentativa, usuario_id, usuario_nombre) -> int:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO casos_legales
            (tipo, tipo_tramite, estudio_juridico, observacion, fecha_tramite,
             fecha_fin_tentativa, estado, creado_por_id, creado_por_nombre)
        OUTPUT INSERTED.id
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (tipo, tipo_tramite, estudio_juridico or None, observacion, fecha_tramite,
          fecha_fin_tentativa or None, ESTADO_ABIERTO, usuario_id, usuario_nombre))
    row = cur.fetchone()
    conn.commit()
    return int(row[0])


def get_casos(estado: str | None = None, tipo: str | None = None,
              creado_por_id: int | None = None) -> list[dict]:
    sql = """
        SELECT c.id, c.tipo, c.tipo_tramite, c.estudio_juridico, c.fecha_tramite,
               c.fecha_fin_tentativa, c.estado, c.creado_por_nombre, c.fecha_creacion,
               (SELECT COUNT(*) FROM casos_legales_avances a
                 WHERE a.caso_id = c.id AND a.activo = 1) AS n_avances
        FROM casos_legales c
        WHERE c.activo = 1
    """
    params: list = []
    if estado:
        sql += " AND c.estado = ?"
        params.append(estado)
    if tipo:
        sql += " AND c.tipo = ?"
        params.append(tipo)
    if creado_por_id:
        sql += " AND c.creado_por_id = ?"
        params.append(creado_por_id)
    sql += " ORDER BY c.id DESC"
    cur = get_db().cursor()
    cur.execute(sql, params)
    return _rows(cur)


def get_caso(caso_id: int) -> dict | None:
    cur = get_db().cursor()
    cur.execute("SELECT * FROM casos_legales WHERE id = ? AND activo = 1", (caso_id,))
    row = cur.fetchone()
    return dict(row) if row else None


def cerrar_caso(caso_id: int, observacion: str, usuario_id: int, usuario_nombre: str) -> bool:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE casos_legales
           SET estado = ?, cerrado_por_id = ?, cerrado_por_nombre = ?,
               fecha_cierre = GETDATE(), observacion_cierre = ?
         WHERE id = ? AND activo = 1 AND estado = ?
    """, (ESTADO_CERRADO, usuario_id, usuario_nombre, observacion or None,
          caso_id, ESTADO_ABIERTO))
    ok = cur.rowcount > 0
    conn.commit()
    return ok


# ── Avances ──────────────────────────────────────────────────

def add_avance(caso_id: int, observacion: str, usuario_id: int, usuario_nombre: str) -> int:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO casos_legales_avances (caso_id, observacion, usuario_id, usuario_nombre)
        OUTPUT INSERTED.id
        VALUES (?, ?, ?, ?)
    """, (caso_id, observacion, usuario_id, usuario_nombre))
    row = cur.fetchone()
    conn.commit()
    return int(row[0])


def get_avances(caso_id: int) -> list[dict]:
    cur = get_db().cursor()
    cur.execute("""
        SELECT id, observacion, usuario_id, usuario_nombre, fecha
        FROM casos_legales_avances
        WHERE caso_id = ? AND activo = 1
        ORDER BY fecha, id
    """, (caso_id,))
    return _rows(cur)


# ── Adjuntos ─────────────────────────────────────────────────

def insert_adjunto(caso_id: int, avance_id: int | None, etapa: str, nombre_original: str,
                   nombre_guardado: str, tamano: int, usuario_id: int, usuario_nombre: str) -> int:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO casos_legales_adjuntos
            (caso_id, avance_id, etapa, nombre_original, nombre_guardado, tamano,
             usuario_id, usuario_nombre)
        OUTPUT INSERTED.id
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (caso_id, avance_id, etapa, nombre_original, nombre_guardado, tamano,
          usuario_id, usuario_nombre))
    row = cur.fetchone()
    conn.commit()
    return int(row[0])


def get_adjuntos(caso_id: int) -> list[dict]:
    cur = get_db().cursor()
    cur.execute("""
        SELECT id, avance_id, etapa, nombre_original, tamano, usuario_nombre, fecha
        FROM casos_legales_adjuntos
        WHERE caso_id = ? AND activo = 1
        ORDER BY fecha, id
    """, (caso_id,))
    return _rows(cur)


def get_adjunto(adjunto_id: int) -> dict | None:
    cur = get_db().cursor()
    cur.execute("""
        SELECT id, caso_id, nombre_original, nombre_guardado
        FROM casos_legales_adjuntos
        WHERE id = ? AND activo = 1
    """, (adjunto_id,))
    row = cur.fetchone()
    return dict(row) if row else None


# ── Usuarios / gestores / notificaciones ────────────────────

def get_gestores(tipo: str) -> list[dict]:
    """Usuarios gestores configurados para el tipo (clave casos_legales_gestores_<TIPO>)."""
    raw = get_config_value(f"{CONFIG_GESTORES_PREFIX}{tipo}", "") or ""
    ids = [int(x) for x in raw.replace(";", ",").split(",") if x.strip().isdigit()]
    if not ids:
        return []
    marcas = ",".join("?" for _ in ids)
    cur = get_db().cursor()
    cur.execute(f"""
        SELECT id, COALESCE(nombre_completo, username) AS nombre, email
        FROM usuarios
        WHERE disabled = 0 AND id IN ({marcas})
    """, ids)
    return _rows(cur)


def get_usuario_contacto(usuario_id: int) -> dict | None:
    cur = get_db().cursor()
    cur.execute("""
        SELECT id, COALESCE(nombre_completo, username) AS nombre, email
        FROM usuarios WHERE id = ? AND disabled = 0
    """, (usuario_id,))
    row = cur.fetchone()
    return dict(row) if row else None


def insert_notify_inapp(user_id: int, title: str, body: str) -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO notify_inapp (user_id, title, body, created_at, is_read)
        VALUES (?, ?, ?, ?, 0)
    """, (user_id, title, body, datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")))
    conn.commit()
