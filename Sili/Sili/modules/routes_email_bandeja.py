# modules/routes_email_bandeja.py
# -*- coding: utf-8 -*-
"""
Rutas de la Bandeja de Correos por Asignar.
Solo accesible para usuarios del departamento SISTEMAS QP.

Rutas:
    GET  /tareas/bandeja-soporte           → lista de correos POR_ASIGNAR
    POST /tareas/bandeja-soporte/<int:id>/asignar → crea tarea y asigna responsable
    POST /tareas/bandeja-soporte/<int:id>/descartar → descarta el correo sin crear tarea
"""

from __future__ import annotations

import logging
from datetime import date, datetime

from flask import jsonify, redirect, render_template, request, session, url_for, flash, Response

from modules.db import get_db, get_config_value
from modules.security import require_login, get_user
from modules.email_to_task.email_inbox_service import send_assignment_emails
from modules.email_to_task.graph_fetcher import fetch_attachment_content, fetch_attachments_list

_log = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────
# Nombre del departamento con acceso a la bandeja
# ────────────────────────────────────────────────────────────────────
DEPT_PERMITIDO = "SISTEMAS QP"


def _es_sistemas_qp(user: dict) -> bool:
    """Verifica si el usuario pertenece al departamento SISTEMAS QP."""
    dep_id = user.get("departamento_id")
    if not dep_id:
        return False
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT nombre FROM departamentos WHERE id = ?", (dep_id,)
        ).fetchone()
        if row:
            return row["nombre"].strip().upper() == DEPT_PERMITIDO
    except Exception as exc:
        _log.warning("[bandeja] Error verificando departamento: %s", exc)
    return False


PAGE_SIZE = 15


def _obtener_bandeja(estado: str = "POR_ASIGNAR", pagina: int = 1) -> tuple[list[dict], int]:
    """
    Devuelve (correos_pagina, total_registros).
    pagina es 1-based.
    """
    conn   = get_db()
    offset = (pagina - 1) * PAGE_SIZE

    total_row = conn.execute(
        "SELECT COUNT(*) AS c FROM email_tickets_inbox WHERE estado = ?", (estado,)
    ).fetchone()
    total = total_row["c"] if total_row else 0

    rows = conn.execute(
        """
        SELECT
            b.id, b.message_id, b.from_email, b.from_name, b.subject,
            b.body_text, b.received_at, b.fecha_registro,
            b.estado, b.tarea_id, b.confirmacion_enviada,
            b.usuario_id_match,
            COALESCE(u.nombre_completo, u.username) AS solicitante_nombre
        FROM email_tickets_inbox b
        LEFT JOIN usuarios u ON u.id = b.usuario_id_match
        WHERE b.estado = ?
        ORDER BY b.received_at ASC
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
        """,
        (estado, offset, PAGE_SIZE)
    ).fetchall()
    return [dict(r) for r in rows], total


def _obtener_usuarios_para_asignar() -> list[dict]:
    """Usuarios activos del departamento SISTEMAS QP para asignar como responsable."""
    conn = get_db()
    rows = conn.execute(
        """
        SELECT u.id, COALESCE(u.nombre_completo, u.username) AS nombre, d.nombre AS departamento
        FROM usuarios u
        INNER JOIN departamentos d ON d.id = u.departamento_id
        WHERE u.disabled = 0
          AND UPPER(d.nombre) = 'SISTEMAS QP'
        ORDER BY u.nombre_completo, u.username
        """
    ).fetchall()
    return [dict(r) for r in rows]


