# modules/aws_tickets_sync.py
# -*- coding: utf-8 -*-
"""
Polling de tickets generados desde WhatsApp (Twilio → Bedrock → AWS API Gateway).

Flujo:
  GET  /tickets/pendientes-flask  → lista tickets en estado PENDIENTE_FLASK
  Por cada ticket:
    - Resolver creador_id  por telefono_tecnico  (usuarios.telefono)
    - Resolver usuario_id  por usuario_alias (username) o nombre parcial
    - Crear tarea con el mismo servicio que la bandeja de correos
    - Notificar al técnico por correo (send_assignment_emails)
  POST /tickets/resultado-flask   → CREADO_EN_FLASK | ERROR_FLASK | PENDIENTE_CONFIRMACION_USUARIO
"""

import logging
import os
import unicodedata
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

_AWS_BASE   = None
_AWS_TOKEN  = None
_ENABLED    = False
_TIPO_ID    = None
_EMPRESA_ID = None


def _load_config():
    global _AWS_BASE, _AWS_TOKEN, _ENABLED, _TIPO_ID, _EMPRESA_ID
    _AWS_BASE   = (os.environ.get("AWS_TICKETS_API_URL") or "").rstrip("/")
    _AWS_TOKEN  = (os.environ.get("AWS_TICKETS_API_TOKEN") or "").strip()
    _ENABLED    = os.environ.get("AWS_TICKETS_ENABLED", "0").strip() == "1"
    try:
        _TIPO_ID = int(os.environ.get("AWS_TICKETS_DEFAULT_TIPO_TAREA_ID") or 0) or None
    except ValueError:
        _TIPO_ID = None
    try:
        _EMPRESA_ID = int(os.environ.get("AWS_TICKETS_DEFAULT_EMPRESA_ID") or 0) or None
    except ValueError:
        _EMPRESA_ID = None


def _headers():
    return {
        "X-Api-Token": _AWS_TOKEN,
        "Content-Type": "application/json",
    }


def _get_db():
    from .db import get_db
    return get_db()


# ─────────────────────────────────────────────────────────────
# Normalización de texto para comparación
# ─────────────────────────────────────────────────────────────

def _normalizar(texto: str) -> str:
    """Convierte a minúsculas y elimina tildes/diacríticos."""
    nfkd = unicodedata.normalize("NFKD", texto or "")
    sin_tildes = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sin_tildes.lower().strip()


# ─────────────────────────────────────────────────────────────
# Resolución de usuarios
# ─────────────────────────────────────────────────────────────

def _resolver_por_telefono(conn, telefono: str):
    """Busca usuario activo por campo telefono (coincidencia exacta)."""
    if not telefono:
        return None
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM usuarios WHERE telefono = ? AND COALESCE(disabled, 0) = 0",
        (telefono.strip(),)
    )
    row = cur.fetchone()
    if not row:
        return None
    try:
        return row["id"]
    except Exception:
        return row[0]


def _resolver_por_username(conn, alias: str):
    """Busca usuario activo por username exacto (case-insensitive)."""
    if not alias:
        return None
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM usuarios WHERE LOWER(username) = ? AND COALESCE(disabled, 0) = 0",
        (alias.strip().lower(),)
    )
    row = cur.fetchone()
    if not row:
        return None
    try:
        return row["id"]
    except Exception:
        return row[0]


def _resolver_por_nombre(conn, nombre_texto: str):
    """
    Búsqueda fuzzy por nombre completo:
    - Normaliza tildes y mayúsculas tanto en el texto buscado como en la BD
    - Filtra por cada palabra ≥ 3 chars usando LIKE
    - Si hay 1 resultado exacto → retorna (id, [])
    - Si hay varios → retorna (None, [candidatos])
    - Si no hay → retorna (None, [])
    """
    if not nombre_texto:
        return None, []

    palabras = [p for p in _normalizar(nombre_texto).split() if len(p) >= 3]
    if not palabras:
        return None, []

    # SQL Server no tiene función nativa de quitar tildes fácilmente,
    # por eso buscamos con LIKE sobre nombre normalizado usando COLLATE
    # que en la mayoría de instancias ya es case/accent-insensitive.
    # Como fallback también construimos condiciones para cada palabra.
    conds  = " AND ".join(
        ["nombre_completo LIKE ? COLLATE Latin1_General_CI_AI" for _ in palabras]
    )
    params = [f"%{p}%" for p in palabras]
    params_q = params + params  # se usa dos veces en la query

    cur = conn.cursor()
    # Traemos todos los que coinciden con las palabras clave
    cur.execute(
        f"""
        SELECT id, nombre_completo, username, COALESCE(email,'') AS email
        FROM usuarios
        WHERE {conds}
          AND COALESCE(disabled, 0) = 0
        """,
        params
    )
    rows = cur.fetchall()

    if not rows:
        return None, []

    candidatos = []
    for r in rows:
        try:
            candidatos.append({
                "usuario_id": r["id"],
                "nombre":     r["nombre_completo"],
                "username":   r["username"],
                "email":      r["email"],
            })
        except Exception:
            candidatos.append({
                "usuario_id": r[0],
                "nombre":     r[1],
                "username":   r[2],
                "email":      r[3],
            })

    if len(candidatos) == 1:
        return candidatos[0]["usuario_id"], []

    # Intento de desambiguar: si algún candidato tiene el username dentro del texto buscado
    texto_norm = _normalizar(nombre_texto)
    for c in candidatos:
        if _normalizar(c["username"]) in texto_norm:
            return c["usuario_id"], []

    return None, candidatos


