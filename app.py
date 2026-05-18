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

# --- CONFIGURACIÓN HORA VENEZUELA ---
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

# 3. MOTOR DE CARGA Y PROCESAMIENTO
@st.cache_data(ttl=5)
def fetch_all_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    creds_info = st.secrets["connections"]["gsheets"]
    creds = service_account.Credentials.from_service_account_info(creds_info)
    service = build('sheets', 'v4', credentials=creds)
    
    asig_id = "1KK1Ng6lF-dGSzOt46kVsqAnY0MG4v-Ggp4S8x1IZokQ"
    adecu_id = "1Y4AkWf4kSRrJcny9SUtW0qY5jzrcizpU3xjdBdjbmqY"
    
    # Carga Asignaciones y Rutas
    asig_data = service.spreadsheets().get(spreadsheetId=asig_id, ranges=["ASIGNADOS!A:G", "RUTAS PRE PLANIFICADAS!A:N"], includeGridData=True).execute()
    rows_asig = asig_data['sheets'][0]['data'][0].get('rowData', [])
    rows_ruta = asig_data['sheets'][1]['data'][0].get('rowData', [])
    
    # Carga Adecuaciones
    adecu_res = service.spreadsheets().values().get(spreadsheetId=adecu_id, range="A:D").execute()
    rows_adecu = adecu_res.get('values', [])
    
    df_main = conn.read(worksheet="Base de Datos ", ttl=0)
    df_main = df_main.dropna(subset=["Marca temporal"], how='all').copy()
    return rows_asig, rows_ruta, rows_adecu, df_main

def process_data(rows_asig, rows_ruta, rows_adecu, df_main):
    asig_map, ruta_map, adecu_map = {}, {}, {}
    p_realizar, p_adecuacion, asig_hoy, asig_ayer = 0, 0, 0, 0
    v_hoy, v_ayer = get_fecha_variantes(ahora_vzla), get_fecha_variantes(ayer_laboral_dt)
    
    # Procesar ASIGNADOS (Mapa y KPIs)
    curr_asig_date = None
    for row in rows_asig:
        cells = row.get('values', [])
        if len(cells) < 7: continue
        val_g = str(cells[6].get('formattedValue', '')).lower()
        bg = cells[6].get('effectiveFormat', {}).get('backgroundColor', {})
        is_orange = abs(bg.get('red', 0)-1.0) < 0.1 and abs(bg.get('green', 0)-0.6) < 0.1
        
        if is_orange or "asignación raq" in val_g:
            for p in val_g.replace('asignación raq','').strip().split(' '):
                if '/' in p: curr_asig_date = p
            continue
        
        contrato = str(cells[4].get('formattedValue', '')).replace('.0', '').strip()
        if contrato and curr_asig_date:
            asig_map[contrato] = curr_asig_date
            if any(v in val_g for v in v_hoy): asig_hoy += 1
            if any(v in val_g for v in v_ayer): asig_ayer += 1
        
        # KPIs por color en ASIGNADOS
        if 'userEnteredValue' in cells[1]:
            bg_gen = cells[1].get('effectiveFormat', {}).get('backgroundColor', {})
            r, g = bg_gen.get('red', 0.0), bg_gen.get('green', 0.0)
            if abs(r-0.851) < 0.03: p_adecuacion += 1
            elif r > 0.9 and g < 0.2: p_realizar += 1

    # Procesar RUTAS (Mapa de fechas de visita)
    curr_ruta_date = None
    for row in rows_ruta:
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

    # Procesar ADECUACIONES
    for r in rows_adecu:
        if len(r) >= 1:
            adecu_map[str(r[0]).strip()] = {"fecha": r[1] if len(r)>1 else "N/A", "motivo": r[2] if len(r)>2 else "N/A", "trabajo": r[3] if len(r)>3 else "N/A"}

    # Motor Híbrido de Fechas (REGLA 2: No tocar)
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

    df_main['Fecha_Limpia'] = df_main["Marca temporal"].apply(parse_individual_date)
    df_main['Fecha_DT'] = pd.to_datetime(df_main['Fecha_Limpia'], errors='coerce')
    df_main['Contrato_Str'] = df_main['Contrato'].astype(str).str.replace('.0', '', regex=False).str.strip()
    df_main['Metraje'] = pd.to_numeric(df_main['Metros '], errors='coerce').fillna(0)
    df_main['Tensores'] = pd.to_numeric(df_main['Tensores'], errors='coerce').fillna(0)
    
    # Cálculo de días de respuesta
    df_main['Fecha_Ref'] = df_main['Contrato_Str'].map(lambda x: ruta_map.get(x) or asig_map.get(x))
    f_inst = pd.to_datetime(df_main['Fecha_Limpia'], errors='coerce')
    f_asig = pd.to_datetime(df_main['Fecha_Ref'], dayfirst=True, errors='coerce')
    df_main['Dias_Realizacion'] = (f_inst - f_asig).dt.days
    df_main.loc[df_main['Dias_Realizacion'] < 0, 'Dias_Realizacion'] = 0

    # Extracción de rutas para visualización
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

    return df_main, asig_map, ruta_map, adecu_map, p_realizar, p_adecuacion, asig_hoy, asig_ayer, get_ruta_list(rows_ruta, ahora_vzla), get_ruta_list(rows_ruta, ayer_laboral_dt)

