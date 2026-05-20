# modules/scheduler/scheduler_notifications.py
# ==========================================================
# Plantillas, encolado y envío por canal del scheduler.
# Conserva lógica de correos de tareas, gastos y OM.
# ==========================================================

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from typing import Optional

from flask import current_app

from .scheduler_security import _exec_retry, _log
from .scheduler_repository import (
    ensure_notify_schema,
    get_ultimo_jefe_activo,
    _get_ultimo_jefe_id,
    _get_user_contact,    _get_username,

)
from .scheduler_constants import (
    CANAL_EMAIL,
    CANAL_INAPP,
    CANAL_SLACK,
    TIPO_GASTO_APROBADO_USER,
    TIPO_GASTO_APROBADO_NEXT,
    TIPO_GASTO,
    TIPO_OM_D4,
    TIPO_OM_D5,
    TIPO_OM_D9,
    TIPO_OM_D10,
    TPL_TAREA_HOY,
    TPL_GASTO_USER_APPROVED,
    TPL_GASTO_NEXT_GG,
    TPL_GASTO_NEXT_GF,
    TPL_GASTO_NEXT_COORD,
    TPL_GASTO_NEXT,
    TPL_GASTO_RECHAZO_GG,
    TPL_OM_SPONSOR_D4,
    TPL_OM_JEFE_D5,
    TPL_OM_SPONSOR_JEFE_D9,
    TPL_OM_GG_D10,
)
from modules.routes_planilla_mensual import send_mail as send_mail_planilla

def ensure_core_templates(conn):
    cur = conn.cursor()

    templates = [
        (
            TPL_TAREA_HOY,
            "tarea",
            "📌 Tareas para hoy {{ fecha }} ({{ usuario }})",
            "<p>Hola {{ usuario }},</p>"
            "<p>Estas son tus tareas para <b>{{ fecha }}</b>:</p>"
            "{% if tareas_hoy_len and tareas_hoy_len > 0 %}"
            "<ul>"
            "{% for t in tareas_hoy %}"
            "<li>"
            "{{ t.departamento or '' }} — <b>{{ t.nombre }}</b>"
            "{% if t.frecuencia %} ({{ t.frecuencia }}){% endif %}"
            "{% if t.hecha %} ✅{% else %} ⏳{% endif %}"
            "</li>"
            "{% endfor %}"
            "</ul>"
            "{% else %}"
            "<p><i>No tienes tareas planificadas para hoy.</i></p>"
            "{% endif %}"
            "<p>{{ app_url }}</p>",
            "Tareas para hoy {{ fecha }} ({{ usuario }}). Total: {{ tareas_hoy_len or 0 }}",
        ),
    ]

    for key, tipo, subject, html, text in templates:
        cur.execute("""
            UPDATE notify_templates
               SET tipo = ?,
                   subject = ?,
                   html = ?,
                   text = ?
             WHERE [key] = ?
        """, (tipo, subject, html, text, key))

        if cur.rowcount == 0:
            cur.execute("""
                INSERT INTO notify_templates ([key], tipo, subject, html, text)
                VALUES (?, ?, ?, ?, ?)
            """, (key, tipo, subject, html, text))

    conn.commit()

def ensure_gasto_templates2(conn):
    cur = conn.cursor()

    templates = [
        (
            TPL_GASTO_USER_APPROVED,
            "gasto",
            "✅ Tu gasto #{{ gasto_id }} fue aprobado ({{ area|upper }})",
            "<p>Hola {{ usuario }},</p>"
            "<p>Tu gasto <b>#{{ gasto_id }}</b> fue aprobado por <b>{{ approved_by_user_id }}</b> ({{ area|upper }}).</p>"
            "<p>Revisa el detalle en el sistema.</p>",
            "Tu gasto #{{ gasto_id }} fue aprobado ({{ area|upper }}).",
        ),
        (
            TPL_GASTO_NEXT_GG,
            "gasto",
            "🟠 Aprobación pendiente GG: gasto #{{ gasto_id }}",
            "<p>Tienes un gasto pendiente de aprobación:</p><p><b>#{{ gasto_id }}</b></p>",
            "Aprobación pendiente GG: gasto #{{ gasto_id }}",
        ),
        (
            TPL_GASTO_NEXT_GF,
            "gasto",
            "🟠 Aprobación pendiente GF: gasto #{{ gasto_id }}",
            "<p>Tienes un gasto pendiente de aprobación:</p><p><b>#{{ gasto_id }}</b></p>",
            "Aprobación pendiente GF: gasto #{{ gasto_id }}",
        ),
        (
            TPL_GASTO_NEXT_COORD,
            "gasto",
            "🟠 Envío/Control: gasto #{{ gasto_id }}",
            "<p>Gasto listo para control/envío:</p><p><b>#{{ gasto_id }}</b></p>",
            "Control/Envío: gasto #{{ gasto_id }}",
        ),
        (
            TPL_GASTO_NEXT,
            "gasto",
            "🟠 Gasto pendiente: #{{ gasto_id }}",
            "<p>Tienes un gasto pendiente:</p><p><b>#{{ gasto_id }}</b></p>",
            "Gasto pendiente: #{{ gasto_id }}",
        ),
    ]

    for key, tipo, subject, html, text in templates:
        _exec_retry(cur, """
            INSERT OR IGNORE INTO notify_templates(key, tipo, subject, html, text)
            VALUES (?,?,?,?,?)
        """, (key, tipo, subject, html, text))

    conn.commit()


