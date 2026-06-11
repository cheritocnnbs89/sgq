# modules/planificador/planificador_constants.py
# -*- coding: utf-8 -*-

ACTIVE_KEY = "planificador"
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
