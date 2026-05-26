import streamlit as st
import pandas as pd
import shutil
from pathlib import Path
from datetime import datetime
import numpy as np
from utils.file_utils import safe_write_json

# Función auxiliar para mapear nombres de columnas de manera robusta
def find_matching_column(df_cols, possible_names):
    norm_possibles = [
        str(n).lower().strip().replace(" ", "").replace("_", "").replace(".", "")
        .replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
        for n in possible_names
    ]
    for col in df_cols:
        norm_col = (
            str(col).lower().strip().replace(" ", "").replace("_", "").replace(".", "")
            .replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
        )
        if norm_col in norm_possibles:
            return col
    return None

st.title("Carga de Datos")
st.markdown("Sube los archivos Excel del sistema operativo (Ventas, Productos, Vendedores) para almacenarlos, indexarlos y habilitarlos en los Dashboards. *La base de clientes y ubicaciones se gestiona de forma centralizada en el Módulo 7.*")

# Security check: only Admin or Dueño
if st.session_state.get("user_info", {}).get("role") not in ["ADMINISTRADOR", "DUEÑO"]:
    st.error("No tienes permisos suficientes para acceder a este módulo.")
    st.stop()

st.markdown("### Selecciona los archivos obligatorios (.xlsx)")

col1, col2 = st.columns(2)
with col1:
    f_compras = st.file_uploader("ÓRDENES DE COMPRA (Purchase...) [Opcional]", type=["xlsx", "xls"])
    f_vendedores = st.file_uploader("VENDEDORES [Opcional]", type=["xlsx", "xls"])
with col2:
    f_productos = st.file_uploader("PRODUCTOS [Opcional]", type=["xlsx", "xls"])
    f_sold_products = st.file_uploader("REPORTE VENTAS PRODUCTOS (SoldProductsReport) [Opcional]", type=["xlsx", "xls"])

st.markdown("---")
st.subheader("Etiquetar Periodo de Reporte")
st.markdown("Deja este campo con la fecha de hoy si deseas que el sistema intente extraer la fecha de los archivos, o selecciona una fecha específica para forzar el nombre del lote.")
fecha_manual = st.date_input("¿De qué fecha es esta información?", datetime.today())

btn_procesar = st.button("Procesar Archivos Subidos", type="primary", use_container_width=True)

