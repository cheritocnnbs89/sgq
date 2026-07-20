# modules/email_to_task/email_inbox_service.py
# -*- coding: utf-8 -*-
"""
Servicio que:
  1. Llama a graph_fetcher para obtener correos nuevos de soporteti@...
  2. Verifica que no hayan sido procesados antes (tabla email_tickets_inbox)
  3. Crea un registro en email_tickets_inbox con estado POR_ASIGNAR
  4. Marca el correo como leído en Graph API
  5. Envía correo de confirmación al remitente con número de ticket

Creación de tarea formal: ocurre cuando un usuario de SISTEMAS QP asigna
responsable desde la "Bandeja por asignar" (ruta separada).
"""

from __future__ import annotations

import logging
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from modules.db import get_db, get_config_value
from modules.email_to_task.graph_fetcher import fetch_soporte_emails, mark_as_read

_log = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────
# Tabla — creada manualmente en SQL Server (ver migration abajo)
# ────────────────────────────────────────────────────────────────────
#
# Script SQL para ejecutar en SQL Server Management Studio:
#
# CREATE TABLE email_tickets_inbox (
#     id               INT IDENTITY(1,1) PRIMARY KEY,
#     message_id       NVARCHAR(500)  NOT NULL,
#     internet_id      NVARCHAR(500)  NULL,
#     from_email       NVARCHAR(200)  NOT NULL,
#     from_name        NVARCHAR(200)  NULL,
#     subject          NVARCHAR(500)  NOT NULL,
#     body_text        NVARCHAR(MAX)  NULL,
#     received_at      DATETIME2      NULL,
#     fecha_registro   DATETIME2      DEFAULT GETDATE(),
#     estado           NVARCHAR(50)   NOT NULL DEFAULT 'POR_ASIGNAR',
#     tarea_id         INT            NULL,
#     asignado_por_id  INT            NULL,
#     fecha_asignacion DATETIME2      NULL,
#     usuario_id_match INT            NULL,
#     confirmacion_enviada BIT        NOT NULL DEFAULT 0,
#     CONSTRAINT UQ_email_inbox_message_id UNIQUE (message_id)
# );
# CREATE INDEX IX_email_inbox_estado ON email_tickets_inbox (estado);
# CREATE INDEX IX_email_inbox_from   ON email_tickets_inbox (from_email);


def ensure_inbox_table():
    """
    Verifica que la tabla email_tickets_inbox existe (solo lectura — no crea).
    La tabla debe crearse manualmente en SQL Server con el script de arriba.
    """
    try:
        conn = get_db()
        conn.execute("SELECT TOP 1 id FROM email_tickets_inbox")
        _log.debug("[email_inbox] Tabla email_tickets_inbox OK")
    except Exception as exc:
        _log.warning(
            "[email_inbox] La tabla email_tickets_inbox no existe o no es accesible. "
            "Ejecuta el script SQL de creación en SQL Server Management Studio. Error: %s", exc
        )


# ────────────────────────────────────────────────────────────────────
# Buscar usuario por email
# ────────────────────────────────────────────────────────────────────

def _find_user_by_email(conn, email_addr: str) -> Optional[int]:
    """Devuelve el usuario_id si el email existe en la tabla usuarios."""
    try:
        row = conn.execute(
            "SELECT id FROM usuarios WHERE LOWER(email) = LOWER(?)",
            (email_addr,)
        ).fetchone()
        return row["id"] if row else None
    except Exception as exc:
        _log.warning("[email_inbox] Error buscando usuario por email '%s': %s", email_addr, exc)
        return None


# ────────────────────────────────────────────────────────────────────
# Correo de confirmación al remitente
# ────────────────────────────────────────────────────────────────────

