from __future__ import annotations

import time
from typing import Any, List

from modules.db import get_db
import json
from datetime import date
from .contratos_querys import (
    SQL_LISTA_CONTRATOS_APROBADOS_PARA_GARANTIA,
    SQL_USUARIOS_COMBO,
    SQL_PROVEEDORES_COMBO,
    SQL_PROVEEDOR_ACTIVO_POR_ID,
    SQL_PROVEEDOR_ID_POR_NOMBRE,
    SQL_USUARIO_NOMBRE_POR_ID,
    SQL_USUARIO_EMAIL_POR_ID,
    SQL_USUARIO_EMAIL_POR_USERNAME_O_EMAIL,
    SQL_PGALLEGOS_EMAIL,
    SQL_USUARIO_EXISTE_POR_ID,
    SQL_CONTRATO_EXISTE_POR_ID,
    SQL_GARANTIA_EXISTE_POR_ID,
    SQL_CONTRATO_POR_ID,
    SQL_GARANTIA_POR_ID_ACTIVA,
    SQL_GARANTIA_ESTADO_APROBACIONES,
    SQL_CONTRATO_ESTADO_APROBACIONES,
    SQL_INSERT_CONTRATO,
    SQL_UPDATE_CONTRATO,
    SQL_SOFT_DELETE_CONTRATO,
    SQL_INSERT_GARANTIA,
    SQL_UPDATE_GARANTIA,
    SQL_SOFT_DELETE_GARANTIA,
    SQL_ARCHIVOS_POR_CONTRATO_ID,
    SQL_ARCHIVOS_POR_CONTRATO_ID_ASC,
    SQL_ARCHIVO_POR_ID,
    SQL_INSERT_ARCHIVO_CONTRATO,
    SQL_LISTA_CONTRATOS_BASE,
    SQL_LISTA_GARANTIAS_BASE,
    SQL_LISTA_CONTRATOS_APROBADOS_JEFE,
    SQL_LISTA_CONTRATOS_APROBADOS_SIN_GARANTIA,
    SQL_CONTRATO_MINIMO_POR_ID,
    SQL_CONTRATO_MINIMO_ACTIVO_POR_ID,
    SQL_TOGGLE_APROBACION_JEFE_CONTRATO,
    SQL_TOGGLE_APROBACION_JEFE_GARANTIA,
    SQL_TOGGLE_APROBACION_CONTRATO,
    SQL_TOGGLE_APROBACION_GARANTIA,
    SQL_TOGGLE_APROBACION_GF_CONTRATO,
    SQL_TOGGLE_APROBACION_GF_GARANTIAS_POR_CONTRATO,
    SQL_EXISTE_GARANTIA_APROBADA_ACTIVA_POR_CONTRATO,
    SQL_DETALLE_GARANTIA_FRAGMENT,
    SQL_APROBACION_LISTA_BASE,
    SQL_GARANTIAS_REPORTE_BASE,
    SQL_GARANTIAS_VENCEN_EN_DIAS,
    SQL_NOTIFY_TEMPLATE_GARANTIA_VENCE_15_EXISTS,
    SQL_NOTIFY_TEMPLATE_GARANTIA_VENCE_15_INSERT,
    SQL_USUARIO_ID_POR_EMAIL,
    SQL_GARANTIAS_VENCEN_EN_15_DIAS,
    SQL_NOTIFY_QUEUE_EXISTS_BY_EVENT,
    SQL_NOTIFY_QUEUE_INSERT_GARANTIA,
)


def exec_retry(conn, sql: str, params: tuple = (), retries: int = 5, delay: float = 0.25):
    last = None
    transient_tokens = (
        "deadlock",
        "timeout",
        "temporarily unavailable",
        "could not serialize",
        "connection is busy",
        "communication link failure",
        "transport-level error",
    )
    for i in range(retries):
        try:
            cur = conn.cursor()
            cur.execute(sql, params)
            return cur
        except Exception as e:
            msg = str(e).lower()
            if any(tok in msg for tok in transient_tokens) and i < retries - 1:
                time.sleep(delay * (i + 1))
                continue
            last = e
            break
    raise last


def get_conn():
    return get_db()


def fetch_usuarios_combo():
    conn = get_conn()
    return conn.cursor().execute(SQL_USUARIOS_COMBO).fetchall()


def fetch_proveedores_combo():
    conn = get_conn()
    return conn.cursor().execute(SQL_PROVEEDORES_COMBO).fetchall()


