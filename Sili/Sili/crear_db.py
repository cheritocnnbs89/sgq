#!/usr/bin/env python3
"""Utility script to initialize the Bitácora database.

Running this script will create the SQLite database at the configured
location (./database/bitacora.db), create the required tables, and insert
default records for a department, an admin user, a department head, and a
regular user. You can run this script manually if you wish to prepare the
database before starting the Flask application.
"""
import os
import sqlite3

DB_PATH = os.path.join('database', 'bitacora.db')


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # Create departments table
    cur.execute(
        '''
        CREATE TABLE IF NOT EXISTS departamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE
        )
        '''
    )
    cur.execute(
        '''
        CREATE TABLE IF NOT EXISTS permisos (
            rol TEXT NOT NULL,
            opcion TEXT NOT NULL,
            ver INTEGER NOT NULL DEFAULT 0,
            crear INTEGER NOT NULL DEFAULT 0,
            editar INTEGER NOT NULL DEFAULT 0,
            eliminar INTEGER NOT NULL DEFAULT 0,
            exportar INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (rol, opcion),
            CHECK (ver IN (0,1) AND crear IN (0,1) AND editar IN (0,1) AND eliminar IN (0,1) AND exportar IN (0,1))
        )
        '''
    )
    # Cargar permisos predeterminados
    permisos_default = [
        # admin tiene acceso total a todas las opciones
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
        # jefe puede gestionar tareas y reembolsos, cambiar su clave
        ('jefe','departamentos',0,0,0,0,0),
        ('jefe','usuarios',0,0,0,0,0),
        ('jefe','parametros',0,0,0,0,0),
        ('jefe','roles_permisos',0,0,0,0,0),
        ('jefe','cambio_clave',1,1,1,0,0),
        ('jefe','tareas',1,1,1,0,0),
        ('jefe','reembolsos',1,1,1,0,0),
        ('jefe','reembolsos_efectivo',1,1,1,0,0),
        ('jefe','gastos_tarjeta',1,1,1,0,0),
        ('jefe','seguridad',0,0,0,0,0),
        # usuario puede gestionar sus tareas y cambiar su clave
        ('usuario','departamentos',0,0,0,0,0),
        ('usuario','usuarios',0,0,0,0,0),
        ('usuario','parametros',0,0,0,0,0),
        ('usuario','roles_permisos',0,0,0,0,0),
        ('usuario','cambio_clave',1,1,1,0,0),
        ('usuario','tareas',1,1,1,0,0),
        ('usuario','reembolsos',0,0,0,0,0),
        ('usuario','seguridad',0,0,0,0,0),
    ]
    for entry in permisos_default:
        cur.execute(
            "INSERT OR IGNORE INTO permisos (rol, opcion, ver, crear, editar, eliminar, exportar) VALUES (?, ?, ?, ?, ?, ?, ?)",
            entry,
        )
  
    # Create users table
    cur.execute(
        '''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            rol TEXT NOT NULL CHECK(rol IN ('admin','jefe','usuario')),
            departamento_id INTEGER,
            FOREIGN KEY(departamento_id) REFERENCES departamentos(id)
        )
        '''
    )

    cur.execute("""
      INSERT OR IGNORE INTO roles_permisos
        (rol_id, opcion_id, ver, crear, editar, eliminar, exportar, aprobar)
      SELECT r.id, o.id, 0,0,0,0,0,0
      FROM roles r
      CROSS JOIN opciones o
      LEFT JOIN roles_permisos rp
        ON rp.rol_id = r.id AND rp.opcion_id = o.id
      WHERE rp.opcion_id IS NULL;
    """)
    # Create tasks table
    cur.execute(
        '''
        CREATE TABLE IF NOT EXISTS tareas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            descripcion TEXT,
            estado TEXT NOT NULL CHECK(estado IN ('Por iniciar','En desarrollo','Atrasada','Terminado')),
            fecha_creacion TEXT NOT NULL,
            fecha_inicio TEXT,
            fecha_fin TEXT,
            usuario_id INTEGER NOT NULL,
            notificado INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
        )
        
        '''
    )
    

    cur.execute("PRAGMA table_info(tareas)")
