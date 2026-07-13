# modules/reclamos/routes_reclamos_notify.py
# -*- coding: utf-8 -*-
"""
Notificaciones por correo (HTML) del módulo de reclamos/oportunidades de mejora.
Cada función arma el cuerpo del correo y lo envía con _send_mail_safe.
"""

from datetime import datetime

from flask import current_app, url_for

from .routes_reclamos_querys import *
from .routes_reclamos_constants import *


def _notify_sponsor_respuesta_equipo(conn, imputacion_id: int, miembro_id: int, reclamo_codigo: str):
    from modules.routes_reclamos import _send_mail_safe

    cur = conn.cursor()

    # =========================================================
    # 1) Obtener datos base de la imputación / reclamo
    # =========================================================
    cur.execute(SQL__NOTIFY_SPONSOR_RESPUESTA_EQUIPO_SEL_1, (miembro_id, miembro_id, miembro_id, imputacion_id))

    base = cur.fetchone()

    if not base:
        return

    reclamo_id = base["reclamo_id"]
    proceso_id = base["proceso_id"]
    miembro_nombre = (
        base["miembro_nombre"]
        or base["miembro_username"]
        or f"UID {miembro_id}"
    )

    # =========================================================
    # 2) Obtener destinatarios: PRINCIPAL + BACKUP del proceso
    #    No desde reclamo_imputados, porque ahí solo existe principal.
    # =========================================================
    sponsor_rows = []

    if proceso_id:
        cur.execute(SQL__NOTIFY_SPONSOR_RESPUESTA_EQUIPO_SEL_2, (proceso_id,))

        sponsor_rows = cur.fetchall()

    # =========================================================
    # 3) Fallback de seguridad:
    #    Si por algún motivo no encuentra sponsors por proceso,
    #    notifica al imputado principal de reclamo_imputados.
    # =========================================================
    if not sponsor_rows:
        cur.execute(SQL__NOTIFY_SPONSOR_RESPUESTA_EQUIPO_SEL_3, (imputacion_id,))

        sponsor_rows = cur.fetchall()

    if not sponsor_rows:
        return

    try:
        link_sponsor = url_for("reclamos", _external=True) + "?tab=imputado"
    except Exception:
        link_sponsor = "http://bitacoraquimpac.com.ec:5000/reclamos?tab=imputado"

    subject = f"[Oportunidad de Mejora] Respuesta registrada por miembro de equipo en {reclamo_codigo}"

    def _parse_dt(v):
        if not v:
            return None

        if isinstance(v, datetime):
            return v

        s = str(v).strip()

        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S"
        ):
            try:
                return datetime.strptime(s[:19], fmt)
            except Exception:
                pass

        return None

    def _dias_respuesta(row):
        f_asig = _parse_dt(row["fecha_asignacion_miembro"])
        f_resp = _parse_dt(row["fecha_respuesta_miembro"])

        if not f_asig and not f_resp:
            return "Sin fechas registradas"

        if not f_asig:
            return "Sin fecha de asignación"

        if not f_resp:
            return "Sin fecha de respuesta"

        dias = (f_resp.date() - f_asig.date()).days

        if dias <= 0:
            return "Mismo día"

        return f"{dias} día(s)"

    def _row_mail(lbl, val):
        val = "" if val is None else str(val)
        val = val.replace("\n", "<br>")

        return (
            "<tr>"
            f"<td style='width:210px;background:#ffedd5;font-weight:600;"
            "padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;color:#374151;'>"
            f"{lbl}</td>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;color:#374151;'>"
            f"{val}</td>"
            "</tr>"
        )

    tiempo_respuesta = _dias_respuesta(base)
    enviados = set()

    # =========================================================
    # 4) Enviar a principal + backup, sin duplicar por correo
    # =========================================================
    for s in sponsor_rows:
        sponsor_email = (s["sponsor_email"] or "").strip().lower()

        if not sponsor_email or sponsor_email in enviados:
            continue

        enviados.add(sponsor_email)

        sponsor_nombre = (
            s["sponsor_nombre"]
            or s["sponsor_username"]
            or "Usuario"
        )

        tipo_sponsor = (s["tipo_sponsor"] or "").strip().upper()

        text_body = f"""Hola {sponsor_nombre},

El miembro de equipo {miembro_nombre} registró su respuesta de apoyo para la Oportunidad de Mejora {reclamo_codigo}.

Resumen:
- Cliente: {base["cliente_nombre"] or ""}
- Tipo de OM: {base["tipo_reclamo"] or ""}
- Tipo de trámite: {base["tipo_tramite"] or ""}
- Proceso: {base["proceso_text"] or ""}
- Rol sponsor: {tipo_sponsor}
- Tiempo de respuesta: {tiempo_respuesta}

Por favor ingresa al sistema y revisa el aporte en la pestaña "Soy Sponsor".

Ir al sistema: {link_sponsor}

Este es un mensaje automático.
"""

        html_body = f"""\
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
                <div style="font-size:12px;text-transform:uppercase;letter-spacing:.08em;opacity:.95;">
                  Oportunidad de Mejora
                </div>
                <div style="font-size:18px;font-weight:700;margin-top:4px;">
                  Respuesta registrada por miembro de equipo
                </div>
                <div style="font-size:12px;opacity:.95;margin-top:6px;">
                  Hola {sponsor_nombre}, el usuario <strong>{miembro_nombre}</strong> ya registró su aporte para la OM {reclamo_codigo}.
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:18px 20px 10px 20px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                       style="border-collapse:collapse;">
                  {_row_mail('Código', base['codigo'])}
                  {_row_mail('Miembro que respondió', miembro_nombre)}
                  {_row_mail('Rol sponsor', tipo_sponsor)}
                  {_row_mail('Cliente', base['cliente_nombre'])}
                  {_row_mail('Tipo de OM', base['tipo_reclamo'])}
                  {_row_mail('Proceso', base['proceso_text'])}
                  {_row_mail('Antecedente', base['antecedente'])}
                  {_row_mail('Observación', base['observacion'])}
                </table>

                <div style="margin-top:18px;margin-bottom:6px;text-align:left;">
                  <a href="{link_sponsor}"
                     style="display:inline-block;background:#f59e0b;color:#ffffff;
                            text-decoration:none;padding:10px 18px;border-radius:6px;
                            font-weight:600;font-size:13px;">
                    Revisar aporte del equipo
                  </a>
                </div>

                <div style="font-size:11px;color:#6b7280;margin-top:8px;">
                  Ingresa al módulo de reclamos y revisa la pestaña <strong>“Soy Sponsor”</strong>.
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

        _send_mail_safe(
            sponsor_email,
            subject,
            text_body,
            html_body=html_body
        )


def _notify_reclamo_adjuntos_change(conn, reclamo_id: int, actor_id: int | None,
                                    accion: str, filenames: list[str]):
    """
    accion: 'agregados' o 'eliminados'
    filenames: lista de nombres originales afectados
    """
    from modules.routes_reclamos import _send_mail_safe, _get_user_basic

    cur = conn.cursor()
    cur.execute(SQL__NOTIFY_RECLAMO_ADJUNTOS_CHANGE_SEL_1, (reclamo_id,))
    r = cur.fetchone()
    if not r:
        return

    codigo = r["codigo"]
    creador_id = r["creado_por"]

    creador = _get_user_basic(conn, creador_id)
    actor = _get_user_basic(conn, actor_id) if actor_id else None

    if not creador or ("email" not in creador.keys()) or not creador["email"]:
        return

    actor_name = (
        actor["nombre_completo"]
        if actor and "nombre_completo" in actor.keys() and actor["nombre_completo"]
        else (actor["username"] if actor else "Sistema")
    )

    lista = "\n".join(f"- {fn}" for fn in filenames) or "(sin detalle)"

    subject = f"[Oportunidad de Mejora] Adjuntos {accion} en {codigo}"
    text_body = f"""Hola {creador['username']},

