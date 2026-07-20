# modules/routes_menu.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from modules.db import get_db
from werkzeug.routing import BuildError
from collections import defaultdict
from pathlib import Path
from datetime import datetime
import re

menu_bp = Blueprint('menu', __name__, template_folder='templates')

# Registro de recursos dinámicos: slug -> {table,label}
DYNAMIC_CRUD: dict[str, dict] = {}


# =========================================================
# Helpers SQL Server
# =========================================================
def _row_to_dict(row, cursor=None):
    if row is None:
        return None

    if isinstance(row, dict):
        return row

    if hasattr(row, "_asdict"):
        return row._asdict()

    if cursor is not None and cursor.description:
        cols = [col[0] for col in cursor.description]
        return dict(zip(cols, row))

    try:
        return dict(row)
    except Exception:
        return None


def _rows_to_dicts(rows, cursor=None):
    if not rows:
        return []
    return [_row_to_dict(r, cursor) for r in rows]


def _fetchone_dict(cur, query, params=()):
    cur.execute(query, params)
    row = cur.fetchone()
    return _row_to_dict(row, cur)


def _fetchall_dict(cur, query, params=()):
    cur.execute(query, params)
    rows = cur.fetchall()
    return _rows_to_dicts(rows, cur)


def _safe_sql_identifier(name: str) -> str:
    """
    Valida identificadores dinámicos para evitar inyección en nombres de tablas.
    Solo admite letras, números y guion bajo, empezando por letra o guion bajo.
    """
    if not name or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError(f"Identificador SQL inválido: {name}")
    return name


def _utc_now():
    return datetime.utcnow()


# =========================================================
# Templates autogenerados
# =========================================================
def _ensure_autogen_templates(slug: str, label: str):
    base_dir = Path(current_app.root_path) / 'templates' / 'autogen'
    base_dir.mkdir(parents=True, exist_ok=True)

    list_tpl = base_dir / f'{slug}_list.html'
    form_tpl = base_dir / f'{slug}_form.html'

    if not list_tpl.exists():
        list_tpl.write_text(f"""{{% extends 'base.html' %}}
{{% block title %}}{label}{{% endblock %}}
{{% block content %}}
<div class="d-flex align-items-center justify-content-between mb-3">
  <h1 class="h5 mb-0">{label}</h1>
  <a class="btn btn-primary" href="{{{{ url_for('{slug}_new') }}}}"><i class="bi bi-plus"></i> Nuevo</a>
</div>

<table class="table table-sm table-dark align-middle">
  <thead>
    <tr>
      <th>ID</th><th>Campo 1</th><th>Campo 2</th><th>Campo 3</th><th>Email 1</th><th>Email 2</th><th></th>
    </tr>
  </thead>
  <tbody>
  {{% for r in rows %}}
    <tr>
      <td>{{{{ r.id }}}}</td>
      <td>{{{{ r.campo1 or '' }}}}</td>
      <td>{{{{ r.campo2 or '' }}}}</td>
      <td>{{{{ r.campo3 or '' }}}}</td>
      <td>{{{{ r.email1 or '' }}}}</td>
      <td>{{{{ r.email2 or '' }}}}</td>
      <td class="text-end">
        <a class="btn btn-sm btn-outline-light" href="{{{{ url_for('{slug}_edit', item_id=r.id) }}}}">Editar</a>
        <form class="d-inline" method="post" action="{{{{ url_for('{slug}_delete', item_id=r.id) }}}}" onsubmit="return confirm('¿Eliminar registro?');">
          <button class="btn btn-sm btn-outline-danger">Borrar</button>
        </form>
      </td>
    </tr>
  {{% endfor %}}
  </tbody>
</table>
{{% endblock %}}
""", encoding='utf-8')

    if not form_tpl.exists():
        form_tpl.write_text(f"""{{% extends 'base.html' %}}
{{% block title %}}{label} - {{% if item %}}Editar{{% else %}}Nuevo{{% endif %}}{{% endblock %}}
{{% block content %}}
<h4 class="mb-3">{label} - {{% if item %}}Editar{{% else %}}Nuevo{{% endif %}}</h4>
<form method="post" class="row g-3">
  <div class="col-md-4">
    <label class="form-label">Campo 1</label>
    <input name="campo1" class="form-control" value="{{{{ item.campo1 if item else '' }}}}">
  </div>
  <div class="col-md-4">
    <label class="form-label">Campo 2</label>
    <input name="campo2" class="form-control" value="{{{{ item.campo2 if item else '' }}}}">
  </div>
  <div class="col-md-4">
    <label class="form-label">Campo 3</label>
    <input name="campo3" class="form-control" value="{{{{ item.campo3 if item else '' }}}}">
  </div>
  <div class="col-md-6">
    <label class="form-label">Email 1</label>
    <input name="email1" type="email" class="form-control" value="{{{{ item.email1 if item else '' }}}}">
  </div>
  <div class="col-md-6">
    <label class="form-label">Email 2</label>
    <input name="email2" type="email" class="form-control" value="{{{{ item.email2 if item else '' }}}}">
  </div>

  <div class="col-12">
    <button class="btn btn-primary">Guardar</button>
    <a href="{{{{ url_for('{slug}') }}}}" class="btn btn-outline-secondary">Cancelar</a>
  </div>
</form>
{{% endblock %}}
""", encoding='utf-8')


