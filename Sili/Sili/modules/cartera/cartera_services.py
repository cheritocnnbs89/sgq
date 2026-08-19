# modules/cartera/cartera_services.py
# -*- coding: utf-8 -*-

from flask import request

from . import cartera_repository as repo
from .cartera_constants import DIAS_ALERTA_DEFAULT


def collect_cartera_filters():
    q = (request.args.get("q") or "").strip()
    estado = request.args.get("estado") or ""
    solo_demoradas = request.args.get("solo_demoradas") in ("1", "on", "true", "True")

    try:
        dias_umbral = int(request.args.get("dias_umbral") or DIAS_ALERTA_DEFAULT)
    except ValueError:
        dias_umbral = DIAS_ALERTA_DEFAULT

    return {
        "q": q,
        "estado": estado,
        "solo_demoradas": solo_demoradas,
        "dias_umbral": dias_umbral,
    }


def list_facturas():
    filters = collect_cartera_filters()
    rows = repo.list_facturas(filters)
    return rows, filters


def get_resumen():
    return repo.get_resumen()
