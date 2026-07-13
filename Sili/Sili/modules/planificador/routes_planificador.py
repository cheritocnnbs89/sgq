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
    flash, session, abort, jsonify, current_app,
)

from modules.auth.routes_auth import require_login, require_permission
from . import planificador_repository as repo
from . import planificador_services as svc
from . import planificador_notifications as notif
from .planificador_constants import (
    ACTIVE_KEY, PERM_SOLICITUDES, PERM_CONFIG, PERM_PRESUPUESTO,
    ESTADOS, PRIORIDADES,
    ROL_COORDINADOR, ROL_APROBADOR, ROL_MOTORIZADO, ROL_GERENTE_PRESUPUESTO,
    ESTADOS_RESERVADAS, ESTADOS_COORDINADAS, ESTADOS_POR_COMPLETAR, ESTADOS_ATENDIDAS,
    MOTIVO_VUELO_OTROS,
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
    current_app.logger.info("[PLANIF] usuario_id=%s nombre=%s", u["id"], u.get("nombre"))
    tipos_solicitud = repo.get_tipos_solicitud()

    filters = {
        "estado":      request.args.get("estado", ""),
        "tipo":        request.args.get("tipo", ""),
        "area":        request.args.get("area", ""),
        "fecha_desde": request.args.get("fecha_desde", ""),
        "fecha_hasta": request.args.get("fecha_hasta", ""),
    }

    solicitudes_list = svc.get_solicitudes_for_user(u["id"], u["rol"], filters)
    current_app.logger.info(
        "[PLANIF] total=%d solicitudes: %s",
        len(solicitudes_list),
        [(r.get("id"), r.get("tipo"), r.get("estado")) for r in solicitudes_list],
    )
    departamentos    = repo.get_departamentos()
    usuario_dept     = repo.get_usuario_departamento(u["id"])

    # Enriquecer cada fila con banderas de acciones
    rows = []
    for s in solicitudes_list:
        d = dict(s)
        d["puede_coordinar"]          = svc.puede_coordinar(s, u["id"], ctx)
        d["puede_aprobar"]            = svc.puede_aprobar(s, u["id"], ctx)
        d["puede_aprobar_gerente"]    = svc.puede_aprobar_gerente(s, u["id"], ctx)
        d["puede_completar"]          = svc.puede_completar(s, u["id"], ctx)
        d["puede_reagendar"]          = svc.puede_reagendar(s, u["id"], ctx)
        d["puede_eliminar"]           = svc.puede_eliminar(s, u["id"], ctx)
        d["puede_aprobar_jefe_vuelo"] = svc.puede_aprobar_jefe_vuelo(s, u["id"], ctx)
        d["puede_cotizar_vuelo"]      = svc.puede_cotizar_vuelo(s, u["id"], ctx)
        d["puede_aprobar_gg_vuelo"]   = svc.puede_aprobar_gg_vuelo(s, u["id"], ctx)
        d["puede_completar_vuelo"]    = svc.puede_completar_vuelo(s, u["id"], ctx)
        d["estado_label"]    = svc.estado_label(s["estado"])
        d["estado_class"]    = svc.estado_badge_class(s["estado"])
        d["fecha_str"]       = str(s["fecha"]) if s["fecha"] else ""
        rows.append(d)

    # Dividir en secciones
    reservadas, coordinadas, por_completar, atendidas = svc.agrupar_por_seccion(rows)
    current_app.logger.info(
        "[PLANIF] secciones reservadas=%d coordinadas=%d por_completar=%d atendidas=%d",
        len(reservadas), len(coordinadas), len(por_completar), len(atendidas),
    )
    current_app.logger.info(
        "[PLANIF] coordinadas detalle=%s",
        [(r.get("id"), r.get("tipo"), r.get("estado")) for r in coordinadas],
    )
    por_aprobar = [r for r in rows if r.get("puede_aprobar_gerente")
                   or r.get("puede_aprobar_jefe_vuelo")
                   or r.get("puede_aprobar_gg_vuelo")]

    # Enriquecer con jefe_nombre para todas las filas tipo Vuelo
    vuelo_sol_ids = list({
        r["solicitante_id"] for r in rows
        if r.get("tipo") == "Vuelo" and r.get("solicitante_id")
    })
    jefe_map = repo.get_jefe_nombre_batch(vuelo_sol_ids) if vuelo_sol_ids else {}
    for r in rows:
        if r.get("tipo") == "Vuelo":
            r["jefe_nombre"] = jefe_map.get(r.get("solicitante_id"), "")

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
        por_completar=por_completar,
        atendidas=atendidas,
        por_aprobar=por_aprobar,
        filters=filters,
        tipos=tipos_solicitud,
        motivos_vuelo=repo.get_motivos_vuelo(),
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
    es_jefe_de_solicitud = s.get("gerente_id") == u["id"]
    if (not svc.puede_ver_detalle_completo(ctx)
            and s["solicitante_id"] != u["id"]
            and not es_jefe_de_solicitud):
        abort(403)

    d = dict(s)
    d["puede_coordinar"]         = svc.puede_coordinar(s, u["id"], ctx)
    d["puede_aprobar"]           = svc.puede_aprobar(s, u["id"], ctx)
    d["puede_aprobar_gerente"]   = svc.puede_aprobar_gerente(s, u["id"], ctx)
    d["puede_completar"]         = svc.puede_completar(s, u["id"], ctx)
    d["puede_reagendar"]         = svc.puede_reagendar(s, u["id"], ctx)
    d["puede_eliminar"]          = svc.puede_eliminar(s, u["id"], ctx)
    d["puede_aprobar_jefe_vuelo"] = svc.puede_aprobar_jefe_vuelo(s, u["id"], ctx)
    d["puede_cotizar_vuelo"]      = svc.puede_cotizar_vuelo(s, u["id"], ctx)
    d["puede_aprobar_gg_vuelo"]   = svc.puede_aprobar_gg_vuelo(s, u["id"], ctx)
    d["puede_completar_vuelo"]         = svc.puede_completar_vuelo(s, u["id"], ctx)
    d["puede_marcar_realizado_vuelo"]  = svc.puede_marcar_realizado_vuelo(s, u["id"], ctx)
    d["puede_liquidar_vuelo"]          = svc.puede_liquidar_vuelo(s, u["id"], ctx)
    d["estado_label"]    = svc.estado_label(s["estado"])
    d["estado_class"]    = svc.estado_badge_class(s["estado"])
    d["fecha_str"]       = str(s["fecha"]) if s["fecha"] else ""
    logs = repo.get_solicitud_logs(sid)

    grupo_solicitudes = []
    if d.get("grupo_id"):
        todas = repo.get_solicitudes_del_grupo(d["grupo_id"])
        grupo_solicitudes = [dict(g) for g in todas if g["id"] != sid]

    adjuntos = repo.get_adjuntos(sid)
    _es_solicitante = s["solicitante_id"] == u["id"]
    _estado_bloqueado_general = s["estado"] in ("COMPLETADA", "RECHAZADA",
                                                "PENDIENTE_APROBACION_JEFE",
                                                "PENDIENTE_APROBACION_GG_VUELO")
    # Para Vuelo en PENDIENTE_INFO_VUELO el adjunto va dentro del form de completar vuelo
    _es_vuelo_pendiente_coord = (s["tipo"] == "Vuelo" and s["estado"] == "PENDIENTE_INFO_VUELO")
    puede_subir_adjunto = (
        not _es_vuelo_pendiente_coord
        and (
            ctx["es_admin"]
            or (
                not _estado_bloqueado_general
                and (ctx["es_gerente"] or ctx["tipos_coordinador"] or ctx["tipos_aprobador"])
            )
            or (_es_solicitante and s["estado"] not in ("COMPLETADA", "RECHAZADA"))
        )
    )
    puede_eliminar_adjunto = ctx["es_admin"] or s["estado"] not in ("APROBADA", "COMPLETADA")

    cc_nombre   = repo.get_cc_nombre(d.get("centro_costo_id")) if d.get("centro_costo_id") else None
    tipos_gasto = repo.get_tipos_gasto() if d.get("puede_liquidar_vuelo") else []

    return render_template(
        "planificador/_detalle_modal_body.html",
        s=d,
        logs=logs,
        grupo_solicitudes=grupo_solicitudes,
        active_page=ACTIVE_KEY,
        today_iso=date.today().isoformat(),
        adjuntos=adjuntos,
        puede_subir_adjunto=puede_subir_adjunto,
        puede_eliminar_adjunto=puede_eliminar_adjunto,
        cc_nombre=cc_nombre,
        tipos_gasto=tipos_gasto,
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

    campos_base = [tipo, area, desc, fecha] if tipo == "Vuelo" else [tipo, area, desc, lugar, fecha]
    if not all(campos_base):
        flash("Todos los campos obligatorios deben completarse.", "warning")
        return redirect(url_for("planificador.planificador_solicitudes"))
    if tipo not in repo.get_tipos_solicitud():
        flash("Tipo de solicitud no válido.", "warning")
        return redirect(url_for("planificador.planificador_solicitudes"))

    fecha_retorno   = None
    punto_salida    = None
    punto_destino   = None
    requiere_hosp   = 0
    orden_servicio  = None
    cc_id           = None
    requiere_aprov  = 0
    motivo_vuelo    = None

    if tipo == "Vuelo":
        motivo_vuelo = request.form.get("motivo_vuelo", "").strip()
        if not motivo_vuelo:
            flash("El motivo de la solicitud de Vuelo es obligatorio.", "warning")
            return redirect(url_for("planificador.planificador_solicitudes"))
        if motivo_vuelo == MOTIVO_VUELO_OTROS and not desc:
            flash("Debe indicar el motivo en el campo Observación.", "warning")
            return redirect(url_for("planificador.planificador_solicitudes"))

        fecha_retorno  = request.form.get("fecha_retorno", "").strip() or None
        punto_salida   = request.form.get("punto_salida", "").strip() or None
        punto_destino  = request.form.get("punto_destino", "").strip() or None
        requiere_hosp  = 1 if request.form.get("requiere_hospedaje") else 0
        orden_servicio = request.form.get("orden_servicio", "").strip() or None

        # Detectar CC del usuario y validar saldo anual de presupuesto (Ticket aéreo)
        import datetime
        cc_info = repo.get_cc_usuario(u["id"])
        if cc_info:
            cc_id = cc_info["cc_id"]
            anio_actual = datetime.date.today().year
            saldo = repo.get_saldo_anual_presupuesto(
                cc_info["empresa_id"], cc_id, "Ticket aéreo", anio_actual
            )
            if saldo["semaforo"] == "rojo":
                requiere_aprov = 1

    ciudad = repo.get_ciudad_usuario(u["id"])

    # Para Vuelo: el flujo empieza con aprobación del jefe directo
    estado_inicial = "PENDIENTE_COORDINACION"
    jefe_id_vuelo   = None
    jefe_nombre_vuelo = None
    if tipo == "Vuelo":
        jefe = repo.get_gerente_del_usuario(u["id"])
        current_app.logger.info(
            "[VUELO] usuario_id=%s nombre=%s → jefe=%s",
            u["id"], u.get("nombre"), jefe
        )
        if jefe:
            jefe_id_vuelo     = jefe["id"]
            jefe_nombre_vuelo = jefe["nombre"]
            estado_inicial    = "PENDIENTE_APROBACION_JEFE"
        else:
            current_app.logger.warning(
                "[VUELO] Sin jefe_id para usuario %s → cae a PENDIENTE_COORDINACION", u["id"]
            )
            estado_inicial = "PENDIENTE_COORDINACION"

    sid = repo.crear_solicitud({
        "tipo":                           tipo,
        "area_solicitante":               area,
        "descripcion":                    desc,
        "lugar_destino":                  lugar,
        "detalle_direccion":              request.form.get("detalle_direccion", "").strip(),
        "contacto":                       request.form.get("contacto", "").strip(),
        "prioridad":                      request.form.get("prioridad", "Normal"),
        "fecha":                          fecha,
        "estado":                         estado_inicial,
        "solicitante_id":                 u["id"],
        "solicitante_nombre":             u["nombre"],
        "ciudad":                         ciudad,
        "fecha_retorno":                  fecha_retorno,
        "punto_salida":                   punto_salida,
        "punto_destino":                  punto_destino,
        "requiere_hospedaje":             requiere_hosp,
        "orden_servicio":                 orden_servicio,
        "centro_costo_id":                cc_id,
        "requiere_aprobacion_presupuesto": requiere_aprov,
        "gerente_id":                     jefe_id_vuelo,
        "gerente_nombre":                 jefe_nombre_vuelo,
        "motivo_vuelo":                   motivo_vuelo,
    })

    if tipo == "Vuelo":
        # Notificar al jefe directo para que apruebe
        try:
            notif.notif_vuelo_pendiente_jefe(
                sid, area, fecha, desc, motivo_vuelo or "—",
                u["nombre"], jefe_id_vuelo, jefe_nombre_vuelo or "—",
            )
        except Exception:
            pass
        msg = "Solicitud de Vuelo creada. Pendiente de aprobación de su jefe directo."
        if not jefe_id_vuelo:
            msg = "Solicitud de Vuelo creada. No tiene jefe configurado; pasó a coordinación."
    else:
        try:
            notif.notif_nueva_solicitud(sid, tipo, area, fecha, u["nombre"], solicitante_id=u["id"])
        except Exception:
            pass
        msg = "Solicitud creada. Queda pendiente de coordinación."

    flash(msg, "success")
    return redirect(url_for("planificador.planificador_solicitudes"))


# ─────────────────────────────────────────────────────────────
# AJAX: Saldo de presupuesto del usuario (para tipo Vuelo)
# ─────────────────────────────────────────────────────────────

@planificador_bp.route("/presupuesto/saldo-usuario", methods=["GET"],
                       endpoint="planificador_saldo_usuario")
@require_login
def presupuesto_saldo_usuario():
    from datetime import date as _date
    u = _current_user()
    cc_info = repo.get_cc_usuario(u["id"])
    if not cc_info:
        return jsonify({"ok": False, "msg": "Sin centro de costo asignado al usuario."})
    hoy = _date.today()
    tipo_gasto = "Ticket aéreo"
    saldo_data = repo.get_saldo_anual_presupuesto(
        cc_info["empresa_id"], cc_info["cc_id"], tipo_gasto, hoy.year
    )
    return jsonify({
        "ok":       True,
        "semaforo": saldo_data["semaforo"],
        "pct":      saldo_data["pct"],
        "anio":     hoy.year,
    })


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

    es_vuelo = s["tipo"] == "Vuelo"
    nuevo_estado = "PENDIENTE_APROBACION_JEFE" if es_vuelo else "PENDIENTE_COORDINACION"
    repo.reagendar_solicitud(sid, nueva_fecha, u["id"], u["nombre"], motivo, nuevo_estado)

    if es_vuelo:
        # Renotificar al jefe para que vuelva a aprobar con la nueva fecha
        try:
            jefe_id   = s.get("gerente_id")
            jefe_nom  = s.get("gerente_nombre", "—")
            notif.notif_vuelo_pendiente_jefe(
                sid, s["area_solicitante"], nueva_fecha,
                s.get("descripcion", ""),
                s.get("motivo_vuelo") or "—",
                s["solicitante_nombre"], jefe_id, jefe_nom,
                es_reagenda=True,
            )
        except Exception:
            pass
        flash(f"Vuelo reagendado para el {nueva_fecha}. Vuelve a aprobación del jefe.", "success")
    else:
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
# Vuelo: aprobación jefe directo
# ─────────────────────────────────────────────────────────────

@planificador_bp.route("/solicitudes/<int:sid>/vuelo/aprobar-jefe", methods=["POST"],
                       endpoint="planificador_vuelo_aprobar_jefe")
@require_login
def vuelo_aprobar_jefe(sid):
    u = _current_user()
    ctx = svc.get_user_context(u["id"], u["rol"])
    s = repo.get_solicitud_by_id(sid)
    if not s or not svc.puede_aprobar_jefe_vuelo(s, u["id"], ctx):
        abort(403)
    obs = request.form.get("observacion", "").strip()
    repo.aprobar_jefe_vuelo(sid, u["id"], u["nombre"], obs)
    try:
        notif.notif_vuelo_aprobada_coordinacion(
            sid, s["area_solicitante"], str(s["fecha"]),
            s.get("descripcion", ""), s["solicitante_nombre"], u["nombre"],
        )
    except Exception:
        pass
    flash("Vuelo aprobado. Pasa al coordinador para cotizar el pasaje.", "success")
    return redirect(url_for("planificador.planificador_solicitudes"))


@planificador_bp.route("/solicitudes/<int:sid>/vuelo/rechazar-jefe", methods=["POST"],
                       endpoint="planificador_vuelo_rechazar_jefe")
@require_login
def vuelo_rechazar_jefe(sid):
    u = _current_user()
    ctx = svc.get_user_context(u["id"], u["rol"])
    s = repo.get_solicitud_by_id(sid)
    if not s or not svc.puede_aprobar_jefe_vuelo(s, u["id"], ctx):
        abort(403)
    obs = request.form.get("observacion", "").strip()
    if not obs:
        flash("Debe indicar el motivo del rechazo.", "warning")
        return redirect(url_for("planificador.planificador_solicitudes"))
    repo.rechazar_vuelo(sid, u["id"], u["nombre"], obs)
    try:
        notif.notif_vuelo_rechazada(
            sid, s["area_solicitante"], str(s["fecha"]),
            obs, s["solicitante_nombre"], s["solicitante_id"], u["nombre"],
        )
    except Exception:
        pass
    flash("Solicitud de Vuelo rechazada.", "warning")
    return redirect(url_for("planificador.planificador_solicitudes"))


@planificador_bp.route("/solicitudes/vuelo/aprobar-jefe-masivo", methods=["POST"],
                       endpoint="planificador_vuelo_aprobar_jefe_masivo")
@require_login
def vuelo_aprobar_jefe_masivo():
    u = _current_user()
    ctx = svc.get_user_context(u["id"], u["rol"])
    ids_raw = request.form.getlist("ids[]")
    try:
        sids = [int(x) for x in ids_raw if x.strip().isdigit()]
    except Exception:
        sids = []
    if not sids:
        flash("No se seleccionaron solicitudes.", "warning")
        return redirect(url_for("planificador.planificador_solicitudes"))
    aprobadas = 0
    for sid in sids:
        s = repo.get_solicitud_by_id(sid)
        if not s or not svc.puede_aprobar_jefe_vuelo(s, u["id"], ctx):
            continue
        repo.aprobar_jefe_vuelo(sid, u["id"], u["nombre"], "")
        try:
            notif.notif_vuelo_aprobada_coordinacion(
                sid, s["area_solicitante"], str(s["fecha"]),
                s.get("descripcion", ""), s["solicitante_nombre"], u["nombre"],
            )
        except Exception:
            pass
        aprobadas += 1
    flash(f"{aprobadas} solicitud(es) aprobada(s).", "success")
    return redirect(url_for("planificador.planificador_solicitudes"))


# ─────────────────────────────────────────────────────────────
# Vuelo: coordinador ingresa el valor cotizado del pasaje
# ─────────────────────────────────────────────────────────────

@planificador_bp.route("/solicitudes/<int:sid>/vuelo/cotizar", methods=["POST"],
                       endpoint="planificador_vuelo_cotizar")
@require_login
def vuelo_cotizar(sid):
    u = _current_user()
    ctx = svc.get_user_context(u["id"], u["rol"])
    s = repo.get_solicitud_by_id(sid)
    if not s or not svc.puede_cotizar_vuelo(s, u["id"], ctx):
        abort(403)
    valor = request.form.get("valor_cotizado", "").strip()
    obs   = request.form.get("observacion", "").strip()
    if not valor:
        flash("Debe ingresar el valor cotizado del pasaje.", "warning")
        return redirect(url_for("planificador.planificador_solicitudes"))
    repo.cotizar_vuelo(sid, u["id"], u["nombre"], valor, obs)
    try:
        gg_lista = repo.get_gerentes_presupuesto_para_tipo("Vuelo")
        for gg in gg_lista:
            notif.notif_vuelo_pendiente_gg(
                sid, s["area_solicitante"], str(s["fecha"]),
                s.get("descripcion", ""), valor,
                s["solicitante_nombre"], u["nombre"],
                gg.get("id"), gg.get("nombre", "—"),
            )
    except Exception:
        pass
    flash("Cotización registrada. Pasa a aprobación del Gerente de Presupuesto.", "success")
    return redirect(url_for("planificador.planificador_solicitudes"))


# ─────────────────────────────────────────────────────────────
# Vuelo: aprobación Gerente de Presupuesto (revisa la cotización)
# ─────────────────────────────────────────────────────────────

@planificador_bp.route("/solicitudes/<int:sid>/vuelo/aprobar-gg", methods=["POST"],
                       endpoint="planificador_vuelo_aprobar_gg")
@require_login
def vuelo_aprobar_gg(sid):
    u = _current_user()
    ctx = svc.get_user_context(u["id"], u["rol"])
    s = repo.get_solicitud_by_id(sid)
    if not s or not svc.puede_aprobar_gg_vuelo(s, u["id"], ctx):
        abort(403)
    obs = request.form.get("observacion", "").strip()
    repo.aprobar_gg_vuelo(sid, u["id"], u["nombre"], obs)
    try:
        notif.notif_vuelo_gg_aprobo_pendiente_info(
            sid, s["area_solicitante"], str(s["fecha"]),
            s.get("descripcion", ""), s["solicitante_nombre"], u["nombre"],
        )
    except Exception:
        pass
    flash("Cotización aprobada. Pasa al coordinador para ingresar la información del vuelo.", "success")
    return redirect(url_for("planificador.planificador_solicitudes"))


@planificador_bp.route("/solicitudes/<int:sid>/vuelo/rechazar-gg", methods=["POST"],
                       endpoint="planificador_vuelo_rechazar_gg")
@require_login
def vuelo_rechazar_gg(sid):
    u = _current_user()
    ctx = svc.get_user_context(u["id"], u["rol"])
    s = repo.get_solicitud_by_id(sid)
    if not s or not svc.puede_aprobar_gg_vuelo(s, u["id"], ctx):
        abort(403)
    obs = request.form.get("observacion", "").strip()
    if not obs:
        flash("Debe indicar el motivo del rechazo.", "warning")
        return redirect(url_for("planificador.planificador_solicitudes"))
    repo.rechazar_gg_vuelo(sid, u["id"], u["nombre"], obs)
    try:
        notif.notif_vuelo_gg_rechazo_coordinador(
            sid, s["area_solicitante"], str(s["fecha"]),
            obs, s["solicitante_nombre"], u["nombre"],
        )
    except Exception:
        pass
    flash("Cotización rechazada. Vuelve al coordinador para recotizar.", "warning")
    return redirect(url_for("planificador.planificador_solicitudes"))


@planificador_bp.route("/solicitudes/vuelo/aprobar-gg-masivo", methods=["POST"],
                       endpoint="planificador_vuelo_aprobar_gg_masivo")
@require_login
def vuelo_aprobar_gg_masivo():
    u = _current_user()
    ctx = svc.get_user_context(u["id"], u["rol"])
    ids_raw = request.form.getlist("ids[]")
    try:
        sids = [int(x) for x in ids_raw if x.strip().isdigit()]
    except Exception:
        sids = []
    if not sids:
        flash("No se seleccionaron solicitudes.", "warning")
        return redirect(url_for("planificador.planificador_solicitudes"))
    aprobadas = 0
    for sid in sids:
        s = repo.get_solicitud_by_id(sid)
        if not s or not svc.puede_aprobar_gg_vuelo(s, u["id"], ctx):
            continue
        repo.aprobar_gg_vuelo(sid, u["id"], u["nombre"], "")
        try:
            notif.notif_vuelo_gg_aprobo_pendiente_info(
                sid, s["area_solicitante"], str(s["fecha"]),
                s.get("descripcion", ""), s["solicitante_nombre"], u["nombre"],
            )
        except Exception:
            pass
        aprobadas += 1
    flash(f"{aprobadas} solicitud(es) aprobada(s) por GG.", "success")
    return redirect(url_for("planificador.planificador_solicitudes"))


# ─────────────────────────────────────────────────────────────
# Vuelo: coordinador registra datos de reserva
# ─────────────────────────────────────────────────────────────

@planificador_bp.route("/solicitudes/<int:sid>/vuelo/coordinar", methods=["POST"],
                       endpoint="planificador_vuelo_coordinar")
@require_login
def vuelo_coordinar(sid):
    import os, uuid
    from werkzeug.utils import secure_filename
    u = _current_user()
    ctx = svc.get_user_context(u["id"], u["rol"])
    s = repo.get_solicitud_by_id(sid)
    if not s or not svc.puede_coordinar(s, u["id"], ctx):
        abort(403)

    action = request.form.get("action", "coordinar")

    # ── Reprogramar: nueva fecha → vuelve a PENDIENTE_APROBACION_JEFE ──
    if action == "reprogramar":
        nueva_fecha = request.form.get("nueva_fecha", "").strip()
        motivo      = request.form.get("motivo_reprogramacion", "").strip()
        if not nueva_fecha:
            flash("Debe indicar la nueva fecha.", "warning")
            return redirect(url_for("planificador.planificador_solicitudes"))
        if not motivo:
            flash("Debe indicar el motivo de la reprogramación.", "warning")
            return redirect(url_for("planificador.planificador_solicitudes"))
        repo.reagendar_vuelo_a_jefe(sid, nueva_fecha, u["id"], u["nombre"], motivo)
        try:
            notif.notif_vuelo_pendiente_jefe(
                sid, s["area_solicitante"], nueva_fecha,
                s.get("descripcion", ""), s.get("motivo_vuelo") or "—",
                s["solicitante_nombre"],
                s.get("gerente_id"), s.get("gerente_nombre", "—"),
            )
        except Exception:
            pass
        flash("Vuelo reprogramado. Vuelve al proceso de aprobación del jefe.", "info")
        return redirect(url_for("planificador.planificador_solicitudes"))

    # ── Coordinar: registrar datos de reserva ──
    hi             = request.form.get("hora_inicio", "").strip()
    hf             = request.form.get("hora_fin", "").strip()
    datos_ticket   = request.form.get("datos_ticket", "").strip()
    datos_hotel    = request.form.get("datos_hotel", "").strip()
    obs            = request.form.get("observacion_coordinador", "").strip()

    if not hi or not hf:
        flash("Debe indicar hora de inicio y hora fin del vuelo.", "warning")
        return redirect(url_for("planificador.planificador_solicitudes"))
    if not datos_ticket:
        flash("Debe ingresar los datos de la reservación del ticket aéreo.", "warning")
        return redirect(url_for("planificador.planificador_solicitudes"))

    # Guardar adjunto si se subió
    attachment_paths = []
    archivo = request.files.get("adjunto_vuelo")
    nombre_original = None
    if archivo and archivo.filename:
        archivo.seek(0, 2)
        tamano = archivo.tell()
        archivo.seek(0)
        if tamano > 10 * 1024 * 1024:
            flash("El archivo supera el límite de 10 MB.", "warning")
            return redirect(url_for("planificador.planificador_solicitudes"))
        nombre_original = archivo.filename
        nombre_seguro   = secure_filename(nombre_original)
        ext             = os.path.splitext(nombre_seguro)[1]
        nombre_guardado = f"{uuid.uuid4().hex}{ext}"
        carpeta = os.path.join(current_app.config["UPLOAD_FOLDER"], "planificador", str(sid))
        os.makedirs(carpeta, exist_ok=True)
        ruta_completa = os.path.join(carpeta, nombre_guardado)
        archivo.save(ruta_completa)
        repo.insert_adjunto(sid, nombre_original, nombre_guardado, tamano, u["id"], u["nombre"])
        attachment_paths = [(ruta_completa, nombre_seguro)]

    repo.coordinar_vuelo(sid, u["id"], u["nombre"], hi, hf, datos_ticket, datos_hotel, obs)
    try:
        notif.notif_vuelo_coordinada_solicitante(
            sid, s["area_solicitante"], str(s["fecha"]),
            s.get("descripcion", ""), hi, hf,
            datos_ticket, datos_hotel,
            s["solicitante_nombre"], s["solicitante_id"],
            u["nombre"], attachment_paths or None,
        )
    except Exception:
        pass
    flash("Datos de reserva registrados. Se notificó al solicitante.", "success")
    return redirect(url_for("planificador.planificador_solicitudes"))


# ─────────────────────────────────────────────────────────────
# Vuelo: coordinador registra gestión y completa
# ─────────────────────────────────────────────────────────────

@planificador_bp.route("/solicitudes/<int:sid>/vuelo/completar", methods=["POST"],
                       endpoint="planificador_vuelo_completar")
@require_login
def vuelo_completar(sid):
    u = _current_user()
    ctx = svc.get_user_context(u["id"], u["rol"])
    s = repo.get_solicitud_by_id(sid)
    if not s or not svc.puede_completar_vuelo(s, u["id"], ctx):
        abort(403)
    hora_inicio = request.form.get("hora_inicio", "").strip() or None
    hora_fin    = request.form.get("hora_fin", "").strip() or None
    aeropuerto  = request.form.get("aeropuerto", "").strip()

    partes = []
    if aeropuerto:
        partes.append(f"Aeropuerto: {aeropuerto}")
    obs_base = request.form.get("observacion_coordinador", "").strip()
    if obs_base:
        partes.append(obs_base)
    obs = "\n".join(partes)

    if not obs_base and not aeropuerto:
        flash("Debe ingresar la información de la reservación.", "warning")
        return redirect(url_for("planificador.planificador_solicitudes"))
    repo.completar_vuelo(sid, u["id"], u["nombre"], obs, hora_inicio, hora_fin)

    # Guardar adjunto del ticket/boleto si se subió
    import os, uuid
    from werkzeug.utils import secure_filename
    archivo = request.files.get("adjunto_vuelo")
    ruta_adjunto = None
    nombre_adjunto = None
    if archivo and archivo.filename:
        archivo.seek(0, 2); tam = archivo.tell(); archivo.seek(0)
        if tam <= 5 * 1024 * 1024:
            nombre_original = secure_filename(archivo.filename)
            ext = os.path.splitext(nombre_original)[1]
            nombre_guardado = f"{uuid.uuid4().hex}{ext}"
            carpeta = os.path.join(current_app.config["UPLOAD_FOLDER"], "planificador", str(sid))
            os.makedirs(carpeta, exist_ok=True)
            ruta_adjunto = os.path.join(carpeta, nombre_guardado)
            archivo.save(ruta_adjunto)
            repo.insert_adjunto(sid, nombre_original, nombre_guardado, tam, u["id"], u["nombre"])
            nombre_adjunto = nombre_original

    # Notificar al solicitante con detalles y archivo adjunto
    try:
        adjuntos_email = [(ruta_adjunto, nombre_adjunto)] if ruta_adjunto else None
        notif.notif_vuelo_completada(
            sid, s["area_solicitante"], str(s["fecha"]),
            s.get("descripcion", ""), obs,
            s["solicitante_nombre"], s["solicitante_id"],
            u["nombre"], adjuntos_email,
        )
    except Exception:
        pass
    flash("Vuelo coordinado. El solicitante fue notificado.", "success")
    return redirect(url_for("planificador.planificador_solicitudes"))


# ─────────────────────────────────────────────────────────────
# Vuelo: solicitante confirma que realizó el vuelo → PENDIENTE_LIQUIDACION
# ─────────────────────────────────────────────────────────────

@planificador_bp.route("/solicitudes/<int:sid>/vuelo/marcar-realizado", methods=["POST"],
                       endpoint="planificador_vuelo_marcar_realizado")
@require_login
def vuelo_marcar_realizado(sid):
    u = _current_user()
    ctx = svc.get_user_context(u["id"], u["rol"])
    s = repo.get_solicitud_by_id(sid)
    if not s or not svc.puede_marcar_realizado_vuelo(s, u["id"], ctx):
        abort(403)
    repo.marcar_realizado_vuelo(sid, u["id"], u["nombre"])
    try:
        notif.notif_vuelo_pendiente_liquidacion(
            sid, s["area_solicitante"], str(s["fecha"]),
            s["solicitante_nombre"], s["coordinador_id"],
            s["coordinador_nombre"],
        )
    except Exception:
        pass
    flash("Vuelo marcado como realizado. El coordinador registrará los costos.", "success")
    return redirect(url_for("planificador.planificador_solicitudes"))


# ─────────────────────────────────────────────────────────────
# Vuelo: coordinador ingresa costos por tipo → COMPLETADA + deducción presupuesto
# ─────────────────────────────────────────────────────────────

@planificador_bp.route("/solicitudes/<int:sid>/vuelo/liquidar", methods=["POST"],
                       endpoint="planificador_vuelo_liquidar")
@require_login
def vuelo_liquidar(sid):
    from datetime import date as _date
    u = _current_user()
    ctx = svc.get_user_context(u["id"], u["rol"])
    s = repo.get_solicitud_by_id(sid)
    if not s or not svc.puede_liquidar_vuelo(s, u["id"], ctx):
        abort(403)

    notas = request.form.get("notas_liquidacion", "").strip()

    # Leer costos por tipo de gasto (campos tipo_costo[NombreTipo])
    tipos_gasto = repo.get_tipos_gasto()
    costos_por_tipo = {}
    costo_real = 0.0
    for tipo in tipos_gasto:
        val_str = request.form.get(f"tipo_costo_{tipo}", "").strip().replace(",", ".")
        try:
            val = float(val_str) if val_str else 0.0
        except ValueError:
            val = 0.0
        if val > 0:
            costos_por_tipo[tipo] = val
            costo_real += val

    if costo_real <= 0:
        flash("Debe ingresar al menos un costo mayor a cero.", "warning")
        return redirect(url_for("planificador.planificador_solicitudes"))

    desglose = ", ".join(f"{t}: ${v:,.2f}" for t, v in costos_por_tipo.items())
    notas_full = f"{desglose}\n{notas}".strip() if notas else desglose
    repo.liquidar_vuelo(sid, u["id"], u["nombre"], costo_real, notas_full)

    # Deducir del presupuesto por tipo de gasto
    if s.get("centro_costo_id"):
        try:
            empresa_id = repo.get_empresa_by_usuario(s["solicitante_id"])
            if empresa_id:
                hoy = _date.today()
                for tipo, costo in costos_por_tipo.items():
                    repo.deducir_presupuesto_vuelo(
                        empresa_id, s["centro_costo_id"], tipo,
                        hoy.year, hoy.month, costo
                    )
        except Exception as exc:
            current_app.logger.warning("[VUELO] Error al deducir presupuesto sid=%s: %s", sid, exc)

    # Notificar al coordinador y al solicitante
    try:
        notif.notif_vuelo_liquidada(
            sid, s["area_solicitante"], str(s["fecha"]),
            s["solicitante_nombre"], s["solicitante_id"],
            u["nombre"], costo_real, notas,
        )
    except Exception:
        pass

    flash("Vuelo completado y costos registrados. El presupuesto fue actualizado.", "success")
    return redirect(url_for("planificador.planificador_solicitudes"))


# ─────────────────────────────────────────────────────────────
# Adjuntos de solicitudes
# ─────────────────────────────────────────────────────────────

@planificador_bp.route("/solicitudes/<int:sid>/adjuntos/subir", methods=["POST"],
                       endpoint="planificador_adjunto_subir")
@require_login
def adjunto_subir(sid):
    import os, uuid
    from werkzeug.utils import secure_filename

    u = _current_user()
    s = repo.get_solicitud_by_id(sid)
    if not s:
        abort(404)

    # Solo se puede subir archivos si la solicitud ya fue coordinada (no PENDIENTE_COORDINACION)
    if s["estado"] == "PENDIENTE_COORDINACION":
        flash("Solo se pueden adjuntar archivos a solicitudes ya coordinadas.", "warning")
        return redirect(url_for("planificador.planificador_solicitudes"))

    # Solo el solicitante, coordinadores, aprobadores, gerentes y admin
    ctx = svc.get_user_context(u["id"], u["rol"])
    es_involucrado = (
        ctx["es_admin"]
        or ctx["es_gerente"]
        or ctx["tipos_coordinador"]
        or ctx["tipos_aprobador"]
        or s["solicitante_id"] == u["id"]
    )
    if not es_involucrado:
        abort(403)

    archivo = request.files.get("adjunto")
    if not archivo or not archivo.filename:
        flash("No se seleccionó ningún archivo.", "warning")
        return redirect(url_for("planificador.planificador_solicitudes"))

    archivo.seek(0, 2)
    tamano = archivo.tell()
    archivo.seek(0)
    if tamano > 5 * 1024 * 1024:
        flash("El archivo supera el límite de 5 MB.", "warning")
        return redirect(url_for("planificador.planificador_solicitudes"))

    nombre_original = secure_filename(archivo.filename)
    ext = os.path.splitext(nombre_original)[1]
    nombre_guardado = f"{uuid.uuid4().hex}{ext}"

    carpeta = os.path.join(current_app.config["UPLOAD_FOLDER"], "planificador", str(sid))
    os.makedirs(carpeta, exist_ok=True)
    archivo.save(os.path.join(carpeta, nombre_guardado))

    repo.insert_adjunto(sid, nombre_original, nombre_guardado, tamano, u["id"], u["nombre"])
    flash("Archivo adjuntado correctamente.", "success")
    return redirect(url_for("planificador.planificador_solicitudes"))


@planificador_bp.route("/adjuntos/<int:aid>/eliminar", methods=["POST"],
                       endpoint="planificador_adjunto_eliminar")
@require_login
def adjunto_eliminar(aid):
    import os

    u = _current_user()
    adj = repo.get_adjunto_by_id(aid)
    if not adj:
        abort(404)

    ctx = svc.get_user_context(u["id"], u["rol"])
    estado = adj["estado"]
    puede = ctx["es_admin"] or estado not in ("APROBADA", "COMPLETADA")
    if not puede:
        flash("No se puede eliminar archivos de solicitudes aprobadas o completadas.", "warning")
        return redirect(url_for("planificador.planificador_solicitudes"))

    ruta = os.path.join(
        current_app.config["UPLOAD_FOLDER"], "planificador",
        str(adj["solicitud_id"]), adj["nombre_guardado"]
    )
    try:
        os.remove(ruta)
    except OSError:
        pass

    repo.delete_adjunto(aid)
    flash("Archivo eliminado.", "info")
    return redirect(url_for("planificador.planificador_solicitudes"))


@planificador_bp.route("/solicitudes/<int:sid>/adjuntos/<nombre>",
                       endpoint="planificador_adjunto_descargar")
@require_login
def adjunto_descargar(sid, nombre):
    import os
    from flask import send_from_directory

    u = _current_user()
    s = repo.get_solicitud_by_id(sid)
    if not s:
        abort(404)

    ctx = svc.get_user_context(u["id"], u["rol"])
    es_involucrado = (
        ctx["es_admin"] or ctx["es_gerente"]
        or ctx["tipos_coordinador"] or ctx["tipos_aprobador"]
        or s["solicitante_id"] == u["id"]
    )
    if not es_involucrado:
        abort(403)

    carpeta = os.path.join(current_app.config["UPLOAD_FOLDER"], "planificador", str(sid))
    return send_from_directory(carpeta, nombre, as_attachment=True)


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
        elif rol_config not in (ROL_COORDINADOR, ROL_APROBADOR, ROL_MOTORIZADO, ROL_GERENTE_PRESUPUESTO):
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
        roles_config=[ROL_COORDINADOR, ROL_APROBADOR, ROL_MOTORIZADO, ROL_GERENTE_PRESUPUESTO],
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
# Presupuesto
# ─────────────────────────────────────────────────────────────

@planificador_bp.route("/presupuesto", methods=["GET"], endpoint="planificador_presupuesto")
@require_login
@require_permission(PERM_PRESUPUESTO, "ver")
def presupuesto():
    from datetime import date as _date
    anio_actual = _date.today().year
    anio = int(request.args.get("anio", anio_actual))
    empresa_id = request.args.get("empresa_id", type=int)
    tipo_gasto = request.args.get("tipo_gasto", "")

    tipos_gasto = repo.get_tipos_gasto()

    from modules.db import get_db
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, razon_social FROM empresas WHERE activo=1 ORDER BY razon_social")
    empresas = [{"id": r[0], "nombre": r[1]} for r in cur.fetchall()]

    # Centros de costo: param_group "Centro de Costo"
    # No se filtra por activo porque la mayoría están marcados como inactivos en param_values
    cur.execute("""
        SELECT pv.id, pv.nombre, COALESCE(pv.valor, '') AS codigo
        FROM param_values pv
        JOIN param_groups pg ON pg.id = pv.group_id
        WHERE pg.nombre = 'Centro de Costo'
        ORDER BY pv.valor, pv.nombre
    """)
    centros_disponibles = [{"id": r[0], "nombre": r[1], "codigo": r[2]}
                           for r in cur.fetchall()]

    def _build_cc_rows(empresa_id, tipo, anio, cur):
        cur.execute("""
            SELECT DISTINCT p.centro_costo_id, pv.nombre AS cc_nombre,
                   COALESCE(pv.valor, '') AS cc_codigo
            FROM planificador_presupuesto p
            JOIN param_values pv ON pv.id = p.centro_costo_id
            WHERE p.empresa_id = ? AND p.anio = ? AND p.tipo_gasto = ?
            ORDER BY cc_codigo, cc_nombre
        """, (empresa_id, anio, tipo))
        centros = [{"id": r[0], "nombre": r[1], "codigo": r[2]} for r in cur.fetchall()]
        rows = []
        for cc in centros:
            cur.execute("""
                SELECT mes, monto_presupuestado, monto_ejecutado
                FROM planificador_presupuesto
                WHERE empresa_id=? AND centro_costo_id=? AND tipo_gasto=? AND anio=?
            """, (empresa_id, cc["id"], tipo, anio))
            by_mes = {r[0]: {"mes": r[0], "monto_presupuestado": float(r[1]),
                              "monto_ejecutado": float(r[2])}
                      for r in cur.fetchall()}
            meses_data = [by_mes.get(m, {"mes": m, "monto_presupuestado": 0.0,
                                          "monto_ejecutado": 0.0})
                          for m in range(1, 13)]
            total_presup = sum(m["monto_presupuestado"] for m in meses_data)
            total_ejec   = sum(m["monto_ejecutado"]     for m in meses_data)
            pct = round(total_ejec / total_presup * 100, 1) if total_presup > 0 else 0
            semaforo = "rojo" if pct >= 100 else ("amarillo" if pct >= 50 else "verde")
            rows.append({
                "cc_id": cc["id"], "cc_nombre": cc["nombre"], "cc_codigo": cc["codigo"],
                "meses": meses_data, "total_presup": total_presup,
                "total_ejec": total_ejec, "pct": pct, "semaforo": semaforo,
            })
        return rows

    # presupuesto_secciones: lista de {tipo_gasto, rows}
    presupuesto_secciones = []
    if empresa_id:
        tipos_a_mostrar = tipos_gasto if not tipo_gasto else [tipo_gasto]
        for t in tipos_a_mostrar:
            rows = _build_cc_rows(empresa_id, t, anio, cur)
            if rows or tipo_gasto:  # si es "Todos" omite secciones vacías
                presupuesto_secciones.append({"tipo": t, "rows": rows})

    return render_template(
        "planificador/presupuesto.html",
        anio=anio,
        presupuesto_secciones=presupuesto_secciones,
        anio_actual=anio_actual,
        empresas=empresas,
        empresa_id=empresa_id,
        tipos_gasto=tipos_gasto,
        tipo_gasto=tipo_gasto,
        centros_disponibles=centros_disponibles,
        meses_nombres=["Ene","Feb","Mar","Abr","May","Jun",
                        "Jul","Ago","Sep","Oct","Nov","Dic"],
    )


@planificador_bp.route("/presupuesto/guardar", methods=["POST"],
                       endpoint="planificador_presupuesto_guardar")
@require_login
@require_permission(PERM_PRESUPUESTO, "editar")
def presupuesto_guardar():
    empresa_id = request.form.get("empresa_id", type=int)
    cc_id = request.form.get("cc_id", type=int)
    tipo_gasto = request.form.get("tipo_gasto", "")
    anio = request.form.get("anio", type=int)

    if not (empresa_id and cc_id and tipo_gasto and anio):
        flash("Datos incompletos.", "danger")
        return redirect(url_for("planificador.planificador_presupuesto"))

    for mes in range(1, 13):
        raw = request.form.get(f"mes_{mes}", "0").replace(",", ".")
        try:
            monto = float(raw)
        except ValueError:
            monto = 0.0
        repo.upsert_presupuesto(empresa_id, cc_id, tipo_gasto, anio, mes, monto)

    flash("Presupuesto guardado correctamente.", "success")
    return redirect(url_for(
        "planificador.planificador_presupuesto",
        anio=anio, empresa_id=empresa_id, tipo_gasto=tipo_gasto,
    ))


# ─────────────────────────────────────────────────────────────
# Registro
# ─────────────────────────────────────────────────────────────

def register_planificador_routes(app):
    app.register_blueprint(planificador_bp)
