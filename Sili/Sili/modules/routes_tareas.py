from flask import app, render_template, request, redirect, url_for, flash, session, send_file, jsonify
from datetime import datetime
from modules.tasks.task_services import svc_abrir_o_crear_encuesta_desde_bandeja
from .security import require_login, require_permission, get_user
from modules.tasks.task_services import (
    TaskServiceError,
    svc_api_inbound_email_create_task,
    svc_build_dashboard_context,
    svc_build_listar_tareas_context,
    svc_build_nueva_tarea_context,
    svc_eliminar_tarea,
    svc_exportar_tareas_excel,
    svc_finalizar_accion,
    svc_guardar_edicion_tarea,
    svc_obtener_tarea_para_editar,
    svc_obtener_tarea_para_ver,
    svc_crear_tarea,
    svc_reenviar_observacion,
    svc_registrar_accion_tarea,
    svc_require_api_key,
    svc_build_encuestas_context,
    svc_build_responder_encuesta_context,
    svc_guardar_respuesta_encuesta,
)


def register_task_routes(app):


    @app.route('/tareas')
    @require_login
    @require_permission('tareas', 'ver')
    def listar_tareas():
        user = get_user()
        return render_template('tareas.html', **svc_build_listar_tareas_context(user, request.args))

    @app.route('/tareas/nueva', methods=['GET', 'POST'])
    @require_login
    @require_permission('tareas', 'crear')
    def nueva_tarea():
        user = get_user()
        modo = (request.args.get('modo') or request.form.get('modo') or 'asignar').lower()
        if modo not in ('para_mi', 'asignar'):
            modo = 'asignar'

        if request.method == 'POST':
            resultado = svc_crear_tarea(user, request.form)
            flash(resultado['message'], resultado['category'])
            return redirect(url_for(resultado['redirect_endpoint'], **resultado['redirect_kwargs']))

        return render_template('nueva_tarea.html', **svc_build_nueva_tarea_context(user, modo))

    @app.route('/tareas/<int:task_id>/ver', methods=['GET', 'POST'])
    @require_login
    @require_permission('tareas', 'ver')
    def ver_tarea(task_id):
        user = get_user()

        if request.method == 'POST':
            resultado = svc_registrar_accion_tarea(user, task_id, request.form)
            flash(resultado['message'], resultado['category'])
            return redirect(url_for('ver_tarea', task_id=task_id))

        resultado = svc_obtener_tarea_para_ver(user, task_id)
        if not resultado['ok']:
            flash(resultado['message'], resultado['category'])
            return redirect(url_for(resultado['redirect_endpoint'], **resultado['redirect_kwargs']))

        return render_template('tarea_detalle.html', **resultado)

    @app.route('/tareas/reenviar-accion/<int:accion_id>', methods=['POST'])
    @require_login
    @require_permission('tareas', 'ver')
    def reenviar_observacion(accion_id):
        resultado = svc_reenviar_observacion(accion_id, session.get('usuario'))
        flash(resultado['message'], resultado['category'])

        if resultado.get('redirect_endpoint'):
            return redirect(url_for(resultado['redirect_endpoint'], **resultado['redirect_kwargs']))
        return redirect(request.referrer or url_for('listar_tareas'))

    @app.route('/tareas/accion/<int:accion_id>/finalizar', methods=['POST'])
    @require_login
    def finalizar_accion(accion_id):
        resultado = svc_finalizar_accion(accion_id)
        flash(resultado['message'], resultado['category'])
        return redirect(url_for(resultado['redirect_endpoint'], **resultado['redirect_kwargs']))

    @app.route('/tareas/<int:task_id>/editar', methods=['GET', 'POST'])
    @require_login
    @require_permission('tareas', 'editar')
    def editar_tarea(task_id):
        user = get_user()

        if request.method == 'POST':
            resultado = svc_guardar_edicion_tarea(user, task_id, request.form)
            flash(resultado['message'], resultado['category'])
            return redirect(url_for(resultado['redirect_endpoint'], **resultado['redirect_kwargs']))

        resultado = svc_obtener_tarea_para_editar(user, task_id)
        if not resultado['ok']:
            flash(resultado['message'], resultado['category'])
            return redirect(url_for(resultado['redirect_endpoint'], **resultado['redirect_kwargs']))

        return render_template('editar_tarea.html', **resultado)

    @app.route('/tareas/<int:task_id>/eliminar', methods=['POST'])
    @require_login
    @require_permission('tareas', 'eliminar')
    def eliminar_tarea(task_id):
        user = get_user()
        resultado = svc_eliminar_tarea(user, task_id)
        flash(resultado['message'], resultado['category'])
        return redirect(url_for('listar_tareas'))

    @app.route('/tareas/reporte/excel')
    @require_login
    def exportar_tareas_excel():
        try:
            output = svc_exportar_tareas_excel(request.args)
        except TaskServiceError as e:
            return e.message, 500

        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f"Reporte_Sili_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        )

    @app.route('/api/inbound/email', methods=['POST'])
    def api_inbound_email_create_task():
        ok, msg = svc_require_api_key(request)
        if not ok:
            return jsonify({'ok': False, 'error': msg}), 401

        if not request.is_json:
            return jsonify({'ok': False, 'error': 'Content-Type debe ser application/json'}), 415

        payload = request.get_json(silent=True) or {}
        resultado = svc_api_inbound_email_create_task(payload)
        status = resultado.pop('status', 200)
        return jsonify(resultado), status


    @app.route('/dashboard')
    @require_login
    def dashboard():
        user = get_user()
        return render_template('dashboard.html', **svc_build_dashboard_context(user, request.args))


    @app.route('/encuestas')
    @require_login
    def listar_encuestas():
        user = get_user()
        return render_template('encuestas.html', **svc_build_encuestas_context(user, request.args))
    

    @app.route('/encuestas/responder/<token>', methods=['GET', 'POST'])
    def responder_encuesta(token):
        if request.method == 'POST':
            resultado = svc_guardar_respuesta_encuesta(token, request.form)
            flash(resultado['message'], resultado['category'])
            return redirect(url_for('responder_encuesta', token=token))

        resultado = svc_build_responder_encuesta_context(token)
        return render_template('encuesta_responder.html', **resultado)
    

    @app.route('/encuestas/tarea/<int:task_id>/responder', methods=['POST'])
    @require_login
    def responder_encuesta_desde_bandeja(task_id):
        user = get_user()

        resultado = svc_abrir_o_crear_encuesta_desde_bandeja(user, task_id)

        if resultado.get("message"):
            flash(resultado["message"], resultado.get("category", "info"))

        return redirect(
            url_for(
                resultado["redirect_endpoint"],
                **resultado.get("redirect_kwargs", {})
            )
        )