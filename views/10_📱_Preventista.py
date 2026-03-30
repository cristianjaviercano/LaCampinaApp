import streamlit as st
import pandas as pd
from datetime import datetime
import json
from pathlib import Path
from urllib.parse import quote
from utils.data_loader import load_data

# Intentar cargar mapa, si no está disponible hacer fallback
try:
    import folium
    from streamlit_folium import st_folium
    has_map = True
except ImportError:
    has_map = False

st.set_page_config(page_title="Módulo Preventista", page_icon="📱", layout="wide")
st.title("📱 Terminal del Preventista")

# === 1. Sesión y Datos ===
user_info = st.session_state.get('user_info', {})
vend_code = user_info.get('username', 'Desconocido').upper()
vend_actual = user_info.get('name', vend_code).upper()
role = user_info.get('role', 'PREVENTISTA')

if role in ["ADMINISTRADOR", "DUEÑO"]:
    vend_input = st.selectbox("Simulador Global de Preventista:", ["DAIFER GENEY", "JUNIOR MARQUEZ", "JOSE PEREZ"])
    if vend_input.strip():
        vend_actual = vend_input.strip().upper()

st.markdown(f"🛡️ **Operador:** `{vend_actual}`")

BASE_DIR = Path(__file__).resolve().parent.parent
MAESTROS_DIR = BASE_DIR / "datos_maestros"
COMPRAS_PATH = MAESTROS_DIR / "compras_maestras.json"
UBICACIONES_PATH = MAESTROS_DIR / "ubicaciones.json"
CLIENTES_PATH = MAESTROS_DIR / "clientes_maestro.json"

data = load_data()
if not data:
    st.error("Error al cargar la base de datos.")
    st.stop()

df_clientes = data['clientes'].copy()
df_productos = data['productos'].copy()
df_compras = data['compras_detalle'].copy()

# === 2. Configuración de la Jornada ===
st.markdown("---")
dias_map = {"LUNES": 0, "MARTES": 1, "MIERCOLES": 2, "JUEVES": 3, "VIERNES": 4, "SABADO": 5, "DOMINGO": 6}
inv_dias_map = {v: k for k, v in dias_map.items()}
hoy_num = datetime.now().weekday()
hoy_str = inv_dias_map.get(hoy_num, "LUNES")

col1, col2 = st.columns([1, 2])
with col1:
    dia_trabajo = st.selectbox("🗓️ **Planifica tu jornada seleccionando el día:**", list(dias_map.keys()), index=list(dias_map.keys()).index(hoy_str))

with col2:
    st.markdown("<br><span style='color: gray; font-size: 0.9em;'>Al cambiar de día, el sistema cargará tu ruta y el orden de tiendas asignadas automáticamente.</span>", unsafe_allow_html=True)

# Procesar la ruta (Mejora Geoespacial - Algoritmo TSP)
clientes_ruta_hoy = []
df_mis_pedidos = df_compras[df_compras['Vendedor'].astype(str).str.upper() == vend_actual].copy() if not df_compras.empty else pd.DataFrame()

# 1. Obtener matriz de clientes programados para hoy (Historial Operativo + Plantilla de Ubicaciones)
c_hist = []
if not df_mis_pedidos.empty:
    df_mis_pedidos['Fecha_DT'] = pd.to_datetime(df_mis_pedidos['Fecha'], errors='coerce')
    df_mis_pedidos['DiaSem'] = df_mis_pedidos['Fecha_DT'].dt.weekday.map(inv_dias_map)
    c_hist = df_mis_pedidos[df_mis_pedidos['DiaSem'] == dia_trabajo]['ClienteNombre'].unique().tolist()

c_ubi = []
if UBICACIONES_PATH.exists():
    df_ubi = pd.read_json(UBICACIONES_PATH)
    if not df_ubi.empty and 'Ruta' in df_ubi.columns:
        c_ubi = df_ubi[df_ubi['Ruta'].astype(str).str.upper() == dia_trabajo.upper()]['Cliente'].dropna().unique().tolist()

clientes_uni = list(set(c_hist + c_ubi))

