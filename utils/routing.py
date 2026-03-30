"""
routing.py — Motor de Rutas de La Campiña (Sahagún, Córdoba)
═══════════════════════════════════════════════════════════════
• Distancias reales por calles usando OSMnx + NetworkX
• El grafo de Sahagún se pre-carga via st.cache_resource (1 sola vez por sesión)
• Fallback a Haversine × 1.30 si el grafo no está disponible
• TSP vecino más cercano con distancias viales reales
• CVRP greedy con flota heterogénea
"""

import numpy as np
import pandas as pd
import networkx as nx
from pathlib import Path
import pickle
import warnings
warnings.filterwarnings("ignore")

_BASE_DIR     = Path(__file__).resolve().parent.parent / "datos_maestros"
_PKL_PATH     = _BASE_DIR / "sahagun_drive.pkl"       # Binario Python  ← priori dad
_GRAPHML_PATH = _BASE_DIR / "sahagun_drive.graphml"   # XML original    ← fallback

# ─── Carga del grafo via cache de Streamlit (carga 1 sola vez por sesión) ─────
def get_graph():
    """
    Retorna (G, nodes_gdf) del grafo de calles de Sahagún.
    Orden de prioridad:
      1. sahagun_drive.pkl   → carga en ~0.01s (binario nativo Python)
      2. sahagun_drive.graphml → carga en ~25s y auto-genera el .pkl para la siguiente vez
      3. None, None          → sin grafo, fallback Haversine
    Usa st.cache_resource: el grafo vive en RAM durante toda la sesión de Streamlit.
    """
    import streamlit as st

    # ── Prioridad 1: Pickle (grafo NetworkX en binario) ────────────────────────
    if _PKL_PATH.exists():
        @st.cache_resource(show_spinner="⚡ Cargando red vial de Sahagún...")
        def _desde_pkl():
            import osmnx as ox
            with open(_PKL_PATH, 'rb') as f:
                G = pickle.load(f)
            nodes = ox.graph_to_gdfs(G, edges=False)
            return G, nodes
        try:
            return _desde_pkl()
        except Exception:
            pass  # pkl corrupto, continuamos con graphml

    # ── Prioridad 2: GraphML → carga y genera pkl automáticamente ─────────────
    if _GRAPHML_PATH.exists():
        @st.cache_resource(
            show_spinner="🗺️ Cargando red vial de Sahagún..."
        )
        def _desde_graphml():
            import osmnx as ox
            G = ox.load_graphml(str(_GRAPHML_PATH))
            nodes = ox.graph_to_gdfs(G, edges=False)
            # Auto-guardar pkl para acelerar futuros reinicios
            try:
                with open(_PKL_PATH, 'wb') as f:
                    pickle.dump(G, f, protocol=pickle.HIGHEST_PROTOCOL)
            except Exception:
                pass
            return G, nodes
        try:
            return _desde_graphml()
        except Exception:
            pass

    return None, None


def _nearest_node(G, lat: float, lon: float) -> int:
    """Devuelve el nodo vial más cercano a (lat, lon)."""
    import osmnx as ox
    return ox.nearest_nodes(G, X=lon, Y=lat)


# ─── Distancia Haversine (siempre disponible) ─────────────────────────────────
def haversine_m(lat1, lon1, lat2, lon2) -> float:
    """Distancia en metros entre dos puntos (línea recta geográfica)."""
    R = 6_371_000
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlam = np.radians(lon2 - lon1)
    a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlam/2)**2
    return 2 * R * np.arcsin(np.sqrt(a))


