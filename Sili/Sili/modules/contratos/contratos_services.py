from __future__ import annotations

import os
import time
from typing import Any

from flask import current_app, flash, request, session
from werkzeug.utils import secure_filename

from modules.db import get_db

from .contratos_constants import (
    CAMPO_ARCHIVOS_PDF,
    ESTADOS_GARANTIA_VALIDOS,
    MAPA_TIPO_PP_AMIGABLE,
    PGALLEGOS_FALLBACK_EMAIL_DEFAULT,
    REQ_CONTRATO_LABEL_ANIO,
    REQ_CONTRATO_LABEL_FECHA_SUSCRIPCION,
    REQ_CONTRATO_LABEL_OBJETO,
    REQ_CONTRATO_LABEL_PEDIDO,
    REQ_CONTRATO_LABEL_PROVEEDOR,
    REQ_CONTRATO_LABEL_USUARIO_SOLICITANTE,
    REQ_CONTRATO_LABEL_VALOR_CONTRATO,
    REQ_GARANTIA_LABEL_CONTRATO,
    REQ_GARANTIA_LABEL_ESTADO,
    REQ_GARANTIA_LABEL_FECHA_SUSCRIPCION,
    REQ_GARANTIA_LABEL_FECHA_VENCIMIENTO,
    REQ_GARANTIA_LABEL_REQUIERE_RENOVACION,
    REQ_GARANTIA_LABEL_TIPO,
    STATUS_NO_APROBADO,
    TIPO_AMBOS,
    TIPOS_GARANTIA_VALIDOS,
)
from .contratos_security import rowget, session_dept_id, session_user_id
from . import contratos_notifications as notifications
from . import contratos_repository as repository


def bool_to_int(v) -> int:
    if isinstance(v, (int, float)):
        return 1 if v else 0
    s = (str(v or "")).strip().lower()
    return 1 if s in ("1", "true", "t", "y", "yes", "si", "sí") else 0


def normalize_date(s: str | None) -> str | None:
    v = (s or "").strip()
    if not v:
        return None
    if "-" in v and len(v) >= 8:
        return v[:10]
    parts = v.replace(".", "/").split("/")
    if len(parts) == 3 and len(parts[2]) == 4:
        d, m, y = parts
        return f"{y}-{int(m):02d}-{int(d):02d}"
    return v


def safe_int(x):
    try:
        return int(x) if x is not None and str(x).strip() != "" else None
    except Exception:
        return None


def safe_float(x, default: float = 0.0) -> float:
    try:
        return float(str(x).replace(",", ""))
    except Exception:
        return default


def ensure_contratos_columns() -> None:
    return


def ensure_garantias_columns() -> None:
    return


def ensure_softdelete_columns() -> None:
    return


def ensure_aprob_gf_columns() -> None:
    return


def ensure_contrato_archivos_table() -> None:
    return


def get_contratos_upload_folder() -> str:
    base = current_app.config.get("CONTRATOS_UPLOAD_FOLDER")
    if not base:
        base = os.path.join(current_app.root_path, "uploads", "contratos")
    os.makedirs(base, exist_ok=True)
    return base


def save_contrato_pdfs(contrato_id: int) -> None:
    files = request.files.getlist(CAMPO_ARCHIVOS_PDF)
    if not files:
        return

    ensure_contrato_archivos_table()
    folder = get_contratos_upload_folder()

    for f in files:
        if not f or (f.filename or "").strip() == "":
            continue

        original = f.filename.strip()
        _, ext = os.path.splitext(original)
        ext = ext.lower()
        if ext != ".pdf":
            flash(f"El archivo '{original}' no se guardó porque no es un PDF.", "warning")
            continue

        safe_name = secure_filename(original)
        final_name = f"{contrato_id}_{int(time.time())}_{safe_name}"
        file_path = os.path.join(folder, final_name)
        f.save(file_path)
        repository.insert_archivo_contrato(contrato_id, final_name, original)


