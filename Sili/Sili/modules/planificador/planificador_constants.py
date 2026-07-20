# modules/planificador/planificador_constants.py
# -*- coding: utf-8 -*-

ACTIVE_KEY = "planificador"

# ── Nombres de tablas ──────────────────────────────────────────
TBL_SOLICITUDES  = "planificador_solicitudes"
TBL_CONFIG       = "planificador_config"
TBL_GRUPOS       = "planificador_grupos"
TBL_LOGS         = "planificador_solicitud_logs"
TBL_TIPO_FLAGS   = "planificador_tipo_flags"
TBL_NOTIFY_INAPP = "notify_inapp"
TBL_USUARIOS     = "usuarios"
TBL_DEPARTAMENTOS = "departamentos"
TBL_PUESTOS      = "puestos"
TBL_PARAM_VALUES = "param_values"
TBL_PARAM_GROUPS = "param_groups"
PERM_SOLICITUDES = "planificador.solicitudes"
PERM_CONFIG = "planificador.configuracion"

# Nombre del param_group en la tabla param_groups
PARAM_GROUP_TIPOS = "PLANIFICADOR_TIPOS"

# Fallback si no hay datos en param_values todavía
TIPOS_SOLICITUD_DEFAULT = [
    "Recorrido / Motorizado",
    "Voucher",
    "Vuelo",
]

ESTADOS = {
    "PENDIENTE_COORDINACION":       "Pendiente coordinación",
    "PENDIENTE_APROBACION":         "Pendiente aprobación",
    "PENDIENTE_APROBACION_GERENTE": "Pendiente aprobación gerente",
    "APROBADA":                     "Aprobada",
    "RECHAZADA":                    "Rechazada",
    "COMPLETADA":                   "Completada",
}

# Estados que agrupan cada sección de la tabla
ESTADOS_RESERVADAS  = ("PENDIENTE_COORDINACION",)
ESTADOS_COORDINADAS = ("PENDIENTE_APROBACION", "PENDIENTE_APROBACION_GERENTE", "APROBADA")
ESTADOS_ATENDIDAS   = ("COMPLETADA", "RECHAZADA")

# Roles de sistema considerados gerentes (para aprobación gerencial)
ROLES_GERENTE = ("gerente", "gerente financiero", "gerente general")

PRIORIDADES = ["Normal", "Alta", "Urgente"]

ROL_COORDINADOR = "COORDINADOR"
ROL_APROBADOR   = "APROBADOR"
ROL_MOTORIZADO  = "MOTORIZADO"

# roles de sistema que tienen acceso total al planificador
ROLES_ADMIN = ("admin", "jefe")
