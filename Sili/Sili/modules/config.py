# modules/config.py

import os
from flask import Flask, request
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv


# ==========================================================
# Cargar variables de entorno desde .env
# ==========================================================

load_dotenv()


# ==========================================================
# App constants
# ==========================================================

APP_SECRET = os.environ.get("BITACORA_SECRET")
DB_PATH = os.path.join("database", "bitacora1.db")

ESTADOS = [
    "Por iniciar",
    "En desarrollo",
    "Atrasada",
    "Terminado",
    "Cancelada",
    "Cerrado por sistema",
]

ROLES = ["admin", "jefe", "usuario"]
TABLE_GASTOS = "gastos_tarjeta"

ALLOWED_EXTENSIONS = {
    "pdf",
    "doc",
    "docx",
    "xls",
    "xlsx",
    "png",
    "jpg",
    "jpeg",
    "gif",
}


# ==========================================================
# WhatsApp Cloud API
# ==========================================================

WHATSAPP_VERIFY_TOKEN = os.getenv(
    "WHATSAPP_VERIFY_TOKEN",
    "mi_token_seguro"
)

WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")

GRAPH_API_VERSION = os.getenv(
    "GRAPH_API_VERSION",
    "v21.0"
)


# ==========================================================
# SeedBilling - Carga automática XML compras
# ==========================================================

SEEDBILLING_ENABLED = True

# Horarios de ejecución automática del worker
SEEDBILLING_RUN_HOURS = (8, 14)

# Empresa que sí se inserta en SQL
SEEDBILLING_TARGET_RUC = "0990344760001"  # Quimpac Ecuador S.A.

# Igual que SoapUI
SEEDBILLING_CANTIDAD = int(os.getenv("SEEDBILLING_CANTIDAD", "1000"))

# 10 x 1000 = hasta 10.000 comprobantes por ejecución
SEEDBILLING_MAX_LOOPS = int(os.getenv("SEEDBILLING_MAX_LOOPS", "10"))

SEEDBILLING_LIST_URL = (
    "https://cloud.seedbilling.ec:9064/"
    "servicios-web-recepcion-comprobantes-recibidos-1.0/"
    "ServicioWebComprobantesElectronicos"
)

SEEDBILLING_MARK_URL = (
    "https://cloud.seedbilling.ec:9064/"
    "servicios-web-recepcion-comprobantes-recibidos-1.0/"
    "ServicioWebComprobantesElectronicosMarcarEntregados"
)

SEEDBILLING_SUSCRIPTOR = os.getenv("SEEDBILLING_SUSCRIPTOR", "81")
SEEDBILLING_TIPODOCUMENTO = os.getenv("SEEDBILLING_TIPODOCUMENTO", "01")

# Para prueba local, quedan igual que SoapUI.
# En producción es mejor definirlos por variables de entorno.
SEEDBILLING_USUARIO = os.getenv("SEEDBILLING_USUARIO", "RECEPCION")
SEEDBILLING_CLAVE = os.getenv("SEEDBILLING_CLAVE", "RECEPCION")

SEEDBILLING_TOKEN = os.getenv(
    "SEEDBILLING_TOKEN",
    "Bbe8TdMrmiUl2yKNoPIn00751vmMztxN",
)

SEEDBILLING_TIMEOUT = int(os.getenv("SEEDBILLING_TIMEOUT", "180"))
SEEDBILLING_VERIFY_SSL = True

# True = marca como entregadas las facturas de Quimitransport u otras empresas,
# sin insertarlas en SQL.
SEEDBILLING_MARK_OTHER_COMPANIES = True

# Cantidad de claves por request al servicio de marcado.
SEEDBILLING_MARK_CHUNK_SIZE = int(
    os.getenv("SEEDBILLING_MARK_CHUNK_SIZE", "100")
)

# Mantener False para no imprimir XML/RIDE en logs.
SEEDBILLING_DEBUG_RESPONSE_SNIPPET = False

# Si queda vacío, el job guarda XML en static/uploads/seedbilling_xml
SEEDBILLING_XML_ARCHIVE_FOLDER = os.getenv(
    "SEEDBILLING_XML_ARCHIVE_FOLDER",
    ""
)

# Correos adicionales separados por coma.
# Además el job busca usuarios rol admin con email.
SEEDBILLING_ADMIN_EMAILS = os.getenv("SEEDBILLING_ADMIN_EMAILS", "")


# ==========================================================
# Helpers
# ==========================================================

def _bool_env(name: str, default: bool = False) -> bool:
    val = os.environ.get(name)

    if val is None:
        return default

    return str(val).strip().lower() in ("1", "true", "t", "yes", "y")


def _ensure_secret_key(app: Flask):
    """
    Garantiza que SECRET_KEY sea estable:
    - Si existe BITACORA_SECRET en el entorno, úsala.
    - Si no, intenta leer secret_key.txt.
    - Si no existe, la crea una sola vez y la reutiliza.
    """
    if APP_SECRET:
        app.secret_key = APP_SECRET
        return

    secret_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "secret_key.txt",
        )
    )

    try:
        if os.path.exists(secret_path):
            with open(secret_path, "r", encoding="utf-8") as f:
                key = (f.read() or "").strip()

            if key:
                app.secret_key = key
                return

        key = os.urandom(32).hex()

        os.makedirs(os.path.dirname(secret_path), exist_ok=True)

        with open(secret_path, "w", encoding="utf-8") as f:
            f.write(key)

        app.secret_key = key

    except Exception:
        app.secret_key = os.urandom(32)


