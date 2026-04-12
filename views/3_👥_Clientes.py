import streamlit as st
import pandas as pd
import re
from utils.data_loader import load_data

st.set_page_config(page_title="Clientes", page_icon="👥", layout="wide")

# Get user name
user_name = "Evano"
if "user_info" in st.session_state and st.session_state.user_info:
    # Obtener el nombre o usar un fallback
    user_name = st.session_state.user_info.get('name', 'Evano')

# Greetings
st.markdown(f"<h2 style='color: #000000; font-weight: 600; margin-bottom: 30px;'>Hola {user_name} 👋,</h2>", unsafe_allow_html=True)

data = load_data(st.session_state.get("fecha_historica"))
if data is None:
    st.error("No hay datos disponibles.")
    st.stop()

df_clientes = data['clientes'].copy()
df_det = data['compras_detalle'].copy()

# Calculamos Activos para las métricas base
total_clientes = len(df_clientes)
activos_count = 0
porcentaje_activos = 0

if not df_det.empty:
    df_det['Fecha'] = pd.to_datetime(df_det['Fecha'], errors='coerce')
    pedidos_por_cliente = df_det.groupby('ClienteCodigo')['NoPedido'].nunique().reset_index()
    activos_count = len(pedidos_por_cliente)
    porcentaje_activos = (activos_count / total_clientes * 100) if total_clientes > 0 else 0

# ── Tarjetas KPIs HTML ────────────────────────────────────────────────────────
kpi_html = f"""
<div style="display: flex; gap: 20px; text-align: left; margin-bottom: 40px; background-color: #FFFFFF; padding: 25px; border-radius: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.03);">
    
    <!-- Total Customers -->
    <div style="flex: 1; display: flex; align-items: center; gap: 15px; border-right: 1px solid #EEEEEE; padding-right: 20px;">
        <div style="width: 70px; height: 70px; border-radius: 50%; background-color: #E0F4EA; display: flex; align-items: center; justify-content: center;">
            <span style="font-size: 30px;">👥</span>
        </div>
        <div>
            <div style="color: #ACACAC; font-size: 0.85rem; font-weight: 400; margin-bottom: 2px;">Total Customers</div>
            <div style="color: #333333; font-size: 1.8rem; font-weight: 600; line-height: 1;">{total_clientes:,}</div>
            <div style="font-size: 0.75rem; margin-top: 4px; color: #292D32;"><span style="color: #00AC4F; font-weight: 600;">↑ 16%</span> this month</div>
        </div>
    </div>
    
    <!-- Members -->
    <div style="flex: 1; display: flex; align-items: center; gap: 15px; border-right: 1px solid #EEEEEE; padding-right: 20px;">
        <div style="width: 70px; height: 70px; border-radius: 50%; background-color: #E0F4EA; display: flex; align-items: center; justify-content: center;">
            <span style="font-size: 30px;">👤</span>
        </div>
        <div>
            <div style="color: #ACACAC; font-size: 0.85rem; font-weight: 400; margin-bottom: 2px;">Members</div>
            <div style="color: #333333; font-size: 1.8rem; font-weight: 600; line-height: 1;">{activos_count:,}</div>
            <div style="font-size: 0.75rem; margin-top: 4px; color: #292D32;"><span style="color: #DF0404; font-weight: 600;">↓ 1%</span> this month</div>
        </div>
    </div>
    
    <!-- Active Now -->
    <div style="flex: 1; display: flex; align-items: center; gap: 15px;">
        <div style="width: 70px; height: 70px; border-radius: 50%; background-color: #E0F4EA; display: flex; align-items: center; justify-content: center;">
            <span style="font-size: 30px;">🖥️</span>
        </div>
        <div>
            <div style="color: #ACACAC; font-size: 0.85rem; font-weight: 400; margin-bottom: 2px;">Active Now</div>
            <div style="color: #333333; font-size: 1.8rem; font-weight: 600; line-height: 1;">{int(activos_count/max(1,(total_clientes/10)))}</div>
            <div style="display: flex; margin-top: 4px;">
               <!-- Placeholder for overlapping avatars -->
               <div style="width: 20px; height: 20px; border-radius: 50%; background-color: #5932EA; border: 2px solid #FFF;"></div>
               <div style="width: 20px; height: 20px; border-radius: 50%; background-color: #EAABF0; border: 2px solid #FFF; margin-left: -8px;"></div>
               <div style="width: 20px; height: 20px; border-radius: 50%; background-color: #00AC4F; border: 2px solid #FFF; margin-left: -8px;"></div>
            </div>
        </div>
    </div>
</div>
"""
st.markdown(re.sub(r'^[ \t]+', '', kpi_html, flags=re.MULTILINE), unsafe_allow_html=True)

