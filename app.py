import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import pytz 
from streamlit_autorefresh import st_autorefresh 

# 1. CONFIGURACIÓN
st.set_page_config(page_title="FIBRA RAQ | Pro Dashboard", layout="wide")
st_autorefresh(interval=60000, key="datarefresh")

# --- ZONA HORARIA VENEZUELA ---
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

# 3. CARGA DE DATOS (ESTRICTA)
@st.cache_data(ttl=5)
def load_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(worksheet="Base de Datos ", ttl=0) 
    df = df.dropna(subset=["Marca temporal"], how='all')
    
    # --- PROCESAMIENTO ESTRICTO ---
    # 1. Limpiamos espacios y tomamos solo los 10 primeros caracteres (DD/MM/YYYY)
    fechas_raw = df["Marca temporal"].astype(str).str.strip().str[:10]
    
    # 2. Forzamos el formato Día/Mes/Año. Si no cumple, dará NaT
    df['Fecha_DT'] = pd.to_datetime(fechas_raw, format='%d/%m/%Y', errors='coerce')
    
    # 3. Extraer fecha limpia para comparaciones
    df['Fecha_Limpia'] = df['Fecha_DT'].dt.date
    
    # Limpieza de números
    df['Metraje'] = pd.to_numeric(df['Metros '], errors='coerce').fillna(0)
    df['Tensores'] = pd.to_numeric(df['Tensores'], errors='coerce').fillna(0)
    
    return df

try:
    df = load_data()
    
    # Lógica de semanas (Jueves a Miércoles)
    def get_jueves(d):
        return d - timedelta(days=(d.isoweekday() - 4) % 7)

    inicio_sem_actual = get_jueves(hoy_vzla)
    fin_sem_actual = inicio_sem_actual + timedelta(days=6)
    inicio_sem_pasada = inicio_sem_actual - timedelta(days=7)
    fin_sem_pasada = inicio_sem_actual - timedelta(days=1)

    # --- HEADER ---
    st.markdown("<h1 style='text-align: center; color: white;'>💎 FIBRA RAQ INTELLIGENCE</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align: center; color: #00d4ff;'>Corte de datos (Vzla): {ahora_vzla.strftime('%d/%m/%Y %I:%M %p')}</p>", unsafe_allow_html=True)

    # --- SECCIÓN 1: KPI ---
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

    # --- SECCIÓN 2: PRODUCTIVIDAD ---
    st.markdown("<div class='section-title'>Productividad de Técnicos</div>", unsafe_allow_html=True)
    tech_cols = df.iloc[:, 22:25].values.flatten()
    tech_counts = pd.Series(tech_cols).dropna().astype(str).str.strip().value_counts().reset_index()
    tech_counts.columns = ['Técnico', 'Servicios']
    tech_counts = tech_counts[~tech_counts['Técnico'].isin(["", "None", "nan", "NaN", "0", "0.0"])].head(12)

    fig_tech = px.bar(tech_counts, x='Servicios', y='Técnico', orientation='h', 
                      text_auto=True, color='Servicios', color_continuous_scale='Blues')
    fig_tech.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color="white", height=450, margin=dict(l=0,r=0,t=0,b=0))
    st.plotly_chart(fig_tech, use_container_width=True)

    # --- SECCIÓN 3: HISTORIAL ---
    st.markdown("<div class='section-title'>Análisis Histórico</div>", unsafe_allow_html=True)
    c1, c2 = st.columns([1, 2])
    with c1:
        # Usamos Fecha_DT para el historial mensual
        df_hist = df.dropna(subset=['Fecha_DT']).copy()
        df_hist['Mes_Num'] = df_hist['Fecha_DT'].dt.month
        df_hist['Año'] = df_hist['Fecha_DT'].dt.year.astype(int)
        
        meses_nombres = {1:'Enero', 2:'Febrero', 3:'Marzo', 4:'Abril', 5:'Mayo', 6:'Junio', 
                         7:'Julio', 8:'Agosto', 9:'Septiembre', 10:'Octubre', 11:'Noviembre', 12:'Diciembre'}
        df_hist['Mes_Nombre'] = df_hist['Mes_Num'].map(meses_nombres)
        
        # Agrupar y filtrar para no mostrar fechas futuras absurdas (posteriores a hoy)
        hist = df_hist.groupby(['Año', 'Mes_Num', 'Mes_Nombre']).size().reset_index(name='Total')
        # Filtro de seguridad: Solo meses que ya pasaron o el actual
        hist = hist[hist['Año'] <= hoy_vzla.year]
        hist = hist.sort_values(['Año', 'Mes_Num'], ascending=False)
        
        st.write("📂 **Cierre Mensual**")
        for _, row in hist.iterrows():
            st.markdown(f"<div class='month-row'><span>{row['Mes_Nombre']} {int(row['Año'])}</span><span style='color:#00d4ff; font-weight:bold;'>{row['Total']}</span></div>", unsafe_allow_html=True)
    
    with c2:
        total_gen = len(df)
        st.markdown(f"<div style='background: linear-gradient(135deg, #00d4ff 0%, #0072ff 100%); padding: 40px; border-radius: 20px; text-align: center; color: white;'><div style='font-size: 14px; text-transform: uppercase; opacity: 0.9;'>Total Global de Instalaciones</div><div style='font-size: 72px; font-weight: 800; line-height: 1;'>{total_gen:,}</div><div style='font-size: 13px; margin-top: 10px; opacity: 0.7;'>Récord acumulado</div></div>", unsafe_allow_html=True)
        
        # Gráfico de tendencia (Últimos 30 días con datos reales)
        consumo = df.groupby('Fecha_Limpia')['Metraje'].sum().reset_index().tail(30)
        fig_cons = px.area(consumo, x='Fecha_Limpia', y='Metraje', title="Gasto de Material (Últimos 30 días)")
        fig_cons.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color="white")
        st.plotly_chart(fig_cons, use_container_width=True)

except Exception as e:
    st.error(f"Error detectado: {e}")
