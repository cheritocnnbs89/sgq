# modules/planificador/routes_planificador.py
# -*- coding: utf-8 -*-

import csv
import io
import urllib.request
import urllib.parse
from datetime import date, datetime, timedelta
from io import BytesIO

from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, session, abort, jsonify,
)

from modules.auth.routes_auth import require_login, require_permission
from . import planificador_repository as repo
from . import planificador_services as svc
from . import planificador_notifications as notif
from .planificador_constants import (
    ACTIVE_KEY, PERM_SOLICITUDES, PERM_CONFIG,
    ESTADOS, PRIORIDADES,
    ROL_COORDINADOR, ROL_APROBADOR, ROL_MOTORIZADO,
    ESTADOS_RESERVADAS, ESTADOS_COORDINADAS, ESTADOS_ATENDIDAS,
)
from flask import Response

planificador_bp = Blueprint("planificador", __name__, url_prefix="/planificador")


def _current_user():
    return {
        "id":     session.get("usuario_id"),
        "nombre": session.get("usuario", ""),
        "rol":    session.get("rol", "usuario"),
    }


# ─────────────────────────────────────────────────────────────
# Pantalla principal: Solicitudes
# ─────────────────────────────────────────────────────────────

@planificador_bp.route("/solicitudes", endpoint="planificador_solicitudes")
@require_login
@require_permission(PERM_SOLICITUDES, "ver")
def solicitudes():
    u = _current_user()
    ctx = svc.get_user_context(u["id"], u["rol"])
    tipos_solicitud = repo.get_tipos_solicitud()

    filters = {
        "estado":      request.args.get("estado", ""),
        "tipo":        request.args.get("tipo", ""),
        "area":        request.args.get("area", ""),
        "fecha_desde": request.args.get("fecha_desde", ""),
        "fecha_hasta": request.args.get("fecha_hasta", ""),
    }

    solicitudes_list = svc.get_solicitudes_for_user(u["id"], u["rol"], filters)
    departamentos    = repo.get_departamentos()
    usuario_dept     = repo.get_usuario_departamento(u["id"])

    # Enriquecer cada fila con banderas de acciones
    rows = []
    for s in solicitudes_list:
        d = dict(s)
        d["puede_coordinar"]       = svc.puede_coordinar(s, u["id"], ctx)
        d["puede_aprobar"]         = svc.puede_aprobar(s, u["id"], ctx)
        d["puede_aprobar_gerente"] = svc.puede_aprobar_gerente(s, u["id"], ctx)
        d["puede_completar"]       = svc.puede_completar(s, u["id"], ctx)
        d["puede_reagendar"]       = svc.puede_reagendar(s, u["id"], ctx)
        d["puede_eliminar"]        = svc.puede_eliminar(s, u["id"], ctx)
        d["estado_label"]    = svc.estado_label(s["estado"])
        d["estado_class"]    = svc.estado_badge_class(s["estado"])
        d["fecha_str"]       = str(s["fecha"]) if s["fecha"] else ""
        rows.append(d)

    # Dividir en secciones
    reservadas, coordinadas, atendidas = svc.agrupar_por_seccion(rows)

    # Datos de calendario: semana actual ±2 semanas
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    cal_desde = week_start - timedelta(weeks=4)
    cal_hasta = week_start + timedelta(weeks=8)
    cal_rows = repo.get_calendar_solicitudes(str(cal_desde), str(cal_hasta))

    puede_ver_detalle = svc.puede_ver_detalle_completo(ctx)

    cal_events = []
    for c in cal_rows:
        ev = {
            "id":     c["id"],
            "tipo":   c["tipo"],
            "fecha":  str(c["fecha"]) if c["fecha"] else "",
            "hi":     c["hora_inicio"] or "",
            "hf":     c["hora_fin"] or "",
            "estado": c["estado"],
        }
        if puede_ver_detalle:
            ev["area"]         = c["area_solicitante"]
            ev["descripcion"]  = c["descripcion"]
            ev["lugar"]        = c["lugar_destino"]
            ev["solicitante"]  = c["solicitante_nombre"]
        else:
            ev["area"]        = "Ocupado"
            ev["descripcion"] = ""
            ev["lugar"]       = ""
            ev["solicitante"] = ""
        cal_events.append(ev)

    return render_template(
        "planificador/solicitudes.html",
        active_page=ACTIVE_KEY,
        rows=rows,
        reservadas=reservadas,
        coordinadas=coordinadas,
        atendidas=atendidas,
        filters=filters,
        tipos=tipos_solicitud,
        estados=ESTADOS,
        prioridades=PRIORIDADES,
        ctx=ctx,
        puede_ver_detalle=puede_ver_detalle,
        cal_events=cal_events,
        today=str(today),
        departamentos=departamentos,
        usuario_dept=usuario_dept,
    )


# ─────────────────────────────────────────────────────────────
# AJAX: Detalle de solicitud
# ─────────────────────────────────────────────────────────────

