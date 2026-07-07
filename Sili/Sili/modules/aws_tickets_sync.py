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


def _log(level: str, msg: str, *args):
    """Usa current_app.logger cuando hay contexto Flask, sino logging estándar."""
    try:
        from flask import current_app
        fn = getattr(current_app.logger, level, current_app.logger.info)
        fn(msg, *args)
    except Exception:
        fn = getattr(logger, level, logger.info)
        fn(msg, *args)

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
    """
    Convierte a minúsculas, elimina tildes/diacríticos y la 'h' muda.
    La 'h' es muda en español y la transcripción de audio (AWS Transcribe)
    la agrega u omite de forma inconsistente (ej. "Egas" -> "Hegas"),
    por lo que se descarta para que la comparación no falle por eso.
    """
    nfkd = unicodedata.normalize("NFKD", texto or "")
    sin_tildes = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sin_tildes.lower().replace("h", "").strip()


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


def _buscar_por_palabras(cur, palabras: list, operador: str = "AND") -> list:
    """Ejecuta búsqueda LIKE en nombre_completo con AND u OR entre palabras."""
    conds  = f" {operador} ".join(
        ["nombre_completo LIKE ? COLLATE Latin1_General_CI_AI" for _ in palabras]
    )
    params = [f"%{p}%" for p in palabras]
    cur.execute(
        f"""
        SELECT id, nombre_completo, username, COALESCE(email,'') AS email
        FROM usuarios
        WHERE {conds}
          AND COALESCE(disabled, 0) = 0
        """,
        params
    )
    candidatos = []
    for r in cur.fetchall():
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
    return candidatos


def _resolver_por_nombre(conn, nombre_texto: str):
    """
    Búsqueda fuzzy por nombre completo con degradación progresiva:
    1. Todas las palabras (AND)  → match exacto
    2. Palabras largas ≥4 chars con AND → si transcrip tiene apellido erróneo
    3. Cada palabra individualmente (OR) → al menos el nombre coincide
    En cada paso: 1 resultado → devuelve id; varios → desambigua por username;
    ninguno → siguiente paso.
    """
    if not nombre_texto:
        return None, []

    palabras_all  = [p for p in _normalizar(nombre_texto).split() if len(p) >= 3]
    palabras_long = [p for p in palabras_all if len(p) >= 4]
    if not palabras_all:
        return None, []

    texto_norm = _normalizar(nombre_texto)
    cur = conn.cursor()

    def _desambiguar(candidatos):
        if len(candidatos) == 1:
            return candidatos[0]["usuario_id"], []
        for c in candidatos:
            if _normalizar(c["username"]) in texto_norm:
                return c["usuario_id"], []
        return None, candidatos

    # Paso 1: todas las palabras AND
    candidatos = _buscar_por_palabras(cur, palabras_all, "AND")
    if candidatos:
        uid, ambig = _desambiguar(candidatos)
        if uid:
            return uid, []
        if ambig:
            return None, ambig

    # Paso 2: solo palabras largas AND (descarta posibles errores de transcripción en apellidos cortos)
    if palabras_long and palabras_long != palabras_all:
        candidatos = _buscar_por_palabras(cur, palabras_long, "AND")
        if candidatos:
            uid, ambig = _desambiguar(candidatos)
            if uid:
                _log("info", "[AWS_TICKETS] nombre resuelto por palabras largas: '%s' → %s",
                     nombre_texto, candidatos[0]["nombre"] if len(candidatos) == 1 else "ambiguo")
                return uid, []
            if ambig:
                return None, ambig

    return None, []


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
# Fallback: insertar en bandeja de soporte para asignación manual
# ─────────────────────────────────────────────────────────────

