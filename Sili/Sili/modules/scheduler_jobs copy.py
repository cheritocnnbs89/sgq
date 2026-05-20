# modules/scheduler_jobs.py
from __future__ import annotations

import json
import sqlite3
import threading
import time
from datetime import datetime, date, time as dtime
from typing import Optional
from datetime import date

from . import routes_gatos_mail_notify as mail
from flask import current_app, render_template_string
 
  

# Esquema/SMTP de planilla
from modules.routes_planilla_mensual import ensure_schema
from modules.routes_planilla_mensual import send_mail as send_mail_planilla
from modules.config import DB_PATH


# ============================================================
# Helpers de log / SQL debug
# ============================================================
def _log(level: str, msg: str, *args):
    try:
        logger = current_app.logger
        fn = getattr(logger, level if level in ("info", "warning", "error", "debug") else "info")
        fn(msg, *args)
    except Exception:
        try:
            print(f"[{datetime.utcnow().isoformat()}] [{level.upper()}] " + (msg % args if args else msg))
        except Exception:
            pass


def _format_sql_for_log(sql: str, params: tuple) -> str:
    """Devuelve el SQL con cada ? reemplazado por la repr del parámetro (SOLO para LOG)."""
    out = []
    it = iter(params)
    parts = sql.split("?")
    for idx, ch in enumerate(parts):
        out.append(ch)
        if idx < len(parts) - 1:
            try:
                p = next(it)
                if isinstance(p, str):
                    out.append("'" + p.replace("'", "''") + "'")
                else:
                    out.append(repr(p))
            except StopIteration:
                out.append("?")
    return "".join(out)


# ============================================================
# Conexión SQLite EFÍMERA (standalone) para el worker
# ============================================================
def _sqlite_connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def _resolve_db_path() -> str:
    # 1) usa config de Flask (fuente de verdad)
    p = current_app.config.get("DATABASE") or current_app.config.get("DB_PATH")
    if p:
        return str(p)
    # 2) fallback (si tu configure_app usa otro nombre)
    from modules.config import DB_PATH as _DB_PATH
    if _DB_PATH:
        return str(_DB_PATH)
    raise RuntimeError("DB path no configurado: setea app.config['DATABASE']")

def get_db_standalone() -> sqlite3.Connection:
    return _sqlite_connect(_resolve_db_path())


# ============================================================
# Utilidades varias
# ============================================================ 
def _exec_retry(cur, sql, params=(), tries=6, base_wait=0.15):
    import time as _t
    for i in range(tries):
        try:
            return cur.execute(sql, params)
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e).lower() and i < tries - 1:
                _t.sleep(base_wait * (i + 1))
                continue
            raise


def _is_quiet(now_t: dtime, quiet_start: Optional[str], quiet_end: Optional[str]) -> bool:
    if not quiet_start or not quiet_end:
        return False
    qs = datetime.strptime(quiet_start, "%H:%M").time()
    qe = datetime.strptime(quiet_end, "%H:%M").time()
    if qs < qe:
        return qs <= now_t < qe
    return (now_t >= qs) or (now_t < qe)


def _next_5min_sqlite() -> str:
    # devuelve expresion sqlite que redondea al próximo múltiplo de 5 min
    return "datetime((strftime('%s','now')/300 + 1)*300, 'unixepoch')"


# ============================================================
# Esquema de notificaciones
# ============================================================
def ensure_notify_schema(conn):
    cur = conn.cursor()

    _exec_retry(cur, """
      CREATE TABLE IF NOT EXISTS notify_queue(
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id       INTEGER,
        tarea_id      INTEGER,
        tipo          TEXT NOT NULL,      -- hoy | vencida | resumen_* | gasto_*
        fecha_obj     DATE,
        canal         TEXT NOT NULL,      -- email | inapp | slack
        estado        TEXT NOT NULL DEFAULT 'pending',  -- pending|sending|sent|error|skipped
        scheduled_at  TEXT,
        sent_at       TEXT,
        error_msg     TEXT,
        template_key  TEXT,
        payload_json  TEXT
      )
    """)

    _exec_retry(cur, """
      CREATE TABLE IF NOT EXISTS notify_templates(
        key     TEXT PRIMARY KEY,
        tipo    TEXT NOT NULL,
        subject TEXT NOT NULL,
        html    TEXT NOT NULL,
        text    TEXT
      )
    """)

    _exec_retry(cur, """
      CREATE TABLE IF NOT EXISTS notify_user_prefs(
        user_id       INTEGER PRIMARY KEY,
        email_on      INTEGER DEFAULT 1,
        inapp_on      INTEGER DEFAULT 1,
        slack_on      INTEGER DEFAULT 0,
        slack_webhook TEXT,
        quiet_start   TEXT,
        quiet_end     TEXT,
        daily_time    TEXT,
        weekly_dow    TEXT,
        weekly_time   TEXT
      )
    """)

    _exec_retry(cur, """
      CREATE TABLE IF NOT EXISTS notify_inapp(
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER NOT NULL,
        title      TEXT NOT NULL,
        body       TEXT NOT NULL,
        created_at TEXT NOT NULL,
        is_read    INTEGER NOT NULL DEFAULT 0
      )
    """)

    # --- migración suave: columnas para gastos ---
    try:
        cur.execute("SELECT gasto_id FROM notify_queue LIMIT 1")
    except Exception:
        _exec_retry(cur, "ALTER TABLE notify_queue ADD COLUMN gasto_id INTEGER")

    try:
        cur.execute("SELECT area FROM notify_queue LIMIT 1")
    except Exception:
        _exec_retry(cur, "ALTER TABLE notify_queue ADD COLUMN area TEXT")

    try:
        cur.execute("SELECT event_key FROM notify_queue LIMIT 1")
    except Exception:
        _exec_retry(cur, "ALTER TABLE notify_queue ADD COLUMN event_key TEXT")

    # Limpieza SOLO para no-gastos (no tocar gastos)
    _exec_retry(cur, """
        DELETE FROM notify_queue
         WHERE tipo NOT LIKE 'gasto_%'
           AND id NOT IN (
                SELECT MAX(id)
                  FROM notify_queue
                 WHERE tipo NOT LIKE 'gasto_%'
                 GROUP BY user_id, tipo, fecha_obj, canal
           )
    """)

    # Evitar duplicados SOLO para no-gastos
    _exec_retry(cur, """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_notify_queue_once
        ON notify_queue(user_id, tipo, fecha_obj, canal)
        WHERE tipo NOT LIKE 'gasto_%'
    """)

    # (Opcional) acelerar dispatcher
    _exec_retry(cur, """
      CREATE INDEX IF NOT EXISTS ix_notify_queue_pending
      ON notify_queue(estado, scheduled_at)
    """)

    # Evita duplicados de la notificación "hoy" por usuario/canal/día
    _exec_retry(cur, """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_notify_hoy
        ON notify_queue(user_id, fecha_obj, canal, tipo)
        WHERE tipo='hoy'
    """)

    # Evita duplicados de eventos de gastos
    _exec_retry(cur, """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_notify_gasto_event
        ON notify_queue(user_id, gasto_id, area, tipo, canal)
        WHERE tipo LIKE 'gasto_%'
    """)
    
    
    # ✅ nueva columna para guardar motivo de rechazo
    cols = [r[1] for r in cur.execute("PRAGMA table_info(notify_queue)").fetchall()]
    if "comentario" not in cols:
        cur.execute("ALTER TABLE notify_queue ADD COLUMN comentario TEXT")
        conn.commit()

    conn.commit()


def ensure_core_templates(conn: sqlite3.Connection):
    """
    Asegura plantillas mínimas del sistema (por ejemplo: tarea_hoy)
    IMPORTANTE: esto evita el FOREIGN KEY constraint failed cuando tu notify_queue
    tiene FK contra notify_templates.key.
    """
    cur = conn.cursor()

    templates = [
        (
            "tarea_hoy",
            "tarea",
            "📌 Tareas para hoy {{ fecha }} ({{ usuario }})",
            "<p>Hola {{ usuario }},</p>"
            "<p>Estas son tus tareas para <b>{{ fecha }}</b>:</p>"
            "{% if tareas_hoy_len and tareas_hoy_len > 0 %}"
            "<ul>"
            "{% for t in tareas_hoy %}"
            "<li>"
            "{{ t.departamento or '' }} — <b>{{ t.nombre }}</b>"
            "{% if t.frecuencia %} ({{ t.frecuencia }}){% endif %}"
            "{% if t.hecha %} ✅{% else %} ⏳{% endif %}"
            "</li>"
            "{% endfor %}"
            "</ul>"
            "{% else %}"
            "<p><i>No tienes tareas planificadas para hoy.</i></p>"
            "{% endif %}"
            "<p>{{ app_url }}</p>",
            "Tareas para hoy {{ fecha }} ({{ usuario }}). Total: {{ tareas_hoy_len or 0 }}",
        ),
    ]

    for key, tipo, subject, html, text in templates:
        _exec_retry(cur, """
            INSERT OR IGNORE INTO notify_templates(key, tipo, subject, html, text)
            VALUES (?,?,?,?,?)
        """, (key, tipo, subject, html, text))

    conn.commit()


def ensure_gasto_templates2(conn: sqlite3.Connection):
    """
    Asegura que existan las plantillas mínimas para notificaciones de gastos.
    Si ya existen, no hace nada.
    """
    cur = conn.cursor()

    templates = [
        # al creador
        ("gasto_user_approved", "gasto",
         "✅ Tu gasto #{{ gasto_id }} fue aprobado ({{ area|upper }})",
         "<p>Hola {{ usuario }},</p>"
         "<p>Tu gasto <b>#{{ gasto_id }}</b> fue aprobado por <b>{{ approved_by_user_id }}</b> ({{ area|upper }}).</p>"
         "<p>Revisa el detalle en el sistema.</p>",
         "Tu gasto #{{ gasto_id }} fue aprobado ({{ area|upper }})."),

        # al siguiente aprobador
        ("gasto_next_gg", "gasto",
         "🟠 Aprobación pendiente GG: gasto #{{ gasto_id }}",
         "<p>Tienes un gasto pendiente de aprobación:</p><p><b>#{{ gasto_id }}</b></p>",
         "Aprobación pendiente GG: gasto #{{ gasto_id }}"),

        ("gasto_next_gf", "gasto",
         "🟠 Aprobación pendiente GF: gasto #{{ gasto_id }}",
         "<p>Tienes un gasto pendiente de aprobación:</p><p><b>#{{ gasto_id }}</b></p>",
         "Aprobación pendiente GF: gasto #{{ gasto_id }}"),

        ("gasto_next_coord", "gasto",
         "🟠 Envío/Control: gasto #{{ gasto_id }}",
         "<p>Gasto listo para control/envío:</p><p><b>#{{ gasto_id }}</b></p>",
         "Control/Envío: gasto #{{ gasto_id }}"),

        ("gasto_next", "gasto",
         "🟠 Gasto pendiente: #{{ gasto_id }}",
         "<p>Tienes un gasto pendiente:</p><p><b>#{{ gasto_id }}</b></p>",
         "Gasto pendiente: #{{ gasto_id }}"),
    ]

    for key, tipo, subject, html, text in templates:
        _exec_retry(cur, """
            INSERT OR IGNORE INTO notify_templates(key, tipo, subject, html, text)
            VALUES (?,?,?,?,?)
        """, (key, tipo, subject, html, text))

    conn.commit()

def ensure_gasto_templates3(conn: sqlite3.Connection):
    """
    Asegura plantillas de gastos con estilo AZUL (siempre).
    Usa UPSERT para actualizar aunque el key ya exista.
    """
    cur = conn.cursor()

    def upsert(key, tipo, subject, html, text):
        _exec_retry(cur, """
            INSERT INTO notify_templates(key, tipo, subject, html, text)
            VALUES (?,?,?,?,?)
            ON CONFLICT(key) DO UPDATE SET
                tipo    = excluded.tipo,
                subject = excluded.subject,
                html    = excluded.html,
                text    = excluded.text
        """, (key, tipo, subject, html, text))

    # =========================
    # HTML BASE AZUL (compatible Outlook)
    # =========================
    html_user_approved = """\
<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f3f4f6;font-family:Segoe UI,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:24px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="720" cellpadding="0" cellspacing="0"
                 style="max-width:720px;background:#ffffff;border-radius:8px;border:1px solid #e5e7eb;overflow:hidden;">

            <tr>
              <td style="background:#1d4ed8;padding:16px 20px;color:#ffffff;">
                <div style="font-size:12px;text-transform:uppercase;letter-spacing:.08em;opacity:.9;">
                  Gastos con tarjeta
                </div>
                <div style="font-size:18px;font-weight:700;margin-top:4px;">
                  Gasto aprobado #{{ gasto_id }}
                </div>
                <div style="font-size:12px;opacity:.95;margin-top:6px;">
                  Hola {{ usuario }}, tu gasto fue aprobado por {{ approved_by_user_id }} ({{ area|upper }}).
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:18px 20px 10px 20px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
                  <tr>
                    <td style="width:210px;background:#eef2ff;font-weight:600;padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;">ID</td>
                    <td style="padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;">#{{ gasto_id }}</td>
                  </tr>
                  <tr>
                    <td style="width:210px;background:#eef2ff;font-weight:600;padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;">Estado</td>
                    <td style="padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;">Aprobado ({{ area|upper }})</td>
                  </tr>
                  <tr>
                    <td style="width:210px;background:#eef2ff;font-weight:600;padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;">Fecha</td>
                    <td style="padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;">{{ fecha }}</td>
                  </tr>
                </table>

                <div style="margin-top:18px;margin-bottom:6px;text-align:left;">
                  <a href="{{ gasto_url }}"
                     style="display:inline-block;background:#2563eb;color:#ffffff;text-decoration:none;padding:10px 18px;border-radius:6px;font-weight:600;font-size:13px;">
                    Ver gasto
                  </a>
                </div>

                <div style="font-size:11px;color:#6b7280;margin-top:8px;">
                  Este mensaje fue generado automáticamente por el sistema.
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:10px 20px 14px 20px;border-top:1px solid #e5e7eb;font-size:11px;color:#9ca3af;">
                Este es un mensaje automático. No responda a este correo.
              </td>
            </tr>

          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""

    html_next_step = """\
