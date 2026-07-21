# modules/routes_reclamos_pdf.py
# -*- coding: utf-8 -*-
"""
Generación del PDF "Carta al cliente" para OMs cerradas.

Flujo:
  1. Consulta BD para obtener datos completos de la OM y sus respuestas.
  2. Llama a OpenAI para redactar bloques en lenguaje cliente.
  3. Renderiza el template HTML con Jinja2.
  4. Convierte a PDF con xhtml2pdf y devuelve bytes.

IMPORTANTE CSP:
  - El template NO usa <style>.
  - El template NO usa style="".
  - El CSS vive en /static/css/reclamos/reclamos_carta_cliente_pdf.css.
  - xhtml2pdf necesita link_callback para resolver /static/... en Windows.
"""

from __future__ import annotations

import io
import json
import logging
import os
from datetime import date, datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

log = logging.getLogger(__name__)

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


# ─────────────────────────────────────────────────────────────
# SQL
# ─────────────────────────────────────────────────────────────

_SQL_OM = """
    SELECT TOP 1
        r.id,
        r.codigo,
        CONVERT(VARCHAR(10), r.fecha_reclamo, 103)  AS fecha_reclamo,
        r.cliente_nombre,
        r.cliente_contacto,
        r.cliente_email,
        COALESCE(pv_tipo.valor, r.tipo_reclamo, '')  AS tipo_reclamo,
        COALESCE(r.material_desc, '')                AS material,
        r.proceso_text                               AS proceso,
        COALESCE(pv_mot.valor, r.antecedente, '')    AS motivo,
        COALESCE(r.observacion, '')                  AS observacion,
        r.estado_global,
        r.requiere_carta_cliente,
        r.creado_por
    FROM reclamos r
    LEFT JOIN param_groups  pg_tipo ON pg_tipo.nombre = 'RECL_TIPO'
    LEFT JOIN param_values  pv_tipo ON pv_tipo.group_id = pg_tipo.id
                                    AND pv_tipo.nombre = r.tipo_reclamo
    LEFT JOIN param_groups  pg_mot  ON pg_mot.nombre  = 'RECL_MOTIVO'
    LEFT JOIN param_values  pv_mot  ON pv_mot.group_id = pg_mot.id
                                    AND pv_mot.nombre = r.antecedente
    WHERE r.id = ?
"""

_SQL_RESPUESTAS = """
    SELECT
        COALESCE(ri.respuesta_causa,      '') AS causa,
        COALESCE(ri.respuesta_preventiva, '') AS preventiva,
        COALESCE(ri.respuesta_correctiva, '') AS correctiva,
        COALESCE(ri.metodo_analisis,      '') AS metodo_analisis,
        COALESCE(ri.why1,'') AS why1,
        COALESCE(ri.why2,'') AS why2,
        COALESCE(ri.why3,'') AS why3,
        COALESCE(ri.why4,'') AS why4,
        COALESCE(ri.why5,'') AS why5,
        COALESCE(ri.fish_metodo,'')     AS fish_metodo,
        COALESCE(ri.fish_maquinas,'')   AS fish_maquinas,
        COALESCE(ri.fish_materiales,'') AS fish_materiales,
        COALESCE(ri.fish_personas,'')   AS fish_personas,
        COALESCE(ri.fish_entorno,'')    AS fish_entorno,
        COALESCE(ri.fish_medicion,'')   AS fish_medicion,
        COALESCE(u.nombre_completo, u.username, '') AS responsable
    FROM reclamo_imputados ri
    LEFT JOIN usuarios u ON u.id = ri.imputado_id
    WHERE ri.reclamo_id = ?
      AND ri.estado_asignacion = 'aprobado'
      AND ri.estado_respuesta  = 'aprobada'
"""

