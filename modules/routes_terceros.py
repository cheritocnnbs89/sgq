# modules/routes_terceros.py
from flask import (
    render_template, request, redirect, url_for, flash, session,
    jsonify, Response
)
import csv
import io

from modules.db import get_db
from modules.security import require_login, require_permission


def _ensure_terceros_tables(conn):
    """
    SQL Server:
    El esquema ya existe en BD, así que no ejecutamos CREATE/ALTER aquí.
    Se deja como no-op para no romper la lógica existente.
    """
    # cur = conn.cursor()
    # cur.execute("""
    # IF OBJECT_ID(N'dbo.terceros', N'U') IS NULL
    # BEGIN
    #     CREATE TABLE dbo.terceros (
    #         id BIGINT IDENTITY(1,1) PRIMARY KEY,
    #         tipo NVARCHAR(1) NOT NULL,
    #         nombre NVARCHAR(255) NOT NULL,
    #         identificacion NVARCHAR(100) NULL,
    #         email NVARCHAR(255) NULL,
    #         telefono NVARCHAR(100) NULL,
    #         direccion NVARCHAR(MAX) NULL,
    #         activo BIT NOT NULL DEFAULT 1,
    #         codigo_sap NVARCHAR(100) NULL,
    #         observaciones NVARCHAR(MAX) NULL
    #     )
    # END
    # """)
    # conn.commit()
    return None


def _column_exists(conn, table, col):
    """
    SQL Server version. Se deja disponible por compatibilidad aunque no se use.
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT 1
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = ?
          AND COLUMN_NAME = ?
    """, (table, col))
    return cur.fetchone() is not None


def _add_column_if_missing(conn, table, col, decl):
    """
    SQL Server version. Se deja disponible por compatibilidad aunque no se use.
    """
    if not _column_exists(conn, table, col):
        cur = conn.cursor()
        cur.execute(f"ALTER TABLE {table} ADD {col} {decl}")
        conn.commit()


def _row_val(row, key, idx=None, default=None):
    if row is None:
        return default
    try:
        val = row[key]
        return default if val is None else val
    except Exception:
        pass
    if idx is not None:
        try:
            val = row[idx]
            return default if val is None else val
        except Exception:
            pass
    return default


