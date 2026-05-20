# modules/scheduler/seedbilling_xml_job.py
# ==========================================================
# Job SeedBilling:
# - Consulta comprobantes recibidos por SOAP
# - Filtra Quimpac Ecuador S.A. RUC 0990344760001
# - Inserta solo Quimpac en facturas_xml / facturas_xml_det
# - Marca como entregados también los de otras empresas del grupo
# - No imprime XML ni RIDE en logs
# - Envía resumen al admin
# ==========================================================

from __future__ import annotations

import html
import os
import re
import json
import traceback
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any

import requests
from flask import current_app

from .scheduler_security import _log
from .scheduler_notifications import _send_email

from modules.gastos.gastos_constants import FACTURA_XML_PENDIENTE
from modules.gastos.gastos_queries import (
    SQL_EXISTS_FACTURA_XML,
    SQL_INSERT_FACTURA_XML,
    SQL_INSERT_FACTURA_XML_DET,
    SQL_GET_ADMIN_EMAILS,
)


SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"
SEED_NS = "http://webservices.trama.webservices.com/"


# ==========================================================
# Config / helpers
# ==========================================================

def _cfg(name: str, default=None):
    return current_app.config.get(name, default)


def _parse_sri_xml(raw):
    """
    Import diferido para evitar import circular.
    """
    from modules.routes_gastos_tarjeta import parse_sri_xml
    return parse_sri_xml(raw)


def _safe_text(x: Any) -> str:
    return "" if x is None else str(x).strip()


def _norm_ruc(x: str | None) -> str:
    return re.sub(r"\D+", "", x or "").strip()


def _local_name(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _iter_nodes_by_localname(root: ET.Element, wanted: str):
    for el in root.iter():
        if _local_name(el.tag) == wanted:
            yield el


def _strip_wsdl(url: str) -> str:
    url = (url or "").strip()
    if url.lower().endswith("?wsdl"):
        return url[:-5]
    return url


def _soap_escape(v: Any) -> str:
    return html.escape("" if v is None else str(v), quote=True)


def _unique_list(values: list[str]) -> list[str]:
    out = []
    seen = set()

    for v in values or []:
        v = _safe_text(v)
        if not v or v in seen:
            continue
        seen.add(v)
        out.append(v)

    return out


def _chunks(values: list[str], size: int):
    size = max(1, int(size or 100))
    for i in range(0, len(values), size):
        yield values[i:i + size]


def _clean_debug_response(txt: str, max_len: int = 600) -> str:
    """
    Para logs de diagnóstico sin exponer XML completos ni PDF base64.
    """
    if not txt:
        return ""

    s = str(txt)

    s = re.sub(
        r"<lRideBase64>.*?</lRideBase64>",
        "<lRideBase64>[OMITIDO]</lRideBase64>",
        s,
        flags=re.DOTALL | re.IGNORECASE,
    )
    s = re.sub(
        r"<lXmlProveedor>.*?</lXmlProveedor>",
        "<lXmlProveedor>[OMITIDO]</lXmlProveedor>",
        s,
        flags=re.DOTALL | re.IGNORECASE,
    )
    s = re.sub(
        r"<lXmlSRI>.*?</lXmlSRI>",
        "<lXmlSRI>[OMITIDO]</lXmlSRI>",
        s,
        flags=re.DOTALL | re.IGNORECASE,
    )

    return s[:max_len]


# ==========================================================
# SOAP
# ==========================================================

def _post_soap(url: str, envelope: str, *, soap_action: str = "", timeout: int = 120) -> str:
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
    }

    if soap_action:
        headers["SOAPAction"] = soap_action

    resp = requests.post(
        _strip_wsdl(url),
        data=envelope.encode("utf-8"),
        headers=headers,
        timeout=timeout,
        verify=_cfg("SEEDBILLING_VERIFY_SSL", True),
    )

    resp.raise_for_status()
    return resp.text


