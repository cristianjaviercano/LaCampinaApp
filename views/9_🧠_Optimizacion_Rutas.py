import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from utils.data_loader import load_data
from utils.routing import nearest_neighbor_tsp, route_distance_km, greedy_cvrp_heterogeneous

st.set_page_config(page_title="Ingeniería y Optimización", page_icon="🧠", layout="wide")

# CSS especial para impresión y diseño de reporte
st.markdown("""
<style>
    @media print {
        header {display: none !important;}
        footer {display: none !important;}
        .stSidebar {display: none !important;}
        .css-v37k9u {padding-top: 0 !important;}
        .report-header {display: block !important;}
        .no-print {display: none !important;}
    }
    .kpi-box {
        background-color: #f1f8e9;
        border-left: 5px solid #2e7d32;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 20px;
    }
    .kpi-val { font-size: 24px; font-weight: bold; color: #1b5e20; }
    .kpi-title { font-size: 14px; color: #555; text-transform: uppercase; font-weight: 600; }
    .kpi-sub { font-size: 12px; color: #888; }
</style>
""", unsafe_allow_html=True)

st.title("🧠 Inteligencia de Operaciones y Optimizador")
st.markdown("Módulo gerencial avanzado basado en el modelo de tesis. Compara el rendimiento empírico de visitas de los preventistas vs. el ruteo algorítmico ideal (TSP), y genera planeación logística eficiente para la flota de reparto (CVRP).")

data = load_data(st.session_state.get("fecha_historica"))
if data is None or data['compras_detalle'].empty:
    st.error("No hay datos operativos para optimizar.")
    st.stop()

df_det = data['compras_detalle'].copy()
df_cli = data['clientes'].copy()

if df_cli.empty or 'Latitud' not in df_cli.columns:
    st.error("La base de clientes carece de datos geográficos (Latitud/Longitud). No se puede optimizar.")
    st.stop()

df_det['Fecha'] = pd.to_datetime(df_det['Fecha'], errors='coerce')
df_cli['Codigo'] = df_cli['Codigo'].astype(str)
df_det['ClienteCodigo'] = df_det['ClienteCodigo'].astype(str)

# Pre-cruzar datos para tener coordenadas en las transacciones
df_full = pd.merge(df_det, df_cli[['Codigo', 'Nombre', 'Latitud', 'Longitud', 'Barrio']], 
                   left_on='ClienteCodigo', right_on='Codigo', how='inner')
df_full = df_full.dropna(subset=['Latitud', 'Longitud'])

tab_preventa, tab_reparto, tab_pareto = st.tabs([
    "1. Eficiencia de Preventistas (TSP)", 
    "2. Despacho de Reparto (CVRP)", 
    "3. Rentabilidad vs Distancia (Pareto)"
])

