from .menu_constants import (
    MENU_TABLE,
    OPCIONES_TABLE,
    ROLES_TABLE,
    ROLES_PERMISOS_TABLE,
    SCHEMA_NAME,
)


def q_menu_create_table_if_not_exists():
    return f"""
    IF OBJECT_ID('{SCHEMA_NAME}.{MENU_TABLE}', 'U') IS NULL
    BEGIN
        CREATE TABLE {SCHEMA_NAME}.{MENU_TABLE} (
            id INT IDENTITY(1,1) PRIMARY KEY,
            parent_id INT NULL,
            label NVARCHAR(255) NOT NULL,
            endpoint NVARCHAR(255) NULL,
            external_url NVARCHAR(500) NULL,
            icon NVARCHAR(255) NULL,
            order_no INT NOT NULL DEFAULT 0,
            permission NVARCHAR(255) NULL,
            active_key NVARCHAR(255) NULL,
            is_group BIT NOT NULL DEFAULT 0,
            is_collaps BIT NOT NULL DEFAULT 0,
            CONSTRAINT UQ_menu_items_label_parent UNIQUE (label, parent_id)
        );
    END
    """


def q_menu_create_index_if_not_exists():
    return f"""
    IF NOT EXISTS (
        SELECT 1
        FROM sys.indexes
        WHERE name = 'idx_menu_parent'
          AND object_id = OBJECT_ID('{SCHEMA_NAME}.{MENU_TABLE}')
    )
    BEGIN
        CREATE INDEX idx_menu_parent
        ON {SCHEMA_NAME}.{MENU_TABLE}(parent_id, order_no);
    END
    """


def q_menu_count_all():
    return f"SELECT COUNT(*) FROM {SCHEMA_NAME}.{MENU_TABLE}"


def q_menu_insert_root():
    return f"""
    INSERT INTO {SCHEMA_NAME}.{MENU_TABLE}(label, icon, is_group, is_collaps, order_no)
    VALUES (?, ?, ?, ?, ?)
    """


def q_scope_identity():
    return "SELECT CAST(SCOPE_IDENTITY() AS INT)"


def q_menu_insert_child():
    return f"""
    INSERT INTO {SCHEMA_NAME}.{MENU_TABLE}(parent_id, label, endpoint, icon, permission, active_key, order_no)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """


def q_menu_insert_group_child():
    return f"""
    INSERT INTO {SCHEMA_NAME}.{MENU_TABLE}(parent_id, label, icon, is_group, is_collaps, order_no)
    VALUES (?, ?, ?, ?, ?, ?)
    """


def q_menu_insert_subchild():
    return f"""
    INSERT INTO {SCHEMA_NAME}.{MENU_TABLE}(parent_id, label, endpoint, permission, active_key, order_no)
    VALUES (?, ?, ?, ?, ?, ?)
    """


def q_menu_select_all_ordered():
    return f"""
    SELECT *
    FROM {SCHEMA_NAME}.{MENU_TABLE}
    ORDER BY ISNULL(parent_id, 0), order_no, id
    """


def q_menu_select_admin_list():
    return f"""
    SELECT *
    FROM {SCHEMA_NAME}.{MENU_TABLE}
    ORDER BY parent_id, order_no, id
    """


def q_menu_select_by_id():
    return f"SELECT * FROM {SCHEMA_NAME}.{MENU_TABLE} WHERE id = ?"


def q_menu_select_group_parents():
    return f"""
    SELECT id, label
    FROM {SCHEMA_NAME}.{MENU_TABLE}
    WHERE is_group = 1
    ORDER BY label
    """


def q_menu_update_item():
    return f"""
    UPDATE {SCHEMA_NAME}.{MENU_TABLE}
    SET parent_id = ?, label = ?, endpoint = ?, external_url = ?, icon = ?, order_no = ?,
        permission = ?, active_key = ?, is_group = ?, is_collaps = ?
    WHERE id = ?
    """


def q_menu_insert_item():
    return f"""
    INSERT INTO {SCHEMA_NAME}.{MENU_TABLE}
    (parent_id, label, endpoint, external_url, icon, order_no, permission, active_key, is_group, is_collaps)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """


def q_menu_update_endpoint():
    return f"UPDATE {SCHEMA_NAME}.{MENU_TABLE} SET endpoint = ? WHERE id = ?"


def q_menu_delete_item():
    return f"DELETE FROM {SCHEMA_NAME}.{MENU_TABLE} WHERE id = ?"


def q_opciones_create_table_if_not_exists():
    return f"""
    IF OBJECT_ID('{SCHEMA_NAME}.{OPCIONES_TABLE}', 'U') IS NULL
    BEGIN
        CREATE TABLE {SCHEMA_NAME}.{OPCIONES_TABLE} (
            id INT IDENTITY(1,1) PRIMARY KEY,
            nombre NVARCHAR(255) NOT NULL UNIQUE
        );
    END
    """


def q_menu_distinct_permissions():
    return f"""
    SELECT DISTINCT LTRIM(RTRIM(permission)) AS k
    FROM {SCHEMA_NAME}.{MENU_TABLE}
    WHERE LTRIM(RTRIM(ISNULL(permission, ''))) <> ''
    """


def q_opcion_insert_if_not_exists():
    return f"""
    IF NOT EXISTS (
        SELECT 1
        FROM {SCHEMA_NAME}.{OPCIONES_TABLE}
        WHERE nombre = ?
    )
    BEGIN
        INSERT INTO {SCHEMA_NAME}.{OPCIONES_TABLE}(nombre)
        VALUES (?)
    END
    """


def q_admin_role_id():
    return f"SELECT id FROM {SCHEMA_NAME}.{ROLES_TABLE} WHERE LOWER(nombre) = 'admin'"


def q_admin_insert_missing_perms():
    return f"""
    INSERT INTO {SCHEMA_NAME}.{ROLES_PERMISOS_TABLE}
        (rol_id, opcion_id, ver, crear, editar, eliminar, exportar, aprobar)
    SELECT ?, o.id, 1, 1, 1, 1, 1, 1
    FROM {SCHEMA_NAME}.{OPCIONES_TABLE} o
    WHERE NOT EXISTS (
        SELECT 1
        FROM {SCHEMA_NAME}.{ROLES_PERMISOS_TABLE} rp
        WHERE rp.rol_id = ?
          AND rp.opcion_id = o.id
    )
    """