# modules/casos_legales/routes_casos_legales.py
# -*- coding: utf-8 -*-
import os
import uuid
from datetime import date, datetime

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash,
    session, abort, current_app, send_from_directory,
)
from werkzeug.utils import secure_filename

from modules.auth.routes_auth import require_login, require_permission
from modules.security import has_permission
from . import casos_legales_repository as repo
from . import casos_legales_notifications as notif
from .casos_legales_constants import (
    ACTIVE_KEY, PERM_CASOS, TIPOS_CASO, ESTADO_ABIERTO, ESTADO_CERRADO,
    EXTENSIONES_PERMITIDAS, MAX_ADJUNTO_BYTES, MAX_ADJUNTOS_POR_ENVIO,
    ETAPA_REGISTRO, ETAPA_AVANCE, ETAPA_CIERRE,
)

casos_legales_bp = Blueprint("casos_legales", __name__, url_prefix="/casos-legales")


# ── Helpers ──────────────────────────────────────────────────

def _user():
    return {
        "id": session.get("usuario_id"),
        "nombre": session.get("usuario", ""),
        "rol": session.get("rol", "usuario"),
    }


def _es_admin(u) -> bool:
    return u["rol"] == "admin"


def _puede_ver(caso: dict, u) -> bool:
    """Admin, quien registró el caso o su jefe directo."""
    if _es_admin(u) or caso["creado_por_id"] == u["id"]:
        return True
    return repo.get_jefe_id(caso["creado_por_id"]) == u["id"]


def _puede_gestionar(caso: dict, u) -> bool:
    """Editar / avances / cierre / eliminar: admin o quien registró el caso (el jefe solo ve)."""
    return _es_admin(u) or caso["creado_por_id"] == u["id"]


def _permiso(u, accion: str) -> bool:
    return _es_admin(u) or has_permission(u["rol"], PERM_CASOS, accion)


def _carpeta_adjuntos(caso_id: int) -> str:
    # Fuera de /static: los documentos legales solo se descargan autenticados.
    base = os.path.join(current_app.root_path, "uploads_privados", "casos_legales", str(caso_id))
    os.makedirs(base, exist_ok=True)
    return base


def _guardar_adjuntos(caso_id: int, avance_id, etapa: str, u):
    """Guarda los archivos del campo 'adjuntos'. Devuelve ([(ruta, nombre)], [mensajes de error])."""
    guardados, errores = [], []
    archivos = [f for f in request.files.getlist("adjuntos") if f and f.filename]
    if len(archivos) > MAX_ADJUNTOS_POR_ENVIO:
        errores.append(f"Máximo {MAX_ADJUNTOS_POR_ENVIO} archivos por envío; se ignoraron los demás.")
        archivos = archivos[:MAX_ADJUNTOS_POR_ENVIO]
    for f in archivos:
        nombre_original = secure_filename(f.filename) or "archivo"
        ext = os.path.splitext(nombre_original)[1].lower()
        if ext not in EXTENSIONES_PERMITIDAS:
            errores.append(f"'{nombre_original}': tipo de archivo no permitido.")
            continue
        f.seek(0, 2)
        tam = f.tell()
        f.seek(0)
        if tam <= 0 or tam > MAX_ADJUNTO_BYTES:
            errores.append(f"'{nombre_original}': supera {MAX_ADJUNTO_BYTES // (1024 * 1024)} MB o está vacío.")
            continue
        nombre_guardado = f"{uuid.uuid4().hex}{ext}"
        ruta = os.path.join(_carpeta_adjuntos(caso_id), nombre_guardado)
        f.save(ruta)
        repo.insert_adjunto(caso_id, avance_id, etapa, nombre_original, nombre_guardado,
                            tam, u["id"], u["nombre"])
        guardados.append((ruta, nombre_original))
    return guardados, errores


