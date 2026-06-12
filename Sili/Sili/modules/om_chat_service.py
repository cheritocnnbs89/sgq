import os
import re
import json
import pyodbc
import logging
from openai import OpenAI
from modules.db import get_db

log = logging.getLogger(__name__)

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Vistas autorizadas. El asistente NO debe consultar tablas físicas.
TABLAS_PERMITIDAS = [
    "vw_om_reporte_base",
    "vw_om_acciones_base",
]

PROHIBIDAS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
    "MERGE", "EXEC", "CREATE", "GRANT", "REVOKE", "XP_",
    "INFORMATION_SCHEMA", "SYS.", "--", "/*", "*/"
]

PALABRAS_OM = [
    "om", "oms", "oportunidad", "oportunidades", "mejora", "reclamo", "reclamos",
    "cliente", "clientes", "proceso", "departamento", "sponsor", "responsable",
    "usuario", "creador", "jefe", "tipo", "estado", "abierta", "abiertas",
    "cerrada", "cerradas", "pendiente", "pendientes", "respuesta", "respuestas",
    "fecha", "fechas", "mes", "semana", "dia", "dias", "mayo", "promedio",
    "tiempo", "flujo", "trazabilidad", "linea", "historial", "equipo", "miembro",
    "accion", "acciones", "control", "correctiva", "correctivas", "cumplimiento",
    "vencida", "vencidas", "vencer", "vencen", "vencio", "vencieron", "evidencia"
]

PREGUNTAS_GUIA = """
Ejemplos de preguntas que el usuario puede hacer y que debes responder si hay columnas disponibles:

Volumen general:
- Cuántas OM hay en total.
- Cuántas OM hay abiertas.
- Cuántas OM hay cerradas.
- Cuántas OM se crearon hoy / esta semana / este mes.
- Cuántas OM cerradas hay por mes.
- Cuántas OM abiertas hay por mes.

Clientes:
- Cuántas OM hay por cliente.
- Qué cliente tiene más OM.
- Qué clientes tienen OM abiertas.
- Cuántas OM cerradas tiene cada cliente.
- Qué tipo de OM tiene cada cliente.
- Cuántas OM por tipo de reclamo y cliente.

Procesos/departamentos:
- Cuántas OM hay por proceso.
- Qué proceso tiene más OM.
- Qué procesos tienen más OM abiertas/cerradas/sin respuesta.
- Cuántas OM tiene Sistemas, Comercial, Quimitransport u otro proceso/departamento.
- Cuántas OM hay por proceso y mes.

Tipo de reclamo / tipo OM:
- Cuántas OM hay por tipo de reclamo.
- Cuál es el tipo de reclamo más frecuente.
- Cuántas OM por tipo de reclamo y cliente.
- Cuántas OM por tipo de reclamo y proceso.
- Cuántas OM por tipo de reclamo y sponsor.
- Cuántas OM por tipo de reclamo y mes.

Sponsors / responsables:
- Cuántas OM tiene cada sponsor.
- Qué sponsor tiene más OM asignadas.
- Qué sponsor tiene más OM cerradas/abiertas/sin respuesta.
- Cuántas OM tiene cada sponsor por mes.
- Promedio de días de respuesta por sponsor.
- Qué sponsor responde más rápido o más lento.

Usuarios / creadores:
- Cuántas OM creó cada usuario.
- Qué usuario creó más OM.
- Cuántas OM creó cada usuario por mes.
- Cuántas OM creó cada usuario en mayo.
- Frecuencia de creación de OM por usuario.

Fechas y tendencias:
- Cuántas OM se crearon por mes, semana o día.
- Cuántas OM se crearon cada día de mayo.
- Día con más creación de OM.
- Mes con más OM creadas.
- Frecuencia promedio de creación de OM por mes/semana.
- Cuántas OM se cerraron en los últimos 10 días.
- Cuántas OM se cerraron en los últimos 30 días.
- Cuántas OM se cerraron esta semana / ayer / hoy.

Tiempo de respuesta:
- Promedio de días de respuesta por sponsor, proceso, cliente, tipo de reclamo o usuario.
- OM con más días sin respuesta sponsor.
- OM con más de 5, 10 o 15 días sin respuesta.
- Tiempo de respuesta de la OM RECL00132.
- Cuántos días tardó en responderse/cerrarse la OM RECL00132.

Flujo / trazabilidad:
- Dame el flujo de la OM RECL00132 desde que se creó hasta que se cerró.
- Dame la trazabilidad, línea de tiempo o historial de la OM RECL00132.

Equipo de respuestas:
- Cuántas OM tienen equipo asignado.
- Cuántas OM no tienen equipo asignado.
- Miembros de equipo por OM.
- Miembro de equipo con más OM asignadas.
- Miembros con respuestas pendientes.
- Promedio de días de respuesta por miembro de equipo.
- OM con equipo asignado pero sin respuesta.

Acciones de control y correctivas:
- Qué acciones de control están por vencer.
- Qué acciones correctivas están por vencer.
- Qué acciones vencen en los próximos 5 días.
- Qué acciones están vencidas.
- Cuáles OM tienen acciones vencidas o por vencer.
- Qué usuarios no han cumplido sus acciones de control/correctivas.
- Qué sponsor tiene acciones vencidas o por vencer.
- Qué acciones vencieron esta semana / vencen esta semana / vencen este mes.
- OM con acciones de control/correctivas sin evidencia.
- Usuarios que no han cargado evidencia de acciones correctivas o de control.

Indicadores ejecutivos:
- Resumen general de OM.
- Top 10 procesos/clientes/sponsors con más OM.
- Top 10 OM con más días sin respuesta.
- Total de OM abiertas, cerradas y sin respuesta.
- Total de OM por mes y estado.
"""


def _kw(*keywords: str):
    """Devuelve un callable que verifica si TODOS los keywords están en el texto."""
    def _check(text: str) -> bool:
        return all(kw in text for kw in keywords)
    return _check


def _any_kw(*keywords: str):
    """Devuelve un callable que verifica si ALGUNO de los keywords está en el texto."""
    def _check(text: str) -> bool:
        return any(kw in text for kw in keywords)
    return _check


def normalizar_pregunta(txt: str) -> str:
    txt = (txt or "").lower().strip()
    repl = {
        "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
        "ñ": "n", "¿": "", "?": "", ",": "", ".": "", ";": ""
    }
    for a, b in repl.items():
        txt = txt.replace(a, b)
    return " ".join(txt.split())


def cargar_reglas_modulo(conn, modulo: str):
    cur = conn.cursor()
    cur.execute("""
        SELECT patron
        FROM ai_chat_modulo_reglas
        WHERE modulo = ?
          AND activo = 1
          AND aprobado = 1
    """, (modulo,))
    return [r["patron"] for r in cur.fetchall()]


def pregunta_permitida_modulo(conn, pregunta_norm: str, modulo: str) -> bool:
    # 1) Sinónimos base: evita bloquear preguntas válidas como "tipo por cliente" o fechas.
    if any(p in pregunta_norm for p in PALABRAS_OM):
        return True

    # 2) Reglas configurables en BD.
    reglas = cargar_reglas_modulo(conn, modulo)
    reglas_norm = [normalizar_pregunta(x) for x in reglas]
    return any(r in pregunta_norm for r in reglas_norm)


def sugerir_regla(conn, modulo: str, pregunta_norm: str):
    palabras = pregunta_norm.split()
    if len(palabras) < 2:
        return

    patron = " ".join(palabras[:5])
    cur = conn.cursor()
    cur.execute("""
        SELECT TOP 1 id
        FROM ai_chat_modulo_reglas
        WHERE modulo = ?
          AND patron = ?
    """, (modulo, patron))

    if cur.fetchone():
        return

    cur.execute("""
        INSERT INTO ai_chat_modulo_reglas (modulo, patron, activo, aprobado)
        VALUES (?, ?, 0, 0)
    """, (modulo, patron))
    conn.commit()


