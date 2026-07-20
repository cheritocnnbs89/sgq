# modules/telegram_webhook.py
# -*- coding: utf-8 -*-
"""
Blueprint: Webhook de Telegram.

FLUJO DE REGISTRO para motorizado:
1. El usuario abre @Quimpac_mensajeria_bot y envía /start
2. El bot pide su correo SGQ
3. El usuario escribe su email
4. El sistema busca el usuario en la BD y guarda el chat_id
5. Desde ese momento recibirá notificaciones de sus solicitudes aprobadas

CONFIGURACIÓN (una sola vez, desde el panel de configuración del planificador):
  POST /telegram/setup-webhook   → registra la URL pública en Telegram
  GET  /telegram/status          → muestra estado del webhook actual

ENDPOINT PÚBLICO (sin autenticación — llamado por Telegram):
  POST /telegram/webhook         → procesa mensajes entrantes
"""
from __future__ import annotations

import json

from flask import Blueprint, request, jsonify, redirect, url_for, flash, session

from .telegram_utils import send_message, set_webhook, get_webhook_info
from .auth.routes_auth import require_login, require_permission

telegram_bp = Blueprint("telegram", __name__, url_prefix="/telegram")

# ─── estados de conversación en memoria (chat_id → estado) ──────────────────
# Producción con múltiples workers: usar redis o tabla DB. Para un solo worker
# este dict en memoria funciona correctamente.
_CONV_STATE: dict[str, str] = {}


# ──────────────────────────────────────────────
# Webhook público (llamado por Telegram)
# ──────────────────────────────────────────────

@telegram_bp.route("/webhook", methods=["POST"], endpoint="telegram_webhook")
def webhook():
    """Recibe updates de Telegram y los procesa."""
    try:
        data    = request.get_json(silent=True) or {}
        message = data.get("message") or data.get("edited_message") or {}
        chat    = message.get("chat", {})
        chat_id = str(chat.get("id", ""))
        text    = (message.get("text") or "").strip()

        if not chat_id or not text:
            return jsonify({"ok": True})

        _handle_message(chat_id, text)
    except Exception as exc:
        try:
            from flask import current_app
            current_app.logger.error("telegram webhook error: %s", exc)
        except Exception:
            pass
    return jsonify({"ok": True})


def _handle_message(chat_id: str, text: str) -> None:
    """Máquina de estados para el registro de usuarios."""
    state = _CONV_STATE.get(chat_id, "idle")

    if text.startswith("/start"):
        _CONV_STATE[chat_id] = "waiting_email"
        send_message(chat_id,
            "👋 ¡Hola! Soy el bot de notificaciones de <b>SGQ Quimpac</b>.\n\n"
            "Para vincularte y recibir alertas de tus servicios asignados, "
            "escribe tu correo corporativo SGQ:"
        )
        return

    if text.startswith("/"):
        send_message(chat_id,
            "Usa /start para vincular tu cuenta SGQ con este bot."
        )
        return

    if state == "waiting_email":
        email = text.lower().strip()
        result = _register_user_by_email(chat_id, email)
        if result["ok"]:
            _CONV_STATE.pop(chat_id, None)
            send_message(chat_id,
                f"✅ ¡Cuenta vinculada correctamente!\n\n"
                f"Hola <b>{result['nombre']}</b>, a partir de ahora recibirás "
                f"notificaciones cuando se te asigne un servicio."
            )
        else:
            send_message(chat_id,
                f"❌ {result['msg']}\n\n"
                "Verifica el correo e intenta de nuevo, o contacta al administrador."
            )
        return

    # Estado idle — recordar al usuario qué hacer
    send_message(chat_id,
        "Envía /start para vincular tu cuenta SGQ con este bot."
    )


def _register_user_by_email(chat_id: str, email: str) -> dict:
    """
    Busca el usuario por email en la BD y guarda su telegram_chat_id.
    Devuelve {'ok': True/False, 'nombre': ..., 'msg': ...}
    """
    try:
        from .db import get_db
        conn = get_db()
        cur  = conn.cursor()

        cur.execute(
            "SELECT id, COALESCE(nombre_completo, username) AS nombre "
            "FROM usuarios WHERE LOWER(email) = ? AND COALESCE(disabled,0) = 0",
            (email.lower(),)
        )
        row = cur.fetchone()
        if not row:
            conn.close()
            return {"ok": False, "msg": f"No encontré ningún usuario activo con el correo «{email}»."}

        uid    = row[0]
        nombre = row[1] or "Usuario"

        cur.execute(
            "UPDATE usuarios SET telegram_chat_id = ? WHERE id = ?",
            (chat_id, uid)
        )
        conn.commit()
        conn.close()
        return {"ok": True, "nombre": nombre}
    except Exception as exc:
        return {"ok": False, "msg": f"Error al registrar: {exc}"}


# ──────────────────────────────────────────────
# Admin: configurar webhook (solo admin)
# ──────────────────────────────────────────────

@telegram_bp.route("/setup-webhook", methods=["POST"], endpoint="telegram_setup_webhook")
@require_login
def setup_webhook():
    """Registra la URL pública del webhook en Telegram."""
    from flask import current_app
    base_url = request.form.get("base_url", "").strip().rstrip("/")
    if not base_url:
        flash("Debes ingresar la URL base pública del servidor.", "warning")
        return redirect(url_for("planificador.planificador_configuracion"))

    webhook_url = base_url + "/telegram/webhook"
    result = set_webhook(webhook_url)
    if result.get("ok"):
        flash(f"✅ Webhook registrado: {webhook_url}", "success")
    else:
        flash(f"❌ Error al registrar webhook: {result.get('description', result)}", "danger")
    return redirect(url_for("planificador.planificador_configuracion"))


@telegram_bp.route("/status", methods=["GET"], endpoint="telegram_status")
@require_login
def status():
    """Devuelve JSON con estado del webhook."""
    return jsonify(get_webhook_info())


# ──────────────────────────────────────────────
# Registro en la app
# ──────────────────────────────────────────────

def register_telegram_routes(app):
    app.register_blueprint(telegram_bp)
