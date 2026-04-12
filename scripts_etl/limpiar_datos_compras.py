import pandas as pd
import json
import os
import glob
from pathlib import Path

# Paths relative to the script
BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_DIR = BASE_DIR.parent / "datosdeventas"
OUTPUT_DIR = BASE_DIR / "datos_historicos"

# Configuration Mapping from Excel Column to JSON Schema
COLUMN_MAPPING = {
    "No. Pedido": "PurchaseOrderID",
    "Fecha": "OrderDate",
    "Hora": "Hora",
    "Método de pago": "MetodoPago",
    "Dirección": "Direccion",
    "Ciudad": "Ciudad",
    "Barrio": "Barrio",
    "Código cliente": "ClienteCodigo",
    "Ruta": "DiaRuta",
    "Vendedor": "Vendedor",
    "Código producto": "ProductoCodigo",
    "Producto": "ProductoNombre",
    "Cantidad": "Cantidad",
    "Precio base": "PrecioBase",
    "Total": "LineTotal"
}

def clean_sales_data(input_file):
    print(f"🔄 Procesando archivo crudo: {Path(input_file).name}")
    
    try:
        # 1. Leer Excel
        df = pd.read_excel(input_file)
        original_len = len(df)
        print(f"📄 Datos originales escaneados: {original_len} filas.")
    except Exception as e:
        print(f"❌ Error al leer el Excel {input_file}: {e}")
        return False
    
    # 2. Filtrar Columnas e Interceptar Mapa
    cols_to_keep = [c for c in COLUMN_MAPPING.keys() if c in df.columns]
    df = df[cols_to_keep].rename(columns=COLUMN_MAPPING)

    missing_cols = set(COLUMN_MAPPING.values()) - set(df.columns)
    if missing_cols:
         print(f"⚠️ Faltan columnas en el reporte tras mapeo: {missing_cols}")
         for col in missing_cols:
             df[col] = "INDEFINIDO"
    
    # 3. Limpieza Estricta Geográfica (Sahagún Only)
    df["Ciudad_Raw"] = df["Ciudad"].astype(str).str.upper().str.strip()
    df["Ciudad_Raw"] = df["Ciudad_Raw"].str.replace("Á", "A").str.replace("É", "E").str.replace("Í", "I").str.replace("Ó", "O").str.replace("Ú", "U")
    
    df = df[df["Ciudad_Raw"] == "SAHAGUN"].copy()
    df.drop(columns=["Ciudad_Raw"], inplace=True)
    sahagun_len = len(df)
    print(f"📌 Filtro Geográfico (Sahagún): Se aislaron {sahagun_len} registros.")

    if df.empty:
        print("❌ No se encontraron transacciones en Sahagún en este archivo. Omientiendo carga.")
        return False
        
    # 4. Formatear Fechas (Transformación del Error de 1970)
    # OrderDate -> a formato YYYY-MM-DD string puro
    df["OrderDate"] = pd.to_datetime(df["OrderDate"], errors="coerce").dt.strftime("%Y-%m-%d")
    
    # Hora -> a formato HH:MM:SS string puro omitiendo las fechas base de excel
    df["Hora"] = pd.to_datetime(df["Hora"], errors="coerce").dt.strftime("%H:%M:%S")

    # Eliminar posibles nulos irreparables en fecha
    df = df.dropna(subset=["OrderDate"])
    
    # Sanear valores numericos
    df['Cantidad'] = pd.to_numeric(df['Cantidad'], errors='coerce').fillna(0).astype(int)
    df['LineTotal'] = pd.to_numeric(df['LineTotal'], errors='coerce').fillna(0).astype(float)
    df['PrecioBase'] = pd.to_numeric(df['PrecioBase'], errors='coerce').fillna(0).astype(float)

    # 5. Deducir carpeta (lote) usando la fecha más reciente de cobro
    fechas_validas = df["OrderDate"].dropna().unique()
    if len(fechas_validas) > 0:
        max_date = sorted(fechas_validas)[-1]
    else:
        print("❌ Tras limpieza, no quedaron fechas válidas procesables. Abortado.")
        return False

    # 6. Exportar Lote
    target_folder = OUTPUT_DIR / max_date
    target_folder.mkdir(parents=True, exist_ok=True)
    target_file = target_folder / "compras_detalle.json"

    # Save to JSON
    df.to_json(target_file, orient="records", date_format="iso", force_ascii=False, indent=4)
    print(f"✅ ÉXITO: {sahagun_len} transacciones limpias de Sahagún se inyectaron en el Data Layer -> {target_file}")
    return True

def procesar_lote_completo():
    if not INPUT_DIR.exists():
        print(f"❌ La carpeta de entrada no existe: {INPUT_DIR}")
        return
        
    archivos_excel = glob.glob(str(INPUT_DIR / "*.xlsx"))
    if not archivos_excel:
        print(f"⚠️ No hay archivos .xlsx hallados en {INPUT_DIR}")
        return
        
    for file_path in archivos_excel:
        clean_sales_data(file_path)

if __name__ == "__main__":
    print(f"--- INICIANDO LAVADORA DE DATOS (ETL) LA CAMPIÑA ---")
    procesar_lote_completo()
