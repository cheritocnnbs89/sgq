# modules/scheduler/__init__.py
# ==========================================================
# Paquete interno del scheduler.
# Reexporta funciones para mantener una API centralizada.
# ==========================================================

from .scheduler_worker import start_scheduler

from .scheduler_services import (
    auto_close_expired_tasks,
    plan_notifications,
    dispatch_notifications,
    notify_overdue,
    send_daily_report,
    process_om_notifications,
    process_gastos_expiry,
)

from .scheduler_notifications import (
    ensure_core_templates,
    ensure_gasto_templates2,
    ensure_gasto_templates3,
    ensure_gasto_templates,
    ensure_om_templates,
    enqueue_gasto_approved,
    enqueue_gasto_rejected_gg,
)

from .scheduler_repository import (
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
)

from .scheduler_security import (
    _log,
    _format_sql_for_log,
    _exec_retry,
    _is_quiet,
    _next_5min_sqlite,
    _now_str,
)