def buscar_cache(conn, pregunta_norm: str):
    cur = conn.cursor()
    cur.execute("""
        SELECT TOP 1 id, sql_generado
        FROM om_chat_sql_cache
        WHERE pregunta_normalizada = ?
          AND activo = 1
        ORDER BY usos DESC, id DESC
    """, (pregunta_norm,))
    return cur.fetchone()


def guardar_cache(conn, pregunta_norm, pregunta_original, sql_generado, user_id=None):
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO om_chat_sql_cache (
            pregunta_normalizada,
            pregunta_original,
            sql_generado,
            creado_por
        )
        VALUES (?, ?, ?, ?)
    """, (pregunta_norm, pregunta_original, sql_generado, user_id))
    conn.commit()


def marcar_uso_cache(conn, cache_id):
    cur = conn.cursor()
    cur.execute("""
        UPDATE om_chat_sql_cache
        SET usos = usos + 1,
            ultimo_uso_at = GETDATE()
        WHERE id = ?
    """, (cache_id,))
    conn.commit()


def normalizar_sql_server(sql: str) -> str:
    sql = (sql or "").strip().rstrip(";")
    sql = re.sub(r"(?i)^SELECT\s+TOP\s+(\d+)\s+DISTINCT\s+", r"SELECT DISTINCT TOP \1 ", sql)
    return sql


def validar_sql_solo_select(sql: str) -> str:
    sql = (sql or "").strip().rstrip(";")
    upper = sql.upper()

    if not upper.startswith("SELECT"):
        raise ValueError("Solo se permiten consultas SELECT.")

    if ";" in sql:
        raise ValueError("No se permite ejecutar múltiples sentencias.")

    for palabra in PROHIBIDAS:
        if palabra in upper:
            raise ValueError(f"SQL no permitido: {palabra}")

    tablas_sql = re.findall(r"\b(?:FROM|JOIN)\s+([a-zA-Z0-9_\.]+)", sql, re.I)
    if not tablas_sql:
        raise ValueError("La consulta debe usar una vista permitida.")

    for t in tablas_sql:
        t_limpia = t.split(".")[-1].lower()
        if t_limpia not in TABLAS_PERMITIDAS:
            raise ValueError(f"Tabla no permitida: {t_limpia}")

    if " TOP " not in upper and "COUNT(" not in upper:
        sql = re.sub(r"^SELECT\s+", "SELECT TOP 100 ", sql, flags=re.I)

    return sql


def _like_param(valor: str) -> str:
    return f"%{(valor or '').strip()}%"


def _extraer_codigo_om(texto: str) -> str | None:
    texto = texto or ""

    # Casos: RECL00162, RECL 162, RECL-162, OM162, OM 162, OM-162
    m = re.search(r"\b(RECL|OM)[- ]?0*(\d{1,})\b", texto, re.I)
    if m:
        numero = m.group(2)
        return f"RECL{numero.zfill(5)}"

    return None




def _extraer_ultimos_dias(pregunta_norm: str) -> int | None:
    m = re.search(r"ultimos\s+(\d+)\s+dias", pregunta_norm, re.I)
    if m:
        return int(m.group(1))
    return None

def sql_predefinido_vista(pregunta_norm: str, pregunta_original: str, user_id: int | None):
    uid = int(user_id or 0)
    texto = (pregunta_original or "").strip()
    codigo_om = _extraer_codigo_om(texto)

    # =========================================================
    # 1) OM específica: tiempo de respuesta
    # =========================================================
        # =========================================================
    # OM específica: acciones correctivas / control / seguimiento
    # Debe ir ANTES del if codigo_om general
    # =========================================================
    if codigo_om and (
        "accion" in pregunta_norm
        or "acciones" in pregunta_norm
        or "correctiva" in pregunta_norm
        or "correctivas" in pregunta_norm
        or "control" in pregunta_norm
        or "seguimiento" in pregunta_norm
        or "evidencia" in pregunta_norm
        or "vencida" in pregunta_norm
        or "vencidas" in pregunta_norm
        or "por vencer" in pregunta_norm
    ):
        filtro_tipo = ""

        if "correctiva" in pregunta_norm or "correctivas" in pregunta_norm:
            filtro_tipo = "AND UPPER(tipo_accion) = 'CORRECTIVA'"
        elif "control" in pregunta_norm:
            filtro_tipo = "AND UPPER(tipo_accion) = 'CONTROL'"

        filtro_estado = ""

        if "vencida" in pregunta_norm or "vencidas" in pregunta_norm:
            filtro_estado = "AND estado_cumplimiento_accion = 'VENCIDA'"
        elif "por vencer" in pregunta_norm:
            filtro_estado = "AND estado_cumplimiento_accion = 'POR VENCER'"

        sql = f"""
            SELECT TOP 100
                codigo_om,
                cliente,
                proceso,
                sponsor_nombre,
                tipo_accion,
                descripcion_accion,
                fecha_compromiso,
                fecha_cumplimiento,
                cumplido,
                requiere_evidencia,
                tiene_evidencia,
                estado_cumplimiento_accion,
                dias_para_vencer
            FROM vw_om_acciones_base
            WHERE UPPER(codigo_om) = UPPER(?)
              {filtro_tipo}
              {filtro_estado}
            ORDER BY
                CASE WHEN cumplido = 1 THEN 1 ELSE 0 END,
                fecha_compromiso ASC
        """

        return sql, [codigo_om], "predefinido_acciones_om"
    if codigo_om and (
        "tiempo de respuesta" in pregunta_norm
        or "dias tardo" in pregunta_norm
        or "cuantos dias" in pregunta_norm
        or "estuvo abierta" in pregunta_norm
    ):
        return """
            SELECT TOP 1
                codigo_om,
                fecha_creacion,
                fecha_reclamo,
                cliente,
                proceso,
                tipo_reclamo,
                estado_global,
                estado_asignacion,
                estado_respuesta,
                sponsor_nombre,
                miembros_equipo,
                fecha_primera_asignacion_equipo,
                fecha_primera_respuesta_equipo,
                fecha_respuesta_imputado,
                fecha_aprobacion_respuesta,
                dias_respuesta_sponsor,
                dias_sin_respuesta_sponsor
            FROM vw_om_reporte_base
            WHERE UPPER(codigo_om) = UPPER(?)
            ORDER BY imputacion_id DESC
        """, [codigo_om], "predefinido_tiempo_om"

    # =========================================================
    # 2) OM específica: flujo / trazabilidad / línea de tiempo
    # =========================================================
    if codigo_om and (
        "flujo" in pregunta_norm
        or "trazabilidad" in pregunta_norm
        or "linea de tiempo" in pregunta_norm
        or "historial" in pregunta_norm
    ):
        return """
            SELECT TOP 1
                codigo_om,
                fecha_creacion,
                fecha_reclamo,
                creador_nombre,
                cliente,
                proceso,
                tipo_reclamo,
                sponsor_nombre,
                jefe_nombre,
                miembros_equipo,
                fecha_primera_asignacion_equipo,
                fecha_primera_respuesta_equipo,
                fecha_respuesta_imputado,
                fecha_aprobacion_respuesta,
                fecha_rechazo_respuesta,
                estado_global,
                estado_asignacion,
                estado_respuesta,
                dias_respuesta_sponsor,
                dias_sin_respuesta_sponsor,
                respuesta_causa,
                respuesta_preventiva,
                respuesta_correctiva
            FROM vw_om_reporte_base
            WHERE UPPER(codigo_om) = UPPER(?)
            ORDER BY imputacion_id DESC
        """, [codigo_om], "predefinido_flujo_om"

    # =========================================================
    # 3) OM específica: detalle general / estado / status
    #    Esto responde cualquier pregunta que tenga una OM concreta:
    #    "status de la om 162", "cómo va la OM 149", "dime la OM 160", etc.
    # =========================================================
    if codigo_om:
        return """
            SELECT TOP 1
                codigo_om,
                fecha_reclamo,
                fecha_creacion,
                cliente,
                proceso,
                tipo_reclamo,
                estado_global,
                estado_asignacion,
                estado_respuesta,
                sponsor_nombre,
                miembros_equipo,
                dias_respuesta_sponsor,
                dias_sin_respuesta_sponsor,
                fecha_primera_asignacion_equipo,
                fecha_primera_respuesta_equipo,
                fecha_respuesta_imputado,
                fecha_aprobacion_respuesta,
                respuesta_causa,
                respuesta_preventiva,
                respuesta_correctiva
            FROM vw_om_reporte_base
            WHERE UPPER(codigo_om) = UPPER(?)
            ORDER BY imputacion_id DESC
        """, [codigo_om], "predefinido_detalle_om"

    # =========================================================
    # Totales personales
    # =========================================================
    if pregunta_norm in (
        "cuantas om estan por vencer las acciones de control y correctivas",
        "cuantas om tienen acciones de control y correctivas por vencer",
        "acciones de control y correctivas por vencer",
        "om con acciones por vencer",
        "cuantas om tienen acciones por vencer",
    ):
        return """
            SELECT
                tipo_accion,
                COUNT(DISTINCT reclamo_id) AS total_om,
                COUNT(*) AS total_acciones
            FROM vw_om_acciones_base
            WHERE estado_cumplimiento_accion = 'POR VENCER'
              AND UPPER(tipo_accion) IN ('CONTROL', 'CORRECTIVA')
            GROUP BY tipo_accion
            ORDER BY total_acciones DESC
        """, [], "predefinido_acciones"

    if pregunta_norm in (
        "cuantas om llevo hoy",
        "cuantas om tengo hoy",
        "cuantas oportunidades de mejora llevo hoy",
        "cuantas om ingrese hoy",
    ):
        return """
            SELECT COUNT(DISTINCT reclamo_id) AS total_om
            FROM vw_om_reporte_base
            WHERE creador_username IN (SELECT username FROM usuarios WHERE id = ?)
              AND TRY_CONVERT(date, fecha_creacion) = CAST(GETDATE() AS date)
        """, [uid], "predefinido_vista"

    if pregunta_norm in (
        "cuantas om llevo esta semana",
        "cuantas om tengo esta semana",
    ):
        return """
            SELECT COUNT(DISTINCT reclamo_id) AS total_om
            FROM vw_om_reporte_base
            WHERE creador_username IN (SELECT username FROM usuarios WHERE id = ?)
              AND TRY_CONVERT(date, fecha_creacion) >= DATEADD(day, 1 - DATEPART(weekday, GETDATE()), CAST(GETDATE() AS date))
        """, [uid], "predefinido_vista"

    # =========================================================
    # Conteos generales
    # =========================================================
    # Total general — sin filtro de estado y sin otros agrupadores
    _sin_grupo = not any(x in pregunta_norm for x in [
        "por cliente", "por proceso", "por departamento", "por sponsor",
        "por usuario", "por tipo", "por mes", "por dia", "abiert",
        "cerrad", "pendiente", "sin respuesta", "vencid",
    ])
    if _sin_grupo and any(x in pregunta_norm for x in [
        "total om", "total de om", "cuantas om hay", "cuantas om existen",
        "cuantas oportunidades hay", "cuantas oportunidades de mejora hay",
        "total oportunidades", "numero de om", "resumen general",
    ]):
        return """
            SELECT COUNT(DISTINCT reclamo_id) AS total_om
            FROM vw_om_reporte_base
        """, [], "predefinido_vista"

    # OM abiertas — sin otros agrupadores
    if any(x in pregunta_norm for x in ["om abiert", "oportunidades abiert", "abiertas hay", "hay abiert"]) \
            and not any(x in pregunta_norm for x in ["por ", "cada "]):
        return """
            SELECT COUNT(DISTINCT reclamo_id) AS total_om
            FROM vw_om_reporte_base
            WHERE LOWER(ISNULL(estado_global,'')) = 'abierto'
        """, [], "predefinido_vista"

    # OM cerradas — sin otros agrupadores
    if any(x in pregunta_norm for x in ["om cerrad", "oportunidades cerrad", "cerradas hay", "hay cerrad"]) \
            and not any(x in pregunta_norm for x in ["por ", "cada "]):
        return """
            SELECT COUNT(DISTINCT reclamo_id) AS total_om
            FROM vw_om_reporte_base
            WHERE LOWER(ISNULL(estado_global,'')) = 'cerrado'
        """, [], "predefinido_vista"

    # =========================================================
    # Por cliente / proceso / tipo / sponsor / usuario
    # =========================================================
    # ── Por cliente ──────────────────────────────────────────────
    _kw_cliente = any(x in pregunta_norm for x in ["por cliente", "por clientes", "cliente tiene", "clientes tienen"])
    _kw_tipo    = any(x in pregunta_norm for x in ["por tipo", "tipos de reclamo", "tipo de reclamo", "tipo reclamo"])
    if _kw_cliente and not _kw_tipo:
        return """
            SELECT TOP 100
                ISNULL(cliente, 'SIN CLIENTE') AS cliente,
                COUNT(DISTINCT reclamo_id) AS total_om
            FROM vw_om_reporte_base
            GROUP BY ISNULL(cliente, 'SIN CLIENTE')
            ORDER BY total_om DESC
        """, [], "predefinido_vista"

    # ── Por proceso / departamento ────────────────────────────────
    if any(x in pregunta_norm for x in [
        "por proceso", "por departamento", "por area", "proceso tiene", "departamento tiene",
        "area tiene", "procesos con mas", "departamentos con mas", "areas con mas",
    ]) and not _kw_tipo and not _kw_cliente \
      and not any(x in pregunta_norm for x in ["demor", "tarda", "tiempo", "dias", "respuesta"]):
        return """
            SELECT TOP 100
                ISNULL(proceso, 'SIN PROCESO') AS proceso,
                COUNT(DISTINCT reclamo_id) AS total_om
            FROM vw_om_reporte_base
            GROUP BY ISNULL(proceso, 'SIN PROCESO')
            ORDER BY total_om DESC
        """, [], "predefinido_vista"

    # ── Por tipo de reclamo ───────────────────────────────────────
    if _kw_tipo and _kw_cliente:
        return """
            SELECT TOP 100
                ISNULL(cliente, 'SIN CLIENTE') AS cliente,
                ISNULL(tipo_reclamo, 'SIN TIPO') AS tipo_reclamo,
                COUNT(DISTINCT reclamo_id) AS total_om
            FROM vw_om_reporte_base
            GROUP BY ISNULL(cliente, 'SIN CLIENTE'), ISNULL(tipo_reclamo, 'SIN TIPO')
            ORDER BY total_om DESC
        """, [], "predefinido_vista"

    if _kw_tipo and not _kw_cliente:
        return """
            SELECT TOP 100
                ISNULL(tipo_reclamo, 'SIN TIPO') AS tipo_reclamo,
                COUNT(DISTINCT reclamo_id) AS total_om
            FROM vw_om_reporte_base
            GROUP BY ISNULL(tipo_reclamo, 'SIN TIPO')
            ORDER BY total_om DESC
        """, [], "predefinido_vista"

    # ── Por sponsor ───────────────────────────────────────────────
    if any(x in pregunta_norm for x in [
        "por sponsor", "sponsor tiene", "sponsors asignados",
        "sponsor asignado", "cada sponsor",
    ]):
        return """
            SELECT TOP 100
                sponsor_nombre,
                COUNT(DISTINCT reclamo_id) AS total_om
            FROM vw_om_reporte_base
            WHERE ISNULL(sponsor_nombre, '') <> ''
            GROUP BY sponsor_nombre
            ORDER BY total_om DESC
        """, [], "predefinido_vista"

    # ── Por usuario / creador ─────────────────────────────────────
    if any(x in pregunta_norm for x in [
        "por usuario", "cada usuario", "creo cada", "creador",
        "usuario creo", "usuarios crearon",
    ]):
        if "por mes" in pregunta_norm:
            return """
                SELECT TOP 100
                    FORMAT(TRY_CONVERT(date, fecha_creacion), 'yyyy-MM') AS mes,
                    creador_nombre,
                    COUNT(DISTINCT reclamo_id) AS total_om
                FROM vw_om_reporte_base
                GROUP BY FORMAT(TRY_CONVERT(date, fecha_creacion), 'yyyy-MM'), creador_nombre
                ORDER BY mes DESC, total_om DESC
            """, [], "predefinido_vista"

        return """
            SELECT TOP 100
                creador_nombre,
                COUNT(DISTINCT reclamo_id) AS total_om
            FROM vw_om_reporte_base
            GROUP BY creador_nombre
            ORDER BY total_om DESC
        """, [], "predefinido_vista"

    # =========================================================
    # Fechas / tendencias
    # =========================================================
    if pregunta_norm in (
        "cuantas om se crearon por mes",
        "om creadas por mes",
        "frecuencia de creacion de om por mes",
        "frecuencia promedio de creacion de om por mes",
    ):
        return """
            SELECT
                FORMAT(TRY_CONVERT(date, fecha_creacion), 'yyyy-MM') AS mes,
                COUNT(DISTINCT reclamo_id) AS total_om
            FROM vw_om_reporte_base
            WHERE TRY_CONVERT(date, fecha_creacion) IS NOT NULL
            GROUP BY FORMAT(TRY_CONVERT(date, fecha_creacion), 'yyyy-MM')
            ORDER BY mes DESC
        """, [], "predefinido_vista"

    if pregunta_norm in (
        "cuantas om se crearon por dia",
        "om creadas por dia",
        "frecuencia de creacion de om por dia",
    ):
        return """
            SELECT
                TRY_CONVERT(date, fecha_creacion) AS fecha,
                COUNT(DISTINCT reclamo_id) AS total_om
            FROM vw_om_reporte_base
            WHERE TRY_CONVERT(date, fecha_creacion) IS NOT NULL
            GROUP BY TRY_CONVERT(date, fecha_creacion)
            ORDER BY fecha DESC
        """, [], "predefinido_vista"

    if pregunta_norm in (
        "cuantas om se crearon en mayo",
        "om creadas en mayo",
        "cuantas om creo cada usuario en mayo",
        "cuantas om se crearon cada dia de mayo",
    ):
        if "cada usuario" in pregunta_norm:
            return """
                SELECT TOP 100
                    creador_username,
                    creador_nombre,
                    COUNT(DISTINCT reclamo_id) AS total_om
                FROM vw_om_reporte_base
                WHERE MONTH(TRY_CONVERT(date, fecha_creacion)) = 5
                GROUP BY creador_username, creador_nombre
                ORDER BY total_om DESC
            """, [], "predefinido_vista"

        if "cada dia" in pregunta_norm:
            return """
                SELECT
                    TRY_CONVERT(date, fecha_creacion) AS fecha,
                    COUNT(DISTINCT reclamo_id) AS total_om
                FROM vw_om_reporte_base
                WHERE MONTH(TRY_CONVERT(date, fecha_creacion)) = 5
                GROUP BY TRY_CONVERT(date, fecha_creacion)
                ORDER BY fecha DESC
            """, [], "predefinido_vista"

        return """
            SELECT COUNT(DISTINCT reclamo_id) AS total_om
            FROM vw_om_reporte_base
            WHERE MONTH(TRY_CONVERT(date, fecha_creacion)) = 5
        """, [], "predefinido_vista"

    if pregunta_norm in (
        "total de om cerradas por mes",
        "om cerradas por mes",
        "cuantas om cerradas por mes",
        "total om cerradas por mes",
    ):
        return """
            SELECT
                FORMAT(TRY_CONVERT(date, fecha_reclamo), 'yyyy-MM') AS mes,
                COUNT(DISTINCT reclamo_id) AS total_om
            FROM vw_om_reporte_base
            WHERE LOWER(ISNULL(estado_global, '')) = 'cerrado'
              AND TRY_CONVERT(date, fecha_reclamo) IS NOT NULL
            GROUP BY FORMAT(TRY_CONVERT(date, fecha_reclamo), 'yyyy-MM')
            ORDER BY mes DESC
        """, [], "predefinido_vista"

    dias = _extraer_ultimos_dias(pregunta_norm)
    if dias and (
        "cerraron" in pregunta_norm
        or "cerradas" in pregunta_norm
        or "cerrada" in pregunta_norm
    ):
        return """
            SELECT COUNT(DISTINCT reclamo_id) AS total_om
            FROM vw_om_reporte_base
            WHERE LOWER(ISNULL(estado_global, '')) = 'cerrado'
              AND TRY_CONVERT(date, fecha_aprobacion_respuesta) >= DATEADD(day, -?, CAST(GETDATE() AS date))
        """, [dias], "predefinido_vista"

    # =========================================================
    # Tiempos de respuesta agregados
    # =========================================================
    _kw_demora_sponsor = any(x in pregunta_norm for x in [
        "promedio de dias de respuesta por sponsor",
        "dias promedio de respuesta por sponsor",
        "tiempo promedio de respuesta por sponsor",
        "que sponsor tarda mas en responder",
        "sponsor mas demorado",
        "sponsor tarda mas",
        "demora por sponsor",
        "tiempo de respuesta por sponsor",
    ])
    if _kw_demora_sponsor:
        return """
            SELECT TOP 100
                sponsor_nombre,
                AVG(CAST(dias_respuesta_sponsor AS decimal(18,2))) AS dias_promedio_respuesta,
                COUNT(DISTINCT reclamo_id) AS total_om,
                SUM(CASE WHEN dias_respuesta_sponsor IS NOT NULL THEN 1 ELSE 0 END) AS om_con_respuesta
            FROM vw_om_reporte_base
            WHERE ISNULL(sponsor_nombre,'') <> ''
            GROUP BY sponsor_nombre
            HAVING SUM(CASE WHEN dias_respuesta_sponsor IS NOT NULL THEN 1 ELSE 0 END) > 0
            ORDER BY dias_promedio_respuesta DESC
        """, [], "predefinido_vista"

    _kw_demora_proceso = any(x in pregunta_norm for x in [
        "promedio de dias de respuesta por proceso",
        "dias promedio de respuesta por proceso",
        "que proceso tiene mayor demora",
        "que area tiene mayor demora",
        "que area es la mas demorada",
        "que proceso es el mas demorado",
        "area mas demorada",
        "proceso mas demorado",
        "tiempo de respuesta por proceso",
        "tiempo de respuesta por area",
        "demora por proceso",
        "demora por area",
        "tarda mas en responder",
        "demoran mas en responder",
    ])
    if _kw_demora_proceso and not any(x in pregunta_norm for x in ["sponsor", "cliente", "usuario"]):
        return """
            SELECT TOP 100
                ISNULL(proceso, 'SIN PROCESO') AS proceso,
                AVG(CAST(dias_respuesta_sponsor AS decimal(18,2))) AS dias_promedio_respuesta,
                COUNT(DISTINCT reclamo_id) AS total_om,
                SUM(CASE WHEN dias_respuesta_sponsor IS NOT NULL THEN 1 ELSE 0 END) AS om_con_respuesta
            FROM vw_om_reporte_base
            WHERE ISNULL(proceso,'') <> ''
            GROUP BY ISNULL(proceso, 'SIN PROCESO')
            HAVING SUM(CASE WHEN dias_respuesta_sponsor IS NOT NULL THEN 1 ELSE 0 END) > 0
            ORDER BY dias_promedio_respuesta DESC
        """, [], "predefinido_vista"

    if pregunta_norm in (
        "cuales om tienen mas dias sin respuesta",
        "om con mas dias sin respuesta",
        "top 10 de om con mas dias sin respuesta",
    ):
        return """
            SELECT TOP 10
                codigo_om,
                cliente,
                proceso,
                sponsor_nombre,
                dias_sin_respuesta_sponsor,
                estado_global
            FROM vw_om_reporte_base
            WHERE ISNULL(dias_sin_respuesta_sponsor, 0) > 0
            ORDER BY dias_sin_respuesta_sponsor DESC
        """, [], "predefinido_vista"

    # =========================================================
    # Equipo
    # =========================================================
    if pregunta_norm in (
        "cuantas om tienen equipo asignado",
        "om con equipo asignado",
        "cuantas om no tienen equipo asignado",
    ):
        if "no tienen" in pregunta_norm:
            return """
                SELECT COUNT(DISTINCT reclamo_id) AS total_om
                FROM vw_om_reporte_base
                WHERE ISNULL(total_miembros_equipo, 0) = 0
            """, [], "predefinido_vista"

        return """
            SELECT COUNT(DISTINCT reclamo_id) AS total_om
            FROM vw_om_reporte_base
            WHERE ISNULL(total_miembros_equipo, 0) > 0
        """, [], "predefinido_vista"

    if pregunta_norm in (
        "promedio de dias de respuesta por miembro de equipo",
        "que miembro de equipo tarda mas en responder",
    ):
        return """
            SELECT TOP 100
                miembros_equipo,
                AVG(CAST(dias_promedio_respuesta_equipo AS decimal(18,2))) AS dias_promedio_respuesta_equipo,
                COUNT(DISTINCT reclamo_id) AS total_om
            FROM vw_om_reporte_base
            WHERE ISNULL(miembros_equipo, '') <> ''
              AND dias_promedio_respuesta_equipo IS NOT NULL
            GROUP BY miembros_equipo
            ORDER BY dias_promedio_respuesta_equipo DESC
        """, [], "predefinido_vista"

    # =========================================================
    # Acciones control / correctiva
    # =========================================================
    if pregunta_norm in (
        "cuantas om tienen acciones vencidas",
        "cuantas om estan vencidas las acciones de control y correctivas",
    ):
        return """
            SELECT
                tipo_accion,
                COUNT(DISTINCT reclamo_id) AS total_om,
                COUNT(*) AS total_acciones
            FROM vw_om_acciones_base
            WHERE estado_cumplimiento_accion = 'VENCIDA'
              AND UPPER(tipo_accion) IN ('CONTROL', 'CORRECTIVA')
            GROUP BY tipo_accion
            ORDER BY total_acciones DESC
        """, [], "predefinido_acciones"

    if pregunta_norm in (
        "cuales om tienen acciones por vencer",
        "dame las om con acciones por vencer",
        "que acciones estan por vencer",
        "cuales son las acciones por vencer",
    ):
        return """
            SELECT TOP 100
                codigo_om,
                cliente,
                proceso,
                sponsor_nombre,
                tipo_accion,
                descripcion_accion,
                fecha_compromiso,
                dias_para_vencer,
                estado_cumplimiento_accion
            FROM vw_om_acciones_base
            WHERE estado_cumplimiento_accion = 'POR VENCER'
              AND UPPER(tipo_accion) IN ('CONTROL', 'CORRECTIVA')
            ORDER BY dias_para_vencer ASC
        """, [], "predefinido_acciones"

    if any(x in pregunta_norm for x in [
        "acciones por vencer",
        "acciones vencen",
        "estan por vencer",
        "por cumplir su fecha",
    ]):
        return """
            SELECT TOP 100
                codigo_om,
                cliente,
                proceso,
                sponsor_nombre,
                tipo_accion,
                descripcion_accion,
                fecha_compromiso,
                dias_para_vencer,
                estado_cumplimiento_accion
            FROM vw_om_acciones_base
            WHERE estado_cumplimiento_accion = 'POR VENCER'
            ORDER BY fecha_compromiso ASC
        """, [], "predefinido_acciones"

    if any(x in pregunta_norm for x in [
        "acciones vencidas",
        "acciones vencieron",
        "estan vencidas",
        "vencidas",
    ]):
        return """
            SELECT TOP 100
                codigo_om,
                cliente,
                proceso,
                sponsor_nombre,
                tipo_accion,
                descripcion_accion,
                fecha_compromiso,
                dias_para_vencer,
                estado_cumplimiento_accion
            FROM vw_om_acciones_base
            WHERE estado_cumplimiento_accion = 'VENCIDA'
            ORDER BY fecha_compromiso ASC
        """, [], "predefinido_acciones"

    if "sin evidencia" in pregunta_norm or "no han cargado evidencia" in pregunta_norm:
        return """
            SELECT TOP 100
                codigo_om,
                cliente,
                proceso,
                sponsor_nombre,
                tipo_accion,
                descripcion_accion,
                fecha_compromiso,
                estado_cumplimiento_accion
            FROM vw_om_acciones_base
            WHERE ISNULL(requiere_evidencia, 0) = 1
              AND ISNULL(tiene_evidencia, 0) = 0
            ORDER BY fecha_compromiso ASC
        """, [], "predefinido_acciones"

    if "no han cumplido" in pregunta_norm or "no han cargado sus acciones" in pregunta_norm:
        return """
            SELECT TOP 100
                codigo_om,
                cliente,
                proceso,
                sponsor_nombre,
                tipo_accion,
                descripcion_accion,
                fecha_compromiso,
                estado_cumplimiento_accion
            FROM vw_om_acciones_base
            WHERE ISNULL(cumplido, 0) = 0
            ORDER BY fecha_compromiso ASC
        """, [], "predefinido_acciones"

    # =========================================================
    # Búsqueda genérica: "cuántas OM tiene X"
    # =========================================================
    m = re.search(r"cu[aá]ntas?\s+om\s+tiene\s+(.+)", texto, re.I)
    if m:
        termino = m.group(1).strip()
        return """
            SELECT
                ? AS busqueda,
                COUNT(DISTINCT reclamo_id) AS total_om
            FROM vw_om_reporte_base
            WHERE UPPER(ISNULL(proceso, '')) LIKE UPPER(?)
               OR UPPER(ISNULL(proceso_text, '')) LIKE UPPER(?)
               OR UPPER(ISNULL(sponsor_nombre, '')) LIKE UPPER(?)
               OR UPPER(ISNULL(sponsor_username, '')) LIKE UPPER(?)
               OR UPPER(ISNULL(imputado_nombre, '')) LIKE UPPER(?)
               OR UPPER(ISNULL(imputado_username, '')) LIKE UPPER(?)
               OR UPPER(ISNULL(creador_nombre, '')) LIKE UPPER(?)
               OR UPPER(ISNULL(creador_username, '')) LIKE UPPER(?)
               OR UPPER(ISNULL(jefe_nombre, '')) LIKE UPPER(?)
               OR UPPER(ISNULL(jefe_username, '')) LIKE UPPER(?)
               OR UPPER(ISNULL(miembros_equipo, '')) LIKE UPPER(?)
               OR UPPER(ISNULL(cliente, '')) LIKE UPPER(?)
               OR UPPER(ISNULL(cliente_nombre, '')) LIKE UPPER(?)
        """, [
            termino,
            _like_param(termino), _like_param(termino),
            _like_param(termino), _like_param(termino),
            _like_param(termino), _like_param(termino),
            _like_param(termino), _like_param(termino),
            _like_param(termino), _like_param(termino),
            _like_param(termino),
            _like_param(termino), _like_param(termino),
        ], "predefinido_vista_busqueda"

    return None



def _corregir_sql_openai(sql_fallido: str, error_msg: str, pregunta: str) -> str:
    """Pide a OpenAI que corrija un SQL que falló en ejecución."""
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    prompt = (
        f"El siguiente SQL generado para la pregunta '{pregunta}' falló con el error:\n"
        f"{error_msg}\n\n"
        f"SQL original:\n{sql_fallido}\n\n"
        f"Vistas disponibles: vw_om_reporte_base, vw_om_acciones_base.\n"
        f"Devuelve SOLO el SQL corregido como JSON: {{\"sql\":\"SELECT ...\"}}"
    )
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=400,
    )
    raw = resp.choices[0].message.content.strip()
    return json.loads(raw).get("sql", "")


def generar_sql_openai(pregunta: str, historial: list[dict] | None = None) -> str:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    prompt = f"""
Eres un asistente EXCLUSIVO para consultar datos de Oportunidades de Mejora.

