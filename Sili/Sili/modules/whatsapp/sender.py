# modules/whatsapp/sender.py

import requests

from modules.config import (
    WHATSAPP_TOKEN,
    WHATSAPP_PHONE_NUMBER_ID,
    GRAPH_API_VERSION
)


def enviar_whatsapp(numero, mensaje):
    """
    Envía un mensaje de texto por WhatsApp Cloud API.
    """

    if not WHATSAPP_TOKEN:
        print("ERROR: Falta WHATSAPP_TOKEN")
        return False

    if not WHATSAPP_PHONE_NUMBER_ID:
        print("ERROR: Falta WHATSAPP_PHONE_NUMBER_ID")
        return False

    url = (
        f"https://graph.facebook.com/"
        f"{GRAPH_API_VERSION}/"
        f"{WHATSAPP_PHONE_NUMBER_ID}/messages"
    )

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": mensaje
        }
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=15
        )

        if response.status_code not in [200, 201]:
            print("Error enviando WhatsApp:")
            print("Status:", response.status_code)
            print("Respuesta:", response.text)
            return False

        print("Mensaje enviado correctamente")
        return True

    except Exception as e:
        print("Excepción enviando WhatsApp:", e)
        return False