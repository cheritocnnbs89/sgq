# modules/routes_roles.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from flask import render_template, request, redirect, url_for, flash, session, current_app

from .db import get_db
from .security import require_login


def _is_admin() -> bool:
    return (session.get('rol') or '').strip().lower() == 'admin'


def _usuarios_con_rol(cur, nombre: str) -> int:
    cur.execute("""
        SELECT COUNT(*) AS n FROM usuarios
        WHERE LOWER(LTRIM(RTRIM(rol))) = LOWER(LTRIM(RTRIM(?)))
    """, (nombre,))
    row = cur.fetchone()
    return int((row['n'] if row else 0) or 0)


def register_roles_routes(app):
    """
    Catálogo de roles del sistema. Antes solo existía la tabla `roles` en la
    base, poblada implícitamente al usar la pantalla de Roles y permisos —
    aquí se administra explícitamente (crear/renombrar/eliminar).

    Solo admin: renombrar/eliminar un rol afecta a todos los usuarios que lo
    tienen asignado y, para los roles ya usados en el código (admin, jefe,
    gerente, gerente general, gerente financiero, coordinador, usuario),
    también hay comparaciones de texto directas fuera de este catálogo que
    no se actualizan solas al renombrar.
    """

    @app.route('/roles', methods=['GET', 'POST'], endpoint='roles')
    @require_login
    def roles_list_create():
        if not _is_admin():
            flash('Solo un administrador puede gestionar roles.', 'danger')
            return redirect(url_for('dashboard'))

        conn = get_db()
        cur = conn.cursor()

        if request.method == 'POST':
            nombre = (request.form.get('nombre') or '').strip().lower()
            if not nombre:
                conn.close()
                flash('El nombre del rol es obligatorio.', 'warning')
                return redirect(url_for('roles'))

            cur.execute("""
                SELECT id FROM roles WHERE LOWER(LTRIM(RTRIM(nombre))) = ?
            """, (nombre,))
            if cur.fetchone():
                conn.close()
                flash('Ya existe un rol con ese nombre.', 'warning')
                return redirect(url_for('roles'))

            try:
                cur.execute("INSERT INTO roles (nombre) VALUES (?)", (nombre,))
                conn.commit()
                flash('Rol creado correctamente.', 'success')
            except Exception:
                conn.rollback()
                current_app.logger.exception("Error creando rol")
                flash('No se pudo crear el rol.', 'danger')
            finally:
                conn.close()
            return redirect(url_for('roles'))

        cur.execute("SELECT id, nombre FROM roles ORDER BY nombre")
        roles_rows = cur.fetchall()
        roles_view = [
            {"id": r["id"], "nombre": r["nombre"], "usuarios_count": _usuarios_con_rol(cur, r["nombre"])}
            for r in roles_rows
        ]
        conn.close()

        return render_template(
            'roles.html',
            roles=roles_view,
            usuario=session.get('usuario'),
            rol=session.get('rol'),
            active_page='roles',
        )

    @app.route('/roles/<int:rid>/editar', methods=['GET', 'POST'], endpoint='editar_rol')
    @require_login
    def editar_rol(rid):
        if not _is_admin():
            flash('Solo un administrador puede gestionar roles.', 'danger')
            return redirect(url_for('dashboard'))

        conn = get_db()
        cur = conn.cursor()

        cur.execute("SELECT id, nombre FROM roles WHERE id = ?", (rid,))
        r = cur.fetchone()
        if not r:
            conn.close()
            flash('Rol no encontrado.', 'warning')
            return redirect(url_for('roles'))

        if request.method == 'GET':
            usuarios_count = _usuarios_con_rol(cur, r['nombre'])
            conn.close()
            return render_template(
                'roles_editar.html',
                r=r,
                usuarios_count=usuarios_count,
                usuario=session.get('usuario'),
                rol=session.get('rol'),
                active_page='roles',
            )

        nuevo_nombre = (request.form.get('nombre') or '').strip().lower()
        if not nuevo_nombre:
            conn.close()
            flash('El nombre del rol es obligatorio.', 'warning')
            return redirect(url_for('editar_rol', rid=rid))

        nombre_anterior = r['nombre']

        cur.execute("""
            SELECT id FROM roles WHERE LOWER(LTRIM(RTRIM(nombre))) = ? AND id != ?
        """, (nuevo_nombre, rid))
        if cur.fetchone():
            conn.close()
            flash('Ya existe otro rol con ese nombre.', 'warning')
            return redirect(url_for('editar_rol', rid=rid))

        try:
            cur.execute("UPDATE roles SET nombre = ? WHERE id = ?", (nuevo_nombre, rid))
            cur.execute("""
                UPDATE usuarios SET rol = ?
                WHERE LOWER(LTRIM(RTRIM(rol))) = LOWER(LTRIM(RTRIM(?)))
            """, (nuevo_nombre, nombre_anterior))
            afectados = cur.rowcount
            conn.commit()
            flash(f'Rol actualizado. Se actualizaron {afectados} usuario(s) con ese rol.', 'success')
        except Exception:
            conn.rollback()
            current_app.logger.exception("Error renombrando rol")
            flash('No se pudo actualizar el rol.', 'danger')
        finally:
            conn.close()

        return redirect(url_for('roles'))

    @app.route('/roles/<int:rid>/eliminar', methods=['POST'], endpoint='eliminar_rol')
    @require_login
    def eliminar_rol(rid):
        if not _is_admin():
            flash('Solo un administrador puede gestionar roles.', 'danger')
            return redirect(url_for('dashboard'))

        conn = get_db()
        cur = conn.cursor()

        cur.execute("SELECT id, nombre FROM roles WHERE id = ?", (rid,))
        r = cur.fetchone()
        if not r:
            conn.close()
            flash('Rol no encontrado.', 'warning')
            return redirect(url_for('roles'))

        usuarios_count = _usuarios_con_rol(cur, r['nombre'])
        if usuarios_count > 0:
            conn.close()
            flash(f'No se puede eliminar: {usuarios_count} usuario(s) tienen asignado este rol.', 'danger')
            return redirect(url_for('roles'))

        try:
            cur.execute("DELETE FROM roles_permisos WHERE rol_id = ?", (rid,))
            cur.execute("DELETE FROM roles WHERE id = ?", (rid,))
            conn.commit()
            flash('Rol eliminado correctamente.', 'success')
        except Exception:
            conn.rollback()
            current_app.logger.exception("Error eliminando rol")
            flash('No se pudo eliminar el rol.', 'danger')
        finally:
            conn.close()

        return redirect(url_for('roles'))
