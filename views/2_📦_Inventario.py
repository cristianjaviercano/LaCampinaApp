import streamlit as st
import pandas as pd
import plotly.express as px
from utils.data_loader import load_data

st.title("Inventario")
st.markdown("Estado de stock en tiempo real, rotación de productos y proyección de abastecimiento.")

data = load_data()
if data is None:
    st.error("No hay datos disponibles.")
    st.stop()

df_productos = data['productos'].copy()
df_detalle = data['compras_detalle'].copy()

if df_productos.empty or df_detalle.empty:
    st.warning("Faltan datos de productos o historial de compras. Verifica la base maestra.")
    st.stop()

# ── StockAsignado: pedidos con Estado "Asignado" aún no despachados ─────────
# El stock físico sólo se descuenta al momento del despacho.
# "StockAsignado" refleja unidades comprometidas en pedidos pendientes de despacho.
df_productos['Codigo'] = df_productos['Codigo'].astype(str)

if 'Estado' in df_detalle.columns and 'Cantidad' in df_detalle.columns:
    df_asignado = (
        df_detalle[df_detalle['Estado'].str.upper().isin(["ASIGNADO", "PENDIENTE"])]
        .groupby('CodigoProducto')['Cantidad']
        .sum()
        .reset_index()
        .rename(columns={'CodigoProducto': 'Codigo', 'Cantidad': 'StockAsignado'})
    )
    df_asignado['Codigo'] = df_asignado['Codigo'].astype(str)
    df_productos = df_productos.merge(df_asignado, on='Codigo', how='left')
else:
    df_productos['StockAsignado'] = 0

df_productos['StockAsignado'] = df_productos['StockAsignado'].fillna(0)

# Stock físico (columna "Stock" si existe en maestros, 0 si no)
if 'Stock' not in df_productos.columns:
    df_productos['Stock'] = 0

df_productos['StockDisponible'] = df_productos['Stock'] - df_productos['StockAsignado']

# ── Categoría ───────────────────────────────────────────────────────────────
if 'Categoria' not in df_productos.columns:
    df_productos['Categoria'] = "Sin Categorizar"
else:
    df_productos['Categoria'] = df_productos['Categoria'].fillna("Sin Categorizar")

# ── Sidebar ──────────────────────────────────────────────────────────────────
st.sidebar.header("Filtros de Inventario")
categorias = ['Todas'] + sorted(df_productos['Categoria'].unique().tolist())
if 'Todas' in categorias:
    categorias.remove('Todas')
categorias.insert(0, 'Todas')
sel_cat = st.sidebar.selectbox("Filtrar por Categoría", categorias)
dias_proyeccion = st.sidebar.slider("Días de proyección de abastecimiento", 1, 60, 7)

# ── Historial de ventas ──────────────────────────────────────────────────────
df_detalle['Fecha'] = pd.to_datetime(df_detalle['Fecha'], errors='coerce')
fechas_validas = df_detalle['Fecha'].dropna()
dias_operacion = max((fechas_validas.max() - fechas_validas.min()).days, 1) if not fechas_validas.empty else 1

historico_prod = (
    df_detalle.groupby('CodigoProducto')
    .agg(CantidadVendida=('Cantidad', 'sum'), IngresosTotales=('Total', 'sum'))
    .reset_index()
    .rename(columns={'CodigoProducto': 'Codigo'})
)
historico_prod['Codigo'] = historico_prod['Codigo'].astype(str)

df_inventario = pd.merge(df_productos, historico_prod, on='Codigo', how='left')
df_inventario['CantidadVendida'] = df_inventario['CantidadVendida'].fillna(0)
df_inventario['IngresosTotales'] = df_inventario['IngresosTotales'].fillna(0)
df_inventario['Demanda_Diaria'] = df_inventario['CantidadVendida'] / dias_operacion
df_inventario['StockRecomendado'] = (df_inventario['Demanda_Diaria'] * dias_proyeccion).round().astype(int)

if sel_cat != 'Todas':
    df_inventario = df_inventario[df_inventario['Categoria'] == sel_cat]

# ════════════════════════════════════════════════════════════════════════════
# SECCIÓN 1 — Estado actual del stock
# ════════════════════════════════════════════════════════════════════════════
st.markdown("### 📊 Estado Actual del Stock")
st.caption(f"Basado en {dias_operacion} días de historial · StockDisponible = Stock Físico − Stock Asignado (pedidos pendientes de despacho)")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("📦 Referencias totales", len(df_inventario))
with col2:
    total_asignado = int(df_inventario['StockAsignado'].sum())
    st.metric("🔒 Unidades asignadas", f"{total_asignado:,}")
with col3:
    disponible = int(df_inventario['StockDisponible'].sum())
    st.metric("✅ Stock disponible neto", f"{disponible:,}")
with col4:
    sin_stock = int((df_inventario['StockDisponible'] <= 0).sum())
    st.metric("⚠️ Refs. sin stock libre", sin_stock, delta_color="inverse")

# Alertas de stock comprometido
df_critico = df_inventario[df_inventario['StockDisponible'] < 0].copy()
if not df_critico.empty:
    st.error(
        f"**{len(df_critico)} producto(s) con stock sobrecomprometido** "
        f"(StockDisponible negativo). Revisar antes del próximo despacho."
    )
    st.dataframe(
        df_critico[['Codigo', 'Nombre', 'Stock', 'StockAsignado', 'StockDisponible']]
        .sort_values('StockDisponible'),
        use_container_width=True, hide_index=True
    )

