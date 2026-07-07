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
from modules.db import get_db
from . import planificador_repository as repo
from modules.scheduler.scheduler_constants import (
    TPL_PLAN_NUEVA_COORD,
    TPL_PLAN_NUEVA_USER,
    TIPO_PLAN_NUEVA_COORD,
    TIPO_PLAN_NUEVA_USER,
)
from modules.scheduler.scheduler_notifications import enqueue_planificador_notify


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


def _email(to_list: list[str], subject: str, html: str, attachments=None) -> None:
    """Envía email ignorando errores (nunca bloquea la respuesta HTTP)."""
    to_list = [e for e in (to_list or []) if e]
    if not to_list:
        return
    try:
        _send_async(to_list, subject, html, attachments=attachments)
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
                          fecha: str, solicitante_nombre: str,
                          solicitante_id: int | None = None) -> None:
    coordinadores, _ = repo.get_coordinadores_aprobadores_para_tipo(tipo)

    payload = {
        "solicitud_id": solicitud_id,
        "tipo":         tipo,
        "area":         area,
        "fecha":        fecha,
        "solicitante":  solicitante_nombre,
    }

    conn = get_db()

    # Notificar a cada coordinador del tipo específico (no de otros tipos)
    for c in coordinadores:
        coord_id = c.get("id")
        inapp_body = f"Solicitud #{solicitud_id} de {solicitante_nombre} — {tipo} — {fecha}"
        _inapp(coord_id, f"[Planificador] Nueva solicitud #{solicitud_id} · {tipo}", inapp_body)
        if coord_id:
            payload_coord = dict(payload, titulo=f"Nueva solicitud #{solicitud_id} · {tipo}",
                                  saludo="Se registró una nueva solicitud que requiere asignación de horario.",
                                  nota="Ingresa al SGQ para asignar el horario y enviar a aprobación.")
            event_key = f"plan:nueva:coord:{solicitud_id}:{coord_id}"
            try:
                enqueue_planificador_notify(conn, coord_id, TPL_PLAN_NUEVA_COORD,
                                            TIPO_PLAN_NUEVA_COORD, payload_coord, event_key)
            except Exception as exc:
                try:
                    current_app.logger.warning("plan notif coord error sid=%s uid=%s: %s",
                                               solicitud_id, coord_id, exc)
                except Exception:
                    pass

    # Confirmar al solicitante
    if solicitante_id:
        _inapp(solicitante_id,
               f"[Planificador] Solicitud #{solicitud_id} registrada",
               f"Tu solicitud #{solicitud_id} — {tipo} — {fecha} quedó pendiente de coordinación.")
        payload_user = dict(payload, titulo=f"Solicitud #{solicitud_id} registrada",
                             saludo="Tu solicitud fue registrada exitosamente.",
                             nota="Recibirás una notificación cuando sea coordinada y aprobada.")
        event_key_u = f"plan:nueva:user:{solicitud_id}:{solicitante_id}"
        try:
            enqueue_planificador_notify(conn, solicitante_id, TPL_PLAN_NUEVA_USER,
                                        TIPO_PLAN_NUEVA_USER, payload_user, event_key_u)
        except Exception as exc:
            try:
                current_app.logger.warning("plan notif user error sid=%s uid=%s: %s",
                                           solicitud_id, solicitante_id, exc)
            except Exception:
                pass


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


# ──────────────────────────────────────────────────────────
# 7. Vuelo: notificar al jefe directo para que apruebe
# ──────────────────────────────────────────────────────────

