# modules/planificador/planificador_notifications.py
# -*- coding: utf-8 -*-
"""
Notificaciones del módulo Planificador.
- In-app : inserta en notify_inapp (el badge del menú las lee)
- Email  : usa send_email_async con formato HTML estilo SGQ
"""
from __future__ import annotations

from flask import current_app

from modules.email_utils import send_email_async as _send_async
from modules import telegram_utils as _tg
from . import planificador_repository as repo


# ──────────────────────────────────────────────────────────
# Helpers internos
# ──────────────────────────────────────────────────────────

def _inapp(user_id: int, title: str, body: str) -> None:
    """Inserta notificación in-app ignorando errores."""
    if not user_id:
        return
    try:
        repo.insert_notify_inapp(user_id, title, body)
    except Exception as exc:
        try:
            current_app.logger.warning("Planificador inapp error uid=%s: %s", user_id, exc)
        except Exception:
            pass


def _email(to_list: list[str], subject: str, html: str) -> None:
    """Envía email ignorando errores (nunca bloquea la respuesta HTTP)."""
    to_list = [e for e in (to_list or []) if e]
    if not to_list:
        return
    try:
        _send_async(to_list, subject, html)
    except Exception as exc:
        try:
            current_app.logger.warning("Planificador email error: %s", exc)
        except Exception:
            pass


# ── HTML email en formato SGQ (igual al estilo OM vencida) ──────────────

def _email_html(categoria: str, titulo: str, saludo: str, filas: list[tuple],
                nota: str = "") -> str:
    """
    Genera HTML de email con el estilo de las notificaciones SGQ:
    Header azul, tabla con filas (label, valor), pie de página.
    """
    rows_html = "".join(
        f"""<tr>
              <td style="padding:8px 12px;background:#f1f5f9;font-size:.82rem;
                         font-weight:600;color:#334155;white-space:nowrap;
                         border-bottom:1px solid #e2e8f0">{label}</td>
              <td style="padding:8px 12px;font-size:.82rem;color:#0f172a;
                         border-bottom:1px solid #e2e8f0">{valor}</td>
           </tr>"""
        for label, valor in filas
    )
    nota_html = (
        f'<p style="margin:14px 0 0;font-size:.8rem;color:#64748b">{nota}</p>'
        if nota else ""
    )
    return f"""<!DOCTYPE html>
<html lang="es"><body style="margin:0;padding:0;background:#f8fafc;font-family:Arial,sans-serif">
<div style="max-width:580px;margin:24px auto">
  <div style="background:#1e3a8a;padding:16px 20px;border-radius:10px 10px 0 0">
    <span style="color:#bfdbfe;font-size:.75rem;font-weight:700;text-transform:uppercase;
                 letter-spacing:.08em">{categoria}</span>
    <h1 style="margin:4px 0 0;color:#fff;font-size:1.1rem;font-weight:700">{titulo}</h1>
  </div>
  <div style="background:#fff;padding:20px;border:1px solid #e2e8f0;border-top:none">
    <p style="margin:0 0 14px;font-size:.9rem;color:#0f172a">{saludo}</p>
    <table style="width:100%;border-collapse:collapse;border:1px solid #e2e8f0;
                  border-radius:8px;overflow:hidden">
      {rows_html}
    </table>
    {nota_html}
  </div>
  <div style="background:#f1f5f9;padding:10px 20px;border:1px solid #e2e8f0;
              border-top:none;border-radius:0 0 10px 10px">
    <p style="margin:0;font-size:.75rem;color:#64748b">
      Este es un mensaje automático generado por SGQ Quimpac. No responda a este correo.
    </p>
  </div>
</div>
</body></html>"""


def _telegram(chat_id: str, text: str) -> None:
    """Envía mensaje Telegram ignorando errores."""
    if not chat_id:
        return
    try:
        _tg.send_message(chat_id, text)
    except Exception as exc:
        try:
            current_app.logger.warning("Planificador telegram error chat=%s: %s", chat_id, exc)
        except Exception:
            pass


def _maps_link(lugar: str) -> str:
    if not lugar:
        return "—"
    encoded = lugar.replace(" ", "+")
    return (f'{lugar} &nbsp;'
            f'<a href="https://www.google.com/maps/search/?api=1&query={encoded}" '
            f'style="color:#2563eb;font-size:.8rem">Ver en mapa</a>')


