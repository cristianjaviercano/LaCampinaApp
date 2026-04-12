import pandas as pd
from utils.data_loader import load_data

data = load_data()
df_det = data['compras_detalle']
df_cli = data['clientes']

df_det['ClienteCodigo'] = df_det['ClienteCodigo'].astype(str)
df_cli['Codigo'] = df_cli['Codigo'].astype(str)

df_full = pd.merge(df_det, df_cli[['Codigo', 'Nombre', 'Latitud', 'Longitud', 'Barrio']], 
                   left_on='ClienteCodigo', right_on='Codigo', how='inner')
df_full['Latitud'] = pd.to_numeric(df_full['Latitud'], errors='coerce')
df_full['Longitud'] = pd.to_numeric(df_full['Longitud'], errors='coerce')
df_full = df_full.dropna(subset=['Latitud', 'Longitud'])

df_jp = df_full[df_full['Vendedor'] == 'JOSE PEREZ']
jornadas = df_jp.groupby(df_jp['Fecha'].dt.date)

print(f"Total de jornadas (con Lat/Lon) para JOSE PEREZ: {len(jornadas)}")
fechas = [str(f) for f, d in list(jornadas)]
print("Fechas renderizadas:")
print(fechas[:20])