@planificador_bp.route("/solicitudes/<int:sid>/detalle", endpoint="planificador_detalle")
@require_login
def detalle(sid):
    u = _current_user()
    ctx = svc.get_user_context(u["id"], u["rol"])
    s = repo.get_solicitud_by_id(sid)
    if not s:
        abort(404)

    # Solo puede ver detalle completo quien tenga acceso
    if not svc.puede_ver_detalle_completo(ctx) and s["solicitante_id"] != u["id"]:
        abort(403)

    d = dict(s)
    d["puede_coordinar"]       = svc.puede_coordinar(s, u["id"], ctx)
    d["puede_aprobar"]         = svc.puede_aprobar(s, u["id"], ctx)
    d["puede_aprobar_gerente"] = svc.puede_aprobar_gerente(s, u["id"], ctx)
    d["puede_completar"]       = svc.puede_completar(s, u["id"], ctx)
    d["puede_reagendar"]       = svc.puede_reagendar(s, u["id"], ctx)
    d["puede_eliminar"]        = svc.puede_eliminar(s, u["id"], ctx)
    d["estado_label"]    = svc.estado_label(s["estado"])
    d["estado_class"]    = svc.estado_badge_class(s["estado"])
    d["fecha_str"]       = str(s["fecha"]) if s["fecha"] else ""
    logs = repo.get_solicitud_logs(sid)

    grupo_solicitudes = []
    if d.get("grupo_id"):
        todas = repo.get_solicitudes_del_grupo(d["grupo_id"])
        grupo_solicitudes = [dict(g) for g in todas if g["id"] != sid]

    return render_template(
        "planificador/_detalle_modal_body.html",
        s=d,
        logs=logs,
        grupo_solicitudes=grupo_solicitudes,
        active_page=ACTIVE_KEY,
        today_iso=date.today().isoformat(),
    )


# ─────────────────────────────────────────────────────────────
# POST: Crear solicitud
# ─────────────────────────────────────────────────────────────

@planificador_bp.route("/solicitudes/crear", methods=["POST"], endpoint="planificador_crear")
@require_login
@require_permission(PERM_SOLICITUDES, "crear")
def crear():
    u = _current_user()
    tipo  = request.form.get("tipo", "").strip()
    area  = request.form.get("area_solicitante", "").strip()
    desc  = request.form.get("descripcion", "").strip()
    lugar = request.form.get("lugar_destino", "").strip()
    fecha = request.form.get("fecha", "").strip()

    if not all([tipo, area, desc, lugar, fecha]):
        flash("Todos los campos obligatorios deben completarse.", "warning")
        return redirect(url_for("planificador.planificador_solicitudes"))
    if tipo not in repo.get_tipos_solicitud():
        flash("Tipo de solicitud no válido.", "warning")
        return redirect(url_for("planificador.planificador_solicitudes"))

    ppto_raw = request.form.get("presupuesto_base_cero", "").strip()
    ppto     = None
    if tipo == "Vuelo":
        if not ppto_raw:
            flash("El Presupuesto Base Cero es obligatorio para solicitudes de tipo Vuelo.", "warning")
            return redirect(url_for("planificador.planificador_solicitudes"))
        try:
            ppto = float(ppto_raw)
            if ppto < 0:
                raise ValueError
        except ValueError:
            flash("El Presupuesto Base Cero debe ser un número positivo.", "warning")
            return redirect(url_for("planificador.planificador_solicitudes"))

    ciudad = repo.get_ciudad_usuario(u["id"])
    sid = repo.crear_solicitud({
        "tipo":                  tipo,
        "area_solicitante":      area,
        "descripcion":           desc,
        "lugar_destino":         lugar,
        "detalle_direccion":     request.form.get("detalle_direccion", "").strip(),
        "contacto":              request.form.get("contacto", "").strip(),
        "prioridad":             request.form.get("prioridad", "Normal"),
        "fecha":                 fecha,
        "solicitante_id":        u["id"],
        "solicitante_nombre":    u["nombre"],
        "ciudad":                ciudad,
        "presupuesto_base_cero": ppto,
    })
    try:
        notif.notif_nueva_solicitud(sid, tipo, area, fecha, u["nombre"])
    except Exception:
        pass

    # Notificar al gerente del solicitante cuando el tipo es Vuelo
    if tipo == "Vuelo":
        try:
            gerente = repo.get_gerente_del_usuario(u["id"])
            if gerente:
                ppto_str = f"${ppto:,.2f}" if ppto is not None else "—"
                notif.notif_vuelo_nueva_gerente(
                    sid, area, fecha, desc, ppto_str,
                    u["nombre"], gerente["id"], gerente["nombre"],
                )
        except Exception:
            pass

    flash("Solicitud creada. Queda pendiente de coordinación.", "success")
    return redirect(url_for("planificador.planificador_solicitudes"))