def notif_vuelo_pendiente_jefe(solicitud_id: int, area: str, fecha: str,
                                descripcion: str, presupuesto: str,
                                solicitante_nombre: str,
                                jefe_id: int | None, jefe_nombre: str,
                                es_reagenda: bool = False) -> None:
    if not jefe_id:
        return
    accion = "reagendada — nuevo ciclo de aprobación" if es_reagenda else "registrada"
    subject = f"[Planificador] Solicitud de Vuelo #{solicitud_id} pendiente de su aprobación"
    titulo  = f"Solicitud de Vuelo #{solicitud_id} — Requiere su aprobación"
    saludo  = (f"Estimado/a <strong>{jefe_nombre}</strong>, "
               f"<strong>{solicitante_nombre}</strong> ha {accion} una solicitud de "
               f"tipo <strong>Vuelo</strong> que requiere su aprobación.")
    filas   = [
        ("N° solicitud",      str(solicitud_id)),
        ("Área solicitante",  area),
        ("Fecha solicitada",  fecha),
        ("Descripción",       descripcion or "—"),
        ("Presupuesto B.C.",  presupuesto or "—"),
        ("Solicitante",       solicitante_nombre),
    ]
    nota = "Ingresa al SGQ para aprobar o rechazar esta solicitud."
    html = _email_html("PLANIFICADOR · VUELO — APROBACIÓN JEFE", titulo, saludo, filas, nota)
    _inapp(jefe_id, subject,
           f"Solicitud de Vuelo #{solicitud_id} de {solicitante_nombre} — {fecha} requiere su aprobación")
    email_j = repo.get_email_by_usuario_id(jefe_id)
    _email([email_j] if email_j else [], subject, html)


# ──────────────────────────────────────────────────────────
# 8. Vuelo: notificar al GG cuando no hay presupuesto
# ──────────────────────────────────────────────────────────

def notif_vuelo_pendiente_gg(solicitud_id: int, area: str, fecha: str,
                              descripcion: str, presupuesto: str,
                              solicitante_nombre: str, jefe_nombre: str,
                              gg_id: int | None, gg_nombre: str) -> None:
    if not gg_id:
        return
    subject = f"[Planificador] Vuelo #{solicitud_id} sin presupuesto — requiere su aprobación"
    titulo  = f"Solicitud de Vuelo #{solicitud_id} — Aprobación Gerente General"
    saludo  = (f"Estimado/a <strong>{gg_nombre}</strong>, el jefe <strong>{jefe_nombre}</strong> "
               f"aprobó una solicitud de Vuelo de <strong>{solicitante_nombre}</strong>, "
               f"pero no existe presupuesto disponible. Requiere su autorización.")
    filas   = [
        ("N° solicitud",     str(solicitud_id)),
        ("Área solicitante", area),
        ("Fecha solicitada", fecha),
        ("Descripción",      descripcion or "—"),
        ("Presupuesto B.C.", presupuesto or "—"),
        ("Solicitante",      solicitante_nombre),
        ("Aprobado por jefe", jefe_nombre),
    ]
    nota = "Ingresa al SGQ para aprobar o rechazar esta solicitud."
    html = _email_html("PLANIFICADOR · VUELO — APROBACIÓN GG", titulo, saludo, filas, nota)
    _inapp(gg_id, subject,
           f"Vuelo #{solicitud_id} de {solicitante_nombre} sin presupuesto — requiere aprobación GG")
    email_g = repo.get_email_by_usuario_id(gg_id)
    _email([email_g] if email_g else [], subject, html)


# ──────────────────────────────────────────────────────────
# 9. Vuelo: aprobado → notificar al coordinador
# ──────────────────────────────────────────────────────────

def notif_vuelo_aprobada_coordinacion(solicitud_id: int, area: str, fecha: str,
                                       descripcion: str, solicitante_nombre: str,
                                       aprobador_nombre: str) -> None:
    coordinadores, _ = repo.get_coordinadores_aprobadores_para_tipo("Vuelo")
    subject = f"[Planificador] Vuelo #{solicitud_id} aprobado — pendiente de coordinación"
    titulo  = f"Solicitud de Vuelo #{solicitud_id} aprobada"
    saludo  = (f"La solicitud de Vuelo de <strong>{solicitante_nombre}</strong> fue aprobada "
               f"por <strong>{aprobador_nombre}</strong> y requiere que gestione los pasajes.")
    filas   = [
        ("N° solicitud",    str(solicitud_id)),
        ("Área solicitante", area),
        ("Fecha",           fecha),
        ("Descripción",     descripcion or "—"),
        ("Aprobado por",    aprobador_nombre),
    ]
    nota = "Ingresa al SGQ, gestiona los pasajes y carga los archivos de soporte."
    html = _email_html("PLANIFICADOR · VUELO — COORDINACIÓN", titulo, saludo, filas, nota)
    emails = []
    for c in coordinadores:
        _inapp(c["id"], subject,
               f"Vuelo #{solicitud_id} de {solicitante_nombre} — {fecha} listo para coordinación")
        if c.get("email"):
            emails.append(c["email"])
    _email(emails, subject, html)


