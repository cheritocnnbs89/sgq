# modules/parametros_generales/parameters_services.py
# -*- coding: utf-8 -*-

from __future__ import annotations

import csv
import io

from .parameters_security import (
    normalize_required_text,
    normalize_csv_separator,
    is_duplicate_error_message,
)
from . import parameters_repository as repo


def _to_int_or_none(value):
    value = (value or "").strip()
    return int(value) if value.isdigit() else None


def _to_int_or_default(value, default=1):
    value = (value or "").strip()
    return int(value) if value.lstrip("-").isdigit() else default


def _activo_to_int(value):
    return 1 if str(value or "").strip() == "1" else 0


def listar_grupos_y_valores():
    repo.ensure_param_tables()
    grupos = repo.fetch_all_groups()
    valores = repo.fetch_all_values()
    return grupos, valores


def obtener_grupo_y_items(group_id: int):
    repo.ensure_param_tables()

    grupo = repo.fetch_group_by_id(group_id)
    if not grupo:
        return None, None

    items = repo.fetch_values_by_group_id(group_id)
    return grupo, items


def crear_grupo(nombre_raw: str):
    repo.ensure_param_tables()

    nombre = normalize_required_text(nombre_raw)
    if not nombre:
        return {
            "ok": False,
            "flash": ("El nombre del parámetro es obligatorio.", "warning"),
        }

    try:
        repo.insert_group(nombre)
        return {
            "ok": True,
            "flash": ("Parámetro (grupo) creado correctamente.", "success"),
        }
    except Exception as exc:
        repo.rollback()

        if is_duplicate_error_message(exc):
            return {
                "ok": False,
                "flash": ("Ya existe un parámetro con ese nombre.", "danger"),
            }

        return {
            "ok": False,
            "flash": (f"No se pudo crear el parámetro: {exc}", "danger"),
        }


def editar_grupo(group_id: int, nombre_raw: str):
    repo.ensure_param_tables()

    grupo = repo.fetch_group_by_id(group_id)
    if not grupo:
        return {
            "ok": False,
            "not_found": True,
            "flash": ("Grupo de parámetros no encontrado.", "warning"),
        }

    nuevo_nombre = normalize_required_text(nombre_raw)
    if not nuevo_nombre:
        return {
            "ok": False,
            "flash": ("El nombre es obligatorio.", "warning"),
        }

    try:
        repo.update_group(group_id, nuevo_nombre)
        return {
            "ok": True,
            "flash": ("Grupo actualizado.", "success"),
        }
    except Exception:
        repo.rollback()
        return {
            "ok": False,
            "flash": ("No se pudo actualizar (¿nombre duplicado?).", "danger"),
        }


def eliminar_grupo(group_id: int):
    repo.ensure_param_tables()

    try:
        repo.delete_group(group_id)
        return {
            "ok": True,
            "flash": ("Grupo eliminado.", "success"),
        }
    except Exception:
        repo.rollback()
        return {
            "ok": False,
            "flash": ("No se pudo eliminar el grupo.", "danger"),
        }


def obtener_grupo(group_id: int):
    repo.ensure_param_tables()
    return repo.fetch_group_by_id(group_id)


def crear_valor(
    group_id: int,
    nombre_raw: str,
    valor_raw: str,
    parent_id_raw: str = None,
    activo_raw: str = None,
    orden_raw: str = None,
):
    repo.ensure_param_tables()

    grupo = repo.fetch_group_by_id(group_id)
    if not grupo:
        return {
            "ok": False,
            "not_found": True,
            "flash": ("Grupo no encontrado.", "warning"),
        }

    nombre = normalize_required_text(nombre_raw)
    valor = normalize_required_text(valor_raw)
    parent_id = _to_int_or_none(parent_id_raw)
    activo = _activo_to_int(activo_raw)
    orden = _to_int_or_default(orden_raw, default=1)

    if not nombre:
        return {
            "ok": False,
            "grupo": grupo,
            "flash": ("El nombre es obligatorio.", "warning"),
        }

    try:
        repo.insert_value(group_id, nombre, valor, parent_id, activo, orden)
        return {
            "ok": True,
            "grupo": grupo,
            "flash": ("Valor creado.", "success"),
        }
    except Exception as exc:
        repo.rollback()
        return {
            "ok": False,
            "grupo": grupo,
            "flash": (f"No se pudo crear el valor: {exc}", "danger"),
        }


