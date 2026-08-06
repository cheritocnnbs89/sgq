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

import hashlib
import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from time import perf_counter
from urllib.parse import urlsplit
from uuid import uuid4

import requests


# ============================================================
# Configuración
# ============================================================

AWS_API_URL = os.environ["AWS_API_URL"].strip().rstrip("/")
FLASK_TOKEN = os.environ["AWS_FLASK_TOKEN"].strip()

if not AWS_API_URL:
    raise RuntimeError("La variable AWS_API_URL está vacía.")

if not FLASK_TOKEN:
    raise RuntimeError("La variable AWS_FLASK_TOKEN está vacía.")

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


def _rol_aprobacion(rol_sistema: str) -> str | None:
    """
    Traduce el rol de sistema (usuarios.rol) al nivel de aprobación que
    espera la Lambda de AWS: GA / GG / GF. Usa la misma configuración de
    gastos_helpers ya usada en el resto de la app (rol_gg()/rol_gf()/roles
    GA), en vez de una lista de nombres literales aparte -- si alguien
    reconfigura quién es GG o GF desde Configuración de Gastos, este mapeo
    lo respeta automáticamente sin tocar código.
    """
    from . import gastos_helpers as gh

    rol = (rol_sistema or "").strip().lower()
    if gh.es_rol_gg(rol):
        return "GG"
    if gh.es_rol_gf(rol):
        return "GF"
    if gh.es_rol_ga(rol):
        return "GA"
    return None


def _roles_gerente_auth() -> tuple[str, ...]:
    """Roles de sistema que hoy mapean a algún nivel de aprobación (GA/GG/GF)."""
    from . import gastos_helpers as gh

    roles = set(gh.roles_ga())
    roles.add(gh.rol_gg())
    roles.add(gh.rol_gf())
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
    "api_host=%s | token_configurado=%s | log=%s",
    API_HOST,
    bool(FLASK_TOKEN),
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

def push_gastos_a_aws(app=None):
    """
    Envía a DynamoDB los gastos con aws_enviado=0.

    Esta función puede ser llamada desde el scheduler cada N minutos.
    """

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

def pull_aprobaciones_de_aws(app=None):
    """
    Lee de DynamoDB los gastos aprobados o rechazados y actualiza
    los campos correspondientes en la base local.
    """

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

            row = conn.execute(
                """
                SELECT
                    ga_aprobado,
                    gf_aprobado,
                    gg_aprobado,
                    COALESCE(ga_aws_sync, 0)
                        AS ga_aws_sync,
                    COALESCE(gf_aws_sync, 0)
                        AS gf_aws_sync,
                    COALESCE(gg_aws_sync, 0)
                        AS gg_aws_sync
                FROM gastos_tarjeta
                WHERE id = ?
                """,
                (local_id,),
            ).fetchone()

            if not row:
                no_encontrados += 1

                logger.warning(
                    "[AWS SYNC][PULL][NOT_FOUND] run_id=%s | "
                    "local_id=%s",
                    run_id,
                    local_id,
                )
                continue

            updates = []
            params = []
            niveles_actualizados = []

            # GA
            if (
                int(g.get("ga_aprobado") or 0)
                and not row["ga_aws_sync"]
            ):
                updates += [
                    "ga_aprobado=1",
                    "ga_aprobado_por=?",
                    "ga_aprobado_at=?",
                    "ga_aprobado_origen='aws'",
                    "ga_aws_sync=1",
                ]

                params += [
                    sys_id,
                    g.get("ga_at") or now_str,
                ]

                niveles_actualizados.append("GA")

            # GF
            if (
                int(g.get("gf_aprobado") or 0)
                and not row["gf_aws_sync"]
                and not int(g.get("gg_aprobado") or 0)
            ):
                updates += [
                    "gf_aprobado=1",
                    "gf_aprobado_por=?",
                    "gf_aprobado_at=?",
                    "gf_aprobado_origen='aws'",
                    "gf_aws_sync=1",
                ]

                params += [
                    sys_id,
                    g.get("gf_at") or now_str,
                ]

                niveles_actualizados.append("GF")

            # GG
            if (
                int(g.get("gg_aprobado") or 0)
                and not row["gg_aws_sync"]
            ):
                updates += [
                    "gg_aprobado=1",
                    "gg_aprobado_por=?",
                    "gg_aprobado_at=?",
                    "gg_aprobado_origen='aws'",
                    "gg_aws_sync=1",
                ]

                params += [
                    sys_id,
                    g.get("gg_at") or now_str,
                ]

                niveles_actualizados.append("GG")

            if updates:
                params.append(local_id)

                conn.execute(
                    f"""
                    UPDATE gastos_tarjeta
                    SET {", ".join(updates)}
                    WHERE id = ?
                    """,
                    params,
                )

                actualizados += 1

                logger.info(
                    "[AWS SYNC][PULL][UPDATED] run_id=%s | "
                    "local_id=%s | niveles=%s",
                    run_id,
                    local_id,
                    ",".join(niveles_actualizados),
                )

            else:
                sin_cambios += 1

                logger.info(
                    "[AWS SYNC][PULL][NO_CHANGE] run_id=%s | "
                    "local_id=%s",
                    run_id,
                    local_id,
                )

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