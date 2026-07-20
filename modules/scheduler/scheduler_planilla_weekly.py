# modules/scheduler/scheduler_planilla_weekly.py
# ==========================================================
# Reporte semanal de planilla mensual - Viernes 17:00
# Envía resumen lunes-viernes al jefe_id de cada responsable
# con copia al responsable. Incluye PDF con gráficos.
# ==========================================================

from __future__ import annotations

import calendar
import io
import os
import smtplib
import mimetypes
from collections import defaultdict
from datetime import date, datetime, timedelta
from email.message import EmailMessage

from .scheduler_repository import get_db_standalone
from .scheduler_security import _log

# ── PDF / gráficos ──────────────────────────────────────────
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.backends.backend_pdf import PdfPages
    _HAS_MPL = True
except ImportError:
    _HAS_MPL = False
    _log("warning", "[PLANILLA_WEEKLY] matplotlib no instalado — PDF omitido. Instala: pip install matplotlib")


# ════════════════════════════════════════════════════════════
# 1. Helpers de BD / SMTP
# ════════════════════════════════════════════════════════════

def _cfg(conn, clave, default=""):
    try:
        row = conn.execute(
            "SELECT valor FROM configuracion WHERE clave=?", (clave,)
        ).fetchone()
        return (row[0] if row else None) or default
    except Exception:
        return default


def _smtp_cfg(conn):
    return {
        "host": _cfg(conn, "smtp_host", ""),
        "port": int(_cfg(conn, "smtp_port", "587") or 587),
        "user": _cfg(conn, "smtp_user", ""),
        "pwd":  _cfg(conn, "smtp_pass", ""),
        "from": _cfg(conn, "smtp_from", "") or _cfg(conn, "smtp_user", ""),
        "tls":  _cfg(conn, "smtp_tls", "1") not in ("0", "false", "no"),
    }


def _send_report_mail(conn, to_addr: str, cc_addrs: list,
                      subject: str, html: str,
                      pdf_bytes: bytes | None = None,
                      pdf_name: str = "reporte_planilla.pdf"):
    cfg = _smtp_cfg(conn)
    if not cfg["host"] or not to_addr:
        _log("warning", "[PLANILLA_WEEKLY] SMTP no configurado o sin destinatario — omitiendo")
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"]    = cfg["from"] or cfg["user"]
    msg["To"]      = to_addr
    if cc_addrs:
        msg["Cc"] = ", ".join(c for c in cc_addrs if c)

    msg.set_content("Este mensaje requiere un cliente de correo que soporte HTML.")
    msg.add_alternative(html, subtype="html")

    if pdf_bytes:
        msg.add_attachment(
            pdf_bytes,
            maintype="application",
            subtype="pdf",
            filename=pdf_name,
        )

    try:
        with smtplib.SMTP(cfg["host"], cfg["port"]) as s:
            s.ehlo()
            if cfg["tls"]:
                s.starttls()
            if cfg["user"]:
                s.login(cfg["user"], cfg["pwd"])
            s.send_message(msg)
        _log("info", "[PLANILLA_WEEKLY] Correo enviado → %s (cc: %s)", to_addr, cc_addrs)
        return True
    except Exception as exc:
        _log("error", "[PLANILLA_WEEKLY] Error enviando a %s: %s", to_addr, exc)
        return False


# ════════════════════════════════════════════════════════════
# 2. Período lunes–viernes
# ════════════════════════════════════════════════════════════

def _week_range() -> tuple[date, date]:
    today  = date.today()
    lunes  = today - timedelta(days=today.weekday())
    viernes = lunes + timedelta(days=4)
    return lunes, viernes


def _is_non_working(d: date, feriados: set) -> bool:
    return d.weekday() in (5, 6) or d.isoformat() in feriados


def _occurs_this_day(t: dict, d: date, feriados: set) -> bool:
    if _is_non_working(d, feriados):
        return False
    f = (t.get("frecuencia") or "").strip().lower()
    if f == "diario":
        return True
    if f == "semanal":
        ds = t.get("dia_semana")
        ds = 0 if ds is None else int(ds)
        if 1 <= ds <= 7:
            ds = ds - 1          # convierte ISO (1=lun) a Python (0=lun)
        return d.weekday() == ds
    if f == "mensual":
        dm = t.get("dia_mes")
        if dm is None:
            return d.day == 1
        last = calendar.monthrange(d.year, d.month)[1]
        return d.day == min(int(dm), last)
    return False


