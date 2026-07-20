# modules/email_to_task/email_fetcher.py
# -*- coding: utf-8 -*-
"""
Conexión IMAP para leer correos no leídos y devolverlos como dicts listos
para ser procesados por email_processor.

Configuración via variables de entorno (.env):
    EMAIL_TICKET_IMAP_HOST   → servidor IMAP  (p.ej. imap.gmail.com)
    EMAIL_TICKET_IMAP_PORT   → puerto         (default 993)
    EMAIL_TICKET_USER        → cuenta de correo
    EMAIL_TICKET_PASS        → contraseña (o App Password para Gmail/Outlook)
    EMAIL_TICKET_FOLDER      → carpeta a leer (default INBOX)
    EMAIL_TICKET_MARK_SEEN   → 1 para marcar leído después de procesar (default 1)
"""

from __future__ import annotations

import email
import imaplib
import logging
import os
import re
from email.header import decode_header as _decode_header

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Helpers de decodificación
# ─────────────────────────────────────────────────────────────

def _decode(value: str | None) -> str:
    """Decodifica cabeceras MIME (encoded-words, UTF-8, etc.)."""
    if not value:
        return ""
    parts = []
    for raw, charset in _decode_header(value):
        if isinstance(raw, bytes):
            parts.append(raw.decode(charset or "utf-8", errors="replace"))
        else:
            parts.append(str(raw))
    return " ".join(parts).strip()


def _extract_email_addr(raw: str) -> str:
    """Extrae la dirección de correo de un campo From / To."""
    m = re.search(r"<([^>]+)>", raw)
    if m:
        return m.group(1).strip().lower()
    # Sin <>, tomar el primer token que parezca email
    for tok in raw.split():
        if "@" in tok:
            return tok.strip(" ,;\"'").lower()
    return raw.strip().lower()