def _build_extraer_envelope(cantidad: int) -> str:
    suscriptor = _cfg("SEEDBILLING_SUSCRIPTOR", "81")
    tipo_documento = _cfg("SEEDBILLING_TIPODOCUMENTO", "01")
    usuario = _cfg("SEEDBILLING_USUARIO", "")
    clave = _cfg("SEEDBILLING_CLAVE", "")
    token = _cfg("SEEDBILLING_TOKEN", "")

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="{SOAP_NS}" xmlns:web="{SEED_NS}">
   <soapenv:Header/>
   <soapenv:Body>
      <web:extraerListaComprobantesRecibidosRide>
         <SUSCRIPTOR>{_soap_escape(suscriptor)}</SUSCRIPTOR>
         <CANTIDAD>{_soap_escape(cantidad)}</CANTIDAD>
         <TIPODOCUMENTO>{_soap_escape(tipo_documento)}</TIPODOCUMENTO>
         <USUARIO>{_soap_escape(usuario)}</USUARIO>
         <CLAVE>{_soap_escape(clave)}</CLAVE>
         <TOKEN>{_soap_escape(token)}</TOKEN>
      </web:extraerListaComprobantesRecibidosRide>
   </soapenv:Body>
</soapenv:Envelope>"""


def _build_marcar_entregados_envelope(claves_acceso: list[str]) -> str:
    suscriptor = _cfg("SEEDBILLING_SUSCRIPTOR", "81")
    tipo_documento = _cfg("SEEDBILLING_TIPODOCUMENTO", "01")
    usuario = _cfg("SEEDBILLING_USUARIO", "")
    clave = _cfg("SEEDBILLING_CLAVE", "")
    token = _cfg("SEEDBILLING_TOKEN", "")

    claves_limpias = _unique_list(claves_acceso)

    claves_xml = "\n".join(
        f"         <CLAVES_ACCESO>{_soap_escape(c)}</CLAVES_ACCESO>"
        for c in claves_limpias
    )

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="{SOAP_NS}" xmlns:web="{SEED_NS}">
   <soapenv:Header/>
   <soapenv:Body>
      <web:marcarComprobantesEntregadosrRecepcion>
         <SUSCRIPTOR>{_soap_escape(suscriptor)}</SUSCRIPTOR>
         <TIPO_DOCUMENTO>{_soap_escape(tipo_documento)}</TIPO_DOCUMENTO>
         <USUARIO>{_soap_escape(usuario)}</USUARIO>
         <CLAVE>{_soap_escape(clave)}</CLAVE>
         <TOKEN>{_soap_escape(token)}</TOKEN>
{claves_xml}
      </web:marcarComprobantesEntregadosrRecepcion>
   </soapenv:Body>
</soapenv:Envelope>"""


# ==========================================================
# Parse respuesta SeedBilling
# ==========================================================

def _extraer_comprobantes_desde_respuesta(xml_text: str) -> list[dict]:
    """
    Extrae nodos LISTA_COMPROBANTES_RECIBIDOS_RIDE.

    No imprime ni guarda XML en logs.
    """
    if not xml_text or not xml_text.strip():
        return []

    text = xml_text.strip()

    try:
        root = ET.fromstring(text.encode("utf-8"))
    except Exception:
        root = ET.fromstring(html.unescape(text).encode("utf-8"))

    out = []

    for item in _iter_nodes_by_localname(root, "LISTA_COMPROBANTES_RECIBIDOS_RIDE"):
        d = {}

        for child in list(item):
            key = _local_name(child.tag)
            val = child.text or ""
            d[key] = val.strip() if isinstance(val, str) else val

        if (
            d.get("lClaveAcceso")
            or d.get("lRucDestinatario")
            or d.get("lXmlSRI")
            or d.get("lXmlProveedor")
        ):
            out.append(d)

    if out:
        return out

    # Caso alternativo: respuesta XML escapada dentro de un nodo texto.
    for el in root.iter():
        txt = (el.text or "").strip()
        if "LISTA_COMPROBANTES_RECIBIDOS_RIDE" not in txt:
            continue

        try:
            inner_root = ET.fromstring(html.unescape(txt).encode("utf-8"))

            for item in _iter_nodes_by_localname(inner_root, "LISTA_COMPROBANTES_RECIBIDOS_RIDE"):
                d = {}

                for child in list(item):
                    key = _local_name(child.tag)
                    val = child.text or ""
                    d[key] = val.strip() if isinstance(val, str) else val

                if (
                    d.get("lClaveAcceso")
                    or d.get("lRucDestinatario")
                    or d.get("lXmlSRI")
                    or d.get("lXmlProveedor")
                ):
                    out.append(d)

        except Exception:
            continue

    return out


