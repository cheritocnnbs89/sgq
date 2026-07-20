# modules/users/user_services.py
# -*- coding: utf-8 -*-
# ==========================================================
# Lógica de negocio del módulo de usuarios.
# Mantiene filtros, validaciones, CSV y carga masiva.
# ==========================================================

from datetime import datetime
from io import TextIOWrapper
import csv
import io
import sqlite3
import re

from flask import current_app

from modules.users.user_constants import (
    USERS_SORT_COLUMNS,
    DEFAULT_BULK_USER_PASSWORD,
    CSV_USUARIOS_TEMPLATE_HEADER,
    CSV_USUARIOS_TEMPLATE_SAMPLE,
    CSV_DEPARTAMENTOS_HEADER,
    CSV_DEPARTAMENTOS_SAMPLE,
)
from modules.users.user_repository import (
    save_user_cc_dist,
    load_bulk_maps,
    insert_puesto_if_missing,
    update_usuario_bulk_by_id,
    update_usuario_set_jefe,
    update_usuario_set_jefe_null,
)
from modules.users.user_security import (
    build_username_candidate,
    ensure_unique_username,
    normalize_date,
)
def get_caja_chica_values(form):
    tiene_caja_chica = 1 if form.get("tiene_caja_chica") == "1" else 0
    tipo_caja_chica = (form.get("tipo_caja_chica") or "").strip().upper()

    tipos_validos = {"C0", "DETALLE_FACTURA"}

    if not tiene_caja_chica:
        return 0, "NINGUNA"

    if tipo_caja_chica not in tipos_validos:
        raise ValueError("Debe seleccionar el tipo de caja chica.")

    return 1, tipo_caja_chica

def build_users_list_filters(q: str, estado: str, sort_col: str, sort_dir: str):
    order_expr = USERS_SORT_COLUMNS.get(sort_col, "u.id")
    order_dir = "ASC" if sort_dir == "asc" else "DESC"

    conds = []
    params = []

    if q:
        like = f"%{q}%"
        conds.append(
            "(u.username LIKE ? "
            "OR u.email LIKE ? "
            "OR COALESCE(d.nombre,'') LIKE ? "
            "OR COALESCE(uj.username,'') LIKE ?)"
        )
        params += [like, like, like, like]

    if estado == "activos":
        conds.append("u.disabled = 0")
    elif estado == "deshabilitados":
        conds.append("u.disabled <> 0")

    where_clause = ""
    if conds:
        where_clause = "WHERE " + " AND ".join(conds)

    return where_clause, params, order_expr, order_dir


def save_cc_distribution_or_error(conn, user_id: int, form):
    cc_ids = form.getlist("cc_id[]")
    cc_pcts = form.getlist("cc_pct[]")
    return save_user_cc_dist(conn, user_id, cc_ids, cc_pcts)


def cc_dist_from_post(form):
    """
    Para re-render cuando hay error en alta de usuario.
    """
    out = []
    cc_ids = form.getlist("cc_id[]")
    cc_pcts = form.getlist("cc_pct[]")

    for a, b in zip(cc_ids, cc_pcts):
        a = (a or "").strip()
        b = (b or "").strip()
        if not a and not b:
            continue
        try:
            ccid = int(a)
        except Exception:
            continue
        try:
            pct = float(b.replace(",", "."))
        except Exception:
            pct = 0.0
        out.append({"cc_id": ccid, "pct": pct})
    return out


def build_usuarios_csv_bytes(rows):
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=";")

    writer.writerow([
        "ID",
        "USERNAME",
        "NOMBRE_COMPLETO",
        "IDENTIFICACION",
        "EMAIL",
        "ROL",
        "DEPARTAMENTO",
        "AREA",
        "PUESTO",
        "EMPRESA",
        "SEXO",
        "FECHA_NACIMIENTO",
        "FECHA_INGRESO",
        "PROVINCIA",
        "CIUDAD",
        "DIRECCION",
        "JEFE_USERNAME",
        "JEFE_NOMBRE",
        "FECHA_REGISTRO",
        "TARJETA_ALIAS",
        "TARJETA_LAST4",
        "TIENE_CAJA_CHICA",
        "TIPO_CAJA_CHICA",
        "ESTADO"
    ])

    for u in rows:
        writer.writerow([
            u["id"],
            u["username"],
            u["nombre_completo"],
            u["identificacion"],
            u["email"],
            u["rol"],
            u["departamento"],
            u["area"],
            u["puesto"],
            u["empresa"],
            u["sexo"],
            u["fecha_nacimiento"],
            u["fecha_ingreso"],
            u["provincia"],
            u["ciudad"],
            u["direccion"],
            u["jefe_username"],
            u["jefe_nombre"],
            u["fecha_registro"],
            u["tarjeta_alias"],
            u["tarjeta_last4"],
            u.get("tiene_caja_chica", 0),
            u.get("tipo_caja_chica", "NINGUNA"),
            "Deshabilitado" if u["disabled"] else "Activo",
        ])

    mem = io.BytesIO()
    mem.write(output.getvalue().encode("utf-8-sig"))
    mem.seek(0)
    return mem


