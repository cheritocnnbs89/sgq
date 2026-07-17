# modules/gastos_auto_registro.py
# ==========================================================
# Auto-registro de gastos tipo tarjeta a partir de facturas
# recurrentes ya sincronizadas en facturas_xml (seedbilling).
#
# Reglas configurables (gastos_auto_registro_reglas): RUC + monto
# exacto -> motivo (cuenta contable) + centro de costo + usuario
# dueño/notificado + si se envía solo a SAP.
# ==========================================================
from __future__ import annotations

import json
from datetime import datetime

from flask import current_app

from . import gastos_helpers as gh
from .config import TABLE_GASTOS

TPL_GASTO_AUTO_REGISTRADO = "gasto_auto_registrado"


def _exec(cur, sql, params=None):
    cur.execute(sql, params) if params is not None else cur.execute(sql)
    return cur


def ensure_auto_registro_template(conn) -> None:
    """Da de alta (o actualiza) la plantilla de notificación, idempotente."""
    cur = conn.cursor()

    subject = "📎 Gasto #{{ gasto_id }} registrado automáticamente"
    html = """\
<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f3f4f6;font-family:Segoe UI,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:24px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="640" cellpadding="0" cellspacing="0"
                 style="max-width:640px;background:#ffffff;border-radius:10px;border:1px solid #e5e7eb;overflow:hidden;">
            <tr>
              <td style="background:#0f766e;padding:18px 22px;color:#ffffff;">
                <div style="font-size:12px;text-transform:uppercase;letter-spacing:.08em;opacity:.92;">
                  GASTOS CON TARJETA — AUTO-REGISTRO
                </div>
                <div style="font-size:18px;font-weight:600;margin-top:4px;">
                  Gasto auto-registrado #{{ gasto_id }}
                </div>
              </td>
            </tr>
            <tr>
              <td style="padding:20px 22px;color:#111827;font-size:14px;line-height:1.5;">
                <p>Hola {{ usuario }}, el sistema reconoció una factura recurrente y registró
                automáticamente el gasto <b>#{{ gasto_id }}</b>, ya aprobado.</p>
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:12px;">
                  <tr><td style="padding:6px 0;color:#6b7280;">Proveedor</td><td style="padding:6px 0;text-align:right;">{{ proveedor }}</td></tr>
                  <tr><td style="padding:6px 0;color:#6b7280;">Motivo</td><td style="padding:6px 0;text-align:right;">{{ motivo }}</td></tr>
                  <tr><td style="padding:6px 0;color:#6b7280;">Fecha factura</td><td style="padding:6px 0;text-align:right;">{{ fecha }}</td></tr>
                  <tr><td style="padding:6px 0;color:#6b7280;">Total</td><td style="padding:6px 0;text-align:right;">${{ total_con_iva_fmt }}</td></tr>
                </table>
                {% if gasto_url %}
                <p style="margin-top:16px;">
                  <a href="{{ gasto_url }}" style="background:#0f766e;color:#fff;padding:10px 16px;border-radius:6px;text-decoration:none;font-weight:600;">Ver gasto</a>
                </p>
                {% endif %}
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""
    text = "Gasto #{{ gasto_id }} registrado automáticamente. Proveedor: {{ proveedor }}. Total: {{ total_con_iva_fmt }}."

    _exec(cur, """
        UPDATE notify_templates
           SET tipo = ?, subject = ?, html = ?, text = ?
         WHERE [key] = ?
    """, ("gasto", subject, html, text, TPL_GASTO_AUTO_REGISTRADO))

    if cur.rowcount == 0:
        _exec(cur, """
            INSERT INTO notify_templates ([key], tipo, subject, html, text)
            VALUES (?, ?, ?, ?, ?)
        """, (TPL_GASTO_AUTO_REGISTRADO, "gasto", subject, html, text))

    conn.commit()


def _resolver_proveedor(conn, ruc: str, nombre_fallback: str):
    cur = conn.cursor()
    ruc = (ruc or "").strip()

    cur.execute("""
        SELECT id, nombre, codigo_sap FROM terceros
        WHERE identificacion = ? AND UPPER(LTRIM(RTRIM(tipo))) = 'P'
    """, (ruc,))
    row = cur.fetchone()
    if row:
        return row["id"], row["nombre"]

    cur.execute("""
        INSERT INTO terceros (nombre, identificacion, tipo, activo)
        OUTPUT INSERTED.id
        VALUES (?, ?, 'P', 1)
    """, (nombre_fallback, ruc))
    new_row = cur.fetchone()
    if not new_row:
        raise ValueError(f"No se pudo crear el proveedor para RUC {ruc}")
    return new_row[0], nombre_fallback


def _detalle_desde_factura(conn, factura_id: int) -> list[dict]:
    """
    Agrupa las líneas de facturas_xml_det por indicador (CE/C0), igual que el
    preload manual (nuevo_gasto?from_xml=<id>) — así los montos de un gasto
    auto-registrado se calculan exactamente igual que uno creado a mano desde XML.
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT descripcion, cantidad, precio_unitario,
               COALESCE(descuento, 0)      AS descuento,
               COALESCE(base_imponible, 0) AS base_imponible,
               COALESCE(iva, 0)            AS iva,
               COALESCE(total_linea, 0)    AS total_linea
        FROM facturas_xml_det
        WHERE factura_id = ?
        ORDER BY id
    """, (factura_id,))
    det_rows = cur.fetchall()

    grupos: dict[str, dict] = {}
    for d in det_rows:
        base = float(d["base_imponible"] or 0)
        iva = float(d["iva"] or 0)
        tot = float(d["total_linea"] or 0)
        if tot == 0:
            tot = base + iva
        ind = "CE" if iva > 0 else "C0"
        g = grupos.setdefault(ind, {"base": 0.0, "iva": 0.0, "tot": 0.0})
        g["base"] += base
        g["iva"] += iva
        g["tot"] += tot

    return [
        {
            "indicador": ind,
            "con_soporte": round(g["base"], 2) if ind != "C0" else 0,
            "sin_soporte": 0,
            "subtotal_factura": round(g["base"], 2),
            "servicios_10": 0,
            "subtotal_sin_iva": 0 if ind != "C0" else round(g["base"], 2),
            "iva": round(g["iva"], 2),
            "total_con_iva": round(g["tot"], 2),
        }
        for ind, g in grupos.items()
    ]


def _crear_gasto_desde_factura(conn, factura: dict, regla: dict) -> int:
    cur = conn.cursor()

    pid, prov_nombre = _resolver_proveedor(conn, factura["ruc_emisor"], factura["razon_social_emisor"])

    fecha_emision = factura.get("fecha_emision") or ""
    try:
        d, m, y = fecha_emision.split("/")
        fecha = f"{y}-{m}-{d}"
        anio, mes, dia = int(y), int(m), int(d)
    except Exception:
        hoy = datetime.now()
        fecha = hoy.strftime("%Y-%m-%d")
        anio, mes, dia = hoy.year, hoy.month, hoy.day

    numero_factura = "-".join([
        (factura.get("estab") or "").strip(),
        (factura.get("pto_emi") or "").strip(),
        str(factura.get("secuencial") or "0").strip().zfill(9),
    ])

    detalle_rows = _detalle_desde_factura(conn, factura["id"])
    if not detalle_rows:
        # Sin líneas de detalle (no debería pasar si la factura ya se sincronizó
        # completa) -> se arma una sola línea con los totales de cabecera.
        detalle_rows = [{
            "indicador": "C0" if float(factura.get("iva") or 0) == 0 else "CE",
            "con_soporte": 0,
            "sin_soporte": 0,
            "subtotal_factura": float(factura.get("subtotal") or 0),
            "servicios_10": 0,
            "subtotal_sin_iva": float(factura.get("subtotal") or 0),
            "iva": float(factura.get("iva") or 0),
            "total_con_iva": float(factura.get("total") or 0),
        }]

    totales = {k: 0.0 for k in (
        "con_soporte", "sin_soporte", "subtotal_factura",
        "servicios_10", "subtotal_sin_iva", "iva", "total_con_iva"
    )}
    for r in detalle_rows:
        for k in totales:
            totales[k] += r[k]

    impuestos_json = json.dumps({
        "iva": [
            {"tarifa": 0.0, "base": r["subtotal_sin_iva"], "valor": r["iva"], "indicador": r["indicador"]}
            for r in detalle_rows
        ]
    }, ensure_ascii=False)

    now = datetime.now()
    usuario_id = regla["usuario_id"]

    cur.execute(f"""
        INSERT INTO {TABLE_GASTOS}
        (
            anio, mes, dia, fecha, motivo, proveedor_id, proveedor, centro_costo,
            con_soporte, sin_soporte, subtotal_factura, servicios_10,
            subtotal_sin_iva, iva, total_con_iva, archivo, usuario_id,
            fecha_autorizacion, numero_factura, orden_compra,
            clave_autorizacion, ccb, factura_xml_id,
            reembolso_vendedor, es_caja_chica, tarjeta_sin_soporte,
            impuestos_json, boletos_aereos,
            ga_aprobado, ga_aprobado_por, ga_aprobado_at,
            gg_aprobado, gg_aprobado_por, gg_aprobado_at,
            gf_aprobado, gf_aprobado_por, gf_aprobado_at,
            coord_revisado, coord_revisado_por, coord_revisado_at
        )
        OUTPUT INSERTED.id
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,
                1,?,?, 1,?,?, 1,?,?, 1,?,?)
    """, (
        anio, mes, dia, fecha, regla["motivo"], pid, prov_nombre, regla["centro_costo"],
        totales["con_soporte"], totales["sin_soporte"], totales["subtotal_factura"], totales["servicios_10"],
        totales["subtotal_sin_iva"], totales["iva"], totales["total_con_iva"],
        None, usuario_id,
        factura.get("fecha_autorizacion") or "", numero_factura, "",
        factura.get("clave_acceso") or "", 0, factura["id"],
        0, 0, 0,
        impuestos_json, 0,
        usuario_id, now,
        usuario_id, now,
        usuario_id, now,
        usuario_id, now,
    ))
    gasto_row = cur.fetchone()
    gasto_id = gasto_row[0] if gasto_row else None
    if not gasto_id:
        raise ValueError("No se pudo recuperar el id del gasto auto-registrado.")

    for r in detalle_rows:
        cur.execute("""
            INSERT INTO gastos_tarjeta_detalle(
                gasto_id, descripcion, observacion, centro_costo, motivo, indicador,
                con_soporte, sin_soporte, subtotal_factura, servicios_10,
                subtotal_sin_iva, iva, total_con_iva
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            gasto_id, "Auto-registro factura recurrente", "", regla["centro_costo"], regla["motivo"],
            r["indicador"], r["con_soporte"], r["sin_soporte"], r["subtotal_factura"],
            r["servicios_10"], r["subtotal_sin_iva"], r["iva"], r["total_con_iva"]
        ))

    cur.execute("""
        UPDATE facturas_xml SET estado = 'PROCESADO'
        WHERE id = ? AND estado = 'PENDIENTE'
    """, (factura["id"],))

    gh.recalc_gasto_totales(conn, gasto_id)

    return gasto_id


