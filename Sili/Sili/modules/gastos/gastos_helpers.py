# modules/gastos_helpers.py
from __future__ import annotations

import unicodedata
from datetime import date, timedelta
from flask import request
from typing import Dict, Any

from ..db import get_db
from ..config import TABLE_GASTOS
from flask import current_app
 
# ---------------- filtros ----------------
from typing import Dict, Any, Tuple

def collect_gastos_filters2(request, session, privileged_roles=None) -> tuple[dict, list[str], list, bool]:
    if privileged_roles is None:
        privileged_roles = {
            'admin', 'gerente financiero', 'gerente general', 'coordinador',
            'gerente', 'gerente de área', 'gerente de area'
        }

    # Parámetros
    desde           = (request.args.get('desde') or '').strip()
    hasta           = (request.args.get('hasta') or '').strip()
    proveedor_id    = (request.args.get('proveedor_id') or '').strip()
    proveedor_txt   = (request.args.get('proveedor') or request.args.get('proveedor_nombre') or '').strip()
    centro          = (request.args.get('centro') or '').strip()
    motivo          = (request.args.get('motivo') or '').strip()
    ccb_raw         = (request.args.get('ccb') or '').strip()

    # 🔹 Tu filtro viejo (bool) se mantiene
    pend_raw        = (request.args.get('pendientes') or '').strip()

    # 🔹 NUEVO: un “modo” de pendientes (string)
    # - '1'                 => pendientes por rol gerencial (como hoy)
    # - 'mis_aprobaciones'  => rol usuario: sus gastos pendientes de aprobaciones
    # - 'pend_sap'          => coordinador/admin: todo aprobado pero sin doc SAP
    pend_view       = (request.args.get('pend_view') or '').strip()

    tipo            = (request.args.get('tipo') or '').strip().lower()
    descripcion     = (request.args.get('descripcion') or '').strip()
    usuario_id_raw  = (request.args.get('usuario_id') or '').strip()

    # Flags booleanos
    def _is_true(v: str) -> bool:
        return v not in ('', '0', 'false', 'False', 'no', 'off', None)

    ccb = _is_true(ccb_raw)
    pendientes_bool = _is_true(pend_raw)

    filtros = {
        'desde':        desde or None,
        'hasta':        hasta or None,
        'proveedor_id': int(proveedor_id) if proveedor_id.isdigit() else None,
        'proveedor':    proveedor_txt or None,
        'centro':       centro or None,
        'motivo':       motivo or None,
        'ccb':          1 if ccb else None,
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
        where.append("date(g.fecha) >= date(?)"); args.append(desde)
    if hasta:
        where.append("date(g.fecha) <= date(?)"); args.append(hasta)

    if filtros['proveedor_id'] is not None:
        where.append("g.proveedor_id = ?"); args.append(filtros['proveedor_id'])
    elif proveedor_txt:
        where.append("LOWER(COALESCE(t.nombre, g.proveedor)) LIKE ?")
        args.append(f"%{proveedor_txt.lower()}%")

    if centro:
        where.append("LOWER(g.centro_costo) LIKE ?"); args.append(f"%{centro.lower()}%")
    if motivo:
        where.append("LOWER(g.motivo) LIKE ?"); args.append(f"%{motivo.lower()}%")

    # Detalle (tu lógica actual lo aplicaba sobre g.motivo)
    if descripcion:
        where.append("LOWER(g.motivo) LIKE ?")
        args.append(f"%{descripcion.lower()}%")

    # Usuario (solo privilegiados)
    if is_privileged and filtros.get('usuario_id') is not None:
        where.append("g.usuario_id = ?")
        args.append(filtros['usuario_id'])

    # Tipo de gasto (incluye boletos)
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
            # tarjeta normal (no caja chica, no reembolso, no online, no boletos)
            where.append("COALESCE(g.es_caja_chica,0)=0")
            where.append("COALESCE(g.reembolso_vendedor,0)=0")
            where.append("COALESCE(g.tarjeta_sin_soporte,0)=0")
            where.append("COALESCE(g.boletos_aereos,0)=0")

    # CCB
    #if ccb:
     #   where.append("COALESCE(g.ccb,0)=1")

 
    if ccb == "1":
        where.append("COALESCE(g.ccb,0)=1")
    elif ccb == "0":
        where.append("COALESCE(g.ccb,0)=0")
    # else: vacío => Todos, no filtra


    # -----------------------------
    # Helpers SQL para “GA efectivo”
    # (mismo concepto que tu backend: GA puede ser sustituido por GG/GF)
    # -----------------------------
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
        THEN COALESCE(g.gg_aprobado,0)=0
    WHEN LOWER(COALESCE(g.ga_actor, g.ga_aprobador, g.ga_aprobador_rol, '')) IN ('gf','gerente financiero','gerente_financiero')
        THEN COALESCE(g.gf_aprobado,0)=0
    ELSE
        COALESCE(g.ga_aprobado,0)=0
    END
    """


    # -----------------------------
    # PENDIENTES (3 modos)
    # -----------------------------
    pend_mode = (pend_view or '').strip().lower()

    # Mantener compatibilidad: si viene ?pendientes=1 y no viene pend_view -> úsalo como "1"
    if not pend_mode and pendientes_bool:
        pend_mode = "1"

    # Siempre que es un modo pendientes: NO enviado a SAP
    if pend_mode in ("1", "mis_aprobaciones", "pend_sap"):
        where.append("(g.sap_contabilizacion IS NULL OR TRIM(g.sap_contabilizacion)='')")

    # 3.1) Pendientes por rol gerencial (tu lógica actual)
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
            # si no es rol gerente, no debe ver esa vista
            where.append("1=0")

    # 3.2) Mis pendientes (ROL USUARIO): sus gastos que aún NO completan el flujo requerido
    
        # solo aplica a usuario; si no es usuario, bloquea para que no “jueguen” con el querystring

    elif pend_mode == "mis_aprobaciones":
        if role_name != "usuario":
            where.append("1=0")
        else:
            where.append("g.usuario_id = ?")
            args.append(uid or -1)

            # 👇 SOLO pendientes del paso GA (primer aprobador)
            where.append(f"({ga_step_pending_sql})")



 
    # 3.3) Pendientes SAP (COORDINADOR/ADMIN): todo aprobado, pero sin doc SAP
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
                AND (
                    COALESCE(g.ga_aprobado,0)=1
                    AND COALESCE(g.gg_aprobado,0)=1
                    AND COALESCE(g.gf_aprobado,0)=1
                )
              )
            )
            """)
        current_app.logger.warning(
            "DEBUG mis_aprobaciones uid=%s ga_aprobado_count=%s",
            uid,
            conn.execute("SELECT COUNT(*) FROM gastos_tarjeta WHERE usuario_id=? AND COALESCE(ga_aprobado,0)=1", (uid,)).fetchone()[0]
            )


    # -----------------------------
    # No privilegiados: solo sus registros (si no están en “mis_aprobaciones”, igual restringe)
    # -----------------------------
    if not is_privileged and pend_mode != "mis_aprobaciones":
        where.append("g.usuario_id = ?"); args.append(uid or -1)

    return filtros, where, args, is_privileged

