# modules/routes_config.py
from flask import render_template, request, redirect, url_for, flash, session
from .db import get_db
from .security import require_login, require_permission, has_permission

# Intentaremos estas variantes de tabla/columnas en orden
CONFIG_CANDIDATES = [
    ("configuracion", "clave", "valor"),  # <-- tu esquema actual
    ("config",        "key",   "value"),
]


def _raw_conn(conn):
    return getattr(conn, "_conn", conn)


def _is_sqlserver_conn(conn) -> bool:
    raw = _raw_conn(conn)
    mod = getattr(raw.__class__, "__module__", "").lower()
    name = getattr(raw.__class__, "__name__", "").lower()
    text = f"{mod} {name}"
    return "pyodbc" in text or "odbc" in text


def _detect_store(conn):
    cur = conn.cursor()

    for t, k, v in CONFIG_CANDIDATES:
        if _is_sqlserver_conn(conn):
            cur.execute("""
                SELECT 1
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_NAME = ?
            """, (t,))
        else:
            cur.execute("""
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = ?
            """, (t,))

        if cur.fetchone():
            return t, k, v

    # En SQL Server no creamos tablas en runtime
    if _is_sqlserver_conn(conn):
        raise RuntimeError(
            "No existe la tabla de configuración esperada en SQL Server. "
            "Debe existir 'configuracion' o 'config'."
        )

    # Solo SQLite: autocrear si no existe
    cur.execute("""
        CREATE TABLE IF NOT EXISTS configuracion (
            clave TEXT PRIMARY KEY,
            valor TEXT
        )
    """)
    conn.commit()
    return "configuracion", "clave", "valor"


def get_cfg(key, default=""):
    conn = get_db()
    table, kcol, vcol = _detect_store(conn)
    cur = conn.cursor()

    if _is_sqlserver_conn(conn):
        cur.execute(f"""
            SELECT TOP 1 {vcol} AS val
            FROM {table}
            WHERE {kcol} = ?
        """, (key,))
    else:
        cur.execute(f"""
            SELECT {vcol} AS val
            FROM {table}
            WHERE {kcol} = ?
        """, (key,))

    row = cur.fetchone()
    return row["val"] if row and row["val"] is not None else default


def set_cfg(key, value):
    conn = get_db()
    table, kcol, vcol = _detect_store(conn)
    cur = conn.cursor()

    if _is_sqlserver_conn(conn):
        cur.execute(f"""
            SELECT TOP 1 1 AS existe
            FROM {table}
            WHERE {kcol} = ?
        """, (key,))
        row = cur.fetchone()

        if row:
            cur.execute(f"""
                UPDATE {table}
                SET {vcol} = ?
                WHERE {kcol} = ?
            """, (value, key))
        else:
            cur.execute(f"""
                INSERT INTO {table} ({kcol}, {vcol})
                VALUES (?, ?)
            """, (key, value))
    else:
        try:
            # SQLite moderno: UPSERT por clave
            cur.execute(
                f"""
                INSERT INTO {table}({kcol},{vcol})
                VALUES (?,?)
                ON CONFLICT({kcol}) DO UPDATE SET {vcol}=excluded.{vcol}
                """,
                (key, value),
            )
        except Exception:
            # Fallback si la tabla no tiene UNIQUE/PRIMARY KEY configurado
            cur.execute(f"SELECT COUNT(1) AS c FROM {table} WHERE {kcol}=?", (key,))
            row = cur.fetchone()
            c = row["c"] if row and "c" in row.keys() else (row[0] if row else 0)

            if c:
                cur.execute(f"UPDATE {table} SET {vcol}=? WHERE {kcol}=?", (value, key))
            else:
                cur.execute(f"INSERT INTO {table}({kcol},{vcol}) VALUES (?,?)", (key, value))

    conn.commit()


