import streamlit as st
import pandas as pd
from pathlib import Path
from utils.data_loader import load_data
from utils.auth import authenticate

# Directorio base del proyecto (absoluto, independiente del CWD)
BASE_DIR = Path(__file__).resolve().parent

st.set_page_config(
    page_title="La Campiña - Sistema de Gestión",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="auto", # Responsive behavior for mobiles/tablets
)

# Custom CSS
st.markdown("""
<style>
    h1 {
        background: -webkit-linear-gradient(45deg, #2e7d32, #81c784);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        margin-bottom: 20px;
    }
    div[data-testid="stSidebarNav"] {
        padding-top: 0px;
    }
</style>
""", unsafe_allow_html=True)

# ----------------- SESSION STATE -----------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_info" not in st.session_state:
    st.session_state.user_info = None
if "fecha_historica" not in st.session_state:
    st.session_state.fecha_historica = None

# ----------------- LOGIN PAGE -----------------
def login_page():
    # Spacer columns to center the login box on desktop, takes full width on mobile naturally
    _, col_center, _ = st.columns([1, 1.2, 1])
    
    with col_center:
        st.markdown("<br><br>", unsafe_allow_html=True)
        with st.container(border=True):
            img_c1, img_c2, img_c3 = st.columns([1, 2, 1])
            with img_c2:
                st.image(str(BASE_DIR / "Logo1.png"), use_container_width=True)
                
            st.markdown("<h3 style='text-align: center; color: #2e7d32; margin-top: 5px; margin-bottom: 20px;'>Acceso al Sistema</h3>", unsafe_allow_html=True)
            
            username = st.text_input("👤 Usuario", placeholder="Ingresa tu ID...")
            password = st.text_input("🔑 Contraseña", type="password", placeholder="Ingresa tu clave...")
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Iniciar Sesión", type="primary", use_container_width=True):
                user = authenticate(username, password)
                if user:
                    # Pass the raw username into the inner dict if not present for ui display
                    user['username'] = username 
                    st.session_state.logged_in = True
                    st.session_state.user_info = user
                    st.rerun()
                else:
                    st.error("❌ Usuario o contraseña incorrectos")

# ----------------- MAIN APP ROUTING -----------------
if not st.session_state.logged_in:
    login_page()
else:
    user_access = st.session_state.user_info['access']
    role = st.session_state.user_info['role']
    username_display = st.session_state.user_info.get('username', role)
    
    # Global Sidebar controls
    with st.sidebar:
        # Tighter layout for sidebar
        st.image(str(BASE_DIR / "Logo1.png"), use_container_width=True)
        
        # Role Badge styling
        badge_color = "#2e7d32" if role in ["ADMINISTRADOR", "DUEÑO"] else "#1565c0"
        st.markdown(f"""
        <div style="background-color: {badge_color}15; padding: 12px; border-radius: 8px; border-left: 5px solid {badge_color}; margin-top: -10px; margin-bottom: 20px;">
            <div style="font-size: 0.75rem; color: #666; text-transform: uppercase; letter-spacing: 0.5px;">Usuario Activo</div>
            <div style="font-size: 1.1rem; font-weight: 800; color: #1a1a1a; margin-top: 2px;">@{username_display.upper()}</div>
            <div style="font-size: 0.85rem; font-weight: 600; color: {badge_color}; margin-top: 4px;">🛡️ Nivel: {role}</div>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user_info = None
            st.rerun()
            
        st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
        
        # Lógica para mostrar estado de la base de datos
        historicos_dir = BASE_DIR / "datos_historicos"
        if historicos_dir.exists():
            fechas_disponibles = sorted([d.name for d in historicos_dir.iterdir() if d.is_dir()], reverse=True)
        else:
            fechas_disponibles = []
            
        if fechas_disponibles:
            st.markdown(f"<div style='background-color:#e8f5e9; padding: 10px; border-radius: 5px; font-size: 0.8rem; color: #2e7d32; text-align: center;'><b>🗃️ Base Consolidada</b><br>{len(fechas_disponibles)} lotes indexados</div>", unsafe_allow_html=True)
        else:
            st.warning("Base de datos vacía.")

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Refrescar Memoria", use_container_width=True):
            st.cache_data.clear()
            st.success("App sincronizada.")
            st.rerun()

    # Define Pages based on roles
    pages = []
    
    if "Dashboard" in user_access:
        pages.append(st.Page("views/1_📊_Dashboard_General.py", title="Dashboard General", icon="📊"))
    if "Inventario" in user_access:
        pages.append(st.Page("views/2_📦_Inventario.py", title="Inventario", icon="📦"))
    if "Clientes" in user_access:
        pages.append(st.Page("views/3_👥_Clientes.py", title="Clientes", icon="👥"))
    if "Rutas" in user_access:
        pass # Fusionado con Preventa
    if "Reporte_Compras" in user_access:
        pages.append(st.Page("views/6_🛒_Reporte_Compras.py", title="Preventa y Entregas", icon="🛒"))
    if role in ["ADMINISTRADOR", "DUEÑO"]:
        pages.append(st.Page("views/5_📂_Carga_Datos.py", title="Carga de Datos", icon="📂"))
        pages.append(st.Page("views/7_👑_Gestor_Base_Maestra.py", title="Gestor Base Maestra", icon="👑"))
        # El panel análitico gerencial
        pages.append(st.Page("views/8_📈_Analitica_Historica.py", title="Analítica Histórica", icon="📈"))
        pages.append(st.Page("views/9_🧠_Optimizacion_Rutas.py", title="Ingeniería y Rutas", icon="🧠"))
        
    if not pages:
        st.warning("Su rol no tiene acceso a ningún módulo.")
        st.stop()

    pg = st.navigation(pages)
    pg.run()
