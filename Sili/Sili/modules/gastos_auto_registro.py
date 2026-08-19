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

TPL_GASTO_AUTO_REGISTRADO = "gasto_auto_registrado"     # verde — SAP auto enviado
TPL_PENDIENTE_SAP         = "gasto_auto_pendiente_sap"  # naranja — SAP pendiente manual


def _exec(cur, sql, params=None):
    cur.execute(sql, params) if params is not None else cur.execute(sql)
    return cur


_HTML_BASE = """\
<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f3f4f6;font-family:Segoe UI,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:24px 0;">
      <tr><td align="center">
        <table role="presentation" width="640" cellpadding="0" cellspacing="0"
               style="max-width:640px;background:#fff;border-radius:10px;border:1px solid #e5e7eb;overflow:hidden;">
          <tr>
            <td style="background:{header_color};padding:18px 22px;color:#fff;">
              <div style="font-size:11px;text-transform:uppercase;letter-spacing:.09em;opacity:.9;">
                GASTOS CON TARJETA — AUTO-REGISTRO
              </div>
              <div style="font-size:18px;font-weight:700;margin-top:5px;">{header_title}</div>
            </td>
          </tr>
          <tr>
            <td style="padding:22px 22px 8px;color:#111827;font-size:14px;line-height:1.6;">
              <p style="margin:0 0 14px;">Hola <b>{{{{ usuario }}}}</b>, {intro}</p>
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                     style="border-top:1px solid #e5e7eb;margin-top:4px;">
                <tr>
                  <td style="padding:8px 0;color:#6b7280;font-size:13px;">Proveedor</td>
                  <td style="padding:8px 0;text-align:right;font-weight:500;">{{{{ proveedor }}}}</td>
                </tr>
                <tr style="background:#f9fafb;">
                  <td style="padding:8px 0;color:#6b7280;font-size:13px;">Motivo</td>
                  <td style="padding:8px 0;text-align:right;font-weight:500;">{{{{ motivo }}}}</td>
                </tr>
                <tr>
                  <td style="padding:8px 0;color:#6b7280;font-size:13px;">Fecha factura</td>
                  <td style="padding:8px 0;text-align:right;font-weight:500;">{{{{ fecha }}}}</td>
                </tr>
                <tr style="background:#f9fafb;">
                  <td style="padding:8px 0;color:#6b7280;font-size:13px;">Total</td>
                  <td style="padding:8px 0;text-align:right;font-weight:700;font-size:15px;">${{{{ total_con_iva_fmt }}}}</td>
                </tr>
              </table>
              <p style="margin:18px 0 4px;">
                <a href="{{{{ gasto_url }}}}"
                   style="background:{btn_color};color:#fff;padding:10px 18px;border-radius:6px;text-decoration:none;font-weight:600;margin-right:8px;">{btn_label}</a>
                {sap_btn}
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding:12px 22px;font-size:11px;color:#9ca3af;border-top:1px solid #f3f4f6;">
              Este correo fue generado automáticamente por el sistema de Sili.
            </td>
          </tr>
        </table>
      </td></tr>
    </table>
  </body>
</html>"""

_SAP_BTN = ('<a href="{gasto_url}" '
            'style="background:#1d4ed8;color:#fff;padding:10px 18px;border-radius:6px;'
            'text-decoration:none;font-weight:600;">Enviar a SAP</a>')


def _render_html(header_color, header_title, intro, btn_color, btn_label, include_sap_btn=False):
    sap_btn = _SAP_BTN.replace("{gasto_url}", "{{ gasto_url }}") if include_sap_btn else ""
    return _HTML_BASE.format(
        header_color=header_color,
        header_title=header_title,
        intro=intro,
        btn_color=btn_color,
        btn_label=btn_label,
        sap_btn=sap_btn,
    )


def _upsert_template(cur, key, subject, html, text):
    _exec(cur, "UPDATE notify_templates SET tipo=?,subject=?,html=?,text=? WHERE [key]=?",
          ("gasto", subject, html, text, key))
    if cur.rowcount == 0:
        _exec(cur, "INSERT INTO notify_templates ([key],tipo,subject,html,text) VALUES (?,?,?,?,?)",
              (key, "gasto", subject, html, text))


def ensure_auto_registro_template(conn) -> None:
    """Da de alta (o actualiza) ambas plantillas de notificación, idempotente."""
    cur = conn.cursor()

    # Verde — SAP enviado automáticamente
    html_verde = _render_html(
        header_color="#15803d",
        header_title="✅ Gasto #{{ gasto_id }} registrado y enviado a SAP",
        intro="el sistema reconoció una factura recurrente, registró el gasto "
              "<b>#{{ gasto_id }}</b> ya aprobado y lo envió a SAP automáticamente.",
        btn_color="#15803d",
        btn_label="Ver gasto",
        include_sap_btn=False,
    )
    _upsert_template(
        cur, TPL_GASTO_AUTO_REGISTRADO,
        subject="✅ Gasto #{{ gasto_id }} registrado y enviado a SAP",
        html=html_verde,
        text="Gasto #{{ gasto_id }} registrado y enviado a SAP. Proveedor: {{ proveedor }}. Total: ${{ total_con_iva_fmt }}.",
    )

    # Naranja — SAP pendiente de envío manual
    html_naranja = _render_html(
        header_color="#ea580c",
        header_title="📎 Gasto #{{ gasto_id }} registrado — SAP pendiente",
        intro="el sistema reconoció una factura recurrente y registró el gasto "
              "<b>#{{ gasto_id }}</b> ya aprobado. El envío a SAP queda pendiente.",
        btn_color="#ea580c",
        btn_label="Ver gasto",
        include_sap_btn=False,
    )
    _upsert_template(
        cur, TPL_PENDIENTE_SAP,
        subject="📎 Gasto #{{ gasto_id }} registrado — SAP pendiente",
        html=html_naranja,
        text="Gasto #{{ gasto_id }} registrado, SAP pendiente. Proveedor: {{ proveedor }}. Total: ${{ total_con_iva_fmt }}.",
    )

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
            coord_revisado, coord_revisado_por, coord_revisado_at,
            auto_registro_regla_id
        )
        OUTPUT INSERTED.id
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,
                1,?,?, 1,?,?, 1,?,?, 1,?,?,?)
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
        regla["id"],
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

    # facturas_xml.estado es exclusivo de Sili (rutina usa su propia columna
    # estado_xml_sap) -> seguro marcarlo aquí sin pisar el flujo de "rutina".
    cur.execute("UPDATE facturas_xml SET estado = 'PROCESADO' WHERE id = ?", (factura["id"],))

    gh.recalc_gasto_totales(conn, gasto_id)

    return gasto_id