def _rule_exists(ep: str) -> bool:
    return any(r.endpoint == ep for r in current_app.url_map.iter_rules())


def _slugify(label: str) -> str:
    s = (label or '').lower().strip()
    s = re.sub(r'[^a-z0-9]+', '_', s)
    s = re.sub(r'_+', '_', s).strip('_')
    if not s:
        s = 'recurso'
    return s


# =========================================================
# CRUD dinámico SQL Server
# =========================================================
def _ensure_crud_table(conn, table: str):
    table = _safe_sql_identifier(table)
    cur = conn.cursor()

    sql = f"""
    IF OBJECT_ID('dbo.{table}', 'U') IS NULL
    BEGIN
        CREATE TABLE dbo.{table} (
            id INT IDENTITY(1,1) PRIMARY KEY,
            campo1 NVARCHAR(255) NULL,
            campo2 NVARCHAR(255) NULL,
            campo3 NVARCHAR(255) NULL,
            email1 NVARCHAR(255) NULL,
            email2 NVARCHAR(255) NULL,
            created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
            updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
        );
    END
    """
    cur.execute(sql)
    conn.commit()


def _register_crud_endpoints(slug: str, label: str, table: str):
    table = _safe_sql_identifier(table)
    DYNAMIC_CRUD[slug] = {'table': table, 'label': label}

    def list_view():
        session['active_page'] = slug
        conn = get_db()
        cur = conn.cursor()

        rows = _fetchall_dict(
            cur,
            f"""
            SELECT id, campo1, campo2, campo3, email1, email2, created_at, updated_at
            FROM dbo.{table}
            ORDER BY id DESC
            """
        )
        conn.close()

        return render_template(
            f'autogen/{slug}_list.html',
            rows=rows,
            label=label,
            active_page=slug
        )

    def form_view(item_id=None):
        session['active_page'] = slug
        conn = get_db()
        cur = conn.cursor()

        if request.method == 'POST':
            data = {
                'campo1': request.form.get('campo1', '').strip(),
                'campo2': request.form.get('campo2', '').strip(),
                'campo3': request.form.get('campo3', '').strip(),
                'email1': request.form.get('email1', '').strip(),
                'email2': request.form.get('email2', '').strip(),
                'now': _utc_now()
            }

            for k in ('email1', 'email2'):
                if data[k] and '@' not in data[k]:
                    flash(f'{k} no parece un correo válido', 'warning')
                    if item_id:
                        item = _fetchone_dict(
                            cur,
                            f"SELECT * FROM dbo.{table} WHERE id = ?",
                            (item_id,)
                        )
                        conn.close()
                        return render_template(
                            f'autogen/{slug}_form.html',
                            item=item,
                            label=label,
                            active_page=slug
                        )

            if item_id:
                cur.execute(
                    f"""
                    UPDATE dbo.{table}
                    SET campo1 = ?, campo2 = ?, campo3 = ?, email1 = ?, email2 = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        data['campo1'], data['campo2'], data['campo3'],
                        data['email1'], data['email2'], data['now'], item_id
                    )
                )
                flash('Registro actualizado', 'success')
            else:
                cur.execute(
                    f"""
                    INSERT INTO dbo.{table} (
                        campo1, campo2, campo3, email1, email2, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        data['campo1'], data['campo2'], data['campo3'],
                        data['email1'], data['email2'], data['now'], data['now']
                    )
                )
                flash('Registro creado', 'success')

            conn.commit()
            conn.close()
            return redirect(url_for(slug))

        item = None
        if item_id:
            item = _fetchone_dict(
                cur,
                f"SELECT * FROM dbo.{table} WHERE id = ?",
                (item_id,)
            )

        conn.close()
        return render_template(
            f'autogen/{slug}_form.html',
            item=item,
            label=label,
            active_page=slug
        )

    def delete_view(item_id):
        conn = get_db()
        cur = conn.cursor()
        cur.execute(f"DELETE FROM dbo.{table} WHERE id = ?", (item_id,))
        conn.commit()
        conn.close()
        flash('Registro eliminado', 'success')
        return redirect(url_for(slug))

    if not _rule_exists(slug):
        current_app.add_url_rule(f'/{slug}', endpoint=slug, view_func=list_view, methods=['GET'])
    if not _rule_exists(f'{slug}_new'):
        current_app.add_url_rule(f'/{slug}/new', endpoint=f'{slug}_new', view_func=form_view, methods=['GET', 'POST'])
    if not _rule_exists(f'{slug}_edit'):
        current_app.add_url_rule(f'/{slug}/<int:item_id>/edit', endpoint=f'{slug}_edit', view_func=form_view, methods=['GET', 'POST'])
    if not _rule_exists(f'{slug}_delete'):
        current_app.add_url_rule(f'/{slug}/<int:item_id>/delete', endpoint=f'{slug}_delete', view_func=delete_view, methods=['POST'])


