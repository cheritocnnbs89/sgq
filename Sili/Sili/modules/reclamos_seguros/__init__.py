# modules/reclamos_seguros/__init__.py
# -*- coding: utf-8 -*-

from .routes_reclamos_seguros import reclamos_seguros_bp, register_reclamos_seguros_routes

__all__ = ["reclamos_seguros_bp", "register_reclamos_seguros_routes"]