def _send_confirmation_email(inbox_id: int, to_email: str, to_name: str, subject: str):
    # ── MODO PRUEBAS ────────────────────────────────────────────────
    # Redirige todos los correos de confirmación a una cuenta de prueba.
    # Cuando pases a producción, comenta las dos líneas siguientes.
    to_email = "jchavez1@quimpac.com.ec"
    to_name  = to_name or "Prueba"
    # ───────────────────────────────────────────────────────────────
    """Envía correo de confirmación al remitente con el número de ticket."""
    smtp_host = (get_config_value("smtp_host", "") or get_config_value("SMTP_HOST", "")).strip()
    smtp_port = int(get_config_value("smtp_port", "") or get_config_value("SMTP_PORT", "587") or 587)
    smtp_user = (get_config_value("smtp_user", "") or get_config_value("SMTP_USER", "")).strip()
    smtp_pass = (get_config_value("smtp_pass", "") or get_config_value("SMTP_PASS", "")).strip()
    smtp_from = (get_config_value("smtp_from", "") or get_config_value("SMTP_FROM", "") or smtp_user).strip()
    use_tls   = str(get_config_value("smtp_tls", "1") or "1").strip() == "1"

    if not smtp_host:
        _log.warning("[email_inbox] SMTP no configurado — no se envió confirmación para inbox_id=%d", inbox_id)
        return False

    nombre = to_name or to_email.split("@")[0].capitalize()
    ticket_code = f"TK-{inbox_id:05d}"

    html_body = f"""
    <html><body style="font-family:Arial,sans-serif; color:#333; max-width:600px; margin:0 auto;">
      <div style="background:#0d6efd; padding:20px; border-radius:8px 8px 0 0;">
        <h2 style="color:#fff; margin:0;">✅ Solicitud Recibida</h2>
      </div>
      <div style="padding:24px; background:#f8f9fa; border:1px solid #dee2e6; border-top:none; border-radius:0 0 8px 8px;">
        <p>Estimado/a <strong>{nombre}</strong>,</p>
        <p>Tu solicitud ha sido recibida y registrada en nuestro sistema de soporte.</p>
        <div style="background:#fff; border:1px solid #dee2e6; border-radius:6px; padding:16px; margin:16px 0;">
          <p style="margin:4px 0;"><strong>🎫 Ticket:</strong> <span style="font-size:18px; color:#0d6efd; font-weight:bold;">{ticket_code}</span></p>
          <p style="margin:4px 0;"><strong>📋 Asunto:</strong> {subject}</p>
          <p style="margin:4px 0;"><strong>📅 Fecha:</strong> {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
        </div>
        <p>El equipo de <strong>Sistemas QP</strong> revisará tu solicitud y asignará un responsable a la brevedad.</p>
        <p>Recibirás una notificación cuando la tarea sea asignada y otra cuando sea completada.</p>
        <hr style="border:none; border-top:1px solid #dee2e6; margin:20px 0;">
        <p style="font-size:12px; color:#6c757d;">
          Este es un correo automático. Para consultas adicionales, responde a este mensaje o escribe directamente a
          <a href="mailto:soporteti@quimpac.com.ec">soporteti@quimpac.com.ec</a>.
        </p>
      </div>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[{ticket_code}] Solicitud recibida: {subject}"
    msg["From"]    = smtp_from
    msg["To"]      = to_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        if use_tls:
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.ehlo()
                server.starttls()
                if smtp_user and smtp_pass:
                    server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_from, [to_email], msg.as_string())
        else:
            with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
                if smtp_user and smtp_pass:
                    server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_from, [to_email], msg.as_string())

        _log.info("[email_inbox] Confirmación enviada a %s (ticket %s)", to_email, ticket_code)
        return True

    except smtplib.SMTPAuthenticationError as exc:
        _log.error("[email_inbox] Error autenticación SMTP: %s", exc)
    except smtplib.SMTPException as exc:
        _log.error("[email_inbox] Error SMTP: %s", exc)
    except Exception as exc:
        _log.error("[email_inbox] Error inesperado enviando confirmación: %s", exc)

    return False


# ────────────────────────────────────────────────────────────────────
# Correos de asignación
# ────────────────────────────────────────────────────────────────────

def _smtp_send(smtp_from: str, to_email: str, msg) -> bool:
    """Envía un mensaje MIME usando la configuración SMTP de la BD."""
    smtp_host = (get_config_value("smtp_host", "") or get_config_value("SMTP_HOST", "")).strip()
    smtp_port = int(get_config_value("smtp_port", "") or get_config_value("SMTP_PORT", "587") or 587)
    smtp_user = (get_config_value("smtp_user", "") or get_config_value("SMTP_USER", "")).strip()
    smtp_pass = (get_config_value("smtp_pass", "") or get_config_value("SMTP_PASS", "")).strip()
    use_tls   = str(get_config_value("smtp_tls", "1") or "1").strip() == "1"

    if not smtp_host:
        _log.warning("[email_inbox] SMTP no configurado — no se envió correo a %s", to_email)
        return False
    try:
        if use_tls:
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.ehlo()
                server.starttls()
                if smtp_user and smtp_pass:
                    server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_from, [to_email], msg.as_string())
        else:
            with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
                if smtp_user and smtp_pass:
                    server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_from, [to_email], msg.as_string())
        return True
    except smtplib.SMTPAuthenticationError as exc:
        _log.error("[email_inbox] Error autenticación SMTP: %s", exc)
    except smtplib.SMTPException as exc:
        _log.error("[email_inbox] Error SMTP: %s", exc)
    except Exception as exc:
        _log.error("[email_inbox] Error inesperado SMTP: %s", exc)
    return False


def send_assignment_emails(
    inbox_id: int,
    tarea_id: int,
    from_email: str,
    from_name: str,
    subject: str,
    tecnico_email: str,
    tecnico_nombre: str,
):
    """
    Envía dos correos tras asignar un ticket:
      1. Al técnico asignado: notificación de nueva tarea
      2. Al solicitante original: confirmación de asignación

    En modo pruebas ambos van a jchavez1@quimpac.com.ec.
    """
    smtp_from = (get_config_value("smtp_from", "") or get_config_value("SMTP_FROM", "")
                 or get_config_value("smtp_user", "")).strip()
    ticket_code = f"TK-{inbox_id:05d}"
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")

    # ── MODO PRUEBAS ── comenta estas dos líneas en producción
    from_email    = "jchavez1@quimpac.com.ec"
    tecnico_email = "jchavez1@quimpac.com.ec"
    # ────────────────────────────────────────────────────────

    # 1. Correo al técnico asignado
    html_tecnico = f"""
    <html><body style="font-family:Arial,sans-serif;color:#333;max-width:600px;margin:0 auto;">
      <div style="background:#198754;padding:18px 24px;border-radius:8px 8px 0 0;">
        <h2 style="color:#fff;margin:0;">🔧 Nueva tarea asignada</h2>
      </div>
      <div style="padding:24px;background:#f8f9fa;border:1px solid #dee2e6;border-top:none;border-radius:0 0 8px 8px;">
        <p>Hola <strong>{tecnico_nombre}</strong>,</p>
        <p>Se te ha asignado el siguiente ticket de soporte para su gestión:</p>
        <div style="background:#fff;border:1px solid #dee2e6;border-radius:6px;padding:16px;margin:16px 0;">
          <p style="margin:4px 0;"><strong>🎫 Ticket:</strong> <span style="font-size:16px;color:#198754;font-weight:bold;">{ticket_code}</span></p>
          <p style="margin:4px 0;"><strong>📋 Asunto:</strong> {subject}</p>
          <p style="margin:4px 0;"><strong>👤 Solicitante:</strong> {from_name or from_email}</p>
          <p style="margin:4px 0;"><strong>📧 Correo:</strong> {from_email}</p>
          <p style="margin:4px 0;"><strong>📅 Asignado:</strong> {fecha}</p>
        </div>
        <p>Por favor gestiona esta solicitud a la brevedad posible.</p>
        <hr style="border:none;border-top:1px solid #dee2e6;margin:20px 0;">
        <p style="font-size:12px;color:#6c757d;">Sistema de Gestión Quimpac · soporteti@quimpac.com.ec</p>
      </div>
    </body></html>"""

    msg1 = MIMEMultipart("alternative")
    msg1["Subject"] = f"[{ticket_code}] Nueva tarea asignada: {subject}"
    msg1["From"]    = smtp_from
    msg1["To"]      = tecnico_email
    msg1.attach(MIMEText(html_tecnico, "html", "utf-8"))

    ok1 = _smtp_send(smtp_from, tecnico_email, msg1)
    if ok1:
        _log.info("[email_inbox] Correo asignación enviado al técnico %s (ticket %s)", tecnico_email, ticket_code)
    else:
        _log.warning("[email_inbox] No se pudo enviar correo al técnico %s", tecnico_email)

    # 2. Correo al solicitante
    nombre_sol = from_name or from_email.split("@")[0].capitalize()
    html_sol = f"""
    <html><body style="font-family:Arial,sans-serif;color:#333;max-width:600px;margin:0 auto;">
      <div style="background:#0d6efd;padding:18px 24px;border-radius:8px 8px 0 0;">
        <h2 style="color:#fff;margin:0;">✅ Tu ticket fue asignado</h2>
      </div>
      <div style="padding:24px;background:#f8f9fa;border:1px solid #dee2e6;border-top:none;border-radius:0 0 8px 8px;">
        <p>Estimado/a <strong>{nombre_sol}</strong>,</p>
        <p>Tu solicitud de soporte ha sido asignada a un técnico que la gestionará a la brevedad.</p>
        <div style="background:#fff;border:1px solid #dee2e6;border-radius:6px;padding:16px;margin:16px 0;">
          <p style="margin:4px 0;"><strong>🎫 Ticket:</strong> <span style="font-size:16px;color:#0d6efd;font-weight:bold;">{ticket_code}</span></p>
          <p style="margin:4px 0;"><strong>📋 Asunto:</strong> {subject}</p>
          <p style="margin:4px 0;"><strong>👨‍💻 Técnico asignado:</strong> {tecnico_nombre}</p>
          <p style="margin:4px 0;"><strong>📅 Fecha asignación:</strong> {fecha}</p>
        </div>
        <p>Te notificaremos cuando la tarea sea completada.</p>
        <hr style="border:none;border-top:1px solid #dee2e6;margin:20px 0;">
        <p style="font-size:12px;color:#6c757d;">Para seguimiento escribe a
          <a href="mailto:soporteti@quimpac.com.ec">soporteti@quimpac.com.ec</a></p>
      </div>
    </body></html>"""

    msg2 = MIMEMultipart("alternative")
    msg2["Subject"] = f"[{ticket_code}] Tu solicitud fue asignada a {tecnico_nombre}"
    msg2["From"]    = smtp_from
    msg2["To"]      = from_email
    msg2.attach(MIMEText(html_sol, "html", "utf-8"))

    ok2 = _smtp_send(smtp_from, from_email, msg2)
    if ok2:
        _log.info("[email_inbox] Correo asignación enviado al solicitante %s (ticket %s)", from_email, ticket_code)
    else:
        _log.warning("[email_inbox] No se pudo enviar correo al solicitante %s", from_email)

    return ok1, ok2


# ────────────────────────────────────────────────────────────────────
# Job principal (llamado por scheduler cada 2 minutos)
# ────────────────────────────────────────────────────────────────────

def process_incoming_emails():
    """
    Obtiene correos nuevos de soporteti@... y los registra en email_tickets_inbox.
    Devuelve cantidad de correos procesados.
    """
    emails = fetch_soporte_emails()
    if not emails:
        return 0

    try:
        conn = get_db()
    except Exception as exc:
        _log.error("[email_inbox] No se pudo obtener conexión BD: %s", exc)
        return 0

    processed = 0

    for em in emails:
        message_id      = em["message_id"]
        conversation_id = em.get("conversation_id") or ""

        # ── Verificar deduplicación exacta por message_id ──────────
        existing_msg = conn.execute(
            "SELECT id FROM email_tickets_inbox WHERE message_id = ?",
            (message_id,)
        ).fetchone()
        if not existing_msg:
            try:
                existing_msg = conn.execute(
                    "SELECT id FROM email_ticket_replies WHERE message_id = ?",
                    (message_id,)
                ).fetchone()
            except Exception:
                existing_msg = None  # Tabla aún no creada
        if existing_msg:
            mark_as_read(message_id)
            continue

        # ── Threading: ¿pertenece a una conversación ya abierta? ───
        # (requiere columna conversation_id — protegido si aún no existe)
        parent_ticket = None
        if conversation_id:
            try:
                parent_ticket = conn.execute(
                    "SELECT id, estado FROM email_tickets_inbox WHERE conversation_id = ?",
                    (conversation_id,)
                ).fetchone()
            except Exception:
                parent_ticket = None  # Columna aún no creada

        received_at = em.get("received_at")
        if received_at and hasattr(received_at, "replace"):
            received_at = received_at.replace(tzinfo=None)

        if parent_ticket:
            # ── Es una respuesta: agregar al hilo ──────────────────
            parent_id = parent_ticket["id"]
            try:
                conn.execute(
                    """
                    INSERT INTO email_ticket_replies
                        (inbox_id, message_id, from_email, from_name,
                         subject, body_text, body_html, received_at, has_attachments)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        parent_id,
                        message_id,
                        em["from_email"],
                        em.get("from_name") or "",
                        em.get("subject", "")[:500],
                        em.get("body_text") or "",
                        em.get("body_html") or "",
                        received_at,
                        1 if em.get("has_attachments") else 0,
                    )
                )
                conn.commit()
                mark_as_read(message_id)
                _log.info(
                    "[email_inbox] Respuesta en hilo inbox_id=%d de %s",
                    parent_id, em["from_email"]
                )
                processed += 1
            except Exception as exc:
                _log.error("[email_inbox] Error insertando respuesta hilo=%d: %s", parent_id, exc)
                try:
                    conn.rollback()
                except Exception:
                    pass
            continue

        # ── Ticket nuevo ───────────────────────────────────────────
        usuario_id = _find_user_by_email(conn, em["from_email"])

        try:
            # Intentar INSERT con columnas nuevas; si fallan (columnas no existen aún),
            # usar el INSERT básico sin ellas
            try:
                row = conn.execute(
                    """
                    INSERT INTO email_tickets_inbox
                        (message_id, internet_id, conversation_id,
                         from_email, from_name, subject,
                         body_text, body_html, received_at,
                         estado, usuario_id_match)
                    OUTPUT INSERTED.id
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'POR_ASIGNAR', ?)
                    """,
                    (
                        message_id,
                        em.get("internet_id") or "",
                        conversation_id,
                        em["from_email"],
                        em.get("from_name") or "",
                        em["subject"][:500],
                        em.get("body_text") or "",
                        em.get("body_html") or "",
                        received_at,
                        usuario_id,
                    )
                ).fetchone()
            except Exception:
                # Fallback: INSERT sin las columnas nuevas (columnas no creadas aún)
                row = conn.execute(
                    """
                    INSERT INTO email_tickets_inbox
                        (message_id, internet_id, from_email, from_name,
                         subject, body_text, received_at, estado, usuario_id_match)
                    OUTPUT INSERTED.id
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'POR_ASIGNAR', ?)
                    """,
                    (
                        message_id,
                        em.get("internet_id") or "",
                        em["from_email"],
                        em.get("from_name") or "",
                        em["subject"][:500],
                        em.get("body_text") or "",
                        received_at,
                        usuario_id,
                    )
                ).fetchone()
            conn.commit()
            inbox_id = row[0]

            _log.info(
                "[email_inbox] Nuevo ticket inbox_id=%d conv=%s de %s — '%s'",
                inbox_id, conversation_id[:20] if conversation_id else "—",
                em["from_email"], em["subject"]
            )

            mark_as_read(message_id)

            ok = _send_confirmation_email(
                inbox_id, em["from_email"],
                em.get("from_name") or "", em["subject"]
            )
            if ok:
                conn.execute(
                    "UPDATE email_tickets_inbox SET confirmacion_enviada = 1 WHERE id = ?",
                    (inbox_id,)
                )
                conn.commit()

            processed += 1

        except Exception as exc:
            _log.error("[email_inbox] Error insertando correo '%s': %s", em.get("subject"), exc)
            try:
                conn.rollback()
            except Exception:
                pass

    return processed


