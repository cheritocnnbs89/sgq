from modules.tasks.task_constants import (
    TABLA_TAREAS,
    TABLA_TAREA_RESPONSABLES,
    TABLA_TAREA_ACCIONES,
    TABLA_USUARIOS,
    TABLA_DEPARTAMENTOS,
    TABLA_PARAM_VALUES,
    TABLA_EMPRESAS,
    TABLA_ENCUESTAS_SATISFACCION,
    TABLA_ENCUESTAS_RESPUESTAS,
    ESTADO_TERMINADO,
    ESTADO_CERRADO_SISTEMA,
)

SQL_OBTENER_SOLICITANTES = f"""
    SELECT id, username, COALESCE(nombre_completo,'') AS nombre_completo
    FROM {TABLA_USUARIOS}
    WHERE disabled = 0
    ORDER BY nombre_completo, username
"""

SQL_OBTENER_RESPONSABLES_ADMIN = f"""
    SELECT id, username, COALESCE(nombre_completo,'') AS nombre_completo
    FROM {TABLA_USUARIOS}
    WHERE disabled = 0
    ORDER BY nombre_completo, username
"""

SQL_OBTENER_RESPONSABLES_JEFE = f"""
    SELECT id, username, COALESCE(nombre_completo,'') AS nombre_completo
    FROM {TABLA_USUARIOS}
    WHERE disabled = 0
      AND (id = ? OR jefe_id = ?)
    ORDER BY nombre_completo, username
"""

SQL_OBTENER_RESPONSABLES_USUARIO = f"""
    SELECT id, username, COALESCE(nombre_completo,'') AS nombre_completo
    FROM {TABLA_USUARIOS}
    WHERE disabled = 0
      AND id = ?
"""

SQL_OBTENER_TIPOS_TAREA = f"""
    SELECT id, nombre
    FROM {TABLA_PARAM_VALUES}
    WHERE group_id = ?  
    ORDER BY orden ASC
"""

SQL_OBTENER_EMPRESAS_ACTIVAS = f"""
    SELECT id, razon_social
    FROM {TABLA_EMPRESAS}
    WHERE activo = 1
    ORDER BY razon_social ASC
"""

SQL_FIND_USER_ID_BY_EMAIL = f"""
    SELECT id
    FROM {TABLA_USUARIOS}
    WHERE disabled = 0
      AND LOWER(LTRIM(RTRIM(email))) = ?
"""
SQL_DASHBOARD_TAREAS_BASE = f"""
    SELECT t.id,
           t.titulo,
           t.descripcion,
           t.estado,
           t.fecha_creacion,
           t.fecha_inicio,
           t.fecha_compromiso,
           t.fecha_fin,
           t.fecha_cierre_real,
           t.usuario_id,
           u.username AS propietario,
           d.nombre AS departamento
    FROM {TABLA_TAREAS} t
    JOIN {TABLA_USUARIOS} u ON t.usuario_id = u.id
    LEFT JOIN {TABLA_DEPARTAMENTOS} d ON u.departamento_id = d.id
"""


SQL_DASHBOARD_ORDER = """
    ORDER BY
        CASE WHEN t.fecha_compromiso IS NULL THEN 1 ELSE 0 END,
        t.fecha_compromiso,
        t.fecha_creacion DESC
"""

SQL_LISTAR_TAREAS_BASE = f"""
    SELECT t.id,
           t.titulo,
           t.descripcion,
           t.estado,
           t.fecha_creacion,
           t.fecha_inicio,
           t.fecha_compromiso,
           t.fecha_fin,
           t.fecha_cierre_real,
           t.solicitante_id,

           -- SOLICITANTE
           usol.username AS solicitante_username,
           usol.nombre_completo AS solicitante_nombre,

           -- DEPARTAMENTO DEL SOLICITANTE
           COALESCE(dsol.nombre,'') AS departamento_nombre,

           t.usuario_id,
           t.creador_id,
           t.tipo_tarea_id,
           p.nombre AS tipo_tarea_nombre,

           cu.username AS creador_username,
           cu.nombre_completo AS creador_nombre,

           t.notificado,
           t.porcentaje_avance,

           e.razon_social AS empresa_nombre,
           ei.id          AS inbox_id

    FROM {TABLA_TAREAS} t
    LEFT JOIN {TABLA_EMPRESAS} e ON t.empresa_id = e.id
    LEFT JOIN {TABLA_USUARIOS} cu ON t.creador_id = cu.id
    LEFT JOIN {TABLA_PARAM_VALUES} p ON t.tipo_tarea_id = p.id

    -- JOIN SOLICITANTE
    LEFT JOIN {TABLA_USUARIOS} usol ON usol.id = t.solicitante_id
    LEFT JOIN {TABLA_DEPARTAMENTOS} dsol ON dsol.id = usol.departamento_id

    -- TICKET BANDEJA (el más reciente si hay varios)
    LEFT JOIN email_tickets_inbox ei ON ei.id = (
        SELECT TOP 1 id FROM email_tickets_inbox
        WHERE tarea_id = t.id
        ORDER BY id DESC
    )

    ORDER BY t.id DESC
"""