def ensure_gasto_templates3(conn):
    cur = conn.cursor()

    def upsert(key, tipo, subject, html, text):
        _exec_retry(cur, """
            INSERT INTO notify_templates(key, tipo, subject, html, text)
            VALUES (?,?,?,?,?)
            ON CONFLICT(key) DO UPDATE SET
                tipo    = excluded.tipo,
                subject = excluded.subject,
                html    = excluded.html,
                text    = excluded.text
        """, (key, tipo, subject, html, text))

    html_user_approved = """\
<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f3f4f6;font-family:Segoe UI,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:24px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="720" cellpadding="0" cellspacing="0"
                 style="max-width:720px;background:#ffffff;border-radius:8px;border:1px solid #e5e7eb;overflow:hidden;">

            <tr>
              <td style="background:#1d4ed8;padding:16px 20px;color:#ffffff;">
                <div style="font-size:12px;text-transform:uppercase;letter-spacing:.08em;opacity:.9;">
                  Gastos con tarjeta
                </div>
                <div style="font-size:18px;font-weight:700;margin-top:4px;">
                  Gasto aprobado #{{ gasto_id }}
                </div>
                <div style="font-size:12px;opacity:.95;margin-top:6px;">
                  Hola {{ usuario }}, tu gasto fue aprobado por {{ approved_by_user_id }} ({{ area|upper }}).
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:18px 20px 10px 20px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
                  <tr>
                    <td style="width:210px;background:#eef2ff;font-weight:600;padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;">ID</td>
                    <td style="padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;">#{{ gasto_id }}</td>
                  </tr>
                  <tr>
                    <td style="width:210px;background:#eef2ff;font-weight:600;padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;">Estado</td>
                    <td style="padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;">Aprobado ({{ area|upper }})</td>
                  </tr>
                  <tr>
                    <td style="width:210px;background:#eef2ff;font-weight:600;padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;">Fecha</td>
                    <td style="padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;">{{ fecha }}</td>
                  </tr>
                </table>

                <div style="margin-top:18px;margin-bottom:6px;text-align:left;">
                  <a href="{{ gasto_url }}"
                     style="display:inline-block;background:#2563eb;color:#ffffff;text-decoration:none;padding:10px 18px;border-radius:6px;font-weight:600;font-size:13px;">
                    Ver gasto
                  </a>
                </div>

                <div style="font-size:11px;color:#6b7280;margin-top:8px;">
                  Este mensaje fue generado automáticamente por el sistema.
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:10px 20px 14px 20px;border-top:1px solid #e5e7eb;font-size:11px;color:#9ca3af;">
                Este es un mensaje automático. No responda a este correo.
              </td>
            </tr>

          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""

    html_next_step = """\
