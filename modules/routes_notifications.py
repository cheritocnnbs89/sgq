# modules/routes_notifications.py
from __future__ import annotations

import io
import os
import base64
import tempfile
from collections import defaultdict, Counter
from datetime import date, datetime, timedelta

import matplotlib
matplotlib.use("Agg")  # backend sin UI
import matplotlib.pyplot as plt

from flask import (
    Blueprint, render_template, render_template_string,
    request, redirect, url_for, abort, session, flash, current_app,
)

from modules.db import get_db
from modules.routes_planilla_mensual import send_mail as send_mail_planilla

# ---------------------------------------------------------------------
# Blueprint
# ---------------------------------------------------------------------
notif_bp = Blueprint("notifications", __name__, url_prefix="/notificaciones")

# ---------------------------------------------------------------------
# ReportLab (PDF) – si no está, se usa HTML como fallback
# ---------------------------------------------------------------------
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
    )
    _HAS_REPORTLAB = True
except Exception:
    _HAS_REPORTLAB = False

# ---------------------------------------------------------------------
# Config tipos de plantilla (para combos)
# ---------------------------------------------------------------------
TPL_TYPES = [
    ("hoy", "Recordatorio del día"),
    ("vencida", "Tarea vencida"),
    ("resumen_semanal", "Resumen semanal"),
    ("resumen_mensual", "Resumen mensual"),
]

# ---------------------------------------------------------------------
# Guardas simples
# ---------------------------------------------------------------------
def _is_admin() -> bool:
    role = (session.get("rol") or "").lower()
    return role == "admin" or bool(session.get("is_admin"))

def _ensure_tpl_schema():
    """Crea tabla notify_templates si no existe y agrega columna 'tipo' si falta."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS notify_templates(
            key TEXT PRIMARY KEY,
            subject TEXT NOT NULL,
            html TEXT NOT NULL,
            text TEXT,
            tipo TEXT
        )
    """)
    try:
        cur.execute("SELECT tipo FROM notify_templates LIMIT 1")
    except Exception:
        cur.execute("ALTER TABLE notify_templates ADD COLUMN tipo TEXT NULL")
    conn.commit()

@notif_bp.before_request
def _guard():
    if not _is_admin():
        abort(403)
    _ensure_tpl_schema()

