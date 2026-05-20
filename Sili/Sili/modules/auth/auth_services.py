from __future__ import annotations

import time
import random
from datetime import datetime, timedelta
from flask import current_app

from ..security import check_password_policy
from .auth_constants import (
    MAX_INTENTOS_LOGIN,
    MAX_INTENTOS_MFA_LOGIN,
    MFA_LOGIN_EXPIRA_MINUTOS,
    EVENTO_INICIO_SESION_EXITOSO,
    EVENTO_INICIO_SESION_FALLIDO,
    EVENTO_CUENTA_BLOQUEADA,
    EVENTO_INTENTO_CUENTA_BLOQUEADA,
    EVENTO_INTENTO_CUENTA_DESHABILITADA,
    EVENTO_CIERRE_SESION,
    EVENTO_SOLICITUD_RECUPERACION_CLAVE,
    EVENTO_CODIGO_RECUPERACION_VALIDO,
    EVENTO_CODIGO_RECUPERACION_INVALIDO,
    EVENTO_CLAVE_ACTUALIZADA_POR_RECUPERACION,
    EVENTO_CLAVE_ACTUALIZADA,
    EVENTO_MFA_LOGIN_ENVIADO,
    EVENTO_MFA_LOGIN_VALIDO,
    EVENTO_MFA_LOGIN_INVALIDO,
    EVENTO_MFA_LOGIN_BLOQUEO,
)

from .auth_security import (
    ahora_str,
    obtener_ip_cliente,
    obtener_agente_usuario,
    esta_hasheado,
    generar_hash_clave,
    verificar_clave,
    es_cuenta_bloqueada_por_seguridad,
    generar_codigo_otp,
    hash_codigo_otp,
    verificar_codigo_otp,
    normalizar_datetime_db,
)

from . import auth_repository as repo
from . import auth_notificaciones as notificaciones


def registrar_evento_seguridad(
    evento: str,
    resultado: str = None,
    detalle: str = None,
    usuario_id: int = None,
    username: str = None,
    actor_usuario_id: int = None,
    ip: str = None,
    user_agent: str = None,
):
    try:
        repo.insertar_auditoria_seguridad(
            usuario_id=usuario_id,
            username=username,
            evento=evento,
            resultado=resultado,
            detalle=detalle,
            ip=ip or obtener_ip_cliente(),
            user_agent=user_agent or obtener_agente_usuario(),
            actor_usuario_id=actor_usuario_id,
            fecha_evento=ahora_str(),
        )
    except Exception as exc:
        current_app.logger.warning("[WARN] No se pudo registrar auditoría de seguridad: %s", exc)


def validar_usuario(usuario: str, password: str):
    """
    Busca por username case-insensitive.
    Usa disabled=1 tanto para cuenta deshabilitada manualmente
    como para cuenta bloqueada por seguridad.
    Migra a hash si detecta texto plano.
    """
    fila = repo.obtener_usuario_por_username(usuario)
    if not fila:
        return None

    if int(fila["disabled"] or 0) == 1:
        if es_cuenta_bloqueada_por_seguridad(fila, MAX_INTENTOS_LOGIN):
            return {
                "bloqueado": True,
                "motivo_bloqueo": fila["motivo_bloqueo"]
            }
        return {"deshabilitado": True}

    clave_guardada = fila["password"]
    if not verificar_clave(clave_guardada, password):
        return None

    if not esta_hasheado(clave_guardada):
        try:
            nuevo_hash = generar_hash_clave(password)
            repo.actualizar_password_hash_por_id(fila["id"], nuevo_hash)
        except Exception as exc:
            current_app.logger.warning("No se pudo migrar password a hash para %s: %s", usuario, exc)

    return {
        "id": fila["id"],
        "username": fila["username"],
        "rol": fila["rol"],
        "departamento_id": fila["departamento_id"],
        "email": fila["email"],
        "disabled": fila["disabled"],
        "failed_attempts": fila["failed_attempts"],
    }


def obtener_estado_autenticacion_usuario(username: str):
    return repo.obtener_estado_autenticacion_usuario(username)


