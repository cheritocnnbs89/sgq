# modules/scheduler/scheduler_worker.py
# ==========================================================
# Worker del scheduler.
# Conserva el hilo de fondo, bootstrap inicial y loop.
# CAMBIO: agrega trigger viernes 17:00 para reporte semanal planilla.
# ==========================================================

from __future__ import annotations

import threading
import time
from datetime import datetime

from flask import current_app

from modules.routes_planilla_mensual import ensure_schema
from .scheduler_security import _log
from .scheduler_repository import (
    get_db_standalone,
    ensure_notify_schema,
    ensure_gastos_expiry_schema,
    ensure_om_notification_schema,
)
from .scheduler_notifications import (
    ensure_core_templates,
    ensure_gasto_templates,
    ensure_om_templates,
)
from .scheduler_services import (
    auto_close_expired_tasks,
    process_gastos_expiry,
    process_om_notifications,
    process_om_acciones_seguimiento,
    plan_notifications,
    dispatch_notifications,
    notify_overdue,
    send_daily_report,
)
from .scheduler_planilla_weekly import send_planilla_weekly_report

from .seedbilling_xml_job import process_seedbilling_facturas_recibidas

# ── Email-to-Task (Graph API) ──────────────────────────────────────
try:
    from modules.email_to_task.email_inbox_service import (
        process_incoming_emails,
        ensure_inbox_table,
        notify_unassigned_tickets,
    )
    _EMAIL_TO_TASK_ENABLED = True
except Exception as _e2t_err:
    _EMAIL_TO_TASK_ENABLED = False
    import logging as _logging
    _logging.getLogger(__name__).warning(
        "[email_to_task] No se pudo importar email_inbox_service: %s", _e2t_err
    )

_worker_started = False


