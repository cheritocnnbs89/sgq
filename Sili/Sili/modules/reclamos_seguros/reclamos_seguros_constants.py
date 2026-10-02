# modules/reclamos_seguros/reclamos_seguros_constants.py
# -*- coding: utf-8 -*-

ACTIVE_KEY = "reclamos_seguros"
PERM_RECLAMOS_SEGUROS = "reclamos_seguros"   # ver · crear · editar · eliminar · exportar
# Clave de resaltado en el menu de la pantalla de configuracion (opcion propia, solo admin)
ACTIVE_KEY_CONFIG = "reclamos_seguros_config"

# Prefijo del código correlativo del caso (SEG001, SEG002, ...). El número sale de la
# tabla compartida secuencias_sap (misma que usan Contratos, Reembolsos y Casos Legales),
# clave 'reclamos_seguros'.
CODIGO_PREFIJO = "SEG"

ESTADO_ABIERTO = "ABIERTO"
ESTADO_CERRADO = "CERRADO"

# Sub-estado: texto libre informativo (no gatilla lógica de negocio en esta versión).
# Se ofrecen como sugerencias en el formulario, tomadas del flujo "Implementar
# Herramienta de Reclamos Seguros".
SUB_ESTADOS_SUGERIDOS = [
    "Apertura",
    "En espera de visita perito",
    "En proceso de preparación de información",
    "Respuesta de perito",
    "Alcance de respuesta de información",
    "En espera de respuesta",
    "En espera de liquidación",
    "En espera de pre cancelación",
    "En espera del pago",
    "Requerimiento de información",
]

TIPOS_CASO = ["Robo Vehículo", "Daño", "Choque"]

# Origen de cada entrada del seguimiento
ORIGEN_MANUAL = "MANUAL"
ORIGEN_CORREO_ENTRANTE = "CORREO_ENTRANTE"
ORIGEN_CORREO_SALIENTE = "CORREO_SALIENTE"

# Adjuntos (mismos límites que Casos Legales)
EXTENSIONES_PERMITIDAS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".jpg", ".jpeg", ".png", ".txt", ".zip", ".msg", ".eml",
}
MAX_ADJUNTO_BYTES = 10 * 1024 * 1024
MAX_ADJUNTOS_POR_ENVIO = 10

# Imagenes pegadas dentro de la descripcion (editor tipo correo)
MAX_IMAGEN_BYTES = 5 * 1024 * 1024
MAX_DESCRIPCION_CHARS = 500_000

# Configuración del módulo (tabla genérica `configuracion`, clave/valor)
CLAVE_COORDINADOR_ID = "reclamos_seguros_coordinador_id"
CLAVE_COORDINADOR_NOMBRE = "reclamos_seguros_coordinador_nombre"
CLAVE_ROLES_VISIBILIDAD_TOTAL = "reclamos_seguros_roles_visibilidad_total"
# Cuenta de correo que se lee para las respuestas del broker/aseguradora (poller,
# reutilizando el mismo mecanismo de email_to_task que ya usa soporteti@).
CLAVE_CUENTA_CORREO = "reclamos_seguros_cuenta_correo"
CUENTA_CORREO_DEFAULT = "segurosqp@quimpac.com.ec"

# Aviso de casos abiertos hace demasiado tiempo (fase 2). Cada tupla es
# (dias, columna_notificado); la columna existe en reclamos_seguros_casos
# (ALTER TABLE corrido a mano, ver plan de Fase 2).
UMBRALES_VENCIMIENTO_DIAS = [
    (30, "notificado_30d"),
    (45, "notificado_45d"),
    (60, "notificado_60d"),
]
