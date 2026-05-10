"""
promos.py — Módulo de Promociones Comerciales
==============================================
Gestiona dos tipos de promo:
  - "bundle"    : agrupa N SKUs en un combo con precio especial
  - "descuento" : aplica un % de rebaja a un SKU específico

Las promos viven en datos_maestros/promociones.json.
"""

import json
from datetime import date
from pathlib import Path

PROMOS_PATH = Path(__file__).resolve().parent.parent / "datos_maestros" / "promociones.json"


# ─── I/O ──────────────────────────────────────────────────────────────────────

def load_promos() -> list[dict]:
    if PROMOS_PATH.exists():
        try:
            with open(PROMOS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def _save_promos(promos: list[dict]) -> None:
    PROMOS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PROMOS_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(promos, f, ensure_ascii=False, indent=2)
    tmp.replace(PROMOS_PATH)


# ─── Consultas ────────────────────────────────────────────────────────────────

def get_active_promos(today: date | None = None) -> list[dict]:
    """Devuelve solo las promos activas y dentro de vigencia para la fecha dada."""
    today = today or date.today()
    result = []
    for p in load_promos():
        if not p.get("activo", False):
            continue
        try:
            fi = date.fromisoformat(p["fecha_inicio"])
            ff = date.fromisoformat(p["fecha_fin"])
            if fi <= today <= ff:
                result.append(p)
        except Exception:
            pass
    return result


# ─── Mutaciones ───────────────────────────────────────────────────────────────

def save_promo(promo: dict) -> None:
    """Crea o actualiza una promo (match por id)."""
    promos = load_promos()
    idx = next((i for i, p in enumerate(promos) if p["id"] == promo["id"]), None)
    if idx is None:
        promos.append(promo)
    else:
        promos[idx] = promo
    _save_promos(promos)


def toggle_promo(promo_id: str) -> bool:
    """Invierte el estado activo de una promo. Retorna el nuevo estado."""
    promos = load_promos()
    for p in promos:
        if p["id"] == promo_id:
            p["activo"] = not p.get("activo", False)
            _save_promos(promos)
            return p["activo"]
    return False


def delete_promo(promo_id: str) -> bool:
    promos = load_promos()
    new = [p for p in promos if p["id"] != promo_id]
    if len(new) < len(promos):
        _save_promos(new)
        return True
    return False


# ─── Helpers de carrito ───────────────────────────────────────────────────────

def bundle_to_cart_items(bundle: dict, df_productos) -> list[dict]:
    """
    Convierte un bundle en líneas de carrito con descuento proporcional aplicado.
    El precio total de las líneas == bundle['precio_especial'].
    """
    items = []
    precio_normal_total = sum(
        p["cantidad"] * p.get("precio_base", 0) for p in bundle["productos"]
    )
    factor = (
        bundle["precio_especial"] / precio_normal_total
        if precio_normal_total > 0 else 1.0
    )
    pct_desc = round((1 - factor) * 100, 2)

    for prod in bundle["productos"]:
        precio_base = prod.get("precio_base", 0)
        if precio_base == 0 and not df_productos.empty:
            row = df_productos[df_productos["Codigo"].astype(str) == str(prod["codigo"])]
            if not row.empty:
                precio_base = float(row.iloc[0].get("PrecioBase", 0))

        total_linea = round(precio_base * prod["cantidad"] * factor, 2)
        items.append({
            "Producto":       prod["nombre"],
            "CodigoProducto": prod["codigo"],
            "Cantidad":       prod["cantidad"],
            "PrecioBase":     precio_base,
            "PctDescuento":   pct_desc,
            "Total":          total_linea,
            "PromoID":        bundle["id"],
            "PromoNombre":    bundle["nombre"],
        })
    return items


def descuento_to_cart_item(promo: dict, cantidad: int, df_productos) -> dict | None:
    """
    Devuelve una línea de carrito para una promo de descuento por SKU.
    """
    if not promo.get("productos"):
        return None
    prod = promo["productos"][0]
    precio_base = prod.get("precio_base", 0)
    if precio_base == 0 and not df_productos.empty:
        row = df_productos[df_productos["Codigo"].astype(str) == str(prod["codigo"])]
        if not row.empty:
            precio_base = float(row.iloc[0].get("PrecioBase", 0))
    pct = float(promo.get("descuento_pct", 0))
    total = round(precio_base * cantidad * (1 - pct / 100), 2)
    return {
        "Producto":       prod["nombre"],
        "CodigoProducto": prod["codigo"],
        "Cantidad":       cantidad,
        "PrecioBase":     precio_base,
        "PctDescuento":   pct,
        "Total":          total,
        "PromoID":        promo["id"],
        "PromoNombre":    promo["nombre"],
    }
