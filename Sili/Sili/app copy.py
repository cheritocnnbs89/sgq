# app.py 
# -*- coding: utf-8 -*-
import os
import logging
import pandas as pd  # <--- Esta es la línea que falta
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.parse import urlsplit, parse_qsl, urlencode
from werkzeug.exceptions import RequestEntityTooLarge
from flask import Request
from itsdangerous import URLSafeSerializer, BadSignature, BadData
from flask import Flask, session, current_app, render_template, request, abort, Response, redirect, url_for
from jinja2 import ChoiceLoader, FileSystemLoader
import time
from flask_wtf.csrf import CSRFError, CSRFProtect
# =========================
# Imports núcleo
# =========================
#from modules.config import configure_app
from modules.config import configure_app

from modules.db import init_db, get_db, init_app as db_init_app
from modules.security import init_security

# --- Rutas/blueprints tolerantes ---
#try:
from modules.auth.routes_auth import register_auth_routes
#except Exception as e:
#    register_auth_routes = None; _auth_err = e


try:
    from modules import routes_reclamos
except Exception as e:
    routes_reclamos = None; _auth_err = e

import sqlite3
csrf = CSRFProtect()
print("SQLite version:", sqlite3.sqlite_version)

try:
    from modules.routes_users import register_user_routes
except Exception as e:
    register_user_routes = None; _users_err = e
try:
    from modules.routes_tareas import register_task_routes
except Exception as e:
    register_task_routes = None; _tareas_err = e
try:
    #from modules.gastos import register_gastos_routes
    from modules.routes_gastos_tarjeta import register_gastos_routes
except Exception as e:
    register_gastos_routes = None; _gastos_err = e

try:
    from modules.routes_config import register_config_routes,register_seguridad_routes
except Exception as e:
    register_config_routes = None; _config_err = e
try:
    from Sili.modules.respaldo.routes_roles_permisos import register_roles_permisos_routes
except Exception as e:
    register_roles_permisos_routes = None; _roles_err = e
try:
    from modules.routes_parametros_generales import register_parametros_generales_routes
except Exception as e:
    register_parametros_generales_routes = None; _paramgen_err = e
try:
    from modules.routes_terceros import register_terceros_routes
except Exception as e:
    register_terceros_routes = None; _terceros_err = e
try:
    from modules.routes_aliases import register_aliases
except Exception as e:
    register_aliases = None; _aliases_err = e
try:
    from modules.routes_terceros_api import register_terceros_api
except Exception as e:
    register_terceros_api = None; _terceros_api_err = e
try:
    from modules.routes_param_api import register_param_api
except Exception as e:
    register_param_api = None; _param_api_err = e
try:
    from modules.xml_bp import xml_bp
except Exception as e:
    xml_bp = None; _xml_err = e
try:
    from modules.routes_planilla_mensual import planilla_bp
except Exception as e:
    planilla_bp = None; _planilla_err = e
try:
    from modules.routes_notifications import notif_bp
except Exception as e:
    notif_bp = None; _notif_err = e
try: 
    from Sili.modules.respaldo.routes_empresas import empresas_bp
except Exception as e:
    empresas_bp = None; _empresas_err = e

from modules.contratos import contratos_bp
#try:
#    from modules.contratos import contratos_bp
#except Exception as e:
#    contratos_bp = None
#    _contratos_err = e
try:
    from modules.routes_puestos import register_puestos_routes
except Exception as e:
    register_puestos_routes = None; _empresas_err = e



# Menú dinámico (+ stubs si faltan)
try:
    from Sili.modules.routes_menu import (
        menu_bp, ensure_menu_schema, seed_menu_if_empty, fetch_menu_tree, ensure_admin_full_perms
    )
except Exception as e:
    menu_bp = None; _menu_err = e
    def ensure_menu_schema(conn): return None  # type: ignore
    def seed_menu_if_empty(conn): return None  # type: ignore
    def fetch_menu_tree(conn, permissions, active_page=None, is_admin=False): return []  # type: ignore
    def ensure_admin_full_perms(conn): return None  # type: ignore

# en app.py (arriba)
import sqlite3
from flask import g

def _get_conn_safe():
    # Intenta reutilizar g.db; si está cerrada, la reemplaza
    for _ in range(2):
        conn = get_db()
        try:
            conn.execute("SELECT 1")
            return conn
        except sqlite3.ProgrammingError:
            try:
                g.pop('db', None)
            except Exception:
                pass
    # Último intento: una nueva
    return get_db()


