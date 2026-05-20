# modules/gastos_helpers.py
from __future__ import annotations

import unicodedata
from datetime import date, timedelta
from flask import request
from typing import Dict, Any

from .db import get_db
from .config import TABLE_GASTOS
from flask import current_app
# ---------------- filtros ----------------
from typing import Dict, Any, Tuple
from flask import current_app

def collect_gastos_filters2(request, session, privileged_roles=None) -> tuple[dict, list[str], list, bool]:
    if privileged_roles is None:
        privileged_roles = {
            'admin', 'gerente financiero', 'gerente general', 'coordinador',
            'gerente', 'gerente de área', 'gerente de area'
        }

    desde           = (request.args.get('desde') or '').strip()
    hasta           = (request.args.get('hasta') or '').strip()
    proveedor_id    = (request.args.get('proveedor_id') or '').strip()
    proveedor_txt   = (request.args.get('proveedor') or request.args.get('proveedor_nombre') or '').strip()
    centro          = (request.args.get('centro') or '').strip()
    motivo          = (request.args.get('motivo') or '').strip()
    ccb_raw         = (request.args.get('ccb') or '').strip()
    pend_raw        = (request.args.get('pendientes') or '').strip()
    pend_view       = (request.args.get('pend_view') or '').strip()
    tipo            = (request.args.get('tipo') or '').strip().lower()
    descripcion     = (request.args.get('descripcion') or '').strip()
    usuario_id_raw  = (request.args.get('usuario_id') or '').strip()

    def _is_true(v: str) -> bool:
        return v not in ('', '0', 'false', 'False', 'no', 'off', None)

    pendientes_bool = _is_true(pend_raw)

    filtros = {
        'desde':        desde or None,
        'hasta':        hasta or None,
        'proveedor_id': int(proveedor_id) if proveedor_id.isdigit() else None,
        'proveedor':    proveedor_txt or None,
        'centro':       centro or None,
        'motivo':       motivo or None,
        'ccb':          ccb_raw if ccb_raw in ('0', '1') else None,
        'pendientes':   1 if pendientes_bool else None,
        'pend_view':    pend_view or None,
        'tipo':         tipo or None,
        'descripcion':  descripcion or None,
        'usuario_id':   int(usuario_id_raw) if usuario_id_raw.isdigit() else None,
    }

    role_name = (session.get('rol') or '').strip().lower()
    is_privileged = role_name in {r.lower() for r in privileged_roles}

    uid = session.get('usuario_id') or session.get('user_id') or session.get('uid')
    try:
        uid = int(uid)
    except (TypeError, ValueError):
        uid = None

    where, args = [], []

    # -----------------------------
    # Filtros base
    # -----------------------------
    if desde:
        where.append("CAST(g.fecha AS date) >= CAST(? AS date)")
        args.append(desde)

    if hasta:
        where.append("CAST(g.fecha AS date) <= CAST(? AS date)")
        args.append(hasta)

    if filtros['proveedor_id'] is not None:
        where.append("g.proveedor_id = ?")
        args.append(filtros['proveedor_id'])
    elif proveedor_txt:
        where.append("LOWER(COALESCE(t.nombre, g.proveedor)) LIKE ?")
        args.append(f"%{proveedor_txt.lower()}%")

    if centro:
        where.append("LOWER(g.centro_costo) LIKE ?")
        args.append(f"%{centro.lower()}%")

    if motivo:
        where.append("LOWER(g.motivo) LIKE ?")
        args.append(f"%{motivo.lower()}%")

    if descripcion:
        where.append("LOWER(g.motivo) LIKE ?")
        args.append(f"%{descripcion.lower()}%")

    if is_privileged and filtros.get('usuario_id') is not None:
        where.append("g.usuario_id = ?")
        args.append(filtros['usuario_id'])

    if tipo in ('caja_chica', 'reembolso', 'tarjeta', 'tarjeta_online', 'boletos_aereos', 'tarjeta_boletos'):
        if tipo == 'caja_chica':
            where.append("COALESCE(g.es_caja_chica,0)=1")
        elif tipo == 'reembolso':
            where.append("COALESCE(g.reembolso_vendedor,0)=1")
        elif tipo in ('boletos_aereos', 'tarjeta_boletos'):
            where.append("COALESCE(g.boletos_aereos,0)=1")
        elif tipo == 'tarjeta_online':
            where.append("COALESCE(g.tarjeta_sin_soporte,0)=1")
            where.append("COALESCE(g.es_caja_chica,0)=0")
            where.append("COALESCE(g.reembolso_vendedor,0)=0")
        else:
            where.append("COALESCE(g.es_caja_chica,0)=0")
            where.append("COALESCE(g.reembolso_vendedor,0)=0")
            where.append("COALESCE(g.tarjeta_sin_soporte,0)=0")
            where.append("COALESCE(g.boletos_aereos,0)=0")

    if ccb_raw == "1":
        where.append("COALESCE(g.ccb,0)=1")
    elif ccb_raw == "0":
        where.append("COALESCE(g.ccb,0)=0")

    ga_eff_sql = """
    CASE
      WHEN LOWER(COALESCE(g.ga_actor, g.ga_aprobador, g.ga_aprobador_rol, '')) IN ('gg','gerente general','gerente_general')
        THEN COALESCE(g.gg_aprobado,0)
      WHEN LOWER(COALESCE(g.ga_actor, g.ga_aprobador, g.ga_aprobador_rol, '')) IN ('gf','gerente financiero','gerente_financiero')
        THEN COALESCE(g.gf_aprobado,0)
      ELSE
        CASE
          WHEN COALESCE(g.ga_aprobado,0)=0 AND (COALESCE(g.gg_aprobado,0)=1 OR COALESCE(g.gf_aprobado,0)=1)
            THEN 1
          ELSE COALESCE(g.ga_aprobado,0)
        END
    END
    """

    ga_step_pending_sql = """
    CASE
      WHEN LOWER(COALESCE(g.ga_actor, g.ga_aprobador, g.ga_aprobador_rol, '')) IN ('gg','gerente general','gerente_general')
        THEN CASE WHEN COALESCE(g.gg_aprobado,0)=0 THEN 1 ELSE 0 END
      WHEN LOWER(COALESCE(g.ga_actor, g.ga_aprobador, g.ga_aprobador_rol, '')) IN ('gf','gerente financiero','gerente_financiero')
        THEN CASE WHEN COALESCE(g.gf_aprobado,0)=0 THEN 1 ELSE 0 END
      ELSE
        CASE WHEN COALESCE(g.ga_aprobado,0)=0 THEN 1 ELSE 0 END
    END
    """

    pend_mode = (pend_view or '').strip().lower()

    if not pend_mode and pendientes_bool:
        pend_mode = "1"

    if pend_mode in ("1", "mis_aprobaciones", "pend_sap"):
        where.append("(g.sap_contabilizacion IS NULL OR LTRIM(RTRIM(COALESCE(g.sap_contabilizacion,'')))='')")

    if pend_mode == "1":
        if role_name in ('gerente', 'gerente de área', 'gerente de area'):
            where.append("""
                COALESCE(g.ga_aprobado,0)=0
                AND COALESCE(g.gg_aprobado,0)=0
                AND COALESCE(g.gf_aprobado,0)=0
            """)
        elif role_name == 'gerente general':
            where.append("""
                COALESCE(g.ga_aprobado,0)=1
                AND COALESCE(g.gg_aprobado,0)=0
                AND COALESCE(g.gf_aprobado,0)=0
            """)
        elif role_name == 'gerente financiero':
            where.append("""
                COALESCE(g.ga_aprobado,0)=1
                AND COALESCE(g.gg_aprobado,0)=1
                AND COALESCE(g.gf_aprobado,0)=0
            """)
        else:
            where.append("1=0")

    elif pend_mode == "mis_aprobaciones":
        if role_name != "usuario":
            where.append("1=0")
        else:
            where.append("g.usuario_id = ?")
            args.append(uid or -1)
            where.append(f"({ga_step_pending_sql}) = 1")

    elif pend_mode == "pend_sap":
        if role_name not in ("coordinador", "admin"):
            where.append("1=0")
        else:
            where.append(f"""
                (
                  (
                    (COALESCE(g.es_caja_chica,0)=1 OR COALESCE(g.reembolso_vendedor,0)=1 OR COALESCE(g.boletos_aereos,0)=1)
                    AND ({ga_eff_sql}) = 1
                  )
                  OR
                  (
                    (COALESCE(g.es_caja_chica,0)=0 AND COALESCE(g.reembolso_vendedor,0)=0 AND COALESCE(g.boletos_aereos,0)=0)
                    AND COALESCE(g.ga_aprobado,0)=1
                    AND COALESCE(g.gg_aprobado,0)=1
                    AND COALESCE(g.gf_aprobado,0)=1
                  )
                )
            """)

    if not is_privileged and pend_mode != "mis_aprobaciones":
        where.append("g.usuario_id = ?")
        args.append(uid or -1)

    return filtros, where, args, is_privileged


