"""
file_utils.py — Escritura segura de JSON para entornos multi-usuario
=====================================================================
Usa filelock (OS-level) para evitar race conditions cuando dos preventistas
confirman pedidos simultáneamente sobre el mismo archivo.
"""

import pandas as pd
from pathlib import Path

try:
    from filelock import FileLock, Timeout
    _FILELOCK_AVAILABLE = True
except ImportError:
    _FILELOCK_AVAILABLE = False


def safe_read_json(path: Path) -> pd.DataFrame:
    """Lee un JSON a DataFrame. Las lecturas son seguras sin bloqueo."""
    if Path(path).exists():
        try:
            return pd.read_json(path)
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def safe_write_json(df: pd.DataFrame, path: Path, timeout: int = 10) -> bool:
    """
    Escribe un DataFrame a JSON con bloqueo de archivo OS-level.
    Garantiza que dos procesos no corrompan el mismo archivo simultáneamente.

    Retorna True si la escritura fue exitosa, False si hubo timeout.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if _FILELOCK_AVAILABLE:
        lock_path = path.with_suffix(".lock")
        try:
            with FileLock(str(lock_path), timeout=timeout):
                df.to_json(path, orient="records", force_ascii=False, indent=2)
            return True
        except Timeout:
            return False
    else:
        # Fallback sin filelock (menor seguridad pero funcional)
        df.to_json(path, orient="records", force_ascii=False, indent=2)
        return True


def safe_append_rows(new_rows: list, path: Path, dedup_cols: list = None) -> bool:
    """
    Agrega filas nuevas a un JSON existente de forma segura.
    Opcional: deduplica por columnas específicas (ej. ['NoPedido', 'CodigoProducto']).
    """
    path = Path(path)

    if _FILELOCK_AVAILABLE:
        lock_path = path.with_suffix(".lock")
        try:
            with FileLock(str(lock_path), timeout=10):
                df_existente = safe_read_json(path)
                df_nuevo = pd.DataFrame(new_rows)
                df_final = pd.concat([df_existente, df_nuevo], ignore_index=True)
                if dedup_cols:
                    df_final.drop_duplicates(subset=dedup_cols, keep="last", inplace=True)
                df_final.to_json(path, orient="records", force_ascii=False, indent=2)
            return True
        except Timeout:
            return False
    else:
        df_existente = safe_read_json(path)
        df_nuevo = pd.DataFrame(new_rows)
        df_final = pd.concat([df_existente, df_nuevo], ignore_index=True)
        if dedup_cols:
            df_final.drop_duplicates(subset=dedup_cols, keep="last", inplace=True)
        df_final.to_json(path, orient="records", force_ascii=False, indent=2)
        return True