def fetch_proveedor_nombre_por_id(proveedor_id: int | None) -> str | None:
    if not proveedor_id:
        return None
    conn = get_conn()
    row = conn.cursor().execute(SQL_PROVEEDOR_ACTIVO_POR_ID, (proveedor_id,)).fetchone()
    return row["nombre"] if row else None


def fetch_proveedor_id_por_nombre(nombre: str | None) -> int | None:
    if not nombre:
        return None
    conn = get_conn()
    row = conn.cursor().execute(SQL_PROVEEDOR_ID_POR_NOMBRE, ((nombre or "").strip(),)).fetchone()
    return row["id"] if row else None


def fetch_usuario_nombre_por_id(usuario_id: int | None) -> str:
    if not usuario_id:
        return ""
    conn = get_conn()
    row = conn.cursor().execute(SQL_USUARIO_NOMBRE_POR_ID, (usuario_id,)).fetchone()
    return (row["nombre"] if row and row["nombre"] else "") if row else ""


def fetch_usuario_email_por_id(usuario_id: int | None) -> str:
    if not usuario_id:
        return ""
    conn = get_conn()
    row = conn.cursor().execute(SQL_USUARIO_EMAIL_POR_ID, (usuario_id,)).fetchone()
    return (row["email"] if row and row["email"] else "") if row else ""


def fetch_usuario_email_por_username_o_email(name_or_email: str | None) -> str:
    v = (name_or_email or "").strip()
    if not v:
        return ""
    vlow = v.lower()
    if "@" in vlow and "." in vlow:
        return v
    conn = get_conn()
    row = conn.cursor().execute(SQL_USUARIO_EMAIL_POR_USERNAME_O_EMAIL, (vlow, vlow)).fetchone()
    return (row["email"] if row and row["email"] else "") if row else ""


def fetch_pgallegos_email() -> str:
    conn = get_conn()
    row = conn.cursor().execute(SQL_PGALLEGOS_EMAIL).fetchone()
    return (row["email"] if row and row["email"] else "") if row else ""


def exists_usuario(usuario_id: int | None) -> bool:
    if not usuario_id:
        return False
    conn = get_conn()
    return conn.cursor().execute(SQL_USUARIO_EXISTE_POR_ID, (usuario_id,)).fetchone() is not None


def exists_contrato(contrato_id: int | None) -> bool:
    if not contrato_id:
        return False
    conn = get_conn()
    return conn.cursor().execute(SQL_CONTRATO_EXISTE_POR_ID, (contrato_id,)).fetchone() is not None


def exists_garantia(garantia_id: int | None) -> bool:
    if not garantia_id:
        return False
    conn = get_conn()
    return conn.cursor().execute(SQL_GARANTIA_EXISTE_POR_ID, (garantia_id,)).fetchone() is not None


def fetch_contrato_por_id(contrato_id: int):
    conn = get_conn()
    return conn.cursor().execute(SQL_CONTRATO_POR_ID, (contrato_id,)).fetchone()


def fetch_garantia_activa_por_id(garantia_id: int):
    conn = get_conn()
    return conn.cursor().execute(SQL_GARANTIA_POR_ID_ACTIVA, (garantia_id,)).fetchone()


def fetch_estado_aprobaciones_contrato(contrato_id: int):
    conn = get_conn()
    return conn.cursor().execute(SQL_CONTRATO_ESTADO_APROBACIONES, (contrato_id,)).fetchone()


def fetch_estado_aprobaciones_garantia(garantia_id: int):
    conn = get_conn()
    return conn.cursor().execute(SQL_GARANTIA_ESTADO_APROBACIONES, (garantia_id,)).fetchone()


def insert_contrato(params: tuple) -> int | None:
    conn = get_conn()
    cur = exec_retry(conn, SQL_INSERT_CONTRATO, params)
    row = cur.fetchone()
    conn.commit()
    return row[0] if row else None


def update_contrato(params: tuple) -> None:
    conn = get_conn()
    conn.cursor().execute(SQL_UPDATE_CONTRATO, params)
    conn.commit()


def soft_delete_contrato(contrato_id: int) -> None:
    conn = get_conn()
    conn.cursor().execute(SQL_SOFT_DELETE_CONTRATO, (contrato_id,))
    conn.commit()


