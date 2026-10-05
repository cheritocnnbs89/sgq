# modules/reclamos_seguros/reclamos_seguros_email_service.py
# -*- coding: utf-8 -*-
"""Fase 2: notificacion saliente al broker y poller entrante de respuestas, enlazando
por conversation_id (Decision 1 del plan -- sin respaldo por codigo en el asunto).
Tambien el aviso de casos abiertos hace demasiado tiempo (30/45/60 dias)."""
from __future__ import annotations

import base64
import html as _html
import logging
import mimetypes
import os
import re
import smtplib
import uuid
from email import encoders
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from urllib.parse import unquote

from modules.email_utils import send_email_async
from . import reclamos_seguros_graph as graph
from . import reclamos_seguros_helpers as rsh
from . import reclamos_seguros_html as rhtml
from . import reclamos_seguros_repository as repo
from .reclamos_seguros_constants import (
    ORIGEN_CORREO_SALIENTE, ORIGEN_CORREO_ENTRANTE, ESTADO_ABIERTO,
    EXTENSIONES_PERMITIDAS, MAX_ADJUNTO_BYTES, MAX_ADJUNTOS_POR_ENVIO,
    MAX_IMAGEN_BYTES, MAX_DESCRIPCION_CHARS,
    UMBRALES_VENCIMIENTO_DIAS,
)

log = logging.getLogger(__name__)

# Tope de adjuntos por correo (Exchange Online rechaza mensajes de mas de ~25-35 MB; el base64 suma ~33%).
MAX_TOTAL_CORREO_BYTES = 20 * 1024 * 1024


def _esc(v) -> str:
    return _html.escape(str(v)) if v not in (None, "") else "—"


def _link_lista() -> str | None:
    """URL absoluta de la lista de casos; None si no hay contexto para construirla (scheduler)."""
    from flask import url_for
    try:
        return url_for("reclamos_seguros.reclamos_seguros_lista", _external=True)
    except Exception:
        return None


def _credenciales_smtp() -> tuple[str, str]:
    """Usuario/clave SMTP generales del sistema (smtp_user/smtp_pass, p. ej. control@)."""
    from modules.db import get_config_value
    return ((get_config_value("smtp_user", "") or "").strip(),
            (get_config_value("smtp_pass", "") or "").strip())


def _smtp_enviar(remitente: str, destinatarios: list[str], msg) -> bool:
    from modules.db import get_config_value
    host = (get_config_value("smtp_host", "") or "").strip()
    port = int(get_config_value("smtp_port", "") or 587)
    use_tls = str(get_config_value("smtp_tls", "1") or "1").strip() == "1"
    user, pwd = _credenciales_smtp()
    if not host:
        log.warning("[reclamos_seguros_email_service] SMTP no configurado (smtp_host vacio)")
        return False
    try:
        cls = smtplib.SMTP if use_tls else smtplib.SMTP_SSL
        with cls(host, port, timeout=20) as server:
            if use_tls:
                server.ehlo()
                server.starttls()
            if user and pwd:
                server.login(user, pwd)
            server.sendmail(remitente, destinatarios, msg.as_string())
        return True
    except smtplib.SMTPAuthenticationError as exc:
        log.error("[reclamos_seguros_email_service] Error de autenticacion SMTP (%s): %s", user, exc)
    except Exception as exc:
        log.error("[reclamos_seguros_email_service] Error SMTP: %s", str(exc)[:300])
    return False