def collect_gastos_filters(request, session, privileged_roles=None) -> tuple[dict, list[str], list, bool]:
    if privileged_roles is None:
        privileged_roles = {
            'admin', 'gerente financiero', 'gerente general', 'coordinador',
            'gerente', 'gerente de área', 'gerente de area'
        }

    desde           = (request.args.get('desde') or '').strip()
    hasta           = (request.args.get('hasta') or '').strip()
    proveedor_id    = (request.args.get('proveedor_id') or '').strip()
    proveedor_txt   = (request.args.get('proveedor') or request.args.get('proveedor_nombre') or '').strip()
    centro          = (request.args.get('centro') or '').strip()
    motivo          = (request.args.get('motivo') or '').strip()
    gerente_id_raw  = (request.args.get('gerente_id') or '').strip()
    ccb_raw         = (request.args.get('ccb') or '').strip()
    pend_raw        = (request.args.get('pendientes') or '').strip()
    pend_view       = (request.args.get('pend_view') or '').strip()
    tipo            = (request.args.get('tipo') or '').strip().lower()
    descripcion     = (request.args.get('descripcion') or '').strip()
    usuario_id_raw  = (request.args.get('usuario_id') or '').strip()

    def _is_true(v: str) -> bool:
        return v not in ('', '0', 'false', 'False', 'no', 'off', None)

    pendientes_bool = _is_true(pend_raw)

    filtros = {
        'desde':        desde or None,
        'hasta':        hasta or None,
        'proveedor_id': int(proveedor_id) if proveedor_id.isdigit() else None,
        'proveedor':    proveedor_txt or None,
        'centro':       centro or None,
        'motivo':       motivo or None,
        'ccb':          ccb_raw or None,
        'pendientes':   1 if pendientes_bool else None,
        'pend_view':    pend_view or None,
        'tipo':         tipo or None,
        'descripcion':  descripcion or None,
        'usuario_id':   int(usuario_id_raw) if usuario_id_raw.isdigit() else None,
        'gerente_id':   int(gerente_id_raw) if gerente_id_raw.isdigit() else None,
    }

    role_name = (session.get('rol') or '').strip().lower()
    is_privileged = role_name in {r.lower() for r in privileged_roles}

    uid = session.get('usuario_id') or session.get('user_id') or session.get('uid')
    try:
        uid = int(uid)
    except (TypeError, ValueError):
        uid = None

    where, args = [], []

    # -----------------------------
    # Filtros base
    # -----------------------------
    if desde:
        where.append("CAST(g.fecha AS date) >= CAST(? AS date)")
        args.append(desde)

    if hasta:
        where.append("CAST(g.fecha AS date) <= CAST(? AS date)")
        args.append(hasta)

    if filtros['proveedor_id'] is not None:
        where.append("g.proveedor_id = ?")
        args.append(filtros['proveedor_id'])
    elif proveedor_txt:
        where.append("LOWER(COALESCE(t.nombre, g.proveedor)) LIKE ?")
        args.append(f"%{proveedor_txt.lower()}%")

    if centro:
        where.append("LOWER(g.centro_costo) LIKE ?")
        args.append(f"%{centro.lower()}%")

    if motivo:
        where.append("LOWER(g.motivo) LIKE ?")
        args.append(f"%{motivo.lower()}%")

    if descripcion:
        where.append("LOWER(g.motivo) LIKE ?")
        args.append(f"%{descripcion.lower()}%")

    if is_privileged and filtros.get('usuario_id') is not None:
        where.append("g.usuario_id = ?")
        args.append(filtros['usuario_id'])

    # -----------------------------
    # Tipo de gasto
    # -----------------------------
    if tipo in ('caja_chica', 'reembolso', 'tarjeta', 'tarjeta_online', 'boletos_aereos', 'tarjeta_boletos'):
        if tipo == 'caja_chica':
            where.append("COALESCE(g.es_caja_chica,0)=1")
        elif tipo == 'reembolso':
            where.append("COALESCE(g.reembolso_vendedor,0)=1")
        elif tipo in ('boletos_aereos', 'tarjeta_boletos'):
            where.append("COALESCE(g.boletos_aereos,0)=1")
        elif tipo == 'tarjeta_online':
            where.append("COALESCE(g.tarjeta_sin_soporte,0)=1")
            where.append("COALESCE(g.es_caja_chica,0)=0")
            where.append("COALESCE(g.reembolso_vendedor,0)=0")
        else:
            where.append("COALESCE(g.es_caja_chica,0)=0")
            where.append("COALESCE(g.reembolso_vendedor,0)=0")
            where.append("COALESCE(g.tarjeta_sin_soporte,0)=0")
            where.append("COALESCE(g.boletos_aereos,0)=0")

    if ccb_raw == "1":
        where.append("COALESCE(g.ccb,0)=1")
    elif ccb_raw == "0":
        where.append("COALESCE(g.ccb,0)=0")

    ga_eff_sql = """
    CASE
      WHEN LOWER(COALESCE(g.ga_actor, g.ga_aprobador, g.ga_aprobador_rol, '')) IN ('gg','gerente general','gerente_general')
        THEN COALESCE(g.gg_aprobado,0)
      WHEN LOWER(COALESCE(g.ga_actor, g.ga_aprobador, g.ga_aprobador_rol, '')) IN ('gf','gerente financiero','gerente_financiero')
        THEN COALESCE(g.gf_aprobado,0)
      ELSE
        CASE
          WHEN COALESCE(g.ga_aprobado,0)=0 AND (COALESCE(g.gg_aprobado,0)=1 OR COALESCE(g.gf_aprobado,0)=1)
            THEN 1
          ELSE COALESCE(g.ga_aprobado,0)
        END
    END
    """

    ga_step_pending_sql = """
    CASE
      WHEN LOWER(COALESCE(g.ga_actor, g.ga_aprobador, g.ga_aprobador_rol, '')) IN ('gg','gerente general','gerente_general')
        THEN CASE WHEN COALESCE(g.gg_aprobado,0)=0 THEN 1 ELSE 0 END
      WHEN LOWER(COALESCE(g.ga_actor, g.ga_aprobador, g.ga_aprobador_rol, '')) IN ('gf','gerente financiero','gerente_financiero')
        THEN CASE WHEN COALESCE(g.gf_aprobado,0)=0 THEN 1 ELSE 0 END
      ELSE
        CASE WHEN COALESCE(g.ga_aprobado,0)=0 THEN 1 ELSE 0 END
    END
    """

    pend_mode = (pend_view or '').strip().lower()

    if not pend_mode and pendientes_bool:
        pend_mode = "1"

    if pend_mode in ("1", "mis_aprobaciones", "pend_sap"):
        where.append("(g.sap_contabilizacion IS NULL OR LTRIM(RTRIM(COALESCE(g.sap_contabilizacion,'')))='')")

    if pend_mode == "1":
        if role_name in ('gerente', 'gerente de área', 'gerente de area'):
            where.append("""
                COALESCE(g.ga_aprobado,0)=0
                AND COALESCE(g.gg_aprobado,0)=0
                AND COALESCE(g.gf_aprobado,0)=0
            """)
        elif role_name == 'gerente general':
            where.append("""
                COALESCE(g.ga_aprobado,0)=1
                AND COALESCE(g.gg_aprobado,0)=0
                AND COALESCE(g.gf_aprobado,0)=0
            """)
        elif role_name == 'gerente financiero':
            where.append("""
                COALESCE(g.ga_aprobado,0)=1
                AND COALESCE(g.gg_aprobado,0)=1
                AND COALESCE(g.gf_aprobado,0)=0
            """)
        else:
            where.append("1=0")

    elif pend_mode == "mis_aprobaciones":
        if role_name != "usuario":
            where.append("1=0")
        else:
            where.append("g.usuario_id = ?")
            args.append(uid or -1)
            where.append(f"({ga_step_pending_sql}) = 1")

    elif pend_mode == "pend_sap":
        if role_name not in ("coordinador", "admin"):
            where.append("1=0")
        else:
            where.append(f"""
                (
                  (
                    (COALESCE(g.es_caja_chica,0)=1 OR COALESCE(g.reembolso_vendedor,0)=1 OR COALESCE(g.boletos_aereos,0)=1)
                    AND ({ga_eff_sql}) = 1
                  )
                  OR
                  (
                    (COALESCE(g.es_caja_chica,0)=0 AND COALESCE(g.reembolso_vendedor,0)=0 AND COALESCE(g.boletos_aereos,0)=0)
                    AND COALESCE(g.ga_aprobado,0)=1
                    AND COALESCE(g.gg_aprobado,0)=1
                    AND COALESCE(g.gf_aprobado,0)=1
                  )
                )
            """)

    if not is_privileged and pend_mode != "mis_aprobaciones":
        where.append("g.usuario_id = ?")
        args.append(uid or -1)

    return filtros, where, args, is_privileged




