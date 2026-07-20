# modules/routes_roles_permisos.py
from flask import render_template, request, redirect, url_for, flash, session
from .db import get_db
from .security import require_login, require_permission, has_permission


ACCIONES = ("ver", "crear", "editar", "eliminar", "exportar", "aprobar")

def _table_exists(conn, name):
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cur.fetchone() is not None

def _import_legacy_permisos(conn):
    if not _table_exists(conn, "permisos"):
        return
    cur = conn.cursor()

    cur.execute("INSERT OR IGNORE INTO roles(nombre) SELECT DISTINCT rol FROM permisos")
    cur.execute("INSERT OR IGNORE INTO opciones(nombre) SELECT DISTINCT opcion FROM permisos")

    # ⬇️ trae también aprobar (con COALESCE por si no existía)
    cur.execute("""
        SELECT rol, opcion, ver, crear, editar, eliminar, exportar, COALESCE(aprobar,0) AS aprobar
        FROM permisos
    """)
    rows = cur.fetchall()
    for r in rows:
        cur.execute("SELECT id FROM roles WHERE nombre=?", (r["rol"],))
        rid = cur.fetchone()["id"]
        cur.execute("SELECT id FROM opciones WHERE nombre=?", (r["opcion"],))
        oid = cur.fetchone()["id"]
        cur.execute("""
            INSERT INTO roles_permisos(rol_id, opcion_id, ver, crear, editar, eliminar, exportar, aprobar)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(rol_id, opcion_id) DO UPDATE SET
                ver=excluded.ver,
                crear=excluded.crear,
                editar=excluded.editar,
                eliminar=excluded.eliminar,
                exportar=excluded.exportar,
                aprobar=excluded.aprobar
        """, (rid, oid, r["ver"], r["crear"], r["editar"], r["eliminar"], r["exportar"], r["aprobar"]))
    conn.commit()

def _ensure_tables(conn):
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS roles(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS opciones(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS roles_permisos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rol_id INTEGER NOT NULL,
            opcion_id INTEGER NOT NULL,
            ver INTEGER DEFAULT 0,
            crear INTEGER DEFAULT 0,
            editar INTEGER DEFAULT 0,
            eliminar INTEGER DEFAULT 0,
            exportar INTEGER DEFAULT 0,
            aprobar INTEGER DEFAULT 0,     -- <- NUEVO
            FOREIGN KEY(rol_id) REFERENCES roles(id),
            FOREIGN KEY(opcion_id) REFERENCES opciones(id)
        )
    """)
    # Por si la tabla ya existía sin la columna:
    _add_column_if_missing(conn, "roles_permisos", "aprobar", "INTEGER DEFAULT 0", default=0)

    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_roles_permisos
        ON roles_permisos(rol_id, opcion_id)
    """)
    conn.commit()

def _get_or_create_role(conn, name):
    cur = conn.cursor()
    cur.execute("SELECT id FROM roles WHERE nombre=?", (name,))
    row = cur.fetchone()
    if row:
        return row["id"]
    cur.execute("INSERT INTO roles(nombre) VALUES (?)", (name,))
    conn.commit()
    return cur.lastrowid

def _get_or_create_opcion(conn, name):
    cur = conn.cursor()
    cur.execute("SELECT id FROM opciones WHERE nombre=?", (name,))
    row = cur.fetchone()
    if row:
        return row["id"]
    cur.execute("INSERT INTO opciones(nombre) VALUES (?)", (name,))
    conn.commit()
    return cur.lastrowid

