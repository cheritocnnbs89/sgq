# modules/scheduler/scheduler_registry.py
# ==========================================================
# Registro central de jobs del scheduler.
# Para agregar un job nuevo:
#   1. Define la función en el módulo correspondiente.
#   2. Agrégala aquí con su metadata.
#   3. Al arrancar la app, auto-seed la inserta en BD automáticamente.
# ==========================================================

from __future__ import annotations

JOB_REGISTRY: dict[str, dict] = {
    # ── Tareas ────────────────────────────────────────────
    "auto_close_expired_tasks": {
        "modulo": "tareas",
        "descripcion": "Cierra automáticamente tareas vencidas sin actividad",
        "tipo": "intervalo",
        "intervalo_min": 300,
        "hora_inicio": None,
    },
    "plan_notifications": {
        "modulo": "tareas",
        "descripcion": "Planifica notificaciones pendientes de tareas",
        "tipo": "intervalo",
        "intervalo_min": 300,
        "hora_inicio": None,
    },
    "dispatch_notifications": {
        "modulo": "tareas",
        "descripcion": "Despacha (envía) notificaciones ya planificadas",
        "tipo": "intervalo",
        "intervalo_min": 300,
        "hora_inicio": None,
    },
    "notify_overdue": {
        "modulo": "tareas",
        "descripcion": "Alerta de tareas vencidas a responsables",
        "tipo": "intervalo",
        "intervalo_min": 30,
        "hora_inicio": None,
    },
    "send_daily_report": {
        "modulo": "tareas",
        "descripcion": "Reporte diario de tareas por correo (07:30)",
        "tipo": "hora_fija",
        "intervalo_min": None,
        "hora_inicio": "07:30",
    },
    # ── Oportunidades de Mejora ───────────────────────────
    "process_om_notifications": {
        "modulo": "oportunidades_mejora",
        "descripcion": "Notificaciones generales de OMs (vencimiento, seguimiento)",
        "tipo": "intervalo",
        "intervalo_min": 300,
        "hora_inicio": None,
    },
    "process_om_acciones_seguimiento": {
        "modulo": "oportunidades_mejora",
        "descripcion": "Recordatorios de acciones de seguimiento pendientes en OMs",
        "tipo": "intervalo",
        "intervalo_min": 300,
        "hora_inicio": None,
    },
    # ── Gastos Tarjeta ────────────────────────────────────
    "process_gastos_expiry": {
        "modulo": "gastos",
        "descripcion": "Alerta de gastos con tarjeta próximos a vencer sin regularizar",
        "tipo": "intervalo",
        "intervalo_min": 300,
        "hora_inicio": None,
    },
    # ── Contratos ─────────────────────────────────────────
    "encolar_notificaciones_contratos_por_vencer": {
        "modulo": "contratos",
        "descripcion": "Encola alertas de contratos próximos a vencer",
        "tipo": "intervalo",
        "intervalo_min": 300,
        "hora_inicio": None,
    },
    "encolar_notificaciones_garantias_multi_dia": {
        "modulo": "contratos",
        "descripcion": "Encola alertas de garantías a 20/10/5/0 días de vencer",
        "tipo": "intervalo",
        "intervalo_min": 300,
        "hora_inicio": None,
    },
    # ── Planilla ──────────────────────────────────────────
    "send_planilla_weekly_report": {
        "modulo": "planilla",
        "descripcion": "Reporte semanal de planilla (viernes 17:00)",
        "tipo": "hora_fija",
        "intervalo_min": None,
        "hora_inicio": "17:00",
    },
    # ── Soporte / Email-to-Task ───────────────────────────
    "process_incoming_emails": {
        "modulo": "soporte",
        "descripcion": "Lee correos de soporteti@quimpac.com.ec y crea tickets",
        "tipo": "intervalo",
        "intervalo_min": 2,
        "hora_inicio": None,
    },
    "notify_unassigned_tickets": {
        "modulo": "soporte",
        "descripcion": "Alerta tickets sin asignar con más de 3 horas",
        "tipo": "intervalo",
        "intervalo_min": 30,
        "hora_inicio": None,
    },
    # ── AWS / Sync ────────────────────────────────────────
    "aws_sync": {
        "modulo": "gastos",
        "descripcion": "Sincroniza aprobaciones de gastos con AWS DynamoDB",
        "tipo": "intervalo",
        "intervalo_min": 5,
        "hora_inicio": None,
    },
    # ── SeedBilling ───────────────────────────────────────
    "seedbilling_xml": {
        "modulo": "facturacion",
        "descripcion": "Importa facturas XML de SeedBilling (08:00 y 14:00)",
        "tipo": "hora_fija",
        "intervalo_min": None,
        "hora_inicio": "08:00",
    },
}