def iniciar_mfa_login(session, user_data: dict, remember: bool) -> dict:
    if not user_data or not user_data.get("id"):
        return {"ok": False, "mensaje": "Usuario inválido.", "tipo": "danger"}

    if not user_data.get("email"):
        return {
            "ok": False,
            "mensaje": "El usuario no tiene correo registrado para verificación.",
            "tipo": "danger"
        }

    codigo = generar_codigo_otp(6)
    codigo_hash = hash_codigo_otp(codigo)
    expira_en = datetime.now() + timedelta(minutes=MFA_LOGIN_EXPIRA_MINUTOS)

    t0 = time.perf_counter()
    token_id = repo.insertar_login_mfa_token(
        user_id=user_data["id"],
        code_hash=codigo_hash,
        expires_at=expira_en,
        attempts_left=MAX_INTENTOS_MFA_LOGIN
    )
    current_app.logger.info("MFA token insert tomó %.3f s", time.perf_counter() - t0)

    session["login_mfa_token_id"] = token_id
    session["login_mfa_user_id"] = user_data["id"]
    session["login_mfa_remember"] = 1 if remember else 0
    session["login_mfa_pending"] = True
    session.pop("login_mfa_verified", None)

    try:
        t1 = time.perf_counter()
        notificaciones.enviar_correo_mfa_login(user_data, codigo)
        current_app.logger.info("MFA email tomó %.3f s", time.perf_counter() - t1)
    except Exception as exc:
        current_app.logger.warning("[WARN] No se pudo enviar correo MFA login: %s", exc)
        return {
            "ok": False,
            "mensaje": "No se pudo enviar el código de verificación. Intente nuevamente.",
            "tipo": "danger"
        }

    registrar_evento_seguridad(
        evento=EVENTO_MFA_LOGIN_ENVIADO,
        resultado="SUCCESS",
        detalle="Código MFA enviado para completar inicio de sesión",
        usuario_id=user_data["id"],
        username=user_data["username"]
    )

    return {
        "ok": True,
        "mensaje": "Se ha enviado un código de verificación a su correo electrónico.",
        "tipo": "info"
    }

def validar_codigo_mfa_login(session, codigo_ingresado: str | None = None) -> dict:
    token_id = session.get('login_mfa_token_id')
    user_id = session.get('login_mfa_user_id')

    if not token_id or not user_id:
        return {
            "ok": False,
            "redirigir": "login",
            "mensaje": "No hay un proceso de verificación de inicio de sesión activo.",
            "tipo": "warning"
        }

    token = repo.obtener_login_mfa_token_por_id(token_id)

    if not token or token['used']:
        session.pop('login_mfa_token_id', None)
        session.pop('login_mfa_user_id', None)
        session.pop('login_mfa_pending', None)
        session.pop('login_mfa_verified', None)
        session.pop('login_mfa_remember', None)
        return {
            "ok": False,
            "redirigir": "login",
            "mensaje": "El código ha expirado o no es válido. Inicie sesión nuevamente.",
            "tipo": "danger"
        }

    expira_dt = normalizar_datetime_db(token['expires_at'])

    if datetime.now() > expira_dt or token['attempts_left'] <= 0:
        repo.marcar_login_mfa_token_usado(token['id'])
        session.pop('login_mfa_token_id', None)
        session.pop('login_mfa_user_id', None)
        session.pop('login_mfa_pending', None)
        session.pop('login_mfa_verified', None)
        session.pop('login_mfa_remember', None)
        return {
            "ok": False,
            "redirigir": "login",
            "mensaje": "El código ha expirado. Inicie sesión nuevamente.",
            "tipo": "danger"
        }

    if codigo_ingresado is None:
        return {"ok": True, "token": token}

    if verificar_codigo_otp(codigo_ingresado, token['code_hash']):
        repo.marcar_login_mfa_token_usado(token['id'])
        session['login_mfa_verified'] = True

        registrar_evento_seguridad(
            evento=EVENTO_MFA_LOGIN_VALIDO,
            resultado="SUCCESS",
            detalle="Código MFA de login validado correctamente",
            usuario_id=user_id
        )

        return {
            "ok": True,
            "verificado": True,
            "mensaje": "Código verificado correctamente.",
            "tipo": "success"
        }

    intentos_restantes = int(token['attempts_left']) - 1
    repo.actualizar_intentos_login_mfa_token(token['id'], intentos_restantes)

    if intentos_restantes <= 0:
        repo.bloquear_usuario_por_intentos_codigo(
            user_id=user_id,
            fecha_bloqueo=ahora_str(),
            motivo_bloqueo="Cuenta deshabilitada por superar intentos del código MFA de login"
        )
        repo.marcar_login_mfa_token_usado(token['id'])

    registrar_evento_seguridad(
        evento=EVENTO_MFA_LOGIN_INVALIDO if intentos_restantes > 0 else EVENTO_MFA_LOGIN_BLOQUEO,
        resultado="FAIL" if intentos_restantes > 0 else "BLOCKED",
        detalle=(
            f"Código MFA incorrecto. Intentos restantes: {intentos_restantes}"
            if intentos_restantes > 0 else
            "Cuenta deshabilitada por superar intentos del código MFA de login"
        ),
        usuario_id=user_id
    )

    if intentos_restantes <= 0:
        session.pop('login_mfa_token_id', None)
        session.pop('login_mfa_user_id', None)
        session.pop('login_mfa_pending', None)
        session.pop('login_mfa_verified', None)
        session.pop('login_mfa_remember', None)
        return {
            "ok": False,
            "redirigir": "login",
            "mensaje": "Ha superado el número máximo de intentos. Su cuenta ha sido bloqueada.",
            "tipo": "danger"
        }

    return {
        "ok": False,
        "redirigir": "verificar_login_codigo",
        "mensaje": f'Código incorrecto. Intentos restantes: {intentos_restantes}',
        "tipo": "danger"
    }


