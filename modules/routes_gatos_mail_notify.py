# modules/mail_notify.py
from __future__ import annotations

import os
import re
import time
import json
import html
import xml.etree.ElementTree as ET
from datetime import datetime
from email.message import EmailMessage
import smtplib, ssl

from typing import Iterable, Optional, Dict, Any, List
from flask import (
    request, render_template, redirect, url_for, flash,
    current_app, session, jsonify
)
from jinja2 import TemplateNotFound
from werkzeug.utils import secure_filename

try:
    import pyodbc  # opcional, solo para compatibilidad SQL Server
except Exception:
    pyodbc = None

from .db import get_db
from .security import require_login, require_permission, has_permission
from .config import TABLE_GASTOS as CFG_TABLE_GASTOS

from . import gastos_helpers as gh
from . import gastos_exports as gx

TABLE_GASTOS = CFG_TABLE_GASTOS or "gastos_tarjeta"


# =============== Utilidades de DB ===============

def _rowdict(row) -> Optional[Dict[str, Any]]:
    return dict(row) if row is not None else None


def _row_to_dict(x):
    if x is None:
        return None
    try:
        return dict(x)
    except Exception:
        return x


def _get_conf(prefix="smtp_") -> Dict[str, str]:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT clave, valor FROM configuracion WHERE LOWER(clave) LIKE ?",
        (f"{prefix}%",)
    )
    data = {
        (r["clave"] or "").strip().lower(): (r["valor"] or "").strip()
        for r in cur.fetchall()
    }
    conn.close()
    return data