def _enqueue_notificacion(conn, gasto_id: int, usuario_id: int, motivo: str, sap_auto: bool = False) -> None:
    tpl = TPL_GASTO_AUTO_REGISTRADO if sap_auto else TPL_PENDIENTE_SAP
    event_key = f"gasto_auto_registrado:{int(gasto_id)}"
    # notify_queue tiene un índice único uq_notify_hoy(user_id, fecha_obj,
    # canal, tipo) -- pensado para el recordatorio diario de "tareas de
    # hoy", no para esto. Si "tipo" se dejara igual a tpl (solo 2 valores
    # posibles), el segundo gasto auto-registrado del mismo usuario en el
    # mismo día chocaría contra ese índice y el BEGIN CATCH de abajo lo
    # descartaría en silencio -- exactamente lo que pasaba en producción.
    # Se agrega el gasto_id para que "tipo" sea único por gasto, sin tocar
    # template_key (que es lo que de verdad resuelve la plantilla del
    # correo) ni el prefijo "gasto_" (scheduler_services.py lo usa para
    # detectar que debe enriquecer el payload con proveedor/motivo/total).
    tipo_row = f"{tpl}:{int(gasto_id)}"
    cur = conn.cursor()

    cur.execute("""
        SELECT g.total_con_iva, g.proveedor, g.fecha, u.username
        FROM gastos_tarjeta g
        LEFT JOIN usuarios u ON u.id = g.usuario_id
        WHERE g.id = ?
    """, (gasto_id,))
    row = cur.fetchone()
    total_fmt = f"{float(row['total_con_iva'] or 0):,.2f}" if row else "0,00"
    proveedor = (row["proveedor"] or "") if row else ""
    fecha_raw = row["fecha"] if row else None
    fecha = fecha_raw.isoformat() if hasattr(fecha_raw, "isoformat") else str(fecha_raw or "")
    usuario = (row["username"] or "") if row else ""

    payload = json.dumps({
        "gasto_id": int(gasto_id),
        "motivo": motivo,
        "total_con_iva_fmt": total_fmt,
        "proveedor": proveedor,
        "fecha": fecha,
        "usuario": usuario,
    }, ensure_ascii=False)
    cur.execute("""
        BEGIN TRY
            IF NOT EXISTS (SELECT 1 FROM notify_queue WHERE event_key = ?)
            BEGIN
                INSERT INTO notify_queue (
                    user_id, tipo, fecha_obj, canal, template_key, payload_json,
                    estado, scheduled_at, gasto_id, area, event_key
                )
                VALUES (?, ?, GETDATE(), 'email', ?, ?, 'pending', GETDATE(), ?, 'auto', ?)
            END
        END TRY
        BEGIN CATCH
            -- índice único por user+tipo+fecha+canal; cada gasto tiene su event_key,
            -- pero el constraint no incluye gasto_id -> se ignora el duplicado
        END CATCH
    """, (
        event_key,
        usuario_id, tipo_row, tpl, payload,
        gasto_id, event_key
    ))


def procesar_auto_registro_facturas(conn) -> list[int]:
    """
    Job idempotente: por cada regla activa, busca facturas_xml que calcen
    (mismo RUC + mismo monto exacto) y que todavía no tengan un gastos_tarjeta
    asociado (factura_xml_id), crea el gasto ya aprobado, marca
    facturas_xml.estado = 'PROCESADO' y encola la notificación.

    facturas_xml.estado es de uso exclusivo de Sili -> el proceso externo
    "rutina" (generación del XML SRI/SAP) usa su propia columna
    estado_xml_sap, así que no hay colisión entre los dos.

    Correrlo varias veces seguidas es seguro: una factura con gasto ya
    creado no se vuelve a tomar (NOT EXISTS contra gastos_tarjeta).
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
            SELECT f.id, f.clave_acceso, f.estab, f.pto_emi, f.secuencial,
                   f.fecha_emision, f.fecha_autorizacion, f.razon_social_emisor,
                   f.ruc_emisor, f.subtotal, f.iva, f.total
            FROM facturas_xml f
            WHERE f.ruc_emisor = ? AND f.total = ?
              AND NOT EXISTS (
                    SELECT 1 FROM gastos_tarjeta g WHERE g.factura_xml_id = f.id
              )
              AND TRY_CONVERT(date,
                    SUBSTRING(f.fecha_emision,7,4)+'-'+
                    SUBSTRING(f.fecha_emision,4,2)+'-'+
                    SUBSTRING(f.fecha_emision,1,2)) >= '2026-06-01'
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
                _enqueue_notificacion(
                    conn, gasto_id, regla_d["usuario_id"], regla_d["motivo"],
                    sap_auto=bool(regla_d.get("enviar_sap_auto")),
                )
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
