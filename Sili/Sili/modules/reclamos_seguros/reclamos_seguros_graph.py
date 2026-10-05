# modules/reclamos_seguros/reclamos_seguros_graph.py
# -*- coding: utf-8 -*-
"""Cliente Graph API del buzon de Reclamos Seguros (segurosqp@quimpac.com.ec).
Reutiliza el token OAuth2 y los helpers de texto de modules/email_to_task/graph_fetcher.py
(son genericos, no especificos de soporteti@) en vez de duplicarlos."""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional

import requests

from modules.email_to_task.graph_fetcher import (
    _get_access_token, _html_to_text, _parse_graph_datetime, _clean_subject,
)
from . import reclamos_seguros_helpers as rsh

log = logging.getLogger(__name__)


def _mailbox() -> str:
    """Buzon a leer/enviar. Override opcional por env var para el caso en que
    segurosqp@ resulte ser un buzon compartido leido a traves de otra cuenta delegada
    (igual que soporteti@ se lee hoy a traves de jchavez@ via GRAPH_MAILBOX) -- depende
    de como este armado el registro de la app en Azure, confirmar con quien administre
    Entra ID antes de produccion."""
    override = os.getenv("GRAPH_RECLAMOS_SEGUROS_MAILBOX", "").strip()
    return override or rsh.get_cuenta_correo_reclamos_seguros()


def _get_since_date() -> str:
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return today.strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_seguros_emails() -> list[dict]:
    """Lee los correos de hoy en el Inbox del buzon de Reclamos Seguros. A diferencia
    de fetch_soporte_emails(), no filtra por destinatario -- el buzon leido YA es la
    cuenta del modulo, no una delegada que recibe de varios departamentos."""
    token = _get_access_token()
    if not token:
        return []

    mailbox = _mailbox()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    since = _get_since_date()
    url = (
        f"https://graph.microsoft.com/v1.0/users/{mailbox}"
        f"/mailFolders/Inbox/messages"
        f"?$filter=receivedDateTime ge {since}"
        f"&$select=id,internetMessageId,conversationId,subject,from,receivedDateTime,body,hasAttachments"
        f"&$orderby=receivedDateTime asc"
        f"&$top=50"
    )

    results: list[dict] = []
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code == 401:
            log.error("[reclamos_seguros_graph] 401 Unauthorized - verifica permisos Mail.Read en Azure para %s", mailbox)
            return []
        if resp.status_code == 403:
            log.error("[reclamos_seguros_graph] 403 Forbidden - la app no tiene consentimiento para el buzon %s", mailbox)
            return []
        resp.raise_for_status()
        messages = resp.json().get("value", [])
        log.info("[reclamos_seguros_graph] %d correo(s) en %s desde hoy", len(messages), mailbox)

        for msg in messages:
            body_obj = msg.get("body") or {}
            body_raw = body_obj.get("content", "")
            body_type = body_obj.get("contentType", "text").lower()
            body_html = body_raw if body_type == "html" else ""
            body_text = _html_to_text(body_raw) if body_type == "html" else body_raw
            body_text = body_text[:10000]

            from_obj = (msg.get("from") or {}).get("emailAddress") or {}

            results.append({
                "message_id": msg["id"],
                "internet_id": msg.get("internetMessageId", "").strip(),
                "conversation_id": (msg.get("conversationId") or "").strip(),
                "from_email": from_obj.get("address", "").lower().strip(),
                "from_name": from_obj.get("name", "").strip(),
                "subject": _clean_subject(msg.get("subject") or "Sin asunto"),
                "subject_raw": (msg.get("subject") or "Sin asunto").strip(),
                "body_text": body_text,
                "body_html": body_html,
                "received_at": _parse_graph_datetime(msg.get("receivedDateTime", "")),
                "has_attachments": bool(msg.get("hasAttachments")),
            })
    except requests.RequestException as exc:
        log.error("[reclamos_seguros_graph] Error HTTP leyendo correos: %s", exc)
    except Exception as exc:
        log.error("[reclamos_seguros_graph] Error inesperado: %s", exc)

    return results


def fetch_seguros_attachments_list(message_id: str) -> list[dict]:
    token = _get_access_token()
    if not token:
        return []
    mailbox = _mailbox()
    url = (
        f"https://graph.microsoft.com/v1.0/users/{mailbox}"
        f"/messages/{message_id}/attachments"
        # contentId NO se puede pedir en $select de la lista (solo existe en fileAttachment y Graph
        # responde 400); se obtiene al descargar cada adjunto.
        f"?$select=id,name,contentType,size,isInline"
    )
    try:
        resp = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=10)
        if resp.ok:
            return [
                {
                    "attachment_id": a.get("id", ""),
                    "name": a.get("name", "sin nombre"),
                    "content_type": a.get("contentType", ""),
                    "size": a.get("size", 0),
                    "is_inline": bool(a.get("isInline")),
                    "content_id": (a.get("contentId") or "").strip("<>"),
                }
                for a in resp.json().get("value", [])
            ]
    except Exception as exc:
        log.debug("[reclamos_seguros_graph] No se pudo listar adjuntos de %s: %s", message_id[:20], exc)
    return []


