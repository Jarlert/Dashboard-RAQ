import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta
import pytz 
from streamlit_autorefresh import st_autorefresh 
from googleapiclient.discovery import build
from google.oauth2 import service_account

# 1. CONFIGURACIÓN Y SEGURIDAD
st.set_page_config(page_title="FIBRA RAQ | Pro Dashboard", layout="wide")

if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

if not st.session_state['authenticated']:
    st.markdown("<h2 style='text-align: center; color: white;'>💎 Acceso Restringido</h2>", unsafe_allow_html=True)
    col_auth_1, col_auth_2, col_auth_3 = st.columns([1,1,1])
    with col_auth_2:
        password = st.text_input("Introduce la clave maestra:", type="password")
        if password == "RAQ2026":
            st.session_state['authenticated'] = True
            st.rerun()
    st.stop()

st_autorefresh(interval=300000, key="datarefresh")

vzla_tz = pytz.timezone('America/Caracas')
ahora_vzla = datetime.now(vzla_tz)
hoy_vzla = ahora_vzla.date()

if ahora_vzla.weekday() == 0:
    ayer_laboral_dt = ahora_vzla - timedelta(days=3)
else:
    ayer_laboral_dt = ahora_vzla - timedelta(days=1)
ayer_laboral_vzla = ayer_laboral_dt.date()

def get_fecha_variantes(dt_obj):
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    nombre_dia = dias[dt_obj.weekday()]
    v1 = f"{nombre_dia} {dt_obj.strftime('%d/%m/%y')}"
    v2 = f"{nombre_dia} {dt_obj.day}/{dt_obj.month}/{dt_obj.strftime('%y')}"
    v3 = dt_obj.strftime('%d/%m/%Y')
    return [v1.lower(), v2.lower(), v3.lower()]