def resolve_usuario_compras_nombre(fila: Any) -> str:
    uid = None
    if "usuario_compras_id" in fila.keys() and fila["usuario_compras_id"]:
        uid = fila["usuario_compras_id"]
    elif "creado_por" in fila.keys() and fila["creado_por"]:
        uid = fila["creado_por"]

    if uid:
        nombre = repository.fetch_usuario_nombre_por_id(uid)
        if nombre:
            return nombre

    txt = (fila["usuario_compras_nombre"] or "").strip() if "usuario_compras_nombre" in fila.keys() else ""
    if txt and txt.lower() != "actual":
        return txt

    uid_now = session_user_id()
    if uid_now:
        nombre_now = repository.fetch_usuario_nombre_por_id(uid_now)
        if nombre_now:
            return nombre_now

    return txt


def contrato_editable(row_db) -> bool:
    tiene_aprob_jefe = int((row_db["aprobado_jefe"] or 0) if "aprobado_jefe" in row_db.keys() else 0)
    tiene_aprob = int((row_db["aprobado"] or 0) if "aprobado" in row_db.keys() else 0)
    tiene_aprob_gf = int((row_db["aprob_gf"] or 0) if "aprob_gf" in row_db.keys() else 0)
    return not (tiene_aprob_jefe or tiene_aprob or tiene_aprob_gf)


def garantia_editable(row_db) -> bool:
    tiene_aprob_jefe = int((row_db["aprobado_jefe"] or 0) if "aprobado_jefe" in row_db.keys() else 0)
    tiene_aprob = int((row_db["aprobado"] or 0) if "aprobado" in row_db.keys() else 0)
    tiene_aprob_gf = int((row_db["aprob_gf"] or 0) if "aprob_gf" in row_db.keys() else 0)
    return not (tiene_aprob_jefe or tiene_aprob or tiene_aprob_gf)


def get_compras_combos():
    return repository.fetch_usuarios_combo(), repository.fetch_proveedores_combo()


def get_row_create_contrato_default():
    row = {}
    uid_actual = session_user_id()
    if uid_actual:
        nombre = repository.fetch_usuario_nombre_por_id(uid_actual)
        if nombre:
            row["usuario_compras_nombre"] = nombre
    return row


def get_contrato_for_edit(contrato_id: int):
    row_db = repository.fetch_contrato_por_id(contrato_id)
    if not row_db:
        return None, None, None

    row = dict(row_db)
    row["proveedor_id"] = repository.fetch_proveedor_id_por_nombre(row.get("proveedor"))
    archivos = repository.fetch_archivos_contrato(row_db["id"])
    return row_db, row, archivos


def get_garantia_for_edit(garantia_id: int):
    row_db = repository.fetch_garantia_activa_por_id(garantia_id)
    if not row_db:
        return None, None, None

    contratos = repository.list_contratos_aprobados_sin_garantia(limit=200, include_id=row_db["contrato_id"])
    ensure_contrato_archivos_table()
    archivos = repository.fetch_archivos_contrato(row_db["contrato_id"])
    return row_db, contratos, archivos


