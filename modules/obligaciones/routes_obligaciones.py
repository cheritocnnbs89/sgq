# -*- coding: utf-8 -*-
import io

import openpyxl
from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, abort, session, send_file,
)

from modules.auth.routes_auth import require_login, require_permission

from .obligaciones_constants import (
    ACTIVE_KEY,
    PERM_VER,
    PERM_CREAR,
    PERM_EDITAR,
    PERM_CARGA_MASIVA,
    PERM_EXPORTAR,
    PERM_HISTORIAL,
    PERM_DASHBOARD,
    ROLES_ADMIN,
    ROL_JEFE_AREA,
    ESTADO_LABELS,
    HISTORIAL_COLUMNAS,
)
from . import obligaciones_services as service

obligaciones_bp = Blueprint("obligaciones", __name__, url_prefix="/obligaciones")


def register_obligaciones_routes(app):
    # 2026-07-15: importa (y registra) las rutas de Frecuencias en el MISMO
    # blueprint antes de app.register_blueprint -- import diferido acá (no al
    # tope del archivo) para evitar import circular, ya que
    # routes_obligaciones_frecuencias.py importa `obligaciones_bp` de este módulo.
    from . import routes_obligaciones_frecuencias  # noqa: F401 (registra decoradores @obligaciones_bp.route)
    from . import routes_obligaciones_tipos  # noqa: F401 (Correccion #4 -- ruta propia Tipos)
    app.register_blueprint(obligaciones_bp)


# ==================================================================
# Fase 3 -- CRUD principal
# ==================================================================
@obligaciones_bp.route("/", endpoint="lista_obligaciones")
@require_login
@require_permission(PERM_VER, "ver")
def lista_obligaciones():
    filters = service.collect_filters(request.args)
    rows = service.list_obligaciones(session.get("usuario_id"), session.get("rol"), filters)
    combos = service.get_combos()
    rol = session.get("rol")
    if rol in ROLES_ADMIN:
        usuarios = service.get_usuarios_combo()
    elif rol == ROL_JEFE_AREA:
        # Mejora (Correccion #5): jefe_area_obligaciones filtra Consultas por
        # uno de sus subordinados directos -- combo acotado a su propio equipo.
        usuarios = service.get_subordinados_combo(session.get("usuario_id"))
    else:
        usuarios = []

    return render_template(
        "obligaciones/obligaciones_lista.html",
        rows=rows,
        filters=filters,
        combos=combos,
        usuarios=usuarios,
        estado_labels=ESTADO_LABELS,
        active_page=ACTIVE_KEY,
    )


@obligaciones_bp.route("/nueva", methods=["GET", "POST"], endpoint="nueva_obligacion")
@require_login
@require_permission(PERM_CREAR, "ver")
def nueva_obligacion():
    combos = service.get_combos()

    if request.method == "POST":
        result = service.crear_obligacion(request.form, session)
        flash(*result["flash"])

        if result["ok"]:
            return redirect(url_for("obligaciones.lista_obligaciones"))

        return render_template(
            "obligaciones/obligaciones_form.html",
            data=result.get("data", {}),
            combos=combos,
            mode="new",
            active_page=ACTIVE_KEY,
        )

    return render_template(
        "obligaciones/obligaciones_form.html",
        data={},
        combos=combos,
        mode="new",
        active_page=ACTIVE_KEY,
    )


@obligaciones_bp.route("/<int:oblig_id>/editar", methods=["GET", "POST"], endpoint="editar_obligacion")
@require_login
@require_permission(PERM_EDITAR, "ver")
def editar_obligacion(oblig_id):
    row = service.get_item(oblig_id)
    if not row:
        abort(404)
    service.assert_puede_acceder_obligacion(row, session)

    combos = service.get_combos()

    if request.method == "POST":
        result = service.editar_obligacion(oblig_id, request.form, session)
        flash(*result["flash"])

        if result.get("not_found"):
            abort(404)

        if result["ok"]:
            return redirect(url_for("obligaciones.lista_obligaciones"))

        return render_template(
            "obligaciones/obligaciones_form.html",
            data=result.get("data", row),
            combos=combos,
            mode="edit",
            oblig_id=oblig_id,
            active_page=ACTIVE_KEY,
        )

    return render_template(
        "obligaciones/obligaciones_form.html",
        data=row,
        combos=combos,
        mode="edit",
        oblig_id=oblig_id,
        active_page=ACTIVE_KEY,
    )


@obligaciones_bp.route("/<int:oblig_id>/eliminar", methods=["POST"], endpoint="eliminar_obligacion")
@require_login
@require_permission(PERM_EDITAR, "ver")
def eliminar_obligacion(oblig_id):
    row = service.get_item(oblig_id)
    if not row:
        abort(404)
    service.assert_puede_acceder_obligacion(row, session)

    result = service.eliminar_obligacion(oblig_id, session)
    flash(*result["flash"])
    return redirect(url_for("obligaciones.lista_obligaciones"))


# ==================================================================
# Fase 4 -- Cumplir
# ==================================================================
@obligaciones_bp.route("/<int:oblig_id>/cumplir", methods=["GET", "POST"], endpoint="cumplir_obligacion")
@require_login
@require_permission(PERM_VER, "ver")
def cumplir_obligacion(oblig_id):
    row = service.get_item(oblig_id)
    if not row:
        abort(404)
    service.assert_puede_acceder_obligacion(row, session)

    if not service.puede_cumplir(oblig_id, session):
        flash("No tiene permiso para cumplir esta obligación.", "danger")
        return redirect(url_for("obligaciones.lista_obligaciones"))

    if request.method == "POST":
        files = request.files.getlist("evidencias")
        result = service.cumplir_obligacion(oblig_id, request.form, files, session)
        flash(*result["flash"])

        if result["ok"]:
            return redirect(url_for("obligaciones.lista_obligaciones"))

        return render_template(
            "obligaciones/obligaciones_cumplir.html",
            row=row,
            active_page=ACTIVE_KEY,
        )

    return render_template(
        "obligaciones/obligaciones_cumplir.html",
        row=row,
        active_page=ACTIVE_KEY,
    )