def insert_garantia(params: tuple) -> int | None:
    conn = get_conn()
    cur = exec_retry(conn, SQL_INSERT_GARANTIA, params)
    row = cur.fetchone()
    conn.commit()
    return row[0] if row else None


def update_garantia(params: tuple) -> None:
    conn = get_conn()
    conn.cursor().execute(SQL_UPDATE_GARANTIA, params)
    conn.commit()


def soft_delete_garantia(garantia_id: int) -> None:
    conn = get_conn()
    conn.cursor().execute(SQL_SOFT_DELETE_GARANTIA, (garantia_id,))
    conn.commit()


def insert_archivo_contrato(contrato_id: int, filename: str, original_name: str) -> None:
    conn = get_conn()
    exec_retry(conn, SQL_INSERT_ARCHIVO_CONTRATO, (contrato_id, filename, original_name))
    conn.commit()


def fetch_archivos_contrato(contrato_id: int):
    conn = get_conn()
    return conn.cursor().execute(SQL_ARCHIVOS_POR_CONTRATO_ID, (contrato_id,)).fetchall()


def fetch_archivos_contrato_asc(contrato_id: int):
    conn = get_conn()
    return conn.cursor().execute(SQL_ARCHIVOS_POR_CONTRATO_ID_ASC, (contrato_id,)).fetchall()


def fetch_archivo_por_id(archivo_id: int):
    conn = get_conn()
    return conn.cursor().execute(SQL_ARCHIVO_POR_ID, (archivo_id,)).fetchone()


def list_contratos(
    proveedor: str = "",
    pedido: str = "",
    tipo_pp: str = "",
    fecha_desde: str = "",
    fecha_hasta: str = "",
):
    sql = SQL_LISTA_CONTRATOS_BASE
    params: List[Any] = []

    proveedor = (proveedor or "").strip()
    pedido = (pedido or "").strip()
    tipo_pp = (tipo_pp or "").strip().upper()
    fecha_desde = (fecha_desde or "").strip()
    fecha_hasta = (fecha_hasta or "").strip()

    if proveedor:
        sql += " AND c.proveedor LIKE ?"
        params.append(f"%{proveedor}%")

    if pedido:
        sql += " AND c.pedido LIKE ?"
        params.append(f"%{pedido}%")

    if tipo_pp in ("PAGARE", "POLIZA", "AMBOS"):
        sql += " AND c.tipo_pp = ?"
        params.append(tipo_pp)

    # Filtro por fecha de suscripción del contrato
    if fecha_desde:
        sql += " AND CAST(c.fecha_suscripcion AS date) >= CAST(? AS date)"
        params.append(fecha_desde)

    if fecha_hasta:
        sql += " AND CAST(c.fecha_suscripcion AS date) <= CAST(? AS date)"
        params.append(fecha_hasta)

    sql += " ORDER BY c.id DESC"

    conn = get_conn()
    return conn.cursor().execute(sql, params).fetchall()
 


