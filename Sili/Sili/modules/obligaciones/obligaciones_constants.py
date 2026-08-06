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
# 2026-07-27: mapeo Tipo -> Entidad Reguladora (muchos a muchos -- confirmado
# contra "Data Power BI - Obligaciones tributarias y societarias.xlsx": una
# misma entidad (ej. Municipio, Superintendencia Cias) aplica a varios tipos,
# y un tipo tiene varias entidades -- parent_id de param_values no alcanza.
TABLA_TIPO_ENTIDAD = "oblig_tipo_entidad"
# 2026-07-22 (Correccion de arquitectura #7): Entidades Reguladoras deja de ser
# tabla propia (oblig_entidades_reguladoras) y pasa a vivir en param_values bajo
# el grupo GRUPO_ENTIDADES -- EXACTAMENTE igual que Tipos. Los 35 valores se
# migraron a param_values (ids nuevos generados por IDENTITY; los ids viejos de
# terceros solapaban con param_values, no se pudieron preservar) y entidad_id de
# oblig_obligaciones se re-apunto a los ids nuevos. La tabla propia se elimino.

# ------------------------------------------------------------
# Tablas Sili existentes usadas por este modulo (NO crear DDL)
# ------------------------------------------------------------
TABLA_USUARIOS      = "usuarios"
TABLA_DEPARTAMENTOS = "departamentos"
TABLA_PUESTOS       = "puestos"   # "Cargo" en la UI
TABLA_EMPRESAS      = "empresas"  # 2026-07-13: catalogo existente, reemplaza oblig_empresas
TABLA_PARAM_GROUPS  = "param_groups"  # 2026-07-14: reemplaza oblig_tipos y oblig_reglas_alerta
TABLA_PARAM_VALUES  = "param_values"

# Nombres de los grupos en param_groups que este modulo usa
# 2026-07-15: GRUPO_FRECUENCIAS eliminado -- Frecuencias ya no vive en
# param_values (ver Correccion de arquitectura #3, PLAN.md).
GRUPO_TIPOS = "Obligaciones - Tipos"
# 2026-07-22 (Correccion #7): grupo de param_values donde viven las Entidades
# Reguladoras (antes tabla propia). El group_id se resuelve por nombre en runtime
# (repository._get_group_id) -- mismo patron que list_tipos(), sin id hardcodeado.
GRUPO_ENTIDADES = "Obligaciones - Entidades Reguladoras"

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

# 2026-07-23 (Correccion #23): pantallas dedicadas de Tipos y Entidades
# Reguladoras eliminadas -- ambas se gestionan desde Parametros Generales
# genericos (/parametros/generales/<grupo>/items), permiso "parametros"
# otorgado a admin_obligaciones. ACTIVE_KEY_TIPOS y ACTIVE_KEY_ENTIDADES
# eliminados (sin uso).

# ------------------------------------------------------------
# Permisos (tabla opciones) -- 7 permisos del modulo
# 2026-07-14 (Ronda 2): obligaciones_configuracion eliminado -- ya no hay
# pantalla propia de Configuracion (Tipos/Frecuencias/Reglas se gestionan
# bajo el permiso general de parametros_generales, ya existente en SGQ).
# ------------------------------------------------------------
PERM_VER            = "obligaciones"
PERM_CREAR          = "obligaciones_crear"
PERM_EDITAR         = "obligaciones_editar"
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
# Tipos de destinatario de una notificación (2026-07-22)
# 'fijo'    -> usuario_id concreto (comportamiento histórico).
# 'creador' -> el usuario que creó la obligación (oblig_obligaciones.creado_por).
# 'jefe'    -> jefe directo del creador (usuarios.jefe_id del creador).
# 'gerente' -> jefe del jefe del creador (dos saltos de jefe_id).
# Los 3 jerárquicos guardan usuario_id NULL: el email se resuelve en tiempo
# real al enviar la alerta (por obligación, según quién la creó).
# ------------------------------------------------------------
TIPO_DESTINATARIO = ("fijo", "creador", "jefe", "gerente")
TIPO_DESTINATARIO_JERARQUICOS = ("creador", "jefe", "gerente")
TIPO_DESTINATARIO_LABELS = {
    "fijo":    "Usuario fijo",
    "creador": "Creador de la obligación",
    "jefe":    "Jefe directo del creador",
    "gerente": "Gerente del área",
}

# Mensaje genérico mostrado al usuario final cuando la cadena de jefe está rota
# (no exponer detalle técnico de jefe/gerente en pantalla -- ese va en el correo).
MSG_CADENA_ROTA = "Esta frecuencia no está disponible en este momento. Contáctate con el área de TI."

# ------------------------------------------------------------
# Valores de negocio
# ------------------------------------------------------------
ESTATUS_VALORES = ("por_presentar", "atrasado", "cumplido", "cumplido_fuera_plazo")
ESTATUS_TERMINALES = ("cumplido", "cumplido_fuera_plazo")

ESTATUS_LABELS = {
    "por_presentar":        "Por presentar a tiempo",
    "atrasado":             "Atrasado",
    "cumplido":             "Cumplido",
    "cumplido_fuera_plazo": "Cumplido fuera de plazo",
}

ESTATUS_BADGE_CLASS = {
    "por_presentar":        "bg-warning text-dark",
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
# Exportar Excel del Historial -- columnas exactas (2026-07-21)
# Confirmado por Matias contra el Excel real de referencia
# (PLANIFICACION-NUEVO-MODULO/Data Power BI - Obligaciones tributarias y
# societarias.xlsx, hoja "Obligaciones"). "Prioridad" no tiene todavía un
# campo en BD -- se exporta en blanco hasta que Matias defina de dónde sale
# (ver HISTORIAL-CORRECCIONES).
# ------------------------------------------------------------
HISTORIAL_COLUMNAS = (
    "ID", "Tipo", "Descripción", "Departamento Responsable", "Responsable",
    "Entidad", "Fecha_Vencimiento", "Frecuencia", "Estatus", "Prioridad",
)
