# modules/empresas/__init__.py
# -*- coding: utf-8 -*-

from .routes_empresas import empresas_bp, register_empresas_routes

__all__ = ["empresas_bp", "register_empresas_routes"]