def _respuesta_entregados_ok(xml_text: str) -> bool:
    """
    Esperado:
    <RESPUESTA_ENTREGADOS>1</RESPUESTA_ENTREGADOS>
    """
    if not xml_text:
        return False

    try:
        root = ET.fromstring(xml_text.encode("utf-8"))

        for el in root.iter():
            if _local_name(el.tag) == "RESPUESTA_ENTREGADOS":
                return (el.text or "").strip() == "1"

    except Exception:
        return False

    return False


def _get_xml_comprobante(item: dict) -> str:
    """
    Para Quimpac preferimos lXmlSRI.
    Si no viene, usamos lXmlProveedor.
    Para otras empresas no se usa XML, solo clave/ruc.
    """
    xml_sri = _safe_text(item.get("lXmlSRI"))
    xml_proveedor = _safe_text(item.get("lXmlProveedor"))

    if xml_sri:
        return xml_sri

    if xml_proveedor:
        return xml_proveedor

    return ""


# ==========================================================
# SQL helpers
# ==========================================================

def _exists_factura_xml(cur, clave_acceso: str) -> int | None:
    cur.execute(SQL_EXISTS_FACTURA_XML, (clave_acceso,))

    row = cur.fetchone()
    if not row:
        return None

    try:
        return int(row["id"])
    except Exception:
        return int(row[0])


def _guardar_xml_archivo(clave_acceso: str, xml_text: str) -> str:
    folder = _cfg("SEEDBILLING_XML_ARCHIVE_FOLDER", "")

    if not folder:
        folder = os.path.join(
            current_app.root_path,
            "static",
            "uploads",
            "seedbilling_xml",
        )

    os.makedirs(folder, exist_ok=True)

    safe_name = re.sub(r"[^0-9A-Za-z_.-]+", "_", clave_acceso or "sin_clave")
    filename = f"seedbilling_{safe_name}.xml"
    path = os.path.join(folder, filename)

    with open(path, "w", encoding="utf-8") as f:
        f.write(xml_text or "")

    return filename


def _insert_factura_xml(conn, header: dict, detalles: list[dict], archivo: str) -> int:
    cur = conn.cursor()

    cur.execute(SQL_INSERT_FACTURA_XML, (
        header.get("clave_acceso"),
        header.get("numero_autorizacion"),
        header.get("tipo_comprobante"),
        header.get("cod_doc"),
        header.get("fecha_emision"),
        header.get("fecha_autorizacion"),
        header.get("ruc_emisor"),
        header.get("razon_social_emisor"),
        header.get("ruc_cliente"),
        header.get("razon_social_cliente"),
        header.get("estab"),
        header.get("pto_emi"),
        header.get("secuencial"),
        header.get("subtotal"),
        header.get("descuento"),
        header.get("iva"),
        header.get("total"),
        header.get("moneda"),
        header.get("base_iva") or 0,
        header.get("iva_tarifa") or 0,
        header.get("subtotal_0") or 0,
        header.get("subtotal_15") or 0,
        header.get("propina") or 0,
        FACTURA_XML_PENDIENTE,
        archivo,
    ))

    row = cur.fetchone()
    factura_id = row[0] if row else None

    if not factura_id:
        raise RuntimeError("No se pudo recuperar el ID insertado en facturas_xml.")

    for d in detalles:
        cur.execute(SQL_INSERT_FACTURA_XML_DET, (
            factura_id,
            d.get("codigo_principal"),
            d.get("descripcion"),
            d.get("cantidad"),
            d.get("precio_unitario"),
            d.get("descuento"),
            d.get("base_imponible"),
            d.get("iva"),
            d.get("total_linea"),
        ))

    return int(factura_id)


# ==========================================================
# Marcar entregados
# ==========================================================

