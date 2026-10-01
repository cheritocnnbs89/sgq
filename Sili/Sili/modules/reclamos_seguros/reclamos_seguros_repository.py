# modules/reclamos_seguros/reclamos_seguros_repository.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from modules.db import get_db
from .reclamos_seguros_constants import ESTADO_ABIERTO, ESTADO_CERRADO, CODIGO_PREFIJO, ORIGEN_MANUAL


def _rows(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


# ── Casos ────────────────────────────────────────────────────

def crear_caso(d: dict, usuario_id: int, usuario_nombre: str) -> int:
    """d = datos validados del formulario (ver routes)."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO reclamos_seguros_casos
            (tipo_caso, broker_tercero_id, descripcion, fecha, estado,
             solicitante_id, solicitante_nombre, creado_por_id, creado_por_nombre)
        OUTPUT INSERTED.id
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (d["tipo_caso"], d["broker_tercero_id"], d["descripcion"], d["fecha"].isoformat(),
          ESTADO_ABIERTO, d["solicitante_id"], d["solicitante_nombre"], usuario_id, usuario_nombre))
    row = cur.fetchone()
    conn.commit()
    return int(row[0])


def siguiente_codigo_caso() -> str:
    """Código correlativo del caso (SEG001, SEG002, ...), usando la tabla compartida
    secuencias_sap (misma que ya usan Contratos, Reembolsos y Casos Legales)."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM secuencias_sap WHERE nombre = 'reclamos_seguros')
            INSERT INTO secuencias_sap (nombre, ultimo_valor) VALUES ('reclamos_seguros', 0)
    """)
    cur.execute("UPDATE secuencias_sap SET ultimo_valor = ultimo_valor + 1 WHERE nombre = 'reclamos_seguros'")
    cur.execute("SELECT ultimo_valor FROM secuencias_sap WHERE nombre = 'reclamos_seguros'")
    row = cur.fetchone()
    conn.commit()
    n = int(row[0]) if row else 1
    return f"{CODIGO_PREFIJO}{n:03d}"


def set_codigo_caso(caso_id: int, codigo: str) -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE reclamos_seguros_casos SET codigo = ? WHERE id = ?", (codigo, caso_id))
    conn.commit()


def get_casos(estado: str | None = None, tipo_caso: str | None = None,
              visible_para: int | None = None) -> list[dict]:
    """visible_para=None -> todos (admin/coordinador/rol con visibilidad total). Si no, casos
    que registró ese usuario, los suyos como solicitante, o los de sus subordinados directos."""
    sql = """
        SELECT c.id, c.codigo, c.tipo_caso, c.fecha, c.descripcion, c.estado, c.sub_estado,
               c.broker_tercero_id, t.nombre AS broker_nombre,
               c.solicitante_id, c.solicitante_nombre,
               c.creado_por_id, c.creado_por_nombre, c.fecha_creacion,
               c.cerrado_por_nombre, c.fecha_cierre, c.observacion_cierre,
               (
                   (SELECT COUNT(*) FROM reclamos_seguros_seguimiento s
                     WHERE s.caso_id = c.id AND s.activo = 1)
                   + CASE WHEN c.estado = 'CERRADO' THEN 1 ELSE 0 END
               ) AS n_seguimiento
        FROM reclamos_seguros_casos c
        LEFT JOIN terceros t ON t.id = c.broker_tercero_id
        WHERE c.activo = 1
    """
    params: list = []
    if estado:
        sql += " AND c.estado = ?"
        params.append(estado)
    if tipo_caso:
        sql += " AND c.tipo_caso = ?"
        params.append(tipo_caso)
    if visible_para:
        sql += (" AND (c.creado_por_id = ? OR c.solicitante_id = ? OR c.creado_por_id IN "
                "(SELECT u.id FROM usuarios u WHERE u.jefe_id = ?))")
        params += [visible_para, visible_para, visible_para]
    sql += " ORDER BY c.id DESC"
    cur = get_db().cursor()
    cur.execute(sql, params)
    return _rows(cur)


def get_caso(caso_id: int) -> dict | None:
    cur = get_db().cursor()
    cur.execute("""
        SELECT c.*, t.nombre AS broker_nombre, t.email AS broker_email
        FROM reclamos_seguros_casos c
        LEFT JOIN terceros t ON t.id = c.broker_tercero_id
        WHERE c.id = ? AND c.activo = 1
    """, (caso_id,))
    row = cur.fetchone()
    return dict(row) if row else None


def get_brokers_combo() -> list[dict]:
    """Aseguradoras/brokers = terceros tipo 'P' (proveedor). Solo tiene sentido elegir uno
    que tenga correo configurado -- la notificación al broker se envía a esa dirección."""
    cur = get_db().cursor()
    cur.execute("""
        SELECT id, nombre, email
        FROM terceros
        WHERE tipo = 'P' AND COALESCE(activo, 1) = 1
        ORDER BY nombre
    """)
    return _rows(cur)


def get_usuario_nombre(usuario_id: int) -> str | None:
    cur = get_db().cursor()
    cur.execute("SELECT nombre_completo FROM usuarios WHERE id = ? AND COALESCE(disabled, 0) = 0",
                (usuario_id,))
    row = cur.fetchone()
    return row[0] if row else None


def get_usuarios_combo() -> list[dict]:
    cur = get_db().cursor()
    cur.execute("""
        SELECT u.id, u.nombre_completo AS nombre, COALESCE(d.nombre, '') AS departamento
        FROM usuarios u
        LEFT JOIN departamentos d ON d.id = u.departamento_id
        WHERE COALESCE(u.disabled, 0) = 0 AND TRIM(COALESCE(u.nombre_completo, '')) <> ''
        ORDER BY u.nombre_completo
    """)
    return _rows(cur)


def actualizar_sub_estado(caso_id: int, sub_estado: str) -> bool:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE reclamos_seguros_casos SET sub_estado = ?
         WHERE id = ? AND activo = 1 AND estado = ?
    """, (sub_estado or None, caso_id, ESTADO_ABIERTO))
    ok = cur.rowcount > 0
    conn.commit()
    return ok


