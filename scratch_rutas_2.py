import pandas as pd
from utils.data_loader import load_data

data = load_data()
df = data['compras_detalle']
df_periodo = df[df['Vendedor'] == 'JOSE PEREZ'].copy()

jornadas = df_periodo.groupby(df_periodo['Fecha'].dt.date)

print(f"Total de jornadas para JOSE PEREZ: {len(jornadas)}")

res = []
for fecha, df_jornada in list(jornadas):
    res.append(str(fecha))

print(res[:15])