<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f3f4f6;font-family:Segoe UI,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:24px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="720" cellpadding="0" cellspacing="0"
                 style="max-width:720px;background:#ffffff;border-radius:8px;border:1px solid #e5e7eb;overflow:hidden;">

            <tr>
              <td style="background:#1d4ed8;padding:16px 20px;color:#ffffff;">
                <div style="font-size:12px;text-transform:uppercase;letter-spacing:.08em;opacity:.9;">
                  Gastos con tarjeta
                </div>
                <div style="font-size:18px;font-weight:700;margin-top:4px;">
                  Acción requerida — Gasto #{{ gasto_id }}
                </div>
                <div style="font-size:12px;opacity:.95;margin-top:6px;">
                  {{ area|upper }} aprobó este gasto. Debes continuar el flujo.
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:18px 20px 10px 20px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
                  <tr>
                    <td style="width:210px;background:#eef2ff;font-weight:600;padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;">ID</td>
                    <td style="padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;">#{{ gasto_id }}</td>
                  </tr>
                  <tr>
                    <td style="width:210px;background:#eef2ff;font-weight:600;padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;">Creado por</td>
                    <td style="padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;">{{ creador|default('') }}</td>
                  </tr>
                  <tr>
                    <td style="width:210px;background:#eef2ff;font-weight:600;padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;">Fecha</td>
                    <td style="padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;">{{ fecha }}</td>
                  </tr>
                </table>

                <div style="margin-top:18px;margin-bottom:6px;text-align:left;">
                  <a href="{{ gasto_url }}"
                     style="display:inline-block;background:#2563eb;color:#ffffff;text-decoration:none;padding:10px 18px;border-radius:6px;font-weight:600;font-size:13px;">
                    Revisar y aprobar
                  </a>
                </div>

                <div style="font-size:11px;color:#6b7280;margin-top:8px;">
                  Este mensaje fue generado automáticamente por el sistema.
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:10px 20px 14px 20px;border-top:1px solid #e5e7eb;font-size:11px;color:#9ca3af;">
                Este es un mensaje automático. No responda a este correo.
              </td>
            </tr>

          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""

    upsert(
        TPL_GASTO_USER_APPROVED,
        "gasto",
        "✅ Tu gasto #{{ gasto_id }} fue aprobado ({{ area|upper }})",
        html_user_approved,
        "Tu gasto #{{ gasto_id }} fue aprobado ({{ area|upper }})."
    )
    upsert(TPL_GASTO_NEXT_GG, "gasto", "🟠 Aprobación pendiente GG: gasto #{{ gasto_id }}", html_next_step, "Aprobación pendiente GG: gasto #{{ gasto_id }}")
    upsert(TPL_GASTO_NEXT_GF, "gasto", "🟠 Aprobación pendiente GF: gasto #{{ gasto_id }}", html_next_step, "Aprobación pendiente GF: gasto #{{ gasto_id }}")
    upsert(TPL_GASTO_NEXT_COORD, "gasto", "🟠 Envío/Control: gasto #{{ gasto_id }}", html_next_step, "Control/Envío: gasto #{{ gasto_id }}")
    upsert(TPL_GASTO_NEXT, "gasto", "🟠 Gasto pendiente: #{{ gasto_id }}", html_next_step, "Gasto pendiente: #{{ gasto_id }}")

    conn.commit()


def ensure_gasto_templates(conn):
    cur = conn.cursor()
    def upsert(key, tipo, subject, html, text):
      cur.execute("""
          UPDATE notify_templates
            SET tipo = ?,
                subject = ?,
                html = ?,
                text = ?
          WHERE [key] = ?
      """, (tipo, subject, html, text, key))

      if cur.rowcount == 0:
          cur.execute("""
              INSERT INTO notify_templates ([key], tipo, subject, html, text)
              VALUES (?, ?, ?, ?, ?)
          """, (key, tipo, subject, html, text))

  
    JINJA_LABELS = """
{% set area_key = (area or '')|lower %}
{% if area_key == 'ga' %}
  {% set area_txt = 'Gerencia de Área' %}
  {% set next_txt = 'Gerencia General' %}
{% elif area_key == 'gg' %}
  {% set area_txt = 'Gerencia General' %}
  {% set next_txt = 'Gerencia Financiera' %}
{% elif area_key == 'gf' %}
  {% set area_txt = 'Gerencia Financiera' %}
  {% set next_txt = 'Coordinación' %}
{% else %}
  {% set area_txt = (area or '')|upper %}
  {% set next_txt = 'Siguiente aprobador' %}
{% endif %}
""".strip()

    html_user_approved = """\
<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f3f4f6;font-family:Segoe UI,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:24px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="720" cellpadding="0" cellspacing="0"
                 style="max-width:720px;background:#ffffff;border-radius:10px;border:1px solid #e5e7eb;overflow:hidden;">

            <tr>
              <td style="background:#1d4ed8;padding:18px 22px;color:#ffffff;">
                <div style="font-size:12px;text-transform:uppercase;letter-spacing:.08em;opacity:.92;">
                  GASTOS CON TARJETA
                </div>
                <div style="font-size:22px;font-weight:800;margin-top:4px;line-height:1.15;">
                  Gasto aprobado — #{{ gasto_id }}
                </div>
                <div style="font-size:13px;opacity:.92;margin-top:8px;line-height:1.35;">
                  """ + JINJA_LABELS + """
                  Hola {{ usuario }}, tu gasto fue aprobado por {{ approved_by_user_id }} ({{ area_txt }}).
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:18px 22px 10px 22px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                       style="border-collapse:separate;border-spacing:0;overflow:hidden;border-radius:10px;">

                  <tr>
                    <td style="width:280px;background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">ID</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">#{{ gasto_id }}</td>
                  </tr>

                  <tr>
                    <td style="width:280px;background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Fecha</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">{{ fecha }}</td>
                  </tr>

                  <tr>
                    <td style="width:280px;background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Proveedor</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">{{ proveedor|default('') }}</td>
                  </tr>

                  <tr>
                    <td style="width:280px;background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Motivo</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">{{ motivo|default('') }}</td>
                  </tr>

                  <tr>
                    <td style="width:280px;background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Total con IVA</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">${{ total_con_iva_fmt|default('0,00') }}</td>
                  </tr>

                  <tr>
                    <td style="width:280px;background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Estado</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Aprobado por {{ area_txt }}</td>
                  </tr>

                </table>

                <div style="margin-top:18px;">
                  <a href="{{ gasto_url }}"
                     style="display:inline-block;background:#2563eb;color:#ffffff;text-decoration:none;
                            padding:11px 18px;border-radius:8px;font-weight:700;font-size:13px;">
                    Ver gasto
                  </a>
                </div>

                <div style="font-size:12px;color:#6b7280;margin-top:12px;">
                  Este correo fue generado automáticamente por el sistema de Sili.
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:12px 22px 14px 22px;border-top:1px solid #e5e7eb;font-size:11px;color:#9ca3af;">
                Este es un mensaje automático. No responda a este correo.
              </td>
            </tr>

          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""

    html_next_step = """\