# ----------------- Permisos/menu helpers -----------------
def build_permissions(conn, role_name: str) -> dict:
    if not role_name:
        return {}
    cur = conn.cursor()
    # Preferencia por matriz roles_permisos/opciones si existe
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
    if rows:
        return {
            r["opcion"]: {
                "ver": bool(r["ver"]), "crear": bool(r["crear"]),
                "editar": bool(r["editar"]), "eliminar": bool(r["eliminar"]),
                "exportar": bool(r["exportar"]), "aprobar": bool(r["aprobar"]),
            } for r in rows
        }
    # Fallback a tabla 'permisos'
    try:
        cur.execute("""
            SELECT opcion, COALESCE(ver,0) ver, COALESCE(crear,0) crear,
                   COALESCE(editar,0) editar, COALESCE(eliminar,0) eliminar,
                   COALESCE(exportar,0) exportar, COALESCE(aprobar,0) aprobar
            FROM permisos
            WHERE LOWER(rol) = LOWER(?)
        """, (role_name,))
        rows = cur.fetchall()
        return {
            r["opcion"]: {
                "ver": bool(r["ver"]), "crear": bool(r["crear"]),
                "editar": bool(r["editar"]), "eliminar": bool(r["eliminar"]),
                "exportar": bool(r["exportar"]), "aprobar": bool(r["aprobar"]),
            } for r in rows
        }
    except Exception:
        return {}

def sync_permissions_from_menu(conn):
    cur = conn.cursor()
    cur.execute("""
      CREATE TABLE IF NOT EXISTS opciones(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT UNIQUE NOT NULL
      )
    """)
    rows = cur.execute("""
      SELECT DISTINCT TRIM(permission) AS k
      FROM menu_items
      WHERE TRIM(COALESCE(permission,'')) <> ''
    """).fetchall()
    for r in rows:
        k = (r['k'] if isinstance(r, dict) else r[0]).strip()
        if not k: 
            continue
        cur.execute("INSERT OR IGNORE INTO opciones(nombre) VALUES (?)", (k,))

    conn.commit()




 

class MyRequest(Request):
    max_form_parts = 5000  # por ejemplo

