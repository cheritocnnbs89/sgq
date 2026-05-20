# modules/db.py
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Dict

from flask import g, current_app
from .config import DB_PATH  # Ruta absoluta/relativa a tu .db

# =========================
# Conexión y configuración
# =========================

def _configure_conn(conn: sqlite3.Connection) -> sqlite3.Connection:
    """
    Aplica PRAGMAs y configuración recomendada para evitar 'database is locked'
    bajo carga moderada con SQLite.
    """
    conn.row_factory = sqlite3.Row
    # PRAGMAs críticos para concurrencia:
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=10000;")  # 10s de espera ante locks
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    # Puedes considerar:
    # conn.execute("PRAGMA temp_store=MEMORY;")
    return conn

def _connect(db_path: str) -> sqlite3.Connection:
    """
    Crea una conexión cruda con timeouts y tipos detectados.
    """
    return sqlite3.connect(
        db_path,
        timeout=30,                     # tiempo máx. de espera a nivel de driver
        check_same_thread=False,        # permite uso en apps con hilos
        detect_types=sqlite3.PARSE_DECLTYPES
    )

# modules/db.py
def get_db() -> sqlite3.Connection:
    """
    Devuelve una conexión por request (cacheada en g).
    Si la que hay en g está cerrada o inválida, crea una nueva.
    """
    db = g.get('db')
    if db is not None:
        try:
            # Si la conn está cerrada/rota, esto lanzará excepción
            db.execute("SELECT 1")
            return db
        except Exception:
            # limpiar handle roto/cerrado
            try:
                db.close()
            except Exception:
                pass
            g.pop('db', None)

    # Crear una nueva conexión fresca
    conn = _connect(DB_PATH)
    g.db = _configure_conn(conn)
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        try:
            db.close()
        except Exception:
            pass

def init_app(app):
    """
    Registra el cierre automático de la conexión por request.
    Llama a init_db() por separado al inicio de la app si lo deseas.
    """
    app.teardown_appcontext(close_db)

# ==========================================
# Helpers de configuración en tabla 'config'
# ==========================================

def get_config_value(clave: str, default=None):
    """
    Lee una clave desde 'configuracion'. Usa la conexión del request.
    Si se llama fuera de un request, crea una conexión temporal.
    """
    try:
        try:
            conn = get_db()
            cur = conn.cursor()
        except RuntimeError:
            # Sin contexto de app/request: usa una conexión temporal segura
            conn = _configure_conn(_connect(DB_PATH))
            cur = conn.cursor()
            _temp = True
        else:
            _temp = False

        cur.execute("SELECT valor FROM configuracion WHERE clave=?", (clave,))
        row = cur.fetchone()
        return row['valor'] if row else default
    except Exception:
        return default
    finally:
        if 'conn' in locals() and _temp:
            try:
                conn.close()
            except Exception:
                pass

def set_config_values(data: Dict[str, str]):
    """
    Inserta/actualiza múltiples claves en 'configuracion'.
    """
    # Usa la conexión del request si existe; si no, temporal
    try:
        try:
            conn = get_db()
            cur = conn.cursor()
        except RuntimeError:
            conn = _configure_conn(_connect(DB_PATH))
            cur = conn.cursor()
            _temp = True
        else:
            _temp = False

        for clave, valor in data.items():
            cur.execute(
                """INSERT INTO configuracion (clave, valor) VALUES (?, ?)
                   ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor""",
                (clave, valor),
            )
        conn.commit()
    finally:
        if 'conn' in locals() and _temp:
            try:
                conn.close()
            except Exception:
                pass

# =========================
# Plantillas de notificación
# =========================
TPL_TYPES = [
    ("hoy", "Recordatorio del día"),
    ("vencida", "Tarea vencida"),
    ("resumen_semanal", "Resumen semanal"),
    ("resumen_mensual", "Resumen mensual"),
]

# =========================
# Inicialización de esquema
# =========================

