import pandas as pd
from utils.data_loader import load_data

data = load_data()
df_det = data['compras_detalle']
df_cli = data['clientes']

df_det['ClienteCodigo'] = df_det['ClienteCodigo'].astype(str)
df_cli['Codigo'] = df_cli['Codigo'].astype(str)

df_left = pd.merge(df_det, df_cli[['Codigo', 'Latitud', 'Longitud']], left_on='ClienteCodigo', right_on='Codigo', how='left')
df_left['Latitud'] = pd.to_numeric(df_left['Latitud'], errors='coerce')

df_jp = df_left[df_left['Vendedor'] == 'JOSE PEREZ']

print("Visitas de JOSE PEREZ sin coordenadas:")
missing = df_jp[df_jp['Latitud'].isnull()]
print(len(missing))
print("Visitas totales JOSE PEREZ:")
print(len(df_jp))

# What days are missing?
print("\nFechas con coordenadas faltantes:")
print(missing['Fecha'].dt.date.value_counts().head(10))
