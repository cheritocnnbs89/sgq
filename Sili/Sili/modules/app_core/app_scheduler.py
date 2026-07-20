import os


def start_email_poller_if_enabled(app):
    """Inicia el hilo de lectura de correos soporteti@quimpac.com.ec (cada 2 min)."""
    try:
        from modules.scheduler_jobs import SCHEDULER_JOBS_ENABLED
        if not SCHEDULER_JOBS_ENABLED:
            print(">>> EmailPoller no arranca: SCHEDULER_JOBS_ENABLED=False")
            return

        # Solo arrancar en el proceso principal (no en el reloader de Flask)
        if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
            print(">>> EmailPoller no arranca: modo debug sin reloader principal")
            return

        from modules.email_to_task.email_poller import start_email_poller
        interval = int(os.environ.get("EMAIL_POLL_INTERVAL", "120"))
        start_email_poller(app, interval=interval)
        print(f">>> EmailPoller iniciado (intervalo={interval}s)")
    except Exception as e:
        print(f">>> ERROR EmailPoller: {e}")
        if hasattr(app, "logger"):
            app.logger.warning("EmailPoller no iniciado: %s", e)


def start_scheduler_if_enabled(app):
    try:
        print(">>> start_scheduler_if_enabled entró")
        print(">>> app.debug =", app.debug)
        print(">>> WERKZEUG_RUN_MAIN =", os.environ.get("WERKZEUG_RUN_MAIN"))

        from modules.scheduler_jobs import start_scheduler

        if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
            print(">>> Condición OK, arrancando scheduler...")
            try:
                th = start_scheduler(app)
            except TypeError:
                th = start_scheduler()

            print(">>> Scheduler retornó:", th)
        else:
            print(">>> Scheduler no arranca por condición debug/reloader")

    except Exception as e:
        app.logger.warning("Scheduler no iniciado (opcional): %s", e)
        print(">>> ERROR scheduler:", e)

    # ------------------------------------------------------
    # Scheduler propio del modulo Obligaciones -- independiente
    # del flag SCHEDULER_JOBS_ENABLED (ese flag solo gobierna
    # modules/scheduler_jobs.py). Respeta el mismo guard de
    # reloader que el bloque de arriba para no arrancar 2 threads
    # en modo debug.
    # ------------------------------------------------------
    if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        try:
            from modules.obligaciones.obligaciones_scheduler import start_obligaciones_scheduler
            start_obligaciones_scheduler(app)
            print(">>> Obligaciones scheduler arrancado")
        except Exception as e:
            app.logger.warning("Obligaciones scheduler no iniciado: %s", e)
            print(">>> ERROR Obligaciones scheduler:", e)