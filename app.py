import streamlit as st
from pathlib import Path
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
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    /* ── Base ─────────────────────────────────────── */
    html, body, [class*="css"], .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, system-ui, sans-serif !important;
        background-color: #F4F6FB !important;
        color: #111827 !important;
    }

    /* ── Page title — caja blanca ─────────────────── */
    h1 {
        background: #FFFFFF;
        border-radius: 14px;
        padding: 16px 22px !important;
        font-size: 1.3rem !important;
        font-weight: 600 !important;
        color: #111827 !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
        margin-bottom: 4px !important;
    }

    h2 { font-size: 1.05rem !important; font-weight: 600 !important; color: #1F2937 !important; }
    h3 { font-size: 0.92rem !important; font-weight: 600 !important; color: #374151 !important; }

    /* ── Sidebar ──────────────────────────────────── */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF !important;
        border-right: 1px solid #EBEBF0 !important;
        box-shadow: none !important;
    }
    div[data-testid="stSidebarNav"] { padding-top: 16px; }

    [data-testid="stSidebarNav"] a {
        border-radius: 10px;
        margin: 2px 10px;
    }
    [data-testid="stSidebarNav"] a[aria-current="page"] {
        background-color: #EEF2FF !important;
        border-radius: 10px !important;
        margin-left: 10px !important;
        margin-right: 10px !important;
    }
    [data-testid="stSidebarNav"] a[aria-current="page"] span {
        color: #6366F1 !important;
        font-weight: 600 !important;
    }
    [data-testid="stSidebarNav"] a[aria-current="page"] svg {
        fill: #6366F1 !important;
        stroke: #6366F1 !important;
        color: #6366F1 !important;
    }
    [data-testid="stSidebarNav"] a:not([aria-current="page"]) span {
        color: #6B7280 !important;
        font-weight: 400 !important;
    }
    [data-testid="stSidebarNav"] a:not([aria-current="page"]):hover {
        background-color: #F9FAFB !important;
        border-radius: 10px !important;
        margin-left: 10px !important;
        margin-right: 10px !important;
    }

    /* ── Botones ──────────────────────────────────── */
    .stButton > button {
        background-color: #6366F1 !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 10px !important;
        font-family: 'Inter', system-ui, sans-serif !important;
        font-weight: 500 !important;
        font-size: 0.875rem !important;
        padding: 9px 18px !important;
        transition: all 0.15s ease !important;
        box-shadow: 0 1px 3px rgba(99,102,241,0.18) !important;
    }
    .stButton > button:hover {
        background-color: #4F46E5 !important;
        box-shadow: 0 4px 14px rgba(99,102,241,0.32) !important;
        transform: translateY(-1px) !important;
    }
    .stButton > button:active { transform: translateY(0) !important; }

    /* ── Métricas ─────────────────────────────────── */
    div[data-testid="stMetric"] {
        background-color: #FFFFFF !important;
        border-radius: 16px !important;
        padding: 20px 24px !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.05) !important;
        border: none !important;
    }
    div[data-testid="stMetric"] label {
        color: #9CA3AF !important;
        font-size: 0.72rem !important;
        font-weight: 500 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.07em !important;
    }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #111827 !important;
        font-weight: 600 !important;
    }

    /* ── Tabs estilo píldora ──────────────────────── */
    .stTabs [data-baseweb="tab-list"] {
        background: #E8EAF0 !important;
        border-radius: 12px !important;
        padding: 4px !important;
        gap: 2px !important;
        border-bottom: none !important;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 9px !important;
        color: #6B7280 !important;
        font-weight: 500 !important;
        font-size: 0.875rem !important;
        padding: 7px 18px !important;
        border: none !important;
        background: transparent !important;
    }
    .stTabs [aria-selected="true"] {
        background: #FFFFFF !important;
        color: #111827 !important;
        font-weight: 600 !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1) !important;
    }
    .stTabs [data-baseweb="tab-highlight"],
    .stTabs [data-baseweb="tab-border"] { display: none !important; }

    /* ── Inputs ───────────────────────────────────── */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stTextArea > div > div > textarea {
        border: 1.5px solid #E5E7EB !important;
        border-radius: 10px !important;
        background: #FFFFFF !important;
        color: #111827 !important;
        font-family: 'Inter', system-ui, sans-serif !important;
        transition: border-color 0.15s, box-shadow 0.15s !important;
    }
    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: #6366F1 !important;
        box-shadow: 0 0 0 3px rgba(99,102,241,0.12) !important;
    }
    .stSelectbox > div > div > div {
        border: 1.5px solid #E5E7EB !important;
        border-radius: 10px !important;
        background: #FFFFFF !important;
    }

    /* ── Progress bar ─────────────────────────────── */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #6366F1, #818CF8) !important;
        border-radius: 8px !important;
    }

    /* ── Expanders ────────────────────────────────── */
    details[data-testid="stExpander"] {
        background: #FFFFFF !important;
        border-radius: 12px !important;
        border: 1px solid #EBEBF0 !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
    }
    details[data-testid="stExpander"] > summary {
        border-radius: 12px !important;
        padding: 13px 18px !important;
        font-weight: 500 !important;
    }

    /* ── Formularios ──────────────────────────────── */
    div[data-testid="stForm"] {
        background: #FFFFFF !important;
        border-radius: 16px !important;
        border: 1px solid #EBEBF0 !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.04) !important;
        padding: 20px 24px !important;
    }

    /* ── Dataframe ────────────────────────────────── */
    .stDataFrame {
        border-radius: 14px !important;
        overflow: hidden !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.05) !important;
    }

    /* ── Alerts ───────────────────────────────────── */
    div[data-testid="stAlert"] {
        border-radius: 12px !important;
        border-left-width: 4px !important;
        border-left-style: solid !important;
        border-top: none !important;
        border-right: none !important;
        border-bottom: none !important;
    }

    /* ── Separadores ──────────────────────────────── */
    hr {
        border: none !important;
        border-top: 1px solid #EBEBF0 !important;
        margin: 20px 0 !important;
    }

    /* ── Chrome de Streamlit ──────────────────────── */
    header { background-color: transparent !important; }
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ----------------- SESSION STATE -----------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_info" not in st.session_state:
    st.session_state.user_info = None

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
        col_logo1, col_logo2, col_logo3 = st.columns([1, 4, 1])
        with col_logo2:
            st.image(str(BASE_DIR / "Logo1.png"), width=140)
        
        # Role Badge styling
        user_real_name = st.session_state.user_info.get('name', username_display)
        st.markdown(f"""
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
    if "Despacho" in user_access or role in ["ADMINISTRADOR", "DUEÑO"]:
        pages.append(st.Page("views/4_🚚_Despacho.py", title="Despacho", icon=":material/local_shipping:"))
    if "Rutas" in user_access:
        pass
    if "Reporte_Compras" in user_access:
        pages.append(st.Page("views/6_🛒_Reporte_Compras.py", title="Preventa", icon=":material/storefront:"))
    if "Preventista" in user_access:
        pages.append(st.Page("views/10_📱_Preventista.py", title="Preventista", icon=":material/smartphone:"))
    if role in ["ADMINISTRADOR", "DUEÑO"]:
        pages.append(st.Page("views/5_📂_Carga_Datos.py", title="Carga de Datos", icon=":material/cloud_upload:"))
        pages.append(st.Page("views/7_👑_Gestor_Base_Maestra.py", title="Base Maestra", icon=":material/database:"))
        pages.append(st.Page("views/11_🎯_Promociones.py", title="Promociones", icon=":material/loyalty:"))
        pages.append(st.Page("views/8_📈_Analitica_Historica.py", title="Analítica", icon=":material/trending_up:"))
        pages.append(st.Page("views/9_🧠_Optimizacion_Rutas.py", title="Rutas", icon=":material/route:"))
        
    if not pages:
        st.warning("Su rol no tiene acceso a ningún módulo.")
        st.stop()

    pg = st.navigation(pages)
    pg.run()
