from __future__ import annotations
import os
from typing import Any, List

from flask import (
    Blueprint, render_template, request, session, flash,
    url_for, redirect, abort, get_flashed_messages, current_app, send_file,
)

# Decoradores unificados
from modules.security import require_login, require_permission
from modules.email_utils import send_email_async as _send_email_async
from modules.db import get_db

from werkzeug.utils import secure_filename

import time


# --- Ejecutar con reintentos si la BD está bloqueada (bloqueos intermitentes de SQLite)
def exec_retry(conn, sql: str, params: tuple = (), retries: int = 5, delay: float = 0.25):
    last = None
    transient_tokens = (
        "deadlock",
        "timeout",
        "temporarily unavailable",
        "could not serialize",
        "connection is busy",
        "communication link failure",
        "transport-level error",
    )
    for i in range(retries):
        try:
            cur = conn.cursor()
            cur.execute(sql, params)
            return cur
        except Exception as e:
            msg = str(e).lower()
            if any(tok in msg for tok in transient_tokens) and i < retries - 1:
                time.sleep(delay * (i + 1))
                continue
            last = e
            break
    raise last


# --- Wrapper de correo usando email_utils (async) ---
def _send_mail(to_addr: str, subject: str, message_plain: str):
    """
    Envía correo en texto plano usando el helper del proyecto.
    Acepta 1 destinatario como string.
    """
    if not to_addr:
        return
    try:
        _send_email_async([to_addr], subject, message_plain)
    except Exception as _e:
        try:
            current_app.logger.warning("Fallo envío de correo a %s: %s", to_addr, _e)
        except Exception:
            pass


# ---------- Blueprint ----------

contratos_bp = Blueprint(
    "contratos",
    __name__,
    url_prefix="/contratos",
    template_folder="templates"
)


@contratos_bp.after_app_request
def _no_cache_for_contratos(response):
    # Solo para este blueprint
    if request.blueprint == "contratos":
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# ---------- Helpers ----------
def _bool(v) -> int:
    if isinstance(v, (int, float)):
        return 1 if v else 0
    s = (str(v or "")).strip().lower()
    return 1 if s in ("1", "true", "t", "y", "yes", "si", "sí") else 0


def _f(s: str | None) -> str | None:
    """Convierte dd/mm/aaaa o yyyy-mm-dd a yyyy-mm-dd (o None)."""
    v = (s or "").strip()
    if not v:
        return None
    if "-" in v and len(v) >= 8:
        return v[:10]
    parts = v.replace(".", "/").split("/")
    if len(parts) == 3 and len(parts[2]) == 4:
        d, m, y = parts
        return f"{y}-{int(m):02d}-{int(d):02d}"
    return v


def _safe_int(x):
    try:
        return int(x) if x is not None and str(x).strip() != "" else None
    except:
        return None


# --- Helpers ---------- (déjalo junto a los demás helpers)
def _rowget(row, key, default=None):
    """Any no tiene .get(); este helper evita KeyError."""
    try:
        return row[key]
    except Exception:
        return default


# --- Helpers de columnas / esquema ---
def _add_column_if_missing(conn, table: str, col: str, decl: str) -> None:
    return

# --- Helpers de archivos (PDF de contratos) ---
def _ensure_contrato_archivos_table() -> None:
    return


def _get_contratos_upload_folder() -> str:
    """
    Carpeta donde se guardan los PDFs de contratos.
    Usa config CONTRATOS_UPLOAD_FOLDER si existe, si no,
    crea /uploads/contratos dentro del root de la app.
    """
    base = current_app.config.get("CONTRATOS_UPLOAD_FOLDER")
    if not base:
        base = os.path.join(current_app.root_path, "uploads", "contratos")
    os.makedirs(base, exist_ok=True)
    return base


def _save_contrato_pdfs(contrato_id: int) -> None:
    """
    Guarda todos los archivos enviados en el campo 'archivos_pdf'
    como PDFs asociados al contrato indicado.
    Solo acepta extensión .pdf (ignora el resto).
    """
    files = request.files.getlist("archivos_pdf")
    if not files:
        return

    _ensure_contrato_archivos_table()
    conn = get_db()
    folder = _get_contratos_upload_folder()

    for f in files:
        if not f or (f.filename or "").strip() == "":
            continue

        original = f.filename.strip()
        _, ext = os.path.splitext(original)
        ext = ext.lower()
        if ext != ".pdf":
            # No rompas el flujo, solo avisa y salta ese archivo
            flash(f"El archivo '{original}' no se guardó porque no es un PDF.", "warning")
            continue

        safe_name = secure_filename(original)
        # Prefijo con contrato_id y timestamp para evitar colisiones
        final_name = f"{contrato_id}_{int(time.time())}_{safe_name}"
        file_path = os.path.join(folder, final_name)
        f.save(file_path)

        exec_retry(
            conn,
            """
            INSERT INTO contrato_archivos (contrato_id, filename, original_name, uploaded_at)
            VALUES (?, ?, ?, GETDATE())
            """,
            (contrato_id, final_name, original),
        )
    conn.commit()

# --- Helpers de correos (destinatarios frecuentes) ---
def _lookup_email_by_user_id(conn, uid: int | None) -> str:
    if not uid:
        return ""
    r = conn.execute("SELECT TOP 1 email FROM usuarios WHERE id=?", (uid,)).fetchone()
    return (r["email"] if r and r["email"] else "") if r else ""


def _lookup_email_by_username_or_email(conn, name_or_email: str | None) -> str:
    v = (name_or_email or "").strip()
    if not v:
        return ""
    vlow = v.lower()
    # si ya parece email, devuélvelo tal cual
    if "@" in vlow and "." in vlow:
        return v
    r = conn.execute("""
        SELECT TOP 1 email FROM usuarios
         WHERE LOWER(username)=? OR LOWER(email)=?
         ORDER BY id DESC
    """, (vlow, vlow)).fetchone()
    return (r["email"] if r and r["email"] else "") if r else ""


def _pgallegos_email(conn) -> str:
    r = conn.execute("""
        SELECT TOP 1 email FROM usuarios
         WHERE LOWER(username) IN ('pgallegos','p.gallegos','paul gallegos','p gallegos','pablo gallegos')
         ORDER BY id DESC
    """).fetchone()
    if r and r["email"]:
        return r["email"]
    # Fallback de configuración o el correo indicado por ti
    return current_app.config.get("PGALLEGOS_FALLBACK_EMAIL", "pgallegos1@quimpac.com.ec")


# --- URL pública fija para todos los correos ---
# Usa SIEMPRE esta URL (sin importar request.url_root ni PUBLIC_BASE_URL)
PUBLIC_FIXED_URL = "http://bitacoraquimpac.com.ec:5000/".rstrip("/") + "/"


def _savera_email() -> str:
    # Dirección fija que indicaste
    return "svera@quimpac1.com.ec"


def _gerente_financiero_email() -> str:
    # Dirección fija que indicaste
    return "dcunninghan2@quimpac.com.ec"


def _find_compras_email(conn, usuario_compras_id: int | None, usuario_compras_nombre: str | None) -> str:
    # Prioriza ID si existe
    mail = _lookup_email_by_user_id(conn, usuario_compras_id)
    if mail:
        return mail
    # Si no hay ID, intenta resolver por username/email escrito en texto libre
    return _lookup_email_by_username_or_email(conn, usuario_compras_nombre)


def _resolve_usuario_compras_nombre(conn, fila: Any) -> str:
    """
    Resuelve el nombre del Usuario de Compras mostrando el NOMBRE COMPLETO si existe.
    Reglas:
      1) Si hay usuario_compras_id -> lookup en usuarios.nombre_completo (fallback username)
      2) Si no, usa 'creado_por' como fallback
      3) Si hay texto en usuario_compras_nombre y NO es 'Actual', úsalo
      4) Como último recurso, usa el usuario de la sesión
    """
    uid = None
    if "usuario_compras_id" in fila.keys() and fila["usuario_compras_id"]:
        uid = fila["usuario_compras_id"]
    elif "creado_por" in fila.keys() and fila["creado_por"]:
        uid = fila["creado_por"]

    if uid:
        r = conn.execute(
            """
            SELECT TOP 1 COALESCE(nombre_completo, username) AS nombre
            FROM usuarios
            WHERE id=?
            """,
            (uid,),
        ).fetchone()
        if r and r["nombre"]:
            return r["nombre"]

    txt = (fila["usuario_compras_nombre"] or "").strip() if "usuario_compras_nombre" in fila.keys() else ""
    if txt and txt.lower() != "actual":
        return txt

    uid_now = _session_user_id()
    if uid_now:
        rnow = conn.execute(
            """
            SELECT TOP 1 COALESCE(nombre_completo, username) AS nombre
            FROM usuarios
            WHERE id=?
            """,
            (uid_now,),
        ).fetchone()
        if rnow and rnow["nombre"]:
            return rnow["nombre"]

    return txt



def _link_contrato(contrato_id: int) -> str:
    """
    En los correos, queremos enviar SIEMPRE el link fijo al sistema,
    NO un enlace profundo al detalle del contrato.
    """
    return PUBLIC_FIXED_URL


def _link_garantia(garantia_id: int) -> str:
    """
    En los correos, queremos enviar SIEMPRE el link fijo al sistema,
    NO un enlace profundo al detalle de la garantía.
    """
    return PUBLIC_FIXED_URL


# --- Helpers de sesión con tolerancia de nombres ---
def _session_user_id() -> int | None:
    for k in ("usuario_id", "user_id", "id", "uid"):
        v = session.get(k)
        if v is not None:
            try:
                return int(v)
            except:
                pass
    return None


def _session_dept_id() -> int | None:
    for k in ("departamento_id", "dept_id", "depto_id", "dep_id"):
        v = session.get(k)
        if v is not None:
            try:
                return int(v)
            except:
                pass
    return None


# --- Migración suave: añade columnas si faltan en 'contratos' ---
def _ensure_contratos_columns() -> None:
    return


def _ensure_garantias_columns() -> None:
    return


def _ensure_softdelete_columns():
    return


# --- util para asegurar columnas de aprobación GF ---
def _ensure_aprob_gf_columns():
    return


# --- util: saber si una columna existe
def _has_column(conn, table: str, col: str) -> bool:
    cur = conn.cursor()
    row = cur.execute("""
        SELECT TOP 1 1 AS ok
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = ?
          AND COLUMN_NAME = ?
    """, (table, col)).fetchone()
    return row is not None


# --- util: existe id en tabla
def _exists(conn, table: str, id_val) -> bool:
    if not id_val:
        return False
    c = conn.cursor()
    return c.execute(f"SELECT TOP 1 1 AS ok FROM {table} WHERE id=?", (id_val,)).fetchone() is not None


def _list_contratos_aprobados_jefe(conn, limit: int = 200, include_id: int | None = None):
    """
    Devuelve contratos habilitados y aprobados por Jefatura.
    include_id: asegura incluir un contrato específico aunque no cumpla el filtro (útil en editar).
    """
    top_n = max(1, int(limit or 200))
    sql = f"""
        SELECT TOP {top_n}
            id,
            pedido,
            proveedor
        FROM contratos
        WHERE COALESCE(disabled,0)=0
          AND COALESCE(aprobado_jefe,0)=1
        ORDER BY id DESC
    """

    rows = conn.execute(sql).fetchall()

    if include_id:
        cur = conn.cursor()
        extra = cur.execute(
            """
            SELECT TOP 1 id, pedido, proveedor
            FROM contratos
            WHERE id=?
            """,
            (include_id,)
        ).fetchone()
        if extra and not any(r["id"] == extra["id"] for r in rows):
            rows = [extra] + list(rows)
    return rows


def _list_contratos_aprobados_sin_garantia(conn, limit: int = 200, include_id: int | None = None):
    """
    Lista contratos habilitados y aprobados por Jefatura que NO tienen ninguna garantía activa (garantias.disabled=0).
    include_id: permite incluir forzosamente un contrato (p.ej. al editar una garantía existente).
    """
    cur = conn.cursor()
    top_n = max(1, int(limit or 200))

    sql = f"""
        SELECT TOP {top_n} c.id, c.pedido, c.proveedor
        FROM contratos c
        LEFT JOIN (
            SELECT DISTINCT contrato_id
            FROM garantias
            WHERE COALESCE(disabled,0)=0
        ) g ON g.contrato_id = c.id
        WHERE COALESCE(c.disabled,0)=0
          AND COALESCE(c.aprobado_jefe,0)=1
          AND g.contrato_id IS NULL
        ORDER BY c.id DESC
    """
    rows = cur.execute(sql).fetchall()

    if include_id:
        extra = cur.execute(
            """
            SELECT TOP 1 id, pedido, proveedor
            FROM contratos
            WHERE id=? AND COALESCE(disabled,0)=0
            """,
            (include_id,),
        ).fetchone()
        if extra and not any(r["id"] == extra["id"] for r in rows):
            rows = [extra] + list(rows)
    return rows


