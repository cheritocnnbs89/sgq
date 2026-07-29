# -*- coding: utf-8 -*-

import calendar
import os
import time
from datetime import date, datetime, timedelta

from flask import abort, current_app, request
from werkzeug.utils import secure_filename

from . import obligaciones_repository as repo
from .obligaciones_constants import (
    ROLES_ADMIN,
    ROL_JEFE_AREA,
    ESTADO_LABELS,
    EXTENSIONES,
    MAX_BYTES,
    MAX_MB,
    RECALCULO_TIPOS,
    TRIGGER_TIPOS,
    MAX_NOTIFICACIONES_POR_FRECUENCIA,
    TIPO_DESTINATARIO_JERARQUICOS,
    MSG_CADENA_ROTA,
)


# ==================================================================
# Helpers genericos
# ==================================================================
def safe_int(val, default=None):
    try:
        return int(val) if val not in (None, "") else default
    except (ValueError, TypeError):
        return default


def _puede_gestionar(row, session):
    """Dueno o admin puede editar/eliminar/cumplir. jefe_area_obligaciones es solo lectura (T2)."""
    rol = session.get("rol")
    if rol in ROLES_ADMIN:
        return True
    if rol == ROL_JEFE_AREA:
        return False
    return row is not None and row["usuario_id"] == session.get("usuario_id")


def assert_puede_acceder_obligacion(obligacion, session):
    """T2 (Correccion de arquitectura #5, 2026-07-20): IDOR fix -- reusa la
    MISMA logica de scope de _apply_visibility() (obligaciones_repository.py)
    pero para UN registro puntual en vez de un WHERE de listado. admin/
    admin_obligaciones sin filtro; jefe_area_obligaciones solo si el dueno de
    la obligacion tiene jefe_id == usuario actual; cualquier otro rol
    (usuario_obligaciones incluido) solo si es el dueno. abort(403) si no
    cumple -- se llama al INICIO de las rutas de un solo registro, antes de
    leer/escribir cualquier dato."""
    rol = session.get("rol")
    if rol in ROLES_ADMIN:
        return
    if rol == ROL_JEFE_AREA:
        perfil = repo.get_usuario_perfil(obligacion["usuario_id"])
        if perfil and perfil["jefe_id"] == session.get("usuario_id"):
            return
        abort(403)
    if obligacion["usuario_id"] == session.get("usuario_id"):
        return
    abort(403)


def _puede_ver_evidencia(row, session):
    """T8: dueno/admin siempre; jefe_area_obligaciones solo si el dueno es su subordinado directo."""
    if _puede_gestionar(row, session):
        return True
    if session.get("rol") == ROL_JEFE_AREA:
        perfil = repo.get_usuario_perfil(row["usuario_id"])
        return bool(perfil and perfil["jefe_id"] == session.get("usuario_id"))
    return False


