# modules/gastos/routes_gastos.py

from __future__ import annotations

from datetime import datetime

from flask import (
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from .gastos_service import (
    aprobar_gasto_data,
    aprobar_gasto_masivo_data,
    create_gasto,
    delete_gasto_data,
    enviar_gasto_sap_data,
    enviar_gasto_sap_masivo_data,
    get_adjuntos_data,
    get_dashboard_data,
    get_gasto_detalle_data,
    get_lista_gastos_data,
    get_pendientes_aprobacion_data,
    get_reporte_data,
    search_facturas_xml_data,
    update_gasto_data,
)
from .gastos_exports import (
    export_gastos_excel_response,
    export_gastos_pdf_response,
    export_gastos_csv_response,
)

from ..db import get_db
from ..security import require_login, require_permission



def register_gastos_routes(app):
    # ==========================================================
    # REPORTE
    # ==========================================================
    @app.route("/reembolsos/gastos/reporte", methods=["GET"], endpoint="reporte_gastos")
    @require_login
    @require_permission("gastos_tarjeta", "ver")
    def reporte_gastos():
        conn = get_db()
        data = get_reporte_data(conn, request.args, dict(session))

        return render_template(
            "gastos_reporte.html",
            gastos=data["gastos"],
            filtros=type("Filtros", (), data["filtros"])(),
            proveedores=data["proveedores"],
            usuarios_reg=data["usuarios_reg"],
            gerentes_reg=data["gerentes_reg"],
            totales=type("Totales", (), data["totales"])(),
            usuario=session.get("usuario"),
            rol=session.get("rol"),
            active_page="gastos_tarjeta",
        )

    # ==========================================================
    # PENDIENTES APROBACIÓN
    # ==========================================================
    @app.route(
        "/reembolsos/gastos/pendientes-aprobacion",
        methods=["GET"],
        endpoint="gastos_pendientes_aprobacion",
    )
    @require_login
    @require_permission("gastos_pendientes_aprobacion", "ver")
    def gastos_pendientes_aprobacion():
        conn = get_db()
        data = get_pendientes_aprobacion_data(conn, request.args, dict(session))

        return render_template(
            "gastos_pendientes_aprobacion.html",
            gastos=data["gastos"],
            filtros=type("Filtros", (), data["filtros"])(),
            proveedores=data["proveedores"],
            usuarios_reg=data["usuarios_reg"],
            gerentes_reg=data["gerentes_reg"],
            totales=type("Totales", (), data["totales"])(),
            can_approve_gg=data["can_approve_gg"],
            can_approve_gf=data["can_approve_gf"],
            can_approve_ga=data["can_approve_ga"],
            readonly_view=data["readonly_view"],
            usuario=session.get("usuario"),
            rol=session.get("rol"),
            active_page="gastos_pendientes",
        )

    # ==========================================================
    # DASHBOARD
    # ==========================================================
    @app.route("/reembolsos/dashboard", methods=["GET"], endpoint="gastos_dashboard")
    @require_login
    @require_permission("gastos_tarjeta", "ver")
    def gastos_dashboard():
        conn = get_db()
        data = get_dashboard_data(conn, request.args, dict(session))

        return render_template(
            "gastos_dashboard.html",
            desde=data["desde"],
            hasta=data["hasta"],
            kpis=type("KPIs", (), data["kpis"])(),
            evolucion=data["evolucion"],
            top_motivos=data["top_motivos"],
            top_proveedores=data["top_proveedores"],
            active_page="gastos_tarjeta",
        )

    # ==========================================================
    # API FACTURAS XML SEARCH
    # ==========================================================
    @app.route("/api/facturas-xml/search", methods=["GET"], endpoint="api_facturas_xml_search")
    @require_login
    def api_facturas_xml_search():
        conn = get_db()

        q = (request.args.get("q") or "").strip()
        try:
            limit = int(request.args.get("limit") or 10)
        except Exception:
            limit = 10

        data = search_facturas_xml_data(conn, q=q, limit=limit)
        return jsonify(data)

    # ==========================================================
    # EXPORT REPORTE EXCEL
    # ==========================================================
    @app.route(
        "/reembolsos/gastos/export/reporte.xlsx",
        methods=["GET"],
        endpoint="export_gastos_reporte_excel",
    )
    @require_login
    @require_permission("gastos_tarjeta", "exportar")
    def export_gastos_reporte_excel():
        # Usa el generador completo con cabecera (compañía, nombre, cargo, etc.)
        return export_gastos_excel_response()


    # ==========================================================
    # ENVÍO SAP INDIVIDUAL
    # ==========================================================
    @app.route(
        "/reembolsos/gastos/<int:gasto_id>/enviar-sap",
        methods=["POST"],
        endpoint="enviar_gasto_sap",
    )
    @require_login
    @require_permission("gastos_tarjeta", "ver")
    def enviar_gasto_sap():
        conn = get_db()
        result = enviar_gasto_sap_data(conn, request.view_args["gasto_id"])
        status = 200 if result.get("ok") else 400
        return jsonify(result), status

    # ==========================================================
    # ENVÍO SAP MASIVO
    # ==========================================================
    @app.route(
        "/reembolsos/gastos/enviar-sap-masivo",
        methods=["POST"],
        endpoint="enviar_gasto_sap_masivo",
    )
    @require_login
    @require_permission("gastos_tarjeta", "ver")
    def enviar_gasto_sap_masivo():
        conn = get_db()
        payload = request.get_json(silent=True) or {}
        ids = payload.get("ids") or []

        result = enviar_gasto_sap_masivo_data(conn, ids)
        status = 200 if result.get("ok") else 400
        return jsonify(result), status
    


    # ==========================================================
    # NUEVO GASTO
    # ==========================================================
    @app.route("/reembolsos/gastos/nuevo", methods=["GET", "POST"], endpoint="nuevo_gasto")
    @require_login
    @require_permission("gastos_tarjeta", "crear")
    def nuevo_gasto():
        conn = get_db()

        if request.method == "POST":
            result = create_gasto(conn, request.form, dict(session))
            if result.get("ok"):
                flash("Gasto registrado correctamente.", "success")
                return redirect(url_for("lista_gastos"))
            flash(result.get("msg") or "No se pudo registrar el gasto.", "danger")

        return render_template(
            "gastos_form.html",
            modo="nuevo",
            g=None,
            form=request.form,
            active_page="gastos_tarjeta",
        )

    # ==========================================================
    # EDITAR GASTO
    # ==========================================================
    @app.route("/reembolsos/gastos/<int:gasto_id>/editar", methods=["GET", "POST"], endpoint="editar_gasto")
    @require_login
    @require_permission("gastos_tarjeta", "editar")
    def editar_gasto(gasto_id: int):
        conn = get_db()

        if request.method == "POST":
            result = update_gasto_data(conn, gasto_id, request.form, dict(session))
            if result.get("ok"):
                flash("Gasto actualizado correctamente.", "success")
                return redirect(url_for("lista_gastos"))
            flash(result.get("msg") or "No se pudo actualizar el gasto.", "danger")

        data = get_gasto_detalle_data(conn, gasto_id, dict(session))
        if not data.get("ok"):
            flash(data.get("msg") or "No se encontró el gasto.", "warning")
            return redirect(url_for("lista_gastos"))

        return render_template(
            "gastos_form.html",
            modo="editar",
            g=data["gasto"],
            detalle=data["detalle"],
            adjuntos=data["adjuntos"],
            form=request.form if request.method == "POST" else None,
            active_page="gastos_tarjeta",
        )

    # ==========================================================
    # ELIMINAR GASTO
    # ==========================================================
    @app.route("/reembolsos/gastos/<int:gasto_id>/eliminar", methods=["POST"], endpoint="eliminar_gasto")
    @require_login
    @require_permission("gastos_tarjeta", "eliminar")
    def eliminar_gasto(gasto_id: int):
        conn = get_db()
        result = delete_gasto_data(conn, gasto_id, dict(session))
        flash(
            "Gasto eliminado correctamente." if result.get("ok") else (result.get("msg") or "No se pudo eliminar."),
            "success" if result.get("ok") else "danger",
        )
        return redirect(url_for("lista_gastos"))

    # ==========================================================
    # VER GASTO
    # ==========================================================
    @app.route("/reembolsos/gastos/<int:gid>/ver", methods=["GET"], endpoint="ver_gasto")
    @require_login
    @require_permission("gastos_tarjeta", "ver")
    def ver_gasto(gid: int):
        conn = get_db()
        data = get_gasto_detalle_data(conn, gid, dict(session))
        if not data.get("ok"):
            flash(data.get("msg") or "No se encontró el gasto.", "warning")
            return redirect(url_for("lista_gastos"))

        return render_template(
            "gastos_ver.html",
            gasto=data["gasto"],
            detalle=data["detalle"],
            adjuntos=data["adjuntos"],
            active_page="gastos_tarjeta",
        )

    # ==========================================================
    # VER ADJUNTOS
    # ==========================================================
    @app.route("/reembolsos/gastos/<int:gid>/adjuntos", methods=["GET"], endpoint="ver_gasto_adjuntos")
    @require_login
    @require_permission("gastos_tarjeta", "ver")
    def ver_gasto_adjuntos(gid: int):
        conn = get_db()
        data = get_adjuntos_data(conn, gid, dict(session))
        status = 200 if data.get("ok") else 404
        return jsonify(data), status

    # ==========================================================
    # APROBAR GASTO
    # ==========================================================
    @app.route("/reembolsos/gastos/<int:gasto_id>/aprobar", methods=["POST"], endpoint="aprobar_gasto")
    @require_login
    @require_permission("gastos_tarjeta", "aprobar")
    def aprobar_gasto(gasto_id: int):
        conn = get_db()
        payload = request.get_json(silent=True) or {}
        area = (payload.get("area") or "").strip().lower()
        value = bool(payload.get("value", True))

        result = aprobar_gasto_data(conn, gasto_id, area, value, dict(session))
        status = 200 if result.get("ok") else 400
        return jsonify(result), status

    # ==========================================================
    # APROBAR GASTO MASIVO
    # ==========================================================
    @app.route("/reembolsos/gastos/aprobar-masivo", methods=["POST"], endpoint="aprobar_gasto_masivo")
    @require_login
    @require_permission("gastos_tarjeta", "aprobar")
    def aprobar_gasto_masivo():
        conn = get_db()
        payload = request.get_json(silent=True) or {}

        ids = payload.get("ids") or []
        area = (payload.get("area") or "").strip().lower()
        value = bool(payload.get("value", True))

        result = aprobar_gasto_masivo_data(conn, ids, area, value, dict(session))
        status = 200 if result.get("ok") else 400
        return jsonify(result), status


    # ==========================================================
    # LISTA / CONSULTA DE GASTOS
    # ==========================================================
    @app.route("/reembolsos/gastos", methods=["GET"], endpoint="lista_gastos")
    @require_login
    @require_permission("gastos_tarjeta", "ver")
    def lista_gastos():
        conn = get_db()
        data = get_lista_gastos_data(conn, request.args, dict(session))

        return render_template(
            "gastos_lista.html",
            gastos=data["gastos"],
            filtros=type("Filtros", (), data["filtros"])(),
            proveedores=data["proveedores"],
            usuarios_reg=data["usuarios_reg"],
            gerentes_reg=data["gerentes_reg"],
            totales=type("Totales", (), data["totales"])(),
            can_approve_gg=data["can_approve_gg"],
            can_approve_gf=data["can_approve_gf"],
            can_approve_ga=data["can_approve_ga"],
            usuario=session.get("usuario"),
            rol=session.get("rol"),
            active_page="gastos_tarjeta",
        )





    # ==========================================================
    # EXPORT EXCEL
    # ==========================================================
    @app.route("/reembolsos/gastos/export/excel", methods=["GET"], endpoint="export_gastos_excel")
    @require_login
    @require_permission("gastos_tarjeta", "exportar")
    def export_gastos_excel():
        return export_gastos_excel_response()

    # ==========================================================
    # EXPORT PDF
    # ==========================================================
    @app.route("/reembolsos/gastos/export/pdf", methods=["GET"], endpoint="export_gastos_pdf")
    @require_login
    @require_permission("gastos_tarjeta", "exportar")
    def export_gastos_pdf():
        return export_gastos_pdf_response()

    # ==========================================================
    # EXPORT CSV
    # ==========================================================
    @app.route("/reembolsos/gastos/export/csv", methods=["GET"], endpoint="export_gastos_csv")
    @require_login
    @require_permission("gastos_tarjeta", "exportar")
    def export_gastos_csv():
        return export_gastos_csv_response()        