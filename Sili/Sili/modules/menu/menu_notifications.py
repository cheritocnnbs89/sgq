from flask import flash

from .menu_constants import (
    FLASH_OPTION_CREATED,
    FLASH_OPTION_UPDATED,
    FLASH_OPTION_DELETED,
    FLASH_RECORD_CREATED,
    FLASH_RECORD_UPDATED,
    FLASH_RECORD_DELETED,
    FLASH_INVALID_EMAIL_1,
    FLASH_INVALID_EMAIL_2,
)


def flash_option_created():
    flash(FLASH_OPTION_CREATED, "success")


def flash_option_updated():
    flash(FLASH_OPTION_UPDATED, "success")


def flash_option_deleted():
    flash(FLASH_OPTION_DELETED, "success")


def flash_record_created():
    flash(FLASH_RECORD_CREATED, "success")


def flash_record_updated():
    flash(FLASH_RECORD_UPDATED, "success")


def flash_record_deleted():
    flash(FLASH_RECORD_DELETED, "success")


def flash_invalid_email(field_name: str):
    if field_name == "email1":
        flash(FLASH_INVALID_EMAIL_1, "warning")
        return

    if field_name == "email2":
        flash(FLASH_INVALID_EMAIL_2, "warning")
        return

    flash(f"{field_name} no parece un correo válido", "warning")