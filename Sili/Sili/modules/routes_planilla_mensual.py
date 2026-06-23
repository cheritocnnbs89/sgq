# modules/routes_planilla_mensual.py
from datetime import date, datetime, timedelta
import os, calendar, smtplib, mimetypes
from email.message import EmailMessage

from flask import (
    Blueprint, render_template, render_template_string, request, jsonify,
    session, abort, redirect, url_for, current_app, send_file
)
from werkzeug.utils import secure_filename
from .db import get_db

planilla_bp = Blueprint("planilla_mensual", __name__, url_prefix="/planilla-mensual")

# ---------- Config ----------
FRECUENCIAS   = ("Diario", "Semanal", "Mensual")
ALLOWED_EXT   = {"pdf", "png", "jpg", "jpeg", "webp"}
MAX_UPLOAD_MB = 20  # límite del lado servidor


# ---------- Utilidades de fecha ----------
def month_days(y: int, m: int):
    last = calendar.monthrange(y, m)[1]
    return [date(y, m, d) for d in range(1, last + 1)]

def prev_next(y: int, m: int):
    prev_y, prev_m = (y - 1, 12) if m == 1 else (y, m - 1)
    next_y, next_m = (y + 1, 1) if m == 12 else (y, m + 1)
    return prev_y, prev_m, next_y, next_m

def has_perm(key: str, action: str = "ver") -> bool:
    role = (session.get("rol") or "").lower()
    if role == "admin" or session.get("is_admin"):
        return True
    perms = session.get("permissions") or {}
    return bool(perms.get(key, {}).get(action))

# --- helpers de sesión/seguridad ---
def _is_admin() -> bool:
    return (str(session.get("rol") or "").lower() == "admin") or bool(session.get("is_admin"))

def _current_username() -> str:
    return (session.get("usuario") or "").strip()

def _can_access_task(conn, tarea_id: int) -> bool:
    """Admin = True. Usuario no admin: solo si usuario_id coincide con el usuario logueado."""
    if _is_admin():
        return True
    row = conn.execute("""
        SELECT LOWER(u.username) AS resp
        FROM plan_tareas t
        JOIN usuarios u ON u.id = t.usuario_id
        WHERE t.id = ?
    """, (tarea_id,)).fetchone()
    if not row:
        return False
    return (row["resp"] or "") == _current_username().lower()

def _uploads_dir():
    base = current_app.instance_path  # p.ej. /.../instance
    folder = os.path.join(base, "uploads", "planilla")
    os.makedirs(folder, exist_ok=True)
    return folder

def _allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


# ---------- Config / correo ----------
def cfg_get(conn, clave, default=None):
    try:
        row = conn.execute("SELECT valor FROM configuracion WHERE clave=?", (clave,)).fetchone()
        if not row:
            return default
        try:
            return row["valor"]
        except Exception:
            return row[0]
    except Exception:
        return default

def cfg_set(conn, clave, valor):
    cur = conn.cursor()
    cur.execute("""
        UPDATE configuracion
        SET valor = ?
        WHERE clave = ?
    """, (str(valor), clave))
    if cur.rowcount == 0:
        cur.execute("""
            INSERT INTO configuracion(clave, valor)
            VALUES(?, ?)
        """, (clave, str(valor)))
    conn.commit()

def evidence_mode_enabled(conn) -> bool:
    # default: ON (1)
    v = cfg_get(conn, "planilla_evidence_mode", "1")
    return str(v).lower() not in ("0", "false", "no")

def smtp_cfg(conn):
    host = cfg_get(conn, "smtp_host", "")
    port = int(cfg_get(conn, "smtp_port", "587") or 587)
    user = cfg_get(conn, "smtp_user", "")
    pwd  = cfg_get(conn, "smtp_pass", "")
    from_addr = cfg_get(conn, "smtp_from", user)
    tls = cfg_get(conn, "smtp_tls", "1")
    return {
        "host": host, "port": port, "user": user, "pwd": pwd,
        "from": from_addr, "tls": str(tls).lower() not in ("0", "false", "no")
    }

def send_mail(conn, to_addr, subject, html, text=None, attachments=None):
    cfg = smtp_cfg(conn)
    if not to_addr:
        return
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"]    = cfg["from"] or cfg["user"]
    msg["To"]      = to_addr

    if text:
        msg.set_content(text)
        msg.add_alternative(html or "", subtype="html")
    else:
        msg.set_content("Este mensaje requiere un cliente que soporte HTML.")
        msg.add_alternative(html or "", subtype="html")

    for path in attachments or []:
        if not path or not os.path.exists(path):
            continue
        ctype, _ = mimetypes.guess_type(path)
        maintype, subtype = (ctype.split("/", 1) if ctype else ("application", "octet-stream"))
        with open(path, "rb") as f:
            msg.add_attachment(
                f.read(), maintype=maintype, subtype=subtype,
                filename=os.path.basename(path)
            )

    with smtplib.SMTP(cfg["host"], cfg["port"]) as s:
        s.ehlo()
        if cfg["tls"]:
            s.starttls()
        if cfg["user"]:
            s.login(cfg["user"], cfg["pwd"])
        s.send_message(msg)


# ---------- Esquema mínimo ----------
def ensure_schema(conn):
    """
    No-op en SQL Server.
    El esquema de planilla mensual ya debe existir y mantenerse fuera del backend.
    """
    return

# ---------- helpers negocio ----------
def dept_email_for_tarea(conn, tarea_id):
    """Devuelve (email, nombre_departamento, nombre_responsable)"""
    cur = conn.cursor()
    row = cur.execute("""
        SELECT t.departamento_id, d.nombre as depto_nombre,
               COALESCE(NULLIF(LTRIM(RTRIM(u.nombre_completo)),''), u.username) as resp_nombre
        FROM plan_tareas t
        LEFT JOIN departamentos d ON d.id = t.departamento_id
        LEFT JOIN usuarios u ON u.id = t.usuario_id
        WHERE t.id = ?
    """, (tarea_id,)).fetchone()

    if not row:
        return None, None, None

    dept_id   = row["departamento_id"] if hasattr(row, "keys") else row[0]
    dept_name = row["depto_nombre"]    if hasattr(row, "keys") else row[1]
    resp_name = row["resp_nombre"]     if hasattr(row, "keys") else row[2]

    if not dept_id:
        return None, dept_name, resp_name

    cfg = conn.execute(
        "SELECT notify_user_id, notify_email FROM plan_dept_config WHERE departamento_id=?",
        (dept_id,)
    ).fetchone()
    if not cfg:
        return None, dept_name, resp_name

    if (cfg["notify_user_id"] if hasattr(cfg, "keys") else cfg[0]):
        u = conn.execute("SELECT email FROM usuarios WHERE id=?",
                         (cfg["notify_user_id"] if hasattr(cfg, "keys") else cfg[0],)).fetchone()
        if u:
            email = u["email"] if hasattr(u, "keys") else u[0]
            return email, dept_name, resp_name

    email = (cfg["notify_email"] if hasattr(cfg, "keys") else cfg[1]) or None
    return email, dept_name, resp_name




def render_mail_template(conn, key, **ctx):
    """Reemplaza la función existente del mismo nombre."""
    tpl = conn.execute(
        "SELECT subject, html, text FROM plan_mail_templates WHERE [key]=?",   # ← [key] corregido
        (key,)
    ).fetchone()
    if not tpl:
        return ("Evidencia registrada", "Evidencia registrada.", None)
    subj = tpl["subject"] if hasattr(tpl, "keys") else tpl[0]
    html = tpl["html"]    if hasattr(tpl, "keys") else tpl[1]
    text = tpl["text"]    if hasattr(tpl, "keys") else tpl[2]
    return (
        render_template_string(subj, **ctx),
        render_template_string(html, **ctx),
        (render_template_string(text, **ctx) if text else None),
    )


 

# =============== DASHBOARD ===============
 
