# modules/scheduler/scheduler_constants.py
# ==========================================================
# Constantes del scheduler.
# Centraliza nombres de tablas, canales, tipos y templates.
# ==========================================================

# -------------------------
# Tablas
# -------------------------
TB_NOTIFY_QUEUE = "notify_queue"
TB_NOTIFY_TEMPLATES = "notify_templates"
TB_NOTIFY_USER_PREFS = "notify_user_prefs"
TB_NOTIFY_INAPP = "notify_inapp"
TB_GASTOS_TARJETA = "gastos_tarjeta"
TB_USUARIOS = "usuarios"
TB_TAREAS = "tareas"
TB_PLAN_TAREAS = "plan_tareas"
TB_PLAN_RESPONSABLES = "plan_responsables"
TB_PLAN_CHECKS = "plan_checks"
TB_DEPARTAMENTOS = "departamentos"
TB_TERCEROS = "terceros"
TB_RECLAMO_IMPUTADOS = "reclamo_imputados"
TB_RECLAMOS = "reclamos"
TB_PUESTOS = "puestos"

# -------------------------
# Canales
# -------------------------
CANAL_EMAIL = "email"
CANAL_INAPP = "inapp"
CANAL_SLACK = "slack"

# -------------------------
# Estados cola
# -------------------------
ESTADO_PENDING = "pending"
ESTADO_SENDING = "sending"
ESTADO_SENT = "sent"
ESTADO_ERROR = "error"
ESTADO_SKIPPED = "skipped"

# -------------------------
# Tipos cola
# -------------------------
TIPO_HOY = "hoy"
TIPO_GASTO = "gasto"
TIPO_GASTO_APROBADO_USER = "gasto_aprobado_user"
TIPO_GASTO_APROBADO_NEXT = "gasto_aprobado_next"
TIPO_OM_D4 = "om_d4"
TIPO_OM_D5 = "om_d5"
TIPO_OM_D9 = "om_d9"
TIPO_OM_D10 = "om_d10"

# -------------------------
# Template keys
# -------------------------
TPL_TAREA_HOY = "tarea_hoy"
TPL_GASTO_USER_APPROVED = "gasto_user_approved"
TPL_GASTO_NEXT_GG = "gasto_next_gg"
TPL_GASTO_NEXT_GF = "gasto_next_gf"
TPL_GASTO_NEXT_COORD = "gasto_next_coord"
TPL_GASTO_NEXT = "gasto_next"
TPL_GASTO_RECHAZO_GG = "gasto_rechazo_gg"
TPL_OM_SPONSOR_D4 = "om_sponsor_d4"
TPL_OM_JEFE_D5 = "om_jefe_d5"
TPL_OM_SPONSOR_JEFE_D9 = "om_sponsor_jefe_d9"
TPL_OM_GG_D10 = "om_gg_d10"

# -------------------------
# Roles
# -------------------------
ROL_GERENTE_GENERAL = "gerente general"
ROL_GERENTE_FINANCIERO = "gerente financiero"
ROL_COORDINADOR = "coordinador"
ROL_ADMIN = "admin"