<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f3f4f6;font-family:Segoe UI,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:24px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="720" cellpadding="0" cellspacing="0"
                 style="max-width:720px;background:#ffffff;border-radius:10px;border:1px solid #e5e7eb;overflow:hidden;">

            <tr>
              <td style="background:#1d4ed8;padding:18px 22px;color:#ffffff;">
                <div style="font-size:12px;text-transform:uppercase;letter-spacing:.08em;opacity:.92;">
                  GASTOS CON TARJETA
                </div>
                <div style="font-size:22px;font-weight:800;margin-top:4px;line-height:1.15;">
                  Acción requerida — Gasto #{{ gasto_id }}
                </div>
                <div style="font-size:13px;opacity:.92;margin-top:8px;line-height:1.35;">
                  """ + JINJA_LABELS + """
                  {{ area_txt }} aprobó este gasto. Debes continuar con la aprobación ({{ next_txt }}).
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:18px 22px 10px 22px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                       style="border-collapse:separate;border-spacing:0;overflow:hidden;border-radius:10px;">

                  <tr>
                    <td style="width:280px;background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">ID</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">#{{ gasto_id }}</td>
                  </tr>

                  <tr>
                    <td style="width:280px;background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Fecha</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">{{ fecha }}</td>
                  </tr>

                  <tr>
                    <td style="width:280px;background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Proveedor</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">{{ proveedor|default('') }}</td>
                  </tr>

                  <tr>
                    <td style="width:280px;background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Motivo</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">{{ motivo|default('') }}</td>
                  </tr>

                  <tr>
                    <td style="width:280px;background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Total con IVA</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">${{ total_con_iva_fmt|default('0,00') }}</td>
                  </tr>

                  <tr>
                    <td style="width:280px;background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Creador</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">{{ creador|default('') }}</td>
                  </tr>

                  <tr>
                    <td style="width:280px;background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Estado</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Aprobado por {{ area_txt }}</td>
                  </tr>

                </table>

                <div style="margin-top:18px;">
                  <a href="{{ gasto_url }}"
                     style="display:inline-block;background:#2563eb;color:#ffffff;text-decoration:none;
                            padding:11px 18px;border-radius:8px;font-weight:700;font-size:13px;">
                    Revisar y aprobar gasto
                  </a>
                </div>

                <div style="font-size:12px;color:#6b7280;margin-top:12px;">
                  Este correo fue generado automáticamente por el sistema de Sili.
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:12px 22px 14px 22px;border-top:1px solid #e5e7eb;font-size:11px;color:#9ca3af;">
                Este es un mensaje automático. No responda a este correo.
              </td>
            </tr>

          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""

    html_rechazo_gg = """\
<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f3f4f6;font-family:Segoe UI,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:24px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="720" cellpadding="0" cellspacing="0"
                 style="max-width:720px;background:#ffffff;border-radius:10px;border:1px solid #e5e7eb;overflow:hidden;">

            <tr>
              <td style="background:#1d4ed8;padding:18px 22px;color:#ffffff;">
                <div style="font-size:12px;text-transform:uppercase;letter-spacing:.08em;opacity:.92;">
                  GASTOS CON TARJETA
                </div>
                <div style="font-size:22px;font-weight:800;margin-top:4px;line-height:1.15;">
                  Gasto rechazado — #{{ gasto_id }}
                </div>
                <div style="font-size:13px;opacity:.92;margin-top:8px;line-height:1.35;">
                  Hola {{ usuario|default('') }}, este gasto fue <b>RECHAZADO</b> por Gerencia General.
                  Por favor acérquese a Gerencia General para revisión.
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:18px 22px 10px 22px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                       style="border-collapse:separate;border-spacing:0;overflow:hidden;border-radius:10px;">

                  <tr>
                    <td style="width:280px;background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">ID</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">#{{ gasto_id }}</td>
                  </tr>

                  <tr>
                    <td style="width:280px;background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Fecha</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">{{ fecha }}</td>
                  </tr>

                  <tr>
                    <td style="width:280px;background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Proveedor</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">{{ proveedor|default('') }}</td>
                  </tr>

                  <tr>
                    <td style="width:280px;background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Motivo</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">{{ motivo|default('') }}</td>
                  </tr>

                  <tr>
                    <td style="width:280px;background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Total con IVA</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">${{ total_con_iva_fmt|default('0,00') }}</td>
                  </tr>

                  <tr>
                    <td style="width:280px;background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Estado</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#b91c1c;font-weight:800;">
                      RECHAZADO (GG)
                    </td>
                  </tr>
                  {% if comentario %}
                    <tr>
                      <td style="width:280px;background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">
                        Motivo del rechazo
                      </td>
                      <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;white-space:pre-wrap;">
                        {{ comentario }}
                      </td>
                    </tr>
                    {% endif %}

                </table>

                <div style="margin-top:18px;">
                  <a href="{{ gasto_url }}"
                     style="display:inline-block;background:#2563eb;color:#ffffff;text-decoration:none;
                            padding:11px 18px;border-radius:8px;font-weight:700;font-size:13px;">
                    Ver gasto
                  </a>
                </div>

                <div style="font-size:12px;color:#6b7280;margin-top:12px;">
                  Este correo fue generado automáticamente por el sistema de Sili.
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:12px 22px 14px 22px;border-top:1px solid #e5e7eb;font-size:11px;color:#9ca3af;">
                Este es un mensaje automático. No responda a este correo.
              </td>
            </tr>

          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""

    upsert(
        TPL_GASTO_USER_APPROVED, "gasto",
        "✅ Tu gasto #{{ gasto_id }} fue aprobado ({{ area|upper }})",
        html_user_approved,
        "Tu gasto #{{ gasto_id }} fue aprobado ({{ area|upper }})."
    )
    upsert(TPL_GASTO_NEXT_GG, "gasto", "🟠 Aprobación pendiente GG: gasto #{{ gasto_id }}", html_next_step, "Aprobación pendiente GG: gasto #{{ gasto_id }}")
    upsert(TPL_GASTO_NEXT_GF, "gasto", "🟠 Aprobación pendiente GF: gasto #{{ gasto_id }}", html_next_step, "Aprobación pendiente GF: gasto #{{ gasto_id }}")
    upsert(TPL_GASTO_NEXT_COORD, "gasto", "🟠 Envío/Control: gasto #{{ gasto_id }}", html_next_step, "Control/Envío: gasto #{{ gasto_id }}")
    upsert(TPL_GASTO_NEXT, "gasto", "🟠 Gasto pendiente: #{{ gasto_id }}", html_next_step, "Gasto pendiente: #{{ gasto_id }}")

    upsert(
        TPL_GASTO_RECHAZO_GG, "gasto",
        "🚫 Gasto rechazado (GG): #{{ gasto_id }}",
        html_rechazo_gg,
        "Tu gasto #{{ gasto_id }} fue RECHAZADO por Gerencia General. Acércate a GG para revisión."
    )

    conn.commit()


def ensure_om_templates(conn):
    ensure_notify_schema(conn)
    cur = conn.cursor()

    def upsert(key, tipo, subject, html, text):
        cur.execute("""
            UPDATE notify_templates
              SET tipo = ?,
                  subject = ?,
                  html = ?,
                  text = ?
            WHERE [key] = ?
        """, (tipo, subject, html, text, key))

        if cur.rowcount == 0:
            cur.execute("""
                INSERT INTO notify_templates ([key], tipo, subject, html, text)
                VALUES (?, ?, ?, ?, ?)
            """, (key, tipo, subject, html, text))

    html_base = """\