# =============== DASHBOARD ===============
@planilla_bp.get("/dashboard")
def planilla_dashboard():
    if not has_perm("Planilla Mensual", "ver"):
        abort(403)

    # ===== Filtros básicos =====
    freq = (request.args.get("freq") or "todos").strip().lower()
    if freq not in ("todos", "diario", "semanal", "mensual"):
        freq = "todos"

    today = date.today()
    #today = date(2025, 10, 27)

    y     = int(request.args.get("year",  today.year))
    m     = int(request.args.get("month", today.month))
    dias  = month_days(y, m)
    ini   = dias[0].isoformat()
    fin   = dias[-1].isoformat()
    cutoff_date = min(today, dias[-1])
    prev_y, prev_m, next_y, next_m = prev_next(y, m)

    # Filtros adicionales (por nombre)
    area_sel  = (request.args.get("area")  or "").strip()
    depto_sel = (request.args.get("depto") or "").strip()
    resp_sel  = (request.args.get("resp")  or "").strip()

    conn = get_db()
    cur = conn.cursor()

    # ===== Restricción por usuario (no admin) =====
    role = (session.get("rol") or "").lower()
    is_admin = (role == "admin" or bool(session.get("is_admin")))
    username = (session.get("usuario") or "").strip()

    base_sql = """
        SELECT t.id, t.nombre, t.frecuencia, t.activo,
               t.departamento_id, t.dia_semana, t.dia_mes,
               u.username                                              AS responsable,
               COALESCE(NULLIF(LTRIM(RTRIM(u.nombre_completo)),''),
                        u.username)                                    AS responsable_display,
               d.nombre                                                AS depto,
               a.nombre                                                AS area_nombre,
               t.okr_id,
               o.nombre                                                AS okr_nombre,
               t.resultado_clave_id,
               rc.nombre                                               AS resultado_clave_nombre
        FROM plan_tareas t
        JOIN usuarios u ON u.id = t.usuario_id
        LEFT JOIN departamentos d ON d.id = t.departamento_id
        LEFT JOIN areas a ON a.id = d.area_id
        LEFT JOIN plan_okrs o ON o.id = t.okr_id
        LEFT JOIN plan_resultados_clave rc ON rc.id = t.resultado_clave_id
        WHERE t.activo = 1
          AND COALESCE(u.disabled, 0) = 0
    """
    params = []
    if not is_admin:
        base_sql += " AND LOWER(u.username)=LOWER(?) "
        params.append(username)

    tareas = [dict(row) for row in cur.execute(base_sql, params).fetchall()]

    # NORMALIZAR CAMPOS
    for t in tareas:
        t["frecuencia"] = (t.get("frecuencia") or "").strip().lower()
        t["dia_semana"] = None if t.get("dia_semana") is None else int(t["dia_semana"])
        t["dia_mes"]    = None if t.get("dia_mes") is None else int(t["dia_mes"])

    # Listas para combos
    areas_list       = sorted({t["area_nombre"] for t in tareas if t.get("area_nombre")})
    departamentos_list = sorted({t["depto"] for t in tareas if t.get("depto")})

    # responsables_list filtrado por departamento/área seleccionado (si aplica)
    tareas_para_resp = tareas
    if area_sel:
        tareas_para_resp = [t for t in tareas_para_resp if (t.get("area_nombre") or "") == area_sel]
    if depto_sel:
        tareas_para_resp = [t for t in tareas_para_resp if (t.get("depto") or "") == depto_sel]
    _resp_map = {t["responsable"]: t.get("responsable_display") or t["responsable"]
                 for t in tareas_para_resp if t.get("responsable")}
    responsables_list = sorted(_resp_map.keys())
    responsables_display = _resp_map

    # ===== Filtros de vista =====
    if freq != "todos":
        tareas = [t for t in tareas if t["frecuencia"].lower() == freq]
    if area_sel:
        tareas = [t for t in tareas if (t.get("area_nombre") or "") == area_sel]
    if depto_sel:
        tareas = [t for t in tareas if (t.get("depto") or "") == depto_sel]
    if resp_sel:
        tareas = [t for t in tareas if (t.get("responsable") or "") == resp_sel]

    # Si no hay tareas visibles
    task_ids = [t["id"] for t in tareas]
    if not task_ids:
        kpis = dict(
            cumplimiento=0.0, realizadas=0, planeadas=0,
            puntualidad=0.0, con_archivo=0.0, pendientes_hoy=0,
            esperado_hoy_pct=0.0, real_a_hoy_pct=0.0, backlog=0,
            proyeccion_pct=0.0
        )
        chart = dict(
            deps={"labels": [], "realizadas": [], "planeadas": []},
            reps={"labels": [], "realizadas": [], "planeadas": []},
            trend={"labels": [], "realizadas": []},
            burnup={"labels": [], "plan_acum": [], "real_acum": []}
        )
        _empty_kf = dict(real_pct=0.0, esp_pct=0.0, realizadas=0, planeadas=0, plan_h=0, real_h=0)
        return render_template(
            "planilla/dashboard.html",
            y=y, m=m, kpis=kpis, chart=chart,
            kpis_freq={"diario": _empty_kf, "semanal": _empty_kf, "mensual": _empty_kf},
            top_high=[], top_low=[], dept_rows=[],
            freq=freq, areas_list=areas_list, departamentos_list=departamentos_list,
            responsables_list=responsables_list, responsables_display=responsables_display,
            area_sel=area_sel, depto_sel=depto_sel,
            resp_sel=resp_sel, prev_y=prev_y, prev_m=prev_m,
            next_y=next_y, next_m=next_m, summary_rows=[],
            proj_rows=[], proj_cols=[],
        )

    ph = ",".join(["?"] * len(task_ids))

    # --- Feriados del mes (por país; usa 'EC' por defecto) ---
    pais = 'EC'
    month_start = dias[0].isoformat()
    month_end   = dias[-1].isoformat()

    feriados_rows = cur.execute("""
        SELECT fecha FROM plan_feriados
        WHERE fecha BETWEEN ? AND ? AND (pais = ? OR pais IS NULL)
    """, (month_start, month_end, pais)).fetchall()

    FERIADOS = {(r["fecha"] if hasattr(r, "keys") else r[0]) for r in feriados_rows}

    def _is_weekend(d: date) -> bool:
        return d.weekday() in (5, 6)

    def _is_holiday(d: date) -> bool:
        return d.isoformat() in FERIADOS

    def _is_non_working_day(d: date) -> bool:
        return _is_weekend(d) or _is_holiday(d)

    def _effective_cutoff(today_: date, workdays_list):
        cand = [d for d in workdays_list if d <= today_]
        return cand[-1] if cand else None

    from collections import defaultdict

    def _last_day_of_month(y2, m2):
        return calendar.monthrange(y2, m2)[1]

    def _occurs_this_day(t, d: date) -> bool:
        if _is_non_working_day(d):
            return False

        f = (t.get("frecuencia") or "").lower()
        if f == "diario":
            return True

        if f == "semanal":
            ds = t.get("dia_semana")
            if ds is None:
                ds = 0
            if 1 <= ds <= 7:
                ds = (ds - 1)
            if ds in (5, 6):
                return False
            return d.weekday() == ds

        if f == "mensual":
            dm = t.get("dia_mes")
            if dm is None:
                return d.day == 1
            dm = min(int(dm), _last_day_of_month(d.year, d.month))
            return d.day == dm

        return False

    def _planned_counts_by_day(tareas_list, days_list):
        out = defaultdict(int)
        for d in days_list:
            if _is_non_working_day(d):
                continue
            for t in tareas_list:
                if _occurs_this_day(t, d):
                    out[d.isoformat()] += 1
        return out

    workdays_all = [d for d in dias if not _is_non_working_day(d)]
    cutoff_eff   = _effective_cutoff(today, workdays_all)

    workdays_elapsed = [d for d in workdays_all if cutoff_eff and d <= cutoff_eff]
    wd_total   = len(workdays_all)
    wd_elapsed = len(workdays_elapsed)

    planned_per_day = _planned_counts_by_day(tareas, dias)

    def planned_in_month_task(t, days_list) -> int:
        return sum(1 for d in days_list if _occurs_this_day(t, d))

    planeadas_por_tarea = {t["id"]: planned_in_month_task(t, dias) for t in tareas}

    rows_checks_mes = cur.execute(f"""
        SELECT tarea_id, CONVERT(varchar(10), CAST(fecha AS date), 23) AS f
        FROM plan_checks
        WHERE fecha BETWEEN ? AND ? AND COALESCE(checked,1)=1
          AND tarea_id IN ({ph})
    """, (ini, fin, *task_ids)).fetchall()

    from collections import defaultdict as _dd
    realizados_por_tarea = _dd(int)
    date_cache = {}
    for r in rows_checks_mes:
        tid = r["tarea_id"] if hasattr(r, "keys") else r[0]
        f   = r["f"] if hasattr(r, "keys") else r[1]
        d   = date_cache.setdefault(f, date.fromisoformat(f))
        if not _is_non_working_day(d):
            t = next((tt for tt in tareas if tt["id"] == tid), None)
            if t and _occurs_this_day(t, d):
                realizados_por_tarea[tid] += 1

    def planned_until_task(t, days_list, cutoff):
        if not cutoff:
            return 0
        return sum(1 for d in days_list if d <= cutoff and _occurs_this_day(t, d))

    planeadas_hoy_por_tarea = {t["id"]: planned_until_task(t, workdays_all, cutoff_eff) for t in tareas}

    if cutoff_eff:
        ce = cutoff_eff.isoformat()
        rows_hoy = cur.execute(f"""
            SELECT tarea_id, CONVERT(varchar(10), CAST(fecha AS date), 23) AS f
            FROM plan_checks
            WHERE fecha BETWEEN ? AND ? AND COALESCE(checked,1)=1
              AND tarea_id IN ({ph})
        """, (ini, ce, *task_ids)).fetchall()

        realizados_hoy_por_tarea = {t["id"]: 0 for t in tareas}
        date_cache2 = {}
        for r in rows_hoy:
            tid = r["tarea_id"] if hasattr(r, "keys") else r[0]
            f   = r["f"] if hasattr(r, "keys") else r[1]
            d   = date_cache2.setdefault(f, date.fromisoformat(f))
            if not _is_non_working_day(d):
                t = next((tt for tt in tareas if tt["id"] == tid), None)
                if t and _occurs_this_day(t, d):
                    realizados_hoy_por_tarea[tid] += 1
    else:
        realizados_hoy_por_tarea = {t["id"]: 0 for t in tareas}

    total_real = sum(realizados_por_tarea.get(t["id"], 0) for t in tareas)
    total_plan = sum(planeadas_por_tarea.get(t["id"], 0) for t in tareas)

    ev_rows = cur.execute(f"""
        SELECT COUNT(*) AS n
        FROM plan_evidencias
        WHERE fecha BETWEEN ? AND ? AND tarea_id IN ({ph})
    """, (ini, fin, *task_ids)).fetchone()
    evidencias_mes = int(ev_rows["n"] if hasattr(ev_rows, "keys") else ev_rows[0])
    puntualidad = (100.0 * evidencias_mes / total_plan) if total_plan else 0.0

    ev_file = cur.execute(f"""
        SELECT COUNT(*) AS n
        FROM plan_evidencias
        WHERE fecha BETWEEN ? AND ? AND file_path IS NOT NULL
          AND tarea_id IN ({ph})
    """, (ini, fin, *task_ids)).fetchone()
    evidencias_con_archivo = int(ev_file["n"] if hasattr(ev_file, "keys") else ev_file[0])
    con_archivo = (100.0 * evidencias_con_archivo / evidencias_mes) if evidencias_mes else 0.0

    day_rows_all = cur.execute(f"""
        SELECT CONVERT(varchar(10), CAST(fecha AS date), 23) AS f, COUNT(*) AS n
        FROM plan_checks
        WHERE fecha BETWEEN ? AND ? AND COALESCE(checked,1)=1
          AND tarea_id IN ({ph})
        GROUP BY CONVERT(varchar(10), CAST(fecha AS date), 23)
        ORDER BY f
    """, (ini, fin, *task_ids)).fetchall()

    real_per_day = {
        (r["f"] if hasattr(r, "keys") else r[0]): int(r["n"] if hasattr(r, "keys") else r[1])
        for r in day_rows_all
    }

    if cutoff_eff:
        planeados_hoy = sum(planned_per_day.get(d.isoformat(), 0) for d in workdays_all if d <= cutoff_eff)
        realizados_hoy = sum(real_per_day.get(d.isoformat(), 0) for d in workdays_all if d <= cutoff_eff)
    else:
        planeados_hoy = 0
        realizados_hoy = 0

    planeados_hoy_total  = sum(int(x or 0) for x in planeadas_hoy_por_tarea.values())
    realizados_hoy_total = sum(int(x or 0) for x in realizados_hoy_por_tarea.values())

    esperado_hoy_pct = (100.0 * planeados_hoy_total / (total_plan or 1)) if total_plan else 0.0

    if planeados_hoy_total:
        real_a_hoy_pct = 100.0 * realizados_hoy_total / planeados_hoy_total
    else:
        real_a_hoy_pct = 100.0 if realizados_hoy_total > 0 else 0.0

    backlog = max(0, planeados_hoy_total - realizados_hoy_total)

    pendientes_hoy = 0
    if y == today.year and m == today.month and not _is_non_working_day(today):
        plan_hoy = planned_per_day.get(today.isoformat(), 0)
        r = cur.execute(f"""
            SELECT COUNT(*) AS n FROM plan_checks
            WHERE fecha=? AND COALESCE(checked,1)=1
              AND tarea_id IN ({ph})
        """, (today.isoformat(), *task_ids)).fetchone()
        hechos_hoy = int(r["n"] if r else 0)
        pendientes_hoy = max(plan_hoy - hechos_hoy, 0)

    by_depto = {}
    for t in tareas:
        key = t["depto"] or "Sin depto"
        dct = by_depto.setdefault(key, {"real": 0, "plan": 0})
        dct["real"] += realizados_por_tarea.get(t["id"], 0)
        dct["plan"] += planeadas_por_tarea.get(t["id"], 0)

    deps_labels = list(by_depto.keys())
    deps_real   = [by_depto[k]["real"] for k in deps_labels]
    deps_plan   = [by_depto[k]["plan"] for k in deps_labels]

    by_resp = {}
    for t in tareas:
        key = t["responsable"]
        dct = by_resp.setdefault(key, {"real": 0, "plan": 0})
        dct["real"] += realizados_por_tarea.get(t["id"], 0)
        dct["plan"] += planeadas_por_tarea.get(t["id"], 0)

    reps_labels = list(by_resp.keys())
    reps_real   = [by_resp[k]["real"] for k in reps_labels]
    reps_plan   = [by_resp[k]["plan"] for k in reps_labels]

    trend_labels = [d.isoformat() for d in workdays_all]
    trend_real   = [real_per_day.get(x, 0) for x in trend_labels]

    plan_acum, real_acum, burn_labels = [], [], []
    acc_p = acc_r = 0

    for d in workdays_all:
        k = d.isoformat()
        acc_p += planned_per_day.get(k, 0)
        plan_acum.append(acc_p)

        if cutoff_eff and d <= cutoff_eff:
            acc_r += real_per_day.get(k, 0)
        real_acum.append(acc_r)

        burn_labels.append(k)

    chart = {
        "deps": {"labels": deps_labels, "realizadas": deps_real, "planeadas": deps_plan},
        "reps": {"labels": reps_labels, "realizadas": reps_real, "planeadas": reps_plan},
        "trend": {"labels": trend_labels, "realizadas": trend_real},
        "burnup": {"labels": burn_labels, "plan_acum": plan_acum, "real_acum": real_acum},
    }

    resp_rows = []
    for k, v in by_resp.items():
        plan_v = v["plan"]
        if plan_v > 0:
            resp_rows.append({
                "usuario": k,
                "realizadas": v["real"],
                "planeadas": plan_v,
                "porc": 100.0 * v["real"] / plan_v
            })
    top_high = sorted(resp_rows, key=lambda x: x["porc"], reverse=True)
    top_low  = sorted(resp_rows, key=lambda x: x["porc"])

    dept_rows = []
    for k, v in by_depto.items():
        plan_v = v["plan"]
        porc = (100.0 * v["real"] / plan_v) if plan_v else 0.0
        dept_rows.append({"depto": k, "realizadas": v["real"], "planeadas": plan_v, "porc": porc})
    dept_rows.sort(key=lambda x: (-x["porc"], x["depto"] or ""))

    avg_real_per_workday = (realizados_hoy_total / (wd_elapsed or 1))
    proy_mes_real        = avg_real_per_workday * wd_total
    proyeccion_pct       = (100.0 * proy_mes_real / (total_plan or 1)) if total_plan else 0.0

    from collections import defaultdict as _dd
    grp = _dd(lambda: {
        "plan_mes": 0, "real_mes": 0,
        "plan_hoy": 0, "real_hoy": 0,
        "depto": None, "resp": None
    })

    for t in tareas:
        tid = t["id"]
        key = (t.get("depto") or "Sin depto", t.get("responsable") or "—")
        g = grp[key]
        g["depto"], g["resp"] = key[0], key[1]
        g["plan_mes"] += int(planeadas_por_tarea.get(tid, 0) or 0)
        g["real_mes"] += int(realizados_por_tarea.get(tid, 0) or 0)
        g["plan_hoy"] += int(planeadas_hoy_por_tarea.get(tid, 0) or 0)
        g["real_hoy"] += int(realizados_hoy_por_tarea.get(tid, 0) or 0)

    wd_elapsed_safe = wd_elapsed or 1
    summary_rows = []
    for (dep, resp), g in grp.items():
        plan_mes = g["plan_mes"] or 0
        real_mes = g["real_mes"] or 0
        plan_hoy = g["plan_hoy"] or 0
        real_hoy = g["real_hoy"] or 0

        cumpl_mes_pct = 100.0 * real_mes / plan_mes if plan_mes else 0.0
        esperado_hoy_pct = 100.0 * plan_hoy / plan_mes if plan_mes else 0.0
        cumpl_a_hoy_pct = 100.0 * real_hoy / plan_hoy if plan_hoy else (100.0 if real_hoy > 0 else 0.0)
        gap_pct = cumpl_mes_pct - esperado_hoy_pct

        avg_real_group_per_wd = (real_hoy / wd_elapsed_safe)
        proy_mes_real_group   = avg_real_group_per_wd * wd_total
        proy_pct              = 100.0 * proy_mes_real_group / plan_mes if plan_mes else 0.0

        summary_rows.append({
            "depto": dep, "resp": resp,
            "plan_mes": plan_mes, "real_mes": real_mes,
            "cumpl_mes_pct": cumpl_mes_pct,
            "plan_hoy": plan_hoy, "real_hoy": real_hoy,
            "esperado_hoy_pct": esperado_hoy_pct,
            "cumpl_a_hoy_pct": cumpl_a_hoy_pct,
            "gap_pct": gap_pct,
            "proy_pct": proy_pct
        })

    summary_rows.sort(key=lambda r: ((r["depto"] or "").lower(), (r["resp"] or "").lower()))

    cumplimiento_mes = (100.0 * total_real / (total_plan or 1)) if total_plan else 0.0

    if planeados_hoy_total:
        cumplimiento_a_hoy = 100.0 * realizados_hoy_total / planeados_hoy_total
    else:
        cumplimiento_a_hoy = 100.0 if realizados_hoy_total > 0 else 0.0

    kpis = dict(
        cumplimiento=cumplimiento_a_hoy,
        real_a_hoy_pct=cumplimiento_mes,
        realizadas=total_real,
        planeadas=total_plan,
        puntualidad=puntualidad,
        con_archivo=con_archivo,
        pendientes_hoy=pendientes_hoy,
        esperado_hoy_pct=esperado_hoy_pct,
        backlog=backlog,
        proyeccion_pct=proyeccion_pct
    )

    # ── KPIs desglosados por frecuencia ──────────────────────────
    # Usa las mismas estructuras por-tarea ya calculadas.
    # Cuando freq=="todos" todos los grupos tienen datos.
    # Cuando se filtró una frecuencia específica, solo ese grupo tendrá datos.
    def _kpi_for_freq(fr_name):
        _t = [t for t in tareas if (t.get("frecuencia") or "").lower() == fr_name]
        if not _t:
            return dict(real_pct=0.0, esp_pct=0.0, realizadas=0, planeadas=0,
                        plan_h=0, real_h=0)
        _plan   = sum(planeadas_por_tarea.get(t["id"], 0) for t in _t)
        _real   = sum(realizados_por_tarea.get(t["id"], 0) for t in _t)
        _plan_h = sum(planeadas_hoy_por_tarea.get(t["id"], 0) for t in _t)
        _real_h = sum(realizados_hoy_por_tarea.get(t["id"], 0) for t in _t)
        # Ambos porcentajes usan el mismo denominador (_plan = total mensual)
        # para que la comparación Esperado vs Real sea sobre la misma base.
        #   Esperado = plan_h / plan  → "qué % del mes debería estar hecho a hoy"
        #   Real     = real_h / plan  → "qué % del mes está realmente hecho a hoy"
        _esp    = (100.0 * _plan_h / _plan) if _plan else 0.0
        _real_p = (100.0 * _real_h / _plan) if _plan else 0.0
        return dict(real_pct=round(_real_p, 1), esp_pct=round(_esp, 1),
                    realizadas=_real, planeadas=_plan, plan_h=_plan_h, real_h=_real_h)

    kpis_freq = {
        "diario":  _kpi_for_freq("diario"),
        "semanal": _kpi_for_freq("semanal"),
        "mensual": _kpi_for_freq("mensual"),
    }

    session["active_page"] = "planilla_mensual"

    def months_to_year_end(y0, m0):
        return [(y0, m) for m in range(m0, 13)]

    def feriados_set(cur, pais, y2, m2):
        dlist = month_days(y2, m2)
        ini2, fin2 = dlist[0].isoformat(), dlist[-1].isoformat()
        rows = cur.execute("""
            SELECT fecha FROM plan_feriados
            WHERE fecha BETWEEN ? AND ? AND (pais = ? OR pais IS NULL)
        """, (ini2, fin2, pais)).fetchall()
        return {(r["fecha"] if hasattr(r, "keys") else r[0]) for r in rows}

    def workdays_count(y2, m2, feriados):
        return sum(1 for d in month_days(y2, m2)
                if d.weekday() not in (5, 6) and d.isoformat() not in feriados)

    def planned_in_month_for_group(y2, m2, tareas_list, dep, resp):
        dias_ = month_days(y2, m2)
        total = 0
        for t in tareas_list:
            if (t.get("depto") or "Sin depto", t.get("responsable") or "—") != (dep, resp):
                continue
            total += sum(1 for d in dias_ if _occurs_this_day(t, d))
        return total

    proj_rows = []
    proj_cols = []
    months_left = months_to_year_end(y, m)

    for (dep, resp), g in grp.items():
        avg_per_wd = (g["real_hoy"] / (wd_elapsed or 1)) if wd_elapsed else 0.0

        row = {"depto": dep, "resp": resp}
        num_real_proj, den_plan_total = 0.0, 0.0

        for yx, mx in months_left:
            key = f"m_{yx}_{mx}"
            label = f"{calendar.month_abbr[mx].capitalize()} %"
            if not any(c["key"] == key for c in proj_cols):
                proj_cols.append({"key": key, "label": label})

            F = feriados_set(cur, pais, yx, mx)
            wd = workdays_count(yx, mx, F)
            plan_mes_x = planned_in_month_for_group(yx, mx, tareas, dep, resp)

            proy_real_x = avg_per_wd * wd
            proy_pct_x  = (100.0 * proy_real_x / plan_mes_x) if plan_mes_x else 0.0

            row[key] = proy_pct_x
            num_real_proj += proy_real_x
            den_plan_total += plan_mes_x

        q_total_pct = (100.0 * num_real_proj / den_plan_total) if den_plan_total else 0.0
        row["q_total_pct"] = q_total_pct

        esperado_pct  = (100.0 * (g["plan_hoy"] or 0) / (g["plan_mes"] or 1)) if g["plan_mes"] else 0.0
        cumpl_hoy_pct = (100.0 * (g["real_hoy"] or 0) / (g["plan_hoy"] or 1)) if g["plan_hoy"] else (100.0 if g["real_hoy"] else 0.0)
        gap_pct_group = cumpl_hoy_pct - esperado_pct

        ATTN_THRESHOLD = 60.0
        WARN_HIGH      = 85.0
        GAP_RED        = -10.0

        first_key = f"m_{months_left[0][0]}_{months_left[0][1]}"
        first_month_pct = row.get(first_key, 100)

        reds = 0
        reds += 1 if gap_pct_group <= GAP_RED else 0
        reds += 1 if (first_month_pct < ATTN_THRESHOLD) else 0
        reds += 1 if (q_total_pct < ATTN_THRESHOLD) else 0

        warns = 0
        warns += 1 if (-10 < gap_pct_group < 0) else 0
        warns += 1 if (ATTN_THRESHOLD <= first_month_pct < WARN_HIGH) else 0
        warns += 1 if (ATTN_THRESHOLD <= q_total_pct < WARN_HIGH) else 0

        if reds >= 2:
            row["estado"], row["estado_level"] = "Requiere atención", "danger"
        elif reds == 1 or warns >= 2:
            row["estado"], row["estado_level"] = "Observación", "warning"
        else:
            row["estado"], row["estado_level"] = "OK", "success"

        proj_rows.append(row)

    proj_rows.sort(key=lambda r: r["q_total_pct"])

    # ── KPIs por Área → OKR → RC → Tareas ───────────────────────────────────
    # Estructura: by_area[area_nombre][okr_key]["rcs"][rc_key]["tareas"]
    by_area = {}
    for t in tareas:
        okr_id  = t.get("okr_id")
        if not okr_id:
            continue
        area_nom = t.get("area_nombre") or "Sin área"
        okr_nom  = t.get("okr_nombre") or "OKR sin nombre"
        okr_key  = (okr_id, okr_nom)
        rc_id    = t.get("resultado_clave_id")
        rc_nom   = t.get("resultado_clave_nombre") or "Sin Resultado Clave"
        rc_key   = (rc_id, rc_nom)
        tid = t["id"]
        tp  = planeadas_por_tarea.get(tid, 0)
        tr  = realizados_por_tarea.get(tid, 0)
        tph = planeadas_hoy_por_tarea.get(tid, 0)
        trh = realizados_hoy_por_tarea.get(tid, 0)

        ag = by_area.setdefault(area_nom, {"plan": 0, "real": 0, "plan_h": 0, "real_h": 0, "okrs": {}, "deptos": set()})
        ag["plan"]   += tp;  ag["real"]   += tr
        ag["plan_h"] += tph; ag["real_h"] += trh
        if t.get("depto"):
            ag["deptos"].add(t["depto"])

        og = ag["okrs"].setdefault(okr_key, {"plan": 0, "real": 0, "plan_h": 0, "real_h": 0, "rcs": {}})
        og["plan"]   += tp;  og["real"]   += tr
        og["plan_h"] += tph; og["real_h"] += trh

        rg = og["rcs"].setdefault(rc_key, {"plan": 0, "real": 0, "plan_h": 0, "real_h": 0, "tareas": []})
        rg["plan"]   += tp;  rg["real"]   += tr
        rg["plan_h"] += tph; rg["real_h"] += trh
        rg["tareas"].append({
            "id": tid,
            "nombre": t.get("nombre") or "",
            "responsable": t.get("responsable") or "",
            "depto": t.get("depto") or "",
            "plan": tp, "real": tr,
            "esp_pct":  round(100.0 * tph / tp, 1) if tp else 0.0,
            "real_pct": round(100.0 * trh / tp, 1) if tp else 0.0,
        })

    def _build_okr_rows(okrs_dict):
        rows = []
        for (oid, onom), og in sorted(okrs_dict.items(), key=lambda x: x[0][1]):
            op = og["plan"] or 0; or_ = og["real"] or 0
            oph = og["plan_h"] or 0; orh = og["real_h"] or 0
            rcs_list = []
            for (rid, rnom), rg in sorted(og["rcs"].items(), key=lambda x: x[0][1] or ""):
                rp = rg["plan"] or 0; rr = rg["real"] or 0
                rph = rg["plan_h"] or 0; rrh = rg["real_h"] or 0
                rcs_list.append({
                    "id": rid, "nombre": rnom,
                    "plan": rp, "real": rr,
                    "esp_pct":  round(100.0 * rph / rp, 1) if rp else 0.0,
                    "real_pct": round(100.0 * rrh / rp, 1) if rp else 0.0,
                    "tareas": rg["tareas"],
                })
            rows.append({
                "id": oid, "nombre": onom,
                "plan": op, "real": or_,
                "esp_pct":  round(100.0 * oph / op, 1) if op else 0.0,
                "real_pct": round(100.0 * orh / op, 1) if op else 0.0,
                "resultados_clave": rcs_list,
            })
        return rows

    area_rows = []
    for area_nom, ag in sorted(by_area.items(), key=lambda x: (x[0] == "Sin área", x[0])):
        ap = ag["plan"] or 0; ar = ag["real"] or 0
        aph = ag["plan_h"] or 0; arh = ag["real_h"] or 0
        area_rows.append({
            "nombre":   area_nom,
            "plan":     ap, "real": ar,
            "esp_pct":  round(100.0 * aph / ap, 1) if ap else 0.0,
            "real_pct": round(100.0 * arh / ap, 1) if ap else 0.0,
            "okrs":     _build_okr_rows(ag["okrs"]),
            "deptos":   sorted(ag["deptos"]),
        })

    # Compatibilidad: okr_rows = lista plana de todos los OKRs (sin agrupación de área)
    okr_rows = []
    for ar_row in area_rows:
        okr_rows.extend(ar_row["okrs"])

    return render_template(
        "planilla/dashboard.html",
        y=y, m=m,
        kpis=kpis,
        kpis_freq=kpis_freq,
        chart=chart,
        top_high=top_high,
        top_low=top_low,
        dept_rows=dept_rows,
        freq=freq,
        areas_list=areas_list,
        departamentos_list=departamentos_list,
        responsables_list=responsables_list,
        responsables_display=responsables_display,
        area_sel=area_sel,
        depto_sel=depto_sel,
        resp_sel=resp_sel,
        prev_y=prev_y, prev_m=prev_m, next_y=next_y, next_m=next_m,
        summary_rows=summary_rows,
        proj_rows=proj_rows,
        proj_cols=proj_cols,
        okr_rows=okr_rows,
        area_rows=area_rows,
    )


