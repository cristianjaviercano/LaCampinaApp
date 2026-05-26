"""
auth.py — Redirección a lacampina_core.auth para retrocompatibilidad
"""

from lacampina_core.auth import (
    hash_password,
    verify_password,
    authenticate,
    list_users,
    add_or_update_user,
    delete_user
)
