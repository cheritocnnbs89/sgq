# modules/gastos_dashboard_helper.py
from __future__ import annotations
from datetime import date, datetime
from calendar import monthrange
from flask import request, session
from .db import get_db
from .config import TABLE_GASTOS

PRIV_ROLES = {
    'admin', 'gerente financiero', 'gerente general', 'coordinador',
    'gerente', 'gerente de área', 'gerente de area'
}

def _parse_ymd(s: str) -> date | None: 
    s = (s or '').strip()
    if not s:
        return None
    try:
        return datetime.strptime(s[:10], '%Y-%m-%d').date()
    except Exception:
        return None

def _default_range_last_6_months() -> tuple[str, str]:
    today = date.today()
    # primer día del mes actual - 5 meses
    y, m = today.year, today.month
    m6 = m - 5
    y6 = y
    while m6 <= 0:
        m6 += 12
        y6 -= 1
    d1 = date(y6, m6, 1)
    d2 = today
    return d1.isoformat(), d2.isoformat()

def _role_name(session) -> str:
    return (session.get('rol') or '').strip().lower()

def _is_privileged(session) -> bool:
    return _role_name(session) in {r.lower() for r in PRIV_ROLES}

def _current_user_id(session) -> int | None:
    uid = session.get('usuario_id') or session.get('user_id') or session.get('uid')
    try:
        return int(uid)
    except (TypeError, ValueError):
        return None

def _get_user_dep(conn, uid: int | None):
    if not uid:
        return None
    cur = conn.cursor()
    cur.execute("SELECT departamento_id FROM usuarios WHERE id=?", (uid,))
    row = cur.fetchone()
    return row['departamento_id'] if row else None

def _pendiente_clause_for_role(role: str) -> str:
    # Siempre sin Doc. SAP y con CCB
    base = "(COALESCE(g.ccb,0)=1) AND (g.sap_contabilizacion IS NULL OR TRIM(g.sap_contabilizacion)='')"
    role = role.lower()
    if role in ('gerente', 'gerente de área', 'gerente de area'):
        # GA: sólo si nadie aprobó aún
        return base + " AND COALESCE(g.ga_aprobado,0)=0 AND COALESCE(g.gg_aprobado,0)=0 AND COALESCE(g.gf_aprobado,0)=0"
    elif role == 'gerente financiero':
        # GF: si GG no aprobó y GF no aprobado
        return base + " AND COALESCE(g.gg_aprobado,0)=0 AND COALESCE(g.gf_aprobado,0)=0"
    elif role == 'gerente general' or role == 'admin':
        # GG (y admin viendo pendientes de GG): si GG no aprobó
        return base + " AND COALESCE(g.gg_aprobado,0)=0"
    else:
        # Otros roles: no tienen “pendientes” propios
        return "1=0"

