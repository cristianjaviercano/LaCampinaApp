import pandas as pd
from utils.data_loader import load_data

data = load_data()
df = data['compras_detalle']

print(df[df['Vendedor'] == 'JOSE PEREZ'][['Fecha', 'Ruta']].drop_duplicates().head(20))
