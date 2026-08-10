# modules/planificador/planificador_auto_jobs.py
# -*- coding: utf-8 -*-
"""
Jobs automáticos del Planificador:
  - auto_confirmar_vuelos: marca como realizados los vuelos COORDINADA
    cuya fecha_retorno ya pasó, cuando el flag está activo.
  - auto_liquidar_vuelos:  liquida con el valor cotizado los vuelos
    PENDIENTE_LIQUIDACION cuya fecha_retorno ya pasó, cuando el flag activo.
  - recordar_vouchers_pendientes_confirmacion: recuerda/escala vouchers
    entregados que el solicitante no ha confirmado (3 y 6 días).
"""
from __future__ import annotations
import logging
from datetime import date

log = logging.getLogger(__name__)


def auto_confirmar_vuelos(app) -> int:
    """Devuelve la cantidad de vuelos auto-confirmados."""
    with app.app_context():
        from modules.planificador import planificador_repository as repo
        from modules.planificador import planificador_notifications as notif

        flags = repo.get_vuelo_flags()
        if not flags.get("auto_confirmar_vuelo"):
            return 0

        vuelos = repo.get_vuelos_para_auto_confirmar()
        count = 0
        for v in vuelos:
            sid = v["id"]
            try:
                repo.marcar_realizado_vuelo(sid, 0, "Sistema (auto-confirmación)")
                try:
                    notif.notif_vuelo_pendiente_liquidacion(
                        sid, v.get("area_solicitante", ""),
                        str(v.get("fecha", "")),
                        v.get("solicitante_nombre", ""),
                        v.get("coordinador_id"),
                        v.get("coordinador_nombre", ""),
                    )
                except Exception:
                    pass
                log.info("[AUTO-CONFIRMAR] Vuelo sid=%s marcado como realizado automáticamente.", sid)
                count += 1
            except Exception as exc:
                log.warning("[AUTO-CONFIRMAR] Error en sid=%s: %s", sid, exc)
        return count


def auto_liquidar_vuelos(app) -> int:
    """Devuelve la cantidad de vuelos auto-liquidados."""
    with app.app_context():
        from modules.planificador import planificador_repository as repo
        from modules.planificador import planificador_notifications as notif

        flags = repo.get_vuelo_flags()
        if not flags.get("auto_liquidar_vuelo"):
            return 0

        vuelos = repo.get_vuelos_para_auto_liquidar()
        count = 0
        hoy = date.today()
        for v in vuelos:
            sid = v["id"]
            try:
                # Construir costos desde cotización
                ticket = 0.0
                try:
                    ticket = float(v.get("datos_ticket") or 0)
                except (TypeError, ValueError):
                    pass
                hosp = 0.0
                try:
                    hosp = float(v.get("cotizacion_hospedaje") or 0)
                except (TypeError, ValueError):
                    pass

                if ticket <= 0 and hosp <= 0:
                    log.info("[AUTO-LIQUIDAR] Vuelo sid=%s sin cotización, omitido.", sid)
                    continue

                costos = {}
                if ticket > 0:
                    costos["Ticket aéreo"] = ticket
                if hosp > 0:
                    costos["Hospedaje"] = hosp
                costo_real = sum(costos.values())

                desglose = ", ".join(f"{t}: ${v2:,.2f}" for t, v2 in costos.items())
                notas = f"Auto-liquidado con valor cotizado. {desglose}"

                repo.liquidar_vuelo(sid, 0, "Sistema (auto-liquidación)", costo_real, notas)

                # Deducir presupuesto
                if v.get("centro_costo_id"):
                    try:
                        empresa_id = repo.get_empresa_by_usuario(v["solicitante_id"])
                        if empresa_id:
                            for tipo, costo in costos.items():
                                repo.deducir_presupuesto_vuelo(
                                    empresa_id, v["centro_costo_id"], tipo,
                                    hoy.year, hoy.month, costo,
                                )
                    except Exception as exc2:
                        log.warning("[AUTO-LIQUIDAR] Error presupuesto sid=%s: %s", sid, exc2)

                try:
                    notif.notif_vuelo_liquidada(
                        sid, v.get("area_solicitante", ""), str(v.get("fecha", "")),
                        v.get("solicitante_nombre", ""), v.get("solicitante_id"),
                        "Sistema", costo_real, notas,
                    )
                except Exception:
                    pass

                log.info("[AUTO-LIQUIDAR] Vuelo sid=%s liquidado automáticamente, total=%.2f.", sid, costo_real)
                count += 1
            except Exception as exc:
                log.warning("[AUTO-LIQUIDAR] Error en sid=%s: %s", sid, exc)
        return count


def recordar_vouchers_pendientes_confirmacion(app) -> dict:
    """
    Recorre los vouchers ya entregados (con secuencial) que el solicitante
    todavía no confirma:
      - 3+ días sin confirmar -> recuerda solo al solicitante.
      - 6+ días sin confirmar -> escala a jefe directo, solicitante y
        coordinador de vouchers.
    Cada item solo dispara cada recordatorio una vez (columnas
    recordatorio1_enviado_at / recordatorio2_enviado_at). Devuelve un dict
    con la cantidad de items notificados en cada nivel.
    """
    with app.app_context():
        from collections import defaultdict
        from modules.planificador import planificador_repository as repo
        from modules.planificador import planificador_notifications as notif

        enviados_3d = 0
        try:
            items_3d = repo.get_voucher_items_pendientes_recordatorio_3d()
        except Exception:
            log.exception("[VOUCHER-RECORDATORIO] Error consultando pendientes 3d")
            items_3d = []

        por_solicitud_3d = defaultdict(list)
        for it in items_3d:
            por_solicitud_3d[it["solicitud_id"]].append(it)

        for sid, items in por_solicitud_3d.items():
            base = items[0]
            try:
                notif.notif_voucher_recordatorio_confirmacion(
                    sid, items, base["solicitante_id"], base["solicitante_nombre"],
                    base["area_solicitante"], str(base["fecha"]),
                )
                for it in items:
                    repo.marcar_voucher_recordatorio1_enviado(it["id"])
                enviados_3d += len(items)
            except Exception:
                log.warning("[VOUCHER-RECORDATORIO] Error 3d sid=%s", sid)

        enviados_6d = 0
        try:
            items_6d = repo.get_voucher_items_pendientes_recordatorio_6d()
        except Exception:
            log.exception("[VOUCHER-RECORDATORIO] Error consultando pendientes 6d")
            items_6d = []

        por_solicitud_6d = defaultdict(list)
        for it in items_6d:
            por_solicitud_6d[it["solicitud_id"]].append(it)

        for sid, items in por_solicitud_6d.items():
            base = items[0]
            jefe = repo.get_gerente_del_usuario(base["solicitante_id"])
            try:
                notif.notif_voucher_escalamiento_confirmacion(
                    sid, items, base["solicitante_id"], base["solicitante_nombre"],
                    base["area_solicitante"], str(base["fecha"]),
                    jefe.get("id") if jefe else None,
                    jefe.get("nombre") if jefe else "—",
                )
                for it in items:
                    repo.marcar_voucher_recordatorio2_enviado(it["id"])
                enviados_6d += len(items)
            except Exception:
                log.warning("[VOUCHER-RECORDATORIO] Error 6d sid=%s", sid)

        return {"recordatorio_3d": enviados_3d, "escalamiento_6d": enviados_6d}
