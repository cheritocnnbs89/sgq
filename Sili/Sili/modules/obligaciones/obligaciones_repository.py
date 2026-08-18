# -*- coding: utf-8 -*-

from modules.db import get_db
from modules.users.user_queries import SQL_SELECT_AREAS_ACTIVAS
from . import obligaciones_queries as q
from .obligaciones_constants import (
    ROL_ADMIN_SILI, ROL_ADMIN_OBLIG, ROL_JEFE_AREA, ROL_GERENTE_OBLIG, ESTATUS_TERMINALES,
)


def get_connection():
    return get_db()


def rollback():
    get_db().rollback()


def _rows_to_dicts(cur):
    """Convierte filas a dicts puros -- usar para jsonify o comparaciones.
    cur.fetchall() ya devuelve RowCompat (dict-like) via ConnectionCompat/CursorCompat
    (modules/db.py) -- no re-zippear con las columnas, eso itera las keys y pisa los valores."""
    return [dict(row) for row in cur.fetchall()]


# ------------------------------------------------------------
# Visibilidad por rol -- usado por Consultas / Historial / Dashboard
# ------------------------------------------------------------
def _apply_visibility(where, params, rol, user_id):
    """Agrega la clausula de visibilidad segun el rol a las listas where/params (in-place)."""
    if rol in (ROL_ADMIN_SILI, ROL_ADMIN_OBLIG):
        return
    if rol == ROL_JEFE_AREA:
        where.append(
            "o.usuario_id IN (SELECT id FROM usuarios WHERE jefe_id = ?)"
        )
        params.append(user_id)
        return
    if rol == ROL_GERENTE_OBLIG:
        # 2026-08-14: "jefe del jefe" -- alcance = subordinados directos del gerente
        # (los jefes que le reportan) MAS los subordinados de esos jefes (2 saltos).
        # NO es resolver_cadena_jefe() (esa resuelve jefe/gerente DE un usuario dado,
        # direccion contraria) -- este es el JOIN inverso, subordinados de un gerente.
        where.append(
            "o.usuario_id IN ("
            "SELECT id FROM usuarios WHERE jefe_id = ? "
            "OR jefe_id IN (SELECT id FROM usuarios WHERE jefe_id = ?)"
            ")"
        )
        params.append(user_id)
        params.append(user_id)
        return
    # usuario_obligaciones (o cualquier otro rol no reconocido) -> solo lo propio
    where.append("o.usuario_id = ?")
    params.append(user_id)


# ------------------------------------------------------------
# Perfil de usuario
# ------------------------------------------------------------
def get_usuario_perfil(usuario_id):
    conn = get_connection()
    cur = conn.cursor()
    return cur.execute(q.SQL_GET_USUARIO_PERFIL, (usuario_id,)).fetchone()


def get_usuario_by_username(username):
    conn = get_connection()
    cur = conn.cursor()
    return cur.execute(q.SQL_GET_USUARIO_BY_USERNAME, (username,)).fetchone()


def list_usuarios_combo():
    conn = get_connection()
    return conn.execute(q.SQL_LIST_USUARIOS_COMBO).fetchall()


def list_subordinados(jefe_id):
    """Mejora (Correccion #5): subordinados directos de un jefe_area_obligaciones
    -- usado para poblar el filtro 'Usuario' en Consultas, acotado a su propio
    equipo (no la lista completa de usuarios que ve admin)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(q.SQL_GET_USUARIOS_A_CARGO, (jefe_id,))
    return _rows_to_dicts(cur)


def list_subordinados_2niveles(gerente_id):
    """2026-08-14: gerente_obligaciones -- mismo proposito que list_subordinados()
    pero 2 saltos de jefe_id (ver _apply_visibility)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(q.SQL_GET_USUARIOS_A_CARGO_2NIVELES, (gerente_id, gerente_id))
    return _rows_to_dicts(cur)


# ------------------------------------------------------------
# Tipos y Entidades Reguladoras -- CRUD propio (2026-08-07, Correccion de
# arquitectura #8) -- tablas oblig_tipos_obligacion / oblig_entidades_
# reguladoras, mismo patron que Frecuencias.
# ------------------------------------------------------------
def list_tipos():
    conn = get_connection()
    return conn.execute(q.SQL_LIST_TIPOS_ACTIVOS).fetchall()


def list_tipos_todos():
    conn = get_connection()
    return conn.execute(q.SQL_LIST_TIPOS_TODOS).fetchall()


def get_tipo_by_id(tipo_id):
    conn = get_connection()
    cur = conn.cursor()
    return cur.execute(q.SQL_GET_TIPO_BY_ID, (tipo_id,)).fetchone()


def create_tipo(nombre, orden):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(q.SQL_INSERT_TIPO, (nombre, orden))
    row = cur.fetchone()  # OUTPUT INSERTED.id en el mismo INSERT
    conn.commit()
    return row[0] if row else None