def _enqueue_notificacion(conn, gasto_id: int, usuario_id: int, motivo: str) -> None:
    payload = json.dumps({"gasto_id": int(gasto_id), "motivo": motivo}, ensure_ascii=False)
    event_key = f"gasto_auto_registrado:{int(gasto_id)}"
    cur = conn.cursor()
    cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM notify_queue WHERE event_key = ?)
        BEGIN
            INSERT INTO notify_queue (
                user_id, tipo, fecha_obj, canal, template_key, payload_json,
                estado, scheduled_at, gasto_id, area, event_key
            )
            VALUES (?, ?, GETDATE(), 'email', ?, ?, 'pending', GETDATE(), ?, 'auto', ?)
        END
    """, (
        event_key,
        usuario_id, TPL_GASTO_AUTO_REGISTRADO, TPL_GASTO_AUTO_REGISTRADO, payload,
        gasto_id, event_key
    ))


def procesar_auto_registro_facturas(conn) -> list[int]:
    """
    Job idempotente: por cada regla activa, busca facturas_xml PENDIENTE que
    calcen (mismo RUC + mismo monto exacto), crea el gasto ya aprobado,
    marca la factura como PROCESADO y encola la notificación. Correrlo varias
    veces seguidas es seguro: una factura ya PROCESADO no se vuelve a tomar.
    """
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT id, ruc_proveedor, monto, motivo, centro_costo, usuario_id, enviar_sap_auto
            FROM gastos_auto_registro_reglas
            WHERE COALESCE(activo, 1) = 1
        """)
        reglas = cur.fetchall()
    except Exception:
        _log_warn("procesar_auto_registro_facturas: tabla gastos_auto_registro_reglas no existe todavía.")
        return []

    if not reglas:
        return []

    ensure_auto_registro_template(conn)

    gastos_creados = []
    reglas_a_enviar_sap = []

    for regla in reglas:
        regla_d = dict(regla)
        cur.execute("""
            SELECT id, clave_acceso, estab, pto_emi, secuencial,
                   fecha_emision, fecha_autorizacion, razon_social_emisor,
                   ruc_emisor, subtotal, iva, total
            FROM facturas_xml
            WHERE ruc_emisor = ? AND total = ? AND estado = 'PENDIENTE'
        """, (regla_d["ruc_proveedor"], regla_d["monto"]))
        facturas = cur.fetchall()

        for factura in facturas:
            factura_d = dict(factura)
            try:
                gasto_id = _crear_gasto_desde_factura(conn, factura_d, regla_d)
                conn.commit()
            except Exception:
                conn.rollback()
                _log_exception(
                    "procesar_auto_registro_facturas: fallo creando gasto desde factura_id=%s regla_id=%s",
                    factura_d.get("id"), regla_d.get("id")
                )
                continue

            try:
                _enqueue_notificacion(conn, gasto_id, regla_d["usuario_id"], regla_d["motivo"])
                conn.commit()
            except Exception:
                conn.rollback()
                _log_exception("procesar_auto_registro_facturas: fallo encolando notificación gasto_id=%s", gasto_id)

            gastos_creados.append(gasto_id)
            if regla_d.get("enviar_sap_auto"):
                reglas_a_enviar_sap.append(gasto_id)

    if reglas_a_enviar_sap:
        _enviar_sap_auto(reglas_a_enviar_sap)

    return gastos_creados


