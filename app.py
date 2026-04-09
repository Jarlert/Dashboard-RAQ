import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import pytz 
from streamlit_autorefresh import st_autorefresh 
from googleapiclient.discovery import build
from google.oauth2 import service_account

# 1. CONFIGURACIÓN DE PÁGINA Y AUTO-REFRESCO (Cada 60 seg)
st.set_page_config(page_title="FIBRA RAQ | Pro Dashboard", layout="wide")
st_autorefresh(interval=60000, key="datarefresh")

# --- CONFIGURACIÓN HORA VENEZUELA ---
vzla_tz = pytz.timezone('America/Caracas')
ahora_vzla = datetime.now(vzla_tz)
hoy_vzla = ahora_vzla.date()
ayer_vzla = hoy_vzla - timedelta(days=1)

# 2. ESTILO CSS DARK PREMIUM
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap');
    .stApp { background-color: #0e1117; color: #ffffff; font-family: 'Poppins', sans-serif; }
    .section-title { color: #ffffff !important; font-size: 22px; font-weight: 600; margin-top: 30px; margin-bottom: 15px; border-left: 5px solid #00d4ff; padding-left: 15px; }
    .metric-container { background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); padding: 20px; border-radius: 15px; text-align: center; }
    .m-label { color: #8899a6; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; }
    .m-value { color: #ffffff; font-size: 32px; font-weight: 700; margin: 5px 0; }
    .m-sub { color: #00d4ff; font-size: 11px; font-weight: 400; }
    .month-row { display: flex; justify-content: space-between; padding: 12px 15px; background: rgba(255, 255, 255, 0.03); margin-bottom: 5px; border-radius: 8px; color: #ffffff !important; }
    p, span, label { color: #ffffff !important; }
    </style>
    """, unsafe_allow_html=True)

# 3. CARGA DE DATOS (Tu lógica de éxito intacta para los 237 de febrero)
@st.cache_data(ttl=5)
def load_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(worksheet="Base de Datos ", ttl=0) 
    df = df.dropna(subset=["Marca temporal"], how='all')
    
    # --- LA CLAVE PARA LOS 237 DE FEBRERO (Sin tocar) ---
    df['Fecha_DT'] = pd.to_datetime(df["Marca temporal"], format='%d/%m/%Y', exact=False, errors='coerce')
    df['Fecha_Limpia'] = df['Fecha_DT'].dt.date
    
    # Limpieza de números
    df['Metraje'] = pd.to_numeric(df['Metros '], errors='coerce').fillna(0)
    df['Tensores'] = pd.to_numeric(df['Tensores'], errors='coerce').fillna(0)
    
    return df

# 4. FUNCIÓN PARA CONTAR COLORES (Validación Ultra-Estricta de contenido)
@st.cache_data(ttl=30)
def load_asignados_counts():
    try:
        creds_info = st.secrets["connections"]["gsheets"]
        creds = service_account.Credentials.from_service_account_info(creds_info)
        service = build('sheets', 'v4', credentials=creds)
        
        spreadsheet_id = "1KK1Ng6lF-dGSzOt46kVsqAnY0MG4v-Ggp4S8x1IZokQ"
        range_name = "ASIGNADOS!B:B" # Columna B (Plan)
        
        result = service.spreadsheets().get(
            spreadsheetId=spreadsheet_id, 
            ranges=[range_name], 
            includeGridData=True
        ).execute()
        
        rows = result['sheets'][0]['data'][0].get('rowData', [])
        blancos = 0
        grises = 0
        
        for row in rows:
            cells = row.get('values', [])
            if not cells: continue
            
            cell_b = cells[0]
            
            # CAPA 1: Si no hay valor efectivo (contenido real), ignorar.
            eff_val = cell_b.get('effectiveValue', {})
            if not eff_val: 
                continue
            
            # CAPA 2: Extraer el texto y verificar que no sea solo espacios.
            # Buscamos en stringValue o numberValue (por si el plan es un número)
            val_texto = str(eff_val.get('stringValue', eff_val.get('numberValue', ''))).strip()
            if not val_texto or val_texto == "":
                continue

            # CAPA 3: Si pasó los filtros, tiene texto. Ahora miramos el color.
            bg = cell_b.get('effectiveFormat', {}).get('backgroundColor', {})
            r = bg.get('red', 1.0)
            g = bg.get('green', 1.0)
            b = bg.get('blue', 1.0)
            
            # Gris: Tonalidades equilibradas por debajo de 0.95
            if r < 0.95 and abs(r - g) < 0.03 and abs(g - b) < 0.03:
                grises += 1
            else:
                blancos += 1
        
        return blancos, grises
    except Exception as e:
        return 0, 0

try:
    df = load_data()
    pend_realizar, pend_adecuacion = load_asignados_counts()
    
    # Lógica de Semanas (Jueves a Miércoles)
    def get_jueves(d):
        return d - timedelta(days=(d.isoweekday() - 4) % 7)

    inicio_sem_actual = get_jueves(hoy_vzla)
    fin_sem_actual = inicio_sem_actual + timedelta(days=6)
    inicio_sem_pasada = inicio_sem_actual - timedelta(days=7)
    fin_sem_pasada = inicio_sem_actual - timedelta(days=1)

    # --- HEADER ---
    st.markdown("<h1 style='text-align: center; color: white;'>💎 FIBRA RAQ INTELLIGENCE</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align: center; color: #00d4ff;'>Reloj Venezuela: {ahora_vzla.strftime('%d/%m/%Y %I:%M %p')}</p>", unsafe_allow_html=True)

    # --- SECCIÓN 1: RENDIMIENTO OPERATIVO ---
    st.markdown("<div class='section-title'>Rendimiento Operativo</div>", unsafe_allow_html=True)
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        val_hoy = len(df[df['Fecha_Limpia'] == hoy_vzla])
        st.markdown(f"<div class='metric-container'><div class='m-label'>Hoy</div><div class='m-value'>{val_hoy}</div><div class='m-sub'>Instalaciones</div></div>", unsafe_allow_html=True)
    with k2:
        val_ayer = len(df[df['Fecha_Limpia'] == ayer_vzla])
        st.markdown(f"<div class='metric-container'><div class='m-label'>Ayer</div><div class='m-value'>{val_ayer}</div><div class='m-sub'>Instalaciones</div></div>", unsafe_allow_html=True)
    with k3:
        val_sem = len(df[(df['Fecha_Limpia'] >= inicio_sem_actual) & (df['Fecha_Limpia'] <= fin_sem_actual)])
        st.markdown(f"<div class='metric-container'><div class='m-label'>Semana Actual</div><div class='m-value'>{val_sem}</div><div class='m-sub'>{inicio_sem_actual.strftime('%d/%m')} al {fin_sem_actual.strftime('%d/%m')}</div></div>", unsafe_allow_html=True)
    with k4:
        val_pas = len(df[(df['Fecha_Limpia'] >= inicio_sem_pasada) & (df['Fecha_Limpia'] <= fin_sem_pasada)])
        st.markdown(f"<div class='metric-container'><div class='m-label'>Semana Pasada</div><div class='m-value'>{val_pas}</div><div class='m-sub'>{inicio_sem_pasada.strftime('%d/%m')} al {fin_sem_pasada.strftime('%d/%m')}</div></div>", unsafe_allow_html=True)

    # --- SECCIÓN: ESTADO DE ASIGNACIONES (Cuadros solicitados) ---
    st.markdown("<div class='section-title'>Estado de Asignaciones</div>", unsafe_allow_html=True)
    a1, a2, a3, a4 = st.columns(4)
    with a1:
        st.markdown(f"<div class='metric-container'><div class='m-label'>Tendidos Pendientes por realizar</div><div class='m-value'>{pend_realizar}</div><div class='m-sub'>Blancas con Texto</div></div>", unsafe_allow_html=True)
    with a2:
        st.markdown(f"<div class='metric-container'><div class='m-label'>Pendientes por Adecuación o Caja</div><div class='m-value'>{pend_adecuacion}</div><div class='m-sub'>Grises con Texto</div></div>", unsafe_allow_html=True)

    # --- SECCIÓN EFICIENCIA (Promedios) ---
    st.markdown("<div class='section-title'>Eficiencia de Materiales</div>", unsafe_allow_html=True)
    e1, e2, e3, e4 = st.columns(4)
    total_inst = len(df) if len(df) > 0 else 1
    media_metros = df['Metraje'].sum() / total_inst
    media_tensores = df['Tensores'].sum() / total_inst
    with e1:
        st.markdown(f"<div class='metric-container'><div class='m-label'>Media Metros</div><div class='m-value'>{media_metros:.2f}</div><div class='m-sub'>Mts por instalación</div></div>", unsafe_allow_html=True)
    with e2:
        st.markdown(f"<div class='metric-container'><div class='m-label'>Media Tensores</div><div class='m-value'>{media_tensores:.2f}</div><div class='m-sub'>Und por instalación</div></div>", unsafe_allow_html=True)

    # --- SECCIÓN 2: PRODUCTIVIDAD ---
    st.markdown("<div class='section-title'>Productividad de Técnicos</div>", unsafe_allow_html=True)
    tech_cols = df.iloc[:, 22:25].values.flatten()
    tech_counts = pd.Series(tech_cols).dropna().astype(str).str.strip().value_counts().reset_index()
    tech_counts.columns = ['Técnico', 'Servicios']
    tech_counts = tech_counts[~tech_counts['Técnico'].isin(["", "None", "nan", "NaN", "0", "0.0"])].head(12)
    fig_tech = px.bar(tech_counts, x='Servicios', y='Técnico', orientation='h', text_auto=True, color='Servicios', color_continuous_scale='Blues')
    fig_tech.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color="white", height=450, margin=dict(l=0,r=0,t=0,b=0))
    st.plotly_chart(fig_tech, use_container_width=True)

    # --- SECCIÓN 3: HISTORIAL ---
    st.markdown("<div class='section-title'>Análisis Histórico</div>", unsafe_allow_html=True)
    c1, c2 = st.columns([1, 2])
    with c1:
        df_hist = df.dropna(subset=['Fecha_DT']).copy()
        df_hist = df_hist[df_hist['Fecha_DT'].dt.date <= hoy_vzla]
        df_hist['Mes_Num'] = df_hist['Fecha_DT'].dt.month
        df_hist['Año'] = df_hist['Fecha_DT'].dt.year.astype(int)
        meses_n = {1:'Enero', 2:'Febrero', 3:'Marzo', 4:'Abril', 5:'Mayo', 6:'Junio', 7:'Julio', 8:'Agosto', 9:'Septiembre', 10:'Octubre', 11:'Noviembre', 12:'Diciembre'}
        df_hist['Mes_Nombre'] = df_hist['Mes_Num'].map(meses_n)
        hist = df_hist.groupby(['Año', 'Mes_Num', 'Mes_Nombre']).size().reset_index(name='Total').sort_values(['Año', 'Mes_Num'], ascending=False)
        st.write("📂 **Cierre Mensual**")
        for _, row in hist.iterrows():
            st.markdown(f"<div class='month-row'><span>{row['Mes_Nombre']} {int(row['Año'])}</span><span style='color:#00d4ff; font-weight:bold;'>{row['Total']}</span></div>", unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div style='background: linear-gradient(135deg, #00d4ff 0%, #0072ff 100%); padding: 40px; border-radius: 20px; text-align: center; color: white;'><div style='font-size: 14px; text-transform: uppercase; opacity: 0.9;'>Total Global de Instalaciones</div><div style='font-size: 72px; font-weight: 800; line-height: 1;'>{len(df):,}</div><div style='font-size: 13px; margin-top: 10px; opacity: 0.7;'>Récord acumulado</div></div>", unsafe_allow_html=True)

except Exception as e:
    st.error(f"Error detectado: {e}")