<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f3f4f6;font-family:Segoe UI,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:24px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="760" cellpadding="0" cellspacing="0"
                 style="max-width:760px;background:#ffffff;border-radius:10px;border:1px solid #e5e7eb;overflow:hidden;">

            <tr>
              <td style="background:{{ header_color }};padding:18px 22px;color:#ffffff;">
                <div style="font-size:12px;text-transform:uppercase;letter-spacing:.08em;opacity:.92;font-weight:700;">
                  OPORTUNIDAD DE MEJORA
                </div>
                <div style="font-size:22px;font-weight:800;margin-top:4px;line-height:1.15;">
                  {{ header_title }}
                </div>
                <div style="font-size:13px;opacity:.95;margin-top:8px;line-height:1.35;">
                  {{ header_subtitle }}
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:18px 22px 10px 22px;">
                <div style="font-size:14px;color:#111827;line-height:1.6;margin-bottom:14px;">
                  Hola {{ destinatario_nombre or sponsor_nombre or jefe_nombre or gg_nombre or sc_nombre or 'Usuario' }},
                </div>

                <div style="font-size:14px;color:#111827;line-height:1.6;margin-bottom:14px;">
                  {{ intro_text }}
                </div>

                <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                       style="border-collapse:separate;border-spacing:0;overflow:hidden;border-radius:10px;">
                  <tr>
                    <td style="width:260px;background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Código</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">{{ codigo }}</td>
                  </tr>
                  <tr>
                    <td style="background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Cliente</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">{{ cliente }}</td>
                  </tr>
                  <tr>
                    <td style="background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Proceso</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">{{ proceso }}</td>
                  </tr>
                  <tr>
                    <td style="background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Sponsor</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">{{ sponsor_nombre or 'No definido' }}</td>
                  </tr>
                  <tr>
                    <td style="background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Gerente del sponsor</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">{{ jefe_nombre or 'No definido' }}</td>
                  </tr>
                  <tr>
                    <td style="background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Servicio al Cliente</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">{{ sc_nombre or 'No definido' }}</td>
                  </tr>
                  <tr>
                    <td style="background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Observación</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;white-space:pre-wrap;">{{ observacion }}</td>
                  </tr>
                  <tr>
                    <td style="background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Día de notificación</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">{{ dia_label }}</td>
                  </tr>
                  <tr>
                    <td style="background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Días transcurridos</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">{{ dias }}</td>
                  </tr>
                </table>

                <div style="margin-top:18px;">
                  <a href="{{ app_url }}"
                     style="display:inline-block;background:#2563eb;color:#ffffff;text-decoration:none;
                            padding:11px 18px;border-radius:8px;font-weight:700;font-size:13px;">
                    Revisar OM
                  </a>
                </div>

                <div style="font-size:12px;color:#6b7280;margin-top:12px;">
                  Este correo fue generado automáticamente por el sistema de Sili.
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:12px 22px 14px 22px;border-top:1px solid #e5e7eb;font-size:11px;color:#9ca3af;">
                Este es un mensaje automático. No responda a este correo.
              </td>
            </tr>

          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""

    upsert(TPL_OM_SPONSOR_D4, "om", "🟢 OM {{ codigo }} - Alerta día 4", html_base, "OM {{ codigo }} - alerta día 4. Cliente: {{ cliente }}. Proceso: {{ proceso }}.")
    upsert(TPL_OM_JEFE_D5, "om", "🟡 OM {{ codigo }} - Seguimiento día 5", html_base, "OM {{ codigo }} - seguimiento día 5. Sponsor: {{ sponsor_nombre }}.")
    upsert(TPL_OM_SPONSOR_JEFE_D9, "om", "🟠 OM {{ codigo }} - Seguimiento día 9", html_base, "OM {{ codigo }} - seguimiento día 9. Sponsor: {{ sponsor_nombre }}.")
    upsert(TPL_OM_GG_D10, "om", "🔴 OM {{ codigo }} - Escalamiento día 10", html_base, "OM {{ codigo }} - escalamiento día 10. Sponsor: {{ sponsor_nombre }}.")

    conn.commit()