def fetch_seguros_attachment_content(message_id: str, attachment_id: str) -> Optional[dict]:
    import base64
    token = _get_access_token()
    if not token:
        return None
    mailbox = _mailbox()
    url = (
        f"https://graph.microsoft.com/v1.0/users/{mailbox}"
        f"/messages/{message_id}/attachments/{attachment_id}"
    )
    try:
        resp = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=15)
        if resp.ok:
            data = resp.json()
            raw_b64 = data.get("contentBytes", "")
            return {
                "content_bytes": base64.b64decode(raw_b64) if raw_b64 else b"",
                "content_type": data.get("contentType", "application/octet-stream"),
                "name": data.get("name", "adjunto"),
                "content_id": (data.get("contentId") or "").strip("<>"),
            }
    except Exception as exc:
        log.error("[reclamos_seguros_graph] Error descargando adjunto %s: %s", attachment_id[:20], exc)
    return None


def mark_seguros_email_as_read(message_id: str) -> bool:
    token = _get_access_token()
    if not token:
        return False
    mailbox = _mailbox()
    url = f"https://graph.microsoft.com/v1.0/users/{mailbox}/messages/{message_id}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        resp = requests.patch(url, headers=headers, json={"isRead": True}, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as exc:
        log.warning("[reclamos_seguros_graph] No se pudo marcar mensaje %s como leido: %s", message_id[:20], exc)
        return False


def find_sent_message(internet_id: str, attempts: int = 6, wait: float = 2.0) -> Optional[dict]:
    """Busca por Message-ID (RFC) un correo ya enviado por SMTP para obtener su id y
    conversationId de Graph (solo requiere Mail.Read). La copia en Enviados puede tardar
    unos segundos en aparecer, por eso reintenta."""
    token = _get_access_token()
    if not token or not internet_id:
        return None
    url = f"https://graph.microsoft.com/v1.0/users/{_mailbox()}/messages"
    params = {"$filter": f"internetMessageId eq '{internet_id}'", "$select": "id,conversationId"}
    headers = {"Authorization": f"Bearer {token}"}
    for i in range(attempts):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            if resp.ok:
                vals = resp.json().get("value", [])
                if vals:
                    return {"message_id": vals[0]["id"],
                            "conversation_id": (vals[0].get("conversationId") or "").strip()}
            else:
                log.warning("[reclamos_seguros_graph] Busqueda de enviado HTTP %d", resp.status_code)
        except Exception as exc:
            log.warning("[reclamos_seguros_graph] Busqueda de enviado fallo: %s", exc)
        if i < attempts - 1:
            time.sleep(wait)
    return None


def send_seguros_email_graph(to_email: str, subject: str, html_body: str,
                             imagenes: Optional[list] = None,
                             archivos: Optional[list] = None) -> Optional[dict]:
    """Envia un correo desde el buzon del modulo via Graph API, en dos pasos para
    capturar el conversation_id ANTES de que pueda llegar una respuesta:
    1) crea el borrador (POST .../messages), 2) lo despacha (POST .../send).
    Nunca lanza excepcion -- devuelve None si falla, el caller decide como avisar.
    DEPENDENCIA A CONFIRMAR: permiso Mail.Send en el registro de la app en Azure,
    cubriendo el buzon del modulo como remitente."""
    token = _get_access_token()
    if not token or not to_email:
        return None
    mailbox = _mailbox()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    draft_payload = {
        "subject": subject,
        "body": {"contentType": "HTML", "content": html_body},
        "toRecipients": [{"emailAddress": {"address": to_email}}],
    }
    if imagenes or archivos:
        import base64
        # Al crear el borrador con adjuntos Graph admite ~3 MB; si hay mas, se devuelve None
        # para que el llamador use el respaldo SMTP (sin ese limite practico).
        if archivos and sum(len(d) for _, d, _ in archivos) > 3 * 1024 * 1024:
            log.info("[reclamos_seguros_graph] Adjuntos > 3 MB: se usa el respaldo SMTP")
            return None
        adjuntos = [{
            "@odata.type": "#microsoft.graph.fileAttachment",
            "name": f"{cid}.{subtipo}", "contentType": f"image/{subtipo}",
            "contentBytes": base64.b64encode(data).decode("ascii"),
            "isInline": True, "contentId": cid,
        } for cid, data, subtipo in (imagenes or [])]
        adjuntos += [{
            "@odata.type": "#microsoft.graph.fileAttachment",
            "name": nombre, "contentType": mime,
            "contentBytes": base64.b64encode(data).decode("ascii"),
            "isInline": False,
        } for nombre, data, mime in (archivos or [])]
        draft_payload["attachments"] = adjuntos
    try:
        resp = requests.post(
            f"https://graph.microsoft.com/v1.0/users/{mailbox}/messages",
            headers=headers, json=draft_payload, timeout=15,
        )
        if not resp.ok:
            log.error("[reclamos_seguros_graph] Error creando borrador para %s: HTTP %d %s",
                      to_email, resp.status_code, resp.text[:300])
            return None
        draft = resp.json()
        message_id = draft.get("id")
        conversation_id = (draft.get("conversationId") or "").strip()
        if not message_id:
            return None

        resp2 = requests.post(
            f"https://graph.microsoft.com/v1.0/users/{mailbox}/messages/{message_id}/send",
            headers=headers, timeout=15,
        )
        if not resp2.ok:
            log.error("[reclamos_seguros_graph] Error enviando borrador %s a %s: HTTP %d %s",
                      message_id[:20], to_email, resp2.status_code, resp2.text[:300])
            return None

        return {"message_id": message_id, "conversation_id": conversation_id}
    except Exception as exc:
        log.error("[reclamos_seguros_graph] Error inesperado enviando correo a %s: %s", to_email, exc)
        return None
