from flask import render_template, request, redirect, url_for, flash, session, current_app
from datetime import datetime, timedelta
import os
import time
import random
from ..db import get_db, get_config_value
from werkzeug.security import generate_password_hash, check_password_hash

from ..security import require_login, require_permission, get_user, check_password_policy
from ..email_utils import send_email, send_email_async

from ..security import require_login, require_permission, get_user
from . import auth_services as servicio_auth

from .auth_constants import (
    TABLA_AUDITORIA_SEGURIDAD

)
# =========================
# Helpers IP / Auditoría
# =========================
def _get_client_ip() -> str:
    """
    Obtiene IP real del cliente.
    Soporta proxies si en el futuro usas X-Forwarded-For.
    """
    xff = (request.headers.get("X-Forwarded-For") or "").strip()
    if xff:
        # toma la primera IP real del chain
        return xff.split(",")[0].strip()

    xri = (request.headers.get("X-Real-IP") or "").strip()
    if xri:
        return xri

    return (request.remote_addr or "").strip() or "0.0.0.0"

def _count_ip_events(ip: str, window_sql: str) -> int:
    """
    Cuenta eventos de seguridad recientes para una IP dentro de una ventana.
    Solo considera eventos relevantes para login abusivo.
    """
    conn = get_db()
    cur = conn.cursor()

    mapa = {
        "-5 minutes": timedelta(minutes=5),
        "-15 minutes": timedelta(minutes=15),
        "-1 hour": timedelta(hours=1),
        "-24 hours": timedelta(hours=24),
    }

    delta = mapa.get(window_sql, timedelta(minutes=5))
    cutoff = datetime.now() - delta

    cur.execute("""
        SELECT COUNT(*) AS total
        FROM auditoria_seguridad
        WHERE COALESCE(ip, '') = ?
          AND evento IN (
              'LOGIN_FALLIDO',
              'INTENTO_CUENTA_BLOQUEADA',
              'INTENTO_CUENTA_DESHABILITADA'
          )
          AND fecha_evento >= ?
    """, (ip, cutoff))

    row = cur.fetchone()
    if not row:
        return 0

    try:
        return int(row["total"] or 0)
    except Exception:
        return int(row[0] or 0)

def _get_ip_penalty_seconds(ip: str) -> float:
    """
    Castigo progresivo por IP:
      - >=10 intentos en 5 min   -> 1 s
      - >=20 intentos en 15 min  -> 4 s
      - >=30 intentos en 1 hora  -> 8 s
    """
    c5m = _count_ip_events(ip, "-5 minutes")
    if c5m >= 10:
        return 1.0

    c15m = _count_ip_events(ip, "-15 minutes")
    if c15m >= 20:
        return 4.0

    c1h = _count_ip_events(ip, "-1 hour")
    if c1h >= 30:
        return 8.0

    return 0.0


def _is_ip_blocked_24h(ip: str) -> bool:
    """
    Nivel 4: si la IP tiene >= 40 intentos en las últimas 24h,
    se trata como comportamiento abusivo/probable bot.
    """
    c24h = _count_ip_events(ip, "-24 hours")
    return c24h >= 40


def _landing_after_login() -> str:
    """
    Devuelve la URL de destino después de hacer login.
    Prioridad: Dashboard de Reclamos → Dashboard de Tareas.
    Si el usuario no tiene el permiso 'reclamos.ver' se cae al de tareas.
    """
    try:
        from modules.security import has_permission
        rol = session.get("rol", "")
        if has_permission(rol, "reclamos", "ver"):
            return url_for("reclamos_dashboard")
    except Exception:
        pass
    return url_for("dashboard")