def list_contratos_reporte(
    proveedor: str = "",
    pedido: str = "",
    tipo_pp: str = "",
    fecha_desde: str = "",
    fecha_hasta: str = "",
):
    sql = """
    SELECT
        c.id,
        c.anio,
        c.pedido,
        c.proveedor,
        c.objeto,
        c.valor_contrato,
        c.valor_anticipo,
        c.tipo_pp,
        c.fecha_suscripcion,
        c.fecha_terminacion,
        c.plazo_dias,
        c.cronograma_pagos,
        c.fecha_entrega_compras,
        c.fecha_firma_gerencia,
        c.fecha_entrega_finanzas_sumilla,
        c.fecha_entrega_originales_fin,
        c.fechas_pago_anticipo,
        c.fecha_entrega_pedido,
        c.status_interno,
        c.observaciones,
        c.usuario_solicitante_id,
        us.nombre_completo AS usuario_solicitante,
        c.usuario_compras_nombre,
        c.usuario_compras_id,
        uc.nombre_completo AS usuario_compras,
        c.departamento_id,
        d.nombre AS departamento,
        COALESCE(c.aprobado_jefe,0) AS aprobado_jefe,
        c.aprobado_jefe_por,
        uj.nombre_completo AS aprobado_jefe_por_nombre,
        c.aprobado_jefe_en,
        COALESCE(c.aprobado,0) AS aprobado,
        c.aprobado_por,
        ua.nombre_completo AS aprobado_por_nombre,
        c.aprobado_en,
        COALESCE(c.aprob_gf,0) AS aprob_gf,
        c.creado_por,
        cr.nombre_completo AS creado_por_nombre,
        c.creado_at,
        c.actualizado_at,
        (
            SELECT COUNT(1)
            FROM contrato_archivos a
            WHERE a.contrato_id = c.id
        ) AS adjuntos_cnt
    FROM contratos c
    LEFT JOIN usuarios us ON us.id = c.usuario_solicitante_id
    LEFT JOIN usuarios uc ON uc.id = c.usuario_compras_id
    LEFT JOIN usuarios uj ON uj.id = c.aprobado_jefe_por
    LEFT JOIN usuarios ua ON ua.id = c.aprobado_por
    LEFT JOIN usuarios cr ON cr.id = c.creado_por
    LEFT JOIN departamentos d ON d.id = c.departamento_id
    WHERE COALESCE(c.disabled,0)=0
    """

    params: List[Any] = []

    proveedor = (proveedor or "").strip()
    pedido = (pedido or "").strip()
    tipo_pp = (tipo_pp or "").strip().upper()
    fecha_desde = (fecha_desde or "").strip()
    fecha_hasta = (fecha_hasta or "").strip()

    if proveedor:
        sql += " AND c.proveedor LIKE ?"
        params.append(f"%{proveedor}%")

    if pedido:
        sql += " AND c.pedido LIKE ?"
        params.append(f"%{pedido}%")

    if tipo_pp in ("PAGARE", "POLIZA", "AMBOS"):
        sql += " AND c.tipo_pp = ?"
        params.append(tipo_pp)

    if fecha_desde:
        sql += " AND CAST(c.fecha_suscripcion AS date) >= CAST(? AS date)"
        params.append(fecha_desde)

    if fecha_hasta:
        sql += " AND CAST(c.fecha_suscripcion AS date) <= CAST(? AS date)"
        params.append(fecha_hasta)

    sql += " ORDER BY c.id DESC"

    conn = get_conn()
    return conn.cursor().execute(sql, params).fetchall()


def list_garantias(
    proveedor: str = "",
    pedido: str = "",
    estado: str = "",
    requiere_renovacion: int | None = None,
    fecha_registro_desde: str = "",
    fecha_registro_hasta: str = "",
    fecha_vencimiento_desde: str = "",
    fecha_vencimiento_hasta: str = "",
):
    sql = SQL_LISTA_GARANTIAS_BASE
    params: List[Any] = []

    if proveedor:
        sql += " AND c.proveedor LIKE ?"
        params.append(f"%{proveedor}%")

    if pedido:
        sql += " AND c.pedido LIKE ?"
        params.append(f"%{pedido}%")

    if estado:
        sql += " AND g.estado = ?"
        params.append(estado)

    if requiere_renovacion is not None:
        sql += " AND g.requiere_renovacion = ?"
        params.append(requiere_renovacion)

    if fecha_registro_desde:
        sql += " AND CAST(g.creado_at AS date) >= ?"
        params.append(fecha_registro_desde)

    if fecha_registro_hasta:
        sql += " AND CAST(g.creado_at AS date) <= ?"
        params.append(fecha_registro_hasta)

    if fecha_vencimiento_desde:
        sql += " AND CAST(g.fecha_vencimiento AS date) >= ?"
        params.append(fecha_vencimiento_desde)

    if fecha_vencimiento_hasta:
        sql += " AND CAST(g.fecha_vencimiento AS date) <= ?"
        params.append(fecha_vencimiento_hasta)

    sql += " ORDER BY g.id DESC"

    conn = get_conn()
    return conn.cursor().execute(sql, params).fetchall()


def list_contratos_aprobados_jefe(limit: int = 200, include_id: int | None = None):
    conn = get_conn()
    cur = conn.cursor()
    top_n = max(1, int(limit or 200))

    rows = cur.execute(SQL_LISTA_CONTRATOS_APROBADOS_JEFE.format(top_n=top_n)).fetchall()

    if include_id:
        extra = cur.execute(SQL_CONTRATO_MINIMO_POR_ID, (include_id,)).fetchone()
        if extra and not any(r["id"] == extra["id"] for r in rows):
            rows = [extra] + list(rows)
    return rows


