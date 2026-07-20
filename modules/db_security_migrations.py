# modules/db_security_migrations.py
from .db import get_db

def ensure_security_columns():
    conn = get_db()
    cur  = conn.cursor()

    # columnas nuevas en usuarios
    cur.execute("PRAGMA table_info(usuarios)")
    cols = {row[1] for row in cur.fetchall()}

    def add(col, decl):
        cur.execute(f"ALTER TABLE usuarios ADD COLUMN {col} {decl}")

    if 'password_hash' not in cols:
        add('password_hash', 'TEXT')  # hash PBKDF2
    if 'locked_until'  not in cols:
        add('locked_until',  'TEXT')  # ISO ts si está bloqueado
    if 'failed_attempts' not in cols:
        add('failed_attempts','INTEGER DEFAULT 0')
    if 'password_changed_at' not in cols:
        add('password_changed_at','TEXT')
    if 'twofa_enabled' not in cols:
        add('twofa_enabled','INTEGER DEFAULT 0')

    # tabla simple para 2FA
    cur.execute("""
        CREATE TABLE IF NOT EXISTS twofa_codes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            code_hash TEXT NOT NULL,
            purpose TEXT NOT NULL,        -- 'login'
            expires_at TEXT NOT NULL,     -- ISO ts
            attempts INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY(user_id) REFERENCES usuarios(id)
        )
    """)

    conn.commit()
    conn.close()
