# modules/gastos/gastos_repository.py

from __future__ import annotations

import sqlite3
from typing import Any, Iterable

from .gastos_queries import (
    SQL_DELETE_DETALLE_BY_GASTO_ID,
    SQL_DELETE_GASTO,
    SQL_FACTURA_XML_ESTA_USADA,
    SQL_GET_ARCHIVOS_BY_GASTO_ID,
    SQL_GET_DETALLE_BY_GASTO_ID,
    SQL_GET_FACTURA_XML_BY_ID,
    SQL_GET_GASTO_BY_ID,
    SQL_GET_GASTO_OWNER,
    SQL_GET_USUARIO_BY_ID,
    SQL_GET_USUARIO_BY_USERNAME,
    SQL_INSERT_DETALLE,
    SQL_INSERT_GASTO,
    SQL_LIST_GASTOS,
    SQL_SEARCH_FACTURAS_XML_BASE,
    SQL_UPDATE_FACTURA_XML_ESTADO,
    SQL_UPDATE_GASTO,
)
from .gastos_constants import (
    DEFAULT_XML_SEARCH_LIMIT,
    FACTURA_XML_PENDIENTE,
    MAX_XML_SEARCH_LIMIT,
    TABLE_ARCHIVOS,
    TABLE_DEPARTAMENTOS,
    TABLE_DETALLE,
    TABLE_FACTURAS_XML,
    TABLE_GASTOS,
    TABLE_TERCEROS,
    TABLE_USUARIOS,
)


def _dicts(rows: Iterable[Any]) -> list[dict]:
    out: list[dict] = []
    for row in rows:
        if isinstance(row, sqlite3.Row):
            out.append(dict(row))
        elif isinstance(row, dict):
            out.append(row)
        else:
            try:
                out.append(dict(row))
            except Exception:
                pass
    return out


def _dict(row: Any) -> dict | None:
    if row is None:
        return None
    if isinstance(row, sqlite3.Row):
        return dict(row)
    if isinstance(row, dict):
        return row
    try:
        return dict(row)
    except Exception:
        return None


def get_gasto_by_id(conn: sqlite3.Connection, gasto_id: int) -> dict | None:
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(SQL_GET_GASTO_BY_ID, (gasto_id,))
    return _dict(cur.fetchone())


def list_gastos(conn: sqlite3.Connection) -> list[dict]:
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(SQL_LIST_GASTOS)
    return _dicts(cur.fetchall())


def insert_gasto(
    conn: sqlite3.Connection,
    *,
    fecha: str,
    usuario_id: int,
    motivo: str,
    total: float,
) -> int:
    cur = conn.cursor()
    cur.execute(SQL_INSERT_GASTO, (fecha, usuario_id, motivo, total))
    return int(cur.lastrowid)


def update_gasto(
    conn: sqlite3.Connection,
    *,
    gasto_id: int,
    fecha: str,
    motivo: str,
    total: float,
) -> None:
    cur = conn.cursor()
    cur.execute(SQL_UPDATE_GASTO, (fecha, motivo, total, gasto_id))


def delete_gasto(conn: sqlite3.Connection, gasto_id: int) -> None:
    cur = conn.cursor()
    cur.execute(SQL_DELETE_GASTO, (gasto_id,))


def get_detalle_by_gasto_id(conn: sqlite3.Connection, gasto_id: int) -> list[dict]:
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(SQL_GET_DETALLE_BY_GASTO_ID, (gasto_id,))
    return _dicts(cur.fetchall())


def replace_detalle(conn: sqlite3.Connection, gasto_id: int, detalle_items: list[dict]) -> None:
    cur = conn.cursor()
    cur.execute(SQL_DELETE_DETALLE_BY_GASTO_ID, (gasto_id,))

    for item in detalle_items:
        cur.execute(
            SQL_INSERT_DETALLE,
            (
                gasto_id,
                item.get("descripcion"),
                item.get("subtotal", 0),
                item.get("iva", 0),
                item.get("total", 0),
            ),
        )


def get_archivos_by_gasto_id(conn: sqlite3.Connection, gasto_id: int) -> list[dict]:
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(SQL_GET_ARCHIVOS_BY_GASTO_ID, (gasto_id,))
    return _dicts(cur.fetchall())