# =========================================================
#   COMPRAS (Ingresar contratos)  — SOLO Comercial
# =========================================================
@contratos_bp.route("/ingresar", methods=["GET", "POST"])
@require_login
@require_permission("contratos_ingresar", "ver")
def compras_nuevo():
    session["active_page"] = "contratos_ingresar"
    _ensure_contratos_columns()
    _ensure_softdelete_columns()
    _ensure_contrato_archivos_table()  # <- NUEVO: asegura tabla de PDFs

    # ===== Combos =====
    conn_pre = get_db()
    cur_pre = conn_pre.cursor()
    usuarios = cur_pre.execute(
        """
        SELECT
            u.id,
            u.nombre_completo AS nombre,
            COALESCE(d.nombre, "") AS departamento
        FROM usuarios u
        LEFT JOIN departamentos d ON d.id = u.departamento_id
        WHERE COALESCE(u.disabled, 0) = 0
          AND TRIM(COALESCE(u.nombre_completo, '')) <> ''
        ORDER BY u.nombre_completo
        """
    ).fetchall()
    proveedores = cur_pre.execute(
        """
        SELECT id, nombre
        FROM terceros
        WHERE tipo = 'P' AND COALESCE(activo, 1) = 1
        ORDER BY nombre
    """
    ).fetchall()

    # ========================= POST =========================
    if request.method == "POST":
        from modules.security import has_permission

        if not has_permission(session.get("rol"), "contratos_ingresar", "crear"):
            flash("No tiene permiso para crear contratos.", "danger")
            return redirect(url_for("contratos.compras_lista"))

        def _nfloat(v):
            try:
                return float(v)
            except:
                return 0.0

        def _safe_int_local(x):
            try:
                return int(x)
            except:
                return None

        # ---- IDs (formulario / sesión) ----
        usuario_solicitante_id = _safe_int_local(request.form.get("usuario_solicitante_id"))

        # Si el campo libre "usuario_compras_nombre" viene vacío o dice "Actual",
        # usamos el username del usuario logueado para que en el detalle NO salga "Actual".
        print(session.get("usuario"))
        usuario_compras_nombre = (request.form.get("usuario_compras_nombre") or "").strip()
        if not usuario_compras_nombre or usuario_compras_nombre.lower() == "actual":
            uid_actual = _session_user_id()
            if uid_actual:
                conn_name = get_db()
                try:
                    rname = conn_name.execute(
                        """
                        SELECT TOP 1 COALESCE(nombre_completo, username) AS nombre
                        FROM usuarios
                        WHERE id=?
                        """,
                        (uid_actual,),
                    ).fetchone()
                except Exception:
                    rname = None
                if rname and rname["nombre"]:
                    usuario_compras_nombre = rname["nombre"]

        # Guardamos también el ID del usuario de compras (quien está creando)
        usuario_compras_id = _session_user_id()

        creado_por = _session_user_id()
        departamento_id = _session_dept_id()

        # ---- Cabecera ----
        anio = (request.form.get("anio") or "").strip()
        pedido = (request.form.get("pedido") or "").strip()
        tipo_pp = "AMBOS"  # default para Compras

        # ---- Proveedor (id del combo o texto libre) ----
        proveedor = None
        prov_id = _safe_int_local(request.form.get("proveedor_id"))

        # ---- Valores y fechas ----
        objeto = (request.form.get("objeto") or request.form.get("objeto_contrato") or "").strip()
        valor_contrato = _nfloat(request.form.get("valor_contrato"))
        valor_anticipo = _nfloat(request.form.get("valor_anticipo"))

        fecha_suscripcion = _f(request.form.get("fecha_suscripcion"))
        fecha_terminacion = _f(request.form.get("fecha_terminacion"))
        plazo_dias = int((request.form.get("plazo_dias") or "0") or 0)
        cronograma_pagos = (request.form.get("cronograma_pagos") or "").strip()
        fecha_entrega_compras = _f(request.form.get("fecha_entrega_compras"))
        fecha_firma_gerencia = _f(request.form.get("fecha_firma_gerencia"))
        fecha_entrega_finanzas_sumilla = _f(
            request.form.get("fecha_entrega_finanzas_sumilla")
            or request.form.get("fecha_entrega_a_finanzas_sumilla")
        )
        fecha_entrega_originales_fin = _f(
            request.form.get("fecha_entrega_originales_finanzas")
            or request.form.get("fecha_entrega_originales_a_finanzas")
        )
        fechas_pago_anticipo = (request.form.get("fechas_pago_anticipo") or "").strip()
        fecha_entrega_pedido = _f(request.form.get("fecha_entrega_pedido"))
        observaciones = (request.form.get("observaciones") or "").strip()

        # ---- Validaciones mínimas (solo lo realmente obligatorio) ----
        missing_required = []
        if not anio:
            missing_required.append("AÑO")
        if not pedido:
            missing_required.append("PEDIDO")
        if not usuario_solicitante_id:
            missing_required.append("Usuario solicitante")
        if not objeto:
            missing_required.append("Objeto del contrato")
        if valor_contrato is None or valor_contrato <= 0:
            missing_required.append("Valor contrato")
        if not fecha_suscripcion:
            missing_required.append("Fecha de suscripción")

        # Resolver nombre de proveedor si llega por id (usando la MISMA conexión que insertará)
        conn = get_db()
        try:
            cur = conn.cursor()
            if prov_id:
                rowp = cur.execute(
                    "SELECT nombre FROM terceros WHERE id=? AND tipo='P' AND COALESCE(activo,1)=1",
                    (prov_id,),
                ).fetchone()
                proveedor = rowp["nombre"] if rowp else None
            if not proveedor:
                proveedor = (request.form.get("proveedor") or "").strip()
            if not proveedor:
                missing_required.append("PROVEEDOR")

            if missing_required:
                flash("Campos obligatorios incompletos: " + ", ".join(missing_required), "danger")
                row_back = {
                    "anio": anio,
                    "pedido": pedido,
                    "proveedor": proveedor,
                    "objeto": objeto,
                    "valor_contrato": valor_contrato,
                    "valor_anticipo": valor_anticipo,
                    "fecha_suscripcion": fecha_suscripcion,
                    "fecha_terminacion": fecha_terminacion,
                    "plazo_dias": plazo_dias,
                    "cronograma_pagos": cronograma_pagos,
                    "fecha_entrega_compras": fecha_entrega_compras,
                    "fecha_firma_gerencia": fecha_firma_gerencia,
                    "fecha_entrega_finanzas_sumilla": fecha_entrega_finanzas_sumilla,
                    "fecha_entrega_originales_fin": fecha_entrega_originales_fin,
                    "fechas_pago_anticipo": fechas_pago_anticipo,
                    "fecha_entrega_pedido": fecha_entrega_pedido,
                    "observaciones": observaciones,
                    "usuario_solicitante_id": usuario_solicitante_id,
                    "usuario_compras_nombre": usuario_compras_nombre,
                }
                # Para nuevo, no hay archivos todavía
                from modules.security import has_permission as _hp
                can_exportar = _hp(session.get("rol"), "contratos_ingresar", "exportar")

                return render_template(
                    "compras_ingreso.html",
                    mode="create",
                    row=row_back,
                    usuarios=usuarios,
                    proveedores=proveedores,
                    archivos=[],
                    can_exportar=can_exportar,
                    post_url=url_for("contratos.compras_nuevo"),
                    back_url=request.form.get("next") or url_for("contratos.compras_lista"),
                )

            # ---- Regla de negocio: anticipo <= contrato ----
            if (valor_contrato or 0) > 0 and (valor_anticipo or 0) > valor_contrato:
                flash("El valor del anticipo no puede ser mayor que el valor del contrato.", "danger")
                row_back = {
                    "anio": anio,
                    "pedido": pedido,
                    "proveedor": proveedor,
                    "objeto": objeto,
                    "valor_contrato": valor_contrato,
                    "valor_anticipo": valor_anticipo,
                    "fecha_suscripcion": fecha_suscripcion,
                    "fecha_terminacion": fecha_terminacion,
                    "plazo_dias": plazo_dias,
                    "cronograma_pagos": cronograma_pagos,
                    "fecha_entrega_compras": fecha_entrega_compras,
                    "fecha_firma_gerencia": fecha_firma_gerencia,
                    "fecha_entrega_finanzas_sumilla": fecha_entrega_finanzas_sumilla,
                    "fecha_entrega_originales_fin": fecha_entrega_originales_fin,
                    "fechas_pago_anticipo": fechas_pago_anticipo,
                    "fecha_entrega_pedido": fecha_entrega_pedido,
                    "observaciones": observaciones,
                    "usuario_solicitante_id": usuario_solicitante_id,
                    "usuario_compras_nombre": usuario_compras_nombre,
                }
                from modules.security import has_permission as _hp
                can_exportar = _hp(session.get("rol"), "contratos_ingresar", "exportar")

                return render_template(
                    "compras_ingreso.html",
                    mode="create",
                    row=row_back,
                    usuarios=usuarios,
                    proveedores=proveedores,
                    archivos=[],
                    can_exportar=can_exportar,
                    post_url=url_for("contratos.compras_nuevo"),
                    back_url=request.form.get("next") or url_for("contratos.compras_lista"),
                )

            # ---- Validaciones de FKs (solo el solicitante, que sí eliges en el combo) --->
            fk_errors = []
            if (
                cur.execute(
                    "SELECT TOP 1 1 AS ok FROM usuarios WHERE id=?", (usuario_solicitante_id,)
                ).fetchone()
                is None
            ):
                fk_errors.append("Usuario solicitante inexistente")

            if fk_errors:
                flash("Revisa IDs relacionados: " + "; ".join(fk_errors), "danger")
                row_back = {
                    "anio": anio,
                    "pedido": pedido,
                    "proveedor": proveedor,
                    "objeto": objeto,
                    "valor_contrato": valor_contrato,
                    "valor_anticipo": valor_anticipo,
                    "fecha_suscripcion": fecha_suscripcion,
                    "fecha_terminacion": fecha_terminacion,
                    "plazo_dias": plazo_dias,
                    "cronograma_pagos": cronograma_pagos,
                    "fecha_entrega_compras": fecha_entrega_compras,
                    "fecha_firma_gerencia": fecha_firma_gerencia,
                    "fecha_entrega_finanzas_sumilla": fecha_entrega_finanzas_sumilla,
                    "fecha_entrega_originales_fin": fecha_entrega_originales_fin,
                    "fechas_pago_anticipo": fechas_pago_anticipo,
                    "fecha_entrega_pedido": fecha_entrega_pedido,
                    "observaciones": observaciones,
                    "usuario_solicitante_id": usuario_solicitante_id,
                    "usuario_compras_nombre": usuario_compras_nombre,
                }
                from modules.security import has_permission as _hp
                can_exportar = _hp(session.get("rol"), "contratos_ingresar", "exportar")

                return render_template(
                    "compras_ingreso.html",
                    mode="create",
                    row=row_back,
                    usuarios=usuarios,
                    proveedores=proveedores,
                    archivos=[],
                    can_exportar=can_exportar,
                    post_url=url_for("contratos.compras_nuevo"),
                    back_url=request.form.get("next") or url_for("contratos.compras_lista"),
                )

            status_interno = "No aprobado"

            insert_sql = """
    INSERT INTO contratos (
        anio, pedido, proveedor, objeto, valor_contrato, valor_anticipo,
        tipo_pp,
        fecha_suscripcion, fecha_terminacion, plazo_dias, cronograma_pagos,
        fecha_entrega_compras, fecha_firma_gerencia, fecha_entrega_finanzas_sumilla,
        fecha_entrega_originales_fin, fechas_pago_anticipo, fecha_entrega_pedido,
        observaciones, status_interno,
        usuario_solicitante_id, usuario_compras_nombre,
        usuario_compras_id, departamento_id, creado_por, actualizado_at
    )
    OUTPUT inserted.id
    VALUES (?,?,?,?,?,?,?,
              ?,?,?,?,?,?,
              ?,?,?,?,
              ?,?,
              ?,?,
              ?, ?, ?, GETDATE())
"""
            cur_ins = exec_retry(
                conn,
                insert_sql,
                (
                    int(anio) if anio else None,
                    pedido,
                    proveedor,
                    objeto,
                    valor_contrato,
                    valor_anticipo,
                    tipo_pp,
                    fecha_suscripcion,
                    fecha_terminacion,
                    plazo_dias,
                    cronograma_pagos,
                    fecha_entrega_compras,
                    fecha_firma_gerencia,
                    fecha_entrega_finanzas_sumilla,
                    fecha_entrega_originales_fin,
                    fechas_pago_anticipo,
                    fecha_entrega_pedido,
                    observaciones,
                    "No aprobado",
                    usuario_solicitante_id,
                    usuario_compras_nombre,
                    usuario_compras_id,
                    departamento_id,
                    creado_por,
                ),
            )
            row_new = cur_ins.fetchone()
            nuevo_contrato_id = row_new[0] if row_new else None
            conn.commit()

            # === NUEVO: guardar PDFs asociados ===
            _save_contrato_pdfs(nuevo_contrato_id)

            # =============== ENVÍO DE CORREOS ===============
            try:
                r_user = cur.execute(
                    """
                    SELECT TOP 1
                        COALESCE(nombre_completo, username) AS nombre,
                        email
                    FROM usuarios
                    WHERE id=?
                    """,
                    (usuario_solicitante_id,),
                ).fetchone()
                solicitante_nombre = (r_user["nombre"] if r_user else "") or ""
                solicitante_email = (r_user["email"] if r_user else "") or ""

                compras_email = _find_compras_email(conn, usuario_compras_id, usuario_compras_nombre)
                pgallegos_email = _pgallegos_email(conn)

                link_contrato = _link_contrato(nuevo_contrato_id)
                subject_user = f"[SILI] Contrato registrado: Pedido {pedido} – {proveedor}"
                subject_compra = f"[SILI] Nuevo contrato registrado: Pedido {pedido} – {proveedor}"
                subject_pg = f"[SILI] Revisión requerida: Pedido {pedido} – {proveedor}"

                body_user_txt = (
                    f"Hola {solicitante_nombre},\n\n"
                    f"Tu contrato fue registrado correctamente.\n\n"
                    f"Pedido: {pedido}\n"
                    f"Proveedor: {proveedor}\n"
                    f"Objeto: {objeto}\n"
                    f"Valor: {valor_contrato:,.2f}\n"
                    f"Fecha de suscripción: {fecha_suscripcion}\n\n"
                    f"Ver detalle: {link_contrato}\n\n"
                    f"— SILI"
                )
                body_compra_txt = (
                    "Estimado/a Compras,\n\n"
                    "Se registró un nuevo contrato.\n\n"
                    f"Pedido: {pedido}\n"
                    f"Proveedor: {proveedor}\n"
                    f"Objeto: {objeto}\n"
                    f"Valor: {valor_contrato:,.2f}\n"
                    f"Fecha de suscripción: {fecha_suscripcion}\n\n"
                    f"Ver contrato: {link_contrato}\n\n"
                    "— SILI"
                )
                body_pg_txt = (
                    "Estimado/a,\n\n"
                    "Se ha registrado un nuevo contrato que requiere REVISIÓN y APROBACIÓN.\n\n"
                    f"Pedido: {pedido}\n"
                    f"Proveedor: {proveedor}\n"
                    f"Objeto: {objeto}\n"
                    f"Valor: {valor_contrato:,.2f}\n"
                    f"Fecha de suscripción: {fecha_suscripcion}\n\n"
                    f"Ver contrato: {link_contrato}\n\n"
                    "— SILI"
                )

                if solicitante_email:
                    _send_mail(solicitante_email, subject_user, body_user_txt)
                if compras_email:
                    _send_mail(compras_email, subject_compra, body_compra_txt)
                if pgallegos_email:
                    _send_mail(pgallegos_email, subject_pg, body_pg_txt)

            except Exception as _e:
                try:
                    current_app.logger.warning(
                        "Fallo envío de correos (contrato %s): %s", nuevo_contrato_id, _e
                    )
                except Exception:
                    pass
        finally:
            # nada que cerrar: get_db() lo maneja Flask
            pass

        flash("Contrato guardado correctamente.", "success")
        return redirect(url_for("contratos.compras_lista"))

    # ========================= GET (nuevo contrato) =========================
    # Prellenar "Usuario compras" con el usuario logueado
    row = {}
    uid_actual = _session_user_id()
    if uid_actual:
        conn_u = get_db()
        r = conn_u.execute(
            """
            SELECT TOP 1 COALESCE(nombre_completo, username) AS nombre
            FROM usuarios
            WHERE id=?
            """,
            (uid_actual,),
        ).fetchone()
        if r and r["nombre"]:
            row["usuario_compras_nombre"] = r["nombre"]

    from modules.security import has_permission as _hp
    can_exportar = _hp(session.get("rol"), "contratos_ingresar", "exportar")

    return render_template(
        "compras_ingreso.html",
        mode="create",
        row=row,
        usuarios=usuarios,
        proveedores=proveedores,
        archivos=[],           # no hay archivos aún
        can_exportar=can_exportar,
        post_url=url_for("contratos.compras_nuevo"),
        back_url=request.args.get("next") or url_for("contratos.compras_lista"),
    )

