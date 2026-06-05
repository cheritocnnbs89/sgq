from __future__ import annotations

from flask import current_app

from modules.email_utils import send_email_async as _send_email_async

from .contratos_constants import (
    PUBLIC_FIXED_URL,
    PGALLEGOS_FALLBACK_EMAIL_DEFAULT,
    SAVERA_EMAIL,
    GERENTE_FINANCIERO_EMAIL,
)
from html import escape
from . import contratos_repository as repository

def send_mail(to_addr: str, subject: str, message_plain: str, message_html: str | None = None):
    if not to_addr:
        return

    try:
        # Tu send_email_async solo acepta 3 parámetros.
        # Si hay HTML, enviamos el HTML como cuerpo del correo.
        body = message_html if message_html else message_plain

        _send_email_async([to_addr], subject, body)

    except Exception as _e:
        try:
            current_app.logger.warning("Fallo envío de correo a %s: %s", to_addr, _e)
        except Exception:
            pass

def lookup_email_by_user_id(uid: int | None) -> str:
    return repository.fetch_usuario_email_por_id(uid)


def lookup_email_by_username_or_email(name_or_email: str | None) -> str:
    return repository.fetch_usuario_email_por_username_o_email(name_or_email)


def pgallegos_email() -> str:
    email = repository.fetch_pgallegos_email()
    if email:
        return email
    return current_app.config.get("PGALLEGOS_FALLBACK_EMAIL", PGALLEGOS_FALLBACK_EMAIL_DEFAULT)


def savera_email() -> str:
    return SAVERA_EMAIL


def gerente_financiero_email() -> str:
    return GERENTE_FINANCIERO_EMAIL


def find_compras_email(usuario_compras_id: int | None, usuario_compras_nombre: str | None) -> str:
    mail = lookup_email_by_user_id(usuario_compras_id)
    if mail:
        return mail
    return lookup_email_by_username_or_email(usuario_compras_nombre)


def link_contrato(contrato_id: int) -> str:
    return PUBLIC_FIXED_URL


def link_garantia(garantia_id: int) -> str:
    return PUBLIC_FIXED_URL


def notify_contrato_registrado(
    contrato_id: int,
    pedido: str,
    proveedor: str,
    objeto: str,
    valor_contrato: float,
    fecha_suscripcion: str | None,
    usuario_solicitante_id: int | None,
    usuario_compras_id: int | None,
    usuario_compras_nombre: str | None,
):
    try:
        solicitante_nombre = repository.fetch_usuario_nombre_por_id(usuario_solicitante_id)
        solicitante_email = lookup_email_by_user_id(usuario_solicitante_id)
        compras_email = find_compras_email(usuario_compras_id, usuario_compras_nombre)
        p_email = pgallegos_email()
        link = link_contrato(contrato_id)

        subject_user = f"[SILI] Contrato registrado: Pedido {pedido} – {proveedor}"
        subject_compra = f"[SILI] Nuevo contrato registrado: Pedido {pedido} – {proveedor}"
        subject_pg = f"[SILI] Revisión requerida: Pedido {pedido} – {proveedor}"

        body_user_txt = (
            f"Hola {solicitante_nombre},\n\n"
            f"Tu contrato fue registrado correctamente.\n\n"
            f"Pedido: {pedido}\n"
            f"Proveedor: {proveedor}\n"
            f"Objeto: {objeto}\n"
            f"Valor: {valor_contrato:,.2f}\n"
            f"Fecha de suscripción: {fecha_suscripcion}\n\n"
            f"Ver detalle: {link}\n\n"
            f"— SILI"
        )
        body_compra_txt = (
            "Estimado/a Compras,\n\n"
            "Se registró un nuevo contrato.\n\n"
            f"Pedido: {pedido}\n"
            f"Proveedor: {proveedor}\n"
            f"Objeto: {objeto}\n"
            f"Valor: {valor_contrato:,.2f}\n"
            f"Fecha de suscripción: {fecha_suscripcion}\n\n"
            f"Ver contrato: {link}\n\n"
            "— SILI"
        )
        body_pg_txt = (
            "Estimado/a,\n\n"
            "Se ha registrado un nuevo contrato que requiere REVISIÓN y APROBACIÓN.\n\n"
            f"Pedido: {pedido}\n"
            f"Proveedor: {proveedor}\n"
            f"Objeto: {objeto}\n"
            f"Valor: {valor_contrato:,.2f}\n"
            f"Fecha de suscripción: {fecha_suscripcion}\n\n"
            f"Ver contrato: {link}\n\n"
            "— SILI"
        )

        if solicitante_email:
            send_mail(solicitante_email, subject_user, body_user_txt)
        if compras_email:
            send_mail(compras_email, subject_compra, body_compra_txt)
        if p_email:
            send_mail(p_email, subject_pg, body_pg_txt)
    except Exception as _e:
        try:
            current_app.logger.warning("Fallo envío de correos (contrato %s): %s", contrato_id, _e)
        except Exception:
            pass


