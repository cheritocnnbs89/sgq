import string
from datetime import datetime
from flask import app, session, redirect, url_for, flash, request
from functools import wraps

from .db import get_db, get_config_value
from .email_utils import send_email


# ---------------------------
# Helpers de usuario/sesión
# ---------------------------
def current_user():
    if 'usuario' in session:
        return {
            'id': session.get('usuario_id'),
            'username': session.get('usuario'),
            'rol': session.get('rol'),
            'departamento_id': session.get('departamento_id'),
        }
    return {'id': None, 'username': 'anon', 'rol': 'usuario', 'departamento_id': None}


def get_user():
    return current_user()


# ---------------------------
# Permisos (unificados)
# ---------------------------

def _load_permissions_from_roles(role_name: str) -> dict:
    """Carga permisos desde roles_permisos + opciones (nuevo esquema)."""
    if not role_name:
        return {}
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT o.nombre AS opcion,
               COALESCE(rp.ver,0)       AS ver,
               COALESCE(rp.crear,0)     AS crear,
               COALESCE(rp.editar,0)    AS editar,
               COALESCE(rp.eliminar,0)  AS eliminar,
               COALESCE(rp.exportar,0)  AS exportar,
               COALESCE(rp.aprobar,0)   AS aprobar
        FROM roles_permisos rp
        JOIN roles    r ON r.id = rp.rol_id
        JOIN opciones o ON o.id = rp.opcion_id
        WHERE LOWER(r.nombre) = LOWER(?)
    """, (role_name,))
    rows = cur.fetchall()
    conn.close()
    if not rows:
        return {}
    return {
        r["opcion"]: {
            "ver":      bool(r["ver"]),
            "crear":    bool(r["crear"]),
            "editar":   bool(r["editar"]),
            "eliminar": bool(r["eliminar"]),
            "exportar": bool(r["exportar"]),
            "aprobar":  bool(r["aprobar"]),
        } for r in rows
    }


def _load_permissions_from_legacy(role_name: str) -> dict:
    """Fallback al esquema legacy 'permisos'."""
    if not role_name:
        return {}
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT opcion, COALESCE(ver,0) ver, COALESCE(crear,0) crear,
               COALESCE(editar,0) editar, COALESCE(eliminar,0) eliminar,
               COALESCE(exportar,0) exportar, COALESCE(aprobar,0) aprobar
        FROM permisos
        WHERE LOWER(rol) = LOWER(?)
    """, (role_name,))
    rows = cur.fetchall()
    conn.close()
    if not rows:
        return {}
    return {
        r["opcion"]: {
            "ver":      bool(r["ver"]),
            "crear":    bool(r["crear"]),
            "editar":   bool(r["editar"]),
            "eliminar": bool(r["eliminar"]),
            "exportar": bool(r["exportar"]),
            "aprobar":  bool(r["aprobar"]),
        } for r in rows
    }


def _load_permissions(role_name: str) -> dict:
    """Primero intenta roles_permisos; si no hay, usa permisos (legacy)."""
    perms = _load_permissions_from_roles(role_name)
    if perms:
        return perms
    return _load_permissions_from_legacy(role_name)


def get_permissions(role: str | None = None) -> dict:
    """
    Devuelve permisos para la UI.
    Prioridad:
      1) session['permissions'] si está presente (cargados en login)
      2) Cargar desde BD según el rol y guardarlos en sesión
    """
    # 1) Usa lo que ya está en sesión (set en login)
    if isinstance(session.get("permissions"), dict) and session.get("permissions"):
        return session["permissions"]

    # 2) Carga y cachea en sesión
    role_name = role or session.get("rol")
    perms = _load_permissions(role_name) if role_name else {}
    session["permissions"] = perms or {}
    session.modified = True
    return session["permissions"]