@contratos_bp.route("/compras/<int:contrato_id>/editar", methods=["GET", "POST"])
@require_login
@require_permission("contratos_ingresar", "ver")
def compras_editar(contrato_id: int):
    session["active_page"] = "contratos_ingresar"
    _ensure_contratos_columns()
    _ensure_softdelete_columns()
    _ensure_contrato_archivos_table()  # <- NUEVO

    conn = get_db()
    cur = conn.cursor()

    # ===== Combos =====
    usuarios = cur.execute(
        """
        SELECT
            u.id,
            u.nombre_completo AS nombre,
            COALESCE(d.nombre,'') AS departamento
        FROM usuarios u
        LEFT JOIN departamentos d ON d.id = u.departamento_id
        WHERE COALESCE(u.disabled,0)=0
          AND TRIM(COALESCE(u.nombre_completo,'')) <> ''
        ORDER BY u.nombre_completo
        """
    ).fetchall()
    proveedores = cur.execute(
        """
        SELECT id, nombre
        FROM terceros
        WHERE tipo='P' AND COALESCE(activo,1)=1
        ORDER BY nombre
    """
    ).fetchall()

    # ===== Registro a editar =====
    row_db = cur.execute("SELECT * FROM contratos WHERE id=?", (contrato_id,)).fetchone()
    if not row_db:
        abort(404)

    # ---------- BLOQUEO: no permitir edición si ya está aprobado ----------
    # Criterios: aprobado por Jefatura, aprobado (gerencias) o aprobado GF.
    tiene_aprob_jefe = int((row_db["aprobado_jefe"] or 0) if "aprobado_jefe" in row_db.keys() else 0)
    tiene_aprob = int((row_db["aprobado"] or 0) if "aprobado" in row_db.keys() else 0)
    tiene_aprob_gf = int((row_db["aprob_gf"] or 0) if "aprob_gf" in row_db.keys() else 0)

    if tiene_aprob_jefe or tiene_aprob or tiene_aprob_gf:
        flash("Este contrato ya fue aprobado y no puede ser editado.", "warning")
        return redirect(url_for("contratos.compras_lista"))
    # ---------------------------------------------------------------------

    # Para el GET: dict + proveedor_id (pre-selección en combo)
    row = dict(row_db)
    prow = cur.execute(
        "SELECT id FROM terceros WHERE tipo='P' AND COALESCE(activo,1)=1 AND nombre=?",
        (row.get("proveedor"),),
    ).fetchone()
    row["proveedor_id"] = prow["id"] if prow else None

    # Archivos asociados (lista para el template)
    archivos = cur.execute(
        """
        SELECT id, filename, original_name, uploaded_at
        FROM contrato_archivos
        WHERE contrato_id=?
        ORDER BY id
        """,
        (contrato_id,),
    ).fetchall()

    from modules.security import has_permission as _hp
    can_exportar = _hp(session.get("rol"), "contratos_ingresar", "exportar")

    if request.method == "POST":
        from modules.security import has_permission

        if not has_permission(session.get("rol"), "contratos_ingresar", "editar"):
            flash("No tiene permiso para editar contratos.", "danger")
            return redirect(url_for("contratos.compras_lista"))

        # Doble verificación por seguridad (por si cambió el estado entre GET y POST)
        row_estado = cur.execute(
            "SELECT aprobado_jefe, aprobado, aprob_gf FROM contratos WHERE id=?", (contrato_id,),
        ).fetchone()
        if row_estado:
            if (
                int(row_estado["aprobado_jefe"] or 0)
                or int(row_estado["aprobado"] or 0)
                or int(row_estado["aprob_gf"] or 0)
            ):
                flash("El contrato fue aprobado recientemente y ya no puede editarse.", "warning")
                return redirect(url_for("contratos.compras_lista"))

        def _nfloat(v):
            try:
                return float(str(v).replace(",", ""))
            except:
                return 0.0

        # ---- IDs
        usuario_solicitante_id = _safe_int(request.form.get("usuario_solicitante_id"))
        usuario_compras_id = _safe_int(request.form.get("usuario_compras_id")) or _safe_int(
            session.get("usuario_id")
        )

        # Sanitizar FKs que podrían romper (si no existen -> NULL)
        if usuario_compras_id and cur.execute(
            "SELECT TOP 1 1 AS ok FROM usuarios WHERE id=?", (usuario_compras_id,)
        ).fetchone() is None:
            usuario_compras_id = None

        if usuario_solicitante_id and cur.execute(
            "SELECT TOP 1 1 AS ok FROM usuarios WHERE id=?", (usuario_solicitante_id,)
        ).fetchone() is None:
            flash("Usuario solicitante inexistente.", "danger")
            return redirect(url_for("contratos.compras_lista"))

        # ---- Cabecera
        anio = (request.form.get("anio") or "").strip()
        pedido = (request.form.get("pedido") or "").strip()

        # ---- Proveedor (prioriza id del combo; si no, texto)
        proveedor = None
        prov_id = _safe_int(request.form.get("proveedor_id"))
        if prov_id:
            r = cur.execute(
                """
                SELECT nombre FROM terceros
                WHERE id=? AND tipo='P' AND COALESCE(activo,1)=1
            """,
                (prov_id,),
            ).fetchone()
            proveedor = r["nombre"] if r else None
        if not proveedor:
            proveedor = (request.form.get("proveedor") or "").strip()

        # ---- Resto de campos
        objeto = (request.form.get("objeto") or request.form.get("objeto_contrato") or "").strip()
        valor_contrato = _nfloat(request.form.get("valor_contrato"))
        valor_anticipo = _nfloat(request.form.get("valor_anticipo"))
        fecha_suscripcion = _f(request.form.get("fecha_suscripcion"))
        fecha_terminacion = _f(request.form.get("fecha_terminacion"))
        plazo_dias = _safe_int(request.form.get("plazo_dias")) or 0
        cronograma_pagos = (request.form.get("cronograma_pagos") or "").strip()
        fecha_entrega_compras = _f(request.form.get("fecha_entrega_compras"))
        fecha_firma_gerencia = _f(request.form.get("fecha_firma_gerencia"))
        fecha_entrega_finanzas_sumilla = _f(
            request.form.get("fecha_entrega_finanzas_sumilla")
            or request.form.get("fecha_entrega_a_finanzas_sumilla")
        )
        fecha_entrega_originales_fin = _f(
            request.form.get("fecha_entrega_originales_finanzas")
            or request.form.get("fecha_entrega_originales_a_finanzas")
        )
        fechas_pago_anticipo = (request.form.get("fechas_pago_anticipo") or "").strip()
        fecha_entrega_pedido = _f(request.form.get("fecha_entrega_pedido"))
        observaciones = (request.form.get("observaciones") or "").strip()

        # ---- Validaciones mínimas
        missing_required = []
        if not anio:
            missing_required.append("AÑO")
        if not pedido:
            missing_required.append("PEDIDO")
        if not proveedor:
            missing_required.append("PROVEEDOR")
        if not objeto:
            missing_required.append("Objeto del contrato")
        if valor_contrato is None or valor_contrato <= 0:
            missing_required.append("Valor contrato")
        if not fecha_suscripcion:
            missing_required.append("Fecha de suscripción")

        if missing_required:
            flash("Campos obligatorios incompletos: " + ", ".join(missing_required), "danger")
            row_back = {
                "anio": anio,
                "pedido": pedido,
                "proveedor": proveedor,
                "proveedor_id": prov_id,
                "objeto": objeto,
                "valor_contrato": valor_contrato,
                "valor_anticipo": valor_anticipo,
                "fecha_suscripcion": fecha_suscripcion,
                "fecha_terminacion": fecha_terminacion,
                "plazo_dias": plazo_dias,
                "cronograma_pagos": cronograma_pagos,
                "fecha_entrega_compras": fecha_entrega_compras,
                "fecha_firma_gerencia": fecha_firma_gerencia,
                "fecha_entrega_finanzas_sumilla": fecha_entrega_finanzas_sumilla,
                "fecha_entrega_originales_fin": fecha_entrega_originales_fin,
                "fechas_pago_anticipo": fechas_pago_anticipo,
                "fecha_entrega_pedido": fecha_entrega_pedido,
                "observaciones": observaciones,
                "usuario_solicitante_id": usuario_solicitante_id,
            }
            return render_template(
                "compras_ingreso.html",
                mode="edit",
                row=row_back,
                usuarios=usuarios,
                proveedores=proveedores,
                archivos=archivos,
                can_exportar=can_exportar,
                post_url=url_for("contratos.compras_editar", contrato_id=contrato_id),
                back_url=request.form.get("next") or url_for("contratos.compras_lista"),
            )

        # ---- Regla de negocio: anticipo <= contrato ----
        if (valor_contrato or 0) > 0 and (valor_anticipo or 0) > valor_contrato:
            flash("El valor del anticipo no puede ser mayor que el valor del contrato.", "danger")
            row_back = {
                "anio": anio,
                "pedido": pedido,
                "proveedor": proveedor,
                "proveedor_id": prov_id,
                "objeto": objeto,
                "valor_contrato": valor_contrato,
                "valor_anticipo": valor_anticipo,
                "fecha_suscripcion": fecha_suscripcion,
                "fecha_terminacion": fecha_terminacion,
                "plazo_dias": plazo_dias,
                "cronograma_pagos": cronograma_pagos,
                "fecha_entrega_compras": fecha_entrega_compras,
                "fecha_firma_gerencia": fecha_firma_gerencia,
                "fecha_entrega_finanzas_sumilla": fecha_entrega_finanzas_sumilla,
                "fecha_entrega_originales_fin": fecha_entrega_originales_fin,
                "fechas_pago_anticipo": fechas_pago_anticipo,
                "fecha_entrega_pedido": fecha_entrega_pedido,
                "observaciones": observaciones,
                "usuario_solicitante_id": usuario_solicitante_id,
                "usuario_compras_nombre": (request.form.get("usuario_compras_nombre") or "").strip(),
            }
            return render_template(
                "compras_ingreso.html",
                mode="edit",
                row=row_back,
                usuarios=usuarios,
                proveedores=proveedores,
                archivos=archivos,
                can_exportar=can_exportar,
                post_url=url_for("contratos.compras_editar", contrato_id=contrato_id),
                back_url=request.form.get("next") or url_for("contratos.compras_lista"),
            )

        # ---- UPDATE (si no está aprobado) ----
        cur.execute(
            """
            UPDATE contratos
            SET anio=?, pedido=?, proveedor=?, objeto=?, valor_contrato=?, valor_anticipo=?,
                fecha_suscripcion=?, fecha_terminacion=?, plazo_dias=?, cronograma_pagos=?,
                fecha_entrega_compras=?, fecha_firma_gerencia=?, fecha_entrega_finanzas_sumilla=?,
                fecha_entrega_originales_fin=?, fechas_pago_anticipo=?, fecha_entrega_pedido=?,
                observaciones=?, usuario_solicitante_id=?, usuario_compras_id=?,
                actualizado_at=GETDATE()
            WHERE id=?
        """,
            (
                _safe_int(anio),
                pedido,
                proveedor,
                objeto,
                valor_contrato,
                valor_anticipo,
                fecha_suscripcion,
                fecha_terminacion,
                plazo_dias,
                cronograma_pagos,
                fecha_entrega_compras,
                fecha_firma_gerencia,
                fecha_entrega_finanzas_sumilla,
                fecha_entrega_originales_fin,
                fechas_pago_anticipo,
                fecha_entrega_pedido,
                observaciones,
                usuario_solicitante_id,
                usuario_compras_id,
                contrato_id,
            ),
        )
        conn.commit()

        # === NUEVO: guardar PDFs adicionales (no borra los anteriores) ===
        _save_contrato_pdfs(contrato_id)

        flash("Contrato actualizado.", "success")
        return redirect(url_for("contratos.compras_lista"))

    # ===== GET edición =====
    return render_template(
        "compras_ingreso.html",
        mode="edit",
        row=row,
        usuarios=usuarios,
        proveedores=proveedores,
        archivos=archivos,
        can_exportar=can_exportar,
        post_url=url_for("contratos.compras_editar", contrato_id=contrato_id),
        back_url=request.args.get("next") or url_for("contratos.compras_lista"),
    )


