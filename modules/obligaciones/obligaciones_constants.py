# -*- coding: utf-8 -*-

# ------------------------------------------------------------
# Tablas propias del modulo (prefijo oblig_)
# 2026-07-14 (Ronda 2): TABLA_TIPOS/TABLA_ENTIDADES/TABLA_REGLAS eliminadas --
# Tipos vive en param_values, Entidades en terceros.
# 2026-07-15 (Correccion #3): Frecuencias vuelve a tener tablas propias --
# cada notificacion necesita destinatarios configurables por usuario, algo
# que param_values no puede modelar sin un JSON opaco.
# ------------------------------------------------------------
TABLA_OBLIGACIONES = "oblig_obligaciones"
TABLA_EVIDENCIAS   = "oblig_evidencias"
TABLA_HISTORIAL    = "oblig_historial"
TABLA_ALERTAS      = "oblig_alertas_enviadas"
TABLA_FRECUENCIAS                = "oblig_frecuencias"
TABLA_FRECUENCIA_NOTIFICACIONES  = "oblig_frecuencia_notificaciones"
TABLA_NOTIFICACION_DESTINATARIOS = "oblig_notificacion_destinatarios"

# ------------------------------------------------------------
# Tablas Sili existentes usadas por este modulo (NO crear DDL)
# ------------------------------------------------------------
TABLA_USUARIOS      = "usuarios"
TABLA_DEPARTAMENTOS = "departamentos"
TABLA_PUESTOS       = "puestos"   # "Cargo" en la UI
TABLA_EMPRESAS      = "empresas"  # 2026-07-13: catalogo existente, reemplaza oblig_empresas
TABLA_TERCEROS      = "terceros"  # 2026-07-14: catalogo existente, reemplaza oblig_entidades
TABLA_PARAM_GROUPS  = "param_groups"  # 2026-07-14: reemplaza oblig_tipos y oblig_reglas_alerta
TABLA_PARAM_VALUES  = "param_values"

# Nombres de los grupos en param_groups que este modulo usa
# 2026-07-15: GRUPO_FRECUENCIAS eliminado -- Frecuencias ya no vive en
# param_values (ver Correccion de arquitectura #3, PLAN.md).
GRUPO_TIPOS = "Obligaciones - Tipos"

# 2026-07-20 (Correccion #4): id fijo del grupo Tipos en param_groups (sgq-local
# y produccion ya lo tienen creado -- ver PLAN.md). routes_obligaciones_tipos.py
# reusa las funciones genericas de modules/parametros_generales acotadas a este
# group_id -- nunca tocar otro group_id desde este modulo.
TIPOS_GROUP_ID = 5796

# ------------------------------------------------------------
# Identidad del modulo
# ------------------------------------------------------------
ACTIVE_KEY = "obligaciones"   # debe coincidir EXACTAMENTE con el slug en menu_items
PERM_BASE  = "obligaciones"

# 2026-07-15: pantalla de Frecuencias -- vive en el menu bajo Configuraciones ->
# Parametros Generales (pedido de Matias), pero el slug de menu_items para esa
# entrada es un dato que falta confirmar -- placeholder hasta que se enganche
# el INSERT real en menu_items (fuera del alcance de esta tarea, NO tocar BD).
ACTIVE_KEY_FRECUENCIAS = "obligaciones_frecuencias"

# 2026-07-20 (Correccion #4): pantalla de Tipos -- ruta propia
# /obligaciones/tipos, mismo submenu Configuraciones que Frecuencias.
ACTIVE_KEY_TIPOS = "obligaciones_tipos"

# ------------------------------------------------------------
# Permisos (tabla opciones) -- 7 permisos del modulo
# 2026-07-14 (Ronda 2): obligaciones_configuracion eliminado -- ya no hay
# pantalla propia de Configuracion (Tipos/Frecuencias/Reglas se gestionan
# bajo el permiso general de parametros_generales, ya existente en SGQ).
# ------------------------------------------------------------
PERM_VER            = "obligaciones"
PERM_CREAR          = "obligaciones_crear"
PERM_EDITAR         = "obligaciones_editar"
PERM_CARGA_MASIVA   = "obligaciones_carga_masiva"
PERM_EXPORTAR       = "obligaciones_exportar"
PERM_HISTORIAL      = "obligaciones_historial"
PERM_DASHBOARD      = "obligaciones_dashboard"
# 2026-07-20 (Correccion #5): Tipos/Frecuencias (Configuraciones) tenian el
# mismo permiso que Consultas/Dashboard -- jefe_area_obligaciones y
# usuario_obligaciones podian entrar por URL directa. Permiso propio,
# ver=1 SOLO para admin_obligaciones/admin -- ver PLAN.md Correccion #5.
PERM_CONFIG         = "obligaciones_config"

