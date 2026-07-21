# modules/parametros_generales/parameters_constants.py
# -*- coding: utf-8 -*-

TABLA_PARAM_GROUPS = "param_groups"
TABLA_PARAM_VALUES = "param_values"

ACTIVE_PAGE_PARAMETROS_GENERALES = "parametros_generales"

TEMPLATE_PARAMETROS_GENERALES = "parametros_generales.html"
TEMPLATE_PARAMETRO_ITEMS = "parametro_items.html"
TEMPLATE_NUEVO_PARAMETRO = "nuevo_parametro.html"
TEMPLATE_EDITAR_PARAMETRO = "editar_parametro.html"
TEMPLATE_NUEVO_VALOR = "nuevo_valor.html"
TEMPLATE_EDITAR_VALOR = "editar_valor.html"
TEMPLATE_CARGA_MASIVA = "parametros_carga_masiva.html"

CSV_TEMPLATE_TEXT = "nombre,valor\nEjemplo 1,100\nEjemplo 2,200\n"
CSV_TEMPLATE_FILENAME = "plantilla_param_values.csv"
DEFAULT_CSV_SEPARATOR = ","

# Grupo especial: valores "padre" (frecuencias) usan lista fija en vez de texto libre.
GRUPO_OBLIGACIONES_FRECUENCIAS = "Obligaciones - Frecuencias"

FRECUENCIAS_VALOR_OPCIONES = [
    ("Mensual", "M:1"),
    ("Cada 2 meses", "M:2"),
    ("Cada 3 meses", "M:3"),
    ("Cada 6 meses", "M:6"),
    ("Anual", "A:1"),
    ("Cada 2 años", "A:2"),
    ("Cada 3 años", "A:3"),
    ("Cada 5 años", "A:5"),
    ("Sin recálculo (manual)", "NINGUNA"),
]