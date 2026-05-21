from collections import defaultdict

from flask import current_app

from .menu_constants import EMAIL_FIELDS
from .menu_notifications import (
    flash_invalid_email,
    flash_option_created,
    flash_option_deleted,
    flash_option_updated,
    flash_record_created,
    flash_record_deleted,
    flash_record_updated,
)
from .menu_repository import (
    count_menu_items,
    delete_dynamic_crud_item,
    delete_menu_item,
    ensure_dynamic_crud_table,
    ensure_menu_schema,
    ensure_opciones_table,
    get_admin_role_id,
    get_distinct_menu_permissions,
    get_dynamic_crud_item,
    get_dynamic_crud_rows,
    get_menu_group_parents,
    get_menu_item_by_id,
    get_menu_items_admin_list,
    get_menu_items_tree_source,
    insert_dynamic_crud_item,
    insert_menu_child,
    insert_menu_group_child,
    insert_menu_item,
    insert_menu_root,
    insert_menu_subchild,
    insert_missing_admin_permissions,
    insert_opcion_if_not_exists,
    update_dynamic_crud_item,
    update_menu_item,
    update_menu_item_endpoint,
)
from .menu_utils import (
    ensure_autogen_templates,
    resolve_endpoint_href,
    rule_exists,
    safe_sql_identifier,
    slugify,
    utc_now,
)


DYNAMIC_CRUD = {}


def seed_menu_if_empty(conn):
    total = count_menu_items(conn)
    if total > 0:
        return

    cfg_id = insert_menu_root(conn, "Configuraciones", "bi bi-gear", 1, 1, 1)
    bit_id = insert_menu_root(conn, "Bitácora", "bi bi-journal-text", 1, 1, 2)
    reb_id = insert_menu_root(conn, "Reembolsos", "bi bi-wallet2", 1, 1, 3)

    insert_menu_child(conn, cfg_id, "Departamentos", "departamentos", "bi bi-building", "departamentos", "departamentos", 1)
    insert_menu_child(conn, cfg_id, "Usuarios", "usuarios", "bi bi-people", "usuarios", "usuarios", 2)
    insert_menu_child(conn, cfg_id, "Parámetros del sistema", "config", "bi bi-sliders", "parametros", "config", 3)
    insert_menu_child(conn, cfg_id, "Parámetros generales", "parametros_generales", "bi bi-card-list", "parametros", "parametros_generales", 4)
    insert_menu_child(conn, cfg_id, "Roles y permisos", "roles_permisos", "bi bi-shield-lock", "roles_permisos", "roles_permisos", 5)
    insert_menu_child(conn, cfg_id, "Políticas de seguridad", "politicas_seguridad", "bi bi-shield-check", "seguridad", "seguridad", 6)
    insert_menu_child(conn, cfg_id, "Cambiar clave", "cambiar_clave", "bi bi-key", "cambio_clave", "cambiar_clave", 7)
    insert_menu_child(conn, cfg_id, "Menú del sistema", "menu_admin", "bi bi-list", "menu", "menu_admin", 8)

    insert_menu_child(conn, bit_id, "Tareas", "listar_tareas", "bi bi-list-task", "tareas", "tareas", 1)

    sub_r = insert_menu_group_child(conn, reb_id, "Reembolsos", "bi bi-wallet2", 1, 1, 1)
    insert_menu_subchild(conn, sub_r, "Inicio", "reembolsos", "reembolsos", "reembolsos", 1)
    insert_menu_subchild(conn, sub_r, "Gastos con tarjeta", "lista_gastos", "reembolsos", "gastos_tarjeta", 2)
    insert_menu_subchild(conn, sub_r, "Reembolsos en efectivo", "reembolsos_efectivo", "reembolsos", "reembolsos_efectivo", 3)

    ter_id = insert_menu_group_child(conn, cfg_id, "Clientes / Proveedores", "bi bi-people-fill", 1, 1, 9)
    insert_menu_subchild(conn, ter_id, "Clientes", "clientes", "terceros", "clientes", 1)
    insert_menu_subchild(conn, ter_id, "Proveedores", "proveedores", "terceros", "proveedores", 2)

    conn.commit()


def initialize_menu_module(conn):
    ensure_menu_schema(conn)
    seed_menu_if_empty(conn)