_SQL_FIRMANTE = """
    SELECT TOP 1
        COALESCE(u.nombre_completo, u.username) AS nombre,
        COALESCE(p.nombre, '')                  AS cargo
    FROM usuarios u
    LEFT JOIN puestos p ON p.id = u.puesto_id
    WHERE u.id = ?
      AND COALESCE(u.disabled, 0) = 0
"""


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _fmt_fecha_es(valor) -> str:
    """
    Convierte fechas a formato:
        29 de mayo de 2026

    Soporta:
        - YYYY-MM-DD
        - DD/MM/YYYY
        - datetime/date
    """
    meses = [
        "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    ]

    if not valor:
        return ""

    if isinstance(valor, datetime):
        return f"{valor.day} de {meses[valor.month]} de {valor.year}"

    if hasattr(valor, "day") and hasattr(valor, "month") and hasattr(valor, "year"):
        return f"{valor.day} de {meses[valor.month]} de {valor.year}"

    s = str(valor).strip()

    # DD/MM/YYYY
    try:
        if "/" in s:
            d, m, y = s[:10].split("/")
            d, m, y = int(d), int(m), int(y)
            return f"{d} de {meses[m]} de {y}"
    except Exception:
        pass

    # YYYY-MM-DD
    try:
        s10 = s[:10]
        y, m, d = int(s10[0:4]), int(s10[5:7]), int(s10[8:10])
        return f"{d} de {meses[m]} de {y}"
    except Exception:
        return s


def _consolidar_respuestas(rows: list[dict]) -> dict:
    causas: list[str] = []
    preventivas: list[str] = []
    correctivas: list[str] = []
    responsables: list[str] = []
    analisis_extra: list[str] = []

    for r in rows:
        if r.get("causa"):
            causas.append(str(r["causa"]).strip())

        if r.get("preventiva"):
            preventivas.append(str(r["preventiva"]).strip())

        if r.get("correctiva"):
            correctivas.append(str(r["correctiva"]).strip())

        if r.get("responsable"):
            responsables.append(str(r["responsable"]).strip())

        whys = [
            str(r.get(f"why{i}", "") or "").strip()
            for i in range(1, 6)
            if str(r.get(f"why{i}", "") or "").strip()
        ]

        if whys:
            analisis_extra.append("5 Por Qué: " + " -> ".join(whys))

        fish_fields = [
            ("Método",     r.get("fish_metodo", "")),
            ("Máquinas",   r.get("fish_maquinas", "")),
            ("Materiales", r.get("fish_materiales", "")),
            ("Personas",   r.get("fish_personas", "")),
            ("Entorno",    r.get("fish_entorno", "")),
            ("Medición",   r.get("fish_medicion", "")),
        ]

        fish_parts = [
            f"{k}: {str(v).strip()}"
            for k, v in fish_fields
            if str(v or "").strip()
        ]

        if fish_parts:
            analisis_extra.append("Ishikawa: " + "; ".join(fish_parts))

    return {
        "causa": "\n".join(causas) or "Sin detalle registrado.",
        "preventiva": "\n".join(preventivas) or "Sin detalle registrado.",
        "correctiva": "\n".join(correctivas) or "Sin detalle registrado.",
        "responsables": "; ".join(sorted(set(responsables))),
        "analisis_extra": "\n".join(analisis_extra),
    }


def _generar_textos_openai(om: dict, respuestas: dict) -> dict:
    """
    Genera los textos formales para cliente.
    Si OpenAI falla, la función principal usa fallback.
    """
    from openai import OpenAI

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    prompt = f"""Eres el redactor de cartas formales del departamento de Servicio al Cliente de QUIMPAC,
empresa química ecuatoriana. Debes redactar 4 párrafos en lenguaje formal, claro y NO técnico
para enviar al cliente como respuesta a su caso registrado.

DATOS DEL CASO:
- Código: {om['codigo']}
- Cliente: {om['cliente_nombre']}
- Tipo de caso: {om['tipo_reclamo']}
- Producto/Servicio: {om['material']}
- Motivo reportado: {om['motivo']}
- Observación original: {om['observacion']}

ANÁLISIS TÉCNICO INTERNO:
- Causa raíz identificada: {respuestas['causa']}
- Análisis adicional: {respuestas['analisis_extra']}
- Acción preventiva tomada: {respuestas['preventiva']}
- Acción correctiva implementada: {respuestas['correctiva']}

Redacta EXACTAMENTE los siguientes 4 párrafos en español formal ecuatoriano.
Responde SOLO con JSON, sin markdown, con estas claves:

{{
  "descripcion": "Párrafo de 2-3 oraciones describiendo qué ocurrió según lo reportado por el cliente, sin culpar ni ser defensivos.",
  "analisis": "Párrafo de 2-3 oraciones explicando la causa identificada en lenguaje no técnico, sin revelar detalles internos sensibles.",
  "acciones": "Párrafo de 2-4 oraciones describiendo las acciones concretas que se tomaron para corregir el problema y evitar que se repita.",
  "cierre": "Párrafo corto de 1-2 oraciones de compromiso de mejora continua e invitación a contactar para cualquier consulta."
}}"""

    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=900,
        response_format={"type": "json_object"},
    )

    raw = resp.choices[0].message.content or "{}"
    data = json.loads(raw)

    return {
        "descripcion": data.get("descripcion", ""),
        "analisis": data.get("analisis", ""),
        "acciones": data.get("acciones", ""),
        "cierre": data.get("cierre", ""),
    }