# ──────────────────────────────────────────────────────────
# 10. Vuelo: rechazado → notificar al solicitante
# ──────────────────────────────────────────────────────────

def notif_vuelo_rechazada(solicitud_id: int, area: str, fecha: str,
                           motivo: str, solicitante_nombre: str,
                           solicitante_id: int, rechazado_por: str) -> None:
    subject = f"[Planificador] Solicitud de Vuelo #{solicitud_id} rechazada"
    titulo  = f"Solicitud de Vuelo #{solicitud_id} rechazada"
    saludo  = "Tu solicitud de Vuelo no fue aprobada."
    filas   = [
        ("N° solicitud",  str(solicitud_id)),
        ("Área",          area),
        ("Fecha",         fecha),
        ("Rechazado por", rechazado_por),
        ("Motivo",        motivo or "—"),
    ]
    html = _email_html("PLANIFICADOR · VUELO — RECHAZADO", titulo, saludo, filas)
    _inapp(solicitante_id, subject,
           f"Tu solicitud de Vuelo #{solicitud_id} fue rechazada. Motivo: {motivo or '—'}")
    email_s = repo.get_email_by_usuario_id(solicitante_id)
    _email([email_s] if email_s else [], subject, html)


# ──────────────────────────────────────────────────────────
# 11. Vuelo: coordinador completa → notificar al solicitante con archivos
# ──────────────────────────────────────────────────────────

def notif_vuelo_completada(solicitud_id: int, area: str, fecha: str,
                            descripcion: str, observacion: str,
                            solicitante_nombre: str, solicitante_id: int,
                            coordinador_nombre: str,
                            adjuntos: list | None = None) -> None:
    """adjuntos: lista de tuplas (ruta_absoluta, nombre_archivo) para adjuntar al correo."""
    subject = f"[Planificador] Tu vuelo #{solicitud_id} está listo"
    titulo  = f"Vuelo #{solicitud_id} — Pasajes y reservas disponibles"
    saludo  = (f"Hola <strong>{solicitante_nombre}</strong>, el coordinador "
               f"<strong>{coordinador_nombre}</strong> ha gestionado tu solicitud de vuelo.")
    filas   = [
        ("N° solicitud",        str(solicitud_id)),
        ("Área",                area),
        ("Fecha del vuelo",     fecha),
        ("Descripción",         descripcion or "—"),
        ("Info. de reservación", observacion or "—"),
    ]
    archivos_html = ""
    if adjuntos:
        items = "".join(f"<li>{nombre}</li>" for _, nombre in adjuntos)
        archivos_html = (f'<p style="margin:12px 0 4px;font-size:.85rem;font-weight:600">'
                         f'Documentos adjuntos en este correo:</p>'
                         f'<ul style="margin:0;padding-left:1.2rem;font-size:.82rem">{items}</ul>')
    nota = f"Ingresa al SGQ para ver los detalles completos.{archivos_html}"
    html = _email_html("PLANIFICADOR · VUELO — COMPLETADO", titulo, saludo, filas, nota)
    _inapp(solicitante_id, subject,
           f"Tu vuelo #{solicitud_id} está listo. El coordinador registró los pasajes y reservas.")
    email_s = repo.get_email_by_usuario_id(solicitante_id)
    _email([email_s] if email_s else [], subject, html, attachments=adjuntos or None)


# ──────────────────────────────────────────────────────────
# Vuelo coordinado: notificar al solicitante con datos de reserva y adjunto
# ──────────────────────────────────────────────────────────

