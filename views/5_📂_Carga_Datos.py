import streamlit as st
import pandas as pd
import json
import os
import shutil
from pathlib import Path
from datetime import datetime
import numpy as np

st.set_page_config(page_title="Carga de Datos", page_icon="📂", layout="wide")

st.title("📂 Subida y Procesamiento de Datos Históricos")
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
                    if 'Fecha' in df_compras.columns:
                        try:
                            # Intentar sacar la última fecha del archivo para nombrar el lote
                            fechas_validas = pd.to_datetime(df_compras['Fecha'], errors='coerce').dropna()
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
                    # Map the column names robustly since report format varies 
                    id_col = 'No. Pedido' if 'No. Pedido' in df_compras.columns else 'Id'
                    fecha_col = 'Fecha' if 'Fecha' in df_compras.columns else 'Fecha de creacion'
                    
                    if id_col not in df_compras.columns or fecha_col not in df_compras.columns or 'Código cliente' not in df_compras.columns or 'Total' not in df_compras.columns:
                        faltantes = [c for c in ['Id/No. Pedido', 'Fecha/Fecha de creacion', 'Código cliente', 'Total'] if c.split('/')[0] not in df_compras.columns and (len(c.split('/')) == 1 or c.split('/')[1] not in df_compras.columns)]
                        st.error(f"El Excel de Compras no tiene las columnas necesarias. Faltan: {faltantes}")
                        raise KeyError(f"{faltantes}")
                    
                    df_compras_clean = pd.DataFrame({
                        'PurchaseOrderID': df_compras[id_col],
                        'OrderDate': pd.to_datetime(df_compras[fecha_col]).dt.strftime('%Y-%m-%d'),
                        'LineTotal': df_compras['Total'],
                        'ClienteCodigo': df_compras['Código cliente']
                    })
                    df_compras_agg = df_compras_clean.groupby('PurchaseOrderID', as_index=False).agg({
                        'OrderDate': 'first',
                        'LineTotal': 'sum',
                        'ClienteCodigo': 'first'
                    })
                    df_compras_agg.to_json(dest_dir / 'compras.json', orient='records', force_ascii=False)
                    
                    # Para el detalle, el PurchaseOrdersReport(cabecera) NO tiene productos, pero rellenamos con genéricos
                    hora_col = 'Hora' if 'Hora' in df_compras.columns else 'Hora de creacion'
                    metodo_pago = df_compras.get('Método de pago', df_compras.get('Tipo documento', 'Desconocido'))
                    
                    df_compras_detalle = pd.DataFrame({
                        'PurchaseOrderID': df_compras[id_col],
                        'OrderDate': pd.to_datetime(df_compras[fecha_col]).dt.strftime('%Y-%m-%d'),
                        'Hora': pd.to_datetime(df_compras.get(hora_col, "00:00:00"), format='%H:%M:%S', errors='coerce').dt.strftime('%H:%M:%S').fillna("00:00:00"),
                        'MetodoPago': metodo_pago,
                        'Direccion': df_compras.get('Dirección', ''),
                        'Ciudad': df_compras.get('Ciudad', 'SAHAGUN').fillna('SAHAGUN'),
                        'Barrio': df_compras.get('Barrio', 'Desconocido').fillna('Desconocido'),
                        'ClienteCodigo': df_compras['Código cliente'],
                        'DiaRuta': df_compras.get('Ruta', ''),
                        'Vendedor': df_compras.get('Vendedor', df_compras.get('Encargado', '')),
                        'ProductoCodigo': df_compras.get('Código producto', 'VARIOS'),
                        'ProductoNombre': df_compras.get('Producto', 'PRODUCTOS VARIOS (Reporte Cabecera)'),
                        'Cantidad': df_compras.get('Cantidad', df_compras.get('Total items', 1)),
                        'PrecioBase': df_compras.get('Precio base', df_compras.get('Subtotal', df_compras['Total'])),
                        'LineTotal': df_compras['Total']
                    })
                    df_compras_detalle.to_json(dest_dir / 'compras_detalle.json', orient='records', force_ascii=False)

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
                    
                    df_final_clientes.to_json(dest_dir / 'clientes.json', orient='records', force_ascii=False)
                    procesados.append("Órdenes de Compra y Clientes Transaccionales")
                
                # --- REPORTE VENTAS PRODUCTOS ---
                if f_sold_products is not None:
                    try:
                        df_sold = pd.read_excel(f_sold_products)
                        
                        col_codigo = 'Código' if 'Código' in df_sold.columns else ('Codigo' if 'Codigo' in df_sold.columns else None)
                        if not col_codigo:
                            raise KeyError(f"No se encontró la columna 'Código'. Columnas detectadas: {df_sold.columns.tolist()}")
                            
                        df_sold_clean = pd.DataFrame({
                            'CodigoProducto': df_sold[col_codigo],
                            'Nombre': df_sold.get('Nombre', 'Variado'),
                            'CantidadVendida': df_sold.get('Total productos vendidos', df_sold.get('Cantidad', 0)),
                            'PrecioPromedio': df_sold.get('Precio base promedio', df_sold.get('Precio base', 0)),
                            'TotalIngresos': df_sold.get('Total base (sin impuestos)', df_sold.get('Total', 0)),
                            'ClientesDiferentes': df_sold.get('Clientes que compraron', 1)
                        })
                        df_sold_clean.to_json(dest_dir / 'sold_products.json', orient='records', force_ascii=False)
                        procesados.append("Reporte Totalizado de Ventas por Producto")
                    except Exception as e:
                        st.error(f"Error procesando EL REPORTE DE VENTAS (SoldProducts): {e}")
                        raise e
                
                # --- PRODUCTOS ---
                if f_productos is not None:
                    try:
                        df_productos = pd.read_excel(f_productos)
                        df_productos_clean = pd.DataFrame({
                            'Codigo': df_productos['CÓDIGO (Obligatorio)'],
                            'Nombre': df_productos['NOMBRE (Obligatorio)'],
                            'Categoria': df_productos['CÓDIGO CATEGORÍA'],
                            'Precio': df_productos['PRECIO BASE (Obligatorio)'],
                            'Stock': df_productos['CANTIDAD EN INVENTARIO']
                        })
                        df_productos_clean['Categoria'] = df_productos_clean['Categoria'].fillna('Sin Categoria')
                        df_productos_clean['Stock'] = df_productos_clean['Stock'].fillna(0)
                        df_productos_clean.to_json(dest_dir / 'productos.json', orient='records', force_ascii=False)
                        procesados.append("Productos")
                    except Exception as e:
                        st.error(f"Error procesando el archivo de PRODUCTOS. ¿Tiene las columnas esperadas?: {e}")
                        raise e
                
                # --- VENDEDORES ---
                if f_vendedores is not None:
                    try:
                        df_vendedores = pd.read_excel(f_vendedores)
                        df_vendedores_clean = pd.DataFrame({
                            'Codigo': df_vendedores['USUARIO (NUMÉRICO)'],
                            'Nombre': df_vendedores['NOMBRE']
                        })
                        df_vendedores_clean.to_json(dest_dir / 'vendedores.json', orient='records', force_ascii=False)
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
st.subheader("🗑️ Gestión de Lotes Históricos")
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