def register_terceros_routes(app):

    # -------- LISTADOS --------
    @app.route('/config/clientes', methods=['GET'], endpoint='clientes')
    @require_login
    @require_permission('terceros', 'ver')
    def clientes():
        return _listar('C')

    @app.get('/terceros/proveedores/carga-masiva/plantilla', endpoint='proveedores_carga_plantilla')
    @require_login
    @require_permission('terceros', 'crear')
    def proveedores_carga_plantilla():
        """
        Descarga un CSV de ejemplo (UTF-8) con las columnas esperadas.
        """
        csv_text = (
            "nombre,identificacion,email,telefono,direccion,codigo_sap,observaciones\n"
            "Proveedor A,1790012345001,contacto@proveedor-a.com,022222222,Av. Siempre Viva 123,PA001,Obs A\n"
            "Proveedor B,0999999999,ventas@proveedor-b.com,099888777,Ofic. Centro,PB002,\n"
        )
        return Response(
            csv_text,
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=plantilla_proveedores.csv'}
        )

    @app.route('/terceros/proveedores/carga-masiva', methods=['GET', 'POST'], endpoint='proveedores_carga_masiva')
    @require_login
    @require_permission('terceros', 'crear')
    def proveedores_carga_masiva():
        """
        Carga masiva de PROVEEDORES desde CSV.

        Columnas esperadas:
        nombre, identificacion, email, telefono, direccion, codigo_sap, observaciones

        Comportamiento:
        - Si identificacion viene y YA existe para tipo='P'  -> ACTUALIZA demás campos.
        - Si identificacion viene y NO existe               -> INSERTA proveedor nuevo.
        - Si NO viene identificacion:
            * si el nombre ya existe en BD para tipo='P'    -> se omite la fila (warning).
        - Duplicadas dentro del archivo (misma identificacion o, sin id, mismo nombre):
            * se omiten como WARNING, pero NO bloquean la importación.
        - Solo errores “graves” (p.ej. sin nombre) bloquean toda la carga.
        """
        conn = get_db()
        _ensure_terceros_tables(conn)
        cur = conn.cursor()

        if request.method == 'GET':
            return render_template(
                'terceros_carga_masiva.html',
                usuario=session.get('usuario'),
                rol=session.get('rol'),
                active_page='proveedores'
            )

        file = request.files.get('archivo')
        sep = (request.form.get('sep') or ',')
        has_header = (request.form.get('has_header') == '1')

        if not file or not file.filename:
            flash('Adjunta un archivo CSV.', 'danger')
            return render_template(
                'terceros_carga_masiva.html',
                usuario=session.get('usuario'),
                rol=session.get('rol'),
                active_page='proveedores'
            )

        try:
            raw = file.stream.read()
            text = raw.decode('utf-8-sig', errors='ignore')
            reader = csv.reader(io.StringIO(text), delimiter=sep)
        except Exception as e:
            flash(f'No se pudo leer el CSV: {e}', 'danger')
            return render_template(
                'terceros_carga_masiva.html',
                usuario=session.get('usuario'),
                rol=session.get('rol'),
                active_page='proveedores'
            )

        start_line = 2 if has_header else 1
        if has_header:
            next(reader, None)

        cur.execute("""
            SELECT
                id,
                LOWER(LTRIM(RTRIM(nombre))) AS ln,
                LOWER(LTRIM(RTRIM(COALESCE(identificacion,'')))) AS lid
            FROM terceros
            WHERE tipo = 'P'
        """)
        existing_rows = cur.fetchall()

        existing_names = set()
        existing_ids_map = {}

        for r in existing_rows:
            rid = _row_val(r, 'id', 0)
            ln = _row_val(r, 'ln', 1, '')
            lid = _row_val(r, 'lid', 2, '')

            if ln:
                existing_names.add(ln)
            if lid:
                existing_ids_map[lid] = rid

        seen_names = set()
        seen_ids = set()

        rows = []
        errors = []
        warnings = []

        for i, row in enumerate(reader, start=start_line):
            nombre = (row[0] if len(row) > 0 else '').strip()
            identificacion = (row[1] if len(row) > 1 else '').strip()
            email = (row[2] if len(row) > 2 else '').strip()
            telefono = (row[3] if len(row) > 3 else '').strip()
            direccion = (row[4] if len(row) > 4 else '').strip()
            codigo_sap = (row[5] if len(row) > 5 else '').strip()
            observaciones = (row[6] if len(row) > 6 else '').strip()

            if not nombre:
                errors.append(f"Línea {i}: el campo 'nombre' es obligatorio.")
                continue

            ln = nombre.lower().strip()
            lid = identificacion.lower().strip() if identificacion else ''

            if not lid and ln in existing_names:
                warnings.append(
                    f"Línea {i}: nombre '{nombre}' ya existe en la base para un proveedor sin identificación; "
                    "fila omitida."
                )
                continue

            if lid:
                if lid in seen_ids:
                    warnings.append(
                        f"Línea {i}: identificación '{identificacion}' duplicada en el archivo; "
                        "se omitió esta ocurrencia."
                    )
                    continue
                seen_ids.add(lid)
            else:
                if ln in seen_names:
                    warnings.append(
                        f"Línea {i}: nombre '{nombre}' duplicado en el archivo (sin identificación); "
                        "se omitió esta ocurrencia."
                    )
                    continue
                seen_names.add(ln)

            rows.append({
                'linea': i,
                'nombre': nombre,
                'identificacion': identificacion,
                'ln': ln,
                'lid': lid,
                'email': email,
                'telefono': telefono,
                'direccion': direccion,
                'codigo_sap': codigo_sap,
                'observaciones': observaciones,
            })

        if errors:
            flash('Se encontraron errores; no se importó nada.', 'danger')
            for e in errors[:50]:
                flash(e, 'warning')
            return render_template(
                'terceros_carga_masiva.html',
                usuario=session.get('usuario'),
                rol=session.get('rol'),
                active_page='proveedores'
            )

        if not rows:
            if warnings:
                flash('No se importó ningún proveedor (todas las filas se omitieron).', 'warning')
                for w in warnings[:50]:
                    flash(w, 'warning')
            else:
                flash('El archivo no contenía filas válidas.', 'warning')
            return render_template(
                'terceros_carga_masiva.html',
                usuario=session.get('usuario'),
                rol=session.get('rol'),
                active_page='proveedores'
            )

        nuevos = 0
        actualizados = 0

        try:
            for r in rows:
                lid = r['lid']

                if lid and lid in existing_ids_map:
                    cur.execute("""
                        UPDATE terceros
                        SET nombre        = ?,
                            email         = ?,
                            telefono      = ?,
                            direccion     = ?,
                            codigo_sap    = ?,
                            observaciones = ?
                        WHERE id = ?
                    """, (
                        r['nombre'],
                        r['email'] or None,
                        r['telefono'] or None,
                        r['direccion'] or None,
                        r['codigo_sap'] or None,
                        r['observaciones'] or None,
                        existing_ids_map[lid],
                    ))
                    actualizados += 1
                else:
                    cur.execute("""
                        INSERT INTO terceros
                            (tipo, nombre, identificacion, email, telefono, direccion, activo, codigo_sap, observaciones)
                        VALUES
                            ('P', ?, ?, ?, ?, ?, 1, ?, ?)
                    """, (
                        r['nombre'],
                        r['identificacion'] or None,
                        r['email'] or None,
                        r['telefono'] or None,
                        r['direccion'] or None,
                        r['codigo_sap'] or None,
                        r['observaciones'] or None,
                    ))
                    nuevos += 1

            conn.commit()

            flash(
                f'Proveedores procesados: {nuevos} nuevos, {actualizados} actualizados. '
                f'Filas omitidas: {len(warnings)}.',
                'success'
            )
            for w in warnings[:50]:
                flash(w, 'warning')

        except Exception as e:
            conn.rollback()
            flash(f'No se pudo importar: {e}', 'danger')
            return render_template(
                'terceros_carga_masiva.html',
                usuario=session.get('usuario'),
                rol=session.get('rol'),
                active_page='proveedores'
            )
        finally:
            conn.close()

        return redirect(url_for('proveedores'))

    @app.route('/terceros/clientes/carga-masiva', methods=['GET', 'POST'], endpoint='clientes_carga_masiva')
    @require_login
    @require_permission('terceros', 'crear')
    def clientes_carga_masiva():
        """
        Carga masiva de CLIENTES desde CSV.

        Columnas esperadas:
        nombre, identificacion, email, telefono, direccion, codigo_sap, observaciones
        """
        conn = get_db()
        cur = conn.cursor()
        _ensure_terceros_tables(conn)

        if request.method == 'GET':
            return render_template(
                'terceros_carga_masiva.html',
                usuario=session.get('usuario'),
                rol=session.get('rol'),
                active_page='clientes'
            )

        file = request.files.get('archivo')
        sep = (request.form.get('sep') or ',')
        has_header = (request.form.get('has_header') == '1')

        if not file or not file.filename:
            flash('Adjunta un archivo CSV.', 'danger')
            return render_template(
                'terceros_carga_masiva.html',
                usuario=session.get('usuario'),
                rol=session.get('rol'),
                active_page='clientes'
            )

        try:
            raw = file.stream.read()
            text = raw.decode('utf-8-sig', errors='ignore')
            reader = csv.reader(io.StringIO(text), delimiter=sep)
        except Exception as e:
            flash(f'No se pudo leer el CSV: {e}', 'danger')
            return render_template(
                'terceros_carga_masiva.html',
                usuario=session.get('usuario'),
                rol=session.get('rol'),
                active_page='clientes'
            )

        start_line = 2 if has_header else 1
        if has_header:
            next(reader, None)

        cur.execute("""
            SELECT LOWER(LTRIM(RTRIM(nombre))) AS ln,
                   LOWER(LTRIM(RTRIM(COALESCE(identificacion,'')))) AS lid
            FROM terceros
            WHERE tipo='C'
        """)
        existing_rows = cur.fetchall()
        existing_names = set()
        existing_ids = set()

        for r in existing_rows:
            ln = _row_val(r, 'ln', 0, '')
            lid = _row_val(r, 'lid', 1, '')
            if ln:
                existing_names.add(ln)
            if lid:
                existing_ids.add(lid)

        seen_names = set()
        seen_ids = set()

        rows = []
        errors = []

        for i, row in enumerate(reader, start=start_line):
            nombre = (row[0] if len(row) > 0 else '').strip()
            identificacion = (row[1] if len(row) > 1 else '').strip()
            email = (row[2] if len(row) > 2 else '').strip()
            telefono = (row[3] if len(row) > 3 else '').strip()
            direccion = (row[4] if len(row) > 4 else '').strip()
            codigo_sap = (row[5] if len(row) > 5 else '').strip()
            observaciones = (row[6] if len(row) > 6 else '').strip()

            if not nombre:
                errors.append(f"Línea {i}: el campo 'nombre' es obligatorio.")
                continue

            ln = nombre.lower().strip()
            lid = identificacion.lower().strip() if identificacion else ''

            if lid and lid in existing_ids:
                errors.append(f"Línea {i}: identificación '{identificacion}' ya existe en la base para un cliente.")
                continue
            if not lid and ln in existing_names:
                errors.append(f"Línea {i}: nombre '{nombre}' ya existe en la base para un cliente.")
                continue

            if lid:
                if lid in seen_ids:
                    errors.append(f"Línea {i}: identificación '{identificacion}' duplicada en el archivo.")
                    continue
                seen_ids.add(lid)
            else:
                if ln in seen_names:
                    errors.append(f"Línea {i}: nombre '{nombre}' duplicado en el archivo.")
                    continue
                seen_names.add(ln)

            rows.append((
                'C',
                nombre,
                identificacion or None,
                email or None,
                telefono or None,
                direccion or None,
                1,
                codigo_sap or None,
                observaciones or None
            ))

        if errors:
            flash('Se encontraron errores; no se importó nada.', 'danger')
            for e in errors[:50]:
                flash(e, 'warning')
            return render_template(
                'terceros_carga_masiva.html',
                usuario=session.get('usuario'),
                rol=session.get('rol'),
                active_page='clientes'
            )

        if not rows:
            flash('El archivo no contenía filas válidas.', 'warning')
            return render_template(
                'terceros_carga_masiva.html',
                usuario=session.get('usuario'),
                rol=session.get('rol'),
                active_page='clientes'
            )

        try:
            cur.executemany("""
                INSERT INTO terceros
                    (tipo, nombre, identificacion, email, telefono, direccion, activo, codigo_sap, observaciones)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, rows)
            conn.commit()
            flash(f'Importados {len(rows)} clientes.', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'No se pudo importar: {e}', 'danger')
            return render_template(
                'terceros_carga_masiva.html',
                usuario=session.get('usuario'),
                rol=session.get('rol'),
                active_page='clientes'
            )
        finally:
            conn.close()

        return redirect(url_for('clientes'))

    @app.route('/config/proveedores', methods=['GET'], endpoint='proveedores')
    @require_login
    @require_permission('terceros', 'ver')
    def proveedores():
        return _listar('P')

    def _listar(tipo):
        conn = get_db()
        _ensure_terceros_tables(conn)
        cur = conn.cursor()
        cur.execute("SELECT * FROM terceros WHERE tipo = ? ORDER BY nombre", (tipo,))
        rows = cur.fetchall()
        conn.close()

        active = 'clientes' if tipo == 'C' else 'proveedores'
        return render_template(
            'terceros_list.html',
            tipo=tipo,
            terceros=rows,
            usuario=session.get('usuario'),
            rol=session.get('rol'),
            active_page=active
        )

    # -------- CREAR --------
    @app.route('/config/terceros/nuevo/<tipo>', methods=['GET', 'POST'], endpoint='tercero_nuevo')
    @require_login
    @require_permission('terceros', 'crear')
    def tercero_nuevo(tipo):
        if tipo not in ('C', 'P'):
            flash('Tipo inválido.', 'warning')
            return redirect(url_for('clientes'))

        if request.method == 'POST':
            data = {
                'tipo': tipo,
                'nombre': (request.form.get('nombre') or '').strip(),
                'identificacion': (request.form.get('identificacion') or '').strip(),
                'email': (request.form.get('email') or '').strip(),
                'telefono': (request.form.get('telefono') or '').strip(),
                'direccion': (request.form.get('direccion') or '').strip(),
                'codigo_sap': (request.form.get('codigo_sap') or '').strip(),
                'observaciones': (request.form.get('observaciones') or '').strip(),
                'activo': 1 if request.form.get('activo') == 'on' else 0
            }

            if not data['nombre']:
                flash('El nombre es obligatorio.', 'warning')
            else:
                conn = get_db()
                _ensure_terceros_tables(conn)
                cur = conn.cursor()
                try:
                    cur.execute("""
                        INSERT INTO terceros
                            (tipo, nombre, identificacion, email, telefono, direccion, codigo_sap, observaciones, activo)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        data['tipo'],
                        data['nombre'],
                        data['identificacion'] or None,
                        data['email'] or None,
                        data['telefono'] or None,
                        data['direccion'] or None,
                        data['codigo_sap'] or None,
                        data['observaciones'] or None,
                        data['activo']
                    ))
                    conn.commit()
                    flash('Guardado.', 'success')
                except Exception:
                    conn.rollback()
                    flash('No se pudo guardar (¿duplicado?).', 'danger')
                finally:
                    conn.close()

                return redirect(url_for('clientes' if tipo == 'C' else 'proveedores'))

        return render_template(
            'tercero_form.html',
            tipo=tipo,
            item=None,
            usuario=session.get('usuario'),
            rol=session.get('rol'),
            active_page=('clientes' if tipo == 'C' else 'proveedores')
        )

    # -------- EDITAR --------
    @app.route('/config/terceros/<int:tid>/editar', methods=['GET', 'POST'], endpoint='tercero_editar')
    @require_login
    @require_permission('terceros', 'editar')
    def tercero_editar(tid):
        conn = get_db()
        _ensure_terceros_tables(conn)
        cur = conn.cursor()
        cur.execute("SELECT * FROM terceros WHERE id = ?", (tid,))
        item = cur.fetchone()

        if not item:
            conn.close()
            flash('Registro no existe.', 'warning')
            return redirect(url_for('clientes'))

        try:
            tipo = item['tipo']
        except Exception:
            tipo = item[1]

        if request.method == 'POST':
            nombre = (request.form.get('nombre') or '').strip()
            if not nombre:
                flash('El nombre es obligatorio.', 'warning')
            else:
                try:
                    cur.execute("""
                        UPDATE terceros
                        SET nombre = ?,
                            identificacion = ?,
                            email = ?,
                            telefono = ?,
                            direccion = ?,
                            codigo_sap = ?,
                            observaciones = ?,
                            activo = ?
                        WHERE id = ?
                    """, (
                        nombre,
                        (request.form.get('identificacion') or '').strip() or None,
                        (request.form.get('email') or '').strip() or None,
                        (request.form.get('telefono') or '').strip() or None,
                        (request.form.get('direccion') or '').strip() or None,
                        (request.form.get('codigo_sap') or '').strip() or None,
                        (request.form.get('observaciones') or '').strip() or None,
                        1 if request.form.get('activo') == 'on' else 0,
                        tid
                    ))
                    conn.commit()
                    flash('Actualizado.', 'success')
                except Exception:
                    conn.rollback()
                    flash('No se pudo actualizar.', 'danger')
                finally:
                    conn.close()

                return redirect(url_for('clientes' if tipo == 'C' else 'proveedores'))

        conn.close()
        return render_template(
            'tercero_form.html',
            tipo=tipo,
            item=item,
            usuario=session.get('usuario'),
            rol=session.get('rol'),
            active_page=('clientes' if tipo == 'C' else 'proveedores')
        )

    # -------- ELIMINAR --------
    @app.route('/config/terceros/<int:tid>/eliminar', methods=['POST'], endpoint='tercero_eliminar')
    @require_login
    @require_permission('terceros', 'eliminar')
    def tercero_eliminar(tid):
        conn = get_db()
        _ensure_terceros_tables(conn)
        cur = conn.cursor()
        cur.execute("SELECT tipo FROM terceros WHERE id = ?", (tid,))
        row = cur.fetchone()

        if not row:
            conn.close()
            flash('Registro no existe.', 'warning')
            return redirect(url_for('clientes'))

        try:
            tipo = row['tipo']
        except Exception:
            tipo = row[0]

        try:
            cur.execute("DELETE FROM terceros WHERE id = ?", (tid,))
            conn.commit()
            flash('Eliminado.', 'success')
        except Exception:
            conn.rollback()
            flash('No se pudo eliminar.', 'danger')
        finally:
            conn.close()

        return redirect(url_for('clientes' if tipo == 'C' else 'proveedores'))