def _to_date(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _add_months(d, months):
    m = d.month - 1 + months
    y = d.year + m // 12
    m = m % 12 + 1
    day = min(d.day, calendar.monthrange(y, m)[1])
    return date(y, m, day)


def _add_years(d, years):
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        return d.replace(month=2, day=28, year=d.year + years)


def _siguiente_fecha(fecha_venc, recalculo_tipo, recalculo_cantidad):
    """2026-07-15 (Corrección #3): ya no se parsea un string "M:6" -- lee
    directo las 2 columnas reales de oblig_frecuencias (recalculo_tipo/
    recalculo_cantidad). Misma lógica de antes, sin partir texto."""
    if not recalculo_tipo or recalculo_tipo == "NINGUNA" or not recalculo_cantidad:
        return fecha_venc

    if recalculo_tipo == "M":
        return _add_months(fecha_venc, recalculo_cantidad)
    if recalculo_tipo == "A":
        return _add_years(fecha_venc, recalculo_cantidad)
    if recalculo_tipo == "D":
        return fecha_venc + timedelta(days=recalculo_cantidad)
    return fecha_venc


# ==================================================================
# Fase 3 -- CRUD principal
# ==================================================================
def get_combos():
    return repo.get_combos()


def get_combos_form():
    # 2026-07-22: combo del formulario Nueva/Editar (todas las empresas activas),
    # distinto del combo de filtros (solo empresas con obligaciones).
    return repo.get_combos_form()


def get_usuarios_combo():
    return repo.list_usuarios_combo()


def list_entidades_por_tipo(tipo_id):
    """2026-07-27: usado por el endpoint AJAX /obligaciones/api/entidades --
    filtro dependiente Tipo -> Entidad en formulario y dashboard/consultas."""
    if not tipo_id:
        return []
    return repo.list_entidades_por_tipo(tipo_id)


def get_subordinados_combo(jefe_id):
    return repo.list_subordinados(jefe_id)


def collect_filters(args):
    get = lambda k: (args.get(k) or "").strip()
    return {
        "tipo_id":           get("tipo_id"),
        "empresa_id":        get("empresa_id"),
        "entidad_id":        get("entidad_id"),
        "frecuencia_id":     get("frecuencia_id"),
        "fecha_desde":       get("fecha_desde"),
        "fecha_hasta":       get("fecha_hasta"),
        "usuario_id":        get("usuario_id"),
        "estado":            get("estado"),
    }


def list_obligaciones(user_id, rol, filters):
    rows = repo.list_obligaciones(user_id, rol, filters)
    for r in rows:
        fv = r.get("fecha_vencimiento")
        r["dias_restantes"] = (fv - date.today()).days if fv else None
    return rows


def get_item(oblig_id):
    return repo.get_by_id(oblig_id)


def normalize_obligacion_form(form):
    get = lambda k: (form.get(k) or "").strip()
    return {
        "tipo_id":     safe_int(get("tipo_id")),
        "empresa_id":  safe_int(get("empresa_id")),
        "descripcion": sanear_formula(get("descripcion")),
        "entidad_id":  safe_int(get("entidad_id")),
        "fecha_vencimiento": get("fecha_vencimiento") or None,
        "frecuencia_id": safe_int(get("frecuencia_id")),
    }


def validate_obligacion_data(data):
    if not data.get("tipo_id"):
        return False, "El tipo es obligatorio."
    if not data.get("empresa_id"):
        return False, "La empresa es obligatoria."
    if not data.get("descripcion"):
        return False, "La descripción es obligatoria."
    if len(data["descripcion"]) < 25:
        return False, "La descripción debe tener al menos 25 caracteres."
    if len(data["descripcion"]) > 200:
        return False, "La descripción no puede superar los 200 caracteres."
    if not data.get("entidad_id"):
        return False, "La entidad reguladora es obligatoria."
    if not data.get("frecuencia_id"):
        return False, "La frecuencia es obligatoria."

    frecuencia = repo.get_frecuencia_by_id(data["frecuencia_id"])
    if not frecuencia:
        return False, "Frecuencia inválida."

    if frecuencia["recalculo_tipo"] == "NINGUNA":
        data["fecha_vencimiento"] = None
    elif not data.get("fecha_vencimiento"):
        return False, "La fecha de vencimiento es obligatoria para esta frecuencia."
    else:
        fecha_venc = _to_date(data["fecha_vencimiento"])
        if fecha_venc is None:
            return False, "La fecha de vencimiento no es válida."
        if fecha_venc < date.today():
            return False, "La fecha de vencimiento no puede ser anterior a hoy."

    return True, None


# ------------------------------------------------------------
# Validación bloqueante de cadena de jefe (2026-07-22)
# Si la frecuencia elegida tiene destinatarios jerárquicos 'jefe'/'gerente',
# la cadena de jefe del CREADOR (usuario actual) debe poder resolverse al
# momento de crear/editar; si no, se bloquea el guardado y se avisa por correo.
# ------------------------------------------------------------
def _frecuencia_requiere_cadena(frecuencia_id):
    """(needs_jefe, needs_gerente) según los tipos jerárquicos configurados."""
    notifs = repo.list_notificaciones_con_destinatarios(frecuencia_id)
    tipos = {d.get("tipo") for n in notifs for d in (n.get("destinatarios") or [])}
    return ("jefe" in tipos), ("gerente" in tipos)


def _notificar_cadena_rota(perfil, frecuencia_id, faltantes):
    """Envía el correo técnico (creador + admin_obligaciones) explicando qué
    eslabón de la cadena de jefe falta. Nunca rompe el flujo del request."""
    try:
        from modules.email_utils import send_email_async
        frecuencia = repo.get_frecuencia_by_id(frecuencia_id)
        frec_nombre = frecuencia["nombre"] if frecuencia else f"ID {frecuencia_id}"
        nombre = (perfil["nombre_completo"] or perfil["username"]) if perfil else "desconocido"
        detalle = "; ".join(faltantes)
        subject = "[Obligaciones] Cadena de notificación incompleta"
        message = "\n".join([
            "Aviso automático del módulo Obligaciones Legales y Regulatorias.",
            "",
            f"El usuario \"{nombre}\" intentó crear/editar una obligación con la "
            f"frecuencia \"{frec_nombre}\", que notifica a destinatarios jerárquicos "
            "(jefe directo y/o gerente del área).",
            "",
            f"Problema detectado: {detalle}.",
            "",
            "Por este motivo la obligación NO se pudo guardar. Para habilitarla, "
            "asigne el jefe directo (campo jefe_id) del usuario en la administración "
            "de usuarios del sistema.",
            "",
            "-- Este correo es automático, generado por el Sistema de Gestión Quimpac (SGQ). "
            "Por favor no responda a este mensaje.",
        ])
        destinatarios = []
        if perfil and perfil["email"]:
            destinatarios.append(perfil["email"])
        destinatarios.extend(repo.list_admin_obligaciones_emails())
        destinatarios = list(dict.fromkeys(d for d in destinatarios if d))
        if destinatarios:
            send_email_async(destinatarios, subject, message)
    except Exception:
        current_app.logger.exception("Obligaciones: no se pudo enviar aviso de cadena de jefe rota")


def validar_cadena_frecuencia(frecuencia_id, session):
    """Devuelve (True, None) si la frecuencia no requiere cadena jerárquica o la
    cadena del usuario actual se puede resolver; (False, MSG_CADENA_ROTA) si está
    rota (y dispara el correo técnico). Mensaje en pantalla genérico a propósito."""
    if not frecuencia_id:
        return True, None
    needs_jefe, needs_gerente = _frecuencia_requiere_cadena(frecuencia_id)
    if not (needs_jefe or needs_gerente):
        return True, None

    creador_id = session.get("usuario_id")
    perfil = repo.get_usuario_perfil(creador_id)
    jefe_id = perfil["jefe_id"] if perfil else None
    jefe = repo.get_usuario_perfil(jefe_id) if jefe_id else None
    gerente_id = jefe["jefe_id"] if jefe else None

    faltantes = []
    if (needs_jefe or needs_gerente) and not jefe_id:
        faltantes.append(
            f"el usuario (id={creador_id}) no tiene un jefe directo asignado (campo jefe_id)"
        )
    if needs_gerente and jefe_id and not gerente_id:
        faltantes.append(
            "el jefe directo del usuario no tiene a su vez un jefe asignado, "
            "por lo que no se puede determinar el gerente del área"
        )

    if not faltantes:
        return True, None

    _notificar_cadena_rota(perfil, frecuencia_id, faltantes)
    return False, MSG_CADENA_ROTA


def crear_obligacion(form, session):
    data = normalize_obligacion_form(form)
    ok, err = validate_obligacion_data(data)
    if not ok:
        return {"ok": False, "flash": (err, "warning"), "data": data}

    ok, err = validar_cadena_frecuencia(data.get("frecuencia_id"), session)
    if not ok:
        return {"ok": False, "flash": (err, "warning"), "data": data}

    usuario_id = session.get("usuario_id")
    perfil = repo.get_usuario_perfil(usuario_id)

    data["usuario_id"] = usuario_id
    data["departamento_id"] = session.get("departamento_id")
    data["puesto_id"] = perfil["puesto_id"] if perfil else None
    data["creado_por"] = usuario_id
    data["estado"] = "por_presentar"

    try:
        new_id = repo.insert(data)
        return {"ok": True, "flash": ("Obligación creada.", "success"), "id": new_id}
    except Exception:
        repo.rollback()
        current_app.logger.exception("Error al crear obligación")
        return {"ok": False, "flash": ("No se pudo crear la obligación.", "danger"), "data": data}


def editar_obligacion(oblig_id, form, session):
    row = repo.get_raw_by_id(oblig_id)
    if not row:
        return {"ok": False, "not_found": True, "flash": ("Obligación no encontrada.", "warning")}
    if not _puede_gestionar(row, session):
        return {"ok": False, "flash": ("No tiene permiso para editar esta obligación.", "danger")}

    data = normalize_obligacion_form(form)
    ok, err = validate_obligacion_data(data)
    if not ok:
        return {"ok": False, "flash": (err, "warning"), "data": data}

    ok, err = validar_cadena_frecuencia(data.get("frecuencia_id"), session)
    if not ok:
        return {"ok": False, "flash": (err, "warning"), "data": data}

    try:
        repo.update(oblig_id, data)
        return {"ok": True, "flash": ("Obligación actualizada.", "success")}
    except Exception:
        repo.rollback()
        current_app.logger.exception("Error al editar obligación")
        return {"ok": False, "flash": ("No se pudo actualizar la obligación.", "danger"), "data": data}


def eliminar_obligacion(oblig_id, session):
    row = repo.get_raw_by_id(oblig_id)
    if not row:
        return {"ok": False, "flash": ("Obligación no encontrada.", "warning")}
    if not _puede_gestionar(row, session):
        return {"ok": False, "flash": ("No tiene permiso para eliminar esta obligación.", "danger")}

    tiene_registros = repo.count_historial_rows(oblig_id) > 0 or repo.count_alertas_rows(oblig_id) > 0
    try:
        if tiene_registros:
            repo.soft_delete(oblig_id)
        else:
            repo.hard_delete(oblig_id)
        return {"ok": True, "flash": ("Obligación eliminada.", "success")}
    except Exception:
        repo.rollback()
        return {"ok": False, "flash": ("No se pudo eliminar: la obligación tiene registros asociados (historial o alertas).", "danger")}


# ==================================================================
# Fase 4 -- Cumplir y evidencias
# ==================================================================
def _uploads_privado_root():
    base = current_app.config.get("OBLIGACIONES_UPLOAD_FOLDER")
    return base or os.path.join(current_app.root_path, "uploads_privado")


def get_obligaciones_upload_folder(oblig_id):
    """2026-07-13 (T8): fuera de static/ -- ya no accesible por URL directa de Flask.
    Se sirve solo via el endpoint autenticado descargar_evidencia (routes)."""
    folder = os.path.join(_uploads_privado_root(), "obligaciones", str(oblig_id))
    os.makedirs(folder, exist_ok=True)
    return folder


# 2026-07-13 (T7): firma binaria real de cada extension permitida -- una extension
# correcta en el nombre no alcanza, el contenido debe coincidir.
_MAGIC_BYTES = {
    "pdf":  (b"%PDF",),
    "jpg":  (b"\xff\xd8\xff",),
    "jpeg": (b"\xff\xd8\xff",),
    "png":  (b"\x89PNG\r\n\x1a\n",),
    "xlsx": (b"PK\x03\x04",),
    "docx": (b"PK\x03\x04",),
}

_EXTENSIONES_PELIGROSAS = {
    "exe", "sh", "bat", "cmd", "js", "php", "vbs", "jar", "msi", "ps1", "com", "scr",
}


def _contenido_coincide_con_extension(f, ext):
    firmas = _MAGIC_BYTES.get(ext)
    if not firmas:
        return True
    f.stream.seek(0)
    head = f.stream.read(8)
    f.stream.seek(0)
    return any(head.startswith(firma) for firma in firmas)


def _tiene_doble_extension_sospechosa(filename):
    """T7: 'acta.pdf.exe' -- el segmento intermedio es tambien una extension conocida
    (permitida o peligrosa), señal de intento de disfrazar el tipo real."""
    partes = filename.rsplit(".", 2)
    if len(partes) < 3:
        return False
    intermedia = partes[1].lower()
    return intermedia in EXTENSIONES or intermedia in _EXTENSIONES_PELIGROSAS


def _validar_archivos(files):
    validos = [f for f in (files or []) if (f.filename or "").strip()]
    if not validos:
        return None, "Debe subir al menos un archivo de evidencia."

    for f in validos:
        filename = f.filename.strip()
        if "." not in filename:
            return None, f"Archivo sin extensión: {filename}"
        if _tiene_doble_extension_sospechosa(filename):
            return None, f"Nombre de archivo sospechoso (doble extensión): {filename}"
        ext = filename.rsplit(".", 1)[1].lower()
        if ext not in EXTENSIONES:
            return None, f"Extensión no permitida ({ext}): {filename}"
        if not _contenido_coincide_con_extension(f, ext):
            return None, f"El contenido del archivo no coincide con su extensión: {filename}"

        f.stream.seek(0, os.SEEK_END)
        size = f.stream.tell()
        f.stream.seek(0)

        if size <= 0:
            return None, f"Archivo vacío: {filename}"
        if size > MAX_BYTES:
            return None, f"El archivo supera los {MAX_MB} MB: {filename}"

    return validos, None


def puede_cumplir(oblig_id, session):
    row = repo.get_raw_by_id(oblig_id)
    if not row:
        return False
    return _puede_gestionar(row, session)


def cumplir_obligacion(oblig_id, form, files, session):
    row = repo.get_raw_by_id(oblig_id)
    if not row:
        return {"ok": False, "flash": ("Obligación no encontrada.", "warning")}
    if not _puede_gestionar(row, session):
        return {"ok": False, "flash": ("No tiene permiso para cumplir esta obligación.", "danger")}
    if row["estado"] in ("cumplido", "cumplido_fuera_plazo"):
        return {"ok": False, "flash": ("Esta obligación ya fue cumplida.", "warning")}

    archivos_validos, err = _validar_archivos(files)
    if not archivos_validos:
        return {"ok": False, "flash": (err, "warning")}

    observacion = sanear_formula((form.get("observacion") or "").strip()) or None
    usuario_id = session.get("usuario_id")

    hoy = date.today()
    fecha_venc = _to_date(row["fecha_vencimiento"])
    fuera_de_plazo = bool(fecha_venc and hoy > fecha_venc)
    estado_final = "cumplido_fuera_plazo" if fuera_de_plazo else "cumplido"

    try:
        folder = get_obligaciones_upload_folder(oblig_id)
        for f in archivos_validos:
            safe_name = secure_filename(f.filename.strip())
            final_name = f"{int(time.time())}_{safe_name}"
            dest = os.path.join(folder, final_name)
            f.save(dest)
            tamanio = os.path.getsize(dest)
            ext = final_name.rsplit(".", 1)[1].lower()
            ruta_relativa = "/".join(["obligaciones", str(oblig_id), final_name])
            repo.insert_evidencia(oblig_id, f.filename.strip(), ruta_relativa, ext, tamanio, usuario_id)

        repo.insert_historial(
            oblig_id, "estado", row["estado"], estado_final, observacion, usuario_id
        )
        repo.marcar_cumplida(oblig_id, estado_final)

        # 2026-07-15 (Corrección #3): "repetitiva" ya no se decide por un `valor`
        # de param_value -- se recalcula si recalculo_tipo de la frecuencia no
        # es NINGUNA (columnas reales en oblig_frecuencias).
        frecuencia = repo.get_frecuencia_by_id(row["frecuencia_id"])
        recalculo_tipo = frecuencia["recalculo_tipo"] if frecuencia else None
        recalculo_cantidad = frecuencia["recalculo_cantidad"] if frecuencia else None
        if recalculo_tipo and recalculo_tipo != "NINGUNA" and fecha_venc:
            nueva_fecha = _siguiente_fecha(fecha_venc, recalculo_tipo, recalculo_cantidad)
            nueva_data = {
                "tipo_id":           row["tipo_id"],
                "empresa_id":        row["empresa_id"],
                "descripcion":       row["descripcion"],
                "entidad_id":        row["entidad_id"],
                "departamento_id":   row["departamento_id"],
                "puesto_id":         row["puesto_id"],
                "usuario_id":        row["usuario_id"],
                "fecha_vencimiento": nueva_fecha.isoformat(),
                "frecuencia_id":     row["frecuencia_id"],
                "estado":            "por_presentar",
                "comentario":        None,
                "creado_por":        row["usuario_id"],
            }
            repo.insert_no_commit(nueva_data)

        repo.commit()
        return {
            "ok": True,
            "flash": (f"Obligación marcada como {ESTADO_LABELS[estado_final]}.", "success"),
        }
    except Exception:
        repo.rollback()
        current_app.logger.exception("Error al cumplir obligación")
        return {"ok": False, "flash": ("No se pudo procesar el cumplimiento.", "danger")}


def descargar_evidencia(oblig_id, evidencia_id, session):
    """T8: valida propiedad/visibilidad, arma la ruta absoluta dentro de
    uploads_privado (nunca fuera), y registra el acceso en auditoria_seguridad."""
    row = repo.get_raw_by_id(oblig_id)
    if not row:
        return {"ok": False, "motivo": "not_found"}
    if not _puede_ver_evidencia(row, session):
        return {"ok": False, "motivo": "forbidden"}

    evidencia = repo.get_evidencia_by_id(evidencia_id, oblig_id)
    if not evidencia:
        return {"ok": False, "motivo": "not_found"}

    root_norm = os.path.normpath(_uploads_privado_root())
    ruta_absoluta = os.path.normpath(os.path.join(root_norm, evidencia["ruta"]))
    if not ruta_absoluta.startswith(root_norm + os.sep):
        current_app.logger.warning(
            "Path traversal bloqueado en descarga de evidencia %s (obligacion %s)",
            evidencia_id, oblig_id,
        )
        return {"ok": False, "motivo": "not_found"}
    if not os.path.isfile(ruta_absoluta):
        return {"ok": False, "motivo": "not_found"}

    try:
        from modules.auth.auth_repository import insertar_auditoria_seguridad
        insertar_auditoria_seguridad(
            usuario_id=session.get("usuario_id"),
            username=session.get("usuario"),
            evento="obligaciones_descarga_evidencia",
            resultado="ok",
            detalle=f"obligacion_id={oblig_id} evidencia_id={evidencia_id} archivo={evidencia['nombre_archivo']}",
            ip=request.remote_addr if request else None,
            user_agent=request.headers.get("User-Agent") if request else None,
            actor_usuario_id=session.get("usuario_id"),
            fecha_evento=datetime.now(),
        )
    except Exception:
        current_app.logger.exception("No se pudo registrar auditoría de descarga de evidencia")

    return {"ok": True, "path": ruta_absoluta, "filename": evidencia["nombre_archivo"]}


# ==================================================================
# Fase 5 -- Historial
# ==================================================================
def collect_historial_filters(args):
    get = lambda k: (args.get(k) or "").strip()
    return {
        "empresa_id":        get("empresa_id"),
        "tipo_id":           get("tipo_id"),
        "entidad_id":        get("entidad_id"),
        "departamento_id":   get("departamento_id"),
        "frecuencia_id":     get("frecuencia_id"),
        "fecha_desde":       get("fecha_desde"),
        "fecha_hasta":       get("fecha_hasta"),
        "estado":            get("estado"),
        "usuario_id":        get("usuario_id"),
    }


def list_historial(user_id, rol, filters):
    rows = repo.list_historial(user_id, rol, filters)
    # 2026-07-22: adjunta las evidencias (id + nombre) de cada obligacion para
    # que el Historial las muestre como enlaces de descarga (ruta autenticada
    # descargar_evidencia), no como texto plano. N+1 aceptable: el historial
    # lista decenas de filas, no miles. ponytail: subir a un solo JOIN agregado
    # si el historial crece mucho.
    for r in rows:
        r["evidencias_list"] = [dict(ev) for ev in repo.list_evidencias(r["id"])]
    return rows


# ==================================================================
# Fase 6 -- soporte para el scheduler (logica reutilizable)
# ==================================================================
def marcar_obligaciones_atrasadas():
    """Tarea A: estado='atrasado' -- NO toca activa (sigue en Consultas)."""
    ids = repo.get_ids_para_marcar_atrasadas()
    total = 0
    for oblig_id in ids:
        repo.marcar_atrasada(oblig_id)
        repo.insert_historial(oblig_id, "estado", None, "atrasado", None, None)
        total += 1
    if ids:
        repo.commit()
    return total


def _periodo_para_regla(fecha_vencimiento):
    """2026-07-14 (Ronda 2): ya no genera 'YYYY-MM'/'YYYY' segun el nombre fijo
    de la frecuencia (ya no existe ese nombre fijo) -- usa la fecha completa como
    clave de periodo, valida para cualquier frecuencia (fija o creada por el usuario)."""
    return fecha_vencimiento.isoformat()


def _dias_hasta_vencimiento(hoy, fecha_vencimiento):
    return (fecha_vencimiento - hoy).days


def _resolver_cadena_creador(creador_id):
    """{creador, jefe, gerente} -> email resuelto en tiempo real para el
    creador de una obligación. Eslabón faltante = None."""
    perfil = repo.get_usuario_perfil(creador_id) if creador_id else None
    cadena = repo.resolver_cadena_jefe(creador_id)
    return {
        "creador": perfil["email"] if perfil else None,
        "jefe":    cadena["jefe_email"],
        "gerente": cadena["gerente_email"],
    }


def _resolver_destinatarios_notif(destinatarios, ob, cadena_cache):
    """Convierte los destinatarios (fijos + jerárquicos) de una notificación en
    una lista de emails, resolviendo creador/jefe/gerente contra el creado_por
    de ESA obligación (siempre actualizado). Un jerárquico no resoluble se
    loguea y se saltea sin romper el envío del resto. Dedup preservando orden."""
    creador_id = ob.get("creado_por")
    emails = []
    for d in destinatarios:
        tipo = d.get("tipo", "fijo")
        if tipo == "fijo":
            if d.get("email"):
                emails.append(d["email"])
            continue
        if creador_id not in cadena_cache:
            cadena_cache[creador_id] = _resolver_cadena_creador(creador_id)
        email = cadena_cache[creador_id].get(tipo)
        if email:
            emails.append(email)
        else:
            current_app.logger.warning(
                "Obligaciones: destinatario '%s' no resoluble para obligacion_id=%s "
                "(creado_por=%s) -- se saltea",
                tipo, ob.get("id"), creador_id,
            )
    return list(dict.fromkeys(emails))


def evaluar_alertas_pendientes():
    """Tarea B (2026-07-15, Corrección #3): para cada obligación activa con
    fecha, lee las notificaciones propias de su frecuencia (oblig_frecuencia_
    notificaciones) junto con sus destinatarios (oblig_notificacion_
    destinatarios) -- ya NO son param_values hijos, y los destinatarios ya
    NO son usuario+jefe fijo, son los usuarios configurados en cada
    notificación. Frecuencias con recalculo_tipo='NINGUNA' no tienen
    notificaciones -> no generan alertas. Devuelve lista de dicts
    {obligacion_id, tipo_alerta, periodo, destinatarios: [email, ...]} listos
    para enviar, ya filtrados de duplicados via oblig_alertas_enviadas."""
    hoy = date.today()
    pendientes = []
    obligaciones = repo.list_obligaciones_para_alertas()

    notificaciones_cache = {}
    cadena_cache = {}  # creado_por -> {creador, jefe, gerente} emails (tiempo real)

    for ob in obligaciones:
        frecuencia_id = ob["frecuencia_id"]

        fecha_venc = _to_date(ob["fecha_vencimiento"])
        if not fecha_venc:
            continue

        if frecuencia_id not in notificaciones_cache:
            notificaciones_cache[frecuencia_id] = repo.list_notificaciones_con_destinatarios(frecuencia_id)
        notificaciones = notificaciones_cache[frecuencia_id]

        for notif in notificaciones:
            disparar = False
            tipo_alerta = None

            if notif["tipo_trigger"] == "dias_antes":
                dias = _dias_hasta_vencimiento(hoy, fecha_venc)
                valor = safe_int(notif.get("dias_antes"))
                if valor is not None and dias == valor:
                    disparar = True
                    tipo_alerta = f"{valor}d"
            elif notif["tipo_trigger"] == "fecha_exacta":
                valor = safe_int(notif.get("dia_fijo_mes"))
                if valor is not None and hoy.day == valor:
                    disparar = True
                    tipo_alerta = "inicio_mes" if valor == 1 else f"dia{valor}"

            if not disparar:
                continue

            destinatarios = _resolver_destinatarios_notif(
                notif.get("destinatarios") or [], ob, cadena_cache
            )
            if not destinatarios:
                continue

            periodo = _periodo_para_regla(fecha_venc)

            if repo.alerta_ya_enviada(ob["id"], tipo_alerta, periodo):
                continue

            pendientes.append({
                "obligacion_id": ob["id"],
                "tipo_alerta":   tipo_alerta,
                "periodo":       periodo,
                "destinatarios": destinatarios,
            })

    return pendientes


def registrar_alerta_enviada(obligacion_id, tipo_alerta, periodo):
    repo.insert_alerta_enviada(obligacion_id, tipo_alerta, periodo)
    repo.commit()


# 2026-07-13 (T6): CSV/Excel formula injection -- un valor de texto libre que
# empieza con = + - @ se interpreta como formula al abrirse en Excel.
_CARACTERES_FORMULA = ("=", "+", "-", "@")


def sanear_formula(valor):
    if valor is None:
        return valor
    texto = str(valor)
    if texto[:1] in _CARACTERES_FORMULA:
        return "'" + texto
    return texto


# ==================================================================
# Fase 10 -- Dashboard
# ==================================================================
def collect_dashboard_filters(args):
    get = lambda k: (args.get(k) or "").strip()
    return {
        "empresa_id":    get("empresa_id"),
        "tipo_id":       get("tipo_id"),
        "entidad_id":    get("entidad_id"),
        "frecuencia_id": get("frecuencia_id"),
        "fecha_desde":   get("fecha_desde"),
        "fecha_hasta":   get("fecha_hasta"),
        # 2026-07-28: agregado filtro usuario_id en Dashboard (admin=todos, jefe_area=solo subordinados)
        "usuario_id":    get("usuario_id"),
    }


def dashboard_data(user_id, rol, filters):
    kpis = repo.dashboard_kpis(rol, user_id, filters)

    # Indicador Cumplidas vs Atrasadas: cumplidas = todas las cerradas (a tiempo
    # + fuera de plazo, sin importar cuando); atrasadas = las que aun no se cumplen
    # y ya vencieron (activa=1 AND estado='atrasado').
    cumplidas = kpis["a_tiempo"] + kpis["fuera_plazo"]
    total_base = cumplidas + kpis["total_atrasadas"]
    pct_cumplidas = round((cumplidas / total_base) * 100, 1) if total_base else 0.0
    pct_atrasadas = round((kpis["total_atrasadas"] / total_base) * 100, 1) if total_base else 0.0

    es_admin = rol in ROLES_ADMIN

    return {
        "kpis": kpis,
        "pct_cumplidas": pct_cumplidas,
        "pct_atrasadas": pct_atrasadas,
        "por_estado":     repo.dashboard_por_estado(rol, user_id, filters),
        "por_tipo":       repo.dashboard_por_tipo(rol, user_id, filters),
        "por_estado_total": repo.dashboard_por_estado_total(rol, user_id, filters) if es_admin else [],
    }


# ==================================================================
# Fase 11 -- Frecuencias y notificaciones (Corrección de arquitectura #3,
# 2026-07-15). Pantalla propia bajo Configuraciones -> Parámetros Generales
# en el menú, pero código/tablas propios de este módulo -- no reutiliza
# modules/parametros_generales por dentro.
# ==================================================================
def list_frecuencias():
    return repo.list_frecuencias()


def get_frecuencia_detalle(frecuencia_id):
    """Frecuencia + sus notificaciones (con destinatarios ya resueltos) --
    usado para prellenar la pantalla de edición."""
    frecuencia = repo.get_frecuencia_by_id(frecuencia_id)
    if not frecuencia:
        return None
    return {
        "frecuencia": frecuencia,
        "notificaciones": repo.list_notificaciones_con_destinatarios(frecuencia_id),
    }


def normalize_frecuencia_form(form):
    get = lambda k: (form.get(k) or "").strip()
    return {
        "nombre":             sanear_formula(get("nombre")),
        "recalculo_tipo":     get("recalculo_tipo") or "NINGUNA",
        "recalculo_cantidad": safe_int(get("recalculo_cantidad")),
    }


def validate_frecuencia_data(data):
    if not data.get("nombre"):
        return False, "El nombre es obligatorio."
    if len(data["nombre"]) > 100:
        return False, "El nombre no puede superar los 100 caracteres."
    if data["recalculo_tipo"] not in RECALCULO_TIPOS:
        return False, "Tipo de recálculo inválido."
    if data["recalculo_tipo"] != "NINGUNA" and not data.get("recalculo_cantidad"):
        return False, "La cantidad es obligatoria para este tipo de recálculo."
    if data["recalculo_tipo"] == "NINGUNA":
        data["recalculo_cantidad"] = None
    return True, None


def normalize_notificaciones_form(form):
    """Lee hasta MAX_NOTIFICACIONES_POR_FRECUENCIA bloques del form
    (notif_<n>_tipo_trigger / _dias_antes / _dia_fijo_mes / _destinatarios[]).
    Un bloque sin tipo_trigger se considera vacío (usuario no lo usó)."""
    notificaciones = []
    for i in range(1, MAX_NOTIFICACIONES_POR_FRECUENCIA + 1):
        tipo_trigger = (form.get(f"notif_{i}_tipo_trigger") or "").strip()
        if not tipo_trigger:
            continue
        # 2026-07-22: destinatarios = usuarios fijos (checkboxes con id) +
        # hasta 3 checkboxes jerárquicos (creador/jefe/gerente, usuario_id NULL).
        destinatarios = [
            {"tipo": "fijo", "usuario_id": uid}
            for uid in (safe_int(u) for u in form.getlist(f"notif_{i}_destinatarios"))
            if uid
        ]
        for tipo in TIPO_DESTINATARIO_JERARQUICOS:
            if form.get(f"notif_{i}_{tipo}"):
                destinatarios.append({"tipo": tipo, "usuario_id": None})
        notificaciones.append({
            "orden":         i,
            "tipo_trigger":  tipo_trigger,
            "dias_antes":    safe_int(form.get(f"notif_{i}_dias_antes")),
            "dia_fijo_mes":  safe_int(form.get(f"notif_{i}_dia_fijo_mes")),
            "destinatarios": destinatarios,
        })
    return notificaciones


def validate_notificaciones_data(notificaciones):
    for n in notificaciones:
        if n["tipo_trigger"] not in TRIGGER_TIPOS:
            return False, "Tipo de notificación inválido."
        if n["tipo_trigger"] == "dias_antes" and not n.get("dias_antes"):
            return False, "Debe indicar los días antes del vencimiento."
        if n["tipo_trigger"] == "fecha_exacta" and not (n.get("dia_fijo_mes") and 1 <= n["dia_fijo_mes"] <= 31):
            return False, "Debe indicar un día válido del mes (1-31)."
        if not n["destinatarios"]:
            return False, "Cada notificación debe tener al menos un destinatario."
    return True, None


def guardar_frecuencia_completa(frecuencia_id, form):
    """Crea o edita una frecuencia junto con sus notificaciones y
    destinatarios en una sola transacción (replace-on-save, ver
    repo.replace_frecuencia_completa)."""
    data = normalize_frecuencia_form(form)
    ok, err = validate_frecuencia_data(data)
    if not ok:
        return {"ok": False, "flash": (err, "warning"), "data": data}

    notificaciones = normalize_notificaciones_form(form)
    ok, err = validate_notificaciones_data(notificaciones)
    if not ok:
        return {"ok": False, "flash": (err, "warning"), "data": data, "notificaciones": notificaciones}

    try:
        new_id = repo.replace_frecuencia_completa(
            frecuencia_id, data["nombre"], data["recalculo_tipo"], data["recalculo_cantidad"], notificaciones
        )
        return {"ok": True, "flash": ("Frecuencia guardada.", "success"), "id": new_id}
    except Exception:
        current_app.logger.exception("Error al guardar frecuencia")
        return {
            "ok": False,
            "flash": ("No se pudo guardar la frecuencia.", "danger"),
            "data": data,
            "notificaciones": notificaciones,
        }


def eliminar_frecuencia(frecuencia_id):
    try:
        repo.soft_delete_frecuencia(frecuencia_id)
        return {"ok": True, "flash": ("Frecuencia eliminada.", "success")}
    except Exception:
        current_app.logger.exception("Error al eliminar frecuencia")
        return {"ok": False, "flash": ("No se pudo eliminar la frecuencia.", "danger")}