# ─── Distancia por calles (OSMnx + NetworkX) ──────────────────────────────────
def street_distance_m(lat1, lon1, lat2, lon2, G=None) -> float:
    """
    Distancia real por calles en metros entre dos puntos.
    - Si G está disponible: ruta más corta en el grafo vial.
    - Fallback automático: Haversine × 1.30 (factor empírico para ciudades).
    """
    if G is None:
        G, _ = get_graph()
    if G is None:
        return haversine_m(lat1, lon1, lat2, lon2) * 1.30

    try:
        import osmnx as ox
        n1 = ox.nearest_nodes(G, X=lon1, Y=lat1)
        n2 = ox.nearest_nodes(G, X=lon2, Y=lat2)
        if n1 == n2:
            return 0.0
        return nx.shortest_path_length(G, n1, n2, weight='length')
    except Exception:
        return haversine_m(lat1, lon1, lat2, lon2) * 1.30


def get_route_geometry(lat1, lon1, lat2, lon2, G=None, nodes_gdf=None):
    """
    Retorna lista de (lat, lon) de la ruta vial entre dos puntos.
    Útil para dibujar recorridos en Folium.
    """
    if G is None:
        G, nodes_gdf = get_graph()
    if G is None:
        return [(lat1, lon1), (lat2, lon2)]
    try:
        import osmnx as ox
        n1 = ox.nearest_nodes(G, X=lon1, Y=lat1)
        n2 = ox.nearest_nodes(G, X=lon2, Y=lat2)
        if n1 == n2:
            return [(lat1, lon1), (lat2, lon2)]
        route_nodes = nx.shortest_path(G, n1, n2, weight='length')
        return [(float(nodes_gdf.loc[n, 'y']), float(nodes_gdf.loc[n, 'x']))
                for n in route_nodes]
    except Exception:
        return [(lat1, lon1), (lat2, lon2)]


# ─── Filtro geográfico Sahagún ────────────────────────────────────────────────
SAHAGUN_BBOX = {
    "lat_min": 8.88, "lat_max": 8.99,
    "lon_min": -75.50, "lon_max": -75.40
}

def filtrar_sahagun(df: pd.DataFrame) -> pd.DataFrame:
    b = SAHAGUN_BBOX
    mask = (
        df['Latitud'].between(b['lat_min'], b['lat_max']) &
        df['Longitud'].between(b['lon_min'], b['lon_max'])
    )
    return df[mask].copy()


# ─── Matriz de distancias N×N ─────────────────────────────────────────────────
def _build_distance_matrix(lats, lons, use_streets=True) -> np.ndarray:
    """
    Construye la matriz completa de distancias N×N.
    - use_streets=True  → distancias reales por calles (OSMnx)
    - use_streets=False → Haversine (línea recta geográfica)
    """
    n = len(lats)
    D = np.zeros((n, n))

    if use_streets:
        G, _ = get_graph()
        graph_ok = (G is not None)
    else:
        G = None
        graph_ok = False

    if graph_ok:
        import osmnx as ox
        # Pre-mapear todos los puntos a nodos del grafo (batch es más eficiente)
        try:
            node_ids = [ox.nearest_nodes(G, X=lons[i], Y=lats[i]) for i in range(n)]
        except Exception:
            node_ids = [None] * n
            graph_ok = False

    for i in range(n):
        for j in range(i + 1, n):
            if graph_ok and node_ids[i] is not None and node_ids[j] is not None:
                try:
                    if node_ids[i] == node_ids[j]:
                        d = 0.0
                    else:
                        d = nx.shortest_path_length(G, node_ids[i], node_ids[j], weight='length')
                except Exception:
                    d = haversine_m(lats[i], lons[i], lats[j], lons[j]) * 1.30
            else:
                d = haversine_m(lats[i], lons[i], lats[j], lons[j]) * 1.30
            D[i][j] = d
            D[j][i] = d

    return D


