# modules/telegram_utils.py
# -*- coding: utf-8 -*-
"""
Utilidades para Telegram Bot API.
- Usa solo urllib (sin dependencias externas).
- El token se lee de la BD (config 'telegram_bot_token') o de la variable
  de entorno TELEGRAM_BOT_TOKEN.
- El chat_id de cada usuario se guarda en usuarios.telegram_chat_id.
"""
from __future__ import annotations

import json
import os
import ssl
import urllib.parse
import urllib.request
from typing import Optional

# Contexto SSL que no verifica el certificado del servidor.
# Necesario en entornos Windows donde Python no puede acceder al store de
# certificados del sistema operativo para validar api.telegram.org.
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

_TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


def _get_token() -> Optional[str]:
    """Lee el token del bot desde la BD o variable de entorno."""
    try:
        from .db import get_config_value
        token = get_config_value("telegram_bot_token")
        if token:
            return token.strip()
    except Exception:
        pass
    return os.environ.get("TELEGRAM_BOT_TOKEN", "").strip() or None


def send_message(chat_id: str | int, text: str,
                 parse_mode: str = "HTML") -> bool:
    """
    Envía un mensaje de texto al chat_id indicado.
    Devuelve True si fue exitoso, False en caso de error.
    """
    token = _get_token()
    if not token or not chat_id:
        return False

    url  = _TELEGRAM_API.format(token=token, method="sendMessage")
    data = json.dumps({
        "chat_id":    str(chat_id),
        "text":       text,
        "parse_mode": parse_mode,
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8, context=_SSL_CTX) as resp:
            result = json.loads(resp.read().decode())
            return result.get("ok", False)
    except Exception as exc:
        _log_warning("telegram send_message error chat_id=%s: %s", chat_id, exc)
        return False


def set_webhook(webhook_url: str) -> dict:
    """
    Registra la URL de webhook en Telegram.
    Llamar una vez al configurar o cambiar de servidor.
    """
    token = _get_token()
    if not token:
        return {"ok": False, "error": "token no configurado"}

    url  = _TELEGRAM_API.format(token=token, method="setWebhook")
    data = json.dumps({"url": webhook_url}).encode("utf-8")
    try:
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as resp:
            return json.loads(resp.read().decode())
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def delete_webhook() -> dict:
    """Elimina el webhook registrado (útil para hacer polling en desarrollo)."""
    token = _get_token()
    if not token:
        return {"ok": False, "error": "token no configurado"}
    url = _TELEGRAM_API.format(token=token, method="deleteWebhook")
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as resp:
            return json.loads(resp.read().decode())
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def get_webhook_info() -> dict:
    """Devuelve información del webhook actual."""
    token = _get_token()
    if not token:
        return {"ok": False, "error": "token no configurado"}
    url = _TELEGRAM_API.format(token=token, method="getWebhookInfo")
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as resp:
            return json.loads(resp.read().decode())
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _log_warning(msg: str, *args) -> None:
    try:
        from flask import current_app
        current_app.logger.warning(msg, *args)
    except Exception:
        pass
