import pandas as pd
import glob
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATOS_HISTORICOS_DIR = BASE_DIR / "datos_historicos"
DATOS_TECNICOS_DIR = BASE_DIR / "datos tecnicos"

def consolidar_datos():
    print("🔄 Iniciando proceso de consolidación para estacionalidad...")
    
    # Buscar todos los JSON limpios en las subcarpetas de fechas
    json_files = glob.glob(str(DATOS_HISTORICOS_DIR / "**/*.json"), recursive=True)
    
    if not json_files:
        print("❌ No se encontraron archivos JSON para consolidar.")
        return
        
    print(f"📄 Se detectaron {len(json_files)} archivos de lotes históricos.")
    
    dfs = []
    for f in json_files:
        try:
            df = pd.read_json(f)
            dfs.append(df)
        except Exception as e:
            print(f"⚠️ Error al leer {f}: {e}")
            
    if not dfs:
        print("❌ Ningún dataframe pudo ser procesado.")
        return
        
    print("⏳ Concatenando datos...")
    df_final = pd.concat(dfs, ignore_index=True)
    
    # Asegurar ordenamiento cronológico por fecha de orden y hora
    if 'OrderDate' in df_final.columns and 'Hora' in df_final.columns:
        df_final['OrderDate'] = pd.to_datetime(df_final['OrderDate'])
        df_final = df_final.sort_values(by=['OrderDate', 'Hora'])
        
    # Exportar a CSV final
    DATOS_TECNICOS_DIR.mkdir(parents=True, exist_ok=True)
    output_csv = DATOS_TECNICOS_DIR / "ventas_historicas_2024_2025.csv"
    
    df_final.to_csv(output_csv, index=False)
    print(f"✅ ÉXITO: Base de datos consolidada exportada. Total registros: {len(df_final)}")
    print(f"📂 Archivo disponible en: {output_csv}")

if __name__ == "__main__":
    consolidar_datos()
