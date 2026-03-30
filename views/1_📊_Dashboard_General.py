"""
MÓDULO: Dashboard General — Power BI Style
Filtros interactivos de fecha / vendedor / ciudad + KPIs con deltas + gráficos enriquecidos.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from utils.data_loader import load_data
import numpy as np

# ─── Estilos premium ─────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Tarjetas KPI */
.kpi-card {
    background: linear-gradient(135deg, #1b5e2015 0%, #ffffff 100%);
    border-radius: 12px;
    padding: 18px 20px 14px 20px;
    border-left: 5px solid #2e7d32;
    box-shadow: 0 2px 8px rgba(0,0,0,0.07);
    margin-bottom: 4px;
}
.kpi-card.red  { border-left-color: #c62828; background: linear-gradient(135deg,#c6282810 0%,#fff 100%); }
.kpi-card.blue { border-left-color: #1565c0; background: linear-gradient(135deg,#1565c010 0%,#fff 100%); }
.kpi-card.amber{ border-left-color: #e65100; background: linear-gradient(135deg,#e6510010 0%,#fff 100%); }
.kpi-label  { font-size: 0.72rem; color: #555; font-weight: 600; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 4px; }
.kpi-value  { font-size: 1.8rem; font-weight: 800; color: #1a1a1a; line-height: 1.1; }
.kpi-delta  { font-size: 0.78rem; margin-top: 4px; }
.kpi-delta.up   { color: #2e7d32; }
.kpi-delta.down { color: #c62828; }
.kpi-delta.neutral { color: #888; }

/* Divisor de sección */
.section-title {
    font-size: 0.8rem; font-weight: 700; color: #2e7d32;
    text-transform: uppercase; letter-spacing: 0.1em;
    border-bottom: 2px solid #e8f5e9; padding-bottom: 6px; margin-bottom: 12px;
}
/* Banner de filtros */
.filter-banner {
    background: #f1f8e9;
    border-radius: 10px;
    padding: 12px 18px;
    margin-bottom: 12px;
    font-size: 0.82rem;
    color: #33691e;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

# ─── Carga de datos ───────────────────────────────────────────────────────────
st.title("📊 Dashboard General — La Campiña")

data = load_data(st.session_state.get("fecha_historica"))

if data is None:
    st.error("No se pudieron cargar los datos.")
    st.stop()

df_det  = data['compras_detalle'].copy()
df_cli  = data['clientes'].copy()
df_vend = data['vendedores'].copy()

if df_det.empty:
    st.warning("No hay datos de compras cargados. Ve al módulo **Gestor Base Maestra → Compras** y carga un Purchase Order.")
    st.stop()

df_det['Fecha'] = pd.to_datetime(df_det['Fecha'], errors='coerce')
df_det = df_det.dropna(subset=['Fecha'])

# Aislar las "Visitas Fallidas" del escaneo DSD para no dañar reportes de dinero o producto
if 'Estado' in df_det.columns:
    df_det = df_det[df_det['Estado'] != 'VISITA_FALLIDA']

# ─────────────────────────────────────────────────────────────────────────────
# PANEL DE FILTROS (sidebar)
# ─────────────────────────────────────────────────────────────────────────────
st.sidebar.markdown("### 🎛️ Filtros del Dashboard")

# Rango de fechas interactivo (slider de línea de tiempo)
min_date = df_det['Fecha'].min().date()
max_date = df_det['Fecha'].max().date()

# Streamlit slider falla si min == max, prevención básica:
import datetime
if min_date == max_date:
    max_date = min_date + datetime.timedelta(days=1)

date_range = st.sidebar.slider(
    "📅 Línea de Tiempo (Rango de Fechas)",
    min_value=min_date,
    max_value=max_date,
    value=(min_date, max_date),
    format="YYYY-MM-DD"
)

# Vendedor
vendedores_lista = ["Todos"] + sorted(df_det['Vendedor'].dropna().unique().tolist())
sel_vendedor = st.sidebar.selectbox("👤 Vendedor", vendedores_lista)

# Ciudad
if 'Ciudad' in df_det.columns:
    ciudades_lista = ["Todas"] + sorted(df_det['Ciudad'].dropna().unique().tolist())
    sel_ciudad = st.sidebar.selectbox("🏙️ Ciudad", ciudades_lista)
else:
    sel_ciudad = "Todas"

# Método de pago
if 'MetodoPago' in df_det.columns:
    metodos_lista = ["Todos"] + sorted(df_det['MetodoPago'].dropna().unique().tolist())
    sel_metodo = st.sidebar.selectbox("💳 Método de Pago", metodos_lista)
else:
    sel_metodo = "Todos"

# Meta de ventas
st.sidebar.markdown("---")
st.sidebar.markdown("### 🎯 Meta de Ventas")
meta_ventas = st.sidebar.number_input(
    "Meta del Período ($)",
    min_value=100_000.0,
    max_value=10_000_000_000.0,
    value=50_000_000.0,
    step=1_000_000.0,
    format="%.0f"
)

# ─── Aplicar filtros ──────────────────────────────────────────────────────────
df = df_det.copy()

if len(date_range) == 2:
    start, end = date_range
    df = df[(df['Fecha'].dt.date >= start) & (df['Fecha'].dt.date <= end)]

if sel_vendedor != "Todos":
    df = df[df['Vendedor'] == sel_vendedor]

if sel_ciudad != "Todas" and 'Ciudad' in df.columns:
    df = df[df['Ciudad'] == sel_ciudad]

if sel_metodo != "Todos" and 'MetodoPago' in df.columns:
    df = df[df['MetodoPago'] == sel_metodo]

# Banner de filtro activo
filtros_activos = []
if len(date_range) == 2:
    filtros_activos.append(f"📅 {date_range[0]} → {date_range[1]}")
if sel_vendedor != "Todos":
    filtros_activos.append(f"👤 {sel_vendedor}")
if sel_ciudad != "Todas":
    filtros_activos.append(f"🏙️ {sel_ciudad}")
if sel_metodo != "Todos":
    filtros_activos.append(f"💳 {sel_metodo}")

if filtros_activos:
    st.markdown(
        f'<div class="filter-banner">Filtros activos: {" &nbsp;|&nbsp; ".join(filtros_activos)}</div>',
        unsafe_allow_html=True
    )

if df.empty:
    st.warning("Sin datos para el filtro seleccionado. Ajusta el rango o los filtros.")
    st.stop()

# ─── Período de comparación (mismo rango anterior) ────────────────────────────
if len(date_range) == 2:
    dias_periodo = (date_range[1] - date_range[0]).days + 1
    prev_end   = date_range[0] - pd.Timedelta(days=1)
    prev_start = prev_end - pd.Timedelta(days=dias_periodo - 1)
    df_prev = df_det[
        (df_det['Fecha'].dt.date >= prev_start) &
        (df_det['Fecha'].dt.date <= prev_end)
    ]
    if sel_vendedor != "Todos":
        df_prev = df_prev[df_prev['Vendedor'] == sel_vendedor]
    if sel_ciudad != "Todas" and 'Ciudad' in df_prev.columns:
        df_prev = df_prev[df_prev['Ciudad'] == sel_ciudad]
else:
    df_prev = pd.DataFrame()

def delta_str(curr, prev, fmt="$"):
    if prev == 0 or df_prev.empty:
        return "neutral", "Sin período anterior"
    diff = curr - prev
    pct  = diff / prev * 100
    arrow = "▲" if diff >= 0 else "▼"
    clase = "up" if diff >= 0 else "down"
    if fmt == "$":
        return clase, f"{arrow} {abs(pct):.1f}% vs período anterior"
    return clase, f"{arrow} {abs(pct):.1f}% vs período anterior"

# ─────────────────────────────────────────────────────────────────────────────
# FILA 1 — KPIs principales
# ─────────────────────────────────────────────────────────────────────────────
total_ventas    = df['Total'].sum()
total_ordenes   = df['NoPedido'].nunique()
ticket_prom     = total_ventas / total_ordenes if total_ordenes > 0 else 0
clientes_unicos = df['ClienteCodigo'].nunique()
unidades_tot    = df['Cantidad'].sum() if 'Cantidad' in df.columns else 0
pct_meta        = total_ventas / meta_ventas * 100

prev_ventas   = df_prev['Total'].sum() if not df_prev.empty else 0
prev_ordenes  = df_prev['NoPedido'].nunique() if not df_prev.empty else 0
prev_ticket   = (prev_ventas / prev_ordenes) if prev_ordenes > 0 else 0
prev_clientes = df_prev['ClienteCodigo'].nunique() if not df_prev.empty else 0
prev_unids    = df_prev['Cantidad'].sum() if (not df_prev.empty and 'Cantidad' in df_prev.columns) else 0

k1, k2, k3, k4, k5 = st.columns(5)

def render_kpi(col, label, value, delta_clase, delta_text, fmt="$", color="green"):
    color_class = {"green": "", "red": " red", "blue": " blue", "amber": " amber"}[color]
    if fmt == "$":
        val_str = f"${value:,.0f}"
    elif fmt == "#":
        val_str = f"{value:,.0f}"
    elif fmt == "%":
        val_str = f"{value:.1f}%"
    else:
        val_str = str(value)
    col.markdown(f"""
    <div class="kpi-card{color_class}">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{val_str}</div>
        <div class="kpi-delta {delta_clase}">{delta_text}</div>
    </div>""", unsafe_allow_html=True)

dc1, t1 = delta_str(total_ventas,    prev_ventas)
dc2, t2 = delta_str(total_ordenes,   prev_ordenes, fmt="#")
dc3, t3 = delta_str(ticket_prom,     prev_ticket)
dc4, t4 = delta_str(clientes_unicos, prev_clientes, fmt="#")
dc5, t5 = delta_str(unidades_tot,    prev_unids,    fmt="#")

render_kpi(k1, "💰 Venta Total",       total_ventas,    dc1, t1, "$",  "green")
render_kpi(k2, "🛒 Órdenes Únicas",    total_ordenes,   dc2, t2, "#",  "blue")
render_kpi(k3, "🧾 Ticket Promedio",   ticket_prom,     dc3, t3, "$",  "amber")
render_kpi(k4, "👥 Clientes Activos",  clientes_unicos, dc4, t4, "#",  "blue")
render_kpi(k5, "📦 Unidades Vendidas", unidades_tot,    dc5, t5, "#",  "green")

st.markdown("<br>", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# FILA 2 — Gauge de meta + Tendencia diaria
# ─────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">📈 Progreso y Tendencia</div>', unsafe_allow_html=True)
c_gauge, c_trend = st.columns([1, 2])

with c_gauge:
    gauge_color = "#2e7d32" if pct_meta >= 80 else ("#e65100" if pct_meta >= 50 else "#c62828")
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=total_ventas,
        number={'prefix': "$", 'valueformat': ",.0f", 'font': {'size': 22}},
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': f"Meta: ${meta_ventas:,.0f}", 'font': {'size': 13, 'color': '#555'}},
        delta={'reference': meta_ventas, 'increasing': {'color': '#2e7d32'}, 'decreasing': {'color': '#c62828'},
               'valueformat': ",.0f", 'prefix': "$"},
        gauge={
            'axis': {'range': [0, meta_ventas], 'tickformat': "$.2s"},
            'bar': {'color': gauge_color},
            'steps': [
                {'range': [0, meta_ventas*0.5],  'color': '#ffcdd2'},
                {'range': [meta_ventas*0.5, meta_ventas*0.8], 'color': '#fff9c4'},
                {'range': [meta_ventas*0.8, meta_ventas],     'color': '#c8e6c9'},
            ],
            'threshold': {'line': {'color': 'red', 'width': 3}, 'thickness': 0.75, 'value': meta_ventas}
        }
    ))
    fig_gauge.add_annotation(
        x=0.5, y=0.18, text=f"<b>{pct_meta:.1f}% de la meta</b>",
        showarrow=False, font=dict(size=13, color=gauge_color), xref="paper", yref="paper"
    )
    fig_gauge.update_layout(height=300, margin=dict(l=20, r=20, t=30, b=10))
    st.plotly_chart(fig_gauge, use_container_width=True)

with c_trend:
    ventas_dia = (
        df.groupby(df['Fecha'].dt.date)['Total'].sum()
        .reset_index()
        .rename(columns={'Fecha': 'Fecha', 'Total': 'Ventas'})
    )
    # Línea de meta diaria proporcional
    meta_dia = meta_ventas / max(len(ventas_dia), 1)

    fig_trend = go.Figure()
    fig_trend.add_trace(go.Scatter(
        x=ventas_dia['Fecha'], y=ventas_dia['Ventas'],
        name="Venta Real", mode='lines+markers',
        line=dict(color='#2e7d32', width=2.5, shape='spline'),
        fill='tozeroy', fillcolor='rgba(46,125,50,0.12)',
        marker=dict(size=5)
    ))
    # Media móvil 7 días
    if len(ventas_dia) >= 3:
        ventas_dia['MA7'] = ventas_dia['Ventas'].rolling(window=min(7, len(ventas_dia)), min_periods=1).mean()
        fig_trend.add_trace(go.Scatter(
            x=ventas_dia['Fecha'], y=ventas_dia['MA7'],
            name="Media Móvil",
            line=dict(color='#ff9800', width=1.8, dash='dot'),
            mode='lines'
        ))
    fig_trend.add_hline(
        y=meta_dia, line_dash='dash', line_color='#e53935', line_width=1.5,
        annotation_text=f"Meta diaria ${meta_dia:,.0f}", annotation_position="top right"
    )
    fig_trend.update_layout(
        title="Evolución Diaria de Ventas",
        template='plotly_white', height=300,
        margin=dict(l=10, r=10, t=40, b=20),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        yaxis_tickprefix='$', yaxis_tickformat=',.0s',
        xaxis_title=None, yaxis_title=None
    )
    st.plotly_chart(fig_trend, use_container_width=True)

st.markdown("---")

# ─────────────────────────────────────────────────────────────────────────────
# FILA 3 — Heatmap semanal + Top vendedores
# ─────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">📆 Comportamiento Temporal y Comercial</div>', unsafe_allow_html=True)
c_heat, c_top_v = st.columns([2, 1])

with c_heat:
    df['DiaSemana'] = df['Fecha'].dt.day_name().map({
        'Monday':'Lun','Tuesday':'Mar','Wednesday':'Mié',
        'Thursday':'Jue','Friday':'Vie','Saturday':'Sáb','Sunday':'Dom'
    })
    df['Semana'] = df['Fecha'].dt.isocalendar().week.astype(str)
    df['AnoSem'] = df['Fecha'].dt.strftime('%Y-W%V')

    # Pivot para heatmap
    heat_data = (
        df.groupby(['DiaSemana', 'AnoSem'])['Total']
        .sum().reset_index()
    )
    dia_order = ['Lun','Mar','Mié','Jue','Vie','Sáb','Dom']
    heat_pivot = heat_data.pivot(index='DiaSemana', columns='AnoSem', values='Total').fillna(0)
    heat_pivot = heat_pivot.reindex([d for d in dia_order if d in heat_pivot.index])
    
    # Limitar columnas si hay muchas semanas
    max_cols = 20
    if heat_pivot.shape[1] > max_cols:
        heat_pivot = heat_pivot.iloc[:, -max_cols:]

    fig_heat = go.Figure(go.Heatmap(
        z=heat_pivot.values,
        x=heat_pivot.columns.tolist(),
        y=heat_pivot.index.tolist(),
        colorscale=[
            [0.0, '#f1f8e9'],
            [0.3, '#a5d6a7'],
            [0.6, '#4caf50'],
            [0.85, '#2e7d32'],
            [1.0, '#1b5e20']
        ],
        hovertemplate='Semana: %{x}<br>Día: %{y}<br>Venta: $%{z:,.0f}<extra></extra>',
        showscale=True,
        colorbar=dict(tickformat='$.2s')
    ))
    fig_heat.update_layout(
        title="Mapa de Calor — Ventas por Semana y Día",
        template='plotly_white', height=280,
        margin=dict(l=10, r=10, t=40, b=20),
        xaxis_title="Semana del año",
        yaxis_title=None
    )
    st.plotly_chart(fig_heat, use_container_width=True)

with c_top_v:
    top_vend = (
        df.groupby('Vendedor')['Total'].sum()
        .reset_index().sort_values('Total', ascending=True).tail(8)
    )
    fig_vend = go.Figure(go.Bar(
        x=top_vend['Total'],
        y=top_vend['Vendedor'],
        orientation='h',
        marker=dict(
            color=top_vend['Total'],
            colorscale=[[0,'#a5d6a7'],[0.5,'#4caf50'],[1,'#1b5e20']],
            showscale=False
        ),
        text=top_vend['Total'].apply(lambda x: f"${x:,.0f}"),
        textposition='outside',
        hovertemplate='%{y}: $%{x:,.0f}<extra></extra>'
    ))
    fig_vend.update_layout(
        title="🏆 Top Vendedores (Recaudo)",
        template='plotly_white', height=280,
        margin=dict(l=10, r=60, t=40, b=20),
        xaxis_tickprefix='$', xaxis_tickformat=',.0s',
        xaxis_title=None, yaxis_title=None
    )
    st.plotly_chart(fig_vend, use_container_width=True)

st.markdown("---")

# ─────────────────────────────────────────────────────────────────────────────
# FILA 4 — Productos + Método de pago + Ciudad
# ─────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">🧩 Desglose de Ventas</div>', unsafe_allow_html=True)
c_prod, c_pay, c_city = st.columns([2, 1, 1])

with c_prod:
    top_prod = (
        df.groupby('Producto').agg(Total=('Total','sum'), Cantidad=('Cantidad','sum'))
        .reset_index().sort_values('Total', ascending=False).head(12)
    )
    fig_prod = go.Figure()
    fig_prod.add_trace(go.Bar(
        name="Valor ($)",
        x=top_prod['Producto'],
        y=top_prod['Total'],
        marker_color='#2e7d32',
        yaxis='y',
        hovertemplate='%{x}<br>Valor: $%{y:,.0f}<extra></extra>'
    ))
    fig_prod.add_trace(go.Scatter(
        name="Unidades",
        x=top_prod['Producto'],
        y=top_prod['Cantidad'],
        mode='lines+markers',
        line=dict(color='#ff9800', width=2),
        marker=dict(size=6),
        yaxis='y2',
        hovertemplate='%{x}<br>Unidades: %{y:,.0f}<extra></extra>'
    ))
    fig_prod.update_layout(
        title="Top 12 Productos",
        template='plotly_white', height=300,
        margin=dict(l=10, r=10, t=40, b=80),
        xaxis_tickangle=-35,
        yaxis=dict(tickprefix='$', tickformat=',.0s', title=None),
        yaxis2=dict(overlaying='y', side='right', title=None),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        barmode='group'
    )
    st.plotly_chart(fig_prod, use_container_width=True)

with c_pay:
    if 'MetodoPago' in df.columns:
        pago_data = (
            df.groupby('NoPedido').agg(MetodoPago=('MetodoPago','first'), Total=('Total','sum'))
            .groupby('MetodoPago')['Total'].sum().reset_index()
        )
        fig_pay = px.pie(
            pago_data, values='Total', names='MetodoPago',
            hole=0.55,
            color_discrete_sequence=['#1b5e20','#388e3c','#66bb6a','#a5d6a7','#e8f5e9'],
            title="💳 Métodos de Pago"
        )
        fig_pay.update_traces(
            textinfo='percent+label',
            textposition='outside',
            hovertemplate='%{label}<br>$%{value:,.0f}<br>%{percent}<extra></extra>'
        )
        fig_pay.update_layout(height=300, margin=dict(l=5,r=5,t=40,b=5), showlegend=False)
        st.plotly_chart(fig_pay, use_container_width=True)
    else:
        st.info("Sin datos de método de pago.")

with c_city:
    if 'Ciudad' in df.columns and df['Ciudad'].notna().any():
        city_data = (
            df.groupby('Ciudad')['Total'].sum()
            .reset_index().sort_values('Total', ascending=True).tail(8)
        )
        fig_city = go.Figure(go.Bar(
            x=city_data['Total'],
            y=city_data['Ciudad'],
            orientation='h',
            marker_color='#1565c0',
            text=city_data['Total'].apply(lambda x: f"${x:,.0f}"),
            textposition='outside',
            hovertemplate='%{y}: $%{x:,.0f}<extra></extra>'
        ))
        fig_city.update_layout(
            title="🏙️ Ventas por Ciudad",
            template='plotly_white', height=300,
            margin=dict(l=10, r=60, t=40, b=5),
            xaxis_tickprefix='$', xaxis_tickformat=',.0s',
            xaxis_title=None, yaxis_title=None
        )
        st.plotly_chart(fig_city, use_container_width=True)
    else:
        st.info("Sin columna Ciudad.")

st.markdown("---")

# ─────────────────────────────────────────────────────────────────────────────
# FILA 5 — Análisis semanal/mensual + Estado de pedidos
# ─────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">📅 Agrupación Temporal</div>', unsafe_allow_html=True)
tab_sem, tab_mes, tab_ruta = st.tabs(["Por Semana", "Por Mes", "Por Ruta"])

with tab_sem:
    df['AnoSem'] = df['Fecha'].dt.strftime('%Y-W%V')
    sem_data = (
        df.groupby('AnoSem').agg(
            Total=('Total','sum'),
            Pedidos=('NoPedido','nunique'),
            Clientes=('ClienteCodigo','nunique')
        ).reset_index()
    )
    fig_sem = make_subplots(specs=[[{"secondary_y": True}]])
    fig_sem.add_trace(go.Bar(
        x=sem_data['AnoSem'], y=sem_data['Total'],
        name='Recaudo', marker_color='#4caf50',
        hovertemplate='%{x}<br>$%{y:,.0f}<extra></extra>'
    ), secondary_y=False)
    fig_sem.add_trace(go.Scatter(
        x=sem_data['AnoSem'], y=sem_data['Pedidos'],
        name='Pedidos', line=dict(color='#1565c0', width=2),
        mode='lines+markers', marker=dict(size=5),
        hovertemplate='%{x}<br>%{y} pedidos<extra></extra>'
    ), secondary_y=True)
    fig_sem.update_layout(
        template='plotly_white', height=320,
        margin=dict(l=10, r=10, t=10, b=60),
        xaxis_tickangle=-45, legend=dict(orientation='h', yanchor='bottom', y=1.02),
        yaxis_tickprefix='$', yaxis_tickformat=',.0s'
    )
    fig_sem.update_yaxes(title_text=None, secondary_y=False)
    fig_sem.update_yaxes(title_text="Pedidos", secondary_y=True)
    st.plotly_chart(fig_sem, use_container_width=True)
    with st.expander("📄 Tabla semanal"):
        st.dataframe(
            sem_data.rename(columns={'AnoSem':'Semana','Total':'Recaudo ($)','Pedidos':'Nº Pedidos'})
            .style.format({'Recaudo ($)':'${:,.0f}'}),
            use_container_width=True, hide_index=True
        )

with tab_mes:
    df['Mes'] = df['Fecha'].dt.strftime('%Y-%m')
    mes_data = (
        df.groupby('Mes').agg(
            Total=('Total','sum'),
            Pedidos=('NoPedido','nunique'),
            Clientes=('ClienteCodigo','nunique')
        ).reset_index()
    )
    # Tasa de crecimiento mes a mes
    mes_data['Crecimiento_%'] = mes_data['Total'].pct_change() * 100

    fig_mes = make_subplots(specs=[[{"secondary_y": True}]])
    fig_mes.add_trace(go.Bar(
        x=mes_data['Mes'], y=mes_data['Total'],
        name='Recaudo', marker_color='#1565c0',
        hovertemplate='%{x}<br>$%{y:,.0f}<extra></extra>'
    ), secondary_y=False)
    fig_mes.add_trace(go.Scatter(
        x=mes_data['Mes'], y=mes_data['Crecimiento_%'],
        name='Crec. MoM %', line=dict(color='#e65100', width=2, dash='dot'),
        mode='lines+markers', marker=dict(size=6),
        hovertemplate='%{x}<br>%{y:.1f}%<extra></extra>'
    ), secondary_y=True)
    fig_mes.update_layout(
        template='plotly_white', height=320,
        margin=dict(l=10, r=10, t=10, b=40),
        legend=dict(orientation='h', yanchor='bottom', y=1.02),
        yaxis_tickprefix='$', yaxis_tickformat=',.0s'
    )
    fig_mes.update_yaxes(title_text=None, secondary_y=False)
    fig_mes.update_yaxes(title_text="Crecimiento MoM %", secondary_y=True)
    st.plotly_chart(fig_mes, use_container_width=True)
    with st.expander("📄 Tabla mensual"):
        st.dataframe(
            mes_data.style.format({'Total':'${:,.0f}','Crecimiento_%':'{:.1f}%'}),
            use_container_width=True, hide_index=True
        )

with tab_ruta:
    if 'Ruta' in df.columns and df['Ruta'].notna().any():
        ruta_data = (
            df.groupby('Ruta').agg(
                Total=('Total','sum'),
                Pedidos=('NoPedido','nunique'),
                Clientes=('ClienteCodigo','nunique')
            ).reset_index().sort_values('Total', ascending=False)
        )
        fig_ruta = px.bar(
            ruta_data, x='Ruta', y='Total',
            color='Pedidos', color_continuous_scale='Greens',
            text=ruta_data['Total'].apply(lambda x: f"${x:,.0f}"),
            template='plotly_white', title='Recaudo por Ruta de Visita'
        )
        fig_ruta.update_traces(textposition='outside')
        fig_ruta.update_layout(
            height=320, margin=dict(l=10, r=10, t=40, b=40),
            xaxis_title=None, yaxis_tickprefix='$', yaxis_tickformat=',.0s'
        )
        st.plotly_chart(fig_ruta, use_container_width=True)
        with st.expander("📄 Tabla por ruta"):
            st.dataframe(
                ruta_data.style.format({'Total':'${:,.0f}'}),
                use_container_width=True, hide_index=True
            )
    else:
        st.info("No hay columna 'Ruta' en los datos.")

st.markdown("---")

# ─────────────────────────────────────────────────────────────────────────────
# FILA 6 — Tabla resumen ejecutivo + Estado de pedidos
# ─────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">📋 Resumen Ejecutivo del Período</div>', unsafe_allow_html=True)

c_estado, c_tabla = st.columns([1, 2])

with c_estado:
    if 'Estado' in df.columns and df['Estado'].notna().any():
        estado_data = (
            df.groupby('NoPedido').agg(Estado=('Estado','first'), Total=('Total','sum'))
            .groupby('Estado')['Total'].sum().reset_index()
        )
        fig_est = px.pie(
            estado_data, values='Total', names='Estado',
            hole=0.6, title="📋 Pedidos por Estado",
            color_discrete_sequence=['#2e7d32','#66bb6a','#ffa726','#ef5350']
        )
        fig_est.update_traces(
            textinfo='percent+label', textposition='outside',
            hovertemplate='%{label}: $%{value:,.0f}<extra></extra>'
        )
        fig_est.update_layout(height=280, margin=dict(l=5,r=5,t=40,b=5), showlegend=False)
        st.plotly_chart(fig_est, use_container_width=True)
    else:
        # Mini KPIs si no hay Estado
        st.metric("Días en período", (date_range[1] - date_range[0]).days + 1 if len(date_range)==2 else "—")
        st.metric("Promedio Diario", f"${total_ventas/max((date_range[1]-date_range[0]).days+1,1):,.0f}" if len(date_range)==2 else "—")
        st.metric("Máx. venta en un día", f"${df.groupby(df['Fecha'].dt.date)['Total'].sum().max():,.0f}")

with c_tabla:
    resumen_vend = (
        df.groupby('Vendedor').agg(
            Recaudo=('Total','sum'),
            Pedidos=('NoPedido','nunique'),
            Clientes_Únicos=('ClienteCodigo','nunique'),
            Unidades=('Cantidad','sum'),
            Ticket_Prom=('Total', lambda x: x.sum() / df.loc[x.index,'NoPedido'].nunique() if df.loc[x.index,'NoPedido'].nunique() > 0 else 0)
        ).reset_index().sort_values('Recaudo', ascending=False)
    )
    resumen_vend['% del Total'] = resumen_vend['Recaudo'] / resumen_vend['Recaudo'].sum() * 100

    st.markdown("**Desempeño por Vendedor en el Período**")
    st.dataframe(
        resumen_vend.style
        .format({
            'Recaudo': '${:,.0f}',
            'Ticket_Prom': '${:,.0f}',
            'Unidades': '{:,.0f}',
            '% del Total': '{:.1f}%'
        })
        .background_gradient(subset=['Recaudo'], cmap='Greens')
        .background_gradient(subset=['% del Total'], cmap='Blues'),
        use_container_width=True, hide_index=True, height=280
    )

st.markdown("<br>", unsafe_allow_html=True)

# Footer
st.markdown(
    f"<div style='text-align:center;color:#aaa;font-size:0.75rem;'>La Campiña Sistema de Gestión · "
    f"Datos al {max_date} · Generado {pd.Timestamp.now().strftime('%d/%m/%Y %H:%M')}</div>",
    unsafe_allow_html=True
)