# =========================================================
# Menú SQL Server
# =========================================================
def ensure_menu_schema(conn):
    cur = conn.cursor()

    cur.execute("""
    IF OBJECT_ID('dbo.menu_items', 'U') IS NULL
    BEGIN
        CREATE TABLE dbo.menu_items (
            id INT IDENTITY(1,1) PRIMARY KEY,
            parent_id INT NULL,
            label NVARCHAR(255) NOT NULL,
            endpoint NVARCHAR(255) NULL,
            external_url NVARCHAR(500) NULL,
            icon NVARCHAR(255) NULL,
            order_no INT NOT NULL DEFAULT 0,
            permission NVARCHAR(255) NULL,
            active_key NVARCHAR(255) NULL,
            is_group BIT NOT NULL DEFAULT 0,
            is_collaps BIT NOT NULL DEFAULT 0,
            CONSTRAINT UQ_menu_items_label_parent UNIQUE (label, parent_id)
        );
    END
    """)

    cur.execute("""
    IF NOT EXISTS (
        SELECT 1
        FROM sys.indexes
        WHERE name = 'idx_menu_parent'
          AND object_id = OBJECT_ID('dbo.menu_items')
    )
    BEGIN
        CREATE INDEX idx_menu_parent ON dbo.menu_items(parent_id, order_no);
    END
    """)

    conn.commit()


