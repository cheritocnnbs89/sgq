# modules/tasks/task_notifications.py
from __future__ import annotations

import smtplib
from email.message import EmailMessage

from ..db import get_config_value


def _send_tarea_avance_mail(
    tarea_row,
    observacion: str,
    detalles: str,
    fecha_accion_str: str,
    actor_username: str
):
    """
    Arma el EmailMessage para notificar un nuevo avance en la tarea.
    Devuelve: (msg, smtp_host, smtp_port, smtp_user, smtp_pass, use_tls)
    Si falta configuración SMTP, msg será None.
    """
    smtp_host = get_config_value('smtp_host', '')
    smtp_port_raw = get_config_value('smtp_port', '587')
    smtp_user = get_config_value('smtp_user', '')
    smtp_pass = get_config_value('smtp_pass', '')
    smtp_from = get_config_value('smtp_from', smtp_user or '')
    use_tls = (get_config_value('smtp_tls', '1') == '1')

    try:
        smtp_port = int(smtp_port_raw or 587)
    except Exception:
        smtp_port = 587

    if not (smtp_host and smtp_from):
        return None, None, None, None, None, None

    tarea = dict(tarea_row)
    codigo_tarea = f"{tarea['id']:07d}"
    titulo = tarea.get('titulo') or 'Sin título'
    estado = tarea.get('estado') or '—'
    fi_str = tarea.get('fecha_inicio') or 'No definida'
    fc_str = tarea.get('fecha_compromiso') or 'No definida'
    ff_str = tarea.get('fecha_fin') or 'No definida'

    obs_txt = observacion or '(sin observación)'
    det_txt = detalles or '(sin detalles)'
    det_html = det_txt.replace("\n", "<br>")

    subject = f"[Tareas {codigo_tarea}] Nuevo avance en la tarea: {titulo}"

    body_text = f"""Se ha registrado un nuevo avance en la tarea {codigo_tarea}.

Tarea: {titulo}
Estado actual: {estado}
Fecha de la acción: {fecha_accion_str}
Registrado por: {actor_username}

Observación:
{obs_txt}

Detalles:
{det_txt}

Este mensaje se generó automáticamente desde el sistema de tareas.
"""

    body_html = f"""
<html>
<body style="font-family: Arial, sans-serif; font-size:14px; color:#333;">
    <h2 style="margin:0 0 10px; color:#0078d4;">
    🔄 Nuevo avance registrado en la tarea
    </h2>

    <p>Se ha registrado un nuevo avance en la siguiente tarea:</p>

    <div style="border-left:4px solid #0078d4;
                padding:12px 16px;
                background:#f5f5f5;
                margin:16px 0;">
    <p style="margin:0 0 4px;">
        🔢 <strong>Código:</strong> {codigo_tarea}
    </p>
    <p style="margin:0 0 4px;">
        📌 <strong>Título:</strong> {titulo}
    </p>
    <p style="margin:0 0 4px;">
        🎯 <strong>Estado actual:</strong> {estado}
    </p>
    <p style="margin:0 0 4px;">
        👤 <strong>Acción registrada por:</strong> {actor_username}
    </p>
    <p style="margin:0 0 4px;">
        🕒 <strong>Fecha de la acción:</strong> {fecha_accion_str}
    </p>
    <p style="margin:0 0 4px;">
        📅 <strong>Fecha inicio:</strong> {fi_str}
    </p>
    <p style="margin:0 0 4px;">
        ⏱️ <strong>Fecha compromiso:</strong> {fc_str}
    </p>
    <p style="margin:0;">
        ✅ <strong>Fecha fin:</strong> {ff_str}
    </p>
    </div>

    <p style="margin:0 0 4px;">
    📝 <strong>Observación:</strong>
    </p>
    <p style="margin:0 0 12px;">{obs_txt}</p>

    <p style="margin:0 0 4px;">
    📄 <strong>Detalles:</strong>
    </p>
    <p style="margin:0 0 12px;">{det_html}</p>

    <p style="margin-top:16px;">
    👉 Por favor ingresa al sistema de tareas para revisar el detalle completo.
    </p>

    <p style="font-size:12px; color:#777; margin-top:24px;">
    ⚠️ Este mensaje se generó automáticamente, por favor no responder a este correo.
    </p>
</body>
</html>
"""

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = smtp_from
    msg.set_content(body_text)
    msg.add_alternative(body_html, subtype="html")

    return msg, smtp_host, smtp_port, smtp_user, smtp_pass, use_tls