def _enviar_correo_smtp(to_email: str, asunto: str, cuerpo: str, imagenes=None, archivos=None) -> dict | None:
    """Respaldo cuando Graph no puede enviar (falta Mail.Send): envia por SMTP con la cuenta
    general del sistema (smtp_*, p. ej. control@) -- la unica con permiso de envio. Las
    respuestas y el hilo se manejan en el buzon del modulo (el que lee el poller):
      - Reply-To = buzon del modulo, para que el broker responda ahi.
      - Copia oculta (Bcc) al buzon del modulo, para que el hilo nazca tambien alli y su
        conversationId (que es por buzon) coincida con el de las respuestas.
    Luego se busca esa copia via Graph (Mail.Read) para capturar message_id/conversation_id."""
    from email.utils import parseaddr
    from modules.db import get_config_value

    mailbox = graph._mailbox()
    smtp_user, _ = _credenciales_smtp()
    from_header = (get_config_value("smtp_from", "") or "").strip() or smtp_user
    remitente = parseaddr(from_header)[1] or smtp_user

    if imagenes:
        cuerpo_msg = MIMEMultipart("related")
        cuerpo_msg.attach(MIMEText(cuerpo, "html", "utf-8"))
        for cid, data, subtipo in imagenes:
            parte = MIMEImage(data, _subtype=subtipo)
            parte.add_header("Content-ID", f"<{cid}>")
            parte.add_header("Content-Disposition", "inline", filename=f"{cid}.{subtipo}")
            cuerpo_msg.attach(parte)
    else:
        cuerpo_msg = MIMEText(cuerpo, "html", "utf-8")
    if archivos:
        msg = MIMEMultipart("mixed")
        msg.attach(cuerpo_msg)
        for nombre, data, mime in archivos:
            tipo, _, sub = mime.partition("/")
            parte = MIMEBase(tipo or "application", sub or "octet-stream")
            parte.set_payload(data)
            encoders.encode_base64(parte)
            parte.add_header("Content-Disposition", "attachment", filename=("utf-8", "", nombre))
            msg.attach(parte)
    else:
        msg = cuerpo_msg
    msg["Subject"] = asunto
    msg["From"] = from_header
    msg["To"] = to_email
    msg["Reply-To"] = mailbox
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=(remitente.split("@")[-1] or "quimpac.com.ec"))

    destinatarios = [to_email]
    if mailbox.strip().lower() not in (to_email.strip().lower(), remitente.lower()):
        destinatarios.append(mailbox)

    if not _smtp_enviar(remitente, destinatarios, msg):
        return None
    sent = graph.find_sent_message(msg["Message-ID"])
    if sent:
        return sent
    log.warning("[reclamos_seguros_email_service] Correo enviado por SMTP pero la copia no aparecio en %s; "
                "sin conversation_id las respuestas no se enlazaran solas", mailbox)
    return {"message_id": msg["Message-ID"], "conversation_id": ""}


def _enviar_correo(to_email: str, asunto: str, cuerpo: str, imagenes=None, archivos=None) -> dict | None:
    result = graph.send_seguros_email_graph(to_email, asunto, cuerpo, imagenes, archivos)
    if result:
        return result
    log.info("[reclamos_seguros_email_service] Graph no pudo enviar; se intenta por SMTP")
    return _enviar_correo_smtp(to_email, asunto, cuerpo, imagenes, archivos)


def _correo_normal_html(codigo: str, caso: dict, desc_html: str,
                        nombres_adjuntos: list[str] | None = None, omitidos: list[str] | None = None) -> str:
    """Correo al broker (externo) con apariencia de correo normal: sin tarjeta de ancho fijo
    ni tabla, para que el texto y las capturas se ajusten solos al ancho del lector. Los
    avisos internos siguen usando el formato de tarjeta SGQ (_email_html)."""
    solicitante = _esc(caso.get("solicitante_nombre"))
    cod = _esc(codigo)
    extra = ""
    if nombres_adjuntos:
        extra += "<p><strong>Documentos adjuntos:</strong> " + ", ".join(_esc(n) for n in nombres_adjuntos) + "</p>"
    if omitidos:
        extra += ("<p>Algunos documentos no se adjuntaron por su tamaño y se los haremos llegar por separado: "
                  + ", ".join(_esc(n) for n in omitidos) + ".</p>")
    return (
        '<div style="font-family:Segoe UI,Arial,sans-serif;font-size:14px;color:#0f172a;line-height:1.5">'
        '<p>Estimados,</p>'
        f'<p>Se registró un nuevo reclamo de seguro con el código <strong>{cod}</strong>.</p>'
        f'<p><strong>Tipo de caso:</strong> {_esc(caso.get("tipo_caso"))}<br>'
        f'<strong>Fecha:</strong> {_esc(caso.get("fecha"))}<br>'
        f'<strong>Usuario solicitante:</strong> {solicitante}</p>'
        '<p><strong>Descripción:</strong></p>'
        f'<div>{desc_html}</div>{extra}'
        f'<p>Por favor responda este correo con la gestión o novedades del caso, '
        f'manteniendo el código <strong>{cod}</strong> en el asunto.</p>'
        f'<p>Saludos cordiales,<br>{solicitante}<br>Quimpac</p>'
        '<p style="color:#64748b;font-size:12px">Mensaje enviado desde SGQ Quimpac — Reclamos Seguros.</p>'
        '</div>'
    )


