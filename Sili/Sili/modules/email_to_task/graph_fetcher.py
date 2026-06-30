# modules/email_to_task/graph_fetcher.py
# -*- coding: utf-8 -*-
"""
Lee correos del buzón configurado en bo.configuracion (graph_mailbox)
filtrando los dirigidos a graph_soporte_addr,
usando Microsoft Graph API con client_credentials (app-only).

Claves en bo.configuracion:
    graph_tenant_id      — ID de tenant Azure
    graph_client_id      — ID de aplicación registrada en Azure
    graph_client_secret  — Clave de aplicación (app password)
    graph_mailbox        — Buzón a leer
    graph_soporte_addr   — Dirección de soporte a filtrar
"""

from __future__ import annotations

import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

def _cfg(clave: str, default: str = "") -> str:
    """Lee un valor de bo.configuracion; fallback a variable de entorno."""
    try:
        from modules.db import get_config_value
        val = get_config_value(clave)
        if val:
            return str(val).strip()
    except Exception:
        pass
    return os.getenv(clave.upper(), default).strip()

log = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────
# Token cache  (simple in-memory, suficiente para proceso único)
# ────────────────────────────────────────────────────────────────────
_token_cache: dict = {"access_token": None, "expires_at": 0.0}


def _get_access_token() -> Optional[str]:
    """Obtiene (o reutiliza) un token OAuth2 client_credentials."""
    now = time.time()
    if _token_cache["access_token"] and now < _token_cache["expires_at"] - 60:
        return _token_cache["access_token"]

    tenant_id     = _cfg("graph_tenant_id")
    client_id     = _cfg("graph_client_id")
    client_secret = _cfg("graph_client_secret")

    if not all([tenant_id, client_id, client_secret]):
        log.warning("[graph_fetcher] Claves graph_tenant_id / graph_client_id / graph_client_secret no configuradas en bo.configuracion")
        return None

    # Diagnóstico (muestra primeros 4 chars del secreto para verificar que cargó bien)
    log.info(
        "[graph_fetcher] Auth: tenant=%s client_id=%s secret_prefix=%s secret_len=%d",
        tenant_id[:8], client_id[:8], client_secret[:4], len(client_secret)
    )

    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    data = {
        "grant_type":    "client_credentials",
        "client_id":     client_id,
        "client_secret": client_secret,
        "scope":         "https://graph.microsoft.com/.default",
    }

    try:
        resp = requests.post(url, data=data, timeout=15)
        if not resp.ok:
            try:
                err_body = resp.json()
                log.error(
                    "[graph_fetcher] 401/Error token Azure — error=%s description=%s "
                    "(tenant=%s client_id=%s secret_len=%d)",
                    err_body.get("error"), err_body.get("error_description", "")[:200],
                    tenant_id, client_id, len(client_secret)
                )
            except Exception:
                log.error("[graph_fetcher] Error token HTTP %d: %s", resp.status_code, resp.text[:300])
            return None
        payload = resp.json()
        _token_cache["access_token"] = payload["access_token"]
        _token_cache["expires_at"]   = now + int(payload.get("expires_in", 3600))
        log.info("[graph_fetcher] Token OAuth2 obtenido (expira en %ds)", payload.get("expires_in", 3600))
        return _token_cache["access_token"]
    except Exception as exc:
        log.error("[graph_fetcher] Error obteniendo token: %s", exc)
        return None


# ────────────────────────────────────────────────────────────────────
# Helpers de texto
# ────────────────────────────────────────────────────────────────────

def _html_to_text(html: str) -> str:
    html = re.sub(r"<style[^>]*>.*?</style>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"</?p[^>]*>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"<[^>]+>", "", html)
    html = html.replace("&nbsp;", " ").replace("&amp;", "&") \
               .replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html.strip()


def _clean_subject(subject: str) -> str:
    """Elimina prefijos Re:, Fwd:, RV:, etc."""
    s = subject.strip()
    s = re.sub(r"^\[\d+\]\s*", "", s)
    prefixes = re.compile(r"^(Re|Fwd|FW|RE|RV|AW|ENT|TR|SV|VS)(\[\d+\])?:\s*", re.IGNORECASE)
    prev = None
    while s != prev:
        prev = s
        s = prefixes.sub("", s)
    return s.strip()