Se han {accion} archivos en la Oportunidad de Mejora {codigo}.

Acción realizada por: {actor_name}

Archivos:
{lista}

Este es un mensaje automático.
"""

    _send_mail_safe(creador["email"], subject, text_body)


def _notify_colaborador_asignado(
    conn,
    colaborador_id: int,
    reclamo_codigo: str,
    responsable_username: str
):
    from modules.routes_reclamos import _send_mail_safe, _get_user_basic, _is_sqlserver_conn

    u = _get_user_basic(conn, colaborador_id)
    if not u or ("email" not in u.keys()) or not u["email"]:
        return

    # --- Datos del reclamo (por codigo) ---
    cur = conn.cursor()
    cur.execute(SQL__NOTIFY_COLABORADOR_ASIGNADO_SEL_1, (reclamo_codigo,))
    r = cur.fetchone()

    # Imputados (si aplica)
    imputados = ""
    if r:
        if _is_sqlserver_conn(conn):
            cur.execute(SQL__NOTIFY_COLABORADOR_ASIGNADO_SEL_2, (r["id"],))
        else:
            if _is_sqlserver_conn(conn):
                cur.execute(SQL__NOTIFY_COLABORADOR_ASIGNADO_SEL_2, (r["id"],))
            else:
                cur.execute(SQL__NOTIFY_COLABORADOR_ASIGNADO_SEL_3, (r["id"],))
            row = cur.fetchone()
            if row and row["lista"]:
                imputados = row["lista"]
        row = cur.fetchone()
        if row and row["lista"]:
            imputados = row["lista"]

    # Link directo a tab "Soy Sponsor"
    try:
        link_sponsor = url_for("reclamos", _external=True) + "?tab=sponsor"
    except Exception:
        link_sponsor = "https://tu-sistema/reclamos?tab=sponsor"

    nombre = (u["nombre_completo"] or "").strip() if "nombre_completo" in u.keys() else ""
    if not nombre:
        nombre = u["username"]

    subject = f"[Oportunidad de Mejora] Aporte requerido en {reclamo_codigo}"

    # Texto plano (fallback)
    text_body = f"""Hola {nombre},

El responsable {responsable_username} te ha solicitado apoyo para la
Oportunidad de Mejora {reclamo_codigo}.

Por favor ingresa al sistema, pestaña "Soy Sponsor" y registra tu aporte
(causa, acción preventiva y acción correctiva).

Ir al sistema: {link_sponsor}

Este aporte no es la respuesta oficial, pero ayudará al responsable a
construir la respuesta final.

Este es un mensaje automático.
"""

    # ---------- HTML mejorado (mismo estilo que aprobador) ----------
    def _row(lbl, val):
        val = (val or "")
        val = str(val).replace("\n", "<br>")
        return (
            "<tr>"
            f"<td style='width:210px;background:#fee2e2;font-weight:600;"
            "padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;'>"
            f"{lbl}</td>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;'>"
            f"{val}</td>"
            "</tr>"
        )

    html_body = f"""\
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
            <!-- Encabezado -->
            <tr>
              <td style="background:#b91c1c;padding:16px 20px;color:#ffffff;">
                <div style="font-size:12px;text-transform:uppercase;
                            letter-spacing:.08em;opacity:.9;">
                  Oportunidad de Mejora
                </div>
                <div style="font-size:18px;font-weight:700;margin-top:4px;">
                  Aporte requerido {reclamo_codigo}
                </div>
                <div style="font-size:12px;opacity:.9;margin-top:6px;">
                  Hola {nombre}, el responsable <strong>{responsable_username}</strong> solicitó tu apoyo.
                </div>
              </td>
            </tr>

            <!-- Cuerpo -->
            <tr>
              <td style="padding:18px 20px 10px 20px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                       style="border-collapse:collapse;">
                  {_row('Código', reclamo_codigo)}
                  {_row('Responsable', responsable_username)}
                  { _row('Fecha OM', r['fecha_reclamo']) if r else '' }
                  { _row('Tipo de OM', r['tipo_reclamo']) if r else '' }
                  { _row('Tipo de Trámite', r['tipo_tramite']) if r else '' }
                  { _row('Cliente', r['cliente_nombre']) if r else '' }
                  { _row('Proceso', r['proceso_text']) if r else '' }
                  { _row('Material', r['material_desc']) if (r and 'material_desc' in r.keys()) else '' }
                  { _row('Fecha de Pedido', r['fecha_pedido']) if r else '' }
                  { _row('Factura', r['factura']) if r else '' }
                  { _row('Guía Remisión', r['guia_remision']) if r else '' }
                  { _row('Imputados', imputados) if imputados else '' }
                  { _row('Antecedente', r['antecedente']) if r else '' }
                  { _row('Observación', r['observacion']) if r else '' }
                </table>

                <div style="margin-top:14px;font-size:12px;color:#374151;">
                  Por favor ingresa a la pestaña <strong>“Soy Sponsor”</strong> y registra tu aporte:
                  <strong>causa</strong>, <strong>acción preventiva</strong> y <strong>acción correctiva</strong>.
                  <br>
                  <span style="color:#6b7280;">
                    Este aporte no es la respuesta oficial, pero ayudará al responsable a construir la respuesta final.
                  </span>
                </div>

                <!-- Botón CTA -->
                <div style="margin-top:18px;margin-bottom:6px;text-align:left;">
                  <a href="{link_sponsor}"
                     style="display:inline-block;background:#2563eb;color:#ffffff;
                            text-decoration:none;padding:10px 18px;border-radius:6px;
                            font-weight:600;font-size:13px;">
                    Registrar aporte (Soy Sponsor)
                  </a>
                </div>

                <div style="font-size:11px;color:#6b7280;margin-top:8px;">
                  También puedes ingresar al módulo de reclamos desde el sistema
                  y abrir la bandeja <strong>“Soy Sponsor”</strong>.
                </div>
              </td>
            </tr>

            <!-- Pie -->
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

    _send_mail_safe(u["email"], subject, text_body, html_body=html_body)


