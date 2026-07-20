# modules/whatsapp/webhook.py

import os
from flask import Blueprint, request

from modules.whatsapp.sender import enviar_whatsapp
from modules.whatsapp.menu import MENU_TEXTO
from modules.whatsapp.states import (
    user_states,
    MENU_PRINCIPAL,
    MODO_OM
)

from modules.routes_reclamos import om_chat_responder

whatsapp_bp = Blueprint("whatsapp", __name__)

from modules.config import WHATSAPP_VERIFY_TOKEN

VERIFY_TOKEN = WHATSAPP_VERIFY_TOKEN


# ==========================================
# VALIDACION META WEBHOOK
# ==========================================

@whatsapp_bp.route("/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("Webhook verificado correctamente")
        return challenge, 200

    print("Error verificando webhook")
    return "Error", 403


# ==========================================
# RECIBIR MENSAJES
# ==========================================

@whatsapp_bp.route("/webhook", methods=["POST"])
def recibir_mensaje():
    data = request.get_json()

    print("Webhook recibido:", data)

    try:
        entry = data.get("entry", [])
        if not entry:
            return "ok", 200

        changes = entry[0].get("changes", [])
        if not changes:
            return "ok", 200

        value = changes[0].get("value", {})
        messages = value.get("messages")

        if not messages:
            return "ok", 200

        message = messages[0]
        numero = message.get("from")

        tipo = message.get("type")

        if tipo == "text":
            mensaje = message["text"]["body"].strip()
        elif tipo == "interactive":
            mensaje = extraer_mensaje_interactivo(message)
        else:
            enviar_whatsapp(numero, "Por ahora solo puedo procesar mensajes de texto.")
            return "ok", 200

        manejar_mensaje(numero, mensaje)

        return "ok", 200

    except Exception as e:
        print("Error procesando webhook:", e)
        return "ok", 200


def extraer_mensaje_interactivo(message):
    interactive = message.get("interactive", {})

    if interactive.get("type") == "button_reply":
        return interactive["button_reply"].get("id", "")

    if interactive.get("type") == "list_reply":
        return interactive["list_reply"].get("id", "")

    return ""


# ==========================================
# LOGICA PRINCIPAL
# ==========================================

def manejar_mensaje(numero, mensaje):
    estado = user_states.get(numero)
    texto = mensaje.strip().lower()

    # ======================================
    # VOLVER AL MENU
    # ======================================

    if texto in ["hola", "menu", "menú", "inicio", "salir", "volver"]:
        user_states[numero] = MENU_PRINCIPAL
        enviar_whatsapp(numero, MENU_TEXTO)
        return

    # ======================================
    # MODO OM
    # ======================================

    if estado == MODO_OM:
        if texto in ["salir", "menu", "menú", "volver"]:
            user_states[numero] = MENU_PRINCIPAL
            enviar_whatsapp(numero, MENU_TEXTO)
            return

        try:
            resultado = om_chat_responder(
                pregunta=mensaje,
                user_id=1
            )

            respuesta = resultado.get(
                "respuesta",
                "No pude procesar la consulta."
            )

            enviar_whatsapp(numero, respuesta)

        except Exception as e:
            print("Error en OM:", e)
            enviar_whatsapp(
                numero,
                "Ocurrió un error consultando el módulo OM. Intente nuevamente."
            )

        return

    # ======================================
    # OPCIONES MENU
    # ======================================

    if texto == "1":
        enviar_whatsapp(
            numero,
            "🔓 Función desbloqueo usuario en construcción."
        )
        return

    if texto == "2":
        enviar_whatsapp(
            numero,
            "🔑 Función reset contraseña en construcción."
        )
        return

    if texto == "3":
        enviar_whatsapp(
            numero,
            "🎫 Estado ticket en construcción."
        )
        return

    if texto == "4":
        enviar_whatsapp(
            numero,
            "👨‍💻 Un agente de soporte lo atenderá."
        )
        return

    if texto == "5":
        user_states[numero] = MODO_OM

        enviar_whatsapp(
            numero,
            """📊 Módulo OM activado.

Ingrese su consulta.

Ejemplos:
- cuantas om hay abiertas
- acciones vencidas
- estado de la om RECL00132

Para volver escriba MENU.
"""
        )

        return

    # ======================================
    # DEFAULT
    # ======================================

    enviar_whatsapp(
        numero,
        "No entendí el mensaje. Escriba MENU para ver las opciones."
    )