def list_contratos_aprobados_sin_garantia(limit: int = 200, include_id: int | None = None):
    conn = get_conn()
    cur = conn.cursor()
    top_n = max(1, int(limit or 200))

    rows = cur.execute(SQL_LISTA_CONTRATOS_APROBADOS_SIN_GARANTIA.format(top_n=top_n)).fetchall()

    if include_id:
        extra = cur.execute(SQL_CONTRATO_MINIMO_ACTIVO_POR_ID, (include_id,)).fetchone()
        if extra and not any(r["id"] == extra["id"] for r in rows):
            rows = [extra] + list(rows)
    return rows


def toggle_aprobacion_jefe_contrato(contrato_id: int, nuevo: int, usuario_id: int | None, status_txt: str):
    conn = get_conn()
    conn.cursor().execute(SQL_TOGGLE_APROBACION_JEFE_CONTRATO, (nuevo, usuario_id, status_txt, contrato_id))
    conn.commit()


def toggle_aprobacion_jefe_garantia(garantia_id: int, nuevo: int, usuario_id: int | None, status_txt: str):
    conn = get_conn()
    conn.cursor().execute(SQL_TOGGLE_APROBACION_JEFE_GARANTIA, (nuevo, usuario_id, status_txt, garantia_id))
    conn.commit()


def toggle_aprobacion_contrato(contrato_id: int, new_val: int, usuario_id: int | None):
    conn = get_conn()
    conn.cursor().execute(SQL_TOGGLE_APROBACION_CONTRATO, (new_val, usuario_id, contrato_id))
    conn.commit()


def toggle_aprobacion_garantia(garantia_id: int, new_val: int, usuario_id: int | None):
    conn = get_conn()
    conn.cursor().execute(SQL_TOGGLE_APROBACION_GARANTIA, (new_val, usuario_id, garantia_id))
    conn.commit()