<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f3f4f6;font-family:Segoe UI,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:24px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="720" cellpadding="0" cellspacing="0"
                 style="max-width:720px;background:#ffffff;border-radius:8px;border:1px solid #e5e7eb;overflow:hidden;">

            <tr>
              <td style="background:#1d4ed8;padding:16px 20px;color:#ffffff;">
                <div style="font-size:12px;text-transform:uppercase;letter-spacing:.08em;opacity:.9;">
                  Gastos con tarjeta
                </div>
                <div style="font-size:18px;font-weight:700;margin-top:4px;">
                  Acción requerida — Gasto #{{ gasto_id }}
                </div>
                <div style="font-size:12px;opacity:.95;margin-top:6px;">
                  {{ area|upper }} aprobó este gasto. Debes continuar el flujo.
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:18px 20px 10px 20px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
                  <tr>
                    <td style="width:210px;background:#eef2ff;font-weight:600;padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;">ID</td>
                    <td style="padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;">#{{ gasto_id }}</td>
                  </tr>
                  <tr>
                    <td style="width:210px;background:#eef2ff;font-weight:600;padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;">Creado por</td>
                    <td style="padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;">{{ creador|default('') }}</td>
                  </tr>
                  <tr>
                    <td style="width:210px;background:#eef2ff;font-weight:600;padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;">Fecha</td>
                    <td style="padding:8px 12px;border-bottom:1px solid #f3f4f6;font-size:13px;">{{ fecha }}</td>
                  </tr>
                </table>

                <div style="margin-top:18px;margin-bottom:6px;text-align:left;">
                  <a href="{{ gasto_url }}"
                     style="display:inline-block;background:#2563eb;color:#ffffff;text-decoration:none;padding:10px 18px;border-radius:6px;font-weight:600;font-size:13px;">
                    Revisar y aprobar
                  </a>
                </div>

                <div style="font-size:11px;color:#6b7280;margin-top:8px;">
                  Este mensaje fue generado automáticamente por el sistema.
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:10px 20px 14px 20px;border-top:1px solid #e5e7eb;font-size:11px;color:#9ca3af;">
                Este es un mensaje automático. No responda a este correo.
              </td>
            </tr>

          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""

    # ---------- keys que usa tu queue ----------
    upsert(
        "gasto_user_approved", "gasto",
        "✅ Tu gasto #{{ gasto_id }} fue aprobado ({{ area|upper }})",
        html_user_approved,
        "Tu gasto #{{ gasto_id }} fue aprobado ({{ area|upper }})."
    )

    # Los siguientes “next” TODOS con el mismo azul
    upsert("gasto_next_gg",    "gasto", "🟠 Aprobación pendiente GG: gasto #{{ gasto_id }}",    html_next_step, "Aprobación pendiente GG: gasto #{{ gasto_id }}")
    upsert("gasto_next_gf",    "gasto", "🟠 Aprobación pendiente GF: gasto #{{ gasto_id }}",    html_next_step, "Aprobación pendiente GF: gasto #{{ gasto_id }}")
    upsert("gasto_next_coord", "gasto", "🟠 Envío/Control: gasto #{{ gasto_id }}",              html_next_step, "Control/Envío: gasto #{{ gasto_id }}")
    upsert("gasto_next",       "gasto", "🟠 Gasto pendiente: #{{ gasto_id }}",                  html_next_step, "Gasto pendiente: #{{ gasto_id }}")

    conn.commit()


def ensure_gasto_templates(conn: sqlite3.Connection):
    """
    Plantillas de gastos en formato AZUL (como tu captura) + Proveedor + Motivo.
    UPSERT para actualizar aunque ya existan.
    """
    cur = conn.cursor()

    def upsert(key, tipo, subject, html, text):
        _exec_retry(cur, """
            INSERT INTO notify_templates(key, tipo, subject, html, text)
            VALUES (?,?,?,?,?)
            ON CONFLICT(key) DO UPDATE SET
                tipo    = excluded.tipo,
                subject = excluded.subject,
                html    = excluded.html,
                text    = excluded.text
        """, (key, tipo, subject, html, text))

    # ====== Bloque Jinja para labels (area_txt y next_txt) ======
    # Se inyecta dentro del HTML para que NO dependas de python f-strings.
    JINJA_LABELS = """
{% set area_key = (area or '')|lower %}
{% if area_key == 'ga' %}
  {% set area_txt = 'Gerencia de Área' %}
  {% set next_txt = 'Gerencia General' %}
{% elif area_key == 'gg' %}
  {% set area_txt = 'Gerencia General' %}
  {% set next_txt = 'Gerencia Financiera' %}
{% elif area_key == 'gf' %}
  {% set area_txt = 'Gerencia Financiera' %}
  {% set next_txt = 'Coordinación' %}
{% else %}
  {% set area_txt = (area or '')|upper %}
  {% set next_txt = 'Siguiente aprobador' %}
{% endif %}
""".strip()

    # ====== HTML: Usuario (aprobado) ======
    html_user_approved = """\
<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f3f4f6;font-family:Segoe UI,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:24px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="720" cellpadding="0" cellspacing="0"
                 style="max-width:720px;background:#ffffff;border-radius:10px;border:1px solid #e5e7eb;overflow:hidden;">

            <tr>
              <td style="background:#1d4ed8;padding:18px 22px;color:#ffffff;">
                <div style="font-size:12px;text-transform:uppercase;letter-spacing:.08em;opacity:.92;">
                  GASTOS CON TARJETA
                </div>
                <div style="font-size:22px;font-weight:800;margin-top:4px;line-height:1.15;">
                  Gasto aprobado — #{{ gasto_id }}
                </div>
                <div style="font-size:13px;opacity:.92;margin-top:8px;line-height:1.35;">
                  """ + JINJA_LABELS + """
                  Hola {{ usuario }}, tu gasto fue aprobado por {{ approved_by_user_id }} ({{ area_txt }}).
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:18px 22px 10px 22px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                       style="border-collapse:separate;border-spacing:0;overflow:hidden;border-radius:10px;">

                  <tr>
                    <td style="width:280px;background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">ID</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">#{{ gasto_id }}</td>
                  </tr>

                  <tr>
                    <td style="width:280px;background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Fecha</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">{{ fecha }}</td>
                  </tr>

                  <!-- ✅ PROVEEDOR -->
                  <tr>
                    <td style="width:280px;background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Proveedor</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">{{ proveedor|default('') }}</td>
                  </tr>

                  <!-- ✅ MOTIVO -->
                  <tr>
                    <td style="width:280px;background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Motivo</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">{{ motivo|default('') }}</td>
                  </tr>

                  <tr>
                    <td style="width:280px;background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Total con IVA</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">${{ total_con_iva_fmt|default('0,00') }}</td>
                  </tr>

                  <tr>
                    <td style="width:280px;background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Estado</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Aprobado por {{ area_txt }}</td>
                  </tr>

                </table>

                <div style="margin-top:18px;">
                  <a href="{{ gasto_url }}"
                     style="display:inline-block;background:#2563eb;color:#ffffff;text-decoration:none;
                            padding:11px 18px;border-radius:8px;font-weight:700;font-size:13px;">
                    Ver gasto
                  </a>
                </div>

                <div style="font-size:12px;color:#6b7280;margin-top:12px;">
                  Este correo fue generado automáticamente por el sistema de Sili.
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:12px 22px 14px 22px;border-top:1px solid #e5e7eb;font-size:11px;color:#9ca3af;">
                Este es un mensaje automático. No responda a este correo.
              </td>
            </tr>

          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""

    # ====== HTML: Siguiente aprobador (acción requerida) ======
    html_next_step = """\