def _fmt_fecha_ddmmyyyy(fecha_str: str | None) -> str:
    if not fecha_str:
        return ""
    try:
        return datetime.strptime(fecha_str, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return str(fecha_str)


def _money(x):
    try:
        return f"{float(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "0,00"


def _h(x) -> str:
    return html.escape("" if x is None else str(x), quote=True)


def _row_blue(lbl, val):
    val = (val or "")
    if isinstance(val, (int, float)):
        val = str(val)
    val = val.replace("\n", "<br>")
    return (
        "<tr>"
        f"<td style='width:210px;background:#eef2ff;font-weight:600;"
        "padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;'>"
        f"{lbl}</td>"
        f"<td style='padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;'>"
        f"{val}</td>"
        "</tr>"
    )


def _row(label: str, value: str, icon: str = "•") -> str:
    return f"""
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin:0 0 8px 0;">
  <tr>
    <td style="width:24px;font-size:16px">{icon}</td>
    <td style="width:160px;color:#6b7280">{label}</td>
    <td style="font-weight:600;color:#111827">{value}</td>
  </tr>
</table>
""".strip()


def _row_kv(label: str, value: str) -> str:
    return f"""
      <tr>
        <td style="width:52%;background:#eef2ff;border:1px solid #e5e7eb;
                   padding:10px 12px;font-size:13px;font-weight:600;color:#111827;">
          {_h(label)}
        </td>
        <td style="border:1px solid #e5e7eb;padding:10px 12px;font-size:13px;color:#111827;">
          {_h(value)}
        </td>
      </tr>
    """.strip()


def _safe_lower(x: Any) -> str:
    try:
        return str(x or "").strip().lower()
    except Exception:
        return ""


def _unique_emails(emails: Iterable[str]) -> List[str]:
    out = []
    seen = set()
    for e in emails or []:
        e2 = (e or "").strip()
        if not e2:
            continue
        k = e2.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(e2)
    return out


def _safe_email(u: dict) -> str:
    return (u.get("email") or "").strip()


def _safe_name(u: dict) -> str:
    for k in ("nombre_completo", "nombre", "full_name", "name", "username", "email"):
        v = (u or {}).get(k)
        if v:
            return str(v).strip()
    return "N/D"


# =============== Links ===============

def _link_ver_gasto(gasto_id: int) -> str:
    try:
        return url_for("ver_gasto", gid=gasto_id, _external=True)
    except Exception:
        return "http://bitacoraquimpac.com.ec:5000/"


def _link_bandeja_aprobar() -> str:
    try:
        return url_for("lista_gastos", _external=True) + "?pendientes=1"
    except Exception:
        return "http://bitacoraquimpac.com.ec:5000/"


def _gasto_public_url(app, gasto_id: int) -> str:
    base = (app.config.get("PUBLIC_BASE_URL") or "").rstrip("/")
    if not base:
        return f"/reembolsos/gastos/{gasto_id}"
    return f"{base}/reembolsos/gastos/{gasto_id}"


def _abs_url(app, path: str) -> str:
    base = (app.config.get("PUBLIC_BASE_URL") or "").rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    return f"{base}{path}" if base else path


# =============== Plantillas HTML correo ===============

def _build_gastos_mail_html(
    titulo: str,
    saludo_linea: str,
    rows_html: str,
    cta_text: str,
    cta_link: str
) -> str:
    return f"""\
<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f3f4f6;
               font-family:Segoe UI,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="background:#f3f4f6;padding:24px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="720" cellpadding="0" cellspacing="0"
                 style="max-width:720px;background:#ffffff;border-radius:8px;
                        border:1px solid #e5e7eb;overflow:hidden;">

            <tr>
              <td style="background:#1d4ed8;padding:16px 20px;color:#ffffff;">
                <div style="font-size:12px;text-transform:uppercase;
                            letter-spacing:.08em;opacity:.9;">
                  Gastos con tarjeta
                </div>
                <div style="font-size:18px;font-weight:700;margin-top:4px;">
                  {titulo}
                </div>
                <div style="font-size:12px;opacity:.9;margin-top:6px;">
                  {saludo_linea}
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:18px 20px 10px 20px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                       style="border-collapse:collapse;">
                  {rows_html}
                </table>

                <div style="margin-top:18px;margin-bottom:6px;text-align:left;">
                  <a href="{cta_link}"
                     style="display:inline-block;background:#2563eb;color:#ffffff;
                            text-decoration:none;padding:10px 18px;border-radius:6px;
                            font-weight:600;font-size:13px;">
                    {cta_text}
                  </a>
                </div>

                <div style="font-size:11px;color:#6b7280;margin-top:8px;">
                  Este mensaje fue generado automáticamente por el sistema.
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:10px 20px 14px 20px;border-top:1px solid #e5e7eb;
                         font-size:11px;color:#9ca3af;">
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


def _build_gastos_html_blue(titulo, saludo, rows_html, cta_text, cta_link):
    return f"""\
<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f3f4f6;font-family:Segoe UI,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="background:#f3f4f6;padding:24px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="720" cellpadding="0" cellspacing="0"
                 style="max-width:720px;background:#ffffff;border-radius:8px;
                        border:1px solid #e5e7eb;overflow:hidden;">
            <tr>
              <td style="background:#1d4ed8;padding:16px 20px;color:#ffffff;">
                <div style="font-size:12px;text-transform:uppercase;
                            letter-spacing:.08em;opacity:.9;">
                  Gastos con tarjeta
                </div>
                <div style="font-size:18px;font-weight:700;margin-top:4px;">
                  {titulo}
                </div>
                <div style="font-size:12px;opacity:.9;margin-top:6px;">
                  {saludo}
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:18px 20px 10px 20px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                       style="border-collapse:collapse;">
                  {rows_html}
                </table>

                <div style="margin-top:18px;margin-bottom:6px;text-align:left;">
                  <a href="{cta_link}"
                     style="display:inline-block;background:#2563eb;color:#ffffff;
                            text-decoration:none;padding:10px 18px;border-radius:6px;
                            font-weight:600;font-size:13px;">
                    {cta_text}
                  </a>
                </div>

                <div style="font-size:11px;color:#6b7280;margin-top:8px;">
                  Este correo fue generado automáticamente por el sistema de Reembolso de Gastos.
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:10px 20px 14px 20px;border-top:1px solid #e5e7eb;
                         font-size:11px;color:#9ca3af;">
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


def _build_gastos_html_orange(titulo, saludo, rows_html, cta_text, cta_link):
    return f"""\
<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f3f4f6;font-family:Segoe UI,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="background:#f3f4f6;padding:24px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="720" cellpadding="0" cellspacing="0"
                 style="max-width:720px;background:#ffffff;border-radius:8px;
                        border:1px solid #e5e7eb;overflow:hidden;">
            <tr>
              <td style="background:#f59e0b;padding:16px 20px;color:#ffffff;">
                <div style="font-size:12px;text-transform:uppercase;
                            letter-spacing:.08em;opacity:.95;">
                  Gastos con tarjeta
                </div>
                <div style="font-size:18px;font-weight:700;margin-top:4px;">
                  {titulo}
                </div>
                <div style="font-size:12px;opacity:.95;margin-top:6px;">
                  {saludo}
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:18px 20px 10px 20px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                       style="border-collapse:collapse;">
                  {rows_html}
                </table>

                <div style="margin-top:18px;margin-bottom:6px;text-align:left;">
                  <a href="{cta_link}"
                     style="display:inline-block;background:#f59e0b;color:#111827;
                            text-decoration:none;padding:10px 18px;border-radius:6px;
                            font-weight:700;font-size:13px;">
                    {cta_text}
                  </a>
                </div>

                <div style="font-size:11px;color:#6b7280;margin-top:8px;">
                  Este correo fue generado automáticamente por el sistema de Reembolso de Gasto.
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:10px 20px 14px 20px;border-top:1px solid #e5e7eb;
                         font-size:11px;color:#9ca3af;">
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


def _build_gastos_html_red(titulo, saludo, rows_html, cta_text, cta_link):
    return f"""\
<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f3f4f6;font-family:Segoe UI,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="background:#f3f4f6;padding:24px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="720" cellpadding="0" cellspacing="0"
                 style="max-width:720px;background:#ffffff;border-radius:8px;
                        border:1px solid #e5e7eb;overflow:hidden;">
            <tr>
              <td style="background:#dc2626;padding:16px 20px;color:#ffffff;">
                <div style="font-size:12px;text-transform:uppercase;
                            letter-spacing:.08em;opacity:.95;">
                  Gastos con tarjeta
                </div>
                <div style="font-size:18px;font-weight:700;margin-top:4px;">
                  {titulo}
                </div>
                <div style="font-size:12px;opacity:.95;margin-top:6px;">
                  {saludo}
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:18px 20px 10px 20px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                       style="border-collapse:collapse;">
                  {rows_html}
                </table>

                <div style="margin-top:18px;margin-bottom:6px;text-align:left;">
                  <a href="{cta_link}"
                     style="display:inline-block;background:#dc2626;color:#ffffff;
                            text-decoration:none;padding:10px 18px;border-radius:6px;
                            font-weight:600;font-size:13px;">
                    {cta_text}
                  </a>
                </div>

                <div style="font-size:11px;color:#6b7280;margin-top:8px;">
                  Este correo fue generado automáticamente por el sistema de Reembolso de Gastos.
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:10px 20px 14px 20px;border-top:1px solid #e5e7eb;
                         font-size:11px;color:#9ca3af;">
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


def _shell(title: str, body_html: str) -> str:
    return f"""
<!doctype html>
<html>
  <body style="margin:0;background:#f6f9fc;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f6f9fc;padding:20px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="640" cellspacing="0" cellpadding="0" style="background:#ffffff;border:1px solid #e5e7eb;border-radius:12px;font-family:'Segoe UI',Arial,sans-serif;color:#111827;">
            <tr>
              <td style="padding:18px 20px;border-bottom:1px solid #e5e7eb;
                         background:linear-gradient(135deg,#1E3A8A 0%,#2563EB 50%,#22D3EE 100%);
                         color:#fff;border-top-left-radius:12px;border-top-right-radius:12px;">
                <span style="font-size:22px;line-height:1.2;display:inline-block;">💳  {title}</span>
              </td>
            </tr>
            <tr>
              <td style="padding:20px;">
                {body_html}
                <div style="margin-top:18px;padding-top:12px;border-top:1px dashed #e5e7eb;font-size:12px;color:#6b7280">
                  Este mensaje fue enviado automáticamente por el Sistemas de Reembolso de Gastos.
                </div>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
""".strip()


def _area_badge(area: str) -> str:
    area = (area or "").lower()
    txt = {"ga": "Gerencia de Área", "gg": "Gerencia General", "gf": "Gerencia Financiera"}.get(area, area.upper())
    emoji = {"ga": "🏢", "gg": "🏛️", "gf": "💼"}.get(area, "✅")
    return f'<span style="display:inline-block;background:#eef2ff;border:1px solid #c7d2fe;padding:4px 8px;border-radius:999px;font-weight:600">{emoji} {txt}</span>'


def _render_gasto_mail(app, title: str, intro: str, rows_html: str, gasto_id: int | None):
    url_ver = _abs_url(app, f"/reembolsos/gastos/{gasto_id}/ver") if gasto_id else "#"
    now_txt = datetime.now().strftime("%Y-%m-%d %H:%M")

    return f"""
    <div style="font-family:Arial,Helvetica,sans-serif;background:#f3f4f6;padding:24px;">
      <div style="max-width:720px;margin:0 auto;background:#ffffff;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;">
        <div style="padding:18px 20px;background:#111827;color:#ffffff;">
          <div style="font-size:16px;font-weight:700;line-height:1.2;">{_h(title)}</div>
          <div style="font-size:12px;opacity:.85;margin-top:6px;">{_h(now_txt)}</div>
        </div>

        <div style="padding:18px 20px;color:#111827;">
          <div style="font-size:14px;line-height:1.45;margin-bottom:12px;">
            {_h(intro)}
          </div>

          <table role="presentation" cellspacing="0" cellpadding="0" style="width:100%;border-collapse:collapse;border:1px solid #e5e7eb;border-radius:10px;overflow:hidden;">
            <tbody>
              {rows_html}
            </tbody>
          </table>

          <div style="margin-top:14px;">
            <a href="{_h(url_ver)}"
               style="display:inline-block;background:#2563eb;color:#fff;text-decoration:none;
                      padding:10px 14px;border-radius:10px;font-size:13px;font-weight:700;">
              Ver gasto
            </a>
          </div>

          <div style="margin-top:14px;font-size:12px;color:#6b7280;">
            Este es un mensaje automático del sistema.
          </div>
        </div>
      </div>
    </div>
    """.strip()


# =============== Envío ===============

def _smtp_conf(app):
    cfg = _get_conf("smtp_")
    host = cfg.get("smtp_host") or app.config.get("MAIL_HOST")
    port = int(cfg.get("smtp_port") or app.config.get("MAIL_PORT") or 587)
    user = cfg.get("smtp_user") or app.config.get("MAIL_USERNAME")
    pwd = cfg.get("smtp_pass") or app.config.get("MAIL_PASSWORD")
    sender = cfg.get("smtp_from") or app.config.get("MAIL_FROM") or user

    use_ssl = (cfg.get("smtp_use_ssl") or "").strip() in ("1", "true", "yes", "on") or port == 465
    use_tls = (cfg.get("smtp_use_tls") or "").strip() in ("1", "true", "yes", "on") or (port == 587 and not use_ssl)
    return host, port, user, pwd, use_tls, use_ssl, sender


def _send_email(app, subject: str, text_body: str,
                to: Iterable[str] | None,
                cc: Iterable[str] | None = None,
                html_body: str | None = None) -> bool:
    to = [x for x in (to or []) if x]
    cc = [x for x in (cc or []) if x]
    if not to:
        app.logger.info("Notificación omitida: sin destinatarios.")
        return False

    host, port, user, pwd, use_tls, use_ssl, sender = _smtp_conf(app)
    if not host or not sender:
        app.logger.warning("SMTP incompleto (host/from). No se envía correo.")
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)

    msg.set_content(text_body or subject)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    try:
        if use_ssl:
            server = smtplib.SMTP_SSL(host, port, timeout=25)
        else:
            server = smtplib.SMTP(host, port, timeout=25)
            if use_tls:
                server.starttls(context=ssl.create_default_context())
        if user and pwd:
            server.login(user, pwd)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        app.logger.exception(f"Fallo al enviar correo: {e}")
        return False


