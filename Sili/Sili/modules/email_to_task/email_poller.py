# modules/email_to_task/email_poller.py
# -*- coding: utf-8 -*-
"""
Hilo independiente que lee correos de soporteti@quimpac.com.ec
cada POLL_INTERVAL segundos (default: 120 = 2 minutos).

Se inicia desde app_startup o directamente desde app.py.
No depende del scheduler principal.
"""

from __future__ import annotations

import logging
import os
import threading
import time

_log = logging.getLogger(__name__)
_poller_started = False


def start_email_poller(app, interval: int = 120):
    """
    Lanza un hilo daemon que ejecuta process_incoming_emails() cada `interval` segundos.
    Idempotente: si ya fue iniciado, no hace nada.
    """
    global _poller_started

    if _poller_started:
        _log.debug("[email_poller] Ya iniciado, ignorando segunda llamada.")
        return

    _poller_started = True

    def _loop():
        _log.info("[email_poller] Hilo iniciado. Intervalo=%ds", interval)

        # Esperar 30 segundos para que la app termine de arrancar
        time.sleep(30)

        # Crear tabla al arrancar
        with app.app_context():
            try:
                from modules.email_to_task.email_inbox_service import ensure_inbox_table
                ensure_inbox_table()
                _log.info("[email_poller] Tabla email_tickets_inbox verificada")
            except Exception as exc:
                _log.error("[email_poller] Error en ensure_inbox_table: %s", exc)

        while True:
            cycle_start = time.time()

            with app.app_context():
                try:
                    from modules.email_to_task.email_inbox_service import process_incoming_emails
                    count = process_incoming_emails()
                    if count:
                        _log.info("[email_poller] Procesados %d correo(s) nuevo(s)", count)
                    else:
                        _log.debug("[email_poller] Sin correos nuevos")
                except Exception as exc:
                    _log.error("[email_poller] Error en process_incoming_emails: %s", exc)

            elapsed = time.time() - cycle_start
            sleep_s = max(10, interval - elapsed)
            time.sleep(sleep_s)

    th = threading.Thread(target=_loop, daemon=True, name="EmailPoller")
    th.start()
    _log.info("[email_poller] Hilo EmailPoller lanzado.")
    return th