SQL_LISTAR_TAREA_RESPONSABLES_MAP = f"""
    SELECT tr.tarea_id,
           ur.id AS usuario_id,
           ur.username AS username,
           COALESCE(ur.nombre_completo,'') AS nombre_completo,
           COALESCE(d.nombre,'') AS depto_nombre
    FROM {TABLA_TAREA_RESPONSABLES} tr
    JOIN {TABLA_USUARIOS} ur ON ur.id = tr.usuario_id
    LEFT JOIN {TABLA_DEPARTAMENTOS} d ON d.id = ur.departamento_id
    ORDER BY tr.tarea_id, ur.username
"""

SQL_INSERTAR_TAREA = f"""
    INSERT INTO {TABLA_TAREAS} (
        titulo,
        descripcion,
        estado,
        fecha_creacion,
        fecha_inicio,
        fecha_compromiso,
        fecha_fin,
        usuario_id,
        creador_id,
        solicitante_id,
        notificado,
        tipo_tarea_id,
        empresa_id
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
"""

SQL_VALIDAR_TAREA_RESPONSABLE_EXISTE = f"""
    SELECT 1
    FROM {TABLA_TAREA_RESPONSABLES}
    WHERE tarea_id = ?
      AND usuario_id = ?
"""

SQL_INSERTAR_TAREA_Y_DEVOLVER_ID = f"""
    INSERT INTO {TABLA_TAREAS} (
        titulo,
        descripcion,
        estado,
        fecha_creacion,
        fecha_inicio,
        fecha_compromiso,
        fecha_fin,
        usuario_id,
        creador_id,
        solicitante_id,
        notificado,
        tipo_tarea_id,
        empresa_id
    )
    OUTPUT INSERTED.id
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
"""

SQL_INSERTAR_TAREA_RESPONSABLE = f"""
    INSERT INTO {TABLA_TAREA_RESPONSABLES} (tarea_id, usuario_id)
    VALUES (?, ?)
"""

SQL_OBTENER_DETALLE_TAREA = f"""
    SELECT t.id,
           t.titulo,
           t.descripcion,
           t.estado,
           t.fecha_creacion,
           t.fecha_inicio,
           t.fecha_compromiso,
           t.fecha_fin,
           t.fecha_cierre_real,
           t.usuario_id,
           t.creador_id,
           t.solicitante_id,
           u.username        AS responsable_username,
           u.nombre_completo AS responsable_nombre,
           c.username        AS creador_username,
           c.nombre_completo AS creador_nombre,
           s.username        AS solicitante_username,
           s.nombre_completo AS solicitante_nombre
    FROM {TABLA_TAREAS} t
    JOIN {TABLA_USUARIOS} u ON t.usuario_id = u.id
    LEFT JOIN {TABLA_USUARIOS} c ON t.creador_id = c.id
    LEFT JOIN {TABLA_USUARIOS} s ON t.solicitante_id = s.id
    WHERE t.id = ?
"""

SQL_INSERTAR_TAREA_ACCION = f"""
    INSERT INTO {TABLA_TAREA_ACCIONES} (
        tarea_id,
        usuario_id,
        fecha_accion,
        observacion,
        detalles,
        estado_accion,
        usuario_asignado_id,
        fecha_fin_tentativa,
        fecha_inicio
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

SQL_OBTENER_EMAIL_RESPONSABLES_TAREA = f"""
    SELECT u.email,
           COALESCE(u.nombre_completo, u.username) AS nombre
    FROM {TABLA_TAREA_RESPONSABLES} tr
    JOIN {TABLA_USUARIOS} u ON u.id = tr.usuario_id
    WHERE tr.tarea_id = ?
      AND u.disabled = 0
"""

SQL_OBTENER_USUARIO_EMAIL_ACTIVO = f"""
    SELECT email,
           COALESCE(nombre_completo, username) AS nombre
    FROM {TABLA_USUARIOS}
    WHERE id = ?
      AND disabled = 0
