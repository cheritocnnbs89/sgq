from modules.db import get_config_value


def require_api_key(req) -> tuple[bool, str]:
    expected = (get_config_value("api_inbound_key", "") or "").strip()
    got = (req.headers.get("X-API-Key") or "").strip()

    if not expected:
        return False, "Falta configurar api_inbound_key en tabla configuracion."

    if got != expected:
        return False, "API key inválida."

    return True, ""