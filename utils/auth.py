"""
auth.py — Autenticación con contraseñas hasheadas (PBKDF2-SHA256)
==================================================================
Las credenciales se almacenan en datos_maestros/users.json como
    "username": { "password_hash": "salt_hex:hash_hex", "role": "...", ... }

Para cambiar una contraseña desde consola:
    python -c "from utils.auth import hash_password; print(hash_password('nueva_clave'))"
Luego pega el resultado en el campo password_hash del usuario en users.json.

Para agregar un usuario desde el Gestor Base Maestra, usa la sección "Usuarios"
que llama a add_or_update_user().
"""

import hashlib
import json
import os
from pathlib import Path

_USERS_PATH = Path(__file__).resolve().parent.parent / "datos_maestros" / "users.json"


# ─── Hashing ─────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Genera un hash seguro PBKDF2-SHA256 con salt aleatorio."""
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return salt.hex() + ":" + key.hex()


def verify_password(password: str, stored_hash: str) -> bool:
    """Verifica una contraseña contra su hash almacenado."""
    try:
        salt_hex, key_hex = stored_hash.split(":")
        salt = bytes.fromhex(salt_hex)
        expected = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
        return expected.hex() == key_hex
    except Exception:
        return False


# ─── Carga de usuarios ────────────────────────────────────────────────────────

def _load_users() -> dict:
    """Lee users.json. Devuelve dict vacío si el archivo no existe."""
    if _USERS_PATH.exists():
        try:
            with open(_USERS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_users(users: dict) -> None:
    """Escribe users.json de forma segura."""
    _USERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _USERS_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)
    tmp.replace(_USERS_PATH)


# ─── API pública ──────────────────────────────────────────────────────────────

def authenticate(username: str, password: str):
    """
    Verifica credenciales. Retorna dict del usuario sin password_hash, o None.
    """
    users = _load_users()
    user = users.get(username)
    if user and verify_password(password, user["password_hash"]):
        return {k: v for k, v in user.items() if k != "password_hash"}
    return None


def list_users() -> list[dict]:
    """Devuelve lista de usuarios (sin password_hash) para la UI de gestión."""
    users = _load_users()
    return [
        {"username": uname, **{k: v for k, v in info.items() if k != "password_hash"}}
        for uname, info in users.items()
    ]


def add_or_update_user(username: str, password: str | None, role: str,
                       access: list, name: str = "") -> None:
    """
    Crea o actualiza un usuario.
    Si password es None o vacío, conserva el hash existente (solo actualiza metadata).
    """
    users = _load_users()
    existing_hash = users.get(username, {}).get("password_hash", "")

    entry: dict = {
        "password_hash": hash_password(password) if password else existing_hash,
        "role": role,
        "access": access,
    }
    if name:
        entry["name"] = name

    users[username] = entry
    _save_users(users)


def delete_user(username: str) -> bool:
    """Elimina un usuario. Devuelve True si existía."""
    users = _load_users()
    if username in users:
        del users[username]
        _save_users(users)
        return True
    return False