def update_tipo(tipo_id, nombre, orden):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(q.SQL_UPDATE_TIPO, (nombre, orden, tipo_id))
    conn.commit()


def toggle_tipo_activo(tipo_id, activo):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(q.SQL_TOGGLE_TIPO_ACTIVO, (1 if activo else 0, tipo_id))
    conn.commit()


def list_entidades():
    conn = get_connection()
    return conn.execute(q.SQL_LIST_ENTIDADES_ACTIVAS).fetchall()


def list_entidades_todas():
    conn = get_connection()
    return conn.execute(q.SQL_LIST_ENTIDADES_TODAS).fetchall()


def get_entidad_by_id(entidad_id):
    conn = get_connection()
    cur = conn.cursor()
    return cur.execute(q.SQL_GET_ENTIDAD_BY_ID, (entidad_id,)).fetchone()


def create_entidad(nombre, orden):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(q.SQL_INSERT_ENTIDAD, (nombre, orden))
    row = cur.fetchone()  # OUTPUT INSERTED.id en el mismo INSERT
    conn.commit()
    return row[0] if row else None


def update_entidad(entidad_id, nombre, orden):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(q.SQL_UPDATE_ENTIDAD, (nombre, orden, entidad_id))
    conn.commit()


def toggle_entidad_activo(entidad_id, activo):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(q.SQL_TOGGLE_ENTIDAD_ACTIVO, (1 if activo else 0, entidad_id))
    conn.commit()


def list_entidades_por_tipo(tipo_id):
    """2026-07-27: Entidades acotadas a un Tipo via oblig_tipo_entidad
    (muchos a muchos) -- usado por el filtro dependiente del formulario y
    del dashboard/consultas."""
    conn = get_connection()
    return conn.execute(q.SQL_LIST_ENTIDADES_POR_TIPO, (tipo_id,)).fetchall()


def list_entidad_ids_por_tipo(tipo_id):
    """2026-08-11: ids de entidad vinculados a un Tipo -- usado para
    premarcar los checkboxes en el form de edicion de Tipo."""
    conn = get_connection()
    rows = conn.execute(q.SQL_LIST_ENTIDAD_IDS_POR_TIPO, (tipo_id,)).fetchall()
    return [r[0] for r in rows]


def set_entidades_de_tipo(tipo_id, entidad_ids):
    """2026-08-11: regraba TODOS los vinculos de un Tipo en una sola
    transaccion (delete + insert) -- nunca deja huecos a mitad de camino
    si falla la mitad de los inserts."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(q.SQL_DELETE_TIPO_ENTIDAD_BY_TIPO, (tipo_id,))
        for entidad_id in entidad_ids:
            cur.execute(q.SQL_INSERT_TIPO_ENTIDAD, (tipo_id, entidad_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise




def list_empresas_con_obligaciones():
    """2026-07-21: solo empresas con al menos una obligacion -- combo Empresa
    de los filtros de Consultas e Historial (antes traia TODO el catalogo)."""
    conn = get_connection()
    return conn.execute(q.SQL_LIST_EMPRESAS_CON_OBLIGACIONES).fetchall()


# ------------------------------------------------------------
# Frecuencias -- tabla propia oblig_frecuencias (2026-07-15, Corrección #3)
# ------------------------------------------------------------
def list_frecuencias():
    conn = get_connection()
    return conn.execute(q.SQL_LIST_FRECUENCIAS_ACTIVAS).fetchall()


def get_frecuencia_by_id(frecuencia_id):
    conn = get_connection()
    cur = conn.cursor()
    return cur.execute(q.SQL_GET_FRECUENCIA_BY_ID, (frecuencia_id,)).fetchone()


def soft_delete_frecuencia(frecuencia_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(q.SQL_SOFT_DELETE_FRECUENCIA, (frecuencia_id,))
    conn.commit()


# ------------------------------------------------------------
# Notificaciones y destinatarios de una frecuencia
# ------------------------------------------------------------
def replace_frecuencia_completa(frecuencia_id, nombre, recalculo_tipo, recalculo_cantidad, notificaciones):
    """Guarda frecuencia + sus notificaciones + destinatarios en una sola
    transacción -- reemplaza siempre el set completo de notificaciones
    (borra las anteriores e inserta las nuevas) en vez de diffear fila por
    fila. `notificaciones` es una lista de dicts:
    {orden, tipo_trigger, dias_antes, dia_fijo_mes, destinatarios: [usuario_id, ...]}.
    ponytail: replace-on-save -- máximo 5 filas por frecuencia, no vale la
    pena un diff incremental; subir a diff solo si esto se vuelve lento."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        if frecuencia_id:
            cur.execute(q.SQL_UPDATE_FRECUENCIA, (nombre, recalculo_tipo, recalculo_cantidad, frecuencia_id))
        else:
            cur.execute(q.SQL_INSERT_FRECUENCIA, (nombre, recalculo_tipo, recalculo_cantidad))
            frecuencia_id = cur.fetchone()[0]  # OUTPUT INSERTED.id -- SCOPE_IDENTITY() en execute() separado devuelve NULL en este entorno

        cur.execute(q.SQL_DELETE_DESTINATARIOS_POR_FRECUENCIA, (frecuencia_id,))
        cur.execute(q.SQL_DELETE_NOTIFICACIONES_POR_FRECUENCIA, (frecuencia_id,))

        for notif in notificaciones:
            cur.execute(q.SQL_INSERT_NOTIFICACION, (
                frecuencia_id,
                notif["orden"],
                notif["tipo_trigger"],
                notif.get("dias_antes"),
                notif.get("dia_fijo_mes"),
            ))
            notificacion_id = cur.fetchone()[0]  # OUTPUT INSERTED.id
            # 2026-07-22: cada destinatario es un dict {tipo, usuario_id}. Los
            # jerárquicos (creador/jefe/gerente) guardan usuario_id NULL.
            for dest in notif.get("destinatarios") or []:
                cur.execute(q.SQL_INSERT_DESTINATARIO, (
                    notificacion_id, dest.get("usuario_id"), dest.get("tipo", "fijo"),
                ))

        conn.commit()
        return frecuencia_id
    except Exception:
        conn.rollback()
        raise