def parse_contrato_form():
    usuario_solicitante_id = safe_int(request.form.get("usuario_solicitante_id"))

    usuario_compras_nombre = (request.form.get("usuario_compras_nombre") or "").strip()
    if not usuario_compras_nombre or usuario_compras_nombre.lower() == "actual":
        uid_actual = session_user_id()
        if uid_actual:
            nombre = repository.fetch_usuario_nombre_por_id(uid_actual)
            if nombre:
                usuario_compras_nombre = nombre

    usuario_compras_id = session_user_id()
    creado_por = session_user_id()
    departamento_id = session_dept_id()

    anio = (request.form.get("anio") or "").strip()
    pedido = (request.form.get("pedido") or "").strip()
    tipo_pp = TIPO_AMBOS

    prov_id = safe_int(request.form.get("proveedor_id"))
    proveedor = repository.fetch_proveedor_nombre_por_id(prov_id)
    if not proveedor:
        proveedor = (request.form.get("proveedor") or "").strip()

    objeto = (request.form.get("objeto") or request.form.get("objeto_contrato") or "").strip()
    valor_contrato = safe_float(request.form.get("valor_contrato"))
    valor_anticipo = safe_float(request.form.get("valor_anticipo"))

    fecha_suscripcion = normalize_date(request.form.get("fecha_suscripcion"))
    fecha_terminacion = normalize_date(request.form.get("fecha_terminacion"))
    plazo_dias = int((request.form.get("plazo_dias") or "0") or 0)
    cronograma_pagos = (request.form.get("cronograma_pagos") or "").strip()
    fecha_entrega_compras = normalize_date(request.form.get("fecha_entrega_compras"))
    fecha_firma_gerencia = normalize_date(request.form.get("fecha_firma_gerencia"))
    fecha_entrega_finanzas_sumilla = normalize_date(
        request.form.get("fecha_entrega_finanzas_sumilla")
        or request.form.get("fecha_entrega_a_finanzas_sumilla")
    )
    fecha_entrega_originales_fin = normalize_date(
        request.form.get("fecha_entrega_originales_finanzas")
        or request.form.get("fecha_entrega_originales_a_finanzas")
    )
    fechas_pago_anticipo = (request.form.get("fechas_pago_anticipo") or "").strip()
    fecha_entrega_pedido = normalize_date(request.form.get("fecha_entrega_pedido"))
    observaciones = (request.form.get("observaciones") or "").strip()

    return {
        "anio": anio,
        "pedido": pedido,
        "tipo_pp": tipo_pp,
        "prov_id": prov_id,
        "proveedor": proveedor,
        "objeto": objeto,
        "valor_contrato": valor_contrato,
        "valor_anticipo": valor_anticipo,
        "fecha_suscripcion": fecha_suscripcion,
        "fecha_terminacion": fecha_terminacion,
        "plazo_dias": plazo_dias,
        "cronograma_pagos": cronograma_pagos,
        "fecha_entrega_compras": fecha_entrega_compras,
        "fecha_firma_gerencia": fecha_firma_gerencia,
        "fecha_entrega_finanzas_sumilla": fecha_entrega_finanzas_sumilla,
        "fecha_entrega_originales_fin": fecha_entrega_originales_fin,
        "fechas_pago_anticipo": fechas_pago_anticipo,
        "fecha_entrega_pedido": fecha_entrega_pedido,
        "observaciones": observaciones,
        "usuario_solicitante_id": usuario_solicitante_id,
        "usuario_compras_nombre": usuario_compras_nombre,
        "usuario_compras_id": usuario_compras_id,
        "departamento_id": departamento_id,
        "creado_por": creado_por,
    }


def validate_contrato_payload(data: dict):
    missing_required = []
    if not data["anio"]:
        missing_required.append(REQ_CONTRATO_LABEL_ANIO)
    if not data["pedido"]:
        missing_required.append(REQ_CONTRATO_LABEL_PEDIDO)
    if not data["usuario_solicitante_id"]:
        missing_required.append(REQ_CONTRATO_LABEL_USUARIO_SOLICITANTE)
    if not data["objeto"]:
        missing_required.append(REQ_CONTRATO_LABEL_OBJETO)
    if data["valor_contrato"] is None or data["valor_contrato"] <= 0:
        missing_required.append(REQ_CONTRATO_LABEL_VALOR_CONTRATO)
    if not data["fecha_suscripcion"]:
        missing_required.append(REQ_CONTRATO_LABEL_FECHA_SUSCRIPCION)
    if not data["proveedor"]:
        missing_required.append(REQ_CONTRATO_LABEL_PROVEEDOR)

    if missing_required:
        return False, "Campos obligatorios incompletos: " + ", ".join(missing_required)

    if (data["valor_contrato"] or 0) > 0 and (data["valor_anticipo"] or 0) > data["valor_contrato"]:
        return False, "El valor del anticipo no puede ser mayor que el valor del contrato."

    if not repository.exists_usuario(data["usuario_solicitante_id"]):
        return False, "Revisa IDs relacionados: Usuario solicitante inexistente"

    return True, ""