def toggle_aprobacion_gf_contrato_y_garantias(contrato_id: int, valor: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(SQL_TOGGLE_APROBACION_GF_CONTRATO, (valor, contrato_id))
    cur.execute(SQL_TOGGLE_APROBACION_GF_GARANTIAS_POR_CONTRATO, (valor, contrato_id))
    conn.commit()


def existe_garantia_aprobada_activa_por_contrato(contrato_id: int) -> bool:
    conn = get_conn()
    row = conn.cursor().execute(SQL_EXISTE_GARANTIA_APROBADA_ACTIVA_POR_CONTRATO, (contrato_id,)).fetchone()
    return row is not None


def fetch_detalle_garantia_fragment(garantia_id: int):
    conn = get_conn()
    return conn.cursor().execute(SQL_DETALLE_GARANTIA_FRAGMENT, (garantia_id,)).fetchone()


def list_aprobacion(proveedor: str = "", pedido: str = "", tipo_pp: str = "", estado: str = "", renovacion: int | None = None):
    sql = SQL_APROBACION_LISTA_BASE
    params: List[Any] = []

    if proveedor:
        sql += " AND c.proveedor LIKE ?"
        params.append(f"%{proveedor}%")
    if pedido:
        sql += " AND c.pedido LIKE ?"
        params.append(f"%{pedido}%")
    if tipo_pp in ("PAGARE", "POLIZA", "AMBOS"):
        sql += " AND c.tipo_pp = ?"
        params.append(tipo_pp)
    if estado:
        sql += " AND COALESCE(g.estado,'') = ?"
        params.append(estado)
    if renovacion is not None:
        sql += " AND COALESCE(g.requiere_renovacion,0) = ?"
        params.append(int(renovacion))

    sql += " ORDER BY c.id DESC, g.id DESC"

    conn = get_conn()
    return conn.cursor().execute(sql, params).fetchall()


def list_garantias_reporte(
    proveedor: str = "",
    pedido: str = "",
    estado: str = "",
    requiere_renovacion: int | None = None,
    fecha_registro_desde: str = "",
    fecha_registro_hasta: str = "",
    fecha_vencimiento_desde: str = "",
    fecha_vencimiento_hasta: str = "",
):
    sql = SQL_GARANTIAS_REPORTE_BASE
    params: List[Any] = []

    proveedor = (proveedor or "").strip()
    pedido = (pedido or "").strip()
    estado = (estado or "").strip()
    fecha_registro_desde = (fecha_registro_desde or "").strip()
    fecha_registro_hasta = (fecha_registro_hasta or "").strip()
    fecha_vencimiento_desde = (fecha_vencimiento_desde or "").strip()
    fecha_vencimiento_hasta = (fecha_vencimiento_hasta or "").strip()

    if proveedor:
        sql += " AND c.proveedor LIKE ?"
        params.append(f"%{proveedor}%")

    if pedido:
        sql += " AND c.pedido LIKE ?"
        params.append(f"%{pedido}%")

    if estado:
        sql += " AND g.estado = ?"
        params.append(estado)

    if requiere_renovacion is not None:
        sql += " AND g.requiere_renovacion = ?"
        params.append(requiere_renovacion)

    if fecha_registro_desde:
        sql += " AND CAST(g.creado_at AS date) >= CAST(? AS date)"
        params.append(fecha_registro_desde)

    if fecha_registro_hasta:
        sql += " AND CAST(g.creado_at AS date) <= CAST(? AS date)"
        params.append(fecha_registro_hasta)

    if fecha_vencimiento_desde:
        sql += " AND CAST(g.fecha_vencimiento AS date) >= CAST(? AS date)"
        params.append(fecha_vencimiento_desde)

    if fecha_vencimiento_hasta:
        sql += " AND CAST(g.fecha_vencimiento AS date) <= CAST(? AS date)"
        params.append(fecha_vencimiento_hasta)

    sql += " ORDER BY g.id DESC"

    conn = get_conn()
    return conn.cursor().execute(sql, params).fetchall()



def list_garantias_vencen_en_15_dias():
    conn = get_conn()
    return conn.cursor().execute(SQL_GARANTIAS_VENCEN_EN_DIAS).fetchall()

def list_contratos_aprobados_para_garantia(limit: int = 300, include_id: int | None = None):
    conn = get_conn()
    cur = conn.cursor()
    top_n = max(1, int(limit or 300))

    rows = cur.execute(
        SQL_LISTA_CONTRATOS_APROBADOS_PARA_GARANTIA.format(top_n=top_n)
    ).fetchall()

    if include_id:
        extra = cur.execute(SQL_CONTRATO_MINIMO_ACTIVO_POR_ID, (include_id,)).fetchone()
        if extra and not any(r["id"] == extra["id"] for r in rows):
            rows = [extra] + list(rows)

    return rows


def fetch_usuario_id_por_email(email: str | None) -> int | None:
    email = (email or "").strip()
    if not email:
        return None

    conn = get_conn()
    row = conn.cursor().execute(SQL_USUARIO_ID_POR_EMAIL, (email,)).fetchone()
    return row["id"] if row else None


def list_garantias_vencen_en_15_dias():
    conn = get_conn()
    return conn.cursor().execute(SQL_GARANTIAS_VENCEN_EN_15_DIAS).fetchall()


def ensure_garantia_vencimiento_template(conn=None) -> None:
    """
    Inserta el template de garantía por vencer si no existe.
    Usa el mismo modelo de notify_templates.
    """
    from .contratos_constants import (
        TPL_GARANTIA_VENCE_15,
        TIPO_GARANTIA_VENCE_15,
    )

    own_conn = False
    if conn is None:
        conn = get_conn()
        own_conn = True

    cur = conn.cursor()
    row = cur.execute(
        SQL_NOTIFY_TEMPLATE_GARANTIA_VENCE_15_EXISTS,
        (TPL_GARANTIA_VENCE_15,),
    ).fetchone()

    if row:
        return

    subject = "🟠 Garantía por vencer en {{ dias_para_vencer }} día(s): Pedido {{ pedido }}"

    html = """<!doctype html>
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
                  GESTIÓN DE GARANTÍAS
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
                  Hola {{ destinatario_nombre or 'Usuario' }},
                </div>

                <div style="font-size:14px;color:#111827;line-height:1.6;margin-bottom:14px;">
                  {{ intro_text }}
                </div>

                <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                       style="border-collapse:separate;border-spacing:0;overflow:hidden;border-radius:10px;">

                  <tr>
                    <td style="width:260px;background:{{ row_bg }};font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Pedido</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">{{ pedido }}</td>
                  </tr>

                  <tr>
                    <td style="background:{{ row_bg }};font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Proveedor</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">{{ proveedor }}</td>
                  </tr>

                  <tr>
                    <td style="background:{{ row_bg }};font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Tipo de garantía</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">{{ garantia_tipo }}</td>
                  </tr>

                  <tr>
                    <td style="background:{{ row_bg }};font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Fecha de vencimiento</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#b45309;font-weight:800;">{{ fecha_vencimiento }}</td>
                  </tr>

                  <tr>
                    <td style="background:{{ row_bg }};font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Días para vencer</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">
                      <span style="display:inline-block;background:#ffedd5;color:#9a3412;padding:4px 10px;border-radius:999px;font-weight:800;">
                        {{ dias_para_vencer }} día(s)
                      </span>
                    </td>
                  </tr>

                  <tr>
                    <td style="background:{{ row_bg }};font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Estado garantía</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">{{ garantia_estado }}</td>
                  </tr>

                  <tr>
                    <td style="background:{{ row_bg }};font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">Compañía emisora</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">{{ compania_emisora }}</td>
                  </tr>

                  <tr>
                    <td style="background:{{ row_bg }};font-weight:700;padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;vertical-align:top;">Objeto del contrato</td>
                    <td style="padding:10px 14px;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;white-space:pre-wrap;">{{ objeto }}</td>
                  </tr>

                </table>

                <div style="margin-top:18px;">
                  <a href="{{ cta_url }}"
                     style="display:inline-block;background:#f97316;color:#ffffff;text-decoration:none;
                            padding:11px 18px;border-radius:8px;font-weight:700;font-size:13px;">
                    {{ cta_label }}
                  </a>
                </div>

                <div style="font-size:12px;color:#6b7280;margin-top:12px;">
                  {{ footer_note }}
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
</html>"""

    text = """Garantía próxima a vencer

Pedido: {{ pedido }}
Proveedor: {{ proveedor }}
Tipo de garantía: {{ garantia_tipo }}
Fecha de vencimiento: {{ fecha_vencimiento }}
Días para vencer: {{ dias_para_vencer }}
Estado garantía: {{ garantia_estado }}
Compañía emisora: {{ compania_emisora }}
Objeto: {{ objeto }}

{{ footer_note }}

App: {{ cta_url }}
"""

    cur.execute(
        SQL_NOTIFY_TEMPLATE_GARANTIA_VENCE_15_INSERT,
        (
            TPL_GARANTIA_VENCE_15,
            subject,
            html,
            text,
            TIPO_GARANTIA_VENCE_15,
        ),
    )

    if own_conn:
        conn.commit()


def enqueue_garantia_vence_15(conn, *, user_id: int, garantia_id: int, payload: dict) -> bool:
    """
    Encola notificación de garantía próxima a vencer.
    Evita duplicados por user_id + template_key + event_key.
    """
    from .contratos_constants import (
        TPL_GARANTIA_VENCE_15,
        TIPO_GARANTIA_VENCE_15,
    )

    if not user_id:
        return False

    fecha_vencimiento = str(payload.get("fecha_vencimiento") or "")
    event_key = f"garantia_vence_15:{garantia_id}:{fecha_vencimiento}:uid:{user_id}"

    payload.setdefault("header_color", "#f97316")
    payload.setdefault("row_bg", "#fff7ed")
    payload.setdefault("header_title", "Garantía próxima a vencer")
    payload.setdefault(
        "header_subtitle",
        f"Pedido {payload.get('pedido', '')} — vence en {payload.get('dias_para_vencer', 15)} día(s)",
    )
    payload.setdefault(
        "intro_text",
        "Se informa que la garantía asociada al siguiente contrato está próxima a vencer. "
        "Por favor, revisar si corresponde gestionar la renovación, liberación o actualización del estado.",
    )
    payload.setdefault("cta_label", "Ver garantía / contrato")
    payload.setdefault(
        "footer_note",
        "Ingresa al módulo de Contratos / Garantías para revisar la información y gestionar la acción correspondiente.",
    )

    cur = conn.cursor()

    exists = cur.execute(
        SQL_NOTIFY_QUEUE_EXISTS_BY_EVENT,
        (
            user_id,
            TPL_GARANTIA_VENCE_15,
            event_key,
        ),
    ).fetchone()

    if exists:
        return False

    cur.execute(
        SQL_NOTIFY_QUEUE_INSERT_GARANTIA,
        (
            user_id,
            TIPO_GARANTIA_VENCE_15,
            fecha_vencimiento or date.today().isoformat(),
            "email",
            TPL_GARANTIA_VENCE_15,
            json.dumps(payload, ensure_ascii=False, default=str),
            "contratos_garantias",
            event_key,
        ),
    )

    return True