def _marcar_entregados(claves_acceso: list[str], *, motivo: str) -> tuple[int, list[str]]:
    """
    Marca comprobantes como entregados.
    No imprime XML ni claves completas en logs.
    Devuelve:
      (cantidad_marcada_ok, errores)
    """
    claves_limpias = _unique_list(claves_acceso)

    if not claves_limpias:
        return 0, []

    mark_url = _cfg("SEEDBILLING_MARK_URL", "")
    if not mark_url:
        return 0, ["No está configurado SEEDBILLING_MARK_URL."]

    timeout = int(_cfg("SEEDBILLING_TIMEOUT", 120))
    chunk_size = int(_cfg("SEEDBILLING_MARK_CHUNK_SIZE", 100))

    total_ok = 0
    errores = []

    for idx, lote_claves in enumerate(_chunks(claves_limpias, chunk_size), start=1):
        try:
            _log(
                "info",
                "[SEEDBILLING] Marcando entregados motivo=%s lote=%s cantidad=%s",
                motivo,
                idx,
                len(lote_claves),
            )

            envelope = _build_marcar_entregados_envelope(lote_claves)

            response_text = _post_soap(
                mark_url,
                envelope,
                soap_action=_cfg("SEEDBILLING_MARK_SOAP_ACTION", ""),
                timeout=timeout,
            )

            if _respuesta_entregados_ok(response_text):
                total_ok += len(lote_claves)
            else:
                errores.append(
                    "Respuesta no exitosa del WS marcar entregados. "
                    f"motivo={motivo} lote={idx} respuesta={_clean_debug_response(response_text)}"
                )

        except Exception as e:
            errores.append(f"Error marcando entregados motivo={motivo} lote={idx}: {e}")

    return total_ok, errores


# ==========================================================
# Notificación admin
# ==========================================================

def _admin_emails(conn) -> list[str]:
    cur = conn.cursor()
    emails = []

    try:
        cur.execute(SQL_GET_ADMIN_EMAILS)

        for r in cur.fetchall() or []:
            try:
                email = r["email"]
            except Exception:
                email = r[0]

            email = (email or "").strip()
            if email and email not in emails:
                emails.append(email)

    except Exception:
        current_app.logger.exception("[SEEDBILLING] No se pudo consultar correos admin")

    extra = _cfg("SEEDBILLING_ADMIN_EMAILS", [])
    if isinstance(extra, str):
        extra = [x.strip() for x in extra.split(",") if x.strip()]

    for email in extra or []:
        if email and email not in emails:
            emails.append(email)

    return emails


