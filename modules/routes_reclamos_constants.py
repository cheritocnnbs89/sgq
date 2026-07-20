# modules/routes_reclamos_constants.py
# -*- coding: utf-8 -*-
"""
Constantes para el módulo de reclamos/oportunidades de mejora.
Centraliza nombres de tablas y grupos de parametros.
"""

# ── Tablas ──────────────────────────────────────────────────────────────────
T_RECLAMOS = "reclamos"
T_RECLAMO_ADJUNTOS = "reclamo_adjuntos"
T_RECLAMO_IMPUTADOS = "reclamo_imputados"
T_RECLAMO_IMPUTADO_ACCIONES = "reclamo_imputado_acciones"
T_RECLAMO_ACCION_EVIDENCIAS = "reclamo_accion_evidencias"
T_RECLAMO_EQUIPO = "reclamo_equipo"
T_RECLAMO_EQUIPO_ACCIONES = "reclamo_equipo_acciones"
T_RECLAMO_EQUIPO_RESPUESTAS = "reclamo_equipo_respuestas"
T_RECLAMO_RESPUESTAS_EQUIPO = "reclamo_respuestas_equipo"
T_RECLAMO_RESPUESTA_EQUIPO_ACCIONES = "reclamo_respuesta_equipo_acciones"
T_RECLAMO_RESPUESTA_EQUIPO_ACCION_EVIDENCIAS = "reclamo_respuesta_equipo_accion_evidencias"
T_RECLAMO_TIPO_CAMPOS = "reclamo_tipo_campos"
T_USUARIOS = "usuarios"
T_DEPARTAMENTOS = "departamentos"
T_PUESTOS = "puestos"
T_PARAM_GROUPS = "param_groups"
T_PARAM_VALUES = "param_values"
T_PRODUCTOS = "productos"
T_TERCEROS = "terceros"
T_REGIONES = "regiones"
T_PROVINCIAS = "provincias"
T_CANTONES = "cantones"

# ── Grupos de parametros (param_groups.nombre) ──────────────────────────────
PG_RECL_PROCESO = "RECL_PROCESO"
PG_RECL_PROCESO_SPONSOR = "RECL_PROCESO_SPONSOR"
PG_RECL_TIPO_RECLAMO = "RECL_TIPO_RECLAMO"
PG_RECL_TIPO_TRAMITE = "RECL_TIPO_TRAMITE"
PG_RECL_MOTIVO = "RECL_MOTIVO"
PG_RECL_CANAL = "RECL_CANAL"

# ── Estados de asignacion ───────────────────────────────────────────────────
ESTADO_APROBADO   = "aprobado"
ESTADO_PENDIENTE  = "pendiente"
ESTADO_RECHAZADO  = "rechazado"

# ── Roles de sponsor ────────────────────────────────────────────────────────
SPONSOR_PRINCIPAL = "PRINCIPAL"
SPONSOR_BACKUP    = "BACKUP"

# ── Tipos de accion ─────────────────────────────────────────────────────────
ACCION_CAUSA      = "CAUSA"
ACCION_CONTROL    = "CONTROL"
ACCION_CORRECTIVA = "CORRECTIVA"

# ── Codigo de reclamo ───────────────────────────────────────────────────────
CODIGO_PREFIX = "RECL"
