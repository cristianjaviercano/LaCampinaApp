import streamlit as st
import pandas as pd
from datetime import datetime, date
import math
from pathlib import Path
from urllib.parse import quote
from utils.data_loader import load_data
from utils.file_utils import safe_write_json, safe_append_rows
from utils.promos import get_active_promos, bundle_to_cart_items, descuento_to_cart_item

try:
    import folium
    from streamlit_folium import st_folium
    has_map = True
except ImportError:
    has_map = False

# ── Identidad del operador ────────────────────────────────────────────────────
user_info = st.session_state.get('user_info', {})
vend_code = user_info.get('username', 'Desconocido').upper()
vend_actual = user_info.get('name', vend_code).upper()
role = user_info.get('role', 'PREVENTISTA')

st.title("Preventista")

if role in ["ADMINISTRADOR", "DUEÑO"]:
    vend_input = st.selectbox("Vista de preventista:", ["DAIFER GENEY", "JUNIOR MARQUEZ", "JOSE PEREZ"])
    vend_actual = vend_input.strip().upper()

# ── Rutas de archivos ─────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).resolve().parent.parent
MAESTROS_DIR  = BASE_DIR / "datos_maestros"
COMPRAS_PATH  = MAESTROS_DIR / "compras_maestras.json"
UBICACIONES_PATH = MAESTROS_DIR / "ubicaciones.json"
CLIENTES_PATH = MAESTROS_DIR / "clientes_maestro.json"
PRODUCTOS_PATH = MAESTROS_DIR / "productos.json"

# ── Datos ─────────────────────────────────────────────────────────────────────
data = load_data()
if not data:
    st.error("Error al cargar la base de datos.")
    st.stop()

df_clientes  = data['clientes'].copy()
df_productos = data['productos'].copy()
df_compras   = data['compras_detalle'].copy()

df_mis_pedidos = (
    df_compras[df_compras['Vendedor'].astype(str).str.upper() == vend_actual].copy()
    if not df_compras.empty else pd.DataFrame()
)

# ── Día de trabajo ────────────────────────────────────────────────────────────
dias_map     = {"LUNES": 0, "MARTES": 1, "MIERCOLES": 2, "JUEVES": 3, "VIERNES": 4, "SABADO": 5, "DOMINGO": 6}
inv_dias_map = {v: k for k, v in dias_map.items()}
hoy_str_dia  = inv_dias_map.get(datetime.now().weekday(), "LUNES")

dia_trabajo = st.selectbox(
    "🗓️ Día de jornada:",
    list(dias_map.keys()),
    index=list(dias_map.keys()).index(hoy_str_dia),
    label_visibility="visible"
)

# ── StockAsignado (pedidos confirmados pero aún no despachados) ───────────────
# El stock físico baja solo al despacho; aquí sólo se compromete "StockAsignado".
if not df_compras.empty and 'Estado' in df_compras.columns:
    df_asig = (
        df_compras[df_compras['Estado'].str.upper().isin(["ASIGNADO", "TOMADO_PREVENTISTA"])]
        .groupby('CodigoProducto')['Cantidad']
        .sum()
        .reset_index()
        .rename(columns={'CodigoProducto': 'Codigo', 'Cantidad': 'StockAsignado'})
    )
    df_asig['Codigo'] = df_asig['Codigo'].astype(str)
else:
    df_asig = pd.DataFrame(columns=['Codigo', 'StockAsignado'])

df_productos['Codigo'] = df_productos['Codigo'].astype(str)
df_productos = df_productos.merge(df_asig, on='Codigo', how='left')
df_productos['StockAsignado']   = df_productos['StockAsignado'].fillna(0)
df_productos['Stock']           = df_productos.get('Stock', pd.Series(0, index=df_productos.index)).fillna(0)
df_productos['StockDisponible'] = df_productos['Stock'] - df_productos['StockAsignado']

# ── Ruta de hoy (TSP) ─────────────────────────────────────────────────────────
c_hist, c_ubi = [], []

if not df_mis_pedidos.empty:
    df_mis_pedidos['Fecha_DT'] = pd.to_datetime(df_mis_pedidos['Fecha'], errors='coerce')
    df_mis_pedidos['DiaSem']   = df_mis_pedidos['Fecha_DT'].dt.weekday.map(inv_dias_map)
    c_hist = df_mis_pedidos[df_mis_pedidos['DiaSem'] == dia_trabajo]['ClienteNombre'].dropna().unique().tolist()

if UBICACIONES_PATH.exists():
    df_ubi = pd.read_json(UBICACIONES_PATH)
    if not df_ubi.empty and 'Ruta' in df_ubi.columns:
        c_ubi = df_ubi[df_ubi['Ruta'].astype(str).str.upper() == dia_trabajo.upper()]['Cliente'].dropna().unique().tolist()

clientes_ruta_hoy = list(set(c_hist + c_ubi))

