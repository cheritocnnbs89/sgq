try:
    from .routes_gastos import register_gastos_routes
except Exception as e:
    print("ERROR EN modules.gastos.__init__:", e)
    raise

__all__ = ["register_gastos_routes"]