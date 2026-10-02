# modules/reclamos_seguros/routes_reclamos_seguros.py
# -*- coding: utf-8 -*-
"""Fase 1: tabla/CRUD básico del caso + ticket correlativo. Pendiente (fases siguientes,
ver conversación): notificación saliente al broker con el código en el asunto, poller de
correo entrante (reutilizando modules/email_to_task), combinar casos duplicados, y
(v2) semáforo/informe de desempeño."""
import os
import re
import uuid
from datetime import date, datetime

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash,
    session, abort, current_app, send_from_directory, jsonify, get_flashed_messages,
)
from werkzeug.utils import secure_filename

from modules.auth.routes_auth import require_login, require_permission
from . import reclamos_seguros_repository as repo
from . import reclamos_seguros_helpers as rsh
from . import reclamos_seguros_html as rhtml
from .reclamos_seguros_constants import (
    ACTIVE_KEY, PERM_RECLAMOS_SEGUROS, TIPOS_CASO, ESTADO_ABIERTO, ESTADO_CERRADO,
    SUB_ESTADOS_SUGERIDOS, EXTENSIONES_PERMITIDAS, MAX_ADJUNTO_BYTES, MAX_ADJUNTOS_POR_ENVIO,
    MAX_IMAGEN_BYTES, MAX_DESCRIPCION_CHARS,
)

reclamos_seguros_bp = Blueprint("reclamos_seguros", __name__, url_prefix="/reclamos-seguros")


# ── Helpers ──────────────────────────────────────────────────

def _user():
    return {
        "id": session.get("usuario_id"),
        "nombre": session.get("usuario", ""),
        "rol": session.get("rol", "usuario"),
    }


def _es_admin(u) -> bool:
    return u["rol"] == "admin"


def _tiene_visibilidad_total(u) -> bool:
    """Admin, coordinador del módulo, o un rol marcado en Configuración con acceso a todo."""
    if _es_admin(u):
        return True
    if rsh.es_coordinador_reclamos_seguros(u["id"], u["rol"]):
        return True
    return rsh.rol_tiene_visibilidad_total(u["rol"])


def _puede_ver(caso: dict, u) -> bool:
    if _tiene_visibilidad_total(u):
        return True
    if caso["creado_por_id"] == u["id"] or caso["solicitante_id"] == u["id"]:
        return True
    from modules.db import get_db
    cur = get_db().cursor()
    cur.execute("SELECT jefe_id FROM usuarios WHERE id IN (?, ?)",
                (caso["creado_por_id"], caso["solicitante_id"]))
    jefes = {r[0] for r in cur.fetchall() if r[0] is not None}
    return int(u["id"]) in jefes


def _puede_gestionar(caso: dict, u) -> bool:
    """Editar/avanzar/cerrar/eliminar: admin, coordinador, o quien registró el caso."""
    return _tiene_visibilidad_total(u) or caso["creado_por_id"] == u["id"]


def _permiso(u, accion: str) -> bool:
    from modules.security import has_permission
    return _es_admin(u) or has_permission(u["rol"], PERM_RECLAMOS_SEGUROS, accion)


def _carpeta_adjuntos(caso_id: int) -> str:
    base = os.path.join(current_app.root_path, "uploads_privados", "reclamos_seguros", str(caso_id))
    os.makedirs(base, exist_ok=True)
    return base


def _guardar_adjuntos(caso_id: int, seguimiento_id, u):
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
        repo.insert_adjunto(caso_id, seguimiento_id, nombre_original, nombre_guardado,
                             tam, u["id"], u["nombre"])
        guardados.append(nombre_original)
    return guardados, errores


