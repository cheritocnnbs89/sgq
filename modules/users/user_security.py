# modules/users/user_security.py
# -*- coding: utf-8 -*-
# ==========================================================
# Utilidades internas del módulo de usuarios.
# Conserva helpers de normalización y generación de username.
# ==========================================================

import re


def strip_accents_and_symbols(txt: str) -> str:
    """
    Convierte tildes -> sin tildes, ñ->n, quita espacios y símbolos raros.
    Deja solo [a-z0-9].
    """
    if not txt:
        return ""

    repl = (
        ("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"),
        ("Á", "a"), ("É", "a"), ("Í", "i"), ("Ó", "o"), ("Ú", "u"),
        ("ñ", "n"), ("Ñ", "n"),
    )
    for a, b in repl:
        txt = txt.replace(a, b)

    txt = txt.lower()
    txt = re.sub(r"[^\w]", "", txt)
    txt = txt.replace("_", "")
    return txt


def first_word(txt: str) -> str:
    """
    Devuelve la primera palabra 'limpia' de un string tipo 'JUAN ALFREDO'
    -> 'JUAN'. Si viene vacío, devuelve ''.
    """
    if not txt:
        return ""
    parts = [p for p in re.split(r"\s+", txt.strip()) if p]
    return parts[0] if parts else ""


def first_lastname_block(txt: str) -> str:
    """
    Devuelve la primera 'palabra' de los apellidos, ej:
    'ALVARADO MORAN' -> 'ALVARADO'
    """
    if not txt:
        return ""
    parts = [p for p in re.split(r"\s+", txt.strip()) if p]
    return parts[0] if parts else ""


def build_username_candidate(nombres: str, apellidos: str) -> str:
    """
    username base = primera letra del primer nombre + primer apellido
    ej. 'JUAN ALFREDO' + 'ALVARADO MORAN' -> 'jalvarado'
    """
    first_name = first_word(nombres)
    first_last = first_lastname_block(apellidos)

    if not first_name:
        first_initial = "u"
    else:
        first_initial = first_name[0]

    if not first_last:
        last_clean = "user"
    else:
        last_clean = first_last

    base = first_initial + last_clean
    base = strip_accents_and_symbols(base)
    if not base:
        base = "user"
    return base


def ensure_unique_username(cur, base_username: str, already_used: set) -> str:
    """
    Garantiza que el username final no exista ni en BD ni en este mismo batch.
    Estrategia:
      - probar base
      - luego base2, base3, base4, ...
    """
    candidate = base_username
    suffix = 2

    while True:
        if candidate in already_used:
            pass
        else:
            cur.execute(
                "SELECT top 11 FROM usuarios WHERE LOWER(username)=LOWER(?)  ",
                (candidate,)
            )
            row = cur.fetchone()
            if not row:
                already_used.add(candidate)
                return candidate

        candidate = f"{base_username}{suffix}"
        suffix += 1


def normalize_date(val: str) -> str | None:
    """
    Convierte '1998-06-24 00:00:00.000' -> '1998-06-24'.
    Si viene vacío o basura -> None.
    """
    if not val:
        return None
    v = val.strip()
    if not v:
        return None
    m = re.match(r"(\d{4}-\d{2}-\d{2})", v)
    if m:
        return m.group(1)
    return None