def _seed_default_opciones(conn):
    """
    Garantiza que existan las opciones por defecto (no solo cuando la tabla está vacía).
    """
    defaults = [
        "dashboard",
        "departamentos",
        "usuarios",
        "puestos",
        "reclamos",
        "parametros",             # menú 'Parámetros del sistema' o legacy
        "roles_permisos",
        "seguridad",
        "cambio_clave",
        "tareas",
        "gastos_tarjeta",
        "reembolsos",
        "reembolsos_efectivo",
        "config",                 # parámetros del sistema (ruta nueva)
        "parametros_generales",   # parámetros generales
        "terceros",               # ← NUEVO (Clientes / Proveedores)
        "contratos_ingresar",
        "contratos_garantias",
        "contratos_aprobaciones",
        "gastos_pendientes_aprobacion",
        "facturas_xml_list",
        "reporte_gastos",
        "proveedores",
        "listar_encuestas",

    ]

    cur = conn.cursor()
    cur.execute("SELECT nombre FROM opciones")
    existentes = {row["nombre"] for row in cur.fetchall()}

    for name in defaults:
        if name not in existentes:
            _get_or_create_opcion(conn, name)


def _ensure_legacy_permisos(conn):
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS permisos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rol TEXT NOT NULL,
            opcion TEXT NOT NULL,
            ver INTEGER DEFAULT 0,
            crear INTEGER DEFAULT 0,
            editar INTEGER DEFAULT 0,
            eliminar INTEGER DEFAULT 0,
            exportar INTEGER DEFAULT 0,
            aprobar INTEGER DEFAULT 0  -- <- NUEVO
        )
    """)
    _add_column_if_missing(conn, "permisos", "aprobar", "INTEGER DEFAULT 0", default=0)
    cur.execute("CREATE INDEX IF NOT EXISTS ix_perm_rol_opcion ON permisos(rol, opcion)")
    conn.commit()

def _get_permisos_por_rol(conn, role_name: str):
    cur = conn.cursor()
    cur.execute("SELECT id FROM roles WHERE nombre=?", (role_name,))
    r = cur.fetchone()
    rol_id = r['id'] if r else None

    # Todas las opciones, con LEFT JOIN a permisos del rol
    cur.execute("""
        SELECT o.nombre AS opcion,
               COALESCE(rp.ver,0)      AS ver,
               COALESCE(rp.crear,0)    AS crear,
               COALESCE(rp.editar,0)   AS editar,
               COALESCE(rp.eliminar,0) AS eliminar,
               COALESCE(rp.exportar,0) AS exportar,
               COALESCE(rp.aprobar,0)  AS aprobar
        FROM opciones o
        LEFT JOIN roles_permisos rp
               ON rp.opcion_id = o.id AND rp.rol_id = ?
        ORDER BY o.nombre
    """, (rol_id,))
    data = {}
    for row in cur.fetchall():
        data[row['opcion']] = dict(
            ver=bool(row['ver']),
            crear=bool(row['crear']),
            editar=bool(row['editar']),
            eliminar=bool(row['eliminar']),
            exportar=bool(row['exportar']),
            aprobar=bool(row['aprobar']),  # <- NUEVO
        )
    return data

def roles_permisos():
    conn = get_db(); _ensure_tables(conn)
    cur = conn.cursor()

    # roles para el selector
    cur.execute("SELECT nombre FROM roles ORDER BY nombre")
    roles = [r['nombre'] for r in cur.fetchall()]
    selected_role = request.values.get('rol') or (roles[0] if roles else '')

    if request.method == 'POST' and request.form.get('save') is not None:
        # ids
        cur.execute("SELECT id FROM roles WHERE nombre=?", (selected_role,))
        rol_id = cur.fetchone()['id']

        cur.execute("SELECT id, nombre FROM opciones ORDER BY nombre")
        opciones = cur.fetchall()

        for o in opciones:
            op = o['nombre']
            flags = {
                'ver':      1 if f"{op}_ver"      in request.form else 0,
                'crear':    1 if f"{op}_crear"    in request.form else 0,
                'editar':   1 if f"{op}_editar"   in request.form else 0,
                'eliminar': 1 if f"{op}_eliminar" in request.form else 0,
                'exportar': 1 if f"{op}_exportar" in request.form else 0,
                'aprobar':  1 if f"{op}_aprobar"  in request.form else 0,  # <- NUEVO
            }

            cur.execute("""
                INSERT INTO roles_permisos(rol_id, opcion_id, ver, crear, editar, eliminar, exportar, aprobar)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(rol_id, opcion_id) DO UPDATE SET
                    ver=excluded.ver,
                    crear=excluded.crear,
                    editar=excluded.editar,
                    eliminar=excluded.eliminar,
                    exportar=excluded.exportar,
                    aprobar=excluded.aprobar
            """, (rol_id, o['id'],
                  flags['ver'], flags['crear'], flags['editar'],
                  flags['eliminar'], flags['exportar'], flags['aprobar']))

        conn.commit()
        _sync_legacy_permisos(conn, selected_role)  # mantiene la tabla legacy si la usas

        # vuelve con toast
        permisos = _get_permisos_por_rol(conn, selected_role)
        return render_template('roles_permisos.html',
                               roles=roles,
                               selected_role=selected_role,
                               permisos=permisos,
                               show_saved=True,
                               usuario=session.get('usuario'),
                               rol=session.get('rol'),
                               active_page='roles_permisos')

    # GET normal
    permisos = _get_permisos_por_rol(conn, selected_role)
    return render_template('roles_permisos.html',
                           roles=roles,
                           selected_role=selected_role,
                           permisos=permisos,
                           show_saved=False,
                           usuario=session.get('usuario'),
                           rol=session.get('rol'),
                           active_page='roles_permisos')


def _sync_legacy_permisos(conn, role_name: str):
    _ensure_legacy_permisos(conn)
    cur = conn.cursor()
    cur.execute("DELETE FROM permisos WHERE rol=?", (role_name,))
    cur.execute("""
        INSERT INTO permisos(rol, opcion, ver, crear, editar, eliminar, exportar, aprobar)
        SELECT r.nombre, o.nombre, rp.ver, rp.crear, rp.editar, rp.eliminar, rp.exportar, rp.aprobar
        FROM roles_permisos rp
        JOIN roles    r ON r.id = rp.rol_id
        JOIN opciones o ON o.id = rp.opcion_id
        WHERE r.nombre = ?
    """, (role_name,))
    conn.commit()


# modules/routes_roles_permisos.py

def _add_column_if_missing(conn, table, col, decl_sql, default=None):
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    cols = {r[1] for r in cur.fetchall()}
    if col not in cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl_sql}")
        if default is not None:
            cur.execute(f"UPDATE {table} SET {col}=?", (default,))
        conn.commit()


def register_roles_permisos_routes(app):

    @app.route("/roles-permisos", methods=["GET", "POST"], endpoint="roles_permisos")
    @require_login
    @require_permission("roles_permisos", "ver")
    def roles_permisos_view():
        conn = get_db(); cur = conn.cursor()
        _ensure_tables(conn)
        _seed_default_opciones(conn)
        _import_legacy_permisos(conn)   # opcional: importar desde tabla legacy si existe

        # --- Rol seleccionado (prioriza GET, luego POST) ---
        selected_role = (request.args.get("rol") or request.form.get("rol") or "").strip()

        # --- Lista de roles; si no hay, sembramos y recargamos ---
        cur.execute("SELECT nombre FROM roles ORDER BY nombre")
        roles = [r["nombre"] for r in cur.fetchall()]
        if not roles:
            for rname in ("admin", "usuario", "jefe"):
                _get_or_create_role(conn, rname)
            cur.execute("SELECT nombre FROM roles ORDER BY nombre")
            roles = [r["nombre"] for r in cur.fetchall()]

        if not selected_role:
            selected_role = roles[0]

        # --- Normalizar nombre de rol (case-insensitive) y obtener rol_id ---
        cur.execute("SELECT id, nombre FROM roles WHERE LOWER(nombre)=LOWER(?)", (selected_role,))
        rol_row = cur.fetchone()
        if not rol_row:
            _get_or_create_role(conn, selected_role)
            cur.execute("SELECT id, nombre FROM roles WHERE LOWER(nombre)=LOWER(?)", (selected_role,))
            rol_row = cur.fetchone()
        rol_id = rol_row["id"]
        selected_role = rol_row["nombre"]  # usar nombre canónico

        # ======================= GUARDAR CAMBIOS =========================
        if request.method == "POST" and "save" in request.form:
            # Verificar permiso de edición
            if not has_permission(session.get("rol"), "roles_permisos", "editar"):
                flash("No tiene permiso para editar los roles y permisos.", "danger")
                conn.close()
                return redirect(url_for("roles_permisos", rol=selected_role))

            acciones = ACCIONES  # <- usa la constante global (incluye 'aprobar')

            # Construir mapa de cambios a partir de los nombres de los inputs
            cambios = {}  # { opcion: {acc:0/1} }
            for key in request.form.keys():
                if key in ("save", "rol"):
                    continue
                for acc in acciones:
                    suf = f"_{acc}"
                    if key.endswith(suf):
                        op_name = key[:-len(suf)]
                        cambios.setdefault(op_name, {a: 0 for a in acciones})
                        cambios[op_name][acc] = 1
                        break

            # Asegura que TODAS las opciones queden en el dict (para forzar 0)
            cur.execute("SELECT nombre FROM opciones")
            for op_name in (row["nombre"] for row in cur.fetchall()):
                cambios.setdefault(op_name, {a: 0 for a in acciones})

            # Limpia y re-inserta (simple y seguro)
            cur.execute("DELETE FROM roles_permisos WHERE rol_id=?", (rol_id,))

            for op_name, flags in cambios.items():
                cur.execute("SELECT id FROM opciones WHERE nombre=?", (op_name,))
                orow = cur.fetchone()
                if not orow:
                    _get_or_create_opcion(conn, op_name)
                    cur.execute("SELECT id FROM opciones WHERE nombre=?", (op_name,))
                    orow = cur.fetchone()
                opcion_id = orow["id"]

                cur.execute("""
                    INSERT INTO roles_permisos(rol_id, opcion_id, ver, crear, editar, eliminar, exportar, aprobar)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    rol_id, opcion_id,
                    flags.get("ver", 0),
                    flags.get("crear", 0),
                    flags.get("editar", 0),
                    flags.get("eliminar", 0),
                    flags.get("exportar", 0),
                    flags.get("aprobar", 0),
                ))

            conn.commit()
            # opcional: sincroniza la tabla legacy 'permisos'
            _sync_legacy_permisos(conn, selected_role)
            conn.close()
            return redirect(url_for("roles_permisos", rol=selected_role, saved=1))
        # =================================================================

        # --------- LECTURA PARA MOSTRAR MATRIZ ----------
        cur.execute("""
            SELECT o.nombre AS opcion,
                COALESCE(rp.ver,0)       AS ver,
                COALESCE(rp.crear,0)     AS crear,
                COALESCE(rp.editar,0)    AS editar,
                COALESCE(rp.eliminar,0)  AS eliminar,
                COALESCE(rp.exportar,0)  AS exportar,
                COALESCE(rp.aprobar,0)   AS aprobar
            FROM opciones o
            LEFT JOIN roles_permisos rp
                ON rp.opcion_id = o.id AND rp.rol_id = ?
            ORDER BY o.nombre
        """, (rol_id,))
        rows = cur.fetchall()
        permisos = {
            r["opcion"]: {
                "ver":      bool(r["ver"]),
                "crear":    bool(r["crear"]),
                "editar":   bool(r["editar"]),
                "eliminar": bool(r["eliminar"]),
                "exportar": bool(r["exportar"]),
                "aprobar":  bool(r["aprobar"]),
            } for r in rows
        }

        show_saved = (request.args.get("saved") == "1")
        conn.close()

        return render_template(
            "roles_permisos.html",
            roles=roles,
            selected_role=selected_role,
            permisos=permisos,
            show_saved=show_saved,
            usuario=session.get("usuario"),
            rol=session.get("rol"),
            active_page="roles_permisos",
        )
