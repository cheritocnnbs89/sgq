# modules/cartera/cartera_queries.py
# -*- coding: utf-8 -*-
#
# Primera versión: solo lectura sobre cartera_facturas (la tabla la llena
# cartera_calculo.calcular_y_guardar() del pipeline de automatización SAP,
# repo rutina/rutina/cartera/ — este módulo NO escribe ahí, solo consulta).
#
# "Días reales de pago" — la necesidad que originó esta vista: una factura
# se emite en guía primero, se refactura después (a veces días/semanas
# más tarde), y recién ahí empiezan a correr los N días de crédito
# pactados. Sumando eso, el tiempo REAL hasta que se cobra suele superar
# los días de crédito nominales. Se calculan 3 tramos:
#
#   dias_guia_factura      = fecha_factura - fecha_guia
#                             (retraso de refacturación)
#   dias_factura_pago      = fecha_ultimo_pago - fecha_factura si está
#                             Pagada; si está Abierta, HOY - fecha_factura
#                             (días transcurridos, corre en vivo)
#   dias_totales_guia_pago = COALESCE(fecha_ultimo_pago, HOY) - fecha_guia
#                             (el número que de verdad le importa a
#                             cobranza: desde que salió la mercadería
#                             hasta que se cobró, o lleva corriendo)
#
# Se envuelve en subquery porque SQL Server no permite referenciar un
# alias del SELECT en el WHERE de la misma consulta — así el repository
# puede filtrar directo por dias_totales_guia_pago sin repetir el CASE.

from .cartera_constants import TABLA_CARTERA_FACTURAS


SQL_SELECT_CARTERA_FACTURAS_BASE = f"""
SELECT * FROM (
    SELECT
        doc_facturacion,
        cuenta,
        nombre_cliente,
        tipo_doc_origen,
        referencia,
        num_documento_origen,
        fecha_factura,
        importe_factura,
        retencion_d7,
        estado,
        saldo,
        fecha_ultimo_pago,
        advertencia,
        fecha_guia,
        num_guia,
        factura_sunat,
        fecha_factura_sunat,
        alerta_fecha_sunat,
        DATEDIFF(day, fecha_guia, fecha_factura) AS dias_guia_factura,
        CASE
            WHEN estado = 'Pagada' AND fecha_ultimo_pago IS NOT NULL
                THEN DATEDIFF(day, fecha_factura, fecha_ultimo_pago)
            WHEN estado = 'Abierta'
                THEN DATEDIFF(day, fecha_factura, GETDATE())
        END AS dias_factura_pago,
        CASE
            WHEN fecha_guia IS NOT NULL
                THEN DATEDIFF(day, fecha_guia, COALESCE(fecha_ultimo_pago, GETDATE()))
        END AS dias_totales_guia_pago
    FROM {TABLA_CARTERA_FACTURAS}
) AS f
"""

SQL_SELECT_CARTERA_RESUMEN = f"""
SELECT
    COUNT(*) AS total_facturas,
    SUM(CASE WHEN estado = 'Abierta' THEN 1 ELSE 0 END) AS total_abiertas,
    SUM(CASE WHEN estado = 'Pagada' THEN 1 ELSE 0 END) AS total_pagadas,
    SUM(CASE WHEN estado = 'Abierta' THEN saldo ELSE 0 END) AS saldo_pendiente
FROM {TABLA_CARTERA_FACTURAS}
"""