# ---------------------------------------------------------------------
# Utilidades de gráficos (Matplotlib -> PNG)
# ---------------------------------------------------------------------
def _fig_to_png(fig) -> bytes:
    """Convierte una figura Matplotlib en PNG bytes con márgenes homogéneos."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130)  # sin bbox_inches="tight"
    plt.close(fig)
    buf.seek(0)
    return buf.read()

def _chart_resp_perf(filas) -> bytes:
    """Barras: plan vs hechos semana anterior por responsable."""
    if not filas:
        fig = plt.figure(figsize=(1, 1))
        return _fig_to_png(fig)

    names   = [f["responsable"] for f in filas]
    planned = [f["planned_prev"] for f in filas]
    done    = [f["done_prev"] for f in filas]
    x = range(len(names))

    fig = plt.figure(figsize=(7.5, 3.5))
    plt.bar(x, planned, width=0.4, label="Plan")
    plt.bar([i + 0.4 for i in x], done, width=0.4, label="Hechos")
    plt.xticks([i + 0.2 for i in x], names, rotation=30, ha="right")
    plt.ylabel("Tareas")
    plt.title("Cumplimiento por responsable (semana anterior)")
    plt.legend()
    plt.tight_layout()
    return _fig_to_png(fig)

def _chart_daily_trend(conn, dep_id: int, dfrom: date, dto: date) -> bytes:
    """Línea: checks por día en la semana anterior."""
    cur = conn.cursor()
    rows = cur.execute("""
        SELECT date(c.fecha) AS d, COUNT(*) AS n
          FROM plan_checks c
          JOIN plan_tareas t ON t.id = c.tarea_id
         WHERE date(c.fecha) BETWEEN ? AND ?
           AND COALESCE(t.departamento_id,-1)=?
         GROUP BY date(c.fecha)
         ORDER BY date(c.fecha)
    """, (dfrom.isoformat(), dto.isoformat(), dep_id)).fetchall()

    by_day = {r["d"]: r["n"] for r in rows}
    xs, ys = [], []
    dd = dfrom
    while dd <= dto:
        xs.append(dd.strftime("%Y-%m-%d"))
        ys.append(by_day.get(dd.isoformat(), 0))
        dd += timedelta(days=1)

    fig = plt.figure(figsize=(7.5, 3.2))
    plt.plot(xs, ys, marker="o")
    plt.xticks(rotation=30, ha="right")
    plt.ylabel("Checks por día")
    plt.title("Tendencia diaria (semana anterior)")
    plt.tight_layout()
    return _fig_to_png(fig)

def _chart_week_dep_area(conn, dep_id: int, dfrom: date, dto: date) -> bytes:
    """
    Serie diaria de 'planeadas' vs 'realizadas' para el departamento en el rango [dfrom, dto].
    Planeadas: derivadas de frecuencia de la tarea (Diario, Semanal, Mensual).
    Realizadas: checks por día.
    """
    cur = conn.cursor()

    # Realizadas por día
    rows = cur.execute("""
        SELECT date(c.fecha) AS d, COUNT(*) AS n
          FROM plan_checks c
          JOIN plan_tareas t ON t.id = c.tarea_id
         WHERE date(c.fecha) BETWEEN ? AND ?
           AND COALESCE(t.departamento_id,-1)=?
         GROUP BY date(c.fecha)
         ORDER BY date(c.fecha)
    """, (dfrom.isoformat(), dto.isoformat(), dep_id)).fetchall()
    realizadas_by_day = {r["d"]: r["n"] for r in rows}

    # Tareas activas del depto
    tareas = cur.execute("""
        SELECT t.id, t.frecuencia, t.dia_semana, t.dia_mes
          FROM plan_tareas t
         WHERE t.activo=1 AND COALESCE(t.departamento_id,-1)=?
    """, (dep_id,)).fetchall()

    def cae_en(fecha: date, r) -> bool:
        if r["frecuencia"] == "Diario":
            return True
        if r["frecuencia"] == "Semanal":
            if r["dia_semana"] is None:
                return True
            return (fecha.weekday() == r["dia_semana"])  # 0=Lunes ... 6=Domingo
        if r["frecuencia"] == "Mensual":
            return (r["dia_mes"] is None) or (fecha.day == r["dia_mes"])
        return False

    xs, plan, done = [], [], []
    dd = dfrom
    while dd <= dto:
        xs.append(dd.strftime("%Y-%m-%d"))
        p = 0
        for t in tareas:
            if cae_en(dd, t):
                p += 1
        plan.append(p)
        done.append(realizadas_by_day.get(dd.isoformat(), 0))
        dd += timedelta(days=1)

    fig = plt.figure(figsize=(7.5, 3.2))
    plt.plot(xs, plan, label="Planeadas")
    plt.fill_between(xs, plan, alpha=0.15)
    plt.plot(xs, done, label="Realizadas")
    plt.fill_between(xs, done, alpha=0.15)
    plt.xticks(rotation=30, ha="right")
    plt.ylabel("Tareas por día")
    plt.title("Planeadas vs Realizadas (semana)")
    plt.legend()
    plt.tight_layout()
    return _fig_to_png(fig)

def _monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())  # 0 = lunes

# ---------------------------------------------------------------------
# Tareas por usuario/fecha (usado por plantillas de correo)
# ---------------------------------------------------------------------
def _tareas_para_usuario_en_fecha(conn, user_id: int, fecha_iso: str):
    """
    Devuelve tareas activas del usuario (por user_id) que 'caen' en fecha_iso,
    respetando frecuencia y programación semanal/mensual.
    """
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
       AND u.id = ?
       AND {sql_condicion_fecha}
     ORDER BY d.nombre, t.nombre
    """
    params = (fecha_iso, fecha_iso, fecha_iso, user_id)
    rows = conn.execute(sql, params).fetchall()

    return [
        {
            "id": r["id"],
            "tarea": r["nombre"],
            "nombre": r["nombre"],
            "frecuencia": r["frecuencia"],
            "departamento": r["departamento"],
            "responsable": r["responsable"],
            "hecha": bool(r["hecha"]),
        }
        for r in rows
    ]

