import pandas as pd
import json
import os

def exportar_csv_y_metricas():
    archivo_json = "datos_maestros/compras_maestras.json"
    archivo_csv = "datos tecnicos/datos consolidados.csv"
    
    print("Cargando maestro de datos...")
    try:
        with open(archivo_json, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error cargando JSON: {e}")
        return
        
    df = pd.DataFrame(data)
    df.to_csv(archivo_csv, index=False, encoding='utf-8')
    print(f"✅ CSV exportado con éxito en: {archivo_csv}")
    print(f"Filas totales: {len(df)}")
    
    # --- EDA Y OEE ---
    print("\n--- ANALISIS ESTADISTICO / EDA ---")
    
    # Fechas
    df['Fecha'] = pd.to_datetime(df['Fecha'], format='mixed')
    print(f"Rango de Fechas: {df['Fecha'].min().date()} a {df['Fecha'].min().date()}")
    
    # 1. Ventas por Vendedor
    ventas_vendedor = df.groupby("Vendedor")["Total"].sum().sort_values(ascending=False)
    print("\nVentas Totales por Vendedor:")
    print(ventas_vendedor)
    
    # 2. Clientes Unicos por Vendedor por Dia
    rutas_por_vendedor = df.groupby(["Vendedor", "Fecha"])["ClienteCodigo"].nunique().reset_index()
    promedio_clientes_dia = rutas_por_vendedor.groupby("Vendedor")["ClienteCodigo"].mean()
    print("\nPromedio Clientes Visitados por Día por Vendedor:")
    print(promedio_clientes_dia)
    
    # 3. Metodo de Pago
    pagos = df.groupby("MetodoPago")["Total"].sum()
    print("\nIngresos por Método de Pago:")
    print(pagos)
    
    # 4. Cálculo de OEE Mensual General
    print("\n--- CALCULO OEE MENSUAL (APROXIMADO) ---")
    # Disponibilidad: Asumiendo una jornada de 8 horas. Como no tenemos tiempo de fin vs inicio exacto en todos, 
    # promediemos que trabajan 7.5 hrs. (Ajuste teorico para la tesis basado en la metadata que vi).
    # Rendimiento: Meta de 50 clientes diarios.
    # Calidad: Ticket promedio vs Meta de $500,000 COP (?) 
    
    # Vamos a calcular el ticket promedio global
    ticket_promedio = df.groupby(["Fecha", "ClienteCodigo"])["Total"].sum().mean()
    meta_ticket = 250000 # Asumamos meta 250k
    calidad = min(ticket_promedio / meta_ticket, 1.0)
    
    # Rendimiento
    clientes_promedio_general = rutas_por_vendedor["ClienteCodigo"].mean()
    meta_clientes = 60 # Asumamos meta 60
    rendimiento = min(clientes_promedio_general / meta_clientes, 1.0)
    
    disponibilidad = 0.9 # Suposición de 90% disponibilidad de horas efectivas para el ejemplo OEE
    oee = disponibilidad * rendimiento * calidad
    
    print(f"Ticket Promedio de Compra: ${ticket_promedio:,.0f}")
    print(f"Clientes/Dia promedio: {clientes_promedio_general:.1f}")
    print(f"Disponibilidad (Asumida): {disponibilidad*100:.1f}%")
    print(f"Rendimiento: {rendimiento*100:.1f}%")
    print(f"Calidad: {calidad*100:.1f}%")
    print(f"OEE Global Estimado: {oee*100:.1f}%")
    
if __name__ == '__main__':
    exportar_csv_y_metricas()