def register_config_routes(app):
    @app.route("/config", methods=["GET", "POST"], endpoint="config")
    @require_login
    @require_permission("parametros", "ver")
    def config_view():
        if request.method == "POST":
            if not has_permission(session.get("rol"), "parametros", "editar"):
                flash("No tiene permiso para editar los parámetros.", "danger")
                return redirect(url_for("config"))

            # NOMBRES EXACTOS que usa tu plantilla config.html
            keys = [
                "smtp_host", "smtp_port", "smtp_user", "smtp_pass",
                "smtp_from", "inactivity_minutes", "edit_minutes",
            ]
            data = {k: (request.form.get(k) or "").strip() for k in keys}

            # Guardar con nombres actuales de tu plantilla
            for k, v in data.items():
                set_cfg(k, v)

            # Guardar alias legacy (por si otros módulos los leen)
            legacy = {
                "smtp_server":             data["smtp_host"],
                "smtp_password":           data["smtp_pass"],
                "session_timeout_minutes": data["inactivity_minutes"],
                "task_edit_minutes":       data["edit_minutes"],
            }
            for k, v in legacy.items():
                set_cfg(k, v)

            flash("Parámetros guardados.", "success")
            return redirect(url_for("config"))

        # GET: cargar usando tus claves, con fallback a legacy
        config = {
            "smtp_host":          get_cfg("smtp_host", get_cfg("smtp_server", "")),
            "smtp_port":          get_cfg("smtp_port", ""),
            "smtp_user":          get_cfg("smtp_user", ""),
            "smtp_pass":          get_cfg("smtp_pass", get_cfg("smtp_password", "")),
            "smtp_from":          get_cfg("smtp_from", ""),
            "inactivity_minutes": get_cfg("inactivity_minutes", get_cfg("session_timeout_minutes", "")),
            "edit_minutes":       get_cfg("edit_minutes", get_cfg("task_edit_minutes", "")),
        }

        # Log útil por si hay dudas de tabla detectada
        try:
            conn = get_db()
            table, kcol, vcol = _detect_store(conn)
            app.logger.info(
                "CONFIG store: %s (%s, %s) | DB=%s",
                table, kcol, vcol, app.config.get("DATABASE")
            )
        except Exception:
            pass

        return render_template(
            "config.html",
            config=config,
            usuario=session.get("usuario"),
            rol=session.get("rol"),
            active_page="config",
        )


def register_seguridad_routes(app):

    @app.route("/politicas_seguridad", methods=["GET", "POST"], endpoint="politicas_seguridad")
    @require_login
    @require_permission("seguridad", "ver")
    def politicas_seguridad():
        # ----- POST: guardar cambios -----
        if request.method == "POST":
            if not has_permission(session.get("rol"), "seguridad", "editar"):
                flash("No tiene permiso para modificar estas políticas.", "warning")
                return redirect(url_for("politicas_seguridad"))

            numeric_keys = [
                "username_min_length",
                "login_max_attempts",
                "password_min_length",
                "password_max_length",
                "password_reminder_days",
                "password_validity_days",
            ]
            for k in numeric_keys:
                val = (request.form.get(k) or "").strip()
                if val == "":
                    val = "0"
                set_cfg(k, val)

            def flag(field):
                raw = request.form.get(field)
                return "1" if raw in ("on", "1", "true", "True") else "0"

            set_cfg("password_allow_symbols",    flag("password_allow_symbols"))
            set_cfg("password_allow_numbers",    flag("password_allow_numbers"))
            set_cfg("password_allow_lowercase",  flag("password_allow_lowercase"))
            set_cfg("password_allow_uppercase",  flag("password_allow_uppercase"))

            try:
                min_len = int(get_cfg("password_min_length", "8"))
                max_len = int(get_cfg("password_max_length", "32"))
                if min_len > max_len:
                    flash("La longitud mínima no puede ser mayor que la máxima.", "danger")
                    return redirect(url_for("politicas_seguridad"))

                if (
                    get_cfg("password_allow_symbols", "0")   == "0" and
                    get_cfg("password_allow_numbers", "0")   == "0" and
                    get_cfg("password_allow_lowercase", "0") == "0" and
                    get_cfg("password_allow_uppercase", "0") == "0"
                ):
                    flash("Debe permitirse al menos un tipo de carácter en la contraseña.", "danger")
                    return redirect(url_for("politicas_seguridad"))

            except ValueError:
                flash("Valores inválidos en la política de contraseñas.", "danger")
                return redirect(url_for("politicas_seguridad"))

            return redirect(url_for("politicas_seguridad", saved=1))

        # ----- GET: cargar valores actuales y pintar el form -----
        config = {
            "username_min_length":      get_cfg("username_min_length", "6"),
            "login_max_attempts":       get_cfg("login_max_attempts", "5"),
            "password_min_length":      get_cfg("password_min_length", "8"),
            "password_max_length":      get_cfg("password_max_length", "15"),
            "password_reminder_days":   get_cfg("password_reminder_days", "20"),
            "password_validity_days":   get_cfg("password_validity_days", "60"),
            "password_allow_symbols":   get_cfg("password_allow_symbols", "1"),
            "password_allow_numbers":   get_cfg("password_allow_numbers", "1"),
            "password_allow_lowercase": get_cfg("password_allow_lowercase", "1"),
            "password_allow_uppercase": get_cfg("password_allow_uppercase", "1"),
        }

        show_saved = (request.args.get("saved") == "1")

        return render_template(
            "politicas_seguridad.html",
            config=config,
            show_saved=show_saved,
            usuario=session.get("usuario"),
            rol=session.get("rol"),
            active_page="seguridad",
        )