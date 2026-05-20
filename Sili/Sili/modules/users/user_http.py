# modules/users/user_http.py
# -*- coding: utf-8 -*-
# ==========================================================
# Capa HTTP del módulo de usuarios.
# Registra rutas, renderiza vistas y delega a repository/services.
# ==========================================================

from datetime import datetime
import sqlite3
import csv
import io

from flask import (
    render_template, request, redirect, url_for, flash,
    session, current_app, send_file
)

from ..db import get_db, get_config_value
from ..config import ROLES
from ..security import require_login, require_permission, check_password_policy
#from modules.users_schema_helper import     ensure_users_extra_schema

from modules.users.user_repository import (
        #ensure_usuarios_cc_schema,
    get_roles_from_db,
    load_centros_costo_from_params,
    load_user_cc_dist,
    get_usuario_for_edit,
    load_user_form_combos,
    load_empresas_for_nuevo_usuario,
    load_jefes_for_list,
    get_usuario_for_delete,
    check_user_delete_dependencies,
    delete_usuario_safe,
    update_usuario_con_password,
    update_usuario_sin_password,
    username_exists,
    email_exists,
    insert_usuario,
    get_users_report_rows,
    update_jefe_masivo,
    insert_departamento,
    get_departamentos_list,
    get_departamento_by_id,
    update_departamento,
    delete_departamento,
    insert_area,
    get_areas_list,
    get_organigrama_rows,
)
from modules.users.user_services import (
    build_users_list_filters,
    save_cc_distribution_or_error,
    cc_dist_from_post,
    build_usuarios_csv_bytes,
    build_usuarios_template_csv_bytes,
    build_departamentos_template_csv_bytes,
    process_departamentos_bulk_upload,
    process_usuarios_bulk_upload,
        get_caja_chica_values,

)