"""

SQL_OBTENER_ACCIONES_TAREA = f"""
    SELECT a.id,
           a.tarea_id,
           a.usuario_id,
           a.fecha_accion,
           a.observacion,
           a.detalles,
           a.estado_accion,
           a.fecha_inicio,
           a.fecha_fin_tentativa,
           u.nombre_completo,
           u.username,
           ua.nombre_completo AS nombre_asignado
    FROM {TABLA_TAREA_ACCIONES} a
    JOIN {TABLA_USUARIOS} u ON a.usuario_id = u.id
    LEFT JOIN {TABLA_USUARIOS} ua ON a.usuario_asignado_id = ua.id
    WHERE a.tarea_id = ?
    ORDER BY a.fecha_accion ASC, a.id ASC
"""

SQL_OBTENER_USUARIOS_ACTIVOS = f"""
    SELECT id, username, COALESCE(nombre_completo,'') AS nombre_completo
    FROM {TABLA_USUARIOS}
    WHERE disabled = 0
    ORDER BY nombre_completo ASC, username ASC
"""

SQL_OBTENER_ACCION_CON_TAREA = f"""
    SELECT a.*,
           t.titulo,
           t.usuario_id AS resp_tarea_id,
           t.solicitante_id,
           t.creador_id
    FROM {TABLA_TAREA_ACCIONES} a
    JOIN {TABLA_TAREAS} t ON a.tarea_id = t.id
    WHERE a.id = ?
"""

SQL_FINALIZAR_ACCION = f"""
    UPDATE {TABLA_TAREA_ACCIONES}
    SET estado_accion = 'Finalizado'
    WHERE id = ?
"""

SQL_OBTENER_TAREA_EDICION = f"""
    SELECT t.id,
           t.titulo,
           t.descripcion,
           t.estado,
           t.fecha_inicio,
           t.fecha_compromiso,
           t.fecha_cierre_real,
           t.usuario_id,
           t.fecha_fin,
           t.creador_id,
           t.solicitante_id,
           t.tipo_tarea_id,
           t.porcentaje_avance,
           t.empresa_id,
           ei.id          AS inbox_id,
           ei.from_name   AS inbox_from_name,
           ei.from_email  AS inbox_from_email,
           ei.subject     AS inbox_subject
    FROM {TABLA_TAREAS} t
    LEFT JOIN email_tickets_inbox ei ON ei.tarea_id = t.id
    WHERE t.id = ?
"""

SQL_ES_RESPONSABLE_TAREA = f"""
    SELECT 1
    FROM {TABLA_TAREA_RESPONSABLES}
    WHERE tarea_id = ?
      AND usuario_id = ?
"""

SQL_ACTUALIZAR_TAREA = f"""
    UPDATE {TABLA_TAREAS}
    SET titulo = ?,
        descripcion = ?,
        empresa_id = ?,
        estado = ?,
        fecha_inicio = ?,
        fecha_compromiso = ?,
        fecha_fin = ?,
        fecha_cierre_real = ?,
        solicitante_id = ?,
        porcentaje_avance = ?,
        tipo_tarea_id = ?
    WHERE id = ?
"""

SQL_ELIMINAR_TAREA_ADMIN = f"""
    DELETE FROM {TABLA_TAREAS}
    WHERE id = ?
"""

SQL_ELIMINAR_TAREA_RESPONSABLE = f"""
    DELETE FROM {TABLA_TAREAS}
    WHERE id = ?
      AND usuario_id = ?
"""

SQL_EXPORTAR_TAREAS = f"""
    SELECT
        t.id AS [Código Tarea],
        t.titulo AS [Título],
        t.descripcion AS [Descripción Tarea],
        t.estado AS [Estado Global],
        pv.nombre AS [Tipo Tarea],
        u_crea.nombre_completo AS [Creado por],
        t.fecha_creacion AS [F. Creación],
        t.fecha_compromiso AS [F. Compromiso],
        u_res.nombre_completo AS [Responsable Tarea],
        d.nombre AS [Departamento],
        a.fecha_accion AS [Fecha Acción],
        u_acc.nombre_completo AS [Acción registrada por],
        a.observacion AS [Resumen Acción],
        a.detalles AS [Detalle Técnico Acción],
        a.estado_accion AS [Estado del Paso],
        u_asig.nombre_completo AS [Asignado en este paso],
        a.fecha_fin_tentativa AS [Fin Tentativo Paso]
    FROM {TABLA_TAREAS} t
    LEFT JOIN {TABLA_PARAM_VALUES} pv ON t.tipo_tarea_id = pv.id
    LEFT JOIN {TABLA_USUARIOS} u_crea ON t.creador_id = u_crea.id
    LEFT JOIN {TABLA_USUARIOS} u_res ON t.usuario_id = u_res.id
    LEFT JOIN {TABLA_DEPARTAMENTOS} d ON u_res.departamento_id = d.id
    LEFT JOIN {TABLA_TAREA_ACCIONES} a ON t.id = a.tarea_id
    LEFT JOIN {TABLA_USUARIOS} u_acc ON a.usuario_id = u_acc.id
    LEFT JOIN {TABLA_USUARIOS} u_asig ON a.usuario_asignado_id = u_asig.id
    WHERE 1 = 1
