# modules/reclamos_seguros/reclamos_seguros_helpers.py
# -*- coding: utf-8 -*-
"""Configuración del módulo (coordinador + roles con visibilidad total), guardada en la
tabla genérica `configuracion` (clave/valor) -- mismo mecanismo que ya usa el módulo de
Gastos con Tarjeta para su coordinador (ver modules/gastos_helpers.py)."""
from __future__ import annotations

from modules.db import get_config_value, set_config_values
from .reclamos_seguros_constants import (
    CLAVE_COORDINADOR_ID, CLAVE_COORDINADOR_NOMBRE, CLAVE_ROLES_VISIBILIDAD_TOTAL,
    CLAVE_CUENTA_CORREO, CUENTA_CORREO_DEFAULT,
)


def get_coordinador_reclamos_seguros() -> dict | None:
    uid_raw = get_config_value(CLAVE_COORDINADOR_ID)
    if not uid_raw:
        return None
    try:
        uid = int(uid_raw)
    except (TypeError, ValueError):
        return None
    nombre = get_config_value(CLAVE_COORDINADOR_NOMBRE) or ""
    return {"usuario_id": uid, "usuario_nombre": nombre}


def set_coordinador_reclamos_seguros(usuario_id: int, usuario_nombre: str) -> None:
    set_config_values({
        CLAVE_COORDINADOR_ID: str(usuario_id),
        CLAVE_COORDINADOR_NOMBRE: usuario_nombre or "",
    })


def quitar_coordinador_reclamos_seguros() -> None:
    set_config_values({CLAVE_COORDINADOR_ID: "", CLAVE_COORDINADOR_NOMBRE: ""})


def es_coordinador_reclamos_seguros(usuario_id, rol=None) -> bool:
    if usuario_id is None:
        return False
    coord = get_coordinador_reclamos_seguros()
    return bool(coord) and int(coord["usuario_id"]) == int(usuario_id)


def get_roles_visibilidad_total() -> list[str]:
    """Lista de roles (en minúscula) con acceso a TODOS los casos, no solo los propios."""
    raw = get_config_value(CLAVE_ROLES_VISIBILIDAD_TOTAL) or ""
    return [r.strip().lower() for r in raw.split(",") if r.strip()]


def set_roles_visibilidad_total(roles: list[str]) -> None:
    valor = ",".join(sorted({(r or "").strip() for r in roles if (r or "").strip()}))
    set_config_values({CLAVE_ROLES_VISIBILIDAD_TOTAL: valor})


def rol_tiene_visibilidad_total(rol: str | None) -> bool:
    return (rol or "").strip().lower() in get_roles_visibilidad_total()


def get_cuenta_correo_reclamos_seguros() -> str:
    return get_config_value(CLAVE_CUENTA_CORREO) or CUENTA_CORREO_DEFAULT


def set_cuenta_correo_reclamos_seguros(email: str) -> None:
    set_config_values({CLAVE_CUENTA_CORREO: (email or "").strip()})
