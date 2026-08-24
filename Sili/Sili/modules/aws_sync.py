"""
aws_sync.py — Sincronización bidireccional Flask ↔ AWS DynamoDB
para aprobación de gastos.

Push:
    Envía gastos nuevos o modificados a DynamoDB (aws_enviado=0).

Pull:
    Lee aprobaciones pendientes de sincronización y actualiza
    la base de datos local.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import mimetypes
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from time import perf_counter
from urllib.parse import urlsplit
from uuid import uuid4

import requests
from flask import current_app


# ============================================================
# Configuración
# ============================================================

AWS_API_URL = os.environ["AWS_API_URL"].strip().rstrip("/")
FLASK_TOKEN = os.environ["AWS_FLASK_TOKEN"].strip()

if not AWS_API_URL:
    raise RuntimeError("La variable AWS_API_URL está vacía.")

if not FLASK_TOKEN:
    raise RuntimeError("La variable AWS_FLASK_TOKEN está vacía.")

# ------------------------------------------------------------
# Interruptor de ambiente: QAS y producción comparten el mismo
# AWS_API_URL/AWS_FLASK_TOKEN (mismo API Gateway/DynamoDB), así que
# si QAS también corriera este sync empujaría gastos de prueba a la
# cola real de aprobaciones que ven los gerentes en el portal AWS.
# Por defecto queda habilitado (producción no necesita tocar nada);
# en el .env de QAS basta con AWS_SYNC_ENABLED=false.
# ------------------------------------------------------------
AWS_SYNC_ENABLED = (
    os.environ.get("AWS_SYNC_ENABLED", "1").strip().lower()
    not in ("0", "false", "no")
)

HEADERS = {
    "x-flask-token": FLASK_TOKEN,
    "Content-Type": "application/json",
}

# ------------------------------------------------------------
# Sincronización de autenticación de gerentes (aprobadores_auth).
# Endpoint y token DELIBERADAMENTE separados del de gastos. Ambas
# variables son opcionales: mientras AWS no tenga el endpoint listo,
# push_gerentes_auth_a_aws() se limita a no hacer nada (no rompe el
# resto del módulo, que sí es requerido).
# ------------------------------------------------------------
AWS_AUTH_API_URL = os.environ.get("AWS_AUTH_API_URL", "").strip().rstrip("/")
AWS_AUTH_TOKEN = os.environ.get("AWS_AUTH_TOKEN", "").strip()

# El nombre del header lo define el autorizador Lambda del lado AWS
# (quimpac-sync-auth-authorizer), no es arbitrario de este lado.
AUTH_HEADERS = {
    "x-flask-auth-token": AWS_AUTH_TOKEN,
    "Content-Type": "application/json",
}


# Roles de sistema (usuarios.rol) que en la práctica ejercen de jefe
# directo -- no necesariamente Gerente de Área -- y que necesitan
# entrar al portal para aprobar vouchers de taxi (Planificador).
# Reutiliza el nivel "ga" del portal, igual que Gerente de Área en
# gastos de tarjeta, ya que ambos son aprobación de un solo nivel.
#
# Lista abierta a propósito: un jefe directo puede tener cualquier rol
# de sistema (Coordinador, Analista, etc.), no solo "jefe" formalmente
# -- cada vez que aparezca uno nuevo que no entre al portal, agregarlo
# aquí. Si esto sigue creciendo, conviene cambiar a "cualquier usuario
# que sea jefe_id de al menos otro usuario activo" en vez de por rol.
ROLES_JEFE_DIRECTO = {"jefe", "coordinador"}


def _rol_aprobacion(rol_sistema: str) -> str | None:
    """
    Traduce el rol de sistema (usuarios.rol) al nivel de aprobación que
    espera la Lambda de AWS: GA / GG / GF. Usa la misma configuración de
    gastos_helpers ya usada en el resto de la app (rol_gg()/rol_gf()/roles
    GA), en vez de una lista de nombres literales aparte -- si alguien
    reconfigura quién es GG o GF desde Configuración de Gastos, este mapeo
    lo respeta automáticamente sin tocar código. Los roles en
    ROLES_JEFE_DIRECTO (jefes directos para vouchers de Planificador)
    mapean también a "GA".
    """
    from . import gastos_helpers as gh

    rol = (rol_sistema or "").strip().lower()
    if gh.es_rol_gg(rol):
        return "GG"
    if gh.es_rol_gf(rol):
        return "GF"
    if gh.es_rol_ga(rol):
        return "GA"
    if rol in ROLES_JEFE_DIRECTO:
        return "GA"
    return None


def _roles_gerente_auth() -> tuple[str, ...]:
    """Roles de sistema que hoy mapean a algún nivel de aprobación (GA/GG/GF)."""
    from . import gastos_helpers as gh

    roles = set(gh.roles_ga())
    roles.add(gh.rol_gg())
    roles.add(gh.rol_gf())
    roles |= ROLES_JEFE_DIRECTO
    return tuple(roles)


# ============================================================
# Configuración del archivo de log
# ============================================================

# aws_sync.py está en:
# SGQ\Sili\modules\aws_sync.py
#
# parents[2] corresponde a:
# SGQ
SGQ_DIR = Path(__file__).resolve().parents[2]

DEFAULT_LOG_FILE = SGQ_DIR / "logs" / "aws_sync.log"

LOG_FILE = Path(
    os.environ.get(
        "AWS_SYNC_LOG_FILE",
        str(DEFAULT_LOG_FILE),
    )
)

LOG_LEVEL = os.environ.get(
    "AWS_SYNC_LOG_LEVEL",
    "INFO",
).upper()


def _configure_logger() -> logging.Logger:
    sync_logger = logging.getLogger("aws_sync")
    sync_logger.setLevel(
        getattr(logging, LOG_LEVEL, logging.INFO)
    )

    # Evita duplicar líneas si el módulo se importa más de una vez.
    if any(
        getattr(handler, "_aws_sync_handler", False)
        for handler in sync_logger.handlers
    ):
        return sync_logger

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | "
        "PID=%(process)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    try:
        LOG_FILE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
            delay=True,
        )

        file_handler.setFormatter(formatter)
        file_handler.setLevel(
            getattr(logging, LOG_LEVEL, logging.INFO)
        )
        file_handler._aws_sync_handler = True

        sync_logger.addHandler(file_handler)
        sync_logger.propagate = False

    except Exception:
        # Si IIS no tiene permisos sobre la carpeta, al menos envía
        # los mensajes al registro general de la aplicación.
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        stream_handler._aws_sync_handler = True

        sync_logger.addHandler(stream_handler)
        sync_logger.propagate = True

    return sync_logger


logger = _configure_logger()

API_HOST = urlsplit(AWS_API_URL).netloc

logger.info(
    "[AWS SYNC][INIT] Módulo cargado | "
    "api_host=%s | token_configurado=%s | sync_enabled=%s | log=%s",
    API_HOST,
    bool(FLASK_TOKEN),
    AWS_SYNC_ENABLED,
    LOG_FILE,
)


# Usuario sistema usado como aprobador_por cuando viene de AWS.
USUARIO_AWS_ID = None


# ============================================================
# Utilidades
# ============================================================

def _new_run_id() -> str:
    """Identificador corto para relacionar las líneas de una ejecución."""
    return uuid4().hex[:10]


def _elapsed_ms(started_at: float) -> int:
    return int(
        (perf_counter() - started_at) * 1000
    )


def _response_excerpt(
    response: requests.Response,
    limit: int = 500,
) -> str:
    """
    Devuelve una parte segura de la respuesta HTTP.

    Nunca registra encabezados ni el token.
    """
    text = (response.text or "").replace(
        "\r",
        " ",
    ).replace(
        "\n",
        " ",
    )

    return text[:limit]


def _get_db():
    from .db import get_db
    return get_db()


def _resolve_sistema_aws_id(conn):
    """
    Devuelve el ID del usuario sistema_aws en la tabla usuarios.
    """
    row = conn.execute(
        """
        SELECT id
        FROM usuarios
        WHERE username = 'sistema_aws'
        """
    ).fetchone()

    return row[0] if row else None


def _tipo_gasto(g: dict) -> str:
    if int(g.get("es_caja_chica") or 0):
        return "caja_chica"

    if int(g.get("reembolso_vendedor") or 0):
        return "reembolso"

    return "tarjeta_credito"


def _get_aprobador_email(
    conn,
    campo: str,
    dep_id=None,
    user_id=None,
) -> str:
    """Resuelve el correo del aprobador según el nivel."""

    from .routes_gatos_mail_notify import (
        _gerente_email_por_jerarquia,
    )

    if campo == "ga":
        email = (
            _gerente_email_por_jerarquia(
                conn,
                user_id,
            )
            or ""
        )

        if not email and user_id:
            # Si el propio usuario es gerente, se aprueba a sí mismo.
            row = conn.execute(
                """
                SELECT email
                FROM usuarios
                WHERE id = ?
                  AND LOWER(rol) LIKE '%gerente%'
                  AND COALESCE(disabled, 0) = 0
                """,
                (user_id,),
            ).fetchone()

            if row:
                email = (row[0] or "").strip()

        return email

    if campo in ("gf", "gg"):
        rol = (
            "gerente financiero"
            if campo == "gf"
            else "gerente general"
        )

        row = conn.execute(
            """
            SELECT TOP 1 email
            FROM usuarios
            WHERE LOWER(rol) = ?
              AND COALESCE(disabled, 0) = 0
              AND email IS NOT NULL
            """,
            (rol,),
        ).fetchone()

        return (row[0] or "").strip() if row else ""

    return ""


# ============================================================
# PUSH — Flask → DynamoDB
# ============================================================

# Límite prudente por archivo: el techo real no es el de API Gateway
# (10MB) sino el de invocación síncrona de Lambda (6MB), y base64 añade
# ~33% de más -- 4MB de archivo crudo ya deja el body en ~5.3MB.
MAX_ADJUNTO_BYTES = 4 * 1024 * 1024


def _push_adjuntos_gasto(conn, run_id: str, local_id, gasto_id_aws: str) -> None:
    """
    Envía a AWS (endpoint /sync/adjunto, mismo x-flask-token que /sync/push)
    los archivos adjuntos de un gasto recién sincronizado, para que el
    portal de aprobación pueda mostrarlos -- el servidor Flask no es
    accesible desde fuera de la red, así que el archivo no puede quedar
    solo como una URL a este servidor.

    Best-effort: nunca lanza, nunca bloquea el push del gasto en sí.
    """
    try:
        filenames = []

        rows = conn.execute(
            "SELECT filename FROM gastos_tarjeta_archivos WHERE gasto_id = ? ORDER BY id",
            (local_id,),
        ).fetchall()
        filenames.extend(
            (r["filename"] or "").strip()
            for r in rows
            if (r["filename"] or "").strip()
        )

        legacy_row = conn.execute(
            "SELECT archivo FROM gastos_tarjeta WHERE id = ?",
            (local_id,),
        ).fetchone()
        legacy = (legacy_row["archivo"] or "").strip() if legacy_row else ""
        if legacy and legacy not in filenames:
            filenames.insert(0, legacy)

        if not filenames:
            return

        upload_dir = Path(current_app.root_path) / "static" / "uploads"

        for filename in filenames:
            file_path = upload_dir / filename

            if not file_path.is_file():
                logger.warning(
                    "[AWS SYNC][PUSH_ADJUNTO][SKIP] run_id=%s | gasto_id=%s | "
                    "archivo=%s | motivo=no_existe_en_disco",
                    run_id, gasto_id_aws, filename,
                )
                continue

            size = file_path.stat().st_size
            if size > MAX_ADJUNTO_BYTES:
                logger.warning(
                    "[AWS SYNC][PUSH_ADJUNTO][SKIP] run_id=%s | gasto_id=%s | "
                    "archivo=%s | motivo=demasiado_grande | bytes=%d",
                    run_id, gasto_id_aws, filename, size,
                )
                continue

            content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            data_b64 = base64.b64encode(file_path.read_bytes()).decode("ascii")

            try:
                res = requests.post(
                    f"{AWS_API_URL}/sync/adjunto",
                    json={
                        "gasto_id": gasto_id_aws,
                        "filename": filename,
                        "content_type": content_type,
                        "data_base64": data_b64,
                    },
                    headers=HEADERS,
                    timeout=60,
                )
                logger.info(
                    "[AWS SYNC][PUSH_ADJUNTO] run_id=%s | gasto_id=%s | "
                    "archivo=%s | bytes=%d | status=%s",
                    run_id, gasto_id_aws, filename, size, res.status_code,
                )
            except requests.RequestException as exc:
                logger.warning(
                    "[AWS SYNC][PUSH_ADJUNTO][ERROR] run_id=%s | gasto_id=%s | "
                    "archivo=%s | error=%s",
                    run_id, gasto_id_aws, filename, exc,
                )

    except Exception as exc:
        logger.warning(
            "[AWS SYNC][PUSH_ADJUNTO][ERROR] run_id=%s | local_id=%s | error=%s",
            run_id, local_id, exc,
        )


def push_gastos_a_aws(app=None):
    """
    Envía a DynamoDB los gastos con aws_enviado=0.

    Esta función puede ser llamada desde el scheduler cada N minutos.
    """

    if not AWS_SYNC_ENABLED:
        logger.debug(
            "[AWS SYNC][PUSH][SKIP] AWS_SYNC_ENABLED=0 (ambiente sin sync a AWS)"
        )
        return

    run_id = _new_run_id()
    started_at = perf_counter()

    ctx = app.app_context() if app else None

    if ctx:
        ctx.push()

    logger.info(
        "[AWS SYNC][PUSH][START] run_id=%s",
        run_id,
    )

    try:
        conn = _get_db()

        rows = conn.execute(
            """
            SELECT
                g.id,
                g.fecha,
                g.motivo,
                g.total_con_iva,
                g.es_caja_chica,
                g.reembolso_vendedor,
                g.ga_aprobado,
                g.gf_aprobado,
                g.gg_aprobado,
                g.usuario_id,
                u.nombre_completo AS usuario_nombre,
                u.email AS usuario_email,
                u.departamento_id AS dep_id
            FROM gastos_tarjeta g
            LEFT JOIN usuarios u
                ON u.id = g.usuario_id
            WHERE COALESCE(g.aws_enviado, 0) = 0
              AND g.sap_contabilizacion IS NULL
              AND (
                  COALESCE(g.es_caja_chica, 0) = 1
                  OR COALESCE(g.reembolso_vendedor, 0) = 1
                  OR COALESCE(g.coord_revisado, 0) = 1
              )
            """
        ).fetchall()

        total_candidatos = len(rows)

        logger.info(
            "[AWS SYNC][PUSH][DB] run_id=%s | "
            "candidatos=%d",
            run_id,
            total_candidatos,
        )

        if not rows:
            logger.info(
                "[AWS SYNC][PUSH][EMPTY] run_id=%s | "
                "sin gastos nuevos",
                run_id,
            )
            return

        gastos_payload = []
        ids_enviados = []
        omitidos_sin_ga = 0

        ga_cache = {}

        gf_email = _get_aprobador_email(
            conn,
            "gf",
        )

        gg_email = _get_aprobador_email(
            conn,
            "gg",
        )

        for g in rows:
            tipo = _tipo_gasto(dict(g))
            gasto_id = f"{tipo}#{g['id']}"

            uid = g["usuario_id"]

            if uid not in ga_cache:
                ga_cache[uid] = _get_aprobador_email(
                    conn,
                    "ga",
                    user_id=uid,
                )

            ga_email = ga_cache[uid]

            if not ga_email:
                omitidos_sin_ga += 1

                logger.warning(
                    "[AWS SYNC][PUSH][SKIP] run_id=%s | "
                    "gasto_id=%s | usuario_id=%s | "
                    "motivo=sin_aprobador_ga",
                    run_id,
                    g["id"],
                    uid,
                )
                continue

            gastos_payload.append(
                {
                    "gasto_id": gasto_id,
                    "tipo": tipo,
                    "local_id": str(g["id"]),
                    "fecha": str(g["fecha"] or ""),
                    "descripcion": g["motivo"] or "",
                    "monto": str(g["total_con_iva"] or 0),
                    "usuario_nombre": (
                        g["usuario_nombre"] or ""
                    ),
                    "usuario_email": (
                        g["usuario_email"] or ""
                    ),
                    "ga_aprobador_email": ga_email,
                    "gf_aprobador_email": gf_email,
                    "gg_aprobador_email": gg_email,
                    "ga_aprobado": int(
                        g["ga_aprobado"] or 0
                    ),
                    "gf_aprobado": int(
                        g["gf_aprobado"] or 0
                    ),
                    "gg_aprobado": int(
                        g["gg_aprobado"] or 0
                    ),
                    "flask_sincronizado": "true",
                }
            )

            ids_enviados.append(g["id"])

        if not gastos_payload:
            logger.warning(
                "[AWS SYNC][PUSH][NO_PAYLOAD] run_id=%s | "
                "candidatos=%d | omitidos_sin_ga=%d",
                run_id,
                total_candidatos,
                omitidos_sin_ga,
            )
            return

        logger.info(
            "[AWS SYNC][PUSH][HTTP] run_id=%s | "
            "endpoint=/sync/push | registros=%d",
            run_id,
            len(gastos_payload),
        )

        http_started_at = perf_counter()

        res = requests.post(
            f"{AWS_API_URL}/sync/push",
            json={
                "gastos": gastos_payload,
            },
            headers=HEADERS,
            timeout=30,
        )

        http_ms = _elapsed_ms(http_started_at)

        logger.info(
            "[AWS SYNC][PUSH][HTTP_RESPONSE] run_id=%s | "
            "status=%s | duration_ms=%d",
            run_id,
            res.status_code,
            http_ms,
        )

        if res.status_code == 200:
            placeholders = ",".join(
                "?"
                for _ in ids_enviados
            )

            conn.execute(
                f"""
                UPDATE gastos_tarjeta
                SET aws_enviado = 1
                WHERE id IN ({placeholders})
                """,
                ids_enviados,
            )

            conn.commit()

            logger.info(
                "[AWS SYNC][PUSH][OK] run_id=%s | "
                "enviados=%d | omitidos_sin_ga=%d | "
                "ids=%s",
                run_id,
                len(ids_enviados),
                omitidos_sin_ga,
                ",".join(
                    str(item_id)
                    for item_id in ids_enviados
                ),
            )

            for item in gastos_payload:
                _push_adjuntos_gasto(
                    conn,
                    run_id,
                    int(item["local_id"]),
                    item["gasto_id"],
                )

        else:
            logger.error(
                "[AWS SYNC][PUSH][HTTP_ERROR] run_id=%s | "
                "status=%s | response=%s",
                run_id,
                res.status_code,
                _response_excerpt(res),
            )

    except requests.Timeout:
        logger.exception(
            "[AWS SYNC][PUSH][TIMEOUT] run_id=%s | "
            "timeout=30s",
            run_id,
        )

    except requests.RequestException as exc:
        logger.exception(
            "[AWS SYNC][PUSH][REQUEST_ERROR] run_id=%s | "
            "error=%s",
            run_id,
            exc,
        )

    except Exception as exc:
        logger.exception(
            "[AWS SYNC][PUSH][ERROR] run_id=%s | "
            "error=%s",
            run_id,
            exc,
        )

    finally:
        logger.info(
            "[AWS SYNC][PUSH][END] run_id=%s | "
            "duration_ms=%d",
            run_id,
            _elapsed_ms(started_at),
        )

        if ctx:
            ctx.pop()


# ============================================================
# PUSH VOUCHER TAXI — Flask → DynamoDB (Planificador)
# ============================================================

def push_vouchers_taxi_a_aws(app=None):
    """
    Envía a DynamoDB los vouchers de taxi (Planificador) pendientes de
    aprobación del jefe directo, para que aparezcan en el portal móvil.

    Reutiliza la misma tabla (gastos_aprobacion) que gastos de tarjeta,
    con gasto_id="voucher_taxi#<id>" / tipo="Voucher", y el nivel "ga"
    del portal (aprobación de un solo nivel, igual que jefe directo).
    A diferencia de un gasto, un voucher no tiene monto en esta etapa
    -- el costo se liquida después -- así que se manda numero_vouchers
    en vez de monto.
    """

    if not AWS_SYNC_ENABLED:
        logger.debug(
            "[AWS SYNC][PUSH_VOUCHER][SKIP] AWS_SYNC_ENABLED=0 (ambiente sin sync a AWS)"
        )
        return

    run_id = _new_run_id()
    started_at = perf_counter()

    ctx = app.app_context() if app else None

    if ctx:
        ctx.push()

    logger.info(
        "[AWS SYNC][PUSH_VOUCHER][START] run_id=%s",
        run_id,
    )

    try:
        conn = _get_db()

        rows = conn.execute(
            """
            SELECT
                s.id, s.fecha, s.descripcion, s.lugar_destino,
                s.punto_salida, s.punto_destino, s.numero_vouchers,
                s.solicitante_id, s.solicitante_nombre,
                s.gerente_id, s.gerente_nombre,
                u.email AS solicitante_email,
                jefe.email AS jefe_email
            FROM planificador_solicitudes s
            LEFT JOIN usuarios u ON u.id = s.solicitante_id
            LEFT JOIN usuarios jefe ON jefe.id = s.gerente_id
            WHERE s.activo = 1
              AND s.tipo = 'Voucher'
              AND s.estado = 'PENDIENTE_APROBACION_JEFE'
              AND COALESCE(s.aws_enviado, 0) = 0
            """
        ).fetchall()

        total_candidatos = len(rows)

        logger.info(
            "[AWS SYNC][PUSH_VOUCHER][DB] run_id=%s | candidatos=%d",
            run_id,
            total_candidatos,
        )

        if not rows:
            logger.info(
                "[AWS SYNC][PUSH_VOUCHER][EMPTY] run_id=%s | sin vouchers nuevos",
                run_id,
            )
            return

        payload = []
        ids_enviados = []
        omitidos_sin_jefe = 0

        for s in rows:
            jefe_email = (s["jefe_email"] or "").strip()

            if not jefe_email:
                omitidos_sin_jefe += 1

                logger.warning(
                    "[AWS SYNC][PUSH_VOUCHER][SKIP] run_id=%s | "
                    "solicitud_id=%s | motivo=jefe_sin_email",
                    run_id,
                    s["id"],
                )
                continue

            destino = s["lugar_destino"] or " / ".join(
                p for p in (s["punto_salida"], s["punto_destino"]) if p
            )

            payload.append(
                {
                    "gasto_id": f"voucher_taxi#{s['id']}",
                    "tipo": "Voucher",
                    "local_id": str(s["id"]),
                    "fecha": str(s["fecha"] or ""),
                    "descripcion": s["descripcion"] or "",
                    "lugar": destino or "",
                    "numero_vouchers": int(s["numero_vouchers"] or 0),
                    "usuario_nombre": s["solicitante_nombre"] or "",
                    "usuario_email": s["solicitante_email"] or "",
                    "ga_aprobador_email": jefe_email,
                    "ga_aprobado": 0,
                    "flask_sincronizado": "true",
                }
            )

            ids_enviados.append(s["id"])

        if not payload:
            logger.warning(
                "[AWS SYNC][PUSH_VOUCHER][NO_PAYLOAD] run_id=%s | "
                "candidatos=%d | omitidos_sin_jefe=%d",
                run_id,
                total_candidatos,
                omitidos_sin_jefe,
            )
            return

        logger.info(
            "[AWS SYNC][PUSH_VOUCHER][HTTP] run_id=%s | "
            "endpoint=/sync/push | registros=%d",
            run_id,
            len(payload),
        )

        http_started_at = perf_counter()

        res = requests.post(
            f"{AWS_API_URL}/sync/push",
            json={
                "gastos": payload,
            },
            headers=HEADERS,
            timeout=30,
        )

        http_ms = _elapsed_ms(http_started_at)

        logger.info(
            "[AWS SYNC][PUSH_VOUCHER][HTTP_RESPONSE] run_id=%s | "
            "status=%s | duration_ms=%d",
            run_id,
            res.status_code,
            http_ms,
        )

        if res.status_code == 200:
            placeholders = ",".join(
                "?"
                for _ in ids_enviados
            )

            conn.execute(
                f"""
                UPDATE planificador_solicitudes
                SET aws_enviado = 1
                WHERE id IN ({placeholders})
                """,
                ids_enviados,
            )

            conn.commit()

            logger.info(
                "[AWS SYNC][PUSH_VOUCHER][OK] run_id=%s | "
                "enviados=%d | omitidos_sin_jefe=%d | ids=%s",
                run_id,
                len(ids_enviados),
                omitidos_sin_jefe,
                ",".join(
                    str(item_id)
                    for item_id in ids_enviados
                ),
            )

        else:
            logger.error(
                "[AWS SYNC][PUSH_VOUCHER][HTTP_ERROR] run_id=%s | "
                "status=%s | response=%s",
                run_id,
                res.status_code,
                _response_excerpt(res),
            )

    except requests.Timeout:
        logger.exception(
            "[AWS SYNC][PUSH_VOUCHER][TIMEOUT] run_id=%s | "
            "timeout=30s",
            run_id,
        )

    except requests.RequestException as exc:
        logger.exception(
            "[AWS SYNC][PUSH_VOUCHER][REQUEST_ERROR] run_id=%s | "
            "error=%s",
            run_id,
            exc,
        )

    except Exception as exc:
        logger.exception(
            "[AWS SYNC][PUSH_VOUCHER][ERROR] run_id=%s | "
            "error=%s",
            run_id,
            exc,
        )

    finally:
        logger.info(
            "[AWS SYNC][PUSH_VOUCHER][END] run_id=%s | "
            "duration_ms=%d",
            run_id,
            _elapsed_ms(started_at),
        )

        if ctx:
            ctx.pop()


# ============================================================
# PUSH AUTH — Flask → DynamoDB (aprobadores_auth)
# ============================================================

def push_gerentes_auth_a_aws(app=None):
    """
    Envía a DynamoDB (vía API Gateway, endpoint/token separados del de
    gastos) el email, nombre, rol, estado activo y hash de clave (scrypt,
    generado por Werkzeug) de los usuarios con rol gerente.

    Reglas de seguridad no negociables:
    - Nunca se envía una clave sin hashear. Si un usuario todavía tiene
      la clave en texto plano (no ha iniciado sesión desde que se le
      asignó), simplemente se omite hasta que el login normal la hashee.
    - Solo se reenvía cuando el hash, el rol o el estado activo cambiaron
      desde el último envío exitoso (comparando un hash de ese estado).
    - Nunca se registra en el log la clave, el hash ni el token.
    """
    if not AWS_SYNC_ENABLED:
        logger.debug(
            "[AWS SYNC][AUTH_PUSH][SKIP] AWS_SYNC_ENABLED=0 (ambiente sin sync a AWS)"
        )
        return

    if not AWS_AUTH_API_URL or not AWS_AUTH_TOKEN:
        logger.debug(
            "[AWS SYNC][AUTH_PUSH][DISABLED] AWS_AUTH_API_URL/AWS_AUTH_TOKEN no configurados todavía."
        )
        return

    from .auth.auth_security import esta_hasheado

    run_id = _new_run_id()
    started_at = perf_counter()

    ctx = app.app_context() if app else None
    if ctx:
        ctx.push()

    logger.info("[AWS SYNC][AUTH_PUSH][START] run_id=%s", run_id)

    try:
        conn = _get_db()

        roles_gerente_auth = _roles_gerente_auth()

        try:
            rows = conn.execute(
                f"""
                SELECT id, username, email, nombre_completo, rol,
                       COALESCE(disabled, 0) AS disabled, password,
                       auth_aws_hash_enviado
                FROM usuarios
                WHERE LOWER(LTRIM(RTRIM(rol))) IN ({",".join("?" for _ in roles_gerente_auth)})
                """,
                roles_gerente_auth,
            ).fetchall()
        except Exception:
            logger.exception(
                "[AWS SYNC][AUTH_PUSH][SCHEMA_ERROR] run_id=%s | "
                "falta la columna usuarios.auth_aws_hash_enviado (DDL pendiente)",
                run_id,
            )
            return

        total_candidatos = len(rows)
        logger.info(
            "[AWS SYNC][AUTH_PUSH][DB] run_id=%s | candidatos=%d",
            run_id,
            total_candidatos,
        )

        if not rows:
            logger.info("[AWS SYNC][AUTH_PUSH][EMPTY] run_id=%s", run_id)
            return

        payload = []
        ids_enviados = []
        hashes_por_id = {}
        omitidos_sin_hash = 0
        omitidos_sin_email = 0

        for u in rows:
            password = u["password"] or ""

            if not esta_hasheado(password):
                omitidos_sin_hash += 1
                logger.warning(
                    "[AWS SYNC][AUTH_PUSH][SKIP] run_id=%s | usuario_id=%s | "
                    "motivo=clave_sin_hashear",
                    run_id,
                    u["id"],
                )
                continue

            email = (u["email"] or "").strip()
            if not email:
                omitidos_sin_email += 1
                logger.warning(
                    "[AWS SYNC][AUTH_PUSH][SKIP] run_id=%s | usuario_id=%s | "
                    "motivo=sin_email",
                    run_id,
                    u["id"],
                )
                continue

            rol_aprobacion = _rol_aprobacion(u["rol"])
            if not rol_aprobacion:
                # No calza con GA/GG/GF configurados actualmente (p.ej. quedó
                # en la lista por una configuración anterior). No se envía.
                logger.warning(
                    "[AWS SYNC][AUTH_PUSH][SKIP] run_id=%s | usuario_id=%s | "
                    "motivo=sin_nivel_aprobacion",
                    run_id,
                    u["id"],
                )
                continue

            activo = 0 if int(u["disabled"] or 0) else 1
            hash_type = password.split(":")[0]
            nombre = u["nombre_completo"] or u["username"] or ""

            # Incluye email y nombre además de password/rol/activo: la tabla
            # de AWS está indexada por email, así que un cambio de correo
            # también debe disparar un reenvío (si no, quedaría desincronizado
            # en silencio -- el hash de antes seguiría "coincidiendo").
            estado_actual = hashlib.sha256(
                f"{email}|{nombre}|{password}|{rol_aprobacion}|{activo}".encode("utf-8")
            ).hexdigest()

            if estado_actual == (u["auth_aws_hash_enviado"] or ""):
                continue

            payload.append(
                {
                    "email": email,
                    "nombre": nombre,
                    "rol": rol_aprobacion,
                    "activo": activo,
                    "password_hash": password,
                    "hash_type": hash_type,
                }
            )
            ids_enviados.append(u["id"])
            hashes_por_id[u["id"]] = estado_actual

        if not payload:
            logger.info(
                "[AWS SYNC][AUTH_PUSH][NO_PAYLOAD] run_id=%s | candidatos=%d | "
                "omitidos_sin_hash=%d | omitidos_sin_email=%d",
                run_id,
                total_candidatos,
                omitidos_sin_hash,
                omitidos_sin_email,
            )
            return

        logger.info(
            "[AWS SYNC][AUTH_PUSH][HTTP] run_id=%s | endpoint=/sync/auth/push | registros=%d",
            run_id,
            len(payload),
        )

        http_started_at = perf_counter()

        res = requests.post(
            f"{AWS_AUTH_API_URL}/sync/auth/push",
            json={"aprobadores": payload},
            headers=AUTH_HEADERS,
            timeout=30,
        )

        http_ms = _elapsed_ms(http_started_at)

        logger.info(
            "[AWS SYNC][AUTH_PUSH][HTTP_RESPONSE] run_id=%s | status=%s | duration_ms=%d",
            run_id,
            res.status_code,
            http_ms,
        )

        if res.status_code == 200:
            for uid in ids_enviados:
                conn.execute(
                    "UPDATE usuarios SET auth_aws_hash_enviado = ? WHERE id = ?",
                    (hashes_por_id[uid], uid),
                )

            conn.commit()

            logger.info(
                "[AWS SYNC][AUTH_PUSH][OK] run_id=%s | enviados=%d | "
                "omitidos_sin_hash=%d | omitidos_sin_email=%d",
                run_id,
                len(ids_enviados),
                omitidos_sin_hash,
                omitidos_sin_email,
            )
        else:
            logger.error(
                "[AWS SYNC][AUTH_PUSH][HTTP_ERROR] run_id=%s | status=%s | response=%s",
                run_id,
                res.status_code,
                _response_excerpt(res),
            )

    except requests.Timeout:
        logger.exception(
            "[AWS SYNC][AUTH_PUSH][TIMEOUT] run_id=%s | timeout=30s",
            run_id,
        )

    except requests.RequestException as exc:
        logger.exception(
            "[AWS SYNC][AUTH_PUSH][REQUEST_ERROR] run_id=%s | error=%s",
            run_id,
            exc,
        )

    except Exception as exc:
        logger.exception(
            "[AWS SYNC][AUTH_PUSH][ERROR] run_id=%s | error=%s",
            run_id,
            exc,
        )

    finally:
        logger.info(
            "[AWS SYNC][AUTH_PUSH][END] run_id=%s | duration_ms=%d",
            run_id,
            _elapsed_ms(started_at),
        )

        if ctx:
            ctx.pop()


# ============================================================
# PULL — DynamoDB → Flask
# ============================================================

def _pull_gasto_tarjeta_item(conn, g, local_id, sys_id, now_str, run_id):
    """
    Aplica una fila del portal AWS sobre gastos_tarjeta.

    La presencia de "<nivel>_at" (no solo "<nivel>_aprobado"=1) es la
    señal de que ese nivel ya se decidió en AWS: "<nivel>_aprobado"=0
    con "<nivel>_at" presente significa rechazo. GA nunca rechaza --
    eso ya está bloqueado del lado del Lambda gastos-aprobar -- así
    que ahí solo se mira "ga_aprobado"=1, igual que antes.

    Devuelve "updated", "no_change" o "not_found".
    """
    row = conn.execute(
        """
        SELECT ga_aprobado, gf_aprobado, gg_aprobado,
               COALESCE(ga_aws_sync, 0) AS ga_aws_sync,
               COALESCE(gf_aws_sync, 0) AS gf_aws_sync,
               COALESCE(gg_aws_sync, 0) AS gg_aws_sync
        FROM gastos_tarjeta
        WHERE id = ?
        """,
        (local_id,),
    ).fetchone()

    if not row:
        logger.warning(
            "[AWS SYNC][PULL][NOT_FOUND] run_id=%s | tabla=gastos_tarjeta | local_id=%s",
            run_id, local_id,
        )
        return "not_found"

    updates, params, niveles, rechazos = [], [], [], []

    if int(g.get("ga_aprobado") or 0) and not row["ga_aws_sync"]:
        updates += [
            "ga_aprobado=1", "ga_aprobado_por=?", "ga_aprobado_at=?",
            "ga_aprobado_origen='aws'", "ga_aws_sync=1",
        ]
        params += [sys_id, g.get("ga_at") or now_str]
        niveles.append("GA")

    if g.get("gf_at") and not row["gf_aws_sync"] and not int(g.get("gg_aprobado") or 0):
        if int(g.get("gf_aprobado") or 0):
            updates += [
                "gf_aprobado=1", "gf_aprobado_por=?", "gf_aprobado_at=?",
                "gf_aprobado_origen='aws'", "gf_aws_sync=1",
            ]
            params += [sys_id, g.get("gf_at") or now_str]
        else:
            updates += ["gf_aws_sync=1"]
            rechazos.append(("GF", g.get("gf_obs") or ""))
        niveles.append("GF")

    if g.get("gg_at") and not row["gg_aws_sync"]:
        if int(g.get("gg_aprobado") or 0):
            updates += [
                "gg_aprobado=1", "gg_aprobado_por=?", "gg_aprobado_at=?",
                "gg_aprobado_origen='aws'", "gg_aws_sync=1",
            ]
            params += [sys_id, g.get("gg_at") or now_str]
        else:
            updates += ["gg_aws_sync=1"]
            rechazos.append(("GG", g.get("gg_obs") or ""))
        niveles.append("GG")

    if not updates:
        logger.info(
            "[AWS SYNC][PULL][NO_CHANGE] run_id=%s | tabla=gastos_tarjeta | local_id=%s",
            run_id, local_id,
        )
        return "no_change"

    params.append(local_id)
    conn.execute(
        f"UPDATE gastos_tarjeta SET {', '.join(updates)} WHERE id = ?",
        params,
    )
    conn.commit()

    for nivel, comentario in rechazos:
        try:
            from modules.scheduler.scheduler_notifications import enqueue_gasto_rejected_gg
            enqueue_gasto_rejected_gg(
                conn, gasto_id=local_id, by_user_id=sys_id, comentario=comentario,
            )
        except Exception:
            logger.exception(
                "[AWS SYNC][PULL][REJECT_NOTIFY_ERROR] run_id=%s | tabla=gastos_tarjeta | "
                "local_id=%s | nivel=%s",
                run_id, local_id, nivel,
            )

    logger.info(
        "[AWS SYNC][PULL][UPDATED] run_id=%s | tabla=gastos_tarjeta | local_id=%s | niveles=%s",
        run_id, local_id, ",".join(niveles),
    )
    return "updated"


def _pull_voucher_item(conn, g, local_id, sys_id, now_str, run_id):
    """
    Aplica una fila "voucher_taxi#<id>" del portal AWS sobre
    planificador_solicitudes, reutilizando las mismas funciones de
    aprobación/rechazo + notificaciones que usa la ruta en-app del
    jefe directo (aprobar_jefe_voucher / rechazar_jefe_voucher +
    notif_voucher_*), para que el resultado sea idéntico sin importar
    si la decisión vino de Flask o del portal móvil.

    Devuelve "updated", "no_change" o "not_found".
    """
    row = conn.execute(
        """
        SELECT estado, solicitante_id, solicitante_nombre, area_solicitante,
               fecha, descripcion, COALESCE(ga_aws_sync, 0) AS ga_aws_sync
        FROM planificador_solicitudes
        WHERE id = ? AND tipo = 'Voucher'
        """,
        (local_id,),
    ).fetchone()

    if not row:
        logger.warning(
            "[AWS SYNC][PULL][NOT_FOUND] run_id=%s | tabla=planificador_solicitudes | local_id=%s",
            run_id, local_id,
        )
        return "not_found"

    if (
        row["ga_aws_sync"]
        or row["estado"] != "PENDIENTE_APROBACION_JEFE"
        or not g.get("ga_at")
    ):
        return "no_change"

    obs = g.get("ga_obs") or ""
    aprobado = bool(int(g.get("ga_aprobado") or 0))

    from modules.planificador import planificador_repository as prepo
    from modules.planificador import planificador_notifications as pnotif

    if aprobado:
        prepo.aprobar_jefe_voucher(local_id, sys_id, "Sistema (AWS)", obs)
        try:
            pnotif.notif_voucher_aprobada_solicitante(
                local_id, row["area_solicitante"], str(row["fecha"]),
                row["descripcion"], row["solicitante_id"], row["solicitante_nombre"],
                "Sistema (AWS)",
            )
            pnotif.notif_voucher_pendiente_entrega(
                local_id, row["area_solicitante"], str(row["fecha"]),
                row["descripcion"], row["solicitante_nombre"], "Sistema (AWS)",
            )
        except Exception:
            logger.exception(
                "[AWS SYNC][PULL][NOTIFY_ERROR] run_id=%s | tabla=planificador_solicitudes | "
                "local_id=%s | accion=aprobado",
                run_id, local_id,
            )
    else:
        prepo.rechazar_jefe_voucher(local_id, sys_id, "Sistema (AWS)", obs)
        try:
            pnotif.notif_voucher_rechazada(
                local_id, row["area_solicitante"], str(row["fecha"]), obs,
                row["solicitante_nombre"], row["solicitante_id"], "Sistema (AWS)",
            )
        except Exception:
            logger.exception(
                "[AWS SYNC][PULL][NOTIFY_ERROR] run_id=%s | tabla=planificador_solicitudes | "
                "local_id=%s | accion=rechazado",
                run_id, local_id,
            )

    conn.execute(
        "UPDATE planificador_solicitudes SET ga_aws_sync = 1 WHERE id = ?",
        (local_id,),
    )
    conn.commit()

    logger.info(
        "[AWS SYNC][PULL][UPDATED] run_id=%s | tabla=planificador_solicitudes | local_id=%s | accion=%s",
        run_id, local_id, "aprobado" if aprobado else "rechazado",
    )
    return "updated"


def pull_aprobaciones_de_aws(app=None):
    """
    Lee de DynamoDB los gastos aprobados o rechazados y actualiza
    los campos correspondientes en la base local.
    """

    if not AWS_SYNC_ENABLED:
        logger.debug(
            "[AWS SYNC][PULL][SKIP] AWS_SYNC_ENABLED=0 (ambiente sin sync a AWS)"
        )
        return

    run_id = _new_run_id()
    started_at = perf_counter()

    ctx = app.app_context() if app else None

    if ctx:
        ctx.push()

    logger.info(
        "[AWS SYNC][PULL][START] run_id=%s",
        run_id,
    )

    try:
        logger.info(
            "[AWS SYNC][PULL][HTTP] run_id=%s | "
            "endpoint=/sync/pull",
            run_id,
        )

        http_started_at = perf_counter()

        res = requests.get(
            f"{AWS_API_URL}/sync/pull",
            headers=HEADERS,
            timeout=30,
        )

        http_ms = _elapsed_ms(http_started_at)

        logger.info(
            "[AWS SYNC][PULL][HTTP_RESPONSE] run_id=%s | "
            "status=%s | duration_ms=%d",
            run_id,
            res.status_code,
            http_ms,
        )

        if res.status_code != 200:
            logger.error(
                "[AWS SYNC][PULL][HTTP_ERROR] run_id=%s | "
                "status=%s | response=%s",
                run_id,
                res.status_code,
                _response_excerpt(res),
            )
            return

        try:
            raw = res.json()
        except ValueError as exc:
            logger.error(
                "[AWS SYNC][PULL][INVALID_JSON] run_id=%s | "
                "response=%s | error=%s",
                run_id,
                _response_excerpt(res),
                exc,
            )
            return

        if not isinstance(raw, dict):
            logger.error(
                "[AWS SYNC][PULL][INVALID_FORMAT] run_id=%s | "
                "tipo=%s",
                run_id,
                type(raw).__name__,
            )
            return

        gastos = raw.get("gastos", [])

        if not isinstance(gastos, list):
            logger.error(
                "[AWS SYNC][PULL][INVALID_GASTOS] run_id=%s | "
                "tipo=%s",
                run_id,
                type(gastos).__name__,
            )
            return

        logger.info(
            "[AWS SYNC][PULL][RECEIVED] run_id=%s | "
            "gastos=%d",
            run_id,
            len(gastos),
        )

        if not gastos:
            logger.info(
                "[AWS SYNC][PULL][EMPTY] run_id=%s | "
                "sin aprobaciones pendientes",
                run_id,
            )
            return

        conn = _get_db()
        sys_id = _resolve_sistema_aws_id(conn)

        if sys_id is None:
            logger.warning(
                "[AWS SYNC][PULL][SYSTEM_USER] run_id=%s | "
                "usuario sistema_aws no encontrado",
                run_id,
            )

        now_str = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        actualizados = 0
        no_encontrados = 0
        sin_cambios = 0
        sin_local_id = 0

        for g in gastos:
            local_id = g.get("local_id")

            if not local_id:
                sin_local_id += 1

                logger.warning(
                    "[AWS SYNC][PULL][SKIP] run_id=%s | "
                    "motivo=sin_local_id",
                    run_id,
                )
                continue

            gasto_id_full = g.get("gasto_id") or ""

            if gasto_id_full.startswith("voucher_taxi#"):
                status = _pull_voucher_item(conn, g, local_id, sys_id, now_str, run_id)
            else:
                status = _pull_gasto_tarjeta_item(conn, g, local_id, sys_id, now_str, run_id)

            if status == "updated":
                actualizados += 1
            elif status == "not_found":
                no_encontrados += 1
            else:
                sin_cambios += 1

        conn.commit()

        logger.info(
            "[AWS SYNC][PULL][OK] run_id=%s | "
            "recibidos=%d | actualizados=%d | "
            "sin_cambios=%d | no_encontrados=%d | "
            "sin_local_id=%d",
            run_id,
            len(gastos),
            actualizados,
            sin_cambios,
            no_encontrados,
            sin_local_id,
        )

    except requests.Timeout:
        logger.exception(
            "[AWS SYNC][PULL][TIMEOUT] run_id=%s | "
            "timeout=30s",
            run_id,
        )

    except requests.RequestException as exc:
        logger.exception(
            "[AWS SYNC][PULL][REQUEST_ERROR] run_id=%s | "
            "error=%s",
            run_id,
            exc,
        )

    except Exception as exc:
        logger.exception(
            "[AWS SYNC][PULL][ERROR] run_id=%s | "
            "error=%s",
            run_id,
            exc,
        )

    finally:
        logger.info(
            "[AWS SYNC][PULL][END] run_id=%s | "
            "duration_ms=%d",
            run_id,
            _elapsed_ms(started_at),
        )

        if ctx:
            ctx.pop()