@planilla_bp.post("/config/evidence-mode")
def toggle_evidence_mode():
    if not _is_admin():
        abort(403)
    conn = get_db()
    cur = conn.cursor()
    data = request.get_json(force=True) or {}
    enabled = bool(int(data.get("enabled", 0)))

    cur.execute("""
        UPDATE configuracion
        SET valor = ?
        WHERE clave = ?
    """, ("1" if enabled else "0", "planilla_evidence_mode"))

    if cur.rowcount == 0:
        cur.execute("""
            INSERT INTO configuracion(clave, valor)
            VALUES(?, ?)
        """, ("planilla_evidence_mode", "1" if enabled else "0"))

    conn.commit()
    return jsonify(ok=True, enabled=enabled)


# =============== VISTA PRINCIPAL (PLANILLA) ===============
@planilla_bp.route("/", methods=["GET"])
def planilla():
    if not has_perm("Planilla Mensual", "ver"):
        abort(403)

    today = date.today()
    y     = int(request.args.get("year",  today.year))
    m     = int(request.args.get("month", today.month))
    rid   = request.args.get("responsable_id")
    freq  = request.args.get("frecuencia")
    depid = request.args.get("departamento_id")

    conn = get_db(); cur = conn.cursor()

    # si no es admin, ignoramos cualquier filtro rid (solo verá las suyas)
    if not _is_admin():
        rid = None

    responsables  = cur.execute("""
        SELECT u.id, COALESCE(NULLIF(LTRIM(RTRIM(u.nombre_completo)),''), u.username) AS nombre
        FROM usuarios u
        WHERE COALESCE(u.disabled,0)=0
          AND EXISTS (SELECT 1 FROM plan_tareas t WHERE t.usuario_id = u.id AND t.activo=1)
        ORDER BY nombre
    """).fetchall()
    departamentos = cur.execute("SELECT id, nombre FROM departamentos ORDER BY nombre").fetchall()

    sql = [
        "SELECT t.id, t.nombre, t.frecuencia, t.usuario_id, t.activo, t.departamento_id,",
        "       COALESCE(NULLIF(LTRIM(RTRIM(u.nombre_completo)),''), u.username) AS responsable_nombre",
        "FROM plan_tareas t JOIN usuarios u ON u.id = t.usuario_id",
        "WHERE t.activo = 1"
    ]
    params = []
    if rid:   sql.append("AND t.usuario_id = ?");      params.append(int(rid))
    if freq:  sql.append("AND t.frecuencia = ?");      params.append(freq)
    if depid: sql.append("AND t.departamento_id = ?"); params.append(int(depid))

    # filtro por usuario logeado (no admin)
    if not _is_admin():
        sql.append("AND LOWER(u.username) = LOWER(?)")
        params.append(_current_username())

    sql.append("ORDER BY t.departamento_id, u.username, t.nombre")
    tareas = cur.execute(" ".join(sql), params).fetchall()

    dias = month_days(y, m)
    inicio, fin = dias[0], dias[-1]

    task_ids = [t["id"] for t in tareas]
    if not task_ids:
        checks = {}
        evidencias = {}
    else:
        ph_t = ",".join(["?"] * len(task_ids))
        rows = cur.execute(
            f"SELECT tarea_id, fecha, checked FROM plan_checks WHERE fecha BETWEEN ? AND ? AND tarea_id IN ({ph_t})",
            [inicio.isoformat(), fin.isoformat()] + task_ids
        ).fetchall()
        checks = {f"{r['tarea_id']}-{r['fecha']}": bool(r["checked"]) for r in rows}

        evrows = cur.execute(
            f"SELECT tarea_id, fecha, file_name, obs FROM plan_evidencias WHERE fecha BETWEEN ? AND ? AND tarea_id IN ({ph_t})",
            [inicio.isoformat(), fin.isoformat()] + task_ids
        ).fetchall()
        evidencias = {f"{r['tarea_id']}-{r['fecha']}": {"file_name": r["file_name"], "obs": r["obs"]} for r in evrows}

    prev_y, prev_m, next_y, next_m = prev_next(y, m)
    session["active_page"] = "planilla_mensual"

    # ── Tarjetas resumen (solo tareas visibles según filtros) ─────
    today = date.today()

    # Feriados del mes para excluirlos del conteo
    _feriados_rows = cur.execute(
        "SELECT fecha FROM plan_feriados WHERE fecha BETWEEN ? AND ? AND (pais='EC' OR pais IS NULL)",
        (dias[0].isoformat(), dias[-1].isoformat())
    ).fetchall()
    _feriados_set = {(r["fecha"] if hasattr(r, "keys") else r[0]) for r in _feriados_rows}

    def _is_lab(d: date) -> bool:
        """Retorna True si el día es laborable (lunes-viernes y no feriado)."""
        return d.weekday() < 5 and d.isoformat() not in _feriados_set

    _tids_visible = {str(t["id"]) for t in tareas}
    total_act    = len(tareas)
    cumplidas    = sum(1 for k, v in checks.items() if v and k.split("-")[0] in _tids_visible)
    dias_pasados = [d for d in dias if d <= today and _is_lab(d)]
    total_esperadas = len(tareas) * len(dias_pasados)
    pendientes   = max(0, total_esperadas - cumplidas)
    vencidas = 0
    for t in tareas:
        tid = str(t["id"])
        for d in dias_pasados:
            k = f"{tid}-{d.isoformat()}"
            if not checks.get(k):
                vencidas += 1
    evi_pendientes = sum(
        1 for t in tareas
        for d in dias_pasados
        if checks.get(f"{str(t['id'])}-{d.isoformat()}")
        and not evidencias.get(f"{str(t['id'])}-{d.isoformat()}")
    )
    resumen = dict(
        total_act=total_act,
        cumplidas=cumplidas,
        pendientes=pendientes,
        vencidas=vencidas,
        evi_pendientes=evi_pendientes,
    )
    # ─────────────────────────────────────────────────────────────

    is_admin = _is_admin()
    evidence_mode = bool(int(cfg_get(conn, "planilla_evidence_mode", "1") or 0))
    return render_template(
        "planilla/planilla_mensual.html",
        evidence_mode=evidence_mode,
        is_admin=is_admin,
        today_iso=date.today().isoformat(),
        resumen=resumen,
        y=y, m=m, dias=dias, tareas=tareas, checks=checks, evidencias=evidencias,
        responsables=responsables, rid=str(rid or ""), freq=str(freq or ""),
        departamentos=departamentos, depid=str(depid or ""),
        prev_y=prev_y, prev_m=prev_m, next_y=next_y, next_m=next_m
    )