@contratos_bp.route("/compras/<int:contrato_id>/eliminar", methods=["POST"])
@require_login
@require_permission("contratos_ingresar", "eliminar")
def compras_eliminar(contrato_id: int):
    _ensure_softdelete_columns()
    conn = get_db()
    cur = conn.cursor()
    row = cur.execute("SELECT id FROM contratos WHERE id=?", (contrato_id,)).fetchone()
    if not row:
        abort(404)

    cur.execute(
        """
        UPDATE contratos
           SET disabled=1, actualizado_at=GETDATE()
         WHERE id=?
    """,
        (contrato_id,),
    )
    conn.commit()
    flash("Contrato eliminado.", "success")
    return redirect(url_for("contratos.compras_lista"))


@contratos_bp.route("/compras", methods=["GET"])
@require_login
@require_permission("contratos_ingresar", "ver")
def compras_lista():
    session["active_page"] = "contratos_ingresar"
    _ensure_contratos_columns()
    _ensure_softdelete_columns()

    prov = (request.args.get("proveedor") or "").strip()
    pedi = (request.args.get("pedido") or "").strip()
    tipo = (
        (request.args.get("tipo_pp") or request.args.get("pagare_poliza_filtro") or "")
        .strip()
        .upper()
    )

    conn = get_db()
    cur = conn.cursor()

    col_aprob_jefe = "COALESCE(c.aprobado_jefe,0) AS aprobado_jefe"

    sql = f"""
    SELECT TOP 300
            c.id, c.pedido, c.proveedor, c.objeto, c.valor_contrato, c.tipo_pp,
            c.fecha_suscripcion, c.fecha_terminacion, c.status_interno, {col_aprob_jefe},
            COALESCE(c.aprobado,0) AS aprobado,
            COALESCE(c.aprob_gf,0) AS aprob_gf,
            (
                SELECT COUNT(1)
                FROM contrato_archivos a
                WHERE a.contrato_id = c.id
            ) AS adjuntos_cnt
    FROM contratos c
    WHERE COALESCE(c.disabled,0)=0
    """
    params: List[Any] = []
    if prov:
        sql += " AND c.proveedor LIKE ?"
        params.append(f"%{prov}%")
    if pedi:
        sql += " AND c.pedido LIKE ?"
        params.append(f"%{pedi}%")
    if tipo in ("PAGARE", "POLIZA", "AMBOS"):
        sql += " AND c.tipo_pp = ?"
        params.append(tipo)
    sql += " ORDER BY c.id DESC"

    rows = cur.execute(sql, params).fetchall()
    return render_template("consulta_compras.html", rows=rows)




@contratos_bp.route("/compras/<int:contrato_id>/archivos/fragment", methods=["GET"])
@require_login
@require_permission("contratos_ingresar", "ver")
def compras_archivos_fragment(contrato_id: int):
    _ensure_contrato_archivos_table()
    conn = get_db()
    cur = conn.cursor()
    archivos = cur.execute(
        """
        SELECT id, filename, original_name, uploaded_at
        FROM contrato_archivos
        WHERE contrato_id=?
        ORDER BY id DESC
        """,
        (contrato_id,),
    ).fetchall()

    from modules.security import has_permission as _hp
    can_exportar = _hp(session.get("rol"), "contratos_ingresar", "exportar")

    return render_template(
        "contrato_archivos_modal_fragment.html",
        archivos=archivos,
        can_exportar=can_exportar,
    )

# --- Toggle aprobación Jefe (Compras) ---
@contratos_bp.route(
    "/compras/<int:contrato_id>/aprobj/toggle",
    methods=["POST"],
    endpoint="toggle_aprobacion_jefe",
)
@require_login
@require_permission("contratos_ingresar", "aprobar")  # Solo roles con aprobar en Compras (ej. Jefe)
def toggle_aprobacion_jefe(contrato_id: int):
    conn = get_db()
    cur = conn.cursor()
    row = cur.execute("SELECT aprobado_jefe FROM contratos WHERE id=?", (contrato_id,)).fetchone()
    if not row:
        abort(404)

    nuevo = 0 if int(row["aprobado_jefe"] or 0) else 1
    status_txt = "Aprobado" if nuevo == 1 else "No aprobado"

    cur.execute(
        """
        UPDATE contratos
        SET aprobado_jefe=?,
            aprobado_jefe_por=?,
            aprobado_jefe_en=GETDATE(),
            status_interno=?,
            actualizado_at=GETDATE()
        WHERE id=?
    """,
        (nuevo, session.get("usuario_id"), status_txt, contrato_id),
    )

    conn.commit()
    # ======= CORREOS al aprobar / desaprobar contrato (sin 'del jefe') =======
    try:
        c2 = get_db()
        k = c2.cursor()
        fila = k.execute(
            """
            SELECT c.id, c.pedido, c.proveedor, c.objeto, c.valor_contrato, c.fecha_suscripcion,
                c.usuario_solicitante_id, c.usuario_compras_id, c.usuario_compras_nombre,
                c.aprobado_jefe, c.aprobado_jefe_por
            FROM contratos c
            WHERE c.id=?
        """,
            (contrato_id,),
        ).fetchone()

        pedido = fila["pedido"]
        proveedor = fila["proveedor"]
        objeto = fila["objeto"]
        valor_contrato = fila["valor_contrato"]
        fecha_suscripcion = fila["fecha_suscripcion"]
        aprobado_jefe = int(fila["aprobado_jefe"] or 0)

        # destinatarios
        solicitante_email = _lookup_email_by_user_id(c2, fila["usuario_solicitante_id"])
        compras_email = _find_compras_email(
            c2, fila["usuario_compras_id"], fila["usuario_compras_nombre"]
        )
        jefe_email = _lookup_email_by_user_id(c2, fila["aprobado_jefe_por"])
        savera_mail = _savera_email()

        link_contrato = _link_contrato(contrato_id)

        if aprobado_jefe == 1:
            # Aprobado (texto neutro, sin 'del jefe')
            subj_jefe = f"[SILI] Aprobación registrada: Pedido {pedido}"
            body_jefe = (
                "Estimado/a,\n\n"
                "Se registró su aprobación del contrato.\n\n"
                f"Pedido: {pedido}\n"
                f"Proveedor: {proveedor}\n"
                f"Objeto: {objeto}\n"
                f"Valor: {valor_contrato:,.2f}\n"
                f"Ver contrato: {link_contrato}\n\n"
                "— SILI"
            )
            subj_info = f"[SILI] Contrato aprobado por Compras: Pedido {pedido}"
            body_info = (
                "Notificación:\n\n"
                "El contrato fue aprobado por el área de Compras.\n\n"
                f"Pedido: {pedido}\nProveedor: {proveedor}\nObjeto: {objeto}\n"
                f"Valor: {valor_contrato:,.2f}\n"
                f"Ver contrato: {link_contrato}\n\n"
                "— SILI"
            )
            # Savera: instrucción de gestión de garantía
            subj_savera = f"[SILI] Contrato aprobado: Gestionar Garantía (Pedido {pedido})"
            body_savera = (
                "Hola Savera,\n\n"
                "El contrato indicado fue ingresado y aprobado por Compras.\n"
                "Por favor, proceder con la gestión e ingreso de la GARANTÍA asociada para su aprobación.\n\n"
                f"Pedido: {pedido}\nProveedor: {proveedor}\nObjeto: {objeto}\n"
                f"Ver contrato: {link_contrato}\n\n"
                "— SILI"
            )
            if jefe_email:
                _send_mail(jefe_email, subj_jefe, body_jefe)
            if solicitante_email:
                _send_mail(solicitante_email, subj_info, body_info)
            if compras_email:
                _send_mail(compras_email, subj_info, body_info)
            if savera_mail:
                _send_mail(savera_mail, subj_savera, body_savera)
        else:
            # Reverso de aprobación (sin 'del Jefe')
            subj_rev = f"[SILI] Aprobación revertida: Pedido {pedido}"
            body_rev = (
                "Notificación:\n\n"
                "La aprobación del contrato fue revertida.\n\n"
                f"Pedido: {pedido}\nProveedor: {proveedor}\nObjeto: {objeto}\n"
                f"Ver contrato: {link_contrato}\n\n"
                "— SILI"
            )
            if jefe_email:
                _send_mail(jefe_email, subj_rev, body_rev)
            if solicitante_email:
                _send_mail(solicitante_email, subj_rev, body_rev)
            if compras_email:
                _send_mail(compras_email, subj_rev, body_rev)
    except Exception as _e:
        try:
            current_app.logger.warning(
                "Fallo correos toggle_aprobacion_jefe(%s): %s", contrato_id, _e
            )
        except Exception:
            pass

    flash("Aprobación actualizada.", "success")
    return redirect(request.referrer or url_for("contratos.compras_lista"))


