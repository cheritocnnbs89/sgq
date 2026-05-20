# modules/gastos/gastos_xml_service.py

from __future__ import annotations

import os
import re
import sqlite3
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation
from typing import Any


def _strip_ns(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _text(node: ET.Element | None, default: str = "") -> str:
    if node is None or node.text is None:
        return default
    return node.text.strip()


def _find_first(root: ET.Element, names: list[str]) -> ET.Element | None:
    wanted = {n.lower() for n in names}
    for el in root.iter():
        if _strip_ns(el.tag).lower() in wanted:
            return el
    return None


def _findall_by_name(root: ET.Element, name: str) -> list[ET.Element]:
    out: list[ET.Element] = []
    target = name.lower()
    for el in root.iter():
        if _strip_ns(el.tag).lower() == target:
            out.append(el)
    return out


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        txt = str(value or "").strip().replace(",", ".")
        if txt == "":
            return default
        return float(txt)
    except Exception:
        return default


def _to_decimal(value: Any, default: str = "0") -> Decimal:
    try:
        txt = str(value or "").strip().replace(",", ".")
        return Decimal(txt or default)
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)


def sanitize_sri_xml(xml_content: str) -> str:
    if not xml_content:
        return ""

    xml_content = xml_content.strip()

    if xml_content.startswith("\ufeff"):
        xml_content = xml_content.lstrip("\ufeff")

    xml_content = re.sub(r"[^\x09\x0A\x0D\x20-\x7E\u00A0-\uFFFF]", "", xml_content)
    return xml_content


def parse_sri_xml(xml_content: str) -> dict[str, Any]:
    xml_content = sanitize_sri_xml(xml_content)
    if not xml_content:
        raise ValueError("El XML está vacío.")

    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as exc:
        raise ValueError(f"XML inválido: {exc}") from exc

    # Algunos XML del SRI vienen envueltos en <autorizacion><comprobante><![CDATA[...]]
    comprobante_node = _find_first(root, ["comprobante"])
    comprobante_raw = _text(comprobante_node)

    if comprobante_raw and "<" in comprobante_raw:
        try:
            factura_root = ET.fromstring(sanitize_sri_xml(comprobante_raw))
        except ET.ParseError:
            factura_root = root
    else:
        factura_root = root

    info_tributaria = _find_first(factura_root, ["infoTributaria"])
    info_factura = _find_first(factura_root, ["infoFactura"])

    def _get_from(parent: ET.Element | None, name: str, default: str = "") -> str:
        if parent is None:
            return default
        for child in parent.iter():
            if _strip_ns(child.tag).lower() == name.lower():
                return _text(child, default)
        return default

    estab = _get_from(info_tributaria, "estab")
    pto_emi = _get_from(info_tributaria, "ptoEmi")
    secuencial = _get_from(info_tributaria, "secuencial")
    clave_acceso = _get_from(info_tributaria, "claveAcceso")
    ruc_emisor = _get_from(info_tributaria, "ruc")
    razon_social_emisor = _get_from(info_tributaria, "razonSocial")

    fecha_emision = _get_from(info_factura, "fechaEmision")
    importe_total = _get_from(info_factura, "importeTotal", "0")
    subtotal_sin_impuestos = _get_from(info_factura, "totalSinImpuestos", "0")
    moneda = _get_from(info_factura, "moneda", "DOLAR")

    fecha_autorizacion = _text(_find_first(root, ["fechaAutorizacion"]))
    numero_autorizacion = _text(_find_first(root, ["numeroAutorizacion"]))
    ambiente = _get_from(info_tributaria, "ambiente")
    tipo_emision = _get_from(info_tributaria, "tipoEmision")
    dir_establecimiento = _get_from(info_factura, "dirEstablecimiento")

    impuestos: list[dict[str, Any]] = []
    total_iva = Decimal("0")

    for imp in _findall_by_name(factura_root, "totalImpuesto"):
        base_imponible = _to_decimal(_get_from(imp, "baseImponible", "0"))
        valor = _to_decimal(_get_from(imp, "valor", "0"))
        tarifa = _to_float(_get_from(imp, "tarifa", "0"))

        impuestos.append(
            {
                "codigo": _get_from(imp, "codigo"),
                "codigo_porcentaje": _get_from(imp, "codigoPorcentaje"),
                "base_imponible": float(base_imponible),
                "tarifa": tarifa,
                "valor": float(valor),
            }
        )
        total_iva += valor

    detalles: list[dict[str, Any]] = []
    for det in _findall_by_name(factura_root, "detalle"):
        cantidad = _to_decimal(_get_from(det, "cantidad", "0"))
        precio_unitario = _to_decimal(_get_from(det, "precioUnitario", "0"))
        descuento = _to_decimal(_get_from(det, "descuento", "0"))
        precio_total_sin_impuesto = _to_decimal(_get_from(det, "precioTotalSinImpuesto", "0"))

        iva_linea = Decimal("0")
        for imp in det.iter():
            if _strip_ns(imp.tag).lower() == "impuesto":
                iva_linea += _to_decimal(_get_from(imp, "valor", "0"))

        detalles.append(
            {
                "codigo_principal": _get_from(det, "codigoPrincipal"),
                "codigo_auxiliar": _get_from(det, "codigoAuxiliar"),
                "descripcion": _get_from(det, "descripcion"),
                "cantidad": float(cantidad),
                "precio_unitario": float(precio_unitario),
                "descuento": float(descuento),
                "base_imponible": float(precio_total_sin_impuesto),
                "iva": float(iva_linea),
                "total_linea": float(precio_total_sin_impuesto + iva_linea),
            }
        )

    return {
        "clave_acceso": clave_acceso,
        "numero_autorizacion": numero_autorizacion or clave_acceso,
        "fecha_autorizacion": fecha_autorizacion,
        "fecha_emision": fecha_emision,
        "ruc_emisor": ruc_emisor,
        "razon_social_emisor": razon_social_emisor,
        "estab": estab,
        "pto_emi": pto_emi,
        "secuencial": secuencial,
        "subtotal_sin_impuestos": float(_to_decimal(subtotal_sin_impuestos)),
        "iva": float(total_iva),
        "total": float(_to_decimal(importe_total)),
        "moneda": moneda,
        "ambiente": ambiente,
        "tipo_emision": tipo_emision,
        "dir_establecimiento": dir_establecimiento,
        "impuestos": impuestos,
        "detalles": detalles,
        "xml_raw": xml_content,
    }