# ─────────────────────────────────────────────────────────────
# AJAX: Otras solicitudes pendientes del mismo tipo (para agrupar)
# ─────────────────────────────────────────────────────────────

@planificador_bp.route("/solicitudes/<int:sid>/pendientes-mismo-tipo",
                        endpoint="planificador_pendientes_mismo_tipo")
@require_login
def pendientes_mismo_tipo(sid):
    u = _current_user()
    ctx = svc.get_user_context(u["id"], u["rol"])
    s = repo.get_solicitud_by_id(sid)
    if not s or not svc.puede_coordinar(s, u["id"], ctx):
        return jsonify([])
    otros = repo.get_solicitudes_pendientes_mismo_tipo(s["tipo"], sid)
    return jsonify([{
        "id":          r["id"],
        "area":        r["area_solicitante"] or "",
        "lugar":       r["lugar_destino"] or "",
        "fecha":       str(r["fecha"]) if r["fecha"] else "",
        "solicitante": r["solicitante_nombre"] or "",
        "descripcion": (r["descripcion"] or "")[:80],
    } for r in otros])


# ─────────────────────────────────────────────────────────────
# POST: Coordinar
# ─────────────────────────────────────────────────────────────

@planificador_bp.route("/solicitudes/<int:sid>/coordinar", methods=["POST"],
                       endpoint="planificador_coordinar")
@require_login
def coordinar(sid):
    u = _current_user()
    ctx = svc.get_user_context(u["id"], u["rol"])
    s = repo.get_solicitud_by_id(sid)
    if not s or not svc.puede_coordinar(s, u["id"], ctx):
        abort(403)

    hi  = request.form.get("hora_inicio", "").strip()
    hf  = request.form.get("hora_fin", "").strip()
    obs = request.form.get("observacion_coordinador", "").strip()

    if not hi or not hf:
        flash("Debe asignar hora de inicio y hora fin.", "warning")
        return redirect(url_for("planificador.planificador_solicitudes"))

    # Fecha pasada → no se puede coordinar, solo reagendar
    if s["fecha"] and str(s["fecha"])[:10] < str(date.today()):
        flash(
            "La fecha de esta solicitud ya pasó. Use la opción 'Reagendar' "
            "para asignarle una nueva fecha antes de coordinar.",
            "warning"
        )
        return redirect(url_for("planificador.planificador_solicitudes"))

    if hf <= hi:
        flash("La hora fin debe ser mayor que la hora de inicio.", "warning")
        return redirect(url_for("planificador.planificador_solicitudes"))

    # Horario laboral: 08:00 – 17:00
    if hi < "08:00" or hf > "17:00":
        flash("El horario debe estar dentro del rango laboral: 08:00 – 17:00.", "warning")
        return redirect(url_for("planificador.planificador_solicitudes"))

    # Si la fecha es hoy y la hora actual ya pasó las 17:00, no se puede planificar para hoy
    today = date.today()
    if str(s["fecha"]) == str(today) and datetime.now().hour >= 17:
        flash(
            "Ya pasaron las 17:00. No se puede planificar para hoy. "
            "Cambia la fecha de la solicitud al siguiente día hábil.",
            "warning"
        )
        return redirect(url_for("planificador.planificador_solicitudes"))

    # Validar que no haya otro registro del MISMO tipo en ese horario
    if repo.check_horario_ocupado(s["tipo"], str(s["fecha"]), hi, hf, exclude_id=sid):
        flash(
            f"Ya existe una solicitud de tipo «{s['tipo']}» planificada en ese horario. "
            "Elija otro horario o cancele la solicitud existente.",
            "warning"
        )
        return redirect(url_for("planificador.planificador_solicitudes"))

    # ¿Se agrupan otras solicitudes del mismo tipo?
    grupo_ids_raw = request.form.getlist("grupo_ids")
    grupo_ids = []
    for gid_str in grupo_ids_raw:
        try:
            gid = int(gid_str)
            gs = repo.get_solicitud_by_id(gid)
            if gs and gs["tipo"] == s["tipo"] and gs["estado"] == "PENDIENTE_COORDINACION":
                grupo_ids.append(gid)
        except (ValueError, TypeError):
            pass

    if grupo_ids:
        all_ids = [sid] + grupo_ids
        grupo_id = repo.crear_grupo_coordinacion(
            s["tipo"], str(s["fecha"]), hi, hf, u["id"], u["nombre"], obs
        )
        repo.coordinar_solicitudes_grupo(all_ids, grupo_id, u["id"], u["nombre"], hi, hf, obs)
        for gid in all_ids:
            gs = repo.get_solicitud_by_id(gid)
            if gs:
                try:
                    notif.notif_coordinada(gid, gs["tipo"], gs["area_solicitante"],
                                           str(gs["fecha"]), hi, hf, u["nombre"])
                except Exception:
                    pass
        flash(
            f"Se coordinaron {len(all_ids)} solicitudes juntas "
            f"en el horario {hi} – {hf}.",
            "success"
        )
    else:
        repo.coordinar_solicitud(sid, u["id"], u["nombre"], hi, hf, obs)
        try:
            notif.notif_coordinada(sid, s["tipo"], s["area_solicitante"],
                                   str(s["fecha"]), hi, hf, u["nombre"])
        except Exception:
            pass
        flash("Solicitud enviada a aprobación.", "success")
    return redirect(url_for("planificador.planificador_solicitudes"))


