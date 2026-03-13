import pandas as pd
from utils.data_loader import load_data

data = load_data("2026-03-01")
df_clientes = data['clientes']
df_compras_detalle = data['compras_detalle']

print("Before:")
print("Vendedores count:", df_clientes['Vendedor'].nunique())
print("DiaVisita count:", df_clientes.get('DiaVisita', pd.Series()).nunique())

# Enrichment logic
if not df_compras_detalle.empty:
    rutas_compras = df_compras_detalle.sort_values('OrderDate').drop_duplicates(subset=['ClienteCodigo'], keep='last')[['ClienteCodigo', 'Vendedor', 'DiaRuta']]
    df_clientes = pd.merge(df_clientes, rutas_compras, left_on='Codigo', right_on='ClienteCodigo', how='left', suffixes=('_old', '_new'))
    
    df_clientes['Vendedor'] = df_clientes['Vendedor_new'].combine_first(df_clientes['Vendedor_old'])
    df_clientes['DiaVisita'] = df_clientes['DiaRuta'].combine_first(df_clientes.get('DiaVisita_old', pd.Series()))

print("After:")
print("Vendedores count:", df_clientes['Vendedor'].nunique())
print("DiaVisita count:", df_clientes['DiaVisita'].nunique())
