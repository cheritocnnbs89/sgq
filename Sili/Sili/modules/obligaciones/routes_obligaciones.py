# -*- coding: utf-8 -*-
import io
from datetime import date, datetime

import openpyxl
from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, abort, session, send_file,
    current_app, jsonify,
)

from modules.auth.routes_auth import require_login, require_permission

from .obligaciones_constants import (
    ACTIVE_KEY,
    PERM_VER,
    PERM_CREAR,
    PERM_EDITAR,
    PERM_EXPORTAR,
    PERM_HISTORIAL,
    PERM_DASHBOARD,
    PERM_CONFIG,
    ACTIVE_KEY_SOLICITUDES,
    ACTIVE_KEY_APROBACIONES,
    ROLES_ADMIN,
    ROL_JEFE_AREA,
    ROL_GERENTE_OBLIG,
    ESTATUS_LABELS,
    HISTORIAL_COLUMNAS,
)
from . import obligaciones_services as service

obligaciones_bp = Blueprint("obligaciones", __name__, url_prefix="/obligaciones")


def _excel_cell(value):
    """Blinda ws.append: openpyxl solo acepta str/número/fecha/None. Cualquier
    otro tipo (list/dict/etc.) se convierte a texto para no romper el export."""
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool, date, datetime)):
        return value
    return str(value)


def register_obligaciones_routes(app):
    # 2026-07-15: importa (y registra) las rutas de Frecuencias en el MISMO
    # blueprint antes de app.register_blueprint -- import diferido acá (no al
    # tope del archivo) para evitar import circular, ya que
    # routes_obligaciones_frecuencias.py importa `obligaciones_bp` de este módulo.
    from . import routes_obligaciones_frecuencias  # noqa: F401 (registra decoradores @obligaciones_bp.route)
    # 2026-08-07 (Correccion #8): rutas de Tipos y Entidades Reguladoras --
    # mismo patron de import diferido que Frecuencias, mismo motivo (evitar
    # import circular con obligaciones_bp).
    from . import routes_obligaciones_tipos  # noqa: F401
    from . import routes_obligaciones_entidades  # noqa: F401
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
    elif rol == ROL_GERENTE_OBLIG:
        # 2026-08-14: gerente_obligaciones -- mismo patron, combo 2 niveles.
        usuarios = service.get_subordinados_2niveles_combo(session.get("usuario_id"))
    else:
        usuarios = []

    return render_template(
        "obligaciones/obligaciones_lista.html",
        rows=rows,
        filters=filters,
        combos=combos,
        usuarios=usuarios,
        estatus_labels=ESTATUS_LABELS,
        active_page=ACTIVE_KEY,
    )


@obligaciones_bp.route("/nueva", methods=["GET", "POST"], endpoint="nueva_obligacion")
@require_login
@require_permission(PERM_CREAR, "ver")
def nueva_obligacion():
    combos = service.get_combos_form()

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
            hoy=date.today().isoformat(),
        )

    return render_template(
        "obligaciones/obligaciones_form.html",
        data={},
        combos=combos,
        mode="new",
        active_page=ACTIVE_KEY,
        hoy=date.today().isoformat(),
    )


@obligaciones_bp.route("/<int:oblig_id>/editar", methods=["GET", "POST"], endpoint="editar_obligacion")
@require_login
@require_permission(PERM_EDITAR, "ver")
def editar_obligacion(oblig_id):
    row = service.get_item(oblig_id)
    if not row:
        abort(404)
    service.assert_puede_acceder_obligacion(row, session)

    combos = service.get_combos_form()

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
            hoy=date.today().isoformat(),
        )

    return render_template(
        "obligaciones/obligaciones_form.html",
        data=row,
        combos=combos,
        mode="edit",
        oblig_id=oblig_id,
        active_page=ACTIVE_KEY,
        hoy=date.today().isoformat(),
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
# Punto 8 (2026-08-14) -- solicitud de autorizacion para editar cumplida
# ==================================================================
@obligaciones_bp.route("/<int:oblig_id>/solicitar-edicion", methods=["POST"], endpoint="solicitar_edicion")
@require_login
@require_permission(PERM_HISTORIAL, "ver")
def solicitar_edicion(oblig_id):
    result = service.solicitar_edicion(oblig_id, session, request.form.get("motivo"))
    flash(*result["flash"])
    return redirect(url_for("obligaciones.historial_obligaciones"))


@obligaciones_bp.route("/solicitudes-edicion", methods=["GET"], endpoint="solicitudes_edicion")
@require_login
@require_permission(PERM_CONFIG, "ver")
def solicitudes_edicion():
    solicitudes = service.list_solicitudes_pendientes()
    return render_template(
        "obligaciones/obligaciones_solicitudes_edicion.html",
        solicitudes=solicitudes,
        active_page=ACTIVE_KEY_SOLICITUDES,
    )


@obligaciones_bp.route("/solicitudes-edicion/<int:solicitud_id>/resolver", methods=["POST"], endpoint="resolver_solicitud_edicion")
@require_login
@require_permission(PERM_CONFIG, "ver")
def resolver_solicitud_edicion(solicitud_id):
    aprobar = request.form.get("accion") == "aprobar"
    result = service.resolver_solicitud_edicion(solicitud_id, aprobar, session)
    flash(*result["flash"])
    return redirect(url_for("obligaciones.solicitudes_edicion"))


# ==================================================================
# Punto 9 (2026-08-15) -- aprobación de cumplimiento por el jefe directo
# ==================================================================
@obligaciones_bp.route("/aprobaciones-jefe", methods=["GET"], endpoint="aprobaciones_jefe")
@require_login
@require_permission(PERM_VER, "ver")
def aprobaciones_jefe():
    pendientes = service.list_pendientes_aprobacion_jefe(session)
    return render_template(
        "obligaciones/obligaciones_aprobaciones_jefe.html",
        pendientes=pendientes,
        estatus_labels=ESTATUS_LABELS,
        active_page=ACTIVE_KEY_APROBACIONES,
    )


@obligaciones_bp.route("/<int:oblig_id>/aprobar-jefe", methods=["POST"], endpoint="resolver_aprobacion_jefe")
@require_login
@require_permission(PERM_VER, "ver")
def resolver_aprobacion_jefe(oblig_id):
    aprobar = request.form.get("accion") == "aprobar"
    result = service.resolver_aprobacion_jefe(oblig_id, aprobar, session, request.form.get("motivo"))
    flash(*result["flash"])
    return redirect(url_for("obligaciones.aprobaciones_jefe"))


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
        estatus_labels=ESTATUS_LABELS,
        active_page=ACTIVE_KEY,
    )


