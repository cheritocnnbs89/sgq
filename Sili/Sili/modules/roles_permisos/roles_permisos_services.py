# -*- coding: utf-8 -*-

from .roles_permisos_constants import ACCIONES, DEFAULT_ROLES, DEFAULT_OPCIONES
from . import roles_permisos_repository as repo


def seed_default_roles(conn):
    existing_roles = [row["nombre"] for row in repo.get_roles(conn)]
    for role_name in DEFAULT_ROLES:
        if role_name not in existing_roles:
            repo.get_or_create_role(conn, role_name)


def seed_default_opciones(conn):
    existing_opciones = {row["nombre"] for row in repo.get_opciones_nombre(conn)}
    for opcion_name in DEFAULT_OPCIONES:
        if opcion_name not in existing_opciones:
            repo.get_or_create_opcion(conn, opcion_name)


def import_legacy_permisos(conn):
    legacy_rows = repo.get_legacy_permisos(conn)
    if not legacy_rows:
        return

    for row in legacy_rows:
        role_row = repo.get_or_create_role(conn, row["rol"])
        opcion_row = repo.get_or_create_opcion(conn, row["opcion"])

        repo.upsert_rol_permiso_from_legacy(
            conn=conn,
            rol_id=role_row["id"],
            opcion_id=opcion_row["id"],
            ver=int(row["ver"] or 0),
            crear=int(row["crear"] or 0),
            editar=int(row["editar"] or 0),
            eliminar=int(row["eliminar"] or 0),
            exportar=int(row["exportar"] or 0),
            aprobar=int(row["aprobar"] or 0),
        )

    conn.commit()


def get_roles_list(conn):
    return [row["nombre"] for row in repo.get_roles(conn)]


def resolve_selected_role(conn, selected_role: str):
    selected_role = (selected_role or "").strip()

    seed_default_roles(conn)

    roles = get_roles_list(conn)
    if not roles:
        return None, [], ""

    if not selected_role:
        selected_role = roles[0]

    role_row = repo.get_role_by_name_case_insensitive(conn, selected_role)
    if not role_row:
        role_row = repo.get_or_create_role(conn, selected_role)

    roles = get_roles_list(conn)
    return role_row, roles, role_row["nombre"]


def build_permisos_dict(conn, rol_id: int):
    rows = repo.get_permisos_by_rol_id(conn, rol_id)

    permisos = {}
    for row in rows:
        permisos[row["opcion"]] = {
            "ver": bool(row["ver"]),
            "crear": bool(row["crear"]),
            "editar": bool(row["editar"]),
            "eliminar": bool(row["eliminar"]),
            "exportar": bool(row["exportar"]),
            "aprobar": bool(row["aprobar"]),
        }

    return permisos


def build_cambios_from_form(form, opciones_nombres):
    cambios = {}

    for opcion_name in opciones_nombres:
        cambios[opcion_name] = {accion: 0 for accion in ACCIONES}

    for key in form.keys():
        if key in ("save", "rol", "csrf_token"):
            continue

        for accion in ACCIONES:
            suffix = f"_{accion}"
            if key.endswith(suffix):
                opcion_name = key[:-len(suffix)]
                if opcion_name not in cambios:
                    cambios[opcion_name] = {a: 0 for a in ACCIONES}
                cambios[opcion_name][accion] = 1
                break

    return cambios


def save_role_permissions(conn, role_name: str, form):
    role_row = repo.get_or_create_role(conn, role_name)
    rol_id = role_row["id"]

    opciones_rows = repo.get_opciones(conn)
    opciones_nombres = [row["nombre"] for row in opciones_rows]

    cambios = build_cambios_from_form(form, opciones_nombres)

    repo.delete_roles_permisos_by_rol_id(conn, rol_id)

    for opcion_name, flags in cambios.items():
        opcion_row = repo.get_or_create_opcion(conn, opcion_name)

        repo.insert_rol_permiso(
            conn=conn,
            rol_id=rol_id,
            opcion_id=opcion_row["id"],
            ver=int(flags.get("ver", 0)),
            crear=int(flags.get("crear", 0)),
            editar=int(flags.get("editar", 0)),
            eliminar=int(flags.get("eliminar", 0)),
            exportar=int(flags.get("exportar", 0)),
            aprobar=int(flags.get("aprobar", 0)),
        )

    conn.commit()
    repo.sync_legacy_permisos(conn, role_name)