# ════════════════════════════════════════════════════════════
# 3. Consultas a BD
# ════════════════════════════════════════════════════════════

def _load_feriados(conn, ini: str, fin: str) -> set:
    rows = conn.execute(
        "SELECT fecha FROM plan_feriados "
        "WHERE fecha BETWEEN ? AND ? AND (pais='EC' OR pais IS NULL)",
        (ini, fin),
    ).fetchall()
    return {r[0] for r in rows}


def _load_tareas(conn) -> list[dict]:
    rows = conn.execute("""
        SELECT t.id, t.nombre, t.frecuencia, t.dia_semana, t.dia_mes,
               t.departamento_id,
               r.nombre  AS responsable,
               d.nombre  AS depto
        FROM plan_tareas t
        JOIN plan_responsables r ON r.id = t.responsable_id
        LEFT JOIN departamentos d ON d.id = t.departamento_id
        WHERE t.activo = 1
        ORDER BY d.nombre, r.nombre, t.nombre
    """).fetchall()
    out = []
    for row in rows:
        out.append({
            "id":              row[0],
            "nombre":          row[1],
            "frecuencia":      (row[2] or "").strip(),
            "dia_semana":      row[3],
            "dia_mes":         row[4],
            "departamento_id": row[5],
            "responsable":     row[6] or "",
            "depto":           row[7] or "—",
        })
    return out


def _load_checks(conn, ini: str, fin: str, task_ids: list) -> set:
    if not task_ids:
        return set()
    ph = ",".join(["?"] * len(task_ids))
    rows = conn.execute(f"""
        SELECT tarea_id,
               CONVERT(varchar(10), CAST(fecha AS date), 23) AS f
        FROM plan_checks
        WHERE fecha BETWEEN ? AND ?
          AND COALESCE(checked, 1) = 1
          AND tarea_id IN ({ph})
    """, (ini, fin, *task_ids)).fetchall()
    return {(r[0], r[1]) for r in rows}


def _load_evidencias(conn, ini: str, fin: str, task_ids: list) -> set:
    if not task_ids:
        return set()
    ph = ",".join(["?"] * len(task_ids))
    rows = conn.execute(f"""
        SELECT tarea_id,
               CONVERT(varchar(10), CAST(fecha AS date), 23) AS f
        FROM plan_evidencias
        WHERE fecha BETWEEN ? AND ?
          AND file_path IS NOT NULL
          AND tarea_id IN ({ph})
    """, (ini, fin, *task_ids)).fetchall()
    return {(r[0], r[1]) for r in rows}


def _load_dept_config(conn) -> dict:
    """
    Devuelve {departamento_id: {notify_email, notify_nombre}}
    usando plan_dept_config → usuarios (para obtener email y nombre del jefe).
    """
    rows = conn.execute("""
        SELECT
            dc.departamento_id,
            d.nombre                                        AS depto_nombre,
            COALESCE(u.email, dc.notify_email, '')          AS jefe_email,
            COALESCE(u.nombre_completo, u.username, '')     AS jefe_nombre
        FROM plan_dept_config dc
        JOIN departamentos d ON d.id = dc.departamento_id
        LEFT JOIN usuarios u ON u.id = dc.notify_user_id
                             AND COALESCE(u.disabled, 0) = 0
    """).fetchall()

    out = {}
    for row in rows:
        dept_id     = row[0]
        depto_nombre = row[1] or ""
        jefe_email  = row[2] or ""
        jefe_nombre = row[3] or depto_nombre
        # fallback: si notify_user_id no tenía email, usar notify_email directo
        if not jefe_email:
            fb = conn.execute(
                "SELECT notify_email FROM plan_dept_config WHERE departamento_id=?",
                (dept_id,)
            ).fetchone()
            jefe_email = (fb[0] if fb else "") or ""
        out[dept_id] = {
            "depto_nombre": depto_nombre,
            "jefe_email":   jefe_email,
            "jefe_nombre":  jefe_nombre or depto_nombre,
        }
    return out


