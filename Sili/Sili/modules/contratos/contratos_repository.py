from __future__ import annotations

import time
from typing import Any, List

from modules.db import get_db

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
    sql = """
    SELECT
        g.id AS garantia_id,
        g.contrato_id,
        g.tipo AS garantia_tipo,
        g.compania_emisora,
        g.monto_poliza,
        g.fecha_suscripcion AS garantia_fecha_suscripcion,
        g.fecha_vencimiento AS garantia_fecha_vencimiento,
        g.fecha_vencimiento_actual,
        g.vigencia_dias,
        g.estado AS garantia_estado,
        g.fecha_renovacion,
        g.requiere_renovacion,
        g.status_interno AS garantia_status_interno,
        g.observaciones AS garantia_observaciones,
        g.creado_at AS garantia_creado_at,
        g.actualizado_at AS garantia_actualizado_at,
        COALESCE(g.aprobado_jefe,0) AS garantia_aprobado_jefe,
        COALESCE(g.aprobado,0) AS garantia_aprobado,
        COALESCE(g.aprob_gf,0) AS garantia_aprob_gf,

        c.id AS contrato_id_real,
        c.anio,
        c.pedido,
        c.proveedor,
        c.objeto,
        c.valor_contrato,
        c.valor_anticipo,
        c.tipo_pp,
        c.fecha_suscripcion AS contrato_fecha_suscripcion,
        c.fecha_terminacion AS contrato_fecha_terminacion,
        c.plazo_dias,
        c.cronograma_pagos,
        c.fecha_entrega_compras,
        c.fecha_firma_gerencia,
        c.fecha_entrega_finanzas_sumilla,
        c.fecha_entrega_originales_fin,
        c.fechas_pago_anticipo,
        c.fecha_entrega_pedido,
        c.status_interno AS contrato_status_interno,
        c.observaciones AS contrato_observaciones,
        COALESCE(c.aprobado_jefe,0) AS contrato_aprobado_jefe,
        COALESCE(c.aprobado,0) AS contrato_aprobado,
        COALESCE(c.aprob_gf,0) AS contrato_aprob_gf
    FROM garantias g
    JOIN contratos c ON c.id = g.contrato_id
    WHERE COALESCE(g.disabled,0)=0
      AND COALESCE(c.disabled,0)=0
    """

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