def _notify_responsable_aporte_listo(conn, responsable_id: int, reclamo_codigo: str, colaborador_username: str):
    from modules.routes_reclamos import _send_mail_safe, _get_user_basic

    r = _get_user_basic(conn, responsable_id)
    if not r or ("email" not in r.keys()) or not r["email"]:
        return

    nombre = r["nombre_completo"] if r.get("nombre_completo") else r["username"]

    subject = f"[Oportunidad de Mejora] Aporte recibido en {reclamo_codigo}"
    text_body = f"""Hola {nombre},

El usuario {colaborador_username} registró su aporte técnico en la
Oportunidad de Mejora {reclamo_codigo}.

Puedes revisarlo en la sección "Soy Sponsor" y, si lo consideras adecuado,
aprovecharlo para tu respuesta final como responsable.

Este es un mensaje automático.
"""
    _send_mail_safe(r["email"], subject, text_body)

def _notify_colaborador_aporte_rechazado(conn, colaborador_id: int, reclamo_codigo: str, motivo: str):
    """
    Notifica rechazo de aporte de equipo a:
    - miembro/colaborador que registró el aporte
    - sponsor principal y backup del proceso
    - usuarios de Servicio al Cliente

    Reutiliza:
    - _get_user_basic
    - _get_sponsor_emails_by_reclamo
    - _send_mail_safe
    """
    from modules.routes_reclamos import _send_mail_safe, _get_user_basic, _get_sponsor_emails_by_reclamo

    colaborador = _get_user_basic(conn, colaborador_id)

    colaborador_email = ""
    colaborador_nombre = "Miembro de equipo"

    if colaborador:
        colaborador_email = (colaborador["email"] or "").strip()
        colaborador_nombre = (
            colaborador["nombre_completo"]
            if "nombre_completo" in colaborador.keys() and colaborador["nombre_completo"]
            else colaborador["username"]
        )

    motivo_txt = (motivo or "Sin detalle").strip()

    cur = conn.cursor()

    # =========================================================
    # Datos base de la OM
    # =========================================================
    cur.execute(SQL__NOTIFY_COLABORADOR_ASIGNADO_SEL_1, (reclamo_codigo,))

    r = cur.fetchone()

    try:
        link_sistema = url_for("reclamos", _external=True) + "?tab=sponsor"
    except Exception:
        link_sistema = "https://tu-sistema/reclamos?tab=sponsor"

    subject = f"[Oportunidad de Mejora] Aporte de equipo rechazado {reclamo_codigo}"

    def _row(lbl, val):
        val = "" if val is None else str(val)
        val = val.replace("\n", "<br>")
        return (
            "<tr>"
            f"<td style='width:210px;background:#fef3c7;font-weight:600;"
            "padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;'>"
            f"{lbl}</td>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;'>"
            f"{val}</td>"
            "</tr>"
        )

    # =========================================================
    # Destinatarios
    # =========================================================
    destinatarios = []

    # 1) Miembro/colaborador
    if colaborador_email:
        destinatarios.append({
            "email": colaborador_email,
            "nombre": colaborador_nombre,
            "rol_notificacion": "MIEMBRO DE EQUIPO"
        })

    # 2) Sponsor principal + backup
    try:
        for s in _get_sponsor_emails_by_reclamo(conn, reclamo_codigo):
            destinatarios.append({
                "email": s["email"],
                "nombre": s["nombre"] or s["username"] or "Usuario",
                "rol_notificacion": s["tipo_sponsor"] or "SPONSOR"
            })
    except Exception:
        current_app.logger.exception(
            "No se pudo obtener sponsor principal/backup para OM %s",
            reclamo_codigo
        )

    # 3) Servicio al Cliente
    cur.execute(SQL__NOTIFY_COLABORADOR_APORTE_RECHAZADO_SEL_1)

    for sc in cur.fetchall():
        destinatarios.append({
            "email": sc["email"],
            "nombre": sc["nombre"] or sc["username"] or "Servicio al Cliente",
            "rol_notificacion": "SERVICIO AL CLIENTE"
        })

    # =========================================================
    # Enviar sin duplicar correos
    # =========================================================
    enviados = set()

    for d in destinatarios:
        email = (d.get("email") or "").strip().lower()

        if not email or email in enviados:
            continue

        enviados.add(email)

        nombre_destinatario = d.get("nombre") or "Usuario"
        rol_notificacion = d.get("rol_notificacion") or ""

        text_body = f"""Hola {nombre_destinatario},

El aporte técnico registrado por {colaborador_nombre} para la Oportunidad de Mejora {reclamo_codigo} fue RECHAZADO.

Rol de notificación:
{rol_notificacion}

Motivo del rechazo:
{motivo_txt}

Por favor ingresa al sistema para revisar el detalle de la OM.

Ir al sistema:
{link_sistema}

Este es un mensaje automático.
"""

        html_body = f"""\
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
              <td style="background:#b45309;padding:16px 20px;color:#ffffff;">
                <div style="font-size:12px;text-transform:uppercase;
                            letter-spacing:.08em;opacity:.9;">
                  Oportunidad de Mejora
                </div>
                <div style="font-size:18px;font-weight:700;margin-top:4px;">
                  Aporte de equipo rechazado {reclamo_codigo}
                </div>
                <div style="font-size:12px;opacity:.9;margin-top:6px;">
                  Hola {nombre_destinatario}, se rechazó un aporte de equipo y requiere seguimiento.
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:18px 20px 10px 20px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                       style="border-collapse:collapse;">
                  {_row('Código', reclamo_codigo)}
                  {_row('Miembro de equipo', colaborador_nombre)}
                  {_row('Rol de notificación', rol_notificacion)}
                  { _row('Fecha OM', r['fecha_reclamo']) if r else '' }
                  { _row('Tipo de OM', r['tipo_reclamo']) if r else '' }
                  { _row('Tipo de Trámite', r['tipo_tramite']) if r else '' }
                  { _row('Cliente', r['cliente_nombre']) if r else '' }
                  { _row('Proceso', r['proceso_text']) if r else '' }
                  { _row('Material', r['material_desc']) if (r and 'material_desc' in r.keys()) else '' }
                  { _row('Fecha de Pedido', r['fecha_pedido']) if r else '' }
                  { _row('Factura', r['factura']) if r else '' }
                  { _row('Guía Remisión', r['guia_remision']) if r else '' }
                  { _row('Antecedente', r['antecedente']) if r else '' }
                  { _row('Observación', r['observacion']) if r else '' }
                  {_row('Motivo del rechazo', motivo_txt)}
                </table>

                <div style="margin-top:18px;margin-bottom:6px;text-align:left;">
                  <a href="{link_sistema}"
                     style="display:inline-block;background:#f97316;color:#ffffff;
                            text-decoration:none;padding:10px 18px;border-radius:6px;
                            font-weight:600;font-size:13px;">
                    Revisar OM en el sistema
                  </a>
                </div>

                <div style="font-size:11px;color:#6b7280;margin-top:8px;">
                  Este correo fue enviado al miembro de equipo, sponsor principal,
                  backup y Servicio al Cliente.
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

        _send_mail_safe(
            email,
            subject,
            text_body,
            html_body=html_body
        )


def _notify_aprobador_imputacion(conn, aprobador_id, reclamo_codigo, imputado_username):
    from modules.routes_reclamos import _send_mail_safe, _get_user_basic

    jefe = _get_user_basic(conn, aprobador_id)
    if not jefe or ("email" not in jefe.keys()) or not jefe["email"]:
        return

    # --- Datos del reclamo (por codigo) ---
    cur = conn.cursor()
    cur.execute(SQL__NOTIFY_COLABORADOR_ASIGNADO_SEL_1, (reclamo_codigo,))
    r = cur.fetchone()

    # Imputados del caso (por si hay más de uno)
    imputados = imputado_username or ""
    if r:
        cur.execute(SQL__NOTIFY_APROBADOR_IMPUTACION_SEL_1, (r["id"],))
        row = cur.fetchone()
        if row and row["lista"]:
            imputados = row["lista"]

    # Link directo al tab "Por aprobar (Jefe)"
    try:
        link_aprobar = url_for("reclamos", _external=True) + "?tab=aprobar"
    except Exception:
        link_aprobar = "https://tu-sistema/reclamos?tab=aprobar"

    nombre = (
        jefe['nombre_completo']
        if 'nombre_completo' in jefe.keys() and jefe['nombre_completo']
        else jefe['username']
    )

    subject = f"[Oportunida de Mejora] Aprobación pendiente {reclamo_codigo}"

    text_body = f"""Hola {nombre},