def _send_mail_safe(to_email: str, subject: str, text_body: str, html_body: str | None = None):
    try:
        to_email = (to_email or "").strip()
        if not to_email:
            return False

        app = current_app._get_current_object()
        return _send_email(app, subject, text_body, [to_email], html_body=html_body)
    except Exception:
        try:
            current_app.logger.exception("[GASTOS][MAIL] Error enviando correo seguro")
        except Exception:
            pass
        return False


# =============== Consultas auxiliares SQL Server ===============

def _gasto_meta(gasto_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT TOP 1
            g.id,
            g.fecha,
            g.motivo,
            g.total_con_iva,
            g.usuario_id,
            u.username AS usuario_username,
            u.email AS usuario_email,
            u.departamento_id AS departamento_id,
            COALESCE(g.es_caja_chica, 0) AS es_caja_chica,
            COALESCE(g.reembolso_vendedor, 0) AS reembolso_vendedor
        FROM gastos_tarjeta g
        LEFT JOIN usuarios u ON u.id = g.usuario_id
        WHERE g.id = ?
        ORDER BY g.id
    """, (gasto_id,))
    row = cur.fetchone()
    return dict(row) if row else None


def obtener_gerente_real(conn, user_id):
    """
    Sube por la cadena jerárquica usando jefe_id.
    En cada nivel busca si existe un usuario con rol 'gerente'
    en el departamento del jefe actual.
    Si lo encuentra -> retorna el gerente.
    Si no existe gerente en ningún nivel -> retorna el último jefe.
    Si no hay jefes -> retorna None.
    """
    gerente_roles = ('gerente', 'gerente de área', 'gerente area')
    MAX_NIVELES = 10

    print("\n=== INICIO BÚSQUEDA DE GERENTE PARA USER:", user_id, "===")

    usuario = conn.execute("""
        SELECT id, rol, departamento_id, jefe_id
        FROM usuarios
        WHERE id = ?
    """, (user_id,)).fetchone()

    if not usuario:
        print("Usuario no existe en BD.")
        return None

    jefe_id = usuario["jefe_id"]
    ultimo_jefe = None
    nivel = 1

    while jefe_id and nivel <= MAX_NIVELES:
        print(f"\n-- NIVEL {nivel}: jefe_id = {jefe_id}")

        jefe = conn.execute("""
            SELECT id, rol, departamento_id, jefe_id
            FROM usuarios
            WHERE id = ?
        """, (jefe_id,)).fetchone()

        if not jefe:
            print("No existe registro del jefe:", jefe_id)
            break

        print("  Jefe encontrado:", dict(jefe))

        ultimo_jefe = jefe
        depto_jefe = jefe["departamento_id"]
        print("  Departamento del jefe:", depto_jefe)

        placeholders = ",".join("?" for _ in gerente_roles)

        gerente = conn.execute(f"""
            SELECT TOP 1 id, rol, departamento_id, jefe_id
            FROM usuarios
            WHERE departamento_id = ?
              AND LOWER(rol) IN ({placeholders})
            ORDER BY id
        """, (depto_jefe, *[r.lower() for r in gerente_roles])).fetchone()

        if gerente:
            print("✔ GERENTE ENCONTRADO EN ESTE NIVEL:", dict(gerente))
            return gerente

        jefe_id = jefe["jefe_id"]
        nivel += 1

    if ultimo_jefe:
        print("⚠ No se encontró gerente, se retorna el último jefe:", dict(ultimo_jefe))
        return ultimo_jefe

    print("⚠ No existe jefe ni gerente para este usuario.")
    return None


def _gerente_email_por_jerarquia(conn, user_id: int | None) -> str:
    if not user_id:
        return ""

    gerente = obtener_gerente_real(conn, user_id)
    if not gerente:
        return ""

    try:
        gerente_id = gerente["id"]
    except Exception:
        try:
            gerente_id = dict(gerente).get("id")
        except Exception:
            gerente_id = None

    if not gerente_id:
        return ""

    cur = conn.cursor()
    cur.execute("""
        SELECT TOP 1 email
        FROM usuarios
        WHERE id = ?
          AND COALESCE(disabled, 0) = 0
        ORDER BY id
    """, (gerente_id,))
    row = cur.fetchone()

    return (row["email"] or "").strip() if row and row["email"] else ""


def _user_meta(uid: int) -> Optional[Dict[str, Any]]:
    if uid is None:
        return None
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, username, email, rol, departamento_id FROM usuarios WHERE id = ?",
        (uid,)
    )
    row = cur.fetchone()
    conn.close()
    return _rowdict(row)


def _dep_manager_email(dep_id: int | None) -> Optional[str]:
    if dep_id is None:
        return None
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT TOP 1 email
        FROM usuarios
        WHERE departamento_id = ?
          AND LOWER(rol) IN ('gerente', 'gerente de área', 'gerente de area')
          AND COALESCE(disabled, 0) = 0
        ORDER BY id
    """, (dep_id,))
    row = cur.fetchone()
    conn.close()
    return row["email"] if row else None


