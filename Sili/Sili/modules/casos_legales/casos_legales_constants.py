# modules/casos_legales/casos_legales_constants.py
# -*- coding: utf-8 -*-

ACTIVE_KEY = "casos_legales"
PERM_CASOS = "casos_legales"          # ver · crear · editar (caso, avances, cierre) · eliminar · exportar

# Prefijo del código correlativo del caso (CASLEG001, CASLEG002, ...). El número sale de la
# tabla compartida secuencias_sap (misma que usan Contratos y Reembolsos), clave 'casos_legales'.
CODIGO_PREFIJO = "CASLEG"

ESTADO_ABIERTO = "ABIERTO"
ESTADO_CERRADO = "CERRADO"

# Tipos de caso según origen. Hoy solo "Internos" tiene campos definidos; Externos
# (Financiero) y Talento Humano usan el formulario base hasta que se definan sus campos.
# Visibilidad: solo quien registra el caso, su jefe directo (usuarios.jefe_id) y admin.
TIPOS_CASO = {
    "INTERNO": {"label": "Internos",       "icon": "bi-person",     "gestiona": "Legal",      "definido": True},
    "EXTERNO": {"label": "Externos",       "icon": "bi-briefcase",  "gestiona": "Financiero", "definido": False},
    "TTH":     {"label": "Talento Humano", "icon": "bi-people",     "gestiona": "TTH",        "definido": False},
}

# Adjuntos
EXTENSIONES_PERMITIDAS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".jpg", ".jpeg", ".png", ".txt", ".zip", ".msg", ".eml",
}
MAX_ADJUNTO_BYTES = 10 * 1024 * 1024       # por archivo
MAX_ADJUNTOS_POR_ENVIO = 10
MAX_BYTES_EMAIL = 10 * 1024 * 1024         # tope de adjuntos que viajan en el correo

ETAPA_REGISTRO = "REGISTRO"
ETAPA_AVANCE = "AVANCE"
ETAPA_CIERRE = "CIERRE"
