# -*- coding: utf-8 -*-

import time
from flask import render_template, request, redirect, url_for, flash, session

from ..db import get_db
from ..security import require_login, require_permission, has_permission
from . import roles_permisos_services as service


def register_roles_permisos_routes(app):

    @app.route("/roles-permisos", methods=["GET", "POST"], endpoint="roles_permisos")
    @require_login
    @require_permission("roles_permisos", "ver")
    def roles_permisos_view():
        t0 = time.perf_counter()
        print("\n[ROLES_PERMISOS] ===== INICIO REQUEST =====")
        print(f"[ROLES_PERMISOS] method={request.method}")
        print(f"[ROLES_PERMISOS] args_rol={request.args.get('rol')}")
        print(f"[ROLES_PERMISOS] form_rol={request.form.get('rol')}")
        print(f"[ROLES_PERMISOS] usuario_session={session.get('usuario')}")
        print(f"[ROLES_PERMISOS] rol_session={session.get('rol')}")

        conn = get_db()

        try:
            t1 = time.perf_counter()
            service.seed_default_roles(conn)
            print(f"[ROLES_PERMISOS] seed_default_roles: {(time.perf_counter() - t1) * 1000:.2f} ms")

            t2 = time.perf_counter()
            service.seed_default_opciones(conn)
            print(f"[ROLES_PERMISOS] seed_default_opciones: {(time.perf_counter() - t2) * 1000:.2f} ms")

            #t3 = time.perf_counter()
            #service.import_legacy_permisos(conn)
            #print(f"[ROLES_PERMISOS] import_legacy_permisos: {(time.perf_counter() - t3) * 1000:.2f} ms")

            selected_role = (
                request.args.get("rol")
                or request.form.get("rol")
                or ""
            ).strip()

            print(f"[ROLES_PERMISOS] selected_role recibido='{selected_role}'")

            t4 = time.perf_counter()
            role_row, roles, selected_role = service.resolve_selected_role(conn, selected_role)
            print(f"[ROLES_PERMISOS] resolve_selected_role: {(time.perf_counter() - t4) * 1000:.2f} ms")
            print(f"[ROLES_PERMISOS] selected_role final='{selected_role}'")

            if not role_row:
                print("[ROLES_PERMISOS] No se pudo resolver role_row")
                flash("No fue posible cargar los roles.", "danger")
                return render_template(
                    "roles_permisos.html",
                    roles=[],
                    selected_role="",
                    permisos={},
                    show_saved=False,
                    usuario=session.get("usuario"),
                    rol=session.get("rol"),
                    active_page="roles_permisos",
                )

            if request.method == "POST" and "save" in request.form:
                print("[ROLES_PERMISOS] Entró a POST save")

                if not has_permission(session.get("rol"), "roles_permisos", "editar"):
                    print("[ROLES_PERMISOS] Sin permiso para editar")
                    flash("No tiene permiso para editar los roles y permisos.", "danger")
                    return redirect(url_for("roles_permisos", rol=selected_role))

                t5 = time.perf_counter()
                service.save_role_permissions(conn, selected_role, request.form)
                print(f"[ROLES_PERMISOS] save_role_permissions: {(time.perf_counter() - t5) * 1000:.2f} ms")
                print(f"[ROLES_PERMISOS] TOTAL REQUEST: {(time.perf_counter() - t0) * 1000:.2f} ms")
                print("[ROLES_PERMISOS] ===== FIN REQUEST =====\n")

                return redirect(url_for("roles_permisos", rol=selected_role, saved=1))

            t6 = time.perf_counter()
            permisos = service.build_permisos_dict(conn, role_row["id"])
            print(f"[ROLES_PERMISOS] build_permisos_dict: {(time.perf_counter() - t6) * 1000:.2f} ms")
            print(f"[ROLES_PERMISOS] TOTAL REQUEST: {(time.perf_counter() - t0) * 1000:.2f} ms")
            print("[ROLES_PERMISOS] ===== FIN REQUEST =====\n")

            show_saved = request.args.get("saved") == "1"

            return render_template(
                "roles_permisos.html",
                roles=roles,
                selected_role=selected_role,
                permisos=permisos,
                show_saved=show_saved,
                usuario=session.get("usuario"),
                rol=session.get("rol"),
                active_page="roles_permisos",
            )

        finally:
            try:
                conn.close()
            except Exception:
                pass