OM, Oportunidad de Mejora, Oportunidades de Mejora, Reclamo y Reclamos significan lo mismo.
Si la pregunta está relacionada con cualquiera de esos términos o con clientes, procesos, sponsors,
usuarios, fechas, estados, respuestas, tiempos, equipo, acciones de control/correctivas, evidencias,
vencimientos o cumplimiento, debe considerarse válida.

Devuelve SOLO JSON válido:
{{"sql":"SELECT ..."}}

Si realmente no está relacionada, devuelve:
{{"sql":""}}

Vistas disponibles y autorizadas:
1) vw_om_reporte_base
2) vw_om_acciones_base

Columnas de vw_om_reporte_base:
reclamo_id, codigo_om, fecha_reclamo, fecha_creacion,
creador_username, creador_nombre,
tipo_om, tipo_tramite, tipo_reclamo, tipo_tramite_codigo,
proceso_text, proceso,
cliente_nombre, cliente, cliente_identificacion, cliente_contacto,
cliente_email, cliente_telefono, material_desc, ciudad,
observacion, procede, estado_global,
imputacion_id,
imputado_username, sponsor_username,
imputado_nombre, sponsor_nombre,
jefe_username, jefe_nombre,
estado_asignacion, fecha_aprobacion_asignacion,
fecha_rechazo_asignacion, motivo_rechazo_asignacion,
respuesta_causa, respuesta_preventiva, respuesta_correctiva,
fecha_causa, fecha_preventiva, fecha_correctiva,
fecha_respuesta_imputado,
dias_respuesta_sponsor, dias_sin_respuesta_sponsor,
miembros_equipo, total_miembros_equipo,
fecha_primera_asignacion_equipo, dias_promedio_asignacion_equipo,
miembros_equipo_respondieron, miembros_equipo_pendientes,
fecha_primera_respuesta_equipo, dias_promedio_respuesta_equipo,
dias_promedio_sin_respuesta_equipo, dias_max_sin_respuesta_equipo,
estado_respuesta, fecha_aprobacion_respuesta,
fecha_rechazo_respuesta, motivo_rechazo_respuesta.

