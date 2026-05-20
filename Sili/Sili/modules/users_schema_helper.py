# modules/users_schema_helper.py
# -*- coding: utf-8 -*-
import sqlite3
from typing import Optional
from .db import get_db

def _safe_alter(cur: sqlite3.Cursor, ddl: str):
    try:
        cur.execute(ddl)
    except sqlite3.OperationalError:
        # columna/índice ya existe, tabla sin esa columna, etc.
        pass

def ensure_users_extra_schema(conn: Optional[sqlite3.Connection] = None):
    """
    Asegura columnas y tablas adicionales usadas por routes_users.py:
      - Columnas extra en usuarios
      - Tablas: empresas, areas, puestos, usuarios_cc
    Si 'conn' es None, abre una conexión propia vía get_db().
    No cierra la conexión si viene de afuera.
    """
    local = False
    if conn is None:
        conn = get_db()
        local = True

    cur = conn.cursor()

    # ---- Columnas nuevas en usuarios (idempotentes) ----
    _safe_alter(cur, "ALTER TABLE usuarios ADD COLUMN nombre_completo TEXT")
    _safe_alter(cur, "ALTER TABLE usuarios ADD COLUMN identificacion TEXT")
    _safe_alter(cur, "ALTER TABLE usuarios ADD COLUMN sexo TEXT")  # 'M','F', etc.
    _safe_alter(cur, "ALTER TABLE usuarios ADD COLUMN fecha_nacimiento TEXT")
    _safe_alter(cur, "ALTER TABLE usuarios ADD COLUMN fecha_ingreso TEXT")
    _safe_alter(cur, "ALTER TABLE usuarios ADD COLUMN provincia TEXT")
    _safe_alter(cur, "ALTER TABLE usuarios ADD COLUMN ciudad TEXT")
    _safe_alter(cur, "ALTER TABLE usuarios ADD COLUMN direccion TEXT")
    _safe_alter(cur, "ALTER TABLE usuarios ADD COLUMN empresa_id INTEGER")
    _safe_alter(cur, "ALTER TABLE usuarios ADD COLUMN area_id INTEGER")
    _safe_alter(cur, "ALTER TABLE usuarios ADD COLUMN puesto_id INTEGER")
    _safe_alter(cur, "ALTER TABLE usuarios ADD COLUMN tarjeta_alias TEXT")
    _safe_alter(cur, "ALTER TABLE usuarios ADD COLUMN tarjeta_last4 TEXT")

    # ---- Tablas maestras (idempotentes) ----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS empresas(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            razon_social TEXT NOT NULL UNIQUE,
            activo INTEGER NOT NULL DEFAULT 1
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS areas(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            activo INTEGER NOT NULL DEFAULT 1
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS puestos(
                
            id INTEGER PRIMARY KEY AUTOINCREMENT,
                        codigo TEXT NOT NULL UNIQUE,

            nombre TEXT NOT NULL UNIQUE,
            activo INTEGER NOT NULL DEFAULT 1
        )
    """)

    # Índices útiles
    cur.execute("CREATE INDEX IF NOT EXISTS idx_empresas_activo ON empresas(activo)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_areas_activo    ON areas(activo)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_puestos_activo  ON puestos(activo)")

    # ---- Distribución de centros de costo por usuario ----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios_cc(
            usuario_id      INTEGER NOT NULL,
            centro_costo_id INTEGER NOT NULL,
            porcentaje      REAL    NOT NULL,
            PRIMARY KEY (usuario_id, centro_costo_id)
        )
    """)
    # Índice opcional para consultas por usuario
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ucc_user ON usuarios_cc(usuario_id)")

    # (Opcional) FK enforcement si usas claves foráneas y existen las tablas destino:
    # cur.execute("PRAGMA foreign_keys=ON")

    if local:
        conn.commit()
