# modules/casos_legales/casos_legales_repository.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime

from modules.db import get_db
from .casos_legales_constants import ESTADO_ABIERTO, ESTADO_CERRADO, CODIGO_PREFIJO


def _rows(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


# ── Casos ────────────────────────────────────────────────────

def crear_caso(tipo: str, d: dict, usuario_id: int, usuario_nombre: str) -> int:
    """d = datos validados del formulario. La fecha fin es la del día actual (la asigna el servidor)."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO casos_legales
            (tipo, fecha, tipo_tarea, descripcion, tercero_tipo, tercero_id, cliente_proveedor,
             tiempo_asignado, requirente_id, requirente, fecha_fin, estado,
             creado_por_id, creado_por_nombre)
        OUTPUT INSERTED.id
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CAST(GETDATE() AS DATE), ?, ?, ?)
    """, (tipo, d["fecha"].isoformat(), d["tipo_tarea"], d["descripcion"], d["tercero_tipo"],
          d["tercero_id"], d["cliente_proveedor"], d["tiempo_asignado"], d["requirente_id"],
          d["requirente"], ESTADO_ABIERTO, usuario_id, usuario_nombre))
    row = cur.fetchone()
    conn.commit()
    return int(row[0])


def get_casos(estado: str | None = None, tipo: str | None = None,
              visible_para: int | None = None) -> list[dict]:
    """visible_para=None -> todos (admin). Si no, casos que registró ese usuario o
    que registraron los usuarios cuyo jefe directo es él."""
    sql = """
        SELECT c.id, c.codigo, c.tipo, c.fecha, c.tipo_tarea, c.descripcion, c.tercero_tipo,
               c.cliente_proveedor, c.tiempo_asignado, c.requirente, c.estado, c.creado_por_id,
               c.creado_por_nombre, c.fecha_creacion, c.cerrado_por_nombre, c.fecha_cierre,
               c.observacion_cierre,
               (
                   (SELECT COUNT(*) FROM casos_legales_avances a
                     WHERE a.caso_id = c.id AND a.activo = 1)
                   + CASE WHEN c.estado = 'CERRADO' THEN 1 ELSE 0 END
               ) AS n_avances
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
    if visible_para:
        sql += (" AND (c.creado_por_id = ? OR c.creado_por_id IN "
                "(SELECT u.id FROM usuarios u WHERE u.jefe_id = ?))")
        params += [visible_para, visible_para]
    sql += " ORDER BY c.id DESC"
    cur = get_db().cursor()
    cur.execute(sql, params)
    return _rows(cur)


def get_usuarios_combo() -> list[dict]:
    """Usuarios activos (tabla usuarios) para el campo Usuario solicitante."""
    cur = get_db().cursor()
    cur.execute("""
        SELECT u.id, u.nombre_completo AS nombre, COALESCE(d.nombre, '') AS departamento
        FROM usuarios u
        LEFT JOIN departamentos d ON d.id = u.departamento_id
        WHERE COALESCE(u.disabled, 0) = 0 AND TRIM(COALESCE(u.nombre_completo, '')) <> ''
        ORDER BY u.nombre_completo
    """)
    return _rows(cur)


def get_terceros_combo(tipo: str) -> list[dict]:
    """tipo 'C' = clientes, 'P' = proveedores (tabla terceros, activos)."""
    cur = get_db().cursor()
    cur.execute("""
        SELECT id, nombre, identificacion
        FROM terceros
        WHERE tipo = ? AND COALESCE(activo, 1) = 1
        ORDER BY nombre
    """, (tipo,))
    return _rows(cur)


def get_usuario_nombre(usuario_id: int) -> str | None:
    cur = get_db().cursor()
    cur.execute("SELECT nombre_completo FROM usuarios WHERE id = ? AND COALESCE(disabled, 0) = 0",
                (usuario_id,))
    row = cur.fetchone()
    return row[0] if row else None


def get_tercero_nombre(tipo: str, tercero_id: int) -> str | None:
    cur = get_db().cursor()
    cur.execute("SELECT nombre FROM terceros WHERE id = ? AND tipo = ? AND COALESCE(activo, 1) = 1",
                (tercero_id, tipo))
    row = cur.fetchone()
    return row[0] if row else None


def siguiente_codigo_caso() -> str:
    """Código correlativo del caso (CASLEG001, CASLEG002, ...), usando la tabla compartida
    secuencias_sap (misma que ya usan Contratos y Reembolsos) bajo el nombre 'casos_legales'."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM secuencias_sap WHERE nombre = 'casos_legales')
            INSERT INTO secuencias_sap (nombre, ultimo_valor) VALUES ('casos_legales', 0)
    """)
    cur.execute("UPDATE secuencias_sap SET ultimo_valor = ultimo_valor + 1 WHERE nombre = 'casos_legales'")
    cur.execute("SELECT ultimo_valor FROM secuencias_sap WHERE nombre = 'casos_legales'")
    row = cur.fetchone()
    conn.commit()
    n = int(row[0]) if row else 1
    return f"{CODIGO_PREFIJO}{n:03d}"


def set_codigo_caso(caso_id: int, codigo: str) -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE casos_legales SET codigo = ? WHERE id = ?", (codigo, caso_id))
    conn.commit()


def get_tipos_tarea() -> list[str]:
    """Tipos de tarea ya usados (sugerencias del campo)."""
    cur = get_db().cursor()
    cur.execute("SELECT DISTINCT TOP 100 tipo_tarea FROM casos_legales WHERE activo = 1 ORDER BY tipo_tarea")
    return [r[0] for r in cur.fetchall()]


def get_caso(caso_id: int) -> dict | None:
    cur = get_db().cursor()
    cur.execute("SELECT * FROM casos_legales WHERE id = ? AND activo = 1", (caso_id,))
    row = cur.fetchone()
    return dict(row) if row else None


def actualizar_caso(caso_id: int, d: dict) -> bool:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE casos_legales
           SET fecha = ?, tipo_tarea = ?, descripcion = ?, tercero_tipo = ?, tercero_id = ?,
               cliente_proveedor = ?, tiempo_asignado = ?, requirente_id = ?, requirente = ?
         WHERE id = ? AND activo = 1 AND estado = ?
    """, (d["fecha"].isoformat(), d["tipo_tarea"], d["descripcion"], d["tercero_tipo"],
          d["tercero_id"], d["cliente_proveedor"], d["tiempo_asignado"], d["requirente_id"],
          d["requirente"], caso_id, ESTADO_ABIERTO))
    ok = cur.rowcount > 0
    conn.commit()
    return ok


def eliminar_caso(caso_id: int) -> bool:
    """Eliminación lógica (activo = 0)."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE casos_legales SET activo = 0 WHERE id = ? AND activo = 1", (caso_id,))
    ok = cur.rowcount > 0
    conn.commit()
    return ok


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


# ── Usuarios / notificaciones ───────────────────────────────

def get_jefe_id(usuario_id: int) -> int | None:
    cur = get_db().cursor()
    cur.execute("SELECT jefe_id FROM usuarios WHERE id = ?", (usuario_id,))
    row = cur.fetchone()
    return row[0] if row and row[0] else None


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