<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f3f4f6;font-family:Segoe UI,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:24px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="720" cellpadding="0" cellspacing="0"
                 style="max-width:720px;background:#ffffff;border-radius:10px;border:1px solid #e5e7eb;overflow:hidden;">

            <tr>
              <td style="background:#1d4ed8;padding:18px 22px;color:#ffffff;">
                <div style="font-size:12px;text-transform:uppercase;letter-spacing:.08em;opacity:.92;">
                  GASTOS CON TARJETA
                </div>
                <div style="font-size:22px;font-weight:800;margin-top:4px;line-height:1.15;">
                  Acción requerida — Gasto #{{ gasto_id }}
                </div>
                <div style="font-size:13px;opacity:.92;margin-top:8px;line-height:1.35;">
                  """ + JINJA_LABELS + """
                  {{ area_txt }} aprobó este gasto. Debes continuar con la aprobación ({{ next_txt }}).
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:18px 22px 10px 22px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                       style="border-collapse:separate;border-spacing:0;overflow:hidden;border-radius:10px;">

                  <tr>
                    <td style="width:280px;background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">ID</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">#{{ gasto_id }}</td>
                  </tr>

                  <tr>
                    <td style="width:280px;background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Fecha</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">{{ fecha }}</td>
                  </tr>

                  <!-- ✅ PROVEEDOR -->
                  <tr>
                    <td style="width:280px;background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Proveedor</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">{{ proveedor|default('') }}</td>
                  </tr>

                  <!-- ✅ MOTIVO -->
                  <tr>
                    <td style="width:280px;background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Motivo</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">{{ motivo|default('') }}</td>
                  </tr>

                  <tr>
                    <td style="width:280px;background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Total con IVA</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">${{ total_con_iva_fmt|default('0,00') }}</td>
                  </tr>

                  <tr>
                    <td style="width:280px;background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Creador</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">{{ creador|default('') }}</td>
                  </tr>

                  <tr>
                    <td style="width:280px;background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Estado</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Aprobado por {{ area_txt }}</td>
                  </tr>

                </table>

                <div style="margin-top:18px;">
                  <a href="{{ gasto_url }}"
                     style="display:inline-block;background:#2563eb;color:#ffffff;text-decoration:none;
                            padding:11px 18px;border-radius:8px;font-weight:700;font-size:13px;">
                    Revisar y aprobar gasto
                  </a>
                </div>

                <div style="font-size:12px;color:#6b7280;margin-top:12px;">
                  Este correo fue generado automáticamente por el sistema de Sili.
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:12px 22px 14px 22px;border-top:1px solid #e5e7eb;font-size:11px;color:#9ca3af;">
                Este es un mensaje automático. No responda a este correo.
              </td>
            </tr>

          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""

    # ====== HTML: Rechazo GG (NUEVO) ======
    html_rechazo_gg = """\
<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f3f4f6;font-family:Segoe UI,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:24px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="720" cellpadding="0" cellspacing="0"
                 style="max-width:720px;background:#ffffff;border-radius:10px;border:1px solid #e5e7eb;overflow:hidden;">

            <tr>
              <td style="background:#1d4ed8;padding:18px 22px;color:#ffffff;">
                <div style="font-size:12px;text-transform:uppercase;letter-spacing:.08em;opacity:.92;">
                  GASTOS CON TARJETA
                </div>
                <div style="font-size:22px;font-weight:800;margin-top:4px;line-height:1.15;">
                  Gasto rechazado — #{{ gasto_id }}
                </div>
                <div style="font-size:13px;opacity:.92;margin-top:8px;line-height:1.35;">
                  Hola {{ usuario|default('') }}, este gasto fue <b>RECHAZADO</b> por Gerencia General.
                  Por favor acérquese a Gerencia General para revisión.
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:18px 22px 10px 22px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                       style="border-collapse:separate;border-spacing:0;overflow:hidden;border-radius:10px;">

                  <tr>
                    <td style="width:280px;background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">ID</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">#{{ gasto_id }}</td>
                  </tr>

                  <tr>
                    <td style="width:280px;background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Fecha</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">{{ fecha }}</td>
                  </tr>

                  <tr>
                    <td style="width:280px;background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Proveedor</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">{{ proveedor|default('') }}</td>
                  </tr>

                  <tr>
                    <td style="width:280px;background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Motivo</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">{{ motivo|default('') }}</td>
                  </tr>

                  <tr>
                    <td style="width:280px;background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Total con IVA</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">${{ total_con_iva_fmt|default('0,00') }}</td>
                  </tr>

                  <tr>
                    <td style="width:280px;background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Estado</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#b91c1c;font-weight:800;">
                      RECHAZADO (GG)
                    </td>
                  </tr>
                  {% if comentario %}
                    <tr>
                      <td style="width:280px;background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">
                        Motivo del rechazo
                      </td>
                      <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;white-space:pre-wrap;">
                        {{ comentario }}
                      </td>
                    </tr>
                    {% endif %}

                </table>

                <div style="margin-top:18px;">
                  <a href="{{ gasto_url }}"
                     style="display:inline-block;background:#2563eb;color:#ffffff;text-decoration:none;
                            padding:11px 18px;border-radius:8px;font-weight:700;font-size:13px;">
                    Ver gasto
                  </a>
                </div>

                <div style="font-size:12px;color:#6b7280;margin-top:12px;">
                  Este correo fue generado automáticamente por el sistema de Sili.
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:12px 22px 14px 22px;border-top:1px solid #e5e7eb;font-size:11px;color:#9ca3af;">
                Este es un mensaje automático. No responda a este correo.
              </td>
            </tr>

          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""

    # ============================
    # Keys que usa tu cola (NO cambiar)
    # ============================
    upsert(
        "gasto_user_approved", "gasto",
        "✅ Tu gasto #{{ gasto_id }} fue aprobado ({{ area|upper }})",
        html_user_approved,
        "Tu gasto #{{ gasto_id }} fue aprobado ({{ area|upper }})."
    )
    upsert("gasto_next_gg",    "gasto", "🟠 Aprobación pendiente GG: gasto #{{ gasto_id }}", html_next_step, "Aprobación pendiente GG: gasto #{{ gasto_id }}")
    upsert("gasto_next_gf",    "gasto", "🟠 Aprobación pendiente GF: gasto #{{ gasto_id }}", html_next_step, "Aprobación pendiente GF: gasto #{{ gasto_id }}")
    upsert("gasto_next_coord", "gasto", "🟠 Envío/Control: gasto #{{ gasto_id }}",           html_next_step, "Control/Envío: gasto #{{ gasto_id }}")
    upsert("gasto_next",       "gasto", "🟠 Gasto pendiente: #{{ gasto_id }}",               html_next_step, "Gasto pendiente: #{{ gasto_id }}")

    # ✅ NUEVO KEY: rechazo GG (ESTE ES EL INSERT/UPSERT QUE TE FALTABA)
    upsert(
        "gasto_rechazo_gg", "gasto",
        "🚫 Gasto rechazado (GG): #{{ gasto_id }}",
        html_rechazo_gg,
        "Tu gasto #{{ gasto_id }} fue RECHAZADO por Gerencia General. Acércate a GG para revisión."
    )

    conn.commit()

# ============================================================
# Encolar notificaciones por aprobación de gasto
# ============================================================
def get_ultimo_jefe_activo(conn: sqlite3.Connection, user_id: int | None) -> int | None:
    """
    Retorna el último jefe activo en la cadena de usuarios.jefe_id.
    Si hay bucles, se detiene por seguridad.
    """
    if not user_id:
        return None

    cur = conn.cursor()

    # traer jefe inicial
    cur.execute("SELECT jefe_id FROM usuarios WHERE id = ?", (user_id,))
    row = cur.fetchone()
    if not row:
        return None

    jefe_id = row["jefe_id"]
    if not jefe_id:
        return None

    seen = set()
    last_valid = None

    while jefe_id and jefe_id not in seen:
        seen.add(jefe_id)

        cur.execute("""
            SELECT id, jefe_id
            FROM usuarios
            WHERE id = ?
              AND COALESCE(disabled, 0) = 0
        """, (jefe_id,))
        j = cur.fetchone()

        if not j:
            break

        last_valid = j["id"]
        jefe_id = j["jefe_id"]

    return last_valid


def enqueue_gasto_approved(conn: sqlite3.Connection, gasto_id: int, area: str, approved_by_user_id: int | None):
    """
    Encola notificaciones por aprobación de gasto:
    (A) al creador
    (B) al siguiente aprobador (según area)
    """

    ensure_notify_schema(conn)
    ensure_gasto_templates(conn)  # <-- clave para evitar FK fail por template_key

    cur = conn.cursor()

    _log("info", "[ENQUEUE_GASTO] start gasto_id=%s area=%s approved_by=%s", gasto_id, area, approved_by_user_id)

    row = cur.execute("""
        SELECT id, usuario_id
        FROM gastos_tarjeta
        WHERE id=?
    """, (int(gasto_id),)).fetchone()
    if not row:
        _log("warning", "[ENQUEUE_GASTO] gasto no existe: %s", gasto_id)
        return

    creator_id = int(row["usuario_id"])

    # valida creador existe (por si la FK es hacia usuarios)
    uok = cur.execute("SELECT 1 FROM usuarios WHERE id=? LIMIT 1", (creator_id,)).fetchone()
    if not uok:
        _log("warning", "[ENQUEUE_GASTO] creator_id no existe en usuarios: %s", creator_id)
        return

    area_key = (area or "").lower().strip()
    if area_key == "ga":
        next_roles = ("gerente general",)
        template_next = "gasto_next_gg"
    elif area_key == "gg":
        next_roles = ("gerente financiero",)
        template_next = "gasto_next_gf"
    elif area_key == "gf":
        next_roles = ("coordinador", "admin")
        template_next = "gasto_next_coord"
    else:
        next_roles = ()
        template_next = "gasto_next"

    next_users = []
    if next_roles:
        placeholders = ",".join(["?"] * len(next_roles))
        next_users = cur.execute(
            f"""
            SELECT id
            FROM usuarios
            WHERE LOWER(rol) IN ({placeholders})
              AND COALESCE(disabled,0)=0
            """,
            tuple([r.lower() for r in next_roles])
        ).fetchall()

    payload = json.dumps({
        "gasto_id": int(gasto_id),
        "area": area_key,
        "approved_by_user_id": approved_by_user_id,
    })

    sched = _next_5min_sqlite()

    # (A) Notificar al CREADOR
    _exec_retry(cur, f"""
        INSERT OR IGNORE INTO notify_queue
            (user_id, tipo, fecha_obj, canal, template_key, payload_json, scheduled_at, estado,
             gasto_id, area, event_key)
        VALUES (?,?,?,?,?, ?, {sched}, 'pending', ?, ?, ?)
    """, (
        creator_id,
        "gasto_aprobado_user",
        date.today().isoformat(),
        "email",
        "gasto_user_approved",
        payload,
        gasto_id,
        area_key,
        f"{gasto_id}:{area_key}:user"
    ))

    # (B) Notificar al SIGUIENTE aprobador
    for u in next_users:
        uid = int(u["id"])
        _exec_retry(cur, f"""
            INSERT OR IGNORE INTO notify_queue
                (user_id, tipo, fecha_obj, canal, template_key, payload_json, scheduled_at, estado,
                 gasto_id, area, event_key)
            VALUES (?,?,?,?,?, ?, {sched}, 'pending', ?, ?, ?)
        """, (
            uid,
            "gasto_aprobado_next",
            date.today().isoformat(),
            "email",
            template_next,
            payload,
            gasto_id,
            area_key,
            f"{gasto_id}:{area_key}:next:{uid}"
        ))

    conn.commit()
    _log("info", "[ENQUEUE_GASTO] done gasto_id=%s area=%s next_users=%s", gasto_id, area_key, len(next_users))



#def enqueue_gasto_rejected_gg(conn: sqlite3.Connection, gasto_id: int, by_user_id: int | None):
def enqueue_gasto_rejected_gg(conn, gasto_id: int, by_user_id: int, comentario: str = ""):
    import json

    cur = conn.cursor()

    # En SQL Server ya existen las tablas / templates
    # ensure_notify_schema(conn)
    # ensure_gasto_templates(conn)

    cur.execute("""
        SELECT
            g.id,
            g.usuario_id,
            COALESCE(g.proveedor, '') AS proveedor,
            COALESCE(g.motivo, '') AS motivo,
            COALESCE(CAST(g.fecha AS NVARCHAR(20)), '') AS fecha
        FROM gastos_tarjeta g
        WHERE g.id = ?
    """, (gasto_id,))
    row = cur.fetchone()

    if not row:
        raise RuntimeError(f"Gasto no encontrado: {gasto_id}")

    try:
        gasto_usuario_id = row["usuario_id"]
        proveedor = row["proveedor"] or ""
        motivo = row["motivo"] or ""
        fecha = row["fecha"] or ""
    except Exception:
        gasto_usuario_id = row[1]
        proveedor = row[2] or ""
        motivo = row[3] or ""
        fecha = row[4] or ""

    gerente_id = _get_ultimo_jefe_id(conn, gasto_usuario_id, fallback_to_self=False)
    gerente = _get_user_contact(conn, gerente_id) if gerente_id else None

    if not gerente:
        raise RuntimeError("No se encontró gerente para notificar")

    destinatario = (gerente.get("email") or "").strip()
    if not destinatario:
        raise RuntimeError("El gerente no tiene email configurado")

    by_username = _get_username(conn, by_user_id)

    payload_obj = {
        "gasto_id": int(gasto_id),
        "comentario": comentario or "",
        "proveedor": proveedor,
        "motivo": motivo,
        "fecha": fecha,
        "by_user_id": by_user_id,
        "by_username": by_username,
        "gerente_id": gerente.get("id"),
        "gerente_nombre": gerente.get("nombre"),
        "gerente_email": destinatario,
    }

    payload = json.dumps(payload_obj, ensure_ascii=False)
    event_key = f"gasto_rejected_gg:{int(gasto_id)}:{int(by_user_id)}"
    tipo = "gasto_rejected_gg"
    user_id = int(gerente.get("id"))
    area = "gg"
    channel = "email"
    status = "pending"
    attempts = 0
    scheduled_at = None

    _exec_retry(cur, """
    IF NOT EXISTS (
        SELECT 1
        FROM notify_queue
        WHERE event_key = ?
    )
    BEGIN
        INSERT INTO notify_queue (
            tipo,
            user_id,
            gasto_id,
            area,
            channel,
            destinatario,
            payload,
            status,
            attempts,
            scheduled_at,
            created_at,
            comentario,
            event_key
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, GETDATE(), ?, ?
        )
    END
    """, (
        event_key,
        tipo,
        user_id,
        gasto_id,
        area,
        channel,
        destinatario,
        payload,
        status,
        attempts,
        scheduled_at,
        comentario,
        event_key,
    ))

    conn.commit()
    return True
#=========================================================
# Tareas del usuario para una fecha (por user_id) + LOG SQL
# ============================================================
def _tareas_para_usuario_en_fecha(conn, user_id: int, fecha_iso: str):
    sql_condicion_fecha = """
      (
        t.frecuencia = 'Diario'
        OR (
          t.frecuencia = 'Semanal'
          AND (t.dia_semana IS NULL OR t.dia_semana = ((CAST(strftime('%w', ?) AS INTEGER) + 6) % 7))
        )
        OR (
          t.frecuencia = 'Mensual'
          AND (t.dia_mes IS NULL OR t.dia_mes = CAST(strftime('%d', ?) AS INTEGER))
        )
      )
    """

    sql = f"""
      SELECT
        t.id, t.nombre, t.frecuencia,
        d.nombre AS departamento,
        r.nombre AS responsable,
        CASE WHEN EXISTS (
          SELECT 1 FROM plan_checks c
          WHERE c.tarea_id = t.id AND c.fecha = ?
        ) THEN 1 ELSE 0 END AS hecha
      FROM plan_tareas t
      JOIN plan_responsables r ON r.id = t.responsable_id
      JOIN usuarios u ON LOWER(u.username) = LOWER(r.nombre)
      LEFT JOIN departamentos d ON d.id = t.departamento_id
      WHERE t.activo = 1
        AND {sql_condicion_fecha}
        AND u.id = ?
      ORDER BY d.nombre, t.nombre
    """

    # Orden correcto para estos ? :
    # 1) c.fecha = ?        -> fecha_iso
    # 2) strftime('%w', ?)  -> fecha_iso
    # 3) strftime('%d', ?)  -> fecha_iso
    # 4) u.id = ?           -> user_id
    params = (fecha_iso, fecha_iso, fecha_iso, user_id)

    _log("info", "SQL tareas_dia:\n%s", _format_sql_for_log(sql, params))
    rows = conn.execute(sql, params).fetchall()
    _log("info", "tareas_dia -> %d filas. Ejemplos: %s",
         len(rows), [(r["id"], r["nombre"]) for r in rows[:5]])

    return [
        {
            "id": r["id"],
            "tarea": r["nombre"],      # alias para tu plantilla
            "nombre": r["nombre"],
            "frecuencia": r["frecuencia"],
            "departamento": r["departamento"],
            "responsable": r["responsable"],
            "hecha": bool(r["hecha"]),
        } for r in rows
    ]


def auto_close_expired_tasks():
    """Busca tareas cuya fecha_fin ya pasó y las marca como 'Terminado'."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    ahora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        # 1. Identificar cuántas se van a cerrar (opcional, para el log)
        cur.execute("""
            SELECT COUNT(*) FROM tareas 
            WHERE estado NOT IN ('Terminado', 'Cerrado por sistema') 
              AND fecha_fin IS NOT NULL 
              AND fecha_fin < ?
        """, (ahora,))
        count = cur.fetchone()[0]

        if count > 0:
            # 2. Actualizar estado y establecer fecha_cierre_real si está vacía
            cur.execute("""
                UPDATE tareas
                SET estado = 'Terminado',
                    fecha_cierre_real = COALESCE(fecha_cierre_real, ?)
                WHERE estado NOT IN ('Terminado', 'Cerrado por sistema')
                  AND fecha_fin IS NOT NULL
                  AND fecha_fin < ?
            """, (ahora, ahora))
            
            conn.commit()
            _log("info", "Scheduler: Se cerraron automáticamente %d tareas vencidas.", count)
    except Exception as e:
        _log("error", "Scheduler: Error en auto_close_expired_tasks -> %s", e)
    finally:
        conn.close()

