"""
MÓDULO: Preventa y Entregas — Corazón de La Campiña
════════════════════════════════════════════════════
• Comparación Ruta Real vs Ruta Óptima (TSP) por vendedor y día
• Análisis de ahorro en distancia y tiempo
• Entrega D+1: lista de carga y asignación de flota (CVRP)
• Trazabilidad de secuencia de visitas
"""
import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster, AntPath
from streamlit_folium import st_folium
import plotly.express as px
import plotly.graph_objects as go
from utils.data_loader import load_data
from utils.routing import (
    nearest_neighbor_tsp, greedy_cvrp_heterogeneous,
    get_route_geometry, tsp_total_distance_km,
    haversine_m, route_distance_km, get_graph, SAHAGUN_BBOX
)
from datetime import timedelta
import numpy as np

# ─── CSS premium ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
.insight-box {
    border-radius: 10px; padding: 14px 18px; margin: 8px 0;
    font-size: 0.88rem; line-height: 1.5;
}
.insight-green  { background:#e8f5e9; border-left: 4px solid #2e7d32; color:#1b5e20; }
.insight-red    { background:#ffebee; border-left: 4px solid #c62828; color:#b71c1c; }
.insight-blue   { background:#e3f2fd; border-left: 4px solid #1565c0; color:#0d47a1; }
.insight-amber  { background:#fff8e1; border-left: 4px solid #e65100; color:#bf360c; }
.route-badge {
    display:inline-block; padding:3px 10px; border-radius:12px;
    font-size:0.75rem; font-weight:700; margin-right:4px;
}
.badge-real   { background:#e63946; color:white; }
.badge-optima { background:#2e7d32; color:white; }
.section-hdr {
    font-size:0.78rem; font-weight:700; color:#2e7d32;
    text-transform:uppercase; letter-spacing:.1em;
    border-bottom:2px solid #e8f5e9; padding-bottom:6px; margin-bottom:10px;
}
</style>
""", unsafe_allow_html=True)

st.title("🛒 Preventa y Entregas")
st.markdown(
    "El módulo central de La Campiña: **analiza rutas reales**, "
    "**optimiza recorridos** de vendedores y **planifica el despacho** con la flota disponible."
)

# ─── Carga de datos ───────────────────────────────────────────────────────────
data = load_data(st.session_state.get("fecha_historica"))
if data is None or data['compras_detalle'].empty:
    st.error("No hay datos de compras. Ve al **Gestor Base Maestra → Compras** y carga un Purchase Order.")
    st.stop()

df_raw        = data['compras_detalle'].copy()
df_clientes   = data['clientes'].copy()
df_ubicaciones = data['ubicaciones'].copy()

df_raw['Fecha'] = pd.to_datetime(df_raw['Fecha'], errors='coerce')

# ─── Enriquecer con coordenadas ────────────────────────────────────────────────
df_raw['ClienteNORMA'] = df_raw['ClienteNombre'].str.strip().str.upper()

# Fuente 1: ubicaciones.json
coords_ubi = pd.DataFrame()
if not df_ubicaciones.empty and 'Cliente' in df_ubicaciones.columns:
    df_ubi = df_ubicaciones.copy()
    df_ubi['ClienteNORMA'] = df_ubi['Cliente'].str.strip().str.upper()
    coords_ubi = df_ubi[['ClienteNORMA','Latitud','Longitud']].dropna().drop_duplicates('ClienteNORMA')

# Fuente 2: clientes_maestro.json
coords_cli = pd.DataFrame()
nombre_col = next((c for c in ['Nombre','Nombre_x'] if c in df_clientes.columns), None)
lat_col    = next((c for c in df_clientes.columns if 'Latitud'  in c), None)
lon_col    = next((c for c in df_clientes.columns if 'Longitud' in c), None)
if nombre_col and lat_col and lon_col:
    df_clientes['ClienteNORMA'] = df_clientes[nombre_col].astype(str).str.strip().str.upper()
    coords_cli = (df_clientes[['ClienteNORMA', lat_col, lon_col]]
                  .rename(columns={lat_col:'Latitud', lon_col:'Longitud'})
                  .dropna().drop_duplicates('ClienteNORMA'))
    coords_cli = coords_cli[coords_cli['Longitud'] < 0]

# Merge: ubicaciones primero, luego clientes
df_raw['Latitud'] = pd.to_numeric(df_raw['Latitud'], errors='coerce') if 'Latitud' in df_raw.columns else np.nan
df_raw['Longitud'] = pd.to_numeric(df_raw['Longitud'], errors='coerce') if 'Longitud' in df_raw.columns else np.nan

df_raw['ClienteCodigo_str'] = df_raw.get('ClienteCodigo', pd.Series(dtype=str)).astype(str).str.strip()

mapa_lat_cod = pd.Series(dtype=float)
mapa_lon_cod = pd.Series(dtype=float)
if not coords_cli.empty and 'Codigo' in df_clientes.columns:
    df_clientes['Codigo_str'] = df_clientes['Codigo'].astype(str).str.strip()
    df_cli_uniq = df_clientes.drop_duplicates('Codigo_str')
    mapa_lat_cod = df_cli_uniq.set_index('Codigo_str')['Latitud']
    mapa_lon_cod = df_cli_uniq.set_index('Codigo_str')['Longitud']

# 1. Asignar por Código (más preciso)
sin_coord = df_raw['Latitud'].isna()
if sin_coord.any():
    df_raw.loc[sin_coord, 'Latitud'] = df_raw.loc[sin_coord, 'ClienteCodigo_str'].map(mapa_lat_cod)
    df_raw.loc[sin_coord, 'Longitud'] = df_raw.loc[sin_coord, 'ClienteCodigo_str'].map(mapa_lon_cod)

# 2. Asignar por Nombre exacto
sin_coord = df_raw['Latitud'].isna()
if sin_coord.any() and not coords_ubi.empty:
    mapa_lat_u = coords_ubi.set_index('ClienteNORMA')['Latitud']
    mapa_lon_u = coords_ubi.set_index('ClienteNORMA')['Longitud']
    df_raw.loc[sin_coord, 'Latitud']  = df_raw.loc[sin_coord,'ClienteNORMA'].map(mapa_lat_u)
    df_raw.loc[sin_coord, 'Longitud'] = df_raw.loc[sin_coord,'ClienteNORMA'].map(mapa_lon_u)

sin_coord = df_raw['Latitud'].isna()
if sin_coord.any() and not coords_cli.empty:
    mapa_lat_c = coords_cli.set_index('ClienteNORMA')['Latitud']
    mapa_lon_c = coords_cli.set_index('ClienteNORMA')['Longitud']
    df_raw.loc[sin_coord, 'Latitud']  = df_raw.loc[sin_coord,'ClienteNORMA'].map(mapa_lat_c)
    df_raw.loc[sin_coord, 'Longitud'] = df_raw.loc[sin_coord,'ClienteNORMA'].map(mapa_lon_c)

# ─── Filtrar Sahagún ──────────────────────────────────────────────────────────
b = SAHAGUN_BBOX
df_geo = df_raw.dropna(subset=['Latitud','Longitud']).copy()
df_geo = df_geo[
    df_geo['Latitud'].between(b['lat_min'], b['lat_max']) &
    df_geo['Longitud'].between(b['lon_min'], b['lon_max'])
]
df_geo['FechaStr'] = df_geo['Fecha'].dt.strftime('%Y-%m-%d')
df_geo['NombreDia'] = df_geo['Fecha'].dt.day_name().map({
    'Monday':'Lunes','Tuesday':'Martes','Wednesday':'Miércoles',
    'Thursday':'Jueves','Friday':'Viernes','Saturday':'Sábado','Sunday':'Domingo'
})

CENTRO = (8.9462, -75.4523)
PALETA = ['#e63946','#2a9d8f','#e9c46a','#f4a261','#264653','#8338ec']
vendedores_lista = sorted(df_geo['Vendedor'].dropna().unique())
COLOR_MAP = {v: PALETA[i % len(PALETA)] for i, v in enumerate(vendedores_lista)}

# ─── Helpers ─────────────────────────────────────────────────────────────────
def dibujar_ruta_folium(m, puntos, etiquetas, color, nombre_ruta, usar_calles=True, G=None, nodes_gdf=None):
    """Dibuja una ruta con marcadores numerados y segmentos en el mapa."""
    for i in range(len(puntos) - 1):
        try:
            if usar_calles and G is not None:
                geom = get_route_geometry(
                    puntos[i][0], puntos[i][1],
                    puntos[i+1][0], puntos[i+1][1],
                    G=G, nodes_gdf=nodes_gdf
                )
            else:
                geom = [puntos[i], puntos[i+1]]
            AntPath(geom, color=color, weight=4, opacity=0.85,
                    delay=800, tooltip=nombre_ruta).add_to(m)
        except Exception:
            folium.PolyLine([puntos[i], puntos[i+1]], color=color, weight=4, opacity=0.7).add_to(m)

    for idx, (pt, label) in enumerate(zip(puntos, etiquetas)):
        folium.Marker(
            location=pt,
            icon=folium.DivIcon(
                html=f"""<div style='background:{color};color:white;
                         border-radius:50%;width:24px;height:24px;
                         text-align:center;line-height:24px;
                         font-weight:bold;font-size:11px;
                         border:2px solid white;box-shadow:1px 1px 3px rgba(0,0,0,.4);'>
                         {idx+1}</div>""",
                icon_size=(24,24), icon_anchor=(12,12)
            ),
            popup=folium.Popup(f"<b>#{idx+1}</b> {label}", max_width=200),
            tooltip=f"#{idx+1} {label}"
        ).add_to(m)

# ═══════════════════════════════════════════════════════════════════════════════
# TABS PRINCIPALES
# ═══════════════════════════════════════════════════════════════════════════════
tab_comp, tab_kpi, tab_entrega, tab_cvrp, tab_mapa = st.tabs([
    "🔄 Ruta Real vs Óptima",
    "📊 KPIs del Período",
    "📦 Entrega D+1",
    "🚚 Despacho de Flota (CVRP)",
    "🗺️ Mapa de Cobertura",
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — COMPARACIÓN RUTA REAL vs ÓPTIMA  ← EL CORAZÓN
# ══════════════════════════════════════════════════════════════════════════════
with tab_comp:
    st.markdown('<div class="section-hdr">🎯 Análisis de Ruta: Real vs Algoritmo Óptimo</div>', unsafe_allow_html=True)
    st.markdown(
        "Selecciona un **vendedor** y un **día** para ver qué ruta realizó en la práctica "
        "y cuánto podría ahorrar siguiendo la ruta calculada por el algoritmo TSP."
    )

    # ── Selección ─────────────────────────────────────────────────────────────
    sc1, sc2, sc3 = st.columns([1, 1, 1])
    with sc1:
        sel_vend_comp = st.selectbox("👤 Vendedor", vendedores_lista, key="comp_vend")
    with sc2:
        fechas_vend = sorted(df_geo[df_geo['Vendedor'] == sel_vend_comp]['FechaStr'].unique(), reverse=True)
        sel_fecha_comp = st.selectbox("📅 Fecha de análisis", fechas_vend, key="comp_fecha")
    with sc3:
        usar_calles = st.toggle(
            "🛣️ Usar calles reales (OSMnx)", value=True,
            help="Distancias reales por la red vial de Sahagún. Más preciso. Se pre-carga en memoria al abrir la app."
        )

    # ── Estado del grafo de calles ─────────────────────────────────────────────
    G_graph, nodes_gdf = get_graph()
    if G_graph is not None:
        st.markdown(
            '<div class="insight-box insight-green" style="padding:8px 14px;margin-bottom:8px;">'
            '✅ <b>Red vial de Sahagún cargada</b> — Las distancias usarán rutas reales por calles '
            f'({G_graph.number_of_nodes():,} nodos · {G_graph.number_of_edges():,} aristas). '
            'Factor promedio calle/línea recta: ~1.29×</div>',
            unsafe_allow_html=True
        )
    else:
        usar_calles = False
        st.markdown(
            '<div class="insight-box insight-amber" style="padding:8px 14px;margin-bottom:8px;">'
            '⚠️ <b>Grafo de calles no disponible</b> — Usando distancia Haversine (línea recta). '
            'Verifica que <code>datos_maestros/sahagun_drive.graphml</code> exista.</div>',
            unsafe_allow_html=True
        )

    # ── Datos del día ──────────────────────────────────────────────────────────
    df_dia = df_geo[
        (df_geo['Vendedor'] == sel_vend_comp) &
        (df_geo['FechaStr'] == sel_fecha_comp)
    ].copy()

    if df_dia.empty:
        st.warning("No hay datos con coordenadas para ese vendedor en esa fecha.")
        st.stop()

    # Un punto por tienda (más info agrupada)
    df_puntos = (
        df_dia.groupby(['NoPedido','ClienteNORMA','ClienteNombre','Barrio','Ruta','Latitud','Longitud'])
        .agg(Total=('Total','sum'), Cantidad=('Cantidad','sum'))
        .reset_index()
        .drop_duplicates('ClienteNORMA')   # una tienda = un punto
        .reset_index(drop=True)
    )

    n_puntos = len(df_puntos)

    if n_puntos < 2:
        st.info(f"Solo {n_puntos} tienda con coordenadas ese día. Se necesitan al menos 2 para comparar rutas.")
        st.stop()

    # ── Ruta REAL (orden NoPedido ascendente) ─────────────────────────────────
    df_real = df_puntos.sort_values('NoPedido').reset_index(drop=True)
    puntos_real    = list(zip(df_real['Latitud'], df_real['Longitud']))
    etiquetas_real = df_real['ClienteNombre'].tolist()
    dist_real_km   = route_distance_km(puntos_real, use_streets=usar_calles)

    # ── Ruta ÓPTIMA (TSP Vecino más Cercano) ─────────────────────────────────
    calcular_key = f"tsp_opt_{sel_vend_comp}_{sel_fecha_comp}_{usar_calles}"
    if calcular_key not in st.session_state:
        spinner_msg = (
            "⚙️ Calculando ruta óptima por calles reales (OSMnx)..."
            if usar_calles else "⚙️ Calculando ruta óptima (Haversine)..."
        )
        with st.spinner(spinner_msg):
            orden_opt = nearest_neighbor_tsp(
                df_puntos[['Latitud','Longitud']], use_streets=usar_calles
            )
            dist_opt_km = tsp_total_distance_km(
                df_puntos[['Latitud','Longitud']], orden_opt, use_streets=usar_calles
            )
            df_optima = df_puntos.iloc[orden_opt].reset_index(drop=True)
            st.session_state[calcular_key] = {
                'orden': orden_opt,
                'dist_km': dist_opt_km,
                'df': df_optima,
                'usó_calles': usar_calles
            }
    else:
        pass

    res = st.session_state[calcular_key]
    dist_opt_km = res['dist_km']
    df_optima   = res['df']
    puntos_opt  = list(zip(df_optima['Latitud'], df_optima['Longitud']))
    etiquetas_opt = df_optima['ClienteNombre'].tolist()

    ahorro_km  = dist_real_km - dist_opt_km
    pct_ahorro = ahorro_km / dist_real_km * 100 if dist_real_km > 0 else 0
    # Tiempo estimado: velocidad promedio 15 km/h en ciudad (moto/camión pequeño)
    vel_kmh = 15
    tiempo_real_min = dist_real_km / vel_kmh * 60
    tiempo_opt_min  = dist_opt_km  / vel_kmh * 60
    ahorro_min = tiempo_real_min - tiempo_opt_min

    # ── Métricas de comparación ───────────────────────────────────────────────
    st.markdown("---")
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("📍 Tiendas visitadas", f"{n_puntos}")
    k2.metric("📏 Distancia Real", f"{dist_real_km:.1f} km",
              delta=f"+{ahorro_km:.1f} km de exceso", delta_color="inverse")
    k3.metric("✅ Ruta Óptima", f"{dist_opt_km:.1f} km")
    k4.metric("💡 Ahorro potencial", f"{ahorro_km:.1f} km", delta=f"{pct_ahorro:.1f}%")
    k5.metric("⏱️ Tiempo ahorrado", f"{ahorro_min:.0f} min")

    # Insight dinámico
    if pct_ahorro > 20:
        nivel, clase = "🔴 Alto potencial de mejora", "insight-red"
        msg = f"La ruta real recorre **{dist_real_km:.1f} km**, mientras que la ruta optimizada solo necesita **{dist_opt_km:.1f} km**. El vendedor podría ahorrar **{ahorro_km:.1f} km** ({pct_ahorro:.0f}%) y aproximadamente **{ahorro_min:.0f} minutos** por día siguiendo el orden óptimo."
    elif pct_ahorro > 10:
        nivel, clase = "🟡 Mejora moderada posible", "insight-amber"
        msg = f"Hay oportunidad de optimización: la ruta actual es **{pct_ahorro:.0f}% más larga** que la óptima. Reorganizar el orden de visitas ahorraría **{ahorro_min:.0f} minutos** por jornada."
    else:
        nivel, clase = "🟢 Ruta muy eficiente", "insight-green"
        msg = f"¡Excelente! El vendedor ya sigue una ruta bastante eficiente. La diferencia con el óptimo es solo **{pct_ahorro:.0f}%** ({ahorro_km:.1f} km)."

    st.markdown(f'<div class="insight-box {clase}"><b>{nivel}</b><br>{msg}</div>', unsafe_allow_html=True)

    # ── MAPA DUAL ─────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown('<div class="section-hdr">🗺️ Comparación en Mapa</div>', unsafe_allow_html=True)
    st.markdown(
        f'<span class="route-badge badge-real">🔴 Ruta Real ({dist_real_km:.1f} km)</span>'
        f'<span class="route-badge badge-optima">🟢 Ruta Óptima ({dist_opt_km:.1f} km)</span>'
        f' — Ambas rutas sobre el mismo mapa. Los números indican el orden de visita de cada ruta.',
        unsafe_allow_html=True
    )

    col_mapa1, col_mapa2 = st.columns(2)

    with col_mapa1:
        st.markdown("#### 🔴 Ruta Real (orden del sistema)")
        m_real = folium.Map(location=CENTRO, zoom_start=14, tiles='OpenStreetMap')
        dibujar_ruta_folium(
            m_real, puntos_real, etiquetas_real,
            '#e63946', 'Ruta Real',
            usar_calles=usar_calles,
            G=G_graph, nodes_gdf=nodes_gdf
        )
        folium.Marker(
            location=CENTRO,
            icon=folium.Icon(color='black', icon='home', prefix='fa'),
            tooltip="Depósito La Campiña"
        ).add_to(m_real)
        st_folium(m_real, use_container_width=True, height=480, returned_objects=[], key="mapa_real")

    with col_mapa2:
        st.markdown("#### 🟢 Ruta Óptima (TSP — Vecino más Cercano)")
        m_opt = folium.Map(location=CENTRO, zoom_start=14, tiles='OpenStreetMap')
        dibujar_ruta_folium(
            m_opt, puntos_opt, etiquetas_opt,
            '#2e7d32', 'Ruta Óptima',
            usar_calles=usar_calles,
            G=G_graph, nodes_gdf=nodes_gdf
        )
        folium.Marker(
            location=CENTRO,
            icon=folium.Icon(color='black', icon='home', prefix='fa'),
            tooltip="Depósito La Campiña"
        ).add_to(m_opt)
        st_folium(m_opt, use_container_width=True, height=480, returned_objects=[], key="mapa_opt")

    # ── TABLA COMPARATIVA DE SECUENCIAS ──────────────────────────────────────
    st.markdown("---")
    st.markdown('<div class="section-hdr">📋 Secuencia Comparativa de Visitas</div>', unsafe_allow_html=True)

    max_filas = max(len(df_real), len(df_optima))
    comp_data = []
    for i in range(max_filas):
        real_row = df_real.iloc[i] if i < len(df_real) else None
        opt_row  = df_optima.iloc[i] if i < len(df_optima) else None
        comp_data.append({
            '# Visita': i + 1,
            '🔴 Tienda Real': real_row['ClienteNombre'] if real_row is not None else '—',
            '🔴 Barrio Real': real_row['Barrio'] if real_row is not None else '—',
            '🔴 Venta ($)': f"${real_row['Total']:,.0f}" if real_row is not None else '—',
            '🟢 Tienda Óptima': opt_row['ClienteNombre'] if opt_row is not None else '—',
            '🟢 Barrio Óptimo': opt_row['Barrio'] if opt_row is not None else '—',
            '🟢 Venta ($)': f"${opt_row['Total']:,.0f}" if opt_row is not None else '—',
        })

    df_comp = pd.DataFrame(comp_data)
    st.dataframe(df_comp, use_container_width=True, hide_index=True, height=400)

    # ── Clearar cache de TSP si cambia la selección ───────────────────────────
    if st.button("🔄 Recalcular ruta óptima", key="btn_recalc"):
        keys_to_del = [k for k in st.session_state if k.startswith("tsp_opt_")]
        for k in keys_to_del:
            del st.session_state[k]
        st.rerun()

    # ── Detalle financiero del día ─────────────────────────────────────────────
    with st.expander("💰 Detalle financiero de la jornada", expanded=False):
        resumen_fin = df_puntos[['ClienteNombre','Barrio','Ruta','Total','Cantidad']].copy()
        resumen_fin = resumen_fin.sort_values('Total', ascending=False)
        total_dia   = resumen_fin['Total'].sum()
        st.markdown(f"**Total recaudado:** `${total_dia:,.0f}` en **{n_puntos}** tiendas | "
                    f"Ticket promedio: `${total_dia/n_puntos:,.0f}`")
        st.dataframe(
            resumen_fin.style.format({'Total':'${:,.0f}','Cantidad':'{:,.0f}'}),
            use_container_width=True, hide_index=True
        )

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — KPIs
# ══════════════════════════════════════════════════════════════════════════════
with tab_kpi:
    st.markdown('<div class="section-hdr">📊 KPIs del Período Seleccionado</div>', unsafe_allow_html=True)

    # Filtros rápidos
    f1, f2, f3, f4 = st.columns(4)
    with f1: sel_sem   = st.selectbox("📅 Semana",   ["Todas"] + sorted(df_geo['Fecha'].dt.strftime('%Y-W%V').unique()))
    with f2: sel_fec   = st.selectbox("📆 Día",      ["Todos"] + sorted(df_geo['FechaStr'].unique()))
    with f3: sel_vend2 = st.selectbox("👤 Vendedor", ["Todos"] + vendedores_lista, key="kpi_vend")
    with f4: sel_ruta  = st.selectbox("🗓️ Ruta",    ["Todas"] + sorted(df_geo['Ruta'].dropna().unique()))

    df_f = df_geo.copy()
    df_f['AnoSem'] = df_f['Fecha'].dt.strftime('%Y-W%V')
    if sel_sem   != "Todas": df_f = df_f[df_f['AnoSem']    == sel_sem]
    if sel_fec   != "Todos": df_f = df_f[df_f['FechaStr']  == sel_fec]
    if sel_vend2 != "Todos": df_f = df_f[df_f['Vendedor']  == sel_vend2]
    if sel_ruta  != "Todas": df_f = df_f[df_f['Ruta']      == sel_ruta]

    c1,c2,c3,c4,c5 = st.columns(5)
    tick = df_f['Total'].sum() / max(df_f['NoPedido'].nunique(), 1)
    c1.metric("💰 Venta Total",    f"${df_f['Total'].sum():,.0f}")
    c2.metric("🛒 Pedidos",        f"{df_f['NoPedido'].nunique():,}")
    c3.metric("👥 Clientes",       f"{df_f['ClienteCodigo'].nunique():,}")
    c4.metric("📦 Unidades",       f"{df_f['Cantidad'].sum():,.0f}")
    c5.metric("🧾 Ticket Prom.",   f"${tick:,.0f}")

    st.markdown("---")
    ca, cb = st.columns([3, 1])
    with ca:
        vd = df_f.groupby('FechaStr').agg(Total=('Total','sum')).reset_index()
        fig = px.bar(vd, x='FechaStr', y='Total', color='Total',
                     color_continuous_scale='Greens', template='plotly_white', title="Venta Diaria")
        fig.update_layout(xaxis_tickangle=-45, showlegend=False,
                          yaxis_tickprefix='$', yaxis_tickformat=',.0s', margin=dict(t=40,b=40))
        st.plotly_chart(fig, use_container_width=True)
    with cb:
        vv = df_f.groupby('Vendedor')['Total'].sum().reset_index()
        fig2 = px.pie(vv, values='Total', names='Vendedor', hole=0.45,
                      color_discrete_sequence=list(COLOR_MAP.values()))
        fig2.update_traces(textinfo='percent+label')
        fig2.update_layout(showlegend=False, margin=dict(t=40))
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")
    cc, cd = st.columns(2)
    with cc:
        tp = df_f.groupby('Producto')['Cantidad'].sum().nlargest(10).reset_index()
        fig3 = px.bar(tp, x='Cantidad', y='Producto', orientation='h',
                      color='Cantidad', color_continuous_scale='Blues', template='plotly_white',
                      title="Top 10 — Unidades")
        fig3.update_layout(yaxis={'categoryorder':'total ascending'}, margin=dict(t=40))
        st.plotly_chart(fig3, use_container_width=True)
    with cd:
        tv = df_f.groupby('Producto')['Total'].sum().nlargest(10).reset_index()
        fig4 = px.bar(tv, x='Total', y='Producto', orientation='h',
                      color='Total', color_continuous_scale='Greens', template='plotly_white',
                      title="Top 10 — Valor $")
        fig4.update_layout(yaxis={'categoryorder':'total ascending'},
                           xaxis_tickprefix='$', xaxis_tickformat=',.0s', margin=dict(t=40))
        st.plotly_chart(fig4, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — ENTREGA D+1
# ══════════════════════════════════════════════════════════════════════════════
with tab_entrega:
    st.markdown('<div class="section-hdr">📦 Programación Entrega D+1</div>', unsafe_allow_html=True)
    st.info("**Regla:** lo que se prevende el día D → se despacha el día D+1. "
            "Aquí se genera la lista de carga para bodega y el mapa de puntos de entrega.")

    fechas_disp = sorted(df_geo['FechaStr'].unique())
    sd1, sd2 = st.columns([2, 2])
    with sd1:
        sel_dia_prev = st.selectbox("📅 Día de Preventa (D)", fechas_disp, index=len(fechas_disp)-1, key="d1")
    fecha_entrega_str = (pd.to_datetime(sel_dia_prev) + timedelta(days=1)).strftime('%Y-%m-%d')
    with sd2:
        st.success(f"🚚 Preventa **{sel_dia_prev}** → Entrega **{fecha_entrega_str}**")

    df_dia_e = df_geo[df_geo['FechaStr'] == sel_dia_prev].copy()

    if df_dia_e.empty:
        st.warning("Sin pedidos en esa fecha.")
    else:
        cm1,cm2,cm3,cm4 = st.columns(4)
        cm1.metric("📦 Pedidos", f"{df_dia_e['NoPedido'].nunique():,}")
        cm2.metric("🏪 Tiendas", f"{df_dia_e['ClienteCodigo'].nunique():,}")
        cm3.metric("💰 Total",   f"${df_dia_e['Total'].sum():,.0f}")
        cm4.metric("📦 Unidades", f"{df_dia_e['Cantidad'].sum():,.0f}")

        # ── Lista de carga (picking list) ─────────────────────────────────────
        st.markdown("#### 📋 Lista de Carga para Bodega")
        pl = (df_dia_e.groupby(['CodigoProducto','Producto'])
              .agg(Cantidad=('Cantidad','sum'), Total=('Total','sum'))
              .reset_index().sort_values('Producto'))
        total_pl = pl['Total'].sum()
        st.dataframe(
            pl.style.format({'Total':'${:,.0f}','Cantidad':'{:,.0f}'}),
            use_container_width=True, hide_index=True
        )
        st.markdown(f"**Total en bodega:** `{pl['Cantidad'].sum():,.0f}` unidades | `${total_pl:,.0f}`")

        # ── Mapa de puntos de entrega ─────────────────────────────────────────
        df_dia_c = df_dia_e.dropna(subset=['Latitud','Longitud'])
        if not df_dia_c.empty:
            st.markdown(f"#### 🗺️ Mapa de Puntos de Entrega — {fecha_entrega_str}")
            df_ent_mapa = (df_dia_c
                           .groupby(['ClienteNombre','Vendedor','Latitud','Longitud','Barrio'])
                           .agg(Total=('Total','sum'), Unidades=('Cantidad','sum'),
                                NoPedido=('NoPedido','first'))
                           .reset_index())

            m_ent = folium.Map(location=CENTRO, zoom_start=13, tiles='OpenStreetMap')
            cluster_ent = MarkerCluster(name="Puntos de Entrega").add_to(m_ent)
            for _, row in df_ent_mapa.iterrows():
                color = COLOR_MAP.get(row['Vendedor'], '#888')
                popup_html = (f"<b>{row['ClienteNombre']}</b><br>"
                              f"Barrio: {row.get('Barrio','N/A')}<br>"
                              f"Vendedor: {row['Vendedor']}<br>"
                              f"Total: ${row['Total']:,.0f}<br>"
                              f"Unidades: {row['Unidades']:,.0f}")
                folium.CircleMarker(
                    location=[row['Latitud'], row['Longitud']],
                    radius=8, color=color, fill=True, fill_color=color, fill_opacity=0.85,
                    popup=folium.Popup(popup_html, max_width=250),
                    tooltip=row['ClienteNombre']
                ).add_to(cluster_ent)
            st_folium(m_ent, use_container_width=True, height=500, returned_objects=[])
            st.caption(f"Mostrando {len(df_ent_mapa)} puntos de entrega con coordenadas.")
        else:
            st.warning("Sin coordenadas disponibles para los puntos de entrega de ese día.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — DESPACHO DE FLOTA (CVRP)
# ══════════════════════════════════════════════════════════════════════════════
with tab_cvrp:
    st.markdown('<div class="section-hdr">🚚 Optimización de Despacho — CVRP con Flota Heterogénea</div>',
                unsafe_allow_html=True)
    st.markdown("""
    Asigna la preventa de un día a los vehículos disponibles, **minimizando distancia total**
    y **respetando la capacidad** de cada camión. El resultado es el plan de despacho óptimo.
    """)

    # ── Selección del día de preventa ─────────────────────────────────────────
    cv_d1, cv_d2 = st.columns([2, 2])
    with cv_d1:
        fechas_cvrp = sorted(df_geo['FechaStr'].unique())
        sel_dia_cvrp = st.selectbox("📅 Día de Preventa para Despacho", fechas_cvrp,
                                    index=len(fechas_cvrp)-1, key="cvrp_dia")
    with cv_d2:
        sel_vend_cvrp = st.selectbox("👤 Filtrar por vendedor (opcional)",
                                     ["Todos"] + vendedores_lista, key="cvrp_vend")

    fecha_despacho = (pd.to_datetime(sel_dia_cvrp) + timedelta(days=1)).strftime('%Y-%m-%d')
    st.success(f"📦 Preventa **{sel_dia_cvrp}** → Despacho **{fecha_despacho}**")

    df_cvrp_base = df_geo[df_geo['FechaStr'] == sel_dia_cvrp].dropna(subset=['Latitud','Longitud']).copy()
    if sel_vend_cvrp != "Todos":
        df_cvrp_base = df_cvrp_base[df_cvrp_base['Vendedor'] == sel_vend_cvrp]

    if df_cvrp_base.empty:
        st.warning("Sin puntos con coordenadas para ese día/vendedor.")
    else:
        demanda = (df_cvrp_base
                   .groupby(['ClienteNORMA','ClienteNombre','Vendedor','Latitud','Longitud','Barrio'])
                   .agg(Cantidad=('Cantidad','sum'), Total=('Total','sum'),
                        Pedidos=('NoPedido','nunique'))
                   .reset_index())

        # ── Configuración de flota (sidebar) ─────────────────────────────────
        with st.sidebar:
            st.markdown("---")
            st.markdown("### 🚛 Flota La Campiña")
            flota = [
                {'nombre': 'Mazda Turbo',    'capacidad': st.number_input("Mazda Turbo (unds)",   value=4000, step=100, key="f1")},
                {'nombre': 'NHR',            'capacidad': st.number_input("NHR (unds)",            value=2000, step=100, key="f2")},
                {'nombre': 'Camioneta',      'capacidad': st.number_input("Camioneta (unds)",      value=700,  step=50,  key="f3")},
                {'nombre': 'MotoC. Pesado',  'capacidad': st.number_input("MotoC.Pesado (unds)",   value=350,  step=50,  key="f4")},
                {'nombre': 'MotoC. Ligero1', 'capacidad': st.number_input("MotoC.Lig.1 (unds)",   value=259,  step=10,  key="f5")},
                {'nombre': 'MotoC. Ligero2', 'capacidad': st.number_input("MotoC.Lig.2 (unds)",   value=259,  step=10,  key="f6")},
            ]
        cap_total = sum(v['capacidad'] for v in flota)

        # Métricas previas
        cv1, cv2, cv3, cv4 = st.columns(4)
        cv1.metric("📍 Puntos de Entrega",  len(demanda))
        cv2.metric("📦 Total Unidades",     f"{demanda['Cantidad'].sum():,.0f}")
        cv3.metric("🚛 Capacidad Flota",    f"{cap_total:,.0f} unds")
        vueltas = max(1, int(np.ceil(demanda['Cantidad'].sum() / cap_total)))
        cv4.metric("🔄 Vueltas estimadas",  f"~{vueltas}")

        if demanda['Cantidad'].sum() > cap_total:
            st.markdown(
                f'<div class="insight-box insight-amber">⚠️ La demanda total ({demanda["Cantidad"].sum():,.0f} unds) '
                f'supera la capacidad de la flota ({cap_total:,.0f} unds). Se calcularán múltiples viajes.</div>',
                unsafe_allow_html=True
            )

        # ── Botón de cálculo ──────────────────────────────────────────────────
        cvrp_key = f"cvrp_{sel_dia_cvrp}_{sel_vend_cvrp}"
        col_btn1, col_btn2 = st.columns([2, 1])
        with col_btn1:
            calcular_cvrp = st.button("🔄 Calcular Asignación de Flota", type="primary",
                                      use_container_width=True, key="btn_cvrp")
        with col_btn2:
            if st.button("🗑️ Limpiar resultado", use_container_width=True, key="btn_clear_cvrp"):
                keys_del = [k for k in st.session_state if k.startswith("cvrp_")]
                for k in keys_del:
                    del st.session_state[k]
                st.rerun()

        if calcular_cvrp or cvrp_key in st.session_state:
            if calcular_cvrp:
                with st.spinner("Calculando asignación CVRP... puede tardar ~20 segundos."):
                    demanda_r = demanda.reset_index(drop=True)
                    assignments = greedy_cvrp_heterogeneous(demanda_r, flota, use_streets=False)
                    if assignments is False:
                        st.error("🚨 Un pedido supera la capacidad del vehículo más grande.")
                        if cvrp_key in st.session_state:
                            del st.session_state[cvrp_key]
                    else:
                        demanda_r['Vehículo'] = assignments
                        st.session_state[cvrp_key] = demanda_r

            demanda_r = st.session_state.get(cvrp_key, pd.DataFrame())

            if not demanda_r.empty and 'Vehículo' in demanda_r.columns:

                # ── Mapa de rutas por vehículo ─────────────────────────────────
                COLORES_VH = ['#e63946','#2a9d8f','#e9c46a','#f4a261','#264653',
                              '#8338ec','#06d6a0','#fb5607','#ff006e','#3a86ff']
                vehiculos_lista = sorted(demanda_r['Vehículo'].unique())
                VH_COLOR = {v: COLORES_VH[i % len(COLORES_VH)] for i, v in enumerate(vehiculos_lista)}

                st.markdown("#### 🗺️ Mapa de Rutas por Vehículo")
                m_cvrp = folium.Map(location=CENTRO, zoom_start=13, tiles='OpenStreetMap')

                for vh, grupo in demanda_r.groupby('Vehículo'):
                    color = VH_COLOR[vh]
                    g = grupo.reset_index(drop=True)
                    pts = list(zip(g['Latitud'], g['Longitud']))
                    for i in range(len(pts)-1):
                        try:
                            geom = get_route_geometry(pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1])
                            AntPath(geom, color=color, weight=4, opacity=0.8,
                                    delay=1000, tooltip=vh).add_to(m_cvrp)
                        except Exception:
                            folium.PolyLine([pts[i], pts[i+1]], color=color, weight=4).add_to(m_cvrp)
                    for _, row in g.iterrows():
                        popup = (f"<b>{row['ClienteNombre']}</b><br>Vehículo: {vh}<br>"
                                 f"Unds: {row['Cantidad']:,.0f}<br>Total: ${row['Total']:,.0f}")
                        folium.CircleMarker(
                            location=[row['Latitud'], row['Longitud']],
                            radius=8, color=color, fill=True, fill_color=color, fill_opacity=0.85,
                            popup=folium.Popup(popup, max_width=220),
                            tooltip=row['ClienteNombre']
                        ).add_to(m_cvrp)

                # Depósito
                folium.Marker(
                    location=CENTRO,
                    icon=folium.Icon(color='black', icon='home', prefix='fa'),
                    tooltip="Depósito La Campiña"
                ).add_to(m_cvrp)

                # Leyenda
                legend_html = "<div style='background:white;padding:10px;border-radius:8px;font-size:12px;'>"
                for vh, c in VH_COLOR.items():
                    vh_base = vh.split(' – ')[0]
                    legend_html += f"<span style='color:{c};font-size:16px;'>⬤</span> {vh}<br>"
                legend_html += "</div>"
                folium.Marker(
                    [b['lat_max'] - 0.002, b['lon_max'] - 0.01],
                    icon=folium.DivIcon(html=legend_html, icon_size=(200, 200))
                ).add_to(m_cvrp)

                st_folium(m_cvrp, use_container_width=True, height=600, returned_objects=[])

                # ── Resumen por vehículo ───────────────────────────────────────
                st.markdown("#### 📊 Plan de Carga por Vehículo")
                res_vh = demanda_r.groupby('Vehículo').agg(
                    Clientes=('ClienteNombre','count'),
                    Unidades=('Cantidad','sum'),
                    Total=('Total','sum'),
                    Barrios=('Barrio', lambda x: ', '.join(x.dropna().unique()[:3]))
                ).reset_index()

                def get_cap(vh_nombre):
                    for veh in flota:
                        if veh['nombre'] in vh_nombre:
                            return veh['capacidad']
                    return None

                res_vh['Capacidad'] = res_vh['Vehículo'].apply(get_cap)
                res_vh['% Ocupación'] = (
                    res_vh['Unidades'] / res_vh['Capacidad']
                ).where(res_vh['Capacidad'].notna()) * 100

                st.dataframe(
                    res_vh.style
                    .format({'Total':'${:,.0f}','% Ocupación':'{:.0f}%','Unidades':'{:,.0f}'})
                    .background_gradient(subset=['% Ocupación'], cmap='RdYlGn'),
                    use_container_width=True, hide_index=True
                )

                # ── Picking list por vehículo ──────────────────────────────────
                st.markdown("#### 📋 Picking List por Vehículo")
                for vh in sorted(demanda_r['Vehículo'].unique()):
                    con_vh = df_cvrp_base.merge(
                        demanda_r[demanda_r['Vehículo'] == vh][['ClienteNORMA','Vehículo']],
                        on='ClienteNORMA', how='inner'
                    )
                    if con_vh.empty:
                        continue
                    picking = (con_vh.groupby(['CodigoProducto','Producto'])
                               .agg(Cantidad=('Cantidad','sum'), Total=('Total','sum'))
                               .reset_index().sort_values('Producto'))
                    cap_str = f" (Cap: {get_cap(vh):,} unds)" if get_cap(vh) else ""
                    total_vh = picking['Cantidad'].sum()
                    with st.expander(
                        f"🚛 {vh}{cap_str} — "
                        f"{demanda_r[demanda_r['Vehículo']==vh].shape[0]} paradas | "
                        f"{total_vh:,.0f} unds | ${con_vh['Total'].sum():,.0f}",
                        expanded=False
                    ):
                        st.dataframe(
                            picking.style.format({'Total':'${:,.0f}','Cantidad':'{:,.0f}'}),
                            use_container_width=True, hide_index=True
                        )
                        # Lista de tiendas a visitar
                        tiendas_vh = demanda_r[demanda_r['Vehículo']==vh][['ClienteNombre','Barrio','Cantidad','Total']]
                        st.markdown("**Tiendas a entregar:**")
                        st.dataframe(
                            tiendas_vh.style.format({'Total':'${:,.0f}','Cantidad':'{:,.0f}'}),
                            use_container_width=True, hide_index=True
                        )

                # ── Detalle completo ────────────────────────────────────────────
                with st.expander("📄 Ver detalle completo de asignación", expanded=False):
                    cols = [c for c in ['Vehículo','ClienteNombre','Barrio','Vendedor','Cantidad','Total']
                            if c in demanda_r.columns]
                    st.dataframe(
                        demanda_r[cols].sort_values(['Vehículo','ClienteNombre'])
                        .style.format({'Total':'${:,.0f}','Cantidad':'{:,.0f}'}),
                        use_container_width=True, hide_index=True
                    )

# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — MAPA DE COBERTURA
# ══════════════════════════════════════════════════════════════════════════════
with tab_mapa:
    st.markdown('<div class="section-hdr">🗺️ Cobertura de Clientes</div>', unsafe_allow_html=True)

    fc1, fc2, fc3, fc4 = st.columns(4)
    with fc1: fs_sem   = st.selectbox("📅 Semana",   ["Todas"] + sorted(df_geo['Fecha'].dt.strftime('%Y-W%V').unique()), key="m_sem")
    with fc2: fs_fec   = st.selectbox("📆 Día",      ["Todos"] + sorted(df_geo['FechaStr'].unique()), key="m_fec")
    with fc3: fs_vend  = st.selectbox("👤 Vendedor", ["Todos"] + vendedores_lista, key="m_vend")
    with fc4: fs_ruta  = st.selectbox("🗓️ Ruta",    ["Todas"] + sorted(df_geo['Ruta'].dropna().unique()), key="m_ruta")

    df_fm = df_geo.copy()
    df_fm['AnoSem'] = df_fm['Fecha'].dt.strftime('%Y-W%V')
    if fs_sem  != "Todas": df_fm = df_fm[df_fm['AnoSem']   == fs_sem]
    if fs_fec  != "Todos": df_fm = df_fm[df_fm['FechaStr'] == fs_fec]
    if fs_vend != "Todos": df_fm = df_fm[df_fm['Vendedor'] == fs_vend]
    if fs_ruta != "Todas": df_fm = df_fm[df_fm['Ruta']     == fs_ruta]

    df_mapa = (df_fm.groupby(['ClienteNORMA','ClienteNombre','Vendedor','Latitud','Longitud','Barrio'], dropna=False)
               .agg(Pedidos=('NoPedido','nunique'), Total=('Total','sum'), Unidades=('Cantidad','sum'))
               .reset_index())

    if df_mapa.empty:
        st.warning("Sin datos para el filtro seleccionado.")
    else:
        m_cob = folium.Map(location=CENTRO, zoom_start=13, tiles='OpenStreetMap')
        cluster_cob = MarkerCluster(name="Clientes").add_to(m_cob)
        for _, row in df_mapa.iterrows():
            color = COLOR_MAP.get(row['Vendedor'], '#888')
            popup_html = (f"<b>{row['ClienteNombre']}</b><br>"
                          f"Barrio: {row.get('Barrio','N/A')}<br>"
                          f"Vendedor: {row['Vendedor']}<br>"
                          f"Pedidos: {int(row['Pedidos'])}<br>"
                          f"Total: ${row['Total']:,.0f}")
            folium.CircleMarker(
                location=[row['Latitud'], row['Longitud']],
                radius=7, color=color, fill=True, fill_color=color, fill_opacity=0.8,
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=row['ClienteNombre']
            ).add_to(cluster_cob)

        legend = "<div style='font-size:12px;background:white;padding:8px;border-radius:6px;'>"
        for v, c in COLOR_MAP.items():
            legend += f"<span style='color:{c};font-size:18px;'>●</span> {v}<br>"
        legend += "</div>"
        folium.Marker(CENTRO, icon=folium.DivIcon(html=legend, icon_size=(160,80))).add_to(m_cob)
        st_folium(m_cob, use_container_width=True, height=550, returned_objects=[])
        st.caption(f"Mostrando {len(df_mapa)} tiendas únicas con coordenadas.")
