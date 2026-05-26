import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import json
import datetime
from pathlib import Path
from utils.data_loader import load_data
from utils.routing import nearest_neighbor_tsp, route_distance_km, greedy_cvrp_heterogeneous

# ── Rutas de datos ────────────────────────────────────────────────────────────
_BASE_DIR   = Path(__file__).resolve().parent.parent / "datos_maestros"
_METAS_PATH = _BASE_DIR / "oee_metas.json"
_CACHE_PATH = _BASE_DIR / "optimizacion_cache.json"

_METAS_DEFAULT = {"meta_diaria": 50, "meta_horas": 8.0, "meta_ticket": 20000}


def _cargar_metas() -> dict:
    if _METAS_PATH.exists():
        try:
            with open(_METAS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {**_METAS_DEFAULT, **data}
        except Exception:
            pass
    return _METAS_DEFAULT.copy()


def _guardar_metas(meta_diaria: int, meta_horas: float, meta_ticket: int) -> None:
    try:
        with open(_METAS_PATH, "w", encoding="utf-8") as f:
            json.dump({"meta_diaria": meta_diaria, "meta_horas": meta_horas,
                       "meta_ticket": meta_ticket}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _semaforo_color(oee: float) -> str:
    if oee >= 80:
        return "#2e7d32"   # verde
    if oee >= 60:
        return "#f9a825"   # amarillo
    return "#c62828"       # rojo


def _semaforo_emoji(oee: float) -> str:
    if oee >= 80:
        return "🟢"
    if oee >= 60:
        return "🟡"
    return "🔴"


def _gauge(valor: float, titulo: str, color: str) -> go.Figure:
    """Gauge tipo velocímetro para un indicador OEE (0-100 %)."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=valor,
        number={"suffix": "%", "font": {"size": 28}},
        delta={"reference": 80, "valueformat": ".1f",
               "increasing": {"color": "#2e7d32"},
               "decreasing": {"color": "#c62828"}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "#555"},
            "bar": {"color": color, "thickness": 0.25},
            "bgcolor": "white",
            "borderwidth": 1,
            "bordercolor": "#ccc",
            "steps": [
                {"range": [0,  60], "color": "#ffebee"},
                {"range": [60, 80], "color": "#fff9c4"},
                {"range": [80, 100], "color": "#e8f5e9"},
            ],
            "threshold": {
                "line": {"color": "#2e7d32", "width": 3},
                "thickness": 0.75,
                "value": 80,
            },
        },
        title={"text": titulo, "font": {"size": 13}},
    ))
    fig.update_layout(height=220, margin=dict(l=10, r=10, t=30, b=10),
                      paper_bgcolor="white")
    return fig


# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @media print {
        header {display: none !important;}
        footer {display: none !important;}
        .stSidebar {display: none !important;}
        .css-v37k9u {padding-top: 0 !important;}
    }
    .kpi-box {
        background-color: #f1f8e9;
        border-left: 5px solid #2e7d32;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 20px;
    }
    .kpi-val   { font-size: 24px; font-weight: bold; color: #1b5e20; }
    .kpi-title { font-size: 14px; color: #555; text-transform: uppercase; font-weight: 600; }
    .kpi-sub   { font-size: 12px; color: #888; }
    .semaforo-row {
        display: flex; align-items: center; gap: 10px;
        padding: 8px 12px; border-radius: 6px; margin-bottom: 4px;
        background: #fafafa; border: 1px solid #e0e0e0;
    }
    .semaforo-nombre { font-weight: 600; flex: 1; }
    .semaforo-badge  {
        padding: 3px 10px; border-radius: 20px; color: white;
        font-weight: bold; font-size: 13px; min-width: 64px; text-align: center;
    }
</style>
""", unsafe_allow_html=True)

st.title("Rutas y Operaciones")
st.markdown("Módulo gerencial avanzado. Compara el rendimiento empírico de preventistas vs. ruteo óptimo (TSP) y planifica la flota de reparto (CVRP).")

data = load_data()
if data is None or data["compras_detalle"].empty:
    st.error("No hay datos operativos para optimizar.")
    st.stop()

df_det = data["compras_detalle"].copy()
df_cli = data["clientes"].copy()

if df_cli.empty or "Latitud" not in df_cli.columns:
    st.error("La base de clientes carece de datos geográficos. No se puede optimizar.")
    st.stop()

df_det["Fecha"] = pd.to_datetime(df_det["Fecha"], errors="coerce")
df_cli["Codigo"] = df_cli["Codigo"].astype(str)
df_det["ClienteCodigo"] = df_det["ClienteCodigo"].astype(str)

df_full = pd.merge(df_det, df_cli[["Codigo", "Nombre", "Latitud", "Longitud", "Barrio"]],
                   left_on="ClienteCodigo", right_on="Codigo", how="left")
df_full["Latitud"]  = pd.to_numeric(df_full["Latitud"],  errors="coerce")
df_full["Longitud"] = pd.to_numeric(df_full["Longitud"], errors="coerce")

tab_preventa, tab_reparto, tab_pareto = st.tabs([
    "1. Eficiencia de Preventistas (OEE)",
    "2. Despacho de Reparto (CVRP)",
    "3. Rentabilidad vs Distancia (Pareto)",
])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — OEE COMERCIAL
# ─────────────────────────────────────────────────────────────────────────────
with tab_preventa:
    st.markdown("### Indicadores Operativos de Tiempo y Cobertura")
    st.markdown("Analiza la gestión temporal de tus vendedores. Compara cobertura de visitas vs. tiempos de facturación y estadía por cliente.")

    # ── Filtros ───────────────────────────────────────────────────────────────
    col_f1, col_f2 = st.columns([1.5, 2])
    vendedores_lista = ["Todos"] + sorted(df_full["Vendedor"].dropna().unique().tolist())

    with col_f1:
        sel_vend = st.selectbox("Preventista:", vendedores_lista)

    with col_f2:
        min_d = df_full["Fecha"].min().date()
        max_d = df_full["Fecha"].max().date()
        if min_d == max_d:
            max_d += datetime.timedelta(days=1)
        rango_fechas = st.slider("Rango de Auditoría:", min_value=min_d, max_value=max_d,
                                 value=(min_d, max_d))

    # ── Metas OEE persistentes ────────────────────────────────────────────────
    metas_guardadas = _cargar_metas()

    with st.expander("Metas OEE Comercial", expanded=True):
        c_m1, c_m2, c_m3, c_m4 = st.columns([1, 1, 1, 0.6])
        meta_diaria = c_m1.number_input(
            "Clientes/Día", min_value=1, value=int(metas_guardadas["meta_diaria"]),
            help="Visitas meta diarias (Rendimiento)")
        meta_horas = c_m2.number_input(
            "Horas/Día", min_value=1.0, value=float(metas_guardadas["meta_horas"]),
            step=0.5, help="Jornada esperada (Disponibilidad)")
        meta_ticket = c_m3.number_input(
            "Ticket Meta ($)", min_value=1000, value=int(metas_guardadas["meta_ticket"]),
            step=1000, help="Venta meta por cliente (Calidad)")
        c_m4.markdown("<br>", unsafe_allow_html=True)
        if c_m4.button("Guardar metas", use_container_width=True):
            _guardar_metas(meta_diaria, meta_horas, meta_ticket)
            st.success("Metas guardadas.")

    col_imp, _ = st.columns([1, 3])
    with col_imp:
        if st.button("Imprimir / PDF", type="secondary", use_container_width=True):
            st.components.v1.html("<script>window.print()</script>", height=0)

    # ── Cálculo principal ─────────────────────────────────────────────────────
    if len(rango_fechas) == 2:
        df_periodo = df_full[
            (df_full["Fecha"].dt.date >= rango_fechas[0]) &
            (df_full["Fecha"].dt.date <= rango_fechas[1])
        ].copy()

        if sel_vend != "Todos":
            df_periodo = df_periodo[df_periodo["Vendedor"] == sel_vend]

        if df_periodo.empty:
            st.warning("No hay visitas registradas en este periodo para este filtro.")
        else:
            with st.spinner("Analizando jornadas..."):
                # Caché persistente
                cache_rutas: dict = {}
                if _CACHE_PATH.exists():
                    try:
                        with open(_CACHE_PATH, "r", encoding="utf-8") as f:
                            cache_rutas = json.load(f)
                    except Exception:
                        pass

                nuevos_calculos = False
                resultados_diarios: list[dict] = []

                for (vendedor, fecha), df_jornada in df_periodo.groupby(
                        ["Vendedor", df_periodo["Fecha"].dt.date]):
                    fecha_str = fecha.strftime("%Y-%m-%d")
                    cache_key = f"{vendedor}_{fecha_str}"

                    if cache_key in cache_rutas:
                        resultados_diarios.append(cache_rutas[cache_key])
                        continue

                    if "Hora" in df_jornada.columns:
                        df_jornada = df_jornada.sort_values("Hora")

                    visitas = df_jornada.drop_duplicates(subset=["ClienteCodigo"]).reset_index(drop=True)
                    num_visitas = len(visitas)
                    if num_visitas == 0:
                        continue

                    tiempo_promedio = 0.0
                    jornada_horas   = 0.0
                    ticket_promedio = df_jornada["Total"].sum() / num_visitas

                    temp_col = "Hora" if "Hora" in df_jornada.columns else "Fecha"
                    temp = df_jornada.dropna(subset=[temp_col]).sort_values(temp_col)
                    if not temp.empty:
                        ts = pd.to_datetime(temp[temp_col], errors="coerce")
                        delta = ts.max() - ts.min()
                        jornada_horas = delta.total_seconds() / 3600.0
                        diffs = ts.diff().dt.total_seconds() / 60
                        diffs = diffs[diffs > 0]
                        if not diffs.empty:
                            tiempo_promedio = diffs.mean()

                    resultado = {
                        "Vendedor": vendedor,
                        "Fecha": fecha_str,
                        "Visitas": num_visitas,
                        "JornadaHoras": jornada_horas,
                        "TiempoPromedioPedido": tiempo_promedio,
                        "TicketPromedio": ticket_promedio,
                    }
                    resultados_diarios.append(resultado)
                    cache_rutas[cache_key] = resultado
                    nuevos_calculos = True

                if nuevos_calculos:
                    try:
                        with open(_CACHE_PATH, "w", encoding="utf-8") as f:
                            json.dump(cache_rutas, f, ensure_ascii=False, indent=2)
                    except Exception:
                        pass

                for r in resultados_diarios:
                    r["Fecha"] = pd.to_datetime(r["Fecha"]).date()

                if not resultados_diarios:
                    st.info("No hay jornadas registradas en este rango.")
                    st.stop()

                df_res = pd.DataFrame(resultados_diarios)
                df_res["Visitas"] = df_res["Visitas"].replace(0, 1)

                df_res["Cobertura"]           = (df_res["Visitas"] / meta_diaria) * 100
                df_res["TiempoPromedioCliente"] = (df_res["JornadaHoras"] * 60) / df_res["Visitas"]

                # ── FIX: clip upper=1.0 (OEE no puede superar 100 %) ─────────
                df_res["Ind_Rendimiento"]    = (df_res["Visitas"]         / meta_diaria).clip(0, 1.0)
                df_res["Ind_Disponibilidad"] = (df_res["JornadaHoras"]    / meta_horas ).clip(0, 1.0)
                df_res["Ind_Calidad"]        = (df_res["TicketPromedio"]  / meta_ticket).clip(0, 1.0)
                df_res["OEE"] = (
                    df_res["Ind_Rendimiento"] *
                    df_res["Ind_Disponibilidad"] *
                    df_res["Ind_Calidad"]
                ) * 100
                df_res.fillna(0, inplace=True)

                promedio_cobertura  = df_res["Cobertura"].mean()
                total_visitas       = int(df_res["Visitas"].sum())
                promedio_pedido     = df_res["TiempoPromedioPedido"].mean()
                promedio_ticket     = df_res["TicketPromedio"].mean()
                promedio_oee        = df_res["OEE"].mean()
                avg_disponibilidad  = df_res["Ind_Disponibilidad"].mean() * 100
                avg_rendimiento     = df_res["Ind_Rendimiento"].mean()    * 100
                avg_calidad         = df_res["Ind_Calidad"].mean()        * 100

            # ── Banner OEE ────────────────────────────────────────────────────
            st.markdown("---")
            oee_color = _semaforo_color(promedio_oee)
            oee_emoji = _semaforo_emoji(promedio_oee)
            st.markdown(
                f"#### {oee_emoji} OEE Comercial Consolidado: "
                f"<span style='color:{oee_color};font-size:1.4em;font-weight:900;'>"
                f"{promedio_oee:.1f}%</span>",
                unsafe_allow_html=True,
            )

            # ── Gauges ────────────────────────────────────────────────────────
            g1, g2, g3 = st.columns(3)
            g1.plotly_chart(_gauge(avg_disponibilidad, "Disponibilidad (Jornada)", "#42a5f5"),
                            use_container_width=True)
            g2.plotly_chart(_gauge(avg_rendimiento,    "Rendimiento (Cobertura)",  "#ffa726"),
                            use_container_width=True)
            g3.plotly_chart(_gauge(avg_calidad,        "Calidad (Ticket)",         "#ab47bc"),
                            use_container_width=True)

            # ── KPIs ──────────────────────────────────────────────────────────
            c_k1, c_k2, c_k3, c_k4, c_k5 = st.columns(5)
            c_k1.markdown(f"""
            <div class="kpi-box">
                <div class="kpi-title">Visitas Totales</div>
                <div class="kpi-val">{total_visitas:,}</div>
                <div class="kpi-sub">Total de impactos.</div>
            </div>""", unsafe_allow_html=True)

            color_ef = _semaforo_color(promedio_cobertura)
            c_k2.markdown(f"""
            <div class="kpi-box" style="border-color:{color_ef};">
                <div class="kpi-title">Cobertura Media</div>
                <div class="kpi-val" style="color:{color_ef};">{promedio_cobertura:.1f}%</div>
                <div class="kpi-sub">De la meta diaria asignada.</div>
            </div>""", unsafe_allow_html=True)

            c_k3.markdown(f"""
            <div class="kpi-box" style="border-color:#1565c0;">
                <div class="kpi-title">Jornada Operativa</div>
                <div class="kpi-val" style="color:#1565c0;">{df_res['JornadaHoras'].mean():.1f} hr/día</div>
                <div class="kpi-sub">Tiempo medio de trabajo.</div>
            </div>""", unsafe_allow_html=True)

            c_k4.markdown(f"""
            <div class="kpi-box" style="border-color:#bf360c;">
                <div class="kpi-title">Ritmo de Facturación</div>
                <div class="kpi-val" style="color:#bf360c;">{promedio_pedido:.1f} min</div>
                <div class="kpi-sub">Margen entre compras.</div>
            </div>""", unsafe_allow_html=True)

            c_k5.markdown(f"""
            <div class="kpi-box" style="border-color:#2e7d32;">
                <div class="kpi-title">Ticket Promedio</div>
                <div class="kpi-val" style="color:#2e7d32;">${promedio_ticket:,.0f}</div>
                <div class="kpi-sub">Por cliente.</div>
            </div>""", unsafe_allow_html=True)

            # ── Gráficos principales ──────────────────────────────────────────
            g_c1, g_c2 = st.columns(2)
            with g_c1:
                st.markdown("**Variación Diaria (Cobertura vs Tiempo por Cliente)**")
                from plotly.subplots import make_subplots
                fig_co = make_subplots(specs=[[{"secondary_y": True}]])
                fig_co.add_trace(go.Bar(x=df_res["Fecha"], y=df_res["Cobertura"],
                                        name="Cobertura (%)", marker_color="#1565c0"),
                                 secondary_y=False)
                fig_co.add_trace(go.Scatter(x=df_res["Fecha"], y=df_res["TiempoPromedioCliente"],
                                            name="Estadía x Cliente (min)", mode="lines+markers",
                                            line=dict(color="#e65100", width=2)),
                                 secondary_y=True)

                y_vals = df_res["TiempoPromedioCliente"].values
                valid_mask = (~np.isnan(y_vals)) & (y_vals > 0)
                if valid_mask.sum() > 1:
                    x_nums  = np.arange(len(df_res["Fecha"]))[valid_mask]
                    y_valid = y_vals[valid_mask]
                    p       = np.polyfit(x_nums, y_valid, 1)
                    trend   = np.polyval(p, np.arange(len(df_res["Fecha"])))
                    ybar    = np.mean(y_valid)
                    ssreg   = np.sum((np.polyval(p, x_nums) - ybar) ** 2)
                    sstot   = np.sum((y_valid - ybar) ** 2)
                    r2      = (ssreg / sstot) if sstot != 0 else 0
                    fig_co.add_trace(go.Scatter(x=df_res["Fecha"], y=trend, mode="lines",
                                                line=dict(dash="dash", color="red", width=1.5),
                                                name=f"Tendencia (R²={r2:.2f})"),
                                     secondary_y=True)

                fig_co.update_layout(template="plotly_white", margin=dict(l=0, r=0, t=30, b=0),
                                     legend=dict(orientation="h", y=1.1))
                st.plotly_chart(fig_co, use_container_width=True)

            with g_c2:
                st.markdown("**Desglose del OEE Comercial Diario**")
                fig_oee = go.Figure()
                fig_oee.add_trace(go.Scatter(x=df_res["Fecha"], y=df_res["Ind_Disponibilidad"] * 100,
                                             mode="lines", name="Disponibilidad",
                                             line=dict(color="#42a5f5", width=1.5)))
                fig_oee.add_trace(go.Scatter(x=df_res["Fecha"], y=df_res["Ind_Rendimiento"] * 100,
                                             mode="lines", name="Rendimiento",
                                             line=dict(color="#ffa726", width=1.5)))
                fig_oee.add_trace(go.Scatter(x=df_res["Fecha"], y=df_res["Ind_Calidad"] * 100,
                                             mode="lines", name="Calidad",
                                             line=dict(color="#ab47bc", width=1.5)))
                fig_oee.add_trace(go.Scatter(x=df_res["Fecha"], y=df_res["OEE"],
                                             mode="lines+markers", name="OEE Total",
                                             line=dict(color="#2e7d32", width=4)))
                fig_oee.add_hline(y=80, line_dash="dot", line_color="#2e7d32",
                                  annotation_text="Meta 80%", annotation_position="right")
                fig_oee.update_layout(template="plotly_white", margin=dict(l=0, r=0, t=30, b=0),
                                      legend=dict(orientation="h", y=1.1))
                st.plotly_chart(fig_oee, use_container_width=True)

            # ── Gráficos secundarios ──────────────────────────────────────────
            g_c3, g_c4 = st.columns(2)
            with g_c3:
                st.markdown("**Matriz Multidimensional (Visitas vs Dinero vs Tiempo)**")
                fig_3d = px.scatter(df_res, x="Visitas", y="TicketPromedio",
                                    size="JornadaHoras", color="OEE",
                                    hover_name="Fecha", size_max=25,
                                    color_continuous_scale="RdYlGn")
                fig_3d.add_hline(y=meta_ticket, line_dash="dash", line_color="gray",
                                 annotation_text="Meta Ticket")
                fig_3d.add_vline(x=meta_diaria, line_dash="dash", line_color="gray",
                                 annotation_text="Meta Clientes")
                fig_3d.update_layout(template="plotly_white", margin=dict(l=0, r=0, t=30, b=0))
                st.plotly_chart(fig_3d, use_container_width=True)

            with g_c4:
                if sel_vend == "Todos":
                    st.markdown("**Top Vendedores con Mayor Tiempo por Cliente**")
                    df_vend = df_res.groupby("Vendedor")[["Visitas", "JornadaHoras"]].sum().reset_index()
                    df_vend["TiempoXCliente"] = (df_vend["JornadaHoras"] * 60) / df_vend["Visitas"]
                    df_vend = df_vend.sort_values("TiempoXCliente", ascending=False).head(10)
                    fig_bar = px.bar(df_vend, y="Vendedor", x="TiempoXCliente", orientation="h",
                                    text=df_vend["TiempoXCliente"].apply(lambda x: f"{x:.1f} min"),
                                    color="Visitas", color_continuous_scale="Reds")
                    fig_bar.update_layout(template="plotly_white", margin=dict(l=0, r=0, t=30, b=0),
                                          showlegend=False)
                    fig_bar.update_yaxes(categoryorder="total ascending", title="")
                    st.plotly_chart(fig_bar, use_container_width=True)
                else:
                    st.markdown("**Desempeño Individual del Preventista**")
                    max_visitas = df_res["Visitas"].max()
                    st.info(f"**Pico máximo de clientes:** {max_visitas} el "
                            f"{df_res.loc[df_res['Visitas'].idxmax(), 'Fecha']}")
                    st.info(f"**Jornada más larga:** {df_res['JornadaHoras'].max():.1f} hrs el "
                            f"{df_res.loc[df_res['JornadaHoras'].idxmax(), 'Fecha']}")
                    st.info(f"**Día más rápido por cliente:** "
                            f"{df_res.loc[df_res['TiempoPromedioCliente'].idxmin(), 'Fecha']} "
                            f"({df_res['TiempoPromedioCliente'].min():.1f} min/cliente)")

            # ── Semáforo por vendedor ─────────────────────────────────────────
            st.markdown("---")
            st.markdown("#### Semáforo OEE por Vendedor")
            st.caption("Verde ≥ 80% · Amarillo 60-79% · Rojo < 60%")

            df_sem = (
                df_res.groupby("Vendedor")
                .agg(
                    OEE_Prom=("OEE", "mean"),
                    Jornadas=("Fecha", "count"),
                    Visitas_Tot=("Visitas", "sum"),
                    Disponibilidad=("Ind_Disponibilidad", "mean"),
                    Rendimiento=("Ind_Rendimiento", "mean"),
                    Calidad=("Ind_Calidad", "mean"),
                )
                .reset_index()
                .sort_values("OEE_Prom", ascending=False)
            )

            for _, row in df_sem.iterrows():
                oee_v    = row["OEE_Prom"]
                color_bg = _semaforo_color(oee_v)
                emoji    = _semaforo_emoji(oee_v)
                disp_pct = row["Disponibilidad"] * 100
                rend_pct = row["Rendimiento"]    * 100
                cal_pct  = row["Calidad"]        * 100
                st.markdown(f"""
                <div class="semaforo-row">
                    <span style="font-size:1.2em;">{emoji}</span>
                    <span class="semaforo-nombre">{row['Vendedor']}</span>
                    <span class="semaforo-badge" style="background:{color_bg};">{oee_v:.1f}%</span>
                    <span style="font-size:11px;color:#555;">
                        {int(row['Jornadas'])} días &nbsp;|&nbsp;
                        {int(row['Visitas_Tot'])} visitas &nbsp;|&nbsp;
                        D:{disp_pct:.0f}% R:{rend_pct:.0f}% C:{cal_pct:.0f}%
                    </span>
                </div>""", unsafe_allow_html=True)

            # ── Tabla detalle ─────────────────────────────────────────────────
            st.markdown("**Detalle Operativo de Jornadas**")
            st.dataframe(
                df_res[["Fecha", "Vendedor", "Visitas", "JornadaHoras",
                         "TiempoPromedioCliente", "TicketPromedio", "Cobertura", "OEE"]]
                .style.format({
                    "JornadaHoras":          "{:.1f} hrs",
                    "Cobertura":             "{:.1f}%",
                    "OEE":                   "{:.1f}%",
                    "TiempoPromedioCliente": "{:.1f} min",
                    "TicketPromedio":        "${:,.0f}",
                })
                .background_gradient(subset=["OEE"], cmap="RdYlGn"),
                use_container_width=True, hide_index=True,
            )

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — DESPACHO / CVRP
# ─────────────────────────────────────────────────────────────────────────────
with tab_reparto:
    st.markdown("### Planificación de Flota y Entregas")
    st.markdown("Analiza el volumen de despacho vs. la capacidad máxima de tu flota (Utilización de Furgones).")

    col_c1, col_c2 = st.columns([1, 2])
    with col_c1:
        min_dr = df_full["Fecha"].min().date()
        max_dr = df_full["Fecha"].max().date()
        if min_dr == max_dr:
            max_dr += datetime.timedelta(days=1)
        rango_entregas = st.slider("Rango de Despacho:", min_value=min_dr, max_value=max_dr,
                                   value=(min_dr, max_dr), key="sl_entregas")
    with col_c2:
        st.markdown("**Flota disponible todos los días**")
        cx1, cx2 = st.columns(2)
        cvrp_furgon_qty = cx1.number_input("Nº Vehículos", min_value=1, value=2)
        cvrp_furgon_cap = cx2.number_input("Capacidad c/u (Unds)", min_value=10, value=3000)
        capacidad_diaria_total = cvrp_furgon_qty * cvrp_furgon_cap

    st.markdown("<br>", unsafe_allow_html=True)

    if len(rango_entregas) == 2:
        df_desp = df_full[
            (df_full["Fecha"].dt.date >= rango_entregas[0]) &
            (df_full["Fecha"].dt.date <= rango_entregas[1])
        ].copy()

        df_desp_dia = df_desp.groupby(df_desp["Fecha"].dt.date).agg(
            UnidadesVendidas=("Cantidad",      "sum"),
            TotalRecaudo    =("Total",         "sum"),
            ClientesAVisitar=("ClienteCodigo", "nunique"),
        ).reset_index()

        if df_desp_dia.empty:
            st.warning("No hay pedidos entregables en estas fechas.")
        else:
            df_desp_dia["CapacidadFlota"]       = capacidad_diaria_total
            df_desp_dia["PorcentajeUso"]        = (df_desp_dia["UnidadesVendidas"] / df_desp_dia["CapacidadFlota"]) * 100
            df_desp_dia["ExcesoPorcentaje"]     = df_desp_dia["PorcentajeUso"].apply(lambda x: x - 100 if x > 100 else 0)
            df_desp_dia["CapacidadOciosaUnidades"] = df_desp_dia.apply(
                lambda r: r["CapacidadFlota"] - r["UnidadesVendidas"] if r["PorcentajeUso"] <= 100 else 0, axis=1)

            st.markdown("---")
            st.markdown("#### Métricas de Satisfacción Logística")

            r_k1, r_k2, r_k3 = st.columns(3)
            promedio_uso = df_desp_dia["PorcentajeUso"].mean()
            dias_exceso  = len(df_desp_dia[df_desp_dia["PorcentajeUso"] > 100])
            total_ocioso = df_desp_dia["CapacidadOciosaUnidades"].sum()

            r_k1.markdown(f"""
            <div class="kpi-box">
                <div class="kpi-title">Uso Promedio de Flota</div>
                <div class="kpi-val">{promedio_uso:.1f}%</div>
                <div class="kpi-sub">Grado de ocupación de los {cvrp_furgon_qty} camiones.</div>
            </div>""", unsafe_allow_html=True)

            r_k2.markdown(f"""
            <div class="kpi-box" style="border-color:{'#c62828' if dias_exceso > 0 else '#2e7d32'};">
                <div class="kpi-title">Días de Desbordamiento</div>
                <div class="kpi-val" style="color:{'#c62828' if dias_exceso > 0 else '#2e7d32'};">{dias_exceso} Días</div>
                <div class="kpi-sub">Ventas superaron la capacidad.</div>
            </div>""", unsafe_allow_html=True)

            r_k3.markdown(f"""
            <div class="kpi-box" style="border-color:#fbc02d;">
                <div class="kpi-title">Unidades Ociosas</div>
                <div class="kpi-val" style="color:#f9a825;">{total_ocioso:,.0f} unds</div>
                <div class="kpi-sub">Espacios vacíos acumulados.</div>
            </div>""", unsafe_allow_html=True)

            fig_uso = go.Figure()
            fig_uso.add_trace(go.Bar(x=df_desp_dia["Fecha"], y=df_desp_dia["UnidadesVendidas"],
                                     name="Volumen de Ventas (Unds)", marker_color="#1565c0"))
            fig_uso.add_trace(go.Scatter(x=df_desp_dia["Fecha"], y=df_desp_dia["CapacidadFlota"],
                                         mode="lines", name="Límite de Capacidad",
                                         line=dict(color="red", width=3, dash="dash")))
            fig_uso.update_layout(title="Llenado Diario de Vehículos (Ventas vs Capacidad)",
                                  barmode="overlay", template="plotly_white")
            st.plotly_chart(fig_uso, use_container_width=True)

            st.markdown("**Alertas y Saturaciones Diarias**")
            st.dataframe(
                df_desp_dia[["Fecha", "UnidadesVendidas", "PorcentajeUso", "ClientesAVisitar"]]
                .style.format({"UnidadesVendidas": "{:,.0f}", "PorcentajeUso": "{:.1f}%"})
                .background_gradient(subset=["PorcentajeUso"], cmap="RdYlGn_r"),
                use_container_width=True, hide_index=True,
            )

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — PARETO LOGÍSTICO
# ─────────────────────────────────────────────────────────────────────────────
with tab_pareto:
    st.markdown("### Matriz de Rentabilidad vs Esfuerzo Logístico")
    st.markdown("Identifica cuáles clientes generan pérdidas por lejanía y bajo volumen de compra.")

    min_dp = df_full["Fecha"].min().date()
    max_dp = df_full["Fecha"].max().date()
    if min_dp == max_dp:
        max_dp += datetime.timedelta(days=1)
    rango_pareto = st.slider("Rango de Evaluación Comercial:", min_value=min_dp, max_value=max_dp,
                             value=(min_dp, max_dp), key="sl_pareto")

    if len(rango_pareto) == 2:
        df_par = df_full[
            (df_full["Fecha"].dt.date >= rango_pareto[0]) &
            (df_full["Fecha"].dt.date <= rango_pareto[1])
        ].copy()

        if df_par.empty:
            st.warning("No hay datos de ventas en este periodo.")
        else:
            with st.spinner("Calculando distancias y rentabilidad..."):
                lat_bodega = df_par["Latitud"].mean()
                lon_bodega = df_par["Longitud"].mean()

                df_cli_rent = df_par.groupby(
                    ["ClienteCodigo", "Nombre", "Latitud", "Longitud"]
                ).agg(TotalCompras=("Total", "sum"), FrecuenciaVisitas=("Fecha", "nunique")).reset_index()

                def haversine(lat1, lon1, lat2, lon2):
                    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
                    dlat, dlon = lat2 - lat1, lon2 - lon1
                    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
                    return 6371 * 2 * np.arcsin(np.sqrt(a))

                df_cli_rent["DistanciaBodega_Km"] = haversine(
                    lat_bodega, lon_bodega, df_cli_rent["Latitud"], df_cli_rent["Longitud"])

                media_compras  = df_cli_rent["TotalCompras"].median()
                media_distancia = df_cli_rent["DistanciaBodega_Km"].median()

                def clasificar_cuadrante(row):
                    cerca  = row["DistanciaBodega_Km"] <= media_distancia
                    mucho  = row["TotalCompras"]        >= media_compras
                    if   mucho and  cerca: return "Estrellas (Cerca, Compran Mucho)"
                    elif mucho and not cerca: return "Caballos de Batalla (Lejos, Compran Mucho)"
                    elif not mucho and  cerca: return "Relleno de Ruta (Cerca, Compran Poco)"
                    else: return "Carga Muerta (Lejos, Compran Poco)"

                df_cli_rent["Clasificacion"] = df_cli_rent.apply(clasificar_cuadrante, axis=1)
                clientes_criticos = (
                    df_cli_rent[df_cli_rent["Clasificacion"] == "Carga Muerta (Lejos, Compran Poco)"]
                    .sort_values("DistanciaBodega_Km", ascending=False)
                )

                st.markdown("---")
                if not clientes_criticos.empty:
                    peor = clientes_criticos.iloc[0]
                    st.warning(
                        f"**Foco Logístico:** {len(clientes_criticos)} clientes 'Carga Muerta'. "
                        f"Ej: **{peor['Nombre']}** a {peor['DistanciaBodega_Km']:.1f} km, "
                        f"visitado {peor['FrecuenciaVisitas']} veces, compró ${peor['TotalCompras']:,.0f}."
                    )

                fig_scatter = px.scatter(
                    df_cli_rent, x="DistanciaBodega_Km", y="TotalCompras",
                    color="Clasificacion", size="FrecuenciaVisitas", hover_name="Nombre",
                    color_discrete_map={
                        "Estrellas (Cerca, Compran Mucho)":         "#2e7d32",
                        "Caballos de Batalla (Lejos, Compran Mucho)": "#0277bd",
                        "Relleno de Ruta (Cerca, Compran Poco)":    "#fbc02d",
                        "Carga Muerta (Lejos, Compran Poco)":       "#c62828",
                    },
                    title="Matriz de Pareto Logístico (Rentabilidad vs Distancia)",
                )
                fig_scatter.add_vline(x=media_distancia, line_width=2, line_dash="dash", line_color="black")
                fig_scatter.add_hline(y=media_compras,   line_width=2, line_dash="dash", line_color="black")
                fig_scatter.update_layout(template="plotly_white")
                st.plotly_chart(fig_scatter, use_container_width=True)

                c_p1, c_p2 = st.columns(2)
                with c_p1:
                    df_res_par = df_cli_rent.groupby("Clasificacion").agg(
                        Cantidad_Clientes=("ClienteCodigo", "count"),
                        Ingresos_Totales =("TotalCompras",  "sum"),
                    ).reset_index()
                    fig_pie = px.pie(df_res_par, values="Cantidad_Clientes", names="Clasificacion",
                                     title="Distribución de Clientes por Cuadrante", hole=0.4)
                    st.plotly_chart(fig_pie, use_container_width=True)

                with c_p2:
                    st.markdown("**Listado Crítico de Carga Muerta**")
                    st.caption("Visitar con menor frecuencia — 1 vez/semana o menos.")
                    df_muertos = clientes_criticos[
                        ["Nombre", "DistanciaBodega_Km", "TotalCompras", "FrecuenciaVisitas"]
                    ].head(10)
                    st.dataframe(
                        df_muertos.style.format(
                            {"DistanciaBodega_Km": "{:.2f} km", "TotalCompras": "${:,.0f}"}
                        ).background_gradient(subset=["TotalCompras"], cmap="Reds_r"),
                        hide_index=True, use_container_width=True,
                    )