# =========================================================
#   CONTABILIDAD (Garantías) — SOLO Contabilidad
# =========================================================
@contratos_bp.route("/contab", methods=["GET"])
@require_login
@require_permission("contratos_garantias", "ver")
def contab_lista():
    session["active_page"] = "contratos_garantias"
    _ensure_garantias_columns()
    _ensure_garantias_columns()

    prov = (request.args.get("proveedor") or "").strip()
    pedi = (request.args.get("pedido") or "").strip()
    estado = (request.args.get("estado") or "").strip()
    requiere = (
        (request.args.get("renovacion") or request.args.get("requiere_renovacion") or "")
        .strip()
        .lower()
    )

    sql = """
     SELECT TOP 300 g.id, g.contrato_id, g.tipo, g.monto_poliza, g.estado,
            g.fecha_suscripcion, g.fecha_vencimiento, g.requiere_renovacion,
            g.status_interno,
            COALESCE(g.aprobado_jefe,0) AS aprobado_jefe,
            COALESCE(g.aprobado,0)      AS aprobado,
            COALESCE(g.aprob_gf,0)      AS aprob_gf,
            c.pedido, c.proveedor, c.objeto, c.valor_contrato
    FROM garantias g
    JOIN contratos c ON c.id = g.contrato_id
    WHERE COALESCE(g.disabled,0)=0
      AND COALESCE(c.disabled,0)=0
     """
    params: List[Any] = []
    if prov:
        sql += " AND c.proveedor LIKE ?"
        params.append(f"%{prov}%")
    if pedi:
        sql += " AND c.pedido LIKE ?"
        params.append(f"%{pedi}%")
    if estado:
        sql += " AND g.estado = ?"
        params.append(estado)
    if requiere in ("si", "sí", "no", "0", "1", "true", "false"):
        sql += " AND g.requiere_renovacion = ?"
        params.append(1 if requiere in ("si", "sí", "1", "true") else 0)

    sql += " ORDER BY g.id DESC"

    conn = get_db()
    cur = conn.cursor()
    rows = cur.execute(sql, params).fetchall()
    return render_template("consulta_contabilidad.html", rows=rows)



@contratos_bp.route("/ver/garantia/<int:garantia_id>/fragment", methods=["GET"])
@require_login
@require_permission("contratos_garantias", "ver")
def ver_garantia_fragment(garantia_id):
    conn = get_db()
    cur = conn.cursor()

    row = cur.execute("""
            SELECT
            g.id,
            g.contrato_id,
            g.tipo,
            COALESCE(g.monto_poliza,0) AS monto_poliza,
            g.estado,
            g.fecha_suscripcion,
            g.fecha_vencimiento,
            g.requiere_renovacion,
            g.status_interno,

            -- 👇 agrega estas SOLO si existen en tu tabla (ajusta nombres reales)
            g.compania_emisora AS compania_emisora,
            g.observaciones    AS observaciones,
            g.fecha_renovacion AS fecha_renovacion,
            '' AS fecha_vencimiento_actualizado,

            COALESCE(g.aprobado_jefe,0) AS aprobado_jefe,
            COALESCE(g.aprobado,0)      AS aprobado,
            COALESCE(g.aprob_gf,0)      AS aprob_gf,

            c.pedido AS pedido,
            c.proveedor AS proveedor,
            c.objeto AS objeto,
            c.valor_contrato AS valor_contrato
            FROM garantias g
            JOIN contratos c ON c.id = g.contrato_id
            WHERE g.id = ?
    """, (garantia_id,)).fetchone()

    if not row:
        return "<div class='alert alert-warning mb-0'>No existe la garantía.</div>", 404

    # separa en dos dicts para el template (más claro)
    garantia = dict(row)
    contrato = {
        "pedido": row["pedido"],
        "proveedor": row["proveedor"],
        "objeto": row["objeto"],
        "valor_contrato": row["valor_contrato"],
    }

    return render_template(
        "garantia_detalle_fragment.html",
        garantia=garantia,
        contrato=contrato,
        proveedor=row["proveedor"],
        pedido=row["pedido"],
    )

@contratos_bp.route("/contab/nuevo", methods=["GET", "POST"])
@require_login
@require_permission("contratos_garantias", "crear")
def contab_nuevo():
    session["active_page"] = "contratos_garantias"
    _ensure_garantias_columns()
    _ensure_softdelete_columns()

    if request.method == "POST":
        # --- Campos obligatorios según Excel ---
        contrato_id = _safe_int(request.form.get("contrato_id"))
        tipo = (request.form.get("tipo") or request.form.get("pagare_poliza") or "").strip().upper()
        if tipo == "PAGARÉ":
            tipo = "PAGARE"
        compania_emisora = (request.form.get("compania_emisora") or "").strip()
        monto_poliza = float(request.form.get("monto_poliza") or 0)
        fecha_suscripcion = _f(request.form.get("fecha_suscripcion"))
        fecha_vencimiento = _f(request.form.get("fecha_vencimiento"))
        fecha_venc_act = _f(request.form.get("fecha_vencimiento_actualizada"))
        vigencia_dias = _safe_int(request.form.get("vigencia_dias")) or 0
        estado = (request.form.get("estado") or "").strip() or "Vigente"
        fecha_renovacion = _f(request.form.get("fecha_renovacion"))
        requiere_renovacion = _bool(request.form.get("requiere_renovacion"))
        observaciones = (request.form.get("observaciones") or "").strip()
        status_interno = (request.form.get("status_interno") or "").strip()

        # Validaciones mínimas
        missing = []
        if not contrato_id:
            missing.append("Contrato")
        if tipo not in ("PAGARE", "POLIZA"):
            missing.append("Pagaré / Póliza")
        if not fecha_suscripcion:
            missing.append("Fecha de suscripción")
        if not fecha_vencimiento:
            missing.append("Fecha de vencimiento")
        if estado not in ("Vigente", "Vencida", "Liberada", "Anulada"):
            missing.append("Estado")
        if request.form.get("requiere_renovacion") in ("", None):
            missing.append("Requiere renovación")

        conn = get_db()
        cur = conn.cursor()
        # FK contrato
        if contrato_id and not _exists(conn, "contratos", contrato_id):
            missing.append("Contrato inexistente")

        if missing:
            flash("Campos obligatorios incompletos: " + ", ".join(missing), "danger")
            # Re-cargar combos (solo aprobados por Jefatura)
            conn2 = get_db()
            contratos = _list_contratos_aprobados_sin_garantia(conn2, limit=200)
            row_back = dict(
                contrato_id=contrato_id,
                tipo=tipo,
                compania_emisora=compania_emisora,
                monto_poliza=monto_poliza,
                fecha_suscripcion=fecha_suscripcion,
                fecha_vencimiento=fecha_vencimiento,
                fecha_vencimiento_actualizada=fecha_venc_act,
                vigencia_dias=vigencia_dias,
                estado=estado,
                fecha_renovacion=fecha_renovacion,
                requiere_renovacion=requiere_renovacion,
                observaciones=observaciones,
                status_interno=status_interno,
            )
            return render_template(
                "contabilidad_ingreso.html",
                mode="create",
                row=row_back,
                contratos=contratos,
                post_url=url_for("contratos.contab_nuevo"),
                back_url=request.form.get("next") or url_for("contratos.contab_lista"),
            )

                # Insert con retry
        insert_sql = """
            INSERT INTO garantias (
              contrato_id, tipo, compania_emisora, monto_poliza,
              fecha_suscripcion, fecha_vencimiento, fecha_vencimiento_actual,
              vigencia_dias, estado, fecha_renovacion, requiere_renovacion,
              status_interno, observaciones, actualizado_at
            )
            OUTPUT inserted.id
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,GETDATE())
        """
        cur_new = exec_retry(
            conn,
            insert_sql,
            (
                contrato_id,
                tipo,
                compania_emisora,
                monto_poliza,
                fecha_suscripcion,
                fecha_vencimiento,
                fecha_venc_act,
                vigencia_dias,
                estado,
                fecha_renovacion,
                requiere_renovacion,
                status_interno,
                observaciones,
            ),
        )
        row_new = cur_new.fetchone()
        nueva_garantia_id = row_new[0] if row_new else None
        conn.commit()
        # Adjuntos PDF que se vinculan al contrato (contrato_archivos)
        _save_contrato_pdfs(contrato_id)
        # ======= CORREOS: ingreso de garantía =======
        try:
            c2 = get_db()
            k = c2.cursor()
            garantia_id = nueva_garantia_id

            c = k.execute(
                """
                SELECT c.id, c.pedido, c.proveedor, c.objeto, c.usuario_solicitante_id,
                    c.usuario_compras_id, c.usuario_compras_nombre, c.aprobado_jefe_por
                FROM contratos c
                WHERE c.id=?
            """,
                (contrato_id,),
            ).fetchone()

            pedido = c["pedido"]
            proveedor = c["proveedor"]
            objeto = c["objeto"]
            solicitante_email = _lookup_email_by_user_id(c2, c["usuario_solicitante_id"])
            compras_email = _find_compras_email(
                c2, c["usuario_compras_id"], c["usuario_compras_nombre"]
            )
            jefe_email = _lookup_email_by_user_id(c2, c["aprobado_jefe_por"])
            savera_mail = _savera_email()

            link_g = _link_garantia(garantia_id) if garantia_id else _link_contrato(contrato_id)

            # Savera (confirmación de ingreso)
            subj_sv = f"[SILI] Garantía ingresada para Pedido {pedido}"
            body_sv = (
                "Hola Savera,\n\n"
                "Se registró correctamente la GARANTÍA asociada a su contrato.\n\n"
                f"Pedido: {pedido}\nProveedor: {proveedor}\nObjeto: {objeto}\n"
                f"Ver garantía: {link_g}\n\n"
                "— SILI"
            )
            # Informativos a Jefe/Compras/Solicitante
            subj_inf = f"[SILI] Garantía ingresada: Pedido {pedido}"
            body_inf = (
                "Notificación:\n\n"
                "Se ha ingresado una GARANTÍA para el contrato indicado.\n\n"
                f"Pedido: {pedido}\nProveedor: {proveedor}\nObjeto: {objeto}\n"
                f"Detalle: {link_g}\n\n"
                "— SILI"
            )
            if savera_mail:
                _send_mail(savera_mail, subj_sv, body_sv)
            if jefe_email:
                _send_mail(jefe_email, subj_inf, body_inf)
            if solicitante_email:
                _send_mail(solicitante_email, subj_inf, body_inf)
            if compras_email:
                _send_mail(compras_email, subj_inf, body_inf)
        except Exception as _e:
            try:
                current_app.logger.warning(
                    "Fallo correos contab_nuevo(contrato %s): %s", contrato_id, _e
                )
            except Exception:
                pass

        flash("Garantía guardada correctamente.", "success")
        return redirect(request.form.get("next") or url_for("contratos.contab_lista"))

    # GET → combo de contratos
    conn = get_db()
    contratos = _list_contratos_aprobados_sin_garantia(conn, limit=200)

    return render_template(
        "contabilidad_ingreso.html",
        mode="create",
        row={},
        contratos=contratos,
        post_url=url_for("contratos.contab_nuevo"),
        back_url=request.args.get("next") or url_for("contratos.contab_lista"),
    )


