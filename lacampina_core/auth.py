"""
auth.py — Autenticación con contraseñas hasheadas (PBKDF2-SHA256)
==================================================================
Lógica unificada para Streamlit y Tkinter.
Las credenciales se almacenan en users.json como:
    "username": { "password_hash": "salt_hex:hash_hex", "role": "...", ... }
"""

import hashlib
import json
import os
from pathlib import Path

# Resolver la ruta de users.json de manera flexible
_CORE_DIR = Path(__file__).resolve().parent
_DEFAULT_USERS_PATH = _CORE_DIR.parent / "datos_maestros" / "users.json"

# Permitir sobrescribir por variable de entorno o buscar en directorios alternativos
_ENV_PATH = os.environ.get("LACAMPINA_USERS_JSON")
if _ENV_PATH:
    _USERS_PATH = Path(_ENV_PATH)
else:
    # Si no hay variable, probar la por defecto, o buscar en la raíz del proyecto
    if _DEFAULT_USERS_PATH.exists():
        _USERS_PATH = _DEFAULT_USERS_PATH
    else:
        # Fallback para ejecuciones desde la_campina_tkinter
        # Buscar en el directorio padre de datos_maestros
        fallback_path = _CORE_DIR.parent.parent / "APP_Lacampiña2.0" / "datos_maestros" / "users.json"
        if fallback_path.exists():
            _USERS_PATH = fallback_path
        else:
            _USERS_PATH = _DEFAULT_USERS_PATH


# ─── Hashing ─────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Genera un hash seguro PBKDF2-SHA256 con salt aleatorio."""
    if not password:
        return ""
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return salt.hex() + ":" + key.hex()


def verify_password(password: str, stored_hash: str) -> bool:
    """Verifica una contraseña contra su hash almacenado."""
    if not stored_hash or ":" not in stored_hash:
        return False
    try:
        salt_hex, key_hex = stored_hash.split(":")
        salt = bytes.fromhex(salt_hex)
        expected = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
        return expected.hex() == key_hex
    except Exception:
        return False


# ─── Carga de usuarios ────────────────────────────────────────────────────────

def load_users() -> dict:
    """Lee users.json. Devuelve dict vacío si el archivo no existe."""
    if _USERS_PATH.exists():
        try:
            with open(_USERS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_users(users: dict) -> None:
    """Escribe users.json de forma segura."""
    _USERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _USERS_PATH.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
        tmp.replace(_USERS_PATH)
    except Exception as e:
        print(f"Error guardando usuarios: {e}")


# ─── API pública ──────────────────────────────────────────────────────────────

def authenticate(username: str, password: str):
    """
    Verifica credenciales. Retorna dict del usuario sin password_hash, o None.
    """
    if not username:
        return None
    users = load_users()
    uname_clean = username.strip().lower()
    user = users.get(uname_clean)
    if user and verify_password(password, user["password_hash"]):
        return {k: v for k, v in user.items() if k != "password_hash"}
    return None


def list_users() -> list[dict]:
    """Devuelve lista de usuarios (sin password_hash) para la UI de gestión."""
    users = load_users()
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
    if not username:
        return
    users = load_users()
    uname_clean = username.strip().lower()
    existing_hash = users.get(uname_clean, {}).get("password_hash", "")

    entry: dict = {
        "password_hash": hash_password(password) if password else existing_hash,
        "role": role,
        "access": access,
    }
    if name:
        entry["name"] = name

    users[uname_clean] = entry
    save_users(users)


def delete_user(username: str) -> bool:
    """Elimina un usuario. Devuelve True si existía."""
    if not username:
        return False
    users = load_users()
    uname_clean = username.strip().lower()
    if uname_clean in users:
        del users[uname_clean]
        save_users(users)
        return True
    return False
