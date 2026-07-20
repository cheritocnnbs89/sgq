# modules/routes_users.py
# -*- coding: utf-8 -*-
from datetime import datetime
import sqlite3, csv, io, re
from flask import (
    render_template, request, redirect, url_for, flash,
    session, current_app, send_file
)
from .db import get_db, get_config_value
from .config import ROLES
from .security import require_login, require_permission, check_password_policy
from modules.users_schema_helper import ensure_users_extra_schema  # migraciones suaves
# NOTE: si tienes doble import (modules. vs .) deja solo uno que funcione en tu proyecto real

# -------------------------------------------------
# Helpers internos reutilizables
# -------------------------------------------------
def _table_exists(cur, table: str) -> bool:
    cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (table,))
    return cur.fetchone() is not None

def _column_exists(cur, table: str, column: str) -> bool:
    # PRAGMA table_info no acepta parámetros, toca interpolar con cuidado:
    cur.execute(f"PRAGMA table_info({table})")
    cols = [r["name"] for r in cur.fetchall()]
    return column in cols

def _strip_accents_and_symbols(txt: str) -> str:
    """
    Convierte tildes -> sin tildes, ñ->n, quita espacios y símbolos raros.
    Deja solo [a-z0-9].
    """
    if not txt:
        return ""
    # normaliza básico
    repl = (
        ("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"),
        ("Á", "a"), ("É", "e"), ("Í", "i"), ("Ó", "o"), ("Ú", "u"),
        ("ñ", "n"), ("Ñ", "n"),
    )
    for a, b in repl:
        txt = txt.replace(a, b)
    # a minúsculas
    txt = txt.lower()
    # reemplaza separadores por nada
    txt = re.sub(r"[^\w]", "", txt)  # quita todo lo que no sea [a-zA-Z0-9_]
    # y luego quita _ extra para compactar
    txt = txt.replace("_", "")
    return txt

def _first_word(txt: str) -> str:
    """
    Devuelve la primera palabra 'limpia' de un string tipo 'JUAN ALFREDO'
    -> 'JUAN'. Si viene vacío, devuelve ''.
    """
    if not txt:
        return ""
    parts = [p for p in re.split(r"\s+", txt.strip()) if p]
    return parts[0] if parts else ""

def _first_lastname_block(txt: str) -> str:
    """
    Devuelve la primera 'palabra' de los apellidos, ej:
    'ALVARADO MORAN' -> 'ALVARADO'
    """
    if not txt:
        return ""
    parts = [p for p in re.split(r"\s+", txt.strip()) if p]
    return parts[0] if parts else ""

def _build_username_candidate(nombres: str, apellidos: str) -> str:
    """
    Regla final:
      username base = primera letra del primer nombre + primer apellido
      ej. nombres='JUAN ALFREDO', apellidos='ALVARADO MORAN'
      -> 'jalvarado'
    """
    first_name = _first_word(nombres)
    first_last = _first_lastname_block(apellidos)

    if not first_name:
        first_initial = "u"
    else:
        first_initial = first_name[0]

    if not first_last:
        last_clean = "user"
    else:
        last_clean = first_last

    base = first_initial + last_clean
    base = _strip_accents_and_symbols(base)
    if not base:
        base = "user"
    return base

def _ensure_unique_username(cur, base_username: str, already_used: set) -> str:
    """
    Garantiza que el username final no exista ni en BD ni en este mismo batch.
    Estrategia:
      - probar base
      - luego base2, base3, base4, ...
    """
    candidate = base_username
    suffix = 2

    while True:
        # ¿ya usado en este batch?
        if candidate in already_used:
            pass
        else:
            # ¿existe en BD?
            cur.execute("SELECT 1 FROM usuarios WHERE LOWER(username)=LOWER(?) LIMIT 1", (candidate,))
            row = cur.fetchone()
            if not row:
                # libre
                already_used.add(candidate)
                return candidate

        # siguiente intento con sufijo
        candidate = f"{base_username}{suffix}"
        suffix += 1

def _normalize_date(val: str) -> str | None:
    """
    Convierte '1998-06-24 00:00:00.000' -> '1998-06-24'.
    Si viene vacío o basura -> None.
    """
    if not val:
        return None
    v = val.strip()
    if not v:
        return None
    # intenta extraer yyyy-mm-dd del inicio
    m = re.match(r"(\d{4}-\d{2}-\d{2})", v)
    if m:
        return m.group(1)
    return None

def _get_roles_from_db(conn):
    """
    Devuelve la lista de nombres de roles desde la tabla `roles`.
    Fallback a ROLES si la tabla falla.
    """
    cur = conn.cursor()
    try:
        cur.execute("SELECT nombre FROM roles ORDER BY nombre")
        rows = cur.fetchall()
        roles = [
            (r["nombre"] or "").strip().lower()
            for r in rows if (r["nombre"] or "").strip()
        ]
        seen = set()
        roles_norm = []
        for r in roles:
            if r not in seen:
                seen.add(r)
                roles_norm.append(r)
        return roles_norm if roles_norm else list(ROLES)
    except Exception:
        return list(ROLES)





# ============================================================
# CENTROS DE COSTO (desde param_groups/param_values)
# group_id = 7  (Centro de Costo)
# ============================================================

CC_GROUP_ID = 7  # <- tu "id padre"