def notify_toggle_aprobacion_jefe_contrato(
    contrato_id: int,
    pedido: str,
    proveedor: str,
    objeto: str,
    valor_contrato: float,
    usuario_solicitante_id: int | None,
    usuario_compras_id: int | None,
    usuario_compras_nombre: str | None,
    aprobado_jefe_por: int | None,
    aprobado_jefe: int,
):
    try:
        solicitante_email = lookup_email_by_user_id(usuario_solicitante_id)
        compras_email = find_compras_email(usuario_compras_id, usuario_compras_nombre)
        jefe_email = lookup_email_by_user_id(aprobado_jefe_por)
        savera_mail = savera_email()
        link = link_contrato(contrato_id)

        if aprobado_jefe == 1:
            subj_jefe = f"[SILI] Aprobación registrada: Pedido {pedido}"
            body_jefe = (
                "Estimado/a,\n\n"
                "Se registró su aprobación del contrato.\n\n"
                f"Pedido: {pedido}\n"
                f"Proveedor: {proveedor}\n"
                f"Objeto: {objeto}\n"
                f"Valor: {valor_contrato:,.2f}\n"
                f"Ver contrato: {link}\n\n"
                "— SILI"
            )
            subj_info = f"[SILI] Contrato aprobado por Compras: Pedido {pedido}"
            body_info = (
                "Notificación:\n\n"
                "El contrato fue aprobado por el área de Compras.\n\n"
                f"Pedido: {pedido}\nProveedor: {proveedor}\nObjeto: {objeto}\n"
                f"Valor: {valor_contrato:,.2f}\n"
                f"Ver contrato: {link}\n\n"
                "— SILI"
            )
            subj_savera = f"[SILI] Contrato aprobado: Gestionar Garantía (Pedido {pedido})"
            body_savera = (
                "Hola Savera,\n\n"
                "El contrato indicado fue ingresado y aprobado por Compras.\n"
                "Por favor, proceder con la gestión e ingreso de la GARANTÍA asociada para su aprobación.\n\n"
                f"Pedido: {pedido}\nProveedor: {proveedor}\nObjeto: {objeto}\n"
                f"Ver contrato: {link}\n\n"
                "— SILI"
            )
            if jefe_email:
                send_mail(jefe_email, subj_jefe, body_jefe)
            if solicitante_email:
                send_mail(solicitante_email, subj_info, body_info)
            if compras_email:
                send_mail(compras_email, subj_info, body_info)
            if savera_mail:
                send_mail(savera_mail, subj_savera, body_savera)
        else:
            subj_rev = f"[SILI] Aprobación revertida: Pedido {pedido}"
            body_rev = (
                "Notificación:\n\n"
                "La aprobación del contrato fue revertida.\n\n"
                f"Pedido: {pedido}\nProveedor: {proveedor}\nObjeto: {objeto}\n"
                f"Ver contrato: {link}\n\n"
                "— SILI"
            )
            if jefe_email:
                send_mail(jefe_email, subj_rev, body_rev)
            if solicitante_email:
                send_mail(solicitante_email, subj_rev, body_rev)
            if compras_email:
                send_mail(compras_email, subj_rev, body_rev)
    except Exception as _e:
        try:
            current_app.logger.warning("Fallo correos toggle_aprobacion_jefe(%s): %s", contrato_id, _e)
        except Exception:
            pass