# --- Verificación para la tabla TAREAS (lo que ya tienes) ---
    columnas_tareas = [col[1] for col in cur.fetchall()]

    if 'tipo_tarea_id' not in columnas_tareas:
        cur.execute('''
            ALTER TABLE tareas 
            ADD COLUMN tipo_tarea_id INTEGER 
            REFERENCES param_values(id)
        ''')
        print("Columna tipo_tarea_id creada en tabla tareas.")

    # --- NUEVO: Verificación para la tabla TAREA_ACCIONES ---
    # Ajusta el nombre 'tarea_acciones' si en tu base de datos se llama distinto
    cur.execute("PRAGMA table_info(tarea_acciones)")
    columnas_acciones = [col[1] for col in cur.fetchall()]

    # 1. Usuario asignado específicamente a ese paso/avance
    if 'usuario_asignado_id' not in columnas_acciones:
        cur.execute('ALTER TABLE tarea_acciones ADD COLUMN usuario_asignado_id INTEGER REFERENCES usuarios(id)')
        print("Columna usuario_asignado_id creada.")

    # 2. Estado específico de la acción (En proceso, Finalizado, etc.)
    if 'estado_accion' not in columnas_acciones:
        cur.execute("ALTER TABLE tarea_acciones ADD COLUMN estado_accion VARCHAR(50) DEFAULT 'En proceso'")
        print("Columna estado_accion creada.")

    # 3. Fecha en la que se inicia este paso (generalmente fecha de registro)
    if 'fecha_inicio' not in columnas_acciones:
        cur.execute('ALTER TABLE tarea_acciones ADD COLUMN fecha_inicio DATETIME')
        print("Columna fecha_inicio creada.")

    # 4. Fecha fin tentativa para concluir este paso específico
    if 'fecha_fin_tentativa' not in columnas_acciones:
        cur.execute('ALTER TABLE tarea_acciones ADD COLUMN fecha_fin_tentativa DATETIME')
        print("Columna fecha_fin_tentativa creada.")

 
    # Seed default department and users
    cur.execute("INSERT OR IGNORE INTO departamentos (id, nombre) VALUES (1, 'General')")
    cur.execute(
        "INSERT OR IGNORE INTO usuarios (id, username, password, email, rol, departamento_id) "
        "VALUES (1, 'admin', '1234', 'admin@example.com', 'admin', NULL)"
    )
    cur.execute(
        "INSERT OR IGNORE INTO usuarios (id, username, password, email, rol, departamento_id) "
        "VALUES (2, 'jefe', '1234', 'jefe@example.com', 'jefe', 1)"
    )
    cur.execute(
        "INSERT OR IGNORE INTO usuarios (id, username, password, email, rol, departamento_id) "
        "VALUES (3, 'usuario', '1234', 'usuario@example.com', 'usuario', 1)"
    )
    # Crear tabla de configuración con claves y valores predeterminados
    cur.execute(
        '''
        CREATE TABLE IF NOT EXISTS configuracion (
            clave TEXT PRIMARY KEY,
            valor TEXT NOT NULL
        )
        '''
    )
    # Valores por defecto
    defaults = {
        'smtp_host': os.environ.get('SMTP_HOST', 'smtp.office365.com'),
        'smtp_port': os.environ.get('SMTP_PORT', '587'),
        'smtp_user': os.environ.get('SMTP_USER', 'control@quimpac.com.ec'),
        'smtp_pass': os.environ.get('SMTP_PASS', 'zGv4*HeCs'),
        'smtp_from': os.environ.get('SMTP_FROM', os.environ.get('SMTP_USER', 'control@quimpac.com.ec')),
        'edit_hours': '1',
    }
    for clave, valor in defaults.items():
        cur.execute(
            "INSERT OR IGNORE INTO configuracion (clave, valor) VALUES (?, ?)",
            (clave, valor),
        )
    conn.commit()
    ensure_users_extra_schema(conn)
    conn.close()
    print(f"Base de datos inicializada en {DB_PATH}")


# modules/users_schema_helper.py
from typing import Iterable

def column_exists(conn, table: str, col: str) -> bool:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return any(r[1].lower() == col.lower() for r in cur.fetchall())

def ensure_users_extra_schema(conn):
    cur = conn.cursor()

    # Tablas auxiliares
    cur.execute("""CREATE TABLE IF NOT EXISTS areas(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL UNIQUE,
        activo INTEGER DEFAULT 1
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS puestos(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
    
                codigo TEXT NOT NULL UNIQUE,

        nombre TEXT NOT NULL UNIQUE,
        activo INTEGER DEFAULT 1
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS usuarios_cc(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER NOT NULL,
        centro_costo_id INTEGER NOT NULL,
        porcentaje REAL NOT NULL CHECK(porcentaje>=0 AND porcentaje<=100),
        UNIQUE(usuario_id, centro_costo_id)
    )""")

    # Columns a añadir en usuarios
    adds = [
        ("area_id", "INTEGER"),
        ("puesto_id", "INTEGER"),
        ("empresa_id", "INTEGER"),
        ("fecha_nacimiento", "TEXT"),
        ("fecha_ingreso", "TEXT"),
        ("provincia", "TEXT"),
        ("ciudad", "TEXT"),
        ("direccion", "TEXT"),
        ("tarjeta_last4", "TEXT"),
        ("tarjeta_alias", "TEXT"),
        ("nombre_completo", "TEXT"),
        ("identificacion", "TEXT"),
        ("sexo", "TEXT"),
        ("jefe_id", "INTEGER"),

    ]
    for col, typ in adds:
        if not column_exists(conn, "usuarios", col):
            cur.execute(f"ALTER TABLE usuarios ADD COLUMN {col} {typ}")
    conn.commit()


if __name__ == '__main__':
    init_db()