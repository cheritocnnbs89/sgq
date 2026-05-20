import os


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