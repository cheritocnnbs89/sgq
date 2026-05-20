# modules/tasks/task_utils.py
from __future__ import annotations

import re
from datetime import datetime, date, time


def build_user_display_name(user_row) -> str:
    """
    Intenta armar 'Nombre Apellido' usando distintos posibles campos.
    Si no encuentra, usa username.
    """
    d = dict(user_row)
    base = ""

    # 1) campos de nombre completo directos
    for k in ("nombre_completo", "nombrecompleto", "full_name"):
        v = d.get(k)
        if v:
            base = str(v).strip()
            break

    # 2) combinar nombres + apellidos o variantes
    if not base:
        first = None
        last = None
        for k in ("nombres", "nombre", "first_name"):
            if k in d and d[k]:
                first = str(d[k]).strip()
                break
        for k in ("apellidos", "apellido", "last_name"):
            if k in d and d[k]:
                last = str(d[k]).strip()
                break
        parts = [p for p in (first, last) if p]
        if parts:
            base = " ".join(parts)

    # 3) fallback username
    if not base:
        u = d.get("username")
        if u:
            base = str(u).strip()
        else:
            base = f"ID {d.get('id', '?')}"

    return base


def parse_dt(val):
    if not val:
        return None

    if isinstance(val, datetime):
        return val

    if isinstance(val, date):
        return datetime.combine(val, time.min)

    texto = str(val).strip()
    if not texto:
        return None

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(texto, fmt)
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(texto)
    except Exception:
        return None


def _norm_email(s: str) -> str:
    return (s or "").strip().lower()


def _extract_email(value) -> str:
    """
    Acepta:
    - "Nombre <a@b.com>"
    - "a@b.com"
    """
    if not value:
        return ""

    raw = str(value)
    m = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", raw, flags=re.I)
    return _norm_email(m.group(0)) if m else ""