def eliminar_caso(caso_id: int) -> bool:
    """Eliminación lógica (activo = 0)."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE reclamos_seguros_casos SET activo = 0 WHERE id = ? AND activo = 1", (caso_id,))
    ok = cur.rowcount > 0
    conn.commit()
    return ok


def cerrar_caso(caso_id: int, observacion: str, usuario_id: int, usuario_nombre: str) -> bool:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE reclamos_seguros_casos
           SET estado = ?, cerrado_por_id = ?, cerrado_por_nombre = ?,
               fecha_cierre = GETDATE(), observacion_cierre = ?
         WHERE id = ? AND activo = 1 AND estado = ?
    """, (ESTADO_CERRADO, usuario_id, usuario_nombre, observacion or None,
          caso_id, ESTADO_ABIERTO))
    ok = cur.rowcount > 0
    conn.commit()
    return ok


# ── Seguimiento ──────────────────────────────────────────────

def add_seguimiento(caso_id: int, observacion: str, usuario_id: int | None = None,
                     usuario_nombre: str | None = None, origen: str = ORIGEN_MANUAL,
                     remitente_email: str | None = None, message_id: str | None = None,
                     conversation_id: str | None = None) -> int:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO reclamos_seguros_seguimiento
            (caso_id, origen, observacion, usuario_id, usuario_nombre,
             remitente_email, message_id, conversation_id)
        OUTPUT INSERTED.id
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (caso_id, origen, observacion, usuario_id, usuario_nombre,
          remitente_email, message_id, conversation_id))
    row = cur.fetchone()
    conn.commit()
    return int(row[0])


def get_seguimiento(caso_id: int) -> list[dict]:
    cur = get_db().cursor()
    cur.execute("""
        SELECT id, origen, observacion, usuario_id, usuario_nombre,
               remitente_email, fecha
        FROM reclamos_seguros_seguimiento
        WHERE caso_id = ? AND activo = 1
        ORDER BY fecha, id
    """, (caso_id,))
    return _rows(cur)


def buscar_caso_por_conversation_id(conversation_id: str) -> dict | None:
    """Para el hilo de correo: encuentra a qué caso pertenece una respuesta ya vinculada
    por conversation_id (ver reclamos_seguros_email_poller, fase 4)."""
    if not conversation_id:
        return None
    cur = get_db().cursor()
    cur.execute("""
        SELECT TOP 1 c.*
        FROM reclamos_seguros_casos c
        INNER JOIN reclamos_seguros_seguimiento s ON s.caso_id = c.id
        WHERE s.conversation_id = ? AND c.activo = 1
        ORDER BY c.id DESC
    """, (conversation_id,))
    row = cur.fetchone()
    return dict(row) if row else None