def insert_archivo(
    conn: sqlite3.Connection,
    *,
    gasto_id: int,
    filename: str,
    filepath: str,
    content_type: str | None = None,
    size: int | None = None,
    uploaded_by: int | None = None,
) -> int:
    cur = conn.cursor()
    cur.execute(
        f"""
        INSERT INTO {TABLE_ARCHIVOS} (
            gasto_id,
            filename,
            filepath,
            content_type,
            size,
            uploaded_by
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (gasto_id, filename, filepath, content_type, size, uploaded_by),
    )
    return int(cur.lastrowid)


def delete_archivos_by_gasto_id(conn: sqlite3.Connection, gasto_id: int) -> None:
    cur = conn.cursor()
    cur.execute(f"DELETE FROM {TABLE_ARCHIVOS} WHERE gasto_id = ?", (gasto_id,))


def get_factura_xml_by_id(conn: sqlite3.Connection, factura_id: int) -> dict | None:
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(SQL_GET_FACTURA_XML_BY_ID, (factura_id,))
    return _dict(cur.fetchone())


def is_factura_xml_used(conn: sqlite3.Connection, factura_id: int) -> bool:
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(SQL_FACTURA_XML_ESTA_USADA, (factura_id,))
    return cur.fetchone() is not None


def update_factura_xml_estado(conn: sqlite3.Connection, factura_id: int, estado: str) -> None:
    cur = conn.cursor()
    cur.execute(SQL_UPDATE_FACTURA_XML_ESTADO, (estado, factura_id))


def get_usuario_by_id(conn: sqlite3.Connection, user_id: int) -> dict | None:
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(SQL_GET_USUARIO_BY_ID, (user_id,))
    return _dict(cur.fetchone())


def get_usuario_by_username(conn: sqlite3.Connection, username: str) -> dict | None:
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(SQL_GET_USUARIO_BY_USERNAME, (username,))
    return _dict(cur.fetchone())


def get_gasto_owner(conn: sqlite3.Connection, gasto_id: int) -> dict | None:
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(SQL_GET_GASTO_OWNER, (gasto_id,))
    return _dict(cur.fetchone())


def search_facturas_xml(
    conn: sqlite3.Connection,
    *,
    q: str = "",
    limit: int = DEFAULT_XML_SEARCH_LIMIT,
) -> list[dict]:
    from .gastos_xml_service import apply_facturas_xml_search

    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        limit = int(limit or DEFAULT_XML_SEARCH_LIMIT)
    except Exception:
        limit = DEFAULT_XML_SEARCH_LIMIT

    limit = max(1, min(limit, MAX_XML_SEARCH_LIMIT))

    where = ["1 = 1", f"f.estado = '{FACTURA_XML_PENDIENTE}'"]
    params: list[Any] = []

    where.append(
        f"""
        NOT EXISTS (
            SELECT 1
            FROM {TABLE_GASTOS} g
            WHERE
                g.factura_xml_id = f.id
                OR (
                    TRIM(COALESCE(g.numero_factura,'')) = TRIM(
                        (COALESCE(f.estab,'') || '-' || COALESCE(f.pto_emi,'') || '-' ||
                        printf('%09d', CAST(COALESCE(f.secuencial,'0') AS INTEGER)))
                    )
                )
        )
        """
    )

    apply_facturas_xml_search(where, params, q, alias="f")

    sql = f"""
        SELECT
            f.*,
            CASE
                WHEN EXISTS (
                    SELECT 1
                    FROM {TABLE_TERCEROS} t
                    WHERE t.tipo = 'P'
                      AND t.activo = 1
                      AND TRIM(t.identificacion) = TRIM(f.ruc_emisor)
                ) THEN 1
                ELSE 0
            END AS proveedor_ok
        FROM {TABLE_FACTURAS_XML} f
        WHERE {" AND ".join(where)}
        ORDER BY
            substr(f.fecha_emision,7,4) || '-' ||
            substr(f.fecha_emision,4,2) || '-' ||
            substr(f.fecha_emision,1,2) DESC,
            f.id DESC
        LIMIT ?
    """
    params.append(limit)

    cur.execute(sql, params)
    return _dicts(cur.fetchall())


def get_gastos_for_sap(conn: sqlite3.Connection, ids: list[int]) -> list[dict]:
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    ids = [int(x) for x in ids if str(x).strip().isdigit()]
    if not ids:
        return []

    ph = ",".join(["?"] * len(ids))
    cur.execute(
        f"""
        SELECT
            g.*,
            u.username,
            u.codigo_sap AS usuario_codigo_sap,
            u.identificacion AS usuario_cedula,
            t.codigo_sap AS proveedor_codigo_sap,
            t.nombre AS proveedor_nombre
        FROM {TABLE_GASTOS} g
        JOIN {TABLE_USUARIOS} u
            ON u.id = g.usuario_id
        LEFT JOIN {TABLE_TERCEROS} t
            ON t.id = g.proveedor_id
        WHERE g.id IN ({ph})
        """,
        ids,
    )
    return _dicts(cur.fetchall())


def get_detalles_for_sap(conn: sqlite3.Connection, ids: list[int]) -> list[dict]:
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    ids = [int(x) for x in ids if str(x).strip().isdigit()]
    if not ids:
        return []

    ph = ",".join(["?"] * len(ids))
    cur.execute(
        f"""
        SELECT d.*
        FROM {TABLE_DETALLE} d
        WHERE d.gasto_id IN ({ph})
        ORDER BY d.gasto_id, d.id
        """,
        ids,
    )
    return _dicts(cur.fetchall())


def mark_gasto_sap_result(
    conn: sqlite3.Connection,
    *,
    gasto_id: int,
    doc_number: str | None,
    response_json: str | None,
    enviado_at: str | None,
    error_msg: str | None,
) -> None:
    cur = conn.cursor()
    cur.execute(
        f"""
        UPDATE {TABLE_GASTOS}
        SET
            sap_contabilizacion = ?,
            sap_response_json   = ?,
            sap_enviado_at      = ?,
            sap_error_msg       = ?
        WHERE id = ?
        """,
        (doc_number, response_json, enviado_at, error_msg, gasto_id),
    )


def get_gastos_resumen_for_export(conn: sqlite3.Connection, ids: list[int] | None = None) -> list[dict]:
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    sql = f"""
        SELECT
            g.*,
            u.username AS usuario_username,
            t.nombre   AS proveedor_nombre,
            d.nombre   AS departamento_nombre
        FROM {TABLE_GASTOS} g
        LEFT JOIN {TABLE_USUARIOS} u
            ON u.id = g.usuario_id
        LEFT JOIN {TABLE_TERCEROS} t
            ON t.id = g.proveedor_id
        LEFT JOIN {TABLE_DEPARTAMENTOS} d
            ON d.id = u.departamento_id
    """
    params: list[Any] = []

    if ids:
        ids = [int(x) for x in ids if str(x).strip().isdigit()]
        if ids:
            ph = ",".join(["?"] * len(ids))
            sql += f" WHERE g.id IN ({ph})"
            params.extend(ids)

    sql += " ORDER BY COALESCE(g.fecha, g.created_at) DESC, g.id DESC"
    cur.execute(sql, params)
    return _dicts(cur.fetchall())


def get_gasto_full_by_id(conn: sqlite3.Connection, gasto_id: int) -> dict | None:
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT
            g.*,
            COALESCE(u.username,'') AS usuario_username,
            COALESCE(t.nombre, g.proveedor, '') AS proveedor_nombre
        FROM {TABLE_GASTOS} g
        LEFT JOIN {TABLE_USUARIOS} u
            ON u.id = g.usuario_id
        LEFT JOIN {TABLE_TERCEROS} t
            ON t.id = g.proveedor_id
        WHERE g.id = ?
        """,
        (gasto_id,),
    )
    return _dict(cur.fetchone())


