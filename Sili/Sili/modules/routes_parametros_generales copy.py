# modules/routes_parametros_generales.py
from flask import render_template, request, redirect, url_for, flash, session
from .db import get_db
from .security import require_login, require_permission
# modules/routes_parametros_generales.py (o el que uses)
import csv, io, os
from flask import request, render_template, redirect, url_for, flash, Response
from modules.db import get_db
from modules.security import require_login, require_permission

# ------------------ Helpers ------------------
def _ensure_param_tables(conn):
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS param_groups(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS param_values(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            nombre TEXT NOT NULL,
            valor TEXT,
            FOREIGN KEY(group_id) REFERENCES param_groups(id)
        )
    """)
    # 🔒 Evita duplicados de nombre dentro del mismo grupo (case-insensitive)
  
    conn.commit()


# --------------- Registro de rutas ---------------
def register_parametros_generales_routes(app):

    # LISTA DE GRUPOS
    @app.route('/parametros/generales', methods=['GET'], endpoint='parametros_generales')
    @require_login
    @require_permission('parametros', 'ver')
    def parametros_generales():
        conn = get_db(); cur = conn.cursor()
        _ensure_param_tables(conn)
        cur.execute("SELECT id, nombre FROM param_groups ORDER BY nombre")
        grupos = cur.fetchall()
        # (opcional) también enviamos todos los valores por si tu template los usa
        cur.execute("SELECT id, group_id, nombre, valor FROM param_values ORDER BY nombre")
        valores = cur.fetchall()
        conn.close()
        return render_template(
            'parametros_generales.html',
            grupos=grupos,
            valores=valores,
            usuario=session.get('usuario'),
            rol=session.get('rol'),
            active_page='parametros_generales'
        )

    # Alias opcional para compatibilidad antigua (NO pisa el endpoint real)
    @app.route('/parametros_generales', methods=['GET'], endpoint='parametros_generales_alias')
    @require_login
    @require_permission('parametros', 'ver')
    def parametros_generales_alias():
        return redirect(url_for('parametros_generales'))

    # LISTAR ITEMS/VALORES DE UN GRUPO
    @app.route('/parametros/generales/<int:group_id>/items', methods=['GET'], endpoint='parametro_items')
    @require_login
    @require_permission('parametros', 'ver')
    def parametro_items(group_id):
        conn = get_db(); cur = conn.cursor()
        _ensure_param_tables(conn)

        cur.execute("SELECT id, nombre FROM param_groups WHERE id=?", (group_id,))
        grupo = cur.fetchone()
        if not grupo:
            conn.close()
            flash('Grupo de parámetros no encontrado.', 'warning')
            return redirect(url_for('parametros_generales'))

        cur.execute("""
            SELECT id, nombre, valor
            FROM param_values
            WHERE group_id=?
            ORDER BY nombre
        """, (group_id,))
        items = cur.fetchall()
        conn.close()

        return render_template(
            'parametro_items.html',   # tabla con los valores del grupo
            grupo=grupo,
            items=items,
            usuario=session.get('usuario'),
            rol=session.get('rol'),
            active_page='parametros_generales'
        )
    # CREAR NUEVO GRUPO (param_groups)
    @app.route('/parametros/generales/nuevo', methods=['GET', 'POST'], endpoint='nuevo_parametro')
    @require_login
    @require_permission('parametros', 'crear')
    def nuevo_parametro():
        conn = get_db()
        _ensure_param_tables(conn)
        cur = conn.cursor()

        if request.method == 'POST':
            nombre = (request.form.get('nombre') or '').strip()
            if not nombre:
                conn.close()
                flash('El nombre del parámetro es obligatorio.', 'warning')
                return redirect(url_for('nuevo_parametro'))

            try:
                cur.execute("INSERT INTO param_groups(nombre) VALUES (?)", (nombre,))
                conn.commit()
                flash('Parámetro (grupo) creado correctamente.', 'success')
                return redirect(url_for('parametros_generales'))
            except sqlite3.IntegrityError:
                conn.rollback()
                flash('Ya existe un parámetro con ese nombre.', 'danger')
                return redirect(url_for('nuevo_parametro'))
            except Exception as e:
                conn.rollback()
                flash(f'No se pudo crear el parámetro: {e}', 'danger')
                return redirect(url_for('nuevo_parametro'))
            finally:
                conn.close()

        conn.close()
        return render_template(
            'nuevo_parametro.html',
            usuario=session.get('usuario'),
            rol=session.get('rol'),
            active_page='parametros_generales'
        )

    # EDITAR NOMBRE DEL GRUPO
    @app.route('/parametros/generales/<int:group_id>/editar', methods=['GET','POST'], endpoint='editar_parametro')
    @require_login
    @require_permission('parametros', 'editar')
    def editar_parametro(group_id):
        conn = get_db(); cur = conn.cursor()
        _ensure_param_tables(conn)

        cur.execute("SELECT id, nombre FROM param_groups WHERE id=?", (group_id,))
        grupo = cur.fetchone()
        if not grupo:
            conn.close()
            flash('Grupo de parámetros no encontrado.', 'warning')
            return redirect(url_for('parametros_generales'))

        if request.method == 'POST':
            nuevo_nombre = (request.form.get('nombre') or '').strip()
            if not nuevo_nombre:
                conn.close()
                flash('El nombre es obligatorio.', 'warning')
                return redirect(url_for('editar_parametro', group_id=group_id))
            try:
                cur.execute("UPDATE param_groups SET nombre=? WHERE id=?", (nuevo_nombre, group_id))
                conn.commit()
                flash('Grupo actualizado.', 'success')
                return redirect(url_for('parametros_generales'))
            except Exception:
                conn.rollback()
                flash('No se pudo actualizar (¿nombre duplicado?).', 'danger')
                return redirect(url_for('editar_parametro', group_id=group_id))
            finally:
                conn.close()

        conn.close()
        return render_template(
            'editar_parametro.html',
            grupo=grupo,
            usuario=session.get('usuario'),
            rol=session.get('rol'),
            active_page='parametros_generales'
        )

    # ELIMINAR GRUPO (y sus valores) — idealmente por POST, pero aquí dejamos GET por compatibilidad con tu enlace
    @app.route('/parametros/generales/<int:group_id>/eliminar', methods=['GET'], endpoint='eliminar_parametro')
    @require_login
    @require_permission('parametros', 'eliminar')
    def eliminar_parametro(group_id):
        conn = get_db(); cur = conn.cursor()
        _ensure_param_tables(conn)
        try:
            cur.execute("DELETE FROM param_values WHERE group_id=?", (group_id,))
            cur.execute("DELETE FROM param_groups WHERE id=?", (group_id,))
            conn.commit()
            flash('Grupo eliminado.', 'success')
        except Exception:
            conn.rollback()
            flash('No se pudo eliminar el grupo.', 'danger')
        finally:
            conn.close()
        return redirect(url_for('parametros_generales'))

    # NUEVO VALOR dentro de un grupo
    @app.route('/parametros/generales/<int:group_id>/items/nuevo', methods=['GET','POST'], endpoint='nuevo_valor')
    @require_login
    @require_permission('parametros', 'crear')
    def nuevo_valor(group_id):
        conn = get_db(); cur = conn.cursor()
        _ensure_param_tables(conn)

        cur.execute("SELECT id, nombre FROM param_groups WHERE id=?", (group_id,))
        grupo = cur.fetchone()
        if not grupo:
            conn.close()
            flash('Grupo no encontrado.', 'warning')
            return redirect(url_for('parametros_generales'))

        if request.method == 'POST':
            nombre = (request.form.get('nombre') or '').strip()
            valor  = (request.form.get('valor') or '').strip()
            if not nombre:
                conn.close()
                flash('El nombre es obligatorio.', 'warning')
                return redirect(url_for('nuevo_valor', group_id=group_id))
            try:
                cur.execute(
                    "INSERT INTO param_values (group_id, nombre, valor) VALUES (?,?,?)",
                    (group_id, nombre, valor)
                )
                conn.commit()
                flash('Valor creado.', 'success')
                return redirect(url_for('parametro_items', group_id=group_id))
            except Exception:
                conn.rollback()
                flash('No se pudo crear el valor (¿duplicado?).', 'danger')
                return redirect(url_for('nuevo_valor', group_id=group_id))
            finally:
                conn.close()

        conn.close()
        return render_template(
            'nuevo_valor.html',
            grupo=grupo,
            usuario=session.get('usuario'),
            rol=session.get('rol'),
            active_page='parametros_generales'
        )

    # EDITAR VALOR de un grupo (usa tu editar_valor.html)
    @app.route('/parametros/generales/<int:group_id>/items/<int:item_id>/editar', methods=['GET','POST'], endpoint='editar_valor')
    @require_login
    @require_permission('parametros', 'editar')
    def editar_valor(group_id, item_id):
        conn = get_db(); cur = conn.cursor()
        _ensure_param_tables(conn)

        cur.execute("""
            SELECT pv.id, pv.group_id, pv.nombre, pv.valor, pg.nombre AS grupo_nombre
            FROM param_values pv
            JOIN param_groups pg ON pg.id = pv.group_id
            WHERE pv.id=? AND pv.group_id=?
        """, (item_id, group_id))
        item = cur.fetchone()
        if not item:
            conn.close()
            flash('Valor no encontrado.', 'warning')
            return redirect(url_for('parametro_items', group_id=group_id))

        if request.method == 'POST':
            nombre = (request.form.get('nombre') or '').strip()
            valor  = (request.form.get('valor') or '').strip()
            if not nombre:
                conn.close()
                flash('El nombre es obligatorio.', 'warning')
                return redirect(url_for('editar_valor', group_id=group_id, item_id=item_id))
            try:
                cur.execute("UPDATE param_values SET nombre=?, valor=? WHERE id=?", (nombre, valor, item_id))
                conn.commit()
                flash('Valor actualizado.', 'success')
                return redirect(url_for('parametro_items', group_id=group_id))
            except Exception:
                conn.rollback()
                flash('No se pudo actualizar (¿duplicado?).', 'danger')
                return redirect(url_for('editar_valor', group_id=group_id, item_id=item_id))
            finally:
                conn.close()

        conn.close()
        return render_template(
            'editar_valor.html',   # tu plantilla
            item=item,
            usuario=session.get('usuario'),
            rol=session.get('rol'),
            active_page='parametros_generales'
        )

    # ELIMINAR VALOR
    @app.route('/parametros/generales/<int:group_id>/items/<int:item_id>/eliminar', methods=['GET'], endpoint='eliminar_valor')
    @require_login
    @require_permission('parametros', 'eliminar')
    def eliminar_valor(group_id, item_id):
        conn = get_db(); cur = conn.cursor()
        _ensure_param_tables(conn)
        try:
            cur.execute("DELETE FROM param_values WHERE id=? AND group_id=?", (item_id, group_id))
            conn.commit()
            flash('Valor eliminado.', 'success')
        except Exception:
            conn.rollback()
            flash('No se pudo eliminar.', 'danger')
        finally:
            conn.close()
        return redirect(url_for('parametro_items', group_id=group_id))



    @app.get('/config/parametros/carga-masiva/plantilla', endpoint='param_carga_plantilla')
    @require_login
    @require_permission('parametros', 'editar')
    def param_carga_plantilla():
        csv_text = "nombre,valor\nEjemplo 1,100\nEjemplo 2,200\n"
        return Response(
            csv_text,
            mimetype='text/csv',
            headers={'Content-Disposition':'attachment; filename=plantilla_param_values.csv'}
        )

    @app.route('/config/parametros/carga-masiva', methods=['GET','POST'], endpoint='param_carga_masiva')
    @require_login
    @require_permission('parametros', 'editar')
    def param_carga_masiva():
        conn = get_db(); cur = conn.cursor()
        grupos = [dict(r) for r in cur.execute("SELECT id, nombre FROM param_groups ORDER BY nombre").fetchall()]

        if request.method == 'POST':
            group_id_raw = (request.form.get('group_id') or '').strip()
            has_header   = (request.form.get('has_header') == '1')
            sep          = (request.form.get('sep') or ',')
            file         = request.files.get('archivo')

            if not group_id_raw.isdigit():
                flash('Seleccione un grupo válido.', 'danger')
                return render_template('parametros_carga_masiva.html', grupos=grupos)

            group_id = int(group_id_raw)

            if not file or not file.filename:
                flash('Adjunte un archivo CSV.', 'danger')
                return render_template('parametros_carga_masiva.html', grupos=grupos, group_id=group_id)

            # Lee CSV (UTF-8 con BOM tolerado)
            try:
                raw = file.stream.read()
                text = raw.decode('utf-8-sig', errors='ignore')
                reader = csv.reader(io.StringIO(text), delimiter=sep)
            except Exception as e:
                flash(f'No se pudo leer el CSV: {e}', 'danger')
                return render_template('parametros_carga_masiva.html', grupos=grupos, group_id=group_id)

            rows_to_insert = []
            try:
                if has_header:
                    next(reader, None)  # descarta encabezado

                for idx, row in enumerate(reader, start=1):
                    if not row:
                        continue
                    nombre = (row[0] if len(row) > 0 else '').strip()
                    valor  = (row[1] if len(row) > 1 else None)
                    valor  = (valor.strip() if isinstance(valor, str) else valor)

                    if not nombre:
                        # fila vacía o sin nombre -> ignora
                        continue
                    rows_to_insert.append((group_id, nombre, valor))
            except Exception as e:
                flash(f'Fila {idx}: {e}', 'danger')
                return render_template('parametros_carga_masiva.html', grupos=grupos, group_id=group_id)

            if not rows_to_insert:
                flash('El archivo no contenía filas válidas.', 'warning')
                return render_template('parametros_carga_masiva.html', grupos=grupos, group_id=group_id)

            # Opcional: evitar duplicados por (group_id, nombre)
            existentes = {
                r['nombre'].lower(): True
                for r in cur.execute("SELECT nombre FROM param_values WHERE group_id=?", (group_id,)).fetchall()
            }
            rows_to_insert = [r for r in rows_to_insert if r[1].lower() not in existentes]

            if not rows_to_insert:
                flash('Todos los nombres ya existían para ese grupo; no se importó nada.', 'info')
                return redirect(url_for('parametro_items', group_id=group_id))

            # INSERT masivo: deja que SQLite asigne id (recomendado)
            try:
                cur.executemany(
                    "INSERT INTO param_values (group_id, nombre, valor) VALUES (?,?,?)",
                    rows_to_insert
                )
                conn.commit()
                flash(f'Importadas {len(rows_to_insert)} filas.', 'success')
            except Exception as e:
                conn.rollback()
                flash(f'No se pudo importar: {e}', 'danger')
                return render_template('parametros_carga_masiva.html', grupos=grupos, group_id=group_id)
            finally:
                conn.close()

            return redirect(url_for('parametro_items', group_id=group_id))

        # GET
        conn.close()
        return render_template('parametros_carga_masiva.html', grupos=grupos)