def _fetch_role_emails(conn, role_names):
    roles = [_safe_lower(r) for r in (role_names or []) if _safe_lower(r)]
    if not roles:
        return []

    placeholders = ",".join("?" * len(roles))
    cur = conn.cursor()
    cur.execute(f"""
        SELECT DISTINCT email
        FROM usuarios
        WHERE email IS NOT NULL
          AND TRIM(email) <> ''
          AND LOWER(TRIM(rol)) IN ({placeholders})
          AND COALESCE(disabled, 0) = 0
        ORDER BY email
    """, roles)
    rows = cur.fetchall()

    emails = []
    for r in rows:
        try:
            emails.append((r["email"] or "").strip())
        except Exception:
            emails.append((r[0] or "").strip())

    return _unique_emails(emails)


# =============== Notificaciones creación ===============

def _send_creator_gasto_created(app, g: dict):
    creator_email = (g.get("usuario_email") or "").strip()
    if not creator_email:
        return False

    fecha_fmt = _fmt_fecha_ddmmyyyy(g.get("fecha"))
    usuario = g.get("usuario_username") or ""

    rows = (
        _row_blue("ID", f"#{g['id']}") +
        _row_blue("Fecha", fecha_fmt) +
        _row_blue("Total con IVA", f"${_money(g.get('total_con_iva'))}") +
        _row_blue("Creador", usuario)
    )

    titulo = f"Gasto registrado #{g['id']}"
    saludo = f"Hola {usuario}, tu gasto fue registrado correctamente."

    link = _link_ver_gasto(g["id"])
    html_body = _build_gastos_html_blue(titulo, saludo, rows, "Ver gasto", link)

    subject = f"[Gastos] ✅ Gasto registrado #{g['id']}"
    text = (
        f"Tu gasto #{g['id']} fue registrado.\n"
        f"Fecha: {fecha_fmt}\n"
        f"Total con IVA: {_money(g.get('total_con_iva'))}\n"
    )

    return _send_mail_safe(creator_email, subject, text, html_body=html_body)