Hay un reclamo {reclamo_codigo} con imputación pendiente para: {imputados}.
Por favor revísalo y aprueba/rechaza la imputación.

Ir al sistema: {link_aprobar}

Este es un mensaje automático.
"""

    def _row(lbl, val):
        val = (val or "").replace("\n", "<br>")
        return (
            "<tr>"
            f"<td style='width:210px;background:#fee2e2;font-weight:600;"
            "padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;'>"
            f"{lbl}</td>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;'>"
            f"{val}</td>"
            "</tr>"
        )

    html_body = f"""\
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
              <td style="background:#b91c1c;padding:16px 20px;color:#ffffff;">
                <div style="font-size:12px;text-transform:uppercase;
                            letter-spacing:.08em;opacity:.9;">
                  Oprotunidad de Mejora
                </div>
                <div style="font-size:18px;font-weight:700;margin-top:4px;">
                  Aprobación pendiente {reclamo_codigo}
                </div>
                <div style="font-size:12px;opacity:.9;margin-top:6px;">
                  Hola {nombre}, tienes una imputación pendiente de revisión.
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:18px 20px 10px 20px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                       style="border-collapse:collapse;">
                  {_row('Código', reclamo_codigo)}
                  {_row('Fecha OM', r['fecha_reclamo']) if r else ''}
                  {_row('Tipo de OM', r['tipo_reclamo']) if r else ''}
                  {_row('Tipo de Trámite', r['tipo_tramite']) if r else ''}
                  {_row('Cliente', r['cliente_nombre']) if r else ''}
                  {_row('Proceso', r['proceso_text']) if r else ''}
                  {_row('Material', r['material_desc']) if (r and 'material_desc' in r.keys()) else ''}
                  {_row('Fecha de Pedido', r['fecha_pedido']) if r else ''}
                  {_row('Factura', r['factura']) if r else ''}
                  {_row('Guía Remisión', r['guia_remision']) if r else ''}
                  {_row('Imputados', imputados)}
                  {_row('Antecedente', r['antecedente']) if r else ''}
                  {_row('Observación', r['observacion']) if r else ''}
                </table>

                <div style="margin-top:18px;margin-bottom:6px;text-align:left;">
                  <a href="{link_aprobar}"
                     style="display:inline-block;background:#2563eb;color:#ffffff;
                            text-decoration:none;padding:10px 18px;border-radius:6px;
                            font-weight:600;font-size:13px;">
                    Revisar y aprobar imputación
                  </a>
                </div>

                <div style="font-size:11px;color:#6b7280;margin-top:8px;">
                  También puedes ingresar al módulo de reclamos desde el sistema
                  y abrir la bandeja <strong>“Por aprobar (Jefe)”</strong>.
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

    _send_mail_safe(jefe["email"], subject, text_body, html_body=html_body)


def _notify_creador_rechazo_asignacion(conn, creador_id, reclamo_codigo, imputado_username, motivo):
    from modules.routes_reclamos import _send_mail_safe, _get_user_basic

    c = _get_user_basic(conn, creador_id)
    if not c:
        return
    subject = f"[Oportunidad de Mejora] Imputación rechazada en {reclamo_codigo}"
    body = (
        f"Hola {c['username']},\n\n"
        f"El reclamo {reclamo_codigo} fue RECHAZADO para el usuario {imputado_username}.\n"
        f"Motivo del rechazo:\n{motivo or 'Sin motivo informado.'}\n\n"
        "Este es un mensaje automático."
    )
    _send_mail_safe(c["email"], subject, body)