def _send_tarea_creada_mail(
    to_email: str,
    solicitante_nombre: str,
    titulo: str,
    descripcion: str,
    fi_str: str,
    fc_str: str,
    ff_str: str,
    responsables_nombres: list[str]
):
    """
    Envía un correo al solicitante cuando se crea una nueva tarea.
    Usa la configuración SMTP almacenada en la tabla de configuración (get_config_value).
    """
    try:
        smtp_host = get_config_value('smtp_host', 'localhost')
        smtp_port = int(get_config_value('smtp_port', '587'))
        smtp_user = get_config_value('smtp_user', '')
        smtp_pass = get_config_value('smtp_pass', '')
        smtp_from = get_config_value('smtp_from', smtp_user or 'no-reply@localhost')
        use_tls = (get_config_value('smtp_tls', '1') == '1')

        if not smtp_host or not smtp_from or not to_email:
            return

        resp_txt = ", ".join(responsables_nombres) if responsables_nombres else "Sin responsables asignados"

        def fmt(fecha_str):
            return fecha_str or 'No definida'

        subject = f"Nueva tarea creada: {titulo}"

        body = f"""Hola {solicitante_nombre},

Se ha creado una nueva tarea en el sistema.

Título: {titulo}
Descripción: {descripcion or 'Sin descripción'}

Responsables: {resp_txt}
Fecha inicio: {fmt(fi_str)}
Fecha compromiso: {fmt(fc_str)}
Fecha fin: {fmt(ff_str)}

Este es un mensaje automático del sistema de tareas.
"""

        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = smtp_from
        msg['To'] = to_email
        msg.set_content(body)

        if use_tls:
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                if smtp_user and smtp_pass:
                    server.login(smtp_user, smtp_pass)
                server.send_message(msg)
        else:
            with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
                if smtp_user and smtp_pass:
                    server.login(smtp_user, smtp_pass)
                server.send_message(msg)

    except Exception as e:
        print("Error enviando correo de tarea creada:", e)



def _send_encuesta_satisfaccion_mail(tarea_row, encuesta_url: str):
    smtp_host = get_config_value('smtp_host', '')
    smtp_port_raw = get_config_value('smtp_port', '587')
    smtp_user = get_config_value('smtp_user', '')
    smtp_pass = get_config_value('smtp_pass', '')
    smtp_from = get_config_value('smtp_from', smtp_user or '')
    use_tls = (get_config_value('smtp_tls', '1') == '1')

    try:
        smtp_port = int(smtp_port_raw or 587)
    except Exception:
        smtp_port = 587

    if not smtp_host or not smtp_from:
        return None, None, None, None, None, None

    tarea = dict(tarea_row)
    codigo_tarea = f"{int(tarea['id']):07d}"
    titulo = tarea.get("titulo") or "Sin título"
    solicitante = tarea.get("solicitante_nombre") or "Usuario"

    subject = f"[Encuesta {codigo_tarea}] Evalúa la atención recibida"

    body_text = f"""Hola {solicitante},

Tu ticket {codigo_tarea} fue cerrado.

Por favor completa la encuesta de satisfacción:
{encuesta_url}

Ticket: {titulo}

Este mensaje se generó automáticamente.
"""

    body_html = f"""
<html>
<body style="font-family: Arial, sans-serif; font-size:14px; color:#333;">
  <h2 style="color:#0d6efd;">Encuesta de satisfacción</h2>
  <p>Hola <strong>{solicitante}</strong>,</p>
  <p>Tu ticket <strong>{codigo_tarea}</strong> fue cerrado.</p>
  <p><strong>Ticket:</strong> {titulo}</p>
  <p>Ayúdanos a mejorar calificando la gestión recibida.</p>
  <p>
    <a href="{encuesta_url}"
       style="background:#0d6efd;color:#fff;padding:10px 16px;text-decoration:none;border-radius:6px;display:inline-block;">
       Responder encuesta
    </a>
  </p>
  <p style="font-size:12px;color:#777;">Este mensaje se generó automáticamente.</p>
</body>
</html>
"""

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = smtp_from
    msg.set_content(body_text)
    msg.add_alternative(body_html, subtype="html")

    return msg, smtp_host, smtp_port, smtp_user, smtp_pass, use_tls