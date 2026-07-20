# modules/gastos_repo.py
from __future__ import annotations
from flask import request, session

from ..db import get_db
from ..config import TABLE_GASTOS
from .gastos_helpers import collect_gastos_filters
from .gastos_exports import _apply_role_scope_for_exports, _parse_ids_req, _fetch_allowed_ids_in_scope
 
def fetch_gastos_rows_for_report(conn, *, force_ids: list[int] | None = None):
    cur = conn.cursor()

    # 1) filtros base
    filtros, where, args, _ = collect_gastos_filters(request, session)

    # 2) scope igual que lista
    _apply_role_scope_for_exports(conn, where, args)

    # 3) refuerzos extra (tipo/gerente) — si en LISTA también existen, deben vivir aquí
    tipo = (request.args.get("tipo") or "").strip().lower()
    gerente_id_raw = (request.args.get("gerente_id") or "").strip()
    if gerente_id_raw.isdigit():
        where.append("COALESCE(g.gerente_id, 0) = ?")
        args.append(int(gerente_id_raw))

    if tipo in ("caja chica", "caja_chica"):
        where.append("COALESCE(g.es_caja_chica,0)=1")
    elif tipo in ("reembolso", "reembolso vendedor", "reembolso_vendedor"):
        where.append("COALESCE(g.reembolso_vendedor,0)=1")
    elif tipo in ("tarjeta","tarjeta_online","tarjeta_boletos"):
        where.append("COALESCE(g.es_caja_chica,0)=0")
        where.append("COALESCE(g.reembolso_vendedor,0)=0")

    # 4) ids visibles (si vienen)
    ids_req = force_ids if force_ids is not None else _parse_ids_req()

    if ids_req:
        ids_ok = _fetch_allowed_ids_in_scope(conn, ids_req)
        if not ids_ok:
            return filtros, []

        placeholders = ",".join("?" * len(ids_ok))
        # mantener orden visible:
        order_case = " ".join([f"WHEN ? THEN {i}" for i, _id in enumerate(ids_ok)])

        sql = f"""
            SELECT
                g.id,
                g.fecha,
                COALESCE(g.es_caja_chica,0) AS es_caja_chica,
                COALESCE(g.reembolso_vendedor,0) AS reembolso_vendedor,

                COALESCE(
                    NULLIF(TRIM(g.motivo), ''),
                    (SELECT d.motivo
                       FROM gastos_tarjeta_detalle d
                      WHERE d.gasto_id=g.id
                        AND TRIM(COALESCE(d.motivo,'')) <> ''
                      ORDER BY d.id
                      LIMIT 1)
                ) AS motivo_resuelto,

                COALESCE(
                    NULLIF(TRIM(g.centro_costo), ''),
                    (SELECT d.centro_costo
                       FROM gastos_tarjeta_detalle d
                      WHERE d.gasto_id=g.id
                        AND TRIM(COALESCE(d.centro_costo,'')) <> ''
                      ORDER BY d.id
                      LIMIT 1)
                ) AS centro_resuelto,

                g.ccb,
                g.con_soporte, g.sin_soporte, g.subtotal_factura,
                g.servicios_10, g.subtotal_sin_iva, g.iva, g.total_con_iva, g.archivo,
                COALESCE(t.nombre, g.proveedor) AS proveedor_nombre,
                COALESCE(g.ga_aprobado,0)    AS ga_aprobado,
                COALESCE(g.ga_aprobado_por,0) AS ga_aprobado_por,
                g.ga_aprobado_at             AS ga_aprobado_at,
                COALESCE(g.gg_aprobado,0)    AS gg_aprobado,
                COALESCE(g.gg_aprobado_por,0) AS gg_aprobado_por,
                g.gg_aprobado_at             AS gg_aprobado_at,
                COALESCE(g.gf_aprobado,0)    AS gf_aprobado,
                COALESCE(g.gf_aprobado_por,0) AS gf_aprobado_por,
                g.gf_aprobado_at             AS gf_aprobado_at,
                COALESCE(g.boletos_aereos,0) AS boletos_aereos
            FROM {TABLE_GASTOS} g
            LEFT JOIN terceros t ON t.id = g.proveedor_id
            WHERE g.id IN ({placeholders})
            ORDER BY CASE g.id {order_case} END
        """
        cur.execute(sql, list(ids_ok) + list(ids_ok))
        return filtros, cur.fetchall()

    # 5) sin ids: filtra normal
    sql = (
        f"""
        SELECT
            g.id,
            g.fecha,
            COALESCE(g.es_caja_chica,0) AS es_caja_chica,
            COALESCE(g.reembolso_vendedor,0) AS reembolso_vendedor,
            COALESCE(
                NULLIF(TRIM(g.motivo), ''),
                (SELECT d.motivo
                   FROM gastos_tarjeta_detalle d
                  WHERE d.gasto_id=g.id
                    AND TRIM(COALESCE(d.motivo,'')) <> ''
                  ORDER BY d.id
                  LIMIT 1)
            ) AS motivo_resuelto,
            COALESCE(
                NULLIF(TRIM(g.centro_costo), ''),
                (SELECT d.centro_costo
                   FROM gastos_tarjeta_detalle d
                  WHERE d.gasto_id=g.id
                    AND TRIM(COALESCE(d.centro_costo,'')) <> ''
                  ORDER BY d.id
                  LIMIT 1)
            ) AS centro_resuelto,
            g.ccb,
            g.con_soporte, g.sin_soporte, g.subtotal_factura,
            g.servicios_10, g.subtotal_sin_iva, g.iva, g.total_con_iva, g.archivo,
            COALESCE(t.nombre, g.proveedor) AS proveedor_nombre,
            COALESCE(g.ga_aprobado,0)    AS ga_aprobado,
            COALESCE(g.ga_aprobado_por,0) AS ga_aprobado_por,
            g.ga_aprobado_at             AS ga_aprobado_at,
            COALESCE(g.gg_aprobado,0)    AS gg_aprobado,
            COALESCE(g.gg_aprobado_por,0) AS gg_aprobado_por,
            g.gg_aprobado_at             AS gg_aprobado_at,
            COALESCE(g.gf_aprobado,0)    AS gf_aprobado,
            COALESCE(g.gf_aprobado_por,0) AS gf_aprobado_por,
            g.gf_aprobado_at             AS gf_aprobado_at,
            COALESCE(g.boletos_aereos,0) AS boletos_aereos
        FROM {TABLE_GASTOS} g
        LEFT JOIN terceros t ON t.id = g.proveedor_id
        """
        + (" WHERE " + " AND ".join(where) if where else "")
        + " ORDER BY date(g.fecha) DESC, g.id DESC"
    )
    cur.execute(sql, args)
    return filtros, cur.fetchall()