def build_usuarios_template_csv_bytes():
    out = io.StringIO(newline="")
    out.write(";".join(CSV_USUARIOS_TEMPLATE_HEADER) + "\n")
    out.write(";".join(CSV_USUARIOS_TEMPLATE_SAMPLE) + "\n")

    mem = io.BytesIO(out.getvalue().encode("utf-8-sig"))
    mem.seek(0)
    return mem


def build_departamentos_template_csv_bytes():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(CSV_DEPARTAMENTOS_HEADER)
    for row in CSV_DEPARTAMENTOS_SAMPLE:
        writer.writerow(row)

    mem = io.BytesIO()
    mem.write(output.getvalue().encode("utf-8-sig"))
    mem.seek(0)
    return mem


def process_departamentos_bulk_upload(conn, file_storage):
    if not file_storage or file_storage.filename == "":
        return {
            "ok": False,
            "message": "Debe seleccionar un archivo para la carga masiva.",
            "category": "danger",
        }

    creados = 0
    duplicados = 0
    vacios = 0

    cur = conn.cursor()

    try:
        wrapper = TextIOWrapper(file_storage.stream, encoding="utf-8-sig")
        reader = csv.DictReader(wrapper)

        if "nombre" not in reader.fieldnames:
            return {
                "ok": False,
                "message": 'El archivo debe tener una columna "nombre".',
                "category": "danger",
            }

        for row in reader:
            nombre = (row.get("nombre") or "").strip()
            if not nombre:
                vacios += 1
                continue

            try:
                cur.execute("INSERT INTO departamentos (nombre) VALUES (?)", (nombre,))
                creados += 1
            except Exception:
                duplicados += 1

        conn.commit()

        msg = f"Carga masiva terminada. Creados: {creados}"
        if duplicados:
            msg += f" | Duplicados/no insertados: {duplicados}"
        if vacios:
            msg += f" | Filas vacías: {vacios}"

        return {"ok": True, "message": msg, "category": "success"}

    except Exception as e:
        conn.rollback()
        current_app.logger.exception(e)
        return {
            "ok": False,
            "message": "Error procesando el archivo de carga masiva.",
            "category": "danger",
        }