@planilla_bp.post("/check")
def toggle_check():
    if not has_perm("Planilla Mensual", "editar"):
        abort(403)

    data = request.get_json(force=True)
    tarea_id = int(data["tarea_id"])
    fecha    = data["fecha"]
    checked  = bool(data["checked"])

    conn = get_db(); cur = conn.cursor()
    if not _can_access_task(conn, tarea_id):
        abort(403)

    evidence_mode = bool(int(cfg_get(conn, "planilla_evidence_mode", "1") or 0))

    if checked:
        if evidence_mode:
            # Con evidencia obligatoria, el check se hace por /evidencia
            return jsonify(ok=False, error="Use /evidencia para marcar con soporte"), 400
        else:
            # Modo “ligero”: marcar sin pedir archivo ni enviar correo
            cur.execute("""
                UPDATE plan_checks
                SET checked = 1
                WHERE tarea_id = ? AND fecha = ?
            """, (tarea_id, fecha))
            if cur.rowcount == 0:
                cur.execute("""
                    INSERT INTO plan_checks (tarea_id, fecha, checked)
                    VALUES (?, ?, 1)
                """, (tarea_id, fecha))
            conn.commit()
            return jsonify(ok=True)
    else:
        # Desmarcar: borra check + evidencia (si existía)
        cur.execute("DELETE FROM plan_evidencias WHERE tarea_id=? AND fecha=?", (tarea_id, fecha))
        cur.execute("DELETE FROM plan_checks     WHERE tarea_id=? AND fecha=?", (tarea_id, fecha))
        conn.commit()
        return jsonify(ok=True)