# ────────────────────────────────────────────────────────────────────
# Alerta de tickets sin asignar por más de 3 horas
# ────────────────────────────────────────────────────────────────────

# Conjunto en memoria para evitar re-alertar el mismo ticket en la misma sesión
_alerted_inbox_ids: set[int] = set()


def notify_unassigned_tickets():
    """
    Busca tickets en estado POR_ASIGNAR con más de 3 horas sin asignar
    y envía un correo de alerta a todos los usuarios activos de SISTEMAS QP.
    Evita re-alertar el mismo ticket dentro de la misma sesión del servidor.
    Devuelve cantidad de tickets alertados por primera vez.
    """
    try:
        conn = get_db()
    except Exception as exc:
        _log.error("[email_inbox] notify_unassigned_tickets: no se pudo obtener BD: %s", exc)
        return 0

    # Tickets POR_ASIGNAR con más de 3 horas desde su registro
    tickets = conn.execute(
        """
        SELECT id, from_email, from_name, subject, fecha_registro
        FROM email_tickets_inbox
        WHERE estado = 'POR_ASIGNAR'
          AND fecha_registro <= DATEADD(hour, -3, GETDATE())
        ORDER BY fecha_registro ASC
        """
    ).fetchall()

    if not tickets:
        return 0

    # Filtrar los que ya fueron alertados en esta sesión
    nuevos = [dict(t) for t in tickets if t["id"] not in _alerted_inbox_ids]
    if not nuevos:
        return 0

    # Obtener usuarios activos de SISTEMAS QP con email
    destinatarios = conn.execute(
        """
        SELECT u.id, COALESCE(u.nombre_completo, u.username) AS nombre, u.email
        FROM usuarios u
        INNER JOIN departamentos d ON d.id = u.departamento_id
        WHERE u.disabled = 0
          AND UPPER(d.nombre) = 'SISTEMAS QP'
          AND u.email IS NOT NULL
          AND LEN(TRIM(u.email)) > 0
        """
    ).fetchall()

    if not destinatarios:
        _log.warning("[email_inbox] notify_unassigned_tickets: no hay usuarios SISTEMAS QP con email")
        return 0

    smtp_from = (get_config_value("smtp_from", "") or get_config_value("SMTP_FROM", "")
                 or get_config_value("smtp_user", "")).strip()

    # Construir tabla HTML de tickets pendientes
    filas = ""
    for t in nuevos:
        hrs = ""
        if t["fecha_registro"]:
            delta = datetime.now() - t["fecha_registro"]
            h = int(delta.total_seconds() // 3600)
            m = int((delta.total_seconds() % 3600) // 60)
            hrs = f"{h}h {m}m"
        ticket_code = f"TK-{t['id']:05d}"
        filas += (
            f"<tr>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #f0f0f0;font-family:monospace;"
            f"font-weight:700;color:#dc3545;'>{ticket_code}</td>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #f0f0f0;'>{t['subject']}</td>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #f0f0f0;color:#6c757d;'>"
            f"{t['from_name'] or t['from_email']}</td>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #f0f0f0;color:#dc3545;"
            f"font-weight:600;white-space:nowrap;'>{hrs}</td>"
            f"</tr>"
        )

    cantidad = len(nuevos)
    html_alerta = f"""
    <html><body style="font-family:Arial,sans-serif;color:#333;max-width:680px;margin:0 auto;">
      <div style="background:#dc3545;padding:18px 24px;border-radius:8px 8px 0 0;">
        <h2 style="color:#fff;margin:0;">⚠️ Tickets sin asignar — más de 3 horas</h2>
      </div>
      <div style="padding:24px;background:#f8f9fa;border:1px solid #dee2e6;
                  border-top:none;border-radius:0 0 8px 8px;">
        <p>Hay <strong>{cantidad} ticket(s)</strong> en la bandeja de soporte que llevan
           más de <strong>3 horas</strong> sin asignar a un responsable:</p>
        <div style="background:#fff;border:1px solid #dee2e6;border-radius:6px;
                    overflow:hidden;margin:16px 0;">
          <table style="width:100%;border-collapse:collapse;font-size:13px;">
            <thead>
              <tr style="background:#f8f9fa;">
                <th style="padding:8px 12px;text-align:left;font-size:11px;
                           text-transform:uppercase;letter-spacing:.4px;color:#495057;
                           border-bottom:2px solid #dee2e6;">Ticket</th>
                <th style="padding:8px 12px;text-align:left;font-size:11px;
                           text-transform:uppercase;letter-spacing:.4px;color:#495057;
                           border-bottom:2px solid #dee2e6;">Asunto</th>
                <th style="padding:8px 12px;text-align:left;font-size:11px;
                           text-transform:uppercase;letter-spacing:.4px;color:#495057;
                           border-bottom:2px solid #dee2e6;">Remitente</th>
                <th style="padding:8px 12px;text-align:left;font-size:11px;
                           text-transform:uppercase;letter-spacing:.4px;color:#495057;
                           border-bottom:2px solid #dee2e6;">Sin asignar</th>
              </tr>
            </thead>
            <tbody>{filas}</tbody>
          </table>
        </div>
        <p>Por favor ingresa a la
          <strong>Bandeja Soporte TI</strong> y asigna cada ticket a la brevedad.</p>
        <hr style="border:none;border-top:1px solid #dee2e6;margin:20px 0;">
        <p style="font-size:12px;color:#6c757d;">
          Sistema de Gestión Quimpac · soporteti@quimpac.com.ec</p>
      </div>
    </body></html>"""

    enviados = 0
    for dest in destinatarios:
        to_email = dest["email"].strip()

        # ── MODO PRUEBAS ── comenta esta línea en producción
        to_email = "jchavez1@quimpac.com.ec"
        # ────────────────────────────────────────────────────

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[Soporte TI] {cantidad} ticket(s) sin asignar hace más de 3 horas"
        msg["From"]    = smtp_from
        msg["To"]      = to_email
        msg.attach(MIMEText(html_alerta, "html", "utf-8"))

        if _smtp_send(smtp_from, to_email, msg):
            enviados += 1

    # Registrar como alertados para no repetir en esta sesión
    for t in nuevos:
        _alerted_inbox_ids.add(t["id"])

    _log.info(
        "[email_inbox] Alerta tickets sin asignar: %d ticket(s) — correos enviados a %d/%d destinatarios",
        cantidad, enviados, len(destinatarios)
    )
    return cantidad