def make_contrato_row_back(data: dict):
    return {
        "anio": data["anio"],
        "pedido": data["pedido"],
        "proveedor": data["proveedor"],
        "proveedor_id": data.get("prov_id"),
        "objeto": data["objeto"],
        "valor_contrato": data["valor_contrato"],
        "valor_anticipo": data["valor_anticipo"],
        "fecha_suscripcion": data["fecha_suscripcion"],
        "fecha_terminacion": data["fecha_terminacion"],
        "plazo_dias": data["plazo_dias"],
        "cronograma_pagos": data["cronograma_pagos"],
        "fecha_entrega_compras": data["fecha_entrega_compras"],
        "fecha_firma_gerencia": data["fecha_firma_gerencia"],
        "fecha_entrega_finanzas_sumilla": data["fecha_entrega_finanzas_sumilla"],
        "fecha_entrega_originales_fin": data["fecha_entrega_originales_fin"],
        "fechas_pago_anticipo": data["fechas_pago_anticipo"],
        "fecha_entrega_pedido": data["fecha_entrega_pedido"],
        "observaciones": data["observaciones"],
        "usuario_solicitante_id": data["usuario_solicitante_id"],
        "usuario_compras_nombre": data["usuario_compras_nombre"],
    }


def create_contrato_from_request():
    data = parse_contrato_form()
    ok, mensaje = validate_contrato_payload(data)
    if not ok:
        return {"ok": False, "message": mensaje, "row_back": make_contrato_row_back(data)}

    nuevo_contrato_id = repository.insert_contrato(
        (
            int(data["anio"]) if data["anio"] else None,
            data["pedido"],
            data["proveedor"],
            data["objeto"],
            data["valor_contrato"],
            data["valor_anticipo"],
            data["tipo_pp"],
            data["fecha_suscripcion"],
            data["fecha_terminacion"],
            data["plazo_dias"],
            data["cronograma_pagos"],
            data["fecha_entrega_compras"],
            data["fecha_firma_gerencia"],
            data["fecha_entrega_finanzas_sumilla"],
            data["fecha_entrega_originales_fin"],
            data["fechas_pago_anticipo"],
            data["fecha_entrega_pedido"],
            data["observaciones"],
            STATUS_NO_APROBADO,
            data["usuario_solicitante_id"],
            data["usuario_compras_nombre"],
            data["usuario_compras_id"],
            data["departamento_id"],
            data["creado_por"],
        )
    )

    save_contrato_pdfs(nuevo_contrato_id)

    notifications.notify_contrato_registrado(
        contrato_id=nuevo_contrato_id,
        pedido=data["pedido"],
        proveedor=data["proveedor"],
        objeto=data["objeto"],
        valor_contrato=data["valor_contrato"],
        fecha_suscripcion=data["fecha_suscripcion"],
        usuario_solicitante_id=data["usuario_solicitante_id"],
        usuario_compras_id=data["usuario_compras_id"],
        usuario_compras_nombre=data["usuario_compras_nombre"],
    )

    return {"ok": True, "contrato_id": nuevo_contrato_id}


def update_contrato_from_request(contrato_id: int):
    data = parse_contrato_form()
    ok, mensaje = validate_contrato_payload(data)
    if not ok:
        return {"ok": False, "message": mensaje, "row_back": make_contrato_row_back(data)}

    usuario_compras_id = safe_int(request.form.get("usuario_compras_id")) or safe_int(session.get("usuario_id"))
    if usuario_compras_id and not repository.exists_usuario(usuario_compras_id):
        usuario_compras_id = None

    repository.update_contrato(
        (
            safe_int(data["anio"]),
            data["pedido"],
            data["proveedor"],
            data["objeto"],
            data["valor_contrato"],
            data["valor_anticipo"],
            data["fecha_suscripcion"],
            data["fecha_terminacion"],
            data["plazo_dias"],
            data["cronograma_pagos"],
            data["fecha_entrega_compras"],
            data["fecha_firma_gerencia"],
            data["fecha_entrega_finanzas_sumilla"],
            data["fecha_entrega_originales_fin"],
            data["fechas_pago_anticipo"],
            data["fecha_entrega_pedido"],
            data["observaciones"],
            data["usuario_solicitante_id"],
            usuario_compras_id,
            contrato_id,
        )
    )

    save_contrato_pdfs(contrato_id)
    return {"ok": True}