def collect_gastos_pendientes_aprobacion_filters(request, session, privileged_roles=None):
    """
    Collect exclusivo para /reembolsos/gastos/pendientes-aprobacion
    """

    if privileged_roles is None:
        privileged_roles = {
            'admin', 'gerente financiero', 'gerente general', 'coordinador',
            'gerente', 'gerente de área', 'gerente de area'
        }

    desde           = (request.args.get('desde') or '').strip()
    hasta           = (request.args.get('hasta') or '').strip()
    proveedor_id    = (request.args.get('proveedor_id') or '').strip()
    proveedor_txt   = (request.args.get('proveedor') or request.args.get('proveedor_nombre') or '').strip()
    centro          = (request.args.get('centro') or '').strip()
    motivo          = (request.args.get('motivo') or '').strip()
    tipo            = (request.args.get('tipo') or '').strip().lower()
    descripcion     = (request.args.get('descripcion') or '').strip()
    usuario_id_raw  = (request.args.get('usuario_id') or '').strip()
    gerente_id_raw  = (request.args.get('gerente_id') or '').strip()
    ccb_raw         = (request.args.get('ccb') or '').strip()

    filtros = {
        'desde':        desde or None,
        'hasta':        hasta or None,
        'proveedor_id': int(proveedor_id) if proveedor_id.isdigit() else None,
        'proveedor':    proveedor_txt or None,
        'centro':       centro or None,
        'motivo':       motivo or None,
        'tipo':         tipo or None,
        'descripcion':  descripcion or None,
        'usuario_id':   int(usuario_id_raw) if usuario_id_raw.isdigit() else None,
        'gerente_id':   int(gerente_id_raw) if gerente_id_raw.isdigit() else None,
        'ccb':          (ccb_raw if ccb_raw in ('0', '1') else ''),
        'pendientes':   "1",
    }

    role_name = (session.get('rol') or '').strip().lower()
    is_privileged = role_name in {r.lower() for r in privileged_roles}

    uid = session.get('usuario_id') or session.get('user_id') or session.get('uid')
    try:
        uid = int(uid)
    except Exception:
        uid = None

    where, args = [], []

    if desde:
        where.append("CAST(g.fecha AS date) >= CAST(? AS date)")
        args.append(desde)

    if hasta:
        where.append("CAST(g.fecha AS date) <= CAST(? AS date)")
        args.append(hasta)

    if filtros['proveedor_id'] is not None:
        where.append("g.proveedor_id = ?")
        args.append(filtros['proveedor_id'])
    elif proveedor_txt:
        where.append("LOWER(COALESCE(t.nombre, g.proveedor)) LIKE ?")
        args.append(f"%{proveedor_txt.lower()}%")

    if centro:
        where.append("LOWER(g.centro_costo) LIKE ?")
        args.append(f"%{centro.lower()}%")

    if motivo:
        where.append("LOWER(g.motivo) LIKE ?")
        args.append(f"%{motivo.lower()}%")

    if descripcion:
        where.append("LOWER(g.motivo) LIKE ?")
        args.append(f"%{descripcion.lower()}%")

    if is_privileged and filtros.get('usuario_id') is not None:
        where.append("g.usuario_id = ?")
        args.append(filtros['usuario_id'])

    if tipo:
        if tipo == 'caja_chica':
            where.append("COALESCE(g.es_caja_chica,0)=1")
        elif tipo == 'reembolso':
            where.append("COALESCE(g.reembolso_vendedor,0)=1")
        elif tipo in ('boletos_aereos', 'tarjeta_boletos'):
            where.append("COALESCE(g.boletos_aereos,0)=1")
        elif tipo == 'tarjeta_online':
            where.append("COALESCE(g.tarjeta_sin_soporte,0)=1")
            where.append("COALESCE(g.es_caja_chica,0)=0")
            where.append("COALESCE(g.reembolso_vendedor,0)=0")
        elif tipo == 'tarjeta':
            where.append("COALESCE(g.es_caja_chica,0)=0")
            where.append("COALESCE(g.reembolso_vendedor,0)=0")

    if ccb_raw == "1":
        where.append("COALESCE(g.ccb,0)=1")
    elif ccb_raw == "0":
        where.append("COALESCE(g.ccb,0)=0")

    where.append("(g.sap_contabilizacion IS NULL OR LTRIM(RTRIM(COALESCE(g.sap_contabilizacion,'')))='')")

    if not is_privileged:
        where.append("g.usuario_id = ?")
        args.append(uid or -1)

    return filtros, where, args, is_privileged