# ----------------- App factory -----------------
def create_app():
 


    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config["PUBLIC_BASE_URL"] = "http://127.0.0.1:5000"
    app.request_class = MyRequest

    app.config["CHROME_PATH"] = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
 
  # Limite máximo de request (por seguridad). Por ejemplo 512 MB.
    app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024
    # Límite de memoria para parsear formularios (sube bastante el techo)
    app.config["MAX_FORM_MEMORY_SIZE"] = 64 * 1024 * 1024  # 64 MB

    @app.before_request
    def _perf_start():
        # inicio del cronómetro y contadores de DB (si tienes el hook de DB del paso 2)
        g._t0 = time.perf_counter()
        g.sql_count = 0
        g.sql_time = 0.0

    @app.after_request
    def _perf_end(resp):
        # guarda el status para que teardown lo pueda imprimir
        g.status_code = resp.status_code
        # (opcional) también expón tiempos en headers para verlos en DevTools
        try:
            total_ms = (time.perf_counter() - getattr(g, "_t0", time.perf_counter())) * 1000.0
            resp.headers["Server-Timing"] = (
                f"app;dur={total_ms:.2f}, "
                f"db;dur={getattr(g,'sql_time',0.0):.2f};desc=\"sqlite\", "
                f"queries;desc=\"{getattr(g,'sql_count',0)} sql\""
            )
            resp.headers["X-Process-Time-ms"] = f"{total_ms:.2f}"
        except Exception:
            pass
        return resp

    @app.teardown_request
    def _perf_log(exc):
        # línea de log compacta por request
        try:
            total_ms = (time.perf_counter() - getattr(g, "_t0", time.perf_counter())) * 1000.0
            app.logger.info(
                "PERF %s %s -> %s | %.2f ms | sql=%s (%.2f ms)",
                request.method,
                request.path,
                getattr(g, "status_code", "-"),
                total_ms,
                getattr(g, "sql_count", 0),
                getattr(g, "sql_time", 0.0),
            )
        except Exception:
            pass

    # Plantillas: permitir cargar desde raíz del proyecto también
    app.jinja_loader = ChoiceLoader([app.jinja_loader, FileSystemLoader(str(Path(app.root_path).parent))])

    # Config de la app (secret_key, rutas, etc.)
    configure_app(app)
    csrf.init_app(app)
    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        flash('La sesión del formulario expiró o la solicitud no es válida. Intente nuevamente.', 'warning')
        return redirect(url_for('login')), 400
    # Inicializa gestor de conexión por request (teardown)
    db_init_app(app)

        # Inicializa esquema una sola vez al arrancar
    from flask import g
    with app.app_context():
        init_db()

        # 👇 descarta cualquier conn previa en g antes y después de cada ensure_*
        from flask import g
        from modules.db import get_db
        from modules import gastos_helpers as gh

        # Los dos primeros helpers NO reciben conn (en tu código actual):
        g.pop('db', None); gh.ensure_gastos_schema();         g.pop('db', None)
        g.pop('db', None); gh.ensure_gastos_detalle_schema(); g.pop('db', None)

        # ESTE SÍ requiere conn:
        g.pop('db', None)
        conn = get_db()
        gh.ensure_proveedor_fk(conn)
        conn.commit()
        g.pop('db', None)
        # Tabla de adjuntos (usa otra conn fresca)
        conn = get_db();   
        
        conn.commit()
        g.pop('db', None)


    # Seguridad
    init_security(app)

    # Blueprints / rutas (tolerantes a que falten)
    if planilla_bp: app.register_blueprint(planilla_bp)
    if notif_bp: app.register_blueprint(notif_bp)
    if xml_bp: app.register_blueprint(xml_bp, url_prefix='/xml')
    if menu_bp: app.register_blueprint(menu_bp)
    if empresas_bp: app.register_blueprint(empresas_bp)

    if register_auth_routes:
        try: register_auth_routes(app)
        except Exception as e: app.logger.exception("Fallo register_auth_routes: %s", e)
    if register_user_routes:
        try: register_user_routes(app)
        except Exception as e: app.logger.exception("Fallo register_user_routes: %s", e)
    if register_task_routes:
        try: register_task_routes(app)
        except Exception as e: app.logger.exception("Fallo register_task_routes: %s", e)
    if register_gastos_routes:
        try: register_gastos_routes(app)
        except Exception as e: app.logger.exception("Fallo register_gastos_routes: %s", e)
    if register_config_routes:
        try: register_config_routes(app)
        except Exception as e: app.logger.exception("Fallo register_config_routes: %s", e)
    if register_seguridad_routes:
        try: register_seguridad_routes(app)
        except Exception as e: app.logger.exception("Fallo register_seguridad_routes: %s", e)        
    #routes_reclamos.register_reclamos_routes(app)
    if routes_reclamos:
        try: routes_reclamos.register_reclamos_routes(app)
        except Exception as e:
            app.logger.exception("Fallo register_reclamos_routes: %s", e)
   
    if register_roles_permisos_routes:
        try: register_roles_permisos_routes(app)
        except Exception as e: app.logger.exception("Fallo register_roles_permisos_routes: %s", e)
    if register_parametros_generales_routes:
        try: register_parametros_generales_routes(app)
        except Exception as e: app.logger.exception("Fallo register_parametros_generales_routes: %s", e)
    if register_terceros_routes:
        try: register_terceros_routes(app)
        except Exception as e: app.logger.exception("Fallo register_terceros_routes: %s", e)
    if register_terceros_api:
        try: register_terceros_api(app)
        except Exception as e: app.logger.exception("Fallo register_terceros_api: %s", e)
    if register_param_api:
        try: register_param_api(app)
        except Exception as e: app.logger.exception("Fallo register_param_api: %s", e)
    if register_aliases:
        try: register_aliases(app)
        except Exception as e: app.logger.exception("Fallo register_aliases: %s", e)
    if register_puestos_routes:
        # DEBUG: ver si ya existe endpoint 'puestos' antes de registrar
        if 'puestos' in app.view_functions:
            f = app.view_functions['puestos']
            app.logger.error(
                "YA EXISTE endpoint 'puestos' definido en %s.%s",
                getattr(f, '__module__', '?'),
                getattr(f, '__name__', '?')
            )
        register_puestos_routes(app)
    app.register_blueprint(contratos_bp)
    #if contratos_bp:
    #    try: app.register_blueprint(contratos_bp)
    #    except Exception as e: app.logger.exception("Fallo contratos_bp: %s", e)

    # Inicialización de menú/permisos en arranque
    with app.app_context():
        try:
            conn = get_db()
            ensure_menu_schema(conn)
            seed_menu_if_empty(conn)
            sync_permissions_from_menu(conn)
            ensure_admin_full_perms(conn)
             # NO cerrar conn manualmente; lo cierra el teardown
        except Exception as e:
            app.logger.exception("Init menú/permisos falló: %s", e)

    # Inyección de menú (sin cerrar la conn manualmente)
    @app.context_processor
    def inject_menu():
        role_name = (session.get('rol') or '').strip()
        is_admin  = str(role_name).lower() == 'admin' or bool(session.get('is_admin'))

        try:
            conn = _get_conn_safe()          # ← en vez de get_db() directo
            cur = conn.cursor()
            permissions = build_permissions(conn, role_name)

            session['permissions'] = permissions

            row = cur.execute("SELECT COUNT(*) AS c, COALESCE(MAX(id),0) AS mx FROM menu_items").fetchone()
            c  = (row['c']  if isinstance(row, dict) else row[0])
            mx = (row['mx'] if isinstance(row, dict) else (row[1] if len(row)>1 else 0))
            rev = f"{c}-{mx}"

            if session.get('menu_rev') != rev:
                session['menu_rev'] = rev
                session.pop('permissions', None)

            permissions = session.get('permissions') or build_permissions(conn, role_name)
            session['permissions'] = permissions

            menu_tree = fetch_menu_tree(
                conn, permissions,
                active_page=session.get('active_page'),
                is_admin=is_admin
            )
            return dict(menu_tree=menu_tree)
        except Exception as e:
            current_app.logger.exception("inject_menu error: %s", e)
            return dict(menu_tree=[])





    @app.context_processor
    def inject_perm_helpers():
        def has_perm(opcion: str, accion: str = "ver") -> bool:
            role = (session.get("rol") or "").lower()
            if role == "admin" or bool(session.get("is_admin")):
                return True
            perms = session.get("permissions") or {}
            p = perms.get(opcion) or next((v for k,v in perms.items() if k.lower()==opcion.lower()), {})
            return bool(p.get(accion))
        return dict(has_permission=has_perm, has_perm=has_perm)

    # Scheduler (tolerante)
    try:
        from modules.scheduler_jobs import start_scheduler
        if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
            try:
                start_scheduler(app)
            except TypeError:
                start_scheduler()
    except Exception as e:
        app.logger.warning("Scheduler no iniciado (opcional): %s", e)


    # Ruta HOME de cortesía
    if "/" not in app.view_functions:
        @app.route("/")
        def _home():
            for cand in ("login", "auth.login", "dashboard"):
                if cand in app.view_functions:
                    return redirect(url_for(cand))
            return (render_template("errors/404.html") if _template_exists("errors/404.html")
                    else ("No hay ruta de inicio definida. Crea 'login' o 'dashboard'.", 404))

    # Gateway
    _register_gateway(app)
    _force_gateway_redirect(app)

    # Logging consola + archivo
    app.logger.setLevel(logging.DEBUG)
    for h in app.logger.handlers: h.setLevel(logging.DEBUG)
    try:
        with app.app_context():
            rules = sorted([f"{r.endpoint} -> {r.rule}" for r in app.url_map.iter_rules()])
            for line in rules: app.logger.info("RUTA: %s", line)
    except Exception:
        pass



    from werkzeug.exceptions import RequestEntityTooLarge
    from flask import flash, redirect, url_for

    @app.errorhandler(RequestEntityTooLarge)
    def handle_413(e):
        flash("La carga de archivos XML excede el límite permitido. "
            "Por favor súbelos en varios grupos más pequeños.", "warning")
        return redirect(url_for("facturas_xml_list"))


    return app