def _send_email(to_email: str, subj: str, html: str, text: Optional[str] = None):
    from .scheduler_repository import get_db_standalone

    c = get_db_standalone()
    try:
        send_mail_planilla(c, to_email, subj, html, text=text, attachments=None)
    finally:
        try:
            c.close()
        except Exception:
            pass


def _send_inapp(title: str, body: str, user_id: int):
    from .scheduler_repository import get_db_standalone

    conn = get_db_standalone()
    try:
        _exec_retry(conn.cursor(), """
          INSERT INTO notify_inapp(user_id, title, body, created_at, is_read)
          VALUES (?,?,?,?,0)
        """, (user_id, title, body, datetime.utcnow().isoformat(timespec="seconds")))
        conn.commit()
    finally:
        conn.close()


def _send_slack(webhook: str, text: str):
    _log("info", "[SLACK] %s -> %s", webhook, text)


def enqueue_gasto_approved(conn, gasto_id: int, area: str, approved_by_user_id: int | None):
    import json
    from datetime import date, datetime, timedelta

    cur = conn.cursor()

    # En SQL Server ya existen tablas y templates
    # ensure_notify_schema(conn)
    # ensure_gasto_templates(conn)

    _log("info", "[ENQUEUE_GASTO] start gasto_id=%s area=%s approved_by=%s", gasto_id, area, approved_by_user_id)

    cur.execute("""
        SELECT id, usuario_id
        FROM gastos_tarjeta
        WHERE id = ?
    """, (int(gasto_id),))
    row = cur.fetchone()

    if not row:
        _log("warning", "[ENQUEUE_GASTO] gasto no existe: %s", gasto_id)
        return

    try:
        creator_id = int(row["usuario_id"])
    except Exception:
        creator_id = int(row[1])

    cur.execute("SELECT TOP 1 1 FROM usuarios WHERE id = ?", (creator_id,))
    uok = cur.fetchone()
    if not uok:
        _log("warning", "[ENQUEUE_GASTO] creator_id no existe en usuarios: %s", creator_id)
        return

    area_key = (area or "").lower().strip()
    if area_key == "ga":
        next_roles = ("gerente general",)
        template_next = TPL_GASTO_NEXT_GG
    elif area_key == "gg":
        next_roles = ("gerente financiero",)
        template_next = TPL_GASTO_NEXT_GF
    elif area_key == "gf":
        next_roles = ("coordinador", "admin")
        template_next = TPL_GASTO_NEXT_COORD
    else:
        next_roles = ()
        template_next = TPL_GASTO_NEXT

    next_users = []
    if next_roles:
        placeholders = ",".join(["?"] * len(next_roles))
        cur.execute(
            f"""
            SELECT id
            FROM usuarios
            WHERE LOWER(rol) IN ({placeholders})
              AND COALESCE(disabled,0)=0
            """,
            tuple(r.lower() for r in next_roles)
        )
        next_users = cur.fetchall()

    payload_json = json.dumps({
        "gasto_id": int(gasto_id),
        "area": area_key,
        "approved_by_user_id": approved_by_user_id,
    }, ensure_ascii=False)

    # reemplazo de _next_5min_sqlite()
    scheduled_at = datetime.now() + timedelta(minutes=5)
    fecha_obj = date.today()
    canal = CANAL_EMAIL
    estado = "PENDIENTE"

    # 1) Notificación al creador del gasto
    event_key_user = f"{int(gasto_id)}:{area_key}:user"

    _exec_retry(cur, """
        IF NOT EXISTS (
            SELECT 1
            FROM notify_queue
            WHERE event_key = ?
        )
        BEGIN
            INSERT INTO notify_queue (
                user_id,
                tipo,
                fecha_obj,
                canal,
                template_key,
                payload_json,
                estado,
                scheduled_at,
                gasto_id,
                area,
                event_key
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        END
    """, (
        event_key_user,
        creator_id,
        TIPO_GASTO_APROBADO_USER,
        fecha_obj,
        canal,
        TPL_GASTO_USER_APPROVED,
        payload_json,
        estado,
        scheduled_at,
        int(gasto_id),
        area_key,
        event_key_user,
    ))

    # 2) Notificación al siguiente aprobador / grupo siguiente
    for u in next_users:
        try:
            uid = int(u["id"])
        except Exception:
            uid = int(u[0])

        event_key_next = f"{int(gasto_id)}:{area_key}:next:{uid}"

        _exec_retry(cur, """
            IF NOT EXISTS (
                SELECT 1
                FROM notify_queue
                WHERE event_key = ?
            )
            BEGIN
                INSERT INTO notify_queue (
                    user_id,
                    tipo,
                    fecha_obj,
                    canal,
                    template_key,
                    payload_json,
                    estado,
                    scheduled_at,
                    gasto_id,
                    area,
                    event_key
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
            END
        """, (
            event_key_next,
            uid,
            TIPO_GASTO_APROBADO_NEXT,
            fecha_obj,
            canal,
            template_next,
            payload_json,
            estado,
            scheduled_at,
            int(gasto_id),
            area_key,
            event_key_next,
        ))

    conn.commit()
    _log("info", "[ENQUEUE_GASTO] done gasto_id=%s area=%s next_users=%s", gasto_id, area_key, len(next_users))


 