# ============================================================
# Planificador (crea items 'hoy' por usuario y canal)
# ============================================================
def plan_notifications():
    conn = get_db_standalone()
    try:
        ensure_schema(conn)
        ensure_notify_schema(conn)
        ensure_core_templates(conn)  # <-- CLAVE para evitar FK fail con tarea_hoy

        cur = conn.cursor()
        today = date.today().isoformat()

        _log("info", "Planificador: revisando tareas para HOY (%s)…", today)

        # ✅ NO se toca tu lógica: este SELECT es el mismo que pegaste
        sql_u = """
          SELECT DISTINCT u.id AS user_id, u.username
          FROM plan_tareas t
          JOIN plan_responsables r ON r.id = t.responsable_id
          JOIN usuarios u ON LOWER(u.username)=LOWER(r.nombre)
          WHERE t.activo=1
            AND (
              t.frecuencia='Diario'
              OR (t.frecuencia='Semanal' AND (t.dia_semana IS NULL OR t.dia_semana = ((CAST(strftime('%w','now','localtime') AS INTEGER)+6)%7)))
              OR (t.frecuencia='Mensual' AND (t.dia_mes IS NULL OR t.dia_mes = CAST(strftime('%d','now','localtime') AS INTEGER)))
            )
        """
        _log("debug", "SQL usuarios_hoy:\n%s", sql_u)
        usuarios_hoy = cur.execute(sql_u).fetchall()

        inserted = 0
        sched = _next_5min_sqlite()  # ⏱️ programar al próximo múltiplo de 5 min

        for u in usuarios_hoy:
            base_ctx = {
                "usuario": u["username"],
                "fecha": today,
                "app_url": current_app.config.get("APP_URL", "")
            }
            payload = json.dumps(base_ctx)
 
            for canal in ("inapp", "email"):
                _exec_retry(cur, f"""
                    INSERT OR IGNORE INTO notify_queue
                        (user_id, tipo, fecha_obj, canal, template_key, payload_json, scheduled_at, estado)
                    VALUES (?,?,?,?,?,?, {sched}, 'pending')
                """, (u["user_id"], "hoy", today, canal, "tarea_hoy", payload))
                inserted += (cur.rowcount or 0)

        conn.commit()
        _log("info", "Planificador: usuarios HOY planificados -> %d", inserted)

    except Exception as e:
        _log("error", "Planificador: fallo -> %s", e)
    finally:
        try:
            conn.close()
        except Exception:
            pass


# ============================================================
# Envíos por canal (usan conexiones efímeras)
# ============================================================
def _send_email(to_email: str, subj: str, html: str, text: Optional[str] = None):
    c = get_db_standalone()
    try:
        send_mail_planilla(c, to_email, subj, html, text=text, attachments=None)
    finally:
        try:
            c.close()
        except Exception:
            pass


def _send_inapp(title: str, body: str, user_id: int):
    conn = get_db_standalone()
    try:
        _exec_retry(conn.cursor(), """
          INSERT INTO notify_inapp(user_id, title, body, created_at, is_read)
          VALUES (?,?,?,?,0)
        """, (user_id, title, body, datetime.utcnow().isoformat(timespec="seconds")))
        conn.commit()
    finally:
        conn.close()


def _send_slack(webhook: str, text: str):
    _log("info", "[SLACK] %s -> %s", webhook, text)


# ============================================================
# Dispatcher (procesa pendientes; una conexión por item)
#  🔥 CAMBIO CLAVE anti-spam:
#  - "claim" del item: pasar de pending -> sending ANTES de enviar
#  - si ya no está pending, se salta
# ============================================================
 