def start_scheduler(app=None):
    global _worker_started

    if _worker_started:
        _log("warning", "Worker: start_scheduler() ignorado porque ya estaba iniciado.")
        return

    if app is None:
        try:
            app = current_app._get_current_object()
        except Exception:
            raise RuntimeError("start_scheduler() requiere app o contexto activo.")

    _worker_started = True

    def _run_tick(target_app, tick_label: str, run_om: bool = False):
        start = time.time()
        _log("info", "Worker: %s start", tick_label)

        try:
            try:
                _log("info", "Worker: Ejecutando cierre automático de tareas...")
                auto_close_expired_tasks()
                _log("info", "Worker: cierre automático de tareas OK")
            except Exception:
                target_app.logger.exception("Worker: auto_close_expired_tasks falló")

            try:
                cexp = get_db_standalone()
                try:
                    _log("info", "Worker: Ejecutando expiración de gastos tarjeta...")
                    process_gastos_expiry(cexp)
                    _log("info", "Worker: process_gastos_expiry OK")
                finally:
                    try:
                        cexp.close()
                    except Exception:
                        pass
            except Exception:
                target_app.logger.exception("Worker: process_gastos_expiry falló")

            if True:
                try:
                    com = get_db_standalone()
                    try:
                        _log("info", "Worker: Ejecutando notificaciones OM (job diario 08:00)...")
                        process_om_notifications(com)
                        _log("info", "Worker: process_om_notifications OK")
                    finally:
                        try:
                            com.close()
                        except Exception:
                            pass
                except Exception:
                    target_app.logger.exception("Worker: process_om_notifications falló")
            else:
                _log("debug", "Worker: process_om_notifications omitido en este ciclo")

            try:
                _log("info", "Worker: Ejecutando plan_notifications...")
                plan_notifications()
                _log("info", "Worker: plan_notifications OK")
            except Exception:
                target_app.logger.exception("Worker: plan_notifications falló")

            try:
                _log("info", "Worker: Ejecutando dispatch_notifications...")
                dispatch_notifications()
                _log("info", "Worker: dispatch_notifications OK")
            except Exception:
                target_app.logger.exception("Worker: dispatch_notifications falló")

            try:
                cacc = get_db_standalone()
                try:
                    _log("info", "Worker: Ejecutando seguimiento de acciones OM...")
                    process_om_acciones_seguimiento(cacc)
                    _log("info", "Worker: process_om_acciones_seguimiento OK")
                finally:
                    try:
                        cacc.close()
                    except Exception:
                        pass
            except Exception:
                target_app.logger.exception("Worker: process_om_acciones_seguimiento falló")

        except Exception:
            target_app.logger.exception("Worker: fallo general en %s", tick_label)

        elapsed = time.time() - start
        _log("info", "Worker: %s end elapsed=%.2fs", tick_label, elapsed)

    def _loop(target_app):
        with target_app.app_context():
            _log("info", "Worker: entrando al hilo de scheduler...")

            try:
                c0 = get_db_standalone()
                try:
                    _log("info", "Worker: bootstrap inicial - preparando esquemas y plantillas...")

                    #ensure_notify_schema(c0)
                    _log("info", "Worker: ensure_notify_schema OK")

                    #ensure_schema(c0)
                    _log("info", "Worker: ensure_schema OK")

                    #ensure_core_templates(c0)
                    _log("info", "Worker: ensure_core_templates OK")

                    #ensure_gasto_templates(c0)
                    _log("info", "Worker: ensure_gasto_templates OK")

                    #ensure_gastos_expiry_schema(c0)
                    _log("info", "Worker: ensure_gastos_expiry_schema OK")

                    ensure_om_notification_schema(c0)
                    _log("info", "Worker: ensure_om_notification_schema OK")

                    #ensure_om_templates(c0)
                    _log("info", "Worker: ensure_om_templates OK")

                    _log("info", "Worker: bootstrap inicial completado correctamente.")
                finally:
                    try:
                        c0.close()
                    except Exception:
                        pass
            except Exception:
                target_app.logger.exception("Worker: fallo en bootstrap inicial")
                return

            _log("info", "Worker: iniciado. Esperando 20s antes de la primera corrida...")
            time.sleep(20)

            _run_tick(target_app, "FIRST_RUN", run_om=False)

            last_overdue           = time.time()
            last_daily_date        = None
            last_om_date           = None
            last_seedbilling_slots = set()
            last_weekly_report_date = None   # ← control reporte semanal planilla
            last_email_poll        = 0.0     # ← control lectura correos soporteti (cada 2 min)
            last_unassigned_check  = 0.0     # ← control alerta tickets sin asignar +3h (cada 30 min)

            # Crear tabla email_tickets_inbox si no existe
            if _EMAIL_TO_TASK_ENABLED:
                try:
                    ensure_inbox_table()
                except Exception:
                    target_app.logger.exception("Worker: ensure_inbox_table falló")

            while True:
                cycle_start = time.time()
                now = datetime.now()
                tick_id = now.strftime("%Y-%m-%d %H:%M:%S")

                run_om_now = False
                _log("info", "Worker: OM programado para ejecución diaria de las 08:00")

                _run_tick(target_app, f"TICK {tick_id}", run_om=run_om_now)

                # ==================================================
                # SeedBilling XML compras - 08:00 y 14:00
                # ==================================================
                try:
                    seed_enabled = bool(target_app.config.get("SEEDBILLING_ENABLED", False))
                    seed_hours = target_app.config.get("SEEDBILLING_RUN_HOURS", (8, 14))
                    seed_hours = set(int(h) for h in seed_hours)

                    if seed_enabled and now.hour in seed_hours:
                        slot_key = f"{now.strftime('%Y-%m-%d')}:{now.hour:02d}"

                        if slot_key not in last_seedbilling_slots:
                            _log("info", "Worker: Ejecutando SeedBilling XML slot=%s", slot_key)

                            cseed = get_db_standalone()
                            try:
                                result = process_seedbilling_facturas_recibidas(cseed)
                                _log("info", "Worker: SeedBilling XML result=%s", result)
                            finally:
                                try:
                                    cseed.close()
                                except Exception:
                                    pass

                            last_seedbilling_slots.add(slot_key)
                        else:
                            _log("debug", "Worker: SeedBilling XML ya ejecutado slot=%s", slot_key)

                except Exception:
                    target_app.logger.exception("Worker: SeedBilling XML falló")

                # ==================================================
                # notify_overdue - cada 30 min
                # ==================================================
                now_ts = time.time()
                if now_ts - last_overdue >= 1800:
                    try:
                        _log("info", "Worker: Ejecutando notify_overdue...")
                        notify_overdue()
                        last_overdue = now_ts
                        _log("info", "Worker: notify_overdue OK")
                    except Exception:
                        target_app.logger.exception("Worker: notify_overdue falló")

                # ==================================================
                # Reporte diario - 07:30
                # ==================================================
                now2 = datetime.now()
                if now2.hour == 7 and now2.minute == 30:
                    if last_daily_date != now2.date():
                        try:
                            _log("info", "Worker: Ejecutando send_daily_report...")
                            send_daily_report()
                            last_daily_date = now2.date()
                            _log("info", "Worker: send_daily_report OK")
                        except Exception:
                            target_app.logger.exception("Worker: send_daily_report falló")

                # ==================================================
                # Reporte SEMANAL planilla - Viernes 17:00
                # ==================================================
                now3 = datetime.now()
                is_friday  = now3.weekday() == 4          # 0=lun … 4=vie
                is_1700    = now3.hour == 17 and now3.minute < 6  # ventana de 5 min
                week_key   = now3.strftime("%Y-W%W")              # ej. 2026-W23

                if is_friday and is_1700 and last_weekly_report_date != week_key:
                    try:
                        _log("info", "Worker: Ejecutando reporte semanal planilla [%s]...", week_key)
                        result = send_planilla_weekly_report(force=False)
                        last_weekly_report_date = week_key
                        _log("info", "Worker: reporte semanal planilla OK result=%s", result)
                    except Exception:
                        target_app.logger.exception("Worker: reporte semanal planilla falló")

                # ==================================================
                # Email-to-Task (soporteti@quimpac.com.ec) - cada 2 min
                # ==================================================
                now_ts2 = time.time()
                if _EMAIL_TO_TASK_ENABLED and (now_ts2 - last_email_poll >= 120):
                    try:
                        _log("info", "Worker: Ejecutando lectura de correos soporteti@...")
                        count = process_incoming_emails()
                        last_email_poll = now_ts2
                        if count:
                            _log("info", "Worker: email_to_task procesó %d correo(s) nuevos", count)
                        else:
                            _log("debug", "Worker: email_to_task — sin correos nuevos")
                    except Exception:
                        target_app.logger.exception("Worker: process_incoming_emails falló")

                # ==================================================
                # Alerta tickets sin asignar +3h - cada 30 min
                # ==================================================
                now_ts3 = time.time()
                if _EMAIL_TO_TASK_ENABLED and (now_ts3 - last_unassigned_check >= 1800):
                    try:
                        _log("info", "Worker: Verificando tickets sin asignar +3h...")
                        alertados = notify_unassigned_tickets()
                        last_unassigned_check = now_ts3
                        if alertados:
                            _log("info", "Worker: alerta enviada por %d ticket(s) sin asignar", alertados)
                        else:
                            _log("debug", "Worker: sin tickets con +3h sin asignar")
                    except Exception:
                        target_app.logger.exception("Worker: notify_unassigned_tickets falló")

                elapsed = time.time() - cycle_start
                sleep_s = max(5, 300 - elapsed)
                _log("info", "Worker: próximo ciclo en %.1fs", sleep_s)
                time.sleep(sleep_s)

    th = threading.Thread(
        target=_loop,
        args=(app,),
        daemon=True,
        name="NotifyWorker"
    )
    th.start()
    _log("info", "Worker: hilo lanzado correctamente.")
    return th
