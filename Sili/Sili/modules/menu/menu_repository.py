from . import menu_queries
from .menu_constants import SCHEMA_NAME
from .menu_utils import fetchall_dict, fetchone_dict, safe_sql_identifier


def ensure_menu_schema(conn):
    cur = conn.cursor()
    cur.execute(menu_queries.q_menu_create_table_if_not_exists())
    cur.execute(menu_queries.q_menu_create_index_if_not_exists())
    conn.commit()


def count_menu_items(conn):
    cur = conn.cursor()
    cur.execute(menu_queries.q_menu_count_all())
    row = cur.fetchone()
    return row[0] if row else 0


def insert_menu_root(conn, label, icon, is_group, is_collaps, order_no):
    cur = conn.cursor()
    cur.execute(
        menu_queries.q_menu_insert_root(),
        (label, icon, is_group, is_collaps, order_no),
    )
    cur.execute(menu_queries.q_scope_identity())
    row = cur.fetchone()
    return row[0]


def insert_menu_child(conn, parent_id, label, endpoint, icon, permission, active_key, order_no):
    cur = conn.cursor()
    cur.execute(
        menu_queries.q_menu_insert_child(),
        (parent_id, label, endpoint, icon, permission, active_key, order_no),
    )


def insert_menu_group_child(conn, parent_id, label, icon, is_group, is_collaps, order_no):
    cur = conn.cursor()
    cur.execute(
        menu_queries.q_menu_insert_group_child(),
        (parent_id, label, icon, is_group, is_collaps, order_no),
    )
    cur.execute(menu_queries.q_scope_identity())
    row = cur.fetchone()
    return row[0]


def insert_menu_subchild(conn, parent_id, label, endpoint, permission, active_key, order_no):
    cur = conn.cursor()
    cur.execute(
        menu_queries.q_menu_insert_subchild(),
        (parent_id, label, endpoint, permission, active_key, order_no),
    )


def get_menu_items_tree_source(conn):
    cur = conn.cursor()
    return fetchall_dict(cur, menu_queries.q_menu_select_all_ordered())


def get_menu_items_admin_list(conn):
    cur = conn.cursor()
    return fetchall_dict(cur, menu_queries.q_menu_select_admin_list())


def get_menu_item_by_id(conn, item_id):
    cur = conn.cursor()
    return fetchone_dict(cur, menu_queries.q_menu_select_by_id(), (item_id,))


def get_menu_group_parents(conn):
    cur = conn.cursor()
    return fetchall_dict(cur, menu_queries.q_menu_select_group_parents())


def update_menu_item(
    conn,
    item_id,
    parent_id,
    label,
    endpoint,
    external_url,
    icon,
    order_no,
    permission,
    active_key,
    is_group,
    is_collaps,
):
    cur = conn.cursor()
    cur.execute(
        menu_queries.q_menu_update_item(),
        (
            parent_id,
            label,
            endpoint,
            external_url,
            icon,
            order_no,
            permission,
            active_key,
            is_group,
            is_collaps,
            item_id,
        ),
    )
    conn.commit()


def insert_menu_item(
    conn,
    parent_id,
    label,
    endpoint,
    external_url,
    icon,
    order_no,
    permission,
    active_key,
    is_group,
    is_collaps,
):
    cur = conn.cursor()
    cur.execute(
        menu_queries.q_menu_insert_item(),
        (
            parent_id,
            label,
            endpoint,
            external_url,
            icon,
            order_no,
            permission,
            active_key,
            is_group,
            is_collaps,
        ),
    )
    cur.execute(menu_queries.q_scope_identity())
    row = cur.fetchone()
    conn.commit()
    return row[0]


def update_menu_item_endpoint(conn, item_id, endpoint):
    cur = conn.cursor()
    cur.execute(menu_queries.q_menu_update_endpoint(), (endpoint, item_id))
    conn.commit()