def fetch_menu_tree(conn, permissions, active_page=None, is_admin=False):
    print(">>> ENTRO fetch_menu_tree *****", flush=True)

    rows = get_menu_items_tree_source(conn)

    print(">>> MENU ROWS:", len(rows), flush=True)

    def can_show(node):
        if is_admin:
            return True

        perm = (node.get("permission_key") or node.get("permission") or "").strip()
        if not perm:
            return True

        module_name, _, action_name = perm.partition(":")
        action_name = action_name or "ver"
        return bool(permissions.get(module_name, {}).get(action_name))

    grouped = defaultdict(list)

    for node in rows:
        endpoint_name = (node.get("endpoint") or "").strip()
        external_url = (node.get("external_url") or "").strip()

        if external_url.lower() in ("none", "null", "#"):
            external_url = ""

        if "encuesta" in (node.get("label") or "").lower() or "encuesta" in endpoint_name.lower():
            print(
                ">>> MENU ENCUESTA RAW:",
                "id=", node.get("id"),
                "label=", node.get("label"),
                "endpoint=", repr(endpoint_name),
                "external_url=", repr(external_url),
                "parent_id=", node.get("parent_id"),
                flush=True
            )

        node["href"] = external_url or resolve_endpoint_href(endpoint_name)

        if "encuesta" in (node.get("label") or "").lower() or "encuesta" in endpoint_name.lower():
            print(
                ">>> MENU ENCUESTA HREF:",
                "label=", node.get("label"),
                "endpoint=", repr(endpoint_name),
                "href=", repr(node.get("href")),
                flush=True
            )

        node["active"] = bool(active_page and node.get("active_key") == active_page)
        grouped[node.get("parent_id")].append(node)

    def build(parent_id=None):
        result = []

        for node in sorted(grouped.get(parent_id, []), key=lambda x: (x.get("order_no", 0), x.get("id"))):
            children = build(node["id"])
            show_self = can_show(node)

            if not show_self and not children:
                continue

            item = {**node}
            item["children"] = children
            item["active"] = item.get("active", False) or any(child.get("active") for child in children)
            result.append(item)

        return result

    return build(None)

def get_menu_admin_page_data(conn):
    initialize_menu_module(conn)
    return get_menu_items_admin_list(conn)


def parse_menu_form_payload(form_data):
    raw_parent_id = form_data.get("parent_id") or None

    parent_id = None
    if raw_parent_id not in (None, "", "None"):
        parent_id = int(raw_parent_id)

    return {
        "label": (form_data.get("label") or "").strip(),
        "parent_id": parent_id,
        "endpoint": (form_data.get("endpoint") or "").strip() or None,
        "external_url": (form_data.get("external_url") or "").strip() or None,
        "icon": (form_data.get("icon") or "").strip() or None,
        "order_no": int(form_data.get("order_no") or 0),
        "permission": (form_data.get("permission") or "").strip() or None,
        "active_key": (form_data.get("active_key") or "").strip() or None,
        "is_group": 1 if form_data.get("is_group") == "1" else 0,
        "is_collaps": 1 if form_data.get("is_collaps") == "1" else 0,
    }


def get_menu_form_data(conn, item_id=None):
    initialize_menu_module(conn)

    item = None
    if item_id:
        item = get_menu_item_by_id(conn, item_id)

    parents = get_menu_group_parents(conn)

    return item, parents


def save_menu_item(conn, form_payload, item_id=None):
    initialize_menu_module(conn)
    data = parse_menu_form_payload(form_payload)

    if item_id:
        update_menu_item(
            conn,
            item_id,
            data["parent_id"],
            data["label"],
            data["endpoint"],
            data["external_url"],
            data["icon"],
            data["order_no"],
            data["permission"],
            data["active_key"],
            data["is_group"],
            data["is_collaps"],
        )
        flash_option_updated()
        return {"mode": "edit", "item_id": item_id, "slug": None, "table": None}

    new_id = insert_menu_item(
        conn,
        data["parent_id"],
        data["label"],
        data["endpoint"],
        data["external_url"],
        data["icon"],
        data["order_no"],
        data["permission"],
        data["active_key"],
        data["is_group"],
        data["is_collaps"],
    )
    flash_option_created()

    created_slug = None
    created_table = None

    if data["is_group"] == 0 and not data["external_url"]:
        created_slug = slugify(data["endpoint"] or data["label"])

        if (data["endpoint"] or "") != created_slug:
            update_menu_item_endpoint(conn, new_id, created_slug)

        created_table = f"crud_{created_slug}"
        #ensure_dynamic_crud_table(conn, created_table)
        #ensure_autogen_templates(created_slug, data["label"])
        #register_dynamic_crud_endpoints(created_slug, data["label"], created_table)

    return {"mode": "create", "item_id": new_id, "slug": created_slug, "table": created_table}


def remove_menu_item(conn, item_id):
    delete_menu_item(conn, item_id)
    flash_option_deleted()


