import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils.data_loader import load_data

st.set_page_config(page_title="Analítica Histórica", page_icon="📈", layout="wide")
st.title("📈 Inteligencia de Preventa Histórica")
st.markdown("Analiza el comportamiento de ventas a lo largo del tiempo, evalúa el rendimiento por vendedor y audita rutas de visita.")

data = load_data(st.session_state.get("fecha_historica"))
if data is None or data['compras_detalle'].empty:
    st.error("No hay datos de compras disponibles. Carga un Purchase Order en el Gestor Base Maestra.")
    st.stop()

df_det = data['compras_detalle'].copy()
df_cli = data['clientes'].copy()
if 'Latitud' in df_cli.columns and 'Longitud' in df_cli.columns:
    df_cli = df_cli.dropna(subset=['Latitud', 'Longitud'])

df_det['Fecha'] = pd.to_datetime(df_det['Fecha'], errors='coerce')

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.header("Filtros Temporales y Operativos")
min_date = df_det['Fecha'].min().date()
max_date = df_det['Fecha'].max().date()
date_range = st.sidebar.date_input("Rango de Fechas", [min_date, max_date], min_value=min_date, max_value=max_date)
vendedores = ["Todos"] + sorted(df_det['Vendedor'].dropna().unique().tolist())
sel_vendedor = st.sidebar.selectbox("Filtro Vendedor", vendedores)

# Aplicar filtros
df_filtered = df_det.copy()
if len(date_range) == 2:
    start, end = date_range
    df_filtered = df_filtered[(df_filtered['Fecha'].dt.date >= start) & (df_filtered['Fecha'].dt.date <= end)]
if sel_vendedor != "Todos":
    df_filtered = df_filtered[df_filtered['Vendedor'] == sel_vendedor]

st.markdown("---")

# ── KPIs ──────────────────────────────────────────────────────────────────────
st.subheader("📊 Indicadores Clave de Rendimiento (KPIs)")
c1, c2, c3, c4 = st.columns(4)

total_ventas      = df_filtered['Total'].sum()
pedidos_unicos    = df_filtered['NoPedido'].nunique()
clientes_visitados = df_filtered['ClienteCodigo'].nunique()
ticket_promedio   = total_ventas / pedidos_unicos if pedidos_unicos > 0 else 0

c1.metric("💰 Recaudo Total Periodo",     f"${total_ventas:,.0f}")
c2.metric("🛍️ Ticket Promedio por Pedido", f"${ticket_promedio:,.0f}")
c3.metric("🛒 Órdenes Únicas",            f"{pedidos_unicos:,}")
c4.metric("👥 Clientes Visitados",         f"{clientes_visitados:,}")

st.markdown("---")

# ── Tendencia diaria + Métodos de pago ───────────────────────────────────────
col_ts, col_pay = st.columns([2, 1])

with col_ts:
    st.subheader("📅 Tendencia de Recaudo Diario")
    ventas_diarias = df_filtered.groupby(df_filtered['Fecha'].dt.date)['Total'].sum().reset_index()
    ventas_diarias.columns = ['Fecha', 'Total']
    fig_ts = px.line(ventas_diarias, x='Fecha', y='Total', markers=True,
                     title="Ventas Agrupadas por Día", color_discrete_sequence=['#1f77b4'],
                     template='plotly_white')
    fig_ts.update_layout(xaxis_title="Fecha", yaxis_title="Recaudo ($)")
    st.plotly_chart(fig_ts, use_container_width=True)

with col_pay:
    st.subheader("💳 Métodos de Pago")
    df_pedidos_pago = df_filtered.groupby('NoPedido').agg(MetodoPago=('MetodoPago', 'first'), Total=('Total', 'sum')).reset_index()
    metodos = df_pedidos_pago['MetodoPago'].value_counts().reset_index()
    metodos.columns = ['Método', 'Cantidad']
    fig_pie = px.pie(metodos, values='Cantidad', names='Método', hole=0.4,
                     color_discrete_sequence=px.colors.qualitative.Pastel)
    st.plotly_chart(fig_pie, use_container_width=True)

st.markdown("---")

# ── Rendimiento vendedor + Frecuencia clientes ────────────────────────────────
col_ven, col_freq = st.columns(2)

with col_ven:
    st.subheader("🏆 Rendimiento por Vendedor")
    if sel_vendedor == "Todos":
        rend = df_filtered.groupby('Vendedor')['Total'].sum().reset_index().sort_values('Total', ascending=False)
        fig_ven = px.bar(rend, x='Total', y='Vendedor', orientation='h',
                         color='Total', color_continuous_scale='Blues', template='plotly_white',
                         title="Recaudo Total ($) por Preventista")
        fig_ven.update_layout(yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig_ven, use_container_width=True)
    else:
        st.info("Desactiva el filtro de Vendedor para ver el ranking general.")

with col_freq:
    st.subheader("🔄 Frecuencia de Compra de Clientes")
    freq_real = df_filtered.groupby('ClienteCodigo')['NoPedido'].nunique().reset_index()
    freq_real.columns = ['ClienteCodigo', 'Total Visitas']
    freq_real['ClienteCodigo'] = freq_real['ClienteCodigo'].astype(str)

    # Intentar agregar nombre del cliente
    if not df_cli.empty and 'Nombre' in df_cli.columns:
        df_cli['Codigo'] = df_cli['Codigo'].astype(str)
        freq_merge = pd.merge(freq_real, df_cli[['Codigo', 'Nombre']].drop_duplicates(),
                              left_on='ClienteCodigo', right_on='Codigo', how='left')
        freq_merge['Nombre'] = freq_merge['Nombre'].fillna("Cliente " + freq_merge['ClienteCodigo'])
    else:
        freq_merge = freq_real.copy()
        freq_merge['Nombre'] = "Cliente " + freq_merge['ClienteCodigo']

    top_freq = freq_merge.sort_values('Total Visitas', ascending=False).head(15)
    fig_freq = px.bar(top_freq, x='Total Visitas', y='Nombre', orientation='h',
                      color='Total Visitas', color_continuous_scale='Teal', template='plotly_white')
    fig_freq.update_layout(yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig_freq, use_container_width=True)