def _notify_imputado_aprobado(conn, imputado_id, reclamo_codigo):
    from modules.routes_reclamos import _send_mail_safe, _get_user_basic

    u = _get_user_basic(conn, imputado_id)
    if not u or ("email" not in u.keys()) or not u["email"]:
        return

    # --- Datos del reclamo (por código) ---
    cur = conn.cursor()
    cur.execute(SQL__NOTIFY_COLABORADOR_ASIGNADO_SEL_1, (reclamo_codigo,))
    r = cur.fetchone()

    # Link directo al tab "Soy responsable"
    try:
        link_responder = url_for("reclamos", _external=True) + "?tab=imputado"
    except Exception:
        link_responder = "https://tu-sistema/reclamos?tab=imputado"

    nombre = (
        u['nombre_completo']
        if 'nombre_completo' in u.keys() and u['nombre_completo']
        else u['username']
    )

    subject = f"[Oportunidad de Mejora] Nueva OM asignada ({reclamo_codigo})"

    # Texto plano (fallback)
    text_body = f"""Hola {nombre},

Se te ha asignado la Oportunidad de Mejora {reclamo_codigo}.
Por favor ingresa al sistema, revisa el detalle y registra:

- Causa raíz
- Acción preventiva
- Acción correctiva

Ir al sistema: {link_responder}

Este es un mensaje automático.
"""

    # ---------- HTML similar al del aprobador ----------
    def _row(lbl, val):
        val = (val or "").replace("\n", "<br>")
        return (
            "<tr>"
            f"<td style='width:210px;background:#dbeafe;font-weight:600;"
            "padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;'>"
            f"{lbl}</td>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;'>"
            f"{val}</td>"
            "</tr>"
        )

    html_body = f"""\
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
            <!-- Encabezado -->
            <tr>
              <td style="background:#2563eb;padding:16px 20px;color:#ffffff;">
                <div style="font-size:12px;text-transform:uppercase;
                            letter-spacing:.08em;opacity:.9;">
                  Oportunidad de Mejora
                </div>
                <div style="font-size:18px;font-weight:700;margin-top:4px;">
                  Nueva OM asignada {reclamo_codigo}
                </div>
                <div style="font-size:12px;opacity:.9;margin-top:6px;">
                  Hola {nombre}, se te ha asignado esta OM para análisis y respuesta técnica.
                </div>
              </td>
            </tr>

            <!-- Cuerpo -->
            <tr>
              <td style="padding:18px 20px 10px 20px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                       style="border-collapse:collapse;">
                  {_row('Código', reclamo_codigo)}
                  { _row('Fecha OM', r['fecha_reclamo']) if r else '' }
                  { _row('Tipo de OM', r['tipo_reclamo']) if r else '' }
                  { _row('Tipo de Trámite', r['tipo_tramite']) if r else '' }
                  { _row('Cliente', r['cliente_nombre']) if r else '' }
                  { _row('Proceso', r['proceso_text']) if r else '' }
                  { _row('Material', r['material_desc']) if (r and 'material_desc' in r.keys()) else '' }
                  { _row('Fecha de Pedido', r['fecha_pedido']) if r else '' }
                  { _row('Factura', r['factura']) if r else '' }
                  { _row('Guía Remisión', r['guia_remision']) if r else '' }
                  { _row('Antecedente', r['antecedente']) if r else '' }
                  { _row('Observación', r['observacion']) if r else '' }
                </table>

                <!-- Botón CTA -->
                <div style="margin-top:18px;margin-bottom:6px;text-align:left;">
                  <a href="{link_responder}"
                     style="display:inline-block;background:#2563eb;color:#ffffff;
                            text-decoration:none;padding:10px 18px;border-radius:6px;
                            font-weight:600;font-size:13px;">
                    Ingresar y responder medidas
                  </a>
                </div>

                <div style="font-size:11px;color:#6b7280;margin-top:8px;">
                  Una vez completes la causa, acción preventiva y correctiva,
                  tu jefe revisará y aprobará la respuesta técnica.
                </div>
              </td>
            </tr>

            <!-- Pie -->
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

    _send_mail_safe(u["email"], subject, text_body, html_body=html_body)


def _notify_jefe_respuesta_listo(conn, aprobador_id, reclamo_codigo, imputado_username):
    from modules.routes_reclamos import _send_mail_safe, _get_user_basic, _is_sqlserver_conn

    jefe = _get_user_basic(conn, aprobador_id)
    if not jefe or ("email" not in jefe.keys()) or not jefe["email"]:
        return

    # --- Datos del reclamo (por código) ---
    cur = conn.cursor()
    if _is_sqlserver_conn(conn):
        cur.execute(SQL__NOTIFY_COLABORADOR_ASIGNADO_SEL_1, (reclamo_codigo,))
    else:
        cur.execute(SQL__NOTIFY_COLABORADOR_ASIGNADO_SEL_1, (reclamo_codigo,))
    r = cur.fetchone()

    # Imputados del caso (por si hay más de uno)
    imputados = imputado_username or ""
    if r:
        cur.execute(SQL__NOTIFY_COLABORADOR_ASIGNADO_SEL_3, (r["id"],))
        row = cur.fetchone()
        if row and row["lista"]:
            imputados = row["lista"]

    # Link directo al tab "Por aprobar (Jefe)" para validar la respuesta técnica
    try:
        link_validar = url_for("reclamos", _external=True) + "?tab=aprobar"
    except Exception:
        link_validar = "https://tu-sistema/reclamos?tab=aprobar"

    nombre = (
        jefe['nombre_completo']
        if 'nombre_completo' in jefe.keys() and jefe['nombre_completo']
        else jefe['username']
    )

    subject = f"[Oportunidad de Mejora] Validar respuesta técnica {reclamo_codigo}"

    # Texto plano (fallback)
    text_body = f"""Hola {nombre},

El usuario {imputado_username} ha registrado la respuesta técnica para la
Oportunidad de Mejora {reclamo_codigo}.

Por favor revisa las medidas propuestas (causa, acción preventiva y correctiva)
y aprueba o rechaza la respuesta.

Ir al sistema: {link_validar}

