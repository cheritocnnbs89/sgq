from flask import app, render_template, request, redirect, url_for, flash, session, send_file, jsonify
from datetime import datetime
from modules.tasks.task_services import svc_abrir_o_crear_encuesta_desde_bandeja, svc_crear_y_enviar_encuesta
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

    @app.route('/tareas/<int:task_id>/detalle-json')
    @require_login
    @require_permission('tareas', 'ver')
    def tarea_detalle_json(task_id):
        user = get_user()
        resultado = svc_obtener_tarea_para_ver(user, task_id)
        if not resultado['ok']:
            return jsonify({'ok': False, 'error': resultado['message']}), 403

        def s(v):
            if v is None: return None
            if hasattr(v, 'strftime'): return v.strftime('%Y-%m-%d %H:%M:%S')
            return v if isinstance(v, (str, int, float, bool)) else str(v)

        tarea = {k: s(resultado['tarea'][k]) for k in resultado['tarea'].keys()}
        acciones = [{k: s(a[k]) for k in a.keys()} for a in resultado['acciones']]
        responsables = [
            {'id': r['id'], 'label': r.get('nombre_completo') or r['username'], 'username': r['username']}
            for r in resultado['responsables']
        ]
        return jsonify({
            'ok': True,
            'tarea': tarea,
            'acciones': acciones,
            'puede_anotar': resultado['puede_anotar'],
            'responsables': responsables,
        })

    @app.route('/tareas/<int:task_id>/accion-ajax', methods=['POST'])
    @require_login
    @require_permission('tareas', 'ver')
    def accion_tarea_ajax(task_id):
        user = get_user()
        resultado = svc_registrar_accion_tarea(user, task_id, request.form)

        task_closed = False
        if resultado.get('ok') and (request.form.get('estado_accion') or '').strip() == 'Finalizado':
            try:
                from modules.db import get_db as _get_db
                _conn = _get_db()
                _cur = _conn.cursor()
                _cur.execute(
                    "UPDATE tareas SET estado = 'Terminado', fecha_cierre_real = GETDATE() WHERE id = ? AND COALESCE(estado,'') <> 'Terminado'",
                    (task_id,)
                )
                _cur.execute(
                    "UPDATE email_tickets_inbox SET estado = 'TERMINADA' WHERE tarea_id = ? AND estado = 'ASIGNADA'",
                    (task_id,)
                )
                _conn.commit()
                task_closed = True
                resultado['message'] = 'Acción registrada. La tarea ha sido marcada como Terminada.'

                # Enviar encuesta de satisfacción al solicitante
                try:
                    import logging as _logging
                    _log_enc = _logging.getLogger(__name__)
                    _log_enc.info('[encuesta] Iniciando envío encuesta para tarea %s', task_id)
                    _ok_enc = svc_crear_y_enviar_encuesta(task_id)
                    _log_enc.info('[encuesta] svc_crear_y_enviar_encuesta tarea %s -> ok=%s', task_id, _ok_enc)
                except Exception as _enc_e:
                    import logging as _logging
                    _logging.getLogger(__name__).exception(
                        'accion_tarea_ajax: encuesta no enviada para tarea %s', task_id
                    )
            except Exception as _e:
                import logging as _logging
                _logging.getLogger(__name__).warning('accion_tarea_ajax: error al cerrar tarea %s: %s', task_id, _e)

        return jsonify({
            'ok': resultado.get('ok', False),
            'message': resultado.get('message', ''),
            'task_closed': task_closed,
        })

    @app.route('/api/tareas/mejorar-comentario', methods=['POST'])
    @require_login
    def api_tareas_mejorar_comentario():
        data  = request.get_json(silent=True) or {}
        texto = (data.get('texto') or '').strip()

        if not texto or len(texto) < 5:
            return jsonify(ok=False, error='Escribe el detalle antes de mejorar.'), 400

        try:
            import os
            from openai import OpenAI
            client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

            prompt = f"""Eres un técnico de soporte TI profesional. Reescribe el siguiente comentario de avance de tarea como un técnico experto: claro, conciso, en tercera persona, sin jerga informal, sin errores ortográficos, enfocado en qué se hizo o qué se identificó.

Comentario original:
\"\"\"{texto}\"\"\"

Reglas:
- Máximo 3 oraciones
- Usa lenguaje técnico y objetivo: "Se verificó...", "Se identificó...", "Se realizó..."
- NO menciones nombres propios ni uses primera persona
- Mantén los hechos concretos del texto original

Responde SOLO con JSON: {{"texto_mejorado": "..."}}"""

            resp = client.chat.completions.create(
                model=os.getenv('OPENAI_MODEL', 'gpt-4o-mini'),
                messages=[
                    {'role': 'system', 'content': 'Responde únicamente con JSON válido.'},
                    {'role': 'user',   'content': prompt},
                ],
                max_tokens=300,
                temperature=0.3,
            )
            import json as _json
            raw = resp.choices[0].message.content.strip()
            if raw.startswith('```'):
                raw = raw.split('```')[1]
                if raw.startswith('json'):
                    raw = raw[4:]
            parsed = _json.loads(raw)
            return jsonify(ok=True, texto_mejorado=parsed.get('texto_mejorado', ''))

        except Exception as e:
            import logging as _log
            _log.getLogger(__name__).warning('mejorar_comentario error: %s', e)
            return jsonify(ok=False, error='No se pudo mejorar el texto. Intenta de nuevo.'), 500

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

    @app.route('/tareas/<int:task_id>/json')
    @require_login
    @require_permission('tareas', 'ver')
    def tarea_json(task_id):
        user = get_user()
        resultado = svc_obtener_tarea_para_editar(user, task_id)
        if not resultado['ok']:
            return jsonify({'ok': False, 'error': resultado['message']}), 403

        tarea_raw = resultado['tarea']
        tarea = {}
        for k in tarea_raw.keys():
            v = tarea_raw[k]
            if hasattr(v, 'strftime'):
                tarea[k] = v.strftime('%Y-%m-%dT%H:%M')
            elif v is None or isinstance(v, (str, int, float, bool)):
                tarea[k] = v
            else:
                tarea[k] = str(v)

        for date_field in ('fecha_inicio', 'fecha_compromiso', 'fecha_fin', 'fecha_cierre_real'):
            raw = tarea.get(date_field) or ''
            if raw and ' ' in str(raw):
                tarea[date_field] = str(raw)[:16].replace(' ', 'T')

        empresas = []
        for e in resultado['empresas']:
            try:
                empresas.append({'id': e.id, 'nombre': e.razon_social})
            except AttributeError:
                empresas.append({'id': e['id'], 'nombre': e['razon_social']})

        return jsonify({
            'ok': True,
            'tarea': tarea,
            'estados': resultado['estados'],
            'tipos_tarea': [{'id': tp['id'], 'nombre': tp['nombre']} for tp in resultado['tipos_tarea']],
            'empresas': empresas,
            'solicitantes': [
                {'id': s['id'], 'label': (s.get('nombre_completo') or '') + ' (' + (s.get('username') or '') + ')'}
                for s in resultado['solicitantes']
            ],
        })

    @app.route('/tareas/<int:task_id>/editar-ajax', methods=['POST'])
    @require_login
    @require_permission('tareas', 'editar')
    def editar_tarea_ajax(task_id):
        user = get_user()
        resultado = svc_guardar_edicion_tarea(user, task_id, request.form)
        return jsonify({'ok': resultado.get('ok', False), 'message': resultado.get('message', '')})

    @app.route('/tareas/<int:task_id>/detalle-json')
    @require_login
    @require_permission('tareas', 'ver')
    def tarea_detalle_json(task_id):
        user = get_user()
        resultado = svc_obtener_tarea_para_ver(user, task_id)
        if not resultado['ok']:
            return jsonify({'ok': False, 'error': resultado['message']}), 403

        def s(v):
            if v is None: return None
            if hasattr(v, 'strftime'): return v.strftime('%Y-%m-%d %H:%M:%S')
            return v if isinstance(v, (str, int, float, bool)) else str(v)

        tarea = {k: s(resultado['tarea'][k]) for k in resultado['tarea'].keys()}
        acciones = [{k: s(a[k]) for k in a.keys()} for a in resultado['acciones']]
        responsables = [
            {'id': r['id'], 'label': r.get('nombre_completo') or r['username'], 'username': r['username']}
            for r in resultado['responsables']
        ]
        return jsonify({
            'ok': True,
            'tarea': tarea,
            'acciones': acciones,
            'puede_anotar': resultado['puede_anotar'],
            'responsables': responsables,
        })

    @app.route('/tareas/<int:task_id>/accion-ajax', methods=['POST'])
    @require_login
    @require_permission('tareas', 'ver')
    def accion_tarea_ajax(task_id):
        user = get_user()
        resultado = svc_registrar_accion_tarea(user, task_id, request.form)

        task_closed = False
        if resultado.get('ok') and (request.form.get('estado_accion') or '').strip() == 'Finalizado':
            try:
                from modules.db import get_db as _get_db
                _conn = _get_db()
                _cur = _conn.cursor()
                _cur.execute(
                    "UPDATE tareas SET estado = 'Terminado', fecha_cierre_real = GETDATE() WHERE id = ? AND COALESCE(estado,'') <> 'Terminado'",
                    (task_id,)
                )
                # Marcar el ticket de bandeja vinculado como TERMINADA
                _cur.execute(
                    "UPDATE email_tickets_inbox SET estado = 'TERMINADA' WHERE tarea_id = ? AND estado = 'ASIGNADA'",
                    (task_id,)
                )
                _conn.commit()
                svc_crear_y_enviar_encuesta(task_id)
                task_closed = True
                resultado['message'] = 'Acción registrada. La tarea ha sido marcada como Terminada.'
            except Exception as _e:
                import logging as _logging
                _logging.getLogger(__name__).warning('accion_tarea_ajax: error al cerrar tarea %s: %s', task_id, _e)

        return jsonify({
            'ok': resultado.get('ok', False),
            'message': resultado.get('message', ''),
            'task_closed': task_closed,
        })

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
    

    @app.route('/encuestas/diagnostico/<int:task_id>')
    @require_login
    def encuesta_diagnostico(task_id):
        """Ruta de diagnóstico: muestra qué pasaría al enviar la encuesta de una tarea."""
        from modules.db import get_db, get_config_value
        from modules.tasks.task_repository import repo_obtener_tarea_para_encuesta, repo_obtener_encuesta_por_tarea
        conn = get_db()
        tarea = repo_obtener_tarea_para_encuesta(task_id)
        encuesta = repo_obtener_encuesta_por_tarea(task_id)
        smtp_host = get_config_value('smtp_host', '')
        smtp_from = get_config_value('smtp_from', '')
        smtp_user = get_config_value('smtp_user', '')
        info = {
            "task_id": task_id,
            "tarea_encontrada": bool(tarea),
            "titulo": tarea.get("titulo") if tarea else None,
            "solicitante_id": tarea.get("solicitante_id") if tarea else None,
            "solicitante_email": tarea.get("solicitante_email") if tarea else None,
            "solicitante_nombre": tarea.get("solicitante_nombre") if tarea else None,
            "encuesta_existente": bool(encuesta),
            "encuesta_id": encuesta.get("id") if encuesta else None,
            "encuesta_estado": encuesta.get("estado") if encuesta else None,
            "encuesta_enviada": str(encuesta.get("fecha_envio") or encuesta.get("enviada")) if encuesta else None,
            "smtp_host": smtp_host or "(no configurado)",
            "smtp_from": smtp_from or "(no configurado)",
            "smtp_user": smtp_user or "(vacío)",
        }
        return jsonify(info)

    @app.route('/encuestas/reenviar/<int:task_id>', methods=['POST'])
    @require_login
    def encuesta_reenviar(task_id):
        """Reenvía (o crea y envía) la encuesta para una tarea terminada."""
        from modules.db import get_db
        from modules.tasks.task_repository import repo_obtener_encuesta_por_tarea
        conn = get_db()
        # Eliminar encuesta previa para forzar reenvío
        existente = repo_obtener_encuesta_por_tarea(task_id)
        if existente:
            cur = conn.cursor()
            cur.execute("DELETE FROM encuestas_satisfaccion WHERE tarea_id = ?", (task_id,))
            conn.commit()
        ok = svc_crear_y_enviar_encuesta(task_id)
        if ok:
            flash("Encuesta reenviada correctamente.", "success")
        else:
            flash("No se pudo reenviar la encuesta. Revisa el log del servidor.", "danger")
        return redirect(url_for("listar_encuestas"))

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