def _load_user_emails(conn) -> dict:
    """Devuelve {username_lower: email} para todos los usuarios activos."""
    rows = conn.execute("""
        SELECT LOWER(username), email
        FROM usuarios
        WHERE COALESCE(disabled, 0) = 0 AND email IS NOT NULL AND email <> ''
    """).fetchall()
    return {row[0]: row[1] for row in rows}


# ════════════════════════════════════════════════════════════
# 4. Cálculo de métricas por responsable
# ════════════════════════════════════════════════════════════

def _compute_stats(tareas: list, lunes: date, viernes: date,
                   feriados: set, checks: set, evidencias: set) -> dict:
    days = [lunes + timedelta(days=i) for i in range(5)]   # lu-vi

    result: dict = defaultdict(lambda: {
        "tareas": [], "planeadas": 0, "realizadas": 0, "con_evidencia": 0,
    })

    for t in tareas:
        resp = t["responsable"]
        task_detail = {
            "id":    t["id"],
            "nombre": t["nombre"],
            "depto":  t["depto"],
            "freq":   t["frecuencia"],
            "dias":   [],
            "plan": 0, "real": 0, "evi": 0,
        }
        for d in days:
            if not _occurs_this_day(t, d, feriados):
                continue
            iso = d.isoformat()
            realizado = (t["id"], iso) in checks
            con_evi   = (t["id"], iso) in evidencias
            task_detail["dias"].append({
                "fecha": iso,
                "dow":   ["Lu", "Ma", "Mi", "Ju", "Vi"][d.weekday()],
                "realizado": realizado,
                "evidencia": con_evi,
            })
            task_detail["plan"] += 1
            if realizado:
                task_detail["real"] += 1
            if con_evi:
                task_detail["evi"] += 1

        if task_detail["plan"] == 0:
            continue

        result[resp]["tareas"].append(task_detail)
        result[resp]["planeadas"]    += task_detail["plan"]
        result[resp]["realizadas"]   += task_detail["real"]
        result[resp]["con_evidencia"] += task_detail["evi"]

    return dict(result)


def _monthly_cumplimiento(conn, tareas: list, lunes: date) -> dict:
    y, m = lunes.year, lunes.month
    first = date(y, m, 1)
    last  = date(y, m, calendar.monthrange(y, m)[1])
    ini, fin = first.isoformat(), last.isoformat()

    feriados = _load_feriados(conn, ini, fin)
    task_ids = [t["id"] for t in tareas]
    if not task_ids:
        return {}

    days = [first + timedelta(days=i) for i in range((last - first).days + 1)]
    ph   = ",".join(["?"] * len(task_ids))
    rows = conn.execute(f"""
        SELECT tarea_id, CONVERT(varchar(10), CAST(fecha AS date), 23) AS f
        FROM plan_checks
        WHERE fecha BETWEEN ? AND ?
          AND COALESCE(checked, 1) = 1
          AND tarea_id IN ({ph})
    """, (ini, fin, *task_ids)).fetchall()
    checks_mes = {(r[0], r[1]) for r in rows}

    by_resp: dict = defaultdict(lambda: {"plan": 0, "real": 0})
    for t in tareas:
        resp = t["responsable"]
        for d in days:
            if not _occurs_this_day(t, d, feriados):
                continue
            by_resp[resp]["plan"] += 1
            if (t["id"], d.isoformat()) in checks_mes:
                by_resp[resp]["real"] += 1

    return {
        resp: round(100 * v["real"] / v["plan"], 1) if v["plan"] else 0.0
        for resp, v in by_resp.items()
    }


# ════════════════════════════════════════════════════════════
# 5. HTML del correo
# ════════════════════════════════════════════════════════════

def _pct_color(pct: float) -> str:
    if pct >= 85:  return "#16a34a"
    if pct >= 60:  return "#d97706"
    return "#dc2626"


