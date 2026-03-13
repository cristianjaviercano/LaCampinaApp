import pandas as pd
import json
from pathlib import Path
import warnings

warnings.simplefilter("ignore")

def split_coordinates(coord):
    if pd.isna(coord):
        return pd.Series([None, None])
    parts = str(coord).split(',')
    if len(parts) == 2:
        return pd.Series([float(parts[0].strip()), float(parts[1].strip())])
    return pd.Series([None, None])

maestro_path = Path('datos_maestros/clientes_maestro.json')
nuevo_excel = "datos de prueba/Ubicaciones_tiendas.xlsx"

df_maestro = pd.read_json(maestro_path)
df_ubi = pd.read_excel(nuevo_excel)

df_ubi[['Latitud', 'Longitud']] = df_ubi['COORDENADAS'].apply(split_coordinates)

df_ubi_clean = pd.DataFrame({
    'Nombre_nuevo': df_ubi['NOMBRE'],
    'Barrio_nuevo': df_ubi.get('BARRIO', None),
    'DiaVisita_nuevo': df_ubi.get('DIA_RUTA', None),
    'Latitud_nueva': df_ubi['Latitud'],
    'Longitud_nueva': df_ubi['Longitud']
})

df_ubi_clean['NOMBRE_NORM'] = df_ubi_clean['Nombre_nuevo'].astype(str).str.strip().str.upper()
df_maestro['NOMBRE_NORM'] = df_maestro['Nombre'].astype(str).str.strip().str.upper()

# Merge
df_merge = pd.merge(df_maestro, df_ubi_clean.drop_duplicates(subset=['NOMBRE_NORM']), on='NOMBRE_NORM', how='left')

# Update logic
df_merge['Latitud'] = df_merge['Latitud_nueva'].combine_first(df_merge['Latitud'])
df_merge['Longitud'] = df_merge['Longitud_nueva'].combine_first(df_merge['Longitud'])

if 'Barrio_nuevo' in df_merge.columns:
    df_merge['Barrio'] = df_merge['Barrio_nuevo'].combine_first(df_merge['Barrio'])
if 'DiaVisita_nuevo' in df_merge.columns:
    df_merge['DiaVisita'] = df_merge['DiaVisita_nuevo'].combine_first(df_merge['DiaVisita'])

cols_to_drop = [c for c in df_merge.columns if '_nueva' in c or '_nuevo' in c] + ['NOMBRE_NORM']
df_merge.drop(columns=cols_to_drop, inplace=True, errors='ignore')

# Add new ones
nuevos_clientes = df_ubi_clean[~df_ubi_clean['NOMBRE_NORM'].isin(df_maestro['NOMBRE_NORM'])]
if not nuevos_clientes.empty:
    max_id = len(df_maestro)
    df_nuevos = pd.DataFrame({
        'Codigo': "NEW-" + pd.Series(range(max_id + 1, max_id + 1 + len(nuevos_clientes))).astype(str),
        'Nombre': nuevos_clientes['Nombre_nuevo'],
        'Ciudad': 'SAHAGUN',
        'Activo': 1,
        'Barrio': nuevos_clientes['Barrio_nuevo'],
        'DiaVisita': nuevos_clientes['DiaVisita_nuevo'],
        'Latitud': nuevos_clientes['Latitud_nueva'],
        'Longitud': nuevos_clientes['Longitud_nueva']
    })
    df_merge = pd.concat([df_merge, df_nuevos], ignore_index=True)

df_merge.to_json(maestro_path, orient='records', force_ascii=False, indent=4)
print(f"Merge Exitoso! Añadidos {len(nuevos_clientes)} clientes nuevos al Maestro.")
