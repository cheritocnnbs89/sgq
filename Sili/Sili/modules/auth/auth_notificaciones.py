from __future__ import annotations

from ..db import get_config_value
from ..email_utils import send_email, send_email_async
from .auth_constants import CONFIG_CORREOS_ADMIN_SEGURIDAD
from .auth_security import obtener_ip_cliente, obtener_agente_usuario


def obtener_correos_admin_seguridad() -> list[str]:
    correos = []
    for key in CONFIG_CORREOS_ADMIN_SEGURIDAD:
        try:
            valor = get_config_value(key)
        except Exception:
            valor = None

        if valor:
            if isinstance(valor, str):
                correos.extend([x.strip() for x in valor.split(",") if x.strip()])
            break

    vistos = set()
    resultado = []
    for correo in correos:
        correo_l = correo.lower()
        if correo_l not in vistos:
            vistos.add(correo_l)
            resultado.append(correo)
    return resultado


def enviar_correo_cuenta_bloqueada(datos_usuario_bloqueado):
    if not datos_usuario_bloqueado:
        return

    correo_usuario = (datos_usuario_bloqueado["email"] or "").strip()
    correos_admin = obtener_correos_admin_seguridad()

    destinatarios = []
    if correo_usuario:
        destinatarios.append(correo_usuario)

    existentes = {x.lower() for x in destinatarios}
    for correo in correos_admin:
        if correo and correo.lower() not in existentes:
            destinatarios.append(correo)
            existentes.add(correo.lower())

    if not destinatarios:
        return

    ip = obtener_ip_cliente()
    ua = obtener_agente_usuario()
    asunto = f"Cuenta bloqueada por seguridad: {datos_usuario_bloqueado['username']}"
    lineas = [
        "🔒 Cuenta bloqueada por seguridad",
        f"👤 Usuario: {datos_usuario_bloqueado['username']}",
        f"📅 Fecha de bloqueo: {datos_usuario_bloqueado['fecha_bloqueo'] or 'N/D'}",
        f"📝 Motivo: {datos_usuario_bloqueado['motivo_bloqueo'] or 'Intentos fallidos de acceso'}",
        f"🌐 IP del intento: {ip or 'N/D'}",
        f"🖥️ User-Agent: {ua or 'N/D'}",
        "",
        "La cuenta ha sido deshabilitada por seguridad.",
        "Para restablecer el acceso, contacte con el administrador.",
        "",
        "— Este correo es automático. Por favor, no responda.",
    ]
    send_email_async(destinatarios, asunto, "\n".join(lineas))


def enviar_correo_login_exitoso(user_data: dict, correo_usuario: str | None):
    if not correo_usuario:
        return

    from datetime import datetime

    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    asunto = f"Nuevo inicio de sesión: {user_data['username']}"
    lineas = [
        '🔐 Nuevo inicio de sesión',
        f"👤 Usuario: {user_data['username']}",
        f"🧑‍💼 Rol: {user_data['rol']}",
        f"📧 Email: {correo_usuario or 'No registrado'}",
        f"📅 Fecha y hora: {ts}",
        '',
        '— Este correo es automático. Por favor, no responda.',
    ]
    send_email_async([correo_usuario], asunto, "\n".join(lineas))


def enviar_correo_recuperacion(usuario: dict, codigo: str):
    destinatarios = [usuario['email']]
    asunto = 'Código de verificación para restablecer contraseña'
    lineas = [
        '🔐 Recuperación de contraseña',
        f"👤 Usuario: {usuario['username']}",
        f"💬 Código de verificación: {codigo}",
        '⏰ Este código expira en 5 minutos.',
        '',
        '— Este correo es automático. Por favor, no responda.',
    ]
    send_email(destinatarios, asunto, "\n".join(lineas))




def enviar_correo_mfa_login(usuario: dict, codigo: str):
    destinatarios = [usuario['email']]
    asunto = 'Código de verificación para inicio de sesión'
    lineas = [
        '🔐 Verificación de inicio de sesión',
        f"👤 Usuario: {usuario['username']}",
        f"💬 Código de verificación: {codigo}",
        '⏰ Este código expira en 5 minutos.',
        '',
        '— Este correo es automático. Por favor, no responda.',
    ]
    send_email_async(destinatarios, asunto, "\n".join(lineas))