def notify_garantia_ingresada(
    garantia_id: int | None,
    contrato_id: int,
    pedido: str,
    proveedor: str,
    objeto: str,
    usuario_solicitante_id: int | None,
    usuario_compras_id: int | None,
    usuario_compras_nombre: str | None,
    aprobado_jefe_por: int | None,
):
    try:
        solicitante_email = lookup_email_by_user_id(usuario_solicitante_id)
        compras_email = find_compras_email(usuario_compras_id, usuario_compras_nombre)
        jefe_email = lookup_email_by_user_id(aprobado_jefe_por)
        savera_mail = savera_email()
        link = link_garantia(garantia_id) if garantia_id else link_contrato(contrato_id)

        subj_sv = f"[SILI] Garantía ingresada para Pedido {pedido}"
        body_sv = (
            "Hola Savera,\n\n"
            "Se registró correctamente la GARANTÍA asociada a su contrato.\n\n"
            f"Pedido: {pedido}\nProveedor: {proveedor}\nObjeto: {objeto}\n"
            f"Ver garantía: {link}\n\n"
            "— SILI"
        )
        subj_inf = f"[SILI] Garantía ingresada: Pedido {pedido}"
        body_inf = (
            "Notificación:\n\n"
            "Se ha ingresado una GARANTÍA para el contrato indicado.\n\n"
            f"Pedido: {pedido}\nProveedor: {proveedor}\nObjeto: {objeto}\n"
            f"Detalle: {link}\n\n"
            "— SILI"
        )
        if savera_mail:
            send_mail(savera_mail, subj_sv, body_sv)
        if jefe_email:
            send_mail(jefe_email, subj_inf, body_inf)
        if solicitante_email:
            send_mail(solicitante_email, subj_inf, body_inf)
        if compras_email:
            send_mail(compras_email, subj_inf, body_inf)
    except Exception as _e:
        try:
            current_app.logger.warning("Fallo correos contab_nuevo(contrato %s): %s", contrato_id, _e)
        except Exception:
            pass


def notify_aprobacion_final_gf(
    contrato_id: int,
    pedido: str,
    proveedor: str,
    objeto: str,
    usuario_solicitante_id: int | None,
    usuario_compras_id: int | None,
    usuario_compras_nombre: str | None,
    aprobado_jefe_por: int | None,
):
    try:
        solicitante_email = lookup_email_by_user_id(usuario_solicitante_id)
        compras_email = find_compras_email(usuario_compras_id, usuario_compras_nombre)
        jefe_email = lookup_email_by_user_id(aprobado_jefe_por)
        savera_mail = savera_email()
        gerente_fin_mail = gerente_financiero_email()
        link = link_contrato(contrato_id)

        subj_gf_ok = f"[SILI] Aprobación FINAL (Gerencia Financiera): Pedido {pedido}"
        body_gf_ok = (
            "Estimado Gerente Financiero,\n\n"
            "Se registró su APROBACIÓN FINAL del contrato con su garantía asociada.\n\n"
            f"Pedido: {pedido}\nProveedor: {proveedor}\nObjeto: {objeto}\n"
            f"Ver contrato: {link}\n\n"
            "— SILI"
        )
        subj_info = f"[SILI] Contrato + Garantía APROBADOS por Gerencia Financiera: Pedido {pedido}"
        body_info = (
            "Notificación:\n\n"
            "El contrato y su garantía recibieron APROBACIÓN FINAL por parte de Gerencia Financiera.\n\n"
            f"Pedido: {pedido}\nProveedor: {proveedor}\nObjeto: {objeto}\n"
            f"Detalle: {link}\n\n"
            "— SILI"
        )

        if gerente_fin_mail:
            send_mail(gerente_fin_mail, subj_gf_ok, body_gf_ok)
        if savera_mail:
            send_mail(savera_mail, subj_info, body_info)
        if compras_email:
            send_mail(compras_email, subj_info, body_info)
        if solicitante_email:
            send_mail(solicitante_email, subj_info, body_info)
        if jefe_email:
            send_mail(jefe_email, subj_info, body_info)
    except Exception as _e:
        try:
            current_app.logger.warning("Fallo correos toggle_aprobacion_gf(%s): %s", contrato_id, _e)
        except Exception:
            pass


