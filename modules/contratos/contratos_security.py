from __future__ import annotations

from flask import session


def session_user_id() -> int | None:
    for k in ("usuario_id", "user_id", "id", "uid"):
        v = session.get(k)
        if v is not None:
            try:
                return int(v)
            except Exception:
                pass
    return None


def session_dept_id() -> int | None:
    for k in ("departamento_id", "dept_id", "depto_id", "dep_id"):
        v = session.get(k)
        if v is not None:
            try:
                return int(v)
            except Exception:
                pass
    return None


def rowget(row, key, default=None):
    try:
        return row[key]
    except Exception:
        return default