# ==================================================================
# Fase 9 -- Exportar Excel (Historial)
# ==================================================================
@obligaciones_bp.route("/historial/exportar", methods=["GET"], endpoint="exportar_historial")
@require_login
@require_permission(PERM_EXPORTAR, "ver")
def exportar_historial():
    # 2026-07-21: export blindado (try/except) + 10 columnas del Excel real de
    # referencia (Data Power BI - Obligaciones tributarias y societarias.xlsx).
    # "Prioridad" no tiene campo en BD todavía -> se exporta vacía
    # (ver HISTORIAL-CORRECCIONES 2026-07-21).
    try:
        filters = service.collect_historial_filters(request.args)
        rows = service.list_historial(session.get("usuario_id"), session.get("rol"), filters)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Historial"
        ws.append(list(HISTORIAL_COLUMNAS))

        for r in rows:
            ws.append([
                _excel_cell(r["id"]),
                _excel_cell(r["tipo_nombre"]),
                _excel_cell(service.sanear_formula(r["descripcion"])),  # anti CSV/formula injection (T6)
                _excel_cell(r["departamento_nombre"] or ""),
                _excel_cell(r["usuario_nombre"] or r["usuario_username"]),
                _excel_cell(r["entidad_nombre"]),
                _excel_cell(r["fecha_vencimiento"]),
                _excel_cell(r["frecuencia_nombre"]),
                _excel_cell(ESTATUS_LABELS.get(r["estatus"], r["estatus"])),
                "",  # Prioridad -- sin campo en BD, pendiente definir origen (Matias)
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
    except Exception:
        current_app.logger.exception("Error al exportar historial de obligaciones")
        flash("No se pudo generar el Excel del historial.", "danger")
        return redirect(url_for("obligaciones.historial_obligaciones"))


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
    # 2026-07-28: mismo patron de combo "usuario" que Consultas (lista_obligaciones) --
    # admin ve todos, jefe_area ve solo sus subordinados, el resto no ve el filtro.
    if rol in ROLES_ADMIN:
        usuarios = service.get_usuarios_combo()
    elif rol == ROL_JEFE_AREA:
        usuarios = service.get_subordinados_combo(session.get("usuario_id"))
    elif rol == ROL_GERENTE_OBLIG:
        usuarios = service.get_subordinados_2niveles_combo(session.get("usuario_id"))
    else:
        usuarios = []

    return render_template(
        "obligaciones/obligaciones_dashboard.html",
        data=data,
        combos=combos,
        filters=filters,
        usuarios=usuarios,
        es_admin=rol in ROLES_ADMIN,
        active_page=ACTIVE_KEY,
    )


@obligaciones_bp.route("/dashboard/desglose", methods=["GET"], endpoint="dashboard_obligaciones_desglose")
@require_login
@require_permission(PERM_DASHBOARD, "ver")
def dashboard_obligaciones_desglose():
    # 2026-08-14: Punto 5 -- click en seccion del pastel -> 3 tablas (Tipo/Entidad/Area).
    seccion = (request.args.get("seccion") or "").strip()
    filters = service.collect_dashboard_filters(request.args)
    rol = session.get("rol")
    data = service.dashboard_desglose_seccion(seccion, session.get("usuario_id"), rol, filters)
    return jsonify(data)


@obligaciones_bp.route("/dashboard/data", methods=["GET"], endpoint="dashboard_obligaciones_data")
@require_login
@require_permission(PERM_DASHBOARD, "ver")
def dashboard_obligaciones_data():
    # Endpoint AJAX del auto-refresco (polling cada 30s). Reusa la MISMA logica
    # de armado de datos que la vista HTML -- solo cambia render_template por
    # jsonify. Respeta los filtros que el JS mande en el query string.
    filters = service.collect_dashboard_filters(request.args)
    rol = session.get("rol")
    data = service.dashboard_data(session.get("usuario_id"), rol, filters)
    return jsonify(data)


# ==================================================================
# 2026-07-27 -- Filtro dependiente Tipo -> Entidad
# ==================================================================
@obligaciones_bp.route("/api/entidades", methods=["GET"], endpoint="api_entidades_por_tipo")
@require_login
@require_permission(PERM_VER, "ver")
def api_entidades_por_tipo():
    tipo_id = (request.args.get("tipo_id") or "").strip()
    if not tipo_id.isdigit():
        return jsonify({"ok": True, "entidades": []})
    rows = service.list_entidades_por_tipo(int(tipo_id))
    return jsonify({"ok": True, "entidades": [{"id": r["id"], "nombre": r["nombre"]} for r in rows]})