def _html_to_text(html: str) -> str:
    """Convierte HTML básico a texto plano."""
    # Eliminar bloques <style> y <script>
    html = re.sub(r"<style[^>]*>.*?</style>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    # <br> y <p> → salto de línea
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"</?p[^>]*>", "\n", html, flags=re.IGNORECASE)
    # Eliminar resto de tags
    html = re.sub(r"<[^>]+>", "", html)
    # Entidades básicas
    html = html.replace("&nbsp;", " ").replace("&amp;", "&").replace(
        "&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    # Espacios múltiples
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html.strip()


def _extract_body(msg: email.message.Message) -> str:
    """Extrae el cuerpo del mensaje como texto plano."""
    plain = ""
    html  = ""

    if msg.is_multipart():
        for part in msg.walk():
            ct  = part.get_content_type()
            cd  = str(part.get("Content-Disposition", "")).lower()
            if "attachment" in cd:
                continue
            charset = part.get_content_charset() or "utf-8"
            try:
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                text = payload.decode(charset, errors="replace")
            except Exception:
                continue

            if ct == "text/plain" and not plain:
                plain = text
            elif ct == "text/html" and not html:
                html = text
    else:
        charset = msg.get_content_charset() or "utf-8"
        try:
            payload = msg.get_payload(decode=True)
            text = payload.decode(charset, errors="replace") if payload else ""
        except Exception:
            text = str(msg.get_payload() or "")

        if msg.get_content_type() == "text/html":
            html = text
        else:
            plain = text

    body = plain.strip() if plain else (_html_to_text(html) if html else "")
    return body[:10_000]   # limitar tamaño


def normalize_subject(subject: str) -> str:
    """
    Elimina prefijos Re:, Fwd:, RV:, FW:, RE:, AW: y los bracketed numbers.
    Devuelve el asunto limpio en minúsculas para comparar.
    """
    s = subject.strip()
    # Eliminar [N] al inicio (listas de correo)
    s = re.sub(r"^\[\d+\]\s*", "", s)
    # Eliminar prefijos iterativamente (pueden estar apilados: Re: Re: Re: ...)
    prefixes = re.compile(
        r"^(Re|Fwd|FW|RE|RV|AW|ENT|TR|SV|VS)(\[\d+\])?:\s*",
        re.IGNORECASE,
    )
    prev = None
    while s != prev:
        prev = s
        s = prefixes.sub("", s)
    return s.strip().lower()


# ─────────────────────────────────────────────────────────────
# Función principal
# ─────────────────────────────────────────────────────────────

def fetch_unread_emails() -> list[dict]:
    """
    Conecta al servidor IMAP, lee los mensajes no vistos (UNSEEN)
    y los devuelve como lista de dicts:

        {
            uid          : bytes,
            message_id   : str,   # cabecera Message-ID (único por email)
            from_email   : str,
            subject      : str,   # asunto original decodificado
            subject_norm : str,   # asunto normalizado (sin Re:/Fwd:) en minúsculas
            body         : str,
            in_reply_to  : str,   # cabecera In-Reply-To (para threading)
            references   : str,   # cabecera References
        }

    Retorna lista vacía si la configuración IMAP no está disponible o hay error.
    """
    host      = os.getenv("EMAIL_TICKET_IMAP_HOST", "").strip()
    port      = int(os.getenv("EMAIL_TICKET_IMAP_PORT", "993"))
    user      = os.getenv("EMAIL_TICKET_USER", "").strip()
    password  = os.getenv("EMAIL_TICKET_PASS", "").strip()
    folder    = os.getenv("EMAIL_TICKET_FOLDER", "INBOX").strip()
    mark_seen = os.getenv("EMAIL_TICKET_MARK_SEEN", "1").strip() == "1"

    if not all([host, user, password]):
        log.debug(
            "[email_to_task] IMAP no configurado — "
            "define EMAIL_TICKET_IMAP_HOST, EMAIL_TICKET_USER y EMAIL_TICKET_PASS en .env"
        )
        return []

    results: list[dict] = []

    try:
        imap = imaplib.IMAP4_SSL(host, port)
        imap.login(user, password)

        status, _ = imap.select(folder)
        if status != "OK":
            log.error("[email_to_task] No se pudo seleccionar carpeta: %s", folder)
            imap.logout()
            return []

        status, data = imap.search(None, "UNSEEN")
        if status != "OK" or not data[0]:
            imap.logout()
            return []

        uid_list = data[0].split()
        log.info("[email_to_task] %d correo(s) no leído(s) encontrado(s)", len(uid_list))

        for uid in uid_list:
            try:
                status, msg_data = imap.fetch(uid, "(RFC822)")
                if status != "OK" or not msg_data or not msg_data[0]:
                    continue

                raw_bytes = msg_data[0][1]
                msg = email.message_from_bytes(raw_bytes)

                message_id   = (msg.get("Message-ID") or "").strip()
                from_raw     = _decode(msg.get("From", ""))
                subject_raw  = _decode(msg.get("Subject", "Sin asunto"))
                in_reply_to  = (msg.get("In-Reply-To") or "").strip()
                references   = (msg.get("References") or "").strip()

                from_email   = _extract_email_addr(from_raw)
                body         = _extract_body(msg)

                results.append({
                    "uid":          uid,
                    "message_id":   message_id,
                    "from_email":   from_email,
                    "subject":      subject_raw,
                    "subject_norm": normalize_subject(subject_raw),
                    "body":         body,
                    "in_reply_to":  in_reply_to,
                    "references":   references,
                })

                # Marcar como leído después de leer exitosamente
                if mark_seen:
                    imap.store(uid, "+FLAGS", "\\Seen")

            except Exception as exc:
                log.error("[email_to_task] Error procesando uid=%s: %s", uid, exc)

        imap.logout()
        log.info("[email_to_task] IMAP: %d correo(s) recuperado(s)", len(results))

    except imaplib.IMAP4.error as exc:
        log.error("[email_to_task] Error de autenticación IMAP: %s", exc)
    except Exception as exc:
        log.error("[email_to_task] Error IMAP inesperado: %s", exc)

    return results