# ─────────────────────────────────────────────────────────────
# POST: Aprobar
# ─────────────────────────────────────────────────────────────

@planificador_bp.route("/solicitudes/<int:sid>/aprobar", methods=["POST"],
                       endpoint="planificador_aprobar")
@require_login
def aprobar(sid):
    u = _current_user()
    ctx = svc.get_user_context(u["id"], u["rol"])
    s = repo.get_solicitud_by_id(sid)
    if not s or not svc.puede_aprobar(s, u["id"], ctx):
        abort(403)

    obs = request.form.get("observacion_aprobador", "").strip()
    repo.aprobar_solicitud(sid, u["id"], u["nombre"], obs)

    # ¿Requiere aprobación gerencial?
    flags = repo.get_tipo_flags(s["tipo"])
    if flags.get("requiere_aprobacion_gerente"):
        gerente = repo.get_gerente_del_usuario(s["solicitante_id"])
        if gerente:
            repo.poner_pendiente_gerente(sid, gerente["id"], gerente["nombre"])
            try:
                notif.notif_pendiente_gerente(
                    sid, s["tipo"], s["area_solicitante"],
                    str(s["fecha"]), s["hora_inicio"] or "", s["hora_fin"] or "",
                    s["lugar_destino"], s["descripcion"],
                    gerente["id"], gerente["nombre"], u["nombre"],
                )
            except Exception:
                pass
            flash("Solicitud aprobada. Pendiente de aprobación gerencial.", "info")
            return redirect(url_for("planificador.planificador_solicitudes"))

    try:
        notif.notif_aprobada(
            sid, s["tipo"], s["area_solicitante"],
            str(s["fecha"]), s["hora_inicio"] or "", s["hora_fin"] or "",
            s["lugar_destino"], s["descripcion"],
            s["solicitante_id"], u["nombre"],
        )
    except Exception:
        pass
    flash("Solicitud aprobada. Aparecerá en el calendario.", "success")
    return redirect(url_for("planificador.planificador_solicitudes"))


# ─────────────────────────────────────────────────────────────
# POST: Aprobar todas las solicitudes de un grupo
# ─────────────────────────────────────────────────────────────

@planificador_bp.route("/solicitudes/grupo/<int:grupo_id>/aprobar", methods=["POST"],
                        endpoint="planificador_aprobar_grupo")
@require_login
def aprobar_grupo(grupo_id):
    u = _current_user()
    ctx = svc.get_user_context(u["id"], u["rol"])

    miembros = repo.get_solicitudes_del_grupo(grupo_id)
    if not miembros:
        flash("Grupo no encontrado o sin solicitudes.", "warning")
        return redirect(url_for("planificador.planificador_solicitudes"))

    obs = request.form.get("observacion_aprobador", "").strip()
    aprobadas = 0

    for m in miembros:
        if not svc.puede_aprobar(m, u["id"], ctx):
            continue
        repo.aprobar_solicitud(m["id"], u["id"], u["nombre"], obs)
        aprobadas += 1
        try:
            notif.notif_aprobada(
                m["id"], m["tipo"], m["area_solicitante"],
                str(m["fecha"]), m["hora_inicio"] or "", m["hora_fin"] or "",
                m["lugar_destino"], "",
                m["solicitante_id"], u["nombre"],
            )
        except Exception:
            pass

    if aprobadas == 0:
        flash("No tienes permiso para aprobar ninguna solicitud de este grupo.", "warning")
    else:
        flash(f"Se aprobaron {aprobadas} solicitudes del grupo #{grupo_id}.", "success")
    return redirect(url_for("planificador.planificador_solicitudes"))


# ─────────────────────────────────────────────────────────────
# POST: Aprobar como gerente
# ─────────────────────────────────────────────────────────────

@planificador_bp.route("/solicitudes/<int:sid>/aprobar-gerente", methods=["POST"],
                       endpoint="planificador_aprobar_gerente")
@require_login
def aprobar_gerente(sid):
    u = _current_user()
    ctx = svc.get_user_context(u["id"], u["rol"])
    s = repo.get_solicitud_by_id(sid)
    if not s or not svc.puede_aprobar_gerente(s, u["id"], ctx):
        abort(403)

    obs = request.form.get("observacion_aprobador", "").strip()
    repo.aprobar_por_gerente(sid, u["id"], u["nombre"], obs)
    try:
        notif.notif_aprobada(
            sid, s["tipo"], s["area_solicitante"],
            str(s["fecha"]), s["hora_inicio"] or "", s["hora_fin"] or "",
            s["lugar_destino"], s["descripcion"],
            s["solicitante_id"], u["nombre"],
        )
    except Exception:
        pass
    flash("Solicitud aprobada gerencialmente. Aparecerá en el calendario.", "success")
    return redirect(url_for("planificador.planificador_solicitudes"))


