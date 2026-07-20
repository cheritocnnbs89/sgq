# modules/gastos/gastos_security.py

from .gastos_constants import ROLES_APROBADORES, ROLES_SUPER


def role_lower(session) -> str:
    return (session.get("rol") or "").strip().lower()


def is_super(session) -> bool:
    return role_lower(session) in ROLES_SUPER or bool(session.get("is_admin"))


def is_aprobador(session) -> bool:
    return role_lower(session) in ROLES_APROBADORES or is_super(session)


def can_approve(session) -> bool:
    return is_aprobador(session)


def can_view_all(session) -> bool:
    return is_super(session) or is_aprobador(session)


def can_edit_gasto(session, gasto) -> bool:
    uid = session.get("usuario_id") or session.get("user_id")
    if is_super(session):
        return True
    try:
        return int(gasto["usuario_id"]) == int(uid)
    except Exception:
        return False


def can_delete_gasto(session, gasto) -> bool:
    return is_super(session)


def ensure_can_edit_gasto(session, gasto):
    if not can_edit_gasto(session, gasto):
        raise PermissionError("No tiene permisos para editar este gasto.")


def ensure_can_delete_gasto(session, gasto):
    if not can_delete_gasto(session, gasto):
        raise PermissionError("No tiene permisos para eliminar este gasto.")


def ensure_can_approve(session):
    if not can_approve(session):
        raise PermissionError("No tiene permisos para aprobar gastos.")