# 4. BUSCADOR MULTINIVEL
def hybrid_search(query, df_inst, asig_m, ruta_m, adecu_m):
    q = str(query).strip()
    match = df_inst[df_inst['Contrato_Str'] == q]
    info_ad = adecu_m.get(q)
    
    # NIVEL 1: INSTALADO
    if not match.empty:
        res = match.iloc[0]
        disc = f"<p style='color:#ff4b4b; font-size:11px;'>⚠️ EN ADECUACIÓN DESDE {info_ad['fecha']}</p>" if info_ad else ""
        return f"<div class='search-result-card'><p style='color:#00d4ff; font-weight:600;'>✅ 100% INSTALADO</p>{disc}<p style='font-size:12px;'><b>CLIENTE:</b> {res['Nombre del cliente']}<br><b>FECHA INST:</b> {res['Fecha_Limpia'].strftime('%d/%m/%y')}<br><b>ONU:</b> {res['ONU_Final']}</p></div>"
    
    # NIVEL 2: RUTA
    if q in ruta_m:
        return f"<div class='search-result-card' style='border-color:#00ff00;'><p style='color:#00ff00; font-weight:600;'>🚚 ASIGNADO PARA {ruta_m[q]}</p><p style='font-size:12px;'>El contrato se encuentra actualmente en la hoja de rutas.</p></div>"
        
    # NIVEL 3: ASIGNADO
    if q in asig_m:
        return f"<div class='search-result-card' style='border-color:#ffff00;'><p style='color:#ffff00; font-weight:600;'>⏳ ASIGNADO DESDE {asig_m[q]} PERO SIN FECHA DE VISITA AÚN</p></div>"
        
    # NIVEL 4: ADECUACIÓN
    if info_ad:
        return f"<div class='search-result-card' style='border-color:#ff9900;'><p style='color:#ff9900; font-weight:600;'>⚠️ PENDIENTE POR {info_ad['motivo'].upper()} DESDE {info_ad['fecha']}</p><p style='font-size:12px;'><b>TRABAJO A REALIZAR:</b> {info_ad['trabajo'].upper()}</p></div>"
        
    return None