def soft_delete_contrato(contrato_id: int):
    repository.soft_delete_contrato(contrato_id)


def parse_garantia_form():
    contrato_id = safe_int(request.form.get("contrato_id"))
    tipo = (request.form.get("tipo") or request.form.get("pagare_poliza") or "").strip().upper()
    if tipo == "PAGARÉ":
        tipo = "PAGARE"

    compania_emisora = (request.form.get("compania_emisora") or "").strip()
    monto_poliza = safe_float(request.form.get("monto_poliza"))
    fecha_suscripcion = normalize_date(request.form.get("fecha_suscripcion"))
    fecha_vencimiento = normalize_date(request.form.get("fecha_vencimiento"))
    fecha_vencimiento_actualizada = normalize_date(request.form.get("fecha_vencimiento_actualizada"))
    vigencia_dias = safe_int(request.form.get("vigencia_dias")) or 0
    estado = (request.form.get("estado") or "").strip() or "Vigente"
    fecha_renovacion = normalize_date(request.form.get("fecha_renovacion"))
    requiere_renovacion = bool_to_int(request.form.get("requiere_renovacion"))
    observaciones = (request.form.get("observaciones") or "").strip()
    status_interno = (request.form.get("status_interno") or "").strip()

    return {
        "contrato_id": contrato_id,
        "tipo": tipo,
        "compania_emisora": compania_emisora,
        "monto_poliza": monto_poliza,
        "fecha_suscripcion": fecha_suscripcion,
        "fecha_vencimiento": fecha_vencimiento,
        "fecha_vencimiento_actualizada": fecha_vencimiento_actualizada,
        "vigencia_dias": vigencia_dias,
        "estado": estado,
        "fecha_renovacion": fecha_renovacion,
        "requiere_renovacion": requiere_renovacion,
        "observaciones": observaciones,
        "status_interno": status_interno,
    }


def validate_garantia_payload(data: dict):
    missing = []
    if not data["contrato_id"]:
        missing.append(REQ_GARANTIA_LABEL_CONTRATO)
    if data["tipo"] not in TIPOS_GARANTIA_VALIDOS:
        missing.append(REQ_GARANTIA_LABEL_TIPO)
    if not data["fecha_suscripcion"]:
        missing.append(REQ_GARANTIA_LABEL_FECHA_SUSCRIPCION)
    if not data["fecha_vencimiento"]:
        missing.append(REQ_GARANTIA_LABEL_FECHA_VENCIMIENTO)
    if data["estado"] not in ESTADOS_GARANTIA_VALIDOS:
        missing.append(REQ_GARANTIA_LABEL_ESTADO)
    if request.form.get("requiere_renovacion") in ("", None):
        missing.append(REQ_GARANTIA_LABEL_REQUIERE_RENOVACION)
    if data["contrato_id"] and not repository.exists_contrato(data["contrato_id"]):
        missing.append("Contrato inexistente")

    if missing:
        return False, "Campos obligatorios incompletos: " + ", ".join(missing)
    return True, ""


def make_garantia_row_back(data: dict):
    return dict(
        contrato_id=data["contrato_id"],
        tipo=data["tipo"],
        compania_emisora=data["compania_emisora"],
        monto_poliza=data["monto_poliza"],
        fecha_suscripcion=data["fecha_suscripcion"],
        fecha_vencimiento=data["fecha_vencimiento"],
        fecha_vencimiento_actualizada=data["fecha_vencimiento_actualizada"],
        vigencia_dias=data["vigencia_dias"],
        estado=data["estado"],
        fecha_renovacion=data["fecha_renovacion"],
        requiere_renovacion=data["requiere_renovacion"],
        observaciones=data["observaciones"],
        status_interno=data["status_interno"],
    )


