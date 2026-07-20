# modules/gastos/gastos_sap_service.py

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import requests

from .gastos_constants import TABLE_GASTOS
from .gastos_repository import (
    get_detalles_for_sap,
    get_gastos_for_sap,
    mark_gasto_sap_result,
)


Q2 = Decimal("0.01")


def _D(value: Any) -> Decimal:
    try:
        return Decimal(str(value or "0"))
    except Exception:
        return Decimal("0")


def _q2(value: Decimal) -> Decimal:
    return value.quantize(Q2, rounding=ROUND_HALF_UP)


def _fmt_ddmmyyyy(iso_date: str | None) -> str:
    if not iso_date:
        return ""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(str(iso_date), fmt).strftime("%d.%m.%Y")
        except Exception:
            continue
    return ""


def _extraer_error_sap(resp: Any) -> str | None:
    if resp is None:
        return "Respuesta vacía de SAP."

    if isinstance(resp, dict):
        for key in (
            "error",
            "message",
            "Message",
            "mensaje",
            "Mensaje",
            "detail",
            "Detail",
            "sap_error",
            "faultstring",
        ):
            val = resp.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()

        for key in ("errors", "return", "RETURN"):
            val = resp.get(key)
            if isinstance(val, list) and val:
                first = val[0]
                if isinstance(first, dict):
                    for sub in ("message", "Message", "mensaje", "MESSAGE"):
                        msg = first.get(sub)
                        if isinstance(msg, str) and msg.strip():
                            return msg.strip()
                elif isinstance(first, str) and first.strip():
                    return first.strip()

    if isinstance(resp, list) and resp:
        first = resp[0]
        return _extraer_error_sap(first)

    return None


def get_param_map(conn: sqlite3.Connection, group_code: str) -> dict[str, str]:
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Ajusta esta consulta si tu modelo de parámetros usa otra estructura
    cur.execute(
        """
        SELECT
            LOWER(TRIM(pv.code)) AS k,
            COALESCE(pv.value, pv.name, '') AS v
        FROM param_values pv
        JOIN param_groups pg
            ON pg.id = pv.group_id
        WHERE LOWER(TRIM(pg.code)) = LOWER(TRIM(?))
          AND COALESCE(pv.active, 1) = 1
        """,
        (group_code,),
    )

    data: dict[str, str] = {}
    for row in cur.fetchall():
        key = (row["k"] or "").strip()
        if key:
            data[key] = (row["v"] or "").strip()
    return data


def get_sap_config_from_db(conn: sqlite3.Connection) -> dict[str, str]:
    cfg = get_param_map(conn, "sap_config")

    return {
        "SAP_URL": cfg.get("sap_url", ""),
        "SAP_URL_QAS": cfg.get("sap_url_qas", ""),
        "SAP_CLIENT": cfg.get("sap_client", ""),
        "SAP_USER": cfg.get("sap_user", ""),
        "SAP_PASS": cfg.get("sap_pass", ""),
        "SAP_COMPANY": cfg.get("sap_company", ""),
    }


def build_sap_payload(gasto: dict, detalles: list[dict]) -> dict[str, Any]:
    documentos: list[dict[str, Any]] = []

    for det in detalles:
        subtotal = _q2(_D(det.get("subtotal", det.get("base_imponible", 0))))
        iva = _q2(_D(det.get("iva", 0)))
        total = _q2(_D(det.get("total", subtotal + iva)))

        documentos.append(
            {
                "Fecha": _fmt_ddmmyyyy(gasto.get("fecha")),
                "Motivo": gasto.get("motivo") or "",
                "ProveedorCodigoSAP": gasto.get("proveedor_codigo_sap") or "",
                "UsuarioCodigoSAP": gasto.get("usuario_codigo_sap") or "",
                "UsuarioCedula": gasto.get("usuario_cedula") or "",
                "NumeroFactura": gasto.get("numero_factura") or "",
                "Detalle": det.get("descripcion") or "",
                "Subtotal": float(subtotal),
                "IVA": float(iva),
                "Total": float(total),
                "CentroCosto": det.get("centro_costo") or gasto.get("centro_costo") or "",
                "CuentaContable": det.get("cuenta_contable") or gasto.get("cuenta_contable") or "",
            }
        )

    payload = {
        "Liquidacion_Documentos": documentos,
        "GastoId": gasto.get("id"),
        "Tipo": gasto.get("tipo") or "",
    }
    return payload