# 5. EJECUCIÓN DASHBOARD
try:
    r_asig, r_ruta, r_adecu, df_raw = fetch_all_data()
    df, asig_map, ruta_map, adecu_map, p_real, p_adec, asig_h, asig_a, ruta_h, ruta_a = process_data(r_asig, r_ruta, r_adecu, df_raw)
    
    with st.sidebar:
        st.markdown("### 🔍 Buscador Maestro")
        sq = st.text_input("Número de contrato:")
        if sq:
            res_html = hybrid_search(sq, df, asig_map, ruta_map, adecu_map)
            if res_html: st.markdown(res_html, unsafe_allow_html=True)
            else: st.warning("Contrato no encontrado.")

    # HEADER (REGLA 4: Simetría)
    ce, cl, ct, cr = st.columns([0.6, 1, 3.5, 1.5])
    with cl: st.image("logo_izq.png", width=150) if True else None
    with ct:
        st.markdown("<h1 style='text-align: center; margin:0;'>💎 FIBRA RAQ INTELLIGENCE</h1>", unsafe_allow_html=True)
        st.markdown(f"<p style='text-align: center; color:#00d4ff;'>{ahora_vzla.strftime('%d/%m/%Y %I:%M %p')}</p>", unsafe_allow_html=True)
    with cr: st.image("logo_der.png", width=150) if True else None

    # MÉTRICAS Y CUADROS (IDÉNTICO A TU VERSIÓN)
    st.markdown("<div class='section-title'>Rendimiento Operativo</div>", unsafe_allow_html=True)
    k1, k2, k3, k4 = st.columns(4)
    with k1: st.markdown(f"<div class='metric-container'><div class='m-label'>Hoy</div><div class='m-value'>{len(df[df['Fecha_Limpia'] == hoy_vzla])}</div></div>", unsafe_allow_html=True)
    with k2: st.markdown(f"<div class='metric-container'><div class='m-label'>Ayer</div><div class='m-value'>{len(df[df['Fecha_Limpia'] == (hoy_vzla - timedelta(days=1))])}</div></div>", unsafe_allow_html=True)
    with k3:
        def get_jueves(d): return d - timedelta(days=(d.isoweekday() - 4) % 7)
        i_s = get_jueves(hoy_vzla); f_s = i_s + timedelta(days=6)
        st.markdown(f"<div class='metric-container'><div class='m-label'>Sem. Actual</div><div class='m-value'>{len(df[(df['Fecha_Limpia'] >= i_s) & (df['Fecha_Limpia'] <= f_s)])}</div><div class='m-sub'>{i_s.strftime('%d/%m')} al {f_s.strftime('%d/%m')}</div></div>", unsafe_allow_html=True)
    with k4:
        i_p = get_jueves(hoy_vzla) - timedelta(days=7); f_p = i_p + timedelta(days=6)
        st.markdown(f"<div class='metric-container'><div class='m-label'>Sem. Pasada</div><div class='m-value'>{len(df[(df['Fecha_Limpia'] >= i_p) & (df['Fecha_Limpia'] <= f_p)])}</div><div class='m-sub'>{i_p.strftime('%d/%m')} al {f_p.strftime('%d/%m')}</div></div>", unsafe_allow_html=True)

    k5, k6, k7, k8 = st.columns(4)
    with k5: st.markdown(f"<div class='metric-container'><div class='m-label'>Asig. Hoy</div><div class='m-value'>{asig_h}</div></div>", unsafe_allow_html=True)
    with k6: st.markdown(f"<div class='metric-container'><div class='m-label'>Asig. Ayer Lab.</div><div class='m-value'>{asig_a}</div></div>", unsafe_allow_html=True)
    with k7:
        avg_s = df[(df['Fecha_Limpia'] >= i_s) & (df['Fecha_Limpia'] <= f_s)]['Dias_Realizacion'].mean()
        st.markdown(f"<div class='metric-container'><div class='m-label'>Media Sem. Actual</div><div class='m-value'>{avg_s:.1f if pd.notnull(avg_s) else 0}</div></div>", unsafe_allow_html=True)
    with k8:
        avg_p = df[(df['Fecha_Limpia'] >= i_p) & (df['Fecha_Limpia'] <= f_p)]['Dias_Realizacion'].mean()
        st.markdown(f"<div class='metric-container'><div class='m-label'>Media Sem. Pasada</div><div class='m-value'>{avg_p:.1f if pd.notnull(avg_p) else 0}</div></div>", unsafe_allow_html=True)

    # RUTA Y MATERIALES
    st.markdown("<div class='section-title'>Control de Ruta y Materiales</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    def rend_c(c): return f"<div class='cliente-item bg-{c['color']}'>{str(int(float(c['contrato'])))} | {c['nombre']} | {c['zona']}</div>"
    with c1:
        with st.expander(f"📍 RUTA HOY ({len(ruta_h)})"): st.markdown(f"<div class='ruta-box'>{''.join([rend_c(c) for c in ruta_h])}</div>", unsafe_allow_html=True)
    with c2:
        df_h_m = df[df['Fecha_Limpia'] == hoy_vzla]
        with st.expander(f"📍 MATERIALES HOY ({len(df_h_m)})"):
            items = "".join([f"<div class='cliente-item bg-green'>{r['Contrato_Str']} | {r['Nombre del cliente']} | 📏{int(r['Metraje'])}m | 🆔{str(r['ONU_Final'])[-6:]}</div>" for _, r in df_h_m.iterrows()])
            st.markdown(f"<div class='ruta-box'>{items}</div>", unsafe_allow_html=True)

    # ANÁLISIS HISTÓRICO (REGLA 2: No tocar lógica de meses)
    st.markdown("<div class='section-title'>Análisis Histórico</div>", unsafe_allow_html=True)
    df_hist = df.dropna(subset=['Fecha_DT']).copy()
    df_hist['Mes_Nombre'] = df_hist['Fecha_DT'].dt.month.map({1:'Enero', 2:'Febrero', 3:'Marzo', 4:'Abril', 5:'Mayo', 6:'Junio', 7:'Julio', 8:'Agosto', 9:'Septiembre', 10:'Octubre', 11:'Noviembre', 12:'Diciembre'})
    hist = df_hist.groupby([df_hist['Fecha_DT'].dt.year, df_hist['Fecha_DT'].dt.month, 'Mes_Nombre']).agg(Total=('Contrato', 'size'), Media=('Dias_Realizacion', 'mean'), Mts=('Metraje', 'sum')).reset_index().sort_values(['Fecha_DT','Fecha_DT'], ascending=False)
    for _, row in hist.iterrows():
        st.markdown(f"<div class='month-row'><span>{row['Mes_Nombre']} {int(row['level_0'])}</span><span><span style='color:#00d4ff; font-weight:bold;'>{row['Total']}</span><span style='color:#8899a6; font-size:10px; margin-left:10px;'>Media: {row['Media']:.1f}d | 📏{row['Mts']:,.0f}m</span></span></div>", unsafe_allow_html=True)

except Exception as e:
    st.error(f"Error detectado: {e}")