st.markdown("---")

# ════════════════════════════════════════════════════════════════════════════
# SECCIÓN 2 — Rotación y análisis ABC
# ════════════════════════════════════════════════════════════════════════════
st.subheader("Rotación y Rentabilidad de Productos")
st.caption(f"Historial operativo: {dias_operacion} días")

tab1, tab2, tab3 = st.tabs(["🔥 Top Movimiento", "🐢 Lento Movimiento", "💼 Clasificación ABC"])

with tab1:
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        top_u = df_inventario.nlargest(10, 'CantidadVendida')
        fig1 = px.bar(
            top_u, x='CantidadVendida', y='Nombre', orientation='h',
            title='Top 10 por Unidades Vendidas',
            color='CantidadVendida', color_continuous_scale='Greens'
        )
        fig1.update_layout(yaxis={'categoryorder': 'total ascending'}, showlegend=False)
        st.plotly_chart(fig1, use_container_width=True)
    with col_t2:
        top_i = df_inventario.nlargest(10, 'IngresosTotales')
        fig2 = px.bar(
            top_i, x='IngresosTotales', y='Nombre', orientation='h',
            title='Top 10 por Ingresos ($)',
            color='IngresosTotales', color_continuous_scale='Blues'
        )
        fig2.update_layout(yaxis={'categoryorder': 'total ascending'}, showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)

with tab2:
    lento = df_inventario[df_inventario['CantidadVendida'] > 0].nsmallest(15, 'CantidadVendida')
    fig3 = px.bar(
        lento, x='CantidadVendida', y='Nombre', orientation='h',
        title='15 Productos de Menor Rotación (con movimiento > 0)',
        color='CantidadVendida', color_continuous_scale='Reds_r'
    )
    fig3.update_layout(yaxis={'categoryorder': 'total descending'}, showlegend=False)
    st.plotly_chart(fig3, use_container_width=True)

with tab3:
    df_abc = df_inventario[df_inventario['IngresosTotales'] > 0].sort_values('IngresosTotales', ascending=False).copy()
    total_rev = df_abc['IngresosTotales'].sum()
    if total_rev > 0:
        df_abc['CumPct'] = df_abc['IngresosTotales'].cumsum() / total_rev
        df_abc['ABC'] = df_abc['CumPct'].apply(
            lambda p: 'A — 80% ingresos' if p <= 0.80 else ('B — 15% ingresos' if p <= 0.95 else 'C — 5% ingresos')
        )
        abc_sum = df_abc.groupby('ABC').agg(Referencias=('Codigo', 'count'), Ingresos=('IngresosTotales', 'sum')).reset_index()
        fig_abc = px.pie(
            abc_sum, values='Ingresos', names='ABC', hole=0.5,
            title='Distribución de Ingresos por Clase ABC',
            color='ABC', color_discrete_map={
                'A — 80% ingresos': '#1b5e20',
                'B — 15% ingresos': '#4caf50',
                'C — 5% ingresos': '#a5d6a7',
            }
        )
        fig_abc.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_abc, use_container_width=True)
    else:
        st.info("Sin datos de ingresos suficientes para la clasificación ABC.")

st.markdown("---")

# ════════════════════════════════════════════════════════════════════════════
# SECCIÓN 3 — Proyección de abastecimiento
# ════════════════════════════════════════════════════════════════════════════
st.subheader(f"Proyección de Abastecimiento — {dias_proyeccion} días")

df_proy = df_inventario[df_inventario['StockRecomendado'] > 0].sort_values('StockRecomendado', ascending=False)

if not df_proy.empty:
    top3 = df_proy.head(3)
    alerta = f"**Sugerencia de compra para los próximos {dias_proyeccion} días:**\n"
    for _, r in top3.iterrows():
        alerta += f"- **{r['StockRecomendado']:,} unds** de _{r['Nombre']}_\n"
    if len(df_proy) > 3:
        alerta += f"*(+{len(df_proy) - 3} referencias adicionales — ver tabla)*"
    st.info(alerta)

    fig_p = px.bar(
        df_proy.head(20), x='Nombre', y='StockRecomendado',
        title='Top 20 — Unidades Sugeridas para Mantener en Bodega',
        color='StockRecomendado', color_continuous_scale='Oranges'
    )
    fig_p.update_layout(xaxis_tickangle=-35)
    st.plotly_chart(fig_p, use_container_width=True)

with st.expander("Ver tabla completa de inventario y proyección", expanded=False):
    cols = [c for c in ['Codigo', 'Nombre', 'Categoria', 'Stock', 'StockAsignado', 'StockDisponible',
                        'CantidadVendida', 'IngresosTotales', 'Demanda_Diaria', 'StockRecomendado']
            if c in df_inventario.columns]
    df_show = df_inventario[cols].copy()
    df_show['Demanda_Diaria'] = df_show['Demanda_Diaria'].round(2)
    df_show.rename(columns={
        'Codigo': 'Código',
        'CantidadVendida': 'Vendidas',
        'IngresosTotales': 'Ingresos ($)',
        'Demanda_Diaria': 'Demanda/día',
        'StockRecomendado': f'Recomendado ({dias_proyeccion}d)',
    }, inplace=True)
    st.dataframe(
        df_show.sort_values(f'Recomendado ({dias_proyeccion}d)', ascending=False),
        use_container_width=True, hide_index=True
    )
