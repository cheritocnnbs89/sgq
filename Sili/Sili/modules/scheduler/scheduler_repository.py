# modules/scheduler/scheduler_repository.py
# ==========================================================
# Acceso a datos y helpers DB del scheduler.
# Adaptado para SQL Server / pyodbc.
# Los ensure_* de creación/migración quedan desactivados
# porque el esquema ya existe en base de datos.
# ==========================================================

from __future__ import annotations

from typing import Any

from flask import current_app

from modules.config import DB_PATH
from modules.scheduler.scheduler_queries import (
    SQL_CREATE_NOTIFY_QUEUE,
    SQL_CREATE_NOTIFY_TEMPLATES,
    SQL_CREATE_NOTIFY_USER_PREFS,
    SQL_CREATE_NOTIFY_INAPP,
    SQL_DELETE_NOTIFY_QUEUE_NON_GASTO_DUPLICATES,
    SQL_CREATE_UQ_NOTIFY_QUEUE_ONCE,
    SQL_CREATE_IX_NOTIFY_QUEUE_PENDING,
    SQL_CREATE_UQ_NOTIFY_HOY,
    SQL_CREATE_UQ_NOTIFY_GASTO_EVENT,
    SQL_SELECT_USER_CONTACT,
    SQL_SELECT_GERENTE_GENERAL_IDS,
    SQL_SELECT_SC_IDS_JOIN_DEPARTAMENTOS,
    SQL_SELECT_SC_IDS_USUARIO_DEPARTAMENTO,
    SQL_SELECT_SC_IDS_PUESTO,
)
from modules.scheduler.scheduler_security import _exec_retry, _log


def _row_get(row: Any, key: str, idx: int | None = None, default=None):
    if row is None:
        return default

    try:
        val = row[key]
        return default if val is None else val
    except Exception:
        pass

    if idx is not None:
        try:
            val = row[idx]
            return default if val is None else val
        except Exception:
            pass

    return default


def _resolve_db_path() -> str:
    p = current_app.config.get("DATABASE") or current_app.config.get("DB_PATH")
    if p:
        return str(p)

    from modules.config import DB_PATH as _DB_PATH
    if _DB_PATH:
        return str(_DB_PATH)

    raise RuntimeError("DB path no configurado: setea app.config['DATABASE'] o app.config['DB_PATH']")


from modules.db import _connect  # 👈 IMPORTANTE (ajusta ruta si cambia)
def get_db_standalone():
    """
    Conexión independiente para scheduler (fuera de Flask context)
    """
    return _connect()


def ensure_notify_schema(conn):
    """
    En SQL Server ya existe el esquema. No ejecutar migraciones automáticas aquí.
    """
    # cur = conn.cursor()

    # _exec_retry(cur, SQL_CREATE_NOTIFY_QUEUE)
    # _exec_retry(cur, SQL_CREATE_NOTIFY_TEMPLATES)
    # _exec_retry(cur, SQL_CREATE_NOTIFY_USER_PREFS)
    # _exec_retry(cur, SQL_CREATE_NOTIFY_INAPP)

    # try:
    #     cur.execute("SELECT TOP 1 gasto_id FROM notify_queue")
    # except Exception:
    #     _exec_retry(cur, "ALTER TABLE notify_queue ADD gasto_id BIGINT NULL")

    # try:
    #     cur.execute("SELECT TOP 1 area FROM notify_queue")
    # except Exception:
    #     _exec_retry(cur, "ALTER TABLE notify_queue ADD area NVARCHAR(50) NULL")

    # try:
    #     cur.execute("SELECT TOP 1 event_key FROM notify_queue")
    # except Exception:
    #     _exec_retry(cur, "ALTER TABLE notify_queue ADD event_key NVARCHAR(255) NULL")

    # try:
    #     cur.execute("SELECT TOP 1 comentario FROM notify_queue")
    # except Exception:
    #     _exec_retry(cur, "ALTER TABLE notify_queue ADD comentario NVARCHAR(MAX) NULL")

    # _exec_retry(cur, SQL_DELETE_NOTIFY_QUEUE_NON_GASTO_DUPLICATES)
    # _exec_retry(cur, SQL_CREATE_UQ_NOTIFY_QUEUE_ONCE)
    # _exec_retry(cur, SQL_CREATE_IX_NOTIFY_QUEUE_PENDING)
    # _exec_retry(cur, SQL_CREATE_UQ_NOTIFY_HOY)
    # _exec_retry(cur, SQL_CREATE_UQ_NOTIFY_GASTO_EVENT)

    # conn.commit()
    return None


