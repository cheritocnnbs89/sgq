# modules/empresas_helpers.py
# -*- coding: utf-8 -*-
from flask import request


def collect_empresas_filters():
    """Lee filtros desde el request para la lista."""
    q = (request.args.get("q") or "").strip()
    activo = request.args.get("activo")
    if activo not in ("0", "1", None, ""):
        activo = None
    return {"q": q, "activo": activo}


def normalize_empresa_form(form):
    """Limpia y prepara los datos del formulario."""
    get = lambda k: (form.get(k) or "").strip()
    data = {
        "razon_social": get("razon_social"),
        "ruc": get("ruc"),
        "direccion": get("direccion"),
        "telefono": get("telefono"),
        "email": get("email").lower(),
        "sitio_web": get("sitio_web"),
        "rep_nombre": get("rep_nombre"),
        "rep_identificacion": get("rep_identificacion"),
        "rep_nacionalidad": get("rep_nacionalidad"),
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

    else:
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