def create_garantia_from_request():
    data = parse_garantia_form()
    ok, mensaje = validate_garantia_payload(data)
    if not ok:
        return {"ok": False, "message": mensaje, "row_back": make_garantia_row_back(data)}

    nueva_garantia_id = repository.insert_garantia(
        (
            data["contrato_id"],
            data["tipo"],
            data["compania_emisora"],
            data["monto_poliza"],
            data["fecha_suscripcion"],
            data["fecha_vencimiento"],
            data["fecha_vencimiento_actualizada"],
            data["vigencia_dias"],
            data["estado"],
            data["fecha_renovacion"],
            data["requiere_renovacion"],
            data["status_interno"],
            data["observaciones"],
        )
    )

    save_contrato_pdfs(data["contrato_id"])

    contrato = repository.fetch_contrato_por_id(data["contrato_id"])
    notifications.notify_garantia_ingresada(
        garantia_id=nueva_garantia_id,
        contrato_id=data["contrato_id"],
        pedido=contrato["pedido"],
        proveedor=contrato["proveedor"],
        objeto=contrato["objeto"],
        usuario_solicitante_id=contrato["usuario_solicitante_id"],
        usuario_compras_id=contrato["usuario_compras_id"],
        usuario_compras_nombre=contrato["usuario_compras_nombre"],
        aprobado_jefe_por=contrato["aprobado_jefe_por"],
    )

    return {"ok": True, "garantia_id": nueva_garantia_id}


def update_garantia_from_request(garantia_id: int, contrato_id: int):
    data = parse_garantia_form()
    ok, mensaje = validate_garantia_payload(data)
    if not ok:
        return {"ok": False, "message": mensaje, "row_back": make_garantia_row_back(data)}

    repository.update_garantia(
        (
            data["tipo"],
            data["compania_emisora"],
            data["monto_poliza"],
            data["fecha_suscripcion"],
            data["fecha_vencimiento"],
            data["fecha_vencimiento_actualizada"],
            data["vigencia_dias"],
            data["estado"],
            data["fecha_renovacion"],
            data["requiere_renovacion"],
            data["status_interno"],
            data["observaciones"],
            garantia_id,
        )
    )

    save_contrato_pdfs(contrato_id)
    return {"ok": True}


def soft_delete_garantia(garantia_id: int):
    repository.soft_delete_garantia(garantia_id)


def get_requiere_renovacion_filter(raw: str):
    raw = (raw or "").strip().lower()
    if raw in ("si", "sí", "1", "true"):
        return 1
    if raw in ("no", "0", "false"):
        return 0
    return None


def get_aprobacion_filters():
    prov = (request.args.get("proveedor") or "").strip()
    pedi = (request.args.get("pedido") or "").strip()
    tipo = (request.args.get("tipo_pp") or "").strip().upper()
    estado = (request.args.get("estado") or "").strip()
    renov = (request.args.get("renovacion") or "").strip()
    renov_int = None
    if renov in ("0", "1"):
        renov_int = int(renov)
    return prov, pedi, tipo, estado, renov_int


