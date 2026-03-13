import pandas as pd
import json
import os
import numpy as np

base_dir = '../datos de prueba/'

def split_coordinates(coord):
    if pd.isna(coord):
        return pd.Series([None, None])
    parts = str(coord).split(',')
    if len(parts) == 2:
        return pd.Series([float(parts[0].strip()), float(parts[1].strip())])
    return pd.Series([None, None])

def clean_data():
    base_dir = './'
    files = {
        'clientes': 'datos de prueba/CLIENTES.xlsx',
        'compras': 'datos de prueba/PurchaseOrderDetailsReport (12).xlsx',
        'productos': 'datos de prueba/TOMAPEDIDOS_PRODUCTOS (10).xlsx',
        'ubicaciones': 'datos de prueba/UBICACIONES.xlsx',
        'vendedores': 'datos de prueba/VENDEDORES.xlsx'
    }

    # Ubicaciones
    df_ubi = pd.read_excel(base_dir + files['ubicaciones'])
    df_ubi[['Latitud', 'Longitud']] = df_ubi['COORDENADAS'].apply(split_coordinates)
    df_ubi_clean = pd.DataFrame({
        'Cliente': df_ubi['NOMBRE'],
        'Barrio': df_ubi.get('BARRIO', None),
        'DiaVisita': df_ubi.get('DIA_RUTA', None),
        'Latitud': df_ubi['Latitud'],
        'Longitud': df_ubi['Longitud']
    })
    df_ubi_clean.dropna(subset=['Latitud', 'Longitud'], inplace=True)
    df_ubi_clean.to_json(base_dir + 'ubicaciones.json', orient='records', force_ascii=False)

    # Clientes
    df_clientes = pd.read_excel(base_dir + files['clientes'])
    df_clientes_clean = pd.DataFrame({
        'Codigo': df_clientes['CÓDIGO (Obligatorio)'],
        'Nombre': df_clientes['NOMBRE DEL NEGOCIO (Obligatorio)'],
        'Ciudad': df_clientes['CIUDAD'],
        'Categoria': df_clientes['TIPO DE NEGOCIO'],
        'Activo': df_clientes['ACTIVO'],
        'Vendedor': df_clientes.get('VENDEDOR', None)
    })
    
    # Merge with ubicaciones to get Latitud and Longitud and DiaVisita
    df_ubi_clean['NOMBRE_NORM'] = df_ubi_clean['Cliente'].astype(str).str.strip().str.upper()
    df_clientes_clean['NOMBRE_NORM'] = df_clientes_clean['Nombre'].astype(str).str.strip().str.upper()
    
    df_clientes_clean = pd.merge(
        df_clientes_clean,
        df_ubi_clean[['NOMBRE_NORM', 'Barrio', 'DiaVisita', 'Latitud', 'Longitud']],
        on='NOMBRE_NORM',
        how='left'
    )
    df_clientes_clean.drop(columns=['NOMBRE_NORM'], inplace=True)
    df_clientes_clean.to_json(base_dir + 'clientes.json', orient='records', force_ascii=False)

    # Compras
    df_compras = pd.read_excel(base_dir + files['compras'])
    df_compras_clean = pd.DataFrame({
        'PurchaseOrderID': df_compras['No. Pedido'],
        'OrderDate': pd.to_datetime(df_compras['Fecha']).dt.strftime('%Y-%m-%d'),
        'LineTotal': df_compras['Total'],
        'ClienteCodigo': df_compras['Código cliente']
    })
    # Drop duplicates to keep the original aggregated behavior for 'compras.json'
    df_compras_agg = df_compras_clean.groupby('PurchaseOrderID', as_index=False).agg({
        'OrderDate': 'first',
        'LineTotal': 'sum',
        'ClienteCodigo': 'first'
    })
    df_compras_agg.to_json(base_dir + 'compras.json', orient='records', force_ascii=False)

    # Compras Detalle (Línea por línea)
    df_compras_detalle = pd.DataFrame({
        'PurchaseOrderID': df_compras['No. Pedido'],
        'OrderDate': pd.to_datetime(df_compras['Fecha']).dt.strftime('%Y-%m-%d'),
        'ClienteCodigo': df_compras['Código cliente'],
        'DiaRuta': df_compras['Ruta'],
        'Vendedor': df_compras['Vendedor'],
        'ProductoCodigo': df_compras['Código producto'],
        'ProductoNombre': df_compras['Producto'],
        'Cantidad': df_compras['Cantidad'],
        'PrecioBase': df_compras['Precio base'],
        'LineTotal': df_compras['Total']
    })
    df_compras_detalle.to_json(base_dir + 'compras_detalle.json', orient='records', force_ascii=False)

    # Productos
    df_productos = pd.read_excel(base_dir + files['productos'])
    df_productos_clean = pd.DataFrame({
        'Codigo': df_productos['CÓDIGO (Obligatorio)'],
        'Nombre': df_productos['NOMBRE (Obligatorio)'],
        'Categoria': df_productos['CÓDIGO CATEGORÍA'],
        'Precio': df_productos['PRECIO BASE (Obligatorio)'],
        'Stock': df_productos['CANTIDAD EN INVENTARIO']
    })
    # Replace NaN with appropriate defaults to avoid JSON invalid arrays
    df_productos_clean['Categoria'] = df_productos_clean['Categoria'].fillna('Sin Categoria')
    df_productos_clean['Stock'] = df_productos_clean['Stock'].fillna(0)
    df_productos_clean.to_json(base_dir + 'productos.json', orient='records', force_ascii=False)

    # Vendedores
    df_vendedores = pd.read_excel(base_dir + files['vendedores'])
    df_vendedores_clean = pd.DataFrame({
        'Codigo': df_vendedores['USUARIO (NUMÉRICO)'],
        'Nombre': df_vendedores['NOMBRE']
    })
    df_vendedores_clean.to_json(base_dir + 'vendedores.json', orient='records', force_ascii=False)

    print("Success: JSON files created in 'datos de prueba' directory.")

if __name__ == '__main__':
    clean_data()
