# -*- coding: utf-8 -*-
import threading
import time

import schedule

from . import obligaciones_repository as repo
from . import obligaciones_services as service
from . import obligaciones_notifications as notifications


def run_obligaciones_job(app):
    """Tarea A: marca atrasadas (estatus='atrasado', activa SIGUE=1).
    Tarea B: envia alertas por correo segun las notificaciones propias de
    cada frecuencia (oblig_frecuencia_notificaciones) y sus destinatarios
    configurados (oblig_notificacion_destinatarios), sin duplicar
    (oblig_alertas_enviadas). No falla si SMTP no esta configurado -- send_email
    ya degrada a log en ese caso."""
    with app.app_context():
        try:
            total_atrasadas = service.marcar_obligaciones_atrasadas()
            if total_atrasadas:
                app.logger.info("Obligaciones: %s marcada(s) como atrasada.", total_atrasadas)
        except Exception:
            app.logger.exception("Obligaciones: fallo Tarea A (marcar atrasadas)")

        try:
            pendientes = service.evaluar_alertas_pendientes()
            for p in pendientes:
                try:
                    obligacion = repo.get_by_id(p["obligacion_id"])
                    if not obligacion:
                        continue

                    destinatarios = p.get("destinatarios") or []
                    notifications.enviar_alerta(destinatarios, obligacion, p["tipo_alerta"])
                    service.registrar_alerta_enviada(
                        p["obligacion_id"], p["tipo_alerta"], p["periodo"]
                    )
                except Exception:
                    app.logger.exception(
                        "Obligaciones: fallo al enviar alerta obligacion_id=%s tipo=%s",
                        p.get("obligacion_id"), p.get("tipo_alerta"),
                    )
            if pendientes:
                app.logger.info("Obligaciones: %s alerta(s) evaluada(s)/enviada(s).", len(pendientes))
        except Exception:
            app.logger.exception("Obligaciones: fallo Tarea B (alertas)")


def _scheduler_loop(app):
    # 07:00 hora Ecuador (UTC-5, sin DST) = 12:00 UTC
    schedule.every().day.at("12:00").do(run_obligaciones_job, app=app)
    while True:
        try:
            schedule.run_pending()
        except Exception:
            app.logger.exception("Obligaciones: error en el loop del scheduler")
        time.sleep(60)


def start_obligaciones_scheduler(app):
    """Arranca en un thread propio, daemon, independiente del flag
    SCHEDULER_JOBS_ENABLED del scheduler principal de Sili."""
    t = threading.Thread(target=_scheduler_loop, args=(app,), daemon=True, name="obligaciones-scheduler")
    t.start()
    return t