@planilla_bp.post("/evidencia")
def evidence_post():
    if not has_perm("Planilla Mensual", "editar"):
        abort(403)

    tarea_id = int(request.form.get("tarea_id"))
    fecha    = request.form.get("fecha")
    obs      = (request.form.get("obs") or "").strip()
    f        = request.files.get("file")

    if not obs:
        return ("La observación es obligatoria.", 400)

    conn = get_db(); cur = conn.cursor()

    # seguridad por tarea
    if not _can_access_task(conn, tarea_id):
        abort(403)

    saved_path = None; fname = None; mime = None
    if f and f.filename:
        if not _allowed(f.filename):
            return ("Extensión no permitida (pdf, png, jpg, jpeg, webp).", 400)
        # Límite de tamaño servidor
        f.seek(0, os.SEEK_END); size = f.tell(); f.seek(0)
        if size > MAX_UPLOAD_MB * 1024 * 1024:
            return (f"Archivo demasiado grande (>{MAX_UPLOAD_MB} MB).", 413)

        fname = secure_filename(f.filename)
        base, ext = os.path.splitext(fname)
        fname = f"{tarea_id}_{fecha}_{base}{ext}"
        full = os.path.join(_uploads_dir(), fname)
        try:
            f.save(full)
        except Exception as e:
            current_app.logger.exception("No se pudo guardar el archivo: %s", e)
            return ("Error guardando el archivo en servidor.", 500)
        saved_path = full; mime = f.mimetype

    # marcar check
    cur.execute("""
        UPDATE plan_checks
        SET checked = 1
        WHERE tarea_id = ? AND fecha = ?
    """, (tarea_id, fecha))
    if cur.rowcount == 0:
        cur.execute("""
            INSERT INTO plan_checks (tarea_id, fecha, checked)
            VALUES (?, ?, 1)
        """, (tarea_id, fecha))

    # upsert evidencia
    cur.execute("""
        UPDATE plan_evidencias
        SET obs = ?,
            file_path = COALESCE(?, file_path),
            file_name = COALESCE(?, file_name),
            mime = COALESCE(?, mime)
        WHERE tarea_id = ? AND fecha = ?
    """, (obs, saved_path, fname, mime, tarea_id, fecha))
    if cur.rowcount == 0:
        cur.execute("""
            INSERT INTO plan_evidencias(tarea_id, fecha, obs, file_path, file_name, mime)
            VALUES (?,?,?,?,?,?)
        """, (tarea_id, fecha, obs, saved_path, fname, mime))
    conn.commit()

    # notificación por correo (no rompe respuesta)
    try:
        to_email, dept_name, resp_name = dept_email_for_tarea(conn, tarea_id)
        if to_email:
            tarea = conn.execute("SELECT nombre FROM plan_tareas WHERE id=?", (tarea_id,)).fetchone()
            tarea_nombre = (tarea["nombre"] if hasattr(tarea, "keys") else tarea[0]) if tarea else f"Tarea {tarea_id}"
            ctx = {
                "tarea": tarea_nombre,
                "fecha": fecha,
                "responsable": resp_name or "",
                "departamento": dept_name or "",
                "observacion": obs or "",
                "app_url": request.url_root.rstrip("/"),
            }
            try:
                subject, html, text = render_mail_template(conn, "evidencia", **ctx)
            except Exception as e:
                current_app.logger.exception("Error renderizando plantilla de correo: %s", e)
                subject = f"Evidencia registrada: {tarea_nombre} ({fecha})"
                html = (
                    f"<p>Se registró evidencia para <strong>{tarea_nombre}</strong> el {fecha}.</p>"
                    f"<p><strong>Departamento:</strong> {ctx['departamento']}<br>"
                    f"<strong>Responsable:</strong> {ctx['responsable']}</p>"
                    f"{f'<p><strong>Observación:</strong><br>{obs}</p>' if obs else ''}"
                )
                text = None
            attachments = [saved_path] if saved_path else []
            try:
                send_mail(conn, to_email, subject, html, text=text, attachments=attachments)
            except Exception as e:
                current_app.logger.exception("Error enviando correo evidencia: %s", e)
    except Exception as e:
        current_app.logger.exception("Error en bloque de notificación: %s", e)

    return jsonify(ok=True)