# ────────────────────────────────────────────────────────────────────────────
# TAB 1: PREVENTISTAS (Eficiencia Operativa TSP)
# ────────────────────────────────────────────────────────────────────────────
with tab_preventa:
    st.markdown("### 🏃‍♂️ Indicadores Logísticos de Preventa")
    st.markdown("Analiza el rendimiento geométrico de tus vendedores en un rango de fechas. Compara su distancia recorrida vs el ideal matemático.")
    
    col_f1, col_f2, col_f3 = st.columns([1.5, 2, 1])
    vendedores_lista = ["Todos"] + sorted(df_full['Vendedor'].dropna().unique().tolist())
    
    with col_f1:
        sel_vend = st.selectbox("Preventista:", vendedores_lista)
    
    with col_f2:
        min_d = df_full['Fecha'].min().date()
        max_d = df_full['Fecha'].max().date()
        import datetime
        if min_d == max_d: max_d += datetime.timedelta(days=1)
        rango_fechas = st.slider("Rango de Auditoría:", min_value=min_d, max_value=max_d, value=(min_d, max_d))
        
    with col_f3:
        st.markdown("<br>", unsafe_allow_html=True)
        btn_generar = st.button("🚀 Generar Análisis", type="primary", use_container_width=True)
        btn_imprimir = st.button("🖨️ Imprimir (PDF)", type="secondary", use_container_width=True)
        if btn_imprimir:
            st.components.v1.html("<script>window.print()</script>", height=0)

    if btn_generar and len(rango_fechas) == 2:
        # Filtrar datos generales
        df_periodo = df_full[
            (df_full['Fecha'].dt.date >= rango_fechas[0]) & 
            (df_full['Fecha'].dt.date <= rango_fechas[1])
        ].copy()
        
        if sel_vend != "Todos":
            df_periodo = df_periodo[df_periodo['Vendedor'] == sel_vend]
            
        if df_periodo.empty:
            st.warning("No hay visitas registradas en este periodo para este filtro.")
        else:
            with st.spinner("Consultando memoria caché y analizando rutas diarias..."):
                import json
                from pathlib import Path
                
                # Setup Caché persistente
                cache_dir = Path(__file__).resolve().parent.parent / "datos_maestros"
                cache_path = cache_dir / "optimizacion_cache.json"
                cache_rutas = {}
                if cache_path.exists():
                    try:
                        with open(cache_path, 'r', encoding='utf-8') as f:
                            cache_rutas = json.load(f)
                    except:
                        pass
                
                nuevos_calculos = False
                resultados_diarios = []
                
                # Iterar sobre cada jornada laboral
                jornadas = df_periodo.groupby(['Vendedor', df_periodo['Fecha'].dt.date])
                
                for (vendedor, fecha), df_jornada in jornadas:
                    fecha_str = fecha.strftime('%Y-%m-%d')
                    cache_key = f"{vendedor}_{fecha_str}"
                    
                    if cache_key in cache_rutas:
                        # Usar dato pre-calculado
                        resultados_diarios.append(cache_rutas[cache_key])
                        continue
                    
                    # Si no está en caché, calcular
                    if 'Hora' in df_jornada.columns:
                        df_jornada = df_jornada.sort_values('Hora')
                    
                    visitas = df_jornada.drop_duplicates(subset=['ClienteCodigo']).copy().reset_index(drop=True)
                    if len(visitas) == 0: 
                        continue 
                        
                    lats = visitas['Latitud'].tolist()
                    lons = visitas['Longitud'].tolist()
                    pts = list(zip(lats, lons))
                    
                    if len(visitas) < 3:
                        # Para 1 o 2 visitas no hay problema del viajante, la ruta es trivial.
                        d_emp = route_distance_km(pts, use_streets=True) if len(visitas) > 1 else 0
                        d_opt = d_emp  # Óptimo es igual a la real, no hay pérdida
                    else:
                        d_emp = route_distance_km(pts, use_streets=True)
                        orden = nearest_neighbor_tsp(visitas[['Latitud', 'Longitud']], use_streets=True)
                        pts_opt = [pts[i] for i in orden]
                        d_opt = route_distance_km(pts_opt, use_streets=True)
                    
                    resultado = {
                        'Vendedor': vendedor,
                        'Fecha': fecha_str,  # Guardar como string para el JSON
                        'Visitas': len(visitas),
                        'DistanciaReal': d_emp,
                        'DistanciaOptima': d_opt
                    }
                    resultados_diarios.append(resultado)
                    cache_rutas[cache_key] = resultado
                    nuevos_calculos = True
                
                # Guardar caché si hicimos nuevos cálculos
                if nuevos_calculos:
                    try:
                        with open(cache_path, 'w', encoding='utf-8') as f:
                            json.dump(cache_rutas, f, ensure_ascii=False, indent=2)
                    except:
                        pass
                
                # Restaurar formato fecha para gráficas
                for r in resultados_diarios:
                    r['Fecha'] = pd.to_datetime(r['Fecha']).date()
                    
                if not resultados_diarios:
                    st.info("No hay jornadas registradas en este rango para analizar el ruteo.")
                else:
                    df_res = pd.DataFrame(resultados_diarios)
                    df_res['KmPerdidos'] = df_res['DistanciaReal'] - df_res['DistanciaOptima']
                    # Limpiar anomalías de punto flotante
                    df_res['KmPerdidos'] = df_res['KmPerdidos'].apply(lambda x: max(0, x))
                    # Velocidad promedio urbana 15 km/h
                    df_res['MinutosPerdidos'] = (df_res['KmPerdidos'] / 15.0) * 60
                    
                    # Acumulados
                    total_d_real = df_res['DistanciaReal'].sum()
                    total_d_opt  = df_res['DistanciaOptima'].sum()
                    total_perd   = df_res['KmPerdidos'].sum()
                    total_tiempo = df_res['MinutosPerdidos'].sum()
                    eficiencia_global = (total_d_opt / total_d_real * 100) if total_d_real > 0 else 100
                    
                    st.markdown("---")
                    st.markdown("#### 📊 Consolidado de Eficiencia Logística")
                    
                    c_k1, c_k2, c_k3, c_k4 = st.columns(4)
                    c_k1.markdown(f"""
                    <div class="kpi-box">
                        <div class="kpi-title">Distancia Real Acumulada</div>
                        <div class="kpi-val">{total_d_real:.1f} km</div>
                        <div class="kpi-sub">Total rodado en el periodo.</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    color_ef = "#2e7d32" if eficiencia_global >= 85 else ("#e65100" if eficiencia_global >= 60 else "#c62828")
                    c_k2.markdown(f"""
                    <div class="kpi-box" style="border-color: {color_ef};">
                        <div class="kpi-title">Eficiencia Promedio</div>
                        <div class="kpi-val" style="color:{color_ef};">{eficiencia_global:.1f}%</div>
                        <div class="kpi-sub">Cercanía a la ruta algorítmica.</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    c_k3.markdown(f"""
                    <div class="kpi-box" style="border-color: #c62828;">
                        <div class="kpi-title">Kilómetros Perdidos</div>
                        <div class="kpi-val" style="color:#c62828;">{total_perd:.1f} km</div>
                        <div class="kpi-sub">Desperdicio por desórdenes.</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    c_k4.markdown(f"""
                    <div class="kpi-box" style="border-color: #bf360c;">
                        <div class="kpi-title">Horas Hombre Perdidas</div>
                        <div class="kpi-val" style="color:#bf360c;">{(total_tiempo/60):.1f} hr</div>
                        <div class="kpi-sub">Tiempo improductivo en traslados.</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Gráficos
                    g_c1, g_c2 = st.columns(2)
                    with g_c1:
                        st.markdown("**Variación Diaria de Eficiencia**")
                        # Gráfico de barras apiladas o agrupadas
                        fig_bar = go.Figure()
                        fig_bar.add_trace(go.Bar(x=df_res['Fecha'], y=df_res['DistanciaOptima'], name='Km Óptimos', marker_color='#2e7d32'))
                        fig_bar.add_trace(go.Bar(x=df_res['Fecha'], y=df_res['KmPerdidos'], name='Km Perdidos', marker_color='#c62828'))
                        fig_bar.update_layout(barmode='stack', template="plotly_white", margin=dict(l=0, r=0, t=30, b=0), legend=dict(orientation='h', y=1.1))
                        st.plotly_chart(fig_bar, use_container_width=True)
                    
                    with g_c2:
                        if sel_vend == "Todos":
                            st.markdown("**Top Vendedores menos Eficientes (Desperdicio)**")
                            df_vend = df_res.groupby('Vendedor')[['KmPerdidos', 'MinutosPerdidos']].sum().reset_index()
                            df_vend = df_vend.sort_values('KmPerdidos', ascending=False).head(10)
                            
                            fig_pie = px.bar(df_vend, y='Vendedor', x='KmPerdidos', orientation='h', 
                                            text=df_vend['KmPerdidos'].apply(lambda x: f"{x:.1f} km"),
                                            color='MinutosPerdidos', color_continuous_scale="Reds")
                            fig_pie.update_layout(template="plotly_white", margin=dict(l=0, r=0, t=30, b=0), showlegend=False)
                            fig_pie.update_yaxes(categoryorder="total ascending", title="")
                            st.plotly_chart(fig_pie, use_container_width=True)
                        else:
                            st.markdown("**Desempeño Individual del Vendedor**")
                            promedio_cliente = df_res['DistanciaReal'].sum() / df_res['Visitas'].sum()
                            st.info(f"**Distancia promedio por cliente:** {promedio_cliente*1000:.1f} metros.")
                            st.info(f"**Promedio de clientes diarios:** {df_res['Visitas'].mean():.0f} clientes.")
                            st.info(f"**Mejor día:** {df_res.loc[df_res['KmPerdidos'].idxmin(), 'Fecha']} ({df_res['KmPerdidos'].min():.1f} km perdidos)")
                    
                    st.markdown("**📑 Detalle Diario de Jornadas**")
                    st.dataframe(
                        df_res.style.format({
                            'DistanciaReal': '{:.2f} km',
                            'DistanciaOptima': '{:.2f} km',
                            'KmPerdidos': '{:.2f} km',
                            'MinutosPerdidos': '{:.0f} min'
                        }).background_gradient(subset=['KmPerdidos'], cmap="Reds"),
                        use_container_width=True, hide_index=True
                    )


# ────────────────────────────────────────────────────────────────────────────
# TAB 2: ENTREGAS A CLIENTE (Módulo de Flota Consolidada)
# ────────────────────────────────────────────────────────────────────────────
with tab_reparto:
    st.markdown("### 🚛 Planificación de Flota y Entregas")
    st.markdown("Analiza en un periodo el tamaño del volumen de despacho vs la capacidad máxima de tu flota (Utilización de Furgones).")
    
    col_c1, col_c2 = st.columns([1,2])
    
    with col_c1:
        min_dr = df_full['Fecha'].min().date()
        max_dr = df_full['Fecha'].max().date()
        if min_dr == max_dr: max_dr += datetime.timedelta(days=1)
        rango_entregas = st.slider("Rango de Despacho:", min_value=min_dr, max_value=max_dr, value=(min_dr, max_dr), key="sl_entregas")
        
    with col_c2:
        st.markdown("**¿Cuál es la flota que tiene la compañía disponible todos los días?**")
        cx1, cx2 = st.columns(2)
        cvrp_furgon_qty = cx1.number_input("Nº Vehículos en parqueadero", min_value=1, value=2)
        cvrp_furgon_cap = cx2.number_input("Capacidad Max c/u (Unidades)", min_value=10, value=3000)
        capacidad_diaria_total = cvrp_furgon_qty * cvrp_furgon_cap

    st.markdown("<br>", unsafe_allow_html=True)
    btn_generar2 = st.button("🚀 Generar Análisis de Flota", type="primary", use_container_width=True)

    if btn_generar2 and len(rango_entregas) == 2:
        df_desp = df_full[
            (df_full['Fecha'].dt.date >= rango_entregas[0]) & 
            (df_full['Fecha'].dt.date <= rango_entregas[1])
        ].copy()
        
        # Consolidar despachos diarios
        df_desp_dia = df_desp.groupby(df_desp['Fecha'].dt.date).agg(
            UnidadesVendidas=('Cantidad', 'sum'),
            TotalRecaudo=('Total', 'sum'),
            ClientesAVisitar=('ClienteCodigo', 'nunique')
        ).reset_index()
        
        if df_desp_dia.empty:
            st.warning("No hay pedidos entregables en estas fechas.")
        else:
            df_desp_dia['CapacidadFlota'] = capacidad_diaria_total
            df_desp_dia['PorcentajeUso'] = (df_desp_dia['UnidadesVendidas'] / df_desp_dia['CapacidadFlota']) * 100
            
            # Penalidades de despilfarro o escasez
            df_desp_dia['ExcesoPorcentaje'] = df_desp_dia['PorcentajeUso'].apply(lambda x: x - 100 if x > 100 else 0)
            df_desp_dia['CapacidadOciosaUnidades'] = df_desp_dia.apply(lambda r: r['CapacidadFlota'] - r['UnidadesVendidas'] if r['PorcentajeUso'] <= 100 else 0, axis=1)
            
            # --- RENDERIZADO DEL REPORTE FLOTA ---
            st.markdown("---")
            st.markdown("#### 📦 Métricas de Satisfacción Logística")
            
            r_k1, r_k2, r_k3 = st.columns(3)
            promedio_uso = df_desp_dia['PorcentajeUso'].mean()
            dias_exceso = len(df_desp_dia[df_desp_dia['PorcentajeUso'] > 100])
            total_ocioso = df_desp_dia['CapacidadOciosaUnidades'].sum()
            
            r_k1.markdown(f"""
            <div class="kpi-box">
                <div class="kpi-title">Uso Promedio de Flota</div>
                <div class="kpi-val">{promedio_uso:.1f}%</div>
                <div class="kpi-sub">Grado de ocupación de los {cvrp_furgon_qty} camiones.</div>
            </div>
            """, unsafe_allow_html=True)
            
            r_k2.markdown(f"""
            <div class="kpi-box" style="border-color: {'#c62828' if dias_exceso > 0 else '#2e7d32'};">
                <div class="kpi-title">Días de Desbordamiento</div>
                <div class="kpi-val" style="color:{'#c62828' if dias_exceso > 0 else '#2e7d32'};">{dias_exceso} Días</div>
                <div class="kpi-sub">Donde las ventas superaron la capacidad.</div>
            </div>
            """, unsafe_allow_html=True)
            
            r_k3.markdown(f"""
            <div class="kpi-box" style="border-color: #fbc02d;">
                <div class="kpi-title">Unidades Ficticias Perdidas</div>
                <div class="kpi-val" style="color:#f9a825;">{total_ocioso:,.0f} unds</div>
                <div class="kpi-sub">Suma de espacios vacíos en los viajes diarios.</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Gráfica de Utilización Diaria
            fig_uso = go.Figure()
            fig_uso.add_trace(go.Bar(
                x=df_desp_dia['Fecha'], y=df_desp_dia['UnidadesVendidas'],
                name='Volumen de Ventas (Unds)', marker_color='#1565c0'
            ))
            fig_uso.add_trace(go.Scatter(
                x=df_desp_dia['Fecha'], y=df_desp_dia['CapacidadFlota'],
                mode='lines', name='Límite de Capacidad', line=dict(color='red', width=3, dash='dash')
            ))
            fig_uso.update_layout(title="Llenado Diario de Vehículos (Ventas vs Capacidad del Parque Automotor)", 
                                  barmode='overlay', template="plotly_white")
            st.plotly_chart(fig_uso, use_container_width=True)
            
            # Tabla de alertas
            st.markdown("**📑 Alertas y Saturaciones Diarias**")
            st.dataframe(
                df_desp_dia[['Fecha', 'UnidadesVendidas', 'PorcentajeUso', 'ClientesAVisitar']].style.format({
                    'UnidadesVendidas': '{:,.0f}',
                    'PorcentajeUso': '{:.1f}%',
                }).background_gradient(subset=['PorcentajeUso'], cmap="RdYlGn_r"),
                use_container_width=True, hide_index=True
            )

# ────────────────────────────────────────────────────────────────────────────
# TAB 3: RENTABILIDAD VS DISTANCIA (PARETO)
# ────────────────────────────────────────────────────────────────────────────
with tab_pareto:
    st.markdown("### 🎯 Matriz de Rentabilidad vs Esfuerzo Logístico")
    st.markdown("Identifica mediante un análisis de cuadrantes cuáles clientes te están generando pérdidas debido a su lejanía y bajo volumen de compra.")
    
    col_p1, col_p2, col_p3 = st.columns([1, 2, 1])
    
    with col_p2:
        min_dp = df_full['Fecha'].min().date()
        max_dp = df_full['Fecha'].max().date()
        if min_dp == max_dp: max_dp += datetime.timedelta(days=1)
        rango_pareto = st.slider("Rango de Evaluación Comercial:", min_value=min_dp, max_value=max_dp, value=(min_dp, max_dp), key="sl_pareto")
    
    with col_p3:
        st.markdown("<br>", unsafe_allow_html=True)
        btn_pareto = st.button("🚀 Generar Matriz", type="primary", use_container_width=True)
        
    if btn_pareto and len(rango_pareto) == 2:
        df_par = df_full[
            (df_full['Fecha'].dt.date >= rango_pareto[0]) & 
            (df_full['Fecha'].dt.date <= rango_pareto[1])
        ].copy()
        
        if df_par.empty:
            st.warning("No hay datos de ventas en este periodo.")
        else:
            with st.spinner("Calculando distancias al centro de distribución y rentabilidad..."):
                # 1. Definir el "Centro Logístico" asumiendo el promedio de coordenadas (o bodega real si la hay)
                lat_bodega = df_par['Latitud'].mean()
                lon_bodega = df_par['Longitud'].mean()
                
                # 2. Agrupar compras totales por cliente
                df_clientes_rentables = df_par.groupby(['ClienteCodigo', 'Nombre', 'Latitud', 'Longitud']).agg(
                    TotalCompras=('Total', 'sum'),
                    FrecuenciaVisitas=('Fecha', 'nunique')
                ).reset_index()
                
                # 3. Calcular distancia lineal aproximada (Haversine) a la bodega en Km
                # Formula rápida earth radius km = 6371
                def haversine(lat1, lon1, lat2, lon2):
                    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
                    dlat = lat2 - lat1
                    dlon = lon2 - lon1
                    a = np.sin(dlat/2.0)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2.0)**2
                    c = 2 * np.arcsin(np.sqrt(a))
                    return 6371 * c
                
                df_clientes_rentables['DistanciaBodega_Km'] = haversine(
                    lat_bodega, lon_bodega, 
                    df_clientes_rentables['Latitud'], df_clientes_rentables['Longitud']
                )
                
                # 4. Establecer las medias para cruzar los ejes del cuadrante
                media_compras = df_clientes_rentables['TotalCompras'].median()
                media_distancia = df_clientes_rentables['DistanciaBodega_Km'].median()
                
                # Clasificar en Cuadrantes
                def clasificar_cuadrante(row):
                    if row['TotalCompras'] >= media_compras and row['DistanciaBodega_Km'] <= media_distancia:
                        return "Estrellas (Cerca, Compran Mucho)"
                    elif row['TotalCompras'] >= media_compras and row['DistanciaBodega_Km'] > media_distancia:
                        return "Caballos de Batalla (Lejos, Compran Mucho)"
                    elif row['TotalCompras'] < media_compras and row['DistanciaBodega_Km'] <= media_distancia:
                        return "Relleno de Ruta (Cerca, Compran Poco)"
                    else:
                        return "Carga Muerta (Lejos, Compran Poco)"
                        
                df_clientes_rentables['Clasificacion'] = df_clientes_rentables.apply(clasificar_cuadrante, axis=1)
                
                # Renderizar Alerta Gerencial
                clientes_criticos = df_clientes_rentables[df_clientes_rentables['Clasificacion'] == "Carga Muerta (Lejos, Compran Poco)"].sort_values('DistanciaBodega_Km', ascending=False)
                
                st.markdown("---")
                if not clientes_criticos.empty:
                    peor_cliente = clientes_criticos.iloc[0]
                    st.warning(f"**🚨 Foco Logístico Detectado:** Tienes {len(clientes_criticos)} clientes clasificados como 'Carga Muerta'. Por ejemplo, el cliente **{peor_cliente['Nombre']}** está a {peor_cliente['DistanciaBodega_Km']:.1f} km, la has visitado {peor_cliente['FrecuenciaVisitas']} veces pero solo ha te comprado ${peor_cliente['TotalCompras']:,.0f}. *Sugerimos revisar su frecuencia de ruteo para no perder dinero en fletes hacia su zona.*")
                
                # Graficar Scatter Plot de Cuadrantes
                fig_scatter = px.scatter(
                    df_clientes_rentables, x="DistanciaBodega_Km", y="TotalCompras", 
                    color="Clasificacion", size="FrecuenciaVisitas", hover_name="Nombre",
                    color_discrete_map={
                        "Estrellas (Cerca, Compran Mucho)": "#2e7d32",
                        "Caballos de Batalla (Lejos, Compran Mucho)": "#0277bd",
                        "Relleno de Ruta (Cerca, Compran Poco)": "#fbc02d",
                        "Carga Muerta (Lejos, Compran Poco)": "#c62828"
                    },
                    title="Matriz de Pareto Logístico (Rentabilidad vs Distancia)"
                )
                
                # Líneas divisorias de cuadrante
                fig_scatter.add_vline(x=media_distancia, line_width=2, line_dash="dash", line_color="black")
                fig_scatter.add_hline(y=media_compras, line_width=2, line_dash="dash", line_color="black")
                
                fig_scatter.update_layout(template="plotly_white")
                st.plotly_chart(fig_scatter, use_container_width=True)
                
                # Gráficos Adicionales y Tablas
                c_p1, c_p2 = st.columns(2)
                with c_p1:
                    df_resumen_par = df_clientes_rentables.groupby('Clasificacion').agg(
                        Cantidad_Clientes=('ClienteCodigo', 'count'),
                        Ingresos_Totales=('TotalCompras', 'sum')
                    ).reset_index()
                    fig_pie_par = px.pie(df_resumen_par, values='Cantidad_Clientes', names='Clasificacion', title='Distribución de Clientes por Matriz', hole=0.4)
                    st.plotly_chart(fig_pie_par, use_container_width=True)
                
                with c_p2:
                    st.markdown("**Listado Crítico de Carga Muerta**")
                    st.markdown("A estos clientes deberías visitarlos 1 vez por semana o menos.")
                    # Ordenar los más lejanos que menos compren
                    df_muertos_mostrar = clientes_criticos[['Nombre', 'DistanciaBodega_Km', 'TotalCompras', 'FrecuenciaVisitas']].head(10)
                    st.dataframe(
                        df_muertos_mostrar.style.format({
                            'DistanciaBodega_Km': '{:.2f} km',
                            'TotalCompras': '${:,.0f}'
                        }).background_gradient(subset=['TotalCompras'], cmap="Reds_r"),
                        hide_index=True, use_container_width=True
                    )