def _get_usuario_info(conn, usuario_id: int) -> dict:
    """Devuelve nombre, email y telefono de un usuario."""
    cur = conn.cursor()
    cur.execute(
        "SELECT COALESCE(nombre_completo, username) AS nombre, COALESCE(email,'') AS email FROM usuarios WHERE id = ?",
        (usuario_id,)
    )
    row = cur.fetchone()
    if not row:
        return {"nombre": "", "email": ""}
    try:
        return {"nombre": row["nombre"], "email": row["email"]}
    except Exception:
        return {"nombre": row[0], "email": row[1]}


# ─────────────────────────────────────────────────────────────
# Reporte a AWS
# ─────────────────────────────────────────────────────────────

def _reportar_resultado(payload: dict):
    try:
        res = requests.post(
            f"{_AWS_BASE}/tickets/resultado-flask",
            json=payload,
            headers=_headers(),
            timeout=15,
        )
        if res.status_code not in (200, 201):
            logger.warning("[AWS_TICKETS] resultado-flask HTTP %s: %s", res.status_code, res.text[:200])
    except Exception as exc:
        logger.exception("[AWS_TICKETS] Error al reportar resultado ticket %s: %s",
                         payload.get("ticket_id"), exc)


# ─────────────────────────────────────────────────────────────
# Procesamiento de un ticket
# ─────────────────────────────────────────────────────────────

