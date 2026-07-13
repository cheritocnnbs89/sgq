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
    "PENDIENTE_APROBACION_JEFE":     "Pend. aprobación jefe",
    "PENDIENTE_COORDINACION":        "Pend. cotización coordinador",
    "PENDIENTE_APROBACION_GG_VUELO": "Pend. aprobación GG",
    "PENDIENTE_INFO_VUELO":          "Pend. información del vuelo",
    "PENDIENTE_APROBACION":          "Pendiente aprobación",
    "PENDIENTE_APROBACION_GERENTE":  "Pendiente aprobación gerente",
    "APROBADA":                      "Aprobada",
    "RECHAZADA":                     "Rechazada",
    "COMPLETADA":                    "Completada",
}

# Estados que agrupan cada sección de la tabla
ESTADOS_RESERVADAS  = (
    "PENDIENTE_APROBACION_JEFE",
    "PENDIENTE_COORDINACION",
    "PENDIENTE_APROBACION_GG_VUELO",
    "PENDIENTE_INFO_VUELO",
)
ESTADOS_COORDINADAS   = ("PENDIENTE_APROBACION", "PENDIENTE_APROBACION_GERENTE", "APROBADA")
ESTADOS_POR_COMPLETAR = ("COORDINADA", "PENDIENTE_LIQUIDACION")
ESTADOS_ATENDIDAS     = ("COMPLETADA", "RECHAZADA")

# Roles de sistema considerados gerentes (para aprobación gerencial)
ROLES_GERENTE = ("gerente", "gerente financiero", "gerente general", "jefe")

PRIORIDADES = ["Normal", "Alta", "Urgente"]

ROL_COORDINADOR        = "COORDINADOR"
ROL_APROBADOR          = "APROBADOR"
ROL_MOTORIZADO         = "MOTORIZADO"
ROL_GERENTE_PRESUPUESTO = "GERENTE_PRESUPUESTO"

# roles de sistema que tienen acceso total al planificador
ROLES_ADMIN = ("admin",)

# Tabla de presupuesto por CC/empresa/tipo de gasto
TBL_PRESUPUESTO = "planificador_presupuesto"

# param_group para tipos de gasto (parametrizables desde Parámetros generales)
PARAM_GROUP_TIPOS_GASTO = "PLANIFICADOR_TIPOS_GASTO"

# Fallback si no hay datos en param_values todavía
TIPOS_GASTO_DEFAULT = ["Alimentación", "Hospedaje", "Ticket aéreo"]

# param_group para motivos de solicitud de Vuelo (parametrizables desde Parámetros generales)
PARAM_GROUP_MOTIVOS_VUELO = "PLANIFICADOR_MOTIVOS_VUELO"

# Fallback si no hay datos en param_values todavía
MOTIVOS_VUELO_DEFAULT = [
    "Capacitación/charla",
    "Charla informativa a colaboradores",
    "Chequeo médico anual",
    "Entrenamiento cruzado",
    "Evaluación actividades CAPEX",
    "Fiesta de Navidad",
    "Inspección de trabajos preventivos y seguimiento de obras",
    "Otros",
    "Reunión clientes",
    "Reuniones gerenciales/colaboradores",
    "Seguimiento equipo comercial/servicio al cliente",
    "Seguimiento procesos",
    "Seguimiento procesos/ pruebas clientes",
    "Semana de la salud",
    "Visita planta QP internacional",
    "Visita planta QP UIO",
    "Visita/reunión planta QP internacional",
    "Visita planta UIO",
]
MOTIVO_VUELO_OTROS = "Otros"

# Semáforo: % ejecutado a partir del cual cambia de verde a amarillo
SEMAFORO_AMARILLO_PCT = 50  # >= 50% usado → amarillo
# >= 100% usado → rojo (sin presupuesto, requiere aprobación GG)

PERM_PRESUPUESTO = "planificador.presupuesto"