def _parse_graph_datetime(dt_str: str) -> Optional[datetime]:
    """Parsea fechas de Graph API (ISO 8601 UTC)."""
    if not dt_str:
        return None
    try:
        # Graph devuelve "2024-06-10T14:32:00Z"
        dt_str = dt_str.replace("Z", "+00:00")
        return datetime.fromisoformat(dt_str)
    except Exception:
        return None


# ────────────────────────────────────────────────────────────────────
# Fecha de corte
# ────────────────────────────────────────────────────────────────────

def _get_since_date() -> str:
    """Inicio del día de hoy en UTC — solo se procesan correos recibidos hoy en adelante."""
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return today.strftime("%Y-%m-%dT%H:%M:%SZ")


# ────────────────────────────────────────────────────────────────────
# Función principal
# ────────────────────────────────────────────────────────────────────

def fetch_attachment_content(message_id: str, attachment_id: str) -> Optional[dict]:
    """
    Descarga el contenido binario de un adjunto desde Graph API.
    Devuelve dict con keys: content_bytes, content_type, name.
    """
    import base64
    token = _get_access_token()
    if not token:
        return None
    mailbox = _cfg("graph_mailbox", "notificacionesssg@quimpac.com.ec")
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
                "content_type":  data.get("contentType", "application/octet-stream"),
                "name":          data.get("name", "adjunto"),
            }
    except Exception as exc:
        log.error("[graph_fetcher] Error descargando adjunto %s: %s", attachment_id[:20], exc)
    return None


def fetch_attachments_list(message_id: str) -> list[dict]:
    """
    Devuelve metadata de todos los adjuntos de un mensaje (sin descargar contenido).
    Cada item: {attachment_id, name, content_type, size, is_inline, content_id}
    """
    token = _get_access_token()
    if not token:
        return []
    mailbox = _cfg("graph_mailbox", "notificacionesssg@quimpac.com.ec")
    url = (
        f"https://graph.microsoft.com/v1.0/users/{mailbox}"
        f"/messages/{message_id}/attachments"
        f"?$select=id,name,contentType,size,isInline,contentId"
    )
    try:
        resp = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=10)
        if resp.ok:
            return [
                {
                    "attachment_id": a.get("id", ""),
                    "name":          a.get("name", "sin nombre"),
                    "content_type":  a.get("contentType", ""),
                    "size":          a.get("size", 0),
                    "is_inline":     bool(a.get("isInline")),
                    "content_id":    (a.get("contentId") or "").strip("<>"),
                }
                for a in resp.json().get("value", [])
            ]
    except Exception as exc:
        log.debug("[graph_fetcher] No se pudo listar adjuntos de %s: %s", message_id[:20], exc)
    return []


def _fetch_attachment_names(mailbox: str, message_id: str, headers: dict) -> list[str]:
    """Obtiene los nombres de adjuntos de un mensaje (solo metadatos, sin descargar)."""
    url = (
        f"https://graph.microsoft.com/v1.0/users/{mailbox}"
        f"/messages/{message_id}/attachments"
        f"?$select=name,size,contentType"
    )
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.ok:
            return [a.get("name", "sin nombre") for a in resp.json().get("value", [])]
    except Exception as exc:
        log.debug("[graph_fetcher] No se pudo obtener adjuntos de %s: %s", message_id[:20], exc)
    return []