def obtener_usuario_autenticado_por_id(user_id: int):
    fila = repo.obtener_usuario_por_id(user_id)
    if not fila:
        return None

    if int(fila["disabled"] or 0) == 1:
        return None

    return {
        "id": fila["id"],
        "username": fila["username"],
        "rol": fila["rol"],
        "departamento_id": fila["departamento_id"],
        "email": fila["email"],
        "disabled": fila["disabled"],
        "failed_attempts": fila["failed_attempts"],
    }


def registrar_login_fallido_bd(username: str):
    if not username:
        return {"actualizado": False, "bloqueado": False, "intentos_fallidos": 0}

    fila = repo.obtener_usuario_para_login_fallido(username)

    if not fila:
        registrar_evento_seguridad(
            evento=EVENTO_INICIO_SESION_FALLIDO,
            resultado="FAIL",
            detalle="Intento fallido sobre usuario inexistente",
            username=username
        )
        return {"actualizado": False, "bloqueado": False, "intentos_fallidos": 0}

    if int(fila["disabled"] or 0) == 1:
        if es_cuenta_bloqueada_por_seguridad(fila, MAX_INTENTOS_LOGIN):
            registrar_evento_seguridad(
                evento=EVENTO_INTENTO_CUENTA_BLOQUEADA,
                resultado="BLOCKED",
                detalle="Intento sobre cuenta bloqueada por seguridad",
                usuario_id=fila["id"],
                username=fila["username"]
            )
            return {
                "actualizado": False,
                "bloqueado": True,
                "deshabilitado": False,
                "intentos_fallidos": int(fila["failed_attempts"] or 0)
            }

        registrar_evento_seguridad(
            evento=EVENTO_INTENTO_CUENTA_DESHABILITADA,
            resultado="BLOCKED",
            detalle="Intento sobre cuenta deshabilitada manualmente",
            usuario_id=fila["id"],
            username=fila["username"]
        )
        return {
            "actualizado": False,
            "bloqueado": False,
            "deshabilitado": True,
            "intentos_fallidos": int(fila["failed_attempts"] or 0)
        }

    nuevos_intentos = int(fila["failed_attempts"] or 0) + 1
    ahora = ahora_str()
    ip = obtener_ip_cliente()

    bloqueado = nuevos_intentos >= MAX_INTENTOS_LOGIN
    fecha_bloqueo = ahora if bloqueado else None
    motivo_bloqueo = (
        f"Bloqueo automático por {MAX_INTENTOS_LOGIN} intentos fallidos de acceso"
        if bloqueado else None
    )

    repo.actualizar_login_fallido(
        user_id=fila["id"],
        nuevos_intentos=nuevos_intentos,
        fecha_evento=ahora,
        ip=ip,
        bloquear=bloqueado,
        fecha_bloqueo=fecha_bloqueo,
        motivo_bloqueo=motivo_bloqueo,
    )

    registrar_evento_seguridad(
        evento=EVENTO_INICIO_SESION_FALLIDO if not bloqueado else EVENTO_CUENTA_BLOQUEADA,
        resultado="FAIL" if not bloqueado else "BLOCKED",
        detalle=(
            f"Intento fallido #{nuevos_intentos} de {MAX_INTENTOS_LOGIN}"
            if not bloqueado else
            f"Cuenta deshabilitada por seguridad al superar {MAX_INTENTOS_LOGIN} intentos fallidos"
        ),
        usuario_id=fila["id"],
        username=fila["username"],
        ip=ip
    )

    if bloqueado:
        datos_bloqueo = repo.obtener_datos_correo_bloqueo(fila["username"])
        try:
            notificaciones.enviar_correo_cuenta_bloqueada(datos_bloqueo)
        except Exception as exc:
            current_app.logger.warning("[WARN] No se pudo enviar correo de cuenta bloqueada: %s", exc)

    return {
        "actualizado": True,
        "bloqueado": bloqueado,
        "deshabilitado": False,
        "intentos_fallidos": nuevos_intentos
    }