def recalc_gasto_totales(conn, gasto_id):
    cur = conn.cursor()

    cur.execute("""
        SELECT
            COALESCE(SUM(con_soporte), 0)        AS con_soporte,
            COALESCE(SUM(sin_soporte), 0)        AS sin_soporte,
            COALESCE(SUM(subtotal_factura), 0)   AS subtotal_factura,
            COALESCE(SUM(servicios_10), 0)       AS servicios_10,
            COALESCE(SUM(subtotal_sin_iva), 0)   AS subtotal_sin_iva,
            COALESCE(SUM(iva), 0)                AS iva,
            COALESCE(SUM(total_con_iva), 0)      AS total_con_iva
        FROM gastos_tarjeta_detalle
        WHERE gasto_id = ?
    """, (gasto_id,))

    row = cur.fetchone()

    if not row:
        cs = ss = sf = s10 = ssi = iv = tci = 0
    else:
        try:
            cs  = row["con_soporte"] or 0
            ss  = row["sin_soporte"] or 0
            sf  = row["subtotal_factura"] or 0
            s10 = row["servicios_10"] or 0
            ssi = row["subtotal_sin_iva"] or 0
            iv  = row["iva"] or 0
            tci = row["total_con_iva"] or 0
        except Exception:
            cs  = row[0] or 0
            ss  = row[1] or 0
            sf  = row[2] or 0
            s10 = row[3] or 0
            ssi = row[4] or 0
            iv  = row[5] or 0
            tci = row[6] or 0

    cur.execute("""
        UPDATE gastos_tarjeta
        SET
            con_soporte = ?,
            sin_soporte = ?,
            subtotal_factura = ?,
            servicios_10 = ?,
            subtotal_sin_iva = ?,
            iva = ?,
            total_con_iva = ?
        WHERE id = ?
    """, (cs, ss, sf, s10, ssi, iv, tci, gasto_id))