def enqueue_gasto_rejected_gg(conn, gasto_id: int, by_user_id: int, comentario: str = ""):
    import json
    from datetime import datetime, date
    from flask import current_app

    current_app.logger.warning(" enqueue_gasto_rejected_gg DB PATH=%s", current_app.config.get("DATABASE"))
    _log("info", "[ENQUEUE_RECHAZO_GG] start gasto_id=%s by_user=%s", gasto_id, by_user_id)

    cur = conn.cursor()

    # En SQL Server ya existe el esquema / templates
    # ensure_notify_schema(conn)
    # ensure_gasto_templates(conn)

    cur.execute("""
        SELECT
            g.id,
            g.usuario_id,
            COALESCE(g.proveedor, '') AS proveedor,
            COALESCE(g.motivo, '') AS motivo,
            COALESCE(CAST(g.fecha AS NVARCHAR(30)), '') AS fecha
        FROM gastos_tarjeta g
        WHERE g.id = ?
    """, (gasto_id,))
    row = cur.fetchone()

    if not row:
        raise RuntimeError(f"No existe el gasto {gasto_id}")

    try:
        gasto_usuario_id = row["usuario_id"]
        proveedor = row["proveedor"] or ""
        motivo = row["motivo"] or ""
        fecha = row["fecha"] or ""
    except Exception:
        gasto_usuario_id = row[1]
        proveedor = row[2] or ""
        motivo = row[3] or ""
        fecha = row[4] or ""

    gerente_id = _get_ultimo_jefe_id(conn, gasto_usuario_id, fallback_to_self=False)
    if not gerente_id:
        raise RuntimeError("No se encontró gerente para el gasto")

    gerente = _get_user_contact(conn, gerente_id)
    if not gerente:
        raise RuntimeError("No se encontró contacto del gerente")

    gerente_email = (gerente.get("email") or "").strip()
    if not gerente_email:
        raise RuntimeError("El gerente no tiene email configurado")

    by_username = _get_username(conn, by_user_id)

    payload_obj = {
        "gasto_id": int(gasto_id),
        "comentario": comentario or "",
        "proveedor": proveedor,
        "motivo": motivo,
        "fecha": fecha,
        "by_user_id": by_user_id,
        "by_username": by_username,
        "gerente_id": gerente.get("id"),
        "gerente_nombre": gerente.get("nombre"),
        "gerente_email": gerente_email,
    }

    payload_json = json.dumps(payload_obj, ensure_ascii=False)

    event_key = f"gasto_rejected_gg:{int(gasto_id)}:{int(by_user_id)}"
    tipo = "gasto_rejected_gg"
    user_id = int(gerente_id)
    tarea_id = int(gasto_id)
    area = "gg"
    canal = "email"
    template_key = "gasto_rejected_gg"
    estado = "PENDIENTE"
    fecha_obj = date.today()
    scheduled_at = datetime.now()

    current_app.logger.info("[Va a insertar rechazo GG]")

    _exec_retry(cur, """
    IF NOT EXISTS (
        SELECT 1
        FROM notify_queue
        WHERE user_id = ?
          AND tarea_id = ?
          AND tipo = ?
          AND fecha_obj = ?
          AND canal = ?
    )
    BEGIN
        INSERT INTO notify_queue (
            user_id,
            tarea_id,
            tipo,
            fecha_obj,
            canal,
            template_key,
            payload_json,
            estado,
            scheduled_at,
            gasto_id,
            area,
            event_key,
            comentario
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
    END
    """, (
        user_id,
        tarea_id,
        tipo,
        fecha_obj,
        canal,

        user_id,
        tarea_id,
        tipo,
        fecha_obj,
        canal,
        template_key,
        payload_json,
        estado,
        scheduled_at,
        int(gasto_id),
        area,
        event_key,
        comentario,
    ))

    conn.commit()
    return True