# ---------------------------------------------------------------------
# Informe semanal – datos e informe (PDF/HTML)
# ---------------------------------------------------------------------
def _collect_weekly_data(conn, dep_id: int, next_mon: date):
    next_sun = next_mon + timedelta(days=6)
    prev_mon = next_mon - timedelta(days=7)
    prev_sun = next_mon - timedelta(days=1)

    cur = conn.cursor()
    tareas = cur.execute("""
        SELECT t.id, t.nombre, t.frecuencia, t.dia_semana, t.dia_mes,
               r.nombre AS responsable, COALESCE(d.nombre,'') AS departamento
          FROM plan_tareas t
          JOIN plan_responsables r ON r.id = t.responsable_id
          LEFT JOIN departamentos d ON d.id = t.departamento_id
         WHERE t.activo=1 AND COALESCE(t.departamento_id,-1)=?
         ORDER BY r.nombre, t.nombre
    """, (dep_id,)).fetchall()

    planned_next = defaultdict(lambda: defaultdict(list))
    for r in tareas:
        freq = r["frecuencia"]
        cae = False
        if freq == "Diario":
            cae = True
        elif freq == "Semanal":
            cae = True if r["dia_semana"] is None else (0 <= r["dia_semana"] <= 6)
        elif freq == "Mensual":
            if r["dia_mes"] is None:
                cae = True
            else:
                dm = r["dia_mes"]
                for i in range(7):
                    if (next_mon + timedelta(days=i)).day == dm:
                        cae = True
                        break
        if cae:
            planned_next[r["responsable"]][freq].append({
                "tarea": r["nombre"],
                "frecuencia": freq,
                "departamento": r["departamento"],
            })

    planned_prev = Counter()
    for r in tareas:
        freq = r["frecuencia"]; resp = r["responsable"]
        cae = False
        if freq == "Diario":
            cae = True
        elif freq == "Semanal":
            cae = True if r["dia_semana"] is None else (prev_mon <= (prev_mon + timedelta(days=r["dia_semana"])) <= prev_sun)
        elif freq == "Mensual":
            if r["dia_mes"] is None:
                cae = True
            else:
                for i in range(7):
                    if (prev_mon + timedelta(days=i)).day == r["dia_mes"]:
                        cae = True
                        break
        if cae:
            planned_prev[(resp, freq)] += 1

    hechos_prev = Counter()
    rows = cur.execute("""
        SELECT r.nombre AS responsable, t.frecuencia, COUNT(1) AS n
          FROM plan_checks c
          JOIN plan_tareas t ON t.id=c.tarea_id
          JOIN plan_responsables r ON r.id=t.responsable_id
         WHERE date(c.fecha) BETWEEN ? AND ?
           AND COALESCE(t.departamento_id,-1)=?
         GROUP BY r.nombre, t.frecuencia
    """, (prev_mon.isoformat(), prev_sun.isoformat(), dep_id)).fetchall()
    for r in rows:
        hechos_prev[(r["responsable"], r["frecuencia"])] += r["n"]

    responsables = sorted({r["responsable"] for r in tareas})
    out_rows = []
    for resp in responsables:
        plan_sum = sum(planned_prev[(resp, f)] for f in ("Diario", "Semanal", "Mensual"))
        done_sum = sum(hechos_prev[(resp, f)] for f in ("Diario", "Semanal", "Mensual"))
        out_rows.append({
            "responsable": resp,
            "planned_prev": plan_sum,
            "done_prev": done_sum,
            "cumplimiento_prev": (done_sum / plan_sum * 100.0) if plan_sum else 0.0,
            "tareas_next": [t for f in ("Diario", "Semanal", "Mensual") for t in planned_next[resp].get(f, [])],
            "detalle_prev": {
                "Diario":  {"plan": planned_prev[(resp, "Diario")],  "done": hechos_prev[(resp, "Diario")]},
                "Semanal": {"plan": planned_prev[(resp, "Semanal")], "done": hechos_prev[(resp, "Semanal")]},
                "Mensual": {"plan": planned_prev[(resp, "Mensual")], "done": hechos_prev[(resp, "Mensual")]},
            },
        })

    return {
        "next_mon": next_mon, "next_sun": next_sun,
        "prev_mon": prev_mon, "prev_sun": prev_sun,
        "rows": out_rows,
        "planned_next": planned_next,
    }

def _build_insights(rows):
    insights = []
    if not rows:
        insights.append("No hay responsables con tareas activas en el departamento.")
        return insights

    prom  = sum(r["cumplimiento_prev"] for r in rows) / len(rows)
    worst = min(rows, key=lambda r: r["cumplimiento_prev"])
    best  = max(rows, key=lambda r: r["cumplimiento_prev"])
    insights.append(
        f"Cumplimiento promedio semana anterior: {prom:.1f}%. "
        f"Mejor responsable: {best['responsable']} ({best['cumplimiento_prev']:.1f}%). "
        f"Atención en: {worst['responsable']} ({worst['cumplimiento_prev']:.1f}%)."
    )

    for freq in ("Diario", "Semanal", "Mensual"):
        plan = sum(r["detalle_prev"][freq]["plan"] for r in rows)
        done = sum(r["detalle_prev"][freq]["done"] for r in rows)
        pct  = (done / plan * 100.0) if plan else 0.0
        insights.append(f"{freq}: plan={plan}, hechos={done}, cumplimiento={pct:.1f}%.")

    next_count = sum(len(r["tareas_next"]) for r in rows)
    insights.append(
        f"Próxima semana hay {next_count} tareas distribuidas entre "
        f"{sum(1 for r in rows if r['tareas_next'] )} responsables."
    )
    return insights

