# -*- coding: utf-8 -*-

from modules.email_utils import send_email_async

from .obligaciones_constants import ESTATUS_LABELS


TIPO_ALERTA_LABELS = {
    "inicio_mes": "inicio de mes",
    "45d": "45 días antes del vencimiento",
    "30d": "30 días antes del vencimiento",
    "15d": "15 días antes del vencimiento",
    "7d": "7 días antes del vencimiento",
}


def build_email_alerta(obligacion, tipo_alerta):
    """Arma asunto + mensaje de la alerta de una obligacion proxima a vencer / vencida.
    `obligacion` es un dict con al menos: id, descripcion, empresa_nombre, tipo_nombre,
    entidad_nombre, fecha_vencimiento, frecuencia_nombre, estatus, usuario_nombre.
    """
    etiqueta_alerta = TIPO_ALERTA_LABELS.get(tipo_alerta, tipo_alerta)
    estatus_label = ESTATUS_LABELS.get(obligacion.get("estatus"), obligacion.get("estatus"))
    frecuencia_label = obligacion.get("frecuencia_nombre")

    subject = f"[Obligaciones] Alerta ({etiqueta_alerta}) -- {obligacion.get('descripcion', '')}"

    message = "\n".join([
        "Alerta automática del módulo Obligaciones con Stakeholder.",  # 2026-08-14: rename visual pedido en reunión
        "",
        f"ID obligación:      {obligacion.get('id')}",
        f"Descripción:        {obligacion.get('descripcion')}",
        f"Empresa:             {obligacion.get('empresa_nombre', '')}",
        f"Tipo:                {obligacion.get('tipo_nombre', '')}",
        f"Entidad reguladora:  {obligacion.get('entidad_nombre', '')}",
        f"Fecha vencimiento:   {obligacion.get('fecha_vencimiento')}",
        f"Frecuencia:          {frecuencia_label}",
        f"Estatus actual:       {estatus_label}",
        f"Responsable:         {obligacion.get('usuario_nombre', '')}",
        "",
        f"Motivo de esta alerta: {etiqueta_alerta}.",
        "",
        "-- Este correo es automático, generado por el Sistema de Gestión Quimpac (SGQ). "
        "Por favor no responda a este mensaje.",
    ])

    return subject, message


def enviar_alerta(destinatarios, obligacion, tipo_alerta):
    destinatarios = [d for d in (destinatarios or []) if d]
    if not destinatarios:
        return
    subject, message = build_email_alerta(obligacion, tipo_alerta)
    send_email_async(destinatarios, subject, message)