def _enqueue_om_notification(
    conn,
    *,
    user_id: int,
    tipo: str,
    template_key: str,
    fecha_obj: str,
    payload: dict,
    event_key: str,
):
    cur = conn.cursor()
    payload_json = json.dumps(payload or {}, ensure_ascii=False)

    # Evita duplicado por event_key o por índice único existente
    cur.execute("""
        SELECT TOP 1 id
        FROM notify_queue
        WHERE event_key = ?
           OR (
                user_id = ?
            AND tarea_id IS NULL
            AND tipo = ?
            AND fecha_obj = ?
            AND canal = ?
           )
    """, (
        event_key,
        int(user_id),
        tipo,
        fecha_obj,
        CANAL_EMAIL,
    ))

    if cur.fetchone():
        return False

    try:
        cur.execute("""
            INSERT INTO notify_queue (
                user_id,
                tarea_id,
                tipo,
                fecha_obj,
                canal,
                template_key,
                payload_json,
                scheduled_at,
                estado,
                event_key
            )
            VALUES (?, NULL, ?, ?, ?, ?, ?, DATEADD(minute, 5, GETDATE()), 'pending', ?)
        """, (
            int(user_id),
            tipo,
            fecha_obj,
            CANAL_EMAIL,
            template_key,
            payload_json,
            event_key,
        ))

        conn.commit()
        return True

    except Exception as e:
        conn.rollback()

        # Si otro ciclo ya insertó la misma notificación, no lo tratamos como error fatal
        if "clave duplicada" in str(e).lower() or "duplicate" in str(e).lower():
            return False

        raise





