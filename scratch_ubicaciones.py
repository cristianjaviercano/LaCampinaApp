import pandas as pd
from utils.data_loader import load_data

data = load_data()
df_ub = data['ubicaciones']
print('Ubicaciones cargadas:', df_ub.columns, len(df_ub))

df_cli = data['clientes']
print('Clientes con Lats:', df_cli['Latitud'].notnull().sum())

# Were the coordinates collected somewhere else?