@planilla_bp.get("/evidencia/<int:tarea_id>/<fecha>")
def evidence_get(tarea_id: int, fecha: str):
    if not has_perm("Planilla Mensual", "ver"):
        abort(403)
    conn = get_db(); cur = conn.cursor()

    if not _can_access_task(conn, tarea_id):
        abort(403)

    row = cur.execute("""
        SELECT obs, file_path, file_name, mime
        FROM plan_evidencias WHERE tarea_id=? AND fecha=?
    """, (tarea_id, fecha)).fetchone()
    if not row:
        abort(404)
    fpath = row["file_path"] if hasattr(row, "keys") else row[1]
    if fpath and os.path.exists(fpath):
        return send_file(
            fpath,
            mimetype=(row["mime"] if hasattr(row, "keys") else row[3]) or None,
            as_attachment=False,
            download_name=(row["file_name"] if hasattr(row, "keys") else row[2])
        )
    obs = row["obs"] if hasattr(row, "keys") else row[0]
    return f"<pre style='padding:12px;font-family:monospace'>{(obs or 'Sin observación.')}</pre>"

@planilla_bp.get("/evidencia/meta/<int:tarea_id>/<fecha>")
def evidence_meta(tarea_id: int, fecha: str):
    if not has_perm("Planilla Mensual", "ver"):
        abort(403)
    conn = get_db()

    if not _can_access_task(conn, tarea_id):
        abort(403)

    row = conn.execute("""
        SELECT obs, file_name, CASE WHEN file_path IS NOT NULL THEN 1 ELSE 0 END AS has_file
        FROM plan_evidencias WHERE tarea_id=? AND fecha=?
    """, (tarea_id, fecha)).fetchone()
    exists = bool(row)
    return jsonify({
        "exists": exists,
        "obs": (row["obs"] if exists else ""),
        "file_name": (row["file_name"] if exists else ""),
        "url": url_for("planilla_mensual.evidence_get", tarea_id=tarea_id, fecha=fecha) if exists else None
    })