def _adjuntos_del_caso(caso_id: int):
    """Documentos subidos al registrar el caso (sin seguimiento) listos para adjuntar al correo:
    ([(nombre, bytes, mime)], [nombres omitidos]). Los que no caben en el tope o no se pueden
    leer se devuelven en 'omitidos' para avisar al usuario."""
    from flask import current_app
    archivos, omitidos, total = [], [], 0
    for a in repo.get_adjuntos(caso_id):
        if a["seguimiento_id"] is not None:
            continue
        ruta = os.path.join(current_app.root_path, "uploads_privados", "reclamos_seguros",
                            str(caso_id), a["nombre_guardado"])
        try:
            with open(ruta, "rb") as f:
                data = f.read()
        except OSError:
            log.warning("[reclamos_seguros_email_service] No se pudo leer el adjunto %s del caso %s", ruta, caso_id)
            omitidos.append(a["nombre_original"])
            continue
        if total + len(data) > MAX_TOTAL_CORREO_BYTES:
            omitidos.append(a["nombre_original"])
            continue
        total += len(data)
        mime = mimetypes.guess_type(a["nombre_original"])[0] or "application/octet-stream"
        archivos.append((a["nombre_original"], data, mime))
    return archivos, omitidos


def notificar_broker_nuevo_caso(caso: dict, broker_email: str, broker_nombre: str | None):
    """Devuelve (enviado, omitidos): omitidos = documentos que no se adjuntaron por tamaño.
    Nunca lanza -- el caller trata enviado=False como advertencia no bloqueante."""
    if not broker_email:
        return False, []
    codigo = caso.get("codigo") or f"#{caso['id']}"
    omitidos: list[str] = []
    try:
        desc_html, imagenes = rhtml.para_correo(caso.get("descripcion"))
        archivos, omitidos = _adjuntos_del_caso(caso["id"])
        asunto = f"[Reclamos Seguros] Nuevo reclamo {codigo} — {caso.get('tipo_caso', '')}"
        cuerpo = _correo_normal_html(codigo, caso, desc_html, [a[0] for a in archivos], omitidos)
        result = _enviar_correo(broker_email, asunto, cuerpo, imagenes, archivos)
        if not result:
            log.warning("[reclamos_seguros_email_service] No se pudo notificar al broker %s del caso %s",
                        broker_email, codigo)
            return False, omitidos
        repo.add_seguimiento(
            caso["id"], "Notificacion enviada al broker por correo."
            + (f" Documentos adjuntos: {len(archivos)}." if archivos else ""),
            usuario_id=None, usuario_nombre="Sistema", origen=ORIGEN_CORREO_SALIENTE,
            remitente_email=rsh.get_cuenta_correo_reclamos_seguros(),
            message_id=result["message_id"], conversation_id=result["conversation_id"] or None,
        )
        return True, omitidos
    except Exception:
        log.exception("[reclamos_seguros_email_service] Fallo notificando al broker caso_id=%s", caso.get("id"))
        return False, omitidos


def _guardar_adjuntos_entrantes(caso_id: int, seguimiento_id: int, message_id: str) -> None:
    """Descarga y guarda los adjuntos de un correo entrante ya vinculado a un caso, con
    los mismos limites que los adjuntos subidos manualmente (ver routes_reclamos_seguros._guardar_adjuntos)."""
    from flask import current_app
    lista = graph.fetch_seguros_attachments_list(message_id)
    if not lista:
        return
    carpeta = os.path.join(current_app.root_path, "uploads_privados", "reclamos_seguros", str(caso_id))
    os.makedirs(carpeta, exist_ok=True)
    guardados = 0
    for a in lista[:MAX_ADJUNTOS_POR_ENVIO]:
        if a.get("is_inline"):
            continue
        nombre_original = a.get("name") or "archivo"
        ext = os.path.splitext(nombre_original)[1].lower()
        if ext not in EXTENSIONES_PERMITIDAS:
            continue
        if not a.get("size") or a["size"] > MAX_ADJUNTO_BYTES:
            continue
        contenido = graph.fetch_seguros_attachment_content(message_id, a["attachment_id"])
        if not contenido or not contenido.get("content_bytes"):
            continue
        nombre_guardado = f"{uuid.uuid4().hex}{ext}"
        ruta = os.path.join(carpeta, nombre_guardado)
        with open(ruta, "wb") as f:
            f.write(contenido["content_bytes"])
        repo.insert_adjunto(caso_id, seguimiento_id, nombre_original, nombre_guardado,
                             a["size"], usuario_id=None, usuario_nombre="Correo entrante")
        guardados += 1
    if guardados:
        log.info("[reclamos_seguros_email_service] %d adjunto(s) guardado(s) del correo %s en caso %s",
                  guardados, message_id[:20], caso_id)