Columnas esperadas de vw_om_acciones_base:
reclamo_id, codigo_om, fecha_reclamo, fecha_creacion, estado_global,
proceso, cliente, sponsor_username, sponsor_nombre,
tipo_accion, descripcion_accion, fecha_compromiso, fecha_cumplimiento,
cumplido, requiere_evidencia, tiene_evidencia,
estado_cumplimiento_accion, dias_para_vencer.

Reglas obligatorias:
- Solo SQL Server SELECT.
- No uses tablas físicas.
- No uses INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, MERGE, EXEC.
- Para conteos de OM usa COUNT(DISTINCT reclamo_id).
- Para listados usa TOP 100.
- Para preguntas de acciones, vencimientos, evidencia o cumplimiento usa vw_om_acciones_base.
- Para preguntas generales de OM usa vw_om_reporte_base.
- "cerradas" significa LOWER(estado_global) = 'cerrado'.
- "abiertas" significa LOWER(estado_global) = 'abierto'.
- "por mes" significa agrupar por FORMAT(TRY_CONVERT(date, fecha), 'yyyy-MM').
- Para creación usa fecha_creacion.
- Para fecha OM usa fecha_reclamo.
- Para cierre usa fecha_aprobacion_respuesta si existe; si no, usa fecha_respuesta_imputado.
- "últimos N días" significa fecha >= DATEADD(day, -N, CAST(GETDATE() AS date)).
- "por vencer" significa estado_cumplimiento_accion = 'POR VENCER'.
- "vencida" significa estado_cumplimiento_accion = 'VENCIDA'.
- "cumplida" significa cumplido = 1.
- Para buscar una OM específica usa codigo_om.
- Para tiempo de respuesta usa dias_respuesta_sponsor.
- Para días sin respuesta usa dias_sin_respuesta_sponsor.
- No inventes columnas.