def _build_pdf_or_html(
    dept_name: str,
    data,
    charts_png: dict,
    dashboard_pngs: list[bytes] | None = None
) -> tuple[str, bytes, str]:
    """
    Genera PDF (o HTML fallback) con charts y tabla. Las imágenes se centran
    y se restringen a un ancho máximo para evitar desalineados.
    """
    title = f"Informe_semanal_{dept_name}_{data['next_mon'].isoformat()}_{data['next_sun'].isoformat()}".replace(" ","_")

    if _HAS_REPORTLAB:
        fd, tmp = tempfile.mkstemp(suffix=".pdf"); os.close(fd)

        # Márgenes y medidas base
        PAGE = A4
        LEFT, RIGHT, TOP, BOTTOM = 2.0*cm, 2.0*cm, 1.8*cm, 1.8*cm
        doc = SimpleDocTemplate(
            tmp, pagesize=PAGE, title=title,
            leftMargin=LEFT, rightMargin=RIGHT, topMargin=TOP, bottomMargin=BOTTOM
        )
        avail_w = PAGE[0] - LEFT - RIGHT

        styles = getSampleStyleSheet()
        base_h1 = styles.get('Heading1') or styles['Title']
        if 'H1Alt' not in styles.byName:
            styles.add(ParagraphStyle(
                name="H1Alt",
                parent=base_h1,
                fontSize=15,
                leading=18,
                spaceAfter=10,
                spaceBefore=4,
                alignment=1,  # center
                textColor=colors.HexColor("#153e75")
            ))
        if 'BodySm' not in styles.byName:
            styles.add(ParagraphStyle(
                name="BodySm",
                parent=styles['Normal'],
                leading=13,
                spaceAfter=4
            ))
        h1_style = styles['H1Alt']
        p_style  = styles['BodySm']

        # Helper: imagen centrada y encajada
        def _img_box(png_bytes: bytes, max_w_cm: float, max_h_cm: float):
            ip = tempfile.mktemp(suffix=".png")
            with open(ip, "wb") as f: f.write(png_bytes)
            img = RLImage(ip)
            img._restrictSize(max_w_cm*cm, max_h_cm*cm)
            img.hAlign = 'CENTER'
            t = Table([[img]], colWidths=[avail_w])
            t.setStyle(TableStyle([
                ("ALIGN",(0,0),(-1,-1),"CENTER"),
                ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
                ("LEFTPADDING",(0,0),(-1,-1),0),
                ("RIGHTPADDING",(0,0),(-1,-1),0),
                ("TOPPADDING",(0,0),(-1,-1),0),
                ("BOTTOMPADDING",(0,0),(-1,-1),0),
            ]))
            return t

        flow = []
        # Título
        flow.append(Paragraph(f"📊 Informe Semanal – {dept_name}", h1_style))
        flow.append(Paragraph(
            f"Semana próxima: <b>{data['next_mon'].isoformat()}</b> – <b>{data['next_sun'].isoformat()}</b><br/>"
            f"Comparativo semana anterior: {data['prev_mon'].isoformat()} – {data['prev_sun'].isoformat()}",
            p_style
        ))
        flow.append(Spacer(1, 8))

        # Gráficos (server-side)
        if charts_png.get("dep_area"):
            flow.append(_img_box(charts_png["dep_area"], max_w_cm=17.0, max_h_cm=7.2))
            flow.append(Spacer(1, 6))
        if charts_png.get("resp"):
            flow.append(_img_box(charts_png["resp"], max_w_cm=17.0, max_h_cm=7.0))
            flow.append(Spacer(1, 6))
        if charts_png.get("trend"):
            flow.append(_img_box(charts_png["trend"], max_w_cm=17.0, max_h_cm=7.0))
            flow.append(Spacer(1, 8))

        # Interpretación ejecutiva
        flow.append(Paragraph("<b>Análisis por frecuencia</b>", p_style))
        for p in _build_insights(data["rows"]):
            flow.append(Paragraph("• " + p, p_style))
        flow.append(Spacer(1, 8))

        # Tabla resumen por responsable
        header = ["Responsable","Plan (prev)","Hechos (prev)","%","Diario P/H","Semanal P/H","Mensual P/H","Tareas próxima semana"]
        table_data = [header]

        def P(txt):  # wrap de textos largos
            return Paragraph(str(txt).replace("\n", "<br/>"), styles['BodySm'])

        for r in data["rows"]:
            d = r["detalle_prev"]
            tareas_txt = ", ".join(t["tarea"] for t in r["tareas_next"]) or "—"
            table_data.append([
                P(r["responsable"]),
                f"{r['planned_prev']}",
                f"{r['done_prev']}",
                f"{r['cumplimiento_prev']:.1f}%",
                f"{d['Diario']['plan']}/{d['Diario']['done']}",
                f"{d['Semanal']['plan']}/{d['Semanal']['done']}",
                f"{d['Mensual']['plan']}/{d['Mensual']['done']}",
                P(tareas_txt),
            ])

        col_widths = [
            0.18*avail_w, 0.10*avail_w, 0.10*avail_w, 0.08*avail_w,
            0.12*avail_w, 0.12*avail_w, 0.12*avail_w, 0.18*avail_w
        ]
        tbl = Table(table_data, colWidths=col_widths, repeatRows=1, hAlign="CENTER")
        tbl.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0), colors.HexColor("#f5f5f5")),
            ("TEXTCOLOR",(0,0),(-1,0), colors.black),
            ("ALIGN",(0,0),(-1,0),"CENTER"),
            ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
            ("FONTSIZE",(0,0),(-1,0),10),
            ("GRID",(0,0),(-1,-1), 0.25, colors.grey),
            ("LEFTPADDING",(0,0),(-1,-1),4),
            ("RIGHTPADDING",(0,0),(-1,-1),4),
            ("TOPPADDING",(0,0),(-1,-1),3),
            ("BOTTOMPADDING",(0,0),(-1,-1),3),
            ("VALIGN",(0,1),(-1,-1),"TOP"),
            ("ALIGN",(1,1),(3,-1),"RIGHT"),   # números
            ("ALIGN",(4,1),(6,-1),"CENTER"),  # P/H
            ("ALIGN",(0,1),(0,-1),"LEFT"),    # Responsable
            ("ALIGN",(7,1),(7,-1),"LEFT"),    # Tareas próxima semana
            ("FONTSIZE",(0,1),(-1,-1),9),
        ]))
        flow.append(tbl)

        doc.build(flow)
        with open(tmp, "rb") as f:
            content = f.read()
        os.remove(tmp)
        return f"{title}.pdf", content, "application/pdf"

    # ---------- Fallback HTML ----------
    html = render_template_string("""
    <h2>Informe semanal – {{ dept }}</h2>
    <p>Semana próxima: <b>{{ nm }}</b> – <b>{{ ns }}</b><br>
       Semana anterior: {{ pm }} – {{ ps }}</p>

    {% if charts.dep_area %}<img src="data:image/png;base64,{{ charts.dep_area }}" style="max-width:100%">{% endif %}
    {% if charts.resp %}<img src="data:image/png;base64,{{ charts.resp }}" style="max-width:100%">{% endif %}
    {% if charts.trend %}<img src="data:image/png;base64,{{ charts.trend }}" style="max-width:100%">{% endif %}

    <h4>Insights</h4>
    <ul>
      {% for p in insights %}<li>{{ p }}</li>{% endfor %}
    </ul>

    <table border="1" cellspacing="0" cellpadding="4">
      <tr><th>Responsable</th><th>Plan(prev)</th><th>Hechos(prev)</th><th>%</th>
          <th>Diario P/H</th><th>Semanal P/H</th><th>Mensual P/H</th><th>Tareas próxima semana</th></tr>
      {% for r in rows %}
        <tr>
          <td>{{ r.responsable }}</td>
          <td align="right">{{ r.planned_prev }}</td>
          <td align="right">{{ r.done_prev }}</td>
          <td align="right">{{ "%.1f"|format(r.cumplimiento_prev) }}%</td>
          <td align="center">{{ r.detalle_prev.Diario.plan }}/{{ r.detalle_prev.Diario.done }}</td>
          <td align="center">{{ r.detalle_prev.Semanal.plan }}/{{ r.detalle_prev.Semanal.done }}</td>
          <td align="center">{{ r.detalle_prev.Mensual.plan }}/{{ r.detalle_prev.Mensual.done }}</td>
          <td>{{ ", ".join([t.tarea for t in r.tareas_next]) or "—" }}</td>
        </tr>
      {% endfor %}
    </table>
    """,
        dept=dept_name, nm=data["next_mon"].isoformat(), ns=data["next_sun"].isoformat(),
        pm=data["prev_mon"].isoformat(), ps=data["prev_sun"].isoformat(),
        rows=data["rows"],
        insights=_build_insights(data["rows"]),
        charts={
            "resp": base64.b64encode(charts_png.get("resp", b"")).decode("ascii") if charts_png.get("resp") else "",
            "trend": base64.b64encode(charts_png.get("trend", b"")).decode("ascii") if charts_png.get("trend") else "",
            "dep_area": base64.b64encode(charts_png.get("dep_area", b"")).decode("ascii") if charts_png.get("dep_area") else "",
        }
    )
    return f"{title}.html", html.encode("utf-8"), "text/html"