"""

SQL_OBTENER_DEPARTAMENTOS_TAREAS = f"""
    SELECT DISTINCT d.nombre
    FROM {TABLA_TAREAS} t
    JOIN {TABLA_USUARIOS} u ON t.usuario_id = u.id
    JOIN {TABLA_DEPARTAMENTOS} d ON u.departamento_id = d.id
    WHERE d.nombre IS NOT NULL
    ORDER BY d.nombre
"""

SQL_OBTENER_TAREA_PARA_ENCUESTA = f"""
    SELECT t.id,
           t.titulo,
           t.estado,
           t.fecha_cierre_real,
           t.solicitante_id,
           s.email AS solicitante_email,
           COALESCE(s.nombre_completo, s.username) AS solicitante_nombre,
           u.username AS responsable_username,
           COALESCE(u.nombre_completo, u.username) AS responsable_nombre
    FROM {TABLA_TAREAS} t
    LEFT JOIN {TABLA_USUARIOS} s ON s.id = t.solicitante_id
    LEFT JOIN {TABLA_USUARIOS} u ON u.id = t.usuario_id
    WHERE t.id = ?
"""

SQL_INSERTAR_ENCUESTA = """
    INSERT INTO encuestas_satisfaccion (
        tarea_id,
        solicitante_id,
        token,
        estado,
        fecha_creacion
    )
    OUTPUT INSERTED.id
    VALUES (?, ?, ?, 'Pendiente', GETDATE())
"""

SQL_MARCAR_ENCUESTA_ENVIADA = """
    UPDATE encuestas_satisfaccion
    SET fecha_envio = GETDATE()
    WHERE id = ?
"""

SQL_OBTENER_ENCUESTA_POR_TAREA = """
    SELECT id,
           tarea_id,
           solicitante_id,
           token,
           estado,
           fecha_creacion,
           fecha_envio,
           fecha_respuesta,
           comentario
    FROM encuestas_satisfaccion
    WHERE tarea_id = ?
"""

SQL_OBTENER_ENCUESTA_POR_TOKEN = """
    SELECT e.id,
           e.tarea_id,
           e.solicitante_id,
           e.token,
           e.estado,
           e.fecha_creacion,
           e.fecha_envio,
           e.fecha_respuesta,
           e.comentario,
           t.titulo,
           t.fecha_cierre_real,
           COALESCE(s.nombre_completo, s.username) AS solicitante_nombre
    FROM encuestas_satisfaccion e
    JOIN tareas t ON t.id = e.tarea_id
    LEFT JOIN usuarios s ON s.id = e.solicitante_id
    WHERE e.token = ?
"""

SQL_INSERTAR_RESPUESTA_ENCUESTA = """
    INSERT INTO encuestas_respuestas (
        encuesta_id,
        pregunta_numero,
        puntuacion
    ) VALUES (?, ?, ?)
"""

SQL_FINALIZAR_ENCUESTA = """
    UPDATE encuestas_satisfaccion
    SET estado = 'Realizada',
        fecha_respuesta = GETDATE(),
        comentario = ?
    WHERE id = ?
      AND estado = 'Pendiente'
