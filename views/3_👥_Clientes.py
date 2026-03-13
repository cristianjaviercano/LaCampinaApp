import streamlit as st
import pandas as pd
import plotly.express as px
from utils.data_loader import load_data

st.set_page_config(page_title="Clientes", page_icon="👥", layout="wide")
st.title("👥 Comportamiento de Clientes")
st.markdown("Análisis demográfico y transaccional.")

data = load_data(st.session_state.get("fecha_historica"))
if data is None:
    st.error("No hay datos disponibles.")
    st.stop()

df_clientes = data['clientes'].copy()
# Usar compras_detalle (líneas completas) para el análisis RFM
df_det = data['compras_detalle'].copy()

if df_det.empty:
    st.warning("No hay datos de compras. Ve al Gestor Base Maestra → Compras y carga un Purchase Order.")
    st.stop()

df_det['Fecha'] = pd.to_datetime(df_det['Fecha'], errors='coerce')
max_date = df_det['Fecha'].max()

# ── Análisis RFM ──────────────────────────────────────────────────────────────
rfm = df_det.groupby('ClienteCodigo').agg(
    Recencia_Dias=('Fecha',   lambda x: (max_date - x.max()).days),
    Frecuencia_Pedidos=('NoPedido', 'nunique'),
    Valor_Monetario=('Total', 'sum')
).reset_index().rename(columns={'ClienteCodigo': 'Codigo'})

# Normalizar codigo para merge
df_clientes['Codigo'] = df_clientes['Codigo'].astype(str)
rfm['Codigo'] = rfm['Codigo'].astype(str)

df_clientes_rfm = pd.merge(df_clientes, rfm, how='left', on='Codigo')
df_clientes_rfm['Recencia_Dias']      = df_clientes_rfm['Recencia_Dias'].fillna(999)
df_clientes_rfm['Frecuencia_Pedidos'] = df_clientes_rfm['Frecuencia_Pedidos'].fillna(0)
df_clientes_rfm['Valor_Monetario']    = df_clientes_rfm['Valor_Monetario'].fillna(0)

# Columna nombre
nombre_col = 'Nombre' if 'Nombre' in df_clientes_rfm.columns else df_clientes_rfm.columns[1]

# ── Métricas ──────────────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total de Clientes Registrados", f"{len(df_clientes):,}")
with col2:
    ciudades_unicas = df_clientes['Ciudad'].nunique() if 'Ciudad' in df_clientes.columns else 0
    st.metric("Ciudades con Cobertura", ciudades_unicas)
with col3:
    activos = int((df_clientes_rfm['Frecuencia_Pedidos'] > 0).sum())
    st.metric("Clientes Activos (Con Compras)", f"{activos:,}")
with col4:
    retencion = (activos / len(df_clientes) * 100) if len(df_clientes) > 0 else 0
    st.metric("Tasa de Conversión/Retención", f"{retencion:.1f}%")

st.markdown("---")

c1, c2 = st.columns(2)

with c1:
    st.subheader("Matriz de Clientes (Fidelidad vs Valor)")
    df_plot = df_clientes_rfm[df_clientes_rfm['Frecuencia_Pedidos'] > 0].copy()
    
    def segment(row):
        if row['Recencia_Dias'] <= 15 and row['Frecuencia_Pedidos'] >= 3: return "⭐ Cliente Fiel"
        elif row['Recencia_Dias'] > 30 and row['Frecuencia_Pedidos'] >= 3: return "💤 Cliente Durmiente"
        elif row['Frecuencia_Pedidos'] == 1: return "🆕 Compra Única"
        else: return "🔄 Cliente Regular"
    
    if not df_plot.empty:
        df_plot['Segmento'] = df_plot.apply(segment, axis=1)
        fig_matrix = px.scatter(
            df_plot, x='Frecuencia_Pedidos', y='Valor_Monetario', color='Segmento',
            hover_name=nombre_col, size='Valor_Monetario',
            color_discrete_map={
                "⭐ Cliente Fiel": "#2e7d32",
                "🔄 Cliente Regular": "#81c784",
                "🆕 Compra Única": "#4dd0e1",
                "💤 Cliente Durmiente": "#ef5350"
            }, template='plotly_white'
        )
        st.plotly_chart(fig_matrix, use_container_width=True)
    else:
        st.info("No hay suficientes datos para la matriz.")

with c2:
    if 'Barrio' in df_clientes.columns and df_clientes['Barrio'].notna().any():
        st.subheader("Penetración Demográfica por Barrio")
        barrio_counts = df_clientes['Barrio'].value_counts().reset_index()
        barrio_counts.columns = ['Barrio', 'Cantidad']
        fig = px.bar(barrio_counts.head(10), x='Cantidad', y='Barrio', orientation='h',
                     color='Cantidad', color_continuous_scale='Greens', template='plotly_white')
        fig.update_layout(yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig, use_container_width=True)
    elif 'Ciudad' in df_clientes.columns:
        st.subheader("Top Ciudades por Número de Clientes")
        ciudad_counts = df_clientes['Ciudad'].value_counts().reset_index()
        ciudad_counts.columns = ['Ciudad', 'Cantidad']
        fig = px.bar(ciudad_counts.head(10), x='Cantidad', y='Ciudad', orientation='h',
                     color='Cantidad', color_continuous_scale='Greens', template='plotly_white')
        fig.update_layout(yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

with st.expander("📄 Ver Base de Datos RFM de Clientes", expanded=False):
    cols_rfm = [c for c in ['Codigo', nombre_col, 'Ciudad', 'Recencia_Dias', 'Frecuencia_Pedidos', 'Valor_Monetario', 'Activo'] if c in df_clientes_rfm.columns]
    st.dataframe(df_clientes_rfm[cols_rfm], use_container_width=True)