@planificador_bp.route("/solicitudes/<int:sid>/rechazar-gerente", methods=["POST"],
                       endpoint="planificador_rechazar_gerente")
@require_login
def rechazar_gerente(sid):
    u = _current_user()
    ctx = svc.get_user_context(u["id"], u["rol"])
    s = repo.get_solicitud_by_id(sid)
    if not s or not svc.puede_aprobar_gerente(s, u["id"], ctx):
        abort(403)

    obs = request.form.get("observacion_aprobador", "").strip()
    if not obs:
        flash("Para rechazar debe ingresar una observación.", "warning")
        return redirect(url_for("planificador.planificador_solicitudes"))

    repo.rechazar_por_gerente(sid, u["id"], u["nombre"], obs)
    try:
        notif.notif_rechazada(sid, s["tipo"], str(s["fecha"]),
                              obs, s["solicitante_id"], u["nombre"])
    except Exception:
        pass
    flash("Solicitud rechazada.", "info")
    return redirect(url_for("planificador.planificador_solicitudes"))


# ─────────────────────────────────────────────────────────────
# POST: Rechazar
# ─────────────────────────────────────────────────────────────

@planificador_bp.route("/solicitudes/<int:sid>/rechazar", methods=["POST"],
                       endpoint="planificador_rechazar")
@require_login
def rechazar(sid):
    u = _current_user()
    ctx = svc.get_user_context(u["id"], u["rol"])
    s = repo.get_solicitud_by_id(sid)
    if not s or not svc.puede_aprobar(s, u["id"], ctx):
        abort(403)

    obs = request.form.get("observacion_aprobador", "").strip()
    if not obs:
        flash("Para rechazar debe ingresar una observación.", "warning")
        return redirect(url_for("planificador.planificador_solicitudes"))

    repo.rechazar_solicitud(sid, u["id"], u["nombre"], obs)
    try:
        notif.notif_rechazada(sid, s["tipo"], str(s["fecha"]),
                              obs, s["solicitante_id"], u["nombre"])
    except Exception:
        pass
    flash("Solicitud rechazada.", "info")
    return redirect(url_for("planificador.planificador_solicitudes"))


# ─────────────────────────────────────────────────────────────
# POST: Completar
# ─────────────────────────────────────────────────────────────

@planificador_bp.route("/solicitudes/<int:sid>/completar", methods=["POST"],
                       endpoint="planificador_completar")
@require_login
def completar(sid):
    u = _current_user()
    ctx = svc.get_user_context(u["id"], u["rol"])
    s = repo.get_solicitud_by_id(sid)
    if not s or not svc.puede_completar(s, u["id"], ctx):
        abort(403)

    repo.completar_solicitud(sid, u["id"], u["nombre"])
    flash("Actividad marcada como completada.", "success")
    return redirect(url_for("planificador.planificador_solicitudes"))


# ─────────────────────────────────────────────────────────────
# POST: Reagendar (solo coordinadores / admin)
# ─────────────────────────────────────────────────────────────

@planificador_bp.route("/solicitudes/<int:sid>/reagendar", methods=["POST"],
                       endpoint="planificador_reagendar")
@require_login
def reagendar(sid):
    u = _current_user()
    ctx = svc.get_user_context(u["id"], u["rol"])
    s = repo.get_solicitud_by_id(sid)
    if not s or not svc.puede_reagendar(s, u["id"], ctx):
        abort(403)

    nueva_fecha = request.form.get("nueva_fecha", "").strip()
    motivo      = request.form.get("motivo_reagenda", "").strip()

    if not nueva_fecha:
        flash("Debe indicar la nueva fecha.", "warning")
        return redirect(url_for("planificador.planificador_solicitudes"))

    try:
        if date.fromisoformat(nueva_fecha) < date.today():
            flash("La nueva fecha no puede ser anterior al día de hoy.", "warning")
            return redirect(url_for("planificador.planificador_solicitudes"))
    except ValueError:
        flash("Fecha inválida.", "warning")
        return redirect(url_for("planificador.planificador_solicitudes"))

    # Guardar fecha anterior para la notificación
    fecha_anterior = str(s["fecha"]) if s["fecha"] else "—"

    repo.reagendar_solicitud(sid, nueva_fecha, u["id"], u["nombre"], motivo)
    try:
        notif.notif_reagendada(
            sid, s["tipo"], s["area_solicitante"],
            fecha_anterior, nueva_fecha, motivo,
            u["nombre"], s["solicitante_id"],
        )
    except Exception:
        pass
    flash(f"Solicitud reagendada para el {nueva_fecha}. El solicitante fue notificado.", "success")
    return redirect(url_for("planificador.planificador_solicitudes"))


