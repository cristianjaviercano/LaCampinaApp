import pandas as pd
from utils.data_loader import load_data

data = load_data()
df = data['compras_detalle']
df_jp = df[df['Vendedor'] == 'JOSE PEREZ']

fechas_jp = df_jp['Fecha'].dt.date.value_counts().sort_index()
print("Fechas de JOSE PEREZ:")
print(fechas_jp)

fechas_todos = df['Fecha'].dt.date.value_counts().sort_index()
print("\nFechas Totales en el DB:")
print(fechas_todos.head(15))