def seed_menu_if_empty(conn):
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM dbo.menu_items")
    row = cur.fetchone()
    total = row[0] if row else 0

    if total > 0:
        return

    # === raíz ===
    cur.execute("""
        INSERT INTO dbo.menu_items(label, icon, is_group, is_collaps, order_no)
        VALUES (?, ?, ?, ?, ?)
    """, ('Configuraciones', 'bi bi-gear', 1, 1, 1))
    cur.execute("SELECT CAST(SCOPE_IDENTITY() AS INT)")
    cfg_id = cur.fetchone()[0]

    cur.execute("""
        INSERT INTO dbo.menu_items(label, icon, is_group, is_collaps, order_no)
        VALUES (?, ?, ?, ?, ?)
    """, ('Bitácora', 'bi bi-journal-text', 1, 1, 2))
    cur.execute("SELECT CAST(SCOPE_IDENTITY() AS INT)")
    bit_id = cur.fetchone()[0]

    cur.execute("""
        INSERT INTO dbo.menu_items(label, icon, is_group, is_collaps, order_no)
        VALUES (?, ?, ?, ?, ?)
    """, ('Reembolsos', 'bi bi-wallet2', 1, 1, 3))
    cur.execute("SELECT CAST(SCOPE_IDENTITY() AS INT)")
    reb_id = cur.fetchone()[0]

    # === hijos Configuraciones ===
    cur.executemany("""
        INSERT INTO dbo.menu_items(parent_id, label, endpoint, icon, permission, active_key, order_no)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, [
        (cfg_id, 'Departamentos', 'departamentos', 'bi bi-building', 'departamentos', 'departamentos', 1),
        (cfg_id, 'Usuarios', 'usuarios', 'bi bi-people', 'usuarios', 'usuarios', 2),
        (cfg_id, 'Parámetros del sistema', 'config', 'bi bi-sliders', 'parametros', 'config', 3),
        (cfg_id, 'Parámetros generales', 'parametros_generales', 'bi bi-card-list', 'parametros', 'parametros_generales', 4),
        (cfg_id, 'Roles y permisos', 'roles_permisos', 'bi bi-shield-lock', 'roles_permisos', 'roles_permisos', 5),
        (cfg_id, 'Políticas de seguridad', 'politicas_seguridad', 'bi bi-shield-check', 'seguridad', 'seguridad', 6),
        (cfg_id, 'Cambiar clave', 'cambiar_clave', 'bi bi-key', 'cambio_clave', 'cambiar_clave', 7),
        (cfg_id, 'Menú del sistema', 'menu_admin', 'bi bi-list', 'menu', 'menu_admin', 8),
    ])

    # === Bitácora ===
    cur.execute("""
        INSERT INTO dbo.menu_items(parent_id, label, endpoint, icon, permission, active_key, order_no)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (bit_id, 'Tareas', 'listar_tareas', 'bi bi-list-task', 'tareas', 'tareas', 1))

    # === Reembolsos (con submenú) ===
    cur.execute("""
        INSERT INTO dbo.menu_items(parent_id, label, icon, is_group, is_collaps, order_no)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (reb_id, 'Reembolsos', 'bi bi-wallet2', 1, 1, 1))
    cur.execute("SELECT CAST(SCOPE_IDENTITY() AS INT)")
    sub_r = cur.fetchone()[0]

    cur.executemany("""
        INSERT INTO dbo.menu_items(parent_id, label, endpoint, permission, active_key, order_no)
        VALUES (?, ?, ?, ?, ?, ?)
    """, [
        (sub_r, 'Inicio', 'reembolsos', 'reembolsos', 'reembolsos', 1),
        (sub_r, 'Gastos con tarjeta', 'lista_gastos', 'reembolsos', 'gastos_tarjeta', 2),
        (sub_r, 'Reembolsos en efectivo', 'reembolsos_efectivo', 'reembolsos', 'reembolsos_efectivo', 3),
    ])

    # === Clientes / Proveedores ===
    cur.execute("""
        INSERT INTO dbo.menu_items(parent_id, label, icon, is_group, is_collaps, order_no)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (cfg_id, 'Clientes / Proveedores', 'bi bi-people-fill', 1, 1, 9))
    cur.execute("SELECT CAST(SCOPE_IDENTITY() AS INT)")
    ter_id = cur.fetchone()[0]

    cur.executemany("""
        INSERT INTO dbo.menu_items(parent_id, label, endpoint, permission, active_key, order_no)
        VALUES (?, ?, ?, ?, ?, ?)
    """, [
        (ter_id, 'Clientes', 'clientes', 'terceros', 'clientes', 1),
        (ter_id, 'Proveedores', 'proveedores', 'terceros', 'proveedores', 2),
    ])

    conn.commit()