def process_usuarios_bulk_upload(conn, file_storage):
    """
    Procesa el CSV con layout separado por ';'.

    - Identificador principal = CÉDULA (identificacion)
    - Si la cédula YA existe en usuarios.identificacion -> UPDATE
    - Si la cédula NO existe -> INSERT
    - Si existe columna JEFE_CODIGO -> actualiza jefe_id

    Nota:
    - La carga masiva deja por defecto:
        tiene_caja_chica = 0
        tipo_caja_chica = 'NINGUNA'
    """
    if not file_storage or file_storage.filename.strip() == "":
        return {
            "ok": False,
            "message": "Debe seleccionar un archivo CSV.",
            "category": "warning",
        }

    ident_to_id, email_to_id, dep_map, puesto_map = load_bulk_maps(conn)
    cur = conn.cursor()

    usernames_batch_usados = set()

    insertados = 0
    actualizados = 0
    dup_mail = 0
    dep_inexist = 0
    invalidos = 0
    jefes_actualizados = 0
    jefes_no_encontrados = 0
    ejemplos_error = []

    raw_text = file_storage.read().decode("utf-8-sig", errors="replace")
    lines = raw_text.splitlines()
    if not lines:
        return {"ok": False, "message": "El archivo está vacío.", "category": "warning"}

    reader = csv.reader(lines, delimiter=";")
    rows = list(reader)
    if not rows:
        return {"ok": False, "message": "No se encontraron filas.", "category": "warning"}

    header = rows[0]
    data_rows = rows[1:]

    def norm(h):
        return re.sub(r"\s+", " ", (h or "").strip().lower())

    idx_by_name = {norm(h): i for i, h in enumerate(header) if norm(h)}

    def col_index(*names):
        for name in names:
            i = idx_by_name.get(norm(name))
            if i is not None:
                return i
        return None

    idx_nombre = col_index("NOMBRE")
    idx_apellido = col_index("APELLIDO")
    idx_cedula = col_index("CEDULA", "IDENTIFICACION")
    idx_email = col_index("DIRECCION_E_MAIL", "EMAIL", "CORREO", "DIRECCION E_MAIL")
    idx_sexo = col_index("SEXO")
    idx_fnac = col_index("FECHA_NACIMIENTO", "F.NACIMIENTO", "FECHA NACIMIENTO")
    idx_fing = col_index("FECHA_INGRESO", "INGRESO", "FECHA INGRESO")
    idx_provincia = col_index("Provincia", "PROVINCIA")
    idx_ciudad = col_index("Ciudad", "CIUDAD")
    idx_dir = col_index("DESCRIPCION_DIR_1", "DIRECCION")
    idx_puesto = col_index("PUESTO", "CARGO")
    idx_depto = col_index("DEPARTAMENTO", "DEPTO", "DEPARTAMENTO/CENTRO")
    idx_empresa = col_index("EMPRESA")
    idx_jefe_cod = col_index("JEFE_CODIGO", "JEFE CODIGO", "JEFE_COD")

    required_idx = [idx_nombre, idx_apellido, idx_cedula, idx_email, idx_depto]
    if any(i is None for i in required_idx):
        return {
            "ok": False,
            "message": "El CSV no tiene todas las columnas requeridas (NOMBRE, APELLIDO, CEDULA, DIRECCION_E_MAIL, DEPARTAMENTO). Verifique el encabezado.",
            "category": "danger",
        }

    ts_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        cur.execute("BEGIN IMMEDIATE")

        for idx, cols in enumerate(data_rows, start=2):
            if not any((c or "").strip() for c in cols):
                continue

            def val(i):
                return (cols[i] or "").strip() if i is not None and i < len(cols) else ""

            nombres_raw = val(idx_nombre)
            apellidos_raw = val(idx_apellido)
            cedula = val(idx_cedula)
            email = val(idx_email)
            sexo_raw = val(idx_sexo).upper()
            fnac_raw = val(idx_fnac)
            fing_raw = val(idx_fing)
            provincia = val(idx_provincia)
            ciudad = val(idx_ciudad)
            direccion = val(idx_dir)
            puesto_nombre = val(idx_puesto)
            depto_nombre = val(idx_depto)
            empresa_txt = val(idx_empresa)

            if (not nombres_raw or not apellidos_raw or not cedula or not email or not depto_nombre):
                invalidos += 1
                if len(ejemplos_error) < 10:
                    ejemplos_error.append(f"fila {idx}: faltan campos requeridos -> {cols!r}")
                continue

            cedula = cedula.strip()
            if cedula.isdigit() and len(cedula) == 9:
                cedula = "0" + cedula

            cedula_key = cedula.lower().strip()
            email_key = email.lower().strip()

            dep_key = depto_nombre.strip().lower()
            dep_id = dep_map.get(dep_key)
            if not dep_id:
                dep_inexist += 1
                continue

            sexo_val = sexo_raw if sexo_raw in ("M", "F") else None
            fecha_nac = normalize_date(fnac_raw)
            fecha_ing = normalize_date(fing_raw)
            nombre_completo = f"{nombres_raw.strip()} {apellidos_raw.strip()}".strip()

            puesto_key = puesto_nombre.strip().lower()
            puesto_id = None
            if puesto_key:
                if puesto_key not in puesto_map:
                    try:
                        puesto_inserted = insert_puesto_if_missing(conn, puesto_nombre)
                        if puesto_inserted:
                            puesto_map[puesto_key] = puesto_inserted
                    except sqlite3.Error:
                        pass
                puesto_id = puesto_map.get(puesto_key)

            user_id_existente = ident_to_id.get(cedula_key)

            if user_id_existente:
                owner_email = email_to_id.get(email_key)
                if owner_email and owner_email != user_id_existente:
                    dup_mail += 1
                    if len(ejemplos_error) < 10:
                        ejemplos_error.append(
                            f"fila {idx}: email {email} ya usado por otro usuario (id={owner_email})"
                        )
                    continue

                try:
                    update_usuario_bulk_by_id(conn, (
                        email,
                        nombre_completo,
                        cedula,
                        sexo_val,
                        fecha_nac,
                        fecha_ing,
                        provincia,
                        ciudad,
                        direccion,
                        dep_id,
                        puesto_id,
                        user_id_existente
                    ))
                    actualizados += 1
                    ident_to_id[cedula_key] = user_id_existente
                    email_to_id[email_key] = user_id_existente
                except Exception as e:
                    current_app.logger.exception(e)
                    invalidos += 1
                    if len(ejemplos_error) < 10:
                        ejemplos_error.append(
                            f"fila {idx}: error inesperado update -> {cols!r} / {e}"
                        )
                continue

            owner_email = email_to_id.get(email_key)
            if owner_email:
                dup_mail += 1
                if len(ejemplos_error) < 10:
                    ejemplos_error.append(
                        f"fila {idx}: email {email} ya usado por usuario id={owner_email}"
                    )
                continue

            base_username = build_username_candidate(nombres_raw, apellidos_raw)
            final_username = ensure_unique_username(cur, base_username, usernames_batch_usados)

            try:
                cur.execute("""
                    INSERT INTO usuarios(
                        username, password, email, rol,
                        departamento_id, disabled,
                        failed_attempts, password_changed_at,
                        nombre_completo, identificacion, sexo,
                        fecha_nacimiento, fecha_ingreso,
                        provincia, ciudad, direccion,
                        empresa_id, area_id, puesto_id,
                        tarjeta_alias, tarjeta_last4,
                        fecha_registro,
                        tiene_caja_chica, tipo_caja_chica
                    )
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    final_username,
                    DEFAULT_BULK_USER_PASSWORD,
                    email,
                    "usuario",
                    dep_id,
                    0,
                    0,
                    ts_now,
                    nombre_completo,
                    cedula,
                    sexo_val,
                    fecha_nac,
                    fecha_ing,
                    provincia,
                    ciudad,
                    direccion,
                    None,
                    None,
                    puesto_id,
                    "",
                    "",
                    ts_now,
                    0,
                    "NINGUNA"
                ))

                new_id = cur.lastrowid
                insertados += 1
                ident_to_id[cedula_key] = new_id
                email_to_id[email_key] = new_id

            except sqlite3.IntegrityError as e:
                current_app.logger.debug(f"fila {idx} IntegrityError {e}")
                invalidos += 1
            except Exception as e:
                current_app.logger.exception(e)
                invalidos += 1
                if len(ejemplos_error) < 10:
                    ejemplos_error.append(
                        f"fila {idx}: error inesperado insert -> {cols!r} / {e}"
                    )

        if idx_jefe_cod is not None:
            for idx, cols in enumerate(data_rows, start=2):
                if not any((c or "").strip() for c in cols):
                    continue

                def val2(i):
                    return (cols[i] or "").strip() if i is not None and i < len(cols) else ""

                cedula_emp = val2(idx_cedula)
                jefe_codigo = val2(idx_jefe_cod)

                if not cedula_emp:
                    continue

                cedula_emp = cedula_emp.strip()
                if cedula_emp.isdigit() and len(cedula_emp) == 9:
                    cedula_emp = "0" + cedula_emp
                cedula_emp_key = cedula_emp.lower().strip()

                user_id = ident_to_id.get(cedula_emp_key)
                if not user_id:
                    continue

                if not jefe_codigo:
                    try:
                        update_usuario_set_jefe_null(conn, user_id)
                        jefes_actualizados += 1
                    except Exception as e:
                        current_app.logger.exception(e)
                        invalidos += 1
                    continue

                jefe_codigo = jefe_codigo.strip()
                if jefe_codigo.isdigit() and len(jefe_codigo) == 9:
                    jefe_codigo = "0" + jefe_codigo
                jefe_key = jefe_codigo.lower().strip()

                jefe_user_id = ident_to_id.get(jefe_key)
                if not jefe_user_id:
                    jefes_no_encontrados += 1
                    if len(ejemplos_error) < 10:
                        ejemplos_error.append(
                            f"fila {idx}: JEFE_CODIGO {jefe_codigo} no corresponde a ningún usuario"
                        )
                    continue

                try:
                    update_usuario_set_jefe(conn, jefe_user_id, user_id)
                    jefes_actualizados += 1
                except Exception as e:
                    current_app.logger.exception(e)
                    invalidos += 1

        conn.commit()

    except Exception as e:
        current_app.logger.exception(e)
        conn.rollback()
        return {
            "ok": False,
            "message": f"Error procesando la carga masiva: {e}",
            "category": "danger",
        }

    resumen = (
        f"Carga masiva de usuarios lista. "
        f"Insertados nuevos: {insertados} • "
        f"Actualizados (por cédula existente): {actualizados} • "
        f"Emails en uso por otro usuario: {dup_mail} • "
        f"Depto inexistente: {dep_inexist} • "
        f"Filas inválidas: {invalidos} • "
        f"Jefes actualizados: {jefes_actualizados} • "
        f"JEFE_CODIGO sin coincidencia: {jefes_no_encontrados}"
    )
    if ejemplos_error:
        resumen += " • Ejemplos errores: " + " | ".join(ejemplos_error[:5])

    return {
        "ok": True,
        "message": resumen,
        "category": "success" if (insertados or actualizados) > 0 else "warning",
    }
