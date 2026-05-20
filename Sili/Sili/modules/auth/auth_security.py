from __future__ import annotations
import os
import secrets
import hashlib
from datetime import datetime
from flask import request
from werkzeug.security import generate_password_hash, check_password_hash


def ahora_str() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def obtener_ip_cliente() -> str:
    """
    Obtiene la IP real del cliente considerando reverse proxy.
    Prioridad:
    1) X-Forwarded-For -> primera IP
    2) X-Real-IP
    3) remote_addr
    """
    try:
        x_forwarded_for = request.headers.get("X-Forwarded-For", "")
        if x_forwarded_for:
            ip_real = x_forwarded_for.split(",")[0].strip()
            if ip_real:
                return ip_real

        x_real_ip = request.headers.get("X-Real-IP", "").strip()
        if x_real_ip:
            return x_real_ip

        return (request.remote_addr or "").strip()
    except Exception:
        return ""


def obtener_agente_usuario() -> str:
    return request.headers.get('User-Agent', '') or ''


def parece_hash(valor: str) -> bool:
    if not valor or not isinstance(valor, str):
        return False
    return valor.startswith(("scrypt:", "pbkdf2:", "argon2:", "sha256:", "sha1:", "md5:"))


def esta_hasheado(valor: str) -> bool:
    return parece_hash(valor)


def generar_hash_clave(clave_plana: str) -> str:
    metodo = os.environ.get("HASH_METHOD", "scrypt")
    try:
        return generate_password_hash(clave_plana, method=metodo, salt_length=16)
    except Exception:
        return generate_password_hash(clave_plana)


def verificar_clave(clave_guardada: str, clave_ingresada: str) -> bool:
    if not clave_guardada:
        return False
    try:
        if esta_hasheado(clave_guardada):
            return check_password_hash(clave_guardada, clave_ingresada)
    except Exception:
        pass
    return clave_guardada == clave_ingresada



def generar_codigo_otp(longitud: int = 6) -> str:
    digitos = "0123456789"
    return "".join(secrets.choice(digitos) for _ in range(longitud))


def hash_codigo_otp(codigo: str) -> str:
    return hashlib.sha256(codigo.encode("utf-8")).hexdigest()


def verificar_codigo_otp(codigo_plano: str, codigo_hash: str) -> bool:
    return hash_codigo_otp(codigo_plano) == codigo_hash


def es_cuenta_bloqueada_por_seguridad(fila, max_intentos_login: int) -> bool:
    if not fila:
        return False
    return bool(
        int(fila["disabled"] or 0) == 1 and (
            fila["fecha_bloqueo"] or
            fila["motivo_bloqueo"] or
            int(fila["failed_attempts"] or 0) >= max_intentos_login
        )
    )



def normalizar_datetime_db(valor):
    if isinstance(valor, datetime):
        return valor

    if valor is None:
        return datetime.now()

    try:
        return datetime.strptime(str(valor), '%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError):
        return datetime.now()