def resetear_intentos_fallidos(user_id: int):
    repo.resetear_intentos_fallidos(user_id)


def registrar_login_exitoso(user_id: int):
    repo.registrar_login_exitoso(
        user_id=user_id,
        fecha=ahora_str(),
        ip=obtener_ip_cliente(),
        ua=obtener_agente_usuario(),
    )


def cargar_permisos_rol(role_name: str) -> dict:
    return repo.obtener_permisos_por_rol(role_name)


def login_should_slowdown(session) -> float:
    now = time.time()
    registro = session.get("_login_throttle") or {"fail_count": 0, "last_fail": 0.0}
    fail_count = int(registro.get("fail_count", 0))
    last_fail = float(registro.get("last_fail", 0))
    if now - last_fail > 300:
        session["_login_throttle"] = {"fail_count": 0, "last_fail": 0.0}
        session.modified = True
        return 0.0
    delay = min(8.0, (2 ** max(0, fail_count - 1)) * 0.5)
    return delay


def login_register_fail(session):
    now = time.time()
    registro = session.get("_login_throttle") or {"fail_count": 0, "last_fail": 0.0}
    registro["fail_count"] = int(registro.get("fail_count", 0)) + 1
    registro["last_fail"] = now
    session["_login_throttle"] = registro
    session.modified = True


def login_reset_throttle(session):
    if "_login_throttle" in session:
        session.pop("_login_throttle", None)
        session.modified = True