@contratos_bp.route("/contab/<int:garantia_id>/editar", methods=["GET", "POST"])
@require_login
@require_permission("contratos_garantias", "editar")
def contab_editar(garantia_id: int):
    session["active_page"] = "contratos_garantias"
    _ensure_garantias_columns()
    _ensure_softdelete_columns()

    conn = get_db()
    cur = conn.cursor()

    # (Recomendado) No permitir editar garantías deshabilitadas:
    row_db = cur.execute(
        """
        SELECT
            g.*,
            COALESCE(g.aprobado_jefe,0) AS aprobado_jefe,
            COALESCE(g.aprobado,0)      AS aprobado,
            COALESCE(g.aprob_gf,0)      AS aprob_gf
        FROM garantias g
        WHERE g.id=? AND COALESCE(g.disabled,0)=0
        """,
        (garantia_id,),
    ).fetchone()
    if not row_db:
        abort(404)

    # ---------- BLOQUEO: no permitir edición si ya está aprobada ----------
    # Criterios: aprobado por Jefatura, aprobado (instancia) o aprobado GF.
    tiene_aprob_jefe = int((row_db["aprobado_jefe"] or 0) if "aprobado_jefe" in row_db.keys() else 0)
    tiene_aprob = int((row_db["aprobado"] or 0) if "aprobado" in row_db.keys() else 0)
    tiene_aprob_gf = int((row_db["aprob_gf"] or 0) if "aprob_gf" in row_db.keys() else 0)

    if tiene_aprob_jefe or tiene_aprob or tiene_aprob_gf:
        flash("Esta garantía ya fue aprobada y no puede ser editada.", "warning")
        return redirect(url_for("contratos.contab_lista"))
    # ----------------------------------------------------------------------

    if request.method == "POST":
        # Doble verificación por seguridad en POST
        rstate = cur.execute(
            "SELECT aprobado_jefe, aprobado, aprob_gf FROM garantias WHERE id=?",
            (garantia_id,),
        ).fetchone()
        if rstate:
            if (
                int(rstate["aprobado_jefe"] or 0)
                or int(rstate["aprobado"] or 0)
                or int(rstate["aprob_gf"] or 0)
            ):
                flash("La garantía fue aprobada recientemente y ya no puede editarse.", "warning")
                return redirect(url_for("contratos.contab_lista"))

        tipo = (request.form.get("tipo") or "").strip().upper()
        if tipo == "PAGARÉ":
            tipo = "PAGARE"
        compania_emisora = (request.form.get("compania_emisora") or "").strip()
        monto_poliza = float(request.form.get("monto_poliza") or 0)
        fecha_suscripcion = _f(request.form.get("fecha_suscripcion"))
        fecha_vencimiento = _f(request.form.get("fecha_vencimiento"))
        fecha_venc_act = _f(request.form.get("fecha_vencimiento_actualizada"))
        vigencia_dias = _safe_int(request.form.get("vigencia_dias")) or 0
        estado = (request.form.get("estado") or "").strip()
        fecha_renovacion = _f(request.form.get("fecha_renovacion"))
        requiere_renovacion = _bool(request.form.get("requiere_renovacion"))
        observaciones = (request.form.get("observaciones") or "").strip()
        status_interno = (request.form.get("status_interno") or "").strip()

        missing = []
        if tipo not in ("PAGARE", "POLIZA"):
            missing.append("Pagaré / Póliza")
        if not fecha_suscripcion:
            missing.append("Fecha de suscripción")
        if not fecha_vencimiento:
            missing.append("Fecha de vencimiento")
        if estado not in ("Vigente", "Vencida", "Liberada", "Anulada"):
            missing.append("Estado")
        if request.form.get("requiere_renovacion") in ("", None):
            missing.append("Requiere renovación")

        if missing:
            flash("Campos obligatorios incompletos: " + ", ".join(missing), "danger")
            # recargar combos (aprobados por Jefatura) e incluir el actual si no cumple
            conn2 = get_db()
            contratos = _list_contratos_aprobados_sin_garantia(
                conn2, limit=200, include_id=row_db["contrato_id"]
            )
            row_back = dict(row_db)
            row_back.update(
                dict(
                    tipo=tipo,
                    compania_emisora=compania_emisora,
                    monto_poliza=monto_poliza,
                    fecha_suscripcion=fecha_suscripcion,
                    fecha_vencimiento=fecha_vencimiento,
                    fecha_vencimiento_actualizada=fecha_venc_act,
                    vigencia_dias=vigencia_dias,
                    estado=estado,
                    fecha_renovacion=fecha_renovacion,
                    requiere_renovacion=requiere_renovacion,
                    observaciones=observaciones,
                    status_interno=status_interno,
                )
            )
            _ensure_contrato_archivos_table()
            archivos = cur.execute(
                """
                SELECT id, filename, original_name, uploaded_at
                FROM contrato_archivos
                WHERE contrato_id=?
                ORDER BY id DESC
                """,
                (row_db["contrato_id"],),
            ).fetchall()

            return render_template(
                "contabilidad_ingreso.html",
                mode="edit",
                row=row_back,
                contratos=contratos,
                archivos=archivos,  # ✅ nuevo
                post_url=url_for("contratos.contab_editar", garantia_id=garantia_id),
                back_url=request.form.get("next") or url_for("contratos.contab_lista"),
            )

        cur.execute(
            """
            UPDATE garantias
               SET tipo=?, compania_emisora=?, monto_poliza=?,
                   fecha_suscripcion=?, fecha_vencimiento=?, fecha_vencimiento_actual=?,
                   vigencia_dias=?, estado=?, fecha_renovacion=?, requiere_renovacion=?,
                   status_interno=?, observaciones=?, actualizado_at=GETDATE()
             WHERE id=?
        """,
            (
                tipo,
                compania_emisora,
                monto_poliza,
                fecha_suscripcion,
                fecha_vencimiento,
                fecha_venc_act,
                vigencia_dias,
                estado,
                fecha_renovacion,
                requiere_renovacion,
                status_interno,
                observaciones,
                garantia_id,
            ),
        )

        conn.commit()
        _save_contrato_pdfs(row_db["contrato_id"])
        flash("Garantía actualizada.", "success")
        return redirect(url_for("contratos.contab_lista"))

    # GET (cargar combos y fila) solo con contratos habilitados
    contratos = _list_contratos_aprobados_sin_garantia(
        conn, limit=200, include_id=row_db["contrato_id"]
    )
    _ensure_contrato_archivos_table()
    archivos = cur.execute(
            """
            SELECT id, filename, original_name, uploaded_at
            FROM contrato_archivos
            WHERE contrato_id=?
            ORDER BY id DESC
            """,
            (row_db["contrato_id"],),
        ).fetchall()


    return render_template(
        "contabilidad_ingreso.html",
        mode="edit",
        row=dict(row_db),
        contratos=contratos,
        archivos=archivos,  # ✅ nuevo
        post_url=url_for("contratos.contab_editar", garantia_id=garantia_id),
        back_url=request.args.get("next") or url_for("contratos.contab_lista"),
    )


@contratos_bp.route("/contab/<int:garantia_id>/eliminar", methods=["POST"])
@require_login
@require_permission("contratos_garantias", "eliminar")
def contab_eliminar(garantia_id: int):
    _ensure_softdelete_columns()
    conn = get_db()
    cur = conn.cursor()
    row = cur.execute("SELECT id FROM garantias WHERE id=?", (garantia_id,)).fetchone()
    if not row:
        abort(404)

    cur.execute(
        """
        UPDATE garantias
           SET disabled=1, actualizado_at=GETDATE()
         WHERE id=?
    """,
        (garantia_id,),
    )
    conn.commit()
    flash("Garantía eliminada.", "success")
    return redirect(url_for("contratos.contab_lista"))


@contratos_bp.route("/contab/<int:garantia_id>/aprobj/toggle", methods=["POST"])
@require_login
@require_permission(
    "contratos_garantias", "aprobar"
)  # típico para rol Jefe en Contabilidad
def toggle_aprobacion_jefe_garantia(garantia_id: int):
    conn = get_db()
    cur = conn.cursor()
    row = cur.execute("SELECT aprobado_jefe FROM garantias WHERE id=?", (garantia_id,)).fetchone()
    if not row:
        abort(404)

    nuevo = 0 if int(row["aprobado_jefe"] or 0) else 1
    status_txt = "Aprobado" if nuevo == 1 else "No aprobado"

    cur.execute(
        """
        UPDATE garantias
           SET aprobado_jefe=?,
               aprobado_jefe_por=?,
               aprobado_jefe_en=GETDATE(),
               status_interno=?,
               actualizado_at=GETDATE()
         WHERE id=?
    """,
        (nuevo, session.get("usuario_id"), status_txt, garantia_id),
    )

    conn.commit()
    flash("Aprobación de Jefe (Garantía) actualizada.", "success")
    return redirect(request.referrer or url_for("contratos.contab_lista"))

# =========================================================
#   ARCHIVOS PDF DE CONTRATOS
# =========================================================
@contratos_bp.route("/archivo/<int:archivo_id>/ver", methods=["GET"])
@require_login
@require_permission("contratos_ingresar", "ver")
def ver_archivo_contrato(archivo_id: int):
    """
    Muestra el PDF en el navegador (inline).
    Cualquier usuario con permiso 'ver' puede abrirlo.
    """
    _ensure_contrato_archivos_table()
    conn = get_db()
    cur = conn.cursor()
    row = cur.execute(
        """
        SELECT id, contrato_id, filename, original_name
        FROM contrato_archivos
        WHERE id=?
        """,
        (archivo_id,),
    ).fetchone()
    if not row:
        abort(404)

    folder = _get_contratos_upload_folder()
    file_path = os.path.join(folder, row["filename"])
    if not os.path.exists(file_path):
        abort(404)

    return send_file(
        file_path,
        mimetype="application/pdf",
        as_attachment=False,
        download_name=row["original_name"] or "contrato.pdf",
    )


@contratos_bp.route("/archivo/<int:archivo_id>/descargar", methods=["GET"])
@require_login
@require_permission("contratos_ingresar", "exportar")
def descargar_archivo_contrato(archivo_id: int):
    """
    Descarga el PDF.
    Solo usuarios con permiso 'exportar' en contratos_ingresar.
    """
    _ensure_contrato_archivos_table()
    conn = get_db()
    cur = conn.cursor()
    row = cur.execute(
        """
        SELECT id, contrato_id, filename, original_name
        FROM contrato_archivos
        WHERE id=?
        """,
        (archivo_id,),
    ).fetchone()
    if not row:
        abort(404)

    folder = _get_contratos_upload_folder()
    file_path = os.path.join(folder, row["filename"])
    if not os.path.exists(file_path):
        abort(404)

    return send_file(
        file_path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=row["original_name"] or "contrato.pdf",
    )


# =========================================================
#   APROBACIÓN (Gerencias) — marca aprobado/no, sin comentarios
# =========================================================
@contratos_bp.route("/aprobacion", methods=["GET"])
@require_login
@require_permission("contratos_aprobaciones", "ver")
def aprobacion():
    from modules.security import has_permission

    session["active_page"] = "contratos_aprobaciones"

    # asegurar columna aprob_gf
    _ensure_aprob_gf_columns()
    _ensure_softdelete_columns()

    prov = (request.args.get("proveedor") or "").strip()
    pedi = (request.args.get("pedido") or "").strip()
    tipo = (request.args.get("tipo_pp") or "").strip().upper()
    estado = (request.args.get("estado") or "").strip()
    renov = (request.args.get("renovacion") or "").strip()  # "1","0",""

    # --- NUEVO: criterio de elegibilidad para mostrarse en Aprobación (GF) ---
    # Se muestra si:
    #   (a) contrato.aprobado=1 Y garantia.aprobado=1  (aprobación por Gerencias)
    #    OR
    #   (b) contrato aprobado por Jefatura Y garantía aprobada por Jefatura
    #       (aprobado_jefe=1 O status_interno='Aprobado').
    elegibilidad = """
        (
            (COALESCE(c.aprobado,0)=1 AND COALESCE(g.aprobado,0)=1)
            OR
            (
              (COALESCE(c.aprobado_jefe,0)=1 OR c.status_interno='Aprobado')
              AND
              (COALESCE(g.aprobado_jefe,0)=1 OR g.status_interno='Aprobado')
            )
        )
    """

    sql = f"""
        SELECT TOP 400
            c.id AS contrato_id, c.pedido, c.proveedor, c.objeto, c.valor_contrato,
            c.tipo_pp, c.fecha_suscripcion, c.fecha_terminacion,
            c.aprobado AS contrato_aprobado,
            COALESCE(c.aprob_gf,0) AS c_aprob_gf,

            g.id AS garantia_id, g.tipo AS garantia_tipo, g.estado AS garantia_estado,
            g.fecha_vencimiento, g.aprobado AS garantia_aprobado,
            COALESCE(g.requiere_renovacion,0) AS requiere_renovacion
        FROM contratos c
        JOIN garantias g
            ON g.contrato_id = c.id
           AND COALESCE(g.disabled,0)=0
        WHERE COALESCE(c.disabled,0)=0
          AND {elegibilidad}
    """

    params = []
    if prov:
        sql += " AND c.proveedor LIKE ?"
        params.append(f"%{prov}%")
    if pedi:
        sql += " AND c.pedido LIKE ?"
        params.append(f"%{pedi}%")
    if tipo in ("PAGARE", "POLIZA", "AMBOS"):
        sql += " AND c.tipo_pp = ?"
        params.append(tipo)
    if estado:
        sql += " AND COALESCE(g.estado,'') = ?"
        params.append(estado)
    if renov in ("0", "1"):
        sql += " AND COALESCE(g.requiere_renovacion,0) = ?"
        params.append(int(renov))

    sql += " ORDER BY c.id DESC, g.id DESC"

    conn = get_db()
    cur = conn.cursor()
    rows = cur.execute(sql, params).fetchall()

    filtros = {"proveedor": prov, "pedido": pedi, "tipo_pp": (tipo or "")}
    puede_aprobar = has_permission(session.get("rol"), "contratos_aprobaciones", "aprobar")
    return render_template(
        "consulta_aprobacion.html",
        rows=rows,
        filtros=filtros,
        puede_aprobar=puede_aprobar,
    )


