# modules/reclamos_seguros/reclamos_seguros_email_service.py
# -*- coding: utf-8 -*-
"""Fase 2: notificacion saliente al broker y poller entrante de respuestas, enlazando
por conversation_id (Decision 1 del plan -- sin respaldo por codigo en el asunto).
Tambien el aviso de casos abiertos hace demasiado tiempo (30/45/60 dias)."""
from __future__ import annotations

import logging
import os
import uuid
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid

from modules.email_utils import send_email_async
from . import reclamos_seguros_graph as graph
from . import reclamos_seguros_helpers as rsh
from . import reclamos_seguros_repository as repo
from .reclamos_seguros_constants import (
    ORIGEN_CORREO_SALIENTE, ORIGEN_CORREO_ENTRANTE, ESTADO_ABIERTO,
    EXTENSIONES_PERMITIDAS, MAX_ADJUNTO_BYTES, MAX_ADJUNTOS_POR_ENVIO,
    UMBRALES_VENCIMIENTO_DIAS,
)

log = logging.getLogger(__name__)


def _enviar_correo_smtp(to_email: str, asunto: str, cuerpo: str) -> dict | None:
    """Respaldo cuando Graph no puede enviar (falta Mail.Send): envia por SMTP con la
    configuracion smtp_* existente (la clave vive en la BD/config, no en codigo) y luego
    recupera el conversationId desde Enviados via Graph. Para que las respuestas lleguen
    al buzon que lee el poller, el usuario SMTP debe ser el mismo buzon del modulo."""
    from modules.email_to_task.email_inbox_service import _smtp_send
    from modules.db import get_config_value

    mailbox = graph._mailbox()
    smtp_user = (get_config_value("smtp_user", "") or "").strip().lower()
    if smtp_user and smtp_user != mailbox.strip().lower():
        log.warning("[reclamos_seguros_email_service] smtp_user (%s) distinto al buzon del modulo (%s): "
                    "las respuestas no llegaran al buzon que lee el poller", smtp_user, mailbox)

    msg = MIMEText(cuerpo, "html", "utf-8")
    msg["Subject"] = asunto
    msg["From"] = mailbox
    msg["To"] = to_email
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=mailbox.split("@")[-1])

    if not _smtp_send(mailbox, to_email, msg):
        return None
    sent = graph.find_sent_message(msg["Message-ID"])
    if sent:
        return sent
    log.warning("[reclamos_seguros_email_service] Correo enviado por SMTP pero no se hallo en Enviados; "
                "sin conversation_id las respuestas no se enlazaran solas")
    return {"message_id": msg["Message-ID"], "conversation_id": ""}


def _enviar_correo(to_email: str, asunto: str, cuerpo: str) -> dict | None:
    result = graph.send_seguros_email_graph(to_email, asunto, cuerpo)
    if result:
        return result
    log.info("[reclamos_seguros_email_service] Graph no pudo enviar; se intenta por SMTP")
    return _enviar_correo_smtp(to_email, asunto, cuerpo)


def notificar_broker_nuevo_caso(caso: dict, broker_email: str, broker_nombre: str | None) -> bool:
    """Nunca lanza -- el caller trata False como advertencia no bloqueante."""
    if not broker_email:
        return False
    codigo = caso.get("codigo") or f"#{caso['id']}"
    asunto = f"[{codigo}] Nuevo reclamo de seguro registrado \u2014 {caso.get('tipo_caso', '')}"
    cuerpo = (
        f"<p>Se registro un nuevo reclamo de seguro:</p>"
        f"<ul>"
        f"<li><strong>Codigo:</strong> {codigo}</li>"
        f"<li><strong>Tipo:</strong> {caso.get('tipo_caso', '')}</li>"
        f"<li><strong>Fecha:</strong> {caso.get('fecha', '')}</li>"
        f"<li><strong>Descripcion:</strong> {caso.get('descripcion', '')}</li>"
        f"</ul>"
        f"<p>Por favor responda este correo con la gestion/novedades del caso.</p>"
    )
    try:
        result = _enviar_correo(broker_email, asunto, cuerpo)
        if not result:
            log.warning("[reclamos_seguros_email_service] No se pudo notificar al broker %s del caso %s",
                        broker_email, codigo)
            return False
        repo.add_seguimiento(
            caso["id"], "Notificacion enviada al broker por correo.",
            usuario_id=None, usuario_nombre="Sistema", origen=ORIGEN_CORREO_SALIENTE,
            remitente_email=rsh.get_cuenta_correo_reclamos_seguros(),
            message_id=result["message_id"], conversation_id=result["conversation_id"] or None,
        )
        return True
    except Exception:
        log.exception("[reclamos_seguros_email_service] Fallo notificando al broker caso_id=%s", caso.get("id"))
        return False


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


def process_incoming_seguros_emails() -> int:
    """Lee el buzon del modulo y enlaza cada respuesta por conversation_id. Si no hay
    caso relacionado, se ignora (Decision 1: no crea casos nuevos desde correo)."""
    procesados = 0
    for em in graph.fetch_seguros_emails():
        message_id = em["message_id"]
        try:
            if repo.existe_seguimiento_con_message_id(message_id):
                graph.mark_seguros_email_as_read(message_id)
                continue

            caso = repo.buscar_caso_por_conversation_id(em.get("conversation_id"))
            if not caso:
                log.info("[reclamos_seguros_email_service] Correo sin caso relacionado, se ignora: %s",
                         em.get("subject_raw"))
                graph.mark_seguros_email_as_read(message_id)
                continue

            observacion = em.get("body_text") or "(sin contenido)"
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
        filas = "".join(
            f"<tr><td>{c.get('codigo') or c['id']}</td><td>{c.get('tipo_caso', '')}</td>"
            f"<td>{c.get('solicitante_nombre', '')}</td><td>{c.get('fecha', '')}</td></tr>"
            for c in casos
        )
        cuerpo = (
            f"<p>Los siguientes reclamos de seguro llevan mas de {umbral} dias abiertos:</p>"
            f"<table border='1' cellpadding='4' cellspacing='0'>"
            f"<tr><th>Codigo</th><th>Tipo</th><th>Solicitante</th><th>Fecha</th></tr>{filas}</table>"
        )
        send_email_async(destinatarios, f"Reclamos de seguro abiertos +{umbral} dias", cuerpo)
        for c in casos:
            repo.marcar_notificado_vencimiento(c["id"], columna)
        total_notificados += len(casos)

    return total_notificados