# ---------------------------------------------------------------------
# Rutas: Informe semanal (endpoints únicos)
# ---------------------------------------------------------------------
@notif_bp.get("/informe/weekly", endpoint="weekly_report_ping")
def weekly_report_ping():
    current_app.logger.info("[InformeSemanal] GET ping recibido")
    flash("Ping OK: la ruta /notificaciones/informe/weekly existe.", "info")
    return redirect(url_for("notifications.dashboard"))

@notif_bp.post("/informe/weekly", endpoint="weekly_report_send_pdf")
def weekly_report_send_pdf():
    """
    Genera y envía por correo un informe por CADA departamento configurado
    en plan_dept_config (notify_user_id o notify_email).
    """
    conn = get_db()
    cur = conn.cursor()
    rows = cur.execute("""
        SELECT p.departamento_id   AS dep_id,
               COALESCE(u.email, p.notify_email) AS email,
               COALESCE(d.nombre, '') AS dep_name
          FROM plan_dept_config p
          LEFT JOIN usuarios u      ON u.id = p.notify_user_id
          LEFT JOIN departamentos d ON d.id = p.departamento_id
         WHERE COALESCE(u.email, p.notify_email) IS NOT NULL
    """).fetchall()
    if not rows:
        flash("No hay destinatarios configurados en plan_dept_config.", "warning")
        return redirect(url_for("notifications.dashboard"))

    # lunes que se informará como "próxima semana"
    today = date.today()
    next_mon = _monday_of(today) if today.weekday() == 0 else _monday_of(today + timedelta(days=7))

    ok = err = 0
    for r in rows:
        dep_id   = r["dep_id"]
        to_email = r["email"]
        dep_name = r["dep_name"] or f"Dept {dep_id}"

        data = _collect_weekly_data(conn, dep_id, next_mon)

        # Gráficos server-side (sin capturar pantallas)
        png_dep_area = _chart_week_dep_area(conn, dep_id, data["prev_mon"], data["prev_sun"])
        png_resp     = _chart_resp_perf(data["rows"])
        png_trend    = _chart_daily_trend(conn, dep_id, data["prev_mon"], data["prev_sun"])

        # Construir PDF/HTML
        fname, content, mime = _build_pdf_or_html(
            dep_name, data,
            {"resp": png_resp, "trend": png_trend, "dep_area": png_dep_area},
            dashboard_pngs=[]  # sin capturas
        )

        subject  = f"Informe semanal OKR – {dep_name} ({data['next_mon'].isoformat()} – {data['next_sun'].isoformat()})"
        html_body = """📌 Informe semanal de OKR (semana anterior)

Adjunto encontrará el informe correspondiente a la semana que acaba de finalizar, con:
📊 Gráficos de desempeño
📈 Análisis de cumplimiento por frecuencia
✅ Resumen de avances y pendientes"""

        try:
            tmpdir = tempfile.mkdtemp(prefix="informe_sem_")
            fpath  = os.path.join(tmpdir, fname)
            with open(fpath, "wb") as f:
                f.write(content)

            send_mail_planilla(
                conn,
                to_email,
                subject,
                html_body,
                text=html_body,
                attachments=[fpath],
            )
            ok += 1
        except Exception as e:
            current_app.logger.error("Informe semanal: error enviando a %s -> %s", to_email, e)
            err += 1

    flash(f"Informes enviados: OK={ok}, ERROR={err}", "info" if err == 0 else "warning")
    return redirect(url_for("notifications.dashboard"))