def obtener_item(group_id: int, item_id: int):
    repo.ensure_param_tables()
    return repo.fetch_value_with_group(item_id, group_id)


def editar_valor(
    group_id: int,
    item_id: int,
    nombre_raw: str,
    valor_raw: str,
    parent_id_raw: str = None,
    activo_raw: str = None,
    orden_raw: str = None,
):
    repo.ensure_param_tables()

    item = repo.fetch_value_with_group(item_id, group_id)
    if not item:
        return {
            "ok": False,
            "not_found": True,
            "flash": ("Valor no encontrado.", "warning"),
        }

    nombre = normalize_required_text(nombre_raw)
    valor = normalize_required_text(valor_raw)
    parent_id = _to_int_or_none(parent_id_raw)
    activo = _activo_to_int(activo_raw)
    orden = _to_int_or_default(orden_raw, default=1)

    if not nombre:
        return {
            "ok": False,
            "item": item,
            "flash": ("El nombre es obligatorio.", "warning"),
        }

    try:
        repo.update_value(item_id, group_id, nombre, valor, parent_id, activo, orden)
        return {
            "ok": True,
            "item": item,
            "flash": ("Valor actualizado.", "success"),
        }
    except Exception as exc:
        repo.rollback()
        return {
            "ok": False,
            "item": item,
            "flash": (f"No se pudo actualizar: {exc}", "danger"),
        }


def eliminar_valor(group_id: int, item_id: int):
    repo.ensure_param_tables()

    try:
        repo.delete_value(item_id, group_id)
        return {
            "ok": True,
            "flash": ("Valor eliminado.", "success"),
        }
    except Exception:
        repo.rollback()
        return {
            "ok": False,
            "flash": ("No se pudo eliminar.", "danger"),
        }


def listar_grupos_para_carga():
    repo.ensure_param_tables()
    return [dict(r) for r in repo.fetch_all_groups()]


def procesar_carga_masiva_csv(group_id_raw: str, has_header: bool, sep_raw: str, file_storage):
    repo.ensure_param_tables()

    if not str(group_id_raw).isdigit():
        return {
            "ok": False,
            "flash": ("Seleccione un grupo válido.", "danger"),
            "group_id": None,
        }

    group_id = int(group_id_raw)

    if not file_storage or not file_storage.filename:
        return {
            "ok": False,
            "flash": ("Adjunte un archivo CSV.", "danger"),
            "group_id": group_id,
        }

    sep = normalize_csv_separator(sep_raw)

    try:
        raw = file_storage.stream.read()
        text = raw.decode("utf-8-sig", errors="ignore")
        reader = csv.reader(io.StringIO(text), delimiter=sep)
    except Exception as exc:
        return {
            "ok": False,
            "flash": (f"No se pudo leer el CSV: {exc}", "danger"),
            "group_id": group_id,
        }

    rows_to_insert = []
    idx = 0

    try:
        if has_header:
            next(reader, None)

        for idx, row in enumerate(reader, start=1):
            if not row:
                continue

            nombre = (row[0] if len(row) > 0 else "").strip()
            valor = (row[1] if len(row) > 1 else None)
            valor = (valor.strip() if isinstance(valor, str) else valor)

            if not nombre:
                continue

            rows_to_insert.append((group_id, nombre, valor, None, 1, 0))
    except Exception as exc:
        return {
            "ok": False,
            "flash": (f"Fila {idx}: {exc}", "danger"),
            "group_id": group_id,
        }

    if not rows_to_insert:
        return {
            "ok": False,
            "flash": ("El archivo no contenía filas válidas.", "warning"),
            "group_id": group_id,
        }

    existentes = {
        (r["nombre"] or "").lower(): True
        for r in repo.fetch_existing_value_names_by_group_id(group_id)
    }

    rows_to_insert = [
        r for r in rows_to_insert
        if r[1].lower() not in existentes
    ]

    if not rows_to_insert:
        return {
            "ok": False,
            "all_duplicates": True,
            "flash": ("Todos los nombres ya existían para ese grupo; no se importó nada.", "info"),
            "group_id": group_id,
        }

    try:
        repo.insert_many_values(rows_to_insert)
        return {
            "ok": True,
            "flash": (f"Importadas {len(rows_to_insert)} filas.", "success"),
            "group_id": group_id,
        }
    except Exception as exc:
        repo.rollback()
        return {
            "ok": False,
            "flash": (f"No se pudo importar: {exc}", "danger"),
            "group_id": group_id,
        }