"""
routing.py — Redirección a lacampina_core.routing para retrocompatibilidad
"""

from lacampina_core.routing import (
    get_graph,
    haversine_m,
    street_distance_m,
    get_route_geometry,
    filtrar_sahagun,
    nearest_neighbor_tsp,
    tsp_total_distance_km,
    route_distance_km,
    greedy_cvrp_heterogeneous
)
