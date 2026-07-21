# modules/gastos_avance_helper.py
from __future__ import annotations

from datetime import date, datetime
from typing import List, Dict, Tuple

from ..db import get_db
from ..config import TABLE_GASTOS
from . import gastos_helpers as gh


PRIV_ROLES = {
    'admin', 'gerente financiero', 'gerente general', 'coordinador',
    'gerente', 'gerente de área', 'gerente de area'
}


def _rol(session) -> str:
    return (session.get('rol') or '').strip().lower()


def _is_privileged(session) -> bool:
    r = _rol(session)
    return r in {x.lower() for x in PRIV_ROLES}


def _current_uid(session):
    uid = session.get('usuario_id') or session.get('user_id') or session.get('uid')
    try:
        return int(uid)
    except (TypeError, ValueError):
        return None


def _months_between(desde: str, hasta: str) -> List[str]:
    """YYYY-MM-DD → lista YYYY-MM (inclusive)."""
    y1, m1, _ = map(int, desde.split('-'))
    y2, m2, _ = map(int, hasta.split('-'))
    ym = []
    y, m = y1, m1
    while (y < y2) or (y == y2 and m <= m2):
        ym.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return ym


def _pendiente_clause_por_rol(rol: str) -> str:
    """
    Devuelve cláusula SQL para 'pendiente de aprobación' según el rol.
    Siempre exige que NO tenga Doc. SAP.
    """
    base = "(g.sap_contabilizacion IS NULL OR TRIM(g.sap_contabilizacion)='')"
    rol = (rol or '').strip().lower()

    if rol in ('gerente', 'gerente de área', 'gerente de area'):
        # GA: puede aprobar sólo si nadie aprobó antes
        return base + " AND COALESCE(g.ga_aprobado,0)=0 AND COALESCE(g.gg_aprobado,0)=0 AND COALESCE(g.gf_aprobado,0)=0"
    elif rol == 'gerente financiero':
        # GF: pendiente si GG no aprobó y GF no aprobado
        return base + " AND COALESCE(g.gg_aprobado,0)=0 AND COALESCE(g.gf_aprobado,0)=0"
    elif rol == 'gerente general' or rol == 'admin':
        # GG: pendiente si GG no aprobado (independiente de GA/GF)
        return base + " AND COALESCE(g.gg_aprobado,0)=0"
    else:
        # Otros (colaboradores/coordinador): mostramos pendientes según cadena general
        # (si quieres 0 para no privilegiados, reemplaza por "1=0")
        return base + " AND COALESCE(g.gg_aprobado,0)=0"


def get_monthly_ccb_progress(request, session) -> dict:
    """
    Calcula:
      - 'ingresado' mensual: SUM(total_con_iva)
      - 'pendiente_ccb' mensual: SUM(total_con_iva) con ccb=1 y pendiente segun rol
    Respeta:
      - Rango de fechas (?desde, ?hasta) via gh.rango_fechas_desde_request()
      - Si NO privilegiado, limita a g.usuario_id = actual
      - Si rol es GA, filtra por su departamento
    """
    # Rango
    desde, hasta = gh.rango_fechas_desde_request()

    rol = _rol(session)
    uid = _current_uid(session)
    privileged = _is_privileged(session)

    # ¿depto del GA?
    dep_id = None
    conn = get_db()
    cur = conn.cursor()
    if rol in ('gerente', 'gerente de área', 'gerente de area') and uid:
        try:
            cur.execute("SELECT departamento_id FROM usuarios WHERE id=?", (uid,))
            row = cur.fetchone()
            dep_id = row['departamento_id'] if row else None
        except Exception:
            dep_id = None

    # WHERE base (fechas)
    where_base = ["date(g.fecha) BETWEEN date(?) AND date(?)"]
    args_base  = [desde, hasta]

    # Restricción por usuario no privilegiado
    if not privileged: 
        where_base.append("g.usuario_id = ?")
        args_base.append(uid or -1)

    # Restricción por departamento si es GA
    join_u = ""
    if dep_id is not None:
        join_u = "LEFT JOIN usuarios u ON u.id = g.usuario_id"
        where_base.append("u.departamento_id = ?")
        args_base.append(dep_id)

    # ---------- Serie 1: Ingresado ----------
    sql_ing = f"""
        SELECT strftime('%Y-%m', g.fecha) AS ym,
               COALESCE(SUM(g.total_con_iva), 0) AS total
        FROM {TABLE_GASTOS} g
        {join_u}
        WHERE {" AND ".join(where_base)}
        GROUP BY ym
        ORDER BY ym
    """
    cur.execute(sql_ing, args_base)
    rows_ing = {row['ym']: float(row['total'] or 0) for row in cur.fetchall()}

    # ---------- Serie 2: Pendiente CCB ----------
    pend_clause = _pendiente_clause_por_rol(rol)
    where_pend = where_base + [pend_clause, "COALESCE(g.ccb,0)=1"]
    sql_pen = f"""
        SELECT strftime('%Y-%m', g.fecha) AS ym,
               COALESCE(SUM(g.total_con_iva), 0) AS total
        FROM {TABLE_GASTOS} g
        {join_u}
        WHERE {" AND ".join(where_pend)}
        GROUP BY ym
        ORDER BY ym
    """
    cur.execute(sql_pen, args_base)
    rows_pen = {row['ym']: float(row['total'] or 0) for row in cur.fetchall()}

    conn.close()

    # Linea de tiempo de meses completa
    labels = _months_between(desde, hasta)

    ingresado = [round(rows_ing.get(m, 0.0), 2) for m in labels]
    pendiente = [round(rows_pen.get(m, 0.0), 2) for m in labels]
    porc = [round((pendiente[i] * 100.0 / ingresado[i]), 2) if ingresado[i] else 0.0
            for i in range(len(labels))]

    # Totales para KPI rápidos (opcional)
    kpi_ing = round(sum(ingresado), 2)
    kpi_pen = round(sum(pendiente), 2)
    kpi_pct = round((kpi_pen * 100.0 / kpi_ing), 2) if kpi_ing else 0.0

    return dict(
        desde=desde, hasta=hasta,
        labels=labels,
        serie_ingresado=ingresado,
        serie_pendiente=pendiente,
        serie_porc=porc,
        kpi_ingresado=kpi_ing,
        kpi_pendiente=kpi_pen,
        kpi_pct=kpi_pct
    )