from flask import current_app

def collect_gastos_filters(request, session, privileged_roles=None) -> tuple[dict, list[str], list, bool]:
    if privileged_roles is None:
        privileged_roles = {
            'admin', 'gerente financiero', 'gerente general', 'coordinador',
            'gerente', 'gerente de área', 'gerente de area'
        }

    # -----------------------------
    # Parámetros
    # -----------------------------
    desde           = (request.args.get('desde') or '').strip()
    hasta           = (request.args.get('hasta') or '').strip()
    proveedor_id    = (request.args.get('proveedor_id') or '').strip()
    proveedor_txt   = (request.args.get('proveedor') or request.args.get('proveedor_nombre') or '').strip()
    centro          = (request.args.get('centro') or '').strip()
    motivo          = (request.args.get('motivo') or '').strip()
    gerente_id_raw  = (request.args.get('gerente_id') or '').strip()

    # ✅ NUEVO: CCB como modo string: ''=Todos, '1'=Con CCB, '0'=Sin CCB
    ccb_raw         = (request.args.get('ccb') or '').strip()

    # Compatibilidad: pendientes bool viejo
    pend_raw        = (request.args.get('pendientes') or '').strip()

    # NUEVO: modo pendientes
    pend_view       = (request.args.get('pend_view') or '').strip()

    tipo            = (request.args.get('tipo') or '').strip().lower()
    descripcion     = (request.args.get('descripcion') or '').strip()
    usuario_id_raw  = (request.args.get('usuario_id') or '').strip()

    # -----------------------------
    # Helpers
    # -----------------------------
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
        'ccb':          ccb_raw or None,          # ✅ guarda '1' / '0' / None
        'pendientes':   1 if pendientes_bool else None,
        'pend_view':    pend_view or None,
        'tipo':         tipo or None,
        'descripcion':  descripcion or None,
        'usuario_id':   int(usuario_id_raw) if usuario_id_raw.isdigit() else None,
        'gerente_id': int(gerente_id_raw) if gerente_id_raw.isdigit() else None,
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
        where.append("date(g.fecha) >= date(?)")
        args.append(desde)

    if hasta:
        where.append("date(g.fecha) <= date(?)")
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

    # Detalle (según tu lógica actual)
    if descripcion:
        where.append("LOWER(g.motivo) LIKE ?")
        args.append(f"%{descripcion.lower()}%")

    # Usuario (solo privilegiados)
    if is_privileged and filtros.get('usuario_id') is not None:
        where.append("g.usuario_id = ?")
        args.append(filtros['usuario_id'])

    # -----------------------------
    # Tipo de gasto (incluye boletos)
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
            # tarjeta normal (no caja chica, no reembolso, no online, no boletos)
            where.append("COALESCE(g.es_caja_chica,0)=0")
            where.append("COALESCE(g.reembolso_vendedor,0)=0")
            where.append("COALESCE(g.tarjeta_sin_soporte,0)=0")
            where.append("COALESCE(g.boletos_aereos,0)=0")

    # -----------------------------
    # ✅ CCB (nuevo filtro)
    # ''  -> Todos (no filtra)
    # '1' -> Con CCB
    # '0' -> Sin CCB
    # -----------------------------
    if ccb_raw == "1":
        where.append("COALESCE(g.ccb,0)=1")
    elif ccb_raw == "0":
        where.append("COALESCE(g.ccb,0)=0")

    # -----------------------------
    # Helpers SQL para “GA efectivo”
    # -----------------------------
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
        THEN COALESCE(g.gg_aprobado,0)=0
    WHEN LOWER(COALESCE(g.ga_actor, g.ga_aprobador, g.ga_aprobador_rol, '')) IN ('gf','gerente financiero','gerente_financiero')
        THEN COALESCE(g.gf_aprobado,0)=0
    ELSE
        COALESCE(g.ga_aprobado,0)=0
    END
    """

    # -----------------------------
    # PENDIENTES (3 modos)
    # -----------------------------
    pend_mode = (pend_view or '').strip().lower()

    # compatibilidad: si viene ?pendientes=1 y no viene pend_view -> úsalo como "1"
    if not pend_mode and pendientes_bool:
        pend_mode = "1"

    # Siempre que es un modo pendientes: NO enviado a SAP
    if pend_mode in ("1", "mis_aprobaciones", "pend_sap"):
        where.append("(g.sap_contabilizacion IS NULL OR TRIM(g.sap_contabilizacion)='')")

    # 3.1) Pendientes por rol gerencial (tu lógica)
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

    # 3.2) Mis pendientes (ROL USUARIO): sus gastos, pendientes del paso GA efectivo
    elif pend_mode == "mis_aprobaciones":
        if role_name != "usuario":
            where.append("1=0")
        else:
            where.append("g.usuario_id = ?")
            args.append(uid or -1)
            where.append(f"({ga_step_pending_sql})")

    # 3.3) Pendientes SAP (COORDINADOR/ADMIN): todo aprobado, sin doc SAP
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
                AND (
                    COALESCE(g.ga_aprobado,0)=1
                    AND COALESCE(g.gg_aprobado,0)=1
                    AND COALESCE(g.gf_aprobado,0)=1
                )
              )
            )
            """)

    # -----------------------------
    # No privilegiados: solo sus registros
    # (si no están en “mis_aprobaciones”, igual restringe)
    # -----------------------------
    if not is_privileged and pend_mode != "mis_aprobaciones":
        where.append("g.usuario_id = ?")
        args.append(uid or -1)

    return filtros, where, args, is_privileged

