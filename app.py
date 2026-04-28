import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import pytz 
from streamlit_autorefresh import st_autorefresh 
from googleapiclient.discovery import build
from google.oauth2 import service_account

# 1. CONFIGURACIÓN Y AUTO-REFRESCO
st.set_page_config(page_title="FIBRA RAQ | Pro Dashboard", layout="wide")
st_autorefresh(interval=60000, key="datarefresh")

# --- CONFIGURACIÓN HORA VENEZUELA ---
vzla_tz = pytz.timezone('America/Caracas')
ahora_vzla = datetime.now(vzla_tz)
hoy_vzla = ahora_vzla.date()
ayer_vzla = hoy_vzla - timedelta(days=1)

def get_fecha_str_vzla():
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    nombre_dia = dias[ahora_vzla.weekday()]
    return f"{nombre_dia} {ahora_vzla.strftime('%d/%m/%y')}"

# 2. ESTILO CSS DARK PREMIUM
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap');
    .stApp { background-color: #0e1117; color: #ffffff; font-family: 'Poppins', sans-serif; }
    .section-title { color: #ffffff !important; font-size: 20px; font-weight: 600; margin-top: 25px; margin-bottom: 10px; border-left: 5px solid #00d4ff; padding-left: 15px; }
    .metric-container { background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); padding: 15px; border-radius: 12px; text-align: center; }
    .m-label { color: #8899a6; font-size: 12px; text-transform: uppercase; }
    .m-value { color: #ffffff; font-size: 28px; font-weight: 700; }
    
    /* Cajas de ruta Estilo Imagen 3 */
    .ruta-box { background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 10px; padding: 10px; height: 400px; overflow-y: auto; }
    .ruta-header { font-size: 14px; font-weight: 600; border-bottom: 1px solid #444; margin-bottom: 8px; display: flex; justify-content: space-between; padding-bottom: 5px;}
    .cliente-item { font-size: 11px; padding: 5px 10px; margin-bottom: 4px; border-radius: 5px; color: #000 !important; font-weight: 600; line-height: 1.3; border: 1px solid rgba(0,0,0,0.1); }
    
    .bg-white { background-color: #ffffff; color: #000 !important; }
    .bg-green { background-color: #00ff00; color: #000 !important; }
    .bg-grey { background-color: #d9d9d9; color: #000 !important; }
    .bg-red { background-color: #ff4d4d; color: #fff !important; }
    
    .month-row { display: flex; justify-content: space-between; padding: 10px; background: rgba(255, 255, 255, 0.03); margin-bottom: 4px; border-radius: 6px; }
    p, span, label { color: #ffffff !important; }
    </style>
    """, unsafe_allow_html=True)

# 3. CARGA DE DATOS PRINCIPAL (Protección de los 237 de febrero)
@st.cache_data(ttl=5)
def load_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(worksheet="Base de Datos ", ttl=0) 
    df = df.dropna(subset=["Marca temporal"], how='all')
    df['Fecha_DT'] = pd.to_datetime(df["Marca temporal"], format='%d/%m/%Y', exact=False, errors='coerce')
    df['Fecha_Limpia'] = df['Fecha_DT'].dt.date
    df['Metraje'] = pd.to_numeric(df['Metros '], errors='coerce').fillna(0)
    df['Tensores'] = pd.to_numeric(df['Tensores'], errors='coerce').fillna(0)
    return df

# 4. MOTOR PARA RUTAS PRE PLANIFICADAS (Imagen 2 y 3)
@st.cache_data(ttl=30)
def get_today_ruta():
    try:
        creds_info = st.secrets["connections"]["gsheets"]
        creds = service_account.Credentials.from_service_account_info(creds_info)
        service = build('sheets', 'v4', credentials=creds)
        spreadsheet_id = "1KK1Ng6lF-dGSzOt46kVsqAnY0MG4v-Ggp4S8x1IZokQ"
        
        # Leemos el rango donde están Contrato(H), Nombre/Fecha(J), Serial(E), Zona(M)
        result = service.spreadsheets().get(spreadsheetId=spreadsheet_id, ranges=["RUTAS PRE PLANIFICADAS!A:N"], includeGridData=True).execute()
        rows = result['sheets'][0]['data'][0].get('rowData', [])
        
        target_date = get_fecha_str_vzla().lower()
        found_today = False
        clientes = []

        for row in rows:
            cells = row.get('values', [])
            if not cells: continue
            
            # Buscar el encabezado de fecha en la Columna J (índice 9)
            col_j_val = cells[9].get('formattedValue', '').lower() if len(cells) > 9 else ""
            
            if target_date in col_j_val:
                found_today = True
                continue
            
            if found_today:
                # Si encontramos otro encabezado de fecha, paramos la búsqueda
                if ("/" in col_j_val and "202" in col_j_val) and target_date not in col_j_val:
                    break
                
                # Extraer datos según tu mapeo
                try:
                    contrato = cells[7].get('formattedValue', '').strip() # Col H
                    serial_val = cells[4].get('formattedValue', '').strip() # Col E
                    nombre = cells[9].get('formattedValue', '').strip() # Col J
                    zona = cells[12].get('formattedValue', '').strip() # Col M
                    
                    if contrato and nombre and len(nombre) > 2:
                        # Lógica Mudanza (M) o Nuevo (N) según Columna E
                        tipo = "M" if "mudanza" in serial_val.lower() else "N"
                        
                        # Lógica de Color basado en Columna J (donde está el nombre)
                        bg = cells[9].get('effectiveFormat', {}).get('backgroundColor', {})
                        r, g, b = bg.get('red', 1.0), bg.get('green', 1.0), bg.get('blue', 1.0)
                        
                        color_key = "white"
                        # Verde (Activado)
                        if r < 0.3 and g > 0.8 and b < 0.3: color_key = "green"
                        # Gris (Adecuación)
                        elif abs(r - 0.85) < 0.1 and abs(g - 0.85) < 0.1 and abs(b - 0.85) < 0.1: color_key = "grey"
                        # Rojo (Devuelto)
                        elif r > 0.8 and g < 0.3 and b < 0.3: color_key = "red"
                        
                        clientes.append({
                            'contrato': contrato, 'nombre': nombre, 'zona': zona, 
                            'tipo': tipo, 'color': color_key
                        })
                except: continue
        return clientes
    except Exception as e:
        return []

try:
    df = load_data()
    ruta_hoy = get_today_ruta()
    
    # Cálculos para desglose
    total_ruta = len(ruta_hoy)
    activados = [c for c in ruta_hoy if c['color'] == 'green']
    adecuacion = [c for c in ruta_hoy if c['color'] == 'grey']
    devueltos = [c for c in ruta_hoy if c['color'] == 'red']

    # --- HEADER ---
    st.markdown(f"<h1 style='text-align: center;'>💎 FIBRA RAQ INTELLIGENCE</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align: center; color: #00d4ff;'>Reloj Vzla: {ahora_vzla.strftime('%d/%m/%Y %I:%M %p')}</p>", unsafe_allow_html=True)

    # --- SECCIÓN 1: RENDIMIENTO ---
    st.markdown("<div class='section-title'>Rendimiento Operativo</div>", unsafe_allow_html=True)
    k1, k2, k3, k4 = st.columns(4)
    with k1: st.markdown(f"<div class='metric-container'><div class='m-label'>Hoy</div><div class='m-value'>{len(df[df['Fecha_Limpia'] == hoy_vzla])}</div></div>", unsafe_allow_html=True)
    with k2: st.markdown(f"<div class='metric-container'><div class='m-label'>Ayer</div><div class='m-value'>{len(df[df['Fecha_Limpia'] == ayer_vzla])}</div></div>", unsafe_allow_html=True)

    # --- NUEVA SECCIÓN: CLIENTES DE HOY (Control de Ruta) ---
    st.markdown("<div class='section-title'>Control de Ruta - Clientes de Hoy</div>", unsafe_allow_html=True)
    c_ruta, c_act, c_ade, c_dev = st.columns(4)
    
    def render_cliente(c):
        return f"<div class='cliente-item bg-{c['color']}'>{c['contrato']} | {c['nombre'][:15].upper()}<br>{c['zona']} ({c['tipo']})</div>"

    with c_ruta:
        items = "".join([render_cliente(c) for c in ruta_hoy])
        st.markdown(f"<div class='ruta-box'><div class='ruta-header'><span>RUTA</span><span>TOTAL: {total_ruta}</span></div>{items}</div>", unsafe_allow_html=True)
    with c_act:
        items = "".join([render_cliente(c) for c in activados])
        st.markdown(f"<div class='ruta-box'><div class='ruta-header'><span>ACTIVADOS</span><span>TOTAL: {len(activados)}</span></div>{items}</div>", unsafe_allow_html=True)
    with c_ade:
        items = "".join([render_cliente(c) for c in adecuacion])
        st.markdown(f"<div class='ruta-box'><div class='ruta-header'><span>ADECUACIÓN</span><span>TOTAL: {len(adecuacion)}</span></div>{items}</div>", unsafe_allow_html=True)
    with c_dev:
        items = "".join([render_cliente(c) for c in devueltos])
        st.markdown(f"<div class='ruta-box'><div class='ruta-header'><span>DEVUELTOS</span><span>TOTAL: {len(devueltos)}</span></div>{items}</div>", unsafe_allow_html=True)

    # --- EFICIENCIA ---
    st.markdown("<div class='section-title'>Eficiencia de Materiales</div>", unsafe_allow_html=True)
    e1, e2 = st.columns(2)
    t_inst = len(df) if len(df) > 0 else 1
    with e1: st.markdown(f"<div class='metric-container'><div class='m-label'>Media Metros</div><div class='m-value'>{df['Metraje'].sum()/t_inst:.2f}</div></div>", unsafe_allow_html=True)
    with e2: st.markdown(f"<div class='metric-container'><div class='m-label'>Media Tensores</div><div class='m-value'>{df['Tensores'].sum()/t_inst:.2f}</div></div>", unsafe_allow_html=True)

    # --- PRODUCTIVIDAD ---
    st.markdown("<div class='section-title'>Productividad de Técnicos</div>", unsafe_allow_html=True)
    tech_cols = df.iloc[:, 22:25].values.flatten()
    tech_counts = pd.Series(tech_cols).dropna().astype(str).str.strip().value_counts().reset_index()
    tech_counts.columns = ['Técnico', 'Servicios']
    tech_counts = tech_counts[~tech_counts['Técnico'].isin(["", "None", "nan", "0"])].head(12)
    st.plotly_chart(px.bar(tech_counts, x='Servicios', y='Técnico', orientation='h', text_auto=True, color='Servicios', color_continuous_scale='Blues').update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color="white", height=400, margin=dict(l=0,r=0,t=0,b=0)), use_container_width=True)

    # --- HISTORIAL ---
    st.markdown("<div class='section-title'>Análisis Histórico</div>", unsafe_allow_html=True)
    col_h1, col_h2 = st.columns([1, 2])
    with col_h1:
        df_hist = df.dropna(subset=['Fecha_DT']).copy()
        df_hist = df_hist[df_hist['Fecha_DT'].dt.date <= hoy_vzla]
        df_hist['Mes_Num'] = df_hist['Fecha_DT'].dt.month
        df_hist['Año'] = df_hist['Fecha_DT'].dt.year.astype(int)
        meses_n = {1:'Enero', 2:'Febrero', 3:'Marzo', 4:'Abril', 5:'Mayo', 6:'Junio', 7:'Julio', 8:'Agosto', 9:'Septiembre', 10:'Octubre', 11:'Noviembre', 12:'Diciembre'}
        df_hist['Mes_Nombre'] = df_hist['Mes_Num'].map(meses_n)
        hist = df_hist.groupby(['Año', 'Mes_Num', 'Mes_Nombre']).size().reset_index(name='Total').sort_values(['Año', 'Mes_Num'], ascending=False)
        for _, row in hist.iterrows(): st.markdown(f"<div class='month-row'><span>{row['Mes_Nombre']} {int(row['Año'])}</span><span style='color:#00d4ff; font-weight:bold;'>{row['Total']}</span></div>", unsafe_allow_html=True)
    with col_h2:
        st.markdown(f"<div style='background: linear-gradient(135deg, #00d4ff 0%, #0072ff 100%); padding: 40px; border-radius: 20px; text-align: center; color: white;'><div style='font-size: 14px; text-transform: uppercase; opacity: 0.9;'>Total Global</div><div style='font-size: 72px; font-weight: 800;'>{len(df):,}</div><div style='font-size: 13px; opacity: 0.7;'>Récord acumulado</div></div>", unsafe_allow_html=True)

except Exception as e:
    st.error(f"Error detectado: {e}")