_RE_CID = re.compile(r"""src\s*=\s*["']cid:([^"']+)["']""", re.IGNORECASE)
_RE_DATA_IMG = re.compile(r"""src\s*=\s*["']data:image/[a-z+.\-]+;base64,([A-Za-z0-9+/=\s]+)["']""", re.IGNORECASE)


def _guardar_imagen_correo(data: bytes) -> str | None:
    """Guarda una imagen del correo en la carpeta de imagenes y devuelve su URL interna
    (solo si por sus bytes reales es PNG/JPG/GIF/WEBP y no supera el tope)."""
    if not data or len(data) > MAX_IMAGEN_BYTES:
        return None
    ext = rhtml.ext_imagen(data[:16])
    if not ext:
        return None
    nombre = f"{uuid.uuid4().hex}{ext}"
    with open(os.path.join(rhtml.carpeta_imagenes(), nombre), "wb") as f:
        f.write(data)
    return f"/reclamos-seguros/imagen/{nombre}"


def _resolver_imagenes_correo(html: str, message_id: str) -> str:
    """Las firmas/logos de un correo vienen incrustados (cid: o base64). Se descargan al servidor y
    se reemplazan por la URL interna; el sanitizador descarta cualquier otra imagen (externas)."""
    bajo = html.lower()
    if "cid:" not in bajo and "data:image" not in bajo:
        return html
    por_cid: dict[str, str] = {}
    if "cid:" in bajo:
        for a in graph.fetch_seguros_attachments_list(message_id)[:30]:
            if not a.get("is_inline"):
                continue
            if a.get("size", 0) > MAX_IMAGEN_BYTES:
                continue
            cont = graph.fetch_seguros_attachment_content(message_id, a["attachment_id"])
            if not cont:
                continue
            url = _guardar_imagen_correo(cont["content_bytes"])
            cid = (cont.get("content_id") or "").strip().lower()
            if url and cid:
                por_cid[cid] = url

    def _por_cid(m):
        url = por_cid.get(unquote(m.group(1)).strip().lower())
        return f'src="{url}"' if url else 'src=""'

    def _por_data(m):
        try:
            data = base64.b64decode(re.sub(r"\s+", "", m.group(1)))
        except Exception:
            return 'src=""'
        url = _guardar_imagen_correo(data)
        return f'src="{url}"' if url else 'src=""'

    return _RE_DATA_IMG.sub(_por_data, _RE_CID.sub(_por_cid, html))


def _observacion_de_correo(em: dict, message_id: str) -> str:
    """Texto del seguimiento para un correo entrante: su cuerpo HTML limpio (con formato e imagenes
    como firmas); si no hay HTML util, el texto plano."""
    html = em.get("body_html") or ""
    if html:
        try:
            limpio = rhtml.limpiar_html(_resolver_imagenes_correo(html, message_id))
        except Exception:
            log.exception("[reclamos_seguros_email_service] No se pudo procesar el HTML del correo %s", message_id[:20])
            limpio = ""
        if rhtml.tiene_contenido(limpio) and len(limpio) <= MAX_DESCRIPCION_CHARS:
            return f"<div>{limpio}</div>"
    return em.get("body_text") or "(sin contenido)"