def _send_manager_gasto_created(app, g: dict, gerente_email: str):
    gerente_email = (gerente_email or "").strip()
    if not gerente_email:
        return False

    fecha_fmt = _fmt_fecha_ddmmyyyy(g.get("fecha"))
    usuario = g.get("usuario_username") or ""

    rows = (
        _row_blue("ID", f"#{g['id']}") +
        _row_blue("Fecha", fecha_fmt) +
        _row_blue("Total con IVA", f"${_money(g.get('total_con_iva'))}") +
        _row_blue("Creador", usuario)
    )

    titulo = f"Aprobación requerida – Gasto #{g['id']}"
    saludo = f"El usuario {usuario} registró un gasto que requiere tu aprobación."

    link = _link_ver_gasto(g["id"])
    html_body = _build_gastos_html_blue(titulo, saludo, rows, "Revisar y aprobar gasto", link)

    subject = f"[Gastos] ⏳ Aprobación requerida – Gasto #{g['id']}"
    text = (
        f"El usuario {usuario} registró el gasto #{g['id']}.\n"
        f"Fecha: {fecha_fmt}\n"
        f"Proveedor: {g.get('proveedor')}\n"
        f"Factura: {g.get('numero_factura')}\n"
        f"Motivo: {g.get('motivo')}\n"
        f"Total con IVA: {_money(g.get('total_con_iva'))}\n"
        f"Ingresa a revisar y aprobar: {link}\n"
    )

    return _send_mail_safe(gerente_email, subject, text, html_body=html_body)