def list_notificaciones_con_destinatarios(frecuencia_id):
    """Usado por: (1) la pantalla de edición, para prellenar los bloques de
    notificación con sus destinatarios ya elegidos; (2) el scheduler
    (Tarea B), para saber a qué usuario_email enviar cada alerta."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(q.SQL_LIST_NOTIFICACIONES_CON_DESTINATARIOS_POR_FRECUENCIA, (frecuencia_id,))
    filas = _rows_to_dicts(cur)

    notificaciones = {}
    for fila in filas:
        nid = fila["notificacion_id"]
        if nid not in notificaciones:
            notificaciones[nid] = {
                "id": nid,
                "orden": fila["orden"],
                "tipo_trigger": fila["tipo_trigger"],
                "dias_antes": fila["dias_antes"],
                "dia_fijo_mes": fila["dia_fijo_mes"],
                "destinatarios": [],
            }
        # 2026-07-22: incluye destinatarios jerárquicos (usuario_id NULL pero
        # con tipo_destinatario). Se distinguen por 'tipo'.
        if fila.get("tipo_destinatario"):
            notificaciones[nid]["destinatarios"].append({
                "tipo": fila["tipo_destinatario"],
                "usuario_id": fila.get("usuario_id"),
                "email": fila.get("usuario_email"),
            })

    return sorted(notificaciones.values(), key=lambda n: n["orden"])


def list_admin_obligaciones_emails():
    """2026-07-22: emails de los admin_obligaciones -- copia del aviso de
    cadena de jefe rota al crear/editar una obligación."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(q.SQL_LIST_ADMIN_OBLIGACIONES_EMAILS)
    return [r[0] for r in cur.fetchall() if r[0]]


# ------------------------------------------------------------
# 2026-08-14: Punto 8 -- solicitud de autorizacion para editar obligacion cumplida
# ------------------------------------------------------------
def get_solicitud_pendiente(obligacion_id):
    conn = get_connection()
    cur = conn.cursor()
    return cur.execute(q.SQL_GET_SOLICITUD_PENDIENTE_BY_OBLIGACION, (obligacion_id,)).fetchone()


def crear_solicitud_edicion(obligacion_id, solicitante_id, motivo):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(q.SQL_INSERT_SOLICITUD_EDICION, (obligacion_id, solicitante_id, motivo))
        row = cur.fetchone()
        conn.commit()
        return row[0] if row else None
    except Exception:
        conn.rollback()
        raise


def get_solicitud_by_id(solicitud_id):
    conn = get_connection()
    cur = conn.cursor()
    return cur.execute(q.SQL_GET_SOLICITUD_BY_ID, (solicitud_id,)).fetchone()


def list_solicitudes_pendientes():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(q.SQL_LIST_SOLICITUDES_PENDIENTES)
    return _rows_to_dicts(cur)