def _build_html(jefe_nombre: str, lunes: date, viernes: date,
                stats_by_resp: dict, monthly_pct: dict) -> str:

    periodo  = f"{lunes.strftime('%d/%m/%Y')} – {viernes.strftime('%d/%m/%Y')}"
    now_str  = datetime.now().strftime("%d/%m/%Y %H:%M")
    sections = []

    for resp, data in sorted(stats_by_resp.items()):
        plan  = data["planeadas"]
        real  = data["realizadas"]
        evi   = data["con_evidencia"]
        pct   = round(100 * real / plan, 1) if plan else 0.0
        color = _pct_color(pct)
        m_pct = monthly_pct.get(resp, 0.0)

        task_rows = []
        for t in data["tareas"]:
            t_pct   = round(100 * t["real"] / t["plan"], 1) if t["plan"] else 0.0
            t_color = _pct_color(t_pct)

            dias_html = ""
            for d in t["dias"]:
                if d["realizado"]:
                    icon = "✅" if d["evidencia"] else "☑️"
                else:
                    icon = "⬜"
                dias_html += (
                    f'<td style="text-align:center;padding:4px 6px;font-size:13px">'
                    f'{d["dow"]}<br>{icon}</td>'
                )

            # Rellenar días que no aplican (para alinear columnas)
            dias_aplican = len(t["dias"])
            for _ in range(5 - dias_aplican):
                dias_html += '<td style="text-align:center;padding:4px 6px;color:#e2e8f0">—</td>'

            task_rows.append(f"""
            <tr style="border-bottom:1px solid #f0f0f0">
              <td style="padding:6px 10px;font-size:13px;color:#1e293b">{t["nombre"]}</td>
              <td style="padding:6px 8px;font-size:12px;color:#64748b;white-space:nowrap">{t["depto"]}</td>
              <td style="padding:6px 8px;font-size:12px;color:#64748b;text-align:center">{t["freq"]}</td>
              {dias_html}
              <td style="padding:6px 8px;text-align:center;font-size:13px;font-weight:700;color:{t_color}">
                {t["real"]}/{t["plan"]}<br>
                <span style="font-size:11px">{t_pct}%</span>
              </td>
              <td style="padding:6px 8px;text-align:center;font-size:14px">
                {"📎" if t["evi"] else "—"}
              </td>
            </tr>""")

        sin_tareas = (
            '<tr><td colspan="10" style="padding:12px;color:#94a3b8;text-align:center">'
            'Sin tareas esta semana</td></tr>'
        )

        sections.append(f"""
        <div style="margin-bottom:28px;border:1px solid #e2e8f0;border-radius:10px;overflow:hidden">
          <div style="background:#1e3a5f;color:#fff;padding:12px 18px">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
              <span style="font-size:15px;font-weight:700">👤 {resp}</span>
              <div style="display:flex;gap:20px">
                <div style="text-align:center">
                  <div style="font-size:10px;opacity:.75">Semana</div>
                  <div style="font-size:22px;font-weight:800;color:{color}">{pct}%</div>
                  <div style="font-size:11px;opacity:.75">{real}/{plan} tareas</div>
                </div>
                <div style="text-align:center">
                  <div style="font-size:10px;opacity:.75">Mes acumulado</div>
                  <div style="font-size:22px;font-weight:800;color:{_pct_color(m_pct)}">{m_pct}%</div>
                </div>
                <div style="text-align:center">
                  <div style="font-size:10px;opacity:.75">Con evidencia</div>
                  <div style="font-size:22px;font-weight:800">📎 {evi}</div>
                </div>
              </div>
            </div>
          </div>
          <div style="overflow-x:auto">
            <table style="width:100%;border-collapse:collapse;font-family:Arial,sans-serif;min-width:600px">
              <thead>
                <tr style="background:#f8fafc;font-size:12px;color:#64748b;text-align:center">
                  <th style="padding:8px 10px;text-align:left">Actividad</th>
                  <th style="padding:8px">Departamento</th>
                  <th style="padding:8px">Frecuencia</th>
                  <th style="padding:6px">Lu</th>
                  <th style="padding:6px">Ma</th>
                  <th style="padding:6px">Mi</th>
                  <th style="padding:6px">Ju</th>
                  <th style="padding:6px">Vi</th>
                  <th style="padding:8px">Cumpl.</th>
                  <th style="padding:8px">Evi.</th>
                </tr>
              </thead>
              <tbody>
                {''.join(task_rows) if task_rows else sin_tareas}
              </tbody>
            </table>
          </div>
        </div>""")

    leyenda = """
    <div style="margin-top:16px;font-size:12px;color:#64748b;padding:10px;
                background:#f8fafc;border-radius:6px;border:1px solid #e2e8f0">
      <strong>Leyenda:</strong> &nbsp;
      ✅ Realizado con evidencia &nbsp;·&nbsp;
      ☑️ Realizado sin evidencia &nbsp;·&nbsp;
      ⬜ No realizado &nbsp;·&nbsp;
      — No aplica ese día
    </div>"""

    contenido = ''.join(sections) if sections else (
        '<p style="color:#94a3b8;text-align:center;padding:24px">'
        'No hay tareas activas para este período.</p>'
    )

    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
