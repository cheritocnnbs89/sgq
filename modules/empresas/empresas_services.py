# modules/empresas/empresas_services.py
# -*- coding: utf-8 -*-

from flask import request

from . import empresas_repository as repo


def collect_empresas_filters():
    q = (request.args.get("q") or "").strip()
    activo = request.args.get("activo")

    if activo not in ("0", "1", None, ""):
        activo = None

    return {
        "q": q,
        "activo": activo,
    }


def normalize_empresa_form(form):
    get_value = lambda k: (form.get(k) or "").strip()

    return {
        "razon_social": get_value("razon_social"),
        "ruc": get_value("ruc"),
        "direccion": get_value("direccion"),
        "telefono": get_value("telefono"),
        "email": get_value("email").lower(),
        "sitio_web": get_value("sitio_web"),
        "rep_nombre": get_value("rep_nombre"),
        "rep_identificacion": get_value("rep_identificacion"),
        "rep_nacionalidad": get_value("rep_nacionalidad").upper(),
        "usuario_sap": get_value("usuario_sap").upper(),
        "activo": 1 if (form.get("activo") in ("1", "on", "true", "True")) else 0,
    }


def validate_empresa_data(data):
    if not data["razon_social"] or not data["ruc"]:
        return False, "Razón social y RUC son obligatorios."

    if data.get("rep_nacionalidad") and len(data["rep_nacionalidad"]) > 20:
        return False, "La Sociedad SAP no debe superar 20 caracteres."

    if data.get("usuario_sap") and len(data["usuario_sap"]) > 100:
        return False, "El Usuario SAP no debe superar 100 caracteres."

    return True, None


def list_empresas():
    filters = collect_empresas_filters()
    rows = repo.list_empresas(filters)
    return rows, filters


def get_empresa(empresa_id):
    return repo.get_empresa_by_id(empresa_id)


def create_empresa(data):
    return repo.insert_empresa(data)


def update_empresa(empresa_id, data):
    return repo.update_empresa(empresa_id, data)


def delete_empresa(empresa_id):
    repo.delete_empresa(empresa_id)