def insert_gasto_full(conn: sqlite3.Connection, payload: dict, usuario_id: int) -> int:
    cur = conn.cursor()

    columns = []
    values = []
    params = []

    payload = dict(payload or {})
    payload["usuario_id"] = usuario_id

    allowed_fields = [
        "fecha",
        "usuario_id",
        "motivo",
        "proveedor_id",
        "proveedor",
        "numero_factura",
        "descripcion",
        "con_soporte",
        "sin_soporte",
        "subtotal_factura",
        "servicios_10",
        "subtotal_sin_iva",
        "iva",
        "total_con_iva",
        "observacion",
        "ccb",
        "es_caja_chica",
        "reembolso_vendedor",
        "tarjeta_sin_soporte",
        "boletos_aereos",
        "factura_xml_id",
        "centro_costo",
        "cuenta_contable",
        "ga_aprobado",
        "gg_aprobado",
        "gf_aprobado",
    ]

    for field in allowed_fields:
        if field in payload:
            columns.append(field)
            values.append("?")
            params.append(payload.get(field))

    if "created_at" not in columns:
        columns.append("created_at")
        values.append("CURRENT_TIMESTAMP")

    sql = f"""
        INSERT INTO {TABLE_GASTOS} (
            {", ".join(columns)}
        ) VALUES (
            {", ".join(values)}
        )
    """
    cur.execute(sql, params)
    return int(cur.lastrowid)


