# modules/users/__init__.py
# ==========================================================
# Paquete interno del módulo de usuarios.
# Expone el registrador HTTP principal.
# ==========================================================

from modules.users.user_http import register_user_routes
__all__ = ["register_user_routes"]