</head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:Arial,Helvetica,sans-serif">
  <div style="max-width:860px;margin:24px auto;background:#fff;
              border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.08)">

    <div style="background:linear-gradient(135deg,#1e3a5f 0%,#1d4ed8 100%);
                padding:28px 32px;color:#fff">
      <div style="font-size:11px;opacity:.7;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">
        Sistema de Gestión Quimpac — Planilla Mensual
      </div>
      <h1 style="margin:0 0 6px;font-size:22px;font-weight:800">
        📊 Reporte Semanal de Actividades
      </h1>
      <div style="font-size:14px;opacity:.85">
        Período: <strong>{periodo}</strong> &nbsp;·&nbsp; Generado: {now_str}
      </div>
      <div style="margin-top:10px;font-size:14px">
        Estimado/a <strong>{jefe_nombre}</strong>, a continuación encontrará
        el resumen semanal de cumplimiento de actividades clave de su equipo.
      </div>
    </div>

    <div style="padding:28px 32px">
      {contenido}
      {leyenda}
    </div>

    <div style="background:#f8fafc;padding:14px 32px;
                border-top:1px solid #e2e8f0;font-size:11px;color:#94a3b8;text-align:center">
      Mensaje generado automáticamente por el Sistema de Gestión Quimpac.
      No responda a este correo.
    </div>
  </div>