def _parse_fecha(txt: str):
    try:
        return datetime.strptime((txt or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def _to_int(txt):
    try:
        return int(str(txt).strip())
    except (TypeError, ValueError):
        return None


def _es_ajax() -> bool:
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def _mensajes_flash() -> list:
    return [[cat, msg] for cat, msg in get_flashed_messages(with_categories=True)]


def _volver_detalle(caso_id):
    """Tras una accion sobre el caso: en la pagina completa redirige al detalle; en la ventana
    de la lista (AJAX) devuelve JSON con los mensajes y el fragmento actualizado, para no salir
    de la lista."""
    if not _es_ajax():
        return redirect(url_for("reclamos_seguros.reclamos_seguros_detalle", caso_id=caso_id))
    ctx = _contexto_detalle(caso_id, _user())
    mensajes = _mensajes_flash()
    if ctx is None:
        return jsonify(ok=True, cerrado=True, mensajes=mensajes)
    return jsonify(ok=True, mensajes=mensajes,
                   html=render_template("reclamos_seguros/detalle_fragment.html", es_modal=True, **ctx))


def _volver_lista():
    if not _es_ajax():
        return redirect(url_for("reclamos_seguros.reclamos_seguros_lista"))
    return jsonify(ok=True, cerrado=True, mensajes=_mensajes_flash())


def _adjuntos_ctx() -> dict:
    """Parametros de la zona de carga de adjuntos (macro partials/dropzone.html)."""
    exts = sorted(EXTENSIONES_PERMITIDAS)
    max_mb = MAX_ADJUNTO_BYTES // (1024 * 1024)
    return {
        "accept_adjuntos": ",".join(exts),
        "max_mb_adjuntos": max_mb,
        "max_adjuntos": MAX_ADJUNTOS_POR_ENVIO,
        "hint_adjuntos": (f"Hasta {MAX_ADJUNTOS_POR_ENVIO} archivos de {max_mb} MB. "
                          f"Formatos: {', '.join(e.lstrip('.') for e in exts)}."),
    }


def _combos():
    return {
        "usuarios": repo.get_usuarios_combo(),
        "brokers": repo.get_brokers_combo(),
        "sub_estados_sugeridos": SUB_ESTADOS_SUGERIDOS,
    }


def _leer_formulario(form):
    datos = {
        "fecha": _parse_fecha(form.get("fecha")) or date.today(),
        "tipo_caso": (form.get("tipo_caso") or "").strip(),
        "descripcion": rhtml.limpiar_html(form.get("descripcion") or ""),
        "broker_tercero_id": None,
        "solicitante_id": None, "solicitante_nombre": None,
    }
    if datos["tipo_caso"] not in TIPOS_CASO:
        return "Selecciona el tipo de caso.", datos
    if not rhtml.tiene_contenido(datos["descripcion"]):
        return "La descripción es obligatoria.", datos
    if len(datos["descripcion"]) > MAX_DESCRIPCION_CHARS:
        return "La descripción es demasiado extensa.", datos

    sol_id = _to_int(form.get("solicitante_id"))
    nombre = repo.get_usuario_nombre(sol_id) if sol_id else None
    if not sol_id or not nombre:
        return "Selecciona el usuario solicitante.", datos
    datos["solicitante_id"], datos["solicitante_nombre"] = sol_id, nombre

    broker_id = _to_int(form.get("broker_tercero_id"))
    if broker_id:
        brokers = {b["id"]: b for b in repo.get_brokers_combo()}
        if broker_id not in brokers:
            return "El broker/aseguradora seleccionado no es válido.", datos
        datos["broker_tercero_id"] = broker_id
    return None, datos


# ── Lista ────────────────────────────────────────────────────

@reclamos_seguros_bp.route("/", endpoint="reclamos_seguros_lista")
@require_login
@require_permission(PERM_RECLAMOS_SEGUROS, "ver")
def reclamos_seguros_lista():
    u = _user()
    estado = (request.args.get("estado") or ESTADO_ABIERTO).upper()
    if estado not in (ESTADO_ABIERTO, ESTADO_CERRADO, "TODOS"):
        estado = ESTADO_ABIERTO
    tipo_caso = request.args.get("tipo_caso") or ""
    if tipo_caso not in TIPOS_CASO:
        tipo_caso = ""
    casos = repo.get_casos(
        estado=None if estado == "TODOS" else estado,
        tipo_caso=tipo_caso or None,
        visible_para=None if _tiene_visibilidad_total(u) else u["id"],
    )
    return render_template(
        "reclamos_seguros/lista.html", active_page=ACTIVE_KEY, casos=casos,
        estado=estado, tipo_caso=tipo_caso, tipos=TIPOS_CASO,
        tiene_visibilidad_total=_tiene_visibilidad_total(u),
    )


# ── Nuevo ────────────────────────────────────────────────────

@reclamos_seguros_bp.route("/nuevo", methods=["GET", "POST"], endpoint="reclamos_seguros_nuevo")
@require_login
@require_permission(PERM_RECLAMOS_SEGUROS, "crear")
def reclamos_seguros_nuevo():
    u = _user()
    if request.method == "POST":
        error, datos = _leer_formulario(request.form)
        if error:
            flash(error, "warning")
            form = request.form
        else:
            caso_id = repo.crear_caso(datos, u["id"], u["nombre"])
            codigo = repo.siguiente_codigo_caso()
            repo.set_codigo_caso(caso_id, codigo)
            archivos, errores = _guardar_adjuntos(caso_id, None, u)
            for e in errores:
                flash(e, "warning")

            if datos.get("broker_tercero_id"):
                caso = repo.get_caso(caso_id)
                if caso and caso.get("broker_email"):
                    from . import reclamos_seguros_email_service as rses
                    try:
                        enviado, omitidos = rses.notificar_broker_nuevo_caso(
                            caso, caso["broker_email"], caso["broker_nombre"])
                        if not enviado:
                            flash("Caso registrado, pero no se pudo notificar al broker por correo.", "warning")
                        elif omitidos:
                            flash("El broker fue notificado, pero estos documentos no se adjuntaron al correo por su "
                                  "tamaño (hay que enviárselos por separado): " + ", ".join(omitidos) + ".", "warning")
                    except Exception:
                        current_app.logger.exception(
                            "reclamos_seguros: fallo notificando al broker caso_id=%s", caso_id)
                        flash("Caso registrado, pero no se pudo notificar al broker por correo.", "warning")

            flash(f"Caso {codigo} registrado.", "success")
            return _volver_detalle(caso_id)
    else:
        form = {"fecha": date.today().isoformat()}

    return render_template("reclamos_seguros/nuevo.html", active_page=ACTIVE_KEY,
                           tipos=TIPOS_CASO, form=form, **_combos(), **_adjuntos_ctx(),
                           extensiones=", ".join(sorted(e.lstrip(".") for e in EXTENSIONES_PERMITIDAS)))


# ── Detalle ──────────────────────────────────────────────────

def _contexto_detalle(caso_id, u):
    """Datos del detalle de un caso (pagina completa y ventana de la lista). None si no existe
    o el usuario no puede verlo."""
    caso = repo.get_caso(caso_id)
    if not caso or not _puede_ver(caso, u):
        return None
    seguimiento = repo.get_seguimiento(caso_id)
    adjuntos = repo.get_adjuntos(caso_id)
    por_seguimiento = {}
    for a in adjuntos:
        por_seguimiento.setdefault(a["seguimiento_id"], []).append(a)
    gestiona = _puede_gestionar(caso, u)
    return dict(
        active_page=ACTIVE_KEY, caso=caso,
        seguimiento=seguimiento, adj_caso=[a for a in adjuntos if a["seguimiento_id"] is None],
        adj_por_seguimiento=por_seguimiento,
        abierto=caso["estado"] == ESTADO_ABIERTO,
        sub_estados_sugeridos=SUB_ESTADOS_SUGERIDOS,
        puede_avanzar=(caso["estado"] == ESTADO_ABIERTO and gestiona and _permiso(u, "editar")),
        puede_cerrar=(caso["estado"] == ESTADO_ABIERTO and gestiona and _permiso(u, "editar")),
        puede_eliminar=_permiso(u, "eliminar") and (_es_admin(u) if caso["estado"] == ESTADO_CERRADO else gestiona),
        puede_combinar=(caso["estado"] == ESTADO_ABIERTO and gestiona and _permiso(u, "editar")),
        **_adjuntos_ctx(),
    )


@reclamos_seguros_bp.route("/<int:caso_id>", endpoint="reclamos_seguros_detalle")
@require_login
@require_permission(PERM_RECLAMOS_SEGUROS, "ver")
def reclamos_seguros_detalle(caso_id):
    ctx = _contexto_detalle(caso_id, _user())
    if ctx is None:
        abort(404)
    return render_template("reclamos_seguros/detalle.html", **ctx)


@reclamos_seguros_bp.route("/<int:caso_id>/fragment", endpoint="reclamos_seguros_detalle_fragment")
@require_login
@require_permission(PERM_RECLAMOS_SEGUROS, "ver")
def reclamos_seguros_detalle_fragment(caso_id):
    """Contenido del detalle para la ventana (modal) de la lista."""
    ctx = _contexto_detalle(caso_id, _user())
    if ctx is None:
        abort(404)
    return render_template("reclamos_seguros/detalle_fragment.html", es_modal=True, **ctx)


@reclamos_seguros_bp.route("/<int:caso_id>/seguimiento", methods=["POST"], endpoint="reclamos_seguros_seguimiento")
@require_login
@require_permission(PERM_RECLAMOS_SEGUROS, "editar")
def reclamos_seguros_seguimiento(caso_id):
    u = _user()
    caso = repo.get_caso(caso_id)
    if not caso or not _puede_ver(caso, u):
        abort(404)
    if not _puede_gestionar(caso, u) or caso["estado"] != ESTADO_ABIERTO:
        abort(403)
    observacion = rhtml.limpiar_html(request.form.get("observacion") or "")
    sub_estado = (request.form.get("sub_estado") or "").strip()
    if not rhtml.tiene_contenido(observacion) or len(observacion) > MAX_DESCRIPCION_CHARS:
        flash("Escribe la observación del seguimiento.", "warning")
        return _volver_detalle(caso_id)
    seg_id = repo.add_seguimiento(caso_id, observacion, u["id"], u["nombre"])
    if sub_estado:
        repo.actualizar_sub_estado(caso_id, sub_estado)
    archivos, errores = _guardar_adjuntos(caso_id, seg_id, u)
    for e in errores:
        flash(e, "warning")
    flash("Seguimiento registrado.", "success")
    return _volver_detalle(caso_id)


@reclamos_seguros_bp.route("/<int:caso_id>/cerrar", methods=["POST"], endpoint="reclamos_seguros_cerrar")
@require_login
@require_permission(PERM_RECLAMOS_SEGUROS, "editar")
def reclamos_seguros_cerrar(caso_id):
    u = _user()
    caso = repo.get_caso(caso_id)
    if not caso or not _puede_ver(caso, u):
        abort(404)
    if not _puede_gestionar(caso, u):
        abort(403)
    observacion = rhtml.limpiar_html(request.form.get("observacion") or "")
    if not rhtml.tiene_contenido(observacion) or len(observacion) > MAX_DESCRIPCION_CHARS:
        flash("Indica la observación de cierre.", "warning")
        return _volver_detalle(caso_id)
    seg_id = repo.add_seguimiento(caso_id, observacion, u["id"], u["nombre"])
    _, errores = _guardar_adjuntos(caso_id, seg_id, u)
    for e in errores:
        flash(e, "warning")
    if repo.cerrar_caso(caso_id, observacion, u["id"], u["nombre"]):
        flash(f"Caso {caso.get('codigo') or ('#' + str(caso_id))} cerrado.", "success")
    else:
        flash("El caso ya estaba cerrado.", "warning")
    return _volver_detalle(caso_id)


@reclamos_seguros_bp.route("/<int:caso_id>/eliminar", methods=["POST"], endpoint="reclamos_seguros_eliminar")
@require_login
@require_permission(PERM_RECLAMOS_SEGUROS, "eliminar")
def reclamos_seguros_eliminar(caso_id):
    u = _user()
    caso = repo.get_caso(caso_id)
    if not caso or not _puede_ver(caso, u):
        abort(404)
    if caso["estado"] == ESTADO_CERRADO:
        if not _es_admin(u):
            abort(403)
    elif not _puede_gestionar(caso, u):
        abort(403)
    repo.eliminar_caso(caso_id)
    flash(f"Caso {caso.get('codigo') or ('#' + str(caso_id))} eliminado.", "success")
    return _volver_lista()


@reclamos_seguros_bp.route("/<int:caso_id>/combinar", methods=["POST"], endpoint="reclamos_seguros_combinar")
@require_login
@require_permission(PERM_RECLAMOS_SEGUROS, "editar")
def reclamos_seguros_combinar(caso_id):
    u = _user()
    principal = repo.get_caso(caso_id)
    if not principal or not _puede_ver(principal, u):
        abort(404)
    if principal["estado"] != ESTADO_ABIERTO or not _puede_gestionar(principal, u):
        abort(403)

    ref = (request.form.get("caso_secundario") or "").strip()
    secundario = None
    if ref:
        secundario = repo.buscar_caso_por_codigo(ref.upper()) if not ref.isdigit() else repo.get_caso(int(ref))
    if not secundario:
        flash("No se encontró el caso secundario a combinar.", "warning")
        return _volver_detalle(caso_id)
    if secundario["id"] == principal["id"]:
        flash("No puedes combinar un caso consigo mismo.", "warning")
        return _volver_detalle(caso_id)
    if not _puede_ver(secundario, u) or not _puede_gestionar(secundario, u):
        abort(403)
    if secundario["estado"] == ESTADO_CERRADO:
        flash(f"El caso {secundario.get('codigo') or ('#' + str(secundario['id']))} ya está cerrado y no se puede combinar.", "warning")
        return _volver_detalle(caso_id)

    repo.combinar_casos(principal["id"], secundario["id"], u["id"], u["nombre"])
    flash(f"Caso {secundario.get('codigo') or ('#' + str(secundario['id']))} combinado dentro de "
          f"{principal.get('codigo') or ('#' + str(principal['id']))}.", "success")
    return _volver_detalle(caso_id)


_FIRMAS_IMAGEN = (
    (b"\x89PNG\r\n\x1a\n", ".png"), (b"\xff\xd8\xff", ".jpg"),
    (b"GIF87a", ".gif"), (b"GIF89a", ".gif"),
)


def _ext_imagen(cabecera: bytes):
    """Extension segun los primeros bytes reales del archivo (no se confia en el nombre/MIME)."""
    for firma, ext in _FIRMAS_IMAGEN:
        if cabecera.startswith(firma):
            return ext
    if cabecera[:4] == b"RIFF" and cabecera[8:12] == b"WEBP":
        return ".webp"
    return None


@reclamos_seguros_bp.route("/imagen", methods=["POST"], endpoint="reclamos_seguros_imagen_subir")
@require_login
def reclamos_seguros_imagen_subir():
    """Sube una imagen pegada/arrastrada en un editor (descripcion, seguimiento o cierre)."""
    u = _user()
    if not (_permiso(u, "crear") or _permiso(u, "editar")):
        return jsonify(ok=False, msg="No tienes permiso para subir im\u00e1genes."), 403
    f = request.files.get("imagen")
    if not f:
        return jsonify(ok=False, msg="No se recibi\u00f3 ninguna imagen."), 400
    datos = f.read(MAX_IMAGEN_BYTES + 1)
    if not datos:
        return jsonify(ok=False, msg="La imagen est\u00e1 vac\u00eda."), 400
    if len(datos) > MAX_IMAGEN_BYTES:
        return jsonify(ok=False, msg=f"La imagen supera {MAX_IMAGEN_BYTES // (1024 * 1024)} MB."), 400
    ext = _ext_imagen(datos[:16])
    if not ext:
        return jsonify(ok=False, msg="El archivo no es una imagen v\u00e1lida (PNG, JPG, GIF o WEBP)."), 400
    nombre = f"{uuid.uuid4().hex}{ext}"
    with open(os.path.join(rhtml.carpeta_imagenes(), nombre), "wb") as out:
        out.write(datos)
    return jsonify(ok=True, url=url_for("reclamos_seguros.reclamos_seguros_imagen", nombre=nombre))


@reclamos_seguros_bp.route("/imagen/<nombre>", endpoint="reclamos_seguros_imagen")
@require_login
@require_permission(PERM_RECLAMOS_SEGUROS, "ver")
def reclamos_seguros_imagen(nombre):
    # Nombre = uuid4 imposible de adivinar; ademas exige sesion y permiso de lectura del modulo.
    if not re.fullmatch(r"[0-9a-f]{32}\.(?:png|jpg|jpeg|gif|webp)", nombre):
        abort(404)
    return send_from_directory(rhtml.carpeta_imagenes(), nombre)


@reclamos_seguros_bp.route("/adjunto/<int:adjunto_id>", endpoint="reclamos_seguros_adjunto")
@require_login
@require_permission(PERM_RECLAMOS_SEGUROS, "ver")
def reclamos_seguros_adjunto(adjunto_id):
    u = _user()
    from modules.db import get_db
    cur = get_db().cursor()
    cur.execute("SELECT * FROM reclamos_seguros_adjuntos WHERE id = ? AND activo = 1", (adjunto_id,))
    row = cur.fetchone()
    if not row:
        abort(404)
    adj = dict(row)
    caso = repo.get_caso(adj["caso_id"])
    if not caso or not _puede_ver(caso, u):
        abort(404)
    return send_from_directory(_carpeta_adjuntos(adj["caso_id"]), adj["nombre_guardado"],
                               as_attachment=True, download_name=adj["nombre_original"])


# ── Configuración del módulo ───────────────────────────────────

@reclamos_seguros_bp.route("/configuracion", methods=["GET"], endpoint="reclamos_seguros_configuracion")
@require_login
def reclamos_seguros_configuracion():
    u = _user()
    if not _es_admin(u):
        abort(403)
    return render_template(
        "reclamos_seguros/configuracion.html", active_page=ACTIVE_KEY,
        coordinador=rsh.get_coordinador_reclamos_seguros(),
        roles_visibilidad_total=rsh.get_roles_visibilidad_total(),
        cuenta_correo=rsh.get_cuenta_correo_reclamos_seguros(),
        usuarios=repo.get_usuarios_combo(),
    )


@reclamos_seguros_bp.route("/configuracion/coordinador", methods=["POST"],
                           endpoint="reclamos_seguros_configuracion_coordinador")
@require_login
def reclamos_seguros_configuracion_coordinador():
    u = _user()
    if not _es_admin(u):
        abort(403)
    uid = _to_int(request.form.get("usuario_id"))
    if not uid:
        rsh.quitar_coordinador_reclamos_seguros()
        flash("Se quitó el coordinador del módulo.", "warning")
        return redirect(url_for("reclamos_seguros.reclamos_seguros_configuracion"))
    nombre = next((x["nombre"] for x in repo.get_usuarios_combo() if x["id"] == uid), None)
    if not nombre:
        flash("Usuario inválido.", "danger")
        return redirect(url_for("reclamos_seguros.reclamos_seguros_configuracion"))
    rsh.set_coordinador_reclamos_seguros(uid, nombre)
    flash(f"Coordinador del módulo asignado: {nombre}.", "success")
    return redirect(url_for("reclamos_seguros.reclamos_seguros_configuracion"))


@reclamos_seguros_bp.route("/configuracion/roles", methods=["POST"],
                           endpoint="reclamos_seguros_configuracion_roles")
@require_login
def reclamos_seguros_configuracion_roles():
    u = _user()
    if not _es_admin(u):
        abort(403)
    roles = [r.strip() for r in (request.form.get("roles") or "").split(",") if r.strip()]
    rsh.set_roles_visibilidad_total(roles)
    flash("Roles con visibilidad total actualizados.", "success")
    return redirect(url_for("reclamos_seguros.reclamos_seguros_configuracion"))


@reclamos_seguros_bp.route("/configuracion/correo", methods=["POST"],
                           endpoint="reclamos_seguros_configuracion_correo")
@require_login
def reclamos_seguros_configuracion_correo():
    u = _user()
    if not _es_admin(u):
        abort(403)
    email = (request.form.get("cuenta_correo") or "").strip()
    rsh.set_cuenta_correo_reclamos_seguros(email)
    flash("Cuenta de correo del módulo actualizada.", "success")
    return redirect(url_for("reclamos_seguros.reclamos_seguros_configuracion"))


def register_reclamos_seguros_routes(app):
    app.add_template_filter(rhtml.visible, "rs_descripcion")
    app.register_blueprint(reclamos_seguros_bp)