if len(clientes_ruta_hoy) >= 2:
    df_rg = pd.merge(
        pd.DataFrame({'ClienteNombre': clientes_ruta_hoy}),
        df_clientes[['Nombre', 'Latitud', 'Longitud']],
        left_on='ClienteNombre', right_on='Nombre', how='left'
    )
    df_rg['Latitud']  = pd.to_numeric(df_rg['Latitud'],  errors='coerce')
    df_rg['Longitud'] = pd.to_numeric(df_rg['Longitud'], errors='coerce')
    validos   = df_rg.dropna(subset=['Latitud', 'Longitud']).reset_index(drop=True)
    invalidos = df_rg[df_rg['Latitud'].isna()]['ClienteNombre'].tolist()
    if len(validos) >= 2:
        try:
            from utils.routing import nearest_neighbor_tsp
            orden = nearest_neighbor_tsp(validos[['Latitud', 'Longitud']], use_streets=True)
            clientes_ruta_hoy = [validos.iloc[i]['ClienteNombre'] for i in orden] + invalidos
        except Exception:
            clientes_ruta_hoy = validos['ClienteNombre'].tolist() + invalidos

# ── OEE Banner — estadísticas del día actual ─────────────────────────────────
hoy_puro = date.today().strftime('%Y-%m-%d')
ventas_reales_hoy = pd.DataFrame()
if not df_mis_pedidos.empty:
    tmp = df_mis_pedidos.copy()
    tmp['Fecha_DT'] = pd.to_datetime(tmp['Fecha'], errors='coerce')
    tmp_hoy = tmp[tmp['Fecha_DT'].dt.date.astype(str) == hoy_puro]
    ventas_reales_hoy = tmp_hoy[tmp_hoy.get('Estado', pd.Series()).astype(str).str.upper() != 'VISITA_FALLIDA'] if not tmp_hoy.empty else pd.DataFrame()

total_ruta    = len(clientes_ruta_hoy)
atendidos_hoy = ventas_reales_hoy['ClienteNombre'].nunique() if not ventas_reales_hoy.empty else 0
recaudo_hoy   = ventas_reales_hoy['Total'].sum() if not ventas_reales_hoy.empty else 0
unidades_hoy  = ventas_reales_hoy['Cantidad'].sum() if not ventas_reales_hoy.empty else 0
pct_avance    = int(atendidos_hoy / total_ruta * 100) if total_ruta > 0 else 0

b1, b2, b3, b4 = st.columns(4)
b1.metric("📍 Ruta hoy", f"{atendidos_hoy} / {total_ruta} clientes")
b2.metric("💰 Recaudo hoy", f"${recaudo_hoy:,.0f}")
b3.metric("📦 Unidades hoy", f"{int(unidades_hoy)}")
b4.metric("🎯 Avance", f"{pct_avance}%")

if total_ruta > 0:
    st.progress(pct_avance / 100, text=f"{pct_avance}% de la jornada completada")

st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════════
# PESTAÑAS
# ══════════════════════════════════════════════════════════════════════════════
tab_ruta, tab_tomar, tab_factura, tab_desempeno = st.tabs([
    "🗺️ Mi Ruta", "🛒 Tomar Pedido", "🧾 Facturas del Día", "📈 Mi Desempeño"
])

