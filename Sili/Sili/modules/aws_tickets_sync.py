# modules/aws_tickets_sync.py
# -*- coding: utf-8 -*-
"""
Polling de tickets generados desde WhatsApp (Twilio → Bedrock → AWS API Gateway).

Flujo:
  GET  /tickets/pendientes-flask  → lista tickets en estado PENDIENTE_FLASK
  Por cada ticket:
    - Resolver creador_id  por telefono_tecnico  (usuarios.telefono)
    - Resolver usuario_id  por usuario_alias o usuario_solicitante_texto
    - Crear tarea local con svc_crear_tarea
  POST /tickets/resultado-flask   → reportar CREADO_EN_FLASK | ERROR_FLASK | PENDIENTE_CONFIRMACION_USUARIO
"""

import logging
import os
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
# Resolución de usuarios
# ─────────────────────────────────────────────────────────────

def _resolver_usuario_por_telefono(conn, telefono: str):
    """Busca un usuario activo por su campo telefono (coincidencia exacta)."""
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


def _resolver_usuario_por_alias(conn, alias: str):
    """Busca usuario activo por username exacto."""
    if not alias:
        return None, []
    cur = conn.cursor()
    cur.execute(
        "SELECT id, nombre_completo FROM usuarios WHERE LOWER(username) = LOWER(?) AND COALESCE(disabled, 0) = 0",
        (alias.strip(),)
    )
    row = cur.fetchone()
    if not row:
        return None, []
    try:
        return row["id"], []
    except Exception:
        return row[0], []


def _resolver_usuario_por_nombre(conn, nombre_texto: str):
    """
    Busca usuarios activos cuyo nombre_completo contenga todas las palabras del texto.
    Retorna (usuario_id, candidatos):
      - Si hay coincidencia exacta (1 resultado) → (id, [])
      - Si hay varios → (None, [lista de candidatos])
      - Si no hay → (None, [])
    """
    if not nombre_texto:
        return None, []

    palabras = [p for p in nombre_texto.strip().split() if len(p) >= 3]
    if not palabras:
        return None, []

    conds  = " AND ".join(["LOWER(nombre_completo) LIKE ?" for _ in palabras])
    params = [f"%{p.lower()}%" for p in palabras]

    cur = conn.cursor()
    cur.execute(
        f"SELECT id, nombre_completo FROM usuarios WHERE {conds} AND COALESCE(disabled, 0) = 0",
        params
    )
    rows = cur.fetchall()

    if not rows:
        return None, []

    candidatos = []
    for r in rows:
        try:
            candidatos.append({"usuario_id": r["id"], "nombre": r["nombre_completo"]})
        except Exception:
            candidatos.append({"usuario_id": r[0], "nombre": r[1]})

    if len(candidatos) == 1:
        return candidatos[0]["usuario_id"], []

    return None, candidatos


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
    ticket_id      = ticket.get("ticket_id", "")
    telefono_tec   = (ticket.get("telefono_tecnico") or "").strip()
    tj             = ticket.get("ticket_json") or {}

    alias          = (tj.get("usuario_alias") or "").strip()
    nombre_texto   = (tj.get("usuario_solicitante_texto") or "").strip()
    titulo         = (tj.get("asunto") or "Sin asunto").strip()
    descripcion    = (tj.get("descripcion") or "").strip()
    fecha_atencion = (tj.get("fecha_atencion") or "").strip()
    hora_inicio    = (tj.get("hora_inicio") or "").strip()
    hora_fin       = (tj.get("hora_fin") or "").strip()

    # Resolver creador (técnico que envió el audio)
    creador_id = _resolver_usuario_por_telefono(conn, telefono_tec)
    if not creador_id:
        logger.warning("[AWS_TICKETS] Ticket %s: no se encontró técnico con teléfono '%s'",
                       ticket_id, telefono_tec)
        _reportar_resultado({
            "ticket_id": ticket_id,
            "estado":    "ERROR_FLASK",
            "error":     f"No se encontró técnico con teléfono '{telefono_tec}'. "
                         "Registre el teléfono en la ficha del usuario.",
        })
        return

    # Resolver solicitante
    usuario_id  = None
    candidatos  = []

    if alias:
        usuario_id, _ = _resolver_usuario_por_alias(conn, alias)

    if not usuario_id and nombre_texto:
        usuario_id, candidatos = _resolver_usuario_por_nombre(conn, nombre_texto)

    if not usuario_id and candidatos:
        _reportar_resultado({
            "ticket_id":  ticket_id,
            "estado":     "PENDIENTE_CONFIRMACION_USUARIO",
            "mensaje":    "Se encontraron varios usuarios posibles",
            "candidatos": candidatos,
        })
        return

    if not usuario_id:
        # Asignar la tarea al mismo técnico como solicitante si no se resuelve
        usuario_id = creador_id
        logger.info("[AWS_TICKETS] Ticket %s: solicitante no resuelto, se usará el técnico (id=%s)",
                    ticket_id, creador_id)

    # Armar fechas
    fi_str = fc_str = None
    if fecha_atencion:
        if hora_inicio:
            fi_str = f"{fecha_atencion} {hora_inicio}:00"
        if hora_fin:
            fc_str = f"{fecha_atencion} {hora_fin}:00"

    # Crear tarea usando la lógica de servicio existente
    from .tasks.task_repository import (
        repo_insertar_tarea,
        repo_insertar_tarea_responsable_si_no_existe,
    )

    now = datetime.now()
    estado = "Por iniciar"
    if fc_str:
        try:
            fc_dt = datetime.strptime(fc_str, "%Y-%m-%d %H:%M:%S")
            if fc_dt < now:
                estado = "Atrasada"
            else:
                estado = "En desarrollo"
        except ValueError:
            pass

    try:
        tarea_id = repo_insertar_tarea(conn, {
            "titulo":          titulo,
            "descripcion":     descripcion,
            "estado":          estado,
            "fecha_creacion":  now.strftime("%Y-%m-%d %H:%M:%S"),
            "fecha_inicio":    fi_str,
            "fecha_compromiso": fc_str,
            "fecha_fin":       None,
            "usuario_id":      creador_id,      # responsable = técnico
            "creador_id":      creador_id,
            "solicitante_id":  usuario_id,
            "tipo_tarea_id":   _TIPO_ID,
            "empresa_id":      _EMPRESA_ID,
        })
        repo_insertar_tarea_responsable_si_no_existe(conn, tarea_id, creador_id)
        conn.commit()

        logger.info("[AWS_TICKETS] Ticket %s → tarea %s creada OK", ticket_id, tarea_id)
        _reportar_resultado({
            "ticket_id":      ticket_id,
            "estado":         "CREADO_EN_FLASK",
            "flask_tarea_id": tarea_id,
            "mensaje":        f"Tarea {tarea_id:07d} creada correctamente",
        })

    except Exception as exc:
        conn.rollback()
        logger.exception("[AWS_TICKETS] Error al crear tarea para ticket %s", ticket_id)
        _reportar_resultado({
            "ticket_id": ticket_id,
            "estado":    "ERROR_FLASK",
            "error":     f"Error interno al crear tarea: {exc}",
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