def notify_gasto_created(app, gasto_id: int, by_user_id: int | None):
    g = _gasto_meta(gasto_id)
    if not g:
        return False

    conn = get_db()
    gerente_email = _gerente_email_por_jerarquia(conn, g.get("usuario_id"))
    creator_email = (g.get("usuario_email") or "").strip()

    app.logger.info(
        "[GASTOS][MAIL] Creación gasto=%s creator=%r gerente=%r",
        gasto_id, creator_email, gerente_email
    )

    sent_any = False

    try:
        if creator_email:
            sent_any = _send_creator_gasto_created(app, g) or sent_any
    except Exception:
        app.logger.exception("[GASTOS][MAIL] Error correo creador")

    try:
        if gerente_email and gerente_email != creator_email:
            sent_any = _send_manager_gasto_created(app, g, gerente_email) or sent_any
    except Exception:
        app.logger.exception("[GASTOS][MAIL] Error correo gerente")

    if not sent_any:
        app.logger.info("[GASTOS][MAIL] Notificación omitida: sin destinatarios.")

    try:
        conn.close()
    except Exception:
        pass

    return sent_any


def notify_gasto_deleted(app, snapshot: Dict[str, Any], by_user_id: int | None):
    if not snapshot:
        return False

    subject = f"[Gastos] 🗑️ Gasto #{snapshot.get('id')} eliminado"
    text = (
        f"Se eliminó el gasto #{snapshot.get('id')}.\n"
        f"Fecha: {snapshot.get('fecha')}\n"
        f"Motivo: {snapshot.get('motivo')}\n"
        f"Total con IVA: {_money(snapshot.get('total_con_iva'))}\n"
    )
    html_body = _shell(
        "Gasto eliminado",
        _row("ID", f"#{snapshot.get('id')}", "🗑️") +
        _row("Fecha", str(snapshot.get('fecha') or ""), "📅") +
        _row("Motivo", str(snapshot.get('motivo') or ""), "📝") +
        _row("Total con IVA", f"${_money(snapshot.get('total_con_iva'))}", "💲")
    )
    return _send_email(app, subject, text, [snapshot.get("usuario_email")], html_body=html_body)


# ========= NOTIFICACIONES DE APROBACIÓN =========

ROLE_GA = (
    "gerente",
    "gerente de área", "gerente de area",
    "gerencia de área", "gerencia de area",
)

ROLE_GF = (
    "gerente financiero",
    "gerencia financiera",
)

ROLE_GG = (
    "gerente general",
    "gerencia general",
)

ROLE_COORD = ("coordinador",)

NEXT_ROLE_BY_AREA = {
    "ga": ROLE_GG,
    "gg": ROLE_GF,
    "gf": (),
}


def _approval_area_label(area_key: str) -> str:
    return {
        "ga": "Gerencia de Área",
        "gg": "Gerencia General",
        "gf": "Gerencia Financiera",
    }.get(_safe_lower(area_key), area_key or "")


def _build_user_approved_html(g, area_txt):
    fecha_fmt = _fmt_fecha_ddmmyyyy(g.get("fecha"))
    usuario = g.get("usuario_username") or ""

    rows = (
        _row_blue("ID", f"#{g['id']}") +
        _row_blue("Fecha", fecha_fmt) +
        _row_blue("Motivo", g.get("motivo") or "") +
        _row_blue("Total con IVA", f"${_money(g.get('total_con_iva'))}") +
        _row_blue("Aprobado por", area_txt)
    )

    link = _link_ver_gasto(g["id"])
    titulo = f"Gasto aprobado #{g['id']}"
    saludo = f"Hola {usuario}, tu gasto fue aprobado por {area_txt}."

    return _build_gastos_html_blue(titulo, saludo, rows, "Ver gasto", link)


def _build_next_step_html(g, approved_area_txt, next_area_txt):
    fecha_fmt = _fmt_fecha_ddmmyyyy(g.get("fecha"))
    usuario = g.get("usuario_username") or ""

    rows = (
        _row_blue("ID", f"#{g['id']}") +
        _row_blue("Fecha", fecha_fmt) +
        _row_blue("Motivo", g.get("motivo") or "") +
        _row_blue("Total con IVA", f"${_money(g.get('total_con_iva'))}") +
        _row_blue("Creador", usuario) +
        _row_blue("Estado", f"Aprobado por {approved_area_txt}")
    )

    link = _link_ver_gasto(g["id"])
    titulo = f"Acción requerida — Gasto #{g['id']}"
    saludo = f"{approved_area_txt} aprobó este gasto. Debes continuar con la aprobación ({next_area_txt})."

    return _build_gastos_html_blue(titulo, saludo, rows, "Revisar y aprobar gasto", link)


