import os
import sys
import sqlite3
from collections import defaultdict, deque
from datetime import datetime
from typing import Dict, Iterable, List, Sequence, Tuple

import pyodbc

# =========================
# Configuración por defecto
# =========================
SQLITE_PATH = os.getenv(
    "SQLITE_PATH",
    r"C:\Temp\bitacora.db"
)
SQLSERVER_HOST = os.getenv("SQLSERVER_HOST", "172.16.40.52")
SQLSERVER_PORT = os.getenv("SQLSERVER_PORT", "1433")
SQLSERVER_DATABASE = os.getenv("SQLSERVER_DATABASE", "SGQ_BITACORA")
SQLSERVER_USER = os.getenv("SQLSERVER_USER", "sa")
SQLSERVER_PASSWORD = os.getenv("SQLSERVER_PASSWORD", "Qu1mpAC2020$")
SQLSERVER_DRIVER = os.getenv("SQLSERVER_DRIVER", "SQL Server Native Client 11.0")
SQLSERVER_ENCRYPT = os.getenv("SQLSERVER_ENCRYPT", "yes")
SQLSERVER_TRUST_CERT = os.getenv("SQLSERVER_TRUST_CERT", "yes")
SQLSERVER_SCHEMA = os.getenv("SQLSERVER_SCHEMA", "dbo")