@contratos_bp.route("/ver/contrato/<int:contrato_id>/fragment", methods=["GET"])
@require_login
def ver_contrato_fragment(contrato_id: int):
    # Evita mostrar banners/flashes dentro del modal
    get_flashed_messages()
    session.pop("_flashes", None)

    # Importamos aquí para usarlo como _hp
    from modules.security import has_permission as _hp

    def _fmt_money(x):
        try:
            return "${:,.2f}".format(float(x or 0))
        except Exception:
            return ""

    conn = get_db()
    try:
        cur = conn.cursor()
        fila = cur.execute(
            "SELECT * FROM contratos WHERE id=?",
            (contrato_id,),
        ).fetchone()
        if not fila:
            abort(404)

        # proveedor legible
        prov = cur.execute(
            "SELECT TOP 1 nombre FROM terceros WHERE nombre = ?",
            (fila["proveedor"],),
        ).fetchone()
        proveedor = (
            prov["nombre"]
            if (prov and "nombre" in prov.keys() and prov["nombre"])
            else (fila["proveedor"] or "")
        )

        # solicitante (NOMBRE COMPLETO)
        sol = cur.execute(
            """
            SELECT TOP 1 COALESCE(nombre_completo, username) AS nombre
            FROM usuarios
            WHERE id=?
            """,
            (fila["usuario_solicitante_id"],),
        ).fetchone()
        usuario_solicitante = sol["nombre"] if sol else ""

        # usuario de compras (helper ya usa nombre_completo)
        usuario_compras = _resolve_usuario_compras_nombre(conn, fila)

        mapa_tipo = {
            "AMBOS": "Ambos",
            "PAGARE": "Pagaré",
            "PAGARÉ": "Pagaré",
            "POLIZA": "Póliza",
        }
        tipo_pp = mapa_tipo.get(
            (fila["tipo_rp" if "tipo_rp" in fila.keys() else "tipo_pp"] or "").upper(),
            fila["tipo_rp" if "tipo_rp" in fila.keys() else "tipo_pp"],
        )

        # helpers de Sí/No
        def _yn(b):
            return "Sí" if int(b or 0) else "No"

        # estados de aprobación
        aprobado_jef = int(_rowget(fila, "aprobado_jefe", 0) or 0) or (
            (_rowget(fila, "status_interno", "") or "") == "Aprobado"
        )
        aprobado_ger = int(_rowget(fila, "aprobado", 0) or 0)
        aprobado_gf = int(_rowget(fila, "aprob_gf", 0) or 0)

        vista = [
            ("Año", fila["anio"]),
            ("Pedido", fila["pedido"]),
            ("Proveedor", proveedor),
            ("Objeto del contrato", fila["objeto"]),
            ("Valor contrato", _fmt_money(fila["valor_contrato"])),
            ("Valor anticipo", _fmt_money(fila["valor_anticipo"])),
            ("Pagaré / Póliza", tipo_pp),
            ("Fecha de suscripción", fila["fecha_suscripcion"]),
            ("Fecha de terminación", fila["fecha_terminacion"]),
            ("Plazo (días)", fila["plazo_dias"]),
            ("Cronograma de pagos", fila["cronograma_pagos"]),
            ("Fecha entrega a Compras", fila["fecha_entrega_compras"]),
            ("Fecha firma de Gerencia", fila["fecha_firma_gerencia"]),
            ("Fecha de entrega a Finanzas (Sumilla)", fila["fecha_entrega_finanzas_sumilla"]),
            ("Fecha entrega originales a Finanzas", fila["fecha_entrega_originales_fin"]),
            ("Fechas de pago de anticipo", fila["fechas_pago_anticipo"]),
            ("Fecha de entrega de pedido", fila["fecha_entrega_pedido"]),
            ("Usuario solicitante", usuario_solicitante),
            ("Usuario de Compras", usuario_compras),
            # Status interno lo ocultas
            ("Observaciones", fila["observaciones"]),
            ("Aprobación jefatura", _yn(aprobado_jef)),
            ("Aprobación gerencial", _yn(aprobado_ger)),
            ("Aprobación Gerencia Financiera (Final)", _yn(aprobado_gf)),
        ]

        # ===== Archivos PDF del contrato =====
        _ensure_contrato_archivos_table()
        archivos = cur.execute(
            """
            SELECT id, filename, original_name, uploaded_at
            FROM contrato_archivos
            WHERE contrato_id=?
            ORDER BY id
            """,
            (contrato_id,),
        ).fetchall()

        # Permiso para mostrar botón Descargar
        can_exportar = _hp(session.get("rol"), "contratos_ingresar", "exportar")

        return render_template(
            "contrato_detalle_fragment.html",
            vista=vista,
            proveedor=proveedor,
            archivos=archivos,
            can_exportar=can_exportar,
        )
    finally:
        # nada que cerrar, get_db lo maneja Flask
        pass

@contratos_bp.route("/ver/contrato/<int:contrato_id>/full", methods=["GET"])
@require_login
def ver_contrato_full(contrato_id: int):
    """
    Vista de DETALLE en página completa para contratos.
    Reutiliza la misma extracción de datos que el fragmento,
    pero renderiza 'contrato_detalle.html'.
    """
    # Evita banners/flashes residuales
    get_flashed_messages()
    session.pop("_flashes", None)

    # Importamos helper de permisos
    from modules.security import has_permission as _hp

    def _fmt_money(x):
        try:
            return "${:,.2f}".format(float(x or 0))
        except Exception:
            return ""

    conn = get_db()
    try:
        cur = conn.cursor()
        fila = cur.execute(
            "SELECT * FROM contratos WHERE id=?",
            (contrato_id,),
        ).fetchone()
        if not fila:
            abort(404)

        # Proveedor legible
        prov = cur.execute(
            "SELECT TOP 1 nombre FROM terceros WHERE nombre = ?",
            (fila["proveedor"],),
        ).fetchone()
        proveedor = (
            prov["nombre"]
            if (prov and "nombre" in prov.keys() and prov["nombre"])
            else (fila["proveedor"] or "")
        )

        # Solicitante (NOMBRE COMPLETO)
        sol = cur.execute(
            """
            SELECT TOP 1 COALESCE(nombre_completo, username) AS nombre
            FROM usuarios
            WHERE id=?
            """,
            (fila["usuario_solicitante_id"],),
        ).fetchone()
        usuario_solicitante = sol["nombre"] if sol else ""

        # Usuario de Compras (nombre resolviendo reglas)
        usuario_compras = _resolve_usuario_compras_nombre(conn, fila)

        mapa_tipo = {
            "AMBOS": "Ambos",
            "PAGARE": "Pagaré",
            "PAGARÉ": "Pagaré",
            "POLIZA": "Póliza",
        }
        tipo_pp = mapa_tipo.get(
            (fila["tipo_rp" if "tipo_rp" in fila.keys() else "tipo_pp"] or "").upper(),
            fila["tipo_rp" if "tipo_rp" in fila.keys() else "tipo_pp"],
        )

        # helpers de Sí/No
        def _yn(b):
            return "Sí" if int(b or 0) else "No"

        # estados de aprobación
        aprobado_jef = int(_rowget(fila, "aprobado_jefe", 0) or 0) or (
            (_rowget(fila, "status_interno", "") or "") == "Aprobado"
        )
        aprobado_ger = int(_rowget(fila, "aprobado", 0) or 0)
        aprobado_gf = int(_rowget(fila, "aprob_gf", 0) or 0)

        vista = [
            ("Año", fila["anio"]),
            ("Pedido", fila["pedido"]),
            ("Proveedor", proveedor),
            ("Objeto del contrato", fila["objeto"]),
            ("Valor contrato", _fmt_money(fila["valor_contrato"])),
            ("Valor anticipo", _fmt_money(fila["valor_anticipo"])),
            ("Pagaré / Póliza", tipo_pp),
            ("Fecha de suscripción", fila["fecha_suscripcion"]),
            ("Fecha de terminación", fila["fecha_terminacion"]),
            ("Plazo (días)", fila["plazo_dias"]),
            ("Cronograma de pagos", fila["cronograma_pagos"]),
            ("Fecha entrega a Compras", fila["fecha_entrega_compras"]),
            ("Fecha firma de Gerencia", fila["fecha_firma_gerencia"]),
            ("Fecha de entrega a Finanzas (Sumilla)", fila["fecha_entrega_finanzas_sumilla"]),
            ("Fecha entrega originales a Finanzas", fila["fecha_entrega_originales_fin"]),
            ("Fechas de pago de anticipo", fila["fechas_pago_anticipo"]),
            ("Fecha de entrega de pedido", fila["fecha_entrega_pedido"]),
            ("Usuario solicitante", usuario_solicitante),
            ("Usuario de Compras", usuario_compras),
            # (OCULTAMOS 'Status interno')
            ("Observaciones", fila["observaciones"]),
            # Nuevas líneas de aprobación:
            ("Aprobación jefatura", _yn(aprobado_jef)),
            ("Aprobación gerencial", _yn(aprobado_ger)),
            ("Aprobación Gerencia Financiera (Final)", _yn(aprobado_gf)),
        ]

        # ===== Archivos PDF del contrato (mismo manejo que en fragment) =====
        _ensure_contrato_archivos_table()
        archivos = cur.execute(
            """
            SELECT id, filename, original_name, uploaded_at
            FROM contrato_archivos
            WHERE contrato_id=?
            ORDER BY id
            """,
            (contrato_id,),
        ).fetchall()

        # Permiso para mostrar botón Descargar/Exportar
        can_exportar = _hp(session.get("rol"), "contratos_ingresar", "exportar")

        return render_template(
            "contrato_detalle.html",
            vista=vista,
            proveedor=proveedor,
            archivos=archivos,
            can_exportar=can_exportar,
        )
    finally:
        pass




@contratos_bp.route("/ver/contrato/<int:contrato_id>", methods=["GET"])
@require_login
def ver_contrato(contrato_id: int):
    """
    Alias de compatibilidad: algunos templates/short URLs aún llaman a
    'contratos.ver_contrato'. Reutilizamos la misma vista del fragmento.
    """
    return ver_contrato_fragment(contrato_id)


@contratos_bp.route("/ver/garantia/<int:garantia_id>", methods=["GET"])
@require_login
@require_permission("contratos_aprobaciones", "ver")
def ver_garantia(garantia_id: int):
    _ensure_aprob_gf_columns()

    get_flashed_messages()
    session.pop("_flashes", None)

    def _fmt_money(x):
        try:
            return "${:,.2f}".format(float(x or 0))
        except:
            return ""

    conn = get_db()
    cur = conn.cursor()
    g = cur.execute("SELECT * FROM garantias WHERE id=?", (garantia_id,)).fetchone()
    if not g:
        abort(404)

    c = cur.execute(
        "SELECT TOP 1 pedido, proveedor FROM contratos WHERE id=?",
        (g["contrato_id"],),
    ).fetchone()
    pedido = c["pedido"] if c else ""
    proveedor = c["proveedor"] if c else ""

    tipo = (g["tipo"] or "").upper()
    tipo_amig = (
        "Pagaré"
        if tipo in ("PAGARE", "PAGARÉ")
        else ("Póliza" if tipo == "POLIZA" else g["tipo"])
    )

    # helpers
    def _yn(b):
        return "Sí" if int(b or 0) else "No"

    # estados de aprobación
    aprobado_jef = int(_rowget(g, "aprobado_jefe", 0) or 0) or (
        (_rowget(g, "status_interno", "") or "") == "Aprobado"
    )
    aprobado_ger = int(_rowget(g, "aprobado", 0) or 0)
    aprobado_gf = int(_rowget(g, "aprob_gf", 0) or 0)

    vista = [
        ("Contrato (pedido)", pedido),
        ("Proveedor", proveedor),
        ("Pagaré / Póliza", tipo_amig),
        ("Compañía emisora de póliza", g["compania_emisora"]),
        ("Monto de póliza", _fmt_money(g["monto_poliza"])),
        ("Vigencia (días)", g["vigencia_dias"]),
        ("Fecha de suscripción", g["fecha_suscripcion"]),
        ("Fecha de vencimiento", g["fecha_vencimiento"]),
        ("Fecha vencimiento actualizada", g["fecha_vencimiento_actual"]),
        ("Estado de garantía", g["estado"]),
        ("Fecha de renovación de póliza", g["fecha_renovacion"]),
        ("Requiere renovación", "Sí" if int(g["requiere_renovacion"] or 0) else "No"),
        # (OCULTAMOS 'Status interno')
        ("Observaciones", g["observaciones"]),
        # Nuevas líneas de aprobación:
        ("Aprobación jefatura", _yn(aprobado_jef)),
        ("Aprobación gerencial", _yn(aprobado_ger)),
        ("Aprobación Gerencia Financiera (Final)", _yn(aprobado_gf)),
    ]

    return render_template(
        "garantia_detalle.html",
        vista=vista,
        pedido=pedido,
        hide_flashes=True,
    )