st.markdown("---")

# ── Ventas semanales y mensuales ──────────────────────────────────────────────
st.subheader("📅 Análisis Semanal y Mensual")
tab_sem, tab_mes = st.tabs(["Por Semana", "Por Mes"])

with tab_sem:
    df_filtered['Semana'] = df_filtered['Fecha'].dt.to_period('W').astype(str)
    sem_data = df_filtered.groupby('Semana').agg(Total=('Total', 'sum'), Pedidos=('NoPedido', 'nunique')).reset_index()
    fig_sem = px.bar(sem_data, x='Semana', y='Total', color='Total',
                     color_continuous_scale='Greens', template='plotly_white', title="Recaudo Semanal")
    st.plotly_chart(fig_sem, use_container_width=True)
    st.dataframe(sem_data.style.format({'Total': '${:,.0f}'}), use_container_width=True, hide_index=True)

with tab_mes:
    df_filtered['Mes'] = df_filtered['Fecha'].dt.to_period('M').astype(str)
    mes_data = df_filtered.groupby('Mes').agg(Total=('Total', 'sum'), Pedidos=('NoPedido', 'nunique')).reset_index()
    fig_mes = px.bar(mes_data, x='Mes', y='Total', color='Total',
                     color_continuous_scale='Blues', template='plotly_white', title="Recaudo Mensual")
    st.plotly_chart(fig_mes, use_container_width=True)
    st.dataframe(mes_data.style.format({'Total': '${:,.0f}'}), use_container_width=True, hide_index=True)

st.markdown("---")

# ── Auditoría de rutas ────────────────────────────────────────────────────────
st.subheader("🗺️ Auditoría de Rutas Históricas")
st.markdown("Selecciona **un Vendedor** y **una Fecha** para ver su recorrido en el mapa.")

col_f1, col_f2 = st.columns(2)
with col_f1:
    ven_auditoria = st.selectbox("Preventista a Auditar", vendedores, key="ven_aud")
with col_f2:
    if ven_auditoria != "Todos":
        fechas_disp = sorted(df_det[df_det['Vendedor'] == ven_auditoria]['Fecha'].dt.date.unique())
    else:
        fechas_disp = sorted(df_det['Fecha'].dt.date.unique())
    dia_auditoria = st.selectbox("Día Específico", fechas_disp if fechas_disp else [max_date], key="dia_aud")

if ven_auditoria != "Todos" and dia_auditoria:
    df_audi = df_det[
        (df_det['Vendedor'] == ven_auditoria) &
        (df_det['Fecha'].dt.date == dia_auditoria)
    ].copy()

    if df_audi.empty:
        st.warning("Ese vendedor no reportó ventas en esa fecha.")
    elif df_cli.empty or 'Latitud' not in df_cli.columns:
        st.warning("⚠️ No hay coordenadas de clientes para dibujar la ruta. Asegúrate de tener la base de Clientes con Latitud/Longitud.")
    else:
        rutas_time = (df_audi.groupby('NoPedido', as_index=False)
                      .agg(ClienteCodigo=('ClienteCodigo', 'first'), Total=('Total', 'sum')))
        rutas_time['ClienteCodigo'] = rutas_time['ClienteCodigo'].astype(str)
        df_cli['Codigo'] = df_cli['Codigo'].astype(str)
        rutas_time = pd.merge(rutas_time, df_cli[['Codigo', 'Nombre', 'Latitud', 'Longitud', 'Barrio']],
                              left_on='ClienteCodigo', right_on='Codigo', how='inner')
        rutas_time['Paso Secuencial'] = range(1, len(rutas_time)+1)

        if rutas_time.empty:
            st.warning("No se encontraron coordenadas para los clientes de este vendedor.")
        else:
            map_style_aud = st.selectbox("Mapa Base", ["open-street-map", "carto-positron", "carto-darkmatter"], key="aud_map")
            fig_map = px.line_mapbox(rutas_time, lat="Latitud", lon="Longitud", zoom=13, height=500)
            fig_map.add_trace(go.Scattermapbox(
                lat=rutas_time['Latitud'], lon=rutas_time['Longitud'],
                mode='markers+text', marker=go.scattermapbox.Marker(size=12, color='orange'),
                text=rutas_time['Paso Secuencial'].astype(str),
                hovertext=rutas_time['Nombre'] + "<br>Visita #" + rutas_time['Paso Secuencial'].astype(str) + "<br>Venta: $" + rutas_time['Total'].apply(lambda x: f"{x:,.0f}")
            ))
            fig_map.update_layout(mapbox_style=map_style_aud, margin={"r":0,"t":0,"l":0,"b":0})
            st.plotly_chart(fig_map, use_container_width=True)
            st.dataframe(rutas_time[['Paso Secuencial', 'Nombre', 'Barrio', 'Total']].rename(columns={'Total': 'Venta ($)'}), use_container_width=True, hide_index=True)
else:
    st.info("👈 Escoge un Vendedor y una Fecha para generar el recorrido.")