def ensure_gastos_expiry_schema(conn):
    """
    En SQL Server ya existe el esquema. No ejecutar migraciones automáticas aquí.
    """
    # cur = conn.cursor()

    # try:
    #     cur.execute("SELECT TOP 1 inactivo FROM gastos_tarjeta")
    # except Exception:
    #     cur.execute("ALTER TABLE gastos_tarjeta ADD inactivo BIT NOT NULL CONSTRAINT DF_gastos_tarjeta_inactivo DEFAULT 0")

    # try:
    #     cur.execute("SELECT TOP 1 inactivo_at FROM gastos_tarjeta")
    # except Exception:
    #     cur.execute("ALTER TABLE gastos_tarjeta ADD inactivo_at DATETIME NULL")

    # try:
    #     cur.execute("SELECT TOP 1 inactivo_reason FROM gastos_tarjeta")
    # except Exception:
    #     cur.execute("ALTER TABLE gastos_tarjeta ADD inactivo_reason NVARCHAR(MAX) NULL")

    # try:
    #     cur.execute("SELECT TOP 1 warn_sent_at FROM gastos_tarjeta")
    # except Exception:
    #     cur.execute("ALTER TABLE gastos_tarjeta ADD warn_sent_at DATETIME NULL")

    # conn.commit()
    return None


def ensure_om_notification_schema(conn):
    """
    En SQL Server ya existe el esquema. No ejecutar migraciones automáticas aquí.
    """
    # cur = conn.cursor()

    # try:
    #     cur.execute("SELECT TOP 1 om_notif_d4_at FROM reclamo_imputados")
    # except Exception:
    #     cur.execute("ALTER TABLE reclamo_imputados ADD om_notif_d4_at DATETIME NULL")

    # try:
    #     cur.execute("SELECT TOP 1 om_notif_d5_at FROM reclamo_imputados")
    # except Exception:
    #     cur.execute("ALTER TABLE reclamo_imputados ADD om_notif_d5_at DATETIME NULL")

    # try:
    #     cur.execute("SELECT TOP 1 om_notif_d9_at FROM reclamo_imputados")
    # except Exception:
    #     cur.execute("ALTER TABLE reclamo_imputados ADD om_notif_d9_at DATETIME NULL")

    # try:
    #     cur.execute("SELECT TOP 1 om_notif_d10_at FROM reclamo_imputados")
    # except Exception:
    #     cur.execute("ALTER TABLE reclamo_imputados ADD om_notif_d10_at DATETIME NULL")

    # conn.commit()
    return None


def get_ultimo_jefe_activo(conn, user_id: int | None) -> int | None:
    if not user_id:
        return None

    cur = conn.cursor()
    cur.execute("SELECT jefe_id FROM usuarios WHERE id = ?", (user_id,))
    row = cur.fetchone()
    if not row:
        return None

    jefe_id = _row_get(row, "jefe_id", 0)
    if not jefe_id:
        return None

    seen = set()
    last_valid = None

    while jefe_id and jefe_id not in seen:
        seen.add(jefe_id)

        cur.execute("""
            SELECT id, jefe_id
            FROM usuarios
            WHERE id = ?
              AND COALESCE(disabled, 0) = 0
        """, (jefe_id,))
        j = cur.fetchone()

        if not j:
            break

        last_valid = _row_get(j, "id", 0)
        jefe_id = _row_get(j, "jefe_id", 1)

    return int(last_valid) if last_valid else None


def _get_username(conn, user_id: int | None) -> str:
    if not user_id:
        return ""

    cur = conn.cursor()
    cur.execute("SELECT COALESCE(username,'') AS u FROM usuarios WHERE id = ?", (int(user_id),))
    r = cur.fetchone()
    return str(_row_get(r, "u", 0, "") or "")


def _get_user_contact(conn, user_id: int | None) -> dict | None:
    if not user_id:
        return None

    cur = conn.cursor()
    cur.execute(SQL_SELECT_USER_CONTACT, (int(user_id),))
    row = cur.fetchone()

    if not row:
        return None

    return {
        "id": _row_get(row, "id", 0),
        "nombre": (_row_get(row, "nombre", 1) or _row_get(row, "username", 2) or "Usuario"),
        "username": (_row_get(row, "username", 2) or ""),
        "email": (_row_get(row, "email", 3) or ""),
    }