def build_contrato_vista(fila):
    def _fmt_money(x):
        try:
            return "${:,.2f}".format(float(x or 0))
        except Exception:
            return ""

    proveedor = fila["proveedor"] or ""
    usuario_solicitante = repository.fetch_usuario_nombre_por_id(fila["usuario_solicitante_id"])
    usuario_compras = resolve_usuario_compras_nombre(fila)

    tipo_pp = MAPA_TIPO_PP_AMIGABLE.get(
        (fila["tipo_rp" if "tipo_rp" in fila.keys() else "tipo_pp"] or "").upper(),
        fila["tipo_rp" if "tipo_rp" in fila.keys() else "tipo_pp"],
    )

    def _yn(b):
        return "Sí" if int(b or 0) else "No"

    aprobado_jef = int(rowget(fila, "aprobado_jefe", 0) or 0) or ((rowget(fila, "status_interno", "") or "") == "Aprobado")
    aprobado_ger = int(rowget(fila, "aprobado", 0) or 0)
    aprobado_gf = int(rowget(fila, "aprob_gf", 0) or 0)

    vista = [
        ("Año", fila["anio"]),
        ("Pedido", fila["pedido"]),
        ("Proveedor", proveedor),
        ("Objeto del contrato", fila["objeto"]),
        ("Valor contrato", _fmt_money(fila["valor_contrato"])),
        ("Valor anticipo", _fmt_money(fila["valor_anticipo"])),
        ("Pagaré / Póliza", tipo_pp),
        ("Fecha de suscripción", fila["fecha_suscripcion"]),
        ("Fecha de terminación", fila["fecha_terminacion"]),
        ("Plazo (días)", fila["plazo_dias"]),
        ("Cronograma de pagos", fila["cronograma_pagos"]),
        ("Fecha entrega a Compras", fila["fecha_entrega_compras"]),
        ("Fecha firma de Gerencia", fila["fecha_firma_gerencia"]),
        ("Fecha de entrega a Finanzas (Sumilla)", fila["fecha_entrega_finanzas_sumilla"]),
        ("Fecha entrega originales a Finanzas", fila["fecha_entrega_originales_fin"]),
        ("Fechas de pago de anticipo", fila["fechas_pago_anticipo"]),
        ("Fecha de entrega de pedido", fila["fecha_entrega_pedido"]),
        ("Usuario solicitante", usuario_solicitante),
        ("Usuario de Compras", usuario_compras),
        ("Observaciones", fila["observaciones"]),
        ("Aprobación jefatura", _yn(aprobado_jef)),
        ("Aprobación gerencial", _yn(aprobado_ger)),
        ("Aprobación Gerencia Financiera (Final)", _yn(aprobado_gf)),
    ]

    archivos = repository.fetch_archivos_contrato_asc(fila["id"])
    return vista, proveedor, archivos


def build_garantia_vista(g):
    def _fmt_money(x):
        try:
            return "${:,.2f}".format(float(x or 0))
        except Exception:
            return ""

    c = repository.fetch_contrato_por_id(g["contrato_id"])
    pedido = c["pedido"] if c else ""
    proveedor = c["proveedor"] if c else ""

    tipo = (g["tipo"] or "").upper()
    tipo_amig = "Pagaré" if tipo in ("PAGARE", "PAGARÉ") else ("Póliza" if tipo == "POLIZA" else g["tipo"])

    def _yn(b):
        return "Sí" if int(b or 0) else "No"

    aprobado_jef = int(rowget(g, "aprobado_jefe", 0) or 0) or ((rowget(g, "status_interno", "") or "") == "Aprobado")
    aprobado_ger = int(rowget(g, "aprobado", 0) or 0)
    aprobado_gf = int(rowget(g, "aprob_gf", 0) or 0)

    vista = [
        ("Contrato (pedido)", pedido),
        ("Proveedor", proveedor),
        ("Pagaré / Póliza", tipo_amig),
        ("Compañía emisora de póliza", g["compania_emisora"]),
        ("Monto de póliza", _fmt_money(g["monto_poliza"])),
        ("Vigencia (días)", g["vigencia_dias"]),
        ("Fecha de suscripción", g["fecha_suscripcion"]),
        ("Fecha de vencimiento", g["fecha_vencimiento"]),
        ("Fecha vencimiento actualizada", g["fecha_vencimiento_actual"]),
        ("Estado de garantía", g["estado"]),
        ("Fecha de renovación de póliza", g["fecha_renovacion"]),
        ("Requiere renovación", _yn(g["requiere_renovacion"])),
        ("Observaciones", g["observaciones"]),
        ("Aprobación jefatura", _yn(aprobado_jef)),
        ("Aprobación gerencial", _yn(aprobado_ger)),
        ("Aprobación Gerencia Financiera (Final)", _yn(aprobado_gf)),
    ]
    return vista, pedido, proveedor


