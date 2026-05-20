# modules/parametros_generales/routes_parametros_generales.py
# -*- coding: utf-8 -*-

from flask import (
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    Response,
)

from modules.security import require_login, require_permission
from .parameters_constants import (
    ACTIVE_PAGE_PARAMETROS_GENERALES,
    TEMPLATE_PARAMETROS_GENERALES,
    TEMPLATE_PARAMETRO_ITEMS,
    TEMPLATE_NUEVO_PARAMETRO,
    TEMPLATE_EDITAR_PARAMETRO,
    TEMPLATE_NUEVO_VALOR,
    TEMPLATE_EDITAR_VALOR,
    TEMPLATE_CARGA_MASIVA,
    CSV_TEMPLATE_TEXT,
    CSV_TEMPLATE_FILENAME,
)
from . import parameters_services as service


def register_parametros_generales_routes(app):

    @app.route('/parametros/generales', methods=['GET'], endpoint='parametros_generales')
    @require_login
    @require_permission('parametros', 'ver')
    def parametros_generales():
        grupos, valores = service.listar_grupos_y_valores()

        return render_template(
            TEMPLATE_PARAMETROS_GENERALES,
            grupos=grupos,
            valores=valores,
            usuario=session.get('usuario'),
            rol=session.get('rol'),
            active_page=ACTIVE_PAGE_PARAMETROS_GENERALES
        )

    @app.route('/parametros_generales', methods=['GET'], endpoint='parametros_generales_alias')
    @require_login
    @require_permission('parametros', 'ver')
    def parametros_generales_alias():
        return redirect(url_for('parametros_generales'))

    @app.route('/parametros/generales/<int:group_id>/items', methods=['GET'], endpoint='parametro_items')
    @require_login
    @require_permission('parametros', 'ver')
    def parametro_items(group_id):
        grupo, items = service.obtener_grupo_y_items(group_id)

        if not grupo:
            flash('Grupo de parámetros no encontrado.', 'warning')
            return redirect(url_for('parametros_generales'))

        return render_template(
            TEMPLATE_PARAMETRO_ITEMS,
            grupo=grupo,
            items=items,
            usuario=session.get('usuario'),
            rol=session.get('rol'),
            active_page=ACTIVE_PAGE_PARAMETROS_GENERALES
        )

    @app.route('/parametros/generales/nuevo', methods=['GET', 'POST'], endpoint='nuevo_parametro')
    @require_login
    @require_permission('parametros', 'crear')
    def nuevo_parametro():
        if request.method == 'POST':
            result = service.crear_grupo(request.form.get('nombre'))

            flash(*result["flash"])

            if result["ok"]:
                return redirect(url_for('parametros_generales'))

            return redirect(url_for('nuevo_parametro'))

        return render_template(
            TEMPLATE_NUEVO_PARAMETRO,
            usuario=session.get('usuario'),
            rol=session.get('rol'),
            active_page=ACTIVE_PAGE_PARAMETROS_GENERALES
        )

    @app.route('/parametros/generales/<int:group_id>/editar', methods=['GET', 'POST'], endpoint='editar_parametro')
    @require_login
    @require_permission('parametros', 'editar')
    def editar_parametro(group_id):
        if request.method == 'POST':
            result = service.editar_grupo(group_id, request.form.get('nombre'))

            flash(*result["flash"])

            if result.get("not_found"):
                return redirect(url_for('parametros_generales'))

            if result["ok"]:
                return redirect(url_for('parametros_generales'))

            return redirect(url_for('editar_parametro', group_id=group_id))

        grupo = service.obtener_grupo(group_id)
        if not grupo:
            flash('Grupo de parámetros no encontrado.', 'warning')
            return redirect(url_for('parametros_generales'))

        return render_template(
            TEMPLATE_EDITAR_PARAMETRO,
            grupo=grupo,
            usuario=session.get('usuario'),
            rol=session.get('rol'),
            active_page=ACTIVE_PAGE_PARAMETROS_GENERALES
        )

    @app.route('/parametros/generales/<int:group_id>/eliminar', methods=['GET'], endpoint='eliminar_parametro')
    @require_login
    @require_permission('parametros', 'eliminar')
    def eliminar_parametro(group_id):
        result = service.eliminar_grupo(group_id)
        flash(*result["flash"])
        return redirect(url_for('parametros_generales'))

    @app.route('/parametros/generales/<int:group_id>/items/nuevo', methods=['GET', 'POST'], endpoint='nuevo_valor')
    @require_login
    @require_permission('parametros', 'crear')
    def nuevo_valor(group_id):
        if request.method == 'POST':
            result = service.crear_valor(
                group_id=group_id,
                nombre_raw=request.form.get('nombre'),
                valor_raw=request.form.get('valor'),
                parent_id_raw=request.form.get('parent_id'),
                activo_raw=request.form.get('activo'),
                orden_raw=request.form.get('orden'),
            )

            flash(*result["flash"])

            if result.get("not_found"):
                return redirect(url_for('parametros_generales'))

            if result["ok"]:
                return redirect(url_for('parametro_items', group_id=group_id))

            return redirect(url_for('nuevo_valor', group_id=group_id))

        grupo = service.obtener_grupo(group_id)
        if not grupo:
            flash('Grupo no encontrado.', 'warning')
            return redirect(url_for('parametros_generales'))

        return render_template(
            TEMPLATE_NUEVO_VALOR,
            grupo=grupo,
            usuario=session.get('usuario'),
            rol=session.get('rol'),
            active_page=ACTIVE_PAGE_PARAMETROS_GENERALES
        )

    @app.route('/parametros/generales/<int:group_id>/items/<int:item_id>/editar', methods=['GET', 'POST'], endpoint='editar_valor')
    @require_login
    @require_permission('parametros', 'editar')
    def editar_valor(group_id, item_id):
        if request.method == 'POST':
            result = service.editar_valor(
                group_id=group_id,
                item_id=item_id,
                nombre_raw=request.form.get('nombre'),
                valor_raw=request.form.get('valor'),
                parent_id_raw=request.form.get('parent_id'),
                activo_raw=request.form.get('activo'),
                orden_raw=request.form.get('orden'),
            )

            flash(*result["flash"])

            if result.get("not_found"):
                return redirect(url_for('parametro_items', group_id=group_id))

            if result["ok"]:
                return redirect(url_for('parametro_items', group_id=group_id))

            return redirect(url_for('editar_valor', group_id=group_id, item_id=item_id))

        item = service.obtener_item(group_id, item_id)
        if not item:
            flash('Valor no encontrado.', 'warning')
            return redirect(url_for('parametro_items', group_id=group_id))

        return render_template(
            TEMPLATE_EDITAR_VALOR,
            item=item,
            usuario=session.get('usuario'),
            rol=session.get('rol'),
            active_page=ACTIVE_PAGE_PARAMETROS_GENERALES
        )

    @app.route('/parametros/generales/<int:group_id>/items/<int:item_id>/eliminar', methods=['GET'], endpoint='eliminar_valor')
    @require_login
    @require_permission('parametros', 'eliminar')
    def eliminar_valor(group_id, item_id):
        result = service.eliminar_valor(group_id, item_id)
        flash(*result["flash"])
        return redirect(url_for('parametro_items', group_id=group_id))

    @app.get('/config/parametros/carga-masiva/plantilla', endpoint='param_carga_plantilla')
    @require_login
    @require_permission('parametros', 'editar')
    def param_carga_plantilla():
        return Response(
            CSV_TEMPLATE_TEXT,
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename={CSV_TEMPLATE_FILENAME}'
            }
        )

    @app.route('/config/parametros/carga-masiva', methods=['GET', 'POST'], endpoint='param_carga_masiva')
    @require_login
    @require_permission('parametros', 'editar')
    def param_carga_masiva():
        grupos = service.listar_grupos_para_carga()

        if request.method == 'POST':
            result = service.procesar_carga_masiva_csv(
                group_id_raw=request.form.get('group_id'),
                has_header=(request.form.get('has_header') == '1'),
                sep_raw=request.form.get('sep'),
                file_storage=request.files.get('archivo'),
            )

            flash(*result["flash"])

            if result["ok"]:
                return redirect(url_for('parametro_items', group_id=result["group_id"]))

            if result.get("all_duplicates"):
                return redirect(url_for('parametro_items', group_id=result["group_id"]))

            return render_template(
                TEMPLATE_CARGA_MASIVA,
                grupos=grupos,
                group_id=result.get("group_id"),
                usuario=session.get('usuario'),
                rol=session.get('rol'),
                active_page=ACTIVE_PAGE_PARAMETROS_GENERALES
            )

        return render_template(
            TEMPLATE_CARGA_MASIVA,
            grupos=grupos,
            usuario=session.get('usuario'),
            rol=session.get('rol'),
            active_page=ACTIVE_PAGE_PARAMETROS_GENERALES
        )