def _get_ultimo_jefe_id(
    conn,
    user_id: int | None,
    *,
    fallback_to_self: bool = False
) -> int | None:
    if not user_id:
        return None

    cur = conn.cursor()
    cur.execute("SELECT jefe_id FROM usuarios WHERE id = ?", (int(user_id),))
    row = cur.fetchone()
    if not row:
        return None

    jefe_id = _row_get(row, "jefe_id", 0)
    if not jefe_id:
        return int(user_id) if fallback_to_self else None

    seen = set()
    last_valid = None

    while jefe_id and jefe_id not in seen:
        seen.add(jefe_id)
        cur.execute("""
            SELECT id, jefe_id
            FROM usuarios
            WHERE id = ?
              AND COALESCE(disabled,0)=0
        """, (int(jefe_id),))
        j = cur.fetchone()
        if not j:
            break

        last_valid = int(_row_get(j, "id", 0))
        jefe_id = _row_get(j, "jefe_id", 1)

    if last_valid is None and fallback_to_self:
        return int(user_id)

    return last_valid


def guess_gerente_area(conn, user_id: int | None) -> int | None:
    gerente = get_ultimo_jefe_activo(conn, user_id)
    if gerente:
        return gerente

    cur = conn.cursor()
    cur.execute("SELECT departamento_id FROM usuarios WHERE id = ?", (int(user_id),))
    u = cur.fetchone()
    depto_id = _row_get(u, "departamento_id", 0)
    if not depto_id:
        return None

    roles = (
        "jefe",
        "gerente",
        "gerente general",
        "gerente financiero",
        "coordinador",
        "admin",
        "usuario",
    )
    cur.execute(f"""
        SELECT TOP 1 id
        FROM usuarios
        WHERE departamento_id = ?
          AND LOWER(rol) IN ({",".join(["?"] * len(roles))})
          AND COALESCE(disabled, 0) = 0
        ORDER BY id
    """, (depto_id, *[r.lower() for r in roles]))
    row = cur.fetchone()
    rid = _row_get(row, "id", 0)
    return int(rid) if rid else None


def _get_gerente_general_ids(conn) -> list[int]:
    cur = conn.cursor()
    cur.execute(SQL_SELECT_GERENTE_GENERAL_IDS)
    out = []
    for r in cur.fetchall():
        rid = _row_get(r, "id", 0)
        if rid is not None:
            out.append(int(rid))
    return out


def _get_servicio_cliente_ids(conn) -> list[int]:
    cur = conn.cursor()
    ids = set()

    try:
        cur.execute(SQL_SELECT_SC_IDS_JOIN_DEPARTAMENTOS)
        ids.update(
            int(_row_get(r, "id", 0))
            for r in cur.fetchall()
            if _row_get(r, "id", 0) is not None
        )
    except Exception:
        pass

    try:
        cur.execute(SQL_SELECT_SC_IDS_USUARIO_DEPARTAMENTO)
        ids.update(
            int(_row_get(r, "id", 0))
            for r in cur.fetchall()
            if _row_get(r, "id", 0) is not None
        )
    except Exception:
        pass

    try:
        cur.execute(SQL_SELECT_SC_IDS_PUESTO)
        ids.update(
            int(_row_get(r, "id", 0))
            for r in cur.fetchall()
            if _row_get(r, "id", 0) is not None
        )
    except Exception:
        pass

    return sorted(ids)


