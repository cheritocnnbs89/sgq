# modules/app_core/app_logging.py
# ==========================================================
# Configuración de logging general.
# Maneja nivel de consola, archivo rotativo y trazas
# de rutas registradas al iniciar la aplicación.
# ==========================================================

import os
import logging
from logging.handlers import RotatingFileHandler


def configure_app_logging(app):
    # ------------------------------------------------------
    # Ajusta el nivel de logging general de la aplicación.
    # ------------------------------------------------------
    app.logger.setLevel(logging.DEBUG)
    for h in app.logger.handlers:
        h.setLevel(logging.DEBUG)


def attach_file_logger(app):
    # ------------------------------------------------------
    # Agrega un logger a archivo rotativo si aún no existe.
    # ------------------------------------------------------
    try:
        log_dir = os.path.abspath(os.environ.get("LOG_DIR", "logs"))
        os.makedirs(log_dir, exist_ok=True)

        fh = RotatingFileHandler(
            os.path.join(log_dir, "app.log"),
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8"
        )
        fh.setLevel(logging.INFO)
        fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))

        if not any(isinstance(h, RotatingFileHandler) for h in app.logger.handlers):
            app.logger.addHandler(fh)
    except Exception:
        pass


def log_registered_routes(app):
    # ------------------------------------------------------
    # Recorre y registra todas las rutas cargadas.
    # Útil para soporte y diagnóstico de endpoints.
    # ------------------------------------------------------
    try:
        with app.app_context():
            rules = sorted([f"{r.endpoint} -> {r.rule}" for r in app.url_map.iter_rules()])
            for line in rules:
                app.logger.info("RUTA: %s", line)
    except Exception:
        pass