import streamlit as st
import pandas as pd
import plotly.express as px
from utils.data_loader import load_data

st.set_page_config(page_title="Inventario y Operaciones", page_icon="📦", layout="wide")
st.title("📦 Gestión y Proyección de Inventario")
st.markdown("Análisis de rotación de productos, ventas y proyección de inventario operativo.")

data = load_data(st.session_state.get("fecha_historica"))
if data is None:
    st.error("No hay datos disponibles.")
    st.stop()

df_productos = data['productos'].copy()
df_detalle = data['compras_detalle'].copy()

if df_productos.empty or df_detalle.empty:
    st.warning("Faltan datos de productos o historial de compras. Verifica la base maestra.")
    st.stop()

# 1. Ajuste del inventario maestro
# Inicializamos el inventario físico en cero, asumiendo la nueva lógica operativa.
df_productos['Stock_Fisico'] = 0

# 2. Construcción del "Inventario de Ventas" basado en el movimiento histórico
# Calculamos las cantidades totales vendidas y el ingreso por producto
historico_prod = df_detalle.groupby('CodigoProducto').agg(
    CantidadVendida=('Cantidad', 'sum'),
    IngresosTotales=('Total', 'sum')
).reset_index()

# Cruzamos con la base de productos
# Convertir ambos a str para evitar errores de tipo al cruzar
df_productos['Codigo'] = df_productos['Codigo'].astype(str)
historico_prod['CodigoProducto'] = historico_prod['CodigoProducto'].astype(str)

df_inventario = pd.merge(df_productos, historico_prod, left_on='Codigo', right_on='CodigoProducto', how='left')
df_inventario['CantidadVendida'] = df_inventario['CantidadVendida'].fillna(0)
df_inventario['IngresosTotales'] = df_inventario['IngresosTotales'].fillna(0)

# Asegurar que exista la columna 'Categoria'
if 'Categoria' not in df_inventario.columns:
    df_inventario['Categoria'] = "Sin Categorizar"
else:
    df_inventario['Categoria'] = df_inventario['Categoria'].fillna("Sin Categorizar")

# Sidebar filter
st.sidebar.header("Filtros de Inventario")
categorias = ['Todas'] + list(df_inventario['Categoria'].unique())
categorias.sort()
# Mover 'Todas' al principio de la lista de forma explícita si el sort lo movió
if 'Todas' in categorias:
    categorias.remove('Todas')
categorias.insert(0, 'Todas')

sel_cat = st.sidebar.selectbox("Filtrar por Categoría", categorias)
if sel_cat != 'Todas':
    df_inventario = df_inventario[df_inventario['Categoria'] == sel_cat]

# Cálculo de Proyección de Compras
# Determinamos el periodo operativo en días basado en las fechas de los pedidos
df_detalle['Fecha'] = pd.to_datetime(df_detalle['Fecha'], errors='coerce')
fechas_validas = df_detalle['Fecha'].dropna()

if not fechas_validas.empty:
    dias_operacion = (fechas_validas.max() - fechas_validas.min()).days
else:
    dias_operacion = 1

if dias_operacion <= 0:
    dias_operacion = 1 # prevención división por cero

# Asumimos que queremos proyectar el inventario necesario para X días
dias_proyeccion = st.sidebar.slider("Días de Proyección de Inventario a Mantener", min_value=1, max_value=60, value=7)

df_inventario['Demanda_Diaria_Promedio'] = df_inventario['CantidadVendida'] / dias_operacion
df_inventario['Inventario_Proyectado'] = (df_inventario['Demanda_Diaria_Promedio'] * dias_proyeccion).apply(lambda x: int(round(x)))

# Métricas Globales
st.markdown("### 📊 Indicadores Generales de Movimiento")
st.caption(f"Basado en {dias_operacion} días de historial de ventas")
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("🔖 Referencias con Movimiento", len(df_inventario[df_inventario['CantidadVendida'] > 0]))
with col2:
    st.metric("📦 Unidades Movilizadas", f"{df_inventario['CantidadVendida'].sum():,.0f}")
with col3:
    st.metric("💰 Ingresos Totales Generados", f"${df_inventario['IngresosTotales'].sum():,.0f}")
with col4:
    st.metric("🚚 Unidades a Comprar (Proyectado)", f"{df_inventario['Inventario_Proyectado'].sum():,.0f}")

st.markdown("---")

# Análisis 1: Top Productos y Lento Movimiento
st.subheader("Análisis 1: Rotación y Rentabilidad de Productos")

tab1, tab2, tab3 = st.tabs(["🔥 Top Movimiento y Rentabilidad", "🐢 Lento Movimiento", "💼 ABC por Ingresos"])

with tab1:
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        # Top 10 por unidades
        top_unidades = df_inventario.nlargest(10, 'CantidadVendida')
        fig1 = px.bar(top_unidades, x='CantidadVendida', y='Nombre', orientation='h', 
                      title='Top 10 Productos Más Vendidos (Unidades)',
                      color='CantidadVendida', color_continuous_scale='Greens')
        fig1.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig1, use_container_width=True)
    with col_t2:
        # Top 10 por rentabilidad/ingresos
        top_ingresos = df_inventario.nlargest(10, 'IngresosTotales')
        fig2 = px.bar(top_ingresos, x='IngresosTotales', y='Nombre', orientation='h', 
                      title='Top 10 Productos de Mayor Ingreso ($)',
                      color='IngresosTotales', color_continuous_scale='Blues')
        fig2.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig2, use_container_width=True)