# ------------------------------------------------------------
# Roles del modulo
# ------------------------------------------------------------
ROL_ADMIN_SILI       = "admin"
ROL_ADMIN_OBLIG      = "admin_obligaciones"
ROL_JEFE_AREA        = "jefe_area_obligaciones"
ROL_USUARIO_OBLIG    = "usuario_obligaciones"

ROLES_ADMIN = (ROL_ADMIN_SILI, ROL_ADMIN_OBLIG)

# ------------------------------------------------------------
# Frecuencias (2026-07-15, Correccion #3) -- tabla propia oblig_frecuencias.
# recalculo_tipo/recalculo_cantidad reemplazan el string "M:6" que antes
# vivia en param_values.valor -- ver obligaciones_services._siguiente_fecha().
# ------------------------------------------------------------
RECALCULO_TIPOS = ("M", "A", "D", "NINGUNA")
RECALCULO_LABELS = {
    "M":       "Meses",
    "A":       "Años",
    "D":       "Días",
    "NINGUNA": "No recalcula",
}
TRIGGER_TIPOS = ("dias_antes", "fecha_exacta")
TRIGGER_LABELS = {
    "dias_antes":   "Días antes del vencimiento",
    "fecha_exacta": "Día fijo del mes",
}
MAX_NOTIFICACIONES_POR_FRECUENCIA = 5

# ------------------------------------------------------------
# Valores de negocio
# ------------------------------------------------------------
ESTADOS = ("por_presentar", "atrasado", "cumplido", "cumplido_fuera_plazo")
ESTADOS_TERMINALES = ("cumplido", "cumplido_fuera_plazo")

ESTADO_LABELS = {
    "por_presentar":        "Por presentar",
    "atrasado":             "Atrasado",
    "cumplido":             "Cumplido",
    "cumplido_fuera_plazo": "Cumplido fuera de plazo",
}

ESTADO_BADGE_CLASS = {
    "por_presentar":        "",
    "atrasado":             "bg-danger",
    "cumplido":             "bg-success",
    "cumplido_fuera_plazo": "bg-warning text-dark",
}

# ------------------------------------------------------------
# Evidencias (Fase 4)
# ------------------------------------------------------------
EXTENSIONES = {"pdf", "jpg", "jpeg", "png", "xlsx", "docx"}
MAX_MB      = 4
MAX_BYTES   = MAX_MB * 1024 * 1024

# ------------------------------------------------------------
# Carga masiva (Fase 7) -- normalizacion de valores del Excel
# ------------------------------------------------------------
ENTIDAD_ALIAS = {
    "supercias":                   "superintendencia de compañías",
    "superintendencia cias":       "superintendencia de compañías",
    "senae":                       "senae",
    "servicio de rentas internas": "servicio de rentas internas",
}

# 2026-07-15 (Correccion #3): mapea el texto del Excel al `nombre` exacto de
# oblig_frecuencias (ver seed en PLAN.md) -- ya no a un param_value.
FRECUENCIA_EXCEL_MAP = {
    "anual":                              "anual",
    "mensual":                            "mensual",
    "cada 2 años":                        "cada 2 años",
    "cada 2 anos":                        "cada 2 años",
    "cada 3 años":                        "cada 3 años",
    "cada 3 anos":                        "cada 3 años",
    "cuando exista una actualización":    "manual",
    "cuando exista una actualizacion":    "manual",
}

ESTADO_EXCEL_MAP = {
    "presentado y pagado a tiempo": "cumplido",
    "por presentar (a tiempo)":     "por_presentar",
    "por presentar":                "por_presentar",
    "cumplido":                     "cumplido",
    "en proceso":                   "por_presentar",
    "":                             "por_presentar",
}

CARGA_MASIVA_COLUMNAS = (
    "Tipo", "Empresa", "Descripción", "Entidad",
    "Usuario", "Fecha Vencimiento", "Frecuencia", "Estado",
)

# ------------------------------------------------------------
# Historial / Exportar -- columnas exactas (Fase 5 / Fase 9)
# ------------------------------------------------------------
HISTORIAL_COLUMNAS = (
    "ID", "Empresa", "Entidad", "Tipo", "Descripción", "Frecuencia",
    "Fecha creación", "Fecha vencimiento", "Estado", "Evidencia",
    "Usuario", "Departamento", "Cargo",
)
