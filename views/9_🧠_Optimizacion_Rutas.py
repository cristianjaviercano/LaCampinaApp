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
                   left_on='ClienteCodigo', right_on='Codigo', how='left')
df_full['Latitud'] = pd.to_numeric(df_full['Latitud'], errors='coerce')
df_full['Longitud'] = pd.to_numeric(df_full['Longitud'], errors='coerce')
# Permitimos conservar clientes sin Lat/Lon para graficar su tiempo de trabajo real

tab_preventa, tab_reparto, tab_pareto = st.tabs([
    "1. Eficiencia de Preventistas (TSP)", 
    "2. Despacho de Reparto (CVRP)", 
    "3. Rentabilidad vs Distancia (Pareto)"
])

# ────────────────────────────────────────────────────────────────────────────
# TAB 1: PREVENTISTAS (Eficiencia Operativa TSP)
# ────────────────────────────────────────────────────────────────────────────
with tab_preventa:
    st.markdown("### ⏱️ Indicadores Operativos de Tiempo y Cobertura")
    st.markdown("Analiza la gestión temporal de tus vendedores en un rango de fechas. Compara su cobertura de visitas vs. los tiempos de facturación y estadía por cliente.")
    
    col_f1, col_f2, col_f3 = st.columns([1.5, 2, 2.5])
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
        # Controles Gerenciales Maestros OEE
        st.markdown("**Metas OEE Comercial**")
        c_m1, c_m2, c_m3 = st.columns(3)
        meta_diaria = c_m1.number_input("Clientes/Día", min_value=1, value=50, help="Visitas meta para Cobertura (Rendimiento)")
        meta_horas = c_m2.number_input("Horas/Día", min_value=1.0, value=8.0, step=0.5, help="Jornada esperada (Disponibilidad)")
        meta_ticket = c_m3.number_input("Ticket ($)", min_value=1000, value=20000, step=1000, help="Venta meta por cliente (Calidad)")
        
    cc1, cc2, cc3 = st.columns([2,1,1])
    with cc2:
        btn_generar = st.button("🚀 Calcular OEE", type="primary", use_container_width=True)
    with cc3:
        btn_imprimir = st.button("🖨️ PDF", type="secondary", use_container_width=True)
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
                    num_visitas = len(visitas)
                    if num_visitas == 0: 
                        continue 
                        
                    tiempo_promedio = 0
                    jornada_horas = 0
                    ticket_promedio = df_jornada['Total'].sum() / num_visitas if num_visitas > 0 else 0
                    
                    if 'Hora' in df_jornada.columns or 'Fecha' in df_jornada.columns:
                        temp_col = 'Hora' if 'Hora' in df_jornada.columns else 'Fecha'
                        temp = df_jornada.dropna(subset=[temp_col]).sort_values(temp_col)
                        
                        if not temp.empty:
                            time_series = pd.to_datetime(temp[temp_col], errors='coerce')
                            delta = time_series.max() - time_series.min()
                            jornada_horas = delta.total_seconds() / 3600.0
                            
                            diffs = time_series.diff().dt.total_seconds() / 60
                            diffs = diffs[diffs > 0]
                            if not diffs.empty:
                                tiempo_promedio = diffs.mean()

                    resultado = {
                        'Vendedor': vendedor,
                        'Fecha': fecha_str,  # Guardar como string para el JSON
                        'Visitas': num_visitas,
                        'JornadaHoras': jornada_horas,
                        'TiempoPromedioPedido': tiempo_promedio,
                        'TicketPromedio': ticket_promedio
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
                    st.info("No hay jornadas registradas en este rango para analizar.")
                else:
                    df_res = pd.DataFrame(resultados_diarios)
                    
                    # --- CÁLCULO DINÁMICO OEE COMERCIAL ---
                    # Evitar NaN si hay cero visitas
                    df_res['Visitas'] = df_res['Visitas'].replace(0, 1)
                    
                    df_res['Cobertura'] = (df_res['Visitas'] / meta_diaria) * 100
                    df_res['TiempoPromedioCliente'] = (df_res['JornadaHoras'] * 60) / df_res['Visitas']
                    
                    df_res['Ind_Rendimiento'] = (df_res['Visitas'] / meta_diaria).clip(upper=1.2)
                    df_res['Ind_Disponibilidad'] = (df_res['JornadaHoras'] / meta_horas).clip(upper=1.2)
                    df_res['Ind_Calidad'] = (df_res['TicketPromedio'] / meta_ticket).clip(upper=1.2)
                    df_res['OEE'] = (df_res['Ind_Rendimiento'] * df_res['Ind_Disponibilidad'] * df_res['Ind_Calidad']) * 100
                    df_res.fillna(0, inplace=True)
                    
                    # Acumulados
                    total_jornadas = df_res['JornadaHoras'].sum()
                    promedio_cobertura = df_res['Cobertura'].mean()
                    total_visitas = df_res['Visitas'].sum()
                    promedio_pedido = df_res['TiempoPromedioPedido'].mean()
                    promedio_ticket = df_res['TicketPromedio'].mean()
                    promedio_oee = df_res['OEE'].mean()
                    
                    st.markdown("---")
                    st.markdown(f"#### 🏆 OEE Comercial Consolidado: **{promedio_oee:.1f}%**")
                    
                    c_k1, c_k2, c_k3, c_k4, c_k5 = st.columns(5)
                    c_k1.markdown(f"""
                    <div class="kpi-box">
                        <div class="kpi-title">Visitas Totales</div>
                        <div class="kpi-val">{total_visitas:,}</div>
                        <div class="kpi-sub">Total de impactos.</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    color_ef = "#2e7d32" if promedio_cobertura >= 90 else ("#e65100" if promedio_cobertura >= 70 else "#c62828")
                    c_k2.markdown(f"""
                    <div class="kpi-box" style="border-color: {color_ef};">
                        <div class="kpi-title">Cobertura Media</div>
                        <div class="kpi-val" style="color:{color_ef};">{promedio_cobertura:.1f}%</div>
                        <div class="kpi-sub">De la meta diaria asignada.</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    c_k3.markdown(f"""
                    <div class="kpi-box" style="border-color: #1565c0;">
                        <div class="kpi-title">Jornada Operativa</div>
                        <div class="kpi-val" style="color:#1565c0;">{df_res['JornadaHoras'].mean():.1f} hr/día</div>
                        <div class="kpi-sub">Tiempo medio encendido.</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    c_k4.markdown(f"""
                    <div class="kpi-box" style="border-color: #bf360c;">
                        <div class="kpi-title">Ritmo de Facturación</div>
                        <div class="kpi-val" style="color:#bf360c;">{promedio_pedido:.1f} min</div>
                        <div class="kpi-sub">Márgen entre compras.</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    c_k5.markdown(f"""
                    <div class="kpi-box" style="border-color: #2e7d32;">
                        <div class="kpi-title">Ticket Promedio</div>
                        <div class="kpi-val" style="color:#2e7d32;">${promedio_ticket:,.0f}</div>
                        <div class="kpi-sub">Por cliente.</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Gráficos de Primera Fila (Tendencias y OEE)
                    g_c1, g_c2 = st.columns(2)
                    with g_c1:
                        st.markdown("**Variación Diaria (Cobertura vs Tiempo por Cliente)**")
                        from plotly.subplots import make_subplots
                        fig_co = make_subplots(specs=[[{"secondary_y": True}]])
                        
                        fig_co.add_trace(go.Bar(x=df_res['Fecha'], y=df_res['Cobertura'], name='Cobertura (%)', marker_color='#1565c0'), secondary_y=False)
                        fig_co.add_trace(go.Scatter(x=df_res['Fecha'], y=df_res['TiempoPromedioCliente'], name='Estadía x Cliente (min)', mode='lines+markers', line=dict(color='#e65100', width=2)), secondary_y=True)
                        
                        # --- Línea de Tendencia Mínimos Cuadrados (OLS) ---
                        y_vals = df_res['TiempoPromedioCliente'].values
                        valid_mask = (~np.isnan(y_vals)) & (y_vals > 0)
                        if valid_mask.sum() > 1:
                            x_nums = np.arange(len(df_res['Fecha']))[valid_mask]
                            y_valid = y_vals[valid_mask]
                            p = np.polyfit(x_nums, y_valid, 1)
                            trend = np.polyval(p, np.arange(len(df_res['Fecha'])))
                            
                            ybar = np.mean(y_valid)
                            ssreg = np.sum((np.polyval(p, x_nums) - ybar)**2)
                            sstot = np.sum((y_valid - ybar)**2)
                            r2 = (ssreg / sstot) if sstot != 0 else 0
                            
                            fig_co.add_trace(go.Scatter(x=df_res['Fecha'], y=trend, mode='lines', line=dict(dash='dash', color='red', width=1.5), name=f'Tendencia (R²={r2:.2f})'), secondary_y=True)
                        
                        fig_co.update_layout(template="plotly_white", margin=dict(l=0, r=0, t=30, b=0), legend=dict(orientation='h', y=1.1))
                        st.plotly_chart(fig_co, use_container_width=True)
                    
                    with g_c2:
                        st.markdown("**Desglose del OEE Comercial Diario**")
                        fig_oee = go.Figure()
                        fig_oee.add_trace(go.Scatter(x=df_res['Fecha'], y=df_res['Ind_Disponibilidad']*100, mode='lines', name='Disponibilidad', line=dict(color='#42a5f5', width=1.5)))
                        fig_oee.add_trace(go.Scatter(x=df_res['Fecha'], y=df_res['Ind_Rendimiento']*100, mode='lines', name='Rendimiento', line=dict(color='#ffa726', width=1.5)))
                        fig_oee.add_trace(go.Scatter(x=df_res['Fecha'], y=df_res['Ind_Calidad']*100, mode='lines', name='Calidad', line=dict(color='#ab47bc', width=1.5)))
                        fig_oee.add_trace(go.Scatter(x=df_res['Fecha'], y=df_res['OEE'], mode='lines+markers', name='OEE Total', line=dict(color='#2e7d32', width=4)))
                        fig_oee.update_layout(template="plotly_white", margin=dict(l=0, r=0, t=30, b=0), legend=dict(orientation='h', y=1.1))
                        st.plotly_chart(fig_oee, use_container_width=True)

                    # Gráficos de Segunda Fila (3D y Desempeño)
                    g_c3, g_c4 = st.columns(2)
                    with g_c3:
                        st.markdown("**Matriz Multidimensional (Visitas vs Dinero vs Tiempo)**")
                        fig_3d = px.scatter(df_res, x="Visitas", y="TicketPromedio", size="JornadaHoras", color="OEE",
                                            hover_name="Fecha", size_max=25, color_continuous_scale="RdYlGn",
                                            title="")
                        # Líneas Meta
                        fig_3d.add_hline(y=meta_ticket, line_dash="dash", line_color="gray", annotation_text="Meta Ticket")
                        fig_3d.add_vline(x=meta_diaria, line_dash="dash", line_color="gray", annotation_text="Meta Clientes")
                        
                        fig_3d.update_layout(template="plotly_white", margin=dict(l=0, r=0, t=30, b=0))
                        st.plotly_chart(fig_3d, use_container_width=True)
                        
                    with g_c4:
                        if sel_vend == "Todos":
                            st.markdown("**Top Vendedores menos Eficientes (Mayor Tiempo x Cliente)**")
                            df_vend = df_res.groupby('Vendedor')[['Visitas', 'JornadaHoras']].sum().reset_index()
                            # Tiempo Promedio Global del Vendedor
                            df_vend['TiempoXCliente'] = (df_vend['JornadaHoras'] * 60) / df_vend['Visitas']
                            df_vend = df_vend.sort_values('TiempoXCliente', ascending=False).head(10)
                            
                            fig_pie = px.bar(df_vend, y='Vendedor', x='TiempoXCliente', orientation='h', 
                                            text=df_vend['TiempoXCliente'].apply(lambda x: f"{x:.1f} min"),
                                            color='Visitas', color_continuous_scale="Reds")
                            fig_pie.update_layout(template="plotly_white", margin=dict(l=0, r=0, t=30, b=0), showlegend=False)
                            fig_pie.update_yaxes(categoryorder="total ascending", title="")
                            st.plotly_chart(fig_pie, use_container_width=True)
                        else:
                            st.markdown("**Desempeño Individual del Preventista**")
                            max_visitas = df_res['Visitas'].max()
                            st.info(f"**Pico máximo de clientes:** {max_visitas} el {df_res.loc[df_res['Visitas'].idxmax(), 'Fecha']}")
                            st.info(f"**Jornada más agotadora:** {df_res['JornadaHoras'].max():.1f} horas el {df_res.loc[df_res['JornadaHoras'].idxmax(), 'Fecha']}.")
                            st.info(f"**Día más rápido por cliente:** {df_res.loc[df_res['TiempoPromedioCliente'].idxmin(), 'Fecha']} ({df_res['TiempoPromedioCliente'].min():.1f} min/cliente)")
                    
                    st.markdown("**📑 Detalle Operativo de Jornadas**")
                    st.dataframe(
                        df_res[['Fecha', 'Vendedor', 'Visitas', 'JornadaHoras', 'TiempoPromedioCliente', 'TicketPromedio', 'Cobertura', 'OEE']].style.format({
                            'JornadaHoras': '{:.1f} hrs',
                            'Cobertura': '{:.1f}%',
                            'OEE': '{:.1f}%',
                            'TiempoPromedioCliente': '{:.1f} min',
                            'TicketPromedio': '${:,.0f}'
                        }).background_gradient(subset=['OEE'], cmap="RdYlGn"),
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
