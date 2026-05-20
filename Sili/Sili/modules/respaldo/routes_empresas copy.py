# modules/routes_empresas.py
# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from pyodbc import IntegrityError



from modules.auth.routes_auth import require_login, require_permission

empresas_bp = Blueprint("empresas", __name__, url_prefix="/empresas")

ACTIVE_KEY = "empresas"
PERM_BASE = "empresas"   # empresas.ver / crear / editar / eliminar


def collect_empresas_filters():
    """Lee filtros desde el request para la lista."""
    q = (request.args.get("q") or "").strip()
    activo = request.args.get("activo")
    if activo not in ("0", "1", None, ""):
        activo = None
    return {"q": q, "activo": activo}


def normalize_empresa_form(form):
    """Limpia y prepara los datos del formulario."""
    get_value = lambda k: (form.get(k) or "").strip()
    data = {
        "razon_social": get_value("razon_social"),
        "ruc": get_value("ruc"),
        "direccion": get_value("direccion"),
        "telefono": get_value("telefono"),
        "email": get_value("email").lower(),
        "sitio_web": get_value("sitio_web"),
        "rep_nombre": get_value("rep_nombre"),
        "rep_identificacion": get_value("rep_identificacion"),
        "rep_nacionalidad": get_value("rep_nacionalidad"),
        "activo": 1 if (form.get("activo") in ("1", "on", "true", "True")) else 0,
    }
    return data


def upsert_empresa(conn, empresa_id, data):
    cur = conn.cursor()

    if empresa_id is None:
        cur.execute("""
            INSERT INTO empresas
            (
                razon_social,
                ruc,
                direccion,
                telefono,
                email,
                sitio_web,
                rep_nombre,
                rep_identificacion,
                rep_nacionalidad,
                activo,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            data["razon_social"],
            data["ruc"],
            data["direccion"],
            data["telefono"],
            data["email"],
            data["sitio_web"],
            data["rep_nombre"],
            data["rep_identificacion"],
            data["rep_nacionalidad"],
            data["activo"],
        ))

        cur.execute("SELECT CAST(SCOPE_IDENTITY() AS INT)")
        row = cur.fetchone()
        conn.commit()
        return row[0] if row else None

    cur.execute("""
        UPDATE empresas SET
            razon_social = ?,
            ruc = ?,
            direccion = ?,
            telefono = ?,
            email = ?,
            sitio_web = ?,
            rep_nombre = ?,
            rep_identificacion = ?,
            rep_nacionalidad = ?,
            activo = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (
        data["razon_social"],
        data["ruc"],
        data["direccion"],
        data["telefono"],
        data["email"],
        data["sitio_web"],
        data["rep_nombre"],
        data["rep_identificacion"],
        data["rep_nacionalidad"],
        data["activo"],
        empresa_id,
    ))

    conn.commit()
    return empresa_id


# ============ LISTA ============
@empresas_bp.route("/", endpoint="lista_empresas")
@require_login
@require_permission(PERM_BASE, "ver")
def lista_empresas():
    conn = get_db()

    f = collect_empresas_filters()
    params = []
    where = []

    if f["q"]:
        where.append("(razon_social LIKE ? OR ruc LIKE ? OR email LIKE ? OR telefono LIKE ?)")
        like = f"%{f['q']}%"
        params += [like, like, like, like]

    if f["activo"] in ("0", "1"):
        where.append("activo = ?")
        params.append(int(f["activo"]))

    sql = "SELECT id, razon_social, ruc, email, telefono, activo FROM empresas"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY razon_social ASC"

    rows = conn.execute(sql, params).fetchall()

    return render_template(
        "empresas/empresas_lista.html",
        rows=rows,
        f=f,
        active_page=ACTIVE_KEY
    )


# ============ NUEVA ============
@empresas_bp.route("/nueva", methods=["GET", "POST"], endpoint="nueva_empresa")
@require_login
@require_permission(PERM_BASE, "crear")
def nueva_empresa():
    conn = get_db()

    if request.method == "POST":
        data = normalize_empresa_form(request.form)

        if not data["razon_social"] or not data["ruc"]:
            flash("Razón social y RUC son obligatorios.", "warning")
            return render_template(
                "empresas/empresas_form.html",
                data=data,
                mode="new",
                active_page=ACTIVE_KEY
            )

        try:
            upsert_empresa(conn, None, data)
            flash("Empresa creada correctamente.", "success")
            return redirect(url_for("empresas.lista_empresas"))
        except IntegrityError:
            flash("El RUC ya existe. Verifique.", "danger")
            return render_template(
                "empresas/empresas_form.html",
                data=data,
                mode="new",
                active_page=ACTIVE_KEY
            )

    return render_template(
        "empresas/empresas_form.html",
        data={},
        mode="new",
        active_page=ACTIVE_KEY
    )


# ============ EDITAR ============
@empresas_bp.route("/<int:empresa_id>/editar", methods=["GET", "POST"], endpoint="editar_empresa")
@require_login
@require_permission(PERM_BASE, "editar")
def editar_empresa(empresa_id):
    conn = get_db()
    cur = conn.cursor()

    row = cur.execute("SELECT * FROM empresas WHERE id = ?", (empresa_id,)).fetchone()
    if not row:
        abort(404)

    if request.method == "POST":
        data = normalize_empresa_form(request.form)

        if not data["razon_social"] or not data["ruc"]:
            flash("Razón social y RUC son obligatorios.", "warning")
            return render_template(
                "empresas/empresas_form.html",
                data=data,
                mode="edit",
                active_page=ACTIVE_KEY
            )

        try:
            upsert_empresa(conn, empresa_id, data)
            flash("Empresa actualizada.", "success")
            return redirect(url_for("empresas.lista_empresas"))
        except IntegrityError:
            flash("El RUC ya existe en otra empresa.", "danger")
            return render_template(
                "empresas/empresas_form.html",
                data=data,
                mode="edit",
                active_page=ACTIVE_KEY
            )

    return render_template(
        "empresas/empresas_form.html",
        data=row,
        mode="edit",
        active_page=ACTIVE_KEY
    )


# ============ ELIMINAR ============
@empresas_bp.route("/<int:empresa_id>/eliminar", methods=["POST"], endpoint="eliminar_empresa")
@require_login
@require_permission(PERM_BASE, "eliminar")
def eliminar_empresa(empresa_id):
    conn = get_db()
    conn.execute("DELETE FROM empresas WHERE id = ?", (empresa_id,))
    conn.commit()
    flash("Empresa eliminada.", "success")
    return redirect(url_for("empresas.lista_empresas"))