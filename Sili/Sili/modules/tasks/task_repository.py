from __future__ import annotations

from modules.db import get_db
from modules.tasks.task_constants import GRUPO_TIPO_TAREA_ID
from modules.tasks import task_queries as q


def _row_get(row, key, default=None):
    if row is None:
        return default

    try:
        return row[key]
    except Exception:
        pass

    try:
        return getattr(row, key)
    except Exception:
        return default


def _row_value(row, key, index):
    """
    Compatible con pyodbc.Row, sqlite3.Row, dict y objetos similares.
    Evita depender de iterar row directamente.
    """
    if row is None:
        return None

    try:
        return row[key]
    except Exception:
        pass

    try:
        return row[index]
    except Exception:
        pass

    try:
        return getattr(row, key)
    except Exception:
        return None


def _rows_to_dicts(cur):
    cols = [c[0] for c in cur.description]
    rows = cur.fetchall()

    return [
        {
            col: _row_value(row, col, i)
            for i, col in enumerate(cols)
        }
        for row in rows
    ]


def _row_to_dict(cur):
    row = cur.fetchone()
    if not row:
        return None

    cols = [c[0] for c in cur.description]

    return {
        col: _row_value(row, col, i)
        for i, col in enumerate(cols)
    }


def _conn_is_sql_server(conn) -> bool:
    return str(getattr(conn, "db_engine", "")).lower() == "sqlserver"


def _fetch_identity_value(cur, conn):
    if _conn_is_sql_server(conn):
        row = cur.execute("SELECT CAST(SCOPE_IDENTITY() AS INT) AS id").fetchone()
        return int(_row_get(row, "id", row[0] if row else 0)) if row else None

    lastrowid = getattr(cur, "lastrowid", None)
    if lastrowid:
        return int(lastrowid)

    row = cur.execute("SELECT last_insert_rowid() AS id").fetchone()
    if not row:
        return None

    return int(_row_get(row, "id", row[0]))


def repo_obtener_solicitantes():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(q.SQL_OBTENER_SOLICITANTES)
    return cur.fetchall()


def repo_obtener_responsables(user, modo: str):
    if modo != "asignar":
        return []

    conn = get_db()
    cur = conn.cursor()

    if user["rol"] == "admin":
        cur.execute(q.SQL_OBTENER_RESPONSABLES_ADMIN)
    elif user["rol"] == "jefe":
        cur.execute(q.SQL_OBTENER_RESPONSABLES_JEFE, (user["id"], user["id"]))
    else:
        cur.execute(q.SQL_OBTENER_RESPONSABLES_USUARIO, (user["id"],))

    return cur.fetchall()


def repo_obtener_tipos_tarea():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(q.SQL_OBTENER_TIPOS_TAREA, (GRUPO_TIPO_TAREA_ID,))
    return cur.fetchall()


def repo_obtener_empresas_activas():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(q.SQL_OBTENER_EMPRESAS_ACTIVAS)
    return cur.fetchall()


def repo_find_user_id_by_email(cur, email: str):
    if not email:
        return None

    cur.execute(q.SQL_FIND_USER_ID_BY_EMAIL, (email,))
    row = cur.fetchone()

    return int(_row_get(row, "id")) if row else None


def repo_dashboard_tareas(user):
    conn = get_db()
    cur = conn.cursor()

    base_sql = q.SQL_DASHBOARD_TAREAS_BASE
    where = []
    params = []

    if user["rol"] == "admin":
        pass
    elif user["rol"] == "jefe":
        where.append("(u.id = ? OR u.departamento_id = ?)")
        params.extend([user["id"], user.get("departamento_id")])
    else:
        where.append("u.id = ?")
        params.append(user["id"])

    if where:
        base_sql += " WHERE " + " AND ".join(where)

    base_sql += q.SQL_DASHBOARD_ORDER

    cur.execute(base_sql, tuple(params))
    return cur.fetchall()


def repo_listar_tareas_raw():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(q.SQL_LISTAR_TAREAS_BASE)
    return _rows_to_dicts(cur)


