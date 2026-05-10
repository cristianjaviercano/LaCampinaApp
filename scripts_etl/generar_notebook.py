import nbformat as nbf
import os
from pathlib import Path

# Configurar rutas
BASE_DIR = Path('/Users/cristianjaviercanomogollon/Documents/Proyectosv2.0/APP LA CAMPIÑA/APP_Lacampiña2.0')
TESIS_DIR = BASE_DIR / 'tesis'
OUTPUT_NOTEBOOK = TESIS_DIR / 'estadisticas.ipynb'

nb = nbf.v4.new_notebook()

cells = []

# Cell 1: Título y Contexto
cells.append(nbf.v4.new_markdown_cell("""# Análisis de Estacionalidad y Demanda (La Campiña 2.0)
**Proyecto de Grado - Ingeniería de Datos y Análisis Estadístico**

Este notebook contiene el análisis exploratorio de datos (EDA) y la implementación de **5 métricas clave** para entender el comportamiento de la demanda logística a través del tiempo (2024, 2025 y proyección 2026).
"""))

# Cell 2: Importaciones
cells.append(nbf.v4.new_code_cell("""import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import warnings
from datetime import datetime

warnings.filterwarnings('ignore')
sns.set_theme(style='darkgrid')
plt.rcParams['figure.figsize'] = (12, 6)
"""))

# Cell 3: Markdown Armonización
cells.append(nbf.v4.new_markdown_cell("""## 1. Carga y Armonización de los Datos
Combinaremos `datos consolidados.csv` (piloto previo) y `ventas_historicas_2024_2025.csv` (data masiva) estandarizando sus columnas."""))

# Cell 4: Carga y limpieza
cells.append(nbf.v4.new_code_cell("""# Rutas
ruta_historico = '../datos tecnicos/ventas_historicas_2024_2025.csv'
ruta_consolidados = '../datos tecnicos/datos consolidados.csv'

# Cargar históricos masivos
df_hist = pd.read_csv(ruta_historico)
# Renombrar para estandarizar
df_hist.rename(columns={
    'PurchaseOrderID': 'PedidoID',
    'OrderDate': 'Fecha',
    'LineTotal': 'TotalVenta'
}, inplace=True)

# Cargar consolidados piloto
df_cons = pd.read_csv(ruta_consolidados)
# Renombrar para estandarizar
df_cons.rename(columns={
    'NoPedido': 'PedidoID',
    'Total': 'TotalVenta'
}, inplace=True)

# Seleccionar columnas de interés comunes para el análisis temporal
cols_base = ['PedidoID', 'Fecha', 'TotalVenta']

df1 = df_hist[cols_base] if set(cols_base).issubset(df_hist.columns) else pd.DataFrame()
df2 = df_cons[cols_base] if set(cols_base).issubset(df_cons.columns) else pd.DataFrame()

# Concatenar dataset maestro
df_master = pd.concat([df1, df2], ignore_index=True)

# Formatear fecha
df_master['Fecha'] = pd.to_datetime(df_master['Fecha'], errors='coerce')
df_master.dropna(subset=['Fecha'], inplace=True)

# Extraer componentes temporales
df_master['Año'] = df_master['Fecha'].dt.year
df_master['Mes'] = df_master['Fecha'].dt.month
df_master['Dia'] = df_master['Fecha'].dt.day
df_master['Quincena'] = np.where(df_master['Dia'] <= 15, 'Q1', 'Q2')

print(f"✅ Total registros en Dataset Maestro: {len(df_master):,}")
print(f"Rango de fechas analizado: Desde {df_master['Fecha'].min().date()} hasta {df_master['Fecha'].max().date()}")
"""))

# Cell 5: Markdown EDA
cells.append(nbf.v4.new_markdown_cell("""## 2. Análisis Exploratorio de Datos (EDA)
Revisemos las ventas totales en el tiempo."""))

# Cell 6: EDA Código
cells.append(nbf.v4.new_code_cell("""# Agrupamiento mensual total de ventas
ventas_mensuales = df_master.groupby(df_master['Fecha'].dt.to_period('M'))['TotalVenta'].sum()

plt.figure(figsize=(14,6))
ventas_mensuales.plot(marker='o', color='#2ecc71')
plt.title('Tendencia de Ventas (Facturación Mínima) a lo largo del tiempo', fontsize=16)
plt.ylabel('Total Volumen Transaccional')
plt.xlabel('Periodo')
plt.grid(True)
plt.tight_layout()
plt.show()
"""))

# Cell 7: Markdown Metrica 1
cells.append(nbf.v4.new_markdown_cell("""## 3. Propuesta de Valor: 5 Métricas de Estacionalidad

### Métrica 1: Índice de Estacionalidad Mensual (IEM)
Mide el peso relativo de cada mes frente al promedio. (Ej: IEM > 1 significa que es un mes de alta demanda logística)."""))