def _pisa_link_callback(uri, rel):
    """
    Convierte rutas /static/... de Flask en rutas físicas para xhtml2pdf.

    Ejemplo:
        /static/css/reclamos/reclamos_carta_cliente_pdf.css

    Se convierte en:
        C:/.../Sili/static/css/reclamos/reclamos_carta_cliente_pdf.css
    """
    from flask import current_app

    try:
        parsed = urlparse(uri)

        if parsed.scheme in ("http", "https"):
            path = parsed.path
        else:
            path = uri

        path = unquote(path or "").replace("\\", "/")

        if path.startswith("/static/"):
            relative_path = path[len("/static/"):]
            full_path = Path(current_app.static_folder) / relative_path

        elif path.startswith("static/"):
            relative_path = path[len("static/"):]
            full_path = Path(current_app.static_folder) / relative_path

        else:
            full_path = Path(current_app.static_folder) / path.lstrip("/")

        full_path = full_path.resolve()

        current_app.logger.warning(
            "[PDF_RESOURCE] uri=%s | rel=%s | full_path=%s | existe=%s",
            uri,
            rel,
            full_path,
            full_path.exists()
        )

        if full_path.exists():
            return str(full_path)

        return uri

    except Exception:
        current_app.logger.exception(
            "[PDF_RESOURCE] Error resolviendo recurso uri=%s rel=%s",
            uri,
            rel
        )
        return uri


# ─────────────────────────────────────────────────────────────
# Función principal
# ─────────────────────────────────────────────────────────────