# ─────────────────────────────────────────────────────────────
# POST: Eliminar (soft-delete con notificación por email)
# ─────────────────────────────────────────────────────────────

@planificador_bp.route("/solicitudes/<int:sid>/eliminar", methods=["POST"],
                       endpoint="planificador_eliminar")
@require_login
def eliminar(sid):
    u = _current_user()
    ctx = svc.get_user_context(u["id"], u["rol"])
    s = repo.get_solicitud_by_id(sid)
    if not s or not svc.puede_eliminar(s, u["id"], ctx):
        abort(403)

    es_solicitante = (s["solicitante_id"] == u["id"] and
                      not ctx["es_admin"] and
                      not ctx["tipos_coordinador"] and
                      not ctx["tipos_aprobador"])

    repo.insert_solicitud_log(sid, "ELIMINADA", u["id"], u["nombre"],
                              "Solicitud eliminada del sistema.")
    repo.delete_solicitud(sid, eliminado_por_id=u["id"],
                          eliminado_por_nombre=u["nombre"])

    try:
        notif.notif_eliminada(
            sid, s["tipo"], s["area_solicitante"],
            str(s["fecha"]) if s["fecha"] else "—",
            u["nombre"], s["solicitante_id"],
            eliminado_por_es_solicitante=es_solicitante,
        )
    except Exception:
        pass

    flash("Solicitud eliminada.", "info")
    return redirect(url_for("planificador.planificador_solicitudes"))


# ─────────────────────────────────────────────────────────────
# Configuración
# ─────────────────────────────────────────────────────────────

@planificador_bp.route("/configuracion", methods=["GET", "POST"],
                       endpoint="planificador_configuracion")
@require_login
@require_permission(PERM_CONFIG, "ver")
def configuracion():
    u = _current_user()

    if request.method == "POST":
        if not _check_perm(u["rol"], PERM_CONFIG, "crear"):
            abort(403)
        tipo        = request.form.get("tipo", "").strip()
        usuario_id  = request.form.get("usuario_id", "").strip()
        usuario_nombre = request.form.get("usuario_nombre", "").strip()
        rol_config  = request.form.get("rol_config", "").strip()

        tipos_validos = repo.get_tipos_solicitud()
        if not all([tipo, usuario_id, usuario_nombre, rol_config]):
            flash("Todos los campos son requeridos.", "warning")
        elif tipo not in tipos_validos:
            flash("Tipo de solicitud no válido.", "warning")
        elif rol_config not in (ROL_COORDINADOR, ROL_APROBADOR, ROL_MOTORIZADO):
            flash("Rol de configuración no válido.", "warning")
        else:
            try:
                repo.insert_config(tipo, int(usuario_id), usuario_nombre, rol_config)
                flash("Configuración guardada.", "success")
            except Exception:
                flash("Error al guardar. Verifique que no exista ya esa combinación.", "danger")

        return redirect(url_for("planificador.planificador_configuracion"))

    config_rows     = repo.get_all_config()
    usuarios        = repo.get_usuarios_for_select()
    tipos_solicitud = repo.get_tipos_solicitud()
    tipo_flags      = repo.get_all_tipo_flags()
    motorizados_tg  = repo.get_motorizados_telegram_status()

    return render_template(
        "planificador/configuracion.html",
        active_page=ACTIVE_KEY,
        config_rows=config_rows,
        usuarios=usuarios,
        tipos=tipos_solicitud,
        roles_config=[ROL_COORDINADOR, ROL_APROBADOR, ROL_MOTORIZADO],
        tipo_flags=tipo_flags,
        motorizados_tg=motorizados_tg,
    )


@planificador_bp.route("/configuracion/<int:cid>/eliminar", methods=["POST"],
                       endpoint="planificador_config_eliminar")
@require_login
@require_permission(PERM_CONFIG, "eliminar")
def config_eliminar(cid):
    repo.delete_config(cid)
    flash("Configuración eliminada.", "success")
    return redirect(url_for("planificador.planificador_configuracion"))


@planificador_bp.route("/configuracion/telegram-chat-id", methods=["POST"],
                       endpoint="planificador_set_telegram_chat_id")
@require_login
@require_permission(PERM_CONFIG, "editar")
def set_telegram_chat_id():
    """Admin guarda manualmente el telegram_chat_id de un usuario motorizado."""
    usuario_id = request.form.get("usuario_id", "").strip()
    chat_id    = request.form.get("telegram_chat_id", "").strip()
    if not usuario_id:
        flash("Usuario no indicado.", "warning")
        return redirect(url_for("planificador.planificador_configuracion"))
    try:
        repo.update_usuario_telegram_chat_id(int(usuario_id), chat_id or None)
        flash("Chat ID de Telegram actualizado.", "success")
    except Exception as exc:
        flash(f"Error al actualizar: {exc}", "danger")
    return redirect(url_for("planificador.planificador_configuracion"))


