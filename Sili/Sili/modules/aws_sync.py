"""
aws_sync.py — Sincronización bidireccional Flask ↔ AWS DynamoDB para aprobación de gastos.

Push: envía gastos nuevos/modificados a DynamoDB (aws_enviado=0)
Pull: lee aprobaciones pendientes de sync y actualiza la DB local
"""

import requests
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

AWS_API_URL   = "https://gqt5d309jh.execute-api.us-east-2.amazonaws.com/prod"
FLASK_TOKEN   = "85e3d66bbc7be0e507aa2648fd1ca5bb7ade57a97f0ad6d487fa39fc22bd792a"
HEADERS       = {"x-flask-token": FLASK_TOKEN, "Content-Type": "application/json"}

# Usuario sistema usado como aprobador_por cuando viene de AWS
USUARIO_AWS_ID = None  # Se resuelve en tiempo de ejecución buscando username='sistema_aws'


def _get_db():
    from .db import get_db
    return get_db()


def _resolve_sistema_aws_id(conn):
    """Devuelve el id del usuario 'sistema_aws' en la tabla usuarios (lo crea si no existe)."""
    row = conn.execute(
        "SELECT id FROM usuarios WHERE username = 'sistema_aws'"
    ).fetchone()
    if row:
        return row[0]
    # Crear usuario sistema si no existe
    conn.execute("""
        INSERT INTO usuarios (username, nombre_completo, rol, activo)
        VALUES ('sistema_aws', 'Sistema AWS', 'sistema', 0)
    """)
    conn.commit()
    row = conn.execute("SELECT id FROM usuarios WHERE username = 'sistema_aws'").fetchone()
    return row[0] if row else None


def _tipo_gasto(g: dict) -> str:
    if int(g.get("es_caja_chica") or 0):
        return "caja_chica"
    if int(g.get("reembolso_vendedor") or 0):
        return "reembolso"
    return "tarjeta_credito"


def _get_aprobador_email(conn, campo: str, dep_id=None, user_id=None) -> str:
    """Resuelve el email del aprobador según nivel."""
    from .routes_gatos_mail_notify import _gerente_email_por_jerarquia

    if campo == "ga":
        return _gerente_email_por_jerarquia(conn, user_id) or ""

    if campo in ("gf", "gg"):
        rol = "gerente financiero" if campo == "gf" else "gerente general"
        row = conn.execute(
            "SELECT TOP 1 email FROM usuarios WHERE LOWER(rol) = ? AND activo = 1 AND email IS NOT NULL",
            (rol,)
        ).fetchone()
        return (row[0] or "").strip() if row else ""

    return ""


# ─────────────────────────────────────────────────────────────
# PUSH — Flask → DynamoDB
# ─────────────────────────────────────────────────────────────
def push_gastos_a_aws(app=None):
    """
    Envía a DynamoDB los gastos con aws_enviado=0.
    Llamar desde scheduler cada N minutos.
    """
    ctx = app.app_context() if app else None
    if ctx:
        ctx.push()

    try:
        conn = _get_db()
        rows = conn.execute("""
            SELECT
                g.id, g.fecha, g.descripcion, g.monto_total,
                g.es_caja_chica, g.reembolso_vendedor,
                g.ga_aprobado, g.gf_aprobado, g.gg_aprobado,
                g.usuario_id, g.departamento_id,
                u.nombre_completo AS usuario_nombre,
                u.email          AS usuario_email,
                u.departamento_id AS dep_id
            FROM gastos_tarjeta g
            LEFT JOIN usuarios u ON u.id = g.usuario_id
            WHERE COALESCE(g.aws_enviado, 0) = 0
              AND g.sap_contabilizacion IS NULL
        """).fetchall()

        if not rows:
            logger.info("[AWS SYNC][PUSH] Sin gastos nuevos para enviar")
            return

        gastos_payload = []
        for g in rows:
            tipo     = _tipo_gasto(dict(g))
            gasto_id = f"{tipo}#{g['id']}"

            ga_email = _get_aprobador_email(conn, "ga", user_id=g["usuario_id"])
            gf_email = _get_aprobador_email(conn, "gf")
            gg_email = _get_aprobador_email(conn, "gg")

            gastos_payload.append({
                "gasto_id":            gasto_id,
                "tipo":                tipo,
                "local_id":            str(g["id"]),
                "fecha":               str(g["fecha"] or ""),
                "descripcion":         g["descripcion"] or "",
                "monto":               str(g["monto_total"] or 0),
                "usuario_nombre":      g["usuario_nombre"] or "",
                "usuario_email":       g["usuario_email"] or "",
                "ga_aprobador_email":  ga_email,
                "gf_aprobador_email":  gf_email,
                "gg_aprobador_email":  gg_email,
                "ga_aprobado":         int(g["ga_aprobado"] or 0),
                "gf_aprobado":         int(g["gf_aprobado"] or 0),
                "gg_aprobado":         int(g["gg_aprobado"] or 0),
                "flask_sincronizado":  "true",
            })

        res = requests.post(
            f"{AWS_API_URL}/sync/push",
            json={"gastos": gastos_payload},
            headers=HEADERS,
            timeout=30
        )

        if res.status_code == 200:
            ids = [g["id"] for g in rows]
            ph  = ",".join("?" * len(ids))
            conn.execute(
                f"UPDATE gastos_tarjeta SET aws_enviado=1 WHERE id IN ({ph})", ids
            )
            conn.commit()
            logger.info("[AWS SYNC][PUSH] Enviados %d gastos a DynamoDB", len(ids))
        else:
            logger.error("[AWS SYNC][PUSH] Error HTTP %s: %s", res.status_code, res.text)

    except Exception as e:
        logger.exception("[AWS SYNC][PUSH] Error: %s", e)
    finally:
        if ctx:
            ctx.pop()