# ---------------------------------------------------------------------
# Dashboard de cola + filtros
# ---------------------------------------------------------------------
@notif_bp.get("/")
def dashboard():
    conn = get_db()
    users = conn.execute("SELECT id, username FROM usuarios ORDER BY username").fetchall()

    q_fecha  = (request.args.get("fecha") or "").strip()
    q_userid = request.args.get("user_id", type=int)
    q_tipo   = (request.args.get("tipo") or "").strip()
    q_canal  = (request.args.get("canal") or "").strip()
    q_estado = (request.args.get("estado") or "").strip()

    where, params = [], []
    if q_fecha:
        where.append("q.fecha_obj = ?"); params.append(q_fecha)
    if q_userid:
        where.append("q.user_id = ?");   params.append(q_userid)
    if q_tipo:
        where.append("q.tipo = ?");      params.append(q_tipo)
    if q_canal:
        where.append("q.canal = ?");     params.append(q_canal)
    if q_estado:
        where.append("q.estado = ?");    params.append(q_estado)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    queue = conn.execute(f"""
      SELECT 
        q.id, q.user_id,
        COALESCE(u.username, u.email, '—') AS user_desc,
        q.tarea_id,
        COALESCE(pt.nombre, '—')           AS tarea_desc,
        q.tipo,
        CASE q.tipo
          WHEN 'hoy'             THEN 'Recordatorio del día'
          WHEN 'vencida'         THEN 'Tarea vencida'
          WHEN 'resumen_semanal' THEN 'Resumen semanal'
          WHEN 'resumen_mensual' THEN 'Resumen mensual'
          ELSE q.tipo
        END                                 AS tipo_desc,
        q.fecha_obj, q.canal, q.estado,
        q.scheduled_at, q.sent_at, q.error_msg
      FROM notify_queue q
      LEFT JOIN usuarios    u  ON u.id  = q.user_id
      LEFT JOIN plan_tareas pt ON pt.id = q.tarea_id
      {where_sql}
      ORDER BY q.id DESC
      LIMIT 500
    """, tuple(params)).fetchall()

    return render_template(
        "notifications/admin_dashboard.html",
        queue=queue,
        users=users,
        TPL_TYPES=TPL_TYPES,
        q_fecha=q_fecha, q_userid=q_userid, q_tipo=q_tipo, q_canal=q_canal, q_estado=q_estado,
    )