def repo_listar_tarea_responsables_map():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(q.SQL_LISTAR_TAREA_RESPONSABLES_MAP)
    return cur.fetchall()


def repo_insertar_tarea(conn, data: dict) -> int:
    cur = conn.cursor()

    if _conn_is_sql_server(conn):
        cur.execute(
            q.SQL_INSERTAR_TAREA_Y_DEVOLVER_ID,
            (
                data["titulo"],
                data["descripcion"],
                data["estado"],
                data["fecha_creacion"],
                data["fecha_inicio"],
                data["fecha_compromiso"],
                data["fecha_fin"],
                data["usuario_id"],
                data["creador_id"],
                data["solicitante_id"],
                data["tipo_tarea_id"],
                data["empresa_id"],
            ),
        )

        row = cur.fetchone()
        tarea_id = _row_value(row, "id", 0) if row else None

        if tarea_id is None:
            raise RuntimeError("No se pudo recuperar el ID de la tarea creada.")

        return int(tarea_id)

    cur.execute(
        q.SQL_INSERTAR_TAREA,
        (
            data["titulo"],
            data["descripcion"],
            data["estado"],
            data["fecha_creacion"],
            data["fecha_inicio"],
            data["fecha_compromiso"],
            data["fecha_fin"],
            data["usuario_id"],
            data["creador_id"],
            data["solicitante_id"],
            data["tipo_tarea_id"],
            data["empresa_id"],
        ),
    )

    lastrowid = getattr(cur, "lastrowid", None)
    if lastrowid is not None:
        return int(lastrowid)

    row = cur.execute("SELECT last_insert_rowid() AS id").fetchone()
    tarea_id = _row_value(row, "id", 0) if row else None

    if tarea_id is None:
        raise RuntimeError("No se pudo recuperar el ID de la tarea creada.")

    return int(tarea_id)


def repo_insertar_tarea_responsable_si_no_existe(conn, tarea_id: int, usuario_id: int):
    cur = conn.cursor()

    cur.execute(q.SQL_VALIDAR_TAREA_RESPONSABLE_EXISTE, (tarea_id, usuario_id))
    if cur.fetchone():
        return

    cur.execute(q.SQL_INSERTAR_TAREA_RESPONSABLE, (tarea_id, usuario_id))


