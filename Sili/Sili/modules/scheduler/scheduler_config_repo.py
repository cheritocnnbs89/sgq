# modules/scheduler/scheduler_config_repo.py
# ==========================================================
# Acceso a la tabla scheduler_jobs_config en SQL Server.
# Permite leer configuración, actualizar, y auto-seed desde registry.
# ==========================================================

from __future__ import annotations

import logging
from datetime import datetime
from .scheduler_registry import JOB_REGISTRY

logger = logging.getLogger(__name__)

SQL_ENSURE_TABLE = """
IF NOT EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_NAME = 'scheduler_jobs_config'
)
BEGIN
    CREATE TABLE scheduler_jobs_config (
        id                INT IDENTITY(1,1) PRIMARY KEY,
        job_key           VARCHAR(100) NOT NULL,
        modulo            VARCHAR(50),
        descripcion       VARCHAR(300),
        activo            BIT NOT NULL DEFAULT 1,
        tipo              VARCHAR(20) NOT NULL DEFAULT 'intervalo',
        intervalo_min     INT,
        hora_inicio       VARCHAR(5),
        ultima_ejecucion  DATETIME,
        ultimo_resultado  VARCHAR(500),
        creado_en         DATETIME DEFAULT GETDATE(),
        CONSTRAINT UQ_scheduler_job_key UNIQUE (job_key)
    )
END
"""


def ensure_scheduler_table(conn) -> None:
    cur = conn.cursor()
    cur.execute(SQL_ENSURE_TABLE)
    conn.commit()

    # Agregar columnas que podrían faltar en tablas creadas con versión anterior
    _add_column_if_missing(conn, "scheduler_jobs_config", "tipo",
                           "VARCHAR(20) NOT NULL DEFAULT 'intervalo'")
    _add_column_if_missing(conn, "scheduler_jobs_config", "intervalo_min", "INT")
    _add_column_if_missing(conn, "scheduler_jobs_config", "hora_inicio", "VARCHAR(5)")
    _add_column_if_missing(conn, "scheduler_jobs_config", "ultima_ejecucion", "DATETIME")
    _add_column_if_missing(conn, "scheduler_jobs_config", "ultimo_resultado", "VARCHAR(500)")

    _seed_from_registry(conn)


def _add_column_if_missing(conn, table: str, column: str, col_def: str) -> None:
    cur = conn.cursor()
    cur.execute(
        """SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
           WHERE TABLE_NAME = ? AND COLUMN_NAME = ?""",
        (table, column)
    )
    if not cur.fetchone():
        cur.execute(f"ALTER TABLE {table} ADD {column} {col_def}")
        conn.commit()


def _seed_from_registry(conn) -> None:
    cur = conn.cursor()
    for job_key, meta in JOB_REGISTRY.items():
        cur.execute(
            "SELECT id FROM scheduler_jobs_config WHERE job_key = ?",
            (job_key,)
        )
        if not cur.fetchone():
            cur.execute(
                """INSERT INTO scheduler_jobs_config
                   (job_key, modulo, descripcion, activo, tipo, intervalo_min, hora_inicio)
                   VALUES (?, ?, ?, 1, ?, ?, ?)""",
                (
                    job_key,
                    meta.get("modulo"),
                    meta.get("descripcion"),
                    meta.get("tipo", "intervalo"),
                    meta.get("intervalo_min"),
                    meta.get("hora_inicio"),
                )
            )
    conn.commit()


def get_all_jobs(conn) -> list[dict]:
    cur = conn.cursor()
    cur.execute("""
        SELECT id, job_key, modulo, descripcion, activo, tipo,
               intervalo_min, hora_inicio, ultima_ejecucion, ultimo_resultado, creado_en
        FROM scheduler_jobs_config
        ORDER BY modulo, job_key
    """)
    # Guardar descripción antes de fetchall (pyodbc la pierde después en algunos drivers)
    cols = [c[0] for c in cur.description] if cur.description else []
    rows = cur.fetchall()
    if not rows:
        return []
    first = rows[0]
    if isinstance(first, dict):
        return [dict(r) for r in rows]
    return [dict(zip(cols, row)) for row in rows]


def get_job_config(conn, job_key: str) -> dict | None:
    cur = conn.cursor()
    cur.execute(
        """SELECT activo, tipo, intervalo_min, hora_inicio
           FROM scheduler_jobs_config WHERE job_key = ?""",
        (job_key,)
    )
    row = cur.fetchone()
    if not row:
        return None
    return {
        "activo": bool(row[0]),
        "tipo": row[1],
        "intervalo_min": row[2],
        "hora_inicio": row[3],
    }


def update_job_result(conn, job_key: str, resultado: str) -> None:
    cur = conn.cursor()
    cur.execute(
        """UPDATE scheduler_jobs_config
           SET ultima_ejecucion = GETDATE(), ultimo_resultado = ?
           WHERE job_key = ?""",
        (resultado[:500] if resultado else "", job_key)
    )
    conn.commit()


def update_job_config(conn, job_key: str, activo: bool,
                      intervalo_min: int | None, hora_inicio: str | None) -> None:
    cur = conn.cursor()
    cur.execute(
        """UPDATE scheduler_jobs_config
           SET activo = ?, intervalo_min = ?, hora_inicio = ?
           WHERE job_key = ?""",
        (1 if activo else 0, intervalo_min, hora_inicio or None, job_key)
    )
    conn.commit()