def has_permission(role, opcion: str, accion: str) -> bool:
    """
    Verifica un permiso consultando primero la sesión, luego BD (y cachea).
    """
    # 1) Sesión
    perms = get_permissions(role)
    p = perms.get(opcion)
    if p is not None:
        return bool(p.get(accion, False))

    # 2) (Raro) no estaba: recargar todo para ese rol y volver a mirar
    perms = _load_permissions(role or session.get("rol"))
    session["permissions"] = perms or {}
    session.modified = True
    p = session["permissions"].get(opcion)
    return bool(p and p.get(accion, False))


def require_login(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        from flask import session
        if 'usuario' not in session:
            return redirect(url_for('login'))
        return func(*args, **kwargs)
    return wrapper

def require_login2(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if 'usuario' not in session:
            return redirect(url_for('login'))
        return func(*args, **kwargs)
    return wrapper


def require_admin(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if 'usuario' not in session or session.get('rol') != 'admin':
            return redirect(url_for('dashboard'))
        return func(*args, **kwargs)
    return wrapper



def require_permission(opcion, accion):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            from flask import session  # ✅ Importación segura local

            if 'usuario' not in session:
                return redirect(url_for('login'))

            role = session.get('rol')
            if not has_permission(role, opcion, accion):
                flash('No tiene permiso para acceder a esta sección.', 'danger')
                return redirect(url_for('dashboard'))
            return func(*args, **kwargs)
        return wrapper
    return decorator

def require_permission2(opcion, accion):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if 'usuario' not in session:
                return redirect(url_for('login'))
            role = session.get('rol')
            if not has_permission(role, opcion, accion):
                flash('No tiene permiso para acceder a esta sección.', 'danger')
                return redirect(url_for('dashboard'))
            return func(*args, **kwargs)
        return wrapper
    return decorator


def inject_permissions_context(app):
    @app.context_processor
    def _inject():
        """
        Inyecta 'permissions' en todas las plantillas, usando la sesión si existe,
        o cargando desde BD si hace falta.
        """
        if 'usuario' in session:
            return dict(permissions=get_permissions(session.get("rol")))
        return dict(permissions={})


# ---------------------------
# Política de contraseña
# ---------------------------
def check_password_policy(password: str):
    try:
        min_len = int(get_config_value('password_min_length', '8'))
    except ValueError:
        min_len = 8
    try:
        max_len = int(get_config_value('password_max_length', '15'))
    except ValueError:
        max_len = 15

    allow_symbols = get_config_value('password_allow_symbols', '1') == '1'
    allow_numbers = get_config_value('password_allow_numbers', '1') == '1'
    allow_lower   = get_config_value('password_allow_lowercase', '1') == '1'
    allow_upper   = get_config_value('password_allow_uppercase', '1') == '1'

    if len(password) < min_len or len(password) > max_len:
        return False, f'La contraseña debe tener entre {min_len} y {max_len} caracteres.'

    symbols = set('!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~')
    numbers = set('0123456789')
    lowers  = set(string.ascii_lowercase)
    uppers  = set(string.ascii_uppercase)

    if allow_symbols and not any(c in symbols for c in password):
        return False, 'La contraseña debe contener al menos un símbolo.'
    if not allow_symbols and any(c in symbols for c in password):
        return False, 'La contraseña no puede contener símbolos.'

    if allow_numbers and not any(c in numbers for c in password):
        return False, 'La contraseña debe contener al menos un número.'
    if not allow_numbers and any(c in numbers for c in password):
        return False, 'La contraseña no puede contener números.'

    if allow_lower and not any(c in lowers for c in password):
        return False, 'La contraseña debe contener al menos una letra minúscula.'
    if not allow_lower and any(c in lowers for c in password):
        return False, 'La contraseña no puede contener letras minúsculas.'

    if allow_upper and not any(c in uppers for c in password):
        return False, 'La contraseña debe contener al menos una letra mayúscula.'
    if not allow_upper and any(c in uppers for c in password):
        return False, 'La contraseña no puede contener letras mayúsculas.'

    return True, ''


# ---------------------------
# Inicialización de seguridad
# ---------------------------
def init_security(app):
    """Registrar el hook de inactividad y el context_processor."""
    inject_permissions_context(app)

    @app.before_request
    def check_inactivity():
        # Ignorar endpoints que no deben cortar la sesión
        if 'usuario' in session and request.endpoint not in ('login', 'static', 'logout'):
            now_ts = datetime.now().timestamp()
            last = session.get('last_activity')
            try:
                inactivity_minutes_conf = float(get_config_value('inactivity_minutes', '60'))
            except Exception:
                inactivity_minutes_conf = 60
            inactivity_seconds = inactivity_minutes_conf * 60

            if last and now_ts - last > inactivity_seconds:
                # Intento de notificar por email (opcional)
                try:
                    user_name = session.get('usuario')
                    user_role = session.get('rol')
                    user_id   = session.get('usuario_id')
                    conn_mail = get_db()
                    cur_mail  = conn_mail.cursor()
                    cur_mail.execute('SELECT email FROM usuarios WHERE id=?', (user_id,))
                    urow = cur_mail.fetchone()
                    user_email = urow['email'] if urow else None
                    cur_mail.execute("SELECT email FROM usuarios WHERE rol='admin1'")
                    admins = [r['email'] for r in cur_mail.fetchall() if r['email']]
                    recipients = []
                    if user_email: recipients.append(user_email)
                    for ae in admins:
                        if ae not in recipients: recipients.append(ae)
                    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    subject = f'Sesión cerrada por inactividad: {user_name}'
                    im_val = inactivity_minutes_conf
                    if im_val >= 60 and im_val % 60 == 0:
                        horas = int(im_val // 60)
                        tiempo = f"{horas} hora{'s' if horas != 1 else ''}"
                    else:
                        tiempo = f"{im_val} minuto{'s' if float(im_val) != 1.0 else ''}"
                    message = "\n".join([
                        '🔒 Sesión cerrada por inactividad',
                        f'👤 Usuario: {user_name}',
                        f'🧑‍💼 Rol: {user_role}',
                        f'📅 Fecha y hora de cierre: {ts}',
                        f'💤 Motivo: Sin actividad por más de {tiempo}.',
                        '',
                        '— Este correo es automático. Por favor, no responda.',
                    ])
                    if recipients:
                        send_email(recipients, subject, message)
                except Exception:
                    pass

                session.clear()
                flash('Su sesión ha sido cerrada por inactividad.', 'warning')
                return redirect(url_for('login'))

            # Refresca timestamp de actividad
            session['last_activity'] = now_ts

    
    import re
    import logging
    from flask import request

    logger = logging.getLogger(__name__)

    INLINE_SCRIPT_RE = re.compile(
        r"<script"
        r"(?![^>]*\bsrc=)"
        r"(?![^>]*\btype\s*=\s*['\"]application/(json|ld\+json)['\"])"
        r"[^>]*>",
        re.IGNORECASE
    )

    INLINE_STYLE_BLOCK_RE = re.compile(r"<style\b[^>]*>", re.IGNORECASE)
    INLINE_EVENT_RE = re.compile(r"\son\w+\s*=", re.IGNORECASE)
    INLINE_STYLE_ATTR_RE = re.compile(r"\sstyle\s*=", re.IGNORECASE)


    CSP_POLICY = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data:; "
        "font-src 'self' data:; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'self';"
    )


    @app.after_request
    def inspect_and_apply_headers(response):
        response.headers["Content-Security-Policy"] = CSP_POLICY
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        content_type = response.headers.get("Content-Type", "")

        if "text/html" in content_type.lower():
            body = response.get_data(as_text=True)

            issues = []

            if INLINE_SCRIPT_RE.search(body):
                issues.append("inline <script>")

            if INLINE_STYLE_BLOCK_RE.search(body):
                issues.append("inline <style>")

            if INLINE_EVENT_RE.search(body):
                issues.append("inline event handler")

            if INLINE_STYLE_ATTR_RE.search(body):
                issues.append("style attribute inline")

            if issues:
                logger.warning(
                    "CSP debt detected in response: %s | path=%s",
                    ", ".join(issues),
                    request.path
                )

        return response