# Cell 8: Codigo IEM
cells.append(nbf.v4.new_code_cell("""# Agrupar por Mes a través de todos los años
volumen_por_mes = df_master.groupby('Mes')['TotalVenta'].mean() # Promedio historico de ese mes
promedio_anual = volumen_por_mes.mean() # La media de todos los meses

iem = (volumen_por_mes / promedio_anual).reset_index()
iem.rename(columns={'TotalVenta': 'IEM'}, inplace=True)

plt.figure(figsize=(10,5))
sns.barplot(data=iem, x='Mes', y='IEM', palette='viridis')
plt.axhline(1, color='red', linestyle='--', label='Promedio Base (IEM = 1.0)')
plt.title('Índice de Estacionalidad Mensual (IEM)')
plt.legend()
plt.show()
iem
"""))

# Cell 9: Markdown Metrica 2
cells.append(nbf.v4.new_markdown_cell("""### Métrica 2: Coeficiente de Variación de la Demanda (CVD)
Mide la volatilidad (Desviación Estándar / Media). Meses con CVD alto son erráticos y logísticamente complejos."""))

# Cell 10: Codigo CVD
cells.append(nbf.v4.new_code_cell("""# Calcular media y std de ventas diarias para cada mes
ventas_diarias = df_master.groupby(['Mes', 'Dia'])['TotalVenta'].sum().reset_index()

cvd_stats = ventas_diarias.groupby('Mes').agg(
    Media=('TotalVenta', 'mean'),
    Std=('TotalVenta', 'std')
).reset_index()

cvd_stats['CVD (%)'] = (cvd_stats['Std'] / cvd_stats['Media']) * 100

plt.figure(figsize=(10,5))
sns.lineplot(data=cvd_stats, x='Mes', y='CVD (%)', marker='s', color='#e74c3c')
plt.title('Volatilidad Logística Mensual (CVD)')
plt.ylabel('Coeficiente de Variación (%)')
plt.show()
cvd_stats[['Mes', 'CVD (%)']].round(2)
"""))

# Cell 11: Markdown Metrica 3
cells.append(nbf.v4.new_markdown_cell("""### Métrica 3: Tasa de Crecimiento Interanual (YoY Growth)
Compara el mismo mes en diferentes años para ver si el negocio escala."""))

# Cell 12: Codigo YoY
cells.append(nbf.v4.new_code_cell("""ventas_año_mes = df_master.groupby(['Año', 'Mes'])['TotalVenta'].sum().unstack(level=0)

# Calcular crecimiento YoY (si tenemos años consecutivos)
try:
    if 2024 in ventas_año_mes.columns and 2025 in ventas_año_mes.columns:
        ventas_año_mes['YoY 24-25 (%)'] = ((ventas_año_mes[2025] - ventas_año_mes[2024]) / ventas_año_mes[2024]) * 100
        
    display(ventas_año_mes.style.format('{:,.0f}', subset=ventas_año_mes.columns[:-1]).format('{:.2f}%', subset=['YoY 24-25 (%)'], na_rep='-'))
except Exception as e:
    print('Datos insuficientes para YoY completo aún.')
    display(ventas_año_mes)
"""))

# Cell 13: Markdown Metrica 4
cells.append(nbf.v4.new_markdown_cell("""### Métrica 4: Estacionalidad del Ticket Medio (ETM)
Evalúa cómo cambia la calidad transaccional de cada visita a lo largo del año."""))

# Cell 14: Codigo ETM
cells.append(nbf.v4.new_code_cell("""# Ticket Medio = Ingresos Totales / Num de Pedidos
tickets_mensuales = df_master.groupby('Mes').agg(
    Ingresos=('TotalVenta', 'sum'),
    Pedidos=('PedidoID', 'count')
)
tickets_mensuales['Ticket Promedio'] = tickets_mensuales['Ingresos'] / tickets_mensuales['Pedidos']

plt.figure(figsize=(10,5))
sns.barplot(x=tickets_mensuales.index, y=tickets_mensuales['Ticket Promedio'], palette='mako')
plt.title('Evolución del Ticket Promedio por Mes')
plt.ylabel('COP')
plt.show()
"""))

# Cell 15: Markdown Metrica 5
cells.append(nbf.v4.new_markdown_cell("""### Métrica 5: Efecto Quincena (Concentración Logística)
El peso del gasto en la primera mitad del mes vs la segunda mitad."""))

# Cell 16: Codigo Efecto Quincena
cells.append(nbf.v4.new_code_cell("""quincenas = df_master.groupby('Quincena')['TotalVenta'].sum()

plt.figure(figsize=(6,6))
plt.pie(quincenas, labels=['Primera Quincena (Q1)', 'Segunda Quincena (Q2)'], autopct='%1.1f%%', colors=['#3498db', '#f1c40f'], startangle=140)
plt.title('Efecto Quincena en la Demanda Logística')
plt.show()

print("Q1 representa los primeros 15 días. Q2 el resto del mes.")
"""))

nb['cells'] = cells

with open(OUTPUT_NOTEBOOK, 'w', encoding='utf-8') as f:
    nbf.write(nb, f)
    
print(f"✅ Notebook estadisticas.ipynb generado en {OUTPUT_NOTEBOOK}")