def _completar_adjuntos_pendientes(em: dict, message_id: str) -> None:
    """Un correo ya registrado cuyos adjuntos no se guardaron (error anterior al pedirlos a Graph) se
    completa aqui. Es idempotente: solo actua si el correo trae adjuntos y su seguimiento no tiene ninguno."""
    if not em.get("has_attachments"):
        return
    try:
        seg = repo.get_seguimiento_por_message_id(message_id)
        if seg and not repo.tiene_adjuntos_seguimiento(seg["id"]):
            _guardar_adjuntos_entrantes(seg["caso_id"], seg["id"], message_id)
    except Exception:
        log.exception("[reclamos_seguros_email_service] No se pudieron completar los adjuntos de %s", message_id[:20])


def process_incoming_seguros_emails() -> int:
    """Lee el buzon del modulo y enlaza cada respuesta por conversation_id. Si no hay
    caso relacionado, se ignora (Decision 1: no crea casos nuevos desde correo)."""
    procesados = 0
    for em in graph.fetch_seguros_emails():
        message_id = em["message_id"]
        try:
            if repo.existe_seguimiento_con_message_id(message_id):
                _completar_adjuntos_pendientes(em, message_id)
                graph.mark_seguros_email_as_read(message_id)
                continue

            caso = repo.buscar_caso_por_conversation_id(em.get("conversation_id"))
            if not caso:
                log.info("[reclamos_seguros_email_service] Correo sin caso relacionado, se ignora: %s",
                         em.get("subject_raw"))
                graph.mark_seguros_email_as_read(message_id)
                continue

            observacion = _observacion_de_correo(em, message_id)
            seg_id = repo.add_seguimiento(
                caso["id"], observacion, usuario_id=None, usuario_nombre=None,
                origen=ORIGEN_CORREO_ENTRANTE, remitente_email=em.get("from_email"),
                message_id=message_id, conversation_id=em.get("conversation_id"),
            )
            if em.get("has_attachments"):
                _guardar_adjuntos_entrantes(caso["id"], seg_id, message_id)

            procesados += 1
            if caso["estado"] != ESTADO_ABIERTO:
                log.info("[reclamos_seguros_email_service] Correo registrado como nota tardia en caso %s cerrado (sin reabrir)",
                         caso.get("codigo") or caso["id"])

            graph.mark_seguros_email_as_read(message_id)
        except Exception:
            log.exception("[reclamos_seguros_email_service] Fallo procesando correo %s",
                          message_id[:20] if message_id else "?")
    return procesados


def notificar_casos_vencidos() -> int:
    """Avisa de casos abiertos hace mas de 30/45/60 dias, con dedupe durable (columnas
    notificado_30d/45d/60d) -- a diferencia del set() en memoria que usa notify_unassigned_tickets()."""
    coordinador = rsh.get_coordinador_reclamos_seguros()
    roles = rsh.get_roles_visibilidad_total()
    destinatarios = repo.get_destinatarios_notificacion_vencimiento(roles)

    if coordinador and coordinador.get("usuario_id"):
        from modules.db import get_db
        cur = get_db().cursor()
        cur.execute("SELECT email FROM usuarios WHERE id = ? AND email IS NOT NULL", (coordinador["usuario_id"],))
        row = cur.fetchone()
        if row and row[0] and row[0] not in destinatarios:
            destinatarios.append(row[0])

    if not destinatarios:
        log.warning("[reclamos_seguros_email_service] Sin destinatarios configurados para alerta de vencimiento")
        return 0

    total_notificados = 0
    for umbral, columna in UMBRALES_VENCIMIENTO_DIAS:
        casos = repo.get_casos_para_alerta_vencimiento(umbral, columna)
        if not casos:
            continue
        from modules.planificador.planificador_notifications import _email_html
        link = _link_lista()
        cuerpo = _email_html(
            "Reclamos Seguros", f"Reclamos abiertos hace más de {umbral} días",
            f"Hay {len(casos)} reclamo(s) de seguro abierto(s) hace más de {umbral} días:",
            [(_esc(c.get("codigo") or c["id"]),
              _esc(f"{c.get('tipo_caso', '')} · {c.get('solicitante_nombre', '')} · {c.get('fecha', '')}"))
             for c in casos],
            nota="Ingresa al SGQ → Reclamos Seguros para ver el detalle.",
            boton=("Ver casos", link) if link else None,
        )
        send_email_async(destinatarios, f"[Reclamos Seguros] Casos abiertos +{umbral} días", cuerpo)
        for c in casos:
            repo.marcar_notificado_vencimiento(c["id"], columna)
        total_notificados += len(casos)

    return total_notificados