# 2. Trazar la ruta algoritmica (Ruta más corta)
if len(clientes_uni) > 0:
    df_rutas_geo = pd.DataFrame({'ClienteNombre': clientes_uni})
    df_rutas_geo = pd.merge(df_rutas_geo, df_clientes[['Nombre', 'Latitud', 'Longitud']], left_on='ClienteNombre', right_on='Nombre', how='left')
    df_rutas_geo['Latitud'] = pd.to_numeric(df_rutas_geo['Latitud'], errors='coerce')
    df_rutas_geo['Longitud'] = pd.to_numeric(df_rutas_geo['Longitud'], errors='coerce')
    
    validos = df_rutas_geo.dropna(subset=['Latitud', 'Longitud']).reset_index(drop=True)
    invalidos = df_rutas_geo[df_rutas_geo['Latitud'].isna() | df_rutas_geo['Longitud'].isna()]['ClienteNombre'].tolist()
    
    if len(validos) >= 2:
        from utils.routing import nearest_neighbor_tsp
        # El algoritmo evaluará todas las coordenadas y determinará el camino TSP óptimo (A*)
        orden = nearest_neighbor_tsp(validos[['Latitud', 'Longitud']], use_streets=True)
        clientes_ruta_hoy = [validos.iloc[i]['ClienteNombre'] for i in orden]
    else:
        clientes_ruta_hoy = validos['ClienteNombre'].tolist()
        
    clientes_ruta_hoy.extend(invalidos) # Añadir comercios sin coordenada al final de la cola

# === 3. Pestañas de Interfaz ===
st.markdown("---")
tab_ruta, tab_tomar, tab_factura, tab_desempeno = st.tabs([
    "🗺️ Mi Ruta Hoy", "🛒 Toma de Pedido", "🧾 Facturación Local", "📈 Desempeño"
])

# ----- Pestaña Ruta -----
with tab_ruta:
    if len(clientes_ruta_hoy) == 0:
        st.info(f"Hoja de ruta vacía para el día {dia_trabajo}.")
    else:
        st.markdown(f"### 📍 Clientes proyectados para el **{dia_trabajo}**")
        st.write("Control visual de la jornada (Los marcadores cambiarán a verde tras facturar):")
        
        # Obtener clientes que ya atendio hoy localmente (basado en df_mis_pedidos)
        hoy_puro_str = datetime.now().strftime('%Y-%m-%d')
        clientes_visitados_hoy = df_mis_pedidos[df_mis_pedidos['Fecha'].astype(str).str.startswith(hoy_puro_str, na=False)]['ClienteNombre'].unique()
        
        for idx, cli in enumerate(clientes_ruta_hoy):
            info_c = df_clientes[df_clientes['Nombre'] == cli]
            bar = info_c.iloc[0].get('Barrio', 'No registrado') if not info_c.empty else 'No registrado'
            ciu = info_c.iloc[0].get('Ciudad', 'Sahagún') if not info_c.empty else 'Sahagún'
            dir = info_c.iloc[0].get('Direccion', '') if not info_c.empty else ''
            tel = info_c.iloc[0].get('Telefono', '') if not info_c.empty else ''
            
            detalles_extra = f"{bar}, {ciu}"
            if dir: detalles_extra += f" | {dir}"
            if tel: detalles_extra += f" | 📞 {tel}"
            
            if cli in clientes_visitados_hoy:
                st.markdown(f"""
                <div style="background-color: #064e3b; border: 1px solid #059669; padding: 12px; border-radius: 12px; margin-bottom: 10px;">
                    <h4 style="margin:0; color: #a7f3d0;">{idx+1}. ✅ {cli} <span style="font-size: 0.7em; float: right; color:#6ee7b7; border: 1px solid #34d399; padding: 2px 6px; border-radius: 4px;">ATENDIDO HOY</span></h4>
                    <p style="margin:2px 0 0 0; font-size: 0.85em; color: #ecfdf5;">{detalles_extra}</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="background-color: #0A1B7F; border: 1px solid #132488; padding: 12px; border-radius: 12px; margin-bottom: 10px;">
                    <h4 style="margin:0; color: white;">{idx+1}. 📍 {cli} <span style="font-size: 0.7em; float: right; color:#a1a1aa;">PENDIENTE</span></h4>
                    <p style="margin:2px 0 0 0; font-size: 0.85em; color: #d4d4d8;">{detalles_extra}</p>
                </div>
                """, unsafe_allow_html=True)

