# modules/routes_aliases.py
from flask import redirect, url_for, render_template
from .security import require_login, require_permission

def register_aliases(app):
    """
    Capa de compatibilidad con endpoints usados en tus plantillas antiguas.
    1) Aliases con redirect a endpoints reales ya registrados.
    2) Placeholders (opcional) para páginas que tu menú llama pero aún no existen.
    """

    # --- 1) Aliases -> redirigen a endpoints existentes ---
    alias_map = {
        # antes se llamaban así en plantilla:
        #'parametros_generales': 'config',
        'parametros': 'parametros_generales',
        'tareas': 'listar_tareas',   # tu listado de tareas ya existe con ese endpoint
        
    }

    for alias, target in alias_map.items():
        if alias not in app.view_functions and target in app.view_functions:
            def _make_alias(alias_name, target_name):
                @require_login
                def _alias_view():
                    return redirect(url_for(target_name))
                _alias_view.__name__ = f'alias_{alias_name}'
                return _alias_view
            view = _make_alias(alias, target)
            # usamos misma URL que el alias (p.ej. /tareas), pero endpoint=alias
            # si esa URL ya existe con otro endpoint, no se registrará.
            try:
                app.add_url_rule(f'/{alias}', endpoint=alias, view_func=view, methods=['GET'])
            except Exception:
                # si la ruta ya existía, ignoramos
                pass

    # --- 2) Placeholders de vistas comunes en menús ---
    # (si ya tienes una vista real para cada uno, elimina el placeholder correspondiente)
    placeholders = [
        # endpoint, plantilla, permiso.opcion, accion
        ('seguridad', 'seguridad.html', 'seguridad', 'ver'),
        ('politicas_seguridad', 'politicas_seguridad.html', 'seguridad', 'ver'),
        ('reembolsos', 'reembolsos.html', 'reembolsos', 'ver'),
        ('reembolsos_efectivo', 'reembolsos_efectivo.html', 'reembolsos_efectivo', 'ver'),
        ('gastos_tarjeta', 'gastos_tarjeta.html', 'gastos_tarjeta', 'ver'),
    ]

    for ep, tpl, perm_opcion, _accion in placeholders:
        if ep not in app.view_functions:
            def _make_view(endpoint_name, template_name, perm_opcion_name):
                @require_login
                @require_permission(perm_opcion_name, 'ver')
                def _view():
                    # Si no tienes la plantilla real todavía, crea un HTML simple para evitar error.
                    try:
                        return render_template(template_name)
                    except Exception:
                        # Fallback súper básico por si la plantilla no existe aún.
                        return f"<h1>{endpoint_name.replace('_',' ').title()}</h1>"
                _view.__name__ = f'view_{endpoint_name}'
                return _view
            view = _make_view(ep, tpl, perm_opcion)
            try:
                app.add_url_rule(f'/{ep}', endpoint=ep, view_func=view, methods=['GET'])
            except Exception:
                pass