# ---------------------------------------------------------------------
# Acciones masivas (checkbox)
# ---------------------------------------------------------------------
@notif_bp.post("/bulk")
def queue_bulk_action():
    """
    Acciones masivas:
      - action=send  -> envía ahora cada id seleccionado
      - action=retry -> reprograma cada id seleccionado (estado=pending)
    """
    action = (request.form.get("action") or "").strip()
    ids = request.form.getlist("ids")
    if not ids:
        flash("No hay elementos seleccionados.", "warning")
        return redirect(url_for("notifications.dashboard", **request.args))
    try:
        ids_int = [int(x) for x in ids]
    except Exception:
        flash("IDs inválidos.", "danger")
        return redirect(url_for("notifications.dashboard", **request.args))

    conn = get_db()

    if action == "retry":
        placeholders = ",".join(["?"] * len(ids_int))
        conn.execute(
            f"""UPDATE notify_queue
                   SET estado='pending',
                       error_msg=NULL,
                       scheduled_at=datetime('now')
                 WHERE id IN ({placeholders})""",
            ids_int,
        )
        conn.commit()
        flash(f"Reprogramadas {len(ids_int)} notificaciones.", "info")
        return redirect(url_for("notifications.dashboard", **request.args))

    if action == "send":
        from modules.scheduler_jobs import _process_one
        ok = err = 0
        for nid in ids_int:
            row = conn.execute("SELECT * FROM notify_queue WHERE id=?", (nid,)).fetchone()
            if not row:
                err += 1
                continue
            try:
                _process_one(conn, row)
                ok += 1
            except Exception as e:
                err += 1
                conn.execute("UPDATE notify_queue SET estado='error', error_msg=? WHERE id=?", (str(e), nid))
                conn.commit()
        flash(f"Envío masivo: OK={ok}, ERROR={err}", "success" if err == 0 else "warning")
        return redirect(url_for("notifications.dashboard", **request.args))

    flash("Acción no reconocida.", "danger")
    return redirect(url_for("notifications.dashboard", **request.args))

# ---------------------------------------------------------------------
# Acciones por fila
# ---------------------------------------------------------------------
@notif_bp.post("/queue/retry/<int:nid>")
def queue_retry(nid):
    conn = get_db()
    conn.execute("""
        UPDATE notify_queue
           SET estado='pending',
               error_msg=NULL,
               scheduled_at=datetime('now')
         WHERE id=?
    """, (nid,))
    conn.commit()
    return redirect(url_for("notifications.dashboard"))

@notif_bp.post("/queue/send/<int:nid>")
def queue_send_now(nid):
    from modules.scheduler_jobs import _process_one
    conn = get_db()
    row = conn.execute("SELECT * FROM notify_queue WHERE id=?", (nid,)).fetchone()
    if not row:
        abort(404, "Item no existe")
    try:
        _process_one(conn, row)
    except Exception as e:
        conn.execute("UPDATE notify_queue SET estado='error', error_msg=? WHERE id=?", (str(e), nid))
        conn.commit()
    return redirect(url_for("notifications.dashboard"))

# ---------------------------------------------------------------------
# Plantillas (listar/crear/editar)
# ---------------------------------------------------------------------
@notif_bp.get("/templates")
def tpl_list():
    conn = get_db()
    rows = conn.execute(
        "SELECT key, subject, COALESCE(tipo,'') AS tipo FROM notify_templates ORDER BY key"
    ).fetchall()
    return render_template("notifications/tpl_list.html", rows=rows, TPL_TYPES=TPL_TYPES)