# ----- Pestaña Toma de Pedido -----
with tab_tomar:
    st.subheader("🛒 Ingreso de Pedido Venta")
    
    if "cart" not in st.session_state:
        st.session_state.cart = []
        
    tipo_cli = st.radio("Método de Selección de Cliente:", ["📋 De mi Ruta", "🔍 Buscar en General", "➕ Cliente Nuevo Esporádico"], horizontal=True)
    
    cliente_sel = None
    barrio_nuevo = ""
    lat_nuevo, lon_nuevo = None, None
    
    if tipo_cli == "📋 De mi Ruta":
        if len(clientes_ruta_hoy) > 0:
            cliente_sel = st.selectbox("Seleccionar (Ordenado por frecuencia):", [""] + clientes_ruta_hoy)
        else:
            st.warning("No tienes clientes en la ruta de hoy. Cambia el método de selección.")
            
    elif tipo_cli == "🔍 Buscar en General":
        todos_clientes = []
        if not df_clientes.empty:
            todos_clientes = df_clientes['Nombre'].dropna().unique().tolist()
        otros_clientes = [c for c in todos_clientes if c not in clientes_ruta_hoy]
        cliente_sel = st.selectbox("Busca el comercio o nombre del cliente:", [""] + otros_clientes)
        
    elif tipo_cli == "➕ Cliente Nuevo Esporádico":
        st.info("Crearás una cuenta nueva de cliente en el sistema maestro de La Campiña.")
        cliente_sel_raw = st.text_input("Nombre Completo o Razón Social:")
        cliente_sel = cliente_sel_raw.upper().strip() if cliente_sel_raw else None
        barrio_nuevo = st.text_input("Barrio o Referencia:")
        
        if has_map:
            st.markdown("**📍 Toca el mapa para capturar las coordenadas de GPS exactas:**")
            m = folium.Map(location=[8.946, -75.442], zoom_start=14)
            m.add_child(folium.LatLngPopup())
            map_data = st_folium(m, height=350, width=700)
            if map_data and map_data.get("last_clicked"):
                lat_nuevo = map_data["last_clicked"]["lat"]
                lon_nuevo = map_data["last_clicked"]["lng"]
                st.success(f"Coordenadas capturadas: {lat_nuevo:.5f}, {lon_nuevo:.5f}")
        else:
            st.warning("Modulo de mapas Folium no detectado, usa captura manual si lo sabes.")
            lat_col, lon_col = st.columns(2)
            lat_nuevo = lat_col.number_input("Latitud", format="%.6f")
            lon_nuevo = lon_col.number_input("Longitud", format="%.6f")

    # CRM LOGIC: Sugerencias y Registro de NO-VENTA
    if cliente_sel and tipo_cli != "➕ Cliente Nuevo Esporádico":
        st.markdown("---")
        hist_cli = df_compras[df_compras['ClienteNombre'] == cliente_sel]
        
        # VENTA SUGERIDA
        if not hist_cli.empty:
            favs = hist_cli[hist_cli['Cantidad'] > 0]['Producto'].value_counts().head(3).index.tolist()
            en_carrito = [cart_item['Producto'] for cart_item in st.session_state.cart]
            sugerencias = [f for f in favs if f not in en_carrito]
            if sugerencias:
                st.markdown(f"""
                <div style="background-color:#040B2D; border-left:4px solid #41D5FF; padding:12px; border-radius:8px; margin-bottom:15px; box-shadow:0 3px 10px rgba(0,0,0,0.1);">
                    <b style="color:#55C9FB; font-size:14px;">🧠 Inteligencia de Ventas (Sugerido hoy para este cliente):</b><br>
                    <span style="color:#d4d4d8; font-size:13px;">Basado en historial, el cliente suele comprar: <b style="color:white;">{', '.join(sugerencias)}</b>. ¡Ofrécelo ahora mismo!</span>
                </div>
                """, unsafe_allow_html=True)
                
        # MOTIVO DE NO COMPRA
        with st.expander("❌ ¿El cliente NO FACTURARÁ hoy? (Registrar Visita Fallida)"):
            motivo = st.selectbox("Indica la razón por la que no facturó:", ["", "Local cerrado", "Cerrado permanentemente", "Aún tiene inventario", "No tiene dinero / Efectivo", "No está el encargado", "Compró a la competencia", "Queja del servicio"])
            if st.button("Guardar Registro de Visita Sin Venta", type="primary"):
                if motivo:
                    from random import randint
                    ts = datetime.now()
                    c_cod = "N/A"
                    if not hist_cli.empty: c_cod = hist_cli.iloc[0]['ClienteCodigo']
                    n_fallo = f"FAIL-{vend_code[:2]}-{ts.strftime('%H%M')}-{randint(10,99)}"
                    df_bd = pd.DataFrame()
                    if COMPRAS_PATH.exists(): df_bd = pd.read_json(COMPRAS_PATH)
                    fila_falla = [{
                        "NoPedido": n_fallo, "Fecha": ts.strftime('%Y-%m-%d %H:%M:%S'), "ClienteCodigo": str(c_cod), "ClienteNombre": cliente_sel,
                        "Barrio": "", "Ciudad": "", "Ruta": dia_trabajo, "CodigoVendedor": vend_code,
                        "Vendedor": vend_actual, "CodigoProducto": "NO_COMPRA", "Producto": f"MOTIVO: {motivo}",
                        "Cantidad": 0, "PrecioBase": 0.0, "Total": 0.0,
                        "MetodoPago": "N/A", "Abono": 0, "Estado": "VISITA_FALLIDA", "PctDescuento": 0.0
                    }]
                    df_final_bd = pd.concat([df_bd, pd.DataFrame(fila_falla)], ignore_index=True)
                    df_final_bd.to_json(COMPRAS_PATH, orient="records", force_ascii=False, indent=2)
                    st.success(f"Motivo `{motivo}` registrado. ¡A por el siguiente cliente!")
                    st.session_state.cart = []
                    st.rerun()
                else:
                    st.error("Por favor seleccione un motivo válido en la lista.")
        st.markdown("---")

    st.markdown("### Seleccionar Productos (Catálogo Múltiple)")
    df_prods_act = df_productos.copy()
    if 'Activo' in df_prods_act.columns:
        df_prods_act = df_prods_act[df_prods_act['Activo'] == 1]
    
    lista_prods = []
    if not df_prods_act.empty:
        df_prods_act['InfoBusqueda'] = df_prods_act['Codigo'].astype(str) + " | " + df_prods_act['Nombre'] + " | $" + df_prods_act['PrecioBase'].astype(int).astype(str) + " | 📦 Disp: " + df_prods_act.get('Stock', 0).astype(int).astype(str)
        lista_prods = df_prods_act['InfoBusqueda'].dropna().unique().tolist()
    
    c2_1, c2_2, c2_3 = st.columns([3, 1, 1.5])
    with c2_1:
        prod_sel_info = st.selectbox("1. Buscar Producto (Escribe nombre o código):", [""] + sorted(lista_prods))
        
    with c2_2:
        cantidad = st.number_input("2. Unidades:", min_value=1, value=1, step=1)
        
    with c2_3:
        subt = 0
        if prod_sel_info:
            p_nombre = prod_sel_info.split(" | ")[1]
            p_info = df_prods_act[df_prods_act['Nombre'] == p_nombre].iloc[0]
            stock_disp = int(p_info.get('Stock', 0))
            subt = p_info['PrecioBase'] * cantidad
            
            if cantidad > stock_disp:
                stock_msg = f"<div style='color:#ef4444; font-size:12px; text-align:center;'>⚠️ Stock excedido ({stock_disp} Max)</div>"
                st.markdown(f"<div style='margin-top:28px; padding:10px; background-color:#450a0a; border-radius:12px; border: 1px solid #7f1d1d; text-align:center;'><b style='color:#fca5a5; font-size:1.1rem;'>Insuficiente</b></div>{stock_msg}", unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='margin-top:33px; padding:10px; background-color:#0A1B7F; border-radius:12px; border: 1px solid #132488; text-align:center;'><b style='color:#41D5FF; font-size:1.1rem;'>+ ${subt:,.0f}</b></div>", unsafe_allow_html=True)
        else:
            st.markdown("<div style='margin-top:33px; padding:10px; color:gray; text-align:center; border: 1px dashed #132488; border-radius: 12px;'>Total: $0</div>", unsafe_allow_html=True)
        
    st.markdown("<br>", unsafe_allow_html=True)
    c_btn1, c_btn2, c_btn3 = st.columns([1, 2, 1])
    with c_btn2:
        if st.button("➕ AGREGAR ESTO A LA LISTA DEL CLIENTE", use_container_width=True, type="secondary"):
            if getattr(st.session_state, 'cliente_en_curso', '') != cliente_sel:
                st.session_state.cart = [] # Si se cambia el cliente, vaciamos el carrito
                st.session_state.cliente_en_curso = cliente_sel
                
            if cliente_sel and prod_sel_info:
                p_nombre = prod_sel_info.split(" | ")[1]
                p_info = df_prods_act[df_prods_act['Nombre'] == p_nombre].iloc[0]
                stock_disp = int(p_info.get('Stock', 0))
                
                if cantidad > stock_disp:
                    st.error(f"🛑 Error de Stock: No puedes vender {cantidad}. Solo quedan {stock_disp} en inventario central.")
                else:
                    st.session_state.cart.append({
                        "Producto": p_nombre,
                        "CodigoProducto": p_info['Codigo'],
                        "Cantidad": cantidad,
                        "PrecioBase": p_info['PrecioBase'],
                        "Total": p_info['PrecioBase'] * cantidad
                    })
                    st.success(f"✓ {cantidad} x {p_nombre} agregados exitosamente a la factura actual.")
            else:
                st.error("⚠️ Debes tener seleccionado un Cliente válido y un Producto válido.")

    if st.session_state.cart:
        st.markdown("---")
        df_cart = pd.DataFrame(st.session_state.cart)
        st.dataframe(df_cart, use_container_width=True, hide_index=True)
        total_p = df_cart['Total'].sum()
        st.markdown(f"<h3 style='text-align: right;'>Total por productos: <b>${total_p:,.0f}</b></h3>", unsafe_allow_html=True)
        
        st.markdown("### 💳 Recaudo y Cierre")
        cp1, cp2 = st.columns(2)
        with cp1:
            metodo_pago = st.selectbox("Forma de Recaudo:", ["EFECTIVO CONTADO", "TRANSFERENCIA", "CREDITO (Para luego)", "ABONO PARCIAL / MIXTO"])
        with cp2:
            if metodo_pago in ["EFECTIVO CONTADO", "TRANSFERENCIA"]:
                abono = st.number_input("Valor recibido del cliente:", value=float(total_p), min_value=0.0)
            elif metodo_pago == "CREDITO (Para luego)":
                abono = st.number_input("Valor recibido del cliente:", value=0.0, min_value=0.0, max_value=float(total_p))
            else:
                abono = st.number_input("Valor recibido del cliente:", value=float(total_p/2), min_value=0.0)
                
        saldo = total_p - abono
        if saldo > 0:
            st.warning(f"⚠️ **Crédito Activo:** El cliente quedará debiendo **${saldo:,.0f}** en cartera.")
        elif saldo < 0:
            st.info(f"🔄 **Vuelto a entregar:** Dale **${abs(saldo):,.0f}** de cambio al tendero.")
            abono = total_p # Para balance perfecto contablemente
        else:
            st.success("✅ **Pago Completo:** Sin saldo pendiente.")
        
        if st.button("✅ Confirmar y Guardar Factura", type="primary"):
            from random import randint
            ts = datetime.now()
            n_ped = f"P-{vend_code[:2]}-{ts.strftime('%H%M')}-{randint(10,99)}"
            
            # --- 1. Lógica para Guardar Cliente Nuevo ---
            c_cod = "NUEVO"
            ciudad = "SAHAGUN"
            
            if tipo_cli == "➕ Cliente Nuevo Esporádico" and cliente_sel:
                # Escribimos en maestros
                c_cod = f"C-{randint(1000, 9999)}"
                # Cargar y guardar en ubicaciones.json
                df_ubi_bd = pd.DataFrame()
                if UBICACIONES_PATH.exists(): df_ubi_bd = pd.read_json(UBICACIONES_PATH)
                nueva_ubi = {"Cliente": cliente_sel, "Barrio": barrio_nuevo, "DiaVisita": dia_trabajo, "Ruta": dia_trabajo, "Latitud": lat_nuevo, "Longitud": lon_nuevo, "NOMBRE_NORM": cliente_sel.upper()}
                df_ubi_mod = pd.concat([df_ubi_bd, pd.DataFrame([nueva_ubi])], ignore_index=True)
                df_ubi_mod.to_json(UBICACIONES_PATH, orient="records", force_ascii=False, indent=2)
                # Cargar y Guardar en clientes_maestro.json
                df_cli_bd = pd.DataFrame()
                if CLIENTES_PATH.exists(): df_cli_bd = pd.read_json(CLIENTES_PATH)
                nuevo_cli = {"Activo": 1, "Codigo": c_cod, "Nombre": cliente_sel, "Descuento": 0, "Cupo_Credito": 0, "Barrio": barrio_nuevo, "Ciudad": ciudad, "Latitud": lat_nuevo, "Longitud": lon_nuevo}
                df_cli_mod = pd.concat([df_cli_bd, pd.DataFrame([nuevo_cli])], ignore_index=True)
                df_cli_mod.to_json(CLIENTES_PATH, orient="records", force_ascii=False, indent=2)
                
            elif tipo_cli in ["📋 De mi Ruta", "🔍 Buscar en General"]:
                cx = df_clientes[df_clientes['Nombre'] == cliente_sel]
                if not cx.empty:
                    c_cod = cx.iloc[0].get('Codigo', "N/A")
                    barrio_nuevo = cx.iloc[0].get('Barrio', "")
                    ciudad = cx.iloc[0].get('Ciudad', "SAHAGUN")
                    lat_nuevo = cx.iloc[0].get('Latitud', None)
                    lon_nuevo = cx.iloc[0].get('Longitud', None)
                    
            # --- 2. Lógica para Archivar Transacciones ---
            filas_nuevas = []
            f_str = ts.strftime('%Y-%m-%d %H:%M:%S')
            for it in st.session_state.cart:
                filas_nuevas.append({
                    "NoPedido": n_ped, "Fecha": f_str, "ClienteCodigo": str(c_cod), "ClienteNombre": cliente_sel,
                    "Barrio": str(barrio_nuevo), "Ciudad": str(ciudad), "Ruta": dia_trabajo, "CodigoVendedor": vend_code,
                    "Vendedor": vend_actual, "CodigoProducto": str(it["CodigoProducto"]), "Producto": it["Producto"],
                    "Cantidad": it["Cantidad"], "PrecioBase": float(it["PrecioBase"]), "Total": float(it["Total"]),
                    "MetodoPago": metodo_pago, "Abono": float(abono), "Estado": "TOMADO_PREVENTISTA", "PctDescuento": 0.0
                })
            df_agregar = pd.DataFrame(filas_nuevas)
            df_bd = pd.DataFrame()
            if COMPRAS_PATH.exists(): df_bd = pd.read_json(COMPRAS_PATH)
            
            df_final_bd = pd.concat([df_bd, df_agregar], ignore_index=True)
            df_final_bd.to_json(COMPRAS_PATH, orient="records", force_ascii=False, indent=2)
            
            # --- 2.5 Lógica para Descontar el Inventario Físico Central ---
            PRODUCTOS_PATH = MAESTROS_DIR / "productos.json"
            if PRODUCTOS_PATH.exists():
                df_prod_bd = pd.read_json(PRODUCTOS_PATH)
                for it in st.session_state.cart:
                    idx_p = df_prod_bd.index[df_prod_bd['Codigo'].astype(str) == str(it['CodigoProducto'])]
                    if not idx_p.empty:
                        df_prod_bd.loc[idx_p, 'Stock'] -= int(it['Cantidad'])
                df_prod_bd.to_json(PRODUCTOS_PATH, orient="records", force_ascii=False, indent=2)
            
            # --- 3. Preparar Factura en Memoria y limpiar ---
            st.session_state.last_invoice = {
                "no_pedido": n_ped, "fecha": f_str, "cliente": cliente_sel, "barrio": barrio_nuevo,
                "lat": lat_nuevo, "lon": lon_nuevo, "total": total_p, "df": df_cart,
                "metodo_pago": metodo_pago, "abono": abono, "saldo": max(0, total_p - abono)
            }
            st.session_state.cart = []
            st.session_state.cliente_en_curso = ""
            st.cache_data.clear()
            st.rerun()

        if st.button("🗑️ Vaciar Carrito"):
            st.session_state.cart = []
            st.rerun()

# ----- Pestaña Facturación -----
with tab_factura:
    st.subheader("📄 Relación de Facturas del Día")
    
    hoy_puro_str = datetime.now().strftime('%Y-%m-%d')
    facturas_hoy = df_mis_pedidos[df_mis_pedidos['Fecha'].astype(str).str.startswith(hoy_puro_str, na=False)] if not df_mis_pedidos.empty else pd.DataFrame()
        
    if facturas_hoy.empty:
        st.info("No has emitido facturas en el turno de hoy.")
    else:
        # Agrupar para el listado de selección
        resumen_fac = facturas_hoy.groupby('NoPedido').agg({'Fecha':'first', 'ClienteNombre':'first', 'Total':'sum'}).reset_index().sort_values('Fecha', ascending=False)
        lista_opciones = resumen_fac.apply(lambda r: f"{r['NoPedido']} | {r['ClienteNombre']} | ${r['Total']:,.0f}", axis=1).tolist()
        
        # Seleccionar por defecto la compra recién hecha
        idx_defecto = 0
        if "last_invoice" in st.session_state and st.session_state.last_invoice:
            last_ped_id = st.session_state.last_invoice['no_pedido']
            matches = [i for i, x in enumerate(lista_opciones) if last_ped_id in x]
            if matches: idx_defecto = matches[0]
            
        fac_sel_desc = st.selectbox("Seleccione Factura a Gestionar/Imprimir:", lista_opciones, index=idx_defecto)
        
        fac_id = fac_sel_desc.split(" | ")[0]
        fac_df = facturas_hoy[facturas_hoy['NoPedido'] == fac_id].copy()
        
        # Set constants
        fac_vendedor = vend_actual
        fac_fecha = fac_df.iloc[0]['Fecha']
        fac_cliente = fac_df.iloc[0]['ClienteNombre']
        fac_barrio = fac_df.iloc[0].get('Barrio', 'N/A')
        fac_total = fac_df['Total'].sum()
        fac_abono = fac_df.iloc[0].get('Abono', fac_total) # Fallback to total if old invoice
        fac_metodo = fac_df.iloc[0].get('MetodoPago', 'ACORDADO')
        fac_saldo = max(0, fac_total - fac_abono)
        
        c_i1, c_i2 = st.columns([2, 1])
        with c_i1:
            st.markdown(f"""
            <div data-testid="stMetric" style="padding: 20px;">
                <h4 style="margin:0; color:#55C9FB;">PREVENTA LA CAMPIÑA</h4>
                <p style="margin:0;"><b>Factura Volante:</b> {fac_id}</p>
                <p style="margin:0;"><b>Fecha:</b> {fac_fecha}</p>
                <p style="margin:0;"><b>Cliente:</b> {fac_cliente}</p>
                <p style="margin:0;"><b>Barrio:</b> {fac_barrio}</p>
            </div>
            """, unsafe_allow_html=True)
        with c_i2:
            st.markdown(f"<h2 style='color:#41D5FF; text-align:center;'><br>${fac_total:,.0f}</h2>", unsafe_allow_html=True)

        st.dataframe(fac_df[['Producto', 'Cantidad', 'PrecioBase', 'Total']], use_container_width=True, hide_index=True)
        
        st.markdown("---")
        # WhatsApp Text logic
        texto_wa = f"📋 *FACTURA DE PEDIDO:* {fac_id}\n🗓 *Fecha:* {fac_fecha}\n👤 *Cliente:* {fac_cliente}\n💳 *Forma de Pago:* {fac_metodo}\n------------------\n"
        for _, row in fac_df.iterrows():
            texto_wa += f"• {row['Cantidad']} und - {row['Producto']} => ${row['Total']:,.0f}\n"
        texto_wa += f"------------------\n💰 *TOTAL*: ${fac_total:,.0f}\n"
        if fac_saldo > 0:
            texto_wa += f"⚠️ *SALDO PENDIENTE*: ${fac_saldo:,.0f}\n"
        texto_wa += "Gracias por su compra! ~ 🚜 La Campiña"
        
        link_wa = f"https://wa.me/?text={quote(texto_wa)}"
        
        HTML_TICKET = f'''
        <!DOCTYPE html><html><head><style>
        body {{ background: transparent; color: white; display:flex; justify-content:center; padding:10px; margin:0; font-family:sans-serif;}}
        .print-btn {{ cursor:pointer; background:#facc15; border:none; color:black; font-weight:bold; width:100%; border-radius: 8px; padding: 15px; font-size:16px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.3);}}
        .print-btn:hover {{ background:#eab308; }}
        .ticket {{ background: white; color: black; font-family: 'Courier New', Courier, monospace; width: 80mm; padding: 5mm; margin: 0 auto; box-sizing: border-box; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
        th, td {{ border-bottom: 1px dashed #ccc; padding: 4px 0; }}
        .right {{ text-align: right; }}
        .center {{ text-align: center; }}
        .bold {{ font-weight: bold; }}
        hr {{ border: none; border-top: 1px dashed black; margin: 8px 0; }}
        @media print {{
            body {{ background: white; padding:0; margin:0; display:block; }}
            .ticket {{ width: 100%; max-width: 100%; padding:0; margin:0; box-shadow:none; border:none; }}
            .no-print {{ display: none; }}
        }}
        </style></head><body>
        <div style="width: 100%; max-width: 80mm; display:flex; flex-direction:column;">
            <button class="no-print print-btn" onclick="window.print()">🖨️ IMPRIMIR FACTURA (MATRIZ POS)</button>
            <div class="ticket">
                <div class="center">
                    <h2 style="margin:0; font-size:16px;">DISTRIBUIDORA LA CAMPIÑA</h2>
                    <p style="margin:2px 0 0 0; font-size:11px;">NIT: 900.XXX.XXX-X</p>
                    <p style="margin:2px 0 0 0; font-size:11px;">Sahagun, Cordoba</p>
                </div>
                <hr>
                <div style="font-size: 11px; margin-bottom:10px;">
                    <p style="margin:2px 0;"><b>Factura :</b> {fac_id}</p>
                    <p style="margin:2px 0;"><b>Emision :</b> {fac_fecha}</p>
                    <p style="margin:2px 0;"><b>Vendedor:</b> {fac_vendedor}</p>
                    <p style="margin:2px 0;"><b>Cliente :</b> {fac_cliente}</p>
                    <p style="margin:2px 0;"><b>Tipo P. :</b> {fac_metodo}</p>
                </div>
                <hr>
                <table>
                    <tr class="bold"><th>CANT</th><th>DESC</th><th class="right">VALOR</th></tr>
        '''
        for _, r in fac_df.iterrows():
            HTML_TICKET += f"<tr><td>{r['Cantidad']}</td><td>{r['Producto'][:14]}</td><td class='right'>${r['Total']:,.0f}</td></tr>"
            
        HTML_TICKET += f'''
                </table>
                <hr>
                <h3 class="right" style="margin:5px 0;">TOTAL: ${fac_total:,.0f}</h3>
                <h4 class="right" style="margin:5px 0;">ABONO: ${fac_abono:,.0f}</h4>
                <h4 class="right" style="margin:5px 0; color: #555;">SALDO: ${fac_saldo:,.0f}</h4>
                <hr>
                <p class="center" style="font-size:11px; margin-top:20px;">*** OBLIGACION DE PAGO ***</p>
                <p class="center" style="font-size:11px; margin:2px 0;">¡GRACIAS POR SU COMPRA!</p>
            </div>
        </div>
        </body></html>
        '''
        
        c_p1, c_p2 = st.columns([1, 1])
        with c_p1:
            st.markdown(f"<a href='{link_wa}' target='_blank'><button style='width:100%; border-radius: 12px; font-weight: bold; background-color: #040B2D; color: #25D366; border: 1px solid #25D366; padding: 12px; cursor: pointer; margin-top:10px;'>📲 Enviar Comprobante / WhatsApp</button></a>", unsafe_allow_html=True)
            st.info("👈 Envía el resumen vía app móvil o utiliza el visor interactivo de la derecha para mandar a impresión térmica POS. (Contiene desglose de Abono/Saldo para cobradores)")
        with c_p2:
            st.components.v1.html(HTML_TICKET, height=450, scrolling=True)

# ----- Pestaña Mi Desempeño -----
with tab_desempeno:
    st.subheader("📈 Tus Estadísticas de Rentabilidad (Indicadores)")
    if not df_compras.empty:
        df_mis = df_compras[df_compras['Vendedor'].astype(str).str.upper() == vend_actual].copy()
        if df_mis.empty:
            st.info("Sin registros globales acumulados.")
        else:
            df_mis['Fecha_DT'] = pd.to_datetime(df_mis['Fecha'], errors='coerce')
            
            hoy_str = datetime.now().strftime('%Y-%m-%d')
            hace_7_dias = (datetime.now() - pd.Timedelta(days=7)).strftime('%Y-%m-%d')
            
            # Aislamiento de registros fallidos para sumas monetarias
            ventas_reales = df_mis[df_mis['Estado'] != 'VISITA_FALLIDA']
            
            pedidos_hoy_d = ventas_reales[ventas_reales['Fecha_DT'].dt.date.astype(str) == hoy_str]
            pedidos_sp = ventas_reales[ventas_reales['Fecha_DT'].dt.date.astype(str) == hace_7_dias]
            
            ttl_hoy = pedidos_hoy_d['Total'].sum()
            und_hoy = pedidos_hoy_d['Cantidad'].sum()
            
            ttl_sp = pedidos_sp['Total'].sum()
            und_sp = pedidos_sp['Cantidad'].sum()
            
            dif_ttl = ttl_hoy - ttl_sp
            dif_und = und_hoy - und_sp
            
            st.markdown(f"**Comparativa Integral del día (Hoy vs {hace_7_dias})**")
            cM1, cM2 = st.columns(2)
            cM1.metric("Venta Bruta Creada Hoy", f"${ttl_hoy:,.0f}", f"{dif_ttl:,.0f} $ que hace 7 días")
            cM2.metric("Unidades Físicas Facturadas", f"{int(und_hoy)}", f"{int(dif_und)} unds. que hace 7 días")
            
            st.markdown("---")
            st.markdown("**Analítica de Efectividad Logística (Métricas de la Calle)**")
            cx1, cx2 = st.columns(2)
            
            # Calculo de Drop Size & Hit Rate (Requiere ver tanto las compras como las fallidas)
            trans_hoy_todas = df_mis[df_mis['Fecha_DT'].dt.date.astype(str) == hoy_str]
            if not trans_hoy_todas.empty:
                clientes_tocados = trans_hoy_todas['ClienteNombre'].nunique()
                clientes_q_compraron = pedidos_hoy_d['ClienteNombre'].nunique()
                
                hit_rate = (clientes_q_compraron / clientes_tocados) * 100 if clientes_tocados > 0 else 0
                drop_size = ttl_hoy / clientes_q_compraron if clientes_q_compraron > 0 else 0
                
                cx1.metric("Hit Rate (Efectividad Efectiva)", f"{hit_rate:.1f}%", f"{clientes_q_compraron} facturados de {clientes_tocados} visitados.")
                cx2.metric("Drop Size (Ticket de Calle)", f"${drop_size:,.0f}", f"Promedio por cada tendero comprado.")
            else:
                st.info("La jornada operativa no ha iniciado. Toma un pedido para medir el Drop Size.")
            
            st.markdown("---")
            st.markdown("**Acumulado General Histórico**")
            ttl_h = ventas_reales['Total'].sum()
            und_h = ventas_reales['Cantidad'].sum()
            st.metric("Cartera Histórica Personal de este Vendedor", f"${ttl_h:,.0f}")
    else:
        st.info("Motor Central Desactivado o Sin Informes.")