# --- Toggle Aprobación GF (contrato/garantía) ---
@contratos_bp.route("/aprobacion/toggle_gf", methods=["POST"])
@require_login
@require_permission("contratos_aprobaciones", "aprobar")
def toggle_aprobacion_gf():
    payload = request.get_json(silent=True) or {}
    tipo = (payload.get("tipo") or "").strip().lower()  # "contrato" (único admitido)
    rec_id = payload.get("id")
    valor = 1 if payload.get("valor") else 0

    if tipo != "contrato":
        abort(400)
    try:
        contrato_id = int(rec_id)
    except:
        abort(400)

    _ensure_aprob_gf_columns()
    conn = get_db()
    cur = conn.cursor()
    # actualiza contrato
    cur.execute(
        "UPDATE contratos SET aprob_gf=?, actualizado_at=GETDATE() WHERE id=?",
        (valor, contrato_id),
    )
    # sincroniza todas sus garantías
    cur.execute(
        "UPDATE garantias SET aprob_gf=?, actualizado_at=GETDATE() WHERE contrato_id=?",
        (valor, contrato_id),
    )
    conn.commit()
    # ======= CORREOS: aprobación final GF =======
    try:
        c2 = get_db()
        k = c2.cursor()
        # Solo notificamos cuando cambia a 1 (aprobación final)
        if int(valor) == 1:
            c = k.execute(
                """
                SELECT c.id, c.pedido, c.proveedor, c.objeto,
                    c.usuario_solicitante_id, c.usuario_compras_id, c.usuario_compras_nombre,
                    c.aprobado_jefe_por
                FROM contratos c
                WHERE c.id=?
            """,
                (contrato_id,),
            ).fetchone()

            pedido = c["pedido"]
            proveedor = c["proveedor"]
            objeto = c["objeto"]
            solicitante_email = _lookup_email_by_user_id(c2, c["usuario_solicitante_id"])
            compras_email = _find_compras_email(
                c2, c["usuario_compras_id"], c["usuario_compras_nombre"]
            )
            jefe_email = _lookup_email_by_user_id(c2, c["aprobado_jefe_por"])
            savera_mail = _savera_email()
            gerente_fin_mail = _gerente_financiero_email()

            link_c = _link_contrato(contrato_id)

            subj_gf_ok = f"[SILI] Aprobación FINAL (Gerencia Financiera): Pedido {pedido}"
            body_gf_ok = (
                "Estimado Gerente Financiero,\n\n"
                "Se registró su APROBACIÓN FINAL del contrato con su garantía asociada.\n\n"
                f"Pedido: {pedido}\nProveedor: {proveedor}\nObjeto: {objeto}\n"
                f"Ver contrato: {link_c}\n\n"
                "— SILI"
            )
            subj_info = (
                f"[SILI] Contrato + Garantía APROBADOS por Gerencia Financiera: Pedido {pedido}"
            )
            body_info = (
                "Notificación:\n\n"
                "El contrato y su garantía recibieron APROBACIÓN FINAL por parte de Gerencia Financiera.\n\n"
                f"Pedido: {pedido}\nProveedor: {proveedor}\nObjeto: {objeto}\n"
                f"Detalle: {link_c}\n\n"
                "— SILI"
            )

            if gerente_fin_mail:
                _send_mail(gerente_fin_mail, subj_gf_ok, body_gf_ok)
            if savera_mail:
                _send_mail(savera_mail, subj_info, body_info)
            if compras_email:
                _send_mail(compras_email, subj_info, body_info)
            if solicitante_email:
                _send_mail(solicitante_email, subj_info, body_info)
            if jefe_email:
                _send_mail(jefe_email, subj_info, body_info)
    except Exception as _e:
        try:
            current_app.logger.warning(
                "Fallo correos toggle_aprobacion_gf(%s): %s", contrato_id, _e
            )
        except Exception:
            pass

    return {"ok": True, "value": valor}


# --- Toggle aprobar contrato ---
@contratos_bp.route("/aprobacion/contrato/<int:contrato_id>/toggle", methods=["POST"])
@require_login
@require_permission("contratos_aprobaciones", "aprobar")
# @require_department('Gerencia General', 'Financiero', 'General')
def toggle_aprobar_contrato(contrato_id: int):
    conn = get_db()
    cur = conn.cursor()
    row = cur.execute("SELECT aprobado FROM contratos WHERE id=?", (contrato_id,)).fetchone()
    if not row:
        abort(404)
    new_val = 0 if int(row["aprobado"]) else 1
    cur.execute(
        """
    UPDATE contratos
    SET aprobado=?, aprobado_por=?, aprobado_en=GETDATE(), actualizado_at=GETDATE()
    WHERE id=?
    """,
        (new_val, session.get("usuario_id"), contrato_id),
    )
    conn.commit()

    # === NUEVO: si quedó aprobado (=1) y ya existe garantía aprobada, avisar a GF ===
    try:
        if int(new_val) == 1:
            # ¿Existe al menos una garantía aprobada y activa?
            g = cur.execute(
                """
                SELECT TOP 1 1 AS ok
                FROM garantias
                WHERE contrato_id = ?
                AND COALESCE(disabled,0)=0
                AND COALESCE(aprobado,0)=1
            """,
                (contrato_id,),
            ).fetchone()

            if g:
                # Datos básicos para el correo
                c = cur.execute(
                    """
                    SELECT pedido, proveedor, objeto,
                        usuario_solicitante_id, usuario_compras_id, usuario_compras_nombre,
                        aprobado_jefe_por
                    FROM contratos
                    WHERE id=?
                """,
                    (contrato_id,),
                ).fetchone()

                pedido = c["pedido"]
                proveedor = c["proveedor"]
                objeto = c["objeto"]
                solicitante_email = _lookup_email_by_user_id(conn, c["usuario_solicitante_id"])
                compras_email = _find_compras_email(
                    conn, c["usuario_compras_id"], c["usuario_compras_nombre"]
                )
                jefe_email = _lookup_email_by_user_id(conn, c["aprobado_jefe_por"])
                savera_mail = _savera_email()
                gerente_fin_mail = _gerente_financiero_email()

                link_c = _link_contrato(contrato_id)

                subj_gf = f"[SILI] Pendiente aprobación FINAL GF: Contrato {pedido} con garantía aprobada"
                body_gf = (
                    "Estimado Gerente Financiero,\n\n"
                    "El contrato y su garantía ya fueron aprobados en instancias previas.\n"
                    "Se encuentra PENDIENTE su APROBACIÓN FINAL por parte de Gerencia Financiera.\n\n"
                    f"Pedido: {pedido}\nProveedor: {proveedor}\nObjeto: {objeto}\n"
                    f"Ver contrato: {link_c}\n\n"
                    "— SILI"
                )
                subj_info = f"[SILI] Contrato aprobado (falta GF): Pedido {pedido}"
                body_info = (
                    "Notificación:\n\n"
                    "El contrato quedó aprobado y existe garantía aprobada.\n"
                    "Resta la aprobación FINAL por parte de Gerencia Financiera.\n\n"
                    f"Pedido: {pedido}\nProveedor: {proveedor}\nObjeto: {objeto}\n"
                    f"Detalle: {link_c}\n\n"
                    "— SILI"
                )

                if gerente_fin_mail:
                    _send_mail(gerente_fin_mail, subj_gf, body_gf)
                if savera_mail:
                    _send_mail(savera_mail, subj_info, body_info)
                if compras_email:
                    _send_mail(compras_email, subj_info, body_info)
                if solicitante_email:
                    _send_mail(solicitante_email, subj_info, body_info)
                if jefe_email:
                    _send_mail(jefe_email, subj_info, body_info)
    except Exception as _e:
        try:
            current_app.logger.warning(
                "Fallo aviso GF en toggle_aprobar_contrato(%s): %s", contrato_id, _e
            )
        except Exception:
            pass

    flash("Contrato actualizado.", "success")
    return redirect(request.referrer or url_for("contratos.aprobacion"))


# --- Toggle aprobar garantía ---
@contratos_bp.route("/aprobacion/garantia/<int:garantia_id>/toggle", methods=["POST"])
@require_login
@require_permission("contratos_aprobaciones", "aprobar")
# @require_department('Gerencia General', 'Financiero', 'General')
def toggle_aprobar_garantia(garantia_id: int):
    conn = get_db()
    cur = conn.cursor()
    row = cur.execute("SELECT aprobado FROM garantias WHERE id=?", (garantia_id,)).fetchone()
    if not row:
        abort(404)
    new_val = 0 if int(row["aprobado"]) else 1
    cur.execute(
        """
      UPDATE garantias
      SET aprobado=?, aprobado_por=?, aprobado_en=GETDATE(), actualizado_at=GETDATE()
      WHERE id=?
    """,
        (new_val, session.get("usuario_id"), garantia_id),
    )
    conn.commit()
    # ======= CORREOS: aprobación de garantía =======
    try:
        c2 = get_db()
        k = c2.cursor()
        g = k.execute(
            """
            SELECT g.id, g.contrato_id, g.aprobado
            FROM garantias g
            WHERE g.id=?
        """,
            (garantia_id,),
        ).fetchone()

        aprobado = int(g["aprobado"] or 0)
        contrato_id = g["contrato_id"]

        # Datos del contrato
        c = k.execute(
            """
            SELECT c.pedido, c.proveedor, c.objeto,
                c.usuario_solicitante_id, c.usuario_compras_id, c.usuario_compras_nombre,
                c.aprobado_jefe_por
            FROM contratos c
            WHERE c.id=?
        """,
            (contrato_id,),
        ).fetchone()

        pedido = c["pedido"]
        proveedor = c["proveedor"]
        objeto = c["objeto"]
        solicitante_email = _lookup_email_by_user_id(c2, c["usuario_solicitante_id"])
        compras_email = _find_compras_email(
            c2, c["usuario_compras_id"], c["usuario_compras_nombre"]
        )
        jefe_email = _lookup_email_by_user_id(c2, c["aprobado_jefe_por"])
        savera_mail = _savera_email()
        gerente_fin_mail = _gerente_financiero_email()

        link_g = _link_garantia(garantia_id)

        if aprobado == 1:
            # Aprobada por Savera (o quien tenga el permiso), avisos:
            subj_sv_ok = f"[SILI] Aprobación de garantía registrada (Pedido {pedido})"
            body_sv_ok = (
                "Hola Savera,\n\n"
                "Se registró exitosamente la APROBACIÓN de la garantía asociada.\n\n"
                f"Pedido: {pedido}\nProveedor: {proveedor}\nObjeto: {objeto}\n"
                f"Ver garantía: {link_g}\n\n"
                "— SILI"
            )
            subj_info = f"[SILI] Garantía APROBADA: Pedido {pedido}"
            body_info = (
                "Notificación:\n\n"
                "La GARANTÍA asociada al contrato indicado fue APROBADA.\n\n"
                f"Pedido: {pedido}\nProveedor: {proveedor}\nObjeto: {objeto}\n"
                f"Detalle: {link_g}\n\n"
                "— SILI"
            )
            subj_gf = f"[SILI] Pendiente aprobación FINAL GF: Contrato {pedido} con garantía aprobada"
            body_gf = (
                "Estimado Gerente Financiero,\n\n"
                "El contrato y su garantía ya fueron aprobados en instancias previas.\n"
                "Se encuentra PENDIENTE su APROBACIÓN FINAL por parte de Gerencia Financiera.\n\n"
                f"Pedido: {pedido}\nProveedor: {proveedor}\nObjeto: {objeto}\n"
                f"Ver garantía: {link_g}\n\n"
                "— SILI"
            )
            if savera_mail:
                _send_mail(savera_mail, subj_sv_ok, body_sv_ok)
            if jefe_email:
                _send_mail(jefe_email, subj_info, body_info)
            if solicitante_email:
                _send_mail(solicitante_email, subj_info, body_info)
            if compras_email:
                _send_mail(compras_email, subj_info, body_info)
            if gerente_fin_mail:
                _send_mail(gerente_fin_mail, subj_gf, body_gf)
        else:
            # Se revirtió aprobación (opcional)
            subj_rev = f"[SILI] Aprobación de garantía revertida: Pedido {pedido}"
            body_rev = (
                "Notificación:\n\n"
                "La aprobación de la GARANTÍA fue revertida.\n\n"
                f"Pedido: {pedido}\nProveedor: {proveedor}\nObjeto: {objeto}\n"
                f"Detalle: {link_g}\n\n"
                "— SILI"
            )
            if savera_mail:
                _send_mail(savera_mail, subj_rev, body_rev)
            if jefe_email:
                _send_mail(jefe_email, subj_rev, body_rev)
            if solicitante_email:
                _send_mail(solicitante_email, subj_rev, body_rev)
            if compras_email:
                _send_mail(compras_email, subj_rev, body_rev)
    except Exception as _e:
        try:
            current_app.logger.warning(
                "Fallo correos toggle_aprobar_garantia(%s): %s", garantia_id, _e
            )
        except Exception:
            pass

    flash("Garantía actualizada.", "success")
    return redirect(request.referrer or url_for("contratos.aprobacion"))