if btn_procesar:
    if not any([f_compras, f_vendedores, f_productos, f_sold_products]):
        st.error("Debes subir al menos un archivo para procesar.")
    else:
        try:
            with st.spinner("Procesando los archivos y enlazándolos con la Base Maestra..."):
                # Intentar deducir la fecha del archivo compras si se subió
                fecha_lote = fecha_manual
                df_compras = None
                
                if f_compras:
                    df_compras = pd.read_excel(f_compras)
                    # Mapeo flexible para buscar la columna de fecha
                    col_fecha_temp = find_matching_column(df_compras.columns, ['Fecha', 'OrderDate', 'Fecha de creacion', 'FechaCreacion', 'Date'])
                    if col_fecha_temp and col_fecha_temp in df_compras.columns:
                        try:
                            # Intentar sacar la última fecha del archivo para nombrar el lote
                            fechas_validas = pd.to_datetime(df_compras[col_fecha_temp], errors='coerce').dropna()
                            if not fechas_validas.empty:
                                fecha_lote = fechas_validas.max().date()
                        except:
                            pass
                
                # Ensure directory exists
                dest_dir = Path(__file__).resolve().parent.parent / "datos_historicos" / fecha_lote.strftime('%Y-%m-%d')
                dest_dir.mkdir(parents=True, exist_ok=True)
                
                procesados = []
                
                # --- COMPRAS Y DETALLE ---
                if f_compras is not None and df_compras is not None:
                    # Mapeo robusto de columnas
                    id_col = find_matching_column(df_compras.columns, ['No. Pedido', 'No Pedido', 'Id', 'No_Pedido', 'Pedido', 'PurchaseOrderID', 'Purchase Order ID'])
                    fecha_col = find_matching_column(df_compras.columns, ['Fecha', 'OrderDate', 'Fecha de creacion', 'FechaCreacion', 'Date'])
                    cliente_col = find_matching_column(df_compras.columns, ['Código cliente', 'Codigo cliente', 'ClienteCodigo', 'Cliente Código', 'ClientCode', 'Código_cliente'])
                    total_col = find_matching_column(df_compras.columns, ['Total', 'LineTotal', 'Valor Total', 'ValorTotal', 'Monto'])
                    
                    if not id_col or not fecha_col or not cliente_col or not total_col:
                        faltantes = []
                        if not id_col: faltantes.append('No. Pedido')
                        if not fecha_col: faltantes.append('Fecha')
                        if not cliente_col: faltantes.append('Código cliente')
                        if not total_col: faltantes.append('Total')
                        st.error(f"El Excel de Compras no tiene las columnas necesarias. Faltan: {faltantes}")
                        raise KeyError(f"{faltantes}")
                    
                    df_compras_clean = pd.DataFrame({
                        'PurchaseOrderID': df_compras[id_col],
                        'OrderDate': pd.to_datetime(df_compras[fecha_col]).dt.strftime('%Y-%m-%d'),
                        'LineTotal': df_compras[total_col],
                        'ClienteCodigo': df_compras[cliente_col]
                    })
                    df_compras_agg = df_compras_clean.groupby('PurchaseOrderID', as_index=False).agg({
                        'OrderDate': 'first',
                        'LineTotal': 'sum',
                        'ClienteCodigo': 'first'
                    })
                    safe_write_json(df_compras_agg, dest_dir / 'compras.json')
                    
                    # Para el detalle, rellenamos de forma flexible
                    hora_col = find_matching_column(df_compras.columns, ['Hora', 'Hora de creacion', 'HoraCreacion', 'Time'])
                    metodo_pago_col = find_matching_column(df_compras.columns, ['Método de pago', 'Metodo de pago', 'MetodoPago', 'Tipo documento', 'PaymentMethod'])
                    direccion_col = find_matching_column(df_compras.columns, ['Dirección', 'Direccion', 'Address'])
                    ciudad_col = find_matching_column(df_compras.columns, ['Ciudad', 'City'])
                    barrio_col = find_matching_column(df_compras.columns, ['Barrio', 'Neighborhood'])
                    ruta_col = find_matching_column(df_compras.columns, ['Ruta', 'DiaRuta', 'RutaDia', 'Route'])
                    vendedor_col = find_matching_column(df_compras.columns, ['Vendedor', 'Encargado', 'Seller'])
                    prod_cod_col = find_matching_column(df_compras.columns, ['Código producto', 'Codigo producto', 'ProductoCodigo', 'Product Code', 'CodigoProducto'])
                    prod_nom_col = find_matching_column(df_compras.columns, ['Producto', 'Nombre producto', 'NombreProducto', 'Product Name', 'ProductoNombre'])
                    cant_col = find_matching_column(df_compras.columns, ['Cantidad', 'Total items', 'Quantity', 'Qty'])
                    precio_col = find_matching_column(df_compras.columns, ['Precio base', 'PrecioBase', 'Subtotal', 'Base Price'])

                    metodo_pago = df_compras[metodo_pago_col] if metodo_pago_col else 'Desconocido'
                    
                    df_compras_detalle = pd.DataFrame({
                        'PurchaseOrderID': df_compras[id_col],
                        'OrderDate': pd.to_datetime(df_compras[fecha_col]).dt.strftime('%Y-%m-%d'),
                        'Hora': pd.to_datetime(df_compras[hora_col], format='%H:%M:%S', errors='coerce').dt.strftime('%H:%M:%S').fillna("00:00:00") if hora_col else "00:00:00",
                        'MetodoPago': metodo_pago,
                        'Direccion': df_compras[direccion_col] if direccion_col else '',
                        'Ciudad': df_compras[ciudad_col].fillna('SAHAGUN') if ciudad_col else 'SAHAGUN',
                        'Barrio': df_compras[barrio_col].fillna('Desconocido') if barrio_col else 'Desconocido',
                        'ClienteCodigo': df_compras[cliente_col],
                        'DiaRuta': df_compras[ruta_col] if ruta_col else '',
                        'Vendedor': df_compras[vendedor_col] if vendedor_col else '',
                        'ProductoCodigo': df_compras[prod_cod_col] if prod_cod_col else 'VARIOS',
                        'ProductoNombre': df_compras[prod_nom_col] if prod_nom_col else 'PRODUCTOS VARIOS (Reporte Cabecera)',
                        'Cantidad': df_compras[cant_col] if cant_col else 1,
                        'PrecioBase': df_compras[precio_col] if precio_col else df_compras[total_col],
                        'LineTotal': df_compras[total_col]
                    })
                    safe_write_json(df_compras_detalle, dest_dir / 'compras_detalle.json')

                    # --- 🤖  ROBUST CLIENT MATRIX (Decoupled Module 10) ---
                    # 1. Extraer los clientes empíricos reales que aparecieron comprando (La verdad absoluta operativa)
                    compras_clientes = df_compras_detalle[['ClienteCodigo']].drop_duplicates()
                    compras_clientes.rename(columns={'ClienteCodigo': 'Codigo'}, inplace=True)
                    
                    # 2. Leer la Base Maestra Permanente
                    maestro_path = Path(__file__).resolve().parent.parent / "datos_maestros" / "clientes_maestro.json"
                    if maestro_path.exists():
                        df_maestro = pd.read_json(maestro_path)
                    else:
                        st.warning("No se encontró la base maestra de clientes. Creando un esqueleto temporal.")
                        df_maestro = pd.DataFrame(columns=['Codigo', 'Nombre', 'Ciudad', 'Categoria', 'Activo', 'Vendedor', 'Barrio', 'DiaVisita', 'Latitud', 'Longitud'])
                    
                    # 3. Left Join: Traer info del Maestro para los clientes que compraron este periodo. 
                    # (Si un cliente compró y NO está en el maestro, quedará con valores NaN geográficos)
                    df_cruce = pd.merge(compras_clientes, df_maestro, on='Codigo', how='left')
                    
                    # Llenar huecos básicos para huérfanos nuevos que no estaban en el Maestro
                    mask_huérfanos = df_cruce['Nombre'].isna()
                    df_cruce.loc[mask_huérfanos, 'Nombre'] = "CLIENTE NUEVO " + df_cruce.loc[mask_huérfanos, 'Codigo'].astype(str)
                    df_cruce['Activo'] = df_cruce['Activo'].fillna(1)
                    
                    # Rescatar Ciudad, Barrio, Día de Ruta y Vendedor desde las compras detalladas si faltan
                    info_reciente = df_compras_detalle.sort_values('OrderDate').drop_duplicates('ClienteCodigo', keep='last')
                    df_cruce = pd.merge(df_cruce, info_reciente[['ClienteCodigo', 'DiaRuta', 'Vendedor', 'Ciudad', 'Barrio']], left_on='Codigo', right_on='ClienteCodigo', how='left', suffixes=('_master', '_pedidos'))
                    
                    df_cruce['DiaVisita'] = df_cruce['DiaVisita'].combine_first(df_cruce['DiaRuta'])
                    
                    # Preferir Ciudad y Barrio operativos recientes si en el maestro están vacíos o asume SAHAGUN erróneamente
                    if 'Ciudad_master' in df_cruce.columns:
                        df_cruce['Ciudad'] = df_cruce['Ciudad_pedidos'].combine_first(df_cruce['Ciudad_master'])
                    else:
                        df_cruce['Ciudad'] = df_cruce['Ciudad_pedidos'].fillna("SAHAGUN")
                        
                    if 'Barrio_master' in df_cruce.columns:
                        df_cruce['Barrio'] = df_cruce['Barrio_master'].combine_first(df_cruce['Barrio_pedidos'])
                    else:
                        df_cruce['Barrio'] = df_cruce['Barrio_pedidos'].fillna("Desconocido")
                    
                    if 'Vendedor_master' in df_cruce.columns:
                        df_cruce['Vendedor'] = df_cruce['Vendedor_master'].combine_first(df_cruce['Vendedor_pedidos'])
                    else:
                        df_cruce['Vendedor'] = df_cruce['Vendedor_pedidos']
                    
                    # 4. GEOLOCALIZACIÓN ZONAL SIMULADA ("ZONING") SOLO PARA HUÉRFANOS NUEVOS
                    center_lat, center_lon = 8.94617, -75.04523 # Centro de Sahagún base
                    dict_barrios = df_maestro.dropna(subset=['Latitud', 'Longitud']).groupby('Barrio').agg({'Latitud':'mean', 'Longitud':'mean'}).to_dict('index') if not df_maestro.empty else {}
                    
                    np.random.seed(42) # Consistencia visual
                    for i, row in df_cruce.iterrows():
                        # Si el maestro le falló dando coordenadas (cliente muy nuevo sin perfilar)
                        if pd.isna(row['Latitud']) or pd.isna(row['Longitud']) or row['Latitud'] == 0 or str(row['Latitud']) == "0.0" or row['Latitud'] == "":
                            # Tratamos de extraer su barrio para la misma regla de espolvoreado de contingencia
                            # Como no viene del maestro, extraemos su direccion del detalle a ver si hacemos milagro (avanzado) o lo fijamos al centro
                            b = row['Barrio']
                            if pd.isna(b) or b not in dict_barrios:
                                lat = center_lat + np.random.uniform(-0.025, 0.025)
                                lon = center_lon + np.random.uniform(-0.025, 0.025)
                                df_cruce.at[i, 'Barrio'] = 'Desconocido'
                            else:
                                b_lat, b_lon = dict_barrios[b]['Latitud'], dict_barrios[b]['Longitud']
                                lat = b_lat + np.random.uniform(-0.005, 0.005)
                                lon = b_lon + np.random.uniform(-0.005, 0.005)
                                
                            df_cruce.at[i, 'Latitud'] = round(float(lat), 6)
                            df_cruce.at[i, 'Longitud'] = round(float(lon), 6)

                    cols_to_keep = ['Codigo', 'Nombre', 'Ciudad', 'Categoria', 'Activo', 'Vendedor', 'Barrio', 'DiaVisita', 'Latitud', 'Longitud']
                    df_final_clientes = df_cruce[[c for c in cols_to_keep if c in df_cruce.columns]].drop_duplicates(subset=['Codigo'])
                    
                    safe_write_json(df_final_clientes, dest_dir / 'clientes.json')
                    procesados.append("Órdenes de Compra y Clientes Transaccionales")
                
                # --- REPORTE VENTAS PRODUCTOS ---
                if f_sold_products is not None:
                    try:
                        df_sold = pd.read_excel(f_sold_products)
                        
                        col_codigo = find_matching_column(df_sold.columns, ['Código', 'Codigo', 'ProductoCodigo', 'ProductCode', 'Code'])
                        col_nombre = find_matching_column(df_sold.columns, ['Nombre', 'Producto', 'ProductName', 'Name'])
                        col_cantidad = find_matching_column(df_sold.columns, ['Total productos vendidos', 'Cantidad', 'CantidadVendida', 'Quantity', 'Qty'])
                        col_precio = find_matching_column(df_sold.columns, ['Precio base promedio', 'Precio base', 'PrecioPromedio', 'AveragePrice', 'Price'])
                        col_total = find_matching_column(df_sold.columns, ['Total base (sin impuestos)', 'Total', 'TotalIngresos', 'LineTotal', 'Revenue'])
                        col_clientes = find_matching_column(df_sold.columns, ['Clientes que compraron', 'ClientesDiferentes', 'Clientes', 'Customers'])
                        
                        if not col_codigo:
                            raise KeyError(f"No se encontró la columna de Código de producto. Columnas detectadas: {df_sold.columns.tolist()}")
                            
                        df_sold_clean = pd.DataFrame({
                            'CodigoProducto': df_sold[col_codigo],
                            'Nombre': df_sold[col_nombre] if col_nombre else 'Variado',
                            'CantidadVendida': df_sold[col_cantidad] if col_cantidad else 0,
                            'PrecioPromedio': df_sold[col_precio] if col_precio else 0,
                            'TotalIngresos': df_sold[col_total] if col_total else 0,
                            'ClientesDiferentes': df_sold[col_clientes] if col_clientes else 1
                        })
                        safe_write_json(df_sold_clean, dest_dir / 'sold_products.json')
                        procesados.append("Reporte Totalizado de Ventas por Producto")
                    except Exception as e:
                        st.error(f"Error procesando EL REPORTE DE VENTAS (SoldProducts): {e}")
                        raise e
                
                # --- PRODUCTOS ---
                if f_productos is not None:
                    try:
                        df_productos = pd.read_excel(f_productos)
                        col_prod_codigo = find_matching_column(df_productos.columns, ['CÓDIGO (Obligatorio)', 'Código', 'Codigo', 'Code', 'ProductCode'])
                        col_prod_nombre = find_matching_column(df_productos.columns, ['NOMBRE (Obligatorio)', 'Nombre', 'Name', 'ProductName'])
                        col_prod_cat = find_matching_column(df_productos.columns, ['CÓDIGO CATEGORÍA', 'Categoría', 'Categoria', 'Category'])
                        col_prod_precio = find_matching_column(df_productos.columns, ['PRECIO BASE (Obligatorio)', 'Precio base', 'Precio', 'Price'])
                        col_prod_stock = find_matching_column(df_productos.columns, ['CANTIDAD EN INVENTARIO', 'Stock', 'Inventario', 'Cantidad'])

                        if not col_prod_codigo or not col_prod_nombre or not col_prod_precio:
                            raise KeyError("Faltan campos obligatorios en el archivo de Productos (Código, Nombre o Precio).")

                        df_productos_clean = pd.DataFrame({
                            'Codigo': df_productos[col_prod_codigo],
                            'Nombre': df_productos[col_prod_nombre],
                            'Categoria': df_productos[col_prod_cat] if col_prod_cat else 'Sin Categoria',
                            'Precio': df_productos[col_prod_precio],
                            'Stock': df_productos[col_prod_stock] if col_prod_stock else 0
                        })
                        df_productos_clean['Categoria'] = df_productos_clean['Categoria'].fillna('Sin Categoria')
                        df_productos_clean['Stock'] = df_productos_clean['Stock'].fillna(0)
                        safe_write_json(df_productos_clean, dest_dir / 'productos.json')
                        procesados.append("Productos")
                    except Exception as e:
                        st.error(f"Error procesando el archivo de PRODUCTOS. ¿Tiene las columnas esperadas?: {e}")
                        raise e
                
                # --- VENDEDORES ---
                if f_vendedores is not None:
                    try:
                        df_vendedores = pd.read_excel(f_vendedores)
                        col_vend_codigo = find_matching_column(df_vendedores.columns, ['USUARIO (NUMÉRICO)', 'Usuario', 'Código', 'Codigo', 'ID', 'SellerID'])
                        col_vend_nombre = find_matching_column(df_vendedores.columns, ['NOMBRE', 'Nombre', 'Name'])
                        
                        if not col_vend_codigo or not col_vend_nombre:
                            raise KeyError("Faltan campos obligatorios en el archivo de Vendedores (Usuario o Nombre).")

                        df_vendedores_clean = pd.DataFrame({
                            'Codigo': df_vendedores[col_vend_codigo],
                            'Nombre': df_vendedores[col_vend_nombre]
                        })
                        safe_write_json(df_vendedores_clean, dest_dir / 'vendedores.json')
                        procesados.append("Vendedores")
                    except Exception as e:
                        st.error(f"Error procesando el archivo de VENDEDORES: {e}")
                        raise e
                
                st.cache_data.clear() # Clear cache so sidebar date selector registers the new folder
                msg = ", ".join(procesados)
                st.success(f"¡Carga Exitosa! Se procesaron: {msg}. Archivos guardados en el lote '{fecha_lote.strftime('%Y-%m-%d')}'.", icon="✅")
                
        except Exception as e:
            st.error(f"El procesamiento se detuvo debido a un error de estructura en el archivo. Detalle técnico: {e}")

st.markdown("---")
st.subheader("Lotes Históricos")
st.markdown("Si subiste un mes equivocado o quieres limpiar la base de datos, selecciona un lote y bórralo permanentemente.")

historicos_dir = Path(__file__).resolve().parent.parent / "datos_historicos"
if historicos_dir.exists():
    fechas_disponibles = sorted([d.name for d in historicos_dir.iterdir() if d.is_dir()], reverse=True)
else:
    fechas_disponibles = []

if fechas_disponibles:
    lote_a_borrar = st.selectbox("Selecciona el Lote a Eliminar:", fechas_disponibles)
    if st.button("🚨 Eliminar Lote Completamente", type="secondary"):
        try:
            ruta_borrar = historicos_dir / lote_a_borrar
            shutil.rmtree(ruta_borrar)
            st.cache_data.clear()
            st.success(f"El lote '{lote_a_borrar}' ha sido eliminado exitosamente.")
            st.rerun()
        except Exception as e:
            st.error(f"No se pudo eliminar el lote: {e}")
else:
    st.info("No hay lotes históricos cargados para eliminar.")