def register_auth_routes(app):
    @app.route('/', methods=['GET', 'POST'])
    def login():
        if request.method == 'GET':
            if session.get('usuario_id'):
                return redirect(_landing_after_login())

            delay_sesion = servicio_auth.login_should_slowdown(session)
            if delay_sesion > 0:
                current_app.logger.info("Backoff login por sesión activo: sugerido %.1fs", delay_sesion)

            ip = _get_client_ip()
            delay_ip = _get_ip_penalty_seconds(ip)
            if delay_ip > 0:
                current_app.logger.info("Backoff login por IP activo [%s]: sugerido %.1fs", ip, delay_ip)

            if _is_ip_blocked_24h(ip):
                current_app.logger.warning("IP temporalmente bloqueada por abuso [%s]", ip)

            return render_template('login.html')

        # ==========================================
        # 1) Penalización por sesión + penalización por IP
        # ==========================================
        ip = _get_client_ip()

        delay_sesion = servicio_auth.login_should_slowdown(session)
        delay_ip = _get_ip_penalty_seconds(ip)

        delay_total = max(delay_sesion, delay_ip)

        if delay_total > 0:
            current_app.logger.warning(
                "LOGIN DELAY aplicado | ip=%s | sesión=%.2fs | ip=%.2fs | total=%.2fs",
                ip, delay_sesion, delay_ip, delay_total
            )
            time.sleep(delay_total)

        # ==========================================
        # 2) Bloqueo fuerte por IP (24h / 40 intentos)
        # ==========================================
        if _is_ip_blocked_24h(ip):
            current_app.logger.warning("Acceso rechazado por IP bloqueada temporalmente [%s]", ip)
            return render_template(
                'login.html',
                error='Se detectaron demasiados intentos desde su red. Intente nuevamente más tarde.'
            )

        # ==========================================
        # 3) Limpiar solo datos de autenticación
        #    (sin tocar _login_throttle)
        # ==========================================
        session.pop('usuario', None)
        session.pop('usuario_id', None)
        session.pop('rol', None)
        session.pop('departamento_id', None)
        session.pop('permissions', None)
        session.pop('last_login_at', None)
        session.pop('ip', None)
        session.pop('ua', None)

        username = (request.form.get('username', '') or '').strip()
        password = (request.form.get('password', '') or '').strip()

        # ==========================================
        # 4) Validación centralizada
        # ==========================================
        user_data = servicio_auth.validar_usuario(username, password)

        # Cuenta deshabilitada manualmente
        if user_data and user_data.get("deshabilitado"):
            servicio_auth.login_register_fail(session)
            servicio_auth.registrar_evento_seguridad(
                evento="INTENTO_CUENTA_DESHABILITADA",
                resultado="BLOCKED",
                detalle="Intento sobre cuenta deshabilitada",
                username=username
            )
            return render_template(
                'login.html',
                error='La cuenta está deshabilitada. Contacte con el administrador.'
            )

        # Cuenta bloqueada por seguridad
        if user_data and user_data.get("bloqueado"):
            servicio_auth.login_register_fail(session)
            servicio_auth.registrar_evento_seguridad(
                evento="INTENTO_CUENTA_BLOQUEADA",
                resultado="BLOCKED",
                detalle="Intento sobre cuenta bloqueada por seguridad",
                username=username
            )
            return render_template(
                'login.html',
                error='La cuenta está bloqueada por seguridad. Contacte con el administrador.'
            )

        # Login correcto -> iniciar MFA
        if user_data and user_data.get("id"):
            resultado_mfa = servicio_auth.iniciar_mfa_login(
                session=session,
                user_data=user_data,
                remember=('remember' in request.form)
            )

            if resultado_mfa["ok"]:
                flash(resultado_mfa["mensaje"], resultado_mfa["tipo"])
                return redirect(url_for('verificar_login_codigo'))

            return render_template('login.html', error=resultado_mfa["mensaje"])

        # ==========================================
        # 5) Login inválido
        #    - castigo de sesión
        #    - registro en BD solo si corresponde
        # ==========================================
        servicio_auth.login_register_fail(session)
        resultado_fallo = servicio_auth.registrar_login_fallido_bd(username)

        if resultado_fallo.get("deshabilitado"):
            return render_template(
                'login.html',
                error='La cuenta está deshabilitada. Contacte con el administrador.'
            )

        if resultado_fallo.get("bloqueado"):
            return render_template(
                'login.html',
                error='La cuenta ha sido bloqueada por superar el máximo de intentos fallidos. Revise su correo o contacte con el administrador.'
            )

        estado = servicio_auth.obtener_estado_autenticacion_usuario(username)
        if estado:
            restantes = max(
                0,
                servicio_auth.MAX_INTENTOS_LOGIN - int(estado["failed_attempts"] or 0)
            )
            return render_template(
                'login.html',
                error=f'Usuario o contraseña inválidos. Intentos restantes: {restantes}'
            )

        return render_template('login.html', error='Usuario o contraseña inválidos.')

    @app.route('/logout', methods=['POST'])
    def logout():
        servicio_auth.procesar_logout(session)

        session.clear()
        resp = redirect(url_for('login'))
        cookie_name = app.config.get("SESSION_COOKIE_NAME", "session")
        resp.delete_cookie(
            key=cookie_name,
            path=app.config.get("SESSION_COOKIE_PATH", "/"),
            domain=app.config.get("SESSION_COOKIE_DOMAIN"),
            samesite=app.config.get("SESSION_COOKIE_SAMESITE", "Lax"),
            secure=app.config.get("SESSION_COOKIE_SECURE", False),
            httponly=app.config.get("SESSION_COOKIE_HTTPONLY", True),
        )
        return resp

    @app.after_request
    def add_no_cache_headers(resp):
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp

    @app.route('/forgot_password', methods=['GET', 'POST'])
    def forgot_password():
        if request.method == 'POST':
            identificador = request.form.get('identifier', '').strip()
            resultado = servicio_auth.solicitar_recuperacion(identificador, session)

            if resultado["ok"]:
                flash(resultado["mensaje"], resultado["tipo"])
                return redirect(url_for('verificar_codigo'))

            flash(resultado["mensaje"], resultado["tipo"])
            return render_template('forgot_password.html')

        return render_template('forgot_password.html')

    @app.route('/verificar_codigo', methods=['GET', 'POST'])
    def verificar_codigo():
        if request.method == 'GET':
            resultado = servicio_auth.validar_codigo_recuperacion(session, None)
            if not resultado["ok"]:
                flash(resultado["mensaje"], resultado["tipo"])
                return redirect(url_for(resultado["redirigir"]))

            token = resultado["token"]
            intentos_restantes = token['attempts_left']
            return render_template('verificar_codigo.html', attempts_left=intentos_restantes)

        codigo_ingresado = request.form.get('code', '').strip()
        resultado = servicio_auth.validar_codigo_recuperacion(session, codigo_ingresado)

        if resultado.get("ok") and resultado.get("verificado"):
            flash(resultado["mensaje"], resultado["tipo"])
            return redirect(url_for('establecer_clave'))

        if not resultado["ok"] and resultado.get("redirigir"):
            flash(resultado["mensaje"], resultado["tipo"])
            return redirect(url_for(resultado["redirigir"]))

        flash(resultado["mensaje"], resultado["tipo"])
        return redirect(url_for('verificar_codigo'))

    @app.route('/establecer_clave', methods=['GET', 'POST'])
    def establecer_clave():
        if request.method == 'GET':
            if not session.get('reset_verified') or not session.get('reset_user_id'):
                flash('No hay un proceso de restablecimiento válido.', 'warning')
                return redirect(url_for('login'))
            return render_template('establecer_clave.html')

        nueva = request.form.get('password', '').strip()
        confirmar = request.form.get('confirm', '').strip()

        resultado = servicio_auth.establecer_nueva_clave(session, nueva, confirmar)

        if resultado["ok"]:
            flash(resultado["mensaje"], resultado["tipo"])
            return redirect(url_for(resultado["redirigir"]))

        if resultado.get("redirigir"):
            flash(resultado["mensaje"], resultado["tipo"])
            return redirect(url_for(resultado["redirigir"]))

        flash(resultado["mensaje"], resultado["tipo"])
        return render_template('establecer_clave.html')

    @app.route('/cambiar_clave', methods=['GET', 'POST'])
    @require_login
    @require_permission('cambio_clave', 'ver')
    def cambiar_clave():
        user = get_user()

        if request.method == 'POST':
            from ..security import has_permission
            if not has_permission(user['rol'], 'cambio_clave', 'editar'):
                flash('No tiene permiso para cambiar la clave.', 'danger')
                return redirect(_landing_after_login())

            nueva = request.form.get('password', '').strip()
            confirm = request.form.get('confirm', '').strip()

            resultado = servicio_auth.cambiar_clave_usuario(user, nueva, confirm)

            flash(resultado["mensaje"], resultado["tipo"])
            if resultado["ok"]:
                return redirect(_landing_after_login())

        return render_template('cambiar_clave.html')
    



    



    @app.route('/verificar_login_codigo', methods=['GET', 'POST'])
    def verificar_login_codigo():
        if request.method == 'GET':
            resultado = servicio_auth.validar_codigo_mfa_login(session, None)
            if not resultado["ok"]:
                flash(resultado["mensaje"], resultado["tipo"])
                return redirect(url_for(resultado["redirigir"]))

            token = resultado["token"]
            intentos_restantes = token['attempts_left']
            return render_template('verificar_login_codigo.html', attempts_left=intentos_restantes)

        codigo_ingresado = request.form.get('code', '').strip()
        resultado = servicio_auth.validar_codigo_mfa_login(session, codigo_ingresado)

        if resultado.get("ok") and resultado.get("verificado"):
            user_id = session.get('login_mfa_user_id')
            remember = bool(session.get('login_mfa_remember'))

            user_data = servicio_auth.obtener_usuario_autenticado_por_id(user_id)
            if not user_data:
                session.pop('login_mfa_token_id', None)
                session.pop('login_mfa_user_id', None)
                session.pop('login_mfa_pending', None)
                session.pop('login_mfa_verified', None)
                session.pop('login_mfa_remember', None)
                flash('No se pudo completar el inicio de sesión.', 'danger')
                return redirect(url_for('login'))

            servicio_auth.procesar_login_exitoso(
                session=session,
                user_data=user_data,
                remember=remember
            )

            session.pop('login_mfa_token_id', None)
            session.pop('login_mfa_user_id', None)
            session.pop('login_mfa_pending', None)
            session.pop('login_mfa_verified', None)
            session.pop('login_mfa_remember', None)

            return redirect(_landing_after_login())

        flash(resultado["mensaje"], resultado["tipo"])
        return redirect(url_for(resultado["redirigir"]))