table_header_html = """
<div style="background-color: #FFFFFF; padding: 30px; border-radius: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.03);">
    <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #EEEEEE; padding-bottom: 20px; margin-bottom: 20px;">
        <div>
            <h3 style="margin: 0; color: #000000; font-size: 1.4rem; font-weight: 600;">All Customers</h3>
            <span style="color: #16C098; font-size: 0.85rem;">Active Members</span>
        </div>
    </div>
"""
st.markdown(re.sub(r'^[ \t]+', '', table_header_html, flags=re.MULTILINE), unsafe_allow_html=True)

# Generar filas de la tabla
if not df_clientes.empty:
    # Identificar activos si compraron al menos una vez
    if not df_det.empty:
        df_clientes['CodigoStr'] = df_clientes['Codigo'].astype(str)
        activos_codigos = df_det['ClienteCodigo'].astype(str).unique()
        df_clientes['Activo'] = df_clientes['CodigoStr'].isin(activos_codigos)
    else:
        df_clientes['Activo'] = False
        
    # Limit to top 20 for pure aesthetic CRM list
    df_table = df_clientes.head(20)
    
    table_html = """
    <table style="width: 100%; border-collapse: collapse; font-size: 0.9rem; text-align: left;">
        <thead>
            <tr style="color: #B5B7C0; border-bottom: 1px solid #EEEEEE;">
                <th style="padding: 15px 10px; font-weight: 500;">Customer Name</th>
                <th style="padding: 15px 10px; font-weight: 500;">Company Code</th>
                <th style="padding: 15px 10px; font-weight: 500;">City</th>
                <th style="padding: 15px 10px; font-weight: 500;">Seller</th>
                <th style="padding: 15px 10px; font-weight: 500; text-align: center;">Status</th>
            </tr>
        </thead>
        <tbody>
    """
    
    for _, row in df_table.iterrows():
        nombre = row.get('Nombre', 'N/A')
        codigo = row.get('Codigo', 'N/A')
        ciudad = row.get('Ciudad', 'Sahagún')
        vendedor = row.get('Vendedor', 'N/A')
        is_active = row.get('Activo', False)
        
        if is_active:
            status_badge = '<div style="background-color: #16c09833; color: #008767; border: 1px solid #00B087; padding: 4px 12px; border-radius: 4px; display: inline-block; font-weight: 500; font-size: 0.8rem;">Active</div>'
        else:
            status_badge = '<div style="background-color: #FFC5C5; color: #DF0404; border: 1px solid #DF0404; padding: 4px 12px; border-radius: 4px; display: inline-block; font-weight: 500; font-size: 0.8rem;">Inactive</div>'
            
        table_html += f"""
            <tr style="border-bottom: 1px solid #EEEEEE; color: #292D32; font-weight: 500;">
                <td style="padding: 15px 10px;">{nombre}</td>
                <td style="padding: 15px 10px;">{codigo}</td>
                <td style="padding: 15px 10px;">{ciudad}</td>
                <td style="padding: 15px 10px;">{vendedor}</td>
                <td style="padding: 15px 10px; text-align: center;">{status_badge}</td>
            </tr>
        """
        
    table_html += """
        </tbody>
    </table>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 30px; color: #B5B7C0; font-size: 0.85rem;">
        <span>Showing data 1 to 20 of 256K entries</span>
        <div style="display: flex; gap: 5px;">
            <div style="padding: 5px 10px; border-radius: 4px; background-color: #F5F5F5; color: #333; cursor: pointer;">&lt;</div>
            <div style="padding: 5px 10px; border-radius: 4px; background-color: #5932EA; color: #FFF; cursor: pointer;">1</div>
            <div style="padding: 5px 10px; border-radius: 4px; background-color: #F5F5F5; color: #333; cursor: pointer;">2</div>
            <div style="padding: 5px 10px; border-radius: 4px; background-color: #F5F5F5; color: #333; cursor: pointer;">3</div>
            <div style="padding: 5px 10px; border-radius: 4px; background-color: #F5F5F5; color: #333; cursor: pointer;">...</div>
            <div style="padding: 5px 10px; border-radius: 4px; background-color: #F5F5F5; color: #333; cursor: pointer;">40</div>
            <div style="padding: 5px 10px; border-radius: 4px; background-color: #F5F5F5; color: #333; cursor: pointer;">&gt;</div>
        </div>
    </div>
    """
    
    st.markdown(re.sub(r'^[ \t]+', '', table_html, flags=re.MULTILINE), unsafe_allow_html=True)
else:
    st.info("No hay clientes registrados.")

st.markdown("</div>", unsafe_allow_html=True)