def notify_pendiente_gf(
    contrato_id: int,
    pedido: str,
    proveedor: str,
    objeto: str,
    usuario_solicitante_id: int | None,
    usuario_compras_id: int | None,
    usuario_compras_nombre: str | None,
    aprobado_jefe_por: int | None,
):
    try:
        solicitante_email = lookup_email_by_user_id(usuario_solicitante_id)
        compras_email = find_compras_email(usuario_compras_id, usuario_compras_nombre)
        jefe_email = lookup_email_by_user_id(aprobado_jefe_por)
        savera_mail = savera_email()
        gerente_fin_mail = gerente_financiero_email()
        link = link_contrato(contrato_id)

        subj_gf = f"[SILI] Pendiente aprobación FINAL GF: Contrato {pedido} con garantía aprobada"
        body_gf = (
            "Estimado Gerente Financiero,\n\n"
            "El contrato y su garantía ya fueron aprobados en instancias previas.\n"
            "Se encuentra PENDIENTE su APROBACIÓN FINAL por parte de Gerencia Financiera.\n\n"
            f"Pedido: {pedido}\nProveedor: {proveedor}\nObjeto: {objeto}\n"
            f"Ver contrato: {link}\n\n"
            "— SILI"
        )
        subj_info = f"[SILI] Contrato aprobado (falta GF): Pedido {pedido}"
        body_info = (
            "Notificación:\n\n"
            "El contrato quedó aprobado y existe garantía aprobada.\n"
            "Resta la aprobación FINAL por parte de Gerencia Financiera.\n\n"
            f"Pedido: {pedido}\nProveedor: {proveedor}\nObjeto: {objeto}\n"
            f"Detalle: {link}\n\n"
            "— SILI"
        )

        if gerente_fin_mail:
            send_mail(gerente_fin_mail, subj_gf, body_gf)
        if savera_mail:
            send_mail(savera_mail, subj_info, body_info)
        if compras_email:
            send_mail(compras_email, subj_info, body_info)
        if solicitante_email:
            send_mail(solicitante_email, subj_info, body_info)
        if jefe_email:
            send_mail(jefe_email, subj_info, body_info)
    except Exception as _e:
        try:
            current_app.logger.warning("Fallo aviso GF en contrato %s: %s", contrato_id, _e)
        except Exception:
            pass