def sync_permissions_from_menu(conn):
    ensure_opciones_table(conn)
    permission_rows = get_distinct_menu_permissions(conn)

    for row in permission_rows:
        key_name = (row["k"] or "").strip()
        if not key_name:
            continue
        insert_opcion_if_not_exists(conn, key_name)

    conn.commit()


def ensure_admin_full_perms(conn):
    role_id = get_admin_role_id(conn)
    if role_id is None:
        return

    insert_missing_admin_permissions(conn, role_id)


def register_dynamic_crud_endpoints(slug, label, table):
    table = safe_sql_identifier(table)
    DYNAMIC_CRUD[slug] = {"table": table, "label": label}

    def list_view():
        from flask import render_template, session
        from modules.db import get_db

        session["active_page"] = slug
        conn = get_db()
        rows = get_dynamic_crud_rows(conn, table)
        conn.close()

        return render_template(
            f"autogen/{slug}_list.html",
            rows=rows,
            label=label,
            active_page=slug,
        )

    def form_view(item_id=None):
        from flask import render_template, request, redirect, session, url_for
        from modules.db import get_db

        session["active_page"] = slug
        conn = get_db()

        if request.method == "POST":
            data = {
                "campo1": request.form.get("campo1", "").strip(),
                "campo2": request.form.get("campo2", "").strip(),
                "campo3": request.form.get("campo3", "").strip(),
                "email1": request.form.get("email1", "").strip(),
                "email2": request.form.get("email2", "").strip(),
                "now": utc_now(),
            }

            for field_name in EMAIL_FIELDS:
                if data[field_name] and "@" not in data[field_name]:
                    flash_invalid_email(field_name)
                    item = None
                    if item_id:
                        item = get_dynamic_crud_item(conn, table, item_id)

                    conn.close()
                    return render_template(
                        f"autogen/{slug}_form.html",
                        item=item,
                        label=label,
                        active_page=slug,
                    )

            if item_id:
                update_dynamic_crud_item(
                    conn,
                    table,
                    item_id,
                    data["campo1"],
                    data["campo2"],
                    data["campo3"],
                    data["email1"],
                    data["email2"],
                    data["now"],
                )
                flash_record_updated()
            else:
                insert_dynamic_crud_item(
                    conn,
                    table,
                    data["campo1"],
                    data["campo2"],
                    data["campo3"],
                    data["email1"],
                    data["email2"],
                    data["now"],
                    data["now"],
                )
                flash_record_created()

            conn.close()
            return redirect(url_for(slug))

        item = None
        if item_id:
            item = get_dynamic_crud_item(conn, table, item_id)

        conn.close()
        return render_template(
            f"autogen/{slug}_form.html",
            item=item,
            label=label,
            active_page=slug,
        )

    def delete_view(item_id):
        from flask import redirect, session, url_for
        from modules.db import get_db

        session["active_page"] = slug
        conn = get_db()
        delete_dynamic_crud_item(conn, table, item_id)
        conn.close()
        flash_record_deleted()
        return redirect(url_for(slug))

    if not rule_exists(slug):
        current_app.add_url_rule(f"/{slug}", endpoint=slug, view_func=list_view, methods=["GET"])

    if not rule_exists(f"{slug}_new"):
        current_app.add_url_rule(
            f"/{slug}/new",
            endpoint=f"{slug}_new",
            view_func=form_view,
            methods=["GET", "POST"],
        )

    if not rule_exists(f"{slug}_edit"):
        current_app.add_url_rule(
            f"/{slug}/<int:item_id>/edit",
            endpoint=f"{slug}_edit",
            view_func=form_view,
            methods=["GET", "POST"],
        )

    if not rule_exists(f"{slug}_delete"):
        current_app.add_url_rule(
            f"/{slug}/<int:item_id>/delete",
            endpoint=f"{slug}_delete",
            view_func=delete_view,
            methods=["POST"],
        )


def bootstrap_dynamic_menu_endpoints(app):
    from modules.db import get_db

    with app.app_context():
        conn = get_db()
        try:
            initialize_menu_module(conn)
            items = get_menu_items_admin_list(conn)

            for item in items:
                endpoint_name = (item.get("endpoint") or "").strip()
                external_url = (item.get("external_url") or "").strip()
                is_group = int(item.get("is_group") or 0)

                if is_group == 0 and endpoint_name and not external_url:
                    slug = slugify(endpoint_name or item.get("label") or "")
                    table = f"crud_{slug}"
                    ensure_dynamic_crud_table(conn, table)
                    ensure_autogen_templates(slug, item.get("label") or slug)
                    register_dynamic_crud_endpoints(slug, item.get("label") or slug, table)
        finally:
            conn.close()