def _enviar_sap_auto(gasto_ids: list[int]) -> None:
    """
    Reusa la ruta real enviar_gasto_sap (misma lógica que el botón manual,
    sin duplicarla) invocándola vía test_client con una sesión sintética de
    admin — mismo patrón que ya usa el gateway interno de la app.
    """
    try:
        app = current_app._get_current_object()
    except Exception:
        _log_warn("_enviar_sap_auto: sin app activa, se omite envío automático a SAP.")
        return

    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["usuario"] = "auto-registro"
            sess["usuario_id"] = 0
            sess["user_id"] = 0
            sess["rol"] = "admin"
            sess["logged_in"] = True

        for gasto_id in gasto_ids:
            try:
                resp = c.post(f"/reembolsos/gastos/{gasto_id}/enviar-sap")
                if resp.status_code != 200:
                    _log_warn("_enviar_sap_auto: gasto_id=%s status=%s body=%s",
                              gasto_id, resp.status_code, resp.get_data(as_text=True)[:300])
            except Exception:
                _log_exception("_enviar_sap_auto: fallo enviando gasto_id=%s a SAP", gasto_id)


def _log_warn(msg, *args):
    try:
        current_app.logger.warning(msg, *args)
    except Exception:
        pass


def _log_exception(msg, *args):
    try:
        current_app.logger.exception(msg % args if args else msg)
    except Exception:
        pass
