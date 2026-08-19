# modules/cartera/cartera_constants.py
# -*- coding: utf-8 -*-

TABLA_CARTERA_FACTURAS = "cartera_facturas"
TABLA_CARTERA_COBROS_HIST = "cartera_cobros_hist"

ACTIVE_KEY = "cartera"
PERM_BASE = "cartera"   # cartera.ver  (primera versión: solo lectura)

# Umbral por defecto para marcar una factura como "días reales" alto.
# Pensado como el corte típico de crédito (30 días) — a futuro esto debería
# salir de una condición de pago por cliente, no de una constante fija.
DIAS_ALERTA_DEFAULT = 30

MESES = [
    (1, "Enero"), (2, "Febrero"), (3, "Marzo"), (4, "Abril"),
    (5, "Mayo"), (6, "Junio"), (7, "Julio"), (8, "Agosto"),
    (9, "Septiembre"), (10, "Octubre"), (11, "Noviembre"), (12, "Diciembre"),
]