def toggle_jefe_contrato(contrato_id: int, usuario_id: int | None):
    fila = repository.fetch_contrato_por_id(contrato_id)
    if not fila:
        return None

    nuevo = 0 if int(fila["aprobado_jefe"] or 0) else 1
    status_txt = "Aprobado" if nuevo == 1 else "No aprobado"

    repository.toggle_aprobacion_jefe_contrato(contrato_id, nuevo, usuario_id, status_txt)

    fila2 = repository.fetch_contrato_por_id(contrato_id)
    notifications.notify_toggle_aprobacion_jefe_contrato(
        contrato_id=contrato_id,
        pedido=fila2["pedido"],
        proveedor=fila2["proveedor"],
        objeto=fila2["objeto"],
        valor_contrato=fila2["valor_contrato"],
        usuario_solicitante_id=fila2["usuario_solicitante_id"],
        usuario_compras_id=fila2["usuario_compras_id"],
        usuario_compras_nombre=fila2["usuario_compras_nombre"],
        aprobado_jefe_por=fila2["aprobado_jefe_por"],
        aprobado_jefe=int(fila2["aprobado_jefe"] or 0),
    )
    return nuevo


def toggle_jefe_garantia(garantia_id: int, usuario_id: int | None):
    fila = repository.fetch_garantia_activa_por_id(garantia_id)
    if not fila:
        return None

    nuevo = 0 if int(fila["aprobado_jefe"] or 0) else 1
    status_txt = "Aprobado" if nuevo == 1 else "No aprobado"
    repository.toggle_aprobacion_jefe_garantia(garantia_id, nuevo, usuario_id, status_txt)
    return nuevo


def toggle_aprobar_contrato(contrato_id: int, usuario_id: int | None):
    fila = repository.fetch_contrato_por_id(contrato_id)
    if not fila:
        return None

    new_val = 0 if int(fila["aprobado"] or 0) else 1
    repository.toggle_aprobacion_contrato(contrato_id, new_val, usuario_id)

    if int(new_val) == 1 and repository.existe_garantia_aprobada_activa_por_contrato(contrato_id):
        contrato = repository.fetch_contrato_por_id(contrato_id)
        notifications.notify_pendiente_gf(
            contrato_id=contrato_id,
            pedido=contrato["pedido"],
            proveedor=contrato["proveedor"],
            objeto=contrato["objeto"],
            usuario_solicitante_id=contrato["usuario_solicitante_id"],
            usuario_compras_id=contrato["usuario_compras_id"],
            usuario_compras_nombre=contrato["usuario_compras_nombre"],
            aprobado_jefe_por=contrato["aprobado_jefe_por"],
        )

    return new_val


def toggle_aprobar_garantia(garantia_id: int, usuario_id: int | None):
    fila = repository.fetch_garantia_activa_por_id(garantia_id)
    if not fila:
        return None

    new_val = 0 if int(fila["aprobado"] or 0) else 1
    repository.toggle_aprobacion_garantia(garantia_id, new_val, usuario_id)

    if int(new_val) == 1:
        contrato = repository.fetch_contrato_por_id(fila["contrato_id"])
        notifications.notify_pendiente_gf(
            contrato_id=fila["contrato_id"],
            pedido=contrato["pedido"],
            proveedor=contrato["proveedor"],
            objeto=contrato["objeto"],
            usuario_solicitante_id=contrato["usuario_solicitante_id"],
            usuario_compras_id=contrato["usuario_compras_id"],
            usuario_compras_nombre=contrato["usuario_compras_nombre"],
            aprobado_jefe_por=contrato["aprobado_jefe_por"],
        )

    return new_val


def toggle_aprobacion_gf(contrato_id: int, valor: int):
    repository.toggle_aprobacion_gf_contrato_y_garantias(contrato_id, valor)

    if int(valor) == 1:
        contrato = repository.fetch_contrato_por_id(contrato_id)
        notifications.notify_aprobacion_final_gf(
            contrato_id=contrato_id,
            pedido=contrato["pedido"],
            proveedor=contrato["proveedor"],
            objeto=contrato["objeto"],
            usuario_solicitante_id=contrato["usuario_solicitante_id"],
            usuario_compras_id=contrato["usuario_compras_id"],
            usuario_compras_nombre=contrato["usuario_compras_nombre"],
            aprobado_jefe_por=contrato["aprobado_jefe_por"],
        )