@planificador_bp.route("/configuracion/tipo-flags", methods=["POST"],
                       endpoint="planificador_tipo_flags")
@require_login
@require_permission(PERM_CONFIG, "editar")
def tipo_flags_update():
    """Actualiza los flags de configuración por tipo (ej: requiere aprobación gerente)."""
    u = _current_user()
    if not _check_perm(u["rol"], PERM_CONFIG, "editar"):
        abort(403)
    tipos_validos = repo.get_tipos_solicitud()
    for tipo in tipos_validos:
        key = f"req_gerente_{tipo.replace(' ', '_').replace('/', '_')}"
        req_gerente = request.form.get(key) == "1"
        repo.set_tipo_flags(tipo, req_gerente)
    flash("Configuración de tipos actualizada.", "success")
    return redirect(url_for("planificador.planificador_configuracion"))


# ─────────────────────────────────────────────────────────────
# Reverse geocode (proxy Nominatim – mismo origen, no viola CSP)
# ─────────────────────────────────────────────────────────────

@planificador_bp.route("/reverse-geocode", endpoint="planificador_reverse_geocode")
@require_login
def reverse_geocode():
    lat = request.args.get("lat", "").strip()
    lng = request.args.get("lng", "").strip()
    q   = request.args.get("q",   "").strip()
    try:
        if lat and lng:
            url = (f"https://nominatim.openstreetmap.org/reverse"
                   f"?format=json&lat={urllib.parse.quote(lat)}&lon={urllib.parse.quote(lng)}&zoom=18&addressdetails=1")
        elif q:
            url = (f"https://nominatim.openstreetmap.org/search"
                   f"?format=json&q={urllib.parse.quote(q)}&limit=1&addressdetails=1")
        else:
            return jsonify({"error": "Parámetros requeridos: lat+lng o q"}), 400

        req = urllib.request.Request(url, headers={"User-Agent": "SGQ-Quimpac/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = resp.read().decode("utf-8")
        import json as _json
        parsed = _json.loads(data)
        if isinstance(parsed, list):
            parsed = parsed[0] if parsed else {}
        # Construir dirección limpia desde el objeto address
        addr_obj = parsed.get("address", {})
        parts = []
        road = addr_obj.get("road") or addr_obj.get("pedestrian") or addr_obj.get("street") or ""
        house = addr_obj.get("house_number", "")
        if road:
            parts.append((road + " " + house).strip())
        suburb = addr_obj.get("suburb") or addr_obj.get("neighbourhood") or addr_obj.get("quarter") or ""
        if suburb:
            parts.append(suburb)
        city = addr_obj.get("city") or addr_obj.get("town") or addr_obj.get("municipality") or ""
        if city:
            parts.append(city)
        clean = ", ".join(p for p in parts if p) or parsed.get("display_name", "")
        return jsonify({"address": clean})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ─────────────────────────────────────────────────────────────
# Reporte CSV  (bug fix: iterar .values() no keys del dict)
# ─────────────────────────────────────────────────────────────

@planificador_bp.route("/solicitudes/reporte", endpoint="planificador_reporte")
@require_login
@require_permission(PERM_SOLICITUDES, "ver")
def reporte():
    filters = {
        "estado":      request.args.get("estado", ""),
        "tipo":        request.args.get("tipo",   ""),
        "fecha_desde": request.args.get("fecha_desde", ""),
        "fecha_hasta": request.args.get("fecha_hasta", ""),
    }
    cols, rows = repo.get_solicitudes_para_reporte(filters)

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_ALL)
    writer.writerow(cols)
    for row in rows:
        # RowCompat es un dict — iterar .values() para obtener datos, no claves
        writer.writerow([str(v) if v is not None else "" for v in row.values()])

    filename = f"planificador_{date.today()}.csv"
    return Response(
        "﻿" + output.getvalue(),   # BOM UTF-8 para Excel
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ─────────────────────────────────────────────────────────────
# Reporte Excel
# ─────────────────────────────────────────────────────────────

@planificador_bp.route("/solicitudes/reporte.xlsx", endpoint="planificador_reporte_excel")
@require_login
@require_permission(PERM_SOLICITUDES, "ver")
def reporte_excel():
    filters = {
        "estado":      request.args.get("estado", ""),
        "tipo":        request.args.get("tipo",   ""),
        "fecha_desde": request.args.get("fecha_desde", ""),
        "fecha_hasta": request.args.get("fecha_hasta", ""),
    }
    output = _build_planificador_excel(filters)
    filename = f"planificador_{date.today()}.xlsx"
    return Response(
        output.getvalue(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


def _build_planificador_excel(filters: dict) -> BytesIO:
    """Genera el Excel de solicitudes del planificador con formato."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import (Font, PatternFill, Alignment,
                                      Border, Side, GradientFill)
        from openpyxl.utils import get_column_letter
    except ImportError:
        raise RuntimeError("openpyxl no instalado. Ejecuta: pip install openpyxl")

    cols, rows = repo.get_solicitudes_para_reporte(filters)

    wb = Workbook()
    ws = wb.active
    ws.title = "Planificador"

    # ── Fila de título ───────────────────────────────────────
    ws.merge_cells(f"A1:{get_column_letter(len(cols))}1")
    title_cell = ws["A1"]
    title_cell.value = f"PLANIFICADOR DE SOLICITUDES — SGQ Quimpac · {date.today().strftime('%d/%m/%Y')}"
    title_cell.font      = Font(name="Calibri", bold=True, size=13, color="FFFFFF")
    title_cell.fill      = PatternFill("solid", fgColor="1E3A8A")
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 26

    # ── Fila de cabecera ─────────────────────────────────────
    header_fill   = PatternFill("solid", fgColor="DBEAFE")
    header_font   = Font(name="Calibri", bold=True, size=10, color="1E3A8A")
    header_border = Border(
        bottom=Side(style="medium", color="1E3A8A"),
        right=Side(style="thin",   color="CBD5E1"),
    )
    for ci, col_name in enumerate(cols, start=1):
        cell = ws.cell(row=2, column=ci, value=col_name)
        cell.font      = header_font
        cell.fill      = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border    = header_border
    ws.row_dimensions[2].height = 30

    # ── Colores por estado ────────────────────────────────────
    ESTADO_FILL = {
        "PENDIENTE_COORDINACION":       PatternFill("solid", fgColor="FEF9C3"),
        "PENDIENTE_APROBACION":         PatternFill("solid", fgColor="CFFAFE"),
        "PENDIENTE_APROBACION_GERENTE": PatternFill("solid", fgColor="DBEAFE"),
        "APROBADA":                     PatternFill("solid", fgColor="DCFCE7"),
        "RECHAZADA":                    PatternFill("solid", fgColor="FEE2E2"),
        "COMPLETADA":                   PatternFill("solid", fgColor="F3F4F6"),
    }
    thin_border = Border(
        right=Side(style="thin", color="E2E8F0"),
        bottom=Side(style="thin", color="E2E8F0"),
    )
    # Índice de la columna "Estado" (basado en el nombre de col)
    try:
        estado_col_idx = cols.index("Estado") + 1
    except ValueError:
        estado_col_idx = None

    # ── Datos ────────────────────────────────────────────────
    for ri, row in enumerate(rows, start=3):
        values = list(row.values())
        estado_val = ""
        if estado_col_idx:
            estado_val = str(values[estado_col_idx - 1] or "")
        row_fill = ESTADO_FILL.get(estado_val)

        for ci, v in enumerate(values, start=1):
            cell = ws.cell(row=ri, column=ci,
                           value="" if v is None else (str(v) if not isinstance(v, (int, float)) else v))
            cell.font      = Font(name="Calibri", size=9)
            cell.border    = thin_border
            cell.alignment = Alignment(vertical="center", wrap_text=False)
            if row_fill:
                cell.fill = row_fill

        # Alternar fila clara si no tiene color de estado
        if not row_fill and ri % 2 == 0:
            alt_fill = PatternFill("solid", fgColor="F8FAFC")
            for ci in range(1, len(values) + 1):
                ws.cell(row=ri, column=ci).fill = alt_fill

        ws.row_dimensions[ri].height = 16

    # ── Anchos de columna ────────────────────────────────────
    col_widths = {
        "N° Solicitud": 12, "Tipo": 22, "Área Solicitante": 22,
        "Descripción": 35, "Lugar / Destino": 28, "Contacto": 18,
        "Prioridad": 11, "Fecha": 12, "Hora Inicio": 11, "Hora Fin": 10,
        "Estado": 22, "Solicitante": 20, "Coordinador": 20,
        "Aprobador": 20, "Obs. Coordinador": 28, "Obs. Aprobador": 28,
        "Ciudad": 14, "Detalle Dirección": 30,
        "Fecha Creación": 18, "Última Actualización": 18,
    }
    for ci, col_name in enumerate(cols, start=1):
        w = col_widths.get(col_name, 15)
        ws.column_dimensions[get_column_letter(ci)].width = w

    # ── Freeze panes y auto-filtro ───────────────────────────
    ws.freeze_panes = "A3"
    if rows:
        ws.auto_filter.ref = f"A2:{get_column_letter(len(cols))}{len(rows) + 2}"

    # ── Pestaña de color ─────────────────────────────────────
    ws.sheet_properties.tabColor = "1E3A8A"

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output


# ─────────────────────────────────────────────────────────────
# Helper interno de permiso sin decorador
# ─────────────────────────────────────────────────────────────

def _check_perm(rol, opcion, accion):
    from modules.security import has_permission
    return has_permission(rol, opcion, accion)


# ─────────────────────────────────────────────────────────────
# Registro
# ─────────────────────────────────────────────────────────────

def register_planificador_routes(app):
    app.register_blueprint(planificador_bp)