@notif_bp.route("/templates/new", methods=["GET", "POST"])
def tpl_new():
    conn = get_db()
    if request.method == "GET":
        return render_template("notifications/tpl_form.html", row=None, TPL_TYPES=TPL_TYPES)

    key     = (request.form.get("key") or "").strip()
    tipo    = (request.form.get("tipo") or "").strip() or None
    subject = (request.form.get("subject") or "").strip()
    html    = (request.form.get("html") or "").strip()
    text    = (request.form.get("text") or "").strip() or None

    if not key or not subject or not html:
        return "Completa clave, asunto y HTML", 400

    conn.execute(
        "INSERT INTO notify_templates(key, subject, html, text, tipo) VALUES (?,?,?,?,?)",
        (key, subject, html, text, tipo)
    )
    conn.commit()
    return redirect(url_for("notifications.tpl_list"))

@notif_bp.route("/templates/edit/<key>", methods=["GET", "POST"])
def tpl_edit(key):
    conn = get_db()
    if request.method == "GET":
        row = conn.execute("""
            SELECT key, subject, html, text, COALESCE(tipo,'') AS tipo
              FROM notify_templates
             WHERE key=?
        """, (key,)).fetchone()
        if not row:
            abort(404)
        return render_template("notifications/tpl_form.html", row=row, TPL_TYPES=TPL_TYPES)

    tipo    = (request.form.get("tipo") or "").strip() or None
    subject = (request.form.get("subject") or "").strip()
    html    = (request.form.get("html") or "").strip()
    text    = (request.form.get("text") or "").strip() or None

    if not subject or not html:
        return "Completa asunto y HTML", 400

    conn.execute("""
        UPDATE notify_templates
           SET subject=?, html=?, text=?, tipo=?
         WHERE key=?
    """, (subject, html, text, tipo, key))
    conn.commit()
    return redirect(url_for("notifications.tpl_list"))

# ---------------------------------------------------------------------
# Preferencias por usuario
# ---------------------------------------------------------------------
@notif_bp.get("/prefs")
def prefs_list():
    conn = get_db()
    rows = conn.execute("""
      SELECT u.id, u.username,
             COALESCE(p.email_on,1)  AS email_on,
             COALESCE(p.inapp_on,1)  AS inapp_on,
             COALESCE(p.slack_on,0)  AS slack_on,
             p.quiet_start, p.quiet_end, p.daily_time, p.weekly_dow, p.weekly_time
      FROM usuarios u
      LEFT JOIN notify_user_prefs p ON p.user_id=u.id
      ORDER BY u.username
    """).fetchall()
    return render_template("notifications/prefs_list.html", rows=rows)

@notif_bp.route("/prefs/edit/<int:user_id>", methods=["GET","POST"])
def prefs_edit(user_id):
    conn = get_db()
    if request.method == "GET":
        row = conn.execute("""
          SELECT u.id, u.username, p.*
          FROM usuarios u
          LEFT JOIN notify_user_prefs p ON p.user_id=u.id
          WHERE u.id=?
        """, (user_id,)).fetchone()
        return render_template("notifications/prefs_form.html", row=row)

    # POST: guardar
    email_on  = 1 if request.form.get("email_on") == "on" else 0
    inapp_on  = 1 if request.form.get("inapp_on") == "on" else 0
    slack_on  = 1 if request.form.get("slack_on") == "on" else 0
    slack_webhook = (request.form.get("slack_webhook") or "").strip() or None
    quiet_start   = (request.form.get("quiet_start") or "").strip() or None
    quiet_end     = (request.form.get("quiet_end") or "").strip() or None
    daily_time    = (request.form.get("daily_time") or "").strip() or None
    weekly_dow    = (request.form.get("weekly_dow") or "").strip() or None
    weekly_time   = (request.form.get("weekly_time") or "").strip() or None

    conn.execute("""
      INSERT INTO notify_user_prefs(
        user_id, email_on, inapp_on, slack_on, slack_webhook,
        quiet_start, quiet_end, daily_time, weekly_dow, weekly_time
      )
      VALUES (?,?,?,?,?,?,?,?,?,?)
      ON CONFLICT(user_id) DO UPDATE SET
        email_on=excluded.email_on,
        inapp_on=excluded.inapp_on,
        slack_on=excluded.slack_on,
        slack_webhook=excluded.slack_webhook,
        quiet_start=excluded.quiet_start,
        quiet_end=excluded.quiet_end,
        daily_time=excluded.daily_time,
        weekly_dow=excluded.weekly_dow,
        weekly_time=excluded.weekly_time
    """, (
        user_id, email_on, inapp_on, slack_on, slack_webhook,
        quiet_start, quiet_end, daily_time, weekly_dow, weekly_time
    ))
    conn.commit()
    return redirect(url_for("notifications.prefs_list"))
