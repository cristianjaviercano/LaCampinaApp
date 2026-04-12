import pandas as pd
from utils.data_loader import load_data

data = load_data()
df = data['compras_detalle']
df_periodo = df[df['Vendedor'] == 'JOSE PEREZ'].copy()

jornadas = df_periodo.groupby(df_periodo['Fecha'].dt.date)
for fecha, df_jornada in list(jornadas)[:3]:
    if 'Hora' in df_jornada.columns:
        df_jornada = df_jornada.sort_values('Hora')
        
    visitas = df_jornada.drop_duplicates(subset=['ClienteCodigo']).copy()
    print(f"Jornada {fecha}: {len(visitas)} visitas. Horas válidas: {df_jornada['Hora'].notnull().sum()}")
    
    tiempo_promedio = 0
    temp_col = 'Hora'
    temp = df_jornada.dropna(subset=[temp_col]).sort_values(temp_col)
    
    # Prepend an arbitrary date to the time so pd.to_datetime parses it directly as a timedelta sequence
    date_str = pd.to_datetime(fecha).strftime('%Y-%m-%d ')
    time_series = pd.to_datetime(date_str + temp[temp_col], errors='coerce')
    
    diffs = time_series.diff().dt.total_seconds() / 60
    diffs = diffs[diffs > 0]
    if not diffs.empty:
        tiempo_promedio = diffs.mean()
        
    print(f"-> Promedio de tiempo entre pedido: {tiempo_promedio:.2f} minutos")