# ──────────────────────────────────────────────────────────────────────────────
# TAB RUTA
# ──────────────────────────────────────────────────────────────────────────────
with tab_ruta:
    st.markdown(f"### Clientes programados — **{dia_trabajo}**")

    if not clientes_ruta_hoy:
        st.info(f"No hay clientes en la ruta para el día {dia_trabajo}.")
    else:
        clientes_visitados_hoy = (
            ventas_reales_hoy['ClienteNombre'].unique()
            if not ventas_reales_hoy.empty else []
        )

        # ── Mapa Folium ──────────────────────────────────────────────────────
        if has_map:
            coords_ruta = []
            for cli in clientes_ruta_hoy:
                row = df_clientes[df_clientes['Nombre'] == cli]
                if not row.empty:
                    lat = pd.to_numeric(row.iloc[0].get('Latitud'), errors='coerce')
                    lon = pd.to_numeric(row.iloc[0].get('Longitud'), errors='coerce')
                    if pd.notna(lat) and pd.notna(lon):
                        coords_ruta.append((cli, lat, lon))

            if coords_ruta:
                center_lat = sum(c[1] for c in coords_ruta) / len(coords_ruta)
                center_lon = sum(c[2] for c in coords_ruta) / len(coords_ruta)
                m = folium.Map(location=[center_lat, center_lon], zoom_start=14)
                for i, (cli, lat, lon) in enumerate(coords_ruta):
                    visitado = cli in clientes_visitados_hoy
                    color    = "green" if visitado else "blue"
                    icon     = "check" if visitado else "info-sign"
                    folium.Marker(
                        [lat, lon],
                        popup=folium.Popup(f"<b>{i+1}. {cli}</b><br>{'✅ Atendido' if visitado else '⏳ Pendiente'}", max_width=200),
                        tooltip=f"{i+1}. {cli}",
                        icon=folium.Icon(color=color, icon=icon, prefix='glyphicon')
                    ).add_to(m)
                # Trazar ruta en orden
                if len(coords_ruta) >= 2:
                    folium.PolyLine(
                        [(c[1], c[2]) for c in coords_ruta],
                        color="#5932EA", weight=2.5, opacity=0.7, dash_array="8"
                    ).add_to(m)
                st_folium(m, height=380, use_container_width=True)
            else:
                st.info("Ningún cliente de tu ruta tiene coordenadas registradas.")

        # ── Lista de clientes ────────────────────────────────────────────────
        for idx, cli in enumerate(clientes_ruta_hoy):
            info_c = df_clientes[df_clientes['Nombre'] == cli]
            bar = info_c.iloc[0].get('Barrio', 'Sin barrio') if not info_c.empty else 'Sin barrio'
            ciu = info_c.iloc[0].get('Ciudad', 'Sahagún')   if not info_c.empty else 'Sahagún'
            tel = info_c.iloc[0].get('Telefono', '')         if not info_c.empty else ''

            detalle = f"{bar}, {ciu}"
            if tel:
                detalle += f" · 📞 {tel}"

            visitado = cli in clientes_visitados_hoy
            if visitado:
                st.markdown(f"""
                <div style="background:#f0fdf4; border:1px solid #86efac; border-left:4px solid #22c55e;
                            padding:12px 16px; border-radius:10px; margin-bottom:8px;">
                    <b style="color:#15803d;">{idx+1}. ✅ {cli}</b>
                    <span style="float:right; font-size:0.75rem; color:#16a34a; background:#dcfce7;
                                 padding:2px 8px; border-radius:12px;">ATENDIDO</span>
                    <br><span style="color:#4ade80; font-size:0.82rem;">{detalle}</span>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="background:#ffffff; border:1px solid #e5e7eb; border-left:4px solid #5932EA;
                            padding:12px 16px; border-radius:10px; margin-bottom:8px;">
                    <b style="color:#1a1a2e;">{idx+1}. 📍 {cli}</b>
                    <span style="float:right; font-size:0.75rem; color:#6b7280; background:#f3f4f6;
                                 padding:2px 8px; border-radius:12px;">PENDIENTE</span>
                    <br><span style="color:#6b7280; font-size:0.82rem;">{detalle}</span>
                </div>
                """, unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# TAB TOMAR PEDIDO
# ──────────────────────────────────────────────────────────────────────────────
with tab_tomar:
    st.subheader("Nuevo Pedido")

    if "cart" not in st.session_state:
        st.session_state.cart = []

    tipo_cli = st.radio(
        "Selección de cliente:",
        ["📋 De mi Ruta", "🔍 Buscar en base", "➕ Cliente Nuevo"],
        horizontal=True
    )

    cliente_sel = None
    barrio_nuevo = ""
    lat_nuevo, lon_nuevo = None, None

    if tipo_cli == "📋 De mi Ruta":
        if clientes_ruta_hoy:
            cliente_sel = st.selectbox("Cliente de la ruta:", [""] + clientes_ruta_hoy)
        else:
            st.warning("No hay clientes en tu ruta hoy. Usa 'Buscar en base'.")

    elif tipo_cli == "🔍 Buscar en base":
        todos = df_clientes['Nombre'].dropna().unique().tolist() if not df_clientes.empty else []
        otros = [c for c in todos if c not in clientes_ruta_hoy]
        cliente_sel = st.selectbox("Buscar cliente:", [""] + sorted(otros))

    elif tipo_cli == "➕ Cliente Nuevo":
        st.info("El cliente se registrará en la base maestra al confirmar el pedido.")
        raw = st.text_input("Nombre completo o Razón Social:")
        cliente_sel = raw.upper().strip() if raw else None
        barrio_nuevo = st.text_input("Barrio / Referencia de ubicación:")
        if has_map:
            st.markdown("**Toca el mapa para capturar las coordenadas GPS:**")
            m_new = folium.Map(location=[8.946, -75.442], zoom_start=14)
            m_new.add_child(folium.LatLngPopup())
            map_data = st_folium(m_new, height=320, use_container_width=True)
            if map_data and map_data.get("last_clicked"):
                lat_nuevo = map_data["last_clicked"]["lat"]
                lon_nuevo = map_data["last_clicked"]["lng"]
                st.success(f"GPS capturado: {lat_nuevo:.5f}, {lon_nuevo:.5f}")
        else:
            c_lat, c_lon = st.columns(2)
            lat_nuevo = c_lat.number_input("Latitud", format="%.6f")
            lon_nuevo = c_lon.number_input("Longitud", format="%.6f")

    # ── Geocerca 200 m ────────────────────────────────────────────────────────
    # Permite al preventista verificar que está fisicamente en el comercio.
    if cliente_sel and tipo_cli != "➕ Cliente Nuevo":
        cli_row = df_clientes[df_clientes['Nombre'] == cliente_sel]
        if not cli_row.empty:
            cli_lat = pd.to_numeric(cli_row.iloc[0].get('Latitud'), errors='coerce')
            cli_lon = pd.to_numeric(cli_row.iloc[0].get('Longitud'), errors='coerce')
            if pd.notna(cli_lat) and pd.notna(cli_lon) and has_map:
                with st.expander("📍 Verificar mi ubicación (geocerca 200 m)", expanded=False):
                    st.markdown("Toca tu posición actual en el mapa para verificar que estás en el comercio.")
                    m_geo = folium.Map(location=[cli_lat, cli_lon], zoom_start=16)
                    folium.Marker(
                        [cli_lat, cli_lon],
                        tooltip=cliente_sel,
                        icon=folium.Icon(color='red', icon='home', prefix='glyphicon')
                    ).add_to(m_geo)
                    folium.Circle([cli_lat, cli_lon], radius=200, color="#5932EA", fill=True, fill_opacity=0.12).add_to(m_geo)
                    m_geo.add_child(folium.LatLngPopup())
                    geo_data = st_folium(m_geo, height=300, use_container_width=True, key="geocerca_map")
                    if geo_data and geo_data.get("last_clicked"):
                        user_lat = geo_data["last_clicked"]["lat"]
                        user_lon = geo_data["last_clicked"]["lng"]

                        def haversine_m(la1, lo1, la2, lo2):
                            R = 6_371_000
                            φ1, φ2 = math.radians(la1), math.radians(la2)
                            dφ = math.radians(la2 - la1)
                            dλ = math.radians(lo2 - lo1)
                            a = math.sin(dφ/2)**2 + math.cos(φ1)*math.cos(φ2)*math.sin(dλ/2)**2
                            return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

                        dist = haversine_m(user_lat, user_lon, cli_lat, cli_lon)
                        if dist <= 200:
                            st.success(f"✅ Dentro del radio de cobertura ({dist:.0f} m). ¡Puedes registrar el pedido!")
                        else:
                            st.warning(f"⚠️ Estás a {dist:.0f} m del comercio (radio 200 m). Verifica que estés en el lugar correcto.")

    # ── CRM: sugerencias e historial ─────────────────────────────────────────
    if cliente_sel and tipo_cli != "➕ Cliente Nuevo":
        hist_cli = df_compras[df_compras['ClienteNombre'] == cliente_sel]
        if not hist_cli.empty:
            favs = (
                hist_cli[hist_cli['Cantidad'] > 0]['Producto']
                .value_counts().head(3).index.tolist()
            )
            en_carrito = [item['Producto'] for item in st.session_state.cart]
            sugerencias = [f for f in favs if f not in en_carrito]
            if sugerencias:
                st.info(f"🧠 **Sugerido para este cliente:** {', '.join(sugerencias)}")

        with st.expander("❌ ¿No facturará hoy? (Registrar visita fallida)"):
            motivo = st.selectbox("Motivo:", [
                "", "Local cerrado", "Cerrado permanentemente", "Aún tiene inventario",
                "Sin efectivo", "No está el encargado", "Compró a la competencia", "Queja del servicio"
            ], key="motivo_falla")
            if st.button("Guardar visita sin venta", type="secondary"):
                if motivo:
                    from random import randint
                    ts = datetime.now()
                    c_cod = hist_cli.iloc[0]['ClienteCodigo'] if not hist_cli.empty else "N/A"
                    n_fallo = f"FAIL-{vend_code[:2]}-{ts.strftime('%H%M')}-{randint(10,99)}"
                    fila = [{
                        "NoPedido": n_fallo, "Fecha": ts.strftime('%Y-%m-%d %H:%M:%S'),
                        "ClienteCodigo": str(c_cod), "ClienteNombre": cliente_sel,
                        "Barrio": "", "Ciudad": "", "Ruta": dia_trabajo,
                        "CodigoVendedor": vend_code, "Vendedor": vend_actual,
                        "CodigoProducto": "NO_COMPRA", "Producto": f"MOTIVO: {motivo}",
                        "Cantidad": 0, "PrecioBase": 0.0, "Total": 0.0,
                        "MetodoPago": "N/A", "Abono": 0, "Estado": "VISITA_FALLIDA", "PctDescuento": 0.0
                    }]
                    safe_append_rows(fila, COMPRAS_PATH, dedup_cols=["NoPedido", "CodigoProducto"])
                    st.success(f"Motivo '{motivo}' registrado. ¡Al siguiente!")
                    st.session_state.cart = []
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("Selecciona un motivo válido.")

    st.markdown("---")

    # ── Promociones activas ───────────────────────────────────────────────────
    promos_hoy = get_active_promos()
    if promos_hoy:
        st.markdown("### 🎯 Promociones del día")
        for p in promos_hoy:
            if p["tipo"] == "bundle":
                precio_norm = sum(x["cantidad"] * x.get("precio_base", 0) for x in p["productos"])
                ahorro = precio_norm - p["precio_especial"]
                pct_aho = ahorro / precio_norm * 100 if precio_norm > 0 else 0
                prods_str = " + ".join(f"{x['cantidad']}× {x['nombre']}" for x in p["productos"])
                st.markdown(f"""
                <div style="background:#faf5ff; border:1px solid #a78bfa; border-left:4px solid #7c3aed;
                            border-radius:10px; padding:12px 16px; margin-bottom:6px;">
                    <b style="color:#6d28d9;">🎁 {p['nombre']}</b>
                    &nbsp;<span style="font-size:0.75rem; background:#ede9fe; color:#7c3aed;
                                       padding:2px 8px; border-radius:10px;">COMBO</span><br>
                    <span style="font-size:0.82rem; color:#6b7280;">{p.get('descripcion','')}</span><br>
                    <span style="font-size:0.82rem; color:#374151;">{prods_str}</span><br>
                    <span style="color:#6d28d9; font-weight:600;">
                        💰 ${p['precio_especial']:,.0f}
                        <span style="text-decoration:line-through; color:#9ca3af; font-weight:400;
                                     font-size:0.85rem;"> ${precio_norm:,.0f} </span>
                        — ahorra ${ahorro:,.0f} ({pct_aho:.0f}%)
                    </span>
                </div>
                """, unsafe_allow_html=True)
                if st.button(f"🎁 Agregar combo: {p['nombre']}", key=f"bundle_{p['id']}", use_container_width=False):
                    if not cliente_sel:
                        st.error("Selecciona un cliente antes de agregar el combo.")
                    else:
                        if st.session_state.get("cliente_en_curso", "") != cliente_sel:
                            st.session_state.cart = []
                            st.session_state.cliente_en_curso = cliente_sel
                        items = bundle_to_cart_items(p, df_productos)
                        st.session_state.cart.extend(items)
                        st.success(f"✓ Combo '{p['nombre']}' agregado al pedido.")
                        st.rerun()

            else:
                prod = p["productos"][0] if p["productos"] else {}
                pb = prod.get("precio_base", 0)
                pct = p.get("descuento_pct", 0)
                precio_desc = pb * (1 - pct / 100)
                st.markdown(f"""
                <div style="background:#fff7ed; border:1px solid #fb923c; border-left:4px solid #ea580c;
                            border-radius:10px; padding:12px 16px; margin-bottom:6px;">
                    <b style="color:#c2410c;">🏷️ {p['nombre']}</b>
                    &nbsp;<span style="font-size:0.75rem; background:#ffedd5; color:#ea580c;
                                       padding:2px 8px; border-radius:10px;">{pct:.0f}% OFF</span><br>
                    <span style="font-size:0.82rem; color:#6b7280;">{p.get('descripcion','')}</span><br>
                    <span style="color:#c2410c; font-weight:600;">
                        {prod.get('nombre','')}
                        &nbsp;<span style="text-decoration:line-through; color:#9ca3af; font-weight:400;"> ${pb:,.0f} </span>
                        → <b>${precio_desc:,.0f}</b>
                    </span>
                </div>
                """, unsafe_allow_html=True)
                c_qty_d, c_btn_d, _ = st.columns([1, 2, 3])
                qty_desc = c_qty_d.number_input("Cant.:", min_value=1, value=1, step=1, key=f"qty_desc_{p['id']}", label_visibility="collapsed")
                if c_btn_d.button(f"🏷️ Agregar {pct:.0f}% OFF", key=f"desc_{p['id']}", use_container_width=True):
                    if not cliente_sel:
                        st.error("Selecciona un cliente antes de agregar la promo.")
                    else:
                        if st.session_state.get("cliente_en_curso", "") != cliente_sel:
                            st.session_state.cart = []
                            st.session_state.cliente_en_curso = cliente_sel
                        item = descuento_to_cart_item(p, qty_desc, df_productos)
                        if item:
                            st.session_state.cart.append(item)
                            st.success(f"✓ {qty_desc}× {prod.get('nombre','')} con {pct:.0f}% OFF agregados.")
                            st.rerun()

        st.markdown("---")

    # ── Catálogo de productos ─────────────────────────────────────────────────
    st.markdown("### Agregar productos al pedido")
    df_act = df_productos.copy()
    if 'Activo' in df_act.columns:
        df_act = df_act[df_act['Activo'] == 1]

    if df_act.empty:
        st.warning("No hay productos activos en el catálogo.")
    else:
        df_act['InfoBusqueda'] = (
            df_act['Codigo'].astype(str) + " | " +
            df_act['Nombre'].astype(str) + " | $" +
            df_act['PrecioBase'].fillna(0).astype(int).astype(str) +
            " | Disp: " + df_act['StockDisponible'].fillna(0).astype(int).astype(str)
        )
        lista_prods = df_act['InfoBusqueda'].dropna().unique().tolist()

        c_p1, c_p2, c_p3 = st.columns([3, 1, 1.5])
        with c_p1:
            prod_sel_info = st.selectbox("Producto (escribe nombre o código):", [""] + sorted(lista_prods))
        with c_p2:
            cantidad = st.number_input("Unidades:", min_value=1, value=1, step=1)
        with c_p3:
            if prod_sel_info:
                p_nombre = prod_sel_info.split(" | ")[1]
                p_info   = df_act[df_act['Nombre'] == p_nombre].iloc[0]
                stock_d  = int(p_info.get('StockDisponible', 0))
                subt     = float(p_info['PrecioBase']) * cantidad
                color_box = "#fff7ed" if cantidad > stock_d else "#f0fdf4"
                border_c  = "#f97316" if cantidad > stock_d else "#22c55e"
                text_c    = "#c2410c" if cantidad > stock_d else "#15803d"
                msg       = f"⚠️ Máx {stock_d}" if cantidad > stock_d else f"+ ${subt:,.0f}"
                st.markdown(
                    f"<div style='margin-top:28px; padding:10px; background:{color_box}; "
                    f"border:1px solid {border_c}; border-radius:10px; text-align:center;'>"
                    f"<b style='color:{text_c}; font-size:1.1rem;'>{msg}</b></div>",
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    "<div style='margin-top:28px; padding:10px; color:#9ca3af; "
                    "text-align:center; border:1px dashed #d1d5db; border-radius:10px;'>$0</div>",
                    unsafe_allow_html=True
                )

        _, c_btn, _ = st.columns([1, 2, 1])
        with c_btn:
            if st.button("➕ Agregar al pedido", use_container_width=True):
                if not cliente_sel:
                    st.error("Selecciona un cliente primero.")
                elif not prod_sel_info:
                    st.error("Selecciona un producto.")
                else:
                    if st.session_state.get('cliente_en_curso', '') != cliente_sel:
                        st.session_state.cart = []
                        st.session_state.cliente_en_curso = cliente_sel
                    p_nombre = prod_sel_info.split(" | ")[1]
                    p_info   = df_act[df_act['Nombre'] == p_nombre].iloc[0]
                    stock_d  = int(p_info.get('StockDisponible', 0))
                    if cantidad > stock_d:
                        st.error(f"Stock disponible insuficiente: solo quedan {stock_d} unidades libres.")
                    else:
                        st.session_state.cart.append({
                            "Producto":       p_nombre,
                            "CodigoProducto": p_info['Codigo'],
                            "Cantidad":       cantidad,
                            "PrecioBase":     float(p_info['PrecioBase']),
                            "Total":          float(p_info['PrecioBase']) * cantidad
                        })
                        st.success(f"✓ {cantidad}× {p_nombre} agregados.")

    # ── Carrito ───────────────────────────────────────────────────────────────
    if st.session_state.cart:
        st.markdown("---")
        df_cart  = pd.DataFrame(st.session_state.cart)
        total_p  = df_cart['Total'].sum()
        st.dataframe(df_cart[['Producto', 'Cantidad', 'PrecioBase', 'Total']], use_container_width=True, hide_index=True)
        st.markdown(f"<h3 style='text-align:right;'>Total: <b>${total_p:,.0f}</b></h3>", unsafe_allow_html=True)

        st.markdown("### 💳 Recaudo y cierre")
        cp1, cp2 = st.columns(2)
        with cp1:
            metodo_pago = st.selectbox("Forma de pago:", [
                "EFECTIVO CONTADO", "TRANSFERENCIA", "CREDITO (Para luego)", "ABONO PARCIAL / MIXTO"
            ])
        with cp2:
            if metodo_pago == "CREDITO (Para luego)":
                abono = st.number_input("Abono recibido:", value=0.0, min_value=0.0, max_value=float(total_p))
            elif metodo_pago == "ABONO PARCIAL / MIXTO":
                abono = st.number_input("Abono recibido:", value=float(total_p / 2), min_value=0.0)
            else:
                abono = st.number_input("Valor recibido:", value=float(total_p), min_value=0.0)

        saldo = total_p - abono
        if saldo > 0:
            st.warning(f"⚠️ Saldo en cartera: **${saldo:,.0f}**")
        elif saldo < 0:
            st.info(f"🔄 Vuelto a dar: **${abs(saldo):,.0f}**")
            abono = total_p
        else:
            st.success("✅ Pago completo.")

        c_conf, c_vac = st.columns([2, 1])
        with c_vac:
            if st.button("🗑️ Vaciar", use_container_width=True):
                st.session_state.cart = []
                st.rerun()
        with c_conf:
            if st.button("✅ Confirmar y Guardar Pedido", type="primary", use_container_width=True):
                from random import randint
                ts    = datetime.now()
                n_ped = f"P-{vend_code[:2]}-{ts.strftime('%H%M')}-{randint(10,99)}"

                # Datos del cliente
                c_cod, ciudad = "NUEVO", "SAHAGUN"
                if tipo_cli == "➕ Cliente Nuevo" and cliente_sel:
                    c_cod = f"C-{randint(1000, 9999)}"
                    # Registrar ubicación
                    nueva_ubi = {"Cliente": cliente_sel, "Barrio": barrio_nuevo,
                                 "DiaVisita": dia_trabajo, "Ruta": dia_trabajo,
                                 "Latitud": lat_nuevo, "Longitud": lon_nuevo,
                                 "NOMBRE_NORM": cliente_sel.upper()}
                    df_ubi_bd = pd.read_json(UBICACIONES_PATH) if UBICACIONES_PATH.exists() else pd.DataFrame()
                    safe_write_json(pd.concat([df_ubi_bd, pd.DataFrame([nueva_ubi])], ignore_index=True), UBICACIONES_PATH)
                    # Registrar cliente maestro
                    nuevo_cli = {"Activo": 1, "Codigo": c_cod, "Nombre": cliente_sel,
                                 "Barrio": barrio_nuevo, "Ciudad": ciudad,
                                 "Latitud": lat_nuevo, "Longitud": lon_nuevo}
                    df_cli_bd = pd.read_json(CLIENTES_PATH) if CLIENTES_PATH.exists() else pd.DataFrame()
                    safe_write_json(pd.concat([df_cli_bd, pd.DataFrame([nuevo_cli])], ignore_index=True), CLIENTES_PATH)

                elif tipo_cli in ["📋 De mi Ruta", "🔍 Buscar en base"]:
                    cx = df_clientes[df_clientes['Nombre'] == cliente_sel]
                    if not cx.empty:
                        c_cod        = cx.iloc[0].get('Codigo', "N/A")
                        barrio_nuevo = cx.iloc[0].get('Barrio', "")
                        ciudad       = cx.iloc[0].get('Ciudad', "SAHAGUN")
                        lat_nuevo    = cx.iloc[0].get('Latitud', None)
                        lon_nuevo    = cx.iloc[0].get('Longitud', None)

                # Guardar líneas del pedido con Estado="ASIGNADO"
                # (el stock físico solo baja al despacho — no se toca productos.json aquí)
                f_str = ts.strftime('%Y-%m-%d %H:%M:%S')
                filas = []
                for it in st.session_state.cart:
                    filas.append({
                        "NoPedido": n_ped, "Fecha": f_str,
                        "ClienteCodigo": str(c_cod), "ClienteNombre": cliente_sel,
                        "Barrio": str(barrio_nuevo), "Ciudad": str(ciudad),
                        "Ruta": dia_trabajo, "CodigoVendedor": vend_code,
                        "Vendedor": vend_actual, "CodigoProducto": str(it["CodigoProducto"]),
                        "Producto": it["Producto"], "Cantidad": it["Cantidad"],
                        "PrecioBase": it["PrecioBase"], "Total": it["Total"],
                        "MetodoPago": metodo_pago, "Abono": float(abono),
                        "Estado": "ASIGNADO", "PctDescuento": it.get("PctDescuento", 0.0),
                        "PromoID": it.get("PromoID", ""), "PromoNombre": it.get("PromoNombre", "")
                    })

                safe_append_rows(filas, COMPRAS_PATH, dedup_cols=["NoPedido", "CodigoProducto"])

                st.session_state.last_invoice = {
                    "no_pedido": n_ped, "fecha": f_str, "cliente": cliente_sel,
                    "barrio": barrio_nuevo, "lat": lat_nuevo, "lon": lon_nuevo,
                    "total": total_p, "df": df_cart,
                    "metodo_pago": metodo_pago, "abono": abono, "saldo": max(0, saldo)
                }
                st.session_state.cart = []
                st.session_state.cliente_en_curso = ""
                st.cache_data.clear()
                st.rerun()

# ──────────────────────────────────────────────────────────────────────────────
# TAB FACTURAS DEL DÍA
# ──────────────────────────────────────────────────────────────────────────────
with tab_factura:
    st.subheader("Facturas del día")
    facturas_hoy = (
        df_mis_pedidos[df_mis_pedidos['Fecha'].astype(str).str.startswith(hoy_puro, na=False)]
        if not df_mis_pedidos.empty else pd.DataFrame()
    )

    if facturas_hoy.empty:
        st.info("No has emitido facturas en el turno de hoy.")
    else:
        resumen_fac = (
            facturas_hoy.groupby('NoPedido')
            .agg(Fecha=('Fecha', 'first'), ClienteNombre=('ClienteNombre', 'first'), Total=('Total', 'sum'))
            .reset_index()
            .sort_values('Fecha', ascending=False)
        )
        lista_ops = resumen_fac.apply(
            lambda r: f"{r['NoPedido']} | {r['ClienteNombre']} | ${r['Total']:,.0f}", axis=1
        ).tolist()

        idx_def = 0
        if st.session_state.get("last_invoice"):
            last_id = st.session_state.last_invoice['no_pedido']
            matches = [i for i, x in enumerate(lista_ops) if last_id in x]
            if matches:
                idx_def = matches[0]

        fac_sel_desc = st.selectbox("Seleccionar factura:", lista_ops, index=idx_def)
        fac_id       = fac_sel_desc.split(" | ")[0]
        fac_df       = facturas_hoy[facturas_hoy['NoPedido'] == fac_id].copy()

        fac_fecha   = fac_df.iloc[0]['Fecha']
        fac_cliente = fac_df.iloc[0]['ClienteNombre']
        fac_barrio  = fac_df.iloc[0].get('Barrio', 'N/A')
        fac_total   = fac_df['Total'].sum()
        fac_abono   = fac_df.iloc[0].get('Abono', fac_total)
        fac_metodo  = fac_df.iloc[0].get('MetodoPago', 'ACORDADO')
        fac_saldo   = max(0, fac_total - fac_abono)

        c_i1, c_i2 = st.columns([2, 1])
        with c_i1:
            st.markdown(f"""
            <div style="background:#f8f9ff; border:1px solid #e5e7eb; border-radius:10px; padding:16px;">
                <b style="color:#5932EA;">LA CAMPIÑA — PREVENTA</b><br>
                <span style="font-size:0.88rem;">
                    📋 <b>Factura:</b> {fac_id}<br>
                    📅 <b>Fecha:</b> {fac_fecha}<br>
                    👤 <b>Cliente:</b> {fac_cliente}<br>
                    📍 <b>Barrio:</b> {fac_barrio}<br>
                    💳 <b>Pago:</b> {fac_metodo}
                </span>
            </div>
            """, unsafe_allow_html=True)
        with c_i2:
            st.metric("Total", f"${fac_total:,.0f}")
            if fac_saldo > 0:
                st.metric("Saldo pendiente", f"${fac_saldo:,.0f}")

        st.dataframe(fac_df[['Producto', 'Cantidad', 'PrecioBase', 'Total']], use_container_width=True, hide_index=True)
        st.markdown("---")

        # WhatsApp
        texto_wa = (
            f"📋 *PEDIDO:* {fac_id}\n🗓 *Fecha:* {fac_fecha}\n"
            f"👤 *Cliente:* {fac_cliente}\n💳 *Pago:* {fac_metodo}\n──────────────\n"
        )
        for _, row in fac_df.iterrows():
            texto_wa += f"• {row['Cantidad']} und — {row['Producto']} → ${row['Total']:,.0f}\n"
        texto_wa += f"──────────────\n💰 *TOTAL:* ${fac_total:,.0f}\n"
        if fac_saldo > 0:
            texto_wa += f"⚠️ *SALDO:* ${fac_saldo:,.0f}\n"
        texto_wa += "¡Gracias! ~ La Campiña 🌿"

        link_wa = f"https://wa.me/?text={quote(texto_wa)}"

        HTML_TICKET = f'''<!DOCTYPE html><html><head><style>
        body{{background:transparent;color:#111;display:flex;justify-content:center;padding:10px;margin:0;font-family:sans-serif;}}
        .print-btn{{cursor:pointer;background:#5932EA;border:none;color:white;font-weight:bold;width:100%;border-radius:8px;padding:14px;font-size:15px;margin-bottom:16px;}}
        .ticket{{background:white;color:black;font-family:'Courier New',Courier,monospace;width:80mm;padding:5mm;margin:0 auto;box-sizing:border-box;}}
        table{{width:100%;border-collapse:collapse;font-size:12px;}}
        th,td{{border-bottom:1px dashed #ccc;padding:4px 0;}}
        .right{{text-align:right;}}.center{{text-align:center;}}.bold{{font-weight:bold;}}
        hr{{border:none;border-top:1px dashed black;margin:8px 0;}}
        @media print{{body{{background:white;padding:0;margin:0;display:block;}}.no-print{{display:none;}}}}
        </style></head><body>
        <div style="width:100%;max-width:80mm;display:flex;flex-direction:column;">
        <button class="no-print print-btn" onclick="window.print()">🖨️ Imprimir (Térmica POS)</button>
        <div class="ticket">
        <div class="center"><h2 style="margin:0;font-size:16px;">DISTRIBUIDORA LA CAMPIÑA</h2>
        <p style="margin:2px 0;font-size:11px;">Sahagún, Córdoba</p></div>
        <hr>
        <div style="font-size:11px;margin-bottom:8px;">
        <p style="margin:2px 0;"><b>Factura:</b> {fac_id}</p>
        <p style="margin:2px 0;"><b>Fecha:</b> {fac_fecha}</p>
        <p style="margin:2px 0;"><b>Vendedor:</b> {vend_actual}</p>
        <p style="margin:2px 0;"><b>Cliente:</b> {fac_cliente}</p>
        <p style="margin:2px 0;"><b>Pago:</b> {fac_metodo}</p>
        </div><hr>
        <table><tr class="bold"><th>CANT</th><th>DESC</th><th class="right">VALOR</th></tr>'''
        for _, r in fac_df.iterrows():
            HTML_TICKET += f"<tr><td>{r['Cantidad']}</td><td>{str(r['Producto'])[:14]}</td><td class='right'>${r['Total']:,.0f}</td></tr>"
        HTML_TICKET += f'''</table><hr>
        <h3 class="right" style="margin:5px 0;">TOTAL: ${fac_total:,.0f}</h3>
        <h4 class="right" style="margin:5px 0;">ABONO: ${fac_abono:,.0f}</h4>
        <h4 class="right" style="margin:5px 0;color:#555;">SALDO: ${fac_saldo:,.0f}</h4>
        <hr><p class="center" style="font-size:11px;margin-top:16px;">*** OBLIGACION DE PAGO ***</p>
        <p class="center" style="font-size:11px;">¡GRACIAS POR SU COMPRA!</p>
        </div></div></body></html>'''

        c_wa, c_tick = st.columns(2)
        with c_wa:
            st.markdown(
                f"<a href='{link_wa}' target='_blank'>"
                f"<button style='width:100%;border-radius:10px;font-weight:bold;"
                f"background:#25D366;color:white;border:none;padding:12px;cursor:pointer;'>"
                f"📲 Compartir por WhatsApp</button></a>",
                unsafe_allow_html=True
            )
        with c_tick:
            st.components.v1.html(HTML_TICKET, height=450, scrolling=True)

# ──────────────────────────────────────────────────────────────────────────────
# TAB DESEMPEÑO
# ──────────────────────────────────────────────────────────────────────────────
with tab_desempeno:
    st.subheader("Mis indicadores")

    if df_mis_pedidos.empty:
        st.info("Sin registros acumulados para este preventista.")
    else:
        df_mis = df_mis_pedidos.copy()
        df_mis['Fecha_DT'] = pd.to_datetime(df_mis['Fecha'], errors='coerce')
        ventas_r = df_mis[df_mis['Estado'].astype(str).str.upper() != 'VISITA_FALLIDA']

        hace7 = (datetime.now() - pd.Timedelta(days=7)).strftime('%Y-%m-%d')

        hoy_ventas  = ventas_r[ventas_r['Fecha_DT'].dt.date.astype(str) == hoy_puro]
        hace7_ventas = ventas_r[ventas_r['Fecha_DT'].dt.date.astype(str) == hace7]

        ttl_hoy = hoy_ventas['Total'].sum()
        und_hoy = hoy_ventas['Cantidad'].sum()
        ttl_h7  = hace7_ventas['Total'].sum()
        und_h7  = hace7_ventas['Cantidad'].sum()

        m1, m2 = st.columns(2)
        m1.metric("Venta bruta hoy", f"${ttl_hoy:,.0f}", f"${ttl_hoy - ttl_h7:,.0f} vs hace 7 días")
        m2.metric("Unidades facturadas hoy", f"{int(und_hoy)}", f"{int(und_hoy - und_h7)} unds. vs hace 7 días")

        st.markdown("---")

        hoy_todas = df_mis[df_mis['Fecha_DT'].dt.date.astype(str) == hoy_puro]
        if not hoy_todas.empty:
            tocados  = hoy_todas['ClienteNombre'].nunique()
            facturados = hoy_ventas['ClienteNombre'].nunique()
            hit_rate = facturados / tocados * 100 if tocados > 0 else 0
            drop_size = ttl_hoy / facturados if facturados > 0 else 0

            m3, m4 = st.columns(2)
            m3.metric("Hit Rate (efectividad)", f"{hit_rate:.1f}%", f"{facturados} de {tocados} visitados")
            m4.metric("Drop Size (ticket de calle)", f"${drop_size:,.0f}")
        else:
            st.info("La jornada no ha iniciado. Toma un pedido para ver los indicadores.")

        st.markdown("---")
        st.metric("Cartera histórica acumulada", f"${ventas_r['Total'].sum():,.0f}")