{PREGUNTAS_GUIA}

Pregunta del usuario:
{pregunta}
"""

    # Incluye contexto conversacional para follow-ups ("¿y las cerradas?")
    contexto_historial = ""
    if historial:
        ultimos = historial[-6:]
        pares = []
        for msg in ultimos:
            rol = "Usuario" if msg["role"] == "user" else "Asistente"
            pares.append(f"{rol}: {msg['content']}")
        if pares:
            contexto_historial = (
                "\n\nContexto de la conversación previa (para interpretar follow-ups):\n"
                + "\n".join(pares)
            )

    msgs = [
        {"role": "developer", "content": "Devuelve únicamente JSON válido. No expliques."},
        {"role": "user", "content": prompt + contexto_historial},
    ]

    completion = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=msgs,
    )

    raw = completion.choices[0].message.content.strip()
    data = json.loads(raw)
    sql = (data.get("sql") or "").strip()

    if not sql:
        raise ValueError("La pregunta no está relacionada con Oportunidades de Mejora.")

    return sql


def ejecutar_sql(conn, sql, params=None):
    cur = conn.cursor()
    cur.execute(sql, params or [])
    cols = [c[0] for c in cur.description]
    data = []
    for row in cur.fetchall():
        data.append({cols[i]: row[i] for i in range(len(cols))})
    return data


def cargar_diccionario_campos(conn, modulo="om"):
    cur = conn.cursor()
    cur.execute("""
        SELECT columna, etiqueta, visible, sensible
        FROM ai_chat_campos_diccionario
        WHERE modulo = ?
          AND activo = 1
    """, (modulo,))

    dic = {}
    for r in cur.fetchall():
        dic[r["columna"].lower()] = {
            "etiqueta": r["etiqueta"],
            "visible": bool(r["visible"]),
            "sensible": bool(r["sensible"]),
        }
    return dic


def generar_respuesta_natural(
    pregunta: str,
    data: list[dict],
    historial: list[dict] | None = None,
) -> str:
    """
    Usa OpenAI para convertir los resultados SQL en una respuesta
    conversacional en lenguaje natural.
    """
    if not data:
        return "No encontré resultados para esa consulta. Intenta reformular la pregunta."

    # Casos simples sin IA
    if len(data) == 1 and len(data[0]) == 1:
        key, val = next(iter(data[0].items()))
        if "total" in key.lower():
            return f"Hay **{val}** oportunidad(es) de mejora que coinciden con tu consulta."

    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        muestra = data[:20]
        total_registros = len(data)

        msgs: list[dict] = [
            {
                "role": "system",
                "content": (
                    "Eres el asistente de Oportunidades de Mejora (OM) de QUIMPAC Ecuador. "
                    "Responde siempre en español, de forma clara, concisa y profesional. "
                    "Usa **negrita** para valores numéricos importantes. "
                    "Cuando sean listados, preséntalo de forma ordenada y legible. "
                    "Máximo 200 palabras. "
                    "No menciones SQL, vistas, columnas internas ni términos técnicos de base de datos."
                ),
            }
        ]

        # Contexto conversacional (últimos 4 turnos)
        for msg in (historial or [])[-8:]:
            msgs.append({"role": msg["role"], "content": msg["content"]})

        aviso_total = (
            f"\n(Mostrando {len(muestra)} de {total_registros} registros en total)"
            if total_registros > len(muestra)
            else ""
        )

        msgs.append({
            "role": "user",
            "content": (
                f"Pregunta: {pregunta}\n\n"
                f"Datos obtenidos:{aviso_total}\n"
                f"{json.dumps(muestra, ensure_ascii=False, default=str)}"
            ),
        })

        completion = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=msgs,
            max_tokens=400,
            temperature=0.2,
        )

        return completion.choices[0].message.content.strip()

    except Exception as exc:
        log.error("[om_chat] generar_respuesta_natural error: %s", exc)
        # Fallback al formato básico
        return _respuesta_fallback(data)


def _respuesta_fallback(data: list[dict]) -> str:
    """Respuesta simple cuando OpenAI no está disponible."""
    if not data:
        return "Sin resultados."
    if len(data) == 1:
        row = data[0]
        if "total_om" in row:
            return f"Total: {row['total_om']} OM."
        partes = [f"{k}: {v}" for k, v in row.items() if v is not None]
        return " | ".join(partes)
    filas = []
    for row in data[:10]:
        partes = [f"{v}" for v in row.values() if v is not None]
        filas.append(" | ".join(partes))
    return f"{len(data)} resultado(s):\n" + "\n".join(filas)


def responder_simple(conn, pregunta: str, data: list[dict], modulo="om"):
    if not data:
        return "No encontré resultados para esa consulta."

    if len(data) == 1:
        row = data[0]
        if "total_om" in row:
            return f"Resultado: {row.get('total_om', 0)} OM."
        if "total" in row:
            return f"Resultado: {row.get('total', 0)}."

    dic = cargar_diccionario_campos(conn, modulo)
    filas = []

    for row in data[:10]:
        partes = []
        for k, v in row.items():
            k_norm = k.lower()
            cfg = dic.get(k_norm)
            if cfg:
                if not cfg["visible"] or cfg["sensible"]:
                    continue
                etiqueta = cfg["etiqueta"]
            else:
                if k_norm.endswith("_id") or k_norm == "id":
                    continue
                etiqueta = k.replace("_", " ").capitalize()

            partes.append(f"{etiqueta}: {v if v is not None else '—'}")

        if partes:
            filas.append(" | ".join(partes))

    if not filas:
        return f"Encontré {len(data)} resultado(s), pero no hay campos visibles para mostrar."

    return "Estos son los principales resultados:\n" + "\n".join(filas)


def buscar_sponsor_proceso(conn, pregunta_original: str) -> dict | None:
    """
    Detecta preguntas sobre sponsor de un proceso/área y consulta param_values.
    Maneja relación padre (proceso) → hijos (PRINCIPAL/BACKUP con username/cedula).
    """
    texto = (pregunta_original or "").strip()
    # Detectar patrón: "quien es el sponsor de X" / "sponsor de X" / "sponsors de X"
    m = re.search(
        r"(?:quien\s+es\s+(?:el\s+)?sponsor|sponsors?\s+de|responsable\s+de)\s+"
        r"(?:el\s+area\s+de\s+|el\s+proceso\s+de\s+|el\s+departamento\s+de\s+|la\s+area\s+de\s+|de\s+la\s+area\s+|de\s+)?(.+)",
        texto, re.I
    )
    if not m:
        return None

    # Limpiar "de " inicial que puede quedar en el grupo
    proceso_buscado = m.group(1).strip().rstrip("?")
    proceso_buscado = re.sub(r"^de\s+", "", proceso_buscado, flags=re.I).strip().upper()

    cur = conn.cursor()

    # 1. Buscar el proceso en RECL_PROCESO (aquí viven los procesos raíz)
    cur.execute("""
        SELECT TOP 1 pv.id, pv.nombre, pv.valor
        FROM param_values pv
        JOIN param_groups pg ON pg.id = pv.group_id
        WHERE pg.nombre = 'RECL_PROCESO'
          AND COALESCE(pv.activo, 1) = 1
          AND pv.parent_id IS NULL
          AND (UPPER(LTRIM(RTRIM(pv.nombre))) LIKE UPPER(?)
            OR UPPER(LTRIM(RTRIM(pv.valor)))  LIKE UPPER(?))
        ORDER BY COALESCE(pv.orden, 0), pv.nombre
    """, (f"%{proceso_buscado}%", f"%{proceso_buscado}%"))
    proceso_row = cur.fetchone()
    if not proceso_row:
        return {"encontrado": False, "proceso": proceso_buscado}

    proceso_id   = proceso_row["id"]
    proceso_name = proceso_row["valor"] or proceso_row["nombre"]

    # 2. Buscar sponsors PRINCIPAL/BACKUP en RECL_PROCESO_SPONSOR con parent_id = proceso_id
    cur.execute("""
        SELECT
            pv.nombre    AS identificacion,
            UPPER(LTRIM(RTRIM(COALESCE(pv.valor, '')))) AS tipo,
            u.nombre_completo,
            u.username,
            u.email
        FROM param_values pv
        JOIN param_groups pg ON pg.id = pv.group_id
        LEFT JOIN usuarios u
               ON LTRIM(RTRIM(u.identificacion)) = LTRIM(RTRIM(pv.nombre))
        WHERE pg.nombre = 'RECL_PROCESO_SPONSOR'
          AND COALESCE(pv.activo, 1) = 1
          AND pv.parent_id = ?
          AND UPPER(LTRIM(RTRIM(COALESCE(pv.valor, '')))) IN ('PRINCIPAL', 'BACKUP')
        ORDER BY
          CASE UPPER(LTRIM(RTRIM(COALESCE(pv.valor, ''))))
            WHEN 'PRINCIPAL' THEN 1
            WHEN 'BACKUP'    THEN 2
            ELSE 9
          END,
          COALESCE(pv.orden, 0), pv.id
    """, (proceso_id,))
    sponsors = cur.fetchall()

    resultado = {
        "encontrado": True,
        "proceso": proceso_name,
        "sponsors": [],
    }
    for s in sponsors:
        nombre = s["nombre_completo"] or s["username"] or s["identificacion"]
        resultado["sponsors"].append({
            "tipo": s["tipo"],
            "nombre": nombre,
            "email": s["email"] or "",
        })
    return resultado


def formatear_respuesta_sponsor(resultado: dict) -> str:
    if not resultado or not resultado.get("encontrado"):
        proc = (resultado or {}).get("proceso", "ese proceso")
        return f"No encontré configuración de sponsor para el proceso **{proc}**. Verifica que esté registrado en los parámetros RECL_PROCESO_SPONSOR."

    proceso = resultado["proceso"]
    sponsors = resultado.get("sponsors", [])

    if not sponsors:
        return f"El proceso **{proceso}** existe pero no tiene sponsors configurados."

    lineas = [f"Sponsors configurados para el proceso **{proceso}**:\n"]
    for s in sponsors:
        tipo  = s["tipo"].upper()
        nombre = s["nombre"]
        email  = f" ({s['email']})" if s["email"] else ""
        lineas.append(f"- **{tipo}:** {nombre}{email}")

    return "\n".join(lineas)


PREGUNTAS_CONCEPTUALES = [
    "que es una om", "que es om", "que son las om", "que son om",
    "que es una oportunidad de mejora", "que son las oportunidades de mejora",
    "para que sirve una om", "como funciona una om", "como funciona el modulo",
    "que hace este modulo", "como se usa el asistente", "que puedes hacer",
    "que puedo preguntar", "que tipos de consultas puedo hacer",
    "como se crea una om", "quien crea una om", "quien aprueba una om",
    "que estados tiene una om", "cuales son los estados de una om",
    "que es un sponsor", "quien es el sponsor", "que hace el sponsor",
    "que es una accion de control", "que es una accion correctiva",
    "que es la trazabilidad", "que es el flujo de una om",
    "ayuda", "help", "como te uso", "instrucciones",
]


def es_pregunta_conceptual(pregunta_norm: str) -> bool:
    """Detecta preguntas definicionales que no requieren SQL."""
    for patron in PREGUNTAS_CONCEPTUALES:
        if patron in pregunta_norm:
            return True
    # Patrones adicionales
    inicio = ["que es", "que son", "como funciona", "para que sirve",
              "como se", "quien es", "quien crea", "quien aprueba",
              "que hace", "cuales son los", "que tipos"]
    return any(pregunta_norm.startswith(p) for p in inicio)


def responder_conceptual(pregunta: str, historial: list[dict] | None = None) -> str:
    """Responde preguntas conceptuales sobre el módulo OM usando OpenAI en modo chat."""
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        msgs = [
            {
                "role": "system",
                "content": (
                    "Eres el asistente del módulo de Oportunidades de Mejora (OM) de QUIMPAC Ecuador. "
                    "Una OM (Oportunidad de Mejora) es un registro formal de un reclamo, queja o incidencia "
                    "de cliente que requiere análisis de causa, respuesta técnica y acciones correctivas/de control. "
                    "El flujo típico es: creación → asignación de sponsor → formación de equipo → "
                    "análisis → respuesta → aprobación → cierre. "
                    "Los estados son: Abierto, Cerrado. "
                    "El sponsor es el responsable principal de gestionar la OM. "
                    "Las acciones de control son inmediatas; las correctivas atacan la causa raíz. "
                    "Responde en español, de forma clara y concisa (máximo 150 palabras). "
                    "No menciones SQL ni términos técnicos."
                ),
            }
        ]
        for msg in (historial or [])[-6:]:
            msgs.append({"role": msg["role"], "content": msg["content"]})
        msgs.append({"role": "user", "content": pregunta})

        completion = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=msgs,
            max_tokens=300,
            temperature=0.3,
        )
        return completion.choices[0].message.content.strip()
    except Exception as exc:
        log.error("[om_chat] responder_conceptual error: %s", exc)
        return (
            "Una **OM (Oportunidad de Mejora)** es un registro formal de un reclamo o incidencia de cliente "
            "que requiere análisis, respuesta técnica y acciones correctivas. "
            "Puedes preguntarme: cuántas OM hay abiertas, OM por proceso, acciones por vencer, "
            "tiempo de respuesta por sponsor, entre otros."
        )


def om_chat_responder(
    pregunta: str,
    user_id: int | None,
    historial: list[dict] | None = None,
):
    conn = get_db()
    pregunta_norm = normalizar_pregunta(pregunta)
    historial = historial or []
    sql = None
    params = []
    source = "desconocido"

    try:
        # 0a. Consulta de sponsor por proceso (param_values, relación padre-hijo)
        # Va ANTES que el check conceptual porque "quien es el sponsor" está en ambos
        resultado_sponsor = buscar_sponsor_proceso(conn, pregunta)
        if resultado_sponsor is not None:
            respuesta = formatear_respuesta_sponsor(resultado_sponsor)
            return {
                "ok": True,
                "source": "sponsor_params",
                "rows": resultado_sponsor.get("sponsors", []),
                "respuesta": respuesta,
            }

        # 0b. Preguntas conceptuales/definicionales (sin SQL)
        if es_pregunta_conceptual(pregunta_norm):
            respuesta = responder_conceptual(pregunta, historial)
            return {
                "ok": True,
                "source": "conceptual",
                "rows": [],
                "respuesta": respuesta,
            }

        if not pregunta_permitida_modulo(conn, pregunta_norm, "om"):
            return {
                "ok": False,
                "error": "Solo puedo responder preguntas relacionadas con Oportunidades de Mejora.",
            }

        # 1. SQL predefinido (rápido, sin IA)
        pre = sql_predefinido_vista(pregunta_norm, pregunta, user_id)
        if pre:
            sql, params, source = pre

        # 2. Caché de consultas previas
        if not sql:
            cache = buscar_cache(conn, pregunta_norm)
            if cache:
                try:
                    sql_cache = validar_sql_solo_select(
                        normalizar_sql_server(cache["sql_generado"])
                    )
                    sql = sql_cache
                    params = []
                    marcar_uso_cache(conn, cache["id"])
                    source = "cache"
                except Exception:
                    sql = None

        # 3. OpenAI genera SQL con contexto de historial
        if not sql:
            try:
                sql_raw = generar_sql_openai(pregunta, historial)
            except ValueError:
                # OpenAI indicó que la pregunta no es de datos → responder conceptualmente
                respuesta = responder_conceptual(pregunta, historial)
                return {
                    "ok": True,
                    "source": "conceptual_fallback",
                    "rows": [],
                    "respuesta": respuesta,
                }
            sql = normalizar_sql_server(sql_raw)
            sql = validar_sql_solo_select(sql)
            guardar_cache(conn, pregunta_norm, pregunta, sql, user_id)
            sugerir_regla(conn, "om", pregunta_norm)
            source = "openai"

        sql = normalizar_sql_server(sql)
        sql = validar_sql_solo_select(sql)

        data = ejecutar_sql(conn, sql, params)

        # 4. Respuesta en lenguaje natural (con contexto de historial)
        respuesta = generar_respuesta_natural(pregunta, data, historial)

        return {
            "ok": True,
            "source": source,
            "rows": data[:50],
            "respuesta": respuesta,
        }

    except pyodbc.ProgrammingError as exc:
        # Reintento: pide a OpenAI corregir el SQL con el error específico
        log.warning("[om_chat] SQL falló, intentando corrección. SQL=%s err=%s", sql, exc)
        try:
            sql_corregido = _corregir_sql_openai(sql or "", str(exc), pregunta)
            sql_corregido = normalizar_sql_server(sql_corregido)
            sql_corregido = validar_sql_solo_select(sql_corregido)
            data = ejecutar_sql(conn, sql_corregido, [])
            respuesta = generar_respuesta_natural(pregunta, data, historial)
            return {
                "ok": True,
                "source": "openai_retry",
                "rows": data[:50],
                "respuesta": respuesta,
            }
        except Exception:
            return {
                "ok": True,
                "source": source,
                "rows": [],
                "respuesta": (
                    "No pude obtener los datos para esa consulta. "
                    "Intenta ser más específico, por ejemplo indicando el código de OM o el nombre exacto del proceso."
                ),
            }

    except Exception:
        log.exception("[om_chat] Error general")
        return {
            "ok": True,
            "source": source,
            "rows": [],
            "respuesta": "No pude procesar la consulta en este momento. Intenta de nuevo.",
        }

    finally:
        try:
            conn.close()
        except Exception:
            pass