def procesar_login_exitoso(session, user_data: dict, remember: bool):
    try:
        resetear_intentos_fallidos(user_data["id"])
        registrar_login_exitoso(user_data["id"])
    except Exception as exc:
        current_app.logger.warning(
            "No se pudo resetear estado de seguridad para %s: %s",
            user_data["username"],
            exc
        )

    session.permanent = remember
    session['usuario'] = user_data['username']
    session['usuario_id'] = user_data['id']
    session['rol'] = user_data['rol']
    session['departamento_id'] = user_data.get('departamento_id')
    session['last_login_at'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    session['ip'] = obtener_ip_cliente()
    session['ua'] = obtener_agente_usuario()

    try:
        session['permissions'] = cargar_permisos_rol(session['rol'])
    except Exception:
        session['permissions'] = {}

    login_reset_throttle(session)
    session.modified = True

    registrar_evento_seguridad(
        evento=EVENTO_INICIO_SESION_EXITOSO,
        resultado="SUCCESS",
        detalle="Inicio de sesión exitoso",
        usuario_id=user_data["id"],
        username=user_data["username"]
    )

    try:
        fila_correo = repo.obtener_email_usuario_por_id(user_data['id'])
        correo_usuario = fila_correo['email'] if fila_correo else None
        notificaciones.enviar_correo_login_exitoso(user_data, correo_usuario)
    except Exception as exc:
        current_app.logger.warning('[WARN] No se pudo enviar correo de login: %s', exc)


def procesar_logout(session):
    try:
        if session.get("usuario_id"):
            registrar_evento_seguridad(
                evento=EVENTO_CIERRE_SESION,
                resultado="SUCCESS",
                detalle="Cierre de sesión manual",
                usuario_id=session.get("usuario_id"),
                username=session.get("usuario")
            )
    except Exception:
        pass


def solicitar_recuperacion(identificador: str, session) -> dict:
    if not identificador:
        return {"ok": False, "mensaje": 'Debe proporcionar su nombre de usuario o correo.', "tipo": "warning"}

    usuario = repo.obtener_usuario_por_username_o_email(identificador)

    if not usuario:
        registrar_evento_seguridad(
            evento=EVENTO_SOLICITUD_RECUPERACION_CLAVE,
            resultado="FAIL",
            detalle="Solicitud de recuperación para usuario/correo no encontrado",
            username=identificador
        )
        return {"ok": False, "mensaje": 'No se encontró una cuenta con ese identificador.', "tipo": "danger"}

    if int(usuario['disabled'] or 0) == 1:
        if es_cuenta_bloqueada_por_seguridad(usuario, MAX_INTENTOS_LOGIN):
            registrar_evento_seguridad(
                evento=EVENTO_SOLICITUD_RECUPERACION_CLAVE,
                resultado="BLOCKED",
                detalle="Solicitud de recuperación sobre cuenta bloqueada por seguridad",
                usuario_id=usuario["id"],
                username=usuario["username"]
            )
            return {"ok": False, "mensaje": 'Su cuenta está bloqueada por seguridad. Contacte con el administrador.', "tipo": "danger"}

        registrar_evento_seguridad(
            evento=EVENTO_SOLICITUD_RECUPERACION_CLAVE,
            resultado="BLOCKED",
            detalle="Solicitud de recuperación sobre cuenta deshabilitada",
            usuario_id=usuario["id"],
            username=usuario["username"]
        )
        return {"ok": False, "mensaje": 'Su cuenta está deshabilitada. Contacte con el administrador.', "tipo": "danger"}

    codigo = f"{random.randint(100000, 999999)}"
    expira_en = (datetime.now() + timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S')

    try:
        token_id = repo.insertar_reset_token(usuario['id'], codigo, expira_en, 3)
    except Exception as exc:
        current_app.logger.error('[ERROR] No se pudo crear token de restablecimiento: %s', exc)
        return {"ok": False, "mensaje": 'No se pudo generar el código de verificación. Intente nuevamente.', "tipo": "danger"}

    session['reset_token_id'] = token_id
    session['reset_user_id'] = usuario['id']
    session.pop('reset_verified', None)

    registrar_evento_seguridad(
        evento=EVENTO_SOLICITUD_RECUPERACION_CLAVE,
        resultado="SUCCESS",
        detalle="Solicitud de recuperación generada",
        usuario_id=usuario["id"],
        username=usuario["username"]
    )

    try:
        notificaciones.enviar_correo_recuperacion(usuario, codigo)
    except Exception as exc:
        current_app.logger.warning('[WARN] No se pudo enviar correo de recuperación: %s', exc)

    return {"ok": True, "mensaje": 'Se ha enviado un código de verificación a su correo electrónico.', "tipo": "info"}


def validar_codigo_recuperacion(session, codigo_ingresado: str | None = None) -> dict:
    token_id = session.get('reset_token_id')
    user_id = session.get('reset_user_id')

    if not token_id or not user_id:
        return {"ok": False, "redirigir": "login", "mensaje": 'No hay una solicitud de restablecimiento activa.', "tipo": "warning"}

    token = repo.obtener_reset_token_por_id(token_id)

    if not token or token['used']:
        session.pop('reset_token_id', None)
        session.pop('reset_user_id', None)
        session.pop('reset_verified', None)
        return {"ok": False, "redirigir": "forgot_password", "mensaje": 'El código de verificación ha expirado o no es válido. Solicite uno nuevo.', "tipo": "danger"}

    expira_dt = normalizar_datetime_db(token['expires_at'])

    if datetime.now() > expira_dt or token['attempts_left'] <= 0:
        repo.marcar_reset_token_usado(token['id'])
        session.pop('reset_token_id', None)
        session.pop('reset_user_id', None)
        session.pop('reset_verified', None)
        return {"ok": False, "redirigir": "forgot_password", "mensaje": 'El código de verificación ha expirado. Solicite uno nuevo.', "tipo": "danger"}

    if codigo_ingresado is None:
        return {"ok": True, "token": token}

    if codigo_ingresado == token['code']:
        repo.marcar_reset_token_usado(token['id'])
        session['reset_verified'] = True

        registrar_evento_seguridad(
            evento=EVENTO_CODIGO_RECUPERACION_VALIDO,
            resultado="SUCCESS",
            detalle="Código de recuperación validado correctamente",
            usuario_id=user_id
        )

        return {"ok": True, "verificado": True, "mensaje": 'Código verificado. Puede definir una nueva contraseña.', "tipo": "success"}

    intentos_restantes = token['attempts_left'] - 1
    repo.actualizar_intentos_reset_token(token['id'], intentos_restantes)

    if intentos_restantes <= 0:
        repo.bloquear_usuario_por_intentos_codigo(
            user_id=user_id,
            fecha_bloqueo=ahora_str(),
            motivo_bloqueo="Cuenta deshabilitada por superar intentos del código de recuperación"
        )
        repo.marcar_reset_token_usado(token['id'])

    registrar_evento_seguridad(
        evento=EVENTO_CODIGO_RECUPERACION_INVALIDO,
        resultado="FAIL" if intentos_restantes > 0 else "BLOCKED",
        detalle=(
            f"Código de recuperación incorrecto. Intentos restantes: {intentos_restantes}"
            if intentos_restantes > 0 else
            "Cuenta deshabilitada por superar intentos del código de recuperación"
        ),
        usuario_id=user_id
    )

    if intentos_restantes <= 0:
        session.pop('reset_token_id', None)
        session.pop('reset_user_id', None)
        session.pop('reset_verified', None)
        return {"ok": False, "redirigir": "login", "mensaje": 'Ha superado el número máximo de intentos. Su cuenta ha sido deshabilitada.', "tipo": "danger"}

    return {"ok": False, "redirigir": "verificar_codigo", "mensaje": f'Código incorrecto. Intentos restantes: {intentos_restantes}', "tipo": "danger"}


def establecer_nueva_clave(session, nueva: str, confirmar: str) -> dict:
    if not session.get('reset_verified') or not session.get('reset_user_id'):
        return {"ok": False, "redirigir": "login", "mensaje": 'No hay un proceso de restablecimiento válido.', "tipo": "warning"}

    user_id = session.get('reset_user_id')

    if not nueva or not confirmar:
        return {"ok": False, "mensaje": 'Debe ingresar la nueva clave dos veces.', "tipo": "danger"}

    if nueva != confirmar:
        return {"ok": False, "mensaje": 'Las claves no coinciden.', "tipo": "danger"}

    ok, msg = check_password_policy(nueva)
    if not ok:
        return {"ok": False, "mensaje": msg, "tipo": "warning"}

    nuevo_hash = generar_hash_clave(nueva)
    repo.actualizar_password_por_recuperacion(user_id, nuevo_hash, ahora_str())

    registrar_evento_seguridad(
        evento=EVENTO_CLAVE_ACTUALIZADA_POR_RECUPERACION,
        resultado="SUCCESS",
        detalle="Contraseña actualizada mediante recuperación",
        usuario_id=user_id
    )

    session.pop('reset_token_id', None)
    session.pop('reset_user_id', None)
    session.pop('reset_verified', None)

    return {"ok": True, "redirigir": "login", "mensaje": 'Contraseña actualizada correctamente. Puede iniciar sesión.', "tipo": "success"}


def cambiar_clave_usuario(user: dict, nueva: str, confirm: str) -> dict:
    if not nueva or not confirm:
        return {"ok": False, "mensaje": 'Debe ingresar la nueva clave dos veces.', "tipo": "danger"}

    if nueva != confirm:
        return {"ok": False, "mensaje": 'Las claves no coinciden.', "tipo": "danger"}

    ok, msg = check_password_policy(nueva)
    if not ok:
        return {"ok": False, "mensaje": msg, "tipo": "warning"}

    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    nuevo_hash = generar_hash_clave(nueva)
    repo.actualizar_password_usuario(user['id'], nuevo_hash, ts)

    registrar_evento_seguridad(
        evento=EVENTO_CLAVE_ACTUALIZADA,
        resultado="SUCCESS",
        detalle="Cambio de clave desde sesión autenticada",
        usuario_id=user["id"],
        username=user.get("username")
    )

    return {"ok": True, "mensaje": 'Clave actualizada correctamente.', "tipo": "success"}