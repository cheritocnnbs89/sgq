# modules/cartera/cartera_services.py
# -*- coding: utf-8 -*-

from datetime import date

from flask import request

from . import cartera_repository as repo
from .cartera_constants import DIAS_ALERTA_DEFAULT, MESES


def collect_cartera_filters():
    anio_raw = (request.args.get("anio") or "").strip()
    mes_raw = (request.args.get("mes") or "").strip()
    cuenta = (request.args.get("cuenta") or "").strip()
    q = (request.args.get("q") or "").strip()

    try:
        anio = int(anio_raw) if anio_raw else None
    except ValueError:
        anio = None

    try:
        mes = int(mes_raw) if mes_raw else None
    except ValueError:
        mes = None

    return {
        "anio": anio,
        "mes": mes,
        "cuenta": cuenta,
        "q": q,
        "dias_umbral": DIAS_ALERTA_DEFAULT,
    }


def get_dashboard_data():
    """Arma todo lo que necesita la vista "Días reales de pago":
    - ranking de clientes (ordenado por mayor desviación primero)
    - métricas + línea de tiempo del cliente seleccionado (el de la
      URL ?cuenta=, o si no viene ninguno, el primero del ranking —
      el de peor desviación, que es el que más le importa a cobranza)
    """
    filters = collect_cartera_filters()

    ranking = repo.list_ranking_clientes(filters)
    anios_disponibles = repo.list_anios_disponibles()

    cuenta_sel = filters["cuenta"]
    if not cuenta_sel and ranking:
        cuenta_sel = ranking[0]["cuenta"]

    cliente = None
    facturas_cliente = []
    if cuenta_sel:
        cliente = repo.get_cliente_metricas(cuenta_sel, filters)
        facturas_cliente = repo.list_facturas_cliente(cuenta_sel, filters)

    return {
        "filters": filters,
        "cuenta_sel": cuenta_sel,
        "ranking": ranking,
        "anios_disponibles": anios_disponibles,
        "cliente": cliente,
        "facturas_cliente": facturas_cliente,
        "credito_pactado": DIAS_ALERTA_DEFAULT,
        "hoy": date.today(),
        "meses": MESES,
        "mes_nombre": dict(MESES).get(filters["mes"]),
    }


def get_factura_cobros(doc_facturacion):
    """Detalle de cobros para el acordeón de una factura en la línea de
    tiempo. El total abonado sale de cartera_facturas (ya calculado por
    el pipeline); las filas de detalle son las de cartera_cobros_hist
    tal cual, para trazabilidad — ver nota en cartera_queries.py sobre
    por qué no se resuman acá."""
    resumen = repo.get_factura_resumen(doc_facturacion)
    cobros = repo.list_cobros_factura(doc_facturacion)
    return resumen, cobros
