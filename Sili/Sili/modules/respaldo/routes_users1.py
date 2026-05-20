# modules/routes_users.py
# -*- coding: utf-8 -*-
# ==========================================================
# WRAPPER LEGACY DE COMPATIBILIDAD
# ----------------------------------------------------------
# Mantiene vivo el import histórico:
#   from modules.routes_users import register_user_routes
#
# La lógica real ahora vive en modules/users/
# ==========================================================

from modules.users.user_http import register_user_routes

__all__ = ["register_user_routes"] 