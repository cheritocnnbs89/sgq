# modules/planificador/planificador_constants.py
# -*- coding: utf-8 -*-

ACTIVE_KEY = "planificador"

# ── Nombres de tablas ──────────────────────────────────────────
TBL_SOLICITUDES  = "planificador_solicitudes"
TBL_CONFIG       = "planificador_config"
TBL_GRUPOS       = "planificador_grupos"
TBL_LOGS         = "planificador_solicitud_logs"
TBL_TIPO_FLAGS   = "planificador_tipo_flags"
TBL_ROL_FLAGS    = "planificador_rol_flags"
TBL_VOUCHER_ITEMS = "planificador_voucher_items"
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

# Nombre exacto del tipo "Voucher" (voucher de taxi), con flujo propio:
# aprobación del jefe directo -> el usuario finaliza subiendo su respaldo ->
# el coordinador liquida el costo (sin validar presupuesto).
TIPO_VOUCHER = "Voucher"

ESTADOS = {
    "PENDIENTE_APROBACION_JEFE":       "Pend. aprobación jefe",
    "PENDIENTE_COORDINACION":          "Pend. cotización coordinador",
    "PENDIENTE_APROBACION_GG_VUELO":   "Pend. aprobación GG",
    "PENDIENTE_INFO_VUELO":            "Pend. información del vuelo",
    "PENDIENTE_APROBACION":            "Pendiente aprobación",
    "PENDIENTE_APROBACION_GERENTE":    "Pendiente aprobación gerente",
    "PENDIENTE_ENTREGA_VOUCHER":       "Pend. entrega (coordinador)",
    "PENDIENTE_CONFIRMACION_VOUCHER":  "Pend. confirmación (usuario)",
    "PENDIENTE_LIQUIDACION_VOUCHER":   "Pend. liquidación (coordinador)",
    "APROBADA":                        "Aprobada",
    "RECHAZADA":                       "Rechazada",
    "COMPLETADA":                      "Completada",
}

# Estados que agrupan cada sección de la tabla
ESTADOS_RESERVADAS  = (
    "PENDIENTE_APROBACION_JEFE",
    "PENDIENTE_COORDINACION",
    "PENDIENTE_APROBACION_GG_VUELO",
    "PENDIENTE_INFO_VUELO",
)
ESTADOS_COORDINADAS   = ("PENDIENTE_APROBACION", "PENDIENTE_APROBACION_GERENTE", "APROBADA")
ESTADOS_POR_COMPLETAR = (
    "COORDINADA",
    "PENDIENTE_LIQUIDACION",
    "PENDIENTE_ENTREGA_VOUCHER",
    "PENDIENTE_CONFIRMACION_VOUCHER",
    "PENDIENTE_LIQUIDACION_VOUCHER",
)
ESTADOS_ATENDIDAS     = ("COMPLETADA", "RECHAZADA")

# Roles de sistema considerados gerentes (para aprobación gerencial)
ROLES_GERENTE = ("gerente", "gerente financiero", "gerente general", "jefe")

# Roles candidatos para auto-aprobar el paso de aprobación del jefe directo
# en solicitudes de Vuelo y de Voucher (configurable en Planificador >
# Configuración, mismo flag para ambos tipos). Si el rol del solicitante
# está activado ahí, la solicitud salta directo a PENDIENTE_COORDINACION
# (Vuelo) o PENDIENTE_ENTREGA_VOUCHER (Voucher) sin pasar por
# PENDIENTE_APROBACION_JEFE, incluso si en el futuro se le llegara a
# configurar un jefe_id. Si el rol no está activado (o no aplica), se usa
# el flujo normal: valida el jefe directo.
ROLES_CANDIDATOS_AUTOAPROBAR_VUELO = ("gerente", "gerente financiero", "gerente general")

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