def resolver_solicitud(solicitud_id, estado, resuelto_por):
    """estado: 'aprobada' o 'rechazada'. Si aprobada, habilita edicion en la
    obligacion (1 sola vez -- se re-bloquea sola al guardar, ver
    deshabilitar_edicion_obligacion() llamado desde update())."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(q.SQL_RESOLVER_SOLICITUD, (estado, resuelto_por, solicitud_id))
        filas = cur.rowcount
        if filas and estado == "aprobada":
            solicitud = get_solicitud_by_id(solicitud_id)
            if solicitud:
                cur.execute(q.SQL_HABILITAR_EDICION_OBLIGACION, (solicitud["obligacion_id"],))
        conn.commit()
        return bool(filas)
    except Exception:
        conn.rollback()
        raise


def deshabilitar_edicion_obligacion(obligacion_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(q.SQL_DESHABILITAR_EDICION_OBLIGACION, (obligacion_id,))


def list_admin_y_admin_obligaciones_emails():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(q.SQL_LIST_ADMIN_Y_ADMIN_OBLIGACIONES_EMAILS)
    return [r[0] for r in cur.fetchall() if r[0]]


def resolver_cadena_jefe(usuario_id):
    """2026-07-22: dado un usuario, devuelve la cadena jerárquica resuelta en
    tiempo real: {jefe_id, jefe_email, gerente_id, gerente_email}. Un eslabón
    faltante queda en None. 'gerente' = jefe del jefe (dos saltos de jefe_id)."""
    out = {"jefe_id": None, "jefe_email": None, "gerente_id": None, "gerente_email": None}
    if not usuario_id:
        return out
    perfil = get_usuario_perfil(usuario_id)
    jefe_id = perfil["jefe_id"] if perfil else None
    if not jefe_id:
        return out
    jefe = get_usuario_perfil(jefe_id)
    if not jefe:
        return out
    out["jefe_id"] = jefe_id
    out["jefe_email"] = jefe["email"]
    gerente_id = jefe["jefe_id"]
    if not gerente_id:
        return out
    gerente = get_usuario_perfil(gerente_id)
    if gerente:
        out["gerente_id"] = gerente_id
        out["gerente_email"] = gerente["email"]
    return out


# ------------------------------------------------------------
# Combos para formularios
# ------------------------------------------------------------
def list_areas():
    # 2026-08-14: reusa la query ya existente de modules/users (tabla areas es de ese módulo,
    # no se duplica aquí) -- filtro por Área pedido en reunión.
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(SQL_SELECT_AREAS_ACTIVAS)
    return _rows_to_dicts(cur)


def get_combos():
    # 2026-07-15: frecuencias viene de oblig_frecuencias (tabla propia), no de param_values
    # 2026-07-21: empresas del combo de FILTROS (Consultas + Historial + Dashboard) =
    # solo las que tienen obligaciones. El FORMULARIO usa get_combos_form() (todas
    # las empresas activas) -- ver 2026-07-22 en HISTORIAL-CORRECCIONES.
    return {
        "tipos": list_tipos(),
        "frecuencias": list_frecuencias(),
        "empresas": list_empresas_con_obligaciones(),
        "entidades": list_entidades(),
        "areas": list_areas(),
    }


def get_combos_form():
    # 2026-07-22: combo Empresa del formulario Nueva/Editar = TODAS las empresas
    # activas (no solo las que ya tienen obligaciones) -- si no, no se puede crear
    # la primera obligacion de una empresa nueva. Import local para no acoplar este
    # modulo a empresas en tiempo de import.
    from modules.empresas import empresas_repository as empresas_repo
    return {
        "tipos": list_tipos(),
        "frecuencias": list_frecuencias(),
        "empresas": empresas_repo.list_empresas({"q": "", "activo": "1"}),
        "entidades": list_entidades(),
    }


# 2026-07-29: reemplaza _apply_month_filter (año+mes) -- ahora Consultas e
# Historial usan rango de fechas libre (desde/hasta), igual que el Dashboard
# (_dashboard_common_where ya lo hacia asi, ver mismo patron abajo).
def _apply_date_range_filter(where, params, desde, hasta):
    if desde:
        where.append("o.fecha_vencimiento >= ?")
        params.append(desde)
    if hasta:
        where.append("o.fecha_vencimiento <= ?")
        params.append(hasta)


# ------------------------------------------------------------
# Consultas (activa = 1)
# ------------------------------------------------------------
def list_obligaciones(user_id, rol, filters):
    conn = get_connection()
    params = []
    where = ["o.activa = 1"]

    _apply_visibility(where, params, rol, user_id)

    if filters.get("tipo_id"):
        where.append("o.tipo_id = ?")
        params.append(filters["tipo_id"])
    if filters.get("empresa_id"):
        where.append("o.empresa_id = ?")
        params.append(filters["empresa_id"])
    if filters.get("entidad_id"):
        where.append("o.entidad_id = ?")
        params.append(filters["entidad_id"])
    if filters.get("frecuencia_id"):
        where.append("o.frecuencia_id = ?")
        params.append(filters["frecuencia_id"])
    if filters.get("area_id"):
        # 2026-08-14: filtro por Área (pedido en reunión) -- o.departamento_id no guarda
        # area_id directo, se resuelve vía subquery a departamentos.
        where.append("o.departamento_id IN (SELECT id FROM departamentos WHERE area_id = ?)")
        params.append(filters["area_id"])
    if filters.get("seccion") and filters["seccion"] in SECCION_PASTEL_WHERE:
        # 2026-08-14: Punto 6 -- navegación desde el modal del pastel (Punto 5), mismo
        # criterio que dashboard_desglose_seccion() para que los conteos cuadren exacto.
        where.append(SECCION_PASTEL_WHERE[filters["seccion"]])
    _apply_date_range_filter(where, params, filters.get("fecha_desde"), filters.get("fecha_hasta"))
    # Mejora (Correccion #5): jefe_area_obligaciones tambien puede filtrar por
    # usuario -- seguro sin validacion aparte porque _apply_visibility() ya
    # acoto el WHERE a "o.usuario_id IN (subordinados)"; este AND adicional
    # solo puede angostar ese conjunto, nunca ampliarlo a otro jefe/area.
    if filters.get("usuario_id") and rol in (ROL_ADMIN_SILI, ROL_ADMIN_OBLIG, ROL_JEFE_AREA, ROL_GERENTE_OBLIG):
        where.append("o.usuario_id = ?")
        params.append(filters["usuario_id"])
    if filters.get("estatus"):
        where.append("o.estatus = ?")
        params.append(filters["estatus"])

    sql = (
        q.SQL_SELECT_JOIN_BASE + " WHERE " + " AND ".join(where) +
        " ORDER BY CASE WHEN o.estatus = 'atrasado' THEN 0 ELSE 1 END, o.fecha_vencimiento ASC"
    )
    return conn.execute(sql, params).fetchall()


def get_by_id(oblig_id):
    conn = get_connection()
    cur = conn.cursor()
    return cur.execute(q.SQL_GET_OBLIGACION_BY_ID, (oblig_id,)).fetchone()


def get_raw_by_id(oblig_id):
    conn = get_connection()
    cur = conn.cursor()
    return cur.execute(q.SQL_GET_OBLIGACION_RAW_BY_ID, (oblig_id,)).fetchone()


def insert(data):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(q.SQL_INSERT_OBLIGACION, (
            data["tipo_id"],
            data["empresa_id"],
            data["descripcion"],
            data["entidad_id"],
            data["departamento_id"],
            data["puesto_id"],
            data["usuario_id"],
            data["fecha_vencimiento"],
            data["frecuencia_id"],
            data.get("estatus", "por_presentar"),
            data["creado_por"],
        ))
        row = cur.fetchone()  # OUTPUT INSERTED.id en el mismo INSERT -- SCOPE_IDENTITY() en execute() separado devuelve NULL en este entorno
        conn.commit()
        return row[0] if row else None
    except Exception:
        conn.rollback()
        raise


def insert_no_commit(data):
    """Igual que insert() pero SIN commit -- para carga masiva en lote
    (el llamador hace un unico commit/rollback al final para atomicidad total)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(q.SQL_INSERT_OBLIGACION, (
        data["tipo_id"],
        data["empresa_id"],
        data["descripcion"],
        data["entidad_id"],
        data["departamento_id"],
        data["puesto_id"],
        data["usuario_id"],
        data["fecha_vencimiento"],
        data["frecuencia_id"],
        data.get("estatus", "por_presentar"),
        data["creado_por"],
    ))