# ──────────────────────────────────────────────────────────
# 1. Nueva solicitud → notificar coordinadores
# ──────────────────────────────────────────────────────────

def notif_nueva_solicitud(solicitud_id: int, tipo: str, area: str,
                          fecha: str, solicitante_nombre: str) -> None:
    coordinadores, _ = repo.get_coordinadores_aprobadores_para_tipo(tipo)
    if not coordinadores:
        return

    subject = f"[Planificador] Nueva solicitud #{solicitud_id} · {tipo}"
    titulo  = f"Nueva solicitud pendiente de coordinación #{solicitud_id}"
    saludo  = "Se registró una nueva solicitud que requiere asignación de horario."
    filas   = [
        ("N° solicitud",   str(solicitud_id)),
        ("Tipo",           tipo),
        ("Área solicitante", area),
        ("Fecha",          fecha),
        ("Solicitante",    solicitante_nombre),
    ]
    nota = "Ingresa al SGQ para asignar el horario y enviar a aprobación."
    html = _email_html("PLANIFICADOR · COORDINACIÓN", titulo, saludo, filas, nota)

    emails = []
    for c in coordinadores:
        _inapp(c["id"], subject,
               f"Solicitud #{solicitud_id} de {solicitante_nombre} — {tipo} — {fecha}")
        if c.get("email"):
            emails.append(c["email"])

    _email(emails, subject, html)


# ──────────────────────────────────────────────────────────
# 2. Coordinada → notificar aprobadores
# ──────────────────────────────────────────────────────────

def notif_coordinada(solicitud_id: int, tipo: str, area: str,
                     fecha: str, hi: str, hf: str,
                     coordinador_nombre: str) -> None:
    _, aprobadores = repo.get_coordinadores_aprobadores_para_tipo(tipo)
    if not aprobadores:
        return

    subject = f"[Planificador] Solicitud #{solicitud_id} pendiente de aprobación"
    titulo  = f"Solicitud #{solicitud_id} coordinada · Requiere aprobación"
    saludo  = "Una solicitud fue coordinada y está esperando su aprobación."
    filas   = [
        ("N° solicitud",   str(solicitud_id)),
        ("Tipo",           tipo),
        ("Área solicitante", area),
        ("Fecha",          fecha),
        ("Horario asignado", f"{hi} – {hf}"),
        ("Coordinado por", coordinador_nombre),
    ]
    nota = "Ingresa al SGQ para aprobar o rechazar la solicitud."
    html = _email_html("PLANIFICADOR · APROBACIÓN", titulo, saludo, filas, nota)

    emails = []
    for a in aprobadores:
        _inapp(a["id"], subject,
               f"Solicitud #{solicitud_id} — {tipo} — {fecha} — coordinada por {coordinador_nombre}")
        if a.get("email"):
            emails.append(a["email"])

    _email(emails, subject, html)


# ──────────────────────────────────────────────────────────
# 3. Aprobada → notificar solicitante + motorizados
# ──────────────────────────────────────────────────────────