# 2. ESTILO CSS
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap');
    .stApp { background-color: #0e1117; color: #ffffff; font-family: 'Poppins', sans-serif; }
    .section-title { color: #ffffff !important; font-size: 18px; font-weight: 600; margin-top: 20px; margin-bottom: 10px; border-left: 4px solid #00d4ff; padding-left: 12px; }
    .metric-container { 
        background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); 
        padding: 15px; border-radius: 10px; text-align: center; height: 110px;
        display: flex; flex-direction: column; justify-content: center; align-items: center;
        margin-bottom: 10px;
    }
    .m-label { color: #8899a6; font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 5px; }
    .m-value { color: #ffffff; font-size: 22px; font-weight: 700; line-height: 1; }
    .m-sub { color: #00d4ff; font-size: 9px; margin-top: 5px; font-weight: 400; }
    .ruta-box { background: rgba(255, 255, 255, 0.02); border-radius: 10px; padding: 10px; max-height: 400px; overflow-y: auto; }
    .cliente-item { font-size: 9px; padding: 6px 10px; margin-bottom: 3px; border-radius: 4px; color: #000 !important; font-weight: 600; white-space: normal; line-height: 1.3; border: 1px solid rgba(0,0,0,0.1); }
    .bg-green { background-color: #00ff00; color: #000 !important; }
    .bg-grey { background-color: #b7b7b7; color: #000 !important; }
    .search-result-card { background: rgba(0, 212, 255, 0.1); border: 1px solid #00d4ff; padding: 15px; border-radius: 10px; margin-top: 10px; }
    .month-row { display: flex; justify-content: space-between; padding: 8px; background: rgba(255, 255, 255, 0.03); margin-bottom: 3px; border-radius: 6px; font-size: 13px; }
    [data-testid="stExpander"] { background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# 3. FUNCIONES DE APOYO
def parse_individual_date(val):
    v = str(val).strip().lower()
    if not v or v == 'none': return None
    try:
        if v.replace('.','').isdigit() and float(v) > 40000: return pd.to_datetime(float(v), unit='D', origin='1899-12-30').date()
    except: pass
    for fmt in ('%d/%m/%Y', '%d/%m/%y', '%Y-%m-%d'):
        try: return datetime.strptime(v[:10], fmt).date()
        except: continue
    return pd.to_datetime(v, dayfirst=True, errors='coerce').date()

def hybrid_search(query, df_inst, asig_m, ruta_m, adecu_m):
    q = str(query).strip()
    match = df_inst[df_inst['Contrato_Str'] == q]
    info_ad = adecu_m.get(q)
    if not match.empty:
        res = match.iloc[0]
        disc = f"<p style='color:#ff4b4b; font-size:11px; font-weight:bold;'>⚠️ EN ADECUACIÓN DESDE {info_ad['fecha']}</p>" if info_ad else ""
        return f"<div class='search-result-card'><p style='color:#00d4ff; font-weight:600;'>✅ 100% INSTALADO</p>{disc}<p style='font-size:12px;'><b>CLIENTE:</b> {res['Nombre del cliente']}<br><b>FECHA INST:</b> {res['Fecha_Limpia'].strftime('%d/%m/%y')}<br><b>ONU:</b> {res['ONU_Final']}</p></div>"
    if q in ruta_m: return f"<div class='search-result-card' style='border-color:#00ff00;'><p style='color:#00ff00; font-weight:600;'>🚚 ASIGNADO PARA {ruta_m[q]}</p></div>"
    if q in asig_m: return f"<div class='search-result-card' style='border-color:#ffff00;'><p style='color:#ffff00; font-weight:600;'>⏳ ASIGNADO DESDE {asig_m[q]} (SIN FECHA VISITA)</p></div>"
    if info_ad: return f"<div class='search-result-card' style='border-color:#ff9900;'><p style='color:#ff9900; font-weight:600;'>⚠️ PENDIENTE POR {info_ad['motivo'].upper()} DESDE {info_ad['fecha']}</p><p style='font-size:12px;'><b>TRABAJO:</b> {info_ad['trabajo'].upper()}</p></div>"
    return None

# 4. MOTOR DE CARGA
@st.cache_data(ttl=5)
def fetch_all_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    creds_info = st.secrets["connections"]["gsheets"]
    creds = service_account.Credentials.from_service_account_info(creds_info)
    service = build('sheets', 'v4', credentials=creds)
    asig_id = "1KK1Ng6lF-dGSzOt46kVsqAnY0MG4v-Ggp4S8x1IZokQ"
    adecu_id = "1Y4AkWf4kSRrJcny9SUtW0qY5jzrcizpU3xjdBdjbmqY"
    
    # CORRECCIÓN: Los índices 0 y 1 corresponden al orden en 'ranges'
    asig_data = service.spreadsheets().get(spreadsheetId=asig_id, ranges=["ASIGNADOS!A:G", "RUTAS PRE PLANIFICADAS!A:N"], includeGridData=True).execute()
    rows_asig = asig_data['sheets'][0]['data'][0].get('rowData', [])
    rows_ruta = asig_data['sheets'][1]['data'][0].get('rowData', [])
    
    adecu_res = service.spreadsheets().values().get(spreadsheetId=adecu_id, range="A:D").execute()
    rows_adecu = adecu_res.get('values', [])
    
    df_main = conn.read(worksheet="Base de Datos ", ttl=0)
    df_main = df_main.dropna(subset=["Marca temporal"], how='all').copy()
    return rows_asig, rows_ruta, rows_adecu, df_main

# --- INICIO RENDERIZADO (Header siempre visible) ---
ce, cl, ct, cr = st.columns([0.6, 1, 3.5, 1.5])
with cl: st.image("logo_izq.png", width=150)
with ct:
    st.markdown("<h1 style='text-align: center; margin:0; color:white;'>💎 FIBRA RAQ INTELLIGENCE</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align: center; color:#00d4ff; font-weight:600;'>{ahora_vzla.strftime('%d/%m/%Y %I:%M %p')}</p>", unsafe_allow_html=True)
with cr: st.image("logo_der.png", width=150)

try:
    r_asig, r_ruta, r_adecu, df_raw = fetch_all_data()
    
    # Procesar Mapas
    asig_map, ruta_map, adecu_map = {}, {}, {}
    p_real, p_adec, asig_h, asig_a = 0, 0, 0, 0
    v_hoy, v_ayer = get_fecha_variantes(ahora_vzla), get_fecha_variantes(ayer_laboral_dt)
    
    curr_asig_date = None
    for row in r_asig:
        cells = row.get('values', [])
        if len(cells) < 7: continue
        val_g = str(cells[6].get('formattedValue', '')).lower()
        bg = cells[6].get('effectiveFormat', {}).get('backgroundColor', {})
        if (abs(bg.get('red', 0)-1.0) < 0.1 and abs(bg.get('green', 0)-0.6) < 0.1) or "asignación raq" in val_g:
            for p in val_g.replace('asignación raq','').strip().split(' '):
                if '/' in p: curr_asig_date = p
            continue
        contrato = str(cells[4].get('formattedValue', '')).replace('.0', '').strip()
        if contrato and curr_asig_date:
            asig_map[contrato] = curr_asig_date
            if any(v in val_g for v in v_hoy): asig_h += 1
            if any(v in val_g for v in v_ayer): asig_a += 1
        if len(cells) > 1 and 'userEnteredValue' in cells[1]:
            r_val = cells[1].get('effectiveFormat', {}).get('backgroundColor', {}).get('red', 0.0)
            if abs(r_val-0.851) < 0.05: p_adec += 1
            elif r_val > 0.9: p_real += 1

    curr_ruta_date = None
    for row in r_ruta:
        cells = row.get('values', [])
        if len(cells) < 10: continue
        val_j = str(cells[9].get('formattedValue', '')).lower()
        bg_j = cells[9].get('effectiveFormat', {}).get('backgroundColor', {})
        if abs(bg_j.get('red', 0)-1.0) < 0.1 and abs(bg_j.get('green', 0)-0.6) < 0.1:
            for p in val_j.split(' '):
                if '/' in p: curr_ruta_date = p
            continue
        contrato_h = str(cells[7].get('formattedValue', '')).replace('.0', '').strip()
        if contrato_h and curr_ruta_date: ruta_map[contrato_h] = curr_ruta_date

    for r in r_adecu:
        if len(r) >= 1:
            adecu_map[str(r[0]).strip()] = {"fecha": r[1] if len(r)>1 else "N/A", "motivo": r[2] if len(r)>2 else "N/A", "trabajo": r[3] if len(r)>3 else "N/A"}

    # Procesar Base de Datos Principal
    df = df_raw.copy()
    df['Fecha_Limpia'] = df["Marca temporal"].apply(parse_individual_date)
    df['Fecha_DT'] = pd.to_datetime(df['Fecha_Limpia'], errors='coerce')
    df['Contrato_Str'] = df['Contrato'].astype(str).str.replace('.0', '', regex=False).str.strip()
    df['Metraje'] = pd.to_numeric(df['Metros '], errors='coerce').fillna(0)
    df['Tensores'] = pd.to_numeric(df['Tensores'], errors='coerce').fillna(0)
    df['ONU_Final'] = df['Serial ONU'].astype(str) if 'Serial ONU' in df.columns else "N/A"
    
    df['Fecha_Ref'] = df['Contrato_Str'].map(lambda x: ruta_map.get(x) or asig_map.get(x))
    f_inst = pd.to_datetime(df['Fecha_Limpia'], errors='coerce')
    f_asig = pd.to_datetime(df['Fecha_Ref'], dayfirst=True, errors='coerce')
    df['Dias_Realizacion'] = (f_inst - f_asig).dt.days
    df.loc[df['Dias_Realizacion'] < 0, 'Dias_Realizacion'] = 0

    with st.sidebar:
        st.markdown("### 🔍 Buscador Maestro")
        sq = st.text_input("Número de contrato:")
        if sq:
            res_html = hybrid_search(sq, df, asig_map, ruta_map, adecu_map)
            if res_html: st.markdown(res_html, unsafe_allow_html=True)
            else: st.warning("Contrato no encontrado.")

    # Render KPIs
    st.markdown("<div class='section-title'>Rendimiento Operativo</div>", unsafe_allow_html=True)
    k1, k2, k3, k4 = st.columns(4)
    with k1: st.markdown(f"<div class='metric-container'><div class='m-label'>Hoy</div><div class='m-value'>{len(df[df['Fecha_Limpia'] == hoy_vzla])}</div></div>", unsafe_allow_html=True)
    with k2: st.markdown(f"<div class='metric-container'><div class='m-label'>Ayer</div><div class='m-value'>{len(df[df['Fecha_Limpia'] == (hoy_vzla - timedelta(days=1))])}</div></div>", unsafe_allow_html=True)
    with k3:
        i_s = hoy_vzla - timedelta(days=(hoy_vzla.isoweekday() - 4) % 7); f_s = i_s + timedelta(days=6)
        st.markdown(f"<div class='metric-container'><div class='m-label'>Sem. Actual</div><div class='m-value'>{len(df[(df['Fecha_Limpia'] >= i_s) & (df['Fecha_Limpia'] <= f_s)])}</div><div class='m-sub'>{i_s.strftime('%d/%m')} al {f_s.strftime('%d/%m')}</div></div>", unsafe_allow_html=True)
    with k4:
        i_p = i_s - timedelta(days=7); f_p = i_p + timedelta(days=6)
        st.markdown(f"<div class='metric-container'><div class='m-label'>Sem. Pasada</div><div class='m-value'>{len(df[(df['Fecha_Limpia'] >= i_p) & (df['Fecha_Limpia'] <= f_p)])}</div><div class='m-sub'>{i_p.strftime('%d/%m')} al {f_p.strftime('%d/%m')}</div></div>", unsafe_allow_html=True)

    k5, k6, k7, k8 = st.columns(4)
    with k5: st.markdown(f"<div class='metric-container'><div class='m-label'>Asig. Hoy</div><div class='m-value'>{asig_h}</div></div>", unsafe_allow_html=True)
    with k6: st.markdown(f"<div class='metric-container'><div class='m-label'>Asig. Ayer Lab.</div><div class='m-value'>{asig_a}</div></div>", unsafe_allow_html=True)
    with k7: st.markdown(f"<div class='metric-container'><div class='m-label'>PENDIENTES RUTA</div><div class='m-value' style='color:#ff4b4b;'>{p_real}</div></div>", unsafe_allow_html=True)
    with k8: st.markdown(f"<div class='metric-container'><div class='m-label'>ADECUACIONES</div><div class='m-value' style='color:#ff9900;'>{p_adec}</div></div>", unsafe_allow_html=True)

    # Rutas
    def get_ruta_list(rows, target_dt):
        vars = get_fecha_variantes(target_dt)
        found, res = False, []
        for r in rows:
            cells = r.get('values', [])
            if len(cells) < 13: continue
            val_j, val_h = cells[9].get('formattedValue', '').lower().strip(), cells[7].get('formattedValue', '').strip()
            if any(v in val_j for v in vars) and not val_h: found = True; continue
            if found:
                if "/" in val_j and not val_h: break
                if val_h and len(val_j) > 2:
                    bg = cells[9].get('effectiveFormat', {}).get('backgroundColor', {})
                    color = "green" if bg.get('green', 0) > 0.8 else "grey" if bg.get('red', 0) > 0.8 and bg.get('green', 0) > 0.8 else "white"
                    res.append({'contrato': val_h, 'nombre': val_j.upper(), 'zona': cells[12].get('formattedValue', '').strip().upper(), 'color': color})
        return res

    ruta_h, ruta_a = get_ruta_list(r_ruta, ahora_vzla), get_ruta_list(r_ruta, ayer_laboral_dt)
    st.markdown("<div class='section-title'>Control de Ruta y Materiales</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        with st.expander(f"📍 RUTA HOY ({len(ruta_h)})"): 
            items = "".join([f"<div class='cliente-item bg-{c['color']}'>{str(int(float(c['contrato'])))} | {c['nombre']} | {c['zona']}</div>" for c in ruta_h])
            st.markdown(f"<div class='ruta-box'>{items}</div>", unsafe_allow_html=True)
    with c2:
        df_h_m = df[df['Fecha_Limpia'] == hoy_vzla]
        with st.expander(f"📍 MATERIALES HOY ({len(df_h_m)})"):
            items = "".join([f"<div class='cliente-item bg-green'>{r['Contrato_Str']} | {r['Nombre del cliente']} | 📏{int(r['Metraje'])}m | 🆔{str(r['ONU_Final'])[-6:]}</div>" for _, r in df_h_m.iterrows()])
            st.markdown(f"<div class='ruta-box'>{items}</div>", unsafe_allow_html=True)

    # Histórico
    st.markdown("<div class='section-title'>Análisis Histórico</div>", unsafe_allow_html=True)
    df_hist = df.dropna(subset=['Fecha_DT']).copy()
    df_hist['Mes_Nom'] = df_hist['Fecha_DT'].dt.month.map({1:'Enero', 2:'Febrero', 3:'Marzo', 4:'Abril', 5:'Mayo', 6:'Junio', 7:'Julio', 8:'Agosto', 9:'Septiembre', 10:'Octubre', 11:'Noviembre', 12:'Diciembre'})
    hist = df_hist.groupby([df_hist['Fecha_DT'].dt.year, df_hist['Fecha_DT'].dt.month, 'Mes_Nom']).agg(Total=('Contrato', 'size'), Media=('Dias_Realizacion', 'mean'), Mts=('Metraje', 'sum')).reset_index().sort_values(['level_0', 'level_1'], ascending=False)
    for _, row in hist.iterrows():
        st.markdown(f"<div class='month-row'><span>{row['Mes_Nom']} {int(row['level_0'])}</span><span><span style='color:#00d4ff; font-weight:bold;'>{row['Total']}</span><span style='color:#8899a6; font-size:10px; margin-left:10px;'>Media: {row['Media']:.1f}d | 📏{row['Mts']:,.0f}m</span></span></div>", unsafe_allow_html=True)

except Exception as e:
    st.error(f"Error detectado: {e}")
