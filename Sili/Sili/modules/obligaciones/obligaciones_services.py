# -*- coding: utf-8 -*-

import calendar
import json
import os
import time
import uuid
from datetime import date, datetime, timedelta

from flask import abort, current_app, request
from werkzeug.utils import secure_filename

from . import obligaciones_repository as repo
from modules.empresas import empresas_repository as empresas_repo
from .obligaciones_constants import (
    ROLES_ADMIN,
    ROL_JEFE_AREA,
    ESTADO_LABELS,
    EXTENSIONES,
    MAX_BYTES,
    MAX_MB,
    ENTIDAD_ALIAS,
    FRECUENCIA_EXCEL_MAP,
    ESTADO_EXCEL_MAP,
    RECALCULO_TIPOS,
    TRIGGER_TIPOS,
    MAX_NOTIFICACIONES_POR_FRECUENCIA,
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


def get_usuarios_combo():
    return repo.list_usuarios_combo()


def get_subordinados_combo(jefe_id):
    return repo.list_subordinados(jefe_id)


def collect_filters(args):
    get = lambda k: (args.get(k) or "").strip()
    return {
        "tipo_id":           get("tipo_id"),
        "empresa_id":        get("empresa_id"),
        "entidad_id":        get("entidad_id"),
        "frecuencia_id":     get("frecuencia_id"),
        "fecha_vencimiento": get("fecha_vencimiento"),
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
        "comentario":  sanear_formula(get("comentario")) or None,
    }


def validate_obligacion_data(data):
    if not data.get("tipo_id"):
        return False, "El tipo es obligatorio."
    if not data.get("empresa_id"):
        return False, "La empresa es obligatoria."
    if not data.get("descripcion"):
        return False, "La descripción es obligatoria."
    if len(data["descripcion"]) > 500:
        return False, "La descripción no puede superar los 500 caracteres."
    if data.get("comentario") and len(data["comentario"]) > 1000:
        return False, "El comentario no puede superar los 1000 caracteres."
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

    return True, None


def crear_obligacion(form, session):
    data = normalize_obligacion_form(form)
    ok, err = validate_obligacion_data(data)
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
        "id":              get("id"),
        "empresa_id":      get("empresa_id"),
        "tipo_id":         get("tipo_id"),
        "entidad_id":      get("entidad_id"),
        "departamento_id": get("departamento_id"),
        "frecuencia_id":   get("frecuencia_id"),
        "anio":            get("anio"),
        "estado":          get("estado"),
        "usuario_id":      get("usuario_id"),
    }


def list_historial(user_id, rol, filters):
    return repo.list_historial(user_id, rol, filters)


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

            destinatarios = [d["email"] for d in notif.get("destinatarios") or [] if d.get("email")]
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


# ==================================================================
# Fase 7 -- Carga masiva de Excel
# ==================================================================
def _carga_masiva_tmp_folder():
    """2026-07-13 (T8): fuera de static/, igual que get_obligaciones_upload_folder."""
    base = current_app.config.get("OBLIGACIONES_UPLOAD_FOLDER")
    if not base:
        base = os.path.join(current_app.root_path, "uploads_privado", "obligaciones")
    folder = os.path.join(base, "_carga_masiva_tmp")
    os.makedirs(folder, exist_ok=True)
    return folder


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