def notif_vuelo_coordinada_solicitante(solicitud_id: int, area: str, fecha: str,
                                        descripcion: str, hora_inicio: str, hora_fin: str,
                                        datos_ticket: str, datos_hotel: str,
                                        solicitante_nombre: str, solicitante_id: int,
                                        coordinador_nombre: str,
                                        attachment_paths: list | None = None) -> None:
    subject = f"[Planificador] Tu vuelo #{solicitud_id} está coordinado — datos de reserva"
    titulo  = f"Vuelo #{solicitud_id} — Reserva confirmada"
    saludo  = (f"Hola <strong>{solicitante_nombre}</strong>, el coordinador "
               f"<strong>{coordinador_nombre}</strong> ha gestionado los pasajes de tu solicitud.")
    filas = [
        ("N° solicitud",        str(solicitud_id)),
        ("Área",                area),
        ("Fecha del vuelo",     fecha),
        ("Horario asignado",    f"{hora_inicio} – {hora_fin}" if hora_inicio else "—"),
        ("Descripción",         descripcion or "—"),
        ("Datos ticket aéreo",  datos_ticket or "—"),
        ("Datos hotel",         datos_hotel or "Sin reserva de hotel"),
    ]
    nota = "Se adjuntan los documentos de la reserva. Guárdalos para presentarlos en el viaje."
    html = _email_html("PLANIFICADOR · VUELO — COORDINADO", titulo, saludo, filas, nota)
    _inapp(solicitante_id, subject,
           f"Tu vuelo #{solicitud_id} está coordinado. El coordinador registró los datos de reserva.")
    email_s = repo.get_email_by_usuario_id(solicitante_id)
    _email([email_s] if email_s else [], subject, html, attachments=attachment_paths)


# ──────────────────────────────────────────────────────────
# Vuelo marcado como realizado: avisar al coordinador para que liquide costos
# ──────────────────────────────────────────────────────────

def notif_vuelo_pendiente_liquidacion(solicitud_id: int, area: str, fecha: str,
                                       solicitante_nombre: str,
                                       coordinador_id: int,
                                       coordinador_nombre: str) -> None:
    """Avisa al coordinador que el solicitante confirmó haber realizado el vuelo."""
    subject = f"[Planificador] Vuelo #{solicitud_id} realizado — pendiente ingresar costos"
    titulo  = f"Vuelo #{solicitud_id} — Registrar costos"
    saludo  = (f"Hola <strong>{coordinador_nombre}</strong>, "
               f"<strong>{solicitante_nombre}</strong> ha confirmado que realizó el vuelo. "
               f"Por favor ingresa los costos reales para completar la solicitud.")
    filas   = [
        ("N° solicitud",   str(solicitud_id)),
        ("Área",           area),
        ("Fecha del vuelo", fecha),
        ("Confirmado por", solicitante_nombre),
    ]
    nota = ("Ingresa al SGQ → Planificador → Por completar, abre la solicitud y "
            "registra los costos por tipo de gasto.")
    html = _email_html("PLANIFICADOR · VUELO — PENDIENTE LIQUIDACIÓN", titulo, saludo, filas, nota)
    _inapp(coordinador_id, subject,
           f"El solicitante confirmó el vuelo #{solicitud_id}. Debes ingresar los costos para completarlo.")
    email_c = repo.get_email_by_usuario_id(coordinador_id)
    _email([email_c] if email_c else [], subject, html)


# ──────────────────────────────────────────────────────────
# Vuelo liquidado: notificar al solicitante que el viaje está completo
# ──────────────────────────────────────────────────────────