def _build_gasto_approved_html(g: Dict[str, Any], area_key: str, approver: Optional[Dict[str, Any]]):
    area_key = _safe_lower(area_key)
    area_txt = _approval_area_label(area_key)

    fecha_fmt = _fmt_fecha_ddmmyyyy(g.get("fecha"))
    usuario = g.get("usuario_username") or ""

    rows = (
        _row_blue("ID", f"#{g['id']}") +
        _row_blue("Fecha", fecha_fmt) +
        _row_blue("Motivo", g.get("motivo") or "") +
        _row_blue("Total con IVA", f"${_money(g.get('total_con_iva'))}") +
        _row_blue("Aprobado por", area_txt) +
        _row_blue("Creador", usuario)
    )

    link = _link_ver_gasto(g["id"])
    titulo = f"Gasto aprobado #{g['id']}"
    saludo = f"El gasto fue aprobado por {area_txt}."

    return _build_gastos_html_blue(titulo, saludo, rows, "Ver gasto", link)


def notify_gasto_approved(app, gasto_id: int, area: str, approved_by_user_id: int | None):
    """
    Flujo:
      - Siempre notifica al USUARIO.
      - Además notifica al SIGUIENTE rol solo para gastos normales.
      - Caja chica / Reembolso vendedor -> solo usuario.
    """
    conn = None
    try:
        conn = get_db()
        g = _gasto_meta(gasto_id)
        if not g:
            return False

        es_caja_chica = int(g.get("es_caja_chica") or 0) == 1
        es_reembolso = int(g.get("reembolso_vendedor") or 0) == 1
        es_tipo3 = es_caja_chica or es_reembolso

        area_key = _safe_lower(area)
        area_txt = _approval_area_label(area_key)
        creator_email = (g.get("usuario_email") or "").strip()

        sent_any = False

        if creator_email:
            subject_user = f"[Gastos] ✅ Tu gasto #{g['id']} fue aprobado por {area_txt}"
            text_user = (
                f"Tu gasto #{g['id']} fue aprobado por {area_txt}.\n"
                f"Fecha: {g.get('fecha')}\n"
                f"Motivo: {g.get('motivo')}\n"
                f"Total con IVA: {_money(g.get('total_con_iva'))}\n"
                f"Ver gasto: {_link_ver_gasto(g['id'])}\n"
            )
            html_user = _build_user_approved_html(g, area_txt)
            sent_any = _send_mail_safe(creator_email, subject_user, text_user, html_body=html_user) or sent_any

        if es_tipo3:
            try:
                app.logger.info(
                    "[GASTOS][MAIL] tipo3 -> solo usuario (sin siguiente aprobador) gasto_id=%s area=%s",
                    gasto_id, area_key
                )
            except Exception:
                pass
            return sent_any

        next_roles = NEXT_ROLE_BY_AREA.get(area_key, ())
        next_emails = _fetch_role_emails(conn, next_roles)

        next_area_txt = {
            "ga": "Gerencia General",
            "gg": "Gerencia Financiera",
            "gf": "Fin del flujo",
        }.get(area_key, "Siguiente aprobador")

        if next_emails:
            subject_next = f"[Gastos] ⏭️ Acción requerida — {area_txt} aprobó gasto #{g['id']}"
            text_next = (
                f"{area_txt} aprobó el gasto #{g['id']}.\n"
                f"El usuario debe continuar con el proceso de aprobación ({next_area_txt}).\n\n"
                f"Creador: {g.get('usuario_username')}\n"
                f"Fecha: {g.get('fecha')}\n"
                f"Motivo: {g.get('motivo')}\n"
                f"Total con IVA: {_money(g.get('total_con_iva'))}\n"
                f"Revisar: {_link_ver_gasto(g['id'])}\n"
            )
            html_next = _build_next_step_html(g, area_txt, next_area_txt)
            sent_any = _send_email(app, subject_next, text_next, next_emails, html_body=html_next) or sent_any

        return sent_any

    except Exception:
        try:
            app.logger.exception("[GASTOS][MAIL] Error en notify_gasto_approved")
        except Exception:
            pass
        return False
    finally:
        try:
            if conn:
                conn.close()
        except Exception:
            pass


# ========= EXPIRACIÓN / INACTIVACIÓN =========