def _parse_fecha_excel(valor):
    if valor is None or valor == "":
        return None
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    texto = str(valor).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(texto, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _resolver_entidad(nombre_raw, entidades_lookup):
    key = (nombre_raw or "").strip().lower()
    key = ENTIDAD_ALIAS.get(key, key)
    return entidades_lookup.get(key)


def _procesar_fila_excel(row, tipos_lookup, empresas_lookup, entidades_lookup, frecuencias_lookup):
    errores = []

    tipo_raw      = str(row[0] or "").strip() if len(row) > 0 else ""
    empresa_raw   = str(row[1] or "").strip() if len(row) > 1 else ""
    descripcion   = sanear_formula(str(row[2] or "").strip()) if len(row) > 2 else ""
    entidad_raw   = str(row[3] or "").strip() if len(row) > 3 else ""
    usuario_raw   = str(row[4] or "").strip() if len(row) > 4 else ""
    fecha_raw     = row[5] if len(row) > 5 else None
    frecuencia_raw = str(row[6] or "").strip() if len(row) > 6 else ""
    estado_raw    = str(row[7] or "").strip() if len(row) > 7 else ""

    tipo_id = tipos_lookup.get(tipo_raw.lower())
    if not tipo_id:
        errores.append(f"Tipo no encontrado: '{tipo_raw}'")

    empresa_id = empresas_lookup.get(empresa_raw.lower())
    if not empresa_id:
        errores.append(f"Empresa no encontrada: '{empresa_raw}'")

    entidad_id = _resolver_entidad(entidad_raw, entidades_lookup)
    if not entidad_id:
        errores.append(f"Entidad no encontrada: '{entidad_raw}'")

    if not descripcion:
        errores.append("Descripción vacía")

    usuario = repo.get_usuario_by_username(usuario_raw) if usuario_raw else None
    if not usuario:
        errores.append(f"Usuario no encontrado (login): '{usuario_raw}'")

    # 2026-07-15 (Corrección #3): frecuencia se resuelve contra el `nombre`
    # real de oblig_frecuencias (tabla propia, ya no param_values).
    frecuencia_nombre = FRECUENCIA_EXCEL_MAP.get(frecuencia_raw.strip().lower())
    frecuencia_info = frecuencias_lookup.get(frecuencia_nombre) if frecuencia_nombre else None
    if not frecuencia_info:
        errores.append(f"Frecuencia no reconocida: '{frecuencia_raw}'")
    frecuencia_id = frecuencia_info["id"] if frecuencia_info else None
    recalculo_tipo = frecuencia_info["recalculo_tipo"] if frecuencia_info else None

    estado = ESTADO_EXCEL_MAP.get(estado_raw.strip().lower(), "por_presentar")

    fecha_vencimiento = _parse_fecha_excel(fecha_raw)
    if frecuencia_info and recalculo_tipo != "NINGUNA" and not fecha_vencimiento:
        errores.append("Fecha de vencimiento obligatoria para esta frecuencia")
    if recalculo_tipo == "NINGUNA":
        fecha_vencimiento = None

    departamento_id = usuario["departamento_id"] if usuario else None
    puesto_id = usuario["puesto_id"] if usuario else None

    return {
        "tipo_raw": tipo_raw, "empresa_raw": empresa_raw, "descripcion": descripcion,
        "entidad_raw": entidad_raw, "usuario_raw": usuario_raw,
        "fecha_vencimiento": fecha_vencimiento, "frecuencia_raw": frecuencia_raw,
        "estado_raw": estado_raw,
        "tipo_id": tipo_id, "empresa_id": empresa_id, "entidad_id": entidad_id,
        "usuario_id": usuario["id"] if usuario else None,
        "departamento_id": departamento_id, "puesto_id": puesto_id,
        "frecuencia_id": frecuencia_id, "estado": estado,
        "errores": errores, "valido": not errores,
    }


def procesar_carga_masiva_preview(file_storage, session):
    """Lee el Excel, arma preview de filas validas/invalidas y guarda las validas
    en un archivo temporal (server-side) identificado por un token -- no se inserta
    nada en la BD todavia."""
    import openpyxl

    if not file_storage or not (file_storage.filename or "").strip():
        return {"ok": False, "flash": ("Adjunte un archivo Excel (.xlsx).", "danger")}

    try:
        wb = openpyxl.load_workbook(file_storage.stream, data_only=True)
        ws = wb.active
    except Exception:
        current_app.logger.exception("Error al leer Excel de carga masiva")
        return {"ok": False, "flash": ("No se pudo leer el archivo. Verifique que sea un .xlsx válido.", "danger")}

    tipos_lookup      = {(r["nombre"] or "").strip().lower(): r["id"] for r in repo.list_tipos()}
    # 2026-07-13: empresas viene del catalogo existente `empresas`, no de oblig_empresas (eliminada)
    empresas_activas  = empresas_repo.list_empresas({"q": "", "activo": "1"})
    empresas_lookup   = {(r["razon_social"] or "").strip().lower(): r["id"] for r in empresas_activas}
    entidades_lookup  = {(r["nombre"] or "").strip().lower(): r["id"] for r in repo.list_entidades()}
    frecuencias_lookup = {
        (r["nombre"] or "").strip().lower(): {
            "id": r["id"],
            "recalculo_tipo": r["recalculo_tipo"],
        }
        for r in repo.list_frecuencias()
    }

    filas = []
    for idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if row is None or all(c is None for c in row):
            continue
        fila = _procesar_fila_excel(row, tipos_lookup, empresas_lookup, entidades_lookup, frecuencias_lookup)
        fila["excel_row"] = idx
        filas.append(fila)

    if not filas:
        return {"ok": False, "flash": ("El archivo no contiene filas de datos.", "warning")}

    validas = [f for f in filas if f["valido"]]
    token = None
    if validas:
        token = uuid.uuid4().hex
        tmp_path = os.path.join(_carga_masiva_tmp_folder(), f"{token}.json")
        payload = {"usuario_id": session.get("usuario_id"), "filas": validas}
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)

    return {
        "ok": True,
        "filas": filas,
        "total": len(filas),
        "validas": len(validas),
        "invalidas": len(filas) - len(validas),
        "token": token,
    }