"""


SQL_LISTAR_ENCUESTAS = f"""
    SELECT
        e.id AS encuesta_id,
        t.id AS tarea_id,
        e.token,
        COALESCE(e.estado, 'Pendiente') AS estado,
        e.fecha_creacion,
        e.fecha_envio,
        e.fecha_respuesta,
        e.comentario,

        t.titulo,
        t.fecha_cierre_real,
        t.solicitante_id,
        t.usuario_id AS responsable_id,

        COALESCE(s.nombre_completo, s.username) AS solicitante_nombre,
        COALESCE(u.nombre_completo, u.username) AS responsable_nombre,

        s.username AS solicitante_username,
        u.username AS responsable_username,

        u.jefe_id AS responsable_jefe_id,

        resp.responsable_ids_csv,
        resp.jefe_ids_csv,
        resp.responsables_nombre_csv,

        AVG(CAST(r.puntuacion AS FLOAT)) AS promedio

    FROM {TABLA_TAREAS} t

    LEFT JOIN {TABLA_ENCUESTAS_SATISFACCION} e
        ON e.tarea_id = t.id

    LEFT JOIN {TABLA_ENCUESTAS_RESPUESTAS} r
        ON r.encuesta_id = e.id

    LEFT JOIN {TABLA_USUARIOS} s
        ON s.id = t.solicitante_id

    LEFT JOIN {TABLA_USUARIOS} u
        ON u.id = t.usuario_id

    OUTER APPLY (
        SELECT
            STRING_AGG(CAST(tr.usuario_id AS VARCHAR(20)), ',') AS responsable_ids_csv,
            STRING_AGG(CAST(ur.jefe_id AS VARCHAR(20)), ',') AS jefe_ids_csv,
            STRING_AGG(COALESCE(ur.nombre_completo, ur.username), ', ') AS responsables_nombre_csv
        FROM {TABLA_TAREA_RESPONSABLES} tr
        INNER JOIN {TABLA_USUARIOS} ur
            ON ur.id = tr.usuario_id
        WHERE tr.tarea_id = t.id
    ) resp

    WHERE t.estado IN ('{ESTADO_TERMINADO}', '{ESTADO_CERRADO_SISTEMA}')

    GROUP BY
        e.id,
        t.id,
        e.token,
        COALESCE(e.estado, 'Pendiente'),
        e.fecha_creacion,
        e.fecha_envio,
        e.fecha_respuesta,
        e.comentario,
        t.titulo,
        t.fecha_cierre_real,
        t.solicitante_id,
        t.usuario_id,
        s.nombre_completo,
        s.username,
        u.nombre_completo,
        u.username,
        u.jefe_id,
        resp.responsable_ids_csv,
        resp.jefe_ids_csv,
        resp.responsables_nombre_csv

    ORDER BY t.fecha_cierre_real DESC, t.id DESC
"""

SQL_OBTENER_RESULTADO_ENCUESTA_EMAIL = f"""
    SELECT
        e.id AS encuesta_id,
        e.tarea_id,
        e.estado,
        e.fecha_creacion,
        e.fecha_envio,
        e.fecha_respuesta,
        e.comentario,

        t.titulo,
        t.descripcion,
        t.fecha_cierre_real,
        t.usuario_id AS responsable_id,
        t.solicitante_id,

        COALESCE(s.nombre_completo, s.username) AS solicitante_nombre,
        s.username AS solicitante_username,
        s.email AS solicitante_email,

        COALESCE(u.nombre_completo, u.username) AS responsable_nombre,
        u.username AS responsable_username,
        u.email AS responsable_email,

        uj.email AS jefe_email,
        COALESCE(uj.nombre_completo, uj.username) AS jefe_nombre,

        AVG(CAST(r.puntuacion AS FLOAT)) AS promedio,

        MAX(CASE WHEN r.pregunta_numero = 1 THEN r.puntuacion END) AS p1,
        MAX(CASE WHEN r.pregunta_numero = 2 THEN r.puntuacion END) AS p2,
        MAX(CASE WHEN r.pregunta_numero = 3 THEN r.puntuacion END) AS p3,
        MAX(CASE WHEN r.pregunta_numero = 4 THEN r.puntuacion END) AS p4,
        MAX(CASE WHEN r.pregunta_numero = 5 THEN r.puntuacion END) AS p5

    FROM {TABLA_ENCUESTAS_SATISFACCION} e
    INNER JOIN {TABLA_TAREAS} t
        ON t.id = e.tarea_id
    LEFT JOIN {TABLA_USUARIOS} s
        ON s.id = e.solicitante_id
    LEFT JOIN {TABLA_USUARIOS} u
        ON u.id = t.usuario_id
    LEFT JOIN {TABLA_USUARIOS} uj
        ON uj.id = u.jefe_id
    LEFT JOIN {TABLA_ENCUESTAS_RESPUESTAS} r
        ON r.encuesta_id = e.id

    WHERE e.id = ?

    GROUP BY
        e.id,
        e.tarea_id,
        e.estado,
        e.fecha_creacion,
        e.fecha_envio,
        e.fecha_respuesta,
        e.comentario,
        t.titulo,
        t.descripcion,
        t.fecha_cierre_real,
        t.usuario_id,
        t.solicitante_id,
        s.nombre_completo,
        s.username,
        s.email,
        u.nombre_completo,
        u.username,
        u.email,
        uj.email,
        uj.nombre_completo,
        uj.username
"""