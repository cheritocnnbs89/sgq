# modules/gastos/gastos_service.py

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from .gastos_repository import (
    get_gasto_by_id,
    search_facturas_xml,
)
from .gastos_sap_service import enviar_gasto_sap, enviar_gasto_sap_masivo
from .gastos_security import can_view_all
from .gastos_repo import fetch_gastos_rows_for_report
from .gastos_helpers import collect_gastos_filters, collect_gastos_pendientes_aprobacion_filters



def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    if isinstance(row, sqlite3.Row):
        return dict(row)
    if isinstance(row, dict):
        return row
    try:
        return dict(row)
    except Exception:
        return {}


def _rows_to_dicts(rows) -> list[dict]:
    out = []
    for r in rows or []:
        out.append(_row_to_dict(r))
    return out


def _to_float(value: Any) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _get_role_info(session_data: dict) -> tuple[str, int | None, bool]:
    role_name = (session_data.get("rol") or "").lower().strip()
    uid = session_data.get("usuario_id") or session_data.get("user_id")
    is_admin = role_name == "admin" or bool(session_data.get("is_admin"))
    try:
        uid = int(uid) if uid is not None else None
    except Exception:
        uid = None
    return role_name, uid, is_admin


def get_proveedores_activos(conn) -> list[dict]:
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, nombre, identificacion
            FROM terceros
            WHERE UPPER(TRIM(tipo))='P'
              AND COALESCE(activo,1)=1
            ORDER BY nombre
        """)
        return _rows_to_dicts(cur.fetchall())
    except Exception:
        return []


def get_usuarios_visibles(conn, rows: list[dict]) -> list[dict]:
    seen = set()
    out: list[dict] = []
    for d in rows:
        try:
            u_id = int(d.get("usuario_id") or 0)
        except Exception:
            u_id = 0
        u_nm = (d.get("usuario_username") or "").strip()
        if u_id and u_id not in seen:
            seen.add(u_id)
            out.append({"id": u_id, "username": u_nm})
    out.sort(key=lambda x: (x["username"] or "").lower())
    return out


def get_gerentes_visibles(conn, rows: list[dict]) -> list[dict]:
    seen = set()
    out: list[dict] = []
    for d in rows:
        try:
            gid = int(d.get("gerente_id") or 0)
        except Exception:
            gid = 0
        gnm = (d.get("gerente_nombre") or "").strip()
        if gid and gid not in seen:
            seen.add(gid)
            out.append({"id": gid, "nombre": gnm})
    out.sort(key=lambda x: (x["nombre"] or "").lower())
    return out


def build_totales(rows: list[dict]) -> dict:
    keys = (
        "con_soporte",
        "sin_soporte",
        "subtotal_factura",
        "servicios_10",
        "subtotal_sin_iva",
        "iva",
        "total_con_iva",
    )
    totales = {k: 0.0 for k in keys}
    for r in rows:
        for k in keys:
            totales[k] += _to_float(r.get(k))
    return totales


def _build_base_where_from_request(request_args: dict, *, session_data: dict | None = None) -> tuple[list[str], list[Any], dict]:
    role_name, uid, is_admin = _get_role_info(session_data or {})

    filtros = {
        "desde": (request_args.get("desde") or "").strip(),
        "hasta": (request_args.get("hasta") or "").strip(),
        "proveedor_id": (request_args.get("proveedor_id") or "").strip(),
        "proveedor": (request_args.get("proveedor") or "").strip(),
        "usuario_id": (request_args.get("usuario_id") or "").strip(),
        "gerente_id": (request_args.get("gerente_id") or "").strip(),
        "tipo": (request_args.get("tipo") or "").strip(),
        "descripcion": (request_args.get("descripcion") or "").strip(),
        "ccb": (request_args.get("ccb") or "").strip(),
        "pendientes": (request_args.get("pendientes") or "").strip(),
    }

    where = ["COALESCE(g.inactivo,0)=0"]
    args: list[Any] = []

    if filtros["desde"]:
        where.append("date(COALESCE(g.fecha, g.created_at)) >= date(?)")
        args.append(filtros["desde"])

    if filtros["hasta"]:
        where.append("date(COALESCE(g.fecha, g.created_at)) <= date(?)")
        args.append(filtros["hasta"])

    if filtros["proveedor_id"].isdigit():
        where.append("g.proveedor_id = ?")
        args.append(int(filtros["proveedor_id"]))

    if filtros["usuario_id"].isdigit():
        where.append("g.usuario_id = ?")
        args.append(int(filtros["usuario_id"]))

    if filtros["gerente_id"].isdigit():
        where.append("u.jefe_id = ?")
        args.append(int(filtros["gerente_id"]))

    if filtros["tipo"]:
        tipo = filtros["tipo"].lower()
        if tipo == "caja_chica":
            where.append("COALESCE(g.es_caja_chica,0)=1")
        elif tipo == "reembolso":
            where.append("COALESCE(g.reembolso_vendedor,0)=1")
        elif tipo == "tarjeta_online":
            where.append("COALESCE(g.tarjeta_sin_soporte,0)=1")
        elif tipo == "tarjeta_boletos":
            where.append("COALESCE(g.boletos_aereos,0)=1")
        elif tipo == "tarjeta":
            where.append("COALESCE(g.es_caja_chica,0)=0 AND COALESCE(g.reembolso_vendedor,0)=0 AND COALESCE(g.boletos_aereos,0)=0 AND COALESCE(g.tarjeta_sin_soporte,0)=0")

    if filtros["descripcion"]:
        where.append("LOWER(COALESCE(g.motivo,'')) LIKE ?")
        args.append(f"%{filtros['descripcion'].lower()}%")

    if filtros["ccb"] in ("0", "1"):
        where.append("COALESCE(g.ccb,0)=?")
        args.append(int(filtros["ccb"]))

    # visibilidad mínima para no romper mientras migras
    if session_data and not can_view_all(session_data):
        if uid:
            where.append("g.usuario_id = ?")
            args.append(uid)

    return where, args, filtros


def get_reporte_data(conn, request_args: dict, session_data: dict) -> dict:
    filtros, rows = fetch_gastos_rows_for_report(conn)

    gastos = _rows_to_dicts(rows)

    return {
        "gastos": gastos,
        "filtros": filtros,
        "proveedores": get_proveedores_activos(conn),
        "usuarios_reg": get_usuarios_visibles(conn, gastos),
        "gerentes_reg": get_gerentes_visibles(conn, gastos),
        "totales": build_totales(gastos),
    }

def get_pendientes_aprobacion_data(conn, request_args: dict, session_data: dict) -> dict:
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    where, args, filtros = _build_base_where_from_request(request_args, session_data=session_data)

    role_name, uid, is_admin = _get_role_info(session_data)

    # pantalla enfocada a pendientes
    where.append("""
        (
            COALESCE(g.ga_aprobado,0)=0
            OR COALESCE(g.gg_aprobado,0)=0
            OR COALESCE(g.gf_aprobado,0)=0
        )
    """)

    sql = f"""
        SELECT
            g.*,
            COALESCE(u.username,'') AS usuario_username,
            COALESCE(j.username,'') AS gerente_nombre,
            COALESCE(j.id, 0)       AS gerente_id,
            COALESCE(t.nombre, g.proveedor, '') AS proveedor_nombre,
            COALESCE(t.codigo_sap,'') AS proveedor_codigo_sap,
            CASE
              WHEN COALESCE(g.es_caja_chica,0)=1 THEN 'caja_chica'
              WHEN COALESCE(g.reembolso_vendedor,0)=1 THEN 'reembolso'
              WHEN COALESCE(g.boletos_aereos,0)=1 THEN 'tarjeta_boletos'
              WHEN COALESCE(g.tarjeta_sin_soporte,0)=1 THEN 'tarjeta_online'
              ELSE 'tarjeta'
            END AS tipo_gasto
        FROM gastos_tarjeta g
        LEFT JOIN usuarios u ON u.id = g.usuario_id
        LEFT JOIN usuarios j ON j.id = u.jefe_id
        LEFT JOIN terceros t ON t.id = g.proveedor_id
        WHERE {" AND ".join(where)}
        ORDER BY date(COALESCE(g.fecha, g.created_at)) DESC, g.id DESC
    """
    cur.execute(sql, args)
    rows = _rows_to_dicts(cur.fetchall())

    return {
        "gastos": rows,
        "filtros": filtros,
        "proveedores": get_proveedores_activos(conn),
        "usuarios_reg": get_usuarios_visibles(conn, rows),
        "gerentes_reg": get_gerentes_visibles(conn, rows),
        "totales": build_totales(rows),
        "can_approve_gg": is_admin or role_name == "gerente general",
        "can_approve_gf": is_admin or role_name == "gerente financiero",
        "can_approve_ga": is_admin or role_name in ("gerente", "gerente de área", "gerente de area"),
        "readonly_view": role_name == "coordinador",
    }


def get_dashboard_data(conn, request_args: dict, session_data: dict) -> dict:
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    desde = (request_args.get("desde") or "").strip()
    hasta = (request_args.get("hasta") or "").strip()

    where = ["COALESCE(g.inactivo,0)=0"]
    args: list[Any] = []

    if desde:
        where.append("date(COALESCE(g.fecha, g.created_at)) >= date(?)")
        args.append(desde)
    if hasta:
        where.append("date(COALESCE(g.fecha, g.created_at)) <= date(?)")
        args.append(hasta)

    role_name, uid, is_admin = _get_role_info(session_data)
    if session_data and not can_view_all(session_data):
        if uid:
            where.append("g.usuario_id = ?")
            args.append(uid)

    where_sql = " AND ".join(where)

    cur.execute(
        f"""
        SELECT
            COALESCE(SUM(COALESCE(g.total_con_iva,0)),0) AS total_con_iva,
            COALESCE(SUM(COALESCE(g.con_soporte,0)),0) AS con_soporte,
            COALESCE(SUM(COALESCE(g.sin_soporte,0)),0) AS sin_soporte,
            COUNT(*) AS num_gastos
        FROM gastos_tarjeta g
        WHERE {where_sql}
        """,
        args,
    )
    kpis = _row_to_dict(cur.fetchone())

    cur.execute(
        f"""
        SELECT
            date(COALESCE(g.fecha, g.created_at)) AS fecha,
            COALESCE(SUM(COALESCE(g.total_con_iva,0)),0) AS total
        FROM gastos_tarjeta g
        WHERE {where_sql}
        GROUP BY date(COALESCE(g.fecha, g.created_at))
        ORDER BY date(COALESCE(g.fecha, g.created_at))
        """,
        args,
    )
    evolucion = _rows_to_dicts(cur.fetchall())

    cur.execute(
        f"""
        SELECT
            COALESCE(g.motivo,'') AS motivo,
            COUNT(*) AS cantidad
        FROM gastos_tarjeta g
        WHERE {where_sql}
        GROUP BY COALESCE(g.motivo,'')
        ORDER BY COUNT(*) DESC, COALESCE(g.motivo,'')
        LIMIT 10
        """,
        args,
    )
    top_motivos = _rows_to_dicts(cur.fetchall())

    cur.execute(
        f"""
        SELECT
            COALESCE(t.nombre, g.proveedor, 'SIN PROVEEDOR') AS proveedor,
            COALESCE(SUM(COALESCE(g.total_con_iva,0)),0) AS total
        FROM gastos_tarjeta g
        LEFT JOIN terceros t ON t.id = g.proveedor_id
        WHERE {where_sql}
        GROUP BY COALESCE(t.nombre, g.proveedor, 'SIN PROVEEDOR')
        ORDER BY total DESC
        LIMIT 10
        """,
        args,
    )
    top_proveedores = _rows_to_dicts(cur.fetchall())

    return {
        "desde": desde,
        "hasta": hasta,
        "kpis": kpis,
        "evolucion": evolucion,
        "top_motivos": top_motivos,
        "top_proveedores": top_proveedores,
    }


def search_facturas_xml_data(conn, *, q: str, limit: int) -> list[dict]:
    rows = search_facturas_xml(conn, q=q, limit=limit)

    data = []
    for r in rows:
        try:
            sec = int(r.get("secuencial") or 0)
            sec_str = f"{sec:09d}"
        except Exception:
            sec_str = str(r.get("secuencial") or "").strip()

        numero = f"{(r.get('estab') or '').strip()}-{(r.get('pto_emi') or '').strip()}-{sec_str}"

        data.append(
            {
                "id": r.get("id"),
                "numero": numero,
                "clave_acceso": r.get("clave_acceso"),
                "fecha_emision": r.get("fecha_emision"),
                "fecha_autorizacion": r.get("fecha_autorizacion"),
                "razon_social_emisor": r.get("razon_social_emisor"),
                "ruc_emisor": r.get("ruc_emisor"),
                "total": r.get("total"),
                "estado": r.get("estado"),
                "proveedor_ok": r.get("proveedor_ok", 0),
            }
        )
    return data


def enviar_gasto_sap_data(conn, gasto_id: int) -> dict:
    gasto = get_gasto_by_id(conn, gasto_id)
    if not gasto:
        return {"ok": False, "msg": "Gasto no encontrado."}
    return enviar_gasto_sap(conn, gasto_id)


def enviar_gasto_sap_masivo_data(conn, ids: list[int]) -> dict:
    return enviar_gasto_sap_masivo(conn, ids)


from .gastos_repository import (
    delete_gasto_full,
    get_adjuntos_by_gasto_id,
    get_detalle_by_gasto_id,
    get_gasto_full_by_id,
    get_gastos_by_ids,
    insert_gasto_full,
    replace_detalle,
    set_aprobacion_gasto,
    set_aprobacion_gasto_masivo,
    update_gasto_full,
)
from .gastos_security import (
    ensure_can_approve,
    ensure_can_delete_gasto,
    ensure_can_edit_gasto,
)


def _normalize_bool(value: Any) -> int:
    if isinstance(value, bool):
        return 1 if value else 0
    txt = str(value or "").strip().lower()
    return 1 if txt in {"1", "true", "t", "si", "sí", "yes", "on"} else 0


def _normalize_float(value: Any) -> float:
    try:
        return float(str(value or "0").replace(",", "."))
    except Exception:
        return 0.0


def _extract_gasto_payload(form_like: dict) -> dict:
    return {
        "fecha": (form_like.get("fecha") or "").strip(),
        "motivo": (form_like.get("motivo") or "").strip(),
        "proveedor_id": (form_like.get("proveedor_id") or None),
        "proveedor": (form_like.get("proveedor") or "").strip(),
        "numero_factura": (form_like.get("numero_factura") or "").strip(),
        "descripcion": (form_like.get("descripcion") or "").strip(),
        "con_soporte": _normalize_float(form_like.get("con_soporte")),
        "sin_soporte": _normalize_float(form_like.get("sin_soporte")),
        "subtotal_factura": _normalize_float(form_like.get("subtotal_factura")),
        "servicios_10": _normalize_float(form_like.get("servicios_10")),
        "subtotal_sin_iva": _normalize_float(form_like.get("subtotal_sin_iva")),
        "iva": _normalize_float(form_like.get("iva")),
        "total_con_iva": _normalize_float(form_like.get("total_con_iva")),
        "observacion": (form_like.get("observacion") or "").strip(),
        "ccb": _normalize_bool(form_like.get("ccb")),
        "es_caja_chica": _normalize_bool(form_like.get("es_caja_chica")),
        "reembolso_vendedor": _normalize_bool(form_like.get("reembolso_vendedor")),
        "tarjeta_sin_soporte": _normalize_bool(form_like.get("tarjeta_sin_soporte")),
        "boletos_aereos": _normalize_bool(form_like.get("boletos_aereos")),
        "factura_xml_id": form_like.get("factura_xml_id") or None,
        "centro_costo": (form_like.get("centro_costo") or "").strip(),
        "cuenta_contable": (form_like.get("cuenta_contable") or "").strip(),
    }


def _extract_detalle_items(form_like: dict) -> list[dict]:
    # versión base de migración:
    # si tu front manda arrays, esto luego se amplía
    descripcion = (form_like.get("detalle_descripcion") or form_like.get("descripcion") or "").strip()
    subtotal = _normalize_float(form_like.get("detalle_subtotal") or form_like.get("subtotal_factura"))
    iva = _normalize_float(form_like.get("detalle_iva") or form_like.get("iva"))
    total = _normalize_float(form_like.get("detalle_total") or form_like.get("total_con_iva"))

    if not descripcion and subtotal == 0 and iva == 0 and total == 0:
        return []

    return [
        {
            "descripcion": descripcion,
            "subtotal": subtotal,
            "iva": iva,
            "total": total,
        }
    ]


def create_gasto(conn, form_like: dict, session_data: dict) -> dict:
    uid = session_data.get("usuario_id") or session_data.get("user_id")
    if not uid:
        return {"ok": False, "msg": "Sesión inválida."}

    payload = _extract_gasto_payload(form_like)
    detalle = _extract_detalle_items(form_like)

    try:
        uid = int(uid)
    except Exception:
        return {"ok": False, "msg": "Usuario inválido."}

    try:
        gasto_id = insert_gasto_full(conn, payload, uid)
        if detalle:
            replace_detalle(conn, gasto_id, detalle)
        conn.commit()
        return {"ok": True, "id": gasto_id}
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        return {"ok": False, "msg": str(exc)}


def update_gasto_data(conn, gasto_id: int, form_like: dict, session_data: dict) -> dict:
    gasto = get_gasto_full_by_id(conn, gasto_id)
    if not gasto:
        return {"ok": False, "msg": "Gasto no encontrado."}

    try:
        ensure_can_edit_gasto(session_data, gasto)
    except Exception as exc:
        return {"ok": False, "msg": str(exc)}

    payload = _extract_gasto_payload(form_like)
    detalle = _extract_detalle_items(form_like)

    try:
        update_gasto_full(conn, gasto_id, payload)
        replace_detalle(conn, gasto_id, detalle)
        conn.commit()
        return {"ok": True, "id": gasto_id}
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        return {"ok": False, "msg": str(exc)}


def delete_gasto_data(conn, gasto_id: int, session_data: dict) -> dict:
    gasto = get_gasto_full_by_id(conn, gasto_id)
    if not gasto:
        return {"ok": False, "msg": "Gasto no encontrado."}

    try:
        ensure_can_delete_gasto(session_data, gasto)
    except Exception as exc:
        return {"ok": False, "msg": str(exc)}

    try:
        delete_gasto_full(conn, gasto_id)
        conn.commit()
        return {"ok": True}
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        return {"ok": False, "msg": str(exc)}


def aprobar_gasto_data(conn, gasto_id: int, area: str, value: bool, session_data: dict) -> dict:
    try:
        ensure_can_approve(session_data)
    except Exception as exc:
        return {"ok": False, "msg": str(exc)}

    gasto = get_gasto_full_by_id(conn, gasto_id)
    if not gasto:
        return {"ok": False, "msg": "Gasto no encontrado."}

    uid = session_data.get("usuario_id") or session_data.get("user_id")

    try:
        set_aprobacion_gasto(
            conn,
            gasto_id=gasto_id,
            area=area,
            value=bool(value),
            user_id=uid,
        )
        conn.commit()
        return {"ok": True, "id": gasto_id, "area": area, "value": bool(value)}
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        return {"ok": False, "msg": str(exc)}


def aprobar_gasto_masivo_data(conn, ids: list[int], area: str, value: bool, session_data: dict) -> dict:
    try:
        ensure_can_approve(session_data)
    except Exception as exc:
        return {"ok": False, "msg": str(exc)}

    uid = session_data.get("usuario_id") or session_data.get("user_id")

    try:
        updated = set_aprobacion_gasto_masivo(
            conn,
            ids=ids,
            area=area,
            value=bool(value),
            user_id=uid,
        )
        conn.commit()
        return {"ok": True, "updated": updated, "area": area, "value": bool(value)}
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        return {"ok": False, "msg": str(exc)}


def get_gasto_detalle_data(conn, gasto_id: int, session_data: dict) -> dict:
    gasto = get_gasto_full_by_id(conn, gasto_id)
    if not gasto:
        return {"ok": False, "msg": "Gasto no encontrado."}

    detalle = get_detalle_by_gasto_id(conn, gasto_id)
    adjuntos = get_adjuntos_by_gasto_id(conn, gasto_id)

    return {
        "ok": True,
        "gasto": gasto,
        "detalle": detalle,
        "adjuntos": adjuntos,
    }


def get_adjuntos_data(conn, gasto_id: int, session_data: dict) -> dict:
    gasto = get_gasto_full_by_id(conn, gasto_id)
    if not gasto:
        return {"ok": False, "msg": "Gasto no encontrado."}

    adjuntos = get_adjuntos_by_gasto_id(conn, gasto_id)
    return {"ok": True, "items": adjuntos}





def get_lista_gastos_data(conn, request_args: dict, session_data: dict) -> dict:
    filtros, rows = fetch_gastos_rows_for_report(conn)

    gastos = _rows_to_dicts(rows)

    return {
        "gastos": gastos,
        "filtros": filtros,
        "proveedores": get_proveedores_activos(conn),
        "usuarios_reg": get_usuarios_visibles(conn, gastos),
        "gerentes_reg": get_gerentes_visibles(conn, gastos),
        "totales": build_totales(gastos),
        "can_approve_gg": False,
        "can_approve_gf": False,
        "can_approve_ga": False,
    }