def fetch_soporte_emails() -> list[dict]:
    """
    Lee los correos no leídos del buzón configurado (GRAPH_MAILBOX)
    que tienen como destinatario soporteti@quimpac.com.ec (GRAPH_SOPORTE_ADDR).

    Retorna lista de dicts:
        {
            message_id   : str,   # ID único de Graph API
            internet_id  : str,   # cabecera Message-ID del RFC
            from_email   : str,
            from_name    : str,
            subject      : str,
            body_text    : str,   # texto plano con adjuntos al inicio si los hay
            received_at  : datetime (UTC),
            has_attachments: bool,
        }
    """
    token = _get_access_token()
    if not token:
        return []

    mailbox      = _cfg("graph_mailbox",      "notificacionesssg@quimpac.com.ec")
    soporte_addr = _cfg("graph_soporte_addr", "soporteti@quimpac.com.ec").lower()

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
    }

    since = _get_since_date()
    url = (
        f"https://graph.microsoft.com/v1.0/users/{mailbox}"
        f"/mailFolders/Inbox/messages"
        f"?$filter=receivedDateTime ge {since}"
        f"&$select=id,internetMessageId,conversationId,subject,from,toRecipients,ccRecipients,"
        f"receivedDateTime,body,hasAttachments"
        f"&$orderby=receivedDateTime asc"
        f"&$top=50"
    )

    results: list[dict] = []

    try:
        resp = requests.get(url, headers=headers, timeout=20)

        if resp.status_code == 401:
            log.error("[graph_fetcher] 401 Unauthorized — verifica permisos Mail.Read en Azure")
            return []
        if resp.status_code == 403:
            log.error("[graph_fetcher] 403 Forbidden — la app no tiene consentimiento para el buzón %s", mailbox)
            return []

        resp.raise_for_status()
        messages = resp.json().get("value", [])
        log.info("[graph_fetcher] %d correo(s) en %s desde hoy", len(messages), mailbox)

        for msg in messages:
            # Verificar si alguno de los destinatarios es soporteti
            all_recipients = (msg.get("toRecipients") or []) + (msg.get("ccRecipients") or [])
            recipient_emails = [
                (r.get("emailAddress") or {}).get("address", "").lower()
                for r in all_recipients
            ]

            if soporte_addr not in recipient_emails:
                log.debug(
                    "[graph_fetcher] Ignorando mensaje '%s' — no va a %s (destinatarios: %s)",
                    msg.get("subject"), soporte_addr, recipient_emails
                )
                continue

            # Extraer cuerpo (texto + HTML original)
            body_obj  = msg.get("body") or {}
            body_raw  = body_obj.get("content", "")
            body_type = body_obj.get("contentType", "text").lower()
            body_html = body_raw if body_type == "html" else ""
            if body_type == "html":
                body_text = _html_to_text(body_raw)
            else:
                body_text = body_raw

            # Adjuntos: obtener nombres y prefijar al body_text
            has_attachments = bool(msg.get("hasAttachments"))
            if has_attachments:
                attachment_names = _fetch_attachment_names(mailbox, msg["id"], headers)
                if attachment_names:
                    adjuntos_line = "📎 ADJUNTOS: " + ", ".join(attachment_names) + "\n"
                    body_text = adjuntos_line + "─" * 40 + "\n" + body_text

            body_text = body_text[:10000]

            from_obj   = (msg.get("from") or {}).get("emailAddress") or {}
            from_email = from_obj.get("address", "").lower().strip()
            from_name  = from_obj.get("name", "").strip()

            received_at     = _parse_graph_datetime(msg.get("receivedDateTime", ""))
            conversation_id = (msg.get("conversationId") or "").strip()

            results.append({
                "message_id":      msg["id"],
                "internet_id":     msg.get("internetMessageId", "").strip(),
                "conversation_id": conversation_id,
                "from_email":      from_email,
                "from_name":       from_name,
                "subject":         _clean_subject(msg.get("subject") or "Sin asunto"),
                "subject_raw":     (msg.get("subject") or "Sin asunto").strip(),
                "body_text":       body_text,
                "body_html":       body_html,
                "received_at":     received_at,
                "has_attachments": has_attachments,
            })

        log.info("[graph_fetcher] %d correo(s) dirigido(s) a %s encontrado(s)", len(results), soporte_addr)

    except requests.RequestException as exc:
        log.error("[graph_fetcher] Error HTTP leyendo correos: %s", exc)
    except Exception as exc:
        log.error("[graph_fetcher] Error inesperado: %s", exc)

    return results


def mark_as_read(message_id: str) -> bool:
    """Marca un mensaje como leído en Graph API."""
    token = _get_access_token()
    if not token:
        return False

    mailbox = _cfg("graph_mailbox", "notificacionesssg@quimpac.com.ec")
    url = f"https://graph.microsoft.com/v1.0/users/{mailbox}/messages/{message_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
    }

    try:
        resp = requests.patch(url, headers=headers, json={"isRead": True}, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as exc:
        log.warning("[graph_fetcher] No se pudo marcar mensaje %s como leído: %s", message_id[:20], exc)
        return False