RELOAD_TARGET_EACH_RUN = os.getenv("RELOAD_TARGET_EACH_RUN", "yes").strip().lower() in {"1", "true", "yes", "si", "sí"}
MIGRATION_LOG_PATH = os.getenv(
    "MIGRATION_LOG_PATH",
    os.path.join(os.getcwd(), f"sqlite_to_sqlserver_skipped_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
)


# =========================
# Tablas excluidas de migración
# =========================
# Agrega aquí cualquier tabla que NO quieras migrar desde SQLite a SQL Server.
# La comparación se realiza sin distinguir mayúsculas/minúsculas.
EXCLUDED_TABLES = {
    "usuarios",
    "param_values",
    "param_groups",
    "opciones",
    "empresas",
    "menu_items",
    "roles",
    "roles_permisos",
}


def fail(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(1)


def qident(name: str) -> str:
    return f"[{name}]"


def qname(schema: str, table: str) -> str:
    return f"[{schema}].[{table}]"


def sqlite_conn() -> sqlite3.Connection:
    if not os.path.exists(SQLITE_PATH):
        fail(f"No existe SQLITE_PATH: {SQLITE_PATH}")
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def sqlserver_conn() -> pyodbc.Connection:
    if not SQLSERVER_HOST:
        fail("Falta SQLSERVER_HOST")
    if not SQLSERVER_USER:
        fail("Falta SQLSERVER_USER")
    if not SQLSERVER_PASSWORD:
        fail("Falta SQLSERVER_PASSWORD")

    conn_str = (
        f"DRIVER={{{SQLSERVER_DRIVER}}};"
        f"SERVER={SQLSERVER_HOST},{SQLSERVER_PORT};"
        f"DATABASE={SQLSERVER_DATABASE};"
        f"UID={SQLSERVER_USER};"
        f"PWD={SQLSERVER_PASSWORD};"
        f"Encrypt={SQLSERVER_ENCRYPT};"
        f"TrustServerCertificate={SQLSERVER_TRUST_CERT};"
        "MARS_Connection=No;"
    )
    conn = pyodbc.connect(conn_str)
    conn.autocommit = False
    return conn


def get_source_tables(src: sqlite3.Connection) -> List[str]:
    rows = src.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()
    return [row["name"] for row in rows]


def apply_excluded_tables(tables: Sequence[str], excluded: set[str]) -> List[str]:
    """
    Excluye tablas de la migración.

    Se usa una lista centralizada para que, en el futuro, solo tengas que
    agregar el nombre de la tabla en EXCLUDED_TABLES y el proceso siga igual.
    La comparación es case-insensitive para evitar problemas por mayúsculas/minúsculas.
    """
    excluded_norm = {t.strip().lower() for t in excluded if t and t.strip()}

    return [
        table
        for table in tables
        if table.strip().lower() not in excluded_norm
    ]


def get_excluded_found(tables: Sequence[str], excluded: set[str]) -> List[str]:
    """
    Devuelve las tablas excluidas que sí existen en SQLite origen.
    Sirve solo para imprimirlas y registrarlas en el log.
    """
    excluded_norm = {t.strip().lower() for t in excluded if t and t.strip()}
    return [
        table
        for table in tables
        if table.strip().lower() in excluded_norm
    ]


def get_topological_load_order(src: sqlite3.Connection, tables: Sequence[str]) -> List[str]:
    table_set = set(tables)
    parents: Dict[str, set] = defaultdict(set)
    children: Dict[str, set] = defaultdict(set)

    for table in tables:
        fk_rows = src.execute(f"PRAGMA foreign_key_list('{table}')").fetchall()
        for fk in fk_rows:
            parent = fk["table"]
            if parent in table_set and parent != table:
                parents[table].add(parent)
                children[parent].add(table)

    indegree = {table: len(parents[table]) for table in tables}
    queue = deque(sorted([table for table in tables if indegree[table] == 0]))
    order: List[str] = []

    while queue:
        node = queue.popleft()
        order.append(node)
        for child in sorted(children[node]):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)

    remaining = [table for table, deg in indegree.items() if deg > 0]
    if remaining:
        order.extend(sorted(remaining))

    return order


def target_table_exists(dst: pyodbc.Connection, schema: str, table: str) -> bool:
    sql = """
    SELECT 1
    FROM sys.tables t
    INNER JOIN sys.schemas s ON s.schema_id = t.schema_id
    WHERE s.name = ? AND t.name = ?
    """
    return dst.cursor().execute(sql, (schema, table)).fetchone() is not None


def get_sqlite_columns(src: sqlite3.Connection, table: str) -> List[str]:
    rows = src.execute(f"PRAGMA table_info('{table}')").fetchall()
    return [row["name"] for row in rows]


def get_sqlserver_columns(dst: pyodbc.Connection, schema: str, table: str) -> List[str]:
    sql = """
    SELECT c.name
    FROM sys.columns c
    INNER JOIN sys.tables t ON t.object_id = c.object_id
    INNER JOIN sys.schemas s ON s.schema_id = t.schema_id
    WHERE s.name = ? AND t.name = ?
    ORDER BY c.column_id
    """
    rows = dst.cursor().execute(sql, (schema, table)).fetchall()
    return [row[0] for row in rows]


def target_has_identity(dst: pyodbc.Connection, schema: str, table: str) -> bool:
    sql = """
    SELECT 1
    FROM sys.identity_columns ic
    INNER JOIN sys.tables t ON t.object_id = ic.object_id
    INNER JOIN sys.schemas s ON s.schema_id = t.schema_id
    WHERE s.name = ? AND t.name = ?
    """
    return dst.cursor().execute(sql, (schema, table)).fetchone() is not None


def get_existing_target_tables(dst: pyodbc.Connection, schema: str, source_tables: Sequence[str]) -> List[str]:
    return [table for table in source_tables if target_table_exists(dst, schema, table)]


def normalize_value(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bytes):
        return value.hex()
    text = str(value).replace("\r", "\\r").replace("\n", "\\n")
    return text


def format_row(columns: Sequence[str], row: Sequence) -> str:
    pairs = []
    for idx, col in enumerate(columns):
        pairs.append(f"{col}={normalize_value(row[idx])}")
    return " | ".join(pairs)


def log_skip(log_fh, table: str, columns: Sequence[str], row: Sequence, exc: Exception) -> None:
    msg = str(exc).strip()
    line = f"[{table}] SKIP | motivo={msg} | fila={format_row(columns, row)}"
    print(line)
    log_fh.write(line + "\n")
    log_fh.flush()


def log_info(log_fh, message: str) -> None:
    print(message)
    log_fh.write(message + "\n")
    log_fh.flush()


def disable_constraints(dst: pyodbc.Connection, schema: str, tables: Sequence[str], log_fh) -> None:
    cur = dst.cursor()
    for table in tables:
        sql = f"ALTER TABLE {qname(schema, table)} NOCHECK CONSTRAINT ALL;"
        try:
            cur.execute(sql)
            log_info(log_fh, f"[{table}] CONSTRAINTS DESHABILITADAS")
        except pyodbc.Error as exc:
            log_info(log_fh, f"[{table}] ERROR DESHABILITANDO CONSTRAINTS | motivo={exc}")
            continue
    dst.commit()


def enable_constraints(dst: pyodbc.Connection, schema: str, tables: Sequence[str], log_fh) -> Tuple[int, int]:
    cur = dst.cursor()
    ok_count = 0
    error_count = 0

    for table in tables:
        sql = f"ALTER TABLE {qname(schema, table)} WITH CHECK CHECK CONSTRAINT ALL;"
        try:
            cur.execute(sql)
            ok_count += 1
            log_info(log_fh, f"[{table}] CONSTRAINTS HABILITADAS Y VALIDADAS")
        except pyodbc.Error as exc:
            error_count += 1
            log_info(log_fh, f"[{table}] ERROR HABILITANDO CONSTRAINTS | motivo={exc}")

            # Dejar la tabla al menos con constraints habilitadas pero no validadas
            try:
                cur.execute(f"ALTER TABLE {qname(schema, table)} CHECK CONSTRAINT ALL;")
                log_info(log_fh, f"[{table}] CONSTRAINTS HABILITADAS SIN VALIDAR")
            except pyodbc.Error as exc2:
                log_info(log_fh, f"[{table}] ERROR EN CHECK SIN VALIDAR | motivo={exc2}")

            continue

    dst.commit()
    return ok_count, error_count


def delete_target_data(dst: pyodbc.Connection, schema: str, tables: Sequence[str], log_fh) -> None:
    cur = dst.cursor()
    for table in reversed(list(tables)):
        try:
            msg = f"DELETE: {schema}.{table}"
            print(msg)
            log_fh.write(msg + "\n")
            log_fh.flush()
            cur.execute(f"DELETE FROM {qname(schema, table)};")
        except pyodbc.Error as exc:
            log_info(log_fh, f"[{table}] ERROR EN DELETE | motivo={exc}")
            continue
    dst.commit()


def row_count_sqlite(src: sqlite3.Connection, table: str) -> int:
    return src.execute(f"SELECT COUNT(*) FROM '{table}'").fetchone()[0]


def row_count_sqlserver(dst: pyodbc.Connection, schema: str, table: str) -> int:
    sql = f"SELECT COUNT(*) FROM {qname(schema, table)};"
    return int(dst.cursor().execute(sql).fetchone()[0])


def iter_source_rows(src: sqlite3.Connection, table: str, columns: Sequence[str]) -> Iterable[Tuple]:
    col_sql = ", ".join([qident(col) for col in columns])
    sql = f"SELECT {col_sql} FROM {qident(table)}"
    for row in src.execute(sql):
        yield tuple(row[col] for col in columns)


def reseed_identity(dst: pyodbc.Connection, schema: str, table: str) -> None:
    cur = dst.cursor()
    cur.execute(f"SELECT ISNULL(MAX([id]), 0) FROM {qname(schema, table)};")
    max_id = int(cur.fetchone()[0] or 0)
    cur.execute(f"DBCC CHECKIDENT ('{schema}.{table}', RESEED, {max_id});")
    dst.commit()


def copy_table(src: sqlite3.Connection, dst: pyodbc.Connection, schema: str, table: str, log_fh) -> Tuple[int, int]:
    src_cols = get_sqlite_columns(src, table)
    dst_cols = get_sqlserver_columns(dst, schema, table)

    common_cols = [col for col in dst_cols if col in src_cols]
    missing_in_source = [col for col in dst_cols if col not in src_cols]
    missing_in_target = [col for col in src_cols if col not in dst_cols]

    if not common_cols:
        log_info(
            log_fh,
            f"[{table}] SIN COLUMNAS COMUNES | SQLite={src_cols} | SQLServer={dst_cols}"
        )
        return 0, 0

    if missing_in_source or missing_in_target:
        log_info(
            log_fh,
            f"[{table}] DIFERENCIA DE COLUMNAS | "
            f"comunes={common_cols} | "
            f"faltan_en_origen={missing_in_source} | "
            f"faltan_en_destino={missing_in_target}"
        )

    has_identity = target_has_identity(dst, schema, table) and ("id" in common_cols)
    column_list = ", ".join([qident(col) for col in common_cols])
    placeholders = ", ".join(["?"] * len(common_cols))
    insert_sql = f"INSERT INTO {qname(schema, table)} ({column_list}) VALUES ({placeholders})"

    cur = dst.cursor()
    inserted = 0
    skipped = 0

    if has_identity:
        cur.execute(f"SET IDENTITY_INSERT {qname(schema, table)} ON;")

    try:
        for row in iter_source_rows(src, table, src_cols):
            row_dict = {src_cols[i]: row[i] for i in range(len(src_cols))}
            filtered_row = tuple(row_dict[col] for col in common_cols)

            try:
                cur.execute(insert_sql, filtered_row)
                inserted += 1
            except pyodbc.Error as exc:
                skipped += 1
                log_skip(log_fh, table, common_cols, filtered_row, exc)
                continue

        if has_identity:
            cur.execute(f"SET IDENTITY_INSERT {qname(schema, table)} OFF;")

        dst.commit()

        if has_identity:
            reseed_identity(dst, schema, table)

        return inserted, skipped

    except Exception:
        try:
            if has_identity:
                cur.execute(f"SET IDENTITY_INSERT {qname(schema, table)} OFF;")
        except Exception:
            pass
        raise


def print_origin_summary(src: sqlite3.Connection, tables: Sequence[str]) -> None:
    tables_with_data = 0
    total_rows = 0
    for table in tables:
        count = row_count_sqlite(src, table)
        total_rows += count
        if count > 0:
            tables_with_data += 1

    print(
        f"SQLite origen: tablas={len(tables)}, "
        f"tablas_con_datos={tables_with_data}, filas_totales={total_rows}"
    )


def print_target_summary(dst: pyodbc.Connection, schema: str, tables: Sequence[str]) -> None:
    tables_with_data = 0
    total_rows = 0
    for table in tables:
        count = row_count_sqlserver(dst, schema, table)
        total_rows += count
        if count > 0:
            tables_with_data += 1

    print(
        f"SQL Server destino: tablas={len(tables)}, "
        f"tablas_con_datos={tables_with_data}, filas_totales={total_rows}"
    )


def main() -> None:
    src = sqlite_conn()
    dst = sqlserver_conn()

    try:
        source_tables_all = get_source_tables(src)
        source_tables = apply_excluded_tables(source_tables_all, EXCLUDED_TABLES)
        excluded_found = get_excluded_found(source_tables_all, EXCLUDED_TABLES)

        if excluded_found:
            print(
                "TABLAS EXCLUIDAS DE LA MIGRACIÓN:\n- "
                + "\n- ".join(sorted(excluded_found))
            )

        load_order = get_topological_load_order(src, source_tables)
        target_tables = get_existing_target_tables(dst, SQLSERVER_SCHEMA, load_order)

        missing_in_target = [table for table in load_order if table not in target_tables]

        if missing_in_target:
            print(
                "ADVERTENCIA: estas tablas existen en SQLite pero no en SQL Server. "
                "Se omitirán:\n- " + "\n- ".join(missing_in_target)
            )

        load_order = [table for table in load_order if table in target_tables]

        print("HOST:", SQLSERVER_HOST)
        print("DB:", SQLSERVER_DATABASE)
        print("RELOAD_TARGET_EACH_RUN:", RELOAD_TARGET_EACH_RUN)
        print("LOG:", MIGRATION_LOG_PATH)

        print_origin_summary(src, load_order)

        with open(MIGRATION_LOG_PATH, "w", encoding="utf-8") as log_fh:
            log_fh.write(f"SQLite origen: {SQLITE_PATH}\n")
            log_fh.write(f"SQL Server destino: {SQLSERVER_HOST}:{SQLSERVER_PORT}/{SQLSERVER_DATABASE}\n")
            log_fh.write(f"Esquema: {SQLSERVER_SCHEMA}\n")
            log_fh.write(f"Fecha: {datetime.now().isoformat()}\n")
            log_fh.write("=" * 120 + "\n")

            if excluded_found:
                log_fh.write("TABLAS EXCLUIDAS DE LA MIGRACIÓN:\n")
                for table in sorted(excluded_found):
                    log_fh.write(f"- {table}\n")
                log_fh.write("=" * 120 + "\n")

            disable_constraints(dst, SQLSERVER_SCHEMA, target_tables, log_fh)

            if RELOAD_TARGET_EACH_RUN:
                print("Limpiando tablas destino para recarga completa...")
                delete_target_data(dst, SQLSERVER_SCHEMA, target_tables, log_fh)

            grand_inserted = 0
            grand_skipped = 0

            for pos, table in enumerate(load_order, start=1):
                source_count = row_count_sqlite(src, table)
                print(f"[{pos}/{len(load_order)}] {table}: origen={source_count}")
                inserted, skipped = copy_table(src, dst, SQLSERVER_SCHEMA, table, log_fh)
                grand_inserted += inserted
                grand_skipped += skipped
                print(f"    insertados={inserted} | omitidos={skipped}")

            enabled_ok, enabled_error = enable_constraints(dst, SQLSERVER_SCHEMA, target_tables, log_fh)

            print(f"OK. Registros insertados: {grand_inserted}")
            print(f"OK. Registros omitidos: {grand_skipped}")
            print(f"Constraints validadas OK: {enabled_ok}")
            print(f"Constraints con error: {enabled_error}")
            print_target_summary(dst, SQLSERVER_SCHEMA, target_tables)
            print("Log generado en:", MIGRATION_LOG_PATH)

    except Exception:
        try:
            dst.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            src.close()
        except Exception:
            pass
        try:
            dst.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()