# modules/scheduler/scheduler_services.py
# ==========================================================
# Lógica de negocio del scheduler.
# Conserva planificación, dispatcher, overdue, reportes,
# OM y expiración de gastos.
# ==========================================================

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, date
from typing import Optional

from flask import current_app, render_template_string

from modules.config import DB_PATH
from modules.routes_planilla_mensual import ensure_schema
from modules import routes_gatos_mail_notify as mail
from .scheduler_queries import (
    
    SQL_SELECT_TASKS_FOR_USER_BY_DATE,
    SQL_SELECT_PLAN_USERS_HOY,
    SQL_SELECT_NOTIFY_PENDING_IDS,
    SQL_SELECT_NOTIFY_ROW,
    SQL_SELECT_OVERDUE_TASKS,
    SQL_SELECT_DAILY_REPORT_TASKS,
    SQL_SELECT_ADMIN_EMAILS,
    SQL_SELECT_OM_CANDIDATOS,
    SQL_SELECT_GASTOS_WARN,
    SQL_SELECT_GASTOS_EXPIRE,
)


from .scheduler_repository import (
    _get_servicio_cliente_ids,
    get_db_standalone,
    ensure_notify_schema,
    ensure_gastos_expiry_schema,
    ensure_om_notification_schema,
    get_ultimo_jefe_activo,
    _get_username,
    _get_user_contact,
    _get_ultimo_jefe_id,
    guess_gerente_area,
    _get_gerente_general_ids,
    _get_servicio_cliente_ids,
    _sql_debug_counts,
)
from .scheduler_notifications import (
    ensure_core_templates,
    ensure_gasto_templates,
    ensure_om_templates,
    _send_email,
    _send_inapp,
    _send_slack,
    _enqueue_om_notification,
)
from .scheduler_security import (
    _log,
    _format_sql_for_log,
    _exec_retry,
    _is_quiet,
    _next_5min_sqlite,
    _now_str,
)
from .scheduler_constants import (
    CANAL_EMAIL,
    CANAL_INAPP,
    CANAL_SLACK,
    TIPO_HOY,
    TIPO_OM_D4,
    TIPO_OM_D5,
    TIPO_OM_D9,
    TIPO_OM_D10,
    TPL_TAREA_HOY,
    TPL_OM_SPONSOR_D4,
    TPL_OM_JEFE_D5,
    TPL_OM_SPONSOR_JEFE_D9,
    TPL_OM_GG_D10,
)

def _get_sponsors_om(conn, reclamo_id: int):
    cur = conn.cursor()
    cur.execute("""
        SELECT
            u.id,
            COALESCE(u.nombre_completo, u.username) AS nombre,
            u.username
        FROM reclamos r
        JOIN param_values pv
          ON pv.parent_id = r.proceso_id
        JOIN param_groups pg
          ON pg.id = pv.group_id
        JOIN usuarios u
          ON LTRIM(RTRIM(u.identificacion)) = LTRIM(RTRIM(pv.nombre))
        WHERE r.id = ?
          AND pg.nombre = 'RECL_PROCESO_SPONSOR'
          AND COALESCE(pv.activo, 1) = 1
          AND UPPER(LTRIM(RTRIM(COALESCE(pv.valor, '')))) IN ('PRINCIPAL', 'BACKUP')
          AND COALESCE(u.disabled, 0) = 0
        GROUP BY
            u.id,
            COALESCE(u.nombre_completo, u.username),
            u.username
        ORDER BY u.id
    """, (reclamo_id,))

    return [dict(r) for r in cur.fetchall()]
def _tareas_para_usuario_en_fecha(conn, user_id: int, fecha_iso: str):
    params = (fecha_iso, fecha_iso, fecha_iso, user_id)

    _log("info", "SQL tareas_dia:\n%s", _format_sql_for_log(SQL_SELECT_TASKS_FOR_USER_BY_DATE, params))
    rows = conn.execute(SQL_SELECT_TASKS_FOR_USER_BY_DATE, params).fetchall()
    _log("info", "tareas_dia -> %d filas. Ejemplos: %s",
         len(rows), [(r["id"], r["nombre"]) for r in rows[:5]])

    return [
        {
            "id": r["id"],
            "tarea": r["nombre"],
            "nombre": r["nombre"],
            "frecuencia": r["frecuencia"],
            "departamento": r["departamento"],
            "responsable": r["responsable"],
            "hecha": bool(r["hecha"]),
        } for r in rows
    ]


def auto_close_expired_tasks():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        cur.execute("""
            SELECT COUNT(*) FROM tareas
            WHERE estado NOT IN ('Terminado', 'Cerrado por sistema')
              AND fecha_fin IS NOT NULL
              AND fecha_fin < ?
        """, (ahora,))
        count = cur.fetchone()[0]

        if count > 0:
            cur.execute("""
                UPDATE tareas
                SET estado = 'Terminado',
                    fecha_cierre_real = COALESCE(fecha_cierre_real, ?)
                WHERE estado NOT IN ('Terminado', 'Cerrado por sistema')
                  AND fecha_fin IS NOT NULL
                  AND fecha_fin < ?
            """, (ahora, ahora))

            conn.commit()
            _log("info", "Scheduler: Se cerraron automáticamente %d tareas vencidas.", count)
    except Exception as e:
        _log("error", "Scheduler: Error en auto_close_expired_tasks -> %s", e)
    finally:
        conn.close()