def _build_expired_rows(gasto: dict, usuario: dict, gerente: dict) -> str:
    gid = gasto.get("id")
    fecha = (gasto.get("fecha") or "").strip()
    motivo = (gasto.get("motivo") or "").strip()

    return "\n".join([
        _row_kv("ID", f"#{gid}"),
        _row_kv("Fecha", fecha),
        _row_kv("Motivo", motivo),
        _row_kv("Usuario", _safe_name(usuario)),
        _row_kv("Gerente", _safe_name(gerente)),
        _row_kv("Estado", "Eliminado/Inactivado por política (15 días sin aprobación)"),
    ])


def _build_warning_rows(gasto: dict, usuario: dict, gerente: dict) -> str:
    gid = gasto.get("id")
    fecha = (gasto.get("fecha") or "").strip()
    motivo = (gasto.get("motivo") or "").strip()

    return "\n".join([
        _row_kv("ID", f"#{gid}"),
        _row_kv("Fecha", fecha),
        _row_kv("Motivo", motivo),
        _row_kv("Usuario", _safe_name(usuario)),
        _row_kv("Gerente", _safe_name(gerente)),
        _row_kv("Estado", "Aviso: si no se aprueba, se inactivará automáticamente mañana (política 15 días sin aprobación)."),
    ])


def notify_gasto_expiry_warning(app, gasto: dict, usuario: dict, gerente: dict):
    gid = gasto.get("id")
    fecha = (gasto.get("fecha") or "").strip()
    motivo = (gasto.get("motivo") or "").strip()

    to = []
    if _safe_email(usuario):
        to.append(_safe_email(usuario))
    if _safe_email(gerente) and _safe_email(gerente) not in to:
        to.append(_safe_email(gerente))

    subject = f"[Sistema de Reembolso] Aviso: Gasto #{gid} se inactivará si no se aprueba (día 14)"

    cta_link = _abs_url(app, f"/reembolsos/gastos/{gid}/ver")
    cta_text = "Ver gasto"

    titulo = f"Aviso de expiración — #{gid}"
    saludo = (
        "Este es un aviso preventivo: el gasto está por cumplir el plazo sin aprobaciones. "
        "Si no se aprueba, el sistema lo inactivará automáticamente por política (15 días)."
    )

    rows_html = _build_warning_rows(gasto, usuario, gerente)

    html_body = _build_gastos_html_orange(
        titulo=titulo,
        saludo=saludo,
        rows_html=rows_html,
        cta_text=cta_text,
        cta_link=cta_link
    )

    text_body = f"""
Hola,

Este es un aviso preventivo: el gasto #{gid} está por cumplir 15 días sin aprobaciones (GA/GG/GF).
Si no se aprueba, el sistema lo inactivará automáticamente por política.

Detalle:
- ID: {gid}
- Fecha: {fecha}
- Motivo: {motivo}
- Usuario: {_safe_name(usuario)}
- Gerente: {_safe_name(gerente)}
- Estado: Aviso (día 6): se inactivará si no se aprueba.

Ver gasto: {cta_link}

Saludos,
Sistema Reembolso de Gasto
""".strip()

    return _send_email(app, subject=subject, text_body=text_body, html_body=html_body, to=to)


def notify_gasto_expired_inactivated(app, gasto: dict, usuario: dict, gerente: dict):
    gid = gasto.get("id")
    fecha = (gasto.get("fecha") or "").strip()
    motivo = (gasto.get("motivo") or "").strip()

    to = []
    if _safe_email(usuario):
        to.append(_safe_email(usuario))
    if _safe_email(gerente) and _safe_email(gerente) not in to:
        to.append(_safe_email(gerente))

    subject = f"[Sistema de Reembolso] Gasto #{gid} eliminado por política (15 días sin aprobación)"

    cta_link = _abs_url(app, f"/reembolsos/gastos/{gid}/ver")
    cta_text = "Ver gasto"

    titulo = f"Gasto eliminado — #{gid}"
    saludo = "Por política de control, tu gasto fue inactivado automáticamente por no registrar aprobaciones (GA/GG/GF) durante 15 días."

    rows_html = _build_expired_rows(gasto, usuario, gerente)

    html_body = _build_gastos_html_red(
        titulo=titulo,
        saludo=saludo,
        rows_html=rows_html,
        cta_text=cta_text,
        cta_link=cta_link
    )

    text_body = f"""
Hola,

Por política de control, el gasto #{gid} fue inactivado automáticamente debido a que no registró ninguna aprobación (GA/GG/GF) durante 15 días.

Detalle:
- ID: {gid}
- Fecha: {fecha}
- Motivo: {motivo}
- Usuario: {_safe_name(usuario)}
- Gerente: {_safe_name(gerente)}
- Estado: Eliminado/Inactivado por política

Si se requiere cargar nuevamente el gasto, debe ingresarse un nuevo registro cumpliendo el flujo de aprobaciones.

Ver gasto: {cta_link}

Saludos,
Sistema Reembolso de Gastos
""".strip()

    return _send_email(app, subject=subject, text_body=text_body, html_body=html_body, to=to)