def delete_menu_item(conn, item_id):
    cur = conn.cursor()
    cur.execute(menu_queries.q_menu_delete_item(), (item_id,))
    conn.commit()


def ensure_opciones_table(conn):
    cur = conn.cursor()
    cur.execute(menu_queries.q_opciones_create_table_if_not_exists())
    conn.commit()


def get_distinct_menu_permissions(conn):
    cur = conn.cursor()
    return fetchall_dict(cur, menu_queries.q_menu_distinct_permissions())


def insert_opcion_if_not_exists(conn, nombre):
    cur = conn.cursor()
    cur.execute(menu_queries.q_opcion_insert_if_not_exists(), (nombre, nombre))


def get_admin_role_id(conn):
    cur = conn.cursor()
    cur.execute(menu_queries.q_admin_role_id())
    row = cur.fetchone()
    if not row:
        return None
    return row[0]


def insert_missing_admin_permissions(conn, role_id):
    cur = conn.cursor()
    cur.execute(menu_queries.q_admin_insert_missing_perms(), (role_id, role_id))
    conn.commit()


def ensure_dynamic_crud_table(conn, table_name):
    table_name = safe_sql_identifier(table_name)
    cur = conn.cursor()

    cur.execute(
        f"""
        IF OBJECT_ID('{SCHEMA_NAME}.{table_name}', 'U') IS NULL
        BEGIN
            CREATE TABLE {SCHEMA_NAME}.{table_name} (
                id INT IDENTITY(1,1) PRIMARY KEY,
                campo1 NVARCHAR(255) NULL,
                campo2 NVARCHAR(255) NULL,
                campo3 NVARCHAR(255) NULL,
                email1 NVARCHAR(255) NULL,
                email2 NVARCHAR(255) NULL,
                created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
                updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
            );
        END
        """
    )
    conn.commit()


def get_dynamic_crud_rows(conn, table_name):
    table_name = safe_sql_identifier(table_name)
    cur = conn.cursor()
    return fetchall_dict(
        cur,
        f"""
        SELECT id, campo1, campo2, campo3, email1, email2, created_at, updated_at
        FROM {SCHEMA_NAME}.{table_name}
        ORDER BY id DESC
        """
    )


def get_dynamic_crud_item(conn, table_name, item_id):
    table_name = safe_sql_identifier(table_name)
    cur = conn.cursor()
    return fetchone_dict(
        cur,
        f"SELECT * FROM {SCHEMA_NAME}.{table_name} WHERE id = ?",
        (item_id,),
    )


def insert_dynamic_crud_item(
    conn,
    table_name,
    campo1,
    campo2,
    campo3,
    email1,
    email2,
    created_at,
    updated_at,
):
    table_name = safe_sql_identifier(table_name)
    cur = conn.cursor()
    cur.execute(
        f"""
        INSERT INTO {SCHEMA_NAME}.{table_name}
        (campo1, campo2, campo3, email1, email2, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (campo1, campo2, campo3, email1, email2, created_at, updated_at),
    )
    conn.commit()


def update_dynamic_crud_item(
    conn,
    table_name,
    item_id,
    campo1,
    campo2,
    campo3,
    email1,
    email2,
    updated_at,
):
    table_name = safe_sql_identifier(table_name)
    cur = conn.cursor()
    cur.execute(
        f"""
        UPDATE {SCHEMA_NAME}.{table_name}
        SET campo1 = ?, campo2 = ?, campo3 = ?, email1 = ?, email2 = ?, updated_at = ?
        WHERE id = ?
        """,
        (campo1, campo2, campo3, email1, email2, updated_at, item_id),
    )
    conn.commit()


def delete_dynamic_crud_item(conn, table_name, item_id):
    table_name = safe_sql_identifier(table_name)
    cur = conn.cursor()
    cur.execute(
        f"DELETE FROM {SCHEMA_NAME}.{table_name} WHERE id = ?",
        (item_id,),
    )
    conn.commit()