# =============== CRUD TAREAS ===============
@planilla_bp.route("/tareas", methods=["GET"])
def tareas_list():
    if not has_perm("Planilla Mensual", "ver"):
        abort(403)
    conn = get_db(); cur = conn.cursor()

    base = [
        "SELECT t.id, t.nombre, t.frecuencia, t.activo,",
        "       COALESCE(NULLIF(LTRIM(RTRIM(u.nombre_completo)),''), u.username) AS responsable,",
        "       d.nombre AS departamento",
        "FROM plan_tareas t",
        "JOIN usuarios u ON u.id = t.usuario_id",
        "LEFT JOIN departamentos d ON d.id = t.departamento_id",
        "WHERE 1=1"
    ]
    params = []
    if not _is_admin():
        base.append("AND LOWER(u.username) = LOWER(?)")
        params.append(_current_username())

    base.append("ORDER BY d.nombre, u.username, t.nombre")
    tareas = cur.execute(" ".join(base), params).fetchall()

    session["active_page"] = "planilla_mensual"
    return render_template("planilla/tarea_list.html", tareas=tareas)

@planilla_bp.route("/tareas/nueva", methods=["GET", "POST"])
def tareas_new():
    conn = get_db(); cur = conn.cursor()
    if request.method == "GET":
        if not has_perm("Planilla Mensual", "crear"):
            abort(403)
        responsables = cur.execute("""
            SELECT id, COALESCE(NULLIF(LTRIM(RTRIM(nombre_completo)),''), username) AS nombre
            FROM usuarios WHERE COALESCE(disabled,0)=0 ORDER BY nombre_completo, username
        """).fetchall()
        departamentos = cur.execute("SELECT id, nombre FROM departamentos ORDER BY nombre").fetchall()
        okrs = cur.execute("SELECT id, nombre FROM plan_okrs WHERE activo=1 ORDER BY nombre").fetchall()
        return render_template(
            "planilla/tarea_form.html",
            modo="nuevo", responsables=responsables,
            departamentos=departamentos, frecuencias=FRECUENCIAS, tarea=None,
            okrs=okrs, resultados_clave=[]
        )

    if not has_perm("Planilla Mensual", "crear"):
        abort(403)

    nombre              = (request.form.get("nombre") or "").strip()
    frecuencia          = (request.form.get("frecuencia") or "").strip()
    departamento_id     = request.form.get("departamento_id")
    responsable_user_id = request.form.get("responsable_user_id")
    nuevo_resp          = (request.form.get("nuevo_responsable") or "").strip()
    activo              = 1 if request.form.get("activo") == "on" else 0

    # NUEVO: días (según frecuencia)
    dia_semana = request.form.get("dia_semana")
    dia_mes    = request.form.get("dia_mes")
    if frecuencia == "Semanal":
        dia_semana = int(dia_semana) if dia_semana not in (None, "",) else None
        dia_mes = None
    elif frecuencia == "Mensual":
        dia_mes = int(dia_mes) if dia_mes not in (None, "",) else None
        dia_semana = None
    else:
        dia_semana = None
        dia_mes = None


    if not nombre or frecuencia not in FRECUENCIAS:
        return "Datos inválidos", 400

    # Mapear directo a usuarios.id
    if not responsable_user_id:
        return "Seleccione responsable.", 400
    row_u = cur.execute("SELECT id FROM usuarios WHERE id=? AND COALESCE(disabled,0)=0",
                        (int(responsable_user_id),)).fetchone()
    if not row_u:
        return "Usuario responsable inválido", 400

    okr_id            = request.form.get("okr_id")
    resultado_clave_id = request.form.get("resultado_clave_id")
    okr_id            = int(okr_id) if okr_id and str(okr_id).isdigit() else None
    resultado_clave_id = int(resultado_clave_id) if resultado_clave_id and str(resultado_clave_id).isdigit() else None

    cur.execute("""
    INSERT INTO plan_tareas(nombre, frecuencia, usuario_id, departamento_id, activo, dia_semana, dia_mes, okr_id, resultado_clave_id)
    VALUES (?,?,?,?,?,?,?,?,?)
    """, (nombre, frecuencia, int(responsable_user_id),
        (int(departamento_id) if departamento_id else None), activo,
        dia_semana, dia_mes, okr_id, resultado_clave_id))

    conn.commit()
    return redirect(url_for("planilla_mensual.tareas_list"))

@planilla_bp.route("/tareas/<int:tid>/editar", methods=["GET", "POST"])
def tareas_edit(tid: int):
    conn = get_db(); cur = conn.cursor()

    if request.method == "GET":
        if not has_perm("Planilla Mensual", "editar"):
            abort(403)

        tarea = cur.execute("SELECT * FROM plan_tareas WHERE id=?", (tid,)).fetchone()
        if not tarea:
            abort(404)

        responsables  = cur.execute("""
            SELECT id, COALESCE(NULLIF(LTRIM(RTRIM(nombre_completo)),''), username) AS nombre
            FROM usuarios WHERE COALESCE(disabled,0)=0 ORDER BY nombre_completo, username
        """).fetchall()
        departamentos = cur.execute("SELECT id, nombre FROM departamentos ORDER BY nombre").fetchall()

        dep_id = tarea["departamento_id"] if hasattr(tarea, "keys") else tarea[4]

        dept_users = []
        if dep_id:
            dept_users = cur.execute("""
                SELECT id, username, email
                FROM usuarios
                WHERE departamento_id=? AND COALESCE(disabled,0)=0
                ORDER BY username
            """, (dep_id,)).fetchall()

        # usuario_id ya está directo en la tarea
        selected_user_id = tarea["usuario_id"] if hasattr(tarea, "keys") else None

        okrs = cur.execute("SELECT id, nombre FROM plan_okrs WHERE activo=1 ORDER BY nombre").fetchall()
        tarea_okr_id = tarea["okr_id"] if hasattr(tarea, "keys") else None
        resultados_clave = []
        if tarea_okr_id:
            resultados_clave = cur.execute(
                "SELECT id, nombre FROM plan_resultados_clave WHERE okr_id=? AND activo=1 ORDER BY nombre",
                (tarea_okr_id,)
            ).fetchall()

        return render_template(
            "planilla/tarea_form.html",
            modo="editar",
            responsables=responsables,
            departamentos=departamentos,
            frecuencias=FRECUENCIAS,
            tarea=tarea,
            dept_users=dept_users,
            selected_user_id=selected_user_id,
            okrs=okrs,
            resultados_clave=resultados_clave
        )

    if not has_perm("Planilla Mensual", "editar"):
        abort(403)

    nombre              = (request.form.get("nombre") or "").strip()
    frecuencia          = (request.form.get("frecuencia") or "").strip()
    departamento_id     = request.form.get("departamento_id")
    responsable_user_id = request.form.get("responsable_user_id")
    nuevo_resp          = (request.form.get("nuevo_responsable") or "").strip()
    activo              = 1 if request.form.get("activo") == "on" else 0


    dia_semana = request.form.get("dia_semana")
    dia_mes    = request.form.get("dia_mes")
    if frecuencia == "Semanal":
        dia_semana = int(dia_semana) if dia_semana not in (None, "",) else None
        dia_mes = None
    elif frecuencia == "Mensual":
        dia_mes = int(dia_mes) if dia_mes not in (None, "",) else None
        dia_semana = None
    else:
        dia_semana = None
        dia_mes = None

    if not nombre or frecuencia not in FRECUENCIAS:
        return "Datos inválidos", 400

    # Usar usuario_id directamente
    if responsable_user_id:
        uid = int(responsable_user_id)
    else:
        row_old = cur.execute("SELECT usuario_id FROM plan_tareas WHERE id=?", (tid,)).fetchone()
        if not row_old:
            return "Seleccione responsable.", 400
        uid = row_old["usuario_id"] if hasattr(row_old, "keys") else row_old[0]

    okr_id            = request.form.get("okr_id")
    resultado_clave_id = request.form.get("resultado_clave_id")
    okr_id            = int(okr_id) if okr_id and str(okr_id).isdigit() else None
    resultado_clave_id = int(resultado_clave_id) if resultado_clave_id and str(resultado_clave_id).isdigit() else None

    cur.execute("""
    UPDATE plan_tareas
       SET nombre=?, frecuencia=?, usuario_id=?, departamento_id=?, activo=?, dia_semana=?, dia_mes=?,
           okr_id=?, resultado_clave_id=?
     WHERE id=?
    """, (nombre, frecuencia, uid,
      (int(departamento_id) if departamento_id else None), activo,
      dia_semana, dia_mes, okr_id, resultado_clave_id, tid))

    conn.commit()
    return redirect(url_for("planilla_mensual.tareas_list"))

@planilla_bp.route("/tareas/<int:tid>/eliminar", methods=["POST"])
def tareas_delete(tid: int):
    if not has_perm("Planilla Mensual", "eliminar"):
        abort(403)
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM plan_evidencias WHERE tarea_id=?", (tid,))
    cur.execute("DELETE FROM plan_checks WHERE tarea_id=?", (tid,))
    cur.execute("DELETE FROM plan_tareas WHERE id=?", (tid,))
    conn.commit()
    return redirect(url_for("planilla_mensual.tareas_list"))