Este es un mensaje automático.
"""

    # ---------- HTML mejorado ----------
    def _row(lbl, val):
        val = (val or "").replace("\n", "<br>")
        return (
            "<tr>"
            f"<td style='width:210px;background:#fee2e2;font-weight:600;"
            "padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;'>"
            f"{lbl}</td>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;'>"
            f"{val}</td>"
            "</tr>"
        )

    html_body = f"""\
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
            <!-- Encabezado -->
            <tr>
              <td style="background:#1d4ed8;padding:16px 20px;color:#ffffff;">
                <div style="font-size:12px;text-transform:uppercase;
                            letter-spacing:.08em;opacity:.9;">
                  Oportunidad de Mejora
                </div>
                <div style="font-size:18px;font-weight:700;margin-top:4px;">
                  Validar respuesta técnica {reclamo_codigo}
                </div>
                <div style="font-size:12px;opacity:.9;margin-top:6px;">
                  Hola {nombre}, el usuario {imputado_username} ha registrado su respuesta
                  y está pendiente de tu aprobación.
                </div>
              </td>
            </tr>

            <!-- Cuerpo -->
            <tr>
              <td style="padding:18px 20px 10px 20px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                       style="border-collapse:collapse;">
                  {_row('Código', reclamo_codigo)}
                  { _row('Fecha OM', r['fecha_reclamo']) if r else '' }
                  { _row('Tipo de OM', r['tipo_reclamo']) if r else '' }
                  { _row('Tipo de Trámite', r['tipo_tramite']) if r else '' }
                  { _row('Cliente', r['cliente_nombre']) if r else '' }
                  { _row('Proceso', r['proceso_text']) if r else '' }
                  { _row('Material', r['material_desc']) if (r and 'material_desc' in r.keys()) else '' }
                  { _row('Fecha de Pedido', r['fecha_pedido']) if r else '' }
                  { _row('Factura', r['factura']) if r else '' }
                  { _row('Guía Remisión', r['guia_remision']) if r else '' }
                  {_row('Imputados', imputados)}
                  { _row('Antecedente', r['antecedente']) if r else '' }
                  { _row('Observación', r['observacion']) if r else '' }
                </table>

                <!-- Botón CTA -->
                <div style="margin-top:18px;margin-bottom:6px;text-align:left;">
                  <a href="{link_validar}"
                     style="display:inline-block;background:#2563eb;color:#ffffff;
                            text-decoration:none;padding:10px 18px;border-radius:6px;
                            font-weight:600;font-size:13px;">
                    Revisar y validar respuesta técnica
                  </a>
                </div>

                <div style="font-size:11px;color:#6b7280;margin-top:8px;">
                  También puedes ingresar al módulo de reclamos desde el sistema
                  y abrir la bandeja <strong>“Por aprobar (Jefe)”</strong> para validar las respuestas.
                </div>
              </td>
            </tr>

            <!-- Pie -->
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

    _send_mail_safe(jefe["email"], subject, text_body, html_body=html_body)


def _notify_imputado_respuesta_rechazada(conn, imputado_id, reclamo_codigo, motivo):
    """
    Notifica rechazo de respuesta técnica a:
    - imputado/responsable que debe corregir
    - sponsor principal y backup del proceso
    - usuarios de Servicio al Cliente

    Reutiliza:
    - _get_user_basic
    - _get_sponsor_emails_by_reclamo
    - _send_mail_safe
    """
    from modules.routes_reclamos import _send_mail_safe, _get_user_basic, _get_sponsor_emails_by_reclamo

    u = _get_user_basic(conn, imputado_id)
    if not u or ("email" not in u.keys()) or not u["email"]:
        imputado_email = None
        imputado_nombre = "Responsable técnico"
    else:
        imputado_email = (u["email"] or "").strip()
        imputado_nombre = (
            u["nombre_completo"]
            if "nombre_completo" in u.keys() and u["nombre_completo"]
            else u["username"]
        )

    cur = conn.cursor()

    # =========================================================
    # Datos del reclamo
    # =========================================================
    cur.execute(SQL__NOTIFY_COLABORADOR_ASIGNADO_SEL_1, (reclamo_codigo,))

    r = cur.fetchone()

    try:
        link_responder = url_for("reclamos", _external=True) + "?tab=imputado"
    except Exception:
        link_responder = "https://tu-sistema/reclamos?tab=imputado"

    motivo_txt = (motivo or "Sin detalle").strip()

    subject = f"[Oportunidad de Mejora] Ajuste requerido en respuesta {reclamo_codigo}"

    # =========================================================
    # Helper visual para correo HTML
    # =========================================================
    def _row(lbl, val):
        val = "" if val is None else str(val)
        val = val.replace("\n", "<br>")
        return (
            "<tr>"
            f"<td style='width:210px;background:#fef3c7;font-weight:600;"
            "padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;'>"
            f"{lbl}</td>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;'>"
            f"{val}</td>"
            "</tr>"
        )

    # =========================================================
    # Servicio al Cliente
    # No existe actualmente una función que devuelva la lista.
    # Se reutiliza la misma regla ya usada en _can_view_all_reclamos:
    # departamento Servicio al Cliente o puesto que contenga Servicio al Cliente.
    # =========================================================
    cur.execute(SQL__NOTIFY_COLABORADOR_APORTE_RECHAZADO_SEL_1)

    servicio_cliente_rows = cur.fetchall()

    # =========================================================
    # Destinatarios
    # =========================================================
    destinatarios = []

    # 1) Imputado / responsable que debe corregir
    if imputado_email:
        destinatarios.append({
            "email": imputado_email,
            "nombre": imputado_nombre,
            "rol_notificacion": "RESPONSABLE"
        })

    # 2) Sponsor principal + backup
    # Reutiliza función existente.
    try:
        for s in _get_sponsor_emails_by_reclamo(conn, reclamo_codigo):
            destinatarios.append({
                "email": s["email"],
                "nombre": s["nombre"] or s["username"] or "Usuario",
                "rol_notificacion": s["tipo_sponsor"] or "SPONSOR"
            })
    except Exception:
        current_app.logger.exception(
            "No se pudo obtener sponsor principal/backup para reclamo %s",
            reclamo_codigo
        )

    # 3) Servicio al Cliente
    for sc in servicio_cliente_rows:
        destinatarios.append({
            "email": sc["email"],
            "nombre": sc["nombre"] or sc["username"] or "Servicio al Cliente",
            "rol_notificacion": "SERVICIO AL CLIENTE"
        })

    enviados = set()

    for d in destinatarios:
        email = (d.get("email") or "").strip().lower()
        if not email or email in enviados:
            continue

        enviados.add(email)

        nombre_destinatario = d.get("nombre") or "Usuario"
        rol_notificacion = d.get("rol_notificacion") or ""

        text_body = f"""Hola {nombre_destinatario},

La respuesta técnica de la Oportunidad de Mejora {reclamo_codigo} fue RECHAZADA y requiere ajustes.

Responsable técnico:
{imputado_nombre}

Rol de notificación:
{rol_notificacion}

Motivo del rechazo:
{motivo_txt or 'Sin detalle'}

El responsable debe actualizar la causa, acción de control y acción correctiva en el sistema.

Ir al sistema:
{link_responder}

Este es un mensaje automático.
"""

        html_body = f"""\
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
              <td style="background:#b45309;padding:16px 20px;color:#ffffff;">
                <div style="font-size:12px;text-transform:uppercase;
                            letter-spacing:.08em;opacity:.9;">
                  Oportunidad de Mejora
                </div>
                <div style="font-size:18px;font-weight:700;margin-top:4px;">
                  Ajuste requerido en respuesta {reclamo_codigo}
                </div>
                <div style="font-size:12px;opacity:.9;margin-top:6px;">
                  Hola {nombre_destinatario}, se rechazó la respuesta técnica y requiere seguimiento.
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:18px 20px 10px 20px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                       style="border-collapse:collapse;">
                  {_row('Código', reclamo_codigo)}
                  {_row('Responsable técnico', imputado_nombre)}
                  {_row('Rol de notificación', rol_notificacion)}
                  { _row('Fecha OM', r['fecha_reclamo']) if r else '' }
                  { _row('Tipo de OM', r['tipo_reclamo']) if r else '' }
                  { _row('Tipo de Trámite', r['tipo_tramite']) if r else '' }
                  { _row('Cliente', r['cliente_nombre']) if r else '' }
                  { _row('Proceso', r['proceso_text']) if r else '' }
                  { _row('Material', r['material_desc']) if (r and 'material_desc' in r.keys()) else '' }
                  { _row('Fecha de Pedido', r['fecha_pedido']) if r else '' }
                  { _row('Factura', r['factura']) if r else '' }
                  { _row('Guía Remisión', r['guia_remision']) if r else '' }
                  { _row('Antecedente', r['antecedente']) if r else '' }
                  { _row('Observación', r['observacion']) if r else '' }
                  {_row('Motivo del rechazo', motivo_txt or 'Sin detalle')}
                </table>

                <div style="margin-top:18px;margin-bottom:6px;text-align:left;">
                  <a href="{link_responder}"
                     style="display:inline-block;background:#f97316;color:#ffffff;
                            text-decoration:none;padding:10px 18px;border-radius:6px;
                            font-weight:600;font-size:13px;">
                    Revisar respuesta técnica
                  </a>
                </div>

                <div style="font-size:11px;color:#6b7280;margin-top:8px;">
                  El responsable debe ingresar al módulo de reclamos, pestaña
                  <strong>“Soy responsable”</strong>, seleccionar la OM y actualizar
                  la causa raíz, acción de control y acción correctiva.
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

        _send_mail_safe(
            email,
            subject,
            text_body,
            html_body=html_body
        )


def _notify_creador_respuesta_aprobada(conn, creador_id, reclamo_codigo, imputado_username):
    from modules.routes_reclamos import _send_mail_safe, _get_user_basic, _get_sponsor_emails_by_reclamo

    c = _get_user_basic(conn, creador_id)
    if not c or ("email" not in c.keys()) or not c["email"]:
        return

    # --- Datos del reclamo (por código) ---
    cur = conn.cursor()
    cur.execute(SQL__NOTIFY_COLABORADOR_ASIGNADO_SEL_1, (reclamo_codigo,))
    r = cur.fetchone()

    # Link directo a "Mis reclamos"
    try:
        link_mis_reclamos = url_for("reclamos", _external=True) + "?tab=mios"
    except Exception:
        link_mis_reclamos = "https://tu-sistema/reclamos?tab=mios"

    nombre = (
        c['nombre_completo']
        if 'nombre_completo' in c.keys() and c['nombre_completo']
        else c['username']
    )

    responsable = imputado_username or "Responsable técnico"

    subject = f"[Oportunidad de Mejora] Respuesta final aprobada {reclamo_codigo}"

    # Texto plano (fallback)
    text_body = f"""Hola {nombre},