def _crear_tarea_desde_inbox(inbox_id: int, responsable_id: int, asignado_por_id: int) -> int:
    """
    Crea una tarea formal a partir de un registro de email_tickets_inbox.
    Devuelve el nuevo tarea_id.
    """
    conn = get_db()

    inbox = conn.execute(
        "SELECT * FROM email_tickets_inbox WHERE id = ?", (inbox_id,)
    ).fetchone()

    if not inbox:
        raise ValueError(f"inbox_id={inbox_id} no encontrado")

    inbox = dict(inbox)

    titulo      = inbox["subject"][:300]
    descripcion = (
        f"Solicitud recibida por correo de: {inbox['from_name'] or inbox['from_email']}\n"
        f"Correo: {inbox['from_email']}\n\n"
        f"{inbox['body_text'] or ''}"
    )

    # Fecha inicio = fecha en que llegó el correo (o hoy si no está disponible)
    received_at = inbox.get("received_at")
    if received_at:
        fecha_inicio = received_at.date().isoformat() if hasattr(received_at, "date") else str(received_at)[:10]
    else:
        fecha_inicio = date.today().isoformat()

    # Obtener tipo_tarea_id: buscar "Soporte" en param_values (group_id=4945), si no el primero
    tipo_row = conn.execute(
        """
        SELECT TOP 1 id FROM param_values
        WHERE group_id = 4945
        ORDER BY CASE WHEN UPPER(nombre) LIKE '%SOPORTE%' THEN 0 ELSE 1 END, orden ASC
        """
    ).fetchone()
    tipo_id = tipo_row[0] if tipo_row else None

    # empresa_id: primera empresa activa
    emp_row = conn.execute(
        "SELECT TOP 1 id FROM empresas WHERE activo = 1 ORDER BY id"
    ).fetchone()
    empresa_id = emp_row[0] if emp_row else None

    solicitante_id = inbox.get("usuario_id_match")

    # Insertar tarea
    tarea_row = conn.execute(
        """
        INSERT INTO tareas (
            titulo, descripcion, estado,
            fecha_creacion, fecha_inicio, fecha_compromiso, fecha_fin,
            usuario_id, creador_id, solicitante_id,
            notificado, tipo_tarea_id, empresa_id
        )
        OUTPUT INSERTED.id
        VALUES (?, ?, 'Por iniciar', ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
        """,
        (
            titulo, descripcion,
            datetime.now(), fecha_inicio, fecha_inicio, None,
            responsable_id,        # usuario_id = responsable asignado
            asignado_por_id,       # creador = quien asignó desde la bandeja
            solicitante_id,
            tipo_id, empresa_id,
        )
    ).fetchone()
    tarea_id = tarea_row[0]

    # Insertar en tabla de responsables
    conn.execute(
        "INSERT INTO tarea_responsables (tarea_id, usuario_id) VALUES (?, ?)",
        (tarea_id, responsable_id)
    )

    # Actualizar inbox
    conn.execute(
        """
        UPDATE email_tickets_inbox
        SET estado = 'ASIGNADA',
            tarea_id = ?,
            asignado_por_id = ?,
            fecha_asignacion = ?
        WHERE id = ?
        """,
        (tarea_id, asignado_por_id, datetime.now(), inbox_id)
    )

    conn.commit()

    _log.info(
        "[bandeja] Tarea #%d creada desde inbox_id=%d por usuario_id=%d",
        tarea_id, inbox_id, asignado_por_id
    )

    return tarea_id


# ────────────────────────────────────────────────────────────────────
# Registro de rutas
# ────────────────────────────────────────────────────────────────────

