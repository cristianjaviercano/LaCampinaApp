import streamlit as st
import pandas as pd
from pathlib import Path
from utils.data_loader import load_data
from utils.auth import authenticate

# Directorio base del proyecto (absoluto, independiente del CWD)
BASE_DIR = Path(__file__).resolve().parent

st.set_page_config(
    page_title="La Campiña - Sistema de Gestión",
    page_icon=":material/eco:",
    layout="wide",
    initial_sidebar_state="auto", # Responsive behavior for mobiles/tablets
)

# Custom CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"], .stApp {
        font-family: 'Poppins', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
        background-color: #FAFBFF !important;
        color: #292D32 !important;
    }
    
    /* Titles */
    h1 {
        color: #000000 !important;
        font-weight: 600;
        margin-bottom: 24px;
    }

    /* Buttons */
    .stButton>button {
        background-color: #5932EA;
        color: #ffffff;
        border: none;
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.2s ease;
    }
    .stButton>button:hover {
        background-color: #4A2BC4;
        color: #ffffff;
        box-shadow: 0 4px 12px rgba(89, 50, 234, 0.3);
    }
    
    /* Clean Sidebar */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF !important;
        border-right: none !important;
        box-shadow: 4px 0px 24px rgba(0, 0, 0, 0.02) !important;
    }
    div[data-testid="stSidebarNav"] {
        padding-top: 25px;
    }
    
    /* Active Link in Sidebar */
    [data-testid="stSidebarNav"] a[aria-current="page"] {
        background-color: #5932EA !important;
        border-radius: 8px !important;
        margin-left: 16px !important;
        margin-right: 16px !important;
    }
    [data-testid="stSidebarNav"] a[aria-current="page"] span {
        color: #FFFFFF !important;
        font-weight: 500 !important;
    }
    [data-testid="stSidebarNav"] a[aria-current="page"] svg {
        fill: #FFFFFF !important;
        stroke: #FFFFFF !important;
        color: #FFFFFF !important;
    }

    /* Non-active links */
    [data-testid="stSidebarNav"] a:not([aria-current="page"]) span {
        color: #9197B3 !important;
    }
    [data-testid="stSidebarNav"] a:not([aria-current="page"]):hover {
        background-color: #F8F9FF !important;
        border-radius: 8px !important;
        margin-left: 16px !important;
        margin-right: 16px !important;
    }
    
    /* Metric Cards Fix for other views (to reset old dark blue) */
    div[data-testid="stMetric"] {
        background-color: #FFFFFF !important;
        color: #292D32 !important;
        border-radius: 18px;
        padding: 16px 20px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.03) !important;
        border: none !important;
    }
    div[data-testid="stMetric"] label { color: #ACACAC !important; }
    div[data-testid="stMetric"] div { color: #333 !important; }
    
    header { background-color: transparent !important; }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
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
                st.image(str(BASE_DIR / "Logo1.png"), width="stretch")
                
            st.markdown("<h3 style='text-align: center; color: #1d1d1f; font-weight: 600; margin-top: 5px; margin-bottom: 20px;'>Acceso al Sistema</h3>", unsafe_allow_html=True)
            
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
        st.image(str(BASE_DIR / "Logo1.png"), width="stretch")
        
        # Role Badge styling
        user_real_name = st.session_state.user_info.get('name', username_display)
        st.markdown(f"""
        <div style="background: linear-gradient(180deg, #EAABF0 0%, #4623E9 100%); padding: 24px 20px; border-radius: 20px; margin-top: 20px; margin-bottom: 20px; text-align: center; box-shadow: 0 10px 20px rgba(70,35,233,0.2);">
            <div style="font-size: 0.9rem; font-weight: 600; color: #FFFFFF; line-height: 1.4; margin-bottom: 16px;">
                Upgrade to PRO to get<br>access all Features!
            </div>
            <div style="background-color: #FFFFFF; color: #5932EA; padding: 10px; border-radius: 20px; font-weight: 600; font-size: 0.85rem; cursor: pointer; box-shadow: 0 4px 10px rgba(0,0,0,0.1);">
                Get Pro Now!
            </div>
        </div>
        <div style="display: flex; align-items: center; gap: 12px; padding: 10px 0; margin-top: 10px;">
            <div style="width: 42px; height: 42px; border-radius: 50%; background-color: #F8F9FF; display: flex; align-items: center; justify-content: center; font-weight: 600; color: #5932EA; border: 1px solid #EEEEEE;">
                {user_real_name[0].upper() if user_real_name else 'U'}
            </div>
            <div style="display: flex; flex-direction: column;">
                <span style="font-weight: 500; font-size: 0.9rem; color: #292D32; letter-spacing: -0.01em;">{user_real_name}</span>
                <span style="font-size: 0.75rem; color: #757575;">{role}</span>
            </div>
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
        pages.append(st.Page("views/1_📊_Dashboard_General.py", title="Dashboard", icon=":material/bar_chart:"))
    if "Inventario" in user_access:
        pages.append(st.Page("views/2_📦_Inventario.py", title="Inventario", icon=":material/inventory_2:"))
    if "Clientes" in user_access:
        pages.append(st.Page("views/3_👥_Clientes.py", title="Clientes", icon=":material/groups:"))
    if "Rutas" in user_access:
        pass # Fusionado con Preventa
    if "Reporte_Compras" in user_access:
        pages.append(st.Page("views/6_🛒_Reporte_Compras.py", title="Preventa y Entregas", icon=":material/storefront:"))
    if "Preventista" in user_access:
        pages.append(st.Page("views/10_📱_Preventista.py", title="Módulo Preventista", icon=":material/smartphone:"))
    if role in ["ADMINISTRADOR", "DUEÑO"]:
        pages.append(st.Page("views/5_📂_Carga_Datos.py", title="Carga de Datos", icon=":material/cloud_upload:"))
        pages.append(st.Page("views/7_👑_Gestor_Base_Maestra.py", title="Gestor Base Maestra", icon=":material/database:"))
        # El panel análitico gerencial
        pages.append(st.Page("views/8_📈_Analitica_Historica.py", title="Analítica Histórica", icon=":material/trending_up:"))
        pages.append(st.Page("views/9_🧠_Optimizacion_Rutas.py", title="Ingeniería y Rutas", icon=":material/route:"))
        
    if not pages:
        st.warning("Su rol no tiene acceso a ningún módulo.")
        st.stop()

    pg = st.navigation(pages)
    pg.run()