El responsable {responsable} registró y su jefe aprobó la respuesta técnica
de la Oportunidad de Mejora {reclamo_codigo}.

Ya puedes consultarla en el sistema.

Ir al sistema: {link_mis_reclamos}

Este es un mensaje automático.
"""

    # ---------- HTML mejorado ----------
    def _row(lbl, val):
        val = (val or "").replace("\n", "<br>")
        return (
            "<tr>"
            f"<td style='width:210px;background:#dcfce7;font-weight:600;"
            "padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;'>"
            f"{lbl}</td>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;'>"
            f"{val}</td>"
            "</tr>"
        )

    html_body = f"""\
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
            <!-- Encabezado -->
            <tr>
              <td style="background:#15803d;padding:16px 20px;color:#ffffff;">
                <div style="font-size:12px;text-transform:uppercase;
                            letter-spacing:.08em;opacity:.9;">
                  Oportunidad de Mejora
                </div>
                <div style="font-size:18px;font-weight:700;margin-top:4px;">
                  Respuesta final aprobada {reclamo_codigo}
                </div>
                <div style="font-size:12px;opacity:.9;margin-top:6px;">
                  Hola {nombre}, la respuesta técnica de esta OM fue aprobada por el jefe del responsable.
                </div>
              </td>
            </tr>

            <!-- Cuerpo -->
            <tr>
              <td style="padding:18px 20px 10px 20px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                       style="border-collapse:collapse;">
                  {_row('Código', reclamo_codigo)}
                  {_row('Responsable', responsable)}
                  { _row('Fecha OM', r['fecha_reclamo']) if r else '' }
                  { _row('Tipo de OM', r['tipo_reclamo']) if r else '' }
                  { _row('Tipo de Trámite', r['tipo_tramite']) if r else '' }
                  { _row('Cliente', r['cliente_nombre']) if r else '' }
                  { _row('Proceso', r['proceso_text']) if r else '' }
                  { _row('Material', r['material_desc']) if (r and 'material_desc' in r.keys()) else '' }
                  { _row('Fecha de Pedido', r['fecha_pedido']) if r else '' }
                  { _row('Factura', r['factura']) if r else '' }
                  { _row('Guía Remisión', r['guia_remision']) if r else '' }
                  { _row('Antecedente', r['antecedente']) if r else '' }
                  { _row('Observación', r['observacion']) if r else '' }
                </table>

                <!-- Botón CTA -->
                <div style="margin-top:18px;margin-bottom:6px;text-align:left;">
                  <a href="{link_mis_reclamos}"
                     style="display:inline-block;background:#16a34a;color:#ffffff;
                            text-decoration:none;padding:10px 18px;border-radius:6px;
                            font-weight:600;font-size:13px;">
                    Ver respuesta técnica
                  </a>
                </div>

                <div style="font-size:11px;color:#6b7280;margin-top:8px;">
                  También puedes ingresar al módulo de reclamos y abrir la pestaña
                  <strong>“Mis reclamos”</strong> para revisar el detalle completo de la OM.
                </div>
              </td>
            </tr>

            <!-- Pie -->
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

    destinatarios = []

    # creador de la OM
    if c["email"]:
        destinatarios.append({
            "email": c["email"],
            "nombre": nombre
        })

    # principal + backup del proceso
    for s in _get_sponsor_emails_by_reclamo(conn, reclamo_codigo):
        destinatarios.append({
            "email": s["email"],
            "nombre": s["nombre"] or s["username"] or "Usuario"
        })

    enviados = set()

    for d in destinatarios:
        email = (d["email"] or "").strip().lower()
        if not email or email in enviados:
            continue

        enviados.add(email)

        # opcional: personalizar saludo por destinatario
        html_final = html_body.replace(f"Hola {nombre}", f"Hola {d['nombre']}")
        text_final = text_body.replace(f"Hola {nombre}", f"Hola {d['nombre']}")

        _send_mail_safe(email, subject, text_final, html_body=html_final)