def fetch_menu_tree(conn, permissions, active_page=None, is_admin=False):
    """
    Devuelve el árbol de menú filtrado por permisos.
    - Muestra todo si is_admin=True.
    - Acepta permiso 'modulo' o 'modulo:accion' en 'permission' (o 'permission_key' legacy).
    - Mantiene el padre si tiene hijos visibles aunque el padre no tenga permiso propio.
    - Marca activo si él o alguno de sus hijos coincide con active_page.
    """
    cur = conn.cursor()
    rows = _fetchall_dict(cur, """
        SELECT *
        FROM dbo.menu_items
        ORDER BY ISNULL(parent_id, 0), order_no, id
    """)

    def can_show(n: dict) -> bool:
        if is_admin:
            return True
        perm = (n.get('permission_key') or n.get('permission') or '').strip()
        if not perm:
            return True
        mod, _, action = perm.partition(':')
        action = action or 'ver'
        return bool(permissions.get(mod, {}).get(action))

    by_parent = defaultdict(list)
    for n in rows:
        ep = (n.get('endpoint') or '').strip()
        ext = (n.get('external_url') or '').strip()
        n['href'] = ext or _resolve_endpoint_href(ep)
        if active_page:
            n['active'] = (n.get('active_key') == active_page)
        else:
            n['active'] = False
        by_parent[n.get('parent_id')].append(n)

    def build(pid=None):
        out = []
        for n in sorted(by_parent.get(pid, []), key=lambda x: (x.get('order_no', 0), x.get('id'))):
            children = build(n['id'])
            show_self = can_show(n)
            if not show_self and not children:
                continue
            node = {**n}
            node['children'] = children
            node['active'] = node.get('active', False) or any(c.get('active') for c in children)
            out.append(node)
        return out

    return build(None)


def _resolve_endpoint_href(ep: str) -> str | None:
    if not ep:
        return None

    if '://' in ep or ep.startswith('/'):
        return ep

    try:
        return url_for(ep)
    except BuildError:
        pass

    if '.' not in ep:
        try:
            return url_for(f'menu.{ep}')
        except BuildError:
            pass

        candidates = [
            r.endpoint for r in current_app.url_map.iter_rules()
            if r.endpoint.endswith(f'.{ep}')
        ]
        if len(candidates) == 1:
            try:
                return url_for(candidates[0])
            except BuildError:
                pass

    return None


# =========================================================
# UI de administración
# =========================================================
@menu_bp.route('/config/menu', methods=['GET'], endpoint='menu_admin')
def menu_admin():
    conn = get_db()
    ensure_menu_schema(conn)
    seed_menu_if_empty(conn)

    cur = conn.cursor()
    items = _fetchall_dict(cur, """
        SELECT *
        FROM dbo.menu_items
        ORDER BY parent_id, order_no, id
    """)
    conn.close()

    return render_template(
        'menu_admin.html',
        items=items,
        usuario=session.get('usuario'),
        rol=session.get('rol'),
        active_page='menu_admin'
    )


