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

# --- FUNCIONES DE APOYO ---
def get_fecha_variantes(dt_obj):
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    nombre_dia = dias[dt_obj.weekday()]
    v1 = f"{nombre_dia} {dt_obj.strftime('%d/%m/%y')}"
    v2 = f"{nombre_dia} {dt_obj.day}/{dt_obj.month}/{dt_obj.strftime('%y')}"
    v3 = dt_obj.strftime('%d/%m/%Y')
    return [v1.lower(), v2.lower(), v3.lower()]

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

# 2. ESTILO CSS
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap');
    .stApp { background-color: #0e1117; color: #ffffff; font-family: 'Poppins', sans-serif; }
    .section-title { color: #ffffff !important; font-size: 18px; font-weight: 600; margin-top: 20px; margin-bottom: 10px; border-left: 4px solid #00d4ff; padding-left: 12px; }
    [data-testid="column"]:nth-child(1) [data-testid="stVerticalBlock"] { align-items: flex-end; }
    [data-testid="column"]:nth-child(3) [data-testid="stVerticalBlock"] { align-items: flex-start; }
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
    .bg-cyan { background-color: #00ffff; color: #000 !important; }
    .month-row { display: flex; justify-content: space-between; padding: 8px; background: rgba(255, 255, 255, 0.03); margin-bottom: 3px; border-radius: 6px; font-size: 13px; }
    .search-result-card { background: rgba(0, 212, 255, 0.1); border: 1px solid #00d4ff; padding: 15px; border-radius: 10px; margin-top: 10px; }
    [data-testid="stExpander"] { background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 10px; margin-bottom: 5px; }
    </style>
    """, unsafe_allow_html=True)

# 3. MOTOR DE CARGA
@st.cache_data(ttl=5)
def fetch_all_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    creds_info = st.secrets["connections"]["gsheets"]
    creds = service_account.Credentials.from_service_account_info(creds_info)
    service = build('sheets', 'v4', credentials=creds)
    asig_id = "1KK1Ng6lF-dGSzOt46kVsqAnY0MG4v-Ggp4S8x1IZokQ"
    
    asig_data = service.spreadsheets().get(spreadsheetId=asig_id, ranges=["ASIGNADOS!A:G", "RUTAS PRE PLANIFICADAS!A:S"], includeGridData=True).execute()
    rows_asig = asig_data['sheets'][0]['data'][0].get('rowData', [])
    rows_ruta = asig_data['sheets'][1]['data'][0].get('rowData', [])
    
    df_main = conn.read(worksheet="Base de Datos ", ttl=0)
    df_main = df_main.dropna(subset=["Marca temporal"], how='all').copy()
    return rows_asig, rows_ruta, df_main

# 4. BUSCADOR MULTI-LIBRO
def hybrid_search(query, df_inst, asig_map, rows_ruta):
    q_clean = str(query).strip()
    
    # NIVEL 1: Buscar en Instalados
    match = df_inst[df_inst['Contrato_Str'] == q_clean]
    f_asig_dt = asig_map.get(q_clean)
    f_asig_str = f_asig_dt.strftime('%d/%m/%y') if pd.notnull(f_asig_dt) else "N/A"
    
    if not match.empty:
        res = match.iloc[0]
        return {
            "status": "✅ 100% INSTALADO", "cliente": res['Nombre del cliente'], 
            "fecha_asig": f_asig_str, "fecha_inst": res['Fecha_Limpia'].strftime('%d/%m/%y'), 
            "tardo": int(res['Dias_Realizacion']), "metros": int(res['Metraje']), 
            "tensores": int(res['Tensores']), "onu": res['ONU_Final']
        }
    
    # NIVEL 2: Buscar en Rutas
    curr_date_ruta = "FECHA NO DEFINIDA"
    for row in rows_ruta:
        cells = row.get('values', [])
        if len(cells) < 10: continue
        
        # Detectar fila naranja de fecha (Columna J)
        val_j = str(cells[9].get('formattedValue', '')).lower()
        bg_j = cells[9].get('effectiveFormat', {}).get('backgroundColor', {})
        is_orange = abs(bg_j.get('red', 0)-1.0) < 0.1 and abs(bg_j.get('green', 0)-0.6) < 0.1
        
        if is_orange or ("/" in val_j and any(d in val_j for d in ["lunes","martes","miércoles","jueves","viernes","sábado","domingo"])):
            curr_date_ruta = val_j.upper()
            continue
            
        # Match de contrato (Columna H)
        cont_h = str(cells[7].get('formattedValue', '')).replace('.0', '').strip()
        if cont_h == q_clean:
            return {
                "status": f"🚚 EN RUTA PARA {curr_date_ruta}",
                "cliente": cells[9].get('formattedValue', '').upper(),
                "zona": cells[12].get('formattedValue', '').upper() if len(cells) > 12 else "N/A",
                "fecha_asig": f_asig_str
            }
    return None

# 5. EJECUCIÓN
try:
    rows_asig, rows_ruta, df_raw = fetch_all_data()
    
    # Procesar Mapas y KPIs
    asig_map = {}
    p_real, p_adec, asig_h, asig_a = 0, 0, 0, 0
    v_hoy, v_ayer = get_fecha_variantes(ahora_vzla), get_fecha_variantes(ayer_laboral_dt)
    curr_d, f_h, f_a = None, False, False
    
    for row in rows_asig:
        cells = row.get('values', [])
        if len(cells) < 7: continue
        val_g = str(cells[6].get('formattedValue', '')).lower()
        bg = cells[6].get('effectiveFormat', {}).get('backgroundColor', {})
        if (abs(bg.get('red', 0)-1.0) < 0.1 and abs(bg.get('green', 0)-0.6) < 0.1) or "asignación raq" in val_g:
            try: curr_d = pd.to_datetime(val_g.split(' ')[-1], dayfirst=True).date()
            except: pass
            f_h, f_a = any(v in val_g for v in v_hoy), any(v in val_g for v in v_ayer)
            continue
        cont = str(cells[4].get('formattedValue', '')).replace('.0', '').strip()
        if cont and curr_d: 
            asig_map[cont] = curr_d
            if f_h: asig_h += 1
            if f_a: asig_a += 1
        if len(cells) > 1 and 'userEnteredValue' in cells[1]:
            r_val = cells[1].get('effectiveFormat', {}).get('backgroundColor', {}).get('red', 0.0)
            if r_val > 0.9: p_real += 1
            elif abs(r_val-0.851) < 0.05: p_adec += 1

    df = df_raw.copy()
    df['Fecha_Limpia'] = df["Marca temporal"].apply(parse_individual_date)
    df['Contrato_Str'] = df['Contrato'].astype(str).str.replace('.0', '', regex=False).str.strip()
    df['Fecha_Asignacion'] = df['Contrato_Str'].map(asig_map)
    df['Dias_Realizacion'] = (pd.to_datetime(df['Fecha_Limpia']) - pd.to_datetime(df['Fecha_Asignacion'])).dt.days
    df.loc[df['Dias_Realizacion'] < 0, 'Dias_Realizacion'] = 0
    df['Metraje'] = pd.to_numeric(df['Metros '], errors='coerce').fillna(0)
    df['Tensores'] = pd.to_numeric(df['Tensores'], errors='coerce').fillna(0)
    df['ONU_Final'] = df['Serial ONU'].astype(str) if 'Serial ONU' in df.columns else "N/A"
    df['Fecha_DT'] = pd.to_datetime(df['Fecha_Limpia'], errors='coerce')

    with st.sidebar:
        st.markdown("### 🔍 Buscador Maestro")
        sq = st.text_input("Número de contrato:")
        if sq:
            res = hybrid_search(sq, df, asig_map, rows_ruta)
            if res:
                if "INSTALADO" in res['status']:
                    html = f"<div class='search-result-card'><p style='color:#00d4ff; font-weight:600; margin-bottom:5px;'>{res['status']}</p><p style='font-size:12px; margin:0;'><b>CLIENTE:</b> {res['cliente']}</p><p style='font-size:12px; margin:0;'><b>FECHA ASIG:</b> {res['fecha_asig']}</p><p style='font-size:12px; margin:0;'><b>FECHA INST:</b> {res['fecha_inst']}</p><p style='color:#00ff00; font-size:11px; margin-top:5px;'><b>TARDÓ {res['tardo']} DÍAS</b></p><p style='font-size:11px;'>{res['metros']}m | {res['tensores']}⚙️ | ONU: {res['onu']}</p></div>"
                else:
                    html = f"<div class='search-result-card'><p style='color:#00ff00; font-weight:600; margin-bottom:5px;'>{res['status']}</p><p style='font-size:12px; margin:0;'><b>CLIENTE:</b> {res['cliente']}</p><p style='font-size:12px; margin:0;'><b>ZONA:</b> {res['zona']}</p><p style='font-size:12px; margin:0;'><b>FECHA ASIG:</b> {res['fecha_asig']}</p></div>"
                st.markdown(html, unsafe_allow_html=True)
            else: st.warning("No encontrado.")

    # HEADER
    ce, cl, ct, cr = st.columns([0.6, 1, 3.5, 1.5])
    with cl: st.image("logo_izq.png", width=150)
    with ct:
        st.markdown("<h1 style='text-align: center; color: white; margin:0;'>💎 FIBRA RAQ INTELLIGENCE</h1>", unsafe_allow_html=True)
        st.markdown(f"<p style='text-align: center; color: #00d4ff;'>{ahora_vzla.strftime('%d/%m/%Y %I:%M %p')}</p>", unsafe_allow_html=True)
    with cr: st.image("logo_der.png", width=150)
    
    # KPIs
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
    with k7:
        avg_s = df[(df['Fecha_Limpia'] >= i_s) & (df['Fecha_Limpia'] <= f_s)]['Dias_Realizacion'].mean()
        st.markdown(f"<div class='metric-container'><div class='m-label'>Media Sem. Actual</div><div class='m-value'>{avg_s:.1f if pd.notnull(avg_s) else 0}</div></div>", unsafe_allow_html=True)
    with k8:
        avg_p = df[(df['Fecha_Limpia'] >= i_p) & (df['Fecha_Limpia'] <= f_p)]['Dias_Realizacion'].mean()
        st.markdown(f"<div class='metric-container'><div class='m-label'>Media Sem. Pasada</div><div class='m-value'>{avg_p:.1f if pd.notnull(avg_p) else 0}</div></div>", unsafe_allow_html=True)

    # RUTAS
    def get_ruta_list(fecha_dt):
        vars = get_fecha_variantes(fecha_dt)
        f, cls = False, []
        for row in rows_ruta:
            cells = row.get('values', [])
            if len(cells) < 13: continue
            vj, vh = cells[9].get('formattedValue', '').lower().strip(), cells[7].get('formattedValue', '').strip()
            if any(v in vj for v in vars) and not vh: f = True; continue
            if f:
                if "/" in vj and not vh: break
                if vh and len(vj) > 2:
                    bg = cells[9].get('effectiveFormat', {}).get('backgroundColor', {})
                    r, g = bg.get('red', 0.0), bg.get('green', 0.0)
                    ck = "green" if g > 0.8 and r < 0.5 else "grey" if abs(r-0.851) < 0.05 else "white"
                    cls.append({'contrato': vh, 'nombre': vj.upper(), 'zona': cells[12].get('formattedValue', '').upper(), 'color': ck})
        return cls

    ruta_h, ruta_a = get_ruta_list(ahora_vzla), get_ruta_list(ayer_laboral_dt)
    st.markdown("<div class='section-title'>Control de Ruta y Materiales</div>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns([1, 1, 1, 0.6])
    def rend_c(c): return f"<div class='cliente-item bg-{c['color']}'>{str(int(float(c['contrato'])))} | {c['nombre']} | {c['zona']}</div>"
    with c1: st.markdown(f"<div class='ruta-box'><div class='ruta-header'>RUTA HOY ({len(ruta_h)})</div>{''.join([rend_c(c) for c in ruta_h])}</div>", unsafe_allow_html=True)
    with c2: st.markdown(f"<div class='ruta-box'><div class='ruta-header'>RUTA AYER ({len(ruta_a)})</div>{''.join([rend_c(c) for c in ruta_a])}</div>", unsafe_allow_html=True)
    with c3:
        df_a_m = df[df['Fecha_Limpia'] == ayer_laboral_vzla]
        itms = "".join([f"<div class='cliente-item bg-green'>{r['Contrato_Str']} | {r['Nombre del cliente']} | 📏{int(r['Metraje'])}m</div>" for _, r in df_a_m.iterrows()])
        st.markdown(f"<div class='ruta-box'><div class='ruta-header'>MATERIALES AYER ({len(df_a_m)})</div>{itms}</div>", unsafe_allow_html=True)
    with c4: st.markdown("<div class='ruta-box'><div class='ruta-header'>ADECUACIONES</div><div class='m-value' style='color:#ff9900; text-align:center; font-size:30px;'>"+str(p_adec)+"</div><div class='ruta-header' style='margin-top:20px;'>PENDIENTES RUTA</div><div class='m-value' style='color:#ff4b4b; text-align:center; font-size:30px;'>"+str(p_real)+"</div></div>", unsafe_allow_html=True)

    # HISTÓRICO
    st.markdown("<div class='section-title'>Análisis Histórico</div>", unsafe_allow_html=True)
    df_hist = df.dropna(subset=['Fecha_DT']).copy()
    df_hist['Mes_Nom'] = df_hist['Fecha_DT'].dt.month.map({1:'Enero', 2:'Febrero', 3:'Marzo', 4:'Abril', 5:'Mayo', 6:'Junio', 7:'Julio', 8:'Agosto', 9:'Septiembre', 10:'Octubre', 11:'Noviembre', 12:'Diciembre'})
    df_hist['Año_H'] = df_hist['Fecha_DT'].dt.year
    df_hist['Mes_H'] = df_hist['Fecha_DT'].dt.month
    hist = df_hist.groupby(['Año_H', 'Mes_H', 'Mes_Nom']).agg(T=('Contrato', 'size'), M=('Dias_Realizacion', 'mean')).reset_index().sort_values(['Año_H', 'Mes_H'], ascending=False)
    for _, row in hist.iterrows():
        st.markdown(f"<div class='month-row'><span>{row['Mes_Nom']} {int(row['Año_H'])}</span><span><span style='color:#00d4ff; font-weight:bold;'>{row['T']}</span><span style='color:#8899a6; font-size:10px; margin-left:10px;'>Media: {row['M']:.1f} días</span></span></div>", unsafe_allow_html=True)

except Exception as e:
    st.error(f"Error detectado: {e}")