# =============== CONFIGURACIÓN ===============
@planilla_bp.route("/config/plantilla", methods=["GET", "POST"])
def mail_template():
    if not has_perm("Planilla Mensual", "editar"):
        abort(403)

    conn = get_db()

    if request.method == "GET":
        row = conn.execute("""
            SELECT subject, html, text
            FROM plan_mail_templates
            WHERE [key] = ?
        """, ("evidencia",)).fetchone()

        return render_template("planilla/mail_template_form.html", tpl=row)

    # POST
    subject = (request.form.get("subject") or "").strip()
    html    = (request.form.get("html") or "").strip()
    text    = (request.form.get("text") or "").strip()

    if not subject or not html:
        return "Completa asunto y cuerpo HTML", 400

    cur = conn.cursor()

    cur.execute("""
        UPDATE plan_mail_templates
        SET subject = ?, html = ?, text = ?
        WHERE [key] = ?
    """, (subject, html, (text or None), "evidencia"))

    if cur.rowcount == 0:
        cur.execute("""
            INSERT INTO plan_mail_templates([key], subject, html, text)
            VALUES (?, ?, ?, ?)
        """, ("evidencia", subject, html, (text or None)))

    conn.commit()
    return redirect(url_for("planilla_mensual.mail_template"))
# API: usuarios por departamento (para combo dependiente)
@planilla_bp.get("/api/usuarios/by-dep/<int:depid>")
def api_usuarios_by_dep(depid: int):
    """Devuelve usuarios activos del departamento dado."""
    if not has_perm("Planilla Mensual", "crear") and not has_perm("Planilla Mensual", "editar"):
        abort(403)
    conn = get_db()
    rows = conn.execute("""
        SELECT id, username, email
        FROM usuarios
        WHERE departamento_id = ? AND COALESCE(disabled,0) = 0
        ORDER BY username
    """, (depid,)).fetchall()
    out = [dict(id=r["id"], username=r["username"], email=r["email"]) for r in rows]
    return jsonify(out)

# Configuración: correo por departamento
@planilla_bp.route("/config/departamento", methods=["GET", "POST"])
def dept_cfg():
    session["active_page"] = "planilla_mensual"
    if not has_perm("Planilla Mensual", "editar"):
        abort(403)
    conn = get_db(); cur = conn.cursor()
    if request.method == "GET":
        deps = cur.execute("SELECT id, nombre FROM departamentos ORDER BY nombre").fetchall()
        users = cur.execute("SELECT id, username, email FROM usuarios ORDER BY username").fetchall()
        rows = cur.execute("""
            SELECT d.id as departamento_id, d.nombre as depto, c.notify_user_id, c.notify_email
            FROM departamentos d
            LEFT JOIN plan_dept_config c ON c.departamento_id = d.id
            ORDER BY d.nombre
        """).fetchall()
        return render_template("planilla/dept_config.html", deps=deps, users=users, rows=rows)
    # POST (guardar una fila)
    depid   = int(request.form.get("departamento_id"))
    user_id = request.form.get("notify_user_id") or None
    email   = (request.form.get("notify_email") or "").strip() or None
    cur.execute("""
        UPDATE plan_dept_config
        SET notify_user_id = ?, notify_email = ?
        WHERE departamento_id = ?
    """, ((int(user_id) if user_id else None), email, depid))
    if cur.rowcount == 0:
        cur.execute("""
            INSERT INTO plan_dept_config(departamento_id, notify_user_id, notify_email)
            VALUES (?,?,?)
        """, (depid, (int(user_id) if user_id else None), email))
    conn.commit()
    return redirect(url_for("planilla_mensual.dept_cfg"))

from flask import jsonify

def _require_admin():
    role = (session.get("rol") or "").lower()
    is_admin = (role == "admin" or bool(session.get("is_admin")))
    if not is_admin:
        abort(403)

@planilla_bp.get("/api/feriados")
def api_list_feriados():
    _require_admin()

    # Tomamos solo el año del query string
    y = int(request.args.get("year"))

    ini = f"{y}-01-01"
    fin = f"{y}-12-31"

    conn = get_db()
    cur = conn.cursor()

    rows = cur.execute("""
        SELECT id,
               fecha,
               COALESCE(nombre, '') AS nombre,
               COALESCE(pais,   '') AS pais
        FROM plan_feriados
        WHERE fecha BETWEEN ? AND ?
        ORDER BY fecha
    """, (ini, fin)).fetchall()

    out = [{"id": r[0], "fecha": r[1], "nombre": r[2], "pais": r[3]} for r in rows]
    return jsonify(out)


@planilla_bp.post("/api/feriados")
def api_add_feriado():
    _require_admin()
    data = request.get_json(force=True) or {}
    fecha = (data.get("fecha") or "").strip()
    nombre = (data.get("nombre") or "").strip() or None
    pais = (data.get("pais") or "EC").strip() or None
    # Validación simple
    try:
        _ = date.fromisoformat(fecha)
    except Exception:
        return jsonify({"ok": False, "error": "Fecha inválida"}), 400

    conn = get_db();  cur = conn.cursor()
    try:
        exists = cur.execute("""
            SELECT TOP 1 1 AS ok
            FROM plan_feriados
            WHERE fecha = ? AND COALESCE(pais, 'EC') = COALESCE(?, 'EC')
        """, (fecha, pais)).fetchone()
        if not exists:
            cur.execute("INSERT INTO plan_feriados (fecha, nombre, pais) VALUES (?,?,?)",
                        (fecha, nombre, pais))
        conn.commit()
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    return jsonify({"ok": True})

@planilla_bp.delete("/api/feriados/<int:fid>")
def api_delete_feriado(fid):
    _require_admin()
    conn = get_db(); cur = conn.cursor()
    cur.execute("DELETE FROM plan_feriados WHERE id=?", (fid,))
    conn.commit()
    return jsonify({"ok": True})


@planilla_bp.post("/admin/send-weekly-report")
def admin_send_weekly_report():
    """
    Envío manual del reporte semanal de planilla.
    Solo accesible para administradores.
    El CSRF lo valida Flask-WTF automáticamente vía el header X-CSRFToken
    que el JS del template envía.
    """
    if not _is_admin():
        return jsonify(ok=False, error="Sin permisos"), 403

    try:
        from modules.scheduler.scheduler_planilla_weekly import send_planilla_weekly_report
        result = send_planilla_weekly_report(force=True)   # force=True → ignora si es viernes
        return jsonify(ok=True, result=result)
    except Exception as exc:
        current_app.logger.exception("[PLANILLA_WEEKLY] admin_send_weekly_report falló")
        return jsonify(ok=False, error=str(exc)), 500


# =============== API OKR / RESULTADOS CLAVE ===============

@planilla_bp.route("/api/okrs", methods=["GET"])
def api_okrs_list():
    if not has_perm("Planilla Mensual", "ver"):
        abort(403)
    conn = get_db()
    rows = conn.execute(
        "SELECT id, nombre FROM plan_okrs WHERE activo=1 ORDER BY nombre"
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@planilla_bp.route("/api/okrs", methods=["POST"])
def api_okrs_create():
    if not has_perm("Planilla Mensual", "crear"):
        abort(403)
    nombre = (request.get_json(silent=True) or {}).get("nombre", "").strip()
    if not nombre:
        return jsonify(ok=False, msg="Nombre requerido"), 400
    conn = get_db()
    cur  = conn.cursor()
    cur.execute(
        "INSERT INTO plan_okrs(nombre, activo) OUTPUT inserted.id VALUES(?, 1)",
        (nombre,)
    )
    row = cur.fetchone()
    conn.commit()
    new_id = row[0] if row else None
    return jsonify(ok=True, id=new_id, nombre=nombre)


@planilla_bp.route("/api/okrs/<int:okr_id>/resultados-clave", methods=["GET"])
def api_resultados_clave_list(okr_id: int):
    if not has_perm("Planilla Mensual", "ver"):
        abort(403)
    conn = get_db()
    rows = conn.execute(
        "SELECT id, nombre FROM plan_resultados_clave WHERE okr_id=? AND activo=1 ORDER BY nombre",
        (okr_id,)
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@planilla_bp.route("/api/resultados-clave", methods=["POST"])
def api_resultados_clave_create():
    if not has_perm("Planilla Mensual", "crear"):
        abort(403)
    data    = request.get_json(silent=True) or {}
    nombre  = data.get("nombre", "").strip()
    okr_id  = data.get("okr_id")
    if not nombre or not okr_id:
        return jsonify(ok=False, msg="nombre y okr_id requeridos"), 400
    conn = get_db()
    cur  = conn.cursor()
    cur.execute(
        "INSERT INTO plan_resultados_clave(okr_id, nombre, activo) OUTPUT inserted.id VALUES(?,?,1)",
        (int(okr_id), nombre)
    )
    row = cur.fetchone()
    conn.commit()
    new_id = row[0] if row else None
    return jsonify(ok=True, id=new_id, nombre=nombre, okr_id=okr_id)


# =============== REGISTRO DEL BLUEPRINT ===============
def register_planilla_mensual_routes(app):
    app.register_blueprint(planilla_bp)