def buscar_caso_por_codigo(codigo: str) -> dict | None:
    """Respaldo de threading: matchea por el código del caso si viene en el asunto del
    correo (fuera del hilo original)."""
    if not codigo:
        return None
    cur = get_db().cursor()
    cur.execute("SELECT * FROM reclamos_seguros_casos WHERE codigo = ? AND activo = 1", (codigo,))
    row = cur.fetchone()
    return dict(row) if row else None


# ── Adjuntos ─────────────────────────────────────────────────

def insert_adjunto(caso_id: int, seguimiento_id: int | None, nombre_original: str,
                    nombre_guardado: str, tamano: int, usuario_id: int | None,
                    usuario_nombre: str | None) -> int:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO reclamos_seguros_adjuntos
            (caso_id, seguimiento_id, nombre_original, nombre_guardado, tamano,
             usuario_id, usuario_nombre)
        OUTPUT INSERTED.id
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (caso_id, seguimiento_id, nombre_original, nombre_guardado, tamano,
          usuario_id, usuario_nombre))
    row = cur.fetchone()
    conn.commit()
    return int(row[0])


def get_adjuntos(caso_id: int) -> list[dict]:
    cur = get_db().cursor()
    cur.execute("""
        SELECT id, seguimiento_id, nombre_original, nombre_guardado, tamano, fecha
        FROM reclamos_seguros_adjuntos
        WHERE caso_id = ? AND activo = 1
        ORDER BY fecha, id
    """, (caso_id,))
    return _rows(cur)


# ── Fase 2: correo entrante / vencimiento ───────────────────────

def existe_seguimiento_con_message_id(message_id: str) -> bool:
    if not message_id:
        return False
    cur = get_db().cursor()
    cur.execute("SELECT 1 FROM reclamos_seguros_seguimiento WHERE message_id = ?", (message_id,))
    return cur.fetchone() is not None


def get_casos_para_alerta_vencimiento(umbral_dias: int, columna_notificado: str) -> list[dict]:
    """Casos ABIERTOS con más de umbral_dias desde fecha_creacion, que aún no se
    notificaron por esa columna. columna_notificado solo llega desde
    UMBRALES_VENCIMIENTO_DIAS (reclamos_seguros_constants.py), nunca de entrada
    externa -- por eso es seguro armar el SQL con f-string aquí."""
    cur = get_db().cursor()
    cur.execute(f"""
        SELECT id, codigo, tipo_caso, solicitante_nombre, fecha, fecha_creacion
        FROM reclamos_seguros_casos
        WHERE activo = 1 AND estado = ? AND {columna_notificado} = 0
          AND fecha_creacion <= DATEADD(day, -?, GETDATE())
        ORDER BY fecha_creacion
    """, (ESTADO_ABIERTO, umbral_dias))
    return _rows(cur)


def marcar_notificado_vencimiento(caso_id: int, columna_notificado: str) -> None:
    """columna_notificado: ver nota en get_casos_para_alerta_vencimiento."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(f"UPDATE reclamos_seguros_casos SET {columna_notificado} = 1 WHERE id = ?", (caso_id,))
    conn.commit()


def get_destinatarios_notificacion_vencimiento(roles: list[str]) -> list[str]:
    if not roles:
        return []
    placeholders = ",".join("?" for _ in roles)
    cur = get_db().cursor()
    cur.execute(f"""
        SELECT DISTINCT email FROM usuarios
        WHERE COALESCE(disabled, 0) = 0 AND email IS NOT NULL AND TRIM(email) <> ''
          AND LOWER(rol) IN ({placeholders})
    """, [r.lower() for r in roles])
    return [r[0] for r in cur.fetchall()]


# ── Combinar casos (fase 5 -- placeholder de datos, la UI se hace después) ────

def combinar_casos(principal_id: int, secundario_id: int, usuario_id: int, usuario_nombre: str) -> None:
    """Mueve todo el seguimiento/adjuntos del caso secundario al principal, y cierra el
    secundario dejando constancia de la fusión."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE reclamos_seguros_seguimiento SET caso_id = ? WHERE caso_id = ?",
                (principal_id, secundario_id))
    cur.execute("UPDATE reclamos_seguros_adjuntos SET caso_id = ? WHERE caso_id = ?",
                (principal_id, secundario_id))
    cur.execute("""
        UPDATE reclamos_seguros_casos
           SET estado = ?, cerrado_por_id = ?, cerrado_por_nombre = ?,
               fecha_cierre = GETDATE(),
               observacion_cierre = CONCAT('Fusionado con el caso principal #', ?)
         WHERE id = ?
    """, (ESTADO_CERRADO, usuario_id, usuario_nombre, principal_id, secundario_id))
    conn.commit()