def dispatch_notifications():
    # obtener IDs primero
    c0 = get_db_standalone()
    try:
        sql_ids = """
            SELECT id
              FROM notify_queue
             WHERE estado='pending'
               AND (scheduled_at IS NULL OR scheduled_at <= datetime('now'))
             ORDER BY id
             LIMIT 100
        """
        _log("debug", "SQL queue_ids:\n%s", sql_ids)
        ids = [r["id"] for r in c0.execute(sql_ids).fetchall()]
    finally:
        c0.close()

    if not ids:
        _log("info", "Dispatcher: no hay notificaciones pendientes.")
        return

    _log("info", "Dispatcher: procesando %d notificaciones…", len(ids))

    def _money_fmt(v) -> str:
        # 1234.56 -> "1.234,56"
        try:
            n = float(v or 0.0)
        except Exception:
            n = 0.0
        s = f"{n:,.2f}"
        return s.replace(",", "X").replace(".", ",").replace("X", ".")

    def _table_exists(conn, name: str) -> bool:
        try:
            r = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
                (name,)
            ).fetchone()
            return bool(r)
        except Exception:
            return False

    def _cols(conn, table: str):
        try:
            return [r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        except Exception:
            return []

    def _fetch_gasto_info(conn, gid: int) -> dict:
        """
        proveedor: terceros.nombre (tipo='P', activo=1)
        motivo:    gastos_tarjeta.motivo
        fecha:     gastos_tarjeta.fecha (si existe)
        total:     gastos_tarjeta.total_con_iva
        creador:   usuarios.username
        """
        out = {}

        if not _table_exists(conn, "gastos_tarjeta"):
            return out

        gcols = _cols(conn, "gastos_tarjeta")

        # columnas esperadas
        fecha_ok   = "fecha" in gcols
        motivo_ok  = "motivo" in gcols
        total_ok   = "total_con_iva" in gcols
        prov_id_ok = "proveedor_id" in gcols

        # proveedor desde terceros (solo tipo P)
        join_terceros = ""
        proveedor_select = "'' AS proveedor"
        if _table_exists(conn, "terceros") and prov_id_ok:
            proveedor_select = "COALESCE(t.nombre,'') AS proveedor"
            join_terceros = (
                "LEFT JOIN terceros t "
                "ON t.id = g.proveedor_id "
                "AND t.tipo='P' "
                "AND COALESCE(t.activo,1)=1"
            )

        select_parts = ["g.id AS gid"]

        if fecha_ok:
            select_parts.append("g.fecha AS fecha")
        if motivo_ok:
            select_parts.append("g.motivo AS motivo")
        if total_ok:
            select_parts.append("g.total_con_iva AS total_con_iva")

        # creador
        if _table_exists(conn, "usuarios"):
            select_parts.append("u.username AS creador")
            join_users = "LEFT JOIN usuarios u ON u.id = g.usuario_id"
        else:
            select_parts.append("'' AS creador")
            join_users = ""

        select_parts.append(proveedor_select)

        sql = f"""
            SELECT {", ".join(select_parts)}
              FROM gastos_tarjeta g
              {join_users}
              {join_terceros}
             WHERE g.id=?
             LIMIT 1
        """

        try:
            row = conn.execute(sql, (int(gid),)).fetchone()
            if not row:
                return out
            d = dict(row)
        except Exception:
            return out

        if fecha_ok:
            out["fecha_gasto"] = str(d.get("fecha") or "")
        if motivo_ok:
            out["motivo"] = str(d.get("motivo") or "")          # ✅ MOTIVO SALE DE g.motivo
        if total_ok:
            out["total_con_iva"] = d.get("total_con_iva")
        out["proveedor"] = str(d.get("proveedor") or "")
        out["creador"] = str(d.get("creador") or "")
        return out

    def _fmt_fecha_ddmmyyyy_local(fecha_str: str) -> str:
        """
        Convierte YYYY-MM-DD a DD/MM/YYYY (como tu captura).
        Si no cumple, devuelve tal cual.
        """
        f = (fecha_str or "").strip()
        try:
            if len(f) >= 10 and f[4] == "-" and f[7] == "-":
                return f"{f[8:10]}/{f[5:7]}/{f[0:4]}"
        except Exception:
            pass
        return f

    for nid in ids:
        conn = get_db_standalone()
        try:
            cur = conn.cursor()

            # ✅ CLAIM: evita reenvíos si algo truena después de enviar
            _exec_retry(cur, """
                UPDATE notify_queue
                   SET estado='sending', error_msg=NULL
                 WHERE id=?
                   AND estado='pending'
            """, (nid,))
            conn.commit()
            if (cur.rowcount or 0) == 0:
                conn.close()
                continue

            # leer fila con joins
            sql_row = """
              SELECT q.*, u.email, u.username,
                     COALESCE(p.email_on,1)  AS email_on,
                     COALESCE(p.inapp_on,1)  AS inapp_on,
                     COALESCE(p.slack_on,0)  AS slack_on,
                     p.slack_webhook, p.quiet_start, p.quiet_end,
                     nt.subject, nt.html, nt.text
                FROM notify_queue q
                JOIN usuarios u ON u.id = q.user_id
                LEFT JOIN notify_user_prefs p ON p.user_id = q.user_id
                LEFT JOIN notify_templates nt ON nt.key = q.template_key
               WHERE q.id=?
            """
            _log("debug", "SQL queue_row:\n%s", _format_sql_for_log(sql_row, (nid,)))
            r0 = conn.execute(sql_row, (nid,)).fetchone()
            if not r0:
                _exec_retry(cur, "UPDATE notify_queue SET estado='skipped', error_msg=? WHERE id=?",
                            ("Fila no encontrada", nid))
                conn.commit()
                conn.close()
                continue

            r = dict(r0)
            payload = json.loads(r.get("payload_json") or "{}")
            # ✅ si viene comentario en la fila, pásalo al payload para plantillas
            try:
                payload.setdefault("comentario", (r.get("comentario") or "").strip())
            except Exception:
                payload.setdefault("comentario", "")

            # Prepara payload si es "hoy"
            if r.get("tipo") == "hoy":
                from datetime import date as _date
                fecha_iso = r.get("fecha_obj") or _date.today().isoformat()
                tareas_hoy = _tareas_para_usuario_en_fecha(conn, r["user_id"], fecha_iso)
                payload.update({
                    "usuario": r["username"],
                    "fecha": fecha_iso,
                    "tareas_hoy": tareas_hoy,
                    "tareas_hoy_len": len(tareas_hoy),
                    "app_url": payload.get("app_url") or current_app.config.get("APP_URL", ""),
                })
                _log("debug", "dispatch 'hoy': user_id=%s usuario=%s fecha=%s tareas_hoy_len=%s",
                     r["user_id"], r["username"], fecha_iso, len(tareas_hoy))
            else:
                from datetime import date as _date
                payload.setdefault("usuario", r["username"])
                payload.setdefault("fecha", r.get("fecha_obj") or _date.today().isoformat())

                # ✅ URLs base
                base = (current_app.config.get("PUBLIC_BASE_URL")
                        or current_app.config.get("APP_URL")
                        or "").rstrip("/")
                payload.setdefault("app_url", base)

                # ✅ Enriquecimiento para GASTOS (incluye: proveedor + motivo desde g.motivo)
                is_gasto = (str(r.get("tipo") or "").startswith("gasto_")
                            or str(r.get("template_key") or "").startswith("gasto_"))
                if is_gasto:
                    gid = payload.get("gasto_id") or r.get("gasto_id")
                    try:
                        gid_int = int(gid) if gid is not None else None
                    except Exception:
                        gid_int = None

                    if gid_int is not None:
                        info = _fetch_gasto_info(conn, gid_int)

                        payload.setdefault("gasto_id", gid_int)

                        # ✅ PROVEEDOR (terceros.nombre tipo P)
                        payload.setdefault("proveedor", info.get("proveedor", ""))

                        # ✅ MOTIVO (gastos_tarjeta.motivo)
                        payload.setdefault("motivo", info.get("motivo", ""))

                        payload.setdefault("creador", info.get("creador", ""))

                        # fecha del gasto real (si existe) -> dd/mm/yyyy
                        if info.get("fecha_gasto"):
                            payload["fecha"] = _fmt_fecha_ddmmyyyy_local(info.get("fecha_gasto", ""))

                        # total formateado
                        if "total_con_iva" not in payload or payload.get("total_con_iva") in (None, ""):
                            if "total_con_iva" in info:
                                payload["total_con_iva"] = info.get("total_con_iva")
                        payload.setdefault("total_con_iva_fmt", _money_fmt(payload.get("total_con_iva")))

                        # URL detalle
                        if base:
                            payload.setdefault("gasto_url", f"{base}/reembolsos/gastos/{gid_int}/ver")
                        else:
                            payload.setdefault("gasto_url", f"/reembolsos/gastos/{gid_int}/ver")
                    else:
                        payload.setdefault("proveedor", "")
                        payload.setdefault("motivo", "")
                        payload.setdefault("creador", "")
                        payload.setdefault("total_con_iva_fmt", _money_fmt(0))
                        payload.setdefault("gasto_url", payload.get("app_url") or "")

            # 🔥 Si falta plantilla (subject/html NULL), marcamos error y NO reintenta infinito
            if not r.get("subject") or not r.get("html"):
                _exec_retry(cur, """
                    UPDATE notify_queue
                       SET estado='error',
                           error_msg=?,
                           sent_at=datetime('now')
                     WHERE id=?
                """, (f"Plantilla inexistente o incompleta: {r.get('template_key')}", nid))
                conn.commit()
                conn.close()
                continue

            # Render dentro de contexto Flask
            with current_app.test_request_context('/'):
                subject = render_template_string(r["subject"], **payload)
                html = render_template_string(r["html"], **payload)
                text = render_template_string(r["text"], **payload) if r.get("text") else None

            # Quiet hours
            if _is_quiet(datetime.now().time(), r.get("quiet_start"), r.get("quiet_end")):
                _exec_retry(cur, "UPDATE notify_queue SET estado='skipped', error_msg=NULL WHERE id=?", (nid,))
                conn.commit()
                conn.close()
                continue

            ok = False

            # ✅ GASTOS: si quieres que el dispatcher también los procese por aquí, puedes activar esto.
            # (se mantiene igual, comentado)
            #
            # if (r.get("tipo") or "").startswith("gasto_"):
            #     p = json.loads(r.get("payload_json") or "{}")
            #     gasto_id = r.get("gasto_id") or p.get("gasto_id")
            #     area = r.get("area") or p.get("area")
            #     approved_by = p.get("approved_by_user_id")
            #     ok = bool(notify_gasto_approved(current_app._get_current_object(), int(gasto_id), str(area), approved_by))
            # else:

            if r["canal"] == "email" and r.get("email_on") and r.get("email"):
                _send_email(r["email"], subject, html, text)
                ok = True
            elif r["canal"] == "inapp" and r.get("inapp_on"):
                _send_inapp(subject, text or subject, r["user_id"])
                ok = True
            elif r["canal"] == "slack" and r.get("slack_on") and r.get("slack_webhook"):
                _send_slack(r["slack_webhook"], text or subject)
                ok = True

            if ok:
                _exec_retry(cur, """
                    UPDATE notify_queue
                       SET estado='sent',
                           error_msg=NULL,
                           sent_at=datetime('now')
                     WHERE id=?
                """, (nid,))
            else:
                _exec_retry(cur, """
                    UPDATE notify_queue
                       SET estado='skipped',
                           error_msg=NULL,
                           sent_at=datetime('now')
                     WHERE id=?
                """, (nid,))

            conn.commit()

        except Exception as e:
            try:
                _exec_retry(conn.cursor(), """
                    UPDATE notify_queue
                       SET estado='error',
                           error_msg=?,
                           sent_at=datetime('now')
                     WHERE id=?
                """, (str(e), nid))
                conn.commit()
            except Exception:
                pass
            _log("error", "Dispatcher: error id=%s -> %s", nid, e)
        finally:
            try:
                conn.close()
            except Exception:
                pass

# ============================================================
# Jobs auxiliares
# ============================================================
def notify_overdue():
    conn = get_db_standalone()
    try:
        ensure_notify_schema(conn)
        cur = conn.cursor()

        cur.execute("""
            SELECT t.id, t.titulo, t.fecha_fin, t.estado, t.notificado,
                   u.id AS user_id, u.username AS username, u.email AS user_email
              FROM tareas t
              JOIN usuarios u ON t.usuario_id = u.id
             WHERE t.estado != 'Terminado'
               AND COALESCE(t.notificado,0)=0
               AND datetime(t.fecha_fin) < datetime('now')
        """)

        # Migración suave: agrega is_read si falta
        #try:
        #    cur.execute("SELECT is_read FROM notify_inapp LIMIT 1")
        #except Exception:
        #    _exec_retry(cur, "ALTER TABLE notify_inapp ADD COLUMN is_read INTEGER NOT NULL DEFAULT 0")

        tasks = cur.fetchall()
        if not tasks:
            _log("info", "Overdue: 0 tareas.")
            return

        # ✅ detectar si viene como Row o tuple
        is_row = (len(tasks) > 0 and hasattr(tasks[0], "keys"))

        for t in tasks:
            if is_row:
                user_email = t.get("user_email") if hasattr(t, "get") else t["user_email"]
                username   = t.get("username")   if hasattr(t, "get") else t["username"]
                tid        = t.get("id")         if hasattr(t, "get") else t["id"]
                titulo     = t.get("titulo")     if hasattr(t, "get") else t["titulo"]
                fecha_fin  = t.get("fecha_fin")  if hasattr(t, "get") else t["fecha_fin"]
            else:
                # orden del SELECT:
                # 0 id,1 titulo,2 fecha_fin,3 estado,4 notificado,5 user_id,6 username,7 user_email
                tid       = t[0]
                titulo    = t[1]
                fecha_fin = t[2]
                username  = t[6]
                user_email= t[7]

            if user_email:
                try:
                    _send_email(
                        user_email,
                        f"Tarea pendiente: {titulo}",
                        f"La tarea <b>{titulo}</b> (usuario {username}) venció el {fecha_fin} y no ha sido cerrada.",
                        None
                    )
                except Exception as e:
                    _log("error", "Overdue: enviar correo tarea_id=%s -> %s", tid, e)
                    continue

            _exec_retry(cur, "UPDATE tareas SET notificado=1, estado='Atrasada' WHERE id=?", (tid,))
        conn.commit()
        _log("info", "Overdue: marcadas %d.", len(tasks))
    finally:
        try:
            conn.close()
        except Exception:
            pass


def send_daily_report():
    today = datetime.now().strftime('%Y-%m-%d')
    conn = get_db_standalone()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT t.id, t.titulo, t.descripcion, t.estado, t.fecha_creacion,
                   t.fecha_inicio, t.fecha_fin, u.username AS usuario
              FROM tareas t
              JOIN usuarios u ON t.usuario_id = u.id
             WHERE date(t.fecha_creacion) = ?
             ORDER BY t.id
        """, (today,))
        rows = cur.fetchall()

        cur2 = conn.cursor()
        cur2.execute("SELECT email FROM usuarios WHERE rol='admin'")
        admin_emails = [r['email'] for r in cur2.fetchall() if r['email']]
        if not admin_emails:
            _log("warning", "DailyReport: no hay admin emails.")
            return

        lines = ["📅 Tareas registradas hoy"]
        if rows:
            for r in rows:
                lines += [
                    "",
                    f"📝 ID {r['id']}: {r['titulo']}",
                    f"📄 {r['descripcion'] or 'Sin descripción'}",
                    f"🚦 Estado: {r['estado']}",
                    f"📅 Creación: {r['fecha_creacion']}",
                    f"⏳ Inicio: {r['fecha_inicio'] or '—'}",
                    f"✅ Fin: {r['fecha_fin'] or '—'}",
                    f"👤 Usuario: {r['usuario']}",
                ]
        else:
            lines += ["", "No se registraron tareas hoy."]

        try:
            _send_email(
                admin_emails[0],
                f"Reporte de tareas del {today}",
                "<pre>"+("\n".join(lines))+"</pre>",
                "\n".join(lines)
            )
            _log("info", "DailyReport: enviado a %s", admin_emails[0])
        except Exception as e:
            _log("error", "DailyReport: enviar -> %s", e)

    finally:
        try:
            conn.close()
        except Exception:
            pass


# ============================================================
# Worker
# ============================================================
_worker_started = False

def start_scheduler(app=None):
    """
    Hilo de fondo:
    - bootstrap inicial
    - espera corta para no chocar con el arranque del app
    - primera corrida controlada
    - luego loop cada ~5 min

    OM:
    - SOLO se ejecuta una vez al día a las 08:00
    """
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
            # 1) cierre automático tareas
            try:
                _log("info", "Worker: Ejecutando cierre automático de tareas...")
                auto_close_expired_tasks()
                _log("info", "Worker: cierre automático de tareas OK")
            except Exception:
                target_app.logger.exception("Worker: auto_close_expired_tasks falló")

            # 2) expiración gastos
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

            # 3) notificaciones OM -> SOLO si run_om=True
            #if run_om:
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

            # 4) planificar notificaciones
            try:
                _log("info", "Worker: Ejecutando plan_notifications...")
                plan_notifications()
                _log("info", "Worker: plan_notifications OK")
            except Exception:
                target_app.logger.exception("Worker: plan_notifications falló")

            # 5) despachar notificaciones
            try:
                _log("info", "Worker: Ejecutando dispatch_notifications...")
                dispatch_notifications()
                _log("info", "Worker: dispatch_notifications OK")
            except Exception:
                target_app.logger.exception("Worker: dispatch_notifications falló")

        except Exception:
            target_app.logger.exception("Worker: fallo general en %s", tick_label)

        elapsed = time.time() - start
        _log("info", "Worker: %s end elapsed=%.2fs", tick_label, elapsed)

    def _loop(target_app):
        with target_app.app_context():
            _log("info", "Worker: entrando al hilo de scheduler...")

            # =========================================================
            # Bootstrap inicial
            # =========================================================
            try:
                c0 = get_db_standalone()
                try:
                    _log("info", "Worker: bootstrap inicial - preparando esquemas y plantillas...")

                    ensure_notify_schema(c0)
                    _log("info", "Worker: ensure_notify_schema OK")

                    ensure_schema(c0)
                    _log("info", "Worker: ensure_schema OK")

                    ensure_core_templates(c0)
                    _log("info", "Worker: ensure_core_templates OK")

                    ensure_gasto_templates(c0)
                    _log("info", "Worker: ensure_gasto_templates OK")

                    ensure_gastos_expiry_schema(c0)
                    _log("info", "Worker: ensure_gastos_expiry_schema OK")

                    ensure_om_notification_schema(c0)
                    _log("info", "Worker: ensure_om_notification_schema OK")

                    ensure_om_templates(c0)
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

            # =========================================================
            # Primera corrida controlada
            # IMPORTANTE: aquí NO corremos OM para evitar envíos inmediatos
            # =========================================================
            _run_tick(target_app, "FIRST_RUN", run_om=False)

            last_overdue = time.time()
            last_daily_date = None
            last_om_date = None   # <- controla ejecución diaria de OM a las 08:00

            # =========================================================
            # Loop normal cada ~5 minutos
            # =========================================================
            while True:
                cycle_start = time.time()
                now = datetime.now()
                tick_id = now.strftime("%Y-%m-%d %H:%M:%S")

                # OM solo una vez al día a las 08:00
                run_om_now = False
                #if now.hour == 8 and last_om_date != now.date():
                #    run_om_now = True
                #    last_om_date = now.date()
                _log("info", "Worker: OM programado para ejecución diaria de las 08:00")

                _run_tick(target_app, f"TICK {tick_id}", run_om=run_om_now)

                # overdue cada 30 min
                now_ts = time.time()
                if now_ts - last_overdue >= 1800:
                    try:
                        _log("info", "Worker: Ejecutando notify_overdue...")
                        notify_overdue()
                        last_overdue = now_ts
                        _log("info", "Worker: notify_overdue OK")
                    except Exception:
                        target_app.logger.exception("Worker: notify_overdue falló")

                # reporte diario 07:30
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

def ensure_gastos_expiry_schema(conn: sqlite3.Connection):
    """
    Agrega columnas para:
    - inactivar gasto por política (soft delete)
    - registrar aviso (día 6)
    - registrar inactivación (día 7)
    """
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info(gastos_tarjeta)")
    cols = {r[1] for r in cur.fetchall()}

    def add(col: str, typ: str):
        cur.execute(f"ALTER TABLE gastos_tarjeta ADD COLUMN {col} {typ}")

    # Soft delete / inactivación
    if "inactivo" not in cols:
        add("inactivo", "INTEGER NOT NULL DEFAULT 0")
    if "inactivo_at" not in cols:
        add("inactivo_at", "TEXT")
    if "inactivo_reason" not in cols:
        add("inactivo_reason", "TEXT")

    # Tracking correos
    if "warn_sent_at" not in cols:
        add("warn_sent_at", "TEXT")  # aviso día 6

    conn.commit()


# ============================================================
# OM / RECLAMOS - NOTIFICACIONES POR FALTA DE RESPUESTA SPONSOR
# ============================================================

def ensure_om_notification_schema(conn: sqlite3.Connection):
    """
    Tracking de avisos por sponsor en reclamo_imputados.
    Se guarda por imputación/sponsor, no por reclamo global.
    """
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(reclamo_imputados)")
    cols = {r[1] for r in cur.fetchall()}

    def add(col: str, ddl: str):
        cur.execute(f"ALTER TABLE reclamo_imputados ADD COLUMN {col} {ddl}")

    if "om_notif_d4_at" not in cols:
        add("om_notif_d4_at", "TEXT")
    if "om_notif_d5_at" not in cols:
        add("om_notif_d5_at", "TEXT")
    if "om_notif_d9_at" not in cols:
        add("om_notif_d9_at", "TEXT")
    if "om_notif_d10_at" not in cols:
        add("om_notif_d10_at", "TEXT")

    conn.commit()


def ensure_om_templates(conn: sqlite3.Connection):
    """
    Plantillas base para OM con cabecera visual por severidad:
    - Día 4  -> verde
    - Día 5  -> amarillo
    - Día 9  -> naranja
    - Día 10 -> rojo
    """
    ensure_notify_schema(conn)
    cur = conn.cursor()

    def upsert(key, tipo, subject, html, text):
        _exec_retry(cur, """
            INSERT INTO notify_templates(key, tipo, subject, html, text)
            VALUES (?,?,?,?,?)
            ON CONFLICT(key) DO UPDATE SET
                tipo    = excluded.tipo,
                subject = excluded.subject,
                html    = excluded.html,
                text    = excluded.text
        """, (key, tipo, subject, html, text))

    # =========================
    # HTML base tipo “card”
    # =========================
    html_base = """\
<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f3f4f6;font-family:Segoe UI,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:24px 0;">
      <tr>
        <td align="center">
          <table role="presentation" width="760" cellpadding="0" cellspacing="0"
                 style="max-width:760px;background:#ffffff;border-radius:10px;border:1px solid #e5e7eb;overflow:hidden;">

            <tr>
              <td style="background:{{ header_color }};padding:18px 22px;color:#ffffff;">
                <div style="font-size:12px;text-transform:uppercase;letter-spacing:.08em;opacity:.92;font-weight:700;">
                  OPORTUNIDAD DE MEJORA
                </div>
                <div style="font-size:22px;font-weight:800;margin-top:4px;line-height:1.15;">
                  {{ header_title }}
                </div>
                <div style="font-size:13px;opacity:.95;margin-top:8px;line-height:1.35;">
                  {{ header_subtitle }}
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:18px 22px 10px 22px;">
                <div style="font-size:14px;color:#111827;line-height:1.6;margin-bottom:14px;">
                  Hola {{ destinatario_nombre or sponsor_nombre or jefe_nombre or gg_nombre or sc_nombre or 'Usuario' }},
                </div>

                <div style="font-size:14px;color:#111827;line-height:1.6;margin-bottom:14px;">
                  {{ intro_text }}
                </div>

                <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                       style="border-collapse:separate;border-spacing:0;overflow:hidden;border-radius:10px;">
                  <tr>
                    <td style="width:260px;background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Código</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">{{ codigo }}</td>
                  </tr>
                  <tr>
                    <td style="background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Cliente</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">{{ cliente }}</td>
                  </tr>
                  <tr>
                    <td style="background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Proceso</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">{{ proceso }}</td>
                  </tr>
                  <tr>
                    <td style="background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Sponsor</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">{{ sponsor_nombre or 'No definido' }}</td>
                  </tr>
                  <tr>
                    <td style="background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Gerente del sponsor</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">{{ jefe_nombre or 'No definido' }}</td>
                  </tr>
                  <tr>
                    <td style="background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Servicio al Cliente</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">{{ sc_nombre or 'No definido' }}</td>
                  </tr>
                  <tr>
                    <td style="background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Observación</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;white-space:pre-wrap;">{{ observacion }}</td>
                  </tr>
                  <tr>
                    <td style="background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Día de notificación</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">{{ dia_label }}</td>
                  </tr>
                  <tr>
                    <td style="background:#eef2ff;font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Días transcurridos</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">{{ dias }}</td>
                  </tr>
                </table>

                <div style="margin-top:18px;">
                  <a href="{{ app_url }}"
                     style="display:inline-block;background:#2563eb;color:#ffffff;text-decoration:none;
                            padding:11px 18px;border-radius:8px;font-weight:700;font-size:13px;">
                    Revisar OM
                  </a>
                </div>

                <div style="font-size:12px;color:#6b7280;margin-top:12px;">
                  Este correo fue generado automáticamente por el sistema de Sili.
                </div>
              </td>
            </tr>

            <tr>
              <td style="padding:12px 22px 14px 22px;border-top:1px solid #e5e7eb;font-size:11px;color:#9ca3af;">
                Este es un mensaje automático. No responda a este correo.
              </td>
            </tr>

          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""

    # Día 4 - verde
    upsert(
        "om_sponsor_d4",
        "om",
        "🟢 OM {{ codigo }} - Alerta día 4",
        html_base,
        "OM {{ codigo }} - alerta día 4. Cliente: {{ cliente }}. Proceso: {{ proceso }}."
    )

    # Día 5 - amarillo
    upsert(
        "om_jefe_d5",
        "om",
        "🟡 OM {{ codigo }} - Seguimiento día 5",
        html_base,
        "OM {{ codigo }} - seguimiento día 5. Sponsor: {{ sponsor_nombre }}."
    )

    # Día 9 - naranja
    upsert(
        "om_sponsor_jefe_d9",
        "om",
        "🟠 OM {{ codigo }} - Seguimiento día 9",
        html_base,
        "OM {{ codigo }} - seguimiento día 9. Sponsor: {{ sponsor_nombre }}."
    )

    # Día 10 - rojo
    upsert(
        "om_gg_d10",
        "om",
        "🔴 OM {{ codigo }} - Escalamiento día 10",
        html_base,
        "OM {{ codigo }} - escalamiento día 10. Sponsor: {{ sponsor_nombre }}."
    )

    conn.commit()


def process_om_notifications(conn: sqlite3.Connection):
    _log("info", "[OM_NOTIFY] ===== INICIO process_om_notifications =====")

    ensure_notify_schema(conn)
    ensure_om_notification_schema(conn)
    ensure_om_templates(conn)

    cur = conn.cursor()

    sql = """
        SELECT
            ri.id AS imputacion_id,
            ri.reclamo_id,
            ri.imputado_id AS sponsor_id,

            COALESCE(ri.estado_asignacion, '') AS estado_asignacion,
            COALESCE(ri.estado_respuesta, '') AS estado_respuesta,

            COALESCE(ri.om_notif_d4_at, '')  AS om_notif_d4_at,
            COALESCE(ri.om_notif_d5_at, '')  AS om_notif_d5_at,
            COALESCE(ri.om_notif_d9_at, '')  AS om_notif_d9_at,
            COALESCE(ri.om_notif_d10_at, '') AS om_notif_d10_at,

            r.codigo,
            COALESCE(r.cliente_nombre, '') AS cliente,
            COALESCE(r.proceso_text, '') AS proceso,
            COALESCE(r.observacion, '') AS observacion,
            COALESCE(substr(r.fecha_creacion, 1, 10), '') AS fecha_base,

            CAST(julianday('now', 'localtime') - julianday(substr(r.fecha_creacion, 1, 10)) AS INTEGER) AS dias
        FROM reclamo_imputados ri
        JOIN reclamos r ON r.id = ri.reclamo_id
        WHERE ri.estado_asignacion = 'aprobado'
          AND COALESCE(TRIM(ri.estado_respuesta), 'sin_respuesta') = 'sin_respuesta'
          AND COALESCE(substr(r.fecha_creacion, 1, 10), '') <> ''
          AND substr(r.fecha_creacion, 1, 10) >= '2026-03-13'
    """

    _log("debug", "[OM_NOTIFY] SQL candidatos:\n%s", sql)

    rows = cur.execute(sql).fetchall()
    total_rows = len(rows)
    _log("info", "[OM_NOTIFY] candidatos encontrados=%s", total_rows)

    if not rows:
        _log("info", "[OM_NOTIFY] sin imputaciones pendientes")
        return

    today = date.today().isoformat()
    now_txt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    app_url = (current_app.config.get("PUBLIC_BASE_URL")
               or current_app.config.get("APP_URL")
               or "").rstrip("/")
    if app_url:
        app_url = f"{app_url}/reclamos?tab=tab-imputado"
    else:
        app_url = "/reclamos?tab=tab-imputado"

    enqueued = 0
    skipped = 0

    for r in rows:
        imputacion_id = int(r["imputacion_id"])
        sponsor_id = int(r["sponsor_id"])
        dias = int(r["dias"] or 0)
        codigo = r["codigo"] or ""

        d4_sent_today = _sent_today(r["om_notif_d4_at"], today)
        d5_sent_today = _sent_today(r["om_notif_d5_at"], today)
        d9_sent_today = _sent_today(r["om_notif_d9_at"], today)
        d10_sent_today = _sent_today(r["om_notif_d10_at"], today)

        _log(
            "info",
            "[OM_NOTIFY][ROW] imputacion_id=%s reclamo_id=%s sponsor_id=%s codigo=%s dias=%s d4_today=%s d5_today=%s d9_today=%s d10_today=%s",
            imputacion_id,
            r["reclamo_id"],
            sponsor_id,
            codigo,
            dias,
            d4_sent_today,
            d5_sent_today,
            d9_sent_today,
            d10_sent_today,
        )

        sponsor = _get_user_contact(conn, sponsor_id)
        if not sponsor:
            skipped += 1
            _log(
                "warning",
                "[OM_NOTIFY][SKIP] imputacion_id=%s codigo=%s motivo=sponsor_no_encontrado sponsor_id=%s",
                imputacion_id, codigo, sponsor_id
            )
            continue

        jefe_id = guess_gerente_area(conn, sponsor_id)
        jefe = _get_user_contact(conn, jefe_id) if jefe_id else None

        _log(
            "debug",
            "[OM_NOTIFY][CHAIN] imputacion_id=%s codigo=%s sponsor=%s jefe_id=%s jefe_nombre=%s",
            imputacion_id,
            codigo,
            (sponsor.get("nombre") or sponsor.get("username") or ""),
            jefe_id,
            ((jefe.get("nombre") or jefe.get("username") or "") if jefe else "")
        )

        payload_base = {
            "codigo": codigo,
            "cliente": r["cliente"] or "",
            "proceso": r["proceso"] or "",
            "observacion": r["observacion"] or "",
            "dias": dias,

            "sponsor_nombre": sponsor.get("nombre") or sponsor.get("username") or f"Usuario {sponsor_id}",
            "jefe_nombre": (jefe.get("nombre") or jefe.get("username") or f"Usuario {jefe_id}") if jefe else "No definido",
            "gg_nombre": "",
            "sc_nombre": "",

            "destinatario_nombre": "",
            "dia_label": "",
            "header_color": "#2563eb",
            "header_title": "",
            "header_subtitle": "",
            "intro_text": "",

            "app_url": app_url,
        }

        # =========================
        # D4 -> Sponsor (máx 1 vez por día)
        # =========================
        if dias >= 4 and not d4_sent_today:
            _log("info", "[OM_NOTIFY][D4] encolando sponsor imputacion_id=%s codigo=%s sponsor_id=%s", imputacion_id, codigo, sponsor_id)

           
            p = dict(payload_base)
            p["destinatario_nombre"] = sponsor.get("nombre") or sponsor.get("username") or f"Usuario {sponsor_id}"
            p["dia_label"] = "Día 4"
            p["header_color"] = "#16a34a"   # verde
            p["header_title"] = f"Alerta OM — Día 4 ({codigo})"
            p["header_subtitle"] = "Alerta temprana: la OM sigue pendiente de respuesta del sponsor."
            p["intro_text"] = (
                f"La Oportunidad de Mejora {codigo} aún no registra respuesta del sponsor "
                f"y ya alcanzó el día 4 desde su creación."
            )
            _enqueue_om_notification(
                conn,
                user_id=sponsor_id,
                tipo="om_d4",
                template_key="om_sponsor_d4",
                fecha_obj=today,
                payload=p,
                event_key=f"om:{imputacion_id}:d4:{today}:{sponsor_id}",
            )

            _exec_retry(
                cur,
                "UPDATE reclamo_imputados SET om_notif_d4_at = ? WHERE id = ?",
                (now_txt, imputacion_id)
            )
            enqueued += 1
        else:
            _log(
                "debug",
                "[OM_NOTIFY][D4] skip imputacion_id=%s codigo=%s dias=%s sent_today=%s",
                imputacion_id, codigo, dias, d4_sent_today
            )

        # =========================
        # D5 -> Jefe (máx 1 vez por día)
        # =========================
        if dias >= 5 and not d5_sent_today and jefe_id and jefe:
            _log("info", "[OM_NOTIFY][D5] encolando jefe imputacion_id=%s codigo=%s jefe_id=%s", imputacion_id, codigo, jefe_id)

        
            p = dict(payload_base)
            p["destinatario_nombre"] = jefe.get("nombre") or jefe.get("username") or f"Usuario {jefe_id}"
            p["dia_label"] = "Día 5"
            p["header_color"] = "#eab308"   # amarillo
            p["header_title"] = f"Seguimiento OM — Día 5 ({codigo})"
            p["header_subtitle"] = "Seguimiento al sponsor por falta de respuesta."
            p["intro_text"] = (
                f"La Oportunidad de Mejora {codigo} no ha sido respondida por el sponsor "
                f"{payload_base['sponsor_nombre']} y ya alcanzó el día 5."
            )
            _enqueue_om_notification(
                conn,
                user_id=jefe_id,
                tipo="om_d5",
                template_key="om_jefe_d5",
                fecha_obj=today,
                payload=p,
                event_key=f"om:{imputacion_id}:d5:{today}:{jefe_id}",
            )

            _exec_retry(
                cur,
                "UPDATE reclamo_imputados SET om_notif_d5_at = ? WHERE id = ?",
                (now_txt, imputacion_id)
            )
            enqueued += 1
        else:
            _log(
                "debug",
                "[OM_NOTIFY][D5] skip imputacion_id=%s codigo=%s dias=%s sent_today=%s jefe_id=%s",
                imputacion_id, codigo, dias, d5_sent_today, jefe_id
            )

        # =========================
        # D9 -> Sponsor + Jefe (máx 1 vez por día)
        # =========================
        if dias >= 9 and not d9_sent_today:
            _log("info", "[OM_NOTIFY][D9] encolando sponsor+jefe imputacion_id=%s codigo=%s", imputacion_id, codigo)

            p_s = dict(payload_base)
            p_s["destinatario_nombre"] = sponsor.get("nombre") or sponsor.get("username") or f"Usuario {sponsor_id}"
            p_s["dia_label"] = "Día 9"
            p_s["header_color"] = "#f97316"   # naranja
            p_s["header_title"] = f"Seguimiento OM — Día 9 ({codigo})"
            p_s["header_subtitle"] = "La OM continúa pendiente y requiere atención inmediata."
            p_s["intro_text"] = (
                f"La Oportunidad de Mejora {codigo} sigue sin respuesta y ya alcanzó el día 9."
            )

            _enqueue_om_notification(
                conn,
                user_id=sponsor_id,
                tipo="om_d9",
                template_key="om_sponsor_jefe_d9",
                fecha_obj=today,
                payload=p_s,
                event_key=f"om:{imputacion_id}:d9:{today}:sponsor:{sponsor_id}",
            )
            enqueued += 1

            if jefe_id and jefe:
          
                p_j = dict(payload_base)
                p_j["destinatario_nombre"] = jefe.get("nombre") or jefe.get("username") or f"Usuario {jefe_id}"
                p_j["dia_label"] = "Día 9"
                p_j["header_color"] = "#f97316"   # naranja
                p_j["header_title"] = f"Seguimiento OM — Día 9 ({codigo})"
                p_j["header_subtitle"] = "La OM continúa pendiente y requiere atención inmediata."
                p_j["intro_text"] = (
                    f"La Oportunidad de Mejora {codigo} sigue sin respuesta y ya alcanzó el día 9."
                )

                _enqueue_om_notification(
                    conn,
                    user_id=jefe_id,
                    tipo="om_d9",
                    template_key="om_sponsor_jefe_d9",
                    fecha_obj=today,
                    payload=p_j,
                    event_key=f"om:{imputacion_id}:d9:{today}:jefe:{jefe_id}",
                )
                enqueued += 1

            _exec_retry(
                cur,
                "UPDATE reclamo_imputados SET om_notif_d9_at = ? WHERE id = ?",
                (now_txt, imputacion_id)
            )
        else:
            _log(
                "debug",
                "[OM_NOTIFY][D9] skip imputacion_id=%s codigo=%s dias=%s sent_today=%s",
                imputacion_id, codigo, dias, d9_sent_today
            )

        # =========================
        # D10 -> GG + jefe + sponsor + servicio cliente (máx 1 vez por día)
        # =========================
        if dias >= 10 and not d10_sent_today:
            gg_ids = _get_gerente_general_ids(conn)
            sc_ids = _get_servicio_cliente_ids(conn)

            _log(
                "info",
                "[OM_NOTIFY][D10] encolando escalamiento imputacion_id=%s codigo=%s gg=%s sc=%s sponsor_id=%s jefe_id=%s",
                imputacion_id, codigo, len(gg_ids), len(sc_ids), sponsor_id, jefe_id
            )
            sc_nombres = []
            for sc_id_tmp in sc_ids:
                sc_contact = _get_user_contact(conn, sc_id_tmp)
                if sc_contact:
                    sc_nombres.append(
                        sc_contact.get("nombre") or sc_contact.get("username") or f"Usuario {sc_id_tmp}"
                    )

            sc_nombre_join = ", ".join(sc_nombres) if sc_nombres else "No definido"

            for gg_id in gg_ids:
                gg = _get_user_contact(conn, gg_id)
                if not gg:
                    _log("warning", "[OM_NOTIFY][D10] gg_id=%s sin contacto", gg_id)
                    continue

                p = dict(payload_base)
                gg_nombre = gg.get("nombre") or gg.get("username") or f"Usuario {gg_id}"

                p["gg_nombre"] = gg_nombre
                p["sc_nombre"] = sc_nombre_join
                p["destinatario_nombre"] = gg_nombre
                p["dia_label"] = "Día 10"
                p["header_color"] = "#dc2626"   # rojo
                p["header_title"] = f"Escalamiento OM — Día 10 ({codigo})"
                p["header_subtitle"] = "Escalamiento formal por falta de respuesta del sponsor."
                p["intro_text"] = (
                    f"La Oportunidad de Mejora {codigo} no registra respuesta del sponsor y ya alcanzó el día 10. "
                    f"Se escala el caso a Gerencia General con copia al jefe del sponsor, sponsor y Servicio al Cliente."
                )

                _enqueue_om_notification(
                    conn,
                    user_id=gg_id,
                    tipo="om_d10",
                    template_key="om_gg_d10",
                    fecha_obj=today,
                    payload=p,
                    event_key=f"om:{imputacion_id}:d10:{today}:gg:{gg_id}",
                )
                enqueued += 1

            if jefe_id and jefe:
                p = dict(payload_base)
                p = dict(payload_base)
                p["sc_nombre"] = sc_nombre_join
                p["destinatario_nombre"] = jefe.get("nombre") or jefe.get("username") or f"Usuario {jefe_id}"
                p["dia_label"] = "Día 10"
                p["header_color"] = "#dc2626"
                p["header_title"] = f"Escalamiento OM — Día 10 ({codigo})"
                p["header_subtitle"] = "Escalamiento formal por falta de respuesta del sponsor."
                p["intro_text"] = (
                    f"La Oportunidad de Mejora {codigo} no registra respuesta del sponsor y ya alcanzó el día 10. "
                    f"Se escala el caso a Gerencia General con copia al jefe del sponsor, sponsor y Servicio al Cliente."
                )
                _enqueue_om_notification(
                    conn,
                    user_id=jefe_id,
                    tipo="om_d10",
                    template_key="om_gg_d10",
                    fecha_obj=today,
                    payload=p,
                    event_key=f"om:{imputacion_id}:d10:{today}:jefe:{jefe_id}",
                )
                enqueued += 1

            p = dict(payload_base)
            p = dict(payload_base)
            p["sc_nombre"] = sc_nombre_join
            p["destinatario_nombre"] = sponsor.get("nombre") or sponsor.get("username") or f"Usuario {sponsor_id}"
            p["dia_label"] = "Día 10"
            p["header_color"] = "#dc2626"
            p["header_title"] = f"Escalamiento OM — Día 10 ({codigo})"
            p["header_subtitle"] = "Escalamiento formal por falta de respuesta del sponsor."
            p["intro_text"] = (
                f"La Oportunidad de Mejora {codigo} no registra respuesta del sponsor y ya alcanzó el día 10. "
                f"Se escala el caso a Gerencia General con copia al jefe del sponsor, sponsor y Servicio al Cliente."
            )

            _enqueue_om_notification(
                conn,
                user_id=sponsor_id,
                tipo="om_d10",
                template_key="om_gg_d10",
                fecha_obj=today,
                payload=p,
                event_key=f"om:{imputacion_id}:d10:{today}:sponsor:{sponsor_id}",
            )
            enqueued += 1

            for sc_id in sc_ids:
                p = dict(payload_base)
                sc_contact = _get_user_contact(conn, sc_id)

                p = dict(payload_base)
                p["sc_nombre"] = sc_nombre_join
                p["destinatario_nombre"] = (
                    (sc_contact.get("nombre") or sc_contact.get("username")) if sc_contact
                    else f"Usuario {sc_id}"
                )
                p["dia_label"] = "Día 10"
                p["header_color"] = "#dc2626"
                p["header_title"] = f"Escalamiento OM — Día 10 ({codigo})"
                p["header_subtitle"] = "Escalamiento formal por falta de respuesta del sponsor."
                p["intro_text"] = (
                    f"La Oportunidad de Mejora {codigo} no registra respuesta del sponsor y ya alcanzó el día 10. "
                    f"Se escala el caso a Gerencia General con copia al jefe del sponsor, sponsor y Servicio al Cliente."
                )
                _enqueue_om_notification(
                    conn,
                    user_id=sc_id,
                    tipo="om_d10",
                    template_key="om_gg_d10",
                    fecha_obj=today,
                    payload=p,
                    event_key=f"om:{imputacion_id}:d10:{today}:sc:{sc_id}",
                )
                enqueued += 1

            _exec_retry(
                cur,
                "UPDATE reclamo_imputados SET om_notif_d10_at = ? WHERE id = ?",
                (now_txt, imputacion_id)
            )
        else:
            _log(
                "debug",
                "[OM_NOTIFY][D10] skip imputacion_id=%s codigo=%s dias=%s sent_today=%s",
                imputacion_id, codigo, dias, d10_sent_today
            )

    conn.commit()
    _log(
        "info",
        "[OM_NOTIFY] ===== FIN process_om_notifications ===== candidatos=%s enqueued=%s skipped=%s",
        total_rows, enqueued, skipped
    )
def _sent_today(ts: str | None, today_iso: str) -> bool:
    """
    True si el timestamp/texto guardado pertenece al día de hoy.
    Acepta valores tipo:
    - '2026-03-13 15:30:52'
    - '2026-03-13'
    """
    v = (ts or "").strip()
    if not v:
        return False
    return v[:10] == today_iso

def _get_username(conn: sqlite3.Connection, user_id: int | None) -> str:
    if not user_id:
        return ""
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(username,'') AS u FROM usuarios WHERE id=?", (int(user_id),))
    r = cur.fetchone()
    return (r["u"] or "") if r else ""


def _get_user_contact(conn: sqlite3.Connection, user_id: int | None) -> dict | None:
    """
    Retorna siempre un dict con:
    {
        id,
        nombre,
        username,
        email
    }

    nombre:
    - usa nombre_completo si existe
    - si no, usa username
    - si no, 'Usuario'
    """
    if not user_id:
        return None

    try:
        conn.row_factory = sqlite3.Row
    except Exception:
        pass

    cur = conn.cursor()
    cur.execute("""
        SELECT
            id,
            COALESCE(
                NULLIF(TRIM(nombre_completo), ''),
                NULLIF(TRIM(username), ''),
                'Usuario'
            ) AS nombre,
            COALESCE(TRIM(username), '') AS username,
            COALESCE(TRIM(email), '') AS email
        FROM usuarios
        WHERE id = ?
          AND COALESCE(disabled, 0) = 0
        LIMIT 1
    """, (int(user_id),))
    row = cur.fetchone()

    if not row:
        return None

    try:
        return {
            "id": row["id"],
            "nombre": row["nombre"] or row["username"] or "Usuario",
            "username": row["username"] or "",
            "email": row["email"] or "",
        }
    except Exception:
        vals = list(row)
        return {
            "id": vals[0] if len(vals) > 0 else None,
            "nombre": vals[1] if len(vals) > 1 and vals[1] else (vals[2] if len(vals) > 2 else "Usuario"),
            "username": vals[2] if len(vals) > 2 and vals[2] else "",
            "email": vals[3] if len(vals) > 3 and vals[3] else "",
        }
    
def _get_ultimo_jefe_id(
    conn: sqlite3.Connection,
    user_id: int | None,
    *,
    fallback_to_self: bool = False
) -> int | None:
    if not user_id:
        return None

    cur = conn.cursor()
    cur.execute("SELECT jefe_id FROM usuarios WHERE id=?", (int(user_id),))
    row = cur.fetchone()
    if not row:
        return None

    jefe_id = row["jefe_id"]
    if not jefe_id:
        return int(user_id) if fallback_to_self else None

    seen = set()
    last_valid = None

    while jefe_id and jefe_id not in seen:
        seen.add(jefe_id)
        cur.execute("""
            SELECT id, jefe_id
            FROM usuarios
            WHERE id=?
              AND COALESCE(disabled,0)=0
        """, (int(jefe_id),))
        j = cur.fetchone()
        if not j:
            break
        last_valid = int(j["id"])
        jefe_id = j["jefe_id"]

    if last_valid is None and fallback_to_self:
        return int(user_id)

    return last_valid

 

def guess_gerente_area(conn: sqlite3.Connection, user_id: int | None) -> int | None:
    gerente = get_ultimo_jefe_activo(conn, user_id)
    if gerente:
        return gerente

    cur = conn.cursor()
    cur.execute("SELECT departamento_id FROM usuarios WHERE id = ?", (int(user_id),))
    u = cur.fetchone()
    if not u or not u["departamento_id"]:
        return None

    roles = (
        'jefe',
        'gerente',
        'gerente general',
        'gerente financiero',
        'coordinador',
        'admin',
        'usuario',
    )
    cur.execute(f"""
        SELECT id
        FROM usuarios
        WHERE departamento_id = ?
          AND LOWER(rol) IN ({",".join(["?"] * len(roles))})
          AND COALESCE(disabled, 0) = 0
        ORDER BY id
        LIMIT 1
    """, (u["departamento_id"], *[r.lower() for r in roles]))
    row = cur.fetchone()
    return int(row["id"]) if row else None


def _get_gerente_general_ids(conn: sqlite3.Connection) -> list[int]:
    cur = conn.cursor()
    cur.execute("""
        SELECT id
        FROM usuarios
        WHERE LOWER(TRIM(rol)) = 'gerente general'
          AND COALESCE(disabled,0)=0
        ORDER BY id
    """)
    return [int(r["id"]) for r in cur.fetchall()]


def _get_servicio_cliente_ids(conn: sqlite3.Connection) -> list[int]:
    """
    Replica tu lógica flexible de detección de Servicio al Cliente:
    departamento, join a departamentos o puesto.
    """
    cur = conn.cursor()

    ids = set()

    try:
        cur.execute("""
            SELECT u.id
            FROM usuarios u
            JOIN departamentos d ON d.id = u.departamento_id
            WHERE LOWER(TRIM(COALESCE(d.nombre,''))) = 'servicio al cliente'
              AND COALESCE(u.disabled,0)=0
        """)
        ids.update(int(r["id"]) for r in cur.fetchall())
    except Exception:
        pass

    try:
        cur.execute("""
            SELECT id
            FROM usuarios
            WHERE LOWER(TRIM(COALESCE(departamento,''))) = 'servicio al cliente'
              AND COALESCE(disabled,0)=0
        """)
        ids.update(int(r["id"]) for r in cur.fetchall())
    except Exception:
        pass

    try:
        cur.execute("""
            SELECT u.id
            FROM usuarios u
            LEFT JOIN puestos p ON p.id = u.puesto_id
            WHERE UPPER(TRIM(COALESCE(p.nombre,''))) LIKE '%SERVICIO AL CLIENTE%'
              AND COALESCE(u.disabled,0)=0
        """)
        ids.update(int(r["id"]) for r in cur.fetchall())
    except Exception:
        pass

    return sorted(ids)


def _enqueue_om_notification(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    tipo: str,
    template_key: str,
    fecha_obj: str,
    payload: dict,
    event_key: str,
):
    cur = conn.cursor()
    sched = _next_5min_sqlite()

    _exec_retry(cur, f"""
        INSERT OR IGNORE INTO notify_queue
            (user_id, tipo, fecha_obj, canal, template_key, payload_json, scheduled_at, estado, event_key)
        VALUES (?,?,?,?,?, ?, {sched}, 'pending', ?)
    """, (
        int(user_id),
        tipo,
        fecha_obj,
        "email",
        template_key,
        json.dumps(payload, ensure_ascii=False),
        event_key,
    ))
 

def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
import sqlite3
from datetime import datetime

def process_gastos_expiry(conn: sqlite3.Connection):
    """
    Política:
    - Si NO tiene ninguna aprobación (GA/GG/GF = 0) por 7 días => inactivar y notificar.
    - En el penúltimo día (día 6) => enviar aviso previo (solo una vez).
    """
    _log("info", "[EXPIRY] ===== start process_gastos_expiry =====")

    cur = conn.cursor()
    try:
        try:
            conn.row_factory = sqlite3.Row
        except Exception:
            pass

        ensure_gastos_expiry_schema(conn)

        # =========================
        # 0) Diagnóstico de fechas / now
        # =========================
        try:
            cur.execute("""
                SELECT
                GETDATE() AS now_local,
                CAST(GETDATE() AS date) AS today_local,
                DATEADD(day, -6, CAST(GETDATE() AS date)) AS d6,
                DATEADD(day, -7, CAST(GETDATE() AS date)) AS d7
            """)
            row_now = cur.fetchone()
            _log("info", "[EXPIRY][NOW] sqlite now_utc=%s now_local=%s today_utc=%s today_local=%s d6=%s d7=%s",
                 row_now["now_utc"], row_now["now_local"], row_now["today_utc"], row_now["today_local"], row_now["d6"], row_now["d7"])
        except Exception as e:
            _log("warning", "[EXPIRY][NOW] no se pudo leer now de sqlite -> %s", e)

        _log("info", "[EXPIRY][NOW] python now=%s", datetime.now().isoformat(timespec="seconds"))

        # Conteos por condición (te dice en qué filtro se mueren)
        _sql_debug_counts(conn)

        # =========================
        # A) Aviso día 6 (>=6, <7)
        # =========================
        warn_sql = """
            SELECT
                g.id,
                g.created_at,
                g.fecha,
                g.motivo,
                g.usuario_id,
                COALESCE(g.ga_aprobado,0) AS ga_aprobado,
                COALESCE(g.gg_aprobado,0) AS gg_aprobado,
                COALESCE(g.gf_aprobado,0) AS gf_aprobado,
                TRIM(COALESCE(g.sap_contabilizacion,'')) AS sap_contabilizacion,
                COALESCE(g.inactivo,0) AS inactivo,
                g.warn_sent_at
            FROM gastos_tarjeta g
            WHERE COALESCE(g.inactivo,0)=0
            AND TRIM(COALESCE(g.sap_contabilizacion,''))=''
            AND COALESCE(g.ga_aprobado,0)=0
            AND COALESCE(g.gg_aprobado,0)=0
            AND COALESCE(g.gf_aprobado,0)=0
            AND g.warn_sent_at IS NULL
            AND date(g.created_at,'localtime') <= date('now','localtime','-6 day')
            AND date(g.created_at,'localtime') >  date('now','localtime','-7 day')
            ORDER BY date(g.created_at) ASC, g.id ASC
        """
        
        _log("info", "[EXPIRY][WARN] SQL=%s", " ".join(warn_sql.split()))

        cur.execute(warn_sql)
        warn_rows = cur.fetchall() or []
        _log("info", "[EXPIRY][WARN] candidatos=%s", len(warn_rows))

        # Muestra rápida de candidatos
        for i, g in enumerate(warn_rows[:5]):
            _log("info", "[EXPIRY][WARN][SAMPLE %s] id=%s fecha=%s usuario_id=%s motivo=%s warn_sent_at=%s",
                 i+1, g["id"], g["fecha"], g["usuario_id"], (g["motivo"] or "")[:60], g["warn_sent_at"])

        warned = 0
        for g in warn_rows:
            gid = int(g["id"])
            usuario_id = int(g["usuario_id"] or 0)

            if not usuario_id:
                _log("warning", "[EXPIRY][WARN] skip gid=%s porque usuario_id vacío", gid)
                continue

            gerente_id = _get_ultimo_jefe_id(conn, usuario_id, fallback_to_self=True)
            gerente_id = int(gerente_id or 0) or usuario_id

            u = _get_user_contact(conn, usuario_id)
            m = _get_user_contact(conn, gerente_id)

            _log("info", "[EXPIRY][WARN] gid=%s usuario_id=%s gerente_id=%s u_email=%s m_email=%s",
                 gid, usuario_id, gerente_id,
                 (u or {}).get("email"), (m or {}).get("email"))

            try:
                mail.notify_gasto_expiry_warning(
                    current_app._get_current_object(),
                    gasto=dict(g),
                    usuario=u,
                    gerente=m
                )
                cur.execute(
                "UPDATE gastos_tarjeta SET warn_sent_at=? WHERE id=? AND warn_sent_at IS NULL",
                (_now_str(), gid)
                 )
                _log("info", "[EXPIRY][WARN] correo OK gid=%s", gid)
            except Exception:
                current_app.logger.exception("[EXPIRY][WARN] fallo correo gid=%s", gid)


            _log("info", "[EXPIRY][WARN] update warn_sent_at gid=%s rowcount=%s", gid, cur.rowcount)

            warned += 1

        # =========================
        # B) Inactivar día 7 (>=7)
        # =========================
        expire_sql = """
            SELECT g.*
            FROM gastos_tarjeta g
            WHERE COALESCE(g.inactivo,0)=0
            AND TRIM(COALESCE(g.sap_contabilizacion,''))=''
            AND COALESCE(g.ga_aprobado,0)=0
            AND COALESCE(g.gg_aprobado,0)=0
            AND COALESCE(g.gf_aprobado,0)=0
            AND date(g.created_at,'localtime') <= date('now','localtime','-7 day')
            ORDER BY date(g.created_at) ASC, g.id ASC
        """
        _log("info", "[EXPIRY][EXPIRE] SQL=%s", " ".join(expire_sql.split()))

        cur.execute(expire_sql)
        exp_rows = cur.fetchall() or []
        _log("info", "[EXPIRY][EXPIRE] candidatos=%s", len(exp_rows))

   
        inactivated = 0
        for row in exp_rows:
            g = dict(row)
            gid = int(g.get("id") or 0)
            usuario_id = int(g.get("usuario_id") or 0)

            if not gid or not usuario_id:
                _log("warning", "[EXPIRY][EXPIRE] skip gid=%s usuario_id=%s (inválidos)", gid, usuario_id)
                continue

            gerente_id = _get_ultimo_jefe_id(conn, usuario_id, fallback_to_self=True)
            gerente_id = int(gerente_id or 0) or usuario_id

            u = _get_user_contact(conn, usuario_id)
            m = _get_user_contact(conn, gerente_id)

            _log("info", "[EXPIRY][EXPIRE] inactivando gid=%s usuario_id=%s gerente_id=%s", gid, usuario_id, gerente_id)

            cur.execute("""
                UPDATE gastos_tarjeta
                SET inactivo=1,
                    inactivo_at=?,
                    inactivo_reason=?
                WHERE id=?
                  AND COALESCE(inactivo,0)=0
            """, (_now_str(), "AUTO: Sin aprobaciones en 7 días (política)", gid))

            _log("info", "[EXPIRY][EXPIRE] update inactivo gid=%s rowcount=%s", gid, cur.rowcount)

            try:
                mail.notify_gasto_expired_inactivated(
                    current_app._get_current_object(),
                    gasto=g,
                    usuario=u,
                    gerente=m
                )
                _log("info", "[EXPIRY][EXPIRE] correo OK gid=%s", gid)
            except Exception as e:
                _log("error", "[EXPIRY][EXPIRE] fallo correo gid=%s -> %s", gid, e)

            inactivated += 1

        conn.commit()
        _log("info", "[EXPIRY] ===== end ok warned=%s inactivated=%s =====", warned, inactivated)
        return {"ok": True, "warned": warned, "inactivated": inactivated}

    except Exception as e:
        conn.rollback()
        _log("error", "[EXPIRY] rollback por error -> %s", e)
        return {"ok": False, "error": str(e)}


def _sql_debug_counts(conn: sqlite3.Connection):
    """
    Diagnóstico: cuenta cuántos registros van quedando tras cada filtro
    para saber EXACTO dónde se cae el set.
    """
    cur = conn.cursor()

    # total
    cur.execute("SELECT COUNT(*) AS n FROM gastos_tarjeta")
    _log("info", "[EXPIRY][CNT] total gastos_tarjeta=%s", cur.fetchone()["n"])

    # no inactivo
    cur.execute("SELECT COUNT(*) AS n FROM gastos_tarjeta WHERE COALESCE(inactivo,0)=0")
    _log("info", "[EXPIRY][CNT] no_inactivo=%s", cur.fetchone()["n"])

    # no SAP
    cur.execute("""
        SELECT COUNT(*) AS n
        FROM gastos_tarjeta
        WHERE COALESCE(inactivo,0)=0
          AND TRIM(COALESCE(sap_contabilizacion,''))=''
    """)
    _log("info", "[EXPIRY][CNT] no_inactivo_y_no_sap=%s", cur.fetchone()["n"])

    # sin aprobaciones
    cur.execute("""
        SELECT COUNT(*) AS n
        FROM gastos_tarjeta
        WHERE COALESCE(inactivo,0)=0
          AND TRIM(COALESCE(sap_contabilizacion,''))=''
          AND COALESCE(ga_aprobado,0)=0
          AND COALESCE(gg_aprobado,0)=0
          AND COALESCE(gf_aprobado,0)=0
    """)
    _log("info", "[EXPIRY][CNT] base_sin_aprobaciones=%s", cur.fetchone()["n"])

    # warn pendientes (sin warn_sent_at)
    cur.execute("""
        SELECT COUNT(*) AS n
        FROM gastos_tarjeta
        WHERE COALESCE(inactivo,0)=0
          AND TRIM(COALESCE(sap_contabilizacion,''))=''
          AND COALESCE(ga_aprobado,0)=0
          AND COALESCE(gg_aprobado,0)=0
          AND COALESCE(gf_aprobado,0)=0
          AND warn_sent_at IS NULL
    """)
    _log("info", "[EXPIRY][CNT] base_sin_aprobaciones_y_sin_warn=%s", cur.fetchone()["n"])

    # ventana día 6
    cur.execute("""
        SELECT COUNT(*) AS n
        FROM gastos_tarjeta
        WHERE COALESCE(inactivo,0)=0
          AND TRIM(COALESCE(sap_contabilizacion,''))=''
          AND COALESCE(ga_aprobado,0)=0
          AND COALESCE(gg_aprobado,0)=0
          AND COALESCE(gf_aprobado,0)=0
          AND warn_sent_at IS NULL
          AND date(fecha) <= date('now','-6 day')
          AND date(fecha) >  date('now','-7 day')
    """)
    _log("info", "[EXPIRY][CNT] candidatos_warn_dia6=%s", cur.fetchone()["n"])

    # >=7 días
    cur.execute("""
        SELECT COUNT(*) AS n
        FROM gastos_tarjeta
        WHERE COALESCE(inactivo,0)=0
          AND TRIM(COALESCE(sap_contabilizacion,''))=''
          AND COALESCE(ga_aprobado,0)=0
          AND COALESCE(gg_aprobado,0)=0
          AND COALESCE(gf_aprobado,0)=0
          AND date(fecha) <= date('now','-7 day')
    """)
    _log("info", "[EXPIRY][CNT] candidatos_expire_dia7=%s", cur.fetchone()["n"])

    # sospecha: fecha no parseable por date(fecha)
    cur.execute("""
        SELECT COUNT(*) AS n
        FROM gastos_tarjeta
        WHERE fecha IS NOT NULL
          AND date(fecha) IS NULL
    """)
    _log("warning", "[EXPIRY][CNT] fecha_no_parseable_por_sqlite=%s", cur.fetchone()["n"])

    # muestra fechas no parseables (top 5)
    cur.execute("""
        SELECT id, fecha
        FROM gastos_tarjeta
        WHERE fecha IS NOT NULL
          AND date(fecha) IS NULL
        ORDER BY id DESC
        LIMIT 5
    """)
    bad = cur.fetchall() or []
    for r in bad:
        _log("warning", "[EXPIRY][BADFECHA] id=%s fecha='%s'", r["id"], r["fecha"])