def _fmt_money(v) -> str:
    try:
        n = float(v or 0)
    except Exception:
        n = 0.0

    s = f"{n:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _send_admin_summary(conn, resumen: dict):
    emails = _admin_emails(conn)

    if not emails:
        _log("warning", "[SEEDBILLING] No hay correos admin para enviar resumen.")
        return

    now_txt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    detalles_html = ""
    for x in resumen.get("procesados_detalle", [])[:100]:
        detalles_html += f"""
        <tr>
            <td style="padding:6px 8px;border-bottom:1px solid #e5e7eb;">{html.escape(str(x.get("estado", "")))}</td>
            <td style="padding:6px 8px;border-bottom:1px solid #e5e7eb;">{html.escape(str(x.get("clave", "")))}</td>
            <td style="padding:6px 8px;border-bottom:1px solid #e5e7eb;">{html.escape(str(x.get("emisor", "")))}</td>
            <td style="padding:6px 8px;border-bottom:1px solid #e5e7eb;text-align:right;">{_fmt_money(x.get("total"))}</td>
        </tr>
        """

    errores_html = ""
    for err in resumen.get("errores_detalle", [])[:50]:
        errores_html += f"""
        <li><b>{html.escape(str(err.get("clave", "sin clave")))}</b>: {html.escape(str(err.get("error", "")))}</li>
        """

    if not errores_html:
        errores_html = "<li>Sin errores.</li>"

    html_body = f"""
    <div style="font-family:Segoe UI,Arial,sans-serif;color:#111827;">
        <h2>Resumen carga automática XML SeedBilling</h2>

        <p><b>Fecha:</b> {now_txt}</p>
        <p><b>Empresa cargada:</b> Quimpac Ecuador S.A.</p>
        <p><b>RUC cargado:</b> {_cfg("SEEDBILLING_TARGET_RUC", "0990344760001")}</p>

        <table style="border-collapse:collapse;margin-top:12px;">
            <tr><td style="padding:6px 12px;"><b>Lotes consultados</b></td><td>{resumen.get("lotes", 0)}</td></tr>
            <tr><td style="padding:6px 12px;"><b>Recibidos del WS</b></td><td>{resumen.get("recibidos", 0)}</td></tr>
            <tr><td style="padding:6px 12px;"><b>Quimpac encontrados</b></td><td>{resumen.get("quimpac", 0)}</td></tr>
            <tr><td style="padding:6px 12px;"><b>Insertados Quimpac</b></td><td>{resumen.get("insertados", 0)}</td></tr>
            <tr><td style="padding:6px 12px;"><b>Duplicados Quimpac</b></td><td>{resumen.get("duplicados", 0)}</td></tr>
            <tr><td style="padding:6px 12px;"><b>Otras empresas omitidas</b></td><td>{resumen.get("otras_empresas", 0)}</td></tr>
            <tr><td style="padding:6px 12px;"><b>Marcados Quimpac</b></td><td>{resumen.get("marcados_entregados_quimpac", 0)}</td></tr>
            <tr><td style="padding:6px 12px;"><b>Marcados otras empresas</b></td><td>{resumen.get("marcados_entregados_otras", 0)}</td></tr>
            <tr><td style="padding:6px 12px;"><b>Total marcados</b></td><td>{resumen.get("marcados_entregados", 0)}</td></tr>
            <tr><td style="padding:6px 12px;"><b>Errores</b></td><td>{resumen.get("errores", 0)}</td></tr>
        </table>

        <h3>Documentos Quimpac procesados</h3>

        <table style="border-collapse:collapse;width:100%;font-size:13px;">
            <thead>
                <tr style="background:#eef2ff;">
                    <th style="text-align:left;padding:8px;">Estado</th>
                    <th style="text-align:left;padding:8px;">Clave acceso</th>
                    <th style="text-align:left;padding:8px;">Emisor</th>
                    <th style="text-align:right;padding:8px;">Total</th>
                </tr>
            </thead>
            <tbody>
                {detalles_html or '<tr><td colspan="4" style="padding:8px;">Sin documentos Quimpac procesados.</td></tr>'}
            </tbody>
        </table>

        <h3>Errores</h3>
        <ul>{errores_html}</ul>

        <p style="font-size:12px;color:#6b7280;margin-top:18px;">
            Este correo fue generado automáticamente por el worker.
        </p>
    </div>
    """

    text_body = json.dumps(resumen, ensure_ascii=False, indent=2)

    subject = (
        f"[SeedBilling] XML compras Quimpac: "
        f"{resumen.get('insertados', 0)} insertados, "
        f"{resumen.get('duplicados', 0)} duplicados, "
        f"{resumen.get('marcados_entregados_otras', 0)} otras empresas marcadas, "
        f"{resumen.get('errores', 0)} errores"
    )

    for email in emails:
        try:
            _send_email(email, subject, html_body, text_body)
        except Exception:
            current_app.logger.exception("[SEEDBILLING] Error enviando resumen a %s", email)


# ==========================================================
# Proceso principal
# ==========================================================