def _parse_fecha(txt: str):
    try:
        return datetime.strptime((txt or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


# ── Lista ────────────────────────────────────────────────────

@casos_legales_bp.route("/", endpoint="casos_lista")
@require_login
@require_permission(PERM_CASOS, "ver")
def casos_lista():
    u = _user()
    estado = (request.args.get("estado") or ESTADO_ABIERTO).upper()
    if estado not in (ESTADO_ABIERTO, ESTADO_CERRADO, "TODOS"):
        estado = ESTADO_ABIERTO
    tipo = (request.args.get("tipo") or "").upper()
    if tipo not in TIPOS_CASO:
        tipo = ""
    casos = repo.get_casos(
        estado=None if estado == "TODOS" else estado,
        tipo=tipo or None,
        visible_para=None if _es_admin(u) else u["id"],
    )
    return render_template(
        "casos_legales/lista.html", active_page=ACTIVE_KEY, casos=casos,
        estado=estado, tipo=tipo, tipos=TIPOS_CASO, es_admin=_es_admin(u),
        hoy=date.today(),
    )


# ── Nuevo ────────────────────────────────────────────────────

@casos_legales_bp.route("/nuevo", methods=["GET", "POST"], endpoint="casos_nuevo")
@require_login
@require_permission(PERM_CASOS, "crear")
def casos_nuevo():
    u = _user()
    form = request.form if request.method == "POST" else {}
    if request.method == "POST":
        tipo = (form.get("tipo") or "").upper()
        tipo_tramite = (form.get("tipo_tramite") or "").strip()
        estudio = (form.get("estudio_juridico") or "").strip()
        observacion = (form.get("observacion") or "").strip()
        f_tramite = _parse_fecha(form.get("fecha_tramite"))
        f_fin_txt = (form.get("fecha_fin_tentativa") or "").strip()
        f_fin = _parse_fecha(f_fin_txt)

        error = None
        if tipo not in TIPOS_CASO:
            error = "Selecciona el tipo de caso."
        elif not tipo_tramite:
            error = "Indica el tipo de trámite/caso."
        elif not observacion:
            error = "La observación es obligatoria."
        elif not f_tramite:
            error = "Indica la fecha de trámite."
        elif f_fin_txt and not f_fin:
            error = "La fecha fin (tentativa) no es válida."
        elif f_fin and f_fin < f_tramite:
            error = "La fecha fin (tentativa) no puede ser anterior a la fecha de trámite."

        if error:
            flash(error, "warning")
        else:
            caso_id = repo.crear_caso(tipo, tipo_tramite, estudio, observacion,
                                      f_tramite.isoformat(), f_fin.isoformat() if f_fin else None,
                                      u["id"], u["nombre"])
            archivos, errores = _guardar_adjuntos(caso_id, None, ETAPA_REGISTRO, u)
            for e in errores:
                flash(e, "warning")
            try:
                caso = repo.get_caso(caso_id)
                n = notif.notif_caso_creado(caso, u["id"], u["nombre"], archivos)
                if not n:
                    flash("Tu usuario no tiene jefe directo configurado: nadie fue notificado.", "warning")
            except Exception:
                current_app.logger.exception("Casos legales: fallo al notificar caso %s", caso_id)
            flash(f"Caso #{caso_id} registrado.", "success")
            return redirect(url_for("casos_legales.casos_detalle", caso_id=caso_id))

    return render_template("casos_legales/nuevo.html", active_page=ACTIVE_KEY,
                           tipos=TIPOS_CASO, form=form, caso=None,
                           extensiones=", ".join(sorted(e.lstrip(".") for e in EXTENSIONES_PERMITIDAS)))


# ── Detalle ──────────────────────────────────────────────────

@casos_legales_bp.route("/<int:caso_id>", endpoint="casos_detalle")
@require_login
@require_permission(PERM_CASOS, "ver")
def casos_detalle(caso_id):
    u = _user()
    caso = repo.get_caso(caso_id)
    if not caso or not _puede_ver(caso, u):
        abort(404)
    avances = repo.get_avances(caso_id)
    adjuntos = repo.get_adjuntos(caso_id)
    por_avance = {}
    for a in adjuntos:
        por_avance.setdefault(a["avance_id"], []).append(a)
    return render_template(
        "casos_legales/detalle.html", active_page=ACTIVE_KEY, caso=caso,
        tipo_info=TIPOS_CASO.get(caso["tipo"], {"label": caso["tipo"], "icon": "bi-folder"}),
        avances=avances,
        adj_registro=[a for a in adjuntos if a["etapa"] == ETAPA_REGISTRO],
        adj_cierre=[a for a in adjuntos if a["etapa"] == ETAPA_CIERRE],
        adj_por_avance=por_avance,
        abierto=caso["estado"] == ESTADO_ABIERTO,
        puede_avanzar=(caso["estado"] == ESTADO_ABIERTO and _puede_gestionar(caso, u)
                       and _permiso(u, "editar")),
        puede_editar=(caso["estado"] == ESTADO_ABIERTO and _puede_gestionar(caso, u)
                      and _permiso(u, "editar")),
        puede_eliminar=_puede_gestionar(caso, u) and _permiso(u, "eliminar"),
    )


# ── Avance / Cierre ──────────────────────────────────────────

@casos_legales_bp.route("/<int:caso_id>/avance", methods=["POST"], endpoint="casos_avance")
@require_login
@require_permission(PERM_CASOS, "editar")
def casos_avance(caso_id):
    u = _user()
    caso = repo.get_caso(caso_id)
    if not caso or not _puede_ver(caso, u):
        abort(404)
    if not _puede_gestionar(caso, u):
        abort(403)
    if caso["estado"] != ESTADO_ABIERTO:
        flash("El caso ya está cerrado.", "warning")
        return redirect(url_for("casos_legales.casos_detalle", caso_id=caso_id))
    observacion = (request.form.get("observacion") or "").strip()
    if not observacion:
        flash("Escribe la observación del avance.", "warning")
        return redirect(url_for("casos_legales.casos_detalle", caso_id=caso_id))
    avance_id = repo.add_avance(caso_id, observacion, u["id"], u["nombre"])
    archivos, errores = _guardar_adjuntos(caso_id, avance_id, ETAPA_AVANCE, u)
    for e in errores:
        flash(e, "warning")
    try:
        notif.notif_caso_avance(caso, u["id"], u["nombre"], observacion, archivos)
    except Exception:
        current_app.logger.exception("Casos legales: fallo al notificar avance del caso %s", caso_id)
    flash("Avance registrado.", "success")
    return redirect(url_for("casos_legales.casos_detalle", caso_id=caso_id))


@casos_legales_bp.route("/<int:caso_id>/cerrar", methods=["POST"], endpoint="casos_cerrar")
@require_login
@require_permission(PERM_CASOS, "editar")
def casos_cerrar(caso_id):
    u = _user()
    caso = repo.get_caso(caso_id)
    if not caso or not _puede_ver(caso, u):
        abort(404)
    if not _puede_gestionar(caso, u):
        abort(403)
    observacion = (request.form.get("observacion") or "").strip()
    if not repo.cerrar_caso(caso_id, observacion, u["id"], u["nombre"]):
        flash("El caso ya estaba cerrado.", "warning")
        return redirect(url_for("casos_legales.casos_detalle", caso_id=caso_id))
    archivos, errores = _guardar_adjuntos(caso_id, None, ETAPA_CIERRE, u)
    for e in errores:
        flash(e, "warning")
    try:
        notif.notif_caso_cerrado(caso, u["id"], u["nombre"], observacion, archivos)
    except Exception:
        current_app.logger.exception("Casos legales: fallo al notificar cierre del caso %s", caso_id)
    flash(f"Caso #{caso_id} cerrado.", "success")
    return redirect(url_for("casos_legales.casos_detalle", caso_id=caso_id))


# ── Editar / Eliminar ────────────────────────────────────────

@casos_legales_bp.route("/<int:caso_id>/editar", methods=["GET", "POST"], endpoint="casos_editar")
@require_login
@require_permission(PERM_CASOS, "editar")
def casos_editar(caso_id):
    u = _user()
    caso = repo.get_caso(caso_id)
    if not caso or not _puede_ver(caso, u):
        abort(404)
    if not _puede_gestionar(caso, u):
        abort(403)
    if caso["estado"] != ESTADO_ABIERTO:
        flash("Un caso cerrado no se puede editar.", "warning")
        return redirect(url_for("casos_legales.casos_detalle", caso_id=caso_id))

    if request.method == "POST":
        form = request.form
        tipo_tramite = (form.get("tipo_tramite") or "").strip()
        estudio = (form.get("estudio_juridico") or "").strip()
        observacion = (form.get("observacion") or "").strip()
        f_tramite = _parse_fecha(form.get("fecha_tramite"))
        f_fin_txt = (form.get("fecha_fin_tentativa") or "").strip()
        f_fin = _parse_fecha(f_fin_txt)
        error = None
        if not tipo_tramite:
            error = "Indica el tipo de trámite/caso."
        elif not observacion:
            error = "La observación es obligatoria."
        elif not f_tramite:
            error = "Indica la fecha de trámite."
        elif f_fin_txt and not f_fin:
            error = "La fecha fin (tentativa) no es válida."
        elif f_fin and f_fin < f_tramite:
            error = "La fecha fin (tentativa) no puede ser anterior a la fecha de trámite."
        if error:
            flash(error, "warning")
        else:
            repo.actualizar_caso(caso_id, tipo_tramite, estudio, observacion,
                                 f_tramite.isoformat(), f_fin.isoformat() if f_fin else None)
            flash("Caso actualizado.", "success")
            return redirect(url_for("casos_legales.casos_detalle", caso_id=caso_id))
        valores = form
    else:
        valores = {
            "tipo_tramite": caso["tipo_tramite"] or "",
            "estudio_juridico": caso["estudio_juridico"] or "",
            "observacion": caso["observacion"] or "",
            "fecha_tramite": str(caso["fecha_tramite"] or ""),
            "fecha_fin_tentativa": str(caso["fecha_fin_tentativa"] or ""),
        }
    return render_template("casos_legales/nuevo.html", active_page=ACTIVE_KEY, tipos=TIPOS_CASO,
                           form=valores, caso=caso, extensiones="")


@casos_legales_bp.route("/<int:caso_id>/eliminar", methods=["POST"], endpoint="casos_eliminar")
@require_login
@require_permission(PERM_CASOS, "eliminar")
def casos_eliminar(caso_id):
    u = _user()
    caso = repo.get_caso(caso_id)
    if not caso or not _puede_ver(caso, u):
        abort(404)
    if not _puede_gestionar(caso, u):
        abort(403)
    repo.eliminar_caso(caso_id)
    flash(f"Caso #{caso_id} eliminado.", "success")
    return redirect(url_for("casos_legales.casos_lista"))


# ── Descarga de adjuntos (autenticada) ───────────────────────

@casos_legales_bp.route("/adjunto/<int:adjunto_id>", endpoint="casos_adjunto")
@require_login
@require_permission(PERM_CASOS, "ver")
def casos_adjunto(adjunto_id):
    u = _user()
    adj = repo.get_adjunto(adjunto_id)
    if not adj:
        abort(404)
    caso = repo.get_caso(adj["caso_id"])
    if not caso or not _puede_ver(caso, u):
        abort(404)
    return send_from_directory(_carpeta_adjuntos(adj["caso_id"]), adj["nombre_guardado"],
                               as_attachment=True, download_name=adj["nombre_original"])


def register_casos_legales_routes(app):
    app.register_blueprint(casos_legales_bp)
