# modules/gastos/gastos_constants.py

# =========================
# TABLAS
# =========================
TABLE_GASTOS = "gastos_tarjeta"
TABLE_DETALLE = "gastos_tarjeta_detalle"
TABLE_ARCHIVOS = "gastos_tarjeta_archivos"
TABLE_FACTURAS_XML = "facturas_xml"
TABLE_FACTURAS_XML_DET = "facturas_xml_det"
TABLE_TERCEROS = "terceros"
TABLE_USUARIOS = "usuarios"
TABLE_PARAM_GROUPS = "param_groups"
TABLE_PARAM_VALUES = "param_values"
TABLE_DEPARTAMENTOS = "departamentos"
TABLE_ROLES = "roles"
TABLE_PERMISOS = "permisos"
TABLE_ROLES_PERMISOS = "roles_permisos"
TABLE_OPCIONES = "opciones"

# =========================
# ESTADOS
# =========================
ESTADO_PENDIENTE = "PENDIENTE"
ESTADO_APROBADO = "APROBADO"
ESTADO_RECHAZADO = "RECHAZADO"
ESTADO_ENVIADO_SAP = "ENVIADO_SAP"
ESTADO_BORRADOR = "BORRADOR"

# =========================
# FACTURAS XML
# =========================
FACTURA_XML_PENDIENTE = "PENDIENTE"
FACTURA_XML_USADA = "USADA"
FACTURA_XML_ANULADA = "ANULADA"

# =========================
# ROLES
# =========================
ROLES_APROBADORES = {"ga", "gf", "gg"}
ROLES_SUPER = {"admin", "sistemas"}

# =========================
# TIPOS GASTO
# =========================
TIPO_CAJA_CHICA = "caja_chica"
TIPO_TARJETA = "tarjeta"
TIPO_REEMBOLSO = "reembolso"
TIPO_BOLETO = "boletos"
TIPO_TARJETA_ONLINE = "tarjeta_online"

TIPOS_GASTO = {
    TIPO_CAJA_CHICA,
    TIPO_TARJETA,
    TIPO_REEMBOLSO,
    TIPO_BOLETO,
    TIPO_TARJETA_ONLINE,
}

# =========================
# IVA
# =========================
IVA_INDICADOR_MAP = {
    0: "0%",
    8: "8%",
    10: "10%",
    12: "12%",
    15: "15%",
}

IVA_INDICADOR_DEFAULT = "0%"

# =========================
# EXPORTS / LÍMITES
# =========================
MAX_EXPORT_ROWS = 5000
MAX_XML_SEARCH_LIMIT = 50
DEFAULT_XML_SEARCH_LIMIT = 10