def register_bandeja_routes(app):

    @app.route("/tareas/bandeja-soporte/diagnostico")
    @require_login
    def bandeja_diagnostico():
        user = get_user()
        dep_id = user.get("departamento_id")
        dep_nombre = None
        try:
            conn = get_db()
            row = conn.execute("SELECT nombre FROM departamentos WHERE id = ?", (dep_id,)).fetchone()
            dep_nombre = row["nombre"] if row else "NO ENCONTRADO"
        except Exception as exc:
            dep_nombre = f"ERROR: {exc}"
        return jsonify({
            "usuario": user.get("username"),
            "departamento_id": dep_id,
            "departamento_nombre": dep_nombre,
            "es_sistemas_qp": _es_sistemas_qp(user),
            "DEPT_PERMITIDO": DEPT_PERMITIDO,
        })

    @app.route("/tareas/bandeja-soporte")
    @require_login
    def bandeja_soporte():
        user = get_user()
        if not _es_sistemas_qp(user):
            flash("No tienes permisos para acceder a la Bandeja de Soporte.", "danger")
            return redirect(url_for("listar_tareas"))

        estado = request.args.get("estado", "POR_ASIGNAR")
        if estado not in ("POR_ASIGNAR", "ASIGNADA", "DESCARTADA"):
            estado = "POR_ASIGNAR"

        try:
            pagina = max(1, int(request.args.get("p", 1)))
        except (ValueError, TypeError):
            pagina = 1

        _bandeja_result = _obtener_bandeja(estado, pagina)
        correos        = _bandeja_result[0]
        total          = _bandeja_result[1]
        usuarios       = _obtener_usuarios_para_asignar()

        import math
        total_paginas = max(1, math.ceil(total / PAGE_SIZE))
        pagina        = min(pagina, total_paginas)

        # Contar para los badges del tab (totales, no de la página)
        conn = get_db()
        conteos = {}
        for st in ("POR_ASIGNAR", "ASIGNADA", "DESCARTADA"):
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM email_tickets_inbox WHERE estado = ?", (st,)
            ).fetchone()
            conteos[st] = row["c"] if row else 0

        # Contar respuestas por ticket (para badge en "Ver detalle")
        # Protegido: la tabla puede no existir si aún no se ejecutó el script SQL
        inbox_ids = [c["id"] for c in correos]
        reply_counts: dict[int, int] = {}
        if inbox_ids:
            try:
                placeholders = ",".join("?" * len(inbox_ids))
                rows_rc = conn.execute(
                    f"SELECT inbox_id, COUNT(*) AS c FROM email_ticket_replies "
                    f"WHERE inbox_id IN ({placeholders}) GROUP BY inbox_id",
                    inbox_ids
                ).fetchall()
                reply_counts = {r["inbox_id"]: r["c"] for r in rows_rc}
            except Exception:
                pass  # Tabla aún no creada — ignorar hasta que se ejecute el script SQL

        return render_template(
            "bandeja_soporte.html",
            correos=correos,
            usuarios=usuarios,
            estado_activo=estado,
            conteos=conteos,
            reply_counts=reply_counts,
            user=user,
            pagina=pagina,
            total_paginas=total_paginas,
            total=total,
            page_size=PAGE_SIZE,
        )

    @app.route("/tareas/bandeja-soporte/<int:inbox_id>/asignar", methods=["POST"])
    @require_login
    def bandeja_asignar(inbox_id: int):
        user = get_user()
        if not _es_sistemas_qp(user):
            return jsonify({"ok": False, "error": "Sin permisos"}), 403

        responsable_id = request.form.get("responsable_id", "").strip()
        if not responsable_id or not responsable_id.isdigit():
            flash("Debes seleccionar un responsable.", "danger")
            return redirect(url_for("bandeja_soporte"))

        try:
            _log.info("[bandeja] Asignando inbox_id=%d a responsable_id=%s por usuario_id=%s",
                      inbox_id, responsable_id, user["id"])
            tarea_id = _crear_tarea_desde_inbox(
                inbox_id,
                int(responsable_id),
                user["id"]
            )
            _log.info("[bandeja] Tarea #%d creada desde inbox_id=%d", tarea_id, inbox_id)

            # Obtener datos para correos de notificación
            try:
                conn = get_db()
                inbox_row = conn.execute(
                    "SELECT from_email, from_name, subject FROM email_tickets_inbox WHERE id = ?",
                    (inbox_id,)
                ).fetchone()
                tec_row = conn.execute(
                    "SELECT COALESCE(nombre_completo, username) AS nombre, email FROM usuarios WHERE id = ?",
                    (int(responsable_id),)
                ).fetchone()
                if inbox_row and tec_row:
                    send_assignment_emails(
                        inbox_id=inbox_id,
                        tarea_id=tarea_id,
                        from_email=inbox_row["from_email"],
                        from_name=inbox_row["from_name"],
                        subject=inbox_row["subject"],
                        tecnico_email=tec_row["email"] or "",
                        tecnico_nombre=tec_row["nombre"] or "",
                    )
            except Exception as mail_exc:
                _log.warning("[bandeja] No se pudieron enviar correos de asignación: %s", mail_exc)

            flash(f"Tarea #{tarea_id} creada y asignada correctamente.", "success")
        except ValueError as exc:
            _log.warning("[bandeja] ValueError inbox_id=%d: %s", inbox_id, exc)
            flash(f"Error: {exc}", "danger")
        except Exception as exc:
            _log.exception("[bandeja] Error creando tarea desde inbox_id=%d: %s", inbox_id, exc)
            flash(f"Error al crear la tarea: {exc}", "danger")

        return redirect(url_for("bandeja_soporte"))

    @app.route("/tareas/bandeja-soporte/<int:inbox_id>/descartar", methods=["POST"])
    @require_login
    def bandeja_descartar(inbox_id: int):
        user = get_user()
        if not _es_sistemas_qp(user):
            return jsonify({"ok": False, "error": "Sin permisos"}), 403

        motivo = request.form.get("motivo", "").strip()[:500]

        try:
            conn = get_db()
            conn.execute(
                """
                UPDATE email_tickets_inbox
                SET estado = 'DESCARTADA',
                    asignado_por_id = ?,
                    fecha_asignacion = ?
                WHERE id = ?
                """,
                (user["id"], datetime.now(), inbox_id)
            )
            conn.commit()
            flash("Correo descartado.", "info")
        except Exception as exc:
            _log.error("[bandeja] Error descartando inbox_id=%d: %s", inbox_id, exc)
            flash("Error al descartar el correo.", "danger")

        return redirect(url_for("bandeja_soporte"))

    # ── Renderizado HTML del cuerpo del correo ──────────────────────
    @app.route("/tareas/bandeja-soporte/<int:inbox_id>/body")
    @require_login
    def bandeja_body(inbox_id: int):
        import re as _re
        import html as _html_mod

        if not _es_sistemas_qp(get_user()):
            return "", 403

        conn = get_db()
        row = conn.execute(
            "SELECT message_id, body_html, body_text FROM email_tickets_inbox WHERE id = ?",
            (inbox_id,)
        ).fetchone()
        if not row:
            return "<p>No encontrado.</p>", 404

        body_html  = (row["body_html"] or "").strip()
        body_text  = row["body_text"] or ""
        message_id = row["message_id"] or ""

        if body_html:
            # Sanitizar HTML para cumplir CSP estricto sin excepciones:
            # eliminar bloques <style>, <script>, atributos style= y on*=
            body_html = _re.sub(r"<style[^>]*>.*?</style>", "",
                                body_html, flags=_re.DOTALL | _re.IGNORECASE)
            body_html = _re.sub(r"<script[^>]*>.*?</script>", "",
                                body_html, flags=_re.DOTALL | _re.IGNORECASE)
            body_html = _re.sub(r"""\s+style\s*=\s*(?:"[^"]*"|'[^']*')""", "",
                                body_html, flags=_re.IGNORECASE)
            body_html = _re.sub(r"""\s+on\w+\s*=\s*(?:"[^"]*"|'[^']*')""", "",
                                body_html, flags=_re.IGNORECASE)

            # Resolver imágenes inline CID → proxy URL
            if "cid:" in body_html and message_id:
                try:
                    attachments = fetch_attachments_list(message_id)
                    for att in attachments:
                        if att.get("is_inline") and att.get("content_id"):
                            proxy_url = url_for(
                                "bandeja_img",
                                message_id=message_id,
                                attachment_id=att["attachment_id"],
                                _external=False,
                            )
                            cid = att["content_id"].strip("<>")
                            body_html = body_html.replace(f"cid:{cid}", proxy_url)
                except Exception as exc:
                    _log.debug("[bandeja] No se pudieron resolver CIDs: %s", exc)

            content = body_html
        else:
            # Sin HTML guardado: mostrar texto plano con saltos de línea preservados
            content = "<pre class='email-plain'>" + _html_mod.escape(body_text) + "</pre>"

        # Hoja de estilos externa → cumple style-src 'self' sin inline styles
        page = (
            "<!DOCTYPE html><html lang='es'><head>"
            "<meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<link rel='stylesheet' href='/static/css/bandeja/email_body.css'>"
            f"</head><body class='email-body'>{content}</body></html>"
        )
        return Response(page, mimetype="text/html; charset=utf-8")

    # ── API: hilo de respuestas de un ticket ────────────────────────
    @app.route("/tareas/bandeja-soporte/<int:inbox_id>/replies.json")
    @require_login
    def bandeja_replies(inbox_id: int):
        if not _es_sistemas_qp(get_user()):
            return jsonify({"ok": False}), 403
        conn = get_db()
        try:
            rows = conn.execute(
                """
                SELECT id, from_email, from_name, subject,
                       body_text, received_at, has_attachments
                FROM email_ticket_replies
                WHERE inbox_id = ?
                ORDER BY received_at ASC
                """,
                (inbox_id,)
            ).fetchall()
        except Exception:
            return jsonify([])  # Tabla aún no creada

        def fmt_dt(v):
            if v is None:
                return ""
            if hasattr(v, "strftime"):
                return v.strftime("%d/%m/%Y %H:%M")
            return str(v)

        return jsonify([
            {
                "id":              r["id"],
                "from_email":      r["from_email"],
                "from_name":       r["from_name"] or r["from_email"],
                "subject":         r["subject"] or "",
                "body_text":       r["body_text"] or "",
                "has_attachments": bool(r["has_attachments"]),
                "received_at":     fmt_dt(r["received_at"]),
            }
            for r in rows
        ])

    # ── API: lista de adjuntos de un mensaje ────────────────────────
    @app.route("/tareas/bandeja-soporte/attachments/<path:message_id>.json")
    @require_login
    def bandeja_attachments_list(message_id: str):
        if not _es_sistemas_qp(get_user()):
            return jsonify({"ok": False}), 403
        try:
            items = fetch_attachments_list(message_id)
        except Exception as exc:
            _log.error("[bandeja] Error listando adjuntos: %s", exc)
            items = []
        return jsonify(items)

    # ── Proxy: descarga/visualización de adjunto (imagen u otro) ───
    @app.route("/tareas/bandeja-soporte/img/<path:message_id>/<attachment_id>")
    @require_login
    def bandeja_img(message_id: str, attachment_id: str):
        if not _es_sistemas_qp(get_user()):
            return "", 403
        try:
            result = fetch_attachment_content(message_id, attachment_id)
            if not result:
                return "", 404
            return Response(
                result["content_bytes"],
                mimetype=result["content_type"],
                headers={"Content-Disposition": f'inline; filename="{result["name"]}"'},
            )
        except Exception as exc:
            _log.error("[bandeja] Error sirviendo adjunto: %s", exc)
            return "", 500
