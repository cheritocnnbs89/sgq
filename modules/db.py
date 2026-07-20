import os
from typing import Optional, Dict

import pyodbc
from flask import g


class RowCompat(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as e:
            raise AttributeError(name) from e

class CursorCompat:
    db_engine = "sqlserver"

    def __init__(self, cur: pyodbc.Cursor):
        self._cur = cur

    @property
    def raw(self):
        return self._cur

    @property
    def description(self):
        return self._cur.description

    @property
    def rowcount(self):
        return self._cur.rowcount

    def execute(self, sql, params=None):
        if params is None:
            self._cur.execute(sql)
        else:
            self._cur.execute(sql, params)
        return self

    def executemany(self, sql, seq_of_params):
        self._cur.executemany(sql, seq_of_params)
        return self

    def fetchone(self):
        row = self._cur.fetchone()
        if row is None:
            return None
        cols = [c[0] for c in self._cur.description] if self._cur.description else []
        return RowCompat(zip(cols, row))

    def fetchall(self):
        rows = self._cur.fetchall()
        if not rows:
            return []
        cols = [c[0] for c in self._cur.description] if self._cur.description else []
        return [RowCompat(zip(cols, row)) for row in rows]

    def fetchmany(self, size=None):
        rows = self._cur.fetchmany(size) if size is not None else self._cur.fetchmany()
        if not rows:
            return []
        cols = [c[0] for c in self._cur.description] if self._cur.description else []
        return [RowCompat(zip(cols, row)) for row in rows]

    def close(self):
        self._cur.close()

    def __iter__(self):
        cols = [c[0] for c in self._cur.description] if self._cur.description else []
        for row in self._cur:
            yield RowCompat(zip(cols, row)) if cols else row


class ConnectionCompat:
    db_engine = "sqlserver"

    def __init__(self, conn: pyodbc.Connection):
        self._conn = conn

    @property
    def raw(self):
        return self._conn

    @property
    def autocommit(self):
        return self._conn.autocommit

    @autocommit.setter
    def autocommit(self, value):
        self._conn.autocommit = value

    def cursor(self):
        return CursorCompat(self._conn.cursor())

    def execute(self, sql, params=None):
        cur = self.cursor()
        return cur.execute(sql, params)

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        return self._conn.close()
# -------------------------
# config conexión
# -------------------------

def _build_conn_str(database: Optional[str] = None) -> str:
    host = os.environ.get("SQLSERVER_HOST", "172.16.40.52").strip()
    port = os.environ.get("SQLSERVER_PORT", "1433").strip()
    dbname = (database or os.environ.get("SQLSERVER_DATABASE", "SGQ_BITACORA")).strip()
    user = os.environ.get("SQLSERVER_USER", "user_sgp").strip()
    password = os.environ.get("SQLSERVER_PASSWORD", "Qu1mpAC2020$").strip()
    driver = os.environ.get("SQLSERVER_DRIVER", "SQL Server Native Client 11.0").strip()
    encrypt = os.environ.get("SQLSERVER_ENCRYPT", "no").strip()
    trust_cert = os.environ.get("SQLSERVER_TRUST_CERT", "yes").strip()

    server = f"{host},{port}" if port else host
    parts = [
        f"DRIVER={{{driver}}}",
        f"SERVER={server}",
        f"DATABASE={dbname}",
        f"Encrypt={encrypt}",
        f"TrustServerCertificate={trust_cert}",
    ]

    if user and password:
        parts += [f"UID={user}", f"PWD={password}"]
    else:
        parts.append("Trusted_Connection=yes")

    return ";".join(parts)


def _configure_conn(conn: pyodbc.Connection) -> ConnectionCompat:
    conn.autocommit = False
    return ConnectionCompat(conn)


def _connect(database: Optional[str] = None) -> ConnectionCompat:
    raw =pyodbc.connect(_build_conn_str(database=database), timeout=30)
    return _configure_conn(raw)


def get_db() -> ConnectionCompat:
    db = g.get("db")
    if db is not None:
        try:
            db.execute("SELECT 1").fetchone()
            return db
        except Exception:
            try:
                db.close()
            except Exception:
                pass
            g.pop("db", None)

    g.db = _connect()
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        try:
            db.close()
        except Exception:
            pass


def init_app(app):
    app.teardown_appcontext(close_db)


def get_config_value(clave: str, default=None):
    _temp = False
    conn = None
    try:
        try:
            conn = get_db()
        except RuntimeError:
            conn = _connect()
            _temp = True

        cur = conn.cursor()
        cur.execute("SELECT valor FROM configuracion WHERE clave = ?", (clave,))
        row = cur.fetchone()
        return row["valor"] if row else default
    except Exception:
        return default
    finally:
        if _temp and conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def set_config_values(data: Dict[str, str]):
    _temp = False
    conn = None
    try:
        try:
            conn = get_db()
        except RuntimeError:
            conn = _connect()
            _temp = True

        cur = conn.cursor()
        for clave, valor in data.items():
            cur.execute("SELECT 1 FROM configuracion WHERE clave = ?", (clave,))
            row = cur.fetchone()
            if row:
                cur.execute(
                    "UPDATE configuracion SET valor = ? WHERE clave = ?",
                    (valor, clave)
                )
            else:
                cur.execute(
                    "INSERT INTO configuracion (clave, valor) VALUES (?, ?)",
                    (clave, valor)
                )
        conn.commit()
    except Exception:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        raise
    finally:
        if _temp and conn is not None:
            try:
                conn.close()
            except Exception:
                pass


TPL_TYPES = [
    ("hoy", "Recordatorio del día"),
    ("vencida", "Tarea vencida"),
    ("resumen_semanal", "Resumen semanal"),
    ("resumen_mensual", "Resumen mensual"),
]


def init_db():
    # En SQL Server ya no creamos esquema desde Flask.
    return None