def _sql_debug_counts(conn):
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) AS n FROM gastos_tarjeta")
    _log("info", "[EXPIRY][CNT] total gastos_tarjeta=%s", _row_get(cur.fetchone(), "n", 0, 0))

    cur.execute("SELECT COUNT(*) AS n FROM gastos_tarjeta WHERE COALESCE(inactivo,0)=0")
    _log("info", "[EXPIRY][CNT] no_inactivo=%s", _row_get(cur.fetchone(), "n", 0, 0))

    cur.execute("""
        SELECT COUNT(*) AS n
        FROM gastos_tarjeta
        WHERE COALESCE(inactivo,0)=0
          AND (
                sap_contabilizacion IS NULL
                OR LTRIM(RTRIM(COALESCE(CAST(sap_contabilizacion AS NVARCHAR(50)), ''))) = ''
              )
    """)
    _log("info", "[EXPIRY][CNT] no_inactivo_y_no_sap=%s", _row_get(cur.fetchone(), "n", 0, 0))

    cur.execute("""
        SELECT COUNT(*) AS n
        FROM gastos_tarjeta
        WHERE COALESCE(inactivo,0)=0
          AND (
                sap_contabilizacion IS NULL
                OR LTRIM(RTRIM(COALESCE(CAST(sap_contabilizacion AS NVARCHAR(50)), ''))) = ''
              )
          AND COALESCE(ga_aprobado,0)=0
          AND COALESCE(gg_aprobado,0)=0
          AND COALESCE(gf_aprobado,0)=0
    """)
    _log("info", "[EXPIRY][CNT] base_sin_aprobaciones=%s", _row_get(cur.fetchone(), "n", 0, 0))

    cur.execute("""
        SELECT COUNT(*) AS n
        FROM gastos_tarjeta
        WHERE COALESCE(inactivo,0)=0
          AND (
                sap_contabilizacion IS NULL
                OR LTRIM(RTRIM(COALESCE(CAST(sap_contabilizacion AS NVARCHAR(50)), ''))) = ''
              )
          AND COALESCE(ga_aprobado,0)=0
          AND COALESCE(gg_aprobado,0)=0
          AND COALESCE(gf_aprobado,0)=0
          AND warn_sent_at IS NULL
    """)
    _log("info", "[EXPIRY][CNT] base_sin_aprobaciones_y_sin_warn=%s", _row_get(cur.fetchone(), "n", 0, 0))

    cur.execute("""
        SELECT COUNT(*) AS n
        FROM gastos_tarjeta
        WHERE COALESCE(inactivo,0)=0
          AND (
                sap_contabilizacion IS NULL
                OR LTRIM(RTRIM(COALESCE(CAST(sap_contabilizacion AS NVARCHAR(50)), ''))) = ''
              )
          AND COALESCE(ga_aprobado,0)=0
          AND COALESCE(gg_aprobado,0)=0
          AND COALESCE(gf_aprobado,0)=0
          AND warn_sent_at IS NULL
          AND CAST(fecha AS date) <= DATEADD(day, -6, CAST(GETDATE() AS date))
          AND CAST(fecha AS date) >  DATEADD(day, -7, CAST(GETDATE() AS date))
    """)
    _log("info", "[EXPIRY][CNT] candidatos_warn_dia6=%s", _row_get(cur.fetchone(), "n", 0, 0))

    cur.execute("""
        SELECT COUNT(*) AS n
        FROM gastos_tarjeta
        WHERE COALESCE(inactivo,0)=0
          AND (
                sap_contabilizacion IS NULL
                OR LTRIM(RTRIM(COALESCE(CAST(sap_contabilizacion AS NVARCHAR(50)), ''))) = ''
              )
          AND COALESCE(ga_aprobado,0)=0
          AND COALESCE(gg_aprobado,0)=0
          AND COALESCE(gf_aprobado,0)=0
          AND CAST(fecha AS date) <= DATEADD(day, -7, CAST(GETDATE() AS date))
    """)
    _log("info", "[EXPIRY][CNT] candidatos_expire_dia7=%s", _row_get(cur.fetchone(), "n", 0, 0))

    cur.execute("""
        SELECT COUNT(*) AS n
        FROM gastos_tarjeta
        WHERE fecha IS NOT NULL
          AND TRY_CONVERT(date, fecha) IS NULL
    """)
    _log("warning", "[EXPIRY][CNT] fecha_no_parseable_por_sqlserver=%s", _row_get(cur.fetchone(), "n", 0, 0))

    cur.execute("""
        SELECT TOP 5 id, fecha
        FROM gastos_tarjeta
        WHERE fecha IS NOT NULL
          AND TRY_CONVERT(date, fecha) IS NULL
        ORDER BY id DESC
    """)
    bad = cur.fetchall() or []
    for r in bad:
        _log(
            "warning",
            "[EXPIRY][BADFECHA] id=%s fecha='%s'",
            _row_get(r, "id", 0),
            _row_get(r, "fecha", 1),
        )