def repo_obtener_tarea_detalle(task_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(q.SQL_OBTENER_DETALLE_TAREA, (task_id,))
    return cur.fetchone()


def repo_insertar_tarea_accion(conn, data: dict):
    cur = conn.cursor()
    cur.execute(
        q.SQL_INSERTAR_TAREA_ACCION,
        (
            data["tarea_id"],
            data["usuario_id"],
            data["fecha_accion"],
            data["observacion"],
            data["detalles"],
            data["estado_accion"],
            data["usuario_asignado_id"],
            data["fecha_fin_tentativa"],
            data["fecha_inicio"],
        ),
    )


def repo_obtener_email_usuario(user_id: int):
    if not user_id:
        return None

    conn = get_db()
    cur = conn.cursor()
    cur.execute(q.SQL_OBTENER_USUARIO_EMAIL_ACTIVO, (user_id,))
    return cur.fetchone()


def repo_obtener_emails_responsables_tarea(task_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(q.SQL_OBTENER_EMAIL_RESPONSABLES_TAREA, (task_id,))
    return cur.fetchall()


def repo_obtener_tarea_acciones(task_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(q.SQL_OBTENER_ACCIONES_TAREA, (task_id,))
    return cur.fetchall()


def repo_obtener_usuarios_activos():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(q.SQL_OBTENER_USUARIOS_ACTIVOS)
    return _rows_to_dicts(cur)


def repo_obtener_accion_con_tarea(accion_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(q.SQL_OBTENER_ACCION_CON_TAREA, (accion_id,))
    return cur.fetchone()


def repo_finalizar_accion(conn, accion_id: int) -> int:
    cur = conn.cursor()
    cur.execute(q.SQL_FINALIZAR_ACCION, (accion_id,))
    return cur.rowcount


def repo_obtener_tarea_edicion(task_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(q.SQL_OBTENER_TAREA_EDICION, (task_id,))
    return _row_to_dict(cur)


def repo_es_responsable_tarea(task_id: int, user_id: int) -> bool:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(q.SQL_ES_RESPONSABLE_TAREA, (task_id, user_id))
    return cur.fetchone() is not None


def repo_actualizar_tarea(conn, task_id: int, data: dict):
    cur = conn.cursor()
    cur.execute(
        q.SQL_ACTUALIZAR_TAREA,
        (
            data["titulo"],
            data["descripcion"],
            data["empresa_id"],
            data["estado"],
            data["fecha_inicio"],
            data["fecha_compromiso"],
            data["fecha_fin"],
            data["fecha_cierre_real"],
            data["solicitante_id"],
            data["porcentaje_avance"],
            data["tipo_tarea_id"],
            task_id,
        ),
    )


def repo_eliminar_tarea(conn, task_id: int, user: dict) -> int:
    cur = conn.cursor()

    if user["rol"] != "admin":
        cur.execute(q.SQL_ELIMINAR_TAREA_RESPONSABLE, (task_id, user["id"]))
    else:
        cur.execute(q.SQL_ELIMINAR_TAREA_ADMIN, (task_id,))

    return cur.rowcount


def repo_obtener_departamentos_tareas():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(q.SQL_OBTENER_DEPARTAMENTOS_TAREAS)
    rows = _rows_to_dicts(cur)
    return [r["nombre"] for r in rows]


def repo_obtener_tarea_para_encuesta(task_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(q.SQL_OBTENER_TAREA_PARA_ENCUESTA, (task_id,))
    return _row_to_dict(cur)


def repo_obtener_encuesta_por_tarea(task_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(q.SQL_OBTENER_ENCUESTA_POR_TAREA, (task_id,))
    return _row_to_dict(cur)


def repo_insertar_encuesta(conn, tarea_id: int, solicitante_id, token: str):
    cur = conn.cursor()
    cur.execute(
        q.SQL_INSERTAR_ENCUESTA,
        (tarea_id, solicitante_id, token),
    )

    row = cur.fetchone()
    if not row:
        raise RuntimeError("No se pudo obtener el ID de la encuesta creada.")

    encuesta_id = _row_value(row, "id", 0)

    if encuesta_id is None:
        raise RuntimeError("No se pudo leer el ID de la encuesta creada.")

    return int(encuesta_id)


def repo_marcar_encuesta_enviada(conn, encuesta_id: int):
    cur = conn.cursor()
    cur.execute(q.SQL_MARCAR_ENCUESTA_ENVIADA, (encuesta_id,))


def repo_obtener_encuesta_por_token(token: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(q.SQL_OBTENER_ENCUESTA_POR_TOKEN, (token,))
    return _row_to_dict(cur)


def repo_insertar_respuesta_encuesta(conn, encuesta_id: int, pregunta_numero: int, puntuacion: int):
    cur = conn.cursor()
    cur.execute(
        q.SQL_INSERTAR_RESPUESTA_ENCUESTA,
        (encuesta_id, pregunta_numero, puntuacion),
    )


def repo_finalizar_encuesta(conn, encuesta_id: int, comentario: str):
    cur = conn.cursor()
    cur.execute(
        q.SQL_FINALIZAR_ENCUESTA,
        (comentario, encuesta_id),
    )
    return cur.rowcount


def repo_listar_encuestas():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(q.SQL_LISTAR_ENCUESTAS)

    data = _rows_to_dicts(cur)

    print(">>> repo_listar_encuestas FIRST:", data[0] if data else None, flush=True)

    return data

def repo_obtener_resultado_encuesta_email(encuesta_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(q.SQL_OBTENER_RESULTADO_ENCUESTA_EMAIL, (encuesta_id,))
    return _row_to_dict(cur)