def _enviar_a_bandeja(conn, ticket: dict, motivo: str, candidatos: list = None) -> int | None:
    """
    Inserta el ticket en email_tickets_inbox con estado POR_ASIGNAR.
    Así aparece en la bandeja de soporte para que un coordinador lo asigne.
    Retorna el inbox_id creado, o None si falla.
    """
    tj          = ticket.get("ticket_json") or {}
    ticket_id   = ticket.get("ticket_id", "")
    titulo      = (tj.get("asunto") or "Sin asunto").strip()
    descripcion = (tj.get("descripcion") or "").strip()
    nombre_sol  = (tj.get("usuario_solicitante_texto") or tj.get("usuario_alias") or "Desconocido").strip()
    tecnico_tel = (ticket.get("telefono_tecnico") or "").strip()
    nombre_tec  = (ticket.get("nombre_tecnico") or "").strip()

    # Armamos el body con toda la info relevante para que el coordinador tenga contexto
    candidatos_txt = ""
    if candidatos:
        lineas = [f"  - {c['nombre']} (id={c['usuario_id']})" for c in candidatos]
        candidatos_txt = "\n\nCANDIDATOS POSIBLES:\n" + "\n".join(lineas)

    body = (
        f"Ticket WhatsApp recibido desde AWS (ticket_id: {ticket_id})\n"
        f"Técnico: {nombre_tec} ({tecnico_tel})\n"
        f"Solicitante indicado: {nombre_sol}\n"
        f"Motivo de no creación automática: {motivo}"
        f"{candidatos_txt}\n\n"
        f"Descripción original:\n{descripcion}"
    )

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # message_id único para evitar duplicados
    message_id = f"whatsapp:{ticket_id}"

    try:
        row = conn.execute(
            """
            INSERT INTO email_tickets_inbox
                (message_id, internet_id, from_email, from_name,
                 subject, body_text, received_at, estado, usuario_id_match)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, ?, 'POR_ASIGNAR', NULL)
            """,
            (
                message_id,
                ticket_id,
                "whatsapp@aws",
                nombre_sol,
                titulo[:500],
                body,
                now_str,
            )
        ).fetchone()
        conn.commit()
        inbox_id = row[0] if row else None
        _log("info", "[AWS_TICKETS] Ticket %s → bandeja inbox_id=%s (%s)", ticket_id, inbox_id, motivo)
        return inbox_id
    except Exception as exc:
        conn.rollback()
        _log("error", "[AWS_TICKETS] No se pudo insertar ticket %s en bandeja: %s", ticket_id, exc)
        return None


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
            _log("warning", "[AWS_TICKETS] resultado-flask HTTP %s: %s", res.status_code, res.text[:200])
    except Exception as exc:
        _log("error", "[AWS_TICKETS] Error al reportar resultado ticket %s: %s",
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
        motivo = f"No se encontró técnico con teléfono '{telefono_tec}'. Registre el número en la ficha del usuario."
        _log("warning", "[AWS_TICKETS] Ticket %s: %s", ticket_id, motivo)
        inbox_id = _enviar_a_bandeja(conn, ticket, motivo)
        _reportar_resultado({
            "ticket_id": ticket_id,
            "estado":    "ERROR_FLASK",
            "error":     motivo,
            "bandeja_inbox_id": inbox_id,
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
        motivo = f"Se encontraron {len(candidatos)} usuarios posibles para '{nombre_texto}'. Asignación manual requerida."
        inbox_id = _enviar_a_bandeja(conn, ticket, motivo, candidatos)
        _reportar_resultado({
            "ticket_id":        ticket_id,
            "estado":           "PENDIENTE_CONFIRMACION_USUARIO",
            "mensaje":          motivo,
            "bandeja_inbox_id": inbox_id,
            "candidatos": [
                {"usuario_id": c["usuario_id"], "nombre": c["nombre"]}
                for c in candidatos
            ],
        })
        return

    if not solicitante_id:
        # No se resolvió el solicitante: asignar al mismo técnico y continuar
        solicitante_id = creador_id
        _log("info", "[AWS_TICKETS] Ticket %s: solicitante '%s' no resuelto, se asigna al técnico (id=%s)",
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
        _log("info", "[AWS_TICKETS] Ticket %s → tarea %07d creada OK (técnico=%s solicitante=%s)",
                    ticket_id, tarea_id, creador_id, solicitante_id)
    except Exception as exc:
        conn.rollback()
        _log("error", "[AWS_TICKETS] Error al crear tarea para ticket %s", ticket_id)
        motivo = f"Error interno al crear tarea: {exc}"
        inbox_id = _enviar_a_bandeja(conn, ticket, motivo)
        _reportar_resultado({
            "ticket_id":        ticket_id,
            "estado":           "ERROR_FLASK",
            "error":            motivo,
            "bandeja_inbox_id": inbox_id,
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
        _log("warning", "[AWS_TICKETS] No se pudo enviar correo de notificación tarea %07d: %s",
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
        _log("debug", "[AWS_TICKETS] Deshabilitado (AWS_TICKETS_ENABLED != 1)")
        return 0

    if not _AWS_BASE or not _AWS_TOKEN:
        _log("warning", "[AWS_TICKETS] AWS_TICKETS_API_URL o AWS_TICKETS_API_TOKEN no configurados")
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
            _log("error", "[AWS_TICKETS] GET pendientes HTTP %s: %s", res.status_code, res.text[:200])
            return 0

        data    = res.json()
        tickets = data.get("tickets") or []

        if not tickets:
            _log("debug", "[AWS_TICKETS] Sin tickets pendientes")
            return 0

        _log("info", "[AWS_TICKETS] %d ticket(s) pendientes", len(tickets))
        conn = _get_db()

        for ticket in tickets:
            try:
                _procesar_ticket(conn, ticket)
            except Exception as _tex:
                tid = ticket.get("ticket_id", "?")
                _log("error", "[AWS_TICKETS] Fallo inesperado procesando ticket %s: %s", tid, _tex)
                try:
                    _reportar_resultado({
                        "ticket_id": tid,
                        "estado":    "ERROR_FLASK",
                        "error":     f"Excepción inesperada: {_tex}",
                    })
                except Exception:
                    pass

        return len(tickets)

    except Exception as exc:
        _log("error", "[AWS_TICKETS] Error general: %s", exc)
        return 0

    finally:
        if ctx:
            ctx.pop()

