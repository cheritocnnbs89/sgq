# modules/users/user_constants.py
# ==========================================================
# Constantes del módulo de usuarios.
# Centraliza tablas, catálogos y valores repetidos.
# ==========================================================

# -------------------------
# Tablas
# -------------------------
TB_USUARIOS = "usuarios"
TB_DEPARTAMENTOS = "departamentos"
TB_ROLES = "roles"
TB_PERMISOS = "permisos"
TB_AREAS = "areas"
TB_PUESTOS = "puestos"
TB_EMPRESAS = "empresas"
TB_PARAM_VALUES = "param_values"
TB_USUARIOS_CC = "usuarios_cc"
TB_RECLAMOS = "reclamos"
TB_RECLAMO_RESPUESTAS = "reclamo_respuestas"
TB_GASTOS_TARJETA = "gastos_tarjeta"
TB_TAREAS = "tareas"

# -------------------------
# Parametrización
# -------------------------
CC_GROUP_ID = 7  # Centro de Costo

# -------------------------
# Carga masiva usuarios
# -------------------------
DEFAULT_BULK_USER_PASSWORD = "Quimpac2025*"

# -------------------------
# CSV departamentos plantilla
# -------------------------
CSV_DEPARTAMENTOS_HEADER = ["nombre"]
CSV_DEPARTAMENTOS_SAMPLE = [
    ["LOGISTICA"],
    ["OPERACIONES"],
    ["COMERCIAL"],
]

# -------------------------
# CSV usuarios plantilla
# -------------------------
CSV_USUARIOS_TEMPLATE_HEADER = [
    "NOMBRE", "APELLIDO", "CEDULA", "DIRECCION_E_MAIL", "",
    "SEXO", "FECHA_NACIMIENTO", "FECHA_INGRESO",
    "Provincia ", "Ciudad", "DESCRIPCION_DIR_1", "PUESTO",
    "DEPARTAMENTO", "EMPRESA", ""
]

CSV_USUARIOS_TEMPLATE_SAMPLE = [
    "JUAN ALFREDO", "ALVARADO MORAN", "1234567890", "jalvarado@quimpac.com.ec", "",
    "M", "1990-01-15 00:00:00.000", "2020-02-01 00:00:00.000",
    "GUAYAS", "GUAYAQUIL", "AV. 9 DE OCTUBRE 123", "SUPERVISOR DE PRODUCCION",
    "PRODUCCION CLORO SODA GYE QP", "QUIMPAC ECUADOR S.A", ""
]

# -------------------------
# Ordenamiento lista usuarios
# -------------------------
USERS_SORT_COLUMNS = {
    "id": "u.id",
    "username": "u.username",
    "email": "u.email",
    "rol": "u.rol",
    "departamento": "d.nombre",
    "jefe": "jefe_nombre",
    "fecha_registro": "u.fecha_registro",
    "estado": "u.disabled",
}