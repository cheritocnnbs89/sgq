# -*- coding: utf-8 -*-

# ------------------------------------------------------------
# Tablas propias del modulo (prefijo oblig_)
# 2026-07-15 (Correccion #3): Frecuencias vuelve a tener tablas propias --
# cada notificacion necesita destinatarios configurables por usuario, algo
# que param_values no puede modelar sin un JSON opaco.
# 2026-08-07: Tipos y Entidades Reguladoras vuelven a tener tablas propias
# (oblig_tipos_obligacion / oblig_entidades_reguladoras) -- preservan los
# mismos IDs que tenian en param_values (0 huerfanos verificado contra
# oblig_obligaciones.tipo_id/entidad_id). GRUPO_TIPOS/GRUPO_ENTIDADES/
# TABLA_PARAM_GROUPS/TABLA_PARAM_VALUES eliminados de este archivo.
# ------------------------------------------------------------
TABLA_OBLIGACIONES = "oblig_obligaciones"
TABLA_EVIDENCIAS   = "oblig_evidencias"
TABLA_HISTORIAL    = "oblig_historial"
TABLA_ALERTAS      = "oblig_alertas_enviadas"
TABLA_FRECUENCIAS                = "oblig_frecuencias"
TABLA_FRECUENCIA_NOTIFICACIONES  = "oblig_frecuencia_notificaciones"
TABLA_NOTIFICACION_DESTINATARIOS = "oblig_notificacion_destinatarios"
TABLA_TIPOS     = "oblig_tipos_obligacion"
TABLA_ENTIDADES = "oblig_entidades_reguladoras"
# 2026-07-27: mapeo Tipo -> Entidad Reguladora (muchos a muchos -- confirmado
# contra "Data Power BI - Obligaciones tributarias y societarias.xlsx": una
# misma entidad (ej. Municipio, Superintendencia Cias) aplica a varios tipos,
# y un tipo tiene varias entidades -- parent_id de param_values no alcanza.
TABLA_TIPO_ENTIDAD = "oblig_tipo_entidad"
# 2026-08-14: Punto 8 -- solicitud de autorizacion para editar obligacion cumplida
TABLA_SOLICITUDES_EDICION = "oblig_solicitudes_edicion"
# Historial de este bloque: #2 (2026-07-14) movio Tipos/Entidades a
# param_values/terceros; #7 (2026-07-22) unifico Entidades a param_values;
# #8 (2026-08-07) revierte ambas a tablas propias con pantalla dedicada.

# ------------------------------------------------------------
# Tablas Sili existentes usadas por este modulo (NO crear DDL)
# ------------------------------------------------------------
TABLA_USUARIOS      = "usuarios"
TABLA_DEPARTAMENTOS = "departamentos"
TABLA_PUESTOS       = "puestos"   # "Cargo" en la UI
TABLA_EMPRESAS      = "empresas"  # 2026-07-13: catalogo existente, reemplaza oblig_empresas

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

# 2026-08-07: pantallas dedicadas de Tipos y Entidades Reguladoras vuelven a
# existir (revierte Correccion #23) -- ahora con tablas propias, mismo patron
# que Frecuencias.
ACTIVE_KEY_TIPOS = "obligaciones_tipos"
ACTIVE_KEY_ENTIDADES = "obligaciones_entidades"

# 2026-08-14: Punto 8 -- pantalla de solicitudes de edición (admin), menu_items
# insertado directo en BD (id child de 51), active_key debe coincidir.
ACTIVE_KEY_SOLICITUDES = "obligaciones_solicitudes"

# 2026-08-15: Punto 9 -- pantalla de aprobaciones de jefe
ACTIVE_KEY_APROBACIONES = "obligaciones_aprobaciones"

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
# 2026-08-14: rol nuevo pedido en reunión -- "jefe del jefe" (2 saltos de
# usuarios.jefe_id, misma cadena que resolver_cadena_jefe() ya usaba para email
# de "gerente"). Solo lectura -- mismos permisos de vista que ROL_JEFE_AREA,
# alcance ampliado a 2 niveles. Alta del rol en /roles-permisos es manual
# (ver CLAUDE.md raíz de V2, DEFAULT_ROLES del core no lo crea solo).
ROL_GERENTE_OBLIG    = "gerente_obligaciones"

ROLES_ADMIN = (ROL_ADMIN_SILI, ROL_ADMIN_OBLIG)

# ------------------------------------------------------------
# Frecuencias (2026-07-15, Correccion #3) -- tabla propia oblig_frecuencias.
# recalculo_tipo/recalculo_cantidad reemplazan el string "M:6" que antes
# vivia en param_values.valor -- ver obligaciones_services._siguiente_fecha().
# ------------------------------------------------------------
RECALCULO_TIPOS = ("M", "A", "D", "NINGUNA", "UNICA")
RECALCULO_LABELS = {
    "M":       "Meses",
    "A":       "Años",
    "D":       "Días",
    "NINGUNA": "No recalcula",
    # 2026-08-17: pedido en reunión — tiene fecha_vencimiento (a diferencia de
    # NINGUNA, que la anula), pero tampoco renueva al cumplirse. Un solo uso.
    "UNICA":   "Sin frecuencia (un solo uso)",
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
# 2026-08-17: pendiente_aprobacion -- cumplimiento reportado por el usuario pero
# aun sin aprobar por su jefe (Punto 9). NO es terminal (no cuenta como Historial
# todavia) -- distinto de cumplido/cumplido_fuera_plazo, que solo se asignan tras
# la aprobacion del jefe (o de una vez si el usuario no tiene jefe_id).
ESTATUS_VALORES = ("por_presentar", "atrasado", "pendiente_aprobacion", "cumplido", "cumplido_fuera_plazo")
ESTATUS_TERMINALES = ("cumplido", "cumplido_fuera_plazo")

# 2026-08-14: Punto 8 -- solicitud de autorizacion para editar obligacion cumplida
SOLICITUD_PENDIENTE  = "pendiente"
SOLICITUD_APROBADA   = "aprobada"
SOLICITUD_RECHAZADA  = "rechazada"

ESTATUS_LABELS = {
    "por_presentar":        "Por presentar a tiempo",
    "atrasado":             "Atrasado",
    "pendiente_aprobacion": "Pendiente de aprobación",
    "cumplido":             "Cumplido",
    "cumplido_fuera_plazo": "Cumplido fuera de plazo",
}

ESTATUS_BADGE_CLASS = {
    "por_presentar":        "bg-warning text-dark",
    "atrasado":             "bg-danger",
    "pendiente_aprobacion": "bg-info text-dark",
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