def ensure_usuarios_cc_schema(conn):
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios_cc (
            usuario_id INTEGER NOT NULL,
            centro_costo_id INTEGER NOT NULL,
            porcentaje REAL NOT NULL,
            PRIMARY KEY (usuario_id, centro_costo_id)
        )
    """)
    conn.commit()



def _load_centros_costo_from_params(conn):
    """
    Devuelve catálogo de centros de costo desde param_values (group_id=7)
    Retorna filas con: id, nombre, valor, orden
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT
            pv.id,
            pv.nombre,
            COALESCE(pv.valor,'') AS valor,
            COALESCE(pv.orden,1)  AS orden
        FROM param_values pv
        WHERE pv.group_id = ?
          AND COALESCE(pv.activo,1) = 1
        ORDER BY COALESCE(pv.orden,1), pv.nombre
    """, (CC_GROUP_ID,))
    return cur.fetchall()


def _load_user_cc_dist(conn, user_id: int):
    """
    Precarga distribución guardada.
    Tabla real: usuarios_cc(usuario_id, centro_costo_id, porcentaje)
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT
            uc.centro_costo_id AS cc_id,
            uc.porcentaje      AS pct,
            COALESCE(pv.nombre,'') AS cc_nombre
        FROM usuarios_cc uc
        LEFT JOIN param_values pv
               ON pv.id = uc.centro_costo_id
              AND pv.group_id = ?
        WHERE uc.usuario_id = ?
        ORDER BY COALESCE(pv.orden,1), pv.nombre, uc.centro_costo_id
    """, (CC_GROUP_ID, user_id))
    return [dict(r) for r in cur.fetchall()]

def _save_user_cc_dist(conn, user_id: int, cc_ids: list[str], cc_pcts: list[str]):
    """
    Guarda distribución en tabla real:
      usuarios_cc(usuario_id, centro_costo_id, porcentaje)
    """
    items = []
    for cc_raw, pct_raw in zip(cc_ids, cc_pcts):
        cc_raw = (cc_raw or "").strip()
        pct_raw = (pct_raw or "").strip()
        if not cc_raw:
            continue
        try:
            cc_id = int(cc_raw)
        except ValueError:
            continue
        try:
            pct = float(pct_raw.replace(",", ".")) if pct_raw else 0.0
        except ValueError:
            pct = 0.0
        items.append((cc_id, pct))

    cur = conn.cursor()

    # Si no enviaron nada, borramos distribución
    if not items:
        cur.execute("DELETE FROM usuarios_cc WHERE usuario_id=?", (user_id,))
        return True, None

    # Validar que TODOS existan y estén activos en group_id=7
    cur.execute("""
        SELECT id
        FROM param_values
        WHERE group_id = ?
          AND COALESCE(activo,1) = 1
    """, (CC_GROUP_ID,))
    valid_ids = {int(r["id"]) for r in cur.fetchall()}

    for cc_id, _ in items:
        if cc_id not in valid_ids:
            return False, f"Centro de costo inválido (id={cc_id}). Revise Parametrización (grupo Centro de Costo)."

    total = sum(p for _, p in items)
    if abs(total - 100.0) > 0.01:
        return False, f"La distribución de centros de costo debe sumar 100%. Actualmente suma: {total:.2f}%"

    # Reemplazo completo
    cur.execute("DELETE FROM usuarios_cc WHERE usuario_id=?", (user_id,))
    for cc_id, pct in items:
        cur.execute("""
            INSERT INTO usuarios_cc(usuario_id, centro_costo_id, porcentaje)
            VALUES (?,?,?)
        """, (user_id, cc_id, pct))

    return True, None

# -------------------------------------------------
# Registro de rutas
# -------------------------------------------------

def register_user_routes(app):

    # =========================
    # LISTA DE USUARIOS
    # =========================
    # =========================
    # LISTA DE USUARIOS
    # =========================
    @app.route('/usuarios', methods=['GET'], endpoint='usuarios')
    @require_login
    @require_permission('usuarios', 'ver')
    def usuarios_list():
        """
        Lista con filtros y ordenamiento.
        Filtros soportados:
          q: busca parcial username/email/departamento
          estado: 'activos', 'deshabilitados', 'todos'
        Orden soportado:
          sort: columna ('id','username','email','rol','departamento','jefe',
                         'fecha_registro','estado')
          dir: 'asc'/'desc'
        """
        q         = (request.args.get('q') or '').strip()
        estado    = (request.args.get('estado') or 'activos').strip().lower()
        sort_col  = (request.args.get('sort') or 'id').strip().lower()
        sort_dir  = (request.args.get('dir')  or 'desc').strip().lower()

        # Seguridad en ordenamiento
        valid_cols = {
            'id': 'u.id',
            'username': 'u.username',
            'email': 'u.email',
            'rol': 'u.rol',
            'departamento': 'd.nombre',
            'jefe': 'jefe_nombre',
            'fecha_registro': 'u.fecha_registro',
            'estado': 'u.disabled'
        }
        order_expr = valid_cols.get(sort_col, 'u.id')
        order_dir  = 'ASC' if sort_dir == 'asc' else 'DESC'

        conds = []
        params = []

        if q:
            like = f"%{q}%"
            conds.append(
                "(u.username LIKE ? "
                "OR u.email LIKE ? "
                "OR COALESCE(d.nombre,'') LIKE ? "
                "OR COALESCE(uj.username,'') LIKE ?)"
            )
            params += [like, like, like, like]

        if estado == 'activos':
            conds.append("u.disabled = 0")
        elif estado == 'deshabilitados':
            conds.append("u.disabled <> 0")
        # 'todos' -> sin condición

        where_clause = ""
        if conds:
            where_clause = "WHERE " + " AND ".join(conds)

        conn = get_db()
        ensure_users_extra_schema(conn)
        cur = conn.cursor()

        # 👇 OJO: f-string para interpolar order_expr / order_dir / where_clause
        sql = f"""
            SELECT
                u.id,
                u.username,
                u.email,
                u.rol,
                u.disabled,
                u.departamento_id,
                COALESCE(d.nombre,'') AS departamento,
                u.fecha_registro,
                u.jefe_id,
                COALESCE(uj.username, '')        AS jefe_username,
                COALESCE(u.nombre_completo, '')  AS nombre_completo,
                COALESCE(u.identificacion, '')   AS identificacion,
                COALESCE(uj.nombre_completo, '') AS jefe_nombre
            FROM usuarios u
            LEFT JOIN departamentos d ON d.id = u.departamento_id
            LEFT JOIN usuarios uj ON uj.id = u.jefe_id
            {where_clause}
            ORDER BY {order_expr} {order_dir}
        """

        cur.execute(sql, params)
        usuarios = cur.fetchall()

        # Lista de posibles jefes para el combo del front
        cur.execute("""
            SELECT id, username, nombre_completo
            FROM usuarios
            WHERE disabled = 0
            ORDER BY username
        """)
        jefes = cur.fetchall()

        conn.close()

        return render_template(
            'usuarios.html',
            usuarios=usuarios,
            jefes=jefes,                    # 👈 importante para el front
            q=q,
            estado=estado,
            sort=sort_col,
            dir=sort_dir,
            usuario=session.get('usuario'),
            rol=session.get('rol'),
            permissions=session.get('permissions', {}),
            active_page='usuarios'
        )

    # =========================
    # EDITAR USUARIO
    # =========================
    @app.route('/usuarios/<int:user_id>/editar', methods=['GET', 'POST'], endpoint='editar_usuario')
    @require_login
    @require_permission('usuarios', 'editar')
    def editar_usuario(user_id):
        conn = get_db()
        ensure_users_extra_schema(conn)
        cur = conn.cursor()

        # Asegurar tabla de distribución CC
        ensure_usuarios_cc_schema(conn)

        # Traer usuario
        cur.execute("""
            SELECT id, username, email, rol, departamento_id, disabled, cuenta_contable_id,
                nombre_completo, identificacion, sexo,
                fecha_nacimiento, fecha_ingreso,
                provincia, ciudad, direccion,
                empresa_id, area_id, puesto_id,
                tarjeta_alias, tarjeta_last4,
                fecha_registro,
                jefe_id,tiene_caja_chica,codigo_sap  
            FROM usuarios
            WHERE id=?
        """, (user_id,))
        u = cur.fetchone()

        if not u:
            conn.close()
            flash('Usuario no encontrado.', 'warning')
            return redirect(url_for('usuarios'))

        roles_db = _get_roles_from_db(conn)

        # ---------- Cargar combos (se usan tanto en GET como en POST si hay error) ----------
        def _load_combos_local():
            cur2 = conn.cursor()
            cur2.execute("SELECT id, nombre FROM departamentos ORDER BY nombre")
            departamentos = cur2.fetchall()

            cur2.execute("SELECT id, nombre FROM areas WHERE COALESCE(activo,1)=1 ORDER BY nombre")
            areas = cur2.fetchall()

            cur2.execute("SELECT id, nombre FROM puestos WHERE COALESCE(activo,1)=1 ORDER BY nombre")
            puestos = cur2.fetchall()

            cur2.execute("SELECT id, razon_social FROM empresas WHERE COALESCE(activo,1)=1 ORDER BY razon_social")
            empresas = cur2.fetchall()

            cur2.execute("""
                SELECT id, username, nombre_completo
                FROM usuarios
                WHERE disabled = 0
                ORDER BY username
            """)
            jefes = cur2.fetchall()

            return departamentos, areas, puestos, empresas, jefes

        # Catálogo CC y distribución actual (para pintar el form)
        centros_costo = _load_centros_costo_from_params(conn)
        cc_dist = _load_user_cc_dist(conn, user_id)

        # =========================
        # POST: guardar cambios
        # =========================
        if request.method == 'POST':
            username = (request.form.get('username') or '').strip()
            email    = (request.form.get('email') or '').strip()
            rol      = (request.form.get('rol') or '').strip().lower()
            password = (request.form.get('password') or '').strip()

            dept_raw = request.form.get('departamento_id')
            disabled_raw = request.form.get('disabled', '0')
            cuenta_contable_raw = request.form.get('cuenta_contable_id')

            nombre_completo = (request.form.get('nombre_completo') or '').strip()
            identificacion  = (request.form.get('identificacion') or '').strip()
            sexo            = (request.form.get('sexo') or '').strip().upper() or None
            fecha_nac       = (request.form.get('fecha_nacimiento') or '').strip() or None
            fecha_ing       = (request.form.get('fecha_ingreso') or '').strip() or None
            provincia       = (request.form.get('provincia') or '').strip()
            ciudad          = (request.form.get('ciudad') or '').strip()
            direccion       = (request.form.get('direccion') or '').strip()
            empresa_id_raw  = request.form.get('empresa_id')
            area_id_raw     = request.form.get('area_id')
            puesto_id_raw   = request.form.get('puesto_id')
            tarj_alias      = (request.form.get('tarjeta_alias') or '').strip()
            tarj_last4      = (request.form.get('tarjeta_last4') or '').strip()

            # jefe
            jefe_id_raw = request.form.get('jefe_id')
            try:
                jefe_id = int(jefe_id_raw) if jefe_id_raw else None
            except (TypeError, ValueError):
                jefe_id = None
            if jefe_id == user_id:
                jefe_id = None

            # -------- Validaciones básicas --------
            if not username or not email or rol not in roles_db:
                departamentos, areas, puestos, empresas, jefes = _load_combos_local()
                conn.close()
                flash('Datos de usuario inválidos.', 'danger')
                return redirect(url_for('editar_usuario', user_id=user_id))

            try:
                min_user_len = int(get_config_value('username_min_length', '6'))
            except ValueError:
                min_user_len = 6

            if len(username) < min_user_len:
                departamentos, areas, puestos, empresas, jefes = _load_combos_local()
                conn.close()
                flash(f'El nombre de usuario debe tener al menos {min_user_len} caracteres.', 'warning')
                return redirect(url_for('editar_usuario', user_id=user_id))

            # departamento
            if rol == 'admin':
                dept_id = None
            else:
                try:
                    dept_id = int(dept_raw or 0)
                    if dept_id == 0:
                        raise ValueError()
                except (TypeError, ValueError):
                    departamentos, areas, puestos, empresas, jefes = _load_combos_local()
                    conn.close()
                    flash('Debe seleccionar un departamento.', 'warning')
                    return redirect(url_for('editar_usuario', user_id=user_id))

            # disabled
            try:
                disabled_val = 1 if int(disabled_raw) else 0
            except ValueError:
                disabled_val = 0

            # cuenta contable
            try:
                cc_id = int(cuenta_contable_raw or 0) or None
            except (TypeError, ValueError):
                cc_id = None

            # combos numéricos
            empresa_id = int(empresa_id_raw or 0) or None
            area_id    = int(area_id_raw or 0) or None
            puesto_id  = int(puesto_id_raw or 0) or None

            # -------- Guardar (usuario + distribución CC) en una transacción --------
            # Dentro de la ruta de editar usuario (POST)
            # 1. CAPTURAMOS LOS NUEVOS CAMPOS
            codigo_sap = (request.form.get('codigo_sap') or '').strip()
            tiene_caja_chica = 1 if request.form.get('tiene_caja_chica') == '1' else 0
            try:
                if password:
                    ok, msg = check_password_policy(password)
                    if not ok:
                        conn.close()
                        flash(msg, 'warning')
                        return redirect(url_for('editar_usuario', user_id=user_id))

                    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    cur.execute("""
                        UPDATE usuarios
                        SET username=?, email=?, rol=?, departamento_id=?, password=?,
                            disabled=?, cuenta_contable_id=?, password_changed_at=?,
                            nombre_completo=?, identificacion=?, sexo=?,
                            fecha_nacimiento=?, fecha_ingreso=?,
                            provincia=?, ciudad=?, direccion=?,
                            empresa_id=?, area_id=?, puesto_id=?,
                            tarjeta_alias=?, tarjeta_last4=?,
                            jefe_id=?,tiene_caja_chica=?,codigo_sap=?
                        WHERE id=?
                    """, (
                        username, email, rol, dept_id, password,
                        disabled_val, cc_id, ts,
                        nombre_completo, identificacion, sexo,
                        fecha_nac, fecha_ing,
                        provincia, ciudad, direccion,
                        empresa_id, area_id, puesto_id,
                        tarj_alias, tarj_last4,
                        jefe_id,tiene_caja_chica,codigo_sap,
                        user_id
                    ))
                else:
                    cur.execute("""
                        UPDATE usuarios
                        SET username=?, email=?, rol=?, departamento_id=?,
                            disabled=?, cuenta_contable_id=?,
                            nombre_completo=?, identificacion=?, sexo=?,
                            fecha_nacimiento=?, fecha_ingreso=?,
                            provincia=?, ciudad=?, direccion=?,
                            empresa_id=?, area_id=?, puesto_id=?,
                            tarjeta_alias=?, tarjeta_last4=?,
                            jefe_id=?,tiene_caja_chica=?,codigo_sap=?
                        WHERE id=?
                    """, (
                        username, email, rol, dept_id,
                        disabled_val, cc_id,
                        nombre_completo, identificacion, sexo,
                        fecha_nac, fecha_ing,
                        provincia, ciudad, direccion,
                        empresa_id, area_id, puesto_id,
                        tarj_alias, tarj_last4,
                        jefe_id,tiene_caja_chica,codigo_sap,
                        user_id
                    ))

                # ===== Guardar distribución de Centros de Costo (param_values group_id=7) =====
                cc_ids  = request.form.getlist("cc_id[]")
                cc_pcts = request.form.getlist("cc_pct[]")
                ok_cc, msg_cc = _save_user_cc_dist(conn, user_id, cc_ids, cc_pcts)
                if not ok_cc:
                    conn.rollback()
                    conn.close()
                    flash(msg_cc, "warning")
                    return redirect(url_for('editar_usuario', user_id=user_id))

                conn.commit()
                flash('Usuario actualizado correctamente.', 'success')

            except sqlite3.IntegrityError as e:
                conn.rollback()
                current_app.logger.exception(e)
                msg = str(e).lower()
                if 'unique' in msg or 'constraint' in msg:
                    flash('El nombre de usuario o el correo ya existen.', 'danger')
                else:
                    flash('No se pudo actualizar el usuario (restricción de integridad).', 'danger')

            except sqlite3.OperationalError as e:
                conn.rollback()
                current_app.logger.exception(e)
                flash(f'Error de esquema/tabla: {e}. Ejecute migraciones.', 'danger')

            except Exception as e:
                conn.rollback()
                current_app.logger.exception(e)
                flash('Error no previsto al actualizar el usuario.', 'danger')

            finally:
                try:
                    conn.close()
                except Exception:
                    pass

            return redirect(url_for('usuarios'))

        # =========================
        # GET: mostrar formulario
        # =========================
        departamentos, areas, puestos, empresas, jefes = _load_combos_local()

        conn.close()
        return render_template(
            'editar_usuario.html',
            u=u,
            departamentos=departamentos,
            roles=roles_db,
            areas=areas,
            puestos=puestos,
            empresas=empresas,
            jefes=jefes,

            centros_costo=centros_costo,  # param_values group_id=7
            cc_dist=cc_dist,              # precarga

            usuario=session['usuario'],
            rol=session['rol'],
            active_page='usuarios',
        )






        # =========================
    
    
    
    # ELIMINAR USUARIO (solo si no tiene movimientos)
    # =========================
    @app.route('/usuarios/<int:user_id>/eliminar', methods=['POST'], endpoint='usuarios_eliminar')
    @require_login
    @require_permission('usuarios', 'eliminar')
    def usuarios_eliminar(user_id):
        conn = get_db()
        cur = conn.cursor()

        # 1) Usuario existe
        cur.execute("""
            SELECT id, username, rol, COALESCE(nombre_completo,'') AS nombre_completo
            FROM usuarios
            WHERE id = ?
        """, (user_id,))
        u = cur.fetchone()

        if not u:
            conn.close()
            flash('Usuario no encontrado.', 'warning')
            return redirect(url_for('usuarios'))

        # 2) No permitir borrarse a sí mismo
        try:
            my_id = int(session.get('usuario_id') or 0)
        except Exception:
            my_id = 0
        if my_id and my_id == user_id:
            conn.close()
            flash('No puedes eliminar tu propio usuario.', 'warning')
            return redirect(url_for('usuarios'))

        # 3) No permitir eliminar ADMIN
        if (u['rol'] or '').strip().lower() == 'admin':
            conn.close()
            flash('No se puede eliminar un usuario con rol ADMIN. Deshabilítalo en su lugar.', 'warning')
            return redirect(url_for('usuarios'))

        # 4) Chequear usos en otras tablas (solo si existen tabla+columna)
        total_usos = 0
        detalles = []

        checks = [
            # OM / Reclamos (ajusta a tus columnas reales)
            ("reclamos", "creado_por", "OM/Reclamos creados"),
            ("reclamos", "jefe_id", "asignado como jefe"),
            ("reclamo_respuestas", "usuario_id", "respuestas en reclamos"),

            # Gastos
            ("gastos_tarjeta", "usuario_id", "gastos ingresados"),
            ("gastos_tarjeta", "aprobado_ga_por", "aprobaciones GA"),
            ("gastos_tarjeta", "aprobado_gf_por", "aprobaciones GF"),
            ("gastos_tarjeta", "aprobado_gg_por", "aprobaciones GG"),

            # Tareas (ajusta)
            ("tareas", "creado_por", "tareas creadas"),
            ("tareas", "asignado_a", "tareas asignadas"),

            # Usuarios como jefe directo de otros
            ("usuarios", "jefe_id", "usuarios que lo tienen como jefe"),
            # Distribución CC
            ("usuarios_cc", "usuario_id", "distribución de centros de costo"),
        ]

        for tabla, columna, label in checks:
            try:
                if not _table_exists(cur, tabla):
                    continue
                if not _column_exists(cur, tabla, columna):
                    continue

                cur.execute(f"SELECT COUNT(*) AS c FROM {tabla} WHERE {columna} = ?", (user_id,))
                row = cur.fetchone()
                c = int(row["c"] or 0) if row else 0
                if c:
                    total_usos += c
                    detalles.append(f"{c} {label}")
            except Exception:
                # si algo raro pasa, no revienta el sistema
                continue

        if total_usos > 0:
            conn.close()
            flash(
                f"No se puede eliminar el usuario '{u['username']}' porque tiene registros relacionados: "
                + (" / ".join(detalles) if detalles else f"{total_usos} movimientos"),
                "danger"
            )
            return redirect(url_for('usuarios'))

        # 5) Si no tiene usos, eliminar (limpieza extra)
        try:
            # limpieza defensiva por si quedó algo
            if _table_exists(cur, "usuarios_cc") and _column_exists(cur, "usuarios_cc", "usuario_id"):
                cur.execute("DELETE FROM usuarios_cc WHERE usuario_id = ?", (user_id,))

            cur.execute("DELETE FROM usuarios WHERE id = ?", (user_id,))
            conn.commit()
            flash(f"Usuario '{u['username']}' eliminado correctamente.", "success")
        except Exception as e:
            conn.rollback()
            current_app.logger.exception(e)
            flash("No se pudo eliminar el usuario (error de base de datos).", "danger")
        finally:
            conn.close()

        return redirect(url_for('usuarios'))

    # =========================
     # NUEVO USUARIO (form manual)
    # =========================
    @app.route('/usuarios/nuevo', methods=['GET', 'POST'], endpoint='nuevo_usuario')
    @require_login
    @require_permission('usuarios', 'crear')
    def nuevo_usuario():
        conn = get_db()
        ensure_users_extra_schema(conn)
        ensure_usuarios_cc_schema(conn)  # 👈 distribución de CC
        cur = conn.cursor()

        roles_db = _get_roles_from_db(conn)

        def _load_combos():
            cur2 = conn.cursor()

            cur2.execute("SELECT id, nombre FROM departamentos ORDER BY nombre")
            departamentos = cur2.fetchall()

            cur2.execute("SELECT id, nombre FROM areas WHERE COALESCE(activo,1)=1 ORDER BY nombre")
            areas = cur2.fetchall()

            cur2.execute("SELECT id, nombre FROM puestos WHERE COALESCE(activo,1)=1 ORDER BY nombre")
            puestos = cur2.fetchall()

            cur2.execute("SELECT id, razon_social FROM empresas WHERE COALESCE(activo,1)=1 ORDER BY razon_social")
            empresas = cur2.fetchall()

            cur2.execute("""
                SELECT id, username, nombre_completo
                FROM usuarios
                WHERE COALESCE(disabled,0) = 0
                ORDER BY username
            """)
            jefes = cur2.fetchall()

            return departamentos, areas, puestos, empresas, jefes

        def _cc_dist_from_post():
            """
            Para re-render cuando hay error.
            Devuelve lista [{cc_id:int, pct:float}] con lo que el usuario intentó enviar.
            """
            out = []
            cc_ids  = request.form.getlist("cc_id[]")
            cc_pcts = request.form.getlist("cc_pct[]")

            for a, b in zip(cc_ids, cc_pcts):
                a = (a or "").strip()
                b = (b or "").strip()
                if not a and not b:
                    continue
                try:
                    ccid = int(a)
                except Exception:
                    continue
                try:
                    pct = float(b.replace(",", "."))
                except Exception:
                    pct = 0.0
                out.append({"cc_id": ccid, "pct": pct})
            return out

        # Catálogo de centros de costo (param_values group_id=7)
        centros_costo = _load_centros_costo_from_params(conn)


        # Dentro de la ruta de nuevo usuario (POST)
        tiene_caja_chica = 1 if request.form.get('tiene_caja_chica') == '1' else 0
        # ---------- GET ----------
        if request.method != 'POST':
            # Captura el nuevo campo empresa_id del formulario
            empresa_id = request.form.get('empresa_id')
            # Consulta para obtener las empresas
            cur.execute("SELECT id, razon_social FROM empresas WHERE activo = 1 ORDER BY razon_social ASC")
            
            
            empresas = cur.fetchall()
            departamentos, areas, puestos, empresas, jefes = _load_combos()
            
            conn.close()
            return render_template(
                'nuevo_usuario.html',
                departamentos=departamentos,
                roles=roles_db,
                areas=areas,
                puestos=puestos,
                empresas=empresas,
                jefes=jefes,
                centros_costo=centros_costo,  # 👈 NUEVO
                cc_dist=[],                   # 👈 NUEVO (vacío en alta)
                usuario=session.get('usuario'),
                rol=session.get('rol'),
                active_page='usuarios',
            )

        # ---------- POST ----------
        form = dict(request.form)

        username = (form.get('username') or '').strip()
        email    = (form.get('email') or '').strip()
        rol      = (form.get('rol') or '').strip().lower()
        password = (form.get('password') or '').strip()

        dept_raw = form.get('departamento_id')
        disabled_raw = form.get('disabled', '0')

        nombre_completo = (form.get('nombre_completo') or '').strip()
        identificacion  = (form.get('identificacion') or '').strip()
        sexo            = (form.get('sexo') or '').strip().upper() or None
        fecha_nac       = (form.get('fecha_nacimiento') or '').strip() or None
        fecha_ing       = (form.get('fecha_ingreso') or '').strip() or None
        provincia       = (form.get('provincia') or '').strip()
        ciudad          = (form.get('ciudad') or '').strip()
        direccion       = (form.get('direccion') or '').strip()

        empresa_id_raw  = form.get('empresa_id')
        area_id_raw     = form.get('area_id')
        puesto_id_raw   = form.get('puesto_id')

        tarj_alias      = (form.get('tarjeta_alias') or '').strip()
        tarj_last4      = (form.get('tarjeta_last4') or '').strip()

        # jefe
        jefe_id_raw = form.get('jefe_id')
        try:
            jefe_id = int(jefe_id_raw) if jefe_id_raw else None
        except (TypeError, ValueError):
            jefe_id = None

        # Validación: username mínimo configurable
        try:
            min_user_len = int(get_config_value('username_min_length', '6'))
        except ValueError:
            min_user_len = 6

        # disabled
        try:
            disabled_val = 1 if int(disabled_raw) else 0
        except ValueError:
            disabled_val = 0

        # depto
        if rol == 'admin':
            dept_id = None
        else:
            try:
                dept_id = int(dept_raw or 0)
                if dept_id == 0:
                    raise ValueError()
            except (TypeError, ValueError):
                dept_id = None

        # combos numéricos
        empresa_id = int(empresa_id_raw or 0) or None
        area_id    = int(area_id_raw or 0) or None
        puesto_id  = int(puesto_id_raw or 0) or None

        # Para re-render con lo que el usuario intentó
        cc_dist_try = _cc_dist_from_post()

        # -------- Validaciones base --------
        if not username or len(username) < min_user_len:
            flash(f'El nombre de usuario debe tener al menos {min_user_len} caracteres.', 'warning')
        elif not email:
            flash('El correo es obligatorio.', 'warning')
        elif rol not in roles_db:
            flash('Rol inválido.', 'danger')
        elif not password:
            flash('La contraseña es obligatoria.', 'warning')
        elif rol != 'admin' and not dept_id:
            flash('Debe seleccionar un departamento.', 'warning')
        else:
            ok, msg = check_password_policy(password)
            if not ok:
                flash(msg, 'warning')
            else:
                # Unicidad username/email
                cur.execute("SELECT 1 FROM usuarios WHERE LOWER(username)=LOWER(?)", (username.lower(),))
                if cur.fetchone():
                    flash('El nombre de usuario ya existe.', 'danger')
                else:
                    cur.execute("SELECT 1 FROM usuarios WHERE LOWER(email)=LOWER(?)", (email.lower(),))
                    if cur.fetchone():
                        flash('El correo ya existe.', 'danger')
                    else:
                        # ===== Insert + CC dist (en transacción) =====
                        try:
                            ts_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                            cur.execute("""
                                INSERT INTO usuarios(
                                    username, password, email, rol,
                                    departamento_id, disabled,
                                    failed_attempts, password_changed_at,
                                    nombre_completo, identificacion, sexo,
                                    fecha_nacimiento, fecha_ingreso,
                                    provincia, ciudad, direccion,
                                    empresa_id, area_id, puesto_id,
                                    tarjeta_alias, tarjeta_last4,
                                    fecha_registro,
                                    jefe_id,tiene_caja_chica
                                )
                                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                            """, (
                                username, password, email, rol,
                                dept_id, disabled_val,
                                0, ts_now,
                                nombre_completo, identificacion, sexo,
                                fecha_nac, fecha_ing,
                                provincia, ciudad, direccion,
                                empresa_id, area_id, puesto_id,
                                tarj_alias, tarj_last4,
                                ts_now,
                                jefe_id,tiene_caja_chica
                            ))

                            new_id = cur.lastrowid

                            # ===== Guardar distribución de CC (param_values group_id=7) =====
                            cc_ids  = request.form.getlist("cc_id[]")
                            cc_pcts = request.form.getlist("cc_pct[]")

                            ok_cc, msg_cc = _save_user_cc_dist(conn, new_id, cc_ids, cc_pcts)
                            if not ok_cc:
                                conn.rollback()
                                flash(msg_cc, "warning")
                            else:
                                conn.commit()
                                conn.close()
                                flash('Usuario creado correctamente.', 'success')
                                return redirect(url_for('usuarios'))

                        except sqlite3.IntegrityError as e:
                            conn.rollback()
                            current_app.logger.exception(e)
                            flash('No se pudo crear el usuario (restricción de integridad).', 'danger')
                        except sqlite3.Error as e:
                            conn.rollback()
                            current_app.logger.exception(e)
                            flash(f'Error de base de datos: {e}', 'danger')
                        except Exception as e:
                            conn.rollback()
                            current_app.logger.exception(e)
                            flash(f'Ocurrió un error al crear el usuario: {e}', 'danger')

        # Si llegamos aquí: hubo error -> recargamos combos y re-render
        departamentos, areas, puestos, empresas, jefes = _load_combos()
        conn.close()
        return render_template(
            'nuevo_usuario.html',
            departamentos=departamentos,
            roles=roles_db,
            areas=areas,
            puestos=puestos,
            empresas=empresas,
            jefes=jefes,
            centros_costo=centros_costo,  # 👈 param_values group 7
            cc_dist=cc_dist_try,          # 👈 para repintar lo que intentó
            form=form,
            usuario=session.get('usuario'),
            rol=session.get('rol'),
            active_page='usuarios',
        )

    
  
  
  
    # =========================  
    # REPORTE COMPLETO (DESCARGA CSV)
    # =========================
    @app.route('/usuarios/reporte.csv', methods=['GET'], endpoint='usuarios_reporte_csv')
    @require_login
    @require_permission('usuarios', 'ver')
    def usuarios_reporte_csv():
        """
        Devuelve un CSV con TODA la información relevante de los usuarios.
        No usa filtros, saca todo lo que haya en la tabla.
        """
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                u.id,
                u.username,
                COALESCE(u.nombre_completo, '')     AS nombre_completo,
                COALESCE(u.identificacion, '')      AS identificacion,
                COALESCE(u.email, '')               AS email,
                COALESCE(u.rol, '')                 AS rol,
                COALESCE(d.nombre, 'Sin depto')     AS departamento,
                COALESCE(a.nombre, '')              AS area,
                COALESCE(p.nombre, '')              AS puesto,
                COALESCE(e.razon_social, '')        AS empresa,
                COALESCE(u.sexo, '')                AS sexo,
                COALESCE(u.fecha_nacimiento, '')    AS fecha_nacimiento,
                COALESCE(u.fecha_ingreso, '')       AS fecha_ingreso,
                COALESCE(u.provincia, '')           AS provincia,
                COALESCE(u.ciudad, '')              AS ciudad,
                COALESCE(u.direccion, '')           AS direccion,
                COALESCE(j.username, '')            AS jefe_username,
                COALESCE(j.nombre_completo, '')     AS jefe_nombre,
                COALESCE(u.fecha_registro, '')      AS fecha_registro,
                COALESCE(u.tarjeta_alias, '')       AS tarjeta_alias,
                COALESCE(u.tarjeta_last4, '')       AS tarjeta_last4,
                COALESCE(u.disabled, 0)             AS disabled
            FROM usuarios u
            LEFT JOIN departamentos d ON d.id = u.departamento_id
            LEFT JOIN areas a          ON a.id = u.area_id
            LEFT JOIN puestos p        ON p.id = u.puesto_id
            LEFT JOIN empresas e       ON e.id = u.empresa_id
            LEFT JOIN usuarios j       ON j.id = u.jefe_id  -- jefe directo
            ORDER BY d.nombre, a.nombre, u.nombre_completo
        """)

        rows = cur.fetchall()
        conn.close()

        # Construir CSV en memoria
        output = io.StringIO(newline='')
        writer = csv.writer(output, delimiter=';')  # ; como en el resto de tus plantillas

        # Encabezado
        writer.writerow([
            "ID",
            "USERNAME",
            "NOMBRE_COMPLETO",
            "IDENTIFICACION",
            "EMAIL",
            "ROL",
            "DEPARTAMENTO",
            "AREA",
            "PUESTO",
            "EMPRESA",
            "SEXO",
            "FECHA_NACIMIENTO",
            "FECHA_INGRESO",
            "PROVINCIA",
            "CIUDAD",
            "DIRECCION",
            "JEFE_USERNAME",
            "JEFE_NOMBRE",
            "FECHA_REGISTRO",
            "TARJETA_ALIAS",
            "TARJETA_LAST4",
            "ESTADO"
        ])

        # Filas
        for u in rows:
            writer.writerow([
                u['id'],
                u['username'],
                u['nombre_completo'],
                u['identificacion'],
                u['email'],
                u['rol'],
                u['departamento'],
                u['area'],
                u['puesto'],
                u['empresa'],
                u['sexo'],
                u['fecha_nacimiento'],
                u['fecha_ingreso'],
                u['provincia'],
                u['ciudad'],
                u['direccion'],
                u['jefe_username'],
                u['jefe_nombre'],
                u['fecha_registro'],
                u['tarjeta_alias'],
                u['tarjeta_last4'],
                "Deshabilitado" if u['disabled'] else "Activo",
            ])

        # Pasar a bytes para send_file (con BOM para Excel)
        mem = io.BytesIO()
        mem.write(output.getvalue().encode('utf-8-sig'))
        mem.seek(0)

        return send_file(
            mem,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'reporte_usuarios_{datetime.now().strftime("%Y%m%d")}.csv'
        )

    @app.route('/usuarios/asignar-jefe', methods=['POST'], endpoint='usuarios_asignar_jefe')
    @require_login
    @require_permission('usuarios', 'editar')
    def usuarios_asignar_jefe():
        jefe_id = request.form.get('jefe_id')
        ids = request.form.getlist('user_ids')

        if not jefe_id or not ids:
            flash('Debe seleccionar al menos un usuario y un jefe.', 'warning')
            return redirect(url_for('usuarios'))

        conn = get_db(); cur = conn.cursor()
        try:
            placeholders = ",".join("?" for _ in ids)
            params = [int(jefe_id)] + [int(x) for x in ids]
            cur.execute(f"UPDATE usuarios SET jefe_id=? WHERE id IN ({placeholders})", params)
            conn.commit()
            flash(f'Jefe asignado a {len(ids)} usuario(s).', 'success')
        except Exception as e:
            conn.rollback()
            current_app.logger.exception(e)
            flash('No se pudo asignar el jefe masivamente.', 'danger')
        finally:
            conn.close()

        return redirect(url_for('usuarios'))

    # =========================
    # BULK: DESCARGAR PLANTILLA
    # =========================
    @app.route('/usuarios/plantilla.csv', methods=['GET'], endpoint='usuarios_bulk_template')
    @require_login
    @require_permission('usuarios', 'ver')
    def usuarios_bulk_template():
        """
        Devuelve una plantilla CSV con el mismo layout que tú estás usando.
        Importante: usamos ';' como separador porque así viene tu archivo.
        Columnas exactas (incluye la columna vacía después del email):
        NOMBRE;APELLIDO;CEDULA;DIRECCION_E_MAIL;;SEXO;FECHA_NACIMIENTO;FECHA_INGRESO;Provincia ;Ciudad;DESCRIPCION_DIR_1;PUESTO;DEPARTAMENTO;EMPRESA;
        """
        header = [
            "NOMBRE","APELLIDO","CEDULA","DIRECCION_E_MAIL","",
            "SEXO","FECHA_NACIMIENTO","FECHA_INGRESO",
            "Provincia ","Ciudad","DESCRIPCION_DIR_1","PUESTO",
            "DEPARTAMENTO","EMPRESA",""
        ]
        sample = [
            "JUAN ALFREDO","ALVARADO MORAN","1234567890","jalvarado@quimpac.com.ec","",
            "M","1990-01-15 00:00:00.000","2020-02-01 00:00:00.000",
            "GUAYAS","GUAYAQUIL","AV. 9 DE OCTUBRE 123","SUPERVISOR DE PRODUCCION",
            "PRODUCCION CLORO SODA GYE QP","QUIMPAC ECUADOR S.A",""
        ]

        out = io.StringIO(newline='')
        out.write(";".join(header) + "\n")
        out.write(";".join(sample) + "\n")

        mem = io.BytesIO(out.getvalue().encode('utf-8-sig'))
        mem.seek(0)
        return send_file(
            mem,
            mimetype='text/csv',
            as_attachment=True,
            download_name='plantilla_usuarios.csv'
        )

    # =========================
    # BULK: SUBIR CSV
    # =========================
     # =========================
    # BULK: SUBIR CSV
    # =========================
    @app.route('/usuarios/bulk', methods=['POST'], endpoint='usuarios_bulk_upload')
    @require_login
    @require_permission('usuarios', 'crear')
    def usuarios_bulk_upload():
        """
        Procesa el CSV con layout separado por ';'.

        AHORA:
        - Identificador principal = CÉDULA (identificacion)
        - Si la cédula YA existe en usuarios.identificacion -> se ACTUALIZAN datos
            (nombre_completo, email, sexo, fechas, provincia, ciudad, dirección,
            departamento, puesto).
        - Si la cédula NO existe -> se inserta usuario nuevo.
        - Si existe columna JEFE_CODIGO:
            · toma la cédula del jefe
            · busca su usuario
            · actualiza jefe_id del empleado (incluso si ya existía, por si cambió).
        """
        file = request.files.get('archivo')
        if not file or file.filename.strip() == '':
            flash('Debe seleccionar un archivo CSV.', 'warning')
            return redirect(url_for('usuarios'))

        conn = get_db()
        ensure_users_extra_schema(conn)
        cur = conn.cursor()

        # ==========  precargar existentes para validaciones  ==========
        # mapa cedula -> id usuario
        cur.execute("""
            SELECT id, LOWER(TRIM(identificacion)) AS ced
            FROM usuarios
            WHERE identificacion IS NOT NULL
        """)
        ident_to_id = {}
        for row in cur.fetchall():
            if row['ced']:
                ident_to_id[row['ced']] = row['id']

        # mapa email -> id usuario
        cur.execute("""
            SELECT id, LOWER(TRIM(email)) AS em
            FROM usuarios
            WHERE email IS NOT NULL
        """)
        email_to_id = {}
        for row in cur.fetchall():
            if row['em']:
                email_to_id[row['em']] = row['id']

        # mapa de departamentos
        cur.execute("SELECT id, nombre FROM departamentos")
        dep_map = {}
        for row in cur.fetchall():
            dep_name_key = (row['nombre'] or '').strip().lower()
            if dep_name_key:
                dep_map[dep_name_key] = row['id']

        # puestos existentes (nombre->id)
        cur.execute("SELECT id,nombre FROM puestos")
        puesto_map = {}
        for row in cur.fetchall():
            keyp = (row['nombre'] or '').strip().lower()
            if keyp and keyp not in puesto_map:
                puesto_map[keyp] = row['id']

        # Para unicidad de username DENTRO DEL MISMO BATCH
        usernames_batch_usados = set()

        insertados   = 0
        actualizados = 0
        dup_mail     = 0
        dep_inexist  = 0
        invalidos    = 0
        jefes_actualizados    = 0
        jefes_no_encontrados  = 0
        ejemplos_error = []

        # Leer archivo completo como texto y luego usar csv.reader con ';'
        raw_text = file.read().decode('utf-8-sig', errors='replace')
        lines = raw_text.splitlines()
        if not lines:
            flash('El archivo está vacío.', 'warning')
            conn.close()
            return redirect(url_for('usuarios'))

        import re, csv
        reader = csv.reader(lines, delimiter=';')
        rows = list(reader)
        if not rows:
            flash('No se encontraron filas.', 'warning')
            conn.close()
            return redirect(url_for('usuarios'))

        # --------- Mapeo de columnas por nombre de encabezado ----------
        header = rows[0]
        data_rows = rows[1:]

        def norm(h):
            # normaliza encabezados: quita espacios extra, pasa a minúsculas
            return re.sub(r'\s+', ' ', (h or '').strip().lower())

        idx_by_name = {norm(h): i for i, h in enumerate(header) if norm(h)}

        def col_index(*names):
            for name in names:
                i = idx_by_name.get(norm(name))
                if i is not None:
                    return i
            return None

        # índices clave (soportando ambos layouts)
        idx_nombre    = col_index('NOMBRE')
        idx_apellido  = col_index('APELLIDO')
        idx_cedula    = col_index('CEDULA', 'IDENTIFICACION')
        idx_email     = col_index('DIRECCION_E_MAIL', 'EMAIL', 'CORREO', 'DIRECCION E_MAIL')
        idx_sexo      = col_index('SEXO')
        idx_fnac      = col_index('FECHA_NACIMIENTO', 'F.NACIMIENTO', 'FECHA NACIMIENTO')
        idx_fing      = col_index('FECHA_INGRESO', 'INGRESO', 'FECHA INGRESO')
        idx_provincia = col_index('Provincia', 'PROVINCIA')
        idx_ciudad    = col_index('Ciudad', 'CIUDAD')
        idx_dir       = col_index('DESCRIPCION_DIR_1', 'DIRECCION')
        idx_puesto    = col_index('PUESTO', 'CARGO')
        idx_depto     = col_index('DEPARTAMENTO', 'DEPTO', 'DEPARTAMENTO/CENTRO')
        idx_empresa   = col_index('EMPRESA')
        idx_jefe_cod  = col_index('JEFE_CODIGO', 'JEFE CODIGO', 'JEFE_COD')

        # columnas mínimas obligatorias
        required_idx = [idx_nombre, idx_apellido, idx_cedula, idx_email, idx_depto]
        if any(i is None for i in required_idx):
            conn.close()
            flash(
                'El CSV no tiene todas las columnas requeridas (NOMBRE, APELLIDO, '
                'CEDULA, DIRECCION_E_MAIL, DEPARTAMENTO). Verifique el encabezado.',
                'danger'
            )
            return redirect(url_for('usuarios'))

        ts_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        try:
            cur.execute("BEGIN IMMEDIATE")

            # =========================
            # PRIMERA PASADA: INSERT/UPDATE POR CÉDULA
            # =========================
            for idx, cols in enumerate(data_rows, start=2):
                # saltar filas completamente vacías
                if not any((c or '').strip() for c in cols):
                    continue

                def val(i):
                    return (cols[i] or '').strip() if i is not None and i < len(cols) else ''

                nombres_raw   = val(idx_nombre)
                apellidos_raw = val(idx_apellido)
                cedula        = val(idx_cedula)
                email         = val(idx_email)
                sexo_raw      = val(idx_sexo).upper()
                fnac_raw      = val(idx_fnac)
                fing_raw      = val(idx_fing)
                provincia     = val(idx_provincia)
                ciudad        = val(idx_ciudad)
                direccion     = val(idx_dir)
                puesto_nombre = val(idx_puesto)
                depto_nombre  = val(idx_depto)
                empresa_txt   = val(idx_empresa)  # por ahora no lo usamos

                # validar requeridos mínimos
                if (not nombres_raw or not apellidos_raw or not cedula or not email or not depto_nombre):
                    invalidos += 1
                    if len(ejemplos_error) < 10:
                        ejemplos_error.append(
                            f"fila {idx}: faltan campos requeridos -> {cols!r}"
                        )
                    continue

                # normalizar cédula (9 dígitos -> anteponer 0)
                cedula = cedula.strip()
                if cedula.isdigit() and len(cedula) == 9:
                    cedula = '0' + cedula

                cedula_key = cedula.lower().strip()
                email_key  = email.lower().strip()

                # departamento debe existir
                dep_key = depto_nombre.strip().lower()
                dep_id = dep_map.get(dep_key)
                if not dep_id:
                    dep_inexist += 1
                    continue

                # sexo normalizado
                sexo_val = sexo_raw if sexo_raw in ('M', 'F') else None

                # fechas limpias
                fecha_nac = _normalize_date(fnac_raw)
                fecha_ing = _normalize_date(fing_raw)

                # nombre completo
                nombre_completo = f"{nombres_raw.strip()} {apellidos_raw.strip()}".strip()

                # puesto: crearlo si no existe
                puesto_key = puesto_nombre.strip().lower()
                puesto_id = None
                if puesto_key:
                    if puesto_key not in puesto_map:
                        try:
                            cur.execute(
                                "INSERT OR IGNORE INTO puestos(nombre, codigo, activo) VALUES (?,?,1)",
                                (puesto_nombre, puesto_nombre)
                            )
                        except sqlite3.Error:
                            pass
                        cur.execute("SELECT id FROM puestos WHERE LOWER(nombre)=LOWER(?) LIMIT 1", (puesto_nombre,))
                        rowp = cur.fetchone()
                        if rowp:
                            puesto_map[puesto_key] = rowp['id']
                    puesto_id = puesto_map.get(puesto_key)

                # ¿Ya existe un usuario con esta cédula?
                user_id_existente = ident_to_id.get(cedula_key)

                # ========== CASO 1: UPDATE (cédula ya existe) ==========
                if user_id_existente:
                    # Validar que el email no esté usado por OTRO usuario
                    owner_email = email_to_id.get(email_key)
                    if owner_email and owner_email != user_id_existente:
                        dup_mail += 1
                        if len(ejemplos_error) < 10:
                            ejemplos_error.append(
                                f"fila {idx}: email {email} ya usado por otro usuario (id={owner_email})"
                            )
                        continue

                    try:
                        cur.execute("""
                            UPDATE usuarios
                            SET
                                email            = ?,
                                nombre_completo  = ?,
                                identificacion   = ?,
                                sexo             = ?,
                                fecha_nacimiento = ?,
                                fecha_ingreso    = ?,
                                provincia        = ?,
                                ciudad           = ?,
                                direccion        = ?,
                                departamento_id  = ?,
                                puesto_id        = ?
                            WHERE id = ?
                        """, (
                            email,
                            nombre_completo,
                            cedula,
                            sexo_val,
                            fecha_nac,
                            fecha_ing,
                            provincia,
                            ciudad,
                            direccion,
                            dep_id,
                            puesto_id,
                            user_id_existente
                        ))
                        actualizados += 1
                        # refrescar mapas en memoria
                        ident_to_id[cedula_key] = user_id_existente
                        email_to_id[email_key]  = user_id_existente
                    except Exception as e:
                        current_app.logger.exception(e)
                        invalidos += 1
                        if len(ejemplos_error) < 10:
                            ejemplos_error.append(
                                f"fila {idx}: error inesperado update -> {cols!r} / {e}"
                            )
                    continue  # siguiente fila

                # ========== CASO 2: INSERT (cédula nueva) ==========
                # Validar email duplicado en BD para nuevo usuario
                owner_email = email_to_id.get(email_key)
                if owner_email:
                    dup_mail += 1
                    if len(ejemplos_error) < 10:
                        ejemplos_error.append(
                            f"fila {idx}: email {email} ya usado por usuario id={owner_email}"
                        )
                    continue

                # construir username base
                base_username = _build_username_candidate(nombres_raw, apellidos_raw)
                final_username = _ensure_unique_username(cur, base_username, usernames_batch_usados)

                try:
                    cur.execute("""
                        INSERT INTO usuarios(
                            username, password, email, rol,
                            departamento_id, disabled,
                            failed_attempts, password_changed_at,
                            nombre_completo, identificacion, sexo,
                            fecha_nacimiento, fecha_ingreso,
                            provincia, ciudad, direccion,
                            empresa_id, area_id, puesto_id,
                            tarjeta_alias, tarjeta_last4,
                            fecha_registro
                        )
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (
                        final_username,
                        "Quimpac2025*",
                        email,
                        "usuario",
                        dep_id,
                        0,          # disabled=0
                        0,          # failed_attempts
                        ts_now,     # password_changed_at
                        nombre_completo,
                        cedula,
                        sexo_val,
                        fecha_nac,
                        fecha_ing,
                        provincia,
                        ciudad,
                        direccion,
                        None,       # empresa_id
                        None,       # area_id
                        puesto_id,
                        "",         # tarjeta_alias
                        "",         # tarjeta_last4
                        ts_now      # fecha_registro
                    ))

                    new_id = cur.lastrowid
                    insertados += 1
                    ident_to_id[cedula_key] = new_id
                    email_to_id[email_key]  = new_id

                except sqlite3.IntegrityError as e:
                    current_app.logger.debug(f'fila {idx} IntegrityError {e}')
                    invalidos += 1
                except Exception as e:
                    current_app.logger.exception(e)
                    invalidos += 1
                    if len(ejemplos_error) < 10:
                        ejemplos_error.append(
                            f"fila {idx}: error inesperado insert -> {cols!r} / {e}"
                        )

            # =========================
            # SEGUNDA PASADA: JEFE_CODIGO -> jefe_id
            # =========================
            if idx_jefe_cod is not None:
                for idx, cols in enumerate(data_rows, start=2):
                    if not any((c or '').strip() for c in cols):
                        continue

                    def val2(i):
                        return (cols[i] or '').strip() if i is not None and i < len(cols) else ''

                    cedula_emp   = val2(idx_cedula)
                    jefe_codigo  = val2(idx_jefe_cod)

                    if not cedula_emp:
                        continue

                    # normalizar cédula empleado
                    cedula_emp = cedula_emp.strip()
                    if cedula_emp.isdigit() and len(cedula_emp) == 9:
                        cedula_emp = '0' + cedula_emp
                    cedula_emp_key = cedula_emp.lower().strip()

                    user_id = ident_to_id.get(cedula_emp_key)
                    if not user_id:
                        # no se insertó/actualizó este usuario (fila inválida antes)
                        continue

                    # Si JEFE_CODIGO viene vacío -> dejar sin jefe (NULL)
                    if not jefe_codigo:
                        try:
                            cur.execute("UPDATE usuarios SET jefe_id = NULL WHERE id = ?", (user_id,))
                            jefes_actualizados += 1
                        except Exception as e:
                            current_app.logger.exception(e)
                            invalidos += 1
                        continue

                    jefe_codigo = jefe_codigo.strip()
                    if jefe_codigo.isdigit() and len(jefe_codigo) == 9:
                        jefe_codigo = '0' + jefe_codigo
                    jefe_key = jefe_codigo.lower().strip()

                    jefe_user_id = ident_to_id.get(jefe_key)
                    if not jefe_user_id:
                        jefes_no_encontrados += 1
                        if len(ejemplos_error) < 10:
                            ejemplos_error.append(
                                f"fila {idx}: JEFE_CODIGO {jefe_codigo} no corresponde a ningún usuario"
                            )
                        continue

                    try:
                        cur.execute("UPDATE usuarios SET jefe_id = ? WHERE id = ?", (jefe_user_id, user_id))
                        jefes_actualizados += 1
                    except Exception as e:
                        current_app.logger.exception(e)
                        invalidos += 1

            conn.commit()

        except Exception as e:
            current_app.logger.exception(e)
            conn.rollback()
            flash(f'Error procesando la carga masiva: {e}', 'danger')
            conn.close()
            return redirect(url_for('usuarios'))

        conn.close()

        resumen = (
            f"Carga masiva de usuarios lista. "
            f"Insertados nuevos: {insertados} • "
            f"Actualizados (por cédula existente): {actualizados} • "
            f"Emails en uso por otro usuario: {dup_mail} • "
            f"Depto inexistente: {dep_inexist} • "
            f"Filas inválidas: {invalidos} • "
            f"Jefes actualizados: {jefes_actualizados} • "
            f"JEFE_CODIGO sin coincidencia: {jefes_no_encontrados}"
        )
        if ejemplos_error:
            resumen += " • Ejemplos errores: " + " | ".join(ejemplos_error[:5])

        flash(resumen, 'success' if (insertados or actualizados) > 0 else 'warning')
        return redirect(url_for('usuarios'))

    # =========================
    # DEPARTAMENTOS (ya existentes)
    # =========================
    @app.route('/departamentos', methods=['GET', 'POST'])
    @require_login
    @require_permission('departamentos', 'ver')
    def departamentos():
        conn = get_db(); cur = conn.cursor()
        if request.method == 'POST':
            nombre = (request.form.get('nombre') or '').strip()
            if not nombre:
                flash('El nombre del departamento es obligatorio.', 'danger')
                return redirect(url_for('departamentos'))
            try:
                cur.execute("INSERT INTO departamentos (nombre) VALUES (?)", (nombre,))
                conn.commit()
                flash('Departamento creado correctamente.', 'success')
            except Exception as e:
                current_app.logger.exception(e)
                flash('El nombre de departamento ya existe.', 'danger')

        cur.execute("SELECT id, nombre FROM departamentos ORDER BY nombre")
        lista = cur.fetchall()
        conn.close()
        return render_template('departamentos.html', departamentos=lista,
                               usuario=session['usuario'], rol=session['rol'],
                               active_page='departamentos')

    @app.route('/departamentos/<int:dep_id>/editar', methods=['GET', 'POST'])
    @require_login
    @require_permission('departamentos', 'editar')
    def editar_departamento(dep_id):
        conn = get_db(); cur = conn.cursor()
        cur.execute('SELECT id, nombre FROM departamentos WHERE id=?', (dep_id,))
        d = cur.fetchone()
        if not d:
            conn.close(); flash('Departamento no encontrado.', 'warning')
            return redirect(url_for('departamentos'))

        if request.method == 'POST':
            nombre = (request.form.get('nombre') or '').strip()
            if not nombre:
                flash('El nombre del departamento es obligatorio.', 'danger')
                return redirect(url_for('editar_departamento', dep_id=dep_id))
            try:
                cur.execute('UPDATE departamentos SET nombre=? WHERE id=?', (nombre, dep_id))
                conn.commit()
                flash('Departamento actualizado correctamente.', 'success')
            except Exception as e:
                current_app.logger.exception(e)
                flash('El nombre de departamento ya existe.', 'danger')
            finally:
                conn.close()
            return redirect(url_for('departamentos'))

        conn.close()
        return render_template('editar_departamento.html', departamento=d,
                               usuario=session['usuario'], rol=session['rol'],
                               active_page='departamentos')

    @app.route('/departamentos/<int:dep_id>/eliminar', methods=['POST'])
    @require_login
    @require_permission('departamentos', 'eliminar')
    def eliminar_departamento(dep_id):
        conn = get_db(); cur = conn.cursor()
        try:
            cur.execute("DELETE FROM departamentos WHERE id=?", (dep_id,))
            conn.commit()
            flash('Departamento eliminado.', 'success')
        except Exception as e:
            current_app.logger.exception(e)
            flash('No se pudo eliminar el departamento (puede estar en uso).', 'danger')
        finally:
            conn.close()
        return redirect(url_for('departamentos'))

    @app.route('/departamentos/nuevo', methods=['GET', 'POST'], endpoint='nuevo_departamento')
    @require_login
    @require_permission('departamentos', 'crear')
    def nuevo_departamento():
        if request.method == 'POST':
            nombre = (request.form.get('nombre') or '').strip()
            if not nombre:
                flash('El nombre del departamento es obligatorio.', 'danger')
                return redirect(url_for('nuevo_departamento'))

            conn = get_db(); cur = conn.cursor()
            try:
                cur.execute("INSERT INTO departamentos (nombre) VALUES (?)", (nombre,))
                conn.commit()
                flash('Departamento creado correctamente.', 'success')
                return redirect(url_for('departamentos'))
            except Exception as e:
                current_app.logger.exception(e)
                flash('El nombre de departamento ya existe.', 'danger')
            finally:
                conn.close()

        return render_template('nuevo_departamento.html',
                               usuario=session.get('usuario'),
                               rol=session.get('rol'),
                               active_page='departamentos')




    import csv
 
    @app.route('/departamentos/bulk', methods=['POST'], endpoint='departamentos_bulk')
    @require_login
    @require_permission('departamentos', 'editar')
    def departamentos_bulk():
        """
        Carga masiva de departamentos desde un archivo CSV.

        Formato esperado del archivo:
        - CSV con encabezado "nombre"
        - Cada fila = un departamento
        """
        file = request.files.get('archivo')  # nombre del input en el form

        if not file or file.filename == '':
            flash('Debe seleccionar un archivo para la carga masiva.', 'danger')
            return redirect(url_for('departamentos'))

        creados = 0
        duplicados = 0
        vacios = 0

        conn = get_db()
        cur = conn.cursor()

        try:
            # Interpretar como texto UTF-8 (soporta BOM)
            wrapper = TextIOWrapper(file.stream, encoding='utf-8-sig')
            reader = csv.DictReader(wrapper)

            if 'nombre' not in reader.fieldnames:
                flash('El archivo debe tener una columna "nombre".', 'danger')
                return redirect(url_for('departamentos'))

            for row in reader:
                nombre = (row.get('nombre') or '').strip()
                if not nombre:
                    vacios += 1
                    continue

                try:
                    cur.execute(
                        "INSERT INTO departamentos (nombre) VALUES (?)",
                        (nombre,)
                    )
                    creados += 1
                except Exception:
                    # Asumimos que el error típico es por nombre duplicado
                    duplicados += 1

            conn.commit()

            msg = f'Carga masiva terminada. Creados: {creados}'
            if duplicados:
                msg += f' | Duplicados/no insertados: {duplicados}'
            if vacios:
                msg += f' | Filas vacías: {vacios}'

            flash(msg, 'success')

        except Exception as e:
            conn.rollback()
            current_app.logger.exception(e)
            flash('Error procesando el archivo de carga masiva.', 'danger')
        finally:
            conn.close()

        return redirect(url_for('departamentos'))



    @app.route('/departamentos/bulk/template', methods=['GET'], endpoint='departamentos_bulk_template')
    @require_login
    @require_permission('departamentos', 'ver')
    def departamentos_bulk_template():
        """
        Devuelve una plantilla CSV para carga masiva de departamentos.
        Columnas:
        - nombre
        """
        output = io.StringIO()
        writer = csv.writer(output)
        # encabezado
        writer.writerow(['nombre'])
        # filas de ejemplo (puedes cambiar o borrar estas)
        writer.writerow(['LOGISTICA'])
        writer.writerow(['OPERACIONES'])
        writer.writerow(['COMERCIAL'])

        # Convertir a bytes para send_file
        mem = io.BytesIO()
        mem.write(output.getvalue().encode('utf-8-sig'))
        mem.seek(0)

        return send_file(
            mem,
            mimetype='text/csv',
            as_attachment=True,
            download_name='plantilla_departamentos.csv'
        )



    from flask import render_template
    from modules.db import get_db
    import sqlite3

# ...

# ... arriba ya tienes imports de Flask, get_db, require_login, require_permission, etc.

    from collections import deque

    @app.route('/organigrama', methods=['GET'])
    @require_login
    @require_permission('usuarios', 'ver')
    def organigrama():
        conn = get_db()
        cur = conn.cursor()

        # Traemos TODO lo que el template necesita:
        # - nombre
        # - identificacion
        # - rol
        # - departamento
        # - jefe_nombre (usando u.jefe_id)
        cur.execute("""
            SELECT
                u.id,
                COALESCE(u.nombre_completo, u.username) AS nombre,
                COALESCE(u.identificacion, '')         AS identificacion,
                COALESCE(u.rol, '')                    AS rol,
                COALESCE(d.nombre, 'Sin departamento') AS departamento,
                COALESCE(j.nombre_completo, j.username) AS jefe_nombre
            FROM usuarios u
            LEFT JOIN departamentos d ON d.id = u.departamento_id
            LEFT JOIN usuarios j ON j.id = u.jefe_id        -- jefe directo
            WHERE COALESCE(u.disabled, 0) = 0
            ORDER BY departamento, nombre
        """)

        rows = [dict(r) for r in cur.fetchall()]
        conn.close()

        # El template espera roots_flat
        roots_flat = rows

        return render_template(
            'organigrama.html',
            roots_flat=roots_flat,
            active_page='organigrama'
        )

    # =========================.html
    # AREAS / PUESTOS básicos
    # =========================
    @app.route('/areas', methods=['GET', 'POST'], endpoint='areas')
    @require_login
    @require_permission('areas', 'ver')
    def areas():
        conn = get_db()
        ensure_users_extra_schema(conn)
        cur = conn.cursor()
        if request.method == 'POST':
            nombre = (request.form.get('nombre') or '').strip()
            if not nombre:
                flash('Nombre requerido.', 'warning'); return redirect(url_for('areas'))
            try:
                cur.execute("INSERT INTO areas(nombre) VALUES (?)", (nombre,))
                conn.commit(); flash('Área creada.', 'success')
            except Exception as e:
                current_app.logger.exception(e)
                flash('El nombre ya existe.', 'danger')
        cur.execute("SELECT id,nombre,activo FROM areas ORDER BY nombre")
        lista = cur.fetchall(); conn.close()
        return render_template('areas.html', areas=lista, active_page='areas')