with tab2:
    st.markdown("#### Productos con Menor Rotación")
    st.write("Muestra los productos que han tenido algún movimiento pero en muy bajas cantidades.")
    lento_movimiento = df_inventario[df_inventario['CantidadVendida'] > 0].nsmallest(15, 'CantidadVendida')
    fig3 = px.bar(lento_movimiento, x='CantidadVendida', y='Nombre', orientation='h', 
                  title='15 Productos de Lento Movimiento (Unidades > 0)',
                  color='CantidadVendida', color_continuous_scale='Reds_r')
    fig3.update_layout(yaxis={'categoryorder':'total descending'})
    st.plotly_chart(fig3, use_container_width=True)

with tab3:
    st.markdown("#### Clasificación ABC de Productos (Basado en Ingresos)")
    # Calcular ABC por ingresos
    df_abc = df_inventario[df_inventario['IngresosTotales'] > 0].sort_values('IngresosTotales', ascending=False).copy()
    total_revenue = df_abc['IngresosTotales'].sum()
    if total_revenue > 0:
        df_abc['CumSum_%'] = df_abc['IngresosTotales'].cumsum() / total_revenue
        
        def class_abc(pct):
            if pct <= 0.80: return 'A (80% de Ingresos)'
            elif pct <= 0.95: return 'B (15% de Ingresos)'
            else: return 'C (5% de Ingresos)'
        df_abc['Clase_ABC'] = df_abc['CumSum_%'].apply(class_abc)
        
        abc_summary = df_abc.groupby('Clase_ABC').agg(
            Referencias=('Codigo', 'count'),
            Ingresos=('IngresosTotales', 'sum')
        ).reset_index()
        
        fig_abc = px.pie(abc_summary, values='Ingresos', names='Clase_ABC', hole=0.5,
                         title='Distribución de Ingresos por Clasificación ABC',
                         color='Clase_ABC', color_discrete_map={
                             'A (80% de Ingresos)': '#1b5e20',
                             'B (15% de Ingresos)': '#4caf50',
                             'C (5% de Ingresos)': '#a5d6a7'
                         })
        fig_abc.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_abc, use_container_width=True)
    else:
        st.info("No hay suficientes datos de ingresos para generar la clasificación ABC.")

st.markdown("---")

# Análisis 2: Proyección de Compras
st.subheader(f"Análisis 2: Proyección de Inventario a Mantener ({dias_proyeccion} días)")
st.markdown(f"Tomando como base un histórico operativo de **{dias_operacion} días**, esta gráfica señala la cantidad proyectada y sugerida de unidades que deben solicitarse a la central para mantener la bodega abastecida durante los próximos **{dias_proyeccion} días**, mitigando la rotura de inventario.")

df_top_proyectado = df_inventario[df_inventario['Inventario_Proyectado'] > 0].sort_values('Inventario_Proyectado', ascending=False)

if not df_top_proyectado.empty:
    top_3 = df_top_proyectado.head(3)
    alerta_txt = f"**💡 Sugerencia Estratégica de Abastecimiento:** Para garantizar la operación sin quiebre de stock en los próximos **{dias_proyeccion} días**, sugerimos solicitar urgentemente a fábrica:\n"
    for _, fila in top_3.iterrows():
        alerta_txt += f"- **{fila['Inventario_Proyectado']:,.0f} unds** de _{fila['Nombre']}_\n"
    
    if len(df_top_proyectado) > 3:
        alerta_txt += f"*(Revisa la tabla inferior para ver las {len(df_top_proyectado)-3} referencias adicionales que requieren atención).*\n"

    st.info(alerta_txt)

fig_proy = px.bar(df_top_proyectado.head(20), x='Nombre', y='Inventario_Proyectado', 
                  title=f'Top 20 Productos: Unidades Sugeridas a Mantener',
                  color='Inventario_Proyectado', color_continuous_scale='Oranges')
st.plotly_chart(fig_proy, use_container_width=True)

with st.expander("🔍 Ver Tabla Detallada de Proyección y Datos Consolidados", expanded=False):
    cols_show = ['Codigo', 'Nombre', 'Categoria', 'CantidadVendida', 'IngresosTotales', 'Demanda_Diaria_Promedio', 'Inventario_Proyectado']
    
    df_display = df_inventario[cols_show].copy()
    
    # Manejar formatos para visualizacion
    df_display['Demanda_Diaria_Promedio'] = df_display['Demanda_Diaria_Promedio'].round(2)
    
    df_display.rename(columns={
        'Codigo': 'Código',
        'CantidadVendida': 'Unidades Vendidas',
        'IngresosTotales': 'Ingresos ($)',
        'Demanda_Diaria_Promedio': 'Demanda Promedio /día',
        'Inventario_Proyectado': f'Stock Recomendado ({dias_proyeccion} días)'
    }, inplace=True)
    
    st.dataframe(
        df_display.sort_values(f'Stock Recomendado ({dias_proyeccion} días)', ascending=False),
        use_container_width=True, hide_index=True
    )

