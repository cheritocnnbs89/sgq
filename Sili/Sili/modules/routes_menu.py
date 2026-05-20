from modules.menu.menu_http import menu_bp, register_menu_routes
from modules.menu.menu_services import (
    DYNAMIC_CRUD,
    ensure_admin_full_perms,
    fetch_menu_tree,
    initialize_menu_module,
    seed_menu_if_empty,
    sync_permissions_from_menu,
)

__all__ = [
    "menu_bp",
    "register_menu_routes",
    "DYNAMIC_CRUD",
    "initialize_menu_module",
    "seed_menu_if_empty",
    "fetch_menu_tree",
    "sync_permissions_from_menu",
    "ensure_admin_full_perms",
]