</body>
</html>"""


# ════════════════════════════════════════════════════════════
# 6. Generación de PDF con matplotlib
# ════════════════════════════════════════════════════════════

def _build_pdf(lunes: date, viernes: date,
               stats_by_resp: dict, monthly_pct: dict) -> bytes | None:
    if not _HAS_MPL:
        return None

    periodo = f"{lunes.strftime('%d/%m/%Y')} – {viernes.strftime('%d/%m/%Y')}"
    buf = io.BytesIO()

    with PdfPages(buf) as pdf:

        # ── Pág 1: Resumen comparativo (barras horizontales) ──────────
        nombres  = sorted(stats_by_resp.keys())
        sem_pcts = []
        mes_pcts = []
        for resp in nombres:
            d   = stats_by_resp[resp]
            pct = round(100 * d["realizadas"] / d["planeadas"], 1) if d["planeadas"] else 0.0
            sem_pcts.append(pct)
            mes_pcts.append(monthly_pct.get(resp, 0.0))

        n   = len(nombres)
        fig, ax = plt.subplots(figsize=(12, max(4, n * 0.65 + 2.5)))
        width   = 0.38
        y_pos   = range(n)

        bars1 = ax.barh([i + width / 2 for i in y_pos], sem_pcts,
                        height=width, label="Cumplimiento semana", color="#2563eb", alpha=0.85)
        bars2 = ax.barh([i - width / 2 for i in y_pos], mes_pcts,
                        height=width, label="Cumplimiento mes",    color="#16a34a", alpha=0.75)

        ax.set_yticks(list(y_pos))
        ax.set_yticklabels(nombres, fontsize=9)
        ax.set_xlabel("Cumplimiento (%)", fontsize=9)
        ax.set_xlim(0, 118)
        ax.axvline(100, color="#dc2626", linewidth=0.8, linestyle="--", alpha=0.5, label="Meta 100%")
        ax.set_title(
            f"Resumen de Cumplimiento — Semana {periodo}",
            fontsize=13, fontweight="bold", pad=14,
        )
        ax.legend(fontsize=9, loc="lower right")

        for bar in bars1:
            w = bar.get_width()
            ax.text(w + 0.8, bar.get_y() + bar.get_height() / 2,
                    f"{w:.0f}%", va="center", fontsize=8, color="#1e40af")
        for bar in bars2:
            w = bar.get_width()
            ax.text(w + 0.8, bar.get_y() + bar.get_height() / 2,
                    f"{w:.0f}%", va="center", fontsize=8, color="#15803d")

        fig.tight_layout(pad=1.8)
        pdf.savefig(fig, dpi=120)
        plt.close(fig)

        # ── Pág por responsable: detalle tareas + donut ───────────────
        for resp in nombres:
            data   = stats_by_resp[resp]
            tareas = data["tareas"]
            if not tareas:
                continue

            nombres_t = [t["nombre"][:45] for t in tareas]
            reales    = [t["real"] for t in tareas]
            planeados = [t["plan"] for t in tareas]
            pcts_t    = [
                round(100 * r / p, 1) if p else 0.0
                for r, p in zip(reales, planeados)
            ]
            colors_t  = [
                "#16a34a" if p >= 85 else "#d97706" if p >= 60 else "#dc2626"
                for p in pcts_t
            ]

            fig2, axes = plt.subplots(
                1, 2,
                figsize=(14, max(4.5, len(tareas) * 0.55 + 3)),
                gridspec_kw={"width_ratios": [2, 1]},
            )

            # Izquierda: barras por tarea
            ax1  = axes[0]
            y_t  = range(len(nombres_t))
            ax1.barh(list(y_t), pcts_t, color=colors_t, alpha=0.85, height=0.55)
            ax1.set_yticks(list(y_t))
            ax1.set_yticklabels(nombres_t, fontsize=8)
            ax1.set_xlabel("Cumplimiento (%)", fontsize=8)
            ax1.set_xlim(0, 118)
            ax1.axvline(100, color="#dc2626", linewidth=0.7, linestyle="--", alpha=0.5)
            ax1.set_title(
                f"{resp} — Detalle por tarea\n{periodo}",
                fontsize=10, fontweight="bold",
            )
            for i, (p, r, pl) in enumerate(zip(pcts_t, reales, planeados)):
                ax1.text(p + 0.8, i, f"{p:.0f}%  ({r}/{pl})",
                         va="center", fontsize=7.5)

            # Derecha: donut semana + KPIs
            ax2    = axes[1]
            pct_s  = round(100 * data["realizadas"] / data["planeadas"], 1) if data["planeadas"] else 0.0
            pct_m  = monthly_pct.get(resp, 0.0)
            c_s    = _pct_color(pct_s)

            ax2.pie(
                [pct_s, max(0, 100 - pct_s)],
                colors=[c_s, "#e2e8f0"],
                startangle=90,
                counterclock=False,
                wedgeprops={"width": 0.45, "edgecolor": "white"},
            )
            ax2.text(0, 0.12, f"{pct_s:.0f}%",
                     ha="center", va="center", fontsize=24, fontweight="bold", color=c_s)
            ax2.text(0, -0.18, "Semana",
                     ha="center", va="center", fontsize=10, color="#64748b")
            ax2.set_title(
                f"Mes: {pct_m:.1f}%\n"
                f"Realizadas: {data['realizadas']}/{data['planeadas']}\n"
                f"Con evidencia: {data['con_evidencia']}",
                fontsize=9, pad=14,
            )

            leyenda_patches = [
                mpatches.Patch(color="#16a34a", label="≥85%  OK"),
                mpatches.Patch(color="#d97706", label="60–84%  Atención"),
                mpatches.Patch(color="#dc2626", label="<60%  Crítico"),
            ]
            fig2.legend(handles=leyenda_patches, fontsize=8,
                        loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.02))

            fig2.tight_layout(pad=1.8)
            pdf.savefig(fig2, dpi=110)
            plt.close(fig2)

    buf.seek(0)
    return buf.read()


# ════════════════════════════════════════════════════════════
# 7. Función principal
# ════════════════════════════════════════════════════════════

def send_planilla_weekly_report(force: bool = False) -> dict:
    """
    Envía el reporte semanal a cada jefe que tenga subordinados con tareas.

    Args:
        force: si True, ignora el chequeo de día (útil para envío manual).

    Returns:
        dict con claves: sent, errors, skipped, periodo
    """
    today = date.today()

    if not force and today.weekday() != 4:   # 4 = viernes
        _log("info", "[PLANILLA_WEEKLY] Hoy no es viernes (%s), omitiendo", today.strftime("%A"))
        return {"skipped": True, "reason": "no es viernes"}

    lunes, viernes = _week_range()
    ini, fin = lunes.isoformat(), viernes.isoformat()

    _log("info", "[PLANILLA_WEEKLY] Iniciando reporte semana %s – %s (force=%s)", ini, fin, force)

    conn = get_db_standalone()
    try:
        tareas     = _load_tareas(conn)
        feriados   = _load_feriados(conn, ini, fin)
        task_ids   = [t["id"] for t in tareas]
        checks     = _load_checks(conn, ini, fin, task_ids)
        evidencias = _load_evidencias(conn, ini, fin, task_ids)

        all_stats   = _compute_stats(tareas, lunes, viernes, feriados, checks, evidencias)
        monthly_pct = _monthly_cumplimiento(conn, tareas, lunes)

        dept_cfg    = _load_dept_config(conn)
        user_emails = _load_user_emails(conn)

        # Mapa responsable → departamento_id (toma el primer depto que aparezca)
        resp_to_dept: dict = {}
        for t in tareas:
            resp = t["responsable"]
            if resp not in resp_to_dept and t.get("departamento_id"):
                resp_to_dept[resp] = t["departamento_id"]

        # Agrupar responsables por departamento
        dept_grupos: dict = defaultdict(lambda: {
            "jefe_email":  "",
            "jefe_nombre": "",
            "depto_nombre": "",
            "cc_emails":   [],
            "stats":       {},
        })

        for resp_name, stat_data in all_stats.items():
            dept_id = resp_to_dept.get(resp_name)
            if not dept_id or dept_id not in dept_cfg:
                _log("warning",
                     "[PLANILLA_WEEKLY] Responsable '%s' sin config de depto, omitido",
                     resp_name)
                continue

            cfg  = dept_cfg[dept_id]
            grp  = dept_grupos[dept_id]
            grp["jefe_email"]   = cfg["jefe_email"]
            grp["jefe_nombre"]  = cfg["jefe_nombre"]
            grp["depto_nombre"] = cfg["depto_nombre"]
            grp["stats"][resp_name] = stat_data

            # CC al propio responsable si tiene email en usuarios
            ue = user_emails.get(resp_name.lower(), "")
            if ue and ue not in grp["cc_emails"]:
                grp["cc_emails"].append(ue)

        jefe_grupos = dept_grupos

        sent = errors = 0
        for dept_id, grp in jefe_grupos.items():
            if not grp["jefe_email"]:
                _log("warning", "[PLANILLA_WEEKLY] Depto '%s' sin email de jefe, omitido",
                     grp.get("depto_nombre", dept_id))
                continue
            if not grp["stats"]:
                continue

            try:
                html      = _build_html(grp["jefe_nombre"], lunes, viernes,
                                        grp["stats"], monthly_pct)
                pdf_bytes = _build_pdf(lunes, viernes, grp["stats"], monthly_pct)
                pdf_name  = f"reporte_planilla_{ini}_{fin}.pdf"
                subject   = (
                    f"📊 Reporte Semanal Planilla | "
                    f"{lunes.strftime('%d/%m')} – {viernes.strftime('%d/%m/%Y')}"
                )

                ok = _send_report_mail(
                    conn, grp["jefe_email"], grp["cc_emails"],
                    subject, html, pdf_bytes, pdf_name,
                )
                if ok:
                    sent += 1
                else:
                    errors += 1

            except Exception as exc:
                _log("error", "[PLANILLA_WEEKLY] Error procesando depto '%s': %s",
                     grp.get("depto_nombre", dept_id), exc)
                errors += 1

        _log("info", "[PLANILLA_WEEKLY] Finalizado — enviados=%d errores=%d", sent, errors)
        return {"sent": sent, "errors": errors, "skipped": False,
                "periodo": f"{ini} / {fin}"}

    finally:
        try:
            conn.close()
        except Exception:
            pass