def notif_aprobada(solicitud_id: int, tipo: str, area: str, fecha: str,
                   hi: str, hf: str, lugar: str, descripcion: str,
                   solicitante_id: int, aprobador_nombre: str) -> None:

    subject = f"[Planificador] Solicitud #{solicitud_id} APROBADA"
    titulo  = f"Solicitud #{solicitud_id} aprobada"
    saludo  = ("Su solicitud ha sido <strong style='color:#16a34a'>APROBADA</strong> "
               "y aparece en el calendario del planificador.")
    filas   = [
        ("N° solicitud",   str(solicitud_id)),
        ("Tipo",           tipo),
        ("Área",           area),
        ("Fecha",          fecha),
        ("Horario",        f"{hi} – {hf}"),
        ("Lugar / destino", _maps_link(lugar)),
        ("Descripción",    descripcion or "—"),
        ("Aprobado por",   aprobador_nombre),
    ]

    emails = []

    # In-app + email al solicitante
    email_solic = repo.get_email_by_usuario_id(solicitante_id)
    _inapp(solicitante_id, subject,
           f"Tu solicitud #{solicitud_id} — {tipo} — {fecha} fue aprobada")
    if email_solic:
        emails.append(email_solic)

    # In-app + email + Telegram a motorizados configurados para este tipo
    maps_url  = f"https://www.google.com/maps/search/?api=1&query={lugar.replace(' ', '+')}" if lugar else ""
    tg_text   = (
        f"🟢 <b>Servicio asignado #{solicitud_id}</b>\n\n"
        f"📋 <b>Tipo:</b> {tipo}\n"
        f"🏢 <b>Área:</b> {area}\n"
        f"📅 <b>Fecha:</b> {fecha}\n"
        f"⏰ <b>Horario:</b> {hi} – {hf}\n"
        f"📍 <b>Destino:</b> {lugar or '—'}\n"
        f"📝 <b>Descripción:</b> {descripcion or '—'}\n"
        + (f"\n<a href='{maps_url}'>🗺 Ver en Google Maps</a>" if maps_url else "")
        + f"\n\n<i>Aprobado por: {aprobador_nombre}</i>"
    )

    for m in repo.get_motorizados_para_tipo(tipo):
        _inapp(m["id"], subject,
               f"Servicio asignado #{solicitud_id} — {tipo} — {fecha} {hi}–{hf} — {lugar}")
        if m.get("email"):
            emails.append(m["email"])

    # Telegram: solo a motorizados con chat_id registrado
    for m in repo.get_telegram_chat_ids_para_tipo(tipo):
        _telegram(m["chat_id"], tg_text)

    nota = ("El servicio aparece en el calendario. Verifica el lugar de destino "
            "con el enlace a Google Maps.")
    html = _email_html("PLANIFICADOR · APROBADO", titulo, saludo, filas, nota)
    _email(emails, subject, html)


# ──────────────────────────────────────────────────────────
# 4. Rechazada → notificar solicitante
# ──────────────────────────────────────────────────────────

def notif_rechazada(solicitud_id: int, tipo: str, fecha: str,
                    observacion: str, solicitante_id: int,
                    aprobador_nombre: str) -> None:

    subject = f"[Planificador] Solicitud #{solicitud_id} rechazada"
    titulo  = f"Solicitud #{solicitud_id} rechazada"
    saludo  = "Tu solicitud no fue aprobada. Revisa el motivo e ingresa una nueva si es necesario."
    filas   = [
        ("N° solicitud", str(solicitud_id)),
        ("Tipo",         tipo),
        ("Fecha",        fecha),
        ("Rechazado por", aprobador_nombre),
        ("Motivo",       observacion or "—"),
    ]

    _inapp(solicitante_id, subject,
           f"Solicitud #{solicitud_id} — {tipo} — {fecha} fue rechazada. Motivo: {observacion or '—'}")

    email_solic = repo.get_email_by_usuario_id(solicitante_id)
    html = _email_html("PLANIFICADOR · RECHAZADO", titulo, saludo, filas)
    _email([email_solic] if email_solic else [], subject, html)


# ──────────────────────────────────────────────────────────
# 5. Reagendada → notificar al solicitante
# ──────────────────────────────────────────────────────────

def notif_reagendada(solicitud_id: int, tipo: str, area: str, fecha_anterior: str,
                     nueva_fecha: str, motivo: str,
                     coordinador_nombre: str, solicitante_id: int) -> None:

    subject = f"[Planificador] Solicitud #{solicitud_id} reagendada al {nueva_fecha}"
    titulo  = f"Solicitud #{solicitud_id} fue reagendada"
    saludo  = ("Su solicitud ha sido <strong>reagendada</strong> para una nueva fecha. "
               "El coordinador asignará el horario correspondiente.")
    filas   = [
        ("N° solicitud",   str(solicitud_id)),
        ("Tipo",           tipo),
        ("Área",           area),
        ("Fecha anterior", fecha_anterior),
        ("Nueva fecha",    nueva_fecha),
        ("Motivo",         motivo or "—"),
        ("Reagendado por", coordinador_nombre),
    ]
    nota = "Recibirás una nueva notificación cuando el horario sea asignado."
    html = _email_html("PLANIFICADOR · REAGENDADA", titulo, saludo, filas, nota)

    _inapp(solicitante_id, subject,
           f"Tu solicitud #{solicitud_id} — {tipo} fue reagendada para el {nueva_fecha}. "
           f"Motivo: {motivo or '—'}")
    email_solic = repo.get_email_by_usuario_id(solicitante_id)
    _email([email_solic] if email_solic else [], subject, html)


