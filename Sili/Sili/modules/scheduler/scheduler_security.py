# modules/scheduler/scheduler_security.py
# ==========================================================
# Utilidades operativas y de protección del scheduler.
# Conserva helpers de log, SQL debug, retry y quiet hours.
# ==========================================================

from __future__ import annotations

import sqlite3
from datetime import datetime, time as dtime
from typing import Optional

from flask import current_app


def _log(level: str, msg: str, *args):
    try:
        logger = current_app.logger
        fn = getattr(logger, level if level in ("info", "warning", "error", "debug") else "info")
        fn(msg, *args)
    except Exception:
        try:
            print(f"[{datetime.utcnow().isoformat()}] [{level.upper()}] " + (msg % args if args else msg))
        except Exception:
            pass


def _format_sql_for_log(sql: str, params: tuple) -> str:
    """Devuelve el SQL con cada ? reemplazado por la repr del parámetro (SOLO para LOG)."""
    out = []
    it = iter(params)
    parts = sql.split("?")
    for idx, ch in enumerate(parts):
        out.append(ch)
        if idx < len(parts) - 1:
            try:
                p = next(it)
                if isinstance(p, str):
                    out.append("'" + p.replace("'", "''") + "'")
                else:
                    out.append(repr(p))
            except StopIteration:
                out.append("?")
    return "".join(out)


def _exec_retry(cur, sql, params=(), tries=6, base_wait=0.15):
    import time as _t

    for i in range(tries):
        try:
            return cur.execute(sql, params)
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e).lower() and i < tries - 1:
                _t.sleep(base_wait * (i + 1))
                continue
            raise


def _is_quiet(now_t: dtime, quiet_start: Optional[str], quiet_end: Optional[str]) -> bool:
    if not quiet_start or not quiet_end:
        return False
    qs = datetime.strptime(quiet_start, "%H:%M").time()
    qe = datetime.strptime(quiet_end, "%H:%M").time()
    if qs < qe:
        return qs <= now_t < qe
    return (now_t >= qs) or (now_t < qe)


def _next_5min_sqlite() -> str:
    return "datetime((strftime('%s','now')/300 + 1)*300, 'unixepoch')"


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")