def send_payload_to_sap(
    *,
    sap_url: str,
    sap_user: str,
    sap_pass: str,
    sap_client: str,
    payload: dict[str, Any],
    timeout: int = 60,
) -> tuple[int, Any]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    auth = None
    if sap_user or sap_pass:
        auth = (sap_user, sap_pass)

    params = {}
    if sap_client:
        params["sap-client"] = sap_client

    response = requests.post(
        sap_url,
        json=payload,
        headers=headers,
        params=params,
        auth=auth,
        timeout=timeout,
    )

    try:
        data = response.json()
    except Exception:
        data = {"raw_text": response.text}

    return response.status_code, data


def extract_sap_doc(resp: Any) -> str:
    if isinstance(resp, list) and resp:
        first = resp[0]
    elif isinstance(resp, dict):
        first = resp
    else:
        first = None

    if isinstance(first, dict):
        return (
            first.get("doc_number")
            or first.get("document")
            or first.get("num_doc")
            or first.get("DOCUMENTO")
            or first.get("documento")
            or ""
        )
    return ""


def enviar_gasto_sap(conn: sqlite3.Connection, gasto_id: int) -> dict[str, Any]:
    cfg = get_sap_config_from_db(conn)
    sap_url = cfg["SAP_URL"]
    sap_user = cfg["SAP_USER"]
    sap_pass = cfg["SAP_PASS"]
    sap_client = cfg["SAP_CLIENT"]

    if not (sap_url or "").startswith(("http://", "https://")):
        return {"ok": False, "msg": f"SAP_URL inválida: {sap_url!r}"}

    gastos = get_gastos_for_sap(conn, [gasto_id])
    if not gastos:
        return {"ok": False, "msg": "Gasto no encontrado."}

    gasto = gastos[0]
    detalles = [d for d in get_detalles_for_sap(conn, [gasto_id]) if int(d.get("gasto_id") or 0) == int(gasto_id)]

    payload = build_sap_payload(gasto, detalles)

    try:
        status_code, resp = send_payload_to_sap(
            sap_url=sap_url,
            sap_user=sap_user,
            sap_pass=sap_pass,
            sap_client=sap_client,
            payload=payload,
        )

        error_sap = _extraer_error_sap(resp)
        if error_sap:
            mark_gasto_sap_result(
                conn,
                gasto_id=gasto_id,
                doc_number=None,
                response_json=json.dumps(resp)[:4000],
                enviado_at=datetime.utcnow().isoformat(timespec="seconds"),
                error_msg=error_sap,
            )
            conn.commit()
            return {"ok": False, "msg": error_sap}

        if status_code >= 400:
            err = None
            if isinstance(resp, dict):
                err = resp.get("error") or resp.get("message")
            if not err:
                err = f"HTTP {status_code}"

            mark_gasto_sap_result(
                conn,
                gasto_id=gasto_id,
                doc_number=None,
                response_json=json.dumps(resp)[:4000],
                enviado_at=datetime.utcnow().isoformat(timespec="seconds"),
                error_msg=str(err),
            )
            conn.commit()
            return {"ok": False, "msg": str(err)}

        doc = extract_sap_doc(resp)

        mark_gasto_sap_result(
            conn,
            gasto_id=gasto_id,
            doc_number=doc or None,
            response_json=json.dumps(resp)[:4000],
            enviado_at=datetime.utcnow().isoformat(timespec="seconds"),
            error_msg=None,
        )
        conn.commit()

        return {"ok": True, "doc": doc or None, "response": resp}

    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        return {"ok": False, "msg": str(exc)}


def enviar_gasto_sap_masivo(conn: sqlite3.Connection, ids: list[int]) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    sent = 0
    errors = 0

    ids_norm: list[int] = []
    for gid in ids or []:
        try:
            ids_norm.append(int(gid))
        except Exception:
            pass

    ids_norm = list(dict.fromkeys(ids_norm))
    if not ids_norm:
        return {"ok": False, "msg": "No hay IDs válidos.", "sent": 0, "errors": 0, "results": []}

    for gasto_id in ids_norm:
        result = enviar_gasto_sap(conn, gasto_id)
        item = {
            "id": gasto_id,
            "ok": bool(result.get("ok")),
            "doc": result.get("doc"),
            "msg": result.get("msg"),
        }
        results.append(item)

        if item["ok"]:
            sent += 1
        else:
            errors += 1

    return {
        "ok": True,
        "sent": sent,
        "errors": errors,
        "results": results,
    }