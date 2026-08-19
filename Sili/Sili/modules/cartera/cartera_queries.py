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

# ──────────────────────────────────────────────────────────────────────
# Vista "Días reales de pago" (dashboard por cliente)
# ──────────────────────────────────────────────────────────────────────
#
# Reutiliza SQL_SELECT_CARTERA_FACTURAS_BASE (mismos 3 tramos por factura)
# y agrupa por cliente. El "% fuera de plazo" se calcula solo sobre
# facturas Pagadas (no tiene sentido penalizar por incumplimiento a algo
# que todavía no se sabe si va a demorar); la "antigüedad prom. abiertas"
# es el promedio de días transcurridos (en vivo) de las facturas Abiertas
# de ese cliente — puede no haber ninguna, en cuyo caso queda NULL.

SQL_SELECT_ANIOS_DISPONIBLES = f"""
SELECT DISTINCT YEAR(fecha_factura) AS anio
FROM {TABLA_CARTERA_FACTURAS}
WHERE fecha_factura IS NOT NULL
ORDER BY anio DESC
"""

_RANKING_SELECT_COLUMNS = """
    cuenta,
    MAX(nombre_cliente) AS nombre_cliente,
    COUNT(*) AS num_facturas,
    SUM(CASE WHEN estado = 'Abierta' THEN 1 ELSE 0 END) AS num_abiertas,
    SUM(CASE WHEN estado = 'Pagada' THEN 1 ELSE 0 END) AS num_pagadas,
    SUM(importe_factura) AS total_facturado,
    SUM(CASE WHEN estado = 'Abierta' THEN saldo ELSE 0 END) AS saldo_pendiente,
    AVG(CAST(dias_guia_factura AS FLOAT)) AS prom_guia_factura,
    AVG(CAST(dias_factura_pago AS FLOAT)) AS prom_factura_pago,
    AVG(CAST(dias_totales_guia_pago AS FLOAT)) AS prom_ciclo_total,
    100.0 * SUM(CASE WHEN estado = 'Pagada' AND dias_factura_pago > ? THEN 1 ELSE 0 END)
        / NULLIF(SUM(CASE WHEN estado = 'Pagada' THEN 1 ELSE 0 END), 0) AS pct_fuera_plazo,
    AVG(CASE
            WHEN estado = 'Abierta'
                THEN CAST(DATEDIFF(day, fecha_factura, GETDATE()) AS FLOAT)
        END) AS antiguedad_prom_abiertas
"""


def sql_ranking_clientes(where_sql: str) -> str:
    """where_sql ya trae los filtros de año/mes/cuenta (o vacío)."""
    return f"""
        SELECT {_RANKING_SELECT_COLUMNS}
        FROM ({SQL_SELECT_CARTERA_FACTURAS_BASE}) f
        {where_sql}
        GROUP BY cuenta
        ORDER BY ISNULL(prom_factura_pago, -1) DESC
    """


def sql_cliente_metricas(where_sql: str) -> str:
    return f"""
        SELECT {_RANKING_SELECT_COLUMNS}
        FROM ({SQL_SELECT_CARTERA_FACTURAS_BASE}) f
        {where_sql}
        GROUP BY cuenta
    """


def sql_facturas_cliente(where_sql: str) -> str:
    return f"""
        SELECT
            doc_facturacion,
            referencia,
            num_documento_origen,
            fecha_factura,
            fecha_ultimo_pago,
            importe_factura,
            saldo,
            estado,
            dias_guia_factura,
            dias_factura_pago,
            dias_totales_guia_pago
        FROM ({SQL_SELECT_CARTERA_FACTURAS_BASE}) f
        {where_sql}
        ORDER BY fecha_factura DESC
    """