def collect_gastos_pendientes_aprobacion_filters(request, session, privileged_roles=None):
    """
    Collect exclusivo para /reembolsos/gastos/pendientes-aprobacion

    ✅ Aplica:
    - filtros base (fecha/proveedor/centro/motivo/descripcion/usuario/tipo/ccb)
    - FORZA pendientes=1
    - filtro "pendiente real" por rol y por tipo de gasto
    - excluye ya contabilizados en SAP
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
    ccb_raw         = (request.args.get('ccb') or '').strip()  # '' | '1' | '0'

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
        'pendientes':   "1",   # ✅ esta pantalla siempre es pendientes
    }

    role_name = (session.get('rol') or '').strip().lower()
    is_privileged = role_name in {r.lower() for r in privileged_roles}

    uid = session.get('usuario_id') or session.get('user_id') or session.get('uid')
    try:
        uid = int(uid)
    except Exception:
        uid = None

    where, args = [], []

    # -----------------------------
    # Filtros base
    # -----------------------------
    if desde:
        where.append("date(g.fecha) >= date(?)")
        args.append(desde)

    if hasta:
        where.append("date(g.fecha) <= date(?)")
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

    # Usuario (solo privilegiados)
    if is_privileged and filtros.get('usuario_id') is not None:
        where.append("g.usuario_id = ?")
        args.append(filtros['usuario_id'])

    # -----------------------------
    # Tipo gasto
    # -----------------------------
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

    # -----------------------------
    # CCB
    # -----------------------------
    if ccb_raw == "1":
        where.append("COALESCE(g.ccb,0)=1")
    elif ccb_raw == "0":
        where.append("COALESCE(g.ccb,0)=0")

    # -----------------------------
    # ✅ SIEMPRE: NO enviados a SAP (pendientes)
    # -----------------------------
 
    where.append("(g.sap_contabilizacion IS NULL OR TRIM(g.sap_contabilizacion)='')")



    # No privilegiados: seguridad
    if not is_privileged:
        where.append("g.usuario_id = ?")
        args.append(uid or -1)

    return filtros, where, args, is_privileged

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

def recalc_gasto_totales(conn, gasto_id: int):
    cur = conn.cursor()
    cur.execute("""
        SELECT
            COALESCE(SUM(con_soporte),0),
            COALESCE(SUM(sin_soporte),0),
            COALESCE(SUM(subtotal_factura),0),
            COALESCE(SUM(servicios_10),0),
            COALESCE(SUM(subtotal_sin_iva),0),
            COALESCE(SUM(iva),0),
            COALESCE(SUM(total_con_iva),0)
        FROM gastos_tarjeta_detalle
        WHERE gasto_id=?
    """, (gasto_id,))
    cs, ss, sf, s10, ssi, iv, tci = cur.fetchone() or (0,0,0,0,0,0,0)
    cur.execute(f"""
        UPDATE {TABLE_GASTOS}
        SET con_soporte=?, sin_soporte=?, subtotal_factura=?, servicios_10=?,
            subtotal_sin_iva=?, iva=?, total_con_iva=?
        WHERE id=?
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
