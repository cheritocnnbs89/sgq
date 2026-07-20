# modules/routes_puestos.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import io
import sqlite3

from flask import (
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    current_app,
)

from .db import get_db
from .security import (
    require_login,
    require_permission,
    has_permission as _has_permission,
)

#
# ========= Helpers internos de esquema =========
#

def _col_names(conn, table: str) -> set[str]:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return {row["name"] for row in cur.fetchall()}


def ensure_puestos_schema(conn):
    """
    Crea la tabla `puestos` si no existe y aplica migraciones suaves.
    Columnas esperadas:
      id, codigo, nombre, descripcion, activo
    """
    cur = conn.cursor()

    # base mínima
    cur.execute("""
        CREATE TABLE IF NOT EXISTS puestos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            activo INTEGER DEFAULT 1
        )
    """)

    cols = _col_names(conn, "puestos")

    if "codigo" not in cols:
        cur.execute("ALTER TABLE puestos ADD COLUMN codigo TEXT")

    if "descripcion" not in cols:
        cur.execute("ALTER TABLE puestos ADD COLUMN descripcion TEXT")

    if "activo" not in cols:
        cur.execute("ALTER TABLE puestos ADD COLUMN activo INTEGER DEFAULT 1")

    # índice único en codigo
    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_puestos_codigo_unique
        ON puestos(codigo)
    """)

    conn.commit()


#
# ========= Helpers de orden / permisos para la vista =========
#

_VALID_SORT = {
    "codigo": "codigo",
    "nombre": "nombre",
    "activo": "activo",
}


def _order_clause(sort: str | None, direction: str | None) -> str:
    s = _VALID_SORT.get((sort or "").lower(), "nombre")
    d = "DESC" if (direction or "").lower() == "desc" else "ASC"
    return f"{s} {d}"


def _can(mod: str, action: str = "ver") -> bool:
    """
    Revisa permiso del usuario actual sobre el módulo/acción.
    Defiende contra diferencias de firma de has_permission()
    y hace fallback a session['permissions'].
    """
    # superadmin / admin
    if session.get('rol') == 'admin' or session.get('is_admin'):
        return True

    # intento #1: has_permission(mod, action)
    try:
        return bool(_has_permission(mod, action))
    except TypeError:
        pass
    except Exception:
        pass

    # intento #2: has_permission(mod) (firma vieja)
    try:
        return bool(_has_permission(mod))
    except TypeError:
        pass
    except Exception:
        pass

    # intento #3: leer directamente session['permissions']
    perms = session.get('permissions', {})
    mod_perms = perms.get(mod, {})
    if isinstance(mod_perms, dict):
        return bool(mod_perms.get(action))

    return False


#
# ========= Registro de rutas =========
#

def register_puestos_routes(app):
    """
    Debes llamar a register_puestos_routes(app) en app.py
    después de crear la app.
    """

    # -----------------------------------------------------------------
    # LISTAR / CREAR NUEVO PUESTO
    # GET  /puestos      -> lista con filtros, paginación
    # POST /puestos      -> crear nuevo
    # -----------------------------------------------------------------
    @app.route('/puestos', methods=['GET', 'POST'], endpoint='puestos')
    @require_login
    @require_permission('puestos', 'ver')
    def puestos_list_create():
        conn = get_db()
        ensure_puestos_schema(conn)
        cur = conn.cursor()

        # ----- CREAR -----
        if request.method == 'POST':
            if not _can('puestos', 'crear'):
                conn.close()
                flash('No tiene permisos para crear puestos.', 'warning')
                return redirect(url_for('puestos'))

            codigo = (request.form.get('codigo') or '').strip()
            nombre = (request.form.get('nombre') or '').strip()
            descripcion = (request.form.get('descripcion') or '').strip()

            if not codigo or not nombre:
                conn.close()
                flash('Código y nombre son obligatorios.', 'warning')
                return redirect(url_for('puestos'))

            try:
                cur.execute(
                    """
                    INSERT INTO puestos (codigo, nombre, descripcion, activo)
                    VALUES (?, ?, ?, 1)
                    """,
                    (codigo, nombre, descripcion)
                )
                conn.commit()
                flash('Puesto creado correctamente.', 'success')
            except Exception as e:
                conn.rollback()
                current_app.logger.exception(e)
                flash('No se pudo crear: código o nombre ya existen.', 'danger')
            finally:
                conn.close()

            return redirect(url_for('puestos'))

        # ----- LISTAR -----
        q = (request.args.get('q') or '').strip()
        solo_activos = (request.args.get('solo_activos') or '1') in ('1', 'true', 'on')

        sort = request.args.get('sort') or 'nombre'
        direction = request.args.get('dir') or 'asc'
        order_by = _order_clause(sort, direction)

        # paginación
        try:
            per_page = max(5, min(100, int(request.args.get('per_page', 12))))
        except ValueError:
            per_page = 12
        try:
            page = max(1, int(request.args.get('page', 1)))
        except ValueError:
            page = 1
        offset = (page - 1) * per_page

        # filtros dinámicos
        where_clauses = []
        args = []

        if q:
            like = f"%{q}%"
            where_clauses.append(
                "("
                "LOWER(codigo) LIKE LOWER(?) OR "
                "LOWER(nombre) LIKE LOWER(?) OR "
                "LOWER(COALESCE(descripcion,'')) LIKE LOWER(?)"
                ")"
            )
            args += [like, like, like]

        if solo_activos:
            where_clauses.append("COALESCE(activo,1)=1")

        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        # total
        cur.execute(f"SELECT COUNT(*) AS n FROM puestos {where_sql}", args)
        total = int((cur.fetchone() or {"n": 0})["n"])

        # página actual
        cur.execute(f"""
            SELECT
                id,
                codigo,
                nombre,
                COALESCE(descripcion,'') AS descripcion,
                COALESCE(activo,1) AS activo
            FROM puestos
            {where_sql}
            ORDER BY {order_by}
            LIMIT ? OFFSET ?
        """, args + [per_page, offset])
        puestos = cur.fetchall()

        conn.close()

        last_page = max(1, (total + per_page - 1) // per_page)
        has_prev = page > 1
        has_next = page < last_page

        return render_template(
            'puestos.html',
            puestos=puestos,

            # filtros / estado UI
            q=q,
            solo_activos=1 if solo_activos else 0,
            sort=sort,
            direction=direction,
            page=page,
            per_page=per_page,
            total=total,
            last_page=last_page,
            has_prev=has_prev,
            has_next=has_next,

            # sesión / permisos
            usuario=session.get('usuario'),
            rol=session.get('rol'),
            has_permission=_can,
            permissions=session.get('permissions', {}),

            # menú activo
            active_page='puestos',
        )

    # -----------------------------------------------------------------
    # EDITAR PUESTO
    # GET  /puestos/<pid>/editar  -> muestra form edición
    # POST /puestos/<pid>/editar  -> guarda cambios
    # -----------------------------------------------------------------
    @app.route('/puestos/<int:pid>/editar', methods=['GET', 'POST'], endpoint='editar_puesto')
    @require_login
    @require_permission('puestos', 'editar')
    def editar_puesto(pid: int):
        conn = get_db()
        ensure_puestos_schema(conn)
        cur = conn.cursor()

        if request.method == 'GET':
            cur.execute("""
                SELECT
                    id,
                    codigo,
                    nombre,
                    COALESCE(descripcion,'') AS descripcion,
                    COALESCE(activo,1) AS activo
                FROM puestos
                WHERE id=?
            """, (pid,))
            p = cur.fetchone()

            if not p:
                conn.close()
                flash('Puesto no encontrado.', 'warning')
                return redirect(url_for('puestos'))

            conn.close()
            # Renderizamos tu plantilla puestos_editar.html
            return render_template(
                'puestos_editar.html',
                p=p,
                usuario=session.get('usuario'),
                rol=session.get('rol'),
                has_permission=_can,
                permissions=session.get('permissions', {}),
                active_page='puestos',
            )

        # method == 'POST' -> guardar cambios
        codigo = (request.form.get('codigo') or '').strip()
        nombre = (request.form.get('nombre') or '').strip()
        descripcion = (request.form.get('descripcion') or '').strip()
        activo_raw = (request.form.get('activo') or '1').strip()
        activo_val = 1 if activo_raw == '1' else 0

        if not codigo or not nombre:
            conn.close()
            flash('Código y nombre son obligatorios.', 'warning')
            return redirect(url_for('editar_puesto', pid=pid))

        try:
            cur.execute("""
                UPDATE puestos
                SET codigo=?, nombre=?, descripcion=?, activo=?
                WHERE id=?
            """, (codigo, nombre, descripcion, activo_val, pid))
            if cur.rowcount == 0:
                flash('Puesto no encontrado.', 'warning')
            else:
                conn.commit()
                flash('Puesto actualizado correctamente.', 'success')
        except Exception as e:
            conn.rollback()
            current_app.logger.exception(e)
            flash('No se pudo actualizar: código o nombre ya existen.', 'danger')
        finally:
            conn.close()

        return redirect(url_for('puestos'))

    # -----------------------------------------------------------------
    # ACTIVAR / DESACTIVAR
    # POST /puestos/<pid>/toggle
    # -----------------------------------------------------------------
    @app.route('/puestos/<int:pid>/toggle', methods=['POST'], endpoint='toggle_puesto')
    @require_login
    @require_permission('puestos', 'editar')
    def toggle_puesto(pid: int):
        conn = get_db()
        ensure_puestos_schema(conn)
        cur = conn.cursor()

        try:
            cur.execute("""
                UPDATE puestos
                SET activo = CASE COALESCE(activo,1)
                                WHEN 1 THEN 0
                                ELSE 1
                             END
                WHERE id=?
            """, (pid,))
            if cur.rowcount == 0:
                flash('Puesto no encontrado.', 'warning')
            else:
                conn.commit()
                flash('Estado actualizado.', 'success')
        except Exception as e:
            conn.rollback()
            current_app.logger.exception(e)
            flash('No se pudo cambiar el estado.', 'danger')
        finally:
            conn.close()

        return redirect(url_for('puestos'))

    # -----------------------------------------------------------------
    # IMPORT MASIVO CSV
    # POST /puestos/import
    # -----------------------------------------------------------------
    @app.route('/puestos/import', methods=['POST'], endpoint='puestos_import')
    @require_login
    @require_permission('puestos', 'crear')
    def puestos_import():
        file = request.files.get('csv_file')
        if not file or not file.filename.lower().endswith('.csv'):
            flash('Seleccione un archivo CSV válido.', 'warning')
            return redirect(url_for('puestos'))

        raw = file.read()

        # intenta utf-8-sig primero
        try:
            text = raw.decode('utf-8-sig')
        except Exception:
            text = raw.decode('latin-1', errors='ignore')

        conn = get_db()
        ensure_puestos_schema(conn)
        cur = conn.cursor()

        reader = csv.DictReader(io.StringIO(text))
        headers_norm = {h.lower().strip(): h for h in (reader.fieldnames or [])}

        if not {'codigo', 'nombre'}.issubset(headers_norm.keys()):
            conn.close()
            flash('El CSV debe tener al menos las columnas: codigo, nombre (opcional: descripcion).', 'danger')
            return redirect(url_for('puestos'))

        inserted = 0
        skipped = 0

        for row in reader:
            codigo = (row.get(headers_norm['codigo'], '') or '').strip()
            nombre = (row.get(headers_norm['nombre'], '') or '').strip()
            descripcion = (
                (row.get(headers_norm.get('descripcion', ''), '') or '').strip()
                if 'descripcion' in headers_norm else ''
            )

            if not codigo or not nombre:
                skipped += 1
                continue

            try:
                # evitar duplicados
                cur.execute("""
                    SELECT 1
                    FROM puestos
                    WHERE LOWER(codigo)=LOWER(?) OR LOWER(nombre)=LOWER(?)
                    LIMIT 1
                """, (codigo, nombre))
                if cur.fetchone():
                    skipped += 1
                    continue

                cur.execute("""
                    INSERT INTO puestos(codigo, nombre, descripcion, activo)
                    VALUES(?,?,?,1)
                """, (codigo, nombre, descripcion))
                inserted += 1
            except Exception as e:
                current_app.logger.exception(e)
                conn.rollback()
                skipped += 1

        conn.commit()
        conn.close()

        flash(f'Importación finalizada. Insertados: {inserted}, Omitidos: {skipped}.', 'info')
        return redirect(url_for('puestos'))