def _is_dev_like() -> bool:
    """
    Considera dev si:
    - FLASK_ENV=development
    - FLASK_DEBUG=1
    - ENV=development
    """
    return (
        os.environ.get("FLASK_ENV") == "development"
        or os.environ.get("FLASK_DEBUG") in ("1", "true", "True")
        or os.environ.get("ENV") == "development"
    )


# ==========================================================
# Configuración principal
# ==========================================================

def configure_app(app: Flask):
    """
    Aplica configuración al objeto Flask y asegura rutas/carpetas.
    """
    _ensure_secret_key(app)

    upload_folder = os.path.join(app.static_folder, "uploads")
    os.makedirs(upload_folder, exist_ok=True)
    app.config["UPLOAD_FOLDER"] = upload_folder

    # ¿Confiamos en cabeceras de proxy? Nginx / ALB / Cloudflare.
    if _bool_env("TRUST_PROXY", False):
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=1,
            x_proto=1,
            x_host=1,
            x_port=1,
            x_prefix=1,
        )

    cookie_secure_override = os.environ.get("COOKIE_SECURE")

    if cookie_secure_override is not None:
        session_cookie_secure = _bool_env("COOKIE_SECURE", False)
    else:
        session_cookie_secure = False

    app.config.update(
        APP_SECRET=app.secret_key,
        DB_PATH=DB_PATH,
        ESTADOS=ESTADOS,
        ROLES=ROLES,
        TABLE_GASTOS=TABLE_GASTOS,
        ALLOWED_EXTENSIONS=ALLOWED_EXTENSIONS,

        # ==================================================
        # WhatsApp Cloud API
        # ==================================================
        WHATSAPP_VERIFY_TOKEN=WHATSAPP_VERIFY_TOKEN,
        WHATSAPP_PHONE_NUMBER_ID=WHATSAPP_PHONE_NUMBER_ID,
        WHATSAPP_TOKEN=WHATSAPP_TOKEN,
        GRAPH_API_VERSION=GRAPH_API_VERSION,

        # Cookies de sesión
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=session_cookie_secure,

        # 8 horas de sesión permanente
        PERMANENT_SESSION_LIFETIME=60 * 60 * 8,

        PREFERRED_URL_SCHEME="https" if session_cookie_secure else "http",

        # ==================================================
        # SeedBilling
        # ==================================================
        SEEDBILLING_ENABLED=SEEDBILLING_ENABLED,
        SEEDBILLING_RUN_HOURS=SEEDBILLING_RUN_HOURS,
        SEEDBILLING_TARGET_RUC=SEEDBILLING_TARGET_RUC,
        SEEDBILLING_CANTIDAD=SEEDBILLING_CANTIDAD,
        SEEDBILLING_MAX_LOOPS=SEEDBILLING_MAX_LOOPS,
        SEEDBILLING_LIST_URL=SEEDBILLING_LIST_URL,
        SEEDBILLING_MARK_URL=SEEDBILLING_MARK_URL,
        SEEDBILLING_SUSCRIPTOR=SEEDBILLING_SUSCRIPTOR,
        SEEDBILLING_TIPODOCUMENTO=SEEDBILLING_TIPODOCUMENTO,
        SEEDBILLING_USUARIO=SEEDBILLING_USUARIO,
        SEEDBILLING_CLAVE=SEEDBILLING_CLAVE,
        SEEDBILLING_TOKEN=SEEDBILLING_TOKEN,
        SEEDBILLING_TIMEOUT=SEEDBILLING_TIMEOUT,
        SEEDBILLING_VERIFY_SSL=SEEDBILLING_VERIFY_SSL,
        SEEDBILLING_MARK_OTHER_COMPANIES=SEEDBILLING_MARK_OTHER_COMPANIES,
        SEEDBILLING_MARK_CHUNK_SIZE=SEEDBILLING_MARK_CHUNK_SIZE,
        SEEDBILLING_DEBUG_RESPONSE_SNIPPET=SEEDBILLING_DEBUG_RESPONSE_SNIPPET,
        SEEDBILLING_XML_ARCHIVE_FOLDER=SEEDBILLING_XML_ARCHIVE_FOLDER,
        SEEDBILLING_ADMIN_EMAILS=SEEDBILLING_ADMIN_EMAILS,
    )

    # ------------------------------------------------------
    # Auto-detección por request del esquema HTTP/HTTPS
    # ------------------------------------------------------
    if cookie_secure_override is None:

        @app.before_request
        def _adapt_cookie_secure_by_request():
            """
            Si la petición llega como HTTPS o vía proxy con
            X-Forwarded-Proto=https, activa SESSION_COOKIE_SECURE
            para esta request. Si llega por HTTP en LAN, queda False.
            """
            try:
                xf_proto = (
                    request.headers.get("X-Forwarded-Proto") or ""
                ).split(",")[0].strip().lower()

                via_https = request.is_secure or xf_proto == "https"

                app.config["SESSION_COOKIE_SECURE"] = bool(via_https)
                app.config["PREFERRED_URL_SCHEME"] = (
                    "https" if via_https else "http"
                )

            except Exception:
                app.config["SESSION_COOKIE_SECURE"] = False
                app.config["PREFERRED_URL_SCHEME"] = "http"

    else:
        app.config["PREFERRED_URL_SCHEME"] = (
            "https" if app.config["SESSION_COOKIE_SECURE"] else "http"
        )