def notif_vuelo_liquidada(solicitud_id: int, area: str, fecha: str,
                           solicitante_nombre: str, solicitante_id: int,
                           liquidador_nombre: str, costo_real: float,
                           notas: str) -> None:
    subject = f"[Planificador] Vuelo #{solicitud_id} completado y registrado"
    titulo  = f"Vuelo #{solicitud_id} — Liquidación registrada"
    saludo  = (f"Hola <strong>{solicitante_nombre}</strong>, tu solicitud de vuelo "
               f"ha sido completada y los costos han sido registrados.")
    filas   = [
        ("N° solicitud",  str(solicitud_id)),
        ("Área",          area),
        ("Fecha del vuelo", fecha),
        ("Costo registrado", f"${costo_real:,.2f}"),
        ("Registrado por", liquidador_nombre),
    ]
    if notas:
        filas.append(("Notas", notas))
    nota = "El costo ha sido deducido del presupuesto del centro de costo correspondiente."
    html = _email_html("PLANIFICADOR · VUELO — COMPLETADO", titulo, saludo, filas, nota)
    _inapp(solicitante_id, subject, f"Tu vuelo #{solicitud_id} fue completado. Costo: ${costo_real:,.2f}")
    email_s = repo.get_email_by_usuario_id(solicitante_id)
    _email([email_s] if email_s else [], subject, html)


def notif_vuelo_recordatorio_coordinador(solicitud_id: int, area: str, fecha: str,
                                          coordinador_id: int, coordinador_nombre: str,
                                          coordinador_email: str) -> None:
    """Recordatorio al coordinador: el vuelo está coordinado pero no liquidado."""
    subject = f"[Planificador] Recordatorio: Vuelo #{solicitud_id} pendiente de liquidación"
    titulo  = f"Vuelo #{solicitud_id} — Pendiente de costos"
    saludo  = (f"Hola <strong>{coordinador_nombre}</strong>, el siguiente vuelo fue coordinado "
               f"pero aún no se han registrado los costos reales del viaje.")
    filas   = [
        ("N° solicitud", str(solicitud_id)),
        ("Área",         area),
        ("Fecha vuelo",  fecha),
    ]
    nota = ("Por favor ingresa al SGQ → Planificador, abre esta solicitud y completa "
            "los datos de costo para que el presupuesto sea actualizado.")
    html = _email_html("PLANIFICADOR · VUELO — RECORDATORIO", titulo, saludo, filas, nota)
    _inapp(coordinador_id, subject,
           f"Vuelo #{solicitud_id} coordinado pero sin liquidar costos. Ingresa al SGQ para completarlo.")
    if coordinador_email:
        _email([coordinador_email], subject, html)


# ──────────────────────────────────────────────────────────
# (legacy) Nueva solicitud de Vuelo → notificar al gerente del solicitante
# ──────────────────────────────────────────────────────────

def notif_vuelo_nueva_gerente(solicitud_id: int, area: str, fecha: str,
                               descripcion: str, presupuesto: str,
                               solicitante_nombre: str,
                               gerente_id: int, gerente_nombre: str) -> None:

    subject = f"[Planificador] Nueva solicitud de Vuelo #{solicitud_id} — {area}"
    titulo  = f"Solicitud de Vuelo #{solicitud_id} — Informativo"
    saludo  = (f"Estimado/a <strong>{gerente_nombre}</strong>, "
               f"<strong>{solicitante_nombre}</strong> ha registrado una nueva "
               f"solicitud de tipo <strong>Vuelo</strong> que requiere su conocimiento.")
    filas   = [
        ("N° solicitud",         str(solicitud_id)),
        ("Área solicitante",     area),
        ("Fecha solicitada",     fecha),
        ("Descripción",          descripcion or "—"),
        ("Presupuesto Base Cero", presupuesto or "—"),
        ("Solicitante",          solicitante_nombre),
    ]
    nota = "La solicitud pasará por coordinación y aprobación. Será notificado cuando requiera su aprobación gerencial."
    html = _email_html("PLANIFICADOR · SOLICITUD DE VUELO", titulo, saludo, filas, nota)

    _inapp(gerente_id, subject,
           f"Nueva solicitud de Vuelo #{solicitud_id} — {area} — {fecha} registrada por {solicitante_nombre}")
    email_g = repo.get_email_by_usuario_id(gerente_id)
    _email([email_g] if email_g else [], subject, html)