def register_user_routes(app):
    # =========================
    # LISTA DE USUARIOS
    # =========================
    @app.route("/usuarios", methods=["GET"], endpoint="usuarios")
    @require_login
    @require_permission("usuarios", "ver")
    def usuarios_list():
        q = (request.args.get("q") or "").strip()
        estado = (request.args.get("estado") or "activos").strip().lower()
        sort_col = (request.args.get("sort") or "id").strip().lower()
        sort_dir = (request.args.get("dir") or "desc").strip().lower()

        where_clause, params, order_expr, order_dir = build_users_list_filters(
            q, estado, sort_col, sort_dir
        )

        conn = get_db()
            #ensure_users_extra_schema(conn)
        cur = conn.cursor()

        sql = f"""
            SELECT
                u.id,
                u.username,
                u.email,
                u.rol,
                u.disabled,
                u.departamento_id,
                COALESCE(d.nombre,'') AS departamento,
                u.fecha_registro,
                u.jefe_id,
                COALESCE(uj.username, '')        AS jefe_username,
                COALESCE(u.nombre_completo, '')  AS nombre_completo,
                COALESCE(u.identificacion, '')   AS identificacion,
                COALESCE(uj.nombre_completo, '') AS jefe_nombre
            FROM usuarios u
            LEFT JOIN departamentos d ON d.id = u.departamento_id
            LEFT JOIN usuarios uj ON uj.id = u.jefe_id
            {where_clause}
            ORDER BY {order_expr} {order_dir}
        """

        cur.execute(sql, params)
        usuarios = cur.fetchall()

        jefes = load_jefes_for_list(conn)
        conn.close()

        return render_template(
            "usuarios.html",
            usuarios=usuarios,
            jefes=jefes,
            q=q,
            estado=estado,
            sort=sort_col,
            dir=sort_dir,
            usuario=session.get("usuario"),
            rol=session.get("rol"),
            permissions=session.get("permissions", {}),
            active_page="usuarios"
        )

    # =========================
    # EDITAR USUARIO
    # =========================
    # =========================
    # EDITAR USUARIO
    # =========================
    @app.route("/usuarios/<int:user_id>/editar", methods=["GET", "POST"], endpoint="editar_usuario")
    @require_login
    @require_permission("usuarios", "editar")
    def editar_usuario(user_id):
        conn = get_db()
        cur = conn.cursor()

        u = get_usuario_for_edit(conn, user_id)

        if not u:
            conn.close()
            flash("Usuario no encontrado.", "warning")
            return redirect(url_for("usuarios"))

        roles_db = get_roles_from_db(conn, list(ROLES))

        centros_costo = load_centros_costo_from_params(conn)
        cc_dist = load_user_cc_dist(conn, user_id)

        if request.method == "POST":
            username = (request.form.get("username") or "").strip()
            email = (request.form.get("email") or "").strip()
            rol = (request.form.get("rol") or "").strip().lower()
            password = (request.form.get("password") or "").strip()

            dept_raw = request.form.get("departamento_id")
            disabled_raw = request.form.get("disabled", "0")
            cuenta_contable_raw = request.form.get("cuenta_contable_id")

            nombre_completo = (request.form.get("nombre_completo") or "").strip()
            identificacion = (request.form.get("identificacion") or "").strip()
            sexo = (request.form.get("sexo") or "").strip().upper() or None
            fecha_nac = (request.form.get("fecha_nacimiento") or "").strip() or None
            fecha_ing = (request.form.get("fecha_ingreso") or "").strip() or None
            provincia = (request.form.get("provincia") or "").strip()
            ciudad = (request.form.get("ciudad") or "").strip()
            direccion = (request.form.get("direccion") or "").strip()

            empresa_id_raw = request.form.get("empresa_id")
            area_id_raw = request.form.get("area_id")
            puesto_id_raw = request.form.get("puesto_id")

            tarj_alias = (request.form.get("tarjeta_alias") or "").strip()
            tarj_last4 = (request.form.get("tarjeta_last4") or "").strip()

            jefe_id_raw = request.form.get("jefe_id")
            try:
                jefe_id = int(jefe_id_raw) if jefe_id_raw else None
            except (TypeError, ValueError):
                jefe_id = None

            if jefe_id == user_id:
                jefe_id = None

            if not username or not email or rol not in roles_db:
                conn.close()
                flash("Datos de usuario inválidos.", "danger")
                return redirect(url_for("editar_usuario", user_id=user_id))

            try:
                min_user_len = int(get_config_value("username_min_length", "6"))
            except ValueError:
                min_user_len = 6

            if len(username) < min_user_len:
                conn.close()
                flash(f"El nombre de usuario debe tener al menos {min_user_len} caracteres.", "warning")
                return redirect(url_for("editar_usuario", user_id=user_id))

            if rol == "admin":
                dept_id = None
            else:
                try:
                    dept_id = int(dept_raw or 0)
                    if dept_id == 0:
                        raise ValueError()
                except (TypeError, ValueError):
                    conn.close()
                    flash("Debe seleccionar un departamento.", "warning")
                    return redirect(url_for("editar_usuario", user_id=user_id))

            try:
                disabled_val = 1 if int(disabled_raw) else 0
            except ValueError:
                disabled_val = 0

            try:
                cc_id = int(cuenta_contable_raw or 0) or None
            except (TypeError, ValueError):
                cc_id = None

            try:
                empresa_id = int(empresa_id_raw or 0) or None
            except (TypeError, ValueError):
                empresa_id = None

            try:
                area_id = int(area_id_raw or 0) or None
            except (TypeError, ValueError):
                area_id = None

            try:
                puesto_id = int(puesto_id_raw or 0) or None
            except (TypeError, ValueError):
                puesto_id = None

            codigo_sap = (request.form.get("codigo_sap") or "").strip()

            try:
                tiene_caja_chica, tipo_caja_chica = get_caja_chica_values(request.form)
            except ValueError as e:
                conn.close()
                flash(str(e), "warning")
                return redirect(url_for("editar_usuario", user_id=user_id))

            try:
                if password:
                    ok, msg = check_password_policy(password)
                    if not ok:
                        conn.close()
                        flash(msg, "warning")
                        return redirect(url_for("editar_usuario", user_id=user_id))

                    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    update_usuario_con_password(conn, (
                        username,
                        email,
                        rol,
                        dept_id,
                        password,
                        disabled_val,
                        cc_id,
                        ts,
                        nombre_completo,
                        identificacion,
                        sexo,
                        fecha_nac,
                        fecha_ing,
                        provincia,
                        ciudad,
                        direccion,
                        empresa_id,
                        area_id,
                        puesto_id,
                        tarj_alias,
                        tarj_last4,
                        jefe_id,
                        tiene_caja_chica,
                        tipo_caja_chica,
                        codigo_sap,
                        user_id
                    ))

                else:
                    update_usuario_sin_password(conn, (
                        username,
                        email,
                        rol,
                        dept_id,
                        disabled_val,
                        cc_id,
                        nombre_completo,
                        identificacion,
                        sexo,
                        fecha_nac,
                        fecha_ing,
                        provincia,
                        ciudad,
                        direccion,
                        empresa_id,
                        area_id,
                        puesto_id,
                        tarj_alias,
                        tarj_last4,
                        jefe_id,
                        tiene_caja_chica,
                        tipo_caja_chica,
                        codigo_sap,
                        user_id
                    ))

                ok_cc, msg_cc = save_cc_distribution_or_error(conn, user_id, request.form)
                if not ok_cc:
                    conn.rollback()
                    conn.close()
                    flash(msg_cc, "warning")
                    return redirect(url_for("editar_usuario", user_id=user_id))

                conn.commit()
                flash("Usuario actualizado correctamente.", "success")

            except sqlite3.IntegrityError as e:
                conn.rollback()
                current_app.logger.exception(e)
                msg = str(e).lower()

                if "unique" in msg or "constraint" in msg:
                    flash("El nombre de usuario o el correo ya existen.", "danger")
                else:
                    flash("No se pudo actualizar el usuario (restricción de integridad).", "danger")

            except sqlite3.OperationalError as e:
                conn.rollback()
                current_app.logger.exception(e)
                flash(f"Error de esquema/tabla: {e}. Ejecute migraciones.", "danger")

            except Exception as e:
                conn.rollback()
                current_app.logger.exception(e)
                flash("Error no previsto al actualizar el usuario.", "danger")

            finally:
                try:
                    conn.close()
                except Exception:
                    pass

            return redirect(url_for("usuarios"))

        departamentos, areas, puestos, empresas, jefes = load_user_form_combos(conn)

        conn.close()
        return render_template(
            "editar_usuario.html",
            u=u,
            departamentos=departamentos,
            roles=roles_db,
            areas=areas,
            puestos=puestos,
            empresas=empresas,
            jefes=jefes,
            centros_costo=centros_costo,
            cc_dist=cc_dist,
            usuario=session["usuario"],
            rol=session["rol"],
            active_page="usuarios",
        )
    # =========================
    # ELIMINAR USUARIO
    # =========================
    @app.route("/usuarios/<int:user_id>/eliminar", methods=["POST"], endpoint="usuarios_eliminar")
    @require_login
    @require_permission("usuarios", "eliminar")
    def usuarios_eliminar(user_id):
        conn = get_db()
        u = get_usuario_for_delete(conn, user_id)

        if not u:
            conn.close()
            flash("Usuario no encontrado.", "warning")
            return redirect(url_for("usuarios"))

        try:
            my_id = int(session.get("usuario_id") or 0)
        except Exception:
            my_id = 0

        if my_id and my_id == user_id:
            conn.close()
            flash("No puedes eliminar tu propio usuario.", "warning")
            return redirect(url_for("usuarios"))

        if (u["rol"] or "").strip().lower() == "admin":
            conn.close()
            flash("No se puede eliminar un usuario con rol ADMIN. Deshabilítalo en su lugar.", "warning")
            return redirect(url_for("usuarios"))

        total_usos, detalles = check_user_delete_dependencies(conn, user_id)
        if total_usos > 0:
            conn.close()
            flash(
                f"No se puede eliminar el usuario '{u['username']}' porque tiene registros relacionados: "
                + (" / ".join(detalles) if detalles else f"{total_usos} movimientos"),
                "danger"
            )
            return redirect(url_for("usuarios"))

        try:
            delete_usuario_safe(conn, user_id)
            conn.commit()
            flash(f"Usuario '{u['username']}' eliminado correctamente.", "success")
        except Exception as e:
            conn.rollback()
            current_app.logger.exception(e)
            flash("No se pudo eliminar el usuario (error de base de datos).", "danger")
        finally:
            conn.close()

        return redirect(url_for("usuarios"))

    # =========================
    # NUEVO USUARIO
    # =========================
    @app.route("/usuarios/nuevo", methods=["GET", "POST"], endpoint="nuevo_usuario")
    @require_login
    @require_permission("usuarios", "crear")
    def nuevo_usuario():
        conn = get_db()
        cur = conn.cursor()

        roles_db = get_roles_from_db(conn, list(ROLES))
        centros_costo = load_centros_costo_from_params(conn)

        if request.method != "POST":
            departamentos, areas, puestos, empresas, jefes = load_user_form_combos(conn)

            conn.close()

            return render_template(
                "nuevo_usuario.html",
                departamentos=departamentos,
                roles=roles_db,
                areas=areas,
                puestos=puestos,
                empresas=empresas,
                jefes=jefes,
                centros_costo=centros_costo,
                cc_dist=[],
                usuario=session.get("usuario"),
                rol=session.get("rol"),
                active_page="usuarios",
            )

        form = dict(request.form)

        username = (form.get("username") or "").strip()
        email = (form.get("email") or "").strip()
        rol = (form.get("rol") or "").strip().lower()
        password = (form.get("password") or "").strip()

        dept_raw = form.get("departamento_id")
        disabled_raw = form.get("disabled", "0")

        nombre_completo = (form.get("nombre_completo") or "").strip()
        identificacion = (form.get("identificacion") or "").strip()
        sexo = (form.get("sexo") or "").strip().upper() or None
        fecha_nac = (form.get("fecha_nacimiento") or "").strip() or None
        fecha_ing = (form.get("fecha_ingreso") or "").strip() or None
        provincia = (form.get("provincia") or "").strip()
        ciudad = (form.get("ciudad") or "").strip()
        direccion = (form.get("direccion") or "").strip()

        empresa_id_raw = form.get("empresa_id")
        area_id_raw = form.get("area_id")
        puesto_id_raw = form.get("puesto_id")

        tarj_alias = (form.get("tarjeta_alias") or "").strip()
        tarj_last4 = (form.get("tarjeta_last4") or "").strip()

        jefe_id_raw = form.get("jefe_id")
        try:
            jefe_id = int(jefe_id_raw) if jefe_id_raw else None
        except (TypeError, ValueError):
            jefe_id = None

        try:
            min_user_len = int(get_config_value("username_min_length", "6"))
        except ValueError:
            min_user_len = 6

        try:
            disabled_val = 1 if int(disabled_raw) else 0
        except ValueError:
            disabled_val = 0

        if rol == "admin":
            dept_id = None
        else:
            try:
                dept_id = int(dept_raw or 0)
                if dept_id == 0:
                    raise ValueError()
            except (TypeError, ValueError):
                dept_id = None

        try:
            empresa_id = int(empresa_id_raw or 0) or None
        except (TypeError, ValueError):
            empresa_id = None

        try:
            area_id = int(area_id_raw or 0) or None
        except (TypeError, ValueError):
            area_id = None

        try:
            puesto_id = int(puesto_id_raw or 0) or None
        except (TypeError, ValueError):
            puesto_id = None

        try:
            tiene_caja_chica, tipo_caja_chica = get_caja_chica_values(request.form)
        except ValueError as e:
            flash(str(e), "warning")

            departamentos, areas, puestos, empresas, jefes = load_user_form_combos(conn)
            cc_dist_try = cc_dist_from_post(request.form)

            conn.close()

            return render_template(
                "nuevo_usuario.html",
                departamentos=departamentos,
                roles=roles_db,
                areas=areas,
                puestos=puestos,
                empresas=empresas,
                jefes=jefes,
                centros_costo=centros_costo,
                cc_dist=cc_dist_try,
                form=form,
                usuario=session.get("usuario"),
                rol=session.get("rol"),
                active_page="usuarios",
            )

        cc_dist_try = cc_dist_from_post(request.form)

        if not username or len(username) < min_user_len:
            flash(f"El nombre de usuario debe tener al menos {min_user_len} caracteres.", "warning")

        elif not email:
            flash("El correo es obligatorio.", "warning")

        elif rol not in roles_db:
            flash("Rol inválido.", "danger")

        elif not password:
            flash("La contraseña es obligatoria.", "warning")

        elif rol != "admin" and not dept_id:
            flash("Debe seleccionar un departamento.", "warning")

        else:
            ok, msg = check_password_policy(password)

            if not ok:
                flash(msg, "warning")

            elif username_exists(conn, username):
                flash("El nombre de usuario ya existe.", "danger")

            elif email_exists(conn, email):
                flash("El correo ya existe.", "danger")

            else:
                try:
                    ts_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    new_id = insert_usuario(conn, (
                        username,
                        password,
                        email,
                        rol,
                        dept_id,
                        disabled_val,
                        0,
                        ts_now,
                        nombre_completo,
                        identificacion,
                        sexo,
                        fecha_nac,
                        fecha_ing,
                        provincia,
                        ciudad,
                        direccion,
                        empresa_id,
                        area_id,
                        puesto_id,
                        tarj_alias,
                        tarj_last4,
                        ts_now,
                        jefe_id,
                        tiene_caja_chica,
                        tipo_caja_chica
                    ))

                    ok_cc, msg_cc = save_cc_distribution_or_error(conn, new_id, request.form)

                    if not ok_cc:
                        conn.rollback()
                        flash(msg_cc, "warning")
                    else:
                        conn.commit()
                        conn.close()
                        flash("Usuario creado correctamente.", "success")
                        return redirect(url_for("usuarios"))

                except sqlite3.IntegrityError as e:
                    conn.rollback()
                    current_app.logger.exception(e)
                    flash("No se pudo crear el usuario (restricción de integridad).", "danger")

                except sqlite3.Error as e:
                    conn.rollback()
                    current_app.logger.exception(e)
                    flash(f"Error de base de datos: {e}", "danger")

                except Exception as e:
                    conn.rollback()
                    current_app.logger.exception(e)
                    flash(f"Ocurrió un error al crear el usuario: {e}", "danger")

        departamentos, areas, puestos, empresas, jefes = load_user_form_combos(conn)

        conn.close()

        return render_template(
            "nuevo_usuario.html",
            departamentos=departamentos,
            roles=roles_db,
            areas=areas,
            puestos=puestos,
            empresas=empresas,
            jefes=jefes,
            centros_costo=centros_costo,
            cc_dist=cc_dist_try,
            form=form,
            usuario=session.get("usuario"),
            rol=session.get("rol"),
            active_page="usuarios",
        )
    # =========================
    # REPORTE COMPLETO CSV
    # =========================
    @app.route("/usuarios/reporte.csv", methods=["GET"], endpoint="usuarios_reporte_csv")
    @require_login
    @require_permission("usuarios", "ver")
    def usuarios_reporte_csv():
        conn = get_db()
        rows = get_users_report_rows(conn)
        conn.close()

        mem = build_usuarios_csv_bytes(rows)

        return send_file(
            mem,
            mimetype="text/csv",
            as_attachment=True,
            download_name=f"reporte_usuarios_{datetime.now().strftime('%Y%m%d')}.csv"
        )

    @app.route("/usuarios/asignar-jefe", methods=["POST"], endpoint="usuarios_asignar_jefe")
    @require_login
    @require_permission("usuarios", "editar")
    def usuarios_asignar_jefe():
        jefe_id = request.form.get("jefe_id")
        ids = request.form.getlist("user_ids")

        if not jefe_id or not ids:
            flash("Debe seleccionar al menos un usuario y un jefe.", "warning")
            return redirect(url_for("usuarios"))

        conn = get_db()
        try:
            update_jefe_masivo(conn, int(jefe_id), [int(x) for x in ids])
            conn.commit()
            flash(f"Jefe asignado a {len(ids)} usuario(s).", "success")
        except Exception as e:
            conn.rollback()
            current_app.logger.exception(e)
            flash("No se pudo asignar el jefe masivamente.", "danger")
        finally:
            conn.close()

        return redirect(url_for("usuarios"))

    # =========================
    # BULK: PLANTILLA USUARIOS
    # =========================
    @app.route("/usuarios/plantilla.csv", methods=["GET"], endpoint="usuarios_bulk_template")
    @require_login
    @require_permission("usuarios", "ver")
    def usuarios_bulk_template():
        mem = build_usuarios_template_csv_bytes()
        return send_file(
            mem,
            mimetype="text/csv",
            as_attachment=True,
            download_name="plantilla_usuarios.csv"
        )

    # =========================
    # BULK: SUBIR CSV USUARIOS
    # =========================
    @app.route("/usuarios/bulk", methods=["POST"], endpoint="usuarios_bulk_upload")
    @require_login
    @require_permission("usuarios", "crear")
    def usuarios_bulk_upload():
        file = request.files.get("archivo")
        conn = get_db()
            #ensure_users_extra_schema(conn)

        result = process_usuarios_bulk_upload(conn, file)
        conn.close()

        flash(result["message"], result["category"])
        return redirect(url_for("usuarios"))

    # =========================
    # DEPARTAMENTOS
    # =========================
    @app.route("/departamentos", methods=["GET", "POST"])
    @require_login
    @require_permission("departamentos", "ver")
    def departamentos():
        conn = get_db()
        if request.method == "POST":
            nombre = (request.form.get("nombre") or "").strip()
            if not nombre:
                flash("El nombre del departamento es obligatorio.", "danger")
                return redirect(url_for("departamentos"))
            try:
                insert_departamento(conn, nombre)
                conn.commit()
                flash("Departamento creado correctamente.", "success")
            except Exception as e:
                current_app.logger.exception(e)
                flash("El nombre de departamento ya existe.", "danger")

        lista = get_departamentos_list(conn)
        conn.close()
        return render_template(
            "departamentos.html",
            departamentos=lista,
            usuario=session["usuario"],
            rol=session["rol"],
            active_page="departamentos"
        )

    @app.route("/departamentos/<int:dep_id>/editar", methods=["GET", "POST"])
    @require_login
    @require_permission("departamentos", "editar")
    def editar_departamento(dep_id):
        conn = get_db()
        d = get_departamento_by_id(conn, dep_id)
        if not d:
            conn.close()
            flash("Departamento no encontrado.", "warning")
            return redirect(url_for("departamentos"))

        if request.method == "POST":
            nombre = (request.form.get("nombre") or "").strip()
            if not nombre:
                flash("El nombre del departamento es obligatorio.", "danger")
                return redirect(url_for("editar_departamento", dep_id=dep_id))
            try:
                update_departamento(conn, dep_id, nombre)
                conn.commit()
                flash("Departamento actualizado correctamente.", "success")
            except Exception as e:
                current_app.logger.exception(e)
                flash("El nombre de departamento ya existe.", "danger")
            finally:
                conn.close()
            return redirect(url_for("departamentos"))

        conn.close()
        return render_template(
            "editar_departamento.html",
            departamento=d,
            usuario=session["usuario"],
            rol=session["rol"],
            active_page="departamentos"
        )

    @app.route("/departamentos/<int:dep_id>/eliminar", methods=["POST"])
    @require_login
    @require_permission("departamentos", "eliminar")
    def eliminar_departamento(dep_id):
        conn = get_db()
        try:
            delete_departamento(conn, dep_id)
            conn.commit()
            flash("Departamento eliminado.", "success")
        except Exception as e:
            current_app.logger.exception(e)
            flash("No se pudo eliminar el departamento (puede estar en uso).", "danger")
        finally:
            conn.close()
        return redirect(url_for("departamentos"))

    @app.route("/departamentos/nuevo", methods=["GET", "POST"], endpoint="nuevo_departamento")
    @require_login
    @require_permission("departamentos", "crear")
    def nuevo_departamento():
        if request.method == "POST":
            nombre = (request.form.get("nombre") or "").strip()
            if not nombre:
                flash("El nombre del departamento es obligatorio.", "danger")
                return redirect(url_for("nuevo_departamento"))

            conn = get_db()
            try:
                insert_departamento(conn, nombre)
                conn.commit()
                flash("Departamento creado correctamente.", "success")
                return redirect(url_for("departamentos"))
            except Exception as e:
                current_app.logger.exception(e)
                flash("El nombre de departamento ya existe.", "danger")
            finally:
                conn.close()

        return render_template(
            "nuevo_departamento.html",
            usuario=session.get("usuario"),
            rol=session.get("rol"),
            active_page="departamentos"
        )

    @app.route("/departamentos/bulk", methods=["POST"], endpoint="departamentos_bulk")
    @require_login
    @require_permission("departamentos", "editar")
    def departamentos_bulk():
        file = request.files.get("archivo")
        conn = get_db()

        result = process_departamentos_bulk_upload(conn, file)
        flash(result["message"], result["category"])

        conn.close()
        return redirect(url_for("departamentos"))

    @app.route("/departamentos/bulk/template", methods=["GET"], endpoint="departamentos_bulk_template")
    @require_login
    @require_permission("departamentos", "ver")
    def departamentos_bulk_template():
        mem = build_departamentos_template_csv_bytes()
        return send_file(
            mem,
            mimetype="text/csv",
            as_attachment=True,
            download_name="plantilla_departamentos.csv"
        )

    # =========================
    # ORGANIGRAMA
    # =========================
    @app.route("/organigrama", methods=["GET"])
    @require_login
    @require_permission("usuarios", "ver")
    def organigrama():
        conn = get_db()
        rows = get_organigrama_rows(conn)
        conn.close()

        roots_flat = rows

        return render_template(
            "organigrama.html",
            roots_flat=roots_flat,
            active_page="organigrama"
        )

    # =========================
    # AREAS
    # =========================
    @app.route("/areas", methods=["GET", "POST"], endpoint="areas")
    @require_login
    @require_permission("areas", "ver")
    def areas():
        conn = get_db()
            #ensure_users_extra_schema(conn)

        if request.method == "POST":
            nombre = (request.form.get("nombre") or "").strip()
            if not nombre:
                flash("Nombre requerido.", "warning")
                return redirect(url_for("areas"))
            try:
                insert_area(conn, nombre)
                conn.commit()
                flash("Área creada.", "success")
            except Exception as e:
                current_app.logger.exception(e)
                flash("El nombre ya existe.", "danger")

        lista = get_areas_list(conn)
        conn.close()
        return render_template("areas.html", areas=lista, active_page="areas")