def update(oblig_id, data):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(q.SQL_UPDATE_OBLIGACION, (
            data["tipo_id"],
            data["empresa_id"],
            data["descripcion"],
            data["entidad_id"],
            data["fecha_vencimiento"],
            data["frecuencia_id"],
            oblig_id,
        ))
        # 2026-08-14: Punto 8 -- re-bloquea edicion tras guardar (autorizacion es
        # de 1 solo uso). No-op para obligaciones que ya estaban en 0.
        cur.execute(q.SQL_DESHABILITAR_EDICION_OBLIGACION, (oblig_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def count_historial_rows(oblig_id):
    conn = get_connection()
    cur = conn.cursor()
    row = cur.execute(q.SQL_COUNT_HISTORIAL_BY_OBLIGACION, (oblig_id,)).fetchone()
    return int(row[0]) if row else 0


def count_alertas_rows(oblig_id):
    conn = get_connection()
    cur = conn.cursor()
    row = cur.execute(q.SQL_COUNT_ALERTAS_BY_OBLIGACION, (oblig_id,)).fetchone()
    return int(row[0]) if row else 0


def soft_delete(oblig_id):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(q.SQL_SOFT_DELETE_OBLIGACION, (oblig_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def hard_delete(oblig_id):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(q.SQL_HARD_DELETE_OBLIGACION, (oblig_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def insert_historial(oblig_id, campo, valor_anterior, valor_nuevo, comentario, modificado_por):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(q.SQL_INSERT_HISTORIAL, (
        oblig_id, campo, valor_anterior, valor_nuevo, comentario, modificado_por
    ))
    # No hace commit aca -- el llamador maneja la transaccion completa


# ------------------------------------------------------------
# Evidencias
# ------------------------------------------------------------
def insert_evidencia(oblig_id, nombre_archivo, ruta, tipo_archivo, tamanio_bytes, subido_por):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(q.SQL_INSERT_EVIDENCIA, (
        oblig_id, nombre_archivo, ruta, tipo_archivo, tamanio_bytes, subido_por
    ))
    # No hace commit aca -- forma parte de la transaccion de "cumplir"


def list_evidencias(oblig_id):
    conn = get_connection()
    cur = conn.cursor()
    return cur.execute(q.SQL_LIST_EVIDENCIAS_BY_OBLIGACION, (oblig_id,)).fetchall()


def get_evidencia_by_id(evidencia_id, oblig_id):
    """2026-07-13 (T8): valida que la evidencia pertenezca a esa obligacion -- evita
    que alguien adivine un evidencia_id de otra obligacion via la URL."""
    conn = get_connection()
    cur = conn.cursor()
    return cur.execute(q.SQL_GET_EVIDENCIA_BY_ID, (evidencia_id, oblig_id)).fetchone()


def marcar_cumplida(oblig_id, estatus_final):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(q.SQL_MARCAR_CUMPLIDA, (estatus_final, oblig_id))
    # No hace commit aca -- el service hace commit al final de la transaccion


def marcar_cumplida_pendiente_jefe(oblig_id, estatus_final, requiere_aprobacion):
    """2026-08-15: Punto 9 -- si requiere_aprobacion (usuario tiene jefe_id),
    queda pendiente de aprobación (activa=1, sigue "por cumplir" en pastel/
    dashboard -- decisión de Matías). Si no, se auto-aprueba (igual que antes,
    comportamiento previo a este punto).
    2026-08-17: si requiere_aprobacion, estatus_final NO se graba en `estatus`
    todavia -- va a estatus_pendiente_destino (SQL_MARCAR_CUMPLIDA_PENDIENTE_JEFE
    setea estatus='pendiente_aprobacion' fijo)."""
    conn = get_connection()
    cur = conn.cursor()
    sql = q.SQL_MARCAR_CUMPLIDA_PENDIENTE_JEFE if requiere_aprobacion else q.SQL_MARCAR_CUMPLIDA_AUTOAPROBADA
    cur.execute(sql, (estatus_final, oblig_id))
    # No hace commit aca -- el service hace commit al final de la transaccion


def list_pendientes_aprobacion_jefe(jefe_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(q.SQL_LIST_PENDIENTES_APROBACION_JEFE, (jefe_id,))
    return _rows_to_dicts(cur)


def aprobar_cumplimiento_jefe(oblig_id, jefe_id):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(q.SQL_APROBAR_CUMPLIMIENTO_JEFE, (jefe_id, oblig_id))
        filas = cur.rowcount
        conn.commit()
        return bool(filas)
    except Exception:
        conn.rollback()
        raise


def rechazar_cumplimiento_jefe(oblig_id, jefe_id, motivo):
    """Revierte a no-cumplida (el dueño debe volver a marcarla cumplida) --
    estatus se recalcula segun fecha_vencimiento (mismo criterio que usa el
    scheduler para 'atrasado'). Motivo obligatorio -- pedido de Matías,
    2026-08-15 (2), el usuario debe recibir el porqué por email."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        row = get_raw_by_id(oblig_id)
        if not row:
            return False
        from datetime import date
        fecha_venc = row["fecha_vencimiento"]
        if hasattr(fecha_venc, "date"):
            fecha_venc = fecha_venc.date()
        estatus_revertido = "atrasado" if (fecha_venc and fecha_venc < date.today()) else "por_presentar"
        cur.execute(q.SQL_RECHAZAR_CUMPLIMIENTO_JEFE, (estatus_revertido, jefe_id, motivo, oblig_id))
        filas = cur.rowcount
        conn.commit()
        return bool(filas)
    except Exception:
        conn.rollback()
        raise


def commit():
    get_db().commit()


# ------------------------------------------------------------
# Historial (activa = 0)
# ------------------------------------------------------------
def list_historial(user_id, rol, filters):
    conn = get_connection()
    params = []
    placeholders = ",".join("?" * len(ESTATUS_TERMINALES))
    where = ["o.activa = 0", f"o.estatus IN ({placeholders})"]
    params.extend(ESTATUS_TERMINALES)

    _apply_visibility(where, params, rol, user_id)

    if filters.get("empresa_id"):
        where.append("o.empresa_id = ?")
        params.append(filters["empresa_id"])
    if filters.get("tipo_id"):
        where.append("o.tipo_id = ?")
        params.append(filters["tipo_id"])
    if filters.get("entidad_id"):
        where.append("o.entidad_id = ?")
        params.append(filters["entidad_id"])
    if filters.get("departamento_id"):
        where.append("o.departamento_id = ?")
        params.append(filters["departamento_id"])
    if filters.get("frecuencia_id"):
        where.append("o.frecuencia_id = ?")
        params.append(filters["frecuencia_id"])
    if filters.get("area_id"):
        # 2026-08-14: filtro por Área (pedido en reunión).
        where.append("o.departamento_id IN (SELECT id FROM departamentos WHERE area_id = ?)")
        params.append(filters["area_id"])
    if filters.get("seccion") and filters["seccion"] in SECCION_PASTEL_WHERE:
        # 2026-08-14: Punto 6 -- navegación desde el modal del pastel (Punto 5).
        where.append(SECCION_PASTEL_WHERE[filters["seccion"]])
    _apply_date_range_filter(where, params, filters.get("fecha_desde"), filters.get("fecha_hasta"))
    if filters.get("estatus"):
        where.append("o.estatus = ?")
        params.append(filters["estatus"])
    if filters.get("usuario_id") and rol in ("admin", "admin_obligaciones"):
        where.append("o.usuario_id = ?")
        params.append(filters["usuario_id"])

    sql = q.SQL_SELECT_JOIN_BASE + " WHERE " + " AND ".join(where) + " ORDER BY o.modificado_en DESC"
    return conn.execute(sql, params).fetchall()


# ------------------------------------------------------------
# Dashboard -- WHERE dinamico (visibilidad por rol + filtros)
# ------------------------------------------------------------
def _dashboard_common_where(rol, user_id, filters):
    # 2026-07-21: el universo del dashboard = obligaciones VIVAS (activa=1) +
    # cerradas en historial (activa=0 con estatus terminal). Excluye las
    # soft-deleted no terminales (activa=0 con estatus por_presentar/atrasado),
    # que no aparecen ni en Consultas (filtra activa=1) ni en Historial (filtra
    # estatus terminal). Sin esta clausula el dashboard contaba filas borradas
    # logicamente -> total inflado y un "atrasado" fantasma en los graficos que
    # contradecia el KPI total_atrasadas.
    ph = ",".join("?" * len(ESTATUS_TERMINALES))
    where = [f"(o.activa = 1 OR o.estatus IN ({ph}))"]
    params = list(ESTATUS_TERMINALES)
    _apply_visibility(where, params, rol, user_id)

    if filters.get("empresa_id"):
        where.append("o.empresa_id = ?")
        params.append(filters["empresa_id"])
    if filters.get("tipo_id"):
        where.append("o.tipo_id = ?")
        params.append(filters["tipo_id"])
    if filters.get("entidad_id"):
        where.append("o.entidad_id = ?")
        params.append(filters["entidad_id"])
    if filters.get("frecuencia_id"):
        where.append("o.frecuencia_id = ?")
        params.append(filters["frecuencia_id"])
    if filters.get("area_id"):
        # 2026-08-14: filtro por Área (pedido en reunión).
        where.append("o.departamento_id IN (SELECT id FROM departamentos WHERE area_id = ?)")
        params.append(filters["area_id"])
    if filters.get("fecha_desde"):
        where.append("o.fecha_vencimiento >= ?")
        params.append(filters["fecha_desde"])
    if filters.get("fecha_hasta"):
        where.append("o.fecha_vencimiento <= ?")
        params.append(filters["fecha_hasta"])
    # 2026-07-28: agregado filtro usuario_id en Dashboard (admin=todos, jefe_area=solo subordinados)
    # -- mismo guard que list_obligaciones: _apply_visibility() ya acoto el WHERE, este AND
    # solo puede angostar el conjunto visible, nunca ampliarlo a otro jefe/area.
    if filters.get("usuario_id") and rol in (ROL_ADMIN_SILI, ROL_ADMIN_OBLIG, ROL_JEFE_AREA, ROL_GERENTE_OBLIG):
        where.append("o.usuario_id = ?")
        params.append(filters["usuario_id"])

    return where, params


def dashboard_kpis(rol, user_id, filters):
    conn = get_connection()
    common_where, common_params = _dashboard_common_where(rol, user_id, filters)

    def _count(extra_clause=None):
        where = list(common_where)
        if extra_clause:
            where.append(extra_clause)
        sql = q.SQL_DASHBOARD_COUNT_BASE
        if where:
            sql += " WHERE " + " AND ".join(where)
        row = conn.execute(sql, common_params).fetchone()
        return int(row[0] or 0)

    total_obligaciones = _count()
    total_activas = _count("o.activa = 1")
    total_atrasadas = _count("o.activa = 1 AND o.estatus = 'atrasado'")
    proximas_vencer = _count(
        "o.activa = 1 AND o.estatus <> 'atrasado' AND o.fecha_vencimiento IS NOT NULL "
        "AND o.fecha_vencimiento BETWEEN CAST(GETDATE() AS DATE) AND DATEADD(DAY, 30, CAST(GETDATE() AS DATE))"
    )

    where_hist = list(common_where) + ["o.activa = 0"]
    sql_hist = q.SQL_DASHBOARD_CUMPLIDAS_BASE + " WHERE " + " AND ".join(where_hist)
    row = conn.execute(sql_hist, common_params).fetchone()

    return {
        "total_obligaciones": total_obligaciones,
        "total_activas":   total_activas,
        "total_atrasadas": total_atrasadas,
        "proximas_vencer": proximas_vencer,
        "a_tiempo":        int((row[0] if row else 0) or 0),
        "fuera_plazo":     int((row[1] if row else 0) or 0),
    }


def _dashboard_group_query(select_sql, group_by_sql, rol, user_id, filters):
    conn = get_connection()
    cur = conn.cursor()
    where, params = _dashboard_common_where(rol, user_id, filters)
    sql = select_sql
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += group_by_sql
    cur.execute(sql, params)
    return _rows_to_dicts(cur)


def dashboard_por_estatus(rol, user_id, filters):
    return _dashboard_group_query(
        q.SQL_DASHBOARD_POR_ESTATUS_SELECT, q.SQL_DASHBOARD_POR_ESTATUS_GROUP_BY, rol, user_id, filters
    )


# 2026-08-16: dashboard_por_tipo() y dashboard_por_estatus_total() sin consumidor
# tras rediseño dashboard (Matías) -- no borradas sin confirmación explícita, quedan
# como candidatas a eliminar.
def dashboard_por_tipo(rol, user_id, filters):
    return _dashboard_group_query(
        q.SQL_DASHBOARD_POR_TIPO_SELECT, q.SQL_DASHBOARD_POR_TIPO_GROUP_BY, rol, user_id, filters
    )


def dashboard_por_estatus_total(rol, user_id, filters):
    """Conteo por estatus sumando TODAS las empresas -- un solo grafico combinado."""
    return _dashboard_group_query(
        q.SQL_DASHBOARD_POR_ESTATUS_TOTAL_SELECT, q.SQL_DASHBOARD_POR_ESTATUS_TOTAL_GROUP_BY, rol, user_id, filters
    )


# 2026-08-05: dashboard_por_estatus_fundido() eliminada -- sin consumidor tras
# borrar chartEstado (pedido Matias, sesion revision pendientes).


# 2026-08-14: clausula SQL por seccion del pastel (Punto 4) -- MISMO criterio
# usado en dashboard_data()/services.py para pastel_cumplimiento, para que los
# conteos del modal (Punto 5) cuadren exacto con las secciones del pastel.
SECCION_PASTEL_WHERE = {
    "cumplida_a_tiempo":    "o.activa = 0 AND o.estatus = 'cumplido'",
    "cumplida_fuera_plazo": "o.activa = 0 AND o.estatus = 'cumplido_fuera_plazo'",
    "pendiente_en_plazo":   "o.activa = 1 AND o.estatus <> 'atrasado'",
    "pendiente_atrasada":   "o.activa = 1 AND o.estatus = 'atrasado'",
}


def dashboard_desglose_seccion(seccion, rol, user_id, filters):
    """Punto 5: 3 tablas (Tipo/Entidad/Area) con id+nombre+total, acotadas a la
    seccion del pastel clickeada. seccion invalida -> listas vacias (defensivo,
    el front solo manda valores de SECCION_PASTEL_WHERE)."""
    extra = SECCION_PASTEL_WHERE.get(seccion)
    if not extra:
        return {"por_tipo": [], "por_entidad": [], "por_area": []}

    conn = get_connection()
    where, params = _dashboard_common_where(rol, user_id, filters)
    where.append(extra)

    def _grupo(select_sql, group_by_sql):
        sql = select_sql + " WHERE " + " AND ".join(where) + group_by_sql
        cur = conn.cursor()
        cur.execute(sql, params)
        return _rows_to_dicts(cur)

    return {
        "por_tipo":    _grupo(q.SQL_DESGLOSE_POR_TIPO_SELECT, q.SQL_DESGLOSE_POR_TIPO_GROUP_BY),
        "por_entidad": _grupo(q.SQL_DESGLOSE_POR_ENTIDAD_SELECT, q.SQL_DESGLOSE_POR_ENTIDAD_GROUP_BY),
        "por_area":    _grupo(q.SQL_DESGLOSE_POR_AREA_SELECT, q.SQL_DESGLOSE_POR_AREA_GROUP_BY),
    }


# ------------------------------------------------------------
# Scheduler
# ------------------------------------------------------------
def get_ids_para_marcar_atrasadas():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(q.SQL_MARCAR_ATRASADAS)
    return [r[0] for r in cur.fetchall()]


def marcar_atrasada(oblig_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(q.SQL_UPDATE_ESTATUS_ATRASADO, (oblig_id,))


def list_obligaciones_para_alertas():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(q.SQL_LIST_OBLIGACIONES_ACTIVAS_CON_FECHA)
    return _rows_to_dicts(cur)


def alerta_ya_enviada(oblig_id, tipo_alerta, periodo):
    conn = get_connection()
    cur = conn.cursor()
    row = cur.execute(q.SQL_ALERTA_YA_ENVIADA, (oblig_id, tipo_alerta, periodo)).fetchone()
    return row is not None


def insert_alerta_enviada(oblig_id, tipo_alerta, periodo):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(q.SQL_INSERT_ALERTA_ENVIADA, (oblig_id, tipo_alerta, periodo))