def confirmar_carga_masiva(token, session):
    """Lee las filas validas guardadas por el token y las inserta en un solo
    lote con rollback total si cualquiera falla."""
    if not token:
        return {"ok": False, "flash": ("No hay datos de carga masiva pendientes.", "warning")}

    tmp_path = os.path.join(_carga_masiva_tmp_folder(), f"{token}.json")
    if not os.path.exists(tmp_path):
        return {"ok": False, "flash": ("La sesión de carga masiva expiró. Vuelva a subir el archivo.", "warning")}

    try:
        with open(tmp_path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except Exception:
        current_app.logger.exception("Error al leer JSON temporal de carga masiva")
        return {"ok": False, "flash": ("No se pudieron leer los datos temporales de la carga.", "danger")}

    if payload.get("usuario_id") != session.get("usuario_id"):
        return {"ok": False, "flash": ("No tiene permiso para confirmar esta carga masiva.", "danger")}

    filas = payload.get("filas") or []
    if not filas:
        return {"ok": False, "flash": ("No hay filas válidas para importar.", "warning")}

    creado_por = session.get("usuario_id")
    conn = repo.get_connection()

    try:
        insertados = 0
        for fila in filas:
            data = {
                "tipo_id":           fila["tipo_id"],
                "empresa_id":        fila["empresa_id"],
                "descripcion":       fila["descripcion"],
                "entidad_id":        fila["entidad_id"],
                "departamento_id":   fila["departamento_id"],
                "puesto_id":         fila["puesto_id"],
                "usuario_id":        fila["usuario_id"],
                "fecha_vencimiento": fila["fecha_vencimiento"],
                "frecuencia_id":     fila["frecuencia_id"],
                "estado":            fila["estado"],
                "comentario":        None,
                "creado_por":        creado_por,
            }
            repo.insert_no_commit(data)
            insertados += 1
        conn.commit()
    except Exception:
        conn.rollback()
        current_app.logger.exception("Error al insertar lote de carga masiva")
        return {
            "ok": False,
            "approved_count": 0,
            "skipped_count": 0,
            "failed_count": len(filas),
            "flash": (f"Error en la carga masiva, no se importó nada ({len(filas)} fila(s) con error).", "danger"),
        }
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass

    return {
        "ok": True,
        "approved_count": insertados,
        "skipped_count": 0,
        "failed_count": 0,
        "flash": (f"Se importaron {insertados} obligaciones.", "success"),
    }


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
    }


ESTADO_ETIQUETAS = {
    "atrasado": "Atrasado",
    "cumplido": "Cumplido",
    "cumplido_fuera_plazo": "Cumplido fuera de plazo",
    "activa": "Activa",
}


def _por_empresa_estado_a_chart(filas):
    """Transforma [{empresa, estado, total}, ...] al shape de Chart.js para
    un bar chart agrupado (un dataset por estado, un label por empresa)."""
    empresas = []
    for f in filas:
        if f["empresa"] not in empresas:
            empresas.append(f["empresa"])

    estados_presentes = []
    for f in filas:
        if f["estado"] not in estados_presentes:
            estados_presentes.append(f["estado"])
    # orden fijo cuando esten presentes, para colores/leyenda consistentes
    orden = ["atrasado", "cumplido", "cumplido_fuera_plazo", "activa"]
    estados = [e for e in orden if e in estados_presentes] + \
              [e for e in estados_presentes if e not in orden]

    totales = {(f["empresa"], f["estado"]): f["total"] for f in filas}
    datasets = [
        {
            "label": ESTADO_ETIQUETAS.get(estado, estado),
            "estado": estado,
            "data": [totales.get((empresa, estado), 0) for empresa in empresas],
        }
        for estado in estados
    ]
    return {"labels": empresas, "datasets": datasets}


def dashboard_data(user_id, rol, filters):
    kpis = repo.dashboard_kpis(rol, user_id, filters)

    # Base incluye atrasadas: una obligacion atrasada (aun abierta) cuenta como
    # incumplimiento para el % de cumplimiento, igual que las cerradas fuera de plazo.
    total_base = kpis["a_tiempo"] + kpis["fuera_plazo"] + kpis["total_atrasadas"]
    pct_a_tiempo = round((kpis["a_tiempo"] / total_base) * 100, 1) if total_base else 0.0
    pct_fuera_plazo = round(((kpis["fuera_plazo"] + kpis["total_atrasadas"]) / total_base) * 100, 1) if total_base else 0.0

    es_admin = rol in ROLES_ADMIN
    por_empresa_estado = repo.dashboard_por_empresa_estado(rol, user_id, filters) if es_admin else []

    return {
        "kpis": kpis,
        "pct_a_tiempo": pct_a_tiempo,
        "pct_fuera_plazo": pct_fuera_plazo,
        "por_estado":     repo.dashboard_por_estado(rol, user_id, filters),
        "por_tipo":       repo.dashboard_por_tipo(rol, user_id, filters),
        "por_empresa":    repo.dashboard_por_empresa(rol, user_id, filters) if es_admin else [],
        "por_empresa_estado": _por_empresa_estado_a_chart(por_empresa_estado),
        "por_frecuencia": repo.dashboard_por_frecuencia(rol, user_id, filters),
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
        destinatarios = [safe_int(u) for u in form.getlist(f"notif_{i}_destinatarios")]
        notificaciones.append({
            "orden":         i,
            "tipo_trigger":  tipo_trigger,
            "dias_antes":    safe_int(form.get(f"notif_{i}_dias_antes")),
            "dia_fijo_mes":  safe_int(form.get(f"notif_{i}_dia_fijo_mes")),
            "destinatarios": [u for u in destinatarios if u],
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
