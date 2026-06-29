# modules/routes_admin_scheduler.py
# ==========================================================
# Panel de administración de jobs del scheduler.
# URL: /admin/scheduler
# ==========================================================

from flask import Blueprint, render_template, request, jsonify, session
from .db import get_db
from .security import require_login
from .scheduler.scheduler_config_repo import (
    ensure_scheduler_table,
    get_all_jobs,
    update_job_config,
)

scheduler_admin_bp = Blueprint("scheduler_admin", __name__)

MODULO_LABELS = {
    "tareas": "Tareas",
    "oportunidades_mejora": "Oportunidades de Mejora",
    "gastos": "Gastos Tarjeta",
    "contratos": "Contratos",
    "planilla": "Planilla",
    "soporte": "Soporte / Email",
    "facturacion": "Facturación",
}

MODULO_ICONS = {
    "tareas": "bi-check2-square",
    "oportunidades_mejora": "bi-lightbulb",
    "gastos": "bi-credit-card",
    "contratos": "bi-file-earmark-text",
    "planilla": "bi-people",
    "soporte": "bi-envelope",
    "facturacion": "bi-receipt",
}


@scheduler_admin_bp.route("/admin/scheduler")
@require_login
def scheduler_admin_view():
    if session.get("rol") not in ("admin", "coordinador"):
        return render_template("403.html"), 403

    conn = get_db()
    ensure_scheduler_table(conn)
    jobs = get_all_jobs(conn)

    # Agrupar por módulo
    modulos: dict[str, list] = {}
    for job in jobs:
        mod = job.get("modulo") or "otros"
        modulos.setdefault(mod, []).append(job)

    return render_template(
        "admin_scheduler.html",
        modulos=modulos,
        modulo_labels=MODULO_LABELS,
        modulo_icons=MODULO_ICONS,
    )


@scheduler_admin_bp.route("/admin/scheduler/<job_key>/toggle", methods=["POST"])
@require_login
def scheduler_toggle(job_key):
    if session.get("rol") not in ("admin", "coordinador"):
        return jsonify(ok=False, error="Sin permiso"), 403

    data = request.get_json(silent=True) or {}
    activo = bool(data.get("activo", True))

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE scheduler_jobs_config SET activo = ? WHERE job_key = ?",
        (1 if activo else 0, job_key)
    )
    conn.commit()
    return jsonify(ok=True, activo=activo)


@scheduler_admin_bp.route("/admin/scheduler/<job_key>/config", methods=["POST"])
@require_login
def scheduler_update_config(job_key):
    if session.get("rol") not in ("admin", "coordinador"):
        return jsonify(ok=False, error="Sin permiso"), 403

    data = request.get_json(silent=True) or {}
    try:
        intervalo_min = int(data["intervalo_min"]) if data.get("intervalo_min") not in (None, "") else None
    except (ValueError, TypeError):
        return jsonify(ok=False, error="intervalo_min inválido"), 400

    hora_inicio = data.get("hora_inicio") or None

    conn = get_db()
    update_job_config(
        conn,
        job_key=job_key,
        activo=True,
        intervalo_min=intervalo_min,
        hora_inicio=hora_inicio,
    )
    return jsonify(ok=True)


@scheduler_admin_bp.route("/admin/scheduler/<job_key>/run", methods=["POST"])
@require_login
def scheduler_run_now(job_key):
    if session.get("rol") not in ("admin",):
        return jsonify(ok=False, error="Solo admin puede ejecutar manualmente"), 403

    try:
        resultado = _run_job(job_key)
        return jsonify(ok=True, resultado=resultado)
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500


def _run_job(job_key: str) -> str:
    from .scheduler.scheduler_config_repo import update_job_result
    from .scheduler.scheduler_repository import get_db_standalone

    runners = {
        "auto_close_expired_tasks": _run_auto_close,
        "plan_notifications": _run_plan_notifications,
        "dispatch_notifications": _run_dispatch_notifications,
        "notify_overdue": _run_notify_overdue,
        "send_daily_report": _run_daily_report,
        "process_om_notifications": _run_om_notifications,
        "process_om_acciones_seguimiento": _run_om_acciones,
        "process_gastos_expiry": _run_gastos_expiry,
        "encolar_notificaciones_contratos_por_vencer": _run_contratos,
        "encolar_notificaciones_garantias_multi_dia": _run_garantias,
        "notify_unassigned_tickets": _run_unassigned_tickets,
    }

    fn = runners.get(job_key)
    if not fn:
        return f"Job '{job_key}' no soporta ejecución manual."

    resultado = fn()
    conn = get_db_standalone()
    try:
        update_job_result(conn, job_key, resultado)
    finally:
        conn.close()
    return resultado


def _run_auto_close():
    from .scheduler.scheduler_services import auto_close_expired_tasks
    auto_close_expired_tasks()
    return "OK"

def _run_plan_notifications():
    from .scheduler.scheduler_services import plan_notifications
    plan_notifications()
    return "OK"

def _run_dispatch_notifications():
    from .scheduler.scheduler_services import dispatch_notifications
    dispatch_notifications()
    return "OK"

def _run_notify_overdue():
    from .scheduler.scheduler_services import notify_overdue
    notify_overdue()
    return "OK"

def _run_daily_report():
    from .scheduler.scheduler_services import send_daily_report
    send_daily_report()
    return "OK"

def _run_om_notifications():
    from .scheduler.scheduler_repository import get_db_standalone
    from .scheduler.scheduler_services import process_om_notifications
    conn = get_db_standalone()
    try:
        process_om_notifications(conn)
    finally:
        conn.close()
    return "OK"

def _run_om_acciones():
    from .scheduler.scheduler_repository import get_db_standalone
    from .scheduler.scheduler_services import process_om_acciones_seguimiento
    conn = get_db_standalone()
    try:
        process_om_acciones_seguimiento(conn)
    finally:
        conn.close()
    return "OK"

def _run_gastos_expiry():
    from .scheduler.scheduler_repository import get_db_standalone
    from .scheduler.scheduler_services import process_gastos_expiry
    conn = get_db_standalone()
    try:
        process_gastos_expiry(conn)
    finally:
        conn.close()
    return "OK"

def _run_contratos():
    from .contratos.contratos_services import encolar_notificaciones_contratos_por_vencer
    n = encolar_notificaciones_contratos_por_vencer()
    return f"Encolados: {n}"

def _run_garantias():
    from .contratos.contratos_services import encolar_notificaciones_garantias_multi_dia
    n = encolar_notificaciones_garantias_multi_dia()
    return f"Encoladas: {n}"

def _run_unassigned_tickets():
    from .email_to_task.email_inbox_service import notify_unassigned_tickets
    n = notify_unassigned_tickets()
    return f"Alertados: {n}"


def register_scheduler_admin_routes(app):
    app.register_blueprint(scheduler_admin_bp)