def generar_carta_cliente_pdf(
    conn,
    reclamo_id: int,
    firmante_uid: int,
) -> tuple[bytes, str]:
    """
    Genera el PDF corporativo de carta al cliente.

    Returns:
        (pdf_bytes, filename)

    Raises:
        ValueError: OM no encontrada, no cerrada o no requiere carta.
        RuntimeError: error al generar PDF.
    """
    from flask import render_template, url_for

    cur = conn.cursor()

    # 1. Datos de la OM
    cur.execute(_SQL_OM, (reclamo_id,))
    om_row = cur.fetchone()

    if not om_row:
        raise ValueError(f"OM {reclamo_id} no encontrada.")

    om = dict(om_row)

    estado_global = (om.get("estado_global") or "").strip().lower()

    if estado_global != "cerrado":
        raise ValueError("La OM debe estar cerrada para generar la carta.")

    if not int(om.get("requiere_carta_cliente") or 0):
        raise ValueError("Esta OM no fue marcada como OM con carta al cliente.")

    # 2. Respuestas técnicas aprobadas
    cur.execute(_SQL_RESPUESTAS, (reclamo_id,))
    resp_rows = [dict(r) for r in cur.fetchall()]
    respuestas = _consolidar_respuestas(resp_rows)

    # 3. Firmante
    cur.execute(_SQL_FIRMANTE, (firmante_uid,))
    firmante_row = cur.fetchone()

    firmante_nombre = firmante_row["nombre"] if firmante_row else "Coordinador"
    firmante_cargo = firmante_row["cargo"] if firmante_row else "Coordinador de Servicio al Cliente"

    # 4. Textos de la carta
    try:
        textos = _generar_textos_openai(om, respuestas)
    except Exception as exc:
        log.error("[carta_pdf] OpenAI error: %s", exc)
        textos = {
            "descripcion": om.get("observacion", ""),
            "analisis": respuestas["causa"],
            "acciones": f"{respuestas['preventiva']}\n{respuestas['correctiva']}".strip(),
            "cierre": (
                "Nos comprometemos a mejorar continuamente nuestros procesos "
                "y a brindar un servicio de calidad."
            ),
        }

    today_str = _fmt_fecha_es(date.today().isoformat())

    # IMPORTANTE:
    # Estas rutas las resuelve xhtml2pdf con _pisa_link_callback.
    logo_url = url_for("static", filename="quimpac_logo.png")

    context = {
        "codigo": om["codigo"],
        "fecha_reclamo": _fmt_fecha_es(str(om.get("fecha_reclamo", ""))),
        "fecha_emision": today_str,
        "ciudad": "QUITO",

        "cliente_nombre": om.get("cliente_nombre", ""),
        "cliente_contacto": om.get("cliente_contacto") or "",
        "cliente_email": om.get("cliente_email") or "",

        "tipo_reclamo": om.get("tipo_reclamo", ""),
        "material": om.get("material", ""),
        "proceso": om.get("proceso", ""),
        "motivo": om.get("motivo", ""),

        "descripcion": textos["descripcion"],
        "analisis": textos["analisis"],
        "acciones": textos["acciones"],
        "cierre": textos["cierre"],

        "causa_raw": respuestas.get("causa", ""),
        "preventiva_raw": respuestas.get("preventiva", ""),
        "correctiva_raw": respuestas.get("correctiva", ""),
        "responsables_raw": respuestas.get("responsables", ""),

        "firmante_nombre": firmante_nombre,
        "firmante_cargo": firmante_cargo,

        "logo_url": logo_url,

        "empresa_nombre": "QUIMPAC Ecuador S.A.",
        "area_nombre": "GESTIÓN DE SERVICIO AL CLIENTE",
        "documento_subtitulo": "Respuesta a Oportunidad de Mejora",
        "direccion_linea": (
            "Guayaquil: Km 16,5 Vía a Daule | "
            "Quito: Panamericana Sur Km 14,5 | "
            "www.quimpac.com.ec"
        ),
    }

    html_str = render_template("reclamos_carta_cliente_pdf.html", **context)

    # 5. Convertir a PDF
    try:
        from xhtml2pdf import pisa

        buf = io.BytesIO()

        result = pisa.pisaDocument(
            io.StringIO(html_str),
            dest=buf,
            encoding="utf-8",
            link_callback=_pisa_link_callback,
        )

        if result.err:
            raise RuntimeError(f"xhtml2pdf reportó errores al renderizar: {result.err}")

        pdf_bytes = buf.getvalue()

    except ImportError:
        log.error("[carta_pdf] xhtml2pdf no instalado.")
        raise RuntimeError("Librería xhtml2pdf no encontrada. Ejecuta: pip install xhtml2pdf")

    except Exception as exc:
        log.error("[carta_pdf] xhtml2pdf error: %s", exc)
        raise RuntimeError(f"Error al generar PDF: {exc}") from exc

    filename = f"Carta_Cliente_{om['codigo']}_{date.today().isoformat()}.pdf"

    return pdf_bytes, filename