# ---------------- util ----------------
def norm(txt: str) -> str:
    if not isinstance(txt, str):
        return ''
    t = unicodedata.normalize('NFKD', txt).encode('ascii', 'ignore').decode('ascii')
    return ' '.join(t.strip().lower().split())

def parse_num(x):
    if x is None or str(x).strip() == "": return None
    s = str(x).strip().replace(",", ".")
    try: return float(s)
    except ValueError: return None

def build_fecha(anio, mes, dia):
    if not (anio and mes and dia): return None
    try:
        y = int(anio); m = int(mes); d = int(dia)
        return f"{y:04d}-{m:02d}-{d:02d}"
    except ValueError:
        return None

# ---------------- schema ----------------
def _col_exists(conn, table, col):
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return any(r["name"] == col for r in cur.fetchall())

def _add_col_if_missing(conn, table, col, decl, default=None):
    if not _col_exists(conn, table, col):
        cur = conn.cursor()
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
        if default is not None:
            cur.execute(f"UPDATE {table} SET {col}=?", (default,))
        conn.commit()

def ensure_gastos_schema():
    conn = get_db(); cur = conn.cursor()
    

    # Tabla de adjuntos (moverla aquí evita locks durante POST)
    cur.execute("""
            CREATE TABLE IF NOT EXISTS gastos_tarjeta_archivos(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gasto_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                uploaded_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (gasto_id) REFERENCES gastos_tarjeta(id) ON DELETE CASCADE
            )
        """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS configuracion(
            clave TEXT PRIMARY KEY,
            valor TEXT
        )
    """)

    
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_GASTOS} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            anio INTEGER NOT NULL,
            mes INTEGER NOT NULL,
            dia INTEGER NOT NULL,
            fecha TEXT NOT NULL,
            motivo TEXT NOT NULL,
            proveedor TEXT,
            proveedor_id INTEGER,
            centro_costo TEXT,
            con_soporte REAL NOT NULL DEFAULT 0,
            sin_soporte REAL NOT NULL DEFAULT 0,
            subtotal_factura REAL NOT NULL DEFAULT 0,
            servicios_10 REAL NOT NULL DEFAULT 0,
            subtotal_sin_iva REAL NOT NULL DEFAULT 0,
            iva REAL NOT NULL DEFAULT 0,
            total_con_iva REAL NOT NULL DEFAULT 0,
            fecha_autorizacion TEXT,
            numero_factura TEXT,
            clave_autorizacion TEXT,
            ccb INTEGER NOT NULL DEFAULT 0,            -- check con cargo a bono
            sap_contabilizacion INTEGER,               -- numero de contabilizacion SAP (oculto en UI)
            usuario_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    # índices
    cur.execute(f'CREATE INDEX IF NOT EXISTS idx_gastos_tc_fecha ON {TABLE_GASTOS}(fecha)')
    cur.execute(f'CREATE INDEX IF NOT EXISTS idx_gastos_tc_usuario ON {TABLE_GASTOS}(usuario_id)')
    cur.execute(f'CREATE INDEX IF NOT EXISTS ix_{TABLE_GASTOS}_proveedor_id ON {TABLE_GASTOS}(proveedor_id)')
    # columnas que podrían faltar
    _add_col_if_missing(conn, TABLE_GASTOS, "factura_xml_id", "INTEGER", None)
    _add_col_if_missing(conn, TABLE_GASTOS, "ccb", "INTEGER NOT NULL DEFAULT 0", 0)
    _add_col_if_missing(conn, TABLE_GASTOS, "sap_contabilizacion", "INTEGER", None)
    _add_col_if_missing(conn, TABLE_GASTOS, "fecha_autorizacion", "TEXT", None)
    _add_col_if_missing(conn, TABLE_GASTOS, "numero_factura", "TEXT", None)
    _add_col_if_missing(conn, TABLE_GASTOS, "clave_autorizacion", "TEXT", None)
    # aprobaciones (por si no existen)
    _add_col_if_missing(conn, TABLE_GASTOS, "gg_aprobado", "INTEGER NOT NULL DEFAULT 0", 0)
    _add_col_if_missing(conn, TABLE_GASTOS, "gg_aprobado_por", "INTEGER", None)
    _add_col_if_missing(conn, TABLE_GASTOS, "gg_aprobado_at", "TEXT", None)
    _add_col_if_missing(conn, TABLE_GASTOS, "gf_aprobado", "INTEGER NOT NULL DEFAULT 0", 0)
    _add_col_if_missing(conn, TABLE_GASTOS, "gf_aprobado_por", "INTEGER", None)
    _add_col_if_missing(conn, TABLE_GASTOS, "gf_aprobado_at", "TEXT", None)
    _add_col_if_missing(conn, TABLE_GASTOS, "ga_aprobado", "INTEGER NOT NULL DEFAULT 0", 0)
    _add_col_if_missing(conn, TABLE_GASTOS, "ga_aprobado_por", "INTEGER", None)
    _add_col_if_missing(conn, TABLE_GASTOS, "ga_aprobado_at", "TEXT", None)
    _add_col_if_missing(conn, TABLE_GASTOS, "sap_response_json", "TEXT", None)
    _add_col_if_missing(conn, TABLE_GASTOS, "sap_error_msg", "TEXT", None)
    _add_col_if_missing(conn, TABLE_GASTOS, "sap_enviado_at", "TEXT", None)   
    #_add_col_if_missing(conn, TABLE_GASTOS, "orden_compra ", "TEXT", None)   

    
    
    conn.commit(); conn.close()

def ensure_gastos_detalle_schema():
    conn = get_db(); cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS gastos_tarjeta_detalle(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gasto_id INTEGER NOT NULL,
            descripcion TEXT,
            observacion TEXT,
            centro_costo TEXT,
            motivo TEXT,
            indicador TEXT,   -- 'CR' o 'CE'
            con_soporte REAL NOT NULL DEFAULT 0,
            sin_soporte REAL NOT NULL DEFAULT 0,
            subtotal_factura REAL NOT NULL DEFAULT 0,
            servicios_10 REAL NOT NULL DEFAULT 0,
            subtotal_sin_iva REAL NOT NULL DEFAULT 0,
            iva REAL NOT NULL DEFAULT 0,
            total_con_iva REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY(gasto_id) REFERENCES gastos_tarjeta(id) ON DELETE CASCADE
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS ix_gtd_gasto ON gastos_tarjeta_detalle(gasto_id)")
    # asegurar columnas nuevas si venías de esquema viejo
    cols = {r['name'] for r in cur.execute("PRAGMA table_info(gastos_tarjeta_detalle)").fetchall()}
    if 'centro_costo' not in cols:
        cur.execute("ALTER TABLE gastos_tarjeta_detalle ADD COLUMN centro_costo TEXT")
    if 'motivo' not in cols:
        cur.execute("ALTER TABLE gastos_tarjeta_detalle ADD COLUMN motivo TEXT")
    if 'indicador' not in cols:
        cur.execute("ALTER TABLE gastos_tarjeta_detalle ADD COLUMN indicador TEXT")
    
    cur.execute("""
                CREATE TABLE IF NOT EXISTS gastos_tarjeta_archivos(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    gasto_id INTEGER NOT NULL,
                    filename TEXT NOT NULL,
                    uploaded_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (gasto_id) REFERENCES gastos_tarjeta(id) ON DELETE CASCADE
                )
            """)
        


    conn.commit(); conn.close()

def ensure_proveedor_fk(conn):
    _add_col_if_missing(conn, TABLE_GASTOS, "proveedor_id", "INTEGER")
    cur = conn.cursor()
    cur.execute(f"CREATE INDEX IF NOT EXISTS ix_{TABLE_GASTOS}_proveedor_id ON {TABLE_GASTOS}(proveedor_id)")
    cur.execute(f"CREATE INDEX IF NOT EXISTS idx_gastos_usuario ON gastos_tarjeta(usuario_id)")
    conn.commit()

def recalc_gasto_totales(conn, gasto_id):
    cur = conn.cursor()

    cur.execute("""
        SELECT
            COALESCE(SUM(con_soporte), 0)        AS con_soporte,
            COALESCE(SUM(sin_soporte), 0)        AS sin_soporte,
            COALESCE(SUM(subtotal_factura), 0)   AS subtotal_factura,
            COALESCE(SUM(servicios_10), 0)       AS servicios_10,
            COALESCE(SUM(subtotal_sin_iva), 0)   AS subtotal_sin_iva,
            COALESCE(SUM(iva), 0)                AS iva,
            COALESCE(SUM(total_con_iva), 0)      AS total_con_iva
        FROM gastos_tarjeta_detalle
        WHERE gasto_id = ?
    """, (gasto_id,))

    row = cur.fetchone()

    if not row:
        cs = ss = sf = s10 = ssi = iv = tci = 0
    else:
        try:
            # caso row tipo dict / compat row
            cs  = row["con_soporte"] or 0
            ss  = row["sin_soporte"] or 0
            sf  = row["subtotal_factura"] or 0
            s10 = row["servicios_10"] or 0
            ssi = row["subtotal_sin_iva"] or 0
            iv  = row["iva"] or 0
            tci = row["total_con_iva"] or 0
        except Exception:
            # fallback por posición
            cs  = row[0] or 0
            ss  = row[1] or 0
            sf  = row[2] or 0
            s10 = row[3] or 0
            ssi = row[4] or 0
            iv  = row[5] or 0
            tci = row[6] or 0

    cur.execute("""
        UPDATE gastos_tarjeta
        SET
            con_soporte = ?,
            sin_soporte = ?,
            subtotal_factura = ?,
            servicios_10 = ?,
            subtotal_sin_iva = ?,
            iva = ?,
            total_con_iva = ?
        WHERE id = ?
    """, (cs, ss, sf, s10, ssi, iv, tci, gasto_id))

def rango_fechas_desde_request(default_days=30):
    q_desde = (request.args.get('desde') or '').strip()
    q_hasta = (request.args.get('hasta') or '').strip()
    if q_desde and q_hasta:
        return q_desde, q_hasta
    from datetime import date, timedelta
    hoy = date.today()
    desde = hoy - timedelta(days=default_days - 1)
    return (str(desde), str(hoy))