def update_gasto_full(conn: sqlite3.Connection, gasto_id: int, payload: dict) -> None:
    cur = conn.cursor()
    payload = dict(payload or {})

    allowed_fields = [
        "fecha",
        "motivo",
        "proveedor_id",
        "proveedor",
        "numero_factura",
        "descripcion",
        "con_soporte",
        "sin_soporte",
        "subtotal_factura",
        "servicios_10",
        "subtotal_sin_iva",
        "iva",
        "total_con_iva",
        "observacion",
        "ccb",
        "es_caja_chica",
        "reembolso_vendedor",
        "tarjeta_sin_soporte",
        "boletos_aereos",
        "factura_xml_id",
        "centro_costo",
        "cuenta_contable",
    ]

    sets = []
    params = []

    for field in allowed_fields:
        if field in payload:
            sets.append(f"{field} = ?")
            params.append(payload.get(field))

    if not sets:
        return

    params.append(gasto_id)
    sql = f"""
        UPDATE {TABLE_GASTOS}
        SET {", ".join(sets)}
        WHERE id = ?
    """
    cur.execute(sql, params)


def get_adjuntos_by_gasto_id(conn: sqlite3.Connection, gasto_id: int) -> list[dict]:
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT *
        FROM {TABLE_ARCHIVOS}
        WHERE gasto_id = ?
        ORDER BY id ASC
        """,
        (gasto_id,),
    )
    return _dicts(cur.fetchall())


def set_aprobacion_gasto(
    conn: sqlite3.Connection,
    *,
    gasto_id: int,
    area: str,
    value: bool,
    user_id: int | None = None,
) -> None:
    area = (area or "").strip().lower()
    map_fields = {
        "ga": "ga_aprobado",
        "gg": "gg_aprobado",
        "gf": "gf_aprobado",
    }
    field = map_fields.get(area)
    if not field:
        raise ValueError("Área de aprobación inválida.")

    cur = conn.cursor()
    cur.execute(
        f"""
        UPDATE {TABLE_GASTOS}
        SET {field} = ?
        WHERE id = ?
        """,
        (1 if value else 0, gasto_id),
    )


def set_aprobacion_gasto_masivo(
    conn: sqlite3.Connection,
    *,
    ids: list[int],
    area: str,
    value: bool,
    user_id: int | None = None,
) -> int:
    ids = [int(x) for x in ids if str(x).strip().isdigit()]
    if not ids:
        return 0

    area = (area or "").strip().lower()
    map_fields = {
        "ga": "ga_aprobado",
        "gg": "gg_aprobado",
        "gf": "gf_aprobado",
    }
    field = map_fields.get(area)
    if not field:
        raise ValueError("Área de aprobación inválida.")

    ph = ",".join(["?"] * len(ids))
    cur = conn.cursor()
    cur.execute(
        f"""
        UPDATE {TABLE_GASTOS}
        SET {field} = ?
        WHERE id IN ({ph})
        """,
        [1 if value else 0, *ids],
    )
    return cur.rowcount


def delete_gasto_full(conn: sqlite3.Connection, gasto_id: int) -> None:
    cur = conn.cursor()
    cur.execute(f"DELETE FROM {TABLE_DETALLE} WHERE gasto_id = ?", (gasto_id,))
    cur.execute(f"DELETE FROM {TABLE_ARCHIVOS} WHERE gasto_id = ?", (gasto_id,))
    cur.execute(f"DELETE FROM {TABLE_GASTOS} WHERE id = ?", (gasto_id,))


def get_gastos_by_ids(conn: sqlite3.Connection, ids: list[int]) -> list[dict]:
    ids = [int(x) for x in ids if str(x).strip().isdigit()]
    if not ids:
        return []

    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    ph = ",".join(["?"] * len(ids))
    cur.execute(
        f"""
        SELECT *
        FROM {TABLE_GASTOS}
        WHERE id IN ({ph})
        ORDER BY id
        """,
        ids,
    )
    return _dicts(cur.fetchall())