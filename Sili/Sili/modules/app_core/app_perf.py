# modules/app_core/app_perf.py
# ==========================================================
# Hooks de performance por request.
# Registra tiempos totales y métricas de uso de DB.
# ==========================================================

import time
from flask import g, request


def register_perf_hooks(app):
    @app.before_request
    def _perf_start():
        # --------------------------------------------------
        # Marca el inicio del request y reinicia contadores.
        # --------------------------------------------------
        g._t0 = time.perf_counter()
        g.sql_count = 0
        g.sql_time = 0.0

    @app.after_request
    def _perf_end(resp):
        # --------------------------------------------------
        # Guarda el estado final del request y expone headers
        # de tiempo para diagnóstico desde el navegador.
        # --------------------------------------------------
        g.status_code = resp.status_code
        try:
            total_ms = (time.perf_counter() - getattr(g, "_t0", time.perf_counter())) * 1000.0
            resp.headers["Server-Timing"] = (
                f"app;dur={total_ms:.2f}, "
                
                f"db;dur={getattr(g, 'sql_time', 0.0):.2f};desc=\"sqlserver\", "
                f"queries;desc=\"{getattr(g, 'sql_count', 0)} sql\""
            )
            resp.headers["X-Process-Time-ms"] = f"{total_ms:.2f}"
        except Exception:
            pass
        return resp

    @app.teardown_request
    def _perf_log(exc):
        # --------------------------------------------------
        # Log compacto de performance al cerrar cada request.
        # --------------------------------------------------
        try:
            total_ms = (time.perf_counter() - getattr(g, "_t0", time.perf_counter())) * 1000.0
            app.logger.info(
                "PERF %s %s -> %s | %.2f ms | sql=%s (%.2f ms)",
                request.method,
                request.path,
                getattr(g, "status_code", "-"),
                total_ms,
                getattr(g, "sql_count", 0),
                getattr(g, "sql_time", 0.0),
            )
        except Exception:
            pass