def _template_exists(path_rel: str) -> bool:
    try:
        current_app.jinja_env.get_or_select_template(path_rel)
        return True
    except Exception:
        return False

def _build_method_map(app: Flask):
    methods = {}
    for rule in app.url_map.iter_rules():
        methods[rule.endpoint] = set(rule.methods or [])
    return methods

def _register_gateway(app: Flask):
    serializer = URLSafeSerializer(app.secret_key, salt="gw.v1")
    method_map = _build_method_map(app)
    from flask import url_for as _real_url_for

    # ⬇️ Monkey-patch: url_for que devuelve /g/<token> para endpoints GET
    def _short_url_for(endpoint: str, **values):
        if endpoint == 'static':
            return _real_url_for(endpoint, **values)

        m = method_map.get(endpoint, set()) or set()

        # solo enmascarar si el endpoint es de lectura pura
        allowed = set(m) - {'HEAD', 'OPTIONS'}
        if allowed != {'GET'}:
            return _real_url_for(endpoint, **values)

        original = _real_url_for(endpoint, **values)

        if original.startswith('/g/') or original.startswith('http://') or original.startswith('https://'):
            return original

        token = serializer.dumps({'p': original})
        return _real_url_for('gateway_disp', token=token)


    # 👉 activa el override
    app.jinja_env.globals['url_for'] = _short_url_for

    @app.route('/g/<token>', methods=['GET'], endpoint='gateway_disp')
    def gateway_disp(token: str):
        try:
            data = serializer.loads(token)
            raw_path = data.get('p', '/')
            if not isinstance(raw_path, str) or not raw_path.startswith('/'):
                abort(400)
        except (BadSignature, BadData):
            abort(404)
        except Exception:
            abort(400)

        try:
            parts = urlsplit(raw_path)
            token_qs_pairs = parse_qsl(parts.query, keep_blank_values=True)
            req_qs_pairs = parse_qsl((request.query_string or b'').decode('utf-8', 'ignore'), keep_blank_values=True)
            merged = dict(token_qs_pairs)
            for k, v in req_qs_pairs:
                merged.setdefault(k, v)
            forward_qs_str = urlencode(merged, doseq=True)

            if request.headers.get('X-From-Gateway') == '1':
                return current_app.response_class('Loop detectado', status=400)

            fwd_headers = {k: v for k, v in request.headers.items() if k.lower() != 'host'}
            fwd_headers['X-From-Gateway'] = '1'

            has_body = request.method in ('POST', 'PUT', 'PATCH')
            body = request.get_data() if has_body else None

            with current_app.test_request_context(
                path=parts.path,
                method=request.method,
                query_string=forward_qs_str,
                data=body,
                headers=fwd_headers,
                content_type=request.content_type,
                environ_overrides={'REMOTE_ADDR': request.remote_addr or '127.0.0.1'},
            ):
                resp = current_app.full_dispatch_request()
                return resp if isinstance(resp, Response) else resp

        except Exception:
            current_app.logger.exception("Gateway fallo para path=%s", raw_path)
            abort(500)