def plan_notifications():
    conn = get_db_standalone()
    try:
        #ensure_schema(conn)
        #ensure_notify_schema(conn)
        #ensure_core_templates(conn)

        cur = conn.cursor()
        today = date.today().isoformat()

        _log("info", "Planificador: revisando tareas para HOY (%s)…", today)
        _log("debug", "SQL usuarios_hoy:\n%s", SQL_SELECT_PLAN_USERS_HOY)
        usuarios_hoy = cur.execute(SQL_SELECT_PLAN_USERS_HOY).fetchall()

        inserted = 0
        sched = _next_5min_sqlite()

        for u in usuarios_hoy:
            base_ctx = {
                "usuario": u["username"],
                "fecha": today,
                "app_url": current_app.config.get("APP_URL", "")
            }
            payload = json.dumps(base_ctx)

            for canal in (CANAL_INAPP, CANAL_EMAIL):
                _exec_retry(cur, f"""
                    INSERT OR IGNORE INTO notify_queue
                        (user_id, tipo, fecha_obj, canal, template_key, payload_json, scheduled_at, estado)
                    VALUES (?,?,?,?,?,?, {sched}, 'pending')
                """, (u["user_id"], TIPO_HOY, today, canal, TPL_TAREA_HOY, payload))
                inserted += (cur.rowcount or 0)

        conn.commit()
        _log("info", "Planificador: usuarios HOY planificados -> %d", inserted)

    except Exception as e:
        _log("error", "Planificador: fallo -> %s", e)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def dispatch_notifications():
    c0 = get_db_standalone()
    try:
        _log("debug", "SQL queue_ids:\n%s", SQL_SELECT_NOTIFY_PENDING_IDS)
        ids = [r["id"] for r in c0.execute(SQL_SELECT_NOTIFY_PENDING_IDS).fetchall()]
    finally:
        c0.close()

    if not ids:
        _log("info", "Dispatcher: no hay notificaciones pendientes.")
        return

    _log("info", "Dispatcher: procesando %d notificaciones…", len(ids))

    def _money_fmt(v) -> str:
        try:
            n = float(v or 0.0)
        except Exception:
            n = 0.0
        s = f"{n:,.2f}"
        return s.replace(",", "X").replace(".", ",").replace("X", ".")

    def _table_exists(conn, name: str) -> bool:
        try:
            r = conn.execute(
                "SELECT top 1 1 FROM sqlite_master WHERE type='table' AND name=? ",
                (name,)
            ).fetchone()
            return bool(r)
        except Exception:
            return False

    def _cols(conn, table: str):
        try:
            return [r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        except Exception:
            return []

    def _fetch_gasto_info(conn, gid: int) -> dict:
        out = {}

        if not _table_exists(conn, "gastos_tarjeta"):
            return out

        gcols = _cols(conn, "gastos_tarjeta")

        fecha_ok = "fecha" in gcols
        motivo_ok = "motivo" in gcols
        total_ok = "total_con_iva" in gcols
        prov_id_ok = "proveedor_id" in gcols

        join_terceros = ""
        proveedor_select = "'' AS proveedor"
        if _table_exists(conn, "terceros") and prov_id_ok:
            proveedor_select = "COALESCE(t.nombre,'') AS proveedor"
            join_terceros = (
                "LEFT JOIN terceros t "
                "ON t.id = g.proveedor_id "
                "AND t.tipo='P' "
                "AND COALESCE(t.activo,1)=1"
            )

        select_parts = ["g.id AS gid"]

        if fecha_ok:
            select_parts.append("g.fecha AS fecha")
        if motivo_ok:
            select_parts.append("g.motivo AS motivo")
        if total_ok:
            select_parts.append("g.total_con_iva AS total_con_iva")

        if _table_exists(conn, "usuarios"):
            select_parts.append("u.username AS creador")
            join_users = "LEFT JOIN usuarios u ON u.id = g.usuario_id"
        else:
            select_parts.append("'' AS creador")
            join_users = ""

        select_parts.append(proveedor_select)

        sql = f"""
            SELECT top 1 {", ".join(select_parts)}
              FROM gastos_tarjeta g
              {join_users}
              {join_terceros}
             WHERE g.id=?
         """

        try:
            row = conn.execute(sql, (int(gid),)).fetchone()
            if not row:
                return out
            d = dict(row)
        except Exception:
            return out

        if fecha_ok:
            out["fecha_gasto"] = str(d.get("fecha") or "")
        if motivo_ok:
            out["motivo"] = str(d.get("motivo") or "")
        if total_ok:
            out["total_con_iva"] = d.get("total_con_iva")
        out["proveedor"] = str(d.get("proveedor") or "")
        out["creador"] = str(d.get("creador") or "")
        return out

    def _fmt_fecha_ddmmyyyy_local(fecha_str: str) -> str:
        f = (fecha_str or "").strip()
        try:
            if len(f) >= 10 and f[4] == "-" and f[7] == "-":
                return f"{f[8:10]}/{f[5:7]}/{f[0:4]}"
        except Exception:
            pass
        return f

    for nid in ids:
        conn = get_db_standalone()
        try:
            cur = conn.cursor()

            _exec_retry(cur, """
                UPDATE notify_queue
                   SET estado='sending', error_msg=NULL
                 WHERE id=?
                   AND estado='pending'
            """, (nid,))
            conn.commit()
            if (cur.rowcount or 0) == 0:
                conn.close()
                continue

            _log("debug", "SQL queue_row:\n%s", _format_sql_for_log(SQL_SELECT_NOTIFY_ROW, (nid,)))
            r0 = conn.execute(SQL_SELECT_NOTIFY_ROW, (nid,)).fetchone()
            if not r0:
                _exec_retry(cur, "UPDATE notify_queue SET estado='skipped', error_msg=? WHERE id=?", ("Fila no encontrada", nid))
                conn.commit()
                conn.close()
                continue

            r = dict(r0)
            payload = json.loads(r.get("payload_json") or "{}")
            try:
                payload.setdefault("comentario", (r.get("comentario") or "").strip())
            except Exception:
                payload.setdefault("comentario", "")

            if r.get("tipo") == TIPO_HOY:
                from datetime import date as _date
                fecha_iso = r.get("fecha_obj") or _date.today().isoformat()
                tareas_hoy = _tareas_para_usuario_en_fecha(conn, r["user_id"], fecha_iso)
                payload.update({
                    "usuario": r["username"],
                    "fecha": fecha_iso,
                    "tareas_hoy": tareas_hoy,
                    "tareas_hoy_len": len(tareas_hoy),
                    "app_url": payload.get("app_url") or current_app.config.get("APP_URL", ""),
                })
                _log("debug", "dispatch 'hoy': user_id=%s usuario=%s fecha=%s tareas_hoy_len=%s",
                     r["user_id"], r["username"], fecha_iso, len(tareas_hoy))
            else:
                from datetime import date as _date
                payload.setdefault("usuario", r["username"])
                payload.setdefault("fecha", r.get("fecha_obj") or _date.today().isoformat())

                base = (current_app.config.get("PUBLIC_BASE_URL")
                        or current_app.config.get("APP_URL")
                        or "").rstrip("/")
                payload.setdefault("app_url", base)

                is_gasto = (str(r.get("tipo") or "").startswith("gasto_")
                            or str(r.get("template_key") or "").startswith("gasto_"))
                if is_gasto:
                    gid = payload.get("gasto_id") or r.get("gasto_id")
                    try:
                        gid_int = int(gid) if gid is not None else None
                    except Exception:
                        gid_int = None

                    if gid_int is not None:
                        info = _fetch_gasto_info(conn, gid_int)

                        payload.setdefault("gasto_id", gid_int)
                        payload.setdefault("proveedor", info.get("proveedor", ""))
                        payload.setdefault("motivo", info.get("motivo", ""))
                        payload.setdefault("creador", info.get("creador", ""))

                        if info.get("fecha_gasto"):
                            payload["fecha"] = _fmt_fecha_ddmmyyyy_local(info.get("fecha_gasto", ""))

                        if "total_con_iva" not in payload or payload.get("total_con_iva") in (None, ""):
                            if "total_con_iva" in info:
                                payload["total_con_iva"] = info.get("total_con_iva")
                        payload.setdefault("total_con_iva_fmt", _money_fmt(payload.get("total_con_iva")))

                        if base:
                            payload.setdefault("gasto_url", f"{base}/reembolsos/gastos/{gid_int}/ver")
                        else:
                            payload.setdefault("gasto_url", f"/reembolsos/gastos/{gid_int}/ver")
                    else:
                        payload.setdefault("proveedor", "")
                        payload.setdefault("motivo", "")
                        payload.setdefault("creador", "")
                        payload.setdefault("total_con_iva_fmt", _money_fmt(0))
                        payload.setdefault("gasto_url", payload.get("app_url") or "")

            if not r.get("subject") or not r.get("html"):
                _exec_retry(cur, """
                    UPDATE notify_queue
                       SET estado='error',
                           error_msg=?,
                           sent_at = GETDATE()

                     WHERE id=?
                """, (f"Plantilla inexistente o incompleta: {r.get('template_key')}", nid))
                conn.commit()
                conn.close()
                continue

            with current_app.test_request_context("/"):
                subject = render_template_string(r["subject"], **payload)
                html = render_template_string(r["html"], **payload)
                text = render_template_string(r["text"], **payload) if r.get("text") else None

            if _is_quiet(datetime.now().time(), r.get("quiet_start"), r.get("quiet_end")):
                _exec_retry(cur, "UPDATE notify_queue SET estado='skipped', error_msg=NULL WHERE id=?", (nid,))
                conn.commit()
                conn.close()
                continue

            ok = False

            if r["canal"] == CANAL_EMAIL and r.get("email_on") and r.get("email"):
                _send_email(r["email"], subject, html, text)
                ok = True
            elif r["canal"] == CANAL_INAPP and r.get("inapp_on"):
                _send_inapp(subject, text or subject, r["user_id"])
                ok = True
            elif r["canal"] == CANAL_SLACK and r.get("slack_on") and r.get("slack_webhook"):
                _send_slack(r["slack_webhook"], text or subject)
                ok = True

            if ok:
                _exec_retry(cur, """
                    UPDATE notify_queue
                       SET estado='sent',
                           error_msg=NULL,
                           
                            sent_at = GETDATE()

                     WHERE id=?
                """, (nid,))
            else:
                _exec_retry(cur, """
                    UPDATE notify_queue
                    SET estado = 'skipped',
                        error_msg = NULL,
                        sent_at = GETDATE()
                    WHERE id = ?
                """, (nid,))

            conn.commit()

        except Exception as e:
            try:
                _exec_retry(conn.cursor(), """
                    UPDATE notify_queue
                       SET estado='error',
                           error_msg=?,
                           
                           sent_at = GETDATE()

                     WHERE id=?
                """, (str(e), nid))
                conn.commit()
            except Exception:
                pass
            _log("error", "Dispatcher: error id=%s -> %s", nid, e)
        finally:
            try:
                conn.close()
            except Exception:
                pass


def notify_overdue():
    conn = get_db_standalone()
    try:
        ensure_notify_schema(conn)
        cur = conn.cursor()

        cur.execute(SQL_SELECT_OVERDUE_TASKS)
        tasks = cur.fetchall()
        if not tasks:
            _log("info", "Overdue: 0 tareas.")
            return

        is_row = (len(tasks) > 0 and hasattr(tasks[0], "keys"))

        for t in tasks:
            if is_row:
                user_email = t.get("user_email") if hasattr(t, "get") else t["user_email"]
                username = t.get("username") if hasattr(t, "get") else t["username"]
                tid = t.get("id") if hasattr(t, "get") else t["id"]
                titulo = t.get("titulo") if hasattr(t, "get") else t["titulo"]
                fecha_fin = t.get("fecha_fin") if hasattr(t, "get") else t["fecha_fin"]
            else:
                tid = t[0]
                titulo = t[1]
                fecha_fin = t[2]
                username = t[6]
                user_email = t[7]

            if user_email:
                try:
                    _send_email(
                        user_email,
                        f"Tarea pendiente: {titulo}",
                        f"La tarea <b>{titulo}</b> (usuario {username}) venció el {fecha_fin} y no ha sido cerrada.",
                        None
                    )
                except Exception as e:
                    _log("error", "Overdue: enviar correo tarea_id=%s -> %s", tid, e)
                    continue

            _exec_retry(cur, "UPDATE tareas SET notificado=1, estado='Atrasada' WHERE id=?", (tid,))
        conn.commit()
        _log("info", "Overdue: marcadas %d.", len(tasks))
    finally:
        try:
            conn.close()
        except Exception:
            pass


def send_daily_report():
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_db_standalone()
    try:
        cur = conn.cursor()
        cur.execute(SQL_SELECT_DAILY_REPORT_TASKS, (today,))
        rows = cur.fetchall()

        cur2 = conn.cursor()
        cur2.execute(SQL_SELECT_ADMIN_EMAILS)
        admin_emails = [r["email"] for r in cur2.fetchall() if r["email"]]
        if not admin_emails:
            _log("warning", "DailyReport: no hay admin emails.")
            return

        lines = ["📅 Tareas registradas hoy"]
        if rows:
            for r in rows:
                lines += [
                    "",
                    f"📝 ID {r['id']}: {r['titulo']}",
                    f"📄 {r['descripcion'] or 'Sin descripción'}",
                    f"🚦 Estado: {r['estado']}",
                    f"📅 Creación: {r['fecha_creacion']}",
                    f"⏳ Inicio: {r['fecha_inicio'] or '—'}",
                    f"✅ Fin: {r['fecha_fin'] or '—'}",
                    f"👤 Usuario: {r['usuario']}",
                ]
        else:
            lines += ["", "No se registraron tareas hoy."]

        try:
            _send_email(
                admin_emails[0],
                f"Reporte de tareas del {today}",
                "<pre>" + ("\n".join(lines)) + "</pre>",
                "\n".join(lines)
            )
            _log("info", "DailyReport: enviado a %s", admin_emails[0])
        except Exception as e:
            _log("error", "DailyReport: enviar -> %s", e)

    finally:
        try:
            conn.close()
        except Exception:
            pass


def _sent_today(ts: str | None, today_iso: str) -> bool:
    v = (ts or "").strip()
    if not v:
        return False
    return v[:10] == today_iso



def process_om_notifications(conn):
    _log("info", "[OM_NOTIFY] ===== INICIO process_om_notifications =====")

    cur = conn.cursor()

    _log("debug", "[OM_NOTIFY] SQL candidatos:\n%s", SQL_SELECT_OM_CANDIDATOS)

    rows = cur.execute(SQL_SELECT_OM_CANDIDATOS).fetchall()
    total_rows = len(rows)
    _log("info", "[OM_NOTIFY] candidatos encontrados=%s", total_rows)

    if not rows:
        _log("info", "[OM_NOTIFY] sin imputaciones pendientes")
        return

    today = date.today().isoformat()
    now_txt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    app_url = (
        current_app.config.get("PUBLIC_BASE_URL")
        or current_app.config.get("APP_URL")
        or ""
    ).rstrip("/")

    if app_url:
        app_url = f"{app_url}/reclamos?tab=tab-imputado"
    else:
        app_url = "/reclamos?tab=tab-imputado"

    enqueued = 0
    skipped = 0

    def _enqueue_para_sponsors(
        *,
        sponsors_om,
        tipo,
        template_key,
        fecha_obj,
        payload_base,
        event_prefix,
        dia_label,
        header_color,
        header_title,
        header_subtitle,
        intro_text,
    ):
        nonlocal enqueued

        for sp in sponsors_om:
            sp_id = int(sp["id"])
            sp_nombre = sp.get("nombre") or sp.get("username") or f"Usuario {sp_id}"

            p = dict(payload_base)
            p["destinatario_nombre"] = sp_nombre
            p["sponsor_nombre"] = sp_nombre
            p["dia_label"] = dia_label
            p["header_color"] = header_color
            p["header_title"] = header_title
            p["header_subtitle"] = header_subtitle
            p["intro_text"] = intro_text

            _enqueue_om_notification(
                conn,
                user_id=sp_id,
                tipo=tipo,
                template_key=template_key,
                fecha_obj=fecha_obj,
                payload=p,
                event_key=f"{event_prefix}:sponsor:{sp_id}",
            )

            enqueued += 1

    for r in rows:
        imputacion_id = int(r["imputacion_id"])
        reclamo_id = int(r["reclamo_id"])
        sponsor_id = int(r["sponsor_id"])
        dias = int(r["dias"] or 0)
        codigo = r["codigo"] or ""

        d4_sent_today = _sent_today(r["om_notif_d4_at"], today)
        d5_sent_today = _sent_today(r["om_notif_d5_at"], today)
        d9_sent_today = _sent_today(r["om_notif_d9_at"], today)
        d10_sent_today = _sent_today(r["om_notif_d10_at"], today)

        _log(
            "info",
            "[OM_NOTIFY][ROW] imputacion_id=%s reclamo_id=%s sponsor_id=%s codigo=%s dias=%s d4_today=%s d5_today=%s d9_today=%s d10_today=%s",
            imputacion_id,
            reclamo_id,
            sponsor_id,
            codigo,
            dias,
            d4_sent_today,
            d5_sent_today,
            d9_sent_today,
            d10_sent_today,
        )

        sponsor = _get_user_contact(conn, sponsor_id)
        if not sponsor:
            skipped += 1
            _log(
                "warning",
                "[OM_NOTIFY][SKIP] imputacion_id=%s codigo=%s motivo=sponsor_no_encontrado sponsor_id=%s",
                imputacion_id,
                codigo,
                sponsor_id,
            )
            continue

        sponsors_om = _get_sponsors_om(conn, reclamo_id)

        if not sponsors_om:
            sponsors_om = [{
                "id": sponsor_id,
                "nombre": sponsor.get("nombre") or sponsor.get("username") or f"Usuario {sponsor_id}",
                "username": sponsor.get("username") or "",
            }]

        jefe_id = guess_gerente_area(conn, sponsor_id)
        jefe = _get_user_contact(conn, jefe_id) if jefe_id else None

        _log(
            "debug",
            "[OM_NOTIFY][CHAIN] imputacion_id=%s codigo=%s sponsor=%s jefe_id=%s jefe_nombre=%s sponsors_om=%s",
            imputacion_id,
            codigo,
            sponsor.get("nombre") or sponsor.get("username") or "",
            jefe_id,
            (jefe.get("nombre") or jefe.get("username") or "") if jefe else "",
            [s["id"] for s in sponsors_om],
        )

        payload_base = {
            "codigo": codigo,
            "cliente": r["cliente"] or "",
            "proceso": r["proceso"] or "",
            "observacion": r["observacion"] or "",
            "dias": dias,
            "sponsor_nombre": sponsor.get("nombre") or sponsor.get("username") or f"Usuario {sponsor_id}",
            "jefe_nombre": (jefe.get("nombre") or jefe.get("username") or f"Usuario {jefe_id}") if jefe else "No definido",
            "gg_nombre": "",
            "sc_nombre": "",
            "destinatario_nombre": "",
            "dia_label": "",
            "header_color": "#2563eb",
            "header_title": "",
            "header_subtitle": "",
            "intro_text": "",
            "app_url": app_url,
        }

        if dias >= 4 and not d4_sent_today:
            _log(
                "info",
                "[OM_NOTIFY][D4] encolando sponsors imputacion_id=%s codigo=%s sponsors=%s",
                imputacion_id,
                codigo,
                [s["id"] for s in sponsors_om],
            )

            _enqueue_para_sponsors(
                sponsors_om=sponsors_om,
                tipo=TIPO_OM_D4,
                template_key=TPL_OM_SPONSOR_D4,
                fecha_obj=today,
                payload_base=payload_base,
                event_prefix=f"om:{imputacion_id}:d4:{today}",
                dia_label="Día 4",
                header_color="#16a34a",
                header_title=f"Alerta OM — Día 4 ({codigo})",
                header_subtitle="Alerta temprana: la OM sigue pendiente de respuesta del sponsor.",
                intro_text=(
                    f"La Oportunidad de Mejora {codigo} aún no registra respuesta del sponsor "
                    f"y ya alcanzó el día 4 desde su creación."
                ),
            )

            _exec_retry(
                cur,
                "UPDATE reclamo_imputados SET om_notif_d4_at = ? WHERE id = ?",
                (now_txt, imputacion_id),
            )
        else:
            _log(
                "debug",
                "[OM_NOTIFY][D4] skip imputacion_id=%s codigo=%s dias=%s sent_today=%s",
                imputacion_id,
                codigo,
                dias,
                d4_sent_today,
            )

        if dias >= 5 and not d5_sent_today and jefe_id and jefe:
            _log(
                "info",
                "[OM_NOTIFY][D5] encolando jefe imputacion_id=%s codigo=%s jefe_id=%s",
                imputacion_id,
                codigo,
                jefe_id,
            )

            p = dict(payload_base)
            p["destinatario_nombre"] = jefe.get("nombre") or jefe.get("username") or f"Usuario {jefe_id}"
            p["dia_label"] = "Día 5"
            p["header_color"] = "#eab308"
            p["header_title"] = f"Seguimiento OM — Día 5 ({codigo})"
            p["header_subtitle"] = "Seguimiento al sponsor por falta de respuesta."
            p["intro_text"] = (
                f"La Oportunidad de Mejora {codigo} no ha sido respondida por el sponsor "
                f"{payload_base['sponsor_nombre']} y ya alcanzó el día 5."
            )

            _enqueue_om_notification(
                conn,
                user_id=jefe_id,
                tipo=TIPO_OM_D5,
                template_key=TPL_OM_JEFE_D5,
                fecha_obj=today,
                payload=p,
                event_key=f"om:{imputacion_id}:d5:{today}:jefe:{jefe_id}",
            )

            _exec_retry(
                cur,
                "UPDATE reclamo_imputados SET om_notif_d5_at = ? WHERE id = ?",
                (now_txt, imputacion_id),
            )
            enqueued += 1
        else:
            _log(
                "debug",
                "[OM_NOTIFY][D5] skip imputacion_id=%s codigo=%s dias=%s sent_today=%s jefe_id=%s",
                imputacion_id,
                codigo,
                dias,
                d5_sent_today,
                jefe_id,
            )

        if dias >= 9 and not d9_sent_today:
            _log(
                "info",
                "[OM_NOTIFY][D9] encolando sponsors+jefe imputacion_id=%s codigo=%s sponsors=%s",
                imputacion_id,
                codigo,
                [s["id"] for s in sponsors_om],
            )

            _enqueue_para_sponsors(
                sponsors_om=sponsors_om,
                tipo=TIPO_OM_D9,
                template_key=TPL_OM_SPONSOR_JEFE_D9,
                fecha_obj=today,
                payload_base=payload_base,
                event_prefix=f"om:{imputacion_id}:d9:{today}",
                dia_label="Día 9",
                header_color="#f97316",
                header_title=f"Seguimiento OM — Día 9 ({codigo})",
                header_subtitle="La OM continúa pendiente y requiere atención inmediata.",
                intro_text=f"La Oportunidad de Mejora {codigo} sigue sin respuesta y ya alcanzó el día 9.",
            )

            if jefe_id and jefe:
                p_j = dict(payload_base)
                p_j["destinatario_nombre"] = jefe.get("nombre") or jefe.get("username") or f"Usuario {jefe_id}"
                p_j["dia_label"] = "Día 9"
                p_j["header_color"] = "#f97316"
                p_j["header_title"] = f"Seguimiento OM — Día 9 ({codigo})"
                p_j["header_subtitle"] = "La OM continúa pendiente y requiere atención inmediata."
                p_j["intro_text"] = f"La Oportunidad de Mejora {codigo} sigue sin respuesta y ya alcanzó el día 9."

                _enqueue_om_notification(
                    conn,
                    user_id=jefe_id,
                    tipo=TIPO_OM_D9,
                    template_key=TPL_OM_SPONSOR_JEFE_D9,
                    fecha_obj=today,
                    payload=p_j,
                    event_key=f"om:{imputacion_id}:d9:{today}:jefe:{jefe_id}",
                )
                enqueued += 1

            _exec_retry(
                cur,
                "UPDATE reclamo_imputados SET om_notif_d9_at = ? WHERE id = ?",
                (now_txt, imputacion_id),
            )
        else:
            _log(
                "debug",
                "[OM_NOTIFY][D9] skip imputacion_id=%s codigo=%s dias=%s sent_today=%s",
                imputacion_id,
                codigo,
                dias,
                d9_sent_today,
            )

        if dias >= 10 and not d10_sent_today:
            gg_ids = _get_gerente_general_ids(conn)
            sc_ids = _get_servicio_cliente_ids(conn)

            _log(
                "info",
                "[OM_NOTIFY][D10] encolando escalamiento imputacion_id=%s codigo=%s gg=%s sc=%s sponsors=%s jefe_id=%s",
                imputacion_id,
                codigo,
                len(gg_ids),
                len(sc_ids),
                [s["id"] for s in sponsors_om],
                jefe_id,
            )

            sc_nombres = []
            for sc_id_tmp in sc_ids:
                sc_contact = _get_user_contact(conn, sc_id_tmp)
                if sc_contact:
                    sc_nombres.append(
                        sc_contact.get("nombre") or sc_contact.get("username") or f"Usuario {sc_id_tmp}"
                    )

            sc_nombre_join = ", ".join(sc_nombres) if sc_nombres else "No definido"

            intro_d10 = (
                f"La Oportunidad de Mejora {codigo} no registra respuesta del sponsor y ya alcanzó el día 10. "
                f"Se escala el caso a Gerencia General con copia al jefe del sponsor, sponsor y Servicio al Cliente."
            )

            for gg_id in gg_ids:
                gg = _get_user_contact(conn, gg_id)
                if not gg:
                    _log("warning", "[OM_NOTIFY][D10] gg_id=%s sin contacto", gg_id)
                    continue

                gg_nombre = gg.get("nombre") or gg.get("username") or f"Usuario {gg_id}"

                p = dict(payload_base)
                p["gg_nombre"] = gg_nombre
                p["sc_nombre"] = sc_nombre_join
                p["destinatario_nombre"] = gg_nombre
                p["dia_label"] = "Día 10"
                p["header_color"] = "#dc2626"
                p["header_title"] = f"Escalamiento OM — Día 10 ({codigo})"
                p["header_subtitle"] = "Escalamiento formal por falta de respuesta del sponsor."
                p["intro_text"] = intro_d10

                _enqueue_om_notification(
                    conn,
                    user_id=gg_id,
                    tipo=TIPO_OM_D10,
                    template_key=TPL_OM_GG_D10,
                    fecha_obj=today,
                    payload=p,
                    event_key=f"om:{imputacion_id}:d10:{today}:gg:{gg_id}",
                )
                enqueued += 1

            if jefe_id and jefe:
                p = dict(payload_base)
                p["sc_nombre"] = sc_nombre_join
                p["destinatario_nombre"] = jefe.get("nombre") or jefe.get("username") or f"Usuario {jefe_id}"
                p["dia_label"] = "Día 10"
                p["header_color"] = "#dc2626"
                p["header_title"] = f"Escalamiento OM — Día 10 ({codigo})"
                p["header_subtitle"] = "Escalamiento formal por falta de respuesta del sponsor."
                p["intro_text"] = intro_d10

                _enqueue_om_notification(
                    conn,
                    user_id=jefe_id,
                    tipo=TIPO_OM_D10,
                    template_key=TPL_OM_GG_D10,
                    fecha_obj=today,
                    payload=p,
                    event_key=f"om:{imputacion_id}:d10:{today}:jefe:{jefe_id}",
                )
                enqueued += 1

            _enqueue_para_sponsors(
                sponsors_om=sponsors_om,
                tipo=TIPO_OM_D10,
                template_key=TPL_OM_GG_D10,
                fecha_obj=today,
                payload_base={
                    **payload_base,
                    "sc_nombre": sc_nombre_join,
                },
                event_prefix=f"om:{imputacion_id}:d10:{today}",
                dia_label="Día 10",
                header_color="#dc2626",
                header_title=f"Escalamiento OM — Día 10 ({codigo})",
                header_subtitle="Escalamiento formal por falta de respuesta del sponsor.",
                intro_text=intro_d10,
            )

            for sc_id in sc_ids:
                sc_contact = _get_user_contact(conn, sc_id)

                p = dict(payload_base)
                p["sc_nombre"] = sc_nombre_join
                p["destinatario_nombre"] = (
                    sc_contact.get("nombre") or sc_contact.get("username")
                    if sc_contact
                    else f"Usuario {sc_id}"
                )
                p["dia_label"] = "Día 10"
                p["header_color"] = "#dc2626"
                p["header_title"] = f"Escalamiento OM — Día 10 ({codigo})"
                p["header_subtitle"] = "Escalamiento formal por falta de respuesta del sponsor."
                p["intro_text"] = intro_d10

                _enqueue_om_notification(
                    conn,
                    user_id=sc_id,
                    tipo=TIPO_OM_D10,
                    template_key=TPL_OM_GG_D10,
                    fecha_obj=today,
                    payload=p,
                    event_key=f"om:{imputacion_id}:d10:{today}:sc:{sc_id}",
                )
                enqueued += 1

            _exec_retry(
                cur,
                "UPDATE reclamo_imputados SET om_notif_d10_at = ? WHERE id = ?",
                (now_txt, imputacion_id),
            )
        else:
            _log(
                "debug",
                "[OM_NOTIFY][D10] skip imputacion_id=%s codigo=%s dias=%s sent_today=%s",
                imputacion_id,
                codigo,
                dias,
                d10_sent_today,
            )

    conn.commit()
    _log(
        "info",
        "[OM_NOTIFY] ===== FIN process_om_notifications ===== candidatos=%s enqueued=%s skipped=%s",
        total_rows,
        enqueued,
        skipped,
    )


def process_gastos_expiry(conn):
    """
    Política:
    - Si NO tiene ninguna aprobación (GA/GG/GF = 0) por 7 días => inactivar y notificar.
    - En el penúltimo día (día 6) => enviar aviso previo una sola vez.
    """
    _log("info", "[EXPIRY] ===== start process_gastos_expiry =====")

    cur = conn.cursor()

    try:
        ensure_gastos_expiry_schema(conn)

        try:
            cur.execute("""
                SELECT
                    GETDATE() AS now_local,
                    CAST(GETDATE() AS date) AS today_local,
                    DATEADD(day, -6, CAST(GETDATE() AS date)) AS d6,
                    DATEADD(day, -7, CAST(GETDATE() AS date)) AS d7
            """)
            row_now = cur.fetchone()
            _log(
                "info",
                "[EXPIRY][NOW] now_local=%s today_local=%s d6=%s d7=%s",
                row_now["now_local"],
                row_now["today_local"],
                row_now["d6"],
                row_now["d7"],
            )
        except Exception as e:
            _log("warning", "[EXPIRY][NOW] no se pudo leer now SQL Server -> %s", e)

        _log("info", "[EXPIRY][NOW] python now=%s", datetime.now().isoformat(timespec="seconds"))

        _sql_debug_counts(conn)

        warn_sql = """
            SELECT
                g.id,
                g.created_at,
                g.fecha,
                g.motivo,
                g.usuario_id,
                COALESCE(g.ga_aprobado,0) AS ga_aprobado,
                COALESCE(g.gg_aprobado,0) AS gg_aprobado,
                COALESCE(g.gf_aprobado,0) AS gf_aprobado,
                LTRIM(RTRIM(COALESCE(g.sap_contabilizacion,''))) AS sap_contabilizacion,
                COALESCE(g.inactivo,0) AS inactivo,
                g.warn_sent_at
            FROM gastos_tarjeta g
            WHERE COALESCE(g.inactivo,0)=0
              AND LTRIM(RTRIM(COALESCE(g.sap_contabilizacion,'')))=''
              AND COALESCE(g.ga_aprobado,0)=0
              AND COALESCE(g.gg_aprobado,0)=0
              AND COALESCE(g.gf_aprobado,0)=0
              AND g.warn_sent_at IS NULL
              AND CAST(g.created_at AS date) <= DATEADD(day, -6, CAST(GETDATE() AS date))
              AND CAST(g.created_at AS date) >  DATEADD(day, -7, CAST(GETDATE() AS date))
            ORDER BY CAST(g.created_at AS date) ASC, g.id ASC
        """

        _log("info", "[EXPIRY][WARN] SQL=%s", " ".join(warn_sql.split()))

        cur.execute(warn_sql)
        warn_rows = cur.fetchall() or []
        _log("info", "[EXPIRY][WARN] candidatos=%s", len(warn_rows))

        for i, g in enumerate(warn_rows[:5]):
            _log(
                "info",
                "[EXPIRY][WARN][SAMPLE %s] id=%s fecha=%s usuario_id=%s motivo=%s warn_sent_at=%s",
                i + 1,
                g["id"],
                g["fecha"],
                g["usuario_id"],
                (g["motivo"] or "")[:60],
                g["warn_sent_at"],
            )

        warned = 0

        for g in warn_rows:
            gid = int(g["id"])
            usuario_id = int(g["usuario_id"] or 0)

            if not usuario_id:
                _log("warning", "[EXPIRY][WARN] skip gid=%s porque usuario_id vacío", gid)
                continue

            gerente_id = _get_ultimo_jefe_id(conn, usuario_id, fallback_to_self=True)
            gerente_id = int(gerente_id or 0) or usuario_id

            u = _get_user_contact(conn, usuario_id)
            m = _get_user_contact(conn, gerente_id)

            _log(
                "info",
                "[EXPIRY][WARN] gid=%s usuario_id=%s gerente_id=%s u_email=%s m_email=%s",
                gid,
                usuario_id,
                gerente_id,
                (u or {}).get("email"),
                (m or {}).get("email"),
            )

            try:
                mail.notify_gasto_expiry_warning(
                    current_app._get_current_object(),
                    gasto=dict(g),
                    usuario=u,
                    gerente=m,
                )

                cur.execute(
                    """
                    UPDATE gastos_tarjeta
                    SET warn_sent_at = ?
                    WHERE id = ?
                      AND warn_sent_at IS NULL
                    """,
                    (_now_str(), gid),
                )

                _log("info", "[EXPIRY][WARN] correo OK gid=%s", gid)
                _log("info", "[EXPIRY][WARN] update warn_sent_at gid=%s rowcount=%s", gid, cur.rowcount)
                warned += 1

            except Exception:
                current_app.logger.exception("[EXPIRY][WARN] fallo correo gid=%s", gid)

        expire_sql = """
            SELECT g.*
            FROM gastos_tarjeta g
            WHERE COALESCE(g.inactivo,0)=0
              AND LTRIM(RTRIM(COALESCE(g.sap_contabilizacion,'')))=''
              AND COALESCE(g.ga_aprobado,0)=0
              AND COALESCE(g.gg_aprobado,0)=0
              AND COALESCE(g.gf_aprobado,0)=0
              AND CAST(g.created_at AS date) <= DATEADD(day, -7, CAST(GETDATE() AS date))
            ORDER BY CAST(g.created_at AS date) ASC, g.id ASC
        """

        _log("info", "[EXPIRY][EXPIRE] SQL=%s", " ".join(expire_sql.split()))

        cur.execute(expire_sql)
        exp_rows = cur.fetchall() or []
        _log("info", "[EXPIRY][EXPIRE] candidatos=%s", len(exp_rows))

        inactivated = 0

        for row in exp_rows:
            g = dict(row)
            gid = int(g.get("id") or 0)
            usuario_id = int(g.get("usuario_id") or 0)

            if not gid or not usuario_id:
                _log("warning", "[EXPIRY][EXPIRE] skip gid=%s usuario_id=%s inválidos", gid, usuario_id)
                continue

            gerente_id = _get_ultimo_jefe_id(conn, usuario_id, fallback_to_self=True)
            gerente_id = int(gerente_id or 0) or usuario_id

            u = _get_user_contact(conn, usuario_id)
            m = _get_user_contact(conn, gerente_id)

            _log(
                "info",
                "[EXPIRY][EXPIRE] inactivando gid=%s usuario_id=%s gerente_id=%s",
                gid,
                usuario_id,
                gerente_id,
            )

            cur.execute("""
                UPDATE gastos_tarjeta
                SET inactivo = 1,
                    inactivo_at = ?,
                    inactivo_reason = ?
                WHERE id = ?
                  AND COALESCE(inactivo,0)=0
            """, (
                _now_str(),
                "AUTO: Sin aprobaciones en 7 días (política)",
                gid,
            ))

            _log("info", "[EXPIRY][EXPIRE] update inactivo gid=%s rowcount=%s", gid, cur.rowcount)

            try:
                mail.notify_gasto_expired_inactivated(
                    current_app._get_current_object(),
                    gasto=g,
                    usuario=u,
                    gerente=m,
                )
                _log("info", "[EXPIRY][EXPIRE] correo OK gid=%s", gid)
            except Exception as e:
                _log("error", "[EXPIRY][EXPIRE] fallo correo gid=%s -> %s", gid, e)

            inactivated += 1

        conn.commit()
        _log("info", "[EXPIRY] ===== end ok warned=%s inactivated=%s =====", warned, inactivated)
        return {"ok": True, "warned": warned, "inactivated": inactivated}

    except Exception as e:
        conn.rollback()
        _log("error", "[EXPIRY] rollback por error -> %s", e)
        return {"ok": False, "error": str(e)}
     
from datetime import datetime
from modules.scheduler.scheduler_queries import SQL_SELECT_OM_ACCIONES_SEGUIMIENTO
from modules.scheduler.scheduler_repository import (
    _get_user_contact,
    _get_ultimo_jefe_id,
)
from modules.routes_reclamos import _send_mail_safe


def _row_get(row, key, idx=None, default=None):
    if row is None:
        return default
    try:
        val = row[key]
        return default if val is None else val
    except Exception:
        pass
    if idx is not None:
        try:
            val = row[idx]
            return default if val is None else val
        except Exception:
            pass
    return default


def _dedup_ids(ids):
    out = []
    seen = set()
    for x in ids:
        if not x:
            continue
        x = int(x)
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _html_om_accion(row, titulo, dias_txt, destinatario_nombre="Usuario"):
    codigo = _row_get(row, "codigo", default="")
    tipo = _row_get(row, "tipo", default="")
    descripcion = _row_get(row, "descripcion", default="")
    fecha = _row_get(row, "fecha_compromiso", default="")
    cliente = _row_get(row, "cliente_nombre", default="")
    proceso = _row_get(row, "proceso_text", default="")
    observacion = _row_get(row, "observacion", default="")
    fecha_reclamo = _row_get(row, "fecha_reclamo", default="")
    sponsor_nombre = _row_get(row, "sponsor_nombre", default="")

    return f"""
<!doctype html>
<html>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:Segoe UI,Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:24px 0;">
<tr>
<td align="center">
<table width="720" cellpadding="0" cellspacing="0"
       style="max-width:720px;background:#ffffff;border-radius:10px;border:1px solid #e5e7eb;overflow:hidden;">
<tr>
<td style="background:#2563eb;padding:18px 22px;color:#ffffff;">
<div style="font-size:12px;text-transform:uppercase;letter-spacing:.08em;opacity:.9;">
Oportunidad de Mejora
</div>
<div style="font-size:20px;font-weight:800;margin-top:4px;">
{titulo}
</div>
<div style="font-size:13px;opacity:.95;margin-top:8px;">
OM {codigo} — {dias_txt}
</div>
<div style="font-size:13px;color:rgba(255,255,255,.95);line-height:1.6;margin:18px 22px 0 22px;">
    Hola <b>{destinatario_nombre}</b>,
</div>
</td>
</tr>

<tr>
<td style="padding:18px 22px;">
<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
<tr>
<td style="width:210px;background:#eef2ff;font-weight:700;padding:8px 12px;border-bottom:1px solid #e5e7eb;">Código</td>
<td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;">{codigo}</td>
</tr>
<tr>
<td style="width:210px;background:#eef2ff;font-weight:700;padding:8px 12px;border-bottom:1px solid #e5e7eb;">Cliente</td>
<td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;">{cliente or '-'}</td>
</tr>
<tr>
<td style="width:210px;background:#eef2ff;font-weight:700;padding:8px 12px;border-bottom:1px solid #e5e7eb;">Proceso</td>
<td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;">{proceso or '-'}</td>
</tr>
<tr>
<td style="width:210px;background:#eef2ff;font-weight:700;padding:8px 12px;border-bottom:1px solid #e5e7eb;">Tipo acción</td>
<td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;">{tipo}</td>
</tr>
<tr>
<td style="width:210px;background:#eef2ff;font-weight:700;padding:8px 12px;border-bottom:1px solid #e5e7eb;">Fecha reclamo</td>
<td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;">{fecha_reclamo or '-'}</td>
</tr>

<tr>
<td style="width:210px;background:#eef2ff;font-weight:700;padding:8px 12px;border-bottom:1px solid #e5e7eb;">Sponsor / Imputado</td>
<td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;">{sponsor_nombre or '-'}</td>
</tr>
<tr>
<td style="width:210px;background:#eef2ff;font-weight:700;padding:8px 12px;border-bottom:1px solid #e5e7eb;">Fecha compromiso</td>
<td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;">{fecha}</td>
</tr>
<tr>
<td style="width:210px;background:#eef2ff;font-weight:700;padding:8px 12px;border-bottom:1px solid #e5e7eb;">Acción</td>
<td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;white-space:pre-wrap;">{descripcion}</td>
</tr>
<tr>
<td style="width:210px;background:#eef2ff;font-weight:700;padding:8px 12px;border-bottom:1px solid #e5e7eb;">Observación OM</td>
<td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;white-space:pre-wrap;">{observacion or '-'}</td>
</tr>
</table>

<div style="font-size:12px;color:#6b7280;margin-top:14px;">
Este es un mensaje automático. No responda a este correo.
</div>
</td>
</tr>
</table>
</td>
</tr>
</table>
</body>
</html>
"""


def _send_to_users(conn, user_ids, subject, text_body, row, titulo, dias_txt):
    for uid in _dedup_ids(user_ids):
        u = _get_user_contact(conn, uid)

        if not u or not u.get("email"):
            continue

        nombre_destinatario = u.get("nombre") or u.get("username") or "Usuario"

        html_body = _html_om_accion(
            row,
            titulo,
            dias_txt,
            nombre_destinatario
        )

        _send_mail_safe(
            u["email"],
            subject,
            text_body,
            html_body=html_body
        )



def process_om_acciones_seguimiento(conn):
    """
    Seguimiento de acciones CONTROL / CORRECTIVA de OM cerradas.

    Notifica:
    - faltando 15, 10, 5 y 0 días: sponsor/responsable + creador OM
    - vencida: gerente del sponsor, creador OM, jefe del creador y gerente del creador
    """

    cur = conn.cursor()
    cur.execute(SQL_SELECT_OM_ACCIONES_SEGUIMIENTO)
    rows = cur.fetchall()
    _log("info", "[OM_ACCIONES] candidatos=%s", len(rows))

    now = datetime.now()

    for row in rows:
        _log("info", "[OM_ACCIONES] candidatos=%s", len(rows))
        accion_id = int(_row_get(row, "accion_id"))
        dias = int(_row_get(row, "dias_restantes", default=9999))

        sponsor_id = _row_get(row, "sponsor_id")
        creador_id = _row_get(row, "creador_id")
        servicio_cliente_ids = _get_servicio_cliente_ids(conn)

        codigo = _row_get(row, "codigo", default="")
        tipo = _row_get(row, "tipo", default="")
        fecha = _row_get(row, "fecha_compromiso", default="")

        # -------------------------
        # Recordatorios previos
        # -------------------------
        mapa = {
            15: ("notif_15d_at", "Faltan 15 días", "15 días"),
            10: ("notif_10d_at", "Faltan 10 días", "10 días"),
            5: ("notif_5d_at", "Faltan 5 días", "5 días"),
            0: ("notif_0d_at", "Vence hoy", "vence hoy"),
        }

        if dias in mapa:
            col, titulo, dias_txt = mapa[dias]

            if _row_get(row, col):
                continue

            subject = f"[OM] {titulo} para acción {tipo} - {codigo}"
            text_body = (
                f"{titulo} para cumplir una acción {tipo} de la OM {codigo}.\n"
                f"Fecha compromiso: {fecha}\n"
            )

            _send_to_users(
                conn,
                _dedup_ids([sponsor_id, creador_id] + servicio_cliente_ids),
                subject,
                text_body,
                row,
                titulo,
                dias_txt
            )

            cur.execute(
                f"""
                UPDATE reclamo_imputado_acciones
                SET {col} = ?
                WHERE id = ?
                """,
                (now, accion_id)
            )
            conn.commit()
            continue

        # -------------------------
        # Escalamiento vencido
        # -------------------------
        if dias < 0:
            cur.execute("""
                SELECT notif_overdue_last_date
                FROM reclamo_imputado_acciones
                WHERE id = ?
            """, (accion_id,))
            rx = cur.fetchone()

            last_date = _row_get(rx, "notif_overdue_last_date", 0)

            if last_date and str(last_date)[:10] == datetime.now().strftime("%Y-%m-%d"):
                continue

            gerente_sponsor_id = _get_ultimo_jefe_id(conn, sponsor_id)
            jefe_creador_id = None
            gerente_creador_id = None

            if creador_id:
                cur.execute("SELECT jefe_id FROM usuarios WHERE id = ?", (int(creador_id),))
                rj = cur.fetchone()
                jefe_creador_id = _row_get(rj, "jefe_id", 0)
                gerente_creador_id = _get_ultimo_jefe_id(conn, creador_id)

            destinatarios = _dedup_ids([
                gerente_sponsor_id,
                creador_id,
                jefe_creador_id,
                gerente_creador_id,
            ] + servicio_cliente_ids)

            subject = f"[OM VENCIDA] Acción {tipo} no cumplida - {codigo}"
            text_body = (
                f"La acción {tipo} de la OM {codigo} está vencida.\n"
                f"Fecha compromiso: {fecha}\n"
                f"Días vencida: {abs(dias)}\n"
            )
            html_body = _html_om_accion(
                row,
                "Acción vencida no cumplida",
                f"vencida hace {abs(dias)} día(s)"
            )

            _send_to_users(
                conn,
                destinatarios,
                subject,
                text_body,
                row,
                "Acción vencida no cumplida",
                f"vencida hace {abs(dias)} día(s)"
            )

            cur.execute(
                """
                UPDATE reclamo_imputado_acciones
                SET notif_overdue_at = COALESCE(notif_overdue_at, GETDATE()),
                    notif_overdue_last_date = CAST(GETDATE() AS date)
                WHERE id = ?
                """,
                (accion_id,)
            )
            conn.commit()    