def notify_garantia_por_vencer_15_dias(
    garantia_id: int,
    contrato_id: int,
    pedido: str,
    proveedor: str,
    objeto: str,
    garantia_tipo: str,
    fecha_vencimiento: str | None,
    dias_para_vencer: int | None,
    usuario_solicitante_id: int | None,
    usuario_compras_id: int | None,
    usuario_compras_nombre: str | None,
    aprobado_jefe_por: int | None,
):
    try:
        solicitante_email = lookup_email_by_user_id(usuario_solicitante_id)
        compras_email = find_compras_email(usuario_compras_id, usuario_compras_nombre)
        jefe_email = lookup_email_by_user_id(aprobado_jefe_por)
        savera_mail = savera_email()

        solicitante_nombre = repository.fetch_usuario_nombre_por_id(usuario_solicitante_id) or "Estimado/a"
        compras_nombre = repository.fetch_usuario_nombre_por_id(usuario_compras_id) or "Estimado/a"
        jefe_nombre = repository.fetch_usuario_nombre_por_id(aprobado_jefe_por) or "Estimado/a"

        link = link_garantia(garantia_id)

        subject = f"[SILI] Garantía por vencer en {dias_para_vencer or 15} días: Pedido {pedido}"

        body_plain = (
            "Estimado/a,\n\n"
            "Se informa que la garantía asociada al siguiente contrato está próxima a vencer.\n\n"
            f"Pedido: {pedido}\n"
            f"Proveedor: {proveedor}\n"
            f"Objeto: {objeto}\n"
            f"Tipo de garantía: {garantia_tipo}\n"
            f"Fecha de vencimiento: {fecha_vencimiento}\n"
            f"Días para vencer: {dias_para_vencer or 15}\n\n"
            "Por favor, revisar si corresponde gestionar la renovación, liberación o actualización del estado de la garantía.\n\n"
            f"Ver garantía: {link}\n\n"
            "— SILI"
        )

        enviados = set()

        def _send_unique(email: str, nombre: str):
            email = (email or "").strip()
            if not email:
                return

            email_key = email.lower()
            if email_key in enviados:
                return

            body_html = _build_garantia_vencimiento_html(
                pedido=pedido,
                proveedor=proveedor,
                objeto=objeto,
                garantia_tipo=garantia_tipo,
                fecha_vencimiento=fecha_vencimiento,
                dias_para_vencer=dias_para_vencer,
                link=link,
                nombre_destinatario=nombre or "Estimado/a",
            )

            send_mail(email, subject, body_plain, body_html)
            enviados.add(email_key)

        _send_unique(savera_mail, "Savera")
        _send_unique(compras_email, compras_nombre)
        _send_unique(solicitante_email, solicitante_nombre)
        _send_unique(jefe_email, jefe_nombre)

    except Exception as _e:
        try:
            current_app.logger.warning(
                "Fallo aviso garantía por vencer %s: %s",
                garantia_id,
                _e,
            )
        except Exception:
            pass


def _safe_html(value) -> str:
    return escape("" if value is None else str(value))