def _procesar_ticket(conn, ticket: dict):
    ticket_id    = ticket.get("ticket_id", "")
    telefono_tec = (ticket.get("telefono_tecnico") or "").strip()
    tj           = ticket.get("ticket_json") or {}

    alias        = (tj.get("usuario_alias") or "").strip()
    nombre_texto = (tj.get("usuario_solicitante_texto") or "").strip()
    titulo       = (tj.get("asunto") or "Sin asunto").strip()
    descripcion  = (tj.get("descripcion") or "").strip()
    fecha_aten   = (tj.get("fecha_atencion") or "").strip()
    hora_inicio  = (tj.get("hora_inicio") or "").strip()
    hora_fin     = (tj.get("hora_fin") or "").strip()
    origen       = tj.get("origen", "whatsapp_audio")

    # ── 1. Resolver creador (técnico que grabó el audio) ──────
    creador_id = _resolver_por_telefono(conn, telefono_tec)
    if not creador_id:
        logger.warning("[AWS_TICKETS] Ticket %s: no se encontró técnico con teléfono '%s'",
                       ticket_id, telefono_tec)
        _reportar_resultado({
            "ticket_id": ticket_id,
            "estado":    "ERROR_FLASK",
            "error":     f"No se encontró técnico con teléfono '{telefono_tec}'. "
                         "Registre el número en la ficha del usuario.",
        })
        return

    # ── 2. Resolver solicitante ───────────────────────────────
    solicitante_id = None
    candidatos     = []

    # Prioridad 1: alias (username exacto)
    if alias:
        solicitante_id = _resolver_por_username(conn, alias)

    # Prioridad 2: nombre parcial
    if not solicitante_id and nombre_texto:
        # Intentar también como username antes de ir al fuzzy
        solicitante_id = _resolver_por_username(conn, nombre_texto)

    if not solicitante_id and nombre_texto:
        solicitante_id, candidatos = _resolver_por_nombre(conn, nombre_texto)

    if not solicitante_id and candidatos:
        _reportar_resultado({
            "ticket_id":  ticket_id,
            "estado":     "PENDIENTE_CONFIRMACION_USUARIO",
            "mensaje":    f"Se encontraron {len(candidatos)} usuarios posibles para '{nombre_texto}'",
            "candidatos": [
                {"usuario_id": c["usuario_id"], "nombre": c["nombre"]}
                for c in candidatos
            ],
        })
        return

    if not solicitante_id:
        # No se resolvió el solicitante: asignar al mismo técnico y continuar
        solicitante_id = creador_id
        logger.info("[AWS_TICKETS] Ticket %s: solicitante '%s' no resuelto, se asigna al técnico (id=%s)",
                    ticket_id, nombre_texto or alias, creador_id)

    # ── 3. Armar fechas ───────────────────────────────────────
    fi_str = fc_str = None
    if fecha_aten:
        if hora_inicio:
            fi_str = f"{fecha_aten} {hora_inicio}:00"
        if hora_fin:
            fc_str = f"{fecha_aten} {hora_fin}:00"

    now = datetime.now()
    estado = "Por iniciar"
    if fc_str:
        try:
            if datetime.strptime(fc_str, "%Y-%m-%d %H:%M:%S") < now:
                estado = "Atrasada"
            else:
                estado = "En desarrollo"
        except ValueError:
            pass

    # ── 4. Crear tarea usando el repositorio compartido ───────
    from .tasks.task_repository import (
        repo_insertar_tarea,
        repo_insertar_tarea_responsable_si_no_existe,
    )

    try:
        tarea_id = repo_insertar_tarea(conn, {
            "titulo":          titulo,
            "descripcion":     descripcion,
            "estado":          estado,
            "fecha_creacion":  now.strftime("%Y-%m-%d %H:%M:%S"),
            "fecha_inicio":    fi_str,
            "fecha_compromiso": fc_str,
            "fecha_fin":       None,
            "usuario_id":      creador_id,
            "creador_id":      creador_id,
            "solicitante_id":  solicitante_id,
            "tipo_tarea_id":   _TIPO_ID,
            "empresa_id":      _EMPRESA_ID,
        })
        repo_insertar_tarea_responsable_si_no_existe(conn, tarea_id, creador_id)
        conn.commit()
        logger.info("[AWS_TICKETS] Ticket %s → tarea %07d creada OK (técnico=%s solicitante=%s)",
                    ticket_id, tarea_id, creador_id, solicitante_id)
    except Exception as exc:
        conn.rollback()
        logger.exception("[AWS_TICKETS] Error al crear tarea para ticket %s", ticket_id)
        _reportar_resultado({
            "ticket_id": ticket_id,
            "estado":    "ERROR_FLASK",
            "error":     f"Error interno al crear tarea: {exc}",
        })
        return

    # ── 5. Notificar al técnico por correo ────────────────────
    try:
        from .email_to_task.email_inbox_service import send_assignment_emails
        tec_info = _get_usuario_info(conn, creador_id)
        sol_info = _get_usuario_info(conn, solicitante_id)

        send_assignment_emails(
            inbox_id=0,
            tarea_id=tarea_id,
            from_email=sol_info["email"] or "",
            from_name=sol_info["nombre"] or nombre_texto or alias or "Solicitante",
            subject=titulo,
            tecnico_email=tec_info["email"] or "",
            tecnico_nombre=tec_info["nombre"] or "",
        )
    except Exception as notif_exc:
        logger.warning("[AWS_TICKETS] No se pudo enviar correo de notificación tarea %07d: %s",
                       tarea_id, notif_exc)

    # ── 6. Reportar éxito a AWS ───────────────────────────────
    _reportar_resultado({
        "ticket_id":      ticket_id,
        "estado":         "CREADO_EN_FLASK",
        "flask_tarea_id": tarea_id,
        "mensaje":        f"Tarea {tarea_id:07d} creada correctamente",
    })


# ─────────────────────────────────────────────────────────────
# Punto de entrada del scheduler
# ─────────────────────────────────────────────────────────────

def process_whatsapp_tickets(app=None):
    """
    Consulta AWS por tickets pendientes y crea tareas locales.
    Llamar desde el scheduler cada 2 minutos.
    """
    _load_config()

    if not _ENABLED:
        logger.debug("[AWS_TICKETS] Deshabilitado (AWS_TICKETS_ENABLED != 1)")
        return 0

    if not _AWS_BASE or not _AWS_TOKEN:
        logger.warning("[AWS_TICKETS] AWS_TICKETS_API_URL o AWS_TICKETS_API_TOKEN no configurados")
        return 0

    ctx = app.app_context() if app else None
    if ctx:
        ctx.push()

    try:
        res = requests.get(
            f"{_AWS_BASE}/tickets/pendientes-flask",
            headers=_headers(),
            timeout=15,
        )

        if res.status_code != 200:
            logger.error("[AWS_TICKETS] GET pendientes HTTP %s: %s", res.status_code, res.text[:200])
            return 0

        data    = res.json()
        tickets = data.get("tickets") or []

        if not tickets:
            logger.debug("[AWS_TICKETS] Sin tickets pendientes")
            return 0

        logger.info("[AWS_TICKETS] %d ticket(s) pendientes", len(tickets))
        conn = _get_db()

        for ticket in tickets:
            try:
                _procesar_ticket(conn, ticket)
            except Exception:
                logger.exception("[AWS_TICKETS] Fallo inesperado procesando ticket %s",
                                 ticket.get("ticket_id"))

        return len(tickets)

    except Exception as exc:
        logger.exception("[AWS_TICKETS] Error general: %s", exc)
        return 0

    finally:
        if ctx:
            ctx.pop()