@menu_bp.route('/config/menu/new', methods=['GET', 'POST'], endpoint='menu_new')
@menu_bp.route('/config/menu/<int:item_id>/edit', methods=['GET', 'POST'], endpoint='menu_edit')
def menu_edit(item_id=None):
    conn = get_db()
    ensure_menu_schema(conn)
    cur = conn.cursor()

    if request.method == 'POST':
        data = {
            'label': (request.form.get('label') or '').strip(),
            'parent_id': request.form.get('parent_id') or None,
            'endpoint': (request.form.get('endpoint') or '').strip() or None,
            'external_url': (request.form.get('external_url') or '').strip() or None,
            'icon': (request.form.get('icon') or '').strip() or None,
            'order_no': int(request.form.get('order_no') or 0),
            'permission': (request.form.get('permission') or '').strip() or None,
            'active_key': (request.form.get('active_key') or '').strip() or None,
            'is_group': 1 if request.form.get('is_group') == '1' else 0,
            'is_collaps': 1 if request.form.get('is_collaps') == '1' else 0,
        }

        parent_id = int(data['parent_id']) if data['parent_id'] not in (None, '', 'None') else None

        if item_id:
            cur.execute("""
                UPDATE dbo.menu_items
                SET parent_id = ?, label = ?, endpoint = ?, external_url = ?, icon = ?, order_no = ?,
                    permission = ?, active_key = ?, is_group = ?, is_collaps = ?
                WHERE id = ?
            """, (
                parent_id, data['label'], data['endpoint'], data['external_url'],
                data['icon'], data['order_no'], data['permission'], data['active_key'],
                data['is_group'], data['is_collaps'], item_id
            ))
            conn.commit()
            flash('Opción actualizada.', 'success')

        else:
            cur.execute("""
                INSERT INTO dbo.menu_items
                (parent_id, label, endpoint, external_url, icon, order_no, permission, active_key, is_group, is_collaps)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                parent_id, data['label'], data['endpoint'], data['external_url'],
                data['icon'], data['order_no'], data['permission'], data['active_key'],
                data['is_group'], data['is_collaps']
            ))

            cur.execute("SELECT CAST(SCOPE_IDENTITY() AS INT)")
            new_id = cur.fetchone()[0]
            conn.commit()
            flash('Opción creada.', 'success')

            if data['is_group'] == 0 and not data['external_url']:
                slug = _slugify(data['endpoint'] or data['label'])

                if (data['endpoint'] or '') != slug:
                    cur.execute("UPDATE dbo.menu_items SET endpoint = ? WHERE id = ?", (slug, new_id))
                    conn.commit()

                table = f'crud_{slug}'
                _ensure_crud_table(conn, table)
                _ensure_autogen_templates(slug, data['label'])
                _register_crud_endpoints(slug, data['label'], table)

        conn.close()
        return redirect(url_for('menu.menu_admin'))

    item = None
    if item_id:
        item = _fetchone_dict(cur, "SELECT * FROM dbo.menu_items WHERE id = ?", (item_id,))

    parents = _fetchall_dict(
        cur,
        "SELECT id, label FROM dbo.menu_items WHERE is_group = 1 ORDER BY label"
    )
    conn.close()

    return render_template(
        'menu_form.html',
        item=item,
        parents=parents,
        usuario=session.get('usuario'),
        rol=session.get('rol'),
        active_page='menu_admin'
    )


def sync_permissions_from_menu(conn):
    """
    Crea en `opciones` todas las claves usadas en menu_items.permission.
    """
    cur = conn.cursor()

    cur.execute("""
    IF OBJECT_ID('dbo.opciones', 'U') IS NULL
    BEGIN
        CREATE TABLE dbo.opciones (
            id INT IDENTITY(1,1) PRIMARY KEY,
            nombre NVARCHAR(255) NOT NULL UNIQUE
        );
    END
    """)

    rows = _fetchall_dict(cur, """
        SELECT DISTINCT LTRIM(RTRIM(permission)) AS k
        FROM dbo.menu_items
        WHERE LTRIM(RTRIM(ISNULL(permission, ''))) <> ''
    """)

    for r in rows:
        k = (r['k'] or '').strip()
        if not k:
            continue

        cur.execute("""
        IF NOT EXISTS (SELECT 1 FROM dbo.opciones WHERE nombre = ?)
        BEGIN
            INSERT INTO dbo.opciones(nombre) VALUES (?)
        END
        """, (k, k))

    conn.commit()


def ensure_admin_full_perms(conn):
    """
    Da permisos completos al rol Admin para todas las opciones nuevas.
    Requiere que exista restricción UNIQUE(rol_id, opcion_id) en roles_permisos.
    """
    cur = conn.cursor()

    cur.execute("SELECT id FROM dbo.roles WHERE LOWER(nombre) = 'admin'")
    row = cur.fetchone()
    if not row:
        return

    rid = row[0]

    cur.execute("""
        INSERT INTO dbo.roles_permisos
            (rol_id, opcion_id, ver, crear, editar, eliminar, exportar, aprobar)
        SELECT ?, o.id, 1, 1, 1, 1, 1, 1
        FROM dbo.opciones o
        WHERE NOT EXISTS (
            SELECT 1
            FROM dbo.roles_permisos rp
            WHERE rp.rol_id = ?
              AND rp.opcion_id = o.id
        )
    """, (rid, rid))

    conn.commit()


@menu_bp.post('/config/menu/<int:item_id>/delete')
def menu_delete(item_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM dbo.menu_items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    flash('Opción eliminada.', 'success')
    return redirect(url_for('menu.menu_admin'))