def _notify_creador_rechazo_validacion(conn, reclamo_id: int, reclamo_codigo: str,
                                        creador_nombre: str, motivo: str):
    """
    Notifica a sponsors (principal+backup), Servicio al Cliente y miembros de
    equipo cuando el creador de la OM rechaza la respuesta técnica.
    """
    from modules.routes_reclamos import _send_mail_safe

    cur = conn.cursor()

    # Datos completos de la OM
    cur.execute(SQL__NOTIFY_COLABORADOR_ASIGNADO_SEL_1, (reclamo_codigo,))
    r = cur.fetchone()

    try:
        link = url_for("reclamos", _external=True) + "?tab=imputado"
    except Exception:
        link = "http://bitacoraquimpac.com.ec:5000/reclamos?tab=imputado"

    subject = f"[Oportunidad de Mejora] Respuesta rechazada por el creador — {reclamo_codigo}"

    motivo_visible = motivo.strip() if motivo else "Sin motivo especificado."

    def _row(lbl, val):
        val = (val or "").replace("\n", "<br>")
        return (
            "<tr>"
            f"<td style='width:210px;background:#fee2e2;font-weight:600;"
            "padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;'>"
            f"{lbl}</td>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;'>"
            f"{val}</td>"
            "</tr>"
        )

    def _html(dest_nombre):
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
            <!-- Encabezado -->
            <tr>
              <td style="background:#dc2626;padding:16px 20px;color:#ffffff;">
                <div style="font-size:12px;text-transform:uppercase;
                            letter-spacing:.08em;opacity:.9;">
                  Oportunidad de Mejora
                </div>
                <div style="font-size:18px;font-weight:700;margin-top:4px;">
                  Respuesta rechazada — {reclamo_codigo}
                </div>
                <div style="font-size:12px;opacity:.9;margin-top:6px;">
                  Hola {dest_nombre}, el creador <strong>{creador_nombre}</strong>
                  rechazó la respuesta técnica de esta OM.
                </div>
              </td>
            </tr>

            <!-- Cuerpo -->
            <tr>
              <td style="padding:18px 20px 10px 20px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                       style="border-collapse:collapse;">
                  {_row('Código', reclamo_codigo)}
                  { _row('Fecha OM', r['fecha_reclamo']) if r else '' }
                  { _row('Tipo de OM', r['tipo_reclamo']) if r else '' }
                  { _row('Tipo de Trámite', r['tipo_tramite']) if r else '' }
                  { _row('Cliente', r['cliente_nombre']) if r else '' }
                  { _row('Proceso', r['proceso_text']) if r else '' }
                  { _row('Material', r['material_desc']) if (r and 'material_desc' in r.keys()) else '' }
                  { _row('Fecha de Pedido', r['fecha_pedido']) if r else '' }
                  { _row('Factura', r['factura']) if r else '' }
                  { _row('Guía Remisión', r['guia_remision']) if r else '' }
                  { _row('Observación', r['observacion']) if r else '' }
                  {_row('Rechazado por', creador_nombre)}
                  {_row('Motivo del rechazo', motivo_visible)}
                </table>

                <!-- Botón CTA -->
                <div style="margin-top:18px;margin-bottom:6px;text-align:left;">
                  <a href="{link}"
                     style="display:inline-block;background:#dc2626;color:#ffffff;
                            text-decoration:none;padding:10px 18px;border-radius:6px;
                            font-weight:600;font-size:13px;">
                    Ingresar y registrar nueva respuesta
                  </a>
                </div>

                <div style="font-size:11px;color:#6b7280;margin-top:8px;">
                  La OM ha vuelto a estado <strong>Abierto</strong>.
                  Se requiere registrar una nueva respuesta técnica.
                </div>
              </td>
            </tr>

            <!-- Pie -->
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
</html>"""

    enviados = set()

    def _enviar(email, nombre):
        email = (email or "").strip().lower()
        if not email or email in enviados:
            return
        enviados.add(email)
        txt = (
            f"Hola {nombre},\n\n"
            f"El creador {creador_nombre} rechazó la respuesta de la OM {reclamo_codigo}.\n\n"
            f"Motivo: {motivo_visible}\n\n"
            f"La OM volvió a estado Abierto. Por favor ingresa al sistema y "
            f"registra una nueva respuesta técnica.\n\n"
            f"Ir al sistema: {link}\n\nEste es un mensaje automático."
        )
        _send_mail_safe(email, subject, txt, html_body=_html(nombre))

    # 1. Sponsors PRINCIPAL + BACKUP de cada proceso de la OM
    cur.execute(SQL_VALIDAR_CREADOR_SEL_BASE, (reclamo_id,))
    row_om = cur.fetchone()
    if row_om and row_om["proceso_id"]:
        cur.execute(SQL_VALIDAR_CREADOR_SEL_SPONSORS, (row_om["proceso_id"],))
        for s in cur.fetchall():
            _enviar(s["sponsor_email"], s["sponsor_nombre"])

    # 2. Imputados directos del reclamo
    cur.execute(SQL_VALIDAR_CREADOR_SEL_IMPUTADOS, (reclamo_id,))
    for row in cur.fetchall():
        _enviar(row["imputado_email"], row["imputado_nombre"])

    # 3. Servicio al Cliente
    cur.execute(SQL_VALIDAR_CREADOR_SEL_SAC)
    for row in cur.fetchall():
        _enviar(row["email"], row["nombre"])

    # 4. Miembros de equipo
    cur.execute(SQL_VALIDAR_CREADOR_SEL_EQUIPO, (reclamo_id,))
    for row in cur.fetchall():
        _enviar(row["miembro_email"], row["miembro_nombre"])