# ─── TSP: Vecino más Cercano ─────────────────────────────────────────────────
def nearest_neighbor_tsp(df_coords: pd.DataFrame, use_streets: bool = True) -> list:
    """
    Algoritmo Vecino Más Cercano para TSP.
    df_coords debe tener columnas 'Latitud' y 'Longitud'.
    Retorna lista de índices en el orden óptimo calculado.
    """
    if len(df_coords) <= 1:
        return list(range(len(df_coords)))

    lats = df_coords['Latitud'].values
    lons = df_coords['Longitud'].values
    D = _build_distance_matrix(lats, lons, use_streets=use_streets)

    unvisited = set(range(len(df_coords)))
    curr = 0
    tour = [curr]
    unvisited.remove(curr)

    while unvisited:
        nearest = min(unvisited, key=lambda x: D[curr][x])
        tour.append(nearest)
        unvisited.remove(nearest)
        curr = nearest

    return tour


def tsp_total_distance_km(df_coords: pd.DataFrame, tour: list,
                           use_streets: bool = True) -> float:
    """Calcula la distancia total de un tour TSP en kilómetros."""
    lats = df_coords['Latitud'].values
    lons = df_coords['Longitud'].values

    if use_streets:
        G, _ = get_graph()
    else:
        G = None

    total = 0.0
    for i in range(len(tour) - 1):
        a, b_idx = tour[i], tour[i + 1]
        if use_streets and G is not None:
            total += street_distance_m(lats[a], lons[a], lats[b_idx], lons[b_idx], G=G)
        else:
            total += haversine_m(lats[a], lons[a], lats[b_idx], lons[b_idx])
    return total / 1000


# ─── Distancia de ruta (secuencia de puntos) ─────────────────────────────────
def route_distance_km(puntos: list, use_streets: bool = True) -> float:
    """
    Calcula la distancia total de una secuencia de puntos (lat, lon).
    use_streets=True  → calles reales via OSMnx
    use_streets=False → Haversine (línea recta)
    """
    if len(puntos) < 2:
        return 0.0

    if use_streets:
        G, _ = get_graph()
    else:
        G = None

    total = 0.0
    for i in range(len(puntos) - 1):
        lat1, lon1 = puntos[i]
        lat2, lon2 = puntos[i + 1]
        if use_streets and G is not None:
            total += street_distance_m(lat1, lon1, lat2, lon2, G=G)
        else:
            total += haversine_m(lat1, lon1, lat2, lon2)
    return total / 1000


# ─── CVRP: Flota heterogénea ─────────────────────────────────────────────────
def greedy_cvrp_heterogeneous(df_pedidos: pd.DataFrame, vehiculos: list,
                               use_streets: bool = True):
    """
    CVRP greedy con flota heterogénea.
    vehiculos: [{'nombre': str, 'capacidad': int}, ...]
    Retorna lista de asignaciones por índice o False si es imposible.
    """
    if len(df_pedidos) == 0:
        return []

    lats       = df_pedidos['Latitud'].values
    lons       = df_pedidos['Longitud'].values
    cantidades = df_pedidos['Cantidad'].values

    D = _build_distance_matrix(lats, lons, use_streets=use_streets)

    unvisited   = set(range(len(df_pedidos)))
    assignments = ["No Asignado"] * len(df_pedidos)
    viaje_num   = 1

    while unvisited:
        ronda_activa = False

        for vehiculo in vehiculos:
            if not unvisited:
                break

            nombre = f"{vehiculo['nombre']} – Viaje {viaje_num}"
            cap    = vehiculo['capacidad']
            carga  = 0

            candidatos = [u for u in unvisited if cantidades[u] <= cap]
            if not candidatos:
                continue

            curr = candidatos[0]
            ronda_activa = True

            while True:
                if carga + cantidades[curr] <= cap:
                    assignments[curr] = nombre
                    carga += cantidades[curr]
                    unvisited.remove(curr)
                    proximos = [u for u in unvisited if carga + cantidades[u] <= cap]
                    if proximos:
                        curr = min(proximos, key=lambda x: D[curr][x])
                    else:
                        break
                else:
                    break

        if not ronda_activa and unvisited:
            return False

        viaje_num += 1

    return assignments