# ─────────────────────────────────────────────────────────────
# PULL — DynamoDB → Flask
# ─────────────────────────────────────────────────────────────
def pull_aprobaciones_de_aws(app=None):
    """
    Lee de DynamoDB los gastos aprobados/rechazados (flask_sincronizado=false)
    y actualiza los campos de aprobación en la DB local.
    """
    ctx = app.app_context() if app else None
    if ctx:
        ctx.push()

    try:
        res = requests.get(
            f"{AWS_API_URL}/sync/pull",
            headers=HEADERS,
            timeout=30
        )

        if res.status_code != 200:
            logger.error("[AWS SYNC][PULL] Error HTTP %s: %s", res.status_code, res.text)
            return

        gastos = res.json().get("gastos", [])
        if not gastos:
            logger.info("[AWS SYNC][PULL] Sin aprobaciones pendientes")
            return

        conn     = _get_db()
        sys_id   = _resolve_sistema_aws_id(conn)
        now_str  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for g in gastos:
            local_id = g.get("local_id")
            if not local_id:
                continue

            # Leer estado actual local para no sobreescribir aprobaciones locales
            row = conn.execute("""
                SELECT ga_aprobado, gf_aprobado, gg_aprobado,
                       COALESCE(ga_aws_sync,0) AS ga_aws_sync,
                       COALESCE(gf_aws_sync,0) AS gf_aws_sync,
                       COALESCE(gg_aws_sync,0) AS gg_aws_sync
                FROM gastos_tarjeta WHERE id = ?
            """, (local_id,)).fetchone()

            if not row:
                continue

            updates = []
            params  = []

            # GA
            if int(g.get("ga_aprobado") or 0) and not row["ga_aws_sync"]:
                updates += ["ga_aprobado=1", "ga_aprobado_por=?",
                            "ga_aprobado_at=?", "ga_aprobado_origen='aws'", "ga_aws_sync=1"]
                params  += [sys_id, g.get("ga_at") or now_str]

            # GF — solo si GA ya aprobó y GG no bloqueó
            if int(g.get("gf_aprobado") or 0) and not row["gf_aws_sync"] \
                    and not int(g.get("gg_aprobado") or 0):
                updates += ["gf_aprobado=1", "gf_aprobado_por=?",
                            "gf_aprobado_at=?", "gf_aprobado_origen='aws'", "gf_aws_sync=1"]
                params  += [sys_id, g.get("gf_at") or now_str]

            # GG
            if int(g.get("gg_aprobado") or 0) and not row["gg_aws_sync"]:
                updates += ["gg_aprobado=1", "gg_aprobado_por=?",
                            "gg_aprobado_at=?", "gg_aprobado_origen='aws'", "gg_aws_sync=1"]
                params  += [sys_id, g.get("gg_at") or now_str]

            if updates:
                params.append(local_id)
                conn.execute(
                    f"UPDATE gastos_tarjeta SET {', '.join(updates)} WHERE id = ?",
                    params
                )
                logger.info("[AWS SYNC][PULL] Gasto %s actualizado desde AWS", local_id)

        conn.commit()
        logger.info("[AWS SYNC][PULL] Procesados %d registros de DynamoDB", len(gastos))

    except Exception as e:
        logger.exception("[AWS SYNC][PULL] Error: %s", e)
    finally:
        if ctx:
            ctx.pop()
