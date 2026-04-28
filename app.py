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

def get_fecha_variantes_vzla():
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    nombre_dia = dias[ahora_vzla.weekday()]
    v1 = f"{nombre_dia} {ahora_vzla.strftime('%d/%m/%y')}"
    v2 = f"{nombre_dia} {ahora_vzla.day}/{ahora_vzla.month}/{ahora_vzla.strftime('%y')}"
    return [v1.lower(), v2.lower()]

# 2. ESTILO CSS DARK PREMIUM (Simetría total 110px)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap');
    .stApp { background-color: #0e1117; color: #ffffff; font-family: 'Poppins', sans-serif; }
    .section-title { color: #ffffff !important; font-size: 18px; font-weight: 600; margin-top: 20px; margin-bottom: 10px; border-left: 4px solid #00d4ff; padding-left: 12px; }
    
    .metric-container { 
        background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); 
        padding: 15px; border-radius: 10px; text-align: center; height: 110px;
        display: flex; flex-direction: column; justify-content: center; align-items: center;
    }
    .m-label { color: #8899a6; font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 5px; }
    .m-value { color: #ffffff; font-size: 22px; font-weight: 700; line-height: 1; }
    .m-sub { color: #00d4ff; font-size: 9px; margin-top: 5px; }
    
    .ruta-box { background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 10px; padding: 10px; height: 380px; overflow-y: auto; }
    .ruta-header { font-size: 12px; font-weight: 600; border-bottom: 1px solid #444; margin-bottom: 8px; display: flex; justify-content: space-between; padding-bottom: 3px;}
    .cliente-item { font-size: 10px; padding: 4px 8px; margin-bottom: 3px; border-radius: 4px; color: #000 !important; font-weight: 600; line-height: 1.1; border: 1px solid rgba(0,0,0,0.1); }
    
    .bg-white { background-color: #ffffff; color: #000 !important; }
    .bg-green { background-color: #00ff00; color: #000 !important; }
    .bg-grey { background-color: #d9d9d9; color: #000 !important; }
    .bg-red { background-color: #ff4d4d; color: #fff !important; }
    
    .month-row { display: flex; justify-content: space-between; padding: 8px; background: rgba(255, 255, 255, 0.03); margin-bottom: 3px; border-radius: 6px; font-size: 14px; }
    p, span, label { color: #ffffff !important; }
    </style>
    """, unsafe_allow_html=True)

# 3. MOTOR DE CARGA (CONGELADO - Datos Históricos Protegidos)
@st.cache_data(ttl=5)
def load_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_raw = conn.read(worksheet="Base de Datos ", ttl=0) 
    df = df_raw.dropna(subset=["Marca temporal"], how='all').copy()
    def parse_individual_date(val):
        v = str(val).strip().lower()
        if not v or v == 'none': return None
        try:
            if v.replace('.','').isdigit() and float(v) > 40000:
                return pd.to_datetime(float(v), unit='D', origin='1899-12-30').date()
        except: pass
        for fmt in ('%d/%m/%Y', '%d/%m/%y', '%Y-%m-%d'):
            try: return datetime.strptime(v[:10], fmt).date()
            except: continue
        return pd.to_datetime(v, dayfirst=True, errors='coerce').date()
    df['Fecha_Limpia'] = df["Marca temporal"].apply(parse_individual_date)
    df['Fecha_DT'] = pd.to_datetime(df['Fecha_Limpia'], errors='coerce')
    df['Metraje'] = pd.to_numeric(df['Metros '], errors='coerce').fillna(0)
    df['Tensores'] = pd.to_numeric(df['Tensores'], errors='coerce').fillna(0)
    return df

# 4. AGREGADOS ASIGNADOS (Hoja ASIGNADOS - Corregido Motor de Color)
@st.cache_data(ttl=30)
def load_asignados_aggregates():
    try:
        creds_info = st.secrets["connections"]["gsheets"]
        creds = service_account.Credentials.from_service_account_info(creds_info)
        service = build('sheets', 'v4', credentials=creds)
        spreadsheet_id = "1KK1Ng6lF-dGSzOt46kVsqAnY0MG4v-Ggp4S8x1IZokQ"
        result = service.spreadsheets().get(spreadsheetId=spreadsheet_id, ranges=["ASIGNADOS!B:B"], includeGridData=True).execute()
        rows = result['sheets'][0]['data'][0].get('rowData', [])
        p_realizar, p_adecuacion = 0, 0
        for row in rows:
            cells = row.get('values', [])
            if not cells or 'formattedValue' not in cells[0]: continue
            bg = cells[0].get('effectiveFormat', {}).get('backgroundColor', {})
            # Si el fondo existe, los canales faltantes son 0. Si no existe, es blanco (1,1,1)
            r, g, b = bg.get('red', 0.0), bg.get('green', 0.0), bg.get('blue', 0.0)
            if not bg: r = g = b = 1.0
            
            if abs(r-0.937) < 0.02 and abs(g-0.937) < 0.02: p_realizar += 1 # #efefef
            elif abs(r-0.851) < 0.02 and abs(g-0.851) < 0.02: p_adecuacion += 1 # #d9d9d9
        return p_realizar, p_adecuacion
    except: return 0, 0

# 5. MOTOR RUTA HOY (Hoja RUTAS PRE PLANIFICADAS - Corregido Motor de Color)
@st.cache_data(ttl=30)
def get_today_ruta():
    try:
        creds_info = st.secrets["connections"]["gsheets"]
        creds = service_account.Credentials.from_service_account_info(creds_info)
        service = build('sheets', 'v4', credentials=creds)
        spreadsheet_id = "1KK1Ng6lF-dGSzOt46kVsqAnY0MG4v-Ggp4S8x1IZokQ"
        result = service.spreadsheets().get(spreadsheetId=spreadsheet_id, ranges=["RUTAS PRE PLANIFICADAS!A:N"], includeGridData=True).execute()
        rows = result['sheets'][0]['data'][0].get('rowData', [])
        
        variantes_hoy = get_fecha_variantes_vzla()
        dias_semana = ["lunes", "martes", "miercoles", "miércoles", "jueves", "viernes", "sabado", "sábado", "domingo"]
        
        found_today, clientes = False, []
        for row in rows:
            cells = row.get('values', [])
            if not cells or len(cells) < 13: continue
            val_j = cells[9].get('formattedValue', '').lower().strip()
            val_h = cells[7].get('formattedValue', '').strip()
            
            if any(v in val_j for v in variantes_hoy) and not val_h:
                found_today = True
                continue
            
            if found_today:
                if "/" in val_j and any(d in val_j for d in dias_semana) and not val_h: break
                if val_h and len(val_j) > 2:
                    try:
                        tipo = "M" if "mudanza" in cells[4].get('formattedValue', '').lower() else "N"
                        bg = cells[9].get('effectiveFormat', {}).get('backgroundColor', {})
                        # Lógica de color robusta
                        if not bg: r = g = b = 1.0
                        else:
                            r = bg.get('red', 0.0)
                            g = bg.get('green', 0.0)
                            b = bg.get('blue', 0.0)
                        
                        color_key = "white"
                        if g > 0.8 and r < 0.5 and b < 0.5: color_key = "green"
                        elif abs(r-0.85) < 0.05 and abs(g-0.85) < 0.05: color_key = "grey"
                        elif r > 0.8 and g < 0.5 and b < 0.5: color_key = "red"
                        
                        clientes.append({'contrato': val_h, 'nombre': val_j.upper(), 'zona': cells[12].get('formattedValue', '').strip(), 'tipo': tipo, 'color': color_key})
                    except: continue
        return clientes
    except: return []

try:
    df = load_data()
    agg_realizar, agg_adecuacion = load_asignados_aggregates()
    ruta_hoy = get_today_ruta()
    
    def get_jueves(d): return d - timedelta(days=(d.isoweekday() - 4) % 7)
    inicio_sem_actual = get_jueves(hoy_vzla); fin_sem_actual = inicio_sem_actual + timedelta(days=6)
    inicio_sem_pasada = inicio_sem_actual - timedelta(days=7); fin_sem_pasada = inicio_sem_actual - timedelta(days=1)

    # --- HEADER ---
    st.markdown(f"<h1 style='text-align: center;'>💎 FIBRA RAQ INTELLIGENCE</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align: center; color: #00d4ff;'>Reloj Vzla: {ahora_vzla.strftime('%d/%m/%Y %I:%M %p')}</p>", unsafe_allow_html=True)

    # --- SECCIÓN 1: RENDIMIENTO ---
    st.markdown("<div class='section-title'>Rendimiento Operativo</div>", unsafe_allow_html=True)
    k1, k2, k3, k4 = st.columns(4)
    with k1: st.markdown(f"<div class='metric-container'><div class='m-label'>Hoy</div><div class='m-value'>{len(df[df['Fecha_Limpia'] == hoy_vzla])}</div></div>", unsafe_allow_html=True)
    with k2: st.markdown(f"<div class='metric-container'><div class='m-label'>Ayer</div><div class='m-value'>{len(df[df['Fecha_Limpia'] == ayer_vzla])}</div></div>", unsafe_allow_html=True)
    with k3: st.markdown(f"<div class='metric-container'><div class='m-label'>Semana Actual</div><div class='m-value'>{len(df[(df['Fecha_Limpia'] >= inicio_sem_actual) & (df['Fecha_Limpia'] <= fin_sem_actual)])}</div><div class='m-sub'>{inicio_sem_actual.strftime('%d/%m')} al {fin_sem_actual.strftime('%d/%m')}</div></div>", unsafe_allow_html=True)
    with k4: st.markdown(f"<div class='metric-container'><div class='m-label'>Semana Pasada</div><div class='m-value'>{len(df[(df['Fecha_Limpia'] >= inicio_sem_pasada) & (df['Fecha_Limpia'] <= fin_sem_pasada)])}</div><div class='m-sub'>{inicio_sem_pasada.strftime('%d/%m')} al {fin_sem_pasada.strftime('%d/%m')}</div></div>", unsafe_allow_html=True)

    # --- SECCIÓN 2: ESTADO ASIGNACIONES ---
    st.markdown("<div class='section-title'>Estado de Asignaciones (General)</div>", unsafe_allow_html=True)
    a1, a2, a3, a4 = st.columns(4)
    with a1: st.markdown(f"<div class='metric-container'><div class='m-label'>PENDIENTES POR REALIZAR</div><div class='m-value'>{agg_realizar}</div></div>", unsafe_allow_html=True)
    with a2: st.markdown(f"<div class='metric-container'><div class='m-label'>ADECUACIÓN O CAJA</div><div class='m-value'>{agg_adecuacion}</div></div>", unsafe_allow_html=True)

    # --- SECCIÓN 3: CONTROL DE RUTA ---
    st.markdown("<div class='section-title'>Control de Ruta - Clientes de Hoy</div>", unsafe_allow_html=True)
    c_ruta, c_act, c_ade, c_dev = st.columns(4)
    def render_cliente(c): return f"<div class='cliente-item bg-{c['color']}'>{c['contrato']} | {c['nombre'][:15]}<br>{c['zona']} ({c['tipo']})</div>"
    with c_ruta: st.markdown(f"<div class='ruta-box'><div class='ruta-header'><span>RUTA</span><span>TOTAL: {len(ruta_hoy)}</span></div>{''.join([render_cliente(c) for c in ruta_hoy])}</div>", unsafe_allow_html=True)
    with c_act:
        act = [c for c in ruta_hoy if c['color'] == 'green']
        st.markdown(f"<div class='ruta-box'><div class='ruta-header'><span>ACTIVADOS</span><span>TOTAL: {len(act)}</span></div>{''.join([render_cliente(c) for c in act])}</div>", unsafe_allow_html=True)
    with c_ade:
        ade = [c for c in ruta_hoy if c['color'] == 'grey']
        st.markdown(f"<div class='ruta-box'><div class='ruta-header'><span>ADECUACIÓN</span><span>TOTAL: {len(ade)}</span></div>{''.join([render_cliente(c) for c in ade])}</div>", unsafe_allow_html=True)
    with c_dev:
        dev = [c for c in ruta_hoy if c['color'] == 'red']
        st.markdown(f"<div class='ruta-box'><div class='ruta-header'><span>DEVUELTOS</span><span>TOTAL: {len(dev)}</span></div>{''.join([render_cliente(c) for c in dev])}</div>", unsafe_allow_html=True)

    # --- SECCIÓN 4: EFICIENCIA ---
    st.markdown("<div class='section-title'>Eficiencia de Materiales</div>", unsafe_allow_html=True)
    e1, e2 = st.columns(2)
    t_inst = len(df) if len(df) > 0 else 1
    with e1: st.markdown(f"<div class='metric-container'><div class='m-label'>Media Metros</div><div class='m-value'>{df['Metraje'].sum()/t_inst:.2f}</div></div>", unsafe_allow_html=True)
    with e2: st.markdown(f"<div class='metric-container'><div class='m-label'>Media Tensores</div><div class='m-value'>{df['Tensores'].sum()/t_inst:.2f}</div></div>", unsafe_allow_html=True)

    # --- SECCIÓN 5: PRODUCTIVIDAD ---
    st.markdown("<div class='section-title'>Productividad de Técnicos</div>", unsafe_allow_html=True)
    tech_cols = df.iloc[:, 22:25].values.flatten()
    tech_counts = pd.Series(tech_cols).dropna().astype(str).str.strip().value_counts().reset_index()
    tech_counts.columns = ['Técnico', 'Servicios']
    tech_counts = tech_counts[~tech_counts['Técnico'].isin(["", "None", "nan", "0"])].head(12)
    st.plotly_chart(px.bar(tech_counts, x='Servicios', y='Técnico', orientation='h', text_auto=True, color='Servicios', color_continuous_scale='Blues').update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color="white", height=400, margin=dict(l=0,r=0,t=0,b=0)), use_container_width=True)

    # --- SECCIÓN 6: HISTORIAL ---
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