def _build_garantia_vencimiento_html(
    pedido: str,
    proveedor: str,
    objeto: str,
    garantia_tipo: str,
    fecha_vencimiento: str | None,
    dias_para_vencer: int | None,
    link: str,
    nombre_destinatario: str = "Estimado/a",
):
    pedido = _safe_html(pedido)
    proveedor = _safe_html(proveedor)
    objeto = _safe_html(objeto)
    garantia_tipo = _safe_html(garantia_tipo)
    fecha_vencimiento = _safe_html(fecha_vencimiento or "")
    dias_para_vencer = _safe_html(dias_para_vencer or 15)
    link = _safe_html(link)
    nombre_destinatario = _safe_html(nombre_destinatario or "Estimado/a")

    return f"""
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>Garantía próxima a vencer</title>
</head>

<body style="margin:0; padding:0; background:#f4f5f7; font-family:Arial, Helvetica, sans-serif; color:#2f2f2f;">

  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f4f5f7; padding:32px 0;">
    <tr>
      <td align="center">

        <table width="720" cellpadding="0" cellspacing="0" border="0"
               style="width:720px; max-width:720px; background:#ffffff; border-radius:10px; overflow:hidden; border:1px solid #e5e7eb; box-shadow:0 4px 12px rgba(0,0,0,0.05);">

          <!-- ENCABEZADO -->
          <tr>
            <td style="background:#f28c28; padding:22px 26px 18px 26px;">
              <div style="font-size:12px; color:#fff4e8; letter-spacing:1.2px; text-transform:uppercase; font-weight:700; margin-bottom:8px;">
                GESTIÓN DE GARANTÍAS
              </div>

              <div style="font-size:24px; line-height:1.25; color:#ffffff; font-weight:800; margin-bottom:8px;">
                Garantía próxima a vencer
              </div>

              <div style="font-size:14px; color:#fff8f0;">
                Pedido {pedido} — vence en {dias_para_vencer} día(s)
              </div>
            </td>
          </tr>

          <!-- CUERPO -->
          <tr>
            <td style="padding:22px 26px 10px 26px; font-size:14px; line-height:1.6; color:#333333;">
              Hola <strong>{nombre_destinatario}</strong>,
              <br><br>
              Se informa que la garantía asociada al siguiente contrato está próxima a vencer.
              Por favor, revisar si corresponde gestionar la <strong>renovación</strong>,
              <strong>liberación</strong> o actualización del estado de la garantía.
            </td>
          </tr>

          <!-- TABLA DE DETALLE -->
          <tr>
            <td style="padding:8px 26px 20px 26px;">

              <table width="100%" cellpadding="0" cellspacing="0" border="0"
                     style="border-collapse:collapse; width:100%; font-size:14px;">

                <tr>
                  <td style="width:220px; background:#f2f4f8; padding:11px 13px; border-bottom:1px solid #dde3ec; font-weight:700; color:#2f2f2f;">
                    Pedido
                  </td>
                  <td style="padding:11px 13px; border-bottom:1px solid #dde3ec; color:#333333;">
                    {pedido}
                  </td>
                </tr>

                <tr>
                  <td style="background:#f2f4f8; padding:11px 13px; border-bottom:1px solid #dde3ec; font-weight:700; color:#2f2f2f;">
                    Proveedor
                  </td>
                  <td style="padding:11px 13px; border-bottom:1px solid #dde3ec; color:#333333;">
                    {proveedor}
                  </td>
                </tr>

                <tr>
                  <td style="background:#f2f4f8; padding:11px 13px; border-bottom:1px solid #dde3ec; font-weight:700; color:#2f2f2f;">
                    Tipo de garantía
                  </td>
                  <td style="padding:11px 13px; border-bottom:1px solid #dde3ec; color:#333333;">
                    {garantia_tipo}
                  </td>
                </tr>

                <tr>
                  <td style="background:#f2f4f8; padding:11px 13px; border-bottom:1px solid #dde3ec; font-weight:700; color:#2f2f2f;">
                    Fecha de vencimiento
                  </td>
                  <td style="padding:11px 13px; border-bottom:1px solid #dde3ec; color:#333333;">
                    <strong style="color:#d97706;">{fecha_vencimiento}</strong>
                  </td>
                </tr>

                <tr>
                  <td style="background:#f2f4f8; padding:11px 13px; border-bottom:1px solid #dde3ec; font-weight:700; color:#2f2f2f;">
                    Días para vencer
                  </td>
                  <td style="padding:11px 13px; border-bottom:1px solid #dde3ec; color:#333333;">
                    <span style="display:inline-block; background:#fff3e0; color:#b45309; padding:4px 10px; border-radius:999px; font-weight:700;">
                      {dias_para_vencer} día(s)
                    </span>
                  </td>
                </tr>

                <tr>
                  <td style="background:#f2f4f8; padding:11px 13px; border-bottom:1px solid #dde3ec; font-weight:700; color:#2f2f2f; vertical-align:top;">
                    Objeto del contrato
                  </td>
                  <td style="padding:11px 13px; border-bottom:1px solid #dde3ec; color:#333333; line-height:1.5;">
                    {objeto}
                  </td>
                </tr>

              </table>

            </td>
          </tr>

          <!-- BOTÓN -->
          <tr>
            <td align="center" style="padding:0 26px 24px 26px;">
              <a href="{link}"
                 style="display:inline-block; background:#f28c28; color:#ffffff; text-decoration:none; padding:11px 22px; border-radius:7px; font-size:14px; font-weight:700;">
                Ver garantía / contrato
              </a>
            </td>
          </tr>

          <!-- PIE -->
          <tr>
            <td style="padding:14px 26px 20px 26px; font-size:12px; color:#6b7280; border-top:1px solid #edf0f5;">
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