def _force_gateway_redirect(app: Flask):
    serializer = URLSafeSerializer(app.secret_key, salt="gw.v1")

    @app.before_request
    def _gw_auto_redirect():
        if request.method != 'GET':
            return
        if request.path.startswith('/g/'):
            return
        if request.endpoint in ('static',) or request.path == '/favicon.ico':
            return
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return
        if request.headers.get('X-From-Gateway') == '1':
            return

        try:
            allowed = None
            for rule in current_app.url_map.iter_rules():
                if rule.endpoint == (request.endpoint or ''):
                    allowed = set(rule.methods or set()) - {'HEAD', 'OPTIONS'}
                    break

            # Solo redirigir rutas de lectura pura
            if allowed != {'GET'}:
                return
        except Exception:
            return

        full = request.path
        if request.query_string:
            full = f"{request.path}?{request.query_string.decode('utf-8', 'ignore')}"
        if full.startswith('/g/'):
            return

        token = serializer.dumps({'p': full})
        return redirect(url_for('gateway_disp', token=token), code=302)
# =========================
# Crear app / WSGI
# =========================
app = create_app()

# Alias build_only (compat)
app.add_url_rule('/reembolsos/gastos/nuevo', endpoint='nuevo_gasto', build_only=True)
app.add_url_rule('/reembolsos/gastos/<int:gasto_id>/editar', endpoint='editar_gasto', build_only=True)
app.config.setdefault(
    "XML_BULK_FOLDER",
    r"C:\Sili\uploads\xml_masivos_pendientes"
)
app.config.setdefault(
    "XML_BULK_PROCESADOS",
    r"C:\Sili\uploads\xml_masivos_procesados"
)

# =========================
# Logging a archivo (opcional)
# =========================
try:
    log_dir = os.path.abspath(os.environ.get("LOG_DIR", "logs"))
    os.makedirs(log_dir, exist_ok=True)
    fh = RotatingFileHandler(os.path.join(log_dir, "app.log"), maxBytes=5*1024*1024, backupCount=5, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
    if not any(isinstance(h, RotatingFileHandler) for h in app.logger.handlers):
        app.logger.addHandler(fh)
except Exception:
    pass


@app.route("/bi")
def bi():
    # BI.html debe estar en C:\Users\jchav\Pictures\Sili\Sili\templates\BI.html
    return render_template("BI.html")
# =========================
# Entry point
# =========================
if __name__ == '__main__':
    with app.app_context():
        print("\n== Rutas registradas ==")
        for r in app.url_map.iter_rules():
            print(r.endpoint, '->', r.rule, '  methods=', r.methods)
    # Recomendación dev: sin hilos para SQLite
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False, threaded=True)