def init_db():
    """
    Crea/actualiza tablas base. Se usa una conexión dedicada (no la de g)
    para poder invocarla al arrancar la app, incluso sin request activo.
    """
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = _configure_conn(_connect(DB_PATH))
    cur = conn.cursor()

    # --- Departamentos ---
    cur.execute('''
        CREATE TABLE IF NOT EXISTS departamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE
        )
    ''')

    # --- Menú (schema de navegación) ---
    cur.execute('''
        CREATE TABLE IF NOT EXISTS menu_items (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id    INTEGER,
            label        TEXT NOT NULL,
            endpoint     TEXT,
            external_url TEXT,
            icon         TEXT,
            order_no     INTEGER NOT NULL DEFAULT 0,
            permission   TEXT,
            active_key   TEXT,
            is_group     INTEGER NOT NULL DEFAULT 0,
            is_collaps   INTEGER NOT NULL DEFAULT 0,
            UNIQUE(label, parent_id),
            FOREIGN KEY(parent_id) REFERENCES menu_items(id) ON DELETE CASCADE
        )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_menu_parent ON menu_items(parent_id, order_no)')

    # --- Usuarios ---
    cur.execute(
        '''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            rol TEXT NOT NULL CHECK(rol IN ('admin','jefe','usuario')),
            departamento_id INTEGER,
            disabled INTEGER NOT NULL DEFAULT 0,
            failed_attempts INTEGER NOT NULL DEFAULT 0,
            fecha_ultimo_acceso TEXT,
            ip_ultimo_acceso TEXT,
            ua_ultimo_acceso TEXT,
            fecha_ultimo_intento_fallido TEXT,
            ip_ultimo_intento_fallido TEXT,
            bloqueado_hasta TEXT,
            fecha_bloqueo TEXT,
            motivo_bloqueo TEXT,
            password_changed_at TEXT,
            FOREIGN KEY(departamento_id) REFERENCES departamentos(id)
        )
        '''
    )
    # Migraciones suaves (ignora si ya existen)
    for colddl in [
        "ALTER TABLE usuarios ADD COLUMN failed_attempts INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE usuarios ADD COLUMN password_changed_at TEXT",
        "ALTER TABLE usuarios ADD COLUMN cuenta_contable_id INTEGER",
        "ALTER TABLE usuarios ADD COLUMN fecha_registro TEXT",
        "ALTER TABLE usuarios ADD COLUMN fecha_ultimo_acceso TEXT",
        "ALTER TABLE usuarios ADD COLUMN ip_ultimo_acceso TEXT",
        "ALTER TABLE usuarios ADD COLUMN ua_ultimo_acceso TEXT",
        "ALTER TABLE usuarios ADD COLUMN fecha_ultimo_intento_fallido TEXT",
        "ALTER TABLE usuarios ADD COLUMN ip_ultimo_intento_fallido TEXT",
        "ALTER TABLE usuarios ADD COLUMN bloqueado_hasta TEXT",
        "ALTER TABLE usuarios ADD COLUMN fecha_bloqueo TEXT",
        "ALTER TABLE usuarios ADD COLUMN motivo_bloqueo TEXT",
        "ALTER TABLE usuarios ADD COLUMN password_changed_at TEXT",
 

    ]:
        
        try:
            cur.execute(colddl)
        except sqlite3.OperationalError:
            pass

   # Tabla de auditoría de seguridad
    cur.execute(
        '''
        CREATE TABLE IF NOT EXISTS auditoria_seguridad (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            username TEXT,
            evento TEXT NOT NULL,
            resultado TEXT,
            detalle TEXT,
            ip TEXT,
            user_agent TEXT,
            actor_usuario_id INTEGER,
            fecha_evento TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id),
            FOREIGN KEY(actor_usuario_id) REFERENCES usuarios(id)
        )
        '''
    )
   
   
    # --- Tareas ---
    cur.execute('''
        CREATE TABLE IF NOT EXISTS tareas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            descripcion TEXT,
            estado TEXT NOT NULL CHECK(estado IN ('Por iniciar','En desarrollo','Atrasada','Terminado', 'Cerrado por sistema')),
            fecha_creacion TEXT NOT NULL,
            fecha_inicio TEXT,
            fecha_fin TEXT,
            usuario_id INTEGER NOT NULL,
            notificado INTEGER NOT NULL DEFAULT 0
        )
    ''')
   
   
   
   
   
    cur.execute("PRAGMA table_info(tareas)")
    columnas = [col[1] for col in cur.fetchall()]

    if 'tipo_tarea_id' not in columnas:
        # Agregamos la columna como FK hacia param_values
        cur.execute('''
            ALTER TABLE tareas 
            ADD COLUMN tipo_tarea_id INTEGER 
            REFERENCES param_values(id)
        ''')
        print("Columna tipo_tarea_id creada.")


    # --- Tokens de reset ---
    cur.execute('''
        CREATE TABLE IF NOT EXISTS reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            code TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            attempts_left INTEGER NOT NULL,
            used INTEGER NOT NULL DEFAULT 0
        )
    ''')

    # --- Parametrización ---
    cur.execute('''
        CREATE TABLE IF NOT EXISTS param_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS param_values (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            nombre TEXT NOT NULL,
            valor TEXT
        )
    ''')

    # --- Plantillas de notificación ---
    cur.execute("""
        CREATE TABLE IF NOT EXISTS notify_templates(
            key TEXT PRIMARY KEY,
            subject TEXT NOT NULL,
            html TEXT NOT NULL,
            text TEXT,
            tipo TEXT
        )
    """)
    # Columna 'tipo' si faltara (migración suave)
    try:
        cur.execute("SELECT tipo FROM notify_templates LIMIT 1")
    except Exception:
        cur.execute("ALTER TABLE notify_templates ADD COLUMN tipo TEXT NULL")

    # --- Configuración general ---
    cur.execute('''
        CREATE TABLE IF NOT EXISTS configuracion (
            clave TEXT PRIMARY KEY,
            valor TEXT NOT NULL
        )
    ''')

    # --- Permisos ---
    cur.execute('''
        CREATE TABLE IF NOT EXISTS permisos (
            rol TEXT NOT NULL,
            opcion TEXT NOT NULL,
            ver INTEGER NOT NULL DEFAULT 0,
            crear INTEGER NOT NULL DEFAULT 0,
            editar INTEGER NOT NULL DEFAULT 0,
            eliminar INTEGER NOT NULL DEFAULT 0,
            exportar INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (rol, opcion)
        )
    ''')

    # --- Datos por defecto ---
    #cur.execute("INSERT OR IGNORE INTO departamentos (id, nombre) VALUES (1, 'General')")
    #cur.execute("""INSERT OR IGNORE INTO usuarios
    #    (id, username, password, email, rol, departamento_id, disabled)
    #    VALUES (1, 'admin', '1234', 'admin@example.com', 'admin', NULL, 0)""")
    #cur.execute("""INSERT OR IGNORE INTO usuarios
    #    (id, username, password, email, rol, departamento_id, disabled)
    #    VALUES (2, 'jefe', '1234', 'jefe@example.com', 'jefe', 1, 0)""")
    #cur.execute("""INSERT OR IGNORE INTO usuarios
    #    (id, username, password, email, rol, departamento_id, disabled)
    #    VALUES (3, 'usuario', '1234', 'usuario@example.com', 'usuario', 1, 0)""")

    defaults = {
        'smtp_host': os.environ.get('SMTP_HOST'),
        'smtp_port': os.environ.get('SMTP_PORT', '587'),
        'smtp_user': os.environ.get('SMTP_USER'),
        'smtp_pass': os.environ.get('SMTP_PASS'),
        'smtp_from': os.environ.get('SMTP_FROM') or os.environ.get('SMTP_USER'),
        'inactivity_minutes': '60',
        'edit_minutes': '5',
        'edit_hours': '1',
        'username_min_length': '6',
        'login_max_attempts': '5',
        'password_min_length': '8',
        'password_max_length': '15',
        'password_reminder_days': '20',
        'password_validity_days': '60',
        'password_allow_symbols': '1',
        'password_allow_numbers': '1',
        'password_allow_lowercase': '1',
        'password_allow_uppercase': '1',
    }
    #for k, v in defaults.items():
        #cur.execute("INSERT OR IGNORE INTO configuracion (clave, valor) VALUES (?, ?)", (k, v))

    permisos_default = [
        ('admin','departamentos',1,1,1,1,0),
        ('admin','usuarios',1,1,1,1,0),
        ('admin','parametros',1,1,1,0,0),
        ('admin','roles_permisos',1,1,1,0,0),
        ('admin','cambio_clave',1,1,1,0,0),
        ('admin','tareas',1,1,1,1,1),
        ('admin','reembolsos',1,1,1,1,1),
        ('admin','reembolsos_efectivo',1,1,1,1,1),
        ('admin','gastos_tarjeta',1,1,1,1,1),
        ('admin','seguridad',1,1,1,0,0),
        ('jefe','cambio_clave',1,1,1,0,0),
        ('jefe','tareas',1,1,1,0,0),
        ('jefe','reembolsos',1,1,1,0,0),
        ('jefe','reembolsos_efectivo',1,1,1,0,0),
        ('jefe','gastos_tarjeta',1,1,1,0,0),
        ('usuario','cambio_clave',1,1,1,0,0),
        ('usuario','tareas',1,1,1,0,0),
    ]
    #for entry in permisos_default:
        #cur.execute("""INSERT OR IGNORE INTO permisos
            #(rol, opcion, ver, crear, editar, eliminar, exportar)
            #VALUES (?, ?, ?, ?, ?, ?, ?)""", entry)

    default_param_groups = {
        'Configuración de correos': [
            ('smtp_host', defaults.get('smtp_host', '')),
            ('smtp_port', defaults.get('smtp_port', '')),
            ('smtp_user', defaults.get('smtp_user', '')),
            ('smtp_pass', defaults.get('smtp_pass', '')),
            ('smtp_from', defaults.get('smtp_from', '')),
        ],
        'Tiempo de cierre de sesión': [('minutos', defaults.get('inactivity_minutes', '60'))],
        'Minutos de edición de tareas': [('minutos', defaults.get('edit_minutes', '5'))],
        'Cuenta contable': [],
    }
    #for group_name, items in default_param_groups.items():
    #    cur.execute("INSERT OR IGNORE INTO param_groups (nombre) VALUES (?)", (group_name,))
    #    cur.execute("SELECT id FROM param_groups WHERE nombre=?", (group_name,))
    #    row = cur.fetchone()
    #    if row:
    #        gid = row['id']
    #        for item_name, valor in items:
    #            cur.execute(
    #                "INSERT OR IGNORE INTO param_values (group_id, nombre, valor) VALUES (?, ?, ?)",
    #                (gid, item_name, valor)
    #            )

    conn.commit()
    conn.close()