# ──────────────────────────────────────────────────────────
# 6. Eliminada → notificar según quién elimina
# ──────────────────────────────────────────────────────────

def notif_eliminada(solicitud_id: int, tipo: str, area: str, fecha: str,
                    eliminado_por_nombre: str,
                    solicitante_id: int,
                    eliminado_por_es_solicitante: bool) -> None:
    """
    Si el solicitante elimina → avisa a los coordinadores.
    Si coordinador/aprobador/admin elimina → avisa al solicitante y a coordinadores.
    """
    coordinadores, _ = repo.get_coordinadores_aprobadores_para_tipo(tipo)
    filas = [
        ("N° solicitud",   str(solicitud_id)),
        ("Tipo",           tipo),
        ("Área",           area),
        ("Fecha",          fecha),
        ("Eliminado por",  eliminado_por_nombre),
    ]

    if eliminado_por_es_solicitante:
        # Solicitante cancela → avisa a coordinadores
        subject = f"[Planificador] Solicitud #{solicitud_id} cancelada por el solicitante"
        titulo  = f"Solicitud #{solicitud_id} cancelada"
        saludo  = "El solicitante ha cancelado la siguiente solicitud."
        html    = _email_html("PLANIFICADOR · CANCELADA", titulo, saludo, filas)
        emails  = []
        for c in coordinadores:
            _inapp(c["id"], subject,
                   f"Solicitud #{solicitud_id} — {tipo} — {fecha} fue cancelada por {eliminado_por_nombre}")
            if c.get("email"):
                emails.append(c["email"])
        _email(emails, subject, html)
    else:
        # Coordinador / aprobador / admin elimina → avisa al solicitante y coordinadores
        subject = f"[Planificador] Solicitud #{solicitud_id} eliminada"
        titulo  = f"Solicitud #{solicitud_id} eliminada"
        saludo  = "La siguiente solicitud ha sido eliminada del sistema."
        html    = _email_html("PLANIFICADOR · ELIMINADA", titulo, saludo, filas)
        emails  = []
        email_solic = repo.get_email_by_usuario_id(solicitante_id)
        _inapp(solicitante_id, subject,
               f"Tu solicitud #{solicitud_id} — {tipo} — {fecha} fue eliminada por {eliminado_por_nombre}")
        if email_solic:
            emails.append(email_solic)
        for c in coordinadores:
            _inapp(c["id"], subject,
                   f"Solicitud #{solicitud_id} — {tipo} — {fecha} fue eliminada por {eliminado_por_nombre}")
            if c.get("email"):
                emails.append(c["email"])
        _email(emails, subject, html)


# ──────────────────────────────────────────────────────────
# 6. Pendiente aprobación gerente → notificar al gerente
# ──────────────────────────────────────────────────────────

def notif_pendiente_gerente(solicitud_id: int, tipo: str, area: str, fecha: str,
                             hi: str, hf: str, lugar: str, descripcion: str,
                             gerente_id: int, gerente_nombre: str,
                             aprobador_nombre: str) -> None:

    subject = f"[Planificador] Solicitud #{solicitud_id} requiere su aprobación gerencial"
    titulo  = f"Solicitud #{solicitud_id} · Requiere aprobación gerencial"
    saludo  = (f"Estimado/a <strong>{gerente_nombre}</strong>, una solicitud aprobada por "
               f"<strong>{aprobador_nombre}</strong> requiere su aprobación final como gerente.")
    filas   = [
        ("N° solicitud",    str(solicitud_id)),
        ("Tipo",            tipo),
        ("Área solicitante", area),
        ("Fecha",           fecha),
        ("Horario asignado", f"{hi} – {hf}"),
        ("Lugar / destino",  _maps_link(lugar)),
        ("Descripción",     descripcion or "—"),
        ("Aprobado por",    aprobador_nombre),
    ]
    nota = "Ingresa al SGQ para aprobar o rechazar esta solicitud."
    html = _email_html("PLANIFICADOR · APROBACIÓN GERENCIAL", titulo, saludo, filas, nota)

    _inapp(gerente_id, subject,
           f"Solicitud #{solicitud_id} — {tipo} — {fecha} requiere su aprobación gerencial")
    email_g = repo.get_email_by_usuario_id(gerente_id)
    _email([email_g] if email_g else [], subject, html)
