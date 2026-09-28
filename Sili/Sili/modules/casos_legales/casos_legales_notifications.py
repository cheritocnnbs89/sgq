# modules/casos_legales/casos_legales_notifications.py
# -*- coding: utf-8 -*-
"""
Notificaciones de Casos Legales (creación, avance y cierre).
Mismo formato que Planificador/Tareas: aviso in-app (notify_inapp) + correo HTML SGQ,
con los adjuntos del evento cuando pesan poco.
"""
from __future__ import annotations

import html as _html
import os

from flask import current_app, url_for

from modules.planificador.planificador_notifications import _email, _email_html
from . import casos_legales_repository as repo
from .casos_legales_constants import MAX_BYTES_EMAIL, TIPOS_CASO


def _esc(v) -> str:
    return _html.escape(str(v)) if v not in (None, "") else "—"


def _destinatarios(caso: dict, actor_id: int) -> list[dict]:
    """Usuario solicitante (elegido en el formulario) + quien registró el caso, sin el que
    ejecuta la acción (para no notificarse a sí mismo)."""
    vistos, lista = set(), []
    candidatos = [
        repo.get_usuario_contacto(caso.get("requirente_id")),
        repo.get_usuario_contacto(caso.get("creado_por_id")),
    ]
    for u in candidatos:
        if not u:
            continue
        if u["id"] in vistos or u["id"] == actor_id:
            continue
        vistos.add(u["id"])
        lista.append(u)
    return lista


def _adjuntos_email(archivos: list[tuple[str, str]] | None):
    """[(ruta, nombre)] que caben en el correo; el resto solo se ve en el sistema."""
    if not archivos:
        return None
    total, ok = 0, []
    for ruta, nombre in archivos:
        try:
            tam = os.path.getsize(ruta)
        except OSError:
            continue
        if total + tam > MAX_BYTES_EMAIL:
            continue
        total += tam
        ok.append((ruta, nombre))
    return ok or None


def _enviar(caso: dict, actor_id: int, asunto: str, categoria: str,
            titulo: str, saludo: str, filas: list[tuple], aviso_inapp: str,
            archivos: list[tuple[str, str]] | None) -> int:
    destinatarios = _destinatarios(caso, actor_id)
    if not destinatarios:
        return 0
    try:
        link = url_for("casos_legales.casos_detalle", caso_id=caso["id"], _external=True)
    except Exception:
        link = None
    html = _email_html(categoria, titulo, saludo, filas,
                       nota="Ingresa al SGQ → Casos Legales para ver el detalle.",
                       boton=("Ver caso", link) if link else None)
    for u in destinatarios:
        try:
            repo.insert_notify_inapp(u["id"], asunto, aviso_inapp)
        except Exception as exc:
            current_app.logger.warning("Casos legales inapp error uid=%s: %s", u["id"], exc)
    _email([u["email"] for u in destinatarios if u.get("email")], asunto, html,
           attachments=_adjuntos_email(archivos))
    return len(destinatarios)


def _fmt_horas(v) -> str:
    return f"{float(v):g} h" if v not in (None, "") else "—"


def _filas_base(caso: dict) -> list[tuple]:
    return [
        ("N° de caso", f"#{caso['id']}"),
        ("Tipo de caso", _esc(TIPOS_CASO.get(caso["tipo"], {}).get("label", caso["tipo"]))),
        ("Tipo de tarea", _esc(caso["tipo_tarea"])),
        ("Cliente" if caso.get("tercero_tipo") == "C" else "Proveedor" if caso.get("tercero_tipo") == "P"
         else "Cliente/Proveedor", _esc(caso.get("cliente_proveedor"))),
        ("Usuario solicitante", _esc(caso.get("requirente"))),
    ]


def notif_caso_creado(caso: dict, usuario_id: int, usuario_nombre: str, archivos=None) -> int:
    filas = _filas_base(caso) + [
        ("Fecha", _esc(caso["fecha"])),
        ("Tiempo asignado", _fmt_horas(caso.get("tiempo_asignado"))),
        ("Registrado por", _esc(usuario_nombre)),
        ("Descripción", _esc(caso["descripcion"])),
    ]
    return _enviar(
        caso, usuario_id,
        f"[Casos Legales] Nuevo caso #{caso['id']} — {caso['tipo_tarea']}",
        "CASOS LEGALES", f"Caso #{caso['id']} registrado",
        f"<strong>{_esc(usuario_nombre)}</strong> registró un nuevo caso.",
        filas, f"Nuevo caso #{caso['id']} ({caso['tipo_tarea']}) registrado por {usuario_nombre}.",
        archivos,
    )


def notif_caso_avance(caso: dict, usuario_id: int, usuario_nombre: str,
                      observacion: str, archivos=None) -> int:
    filas = _filas_base(caso) + [
        ("Avance de", _esc(usuario_nombre)),
        ("Observación", _esc(observacion)),
    ]
    return _enviar(
        caso, usuario_id,
        f"[Casos Legales] Avance en el caso #{caso['id']}",
        "CASOS LEGALES", f"Nuevo avance en el caso #{caso['id']}",
        f"<strong>{_esc(usuario_nombre)}</strong> registró un avance.",
        filas, f"Nuevo avance en el caso #{caso['id']} ({caso['tipo_tarea']}).",
        archivos,
    )


def notif_caso_cerrado(caso: dict, usuario_id: int, usuario_nombre: str,
                       observacion: str, archivos=None) -> int:
    filas = _filas_base(caso) + [
        ("Cerrado por", _esc(usuario_nombre)),
        ("Observación de cierre", _esc(observacion)),
    ]
    return _enviar(
        caso, usuario_id,
        f"[Casos Legales] Caso #{caso['id']} cerrado",
        "CASOS LEGALES", f"Caso #{caso['id']} cerrado",
        f"<strong>{_esc(usuario_nombre)}</strong> cerró el caso.",
        filas, f"El caso #{caso['id']} ({caso['tipo_tarea']}) fue cerrado.",
        archivos,
    )
