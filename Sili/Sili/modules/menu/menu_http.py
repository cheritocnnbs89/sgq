from flask import Blueprint, redirect, render_template, request, session, url_for

from modules.db import get_db

from .menu_services import (
    bootstrap_dynamic_menu_endpoints,
    get_menu_admin_page_data,
    get_menu_form_data,
    initialize_menu_module,
    remove_menu_item,
    save_menu_item,
)

menu_bp = Blueprint("menu", __name__, template_folder="templates")


@menu_bp.route("/config/menu", methods=["GET"], endpoint="menu_admin")
def menu_admin():
    conn = get_db()
    try:
        items = get_menu_admin_page_data(conn)
    finally:
        conn.close()

    return render_template(
        "menu_admin.html",
        items=items,
        usuario=session.get("usuario"),
        rol=session.get("rol"),
        active_page="menu_admin",
    )


@menu_bp.route("/config/menu/new", methods=["GET", "POST"], endpoint="menu_new")
@menu_bp.route("/config/menu/<int:item_id>/edit", methods=["GET", "POST"], endpoint="menu_edit")
def menu_edit(item_id=None):
    conn = get_db()

    if request.method == "POST":
        try:
            save_menu_item(conn, request.form, item_id=item_id)
        finally:
            conn.close()

        return redirect(url_for("menu.menu_admin"))

    try:
        item, parents = get_menu_form_data(conn, item_id=item_id)
    finally:
        conn.close()

    return render_template(
        "menu_form.html",
        item=item,
        parents=parents,
        usuario=session.get("usuario"),
        rol=session.get("rol"),
        active_page="menu_admin",
    )


@menu_bp.post("/config/menu/<int:item_id>/delete")
def menu_delete(item_id):
    conn = get_db()
    try:
        remove_menu_item(conn, item_id)
    finally:
        conn.close()

    return redirect(url_for("menu.menu_admin"))


def register_menu_routes(app):
    app.register_blueprint(menu_bp)

    with app.app_context():
        conn = get_db()
        try:
            initialize_menu_module(conn)
        finally:
            conn.close()

    bootstrap_dynamic_menu_endpoints(app)