@obligaciones_bp.route("/<int:oblig_id>/evidencia/<int:evidencia_id>", methods=["GET"], endpoint="descargar_evidencia")
@require_login
@require_permission(PERM_VER, "ver")
def descargar_evidencia(oblig_id, evidencia_id):
    """2026-07-13 (T8): unico punto de acceso a evidencias -- ya no se sirven
    desde static/. Valida propiedad/visibilidad y loguea en auditoria_seguridad."""
    result = service.descargar_evidencia(oblig_id, evidencia_id, session)
    if not result["ok"]:
        if result["motivo"] == "forbidden":
            flash("No tiene permiso para ver esta evidencia.", "danger")
            return redirect(url_for("obligaciones.lista_obligaciones"))
        abort(404)

    return send_file(result["path"], as_attachment=True, download_name=result["filename"])


# ==================================================================
# Fase 5 -- Historial
# ==================================================================
@obligaciones_bp.route("/historial", methods=["GET"], endpoint="historial_obligaciones")
@require_login
@require_permission(PERM_HISTORIAL, "ver")
def historial_obligaciones():
    filters = service.collect_historial_filters(request.args)
    rows = service.list_historial(session.get("usuario_id"), session.get("rol"), filters)
    combos = service.get_combos()
    usuarios = service.get_usuarios_combo() if session.get("rol") in ROLES_ADMIN else []

    return render_template(
        "obligaciones/obligaciones_historial.html",
        rows=rows,
        filters=filters,
        combos=combos,
        usuarios=usuarios,
        estado_labels=ESTADO_LABELS,
        active_page=ACTIVE_KEY,
    )


# ==================================================================
# Fase 9 -- Exportar Excel (Historial)
# ==================================================================
@obligaciones_bp.route("/historial/exportar", methods=["GET"], endpoint="exportar_historial")
@require_login
@require_permission(PERM_EXPORTAR, "ver")
def exportar_historial():
    filters = service.collect_historial_filters(request.args)
    rows = service.list_historial(session.get("usuario_id"), session.get("rol"), filters)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Historial"
    ws.append(list(HISTORIAL_COLUMNAS))

    for r in rows:
        ws.append([
            r["id"],
            r["empresa_nombre"],
            r["entidad_nombre"],
            r["tipo_nombre"],
            service.sanear_formula(r["descripcion"]),  # 2026-07-13 (T6): anti CSV/formula injection
            r["frecuencia_nombre"],
            r["creado_en"],
            r["fecha_vencimiento"],
            ESTADO_LABELS.get(r["estado"], r["estado"]),
            r["evidencias"] or "",
            r["usuario_nombre"] or r["usuario_username"],
            r["departamento_nombre"] or "",
            r["puesto_nombre"] or "",
        ])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    return send_file(
        buf,
        as_attachment=True,
        download_name="obligaciones_historial.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ==================================================================
# Fase 10 -- Dashboard
# ==================================================================
@obligaciones_bp.route("/dashboard", methods=["GET"], endpoint="dashboard_obligaciones")
@require_login
@require_permission(PERM_DASHBOARD, "ver")
def dashboard_obligaciones():
    filters = service.collect_dashboard_filters(request.args)
    rol = session.get("rol")
    data = service.dashboard_data(session.get("usuario_id"), rol, filters)
    combos = service.get_combos()

    return render_template(
        "obligaciones/obligaciones_dashboard.html",
        data=data,
        combos=combos,
        filters=filters,
        es_admin=rol in ROLES_ADMIN,
        active_page=ACTIVE_KEY,
    )


# ==================================================================
# Fase 7 -- Carga masiva Excel
# ==================================================================
@obligaciones_bp.route("/carga-masiva", methods=["GET", "POST"], endpoint="carga_masiva")
@require_login
@require_permission(PERM_CARGA_MASIVA, "ver")
def carga_masiva():
    if request.method == "POST":
        archivo = request.files.get("archivo")
        result = service.procesar_carga_masiva_preview(archivo, session)

        if not result["ok"]:
            flash(*result["flash"])
            return render_template(
                "obligaciones/obligaciones_carga_masiva.html",
                preview=None,
                active_page=ACTIVE_KEY,
            )

        return render_template(
            "obligaciones/obligaciones_carga_masiva.html",
            preview=result,
            active_page=ACTIVE_KEY,
        )

    return render_template(
        "obligaciones/obligaciones_carga_masiva.html",
        preview=None,
        active_page=ACTIVE_KEY,
    )


@obligaciones_bp.route("/carga-masiva/confirmar", methods=["POST"], endpoint="carga_masiva_confirmar")
@require_login
@require_permission(PERM_CARGA_MASIVA, "ver")
def carga_masiva_confirmar():
    token = (request.form.get("token") or "").strip()
    result = service.confirmar_carga_masiva(token, session)
    flash(*result["flash"])

    if result["ok"]:
        return redirect(url_for("obligaciones.lista_obligaciones"))
    return redirect(url_for("obligaciones.carga_masiva"))