def process_seedbilling_facturas_recibidas(conn) -> dict:
    resumen = {
        "ok": True,
        "inicio": datetime.now().isoformat(timespec="seconds"),
        "lotes": 0,
        "recibidos": 0,
        "quimpac": 0,
        "insertados": 0,
        "duplicados": 0,
        "otras_empresas": 0,
        "marcados_entregados": 0,
        "marcados_entregados_quimpac": 0,
        "marcados_entregados_otras": 0,
        "errores": 0,
        "procesados_detalle": [],
        "otras_empresas_detalle": [],
        "errores_detalle": [],
    }

    if not _cfg("SEEDBILLING_ENABLED", False):
        resumen["ok"] = False
        resumen["skip"] = "SEEDBILLING_ENABLED=False"
        return resumen

    list_url = _cfg("SEEDBILLING_LIST_URL", "")
    if not list_url:
        resumen["ok"] = False
        resumen["error"] = "No está configurado SEEDBILLING_LIST_URL."
        return resumen

    target_ruc = _norm_ruc(_cfg("SEEDBILLING_TARGET_RUC", "0990344760001"))
    cantidad = int(_cfg("SEEDBILLING_CANTIDAD", 1000))
    timeout = int(_cfg("SEEDBILLING_TIMEOUT", 120))
    max_loops = int(_cfg("SEEDBILLING_MAX_LOOPS", 10))
    mark_other_companies = bool(_cfg("SEEDBILLING_MARK_OTHER_COMPANIES", True))

    cur = conn.cursor()

    _log(
        "info",
        "[SEEDBILLING] Inicio enabled=True cantidad=%s max_loops=%s target_ruc=%s mark_other_companies=%s",
        cantidad,
        max_loops,
        target_ruc,
        mark_other_companies,
    )

    for lote_num in range(1, max_loops + 1):
        resumen["lotes"] += 1

        try:
            _log(
                "info",
                "[SEEDBILLING] Consultando lote=%s cantidad=%s",
                lote_num,
                cantidad,
            )

            envelope = _build_extraer_envelope(cantidad)

            response_text = _post_soap(
                list_url,
                envelope,
                soap_action=_cfg("SEEDBILLING_LIST_SOAP_ACTION", ""),
                timeout=timeout,
            )

            items = _extraer_comprobantes_desde_respuesta(response_text)

            _log(
                "info",
                "[SEEDBILLING] Lote=%s response_len=%s items_detectados=%s",
                lote_num,
                len(response_text or ""),
                len(items),
            )

            if not items and bool(_cfg("SEEDBILLING_DEBUG_RESPONSE_SNIPPET", False)):
                _log(
                    "warning",
                    "[SEEDBILLING_DEBUG] Respuesta sin items snippet=%s",
                    _clean_debug_response(response_text),
                )

        except Exception as e:
            resumen["ok"] = False
            resumen["errores"] += 1
            resumen["errores_detalle"].append({
                "clave": "",
                "error": f"Error consultando SeedBilling lote {lote_num}: {e}",
            })
            current_app.logger.exception("[SEEDBILLING] Error consultando lista")
            break

        if not items:
            _log("info", "[SEEDBILLING] Lote %s sin comprobantes. Fin.", lote_num)
            break

        resumen["recibidos"] += len(items)

        claves_quimpac_a_marcar = []
        claves_otras_a_marcar = []

        for item in items:
            clave_item = _safe_text(item.get("lClaveAcceso"))
            ruc_dest_item = _norm_ruc(item.get("lRucDestinatario"))

            try:
                if not clave_item:
                    resumen["errores"] += 1
                    resumen["errores_detalle"].append({
                        "clave": "",
                        "error": f"Comprobante sin lClaveAcceso. Keys disponibles: {list(item.keys())}",
                    })
                    continue

                # Caso 1: el WS ya indica que es otra empresa.
                # No leemos XML, no parseamos XML, no insertamos.
                # Solo acumulamos la clave para marcar entregado.
                if ruc_dest_item and ruc_dest_item != target_ruc:
                    resumen["otras_empresas"] += 1

                    if mark_other_companies:
                        claves_otras_a_marcar.append(clave_item)

                    resumen["otras_empresas_detalle"].append({
                        "clave": clave_item,
                        "ruc_destinatario": ruc_dest_item,
                        "cliente": _safe_text(item.get("lNombreCliente")),
                        "emisor": _safe_text(item.get("lRazonSocial")),
                        "total": _safe_text(item.get("lValorDocumento")) or 0,
                    })

                    continue

                # Caso 2: podría ser Quimpac.
                # Recién aquí tomamos y parseamos XML.
                xml_text = _get_xml_comprobante(item)

                if not xml_text:
                    resumen["errores"] += 1
                    resumen["errores_detalle"].append({
                        "clave": clave_item,
                        "error": (
                            "El comprobante no trae lXmlSRI ni lXmlProveedor. "
                            f"Keys disponibles: {list(item.keys())}"
                        ),
                    })
                    continue

                header, detalles = _parse_sri_xml(xml_text)

                clave = _safe_text(header.get("clave_acceso")) or clave_item
                ruc_cliente = _norm_ruc(header.get("ruc_cliente")) or ruc_dest_item

                if not clave:
                    raise RuntimeError("No se encontró clave_acceso en el XML.")

                # Caso 3: el lRucDestinatario venía vacío, pero el XML indica otra empresa.
                if ruc_cliente != target_ruc:
                    resumen["otras_empresas"] += 1

                    if mark_other_companies:
                        claves_otras_a_marcar.append(clave)

                    resumen["otras_empresas_detalle"].append({
                        "clave": clave,
                        "ruc_destinatario": ruc_cliente,
                        "cliente": (
                            _safe_text(item.get("lNombreCliente"))
                            or _safe_text(header.get("razon_social_cliente"))
                        ),
                        "emisor": (
                            _safe_text(item.get("lRazonSocial"))
                            or _safe_text(header.get("razon_social_emisor"))
                        ),
                        "total": (
                            _safe_text(item.get("lValorDocumento"))
                            or header.get("total")
                            or 0
                        ),
                    })

                    continue

                # Caso 4: Quimpac.
                resumen["quimpac"] += 1

                factura_existente_id = _exists_factura_xml(cur, clave)

                if factura_existente_id:
                    resumen["duplicados"] += 1
                    estado_doc = "DUPLICADO"
                    factura_id = factura_existente_id
                else:
                    archivo = _guardar_xml_archivo(clave, xml_text)
                    factura_id = _insert_factura_xml(conn, header, detalles, archivo)
                    conn.commit()

                    resumen["insertados"] += 1
                    estado_doc = "INSERTADO"

                claves_quimpac_a_marcar.append(clave)

                resumen["procesados_detalle"].append({
                    "estado": estado_doc,
                    "factura_id": factura_id,
                    "clave": clave,
                    "emisor": header.get("razon_social_emisor"),
                    "ruc_emisor": header.get("ruc_emisor"),
                    "fecha_emision": header.get("fecha_emision"),
                    "total": header.get("total"),
                })

            except Exception as e:
                conn.rollback()
                resumen["errores"] += 1
                resumen["errores_detalle"].append({
                    "clave": clave_item,
                    "error": str(e),
                })
                current_app.logger.error(
                    "[SEEDBILLING] Error procesando clave=%s error=%s\n%s",
                    clave_item,
                    e,
                    traceback.format_exc(),
                )

        # Marcar Quimpac.
        n_ok_quimpac, errs_quimpac = _marcar_entregados(
            claves_quimpac_a_marcar,
            motivo="QUIMPAC",
        )

        if n_ok_quimpac:
            resumen["marcados_entregados"] += n_ok_quimpac
            resumen["marcados_entregados_quimpac"] += n_ok_quimpac

        for err in errs_quimpac:
            resumen["errores"] += 1
            resumen["errores_detalle"].append({
                "clave": "",
                "error": err,
            })

        # Marcar otras empresas.
        n_ok_otras = 0
        if mark_other_companies:
            n_ok_otras, errs_otras = _marcar_entregados(
                claves_otras_a_marcar,
                motivo="OTRAS_EMPRESAS",
            )

            if n_ok_otras:
                resumen["marcados_entregados"] += n_ok_otras
                resumen["marcados_entregados_otras"] += n_ok_otras

            for err in errs_otras:
                resumen["errores"] += 1
                resumen["errores_detalle"].append({
                    "clave": "",
                    "error": err,
                })

        _log(
            "info",
            "[SEEDBILLING] Lote=%s resumen recibido=%s quimpac=%s otras=%s marcadas_quimpac=%s marcadas_otras=%s errores=%s",
            lote_num,
            len(items),
            len(claves_quimpac_a_marcar),
            len(claves_otras_a_marcar),
            n_ok_quimpac,
            n_ok_otras,
            resumen["errores"],
        )

        # Si no se marcó nada y no hubo Quimpac, seguir no tendría sentido.
        # Esto evita loops infinitos ante respuestas raras.
        if not claves_quimpac_a_marcar and not claves_otras_a_marcar:
            _log(
                "warning",
                "[SEEDBILLING] Lote=%s sin claves para marcar. Fin preventivo.",
                lote_num,
            )
            break

        # Si el lote recibido fue menor que la cantidad solicitada,
        # normalmente ya no habrá más pendientes luego de marcarlo.
        if len(items) < cantidad:
            _log(
                "info",
                "[SEEDBILLING] Lote=%s menor que cantidad solicitada. Fin.",
                lote_num,
            )
            break

    resumen["fin"] = datetime.now().isoformat(timespec="seconds")

    try:
        _send_admin_summary(conn, resumen)
    except Exception:
        current_app.logger.exception("[SEEDBILLING] Error enviando resumen admin")

    _log(
        "info",
        "[SEEDBILLING] FIN lotes=%s recibidos=%s quimpac=%s insertados=%s duplicados=%s otras=%s marcados_quimpac=%s marcados_otras=%s marcados_total=%s errores=%s",
        resumen["lotes"],
        resumen["recibidos"],
        resumen["quimpac"],
        resumen["insertados"],
        resumen["duplicados"],
        resumen["otras_empresas"],
        resumen["marcados_entregados_quimpac"],
        resumen["marcados_entregados_otras"],
        resumen["marcados_entregados"],
        resumen["errores"],
    )

    return resumen