def parse_sri_xml_file(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        return parse_sri_xml(fh.read())


def ensure_facturas_xml_schema(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS facturas_xml (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            clave_acceso TEXT,
            numero_autorizacion TEXT,
            fecha_autorizacion TEXT,
            fecha_emision TEXT,
            ruc_emisor TEXT,
            razon_social_emisor TEXT,
            estab TEXT,
            pto_emi TEXT,
            secuencial TEXT,
            subtotal_sin_impuestos REAL DEFAULT 0,
            iva REAL DEFAULT 0,
            total REAL DEFAULT 0,
            moneda TEXT,
            ambiente TEXT,
            tipo_emision TEXT,
            dir_establecimiento TEXT,
            estado TEXT DEFAULT 'PENDIENTE',
            xml_raw TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS facturas_xml_detalle (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            factura_id INTEGER NOT NULL,
            codigo_principal TEXT,
            codigo_auxiliar TEXT,
            descripcion TEXT,
            cantidad REAL DEFAULT 0,
            precio_unitario REAL DEFAULT 0,
            descuento REAL DEFAULT 0,
            base_imponible REAL DEFAULT 0,
            iva REAL DEFAULT 0,
            total_linea REAL DEFAULT 0,
            FOREIGN KEY (factura_id) REFERENCES facturas_xml(id)
        )
        """
    )

    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_facturas_xml_clave_acceso ON facturas_xml(clave_acceso)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_facturas_xml_estado ON facturas_xml(estado)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_facturas_xml_ruc_emisor ON facturas_xml(ruc_emisor)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_facturas_xml_fecha_emision ON facturas_xml(fecha_emision)")

    conn.commit()


def insert_factura_xml_parsed(conn: sqlite3.Connection, parsed: dict[str, Any]) -> int:
    ensure_facturas_xml_schema(conn)
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO facturas_xml (
            clave_acceso,
            numero_autorizacion,
            fecha_autorizacion,
            fecha_emision,
            ruc_emisor,
            razon_social_emisor,
            estab,
            pto_emi,
            secuencial,
            subtotal_sin_impuestos,
            iva,
            total,
            moneda,
            ambiente,
            tipo_emision,
            dir_establecimiento,
            estado,
            xml_raw
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            parsed.get("clave_acceso"),
            parsed.get("numero_autorizacion"),
            parsed.get("fecha_autorizacion"),
            parsed.get("fecha_emision"),
            parsed.get("ruc_emisor"),
            parsed.get("razon_social_emisor"),
            parsed.get("estab"),
            parsed.get("pto_emi"),
            parsed.get("secuencial"),
            parsed.get("subtotal_sin_impuestos", 0),
            parsed.get("iva", 0),
            parsed.get("total", 0),
            parsed.get("moneda"),
            parsed.get("ambiente"),
            parsed.get("tipo_emision"),
            parsed.get("dir_establecimiento"),
            parsed.get("estado", "PENDIENTE"),
            parsed.get("xml_raw"),
        ),
    )
    factura_id = int(cur.lastrowid)

    for det in parsed.get("detalles", []) or []:
        cur.execute(
            """
            INSERT INTO facturas_xml_detalle (
                factura_id,
                codigo_principal,
                codigo_auxiliar,
                descripcion,
                cantidad,
                precio_unitario,
                descuento,
                base_imponible,
                iva,
                total_linea
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                factura_id,
                det.get("codigo_principal"),
                det.get("codigo_auxiliar"),
                det.get("descripcion"),
                det.get("cantidad", 0),
                det.get("precio_unitario", 0),
                det.get("descuento", 0),
                det.get("base_imponible", 0),
                det.get("iva", 0),
                det.get("total_linea", 0),
            ),
        )

    conn.commit()
    return factura_id


def factura_xml_exists_by_clave(conn: sqlite3.Connection, clave_acceso: str) -> bool:
    ensure_facturas_xml_schema(conn)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT top 11 FROM facturas_xml WHERE TRIM(COALESCE(clave_acceso,'')) = TRIM(?)", (clave_acceso,))
    return cur.fetchone() is not None


def build_factura_numero(estab: str | None, pto_emi: str | None, secuencial: str | int | None) -> str:
    estab = (estab or "").strip()
    pto_emi = (pto_emi or "").strip()

    try:
        sec = int(str(secuencial or "0").strip() or "0")
        sec_str = f"{sec:09d}"
    except Exception:
        sec_str = str(secuencial or "").strip()

    return f"{estab}-{pto_emi}-{sec_str}"


def apply_facturas_xml_search(where: list[str], params: list[Any], q: str, alias: str = "f") -> None:
    q = (q or "").strip()
    if not q:
        return

    q_like = f"%{q}%"
    q_digits = re.sub(r"\D+", "", q)

    conds = [
        f"UPPER(COALESCE({alias}.clave_acceso,'')) LIKE UPPER(?)",
        f"UPPER(COALESCE({alias}.razon_social_emisor,'')) LIKE UPPER(?)",
        f"UPPER(COALESCE({alias}.ruc_emisor,'')) LIKE UPPER(?)",
        f"UPPER(COALESCE({alias}.fecha_emision,'')) LIKE UPPER(?)",
        f"UPPER(COALESCE({alias}.numero_autorizacion,'')) LIKE UPPER(?)",
        f"UPPER(COALESCE({alias}.estab,'')) LIKE UPPER(?)",
        f"UPPER(COALESCE({alias}.pto_emi,'')) LIKE UPPER(?)",
        f"UPPER(COALESCE({alias}.secuencial,'')) LIKE UPPER(?)",
        (
            "TRIM(COALESCE("
            f"{alias}.estab,'') || '-' || COALESCE({alias}.pto_emi,'') || '-' || "
            f"printf('%09d', CAST(COALESCE({alias}.secuencial,'0') AS INTEGER))) LIKE ?"
        ),
    ]

    for _ in range(8):
        params.append(q_like)
    params.append(q_like)

    if q_digits:
        conds.append(f"REPLACE(REPLACE(REPLACE(COALESCE({alias}.clave_acceso,''),'-',''),' ',''),'.','') LIKE ?")
        params.append(f"%{q_digits}%")

    where.append("(" + " OR ".join(conds) + ")")


def load_factura_xml_from_file(conn: sqlite3.Connection, path: str) -> tuple[bool, str, int | None]:
    if not os.path.exists(path):
        return False, "Archivo no encontrado.", None

    parsed = parse_sri_xml_file(path)
    clave = (parsed.get("clave_acceso") or "").strip()

    if not clave:
        return False, "El XML no contiene clave de acceso.", None

    if factura_xml_exists_by_clave(conn, clave):
        return False, "XML duplicado por clave de acceso.", None

    factura_id = insert_factura_xml_parsed(conn, parsed)
    return True, "XML cargado correctamente.", factura_id