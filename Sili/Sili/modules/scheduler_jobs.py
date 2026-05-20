# modules/scheduler_jobs.py
# ==========================================================
# WRAPPER LEGACY DE COMPATIBILIDAD
# Mantiene vivos los imports existentes del proyecto.
# ==========================================================

# Cambia a True cuando quieras activar nuevamente los jobs
SCHEDULER_JOBS_ENABLED = False

from modules.scheduler import (
    start_scheduler as _real_start_scheduler,
    auto_close_expired_tasks,
    plan_notifications,
    dispatch_notifications,
    notify_overdue,
    send_daily_report,
    process_om_notifications,
    process_gastos_expiry,
    ensure_core_templates,
    ensure_gasto_templates2,
    ensure_gasto_templates3,
    ensure_gasto_templates,
    ensure_om_templates,
    enqueue_gasto_approved,
    enqueue_gasto_rejected_gg,
    get_db_standalone,
    ensure_notify_schema,
    ensure_gastos_expiry_schema,
    ensure_om_notification_schema,
    get_ultimo_jefe_activo,
    guess_gerente_area,
    _get_username,
    _get_user_contact,
    _get_ultimo_jefe_id,
    _get_gerente_general_ids,
    _get_servicio_cliente_ids,
    _log,
    _format_sql_for_log,
    _exec_retry,
    _is_quiet,
    _next_5min_sqlite,
)

from modules.scheduler.scheduler_notifications import (
    _send_email,
    _send_inapp,
    _send_slack,
    _enqueue_om_notification,
)

from modules.scheduler.scheduler_services import (
    _tareas_para_usuario_en_fecha,
    _sent_today,
)

from modules.scheduler.scheduler_security import _now_str
from modules.scheduler.scheduler_repository import _sql_debug_counts


def start_scheduler(*args, **kwargs):
    if not SCHEDULER_JOBS_ENABLED:
        print("[SCHEDULER] Jobs deshabilitados")
        return None

    return _real_start_scheduler(*args, **kwargs)


__all__ = [
    "SCHEDULER_JOBS_ENABLED",
    "start_scheduler",
    "auto_close_expired_tasks",
    "plan_notifications",
    "dispatch_notifications",
    "notify_overdue",
    "send_daily_report",
    "process_om_notifications",
    "process_gastos_expiry",
    "ensure_core_templates",
    "ensure_gasto_templates2",
    "ensure_gasto_templates3",
    "ensure_gasto_templates",
    "ensure_om_templates",
    "enqueue_gasto_approved",
    "enqueue_gasto_rejected_gg",
    "get_db_standalone",
    "ensure_notify_schema",
    "ensure_gastos_expiry_schema",
    "ensure_om_notification_schema",
    "get_ultimo_jefe_activo",
    "guess_gerente_area",
    "_get_username",
    "_get_user_contact",
    "_get_ultimo_jefe_id",
    "_get_gerente_general_ids",
    "_get_servicio_cliente_ids",
    "_log",
    "_format_sql_for_log",
    "_exec_retry",
    "_is_quiet",
    "_next_5min_sqlite",
    "_send_email",
    "_send_inapp",
    "_send_slack",
    "_enqueue_om_notification",
    "_tareas_para_usuario_en_fecha",
    "_sent_today",
    "_now_str",
    "_sql_debug_counts",
]