def get_monthly_ccb_progress(req, session):
    """
    Devuelve el contexto para dashboard.html:
      - kpi_ingresado, kpi_pendiente, kpi_pct
      - n_registros, n_pendientes
      - labels (YYYY-MM), serie_ingresado, serie_pendiente
      - desde, hasta (para inputs)
    Respeta visibilidad: si no es privilegiado -> sólo sus registros; si es GA -> filtra por su departamento.
    """
    desde = _parse_ymd(req.args.get('desde'))
    hasta = _parse_ymd(req.args.get('hasta'))
    if not desde or not hasta:
        d1, d2 = _default_range_last_6_months()
        desde = _parse_ymd(d1)
        hasta = _parse_ymd(d2)

    desde_s, hasta_s = desde.isoformat(), hasta.isoformat()

    conn = get_db(); cur = conn.cursor()
    role = _role_name(session)
    is_priv = _is_privileged(session)
    uid = _current_user_id(session)
    my_dep = _get_user_dep(conn, uid)

    # Filtros de visibilidad
    vis_where = []
    vis_args = []

    if not is_priv:
        vis_where.append("g.usuario_id = ?")
        vis_args.append(uid or -1)

    if role in ('gerente', 'gerente de área', 'gerente de area') and my_dep is not None:
        vis_where.append("u.departamento_id = ?")
        vis_args.append(my_dep)

    # --------- KPIs ingreso (CCB=1) ----------
    where_ing = ["date(g.fecha) BETWEEN date(?) AND date(?)", "COALESCE(g.ccb,0)=1"]
    args_ing = [desde_s, hasta_s] + vis_args

    sql_ing = f"""
        SELECT
          COALESCE(SUM(g.total_con_iva),0) AS total_ccb,
          COUNT(*) AS n
        FROM {TABLE_GASTOS} g
        LEFT JOIN usuarios u ON u.id = g.usuario_id
        WHERE {' AND '.join(where_ing + vis_where)}
    """
    cur.execute(sql_ing, args_ing)
    r_ing = cur.fetchone() or {'total_ccb': 0, 'n': 0}
    total_ing = float(r_ing['total_ccb'] or 0)
    n_ing = int(r_ing['n'] or 0)

    # --------- KPIs pendientes (según rol) ----------
    pend_clause = _pendiente_clause_for_role(role)
    where_pen = ["date(g.fecha) BETWEEN date(?) AND date(?)", pend_clause]
    args_pen = [desde_s, hasta_s] + vis_args

    sql_pen = f"""
        SELECT
          COALESCE(SUM(g.total_con_iva),0) AS total_pend,
          COUNT(*) AS n
        FROM {TABLE_GASTOS} g
        LEFT JOIN usuarios u ON u.id = g.usuario_id
        WHERE {' AND '.join(where_pen + vis_where)}
    """
    cur.execute(sql_pen, args_pen)
    r_pen = cur.fetchone() or {'total_pend': 0, 'n': 0}
    total_pen = float(r_pen['total_pend'] or 0)
    n_pen = int(r_pen['n'] or 0)

    # --------- Series mensuales ----------
    # (Ingresado CCB)
    sql_s_ing = f"""
      SELECT strftime('%Y-%m', g.fecha) AS m, COALESCE(SUM(g.total_con_iva),0) AS total
      FROM {TABLE_GASTOS} g
      LEFT JOIN usuarios u ON u.id = g.usuario_id
      WHERE date(g.fecha) BETWEEN date(?) AND date(?)
        AND COALESCE(g.ccb,0)=1
        {(' AND ' + ' AND '.join(vis_where)) if vis_where else ''}
      GROUP BY strftime('%Y-%m', g.fecha)
      ORDER BY m
    """
    cur.execute(sql_s_ing, [desde_s, hasta_s] + vis_args)
    rows_ing = {row['m']: float(row['total'] or 0) for row in cur.fetchall()}

    # (Pendiente CCB por rol)
    sql_s_pen = f"""
      SELECT strftime('%Y-%m', g.fecha) AS m, COALESCE(SUM(g.total_con_iva),0) AS total
      FROM {TABLE_GASTOS} g
      LEFT JOIN usuarios u ON u.id = g.usuario_id
      WHERE date(g.fecha) BETWEEN date(?) AND date(?)
        AND {pend_clause}
        {(' AND ' + ' AND '.join(vis_where)) if vis_where else ''}
      GROUP BY strftime('%Y-%m', g.fecha)
      ORDER BY m
    """
    cur.execute(sql_s_pen, [desde_s, hasta_s] + vis_args)
    rows_pen = {row['m']: float(row['total'] or 0) for row in cur.fetchall()}

    conn.close()

    # Construir el eje de meses continuo entre desde..hasta
    labels = []
    ym = (desde.year, desde.month)
    end_ym = (hasta.year, hasta.month)
    y, m = ym
    while True:
        labels.append(f"{y:04d}-{m:02d}")
        if (y, m) == end_ym:
            break
        m += 1
        if m > 12:
            m = 1; y += 1

    serie_ing = [rows_ing.get(k, 0.0) for k in labels]
    serie_pen = [rows_pen.get(k, 0.0) for k in labels]

    pct = (total_pen / total_ing * 100.0) if total_ing > 0 else 0.0

    return dict(
        # Fechas para inputs
        desde=desde_s, hasta=hasta_s,
        # KPI cards
        kpi_ingresado=round(total_ing, 2),
        kpi_pendiente=round(total_pen, 2),
        kpi_pct=round(pct, 2),
        n_registros=n_ing, n_pendientes=n_pen,
        # Series
        labels=labels,
        serie_ingresado=serie_ing,
        serie_pendiente=serie_pen,
    )
