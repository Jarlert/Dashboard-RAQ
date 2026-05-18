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

# --- GATE DE SEGURIDAD ---
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

# 2. ESTILO CSS DARK PREMIUM
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap');
    .stApp { background-color: #0e1117; color: #ffffff; font-family: 'Poppins', sans-serif; }
    .section-title { color: #ffffff !important; font-size: 18px; font-weight: 600; margin-top: 20px; margin-bottom: 10px; border-left: 4px solid #00d4ff; padding-left: 12px; }
    
    /* Alineación de logos para acercarlos al centro */
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
    
    .bg-white { background-color: #ffffff; color: #000 !important; }
    .bg-green { background-color: #00ff00; color: #000 !important; }
    .bg-grey { background-color: #b7b7b7; color: #000 !important; }
    .bg-cyan { background-color: #00ffff; color: #000 !important; }
    .month-row { display: flex; justify-content: space-between; padding: 8px; background: rgba(255, 255, 255, 0.03); margin-bottom: 3px; border-radius: 6px; font-size: 13px; }
    .search-result-card { background: rgba(0, 212, 255, 0.1); border: 1px solid #00d4ff; padding: 15px; border-radius: 10px; margin-top: 10px; }
    .legend-item { display: flex; align-items: center; margin-bottom: 8px; font-size: 12px; }
    .legend-color { width: 15px; height: 15px; border-radius: 3px; margin-right: 10px; border: 1px solid rgba(255,255,255,0.2); }
    [data-testid="stExpander"] { background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 10px; margin-bottom: 5px; }
    </style>
    """, unsafe_allow_html=True)

# 3. MOTOR DE CARGA ÚNICA (OPTIMIZADO)
@st.cache_data(ttl=5)
def fetch_all_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    creds_info = st.secrets["connections"]["gsheets"]
    creds = service_account.Credentials.from_service_account_info(creds_info)
    service = build('sheets', 'v4', credentials=creds)
    asig_id = "1KK1Ng6lF-dGSzOt46kVsqAnY0MG4v-Ggp4S8x1IZokQ"
    
    # Carga 1: ASIGNADOS (Mapa y KPIs)
    asig_sheet = service.spreadsheets().get(spreadsheetId=asig_id, ranges=["ASIGNADOS!A:G"], includeGridData=True).execute()
    rows_asig = asig_sheet['sheets'][0]['data'][0].get('rowData', [])
    
    # Carga 2: RUTAS PRE PLANIFICADAS
    ruta_sheet = service.spreadsheets().get(spreadsheetId=asig_id, ranges=["RUTAS PRE PLANIFICADAS!A:N"], includeGridData=True).execute()
    rows_ruta = ruta_sheet['sheets'][0]['data'][0].get('rowData', [])
    
    # Carga 3: Base Principal
    df_main = conn.read(worksheet="Base de Datos ", ttl=0)
    df_main = df_main.dropna(subset=["Marca temporal"], how='all').copy()
    return rows_asig, rows_ruta, df_main

def process_data(rows_asig, rows_ruta, df_main):
    asig_map = {}
    p_realizar, p_adecuacion, asig_hoy, asig_ayer = 0, 0, 0, 0
    v_hoy, v_ayer = get_fecha_variantes(ahora_vzla), get_fecha_variantes(ayer_laboral_dt)
    current_date_asig, f_h, f_a = None, False, False

    for row in rows_asig:
        cells = row.get('values', [])
        if len(cells) < 7: continue
        val_g = str(cells[6].get('formattedValue', '')).lower()
        bg = cells[6].get('effectiveFormat', {}).get('backgroundColor', {})
        is_orange = abs(bg.get('red', 0)-1.0) < 0.1 and abs(bg.get('green', 0)-0.6) < 0.1
        
        if is_orange or "asignación raq" in val_g:
            parts = val_g.replace('asignación raq','').strip().split(' ')
            for p in parts:
                if '/' in p:
                    try: current_date_asig = pd.to_datetime(p, dayfirst=True).date()
                    except: pass
            if any(v in val_g for v in v_hoy): f_h, f_a = True, False
            elif any(v in val_g for v in v_ayer): f_a, f_h = True, False
            else: f_h = f_a = False
            continue
        
        contrato = str(cells[4].get('formattedValue', '')).replace('.0', '').strip()
        if contrato and current_date_asig:
            asig_map[contrato] = current_date_asig
            if f_h: asig_hoy += 1
            if f_a: asig_ayer += 1

        if 'userEnteredValue' in cells[1]:
            bg_gen = cells[1].get('effectiveFormat', {}).get('backgroundColor', {})
            r, g, b = (bg_gen.get('red', 0.0), bg_gen.get('green', 0.0), bg_gen.get('blue', 0.0)) if bg_gen else (1.0, 1.0, 1.0)
            if abs(r-0.851) < 0.03 and abs(g-0.851) < 0.03: p_adecuacion += 1
            elif (abs(r-0.937) < 0.02) or (r > 0.9 and g < 0.1 and b > 0.9): p_realizar += 1

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
    df_main['Fecha_Asignacion'] = df_main['Contrato_Str'].map(asig_map)
    
    f_inst = pd.to_datetime(df_main['Fecha_Limpia'], errors='coerce')
    f_asig = pd.to_datetime(df_main['Fecha_Asignacion'], errors='coerce')
    df_main['Dias_Realizacion'] = (f_inst - f_asig).dt.days
    df_main.loc[df_main['Dias_Realizacion'] < 0, 'Dias_Realizacion'] = 0
    
    df_main['Metraje'] = pd.to_numeric(df_main['Metros '], errors='coerce').fillna(0)
    df_main['Tensores'] = pd.to_numeric(df_main['Tensores'], errors='coerce').fillna(0)
    col_onu = [c for c in df_main.columns if 'Serial ONU' in c or 'Serial' in c]
    df_main['ONU_Final'] = df_main[col_onu[0]] if col_onu else "N/A"

    def extract_ruta(rows, target_dt):
        variantes = get_fecha_variantes(target_dt)
        dias_sem = ["lunes","martes","miércoles","jueves","viernes","sábado","domingo"]
        found, clients = False, []
        for r in rows:
            cells = r.get('values', [])
            if len(cells) < 13: continue
            val_j, val_h = cells[9].get('formattedValue', '').lower().strip(), cells[7].get('formattedValue', '').strip()
            if any(v in val_j for v in variantes) and not val_h: found = True; continue
            if found:
                if "/" in val_j and any(d in val_j for d in dias_sem) and not val_h: break
                if val_h and len(val_j) > 2:
                    bg = cells[9].get('effectiveFormat', {}).get('backgroundColor', {})
                    r_c, g_c, b_c = (bg.get('red', 0.0), bg.get('green', 0.0), bg.get('blue', 0.0)) if bg else (1.0, 1.0, 1.0)
                    color = "white"
                    if g_c > 0.8 and r_c < 0.5: color = "green"
                    elif abs(r_c-0.851) < 0.05: color = "grey"
                    elif g_c > 0.9 and b_c > 0.9 and r_c < 0.5: color = "cyan"
                    clients.append({'contrato': val_h, 'nombre': val_j.upper(), 'zona': cells[12].get('formattedValue', '').strip().upper(), 'tipo': "M" if "mudanza" in cells[4].get('formattedValue', '').lower() else "N", 'color': color})
        return clients

    ruta_hoy = extract_ruta(rows_ruta, ahora_vzla)
    ruta_ayer = extract_ruta(rows_ruta, ayer_laboral_dt)
    return df_main, asig_map, p_realizar, p_adecuacion, asig_hoy, asig_ayer, ruta_hoy, ruta_ayer

def hybrid_search(query, df_installed, asig_map, rows_ruta, rows_asig):
    query_clean = query.strip()
    
    # --- 1. BUSCAR EN INSTALADOS ---
    match = df_installed[df_installed['Contrato_Str'] == query_clean]
    if not match.empty:
        res = match.iloc[0]
        fecha_asig_dt = asig_map.get(query_clean)
        fecha_asig_str = fecha_asig_dt.strftime('%d/%m/%y') if pd.notnull(fecha_asig_dt) else "N/A"
        
        disclaimer = None
        try:
            adecu_id = "1Y4AkWf4kSRrJcny9SUtW0qY5jzrcizpU3xjdBdjbmqY"
            creds_info = st.secrets["connections"]["gsheets"]
            creds = service_account.Credentials.from_service_account_info(creds_info)
            service = build('sheets', 'v4', credentials=creds)
            res_ad = service.spreadsheets().values().get(spreadsheetId=adecu_id, range="A:B").execute()
            for r_ad in res_ad.get('values', []):
                if len(r_ad) >= 1 and str(r_ad[0]).strip() == query_clean:
                    disclaimer = f"⚠️ EN ADECUACIÓN DESDE: {r_ad[1] if len(r_ad)>1 else 'N/A'}"
                    break
        except: pass

        return {
            "tipo": "INSTALADO",
            "status": "✅ 100% INSTALADO",
            "cliente": str(res['Nombre del cliente']).upper(),
            "fecha_asig": fecha_asig_str,
            "fecha_inst": res['Fecha_Limpia'].strftime('%d/%m/%y'),
            "tardo": int(res['Dias_Realizacion']) if pd.notnull(res['Dias_Realizacion']) else "N/A",
            "metros": int(res['Metraje']),
            "tensores": int(res['Tensores']),
            "onu": res['ONU_Final'],
            "disclaimer": disclaimer
        }

    # --- 2. BUSCAR EN LIBRO DE ADECUACIONES ---
    try:
        adecu_id = "1Y4AkWf4kSRrJcny9SUtW0qY5jzrcizpU3xjdBdjbmqY"
        creds_info = st.secrets["connections"]["gsheets"]
        creds = service_account.Credentials.from_service_account_info(creds_info)
        service = build('sheets', 'v4', credentials=creds)
        res_ad = service.spreadsheets().values().get(spreadsheetId=adecu_id, range="A:D").execute()
        adecu_rows = res_ad.get('values', [])
        
        for row in adecu_rows:
            if len(row) >= 1 and str(row[0]).strip() == query_clean:
                fecha_adecu = row[1] if len(row) > 1 else "N/A"
                motivo = row[2] if len(row)>2 else "No especificado"
                trabajo = row[3] if len(row)>3 else "No especificado"
                
                fecha_programada_ruta = None
                zona_encontrada = "N/A"
                nombre_cliente = "DESCONOCIDO"
                header_temporal = "SIN ASIGNAR"

                for r_ruta in rows_ruta:
                    c_ruta = r_ruta.get('values', [])
                    if len(c_ruta) < 10: continue
                    val_j = str(c_ruta[9].get('formattedValue', '')).upper()
                    
                    # DETECCIÓN DE CABECERAS (Fecha o Pendientes)
                    if "/" in val_j and any(d in val_j for d in ["LUNES", "MARTES", "MIÉRCOLES", "JUEVES", "VIERNES", "SÁBADO", "DOMINGO"]):
                        header_temporal = val_j
                        continue
                    elif "PENDIENTE" in val_j:
                        header_temporal = "PENDIENTE EN RUTA"
                        continue
                    
                    if str(c_ruta[7].get('formattedValue', '')).strip() == query_clean:
                        fecha_programada_ruta = header_temporal
                        zona_encontrada = str(c_ruta[12].get('formattedValue', '')).upper()
                        nombre_cliente = str(c_ruta[9].get('formattedValue', '')).upper()
                        break

                if zona_encontrada == "N/A":
                    for r_asig in rows_asig:
                        c_asig = r_asig.get('values', [])
                        if len(c_asig) > 4 and str(c_asig[4].get('formattedValue', '')).strip() == query_clean:
                            zona_encontrada = str(c_asig[1].get('formattedValue', '')).upper()
                            break

                if fecha_programada_ruta:
                    status_final = f"📍 ADECUACIÓN: {fecha_programada_ruta}"
                    color_alerta = "#00ffff" 
                else:
                    status_final = f"⚠️ CLIENTE EN ESPERA DESDE {fecha_adecu}"
                    color_alerta = "#ff4b4b" 

                return {
                    "tipo": "ADECUACION",
                    "status": status_final,
                    "cliente": nombre_cliente,
                    "fecha_asig": asig_map.get(query_clean).strftime('%d/%m/%y') if pd.notnull(asig_map.get(query_clean)) else "PENDIENTE",
                    "zona": zona_encontrada,
                    "motivo": motivo,
                    "trabajo": trabajo,
                    "color": color_alerta
                }
    except: pass

    # --- 3. BUSCAR EN RUTAS NORMALES ---
    current_date_header = "SIN FECHA"
    for r in rows_ruta:
        cells = r.get('values', [])
        if len(cells) < 10: continue
        val_j = str(cells[9].get('formattedValue', '')).upper()
        
        if "/" in val_j and any(d in val_j for d in ["LUNES", "MARTES", "MIÉRCOLES", "JUEVES", "VIERNES", "SÁBADO", "DOMINGO"]):
            current_date_header = val_j
            continue
        elif "PENDIENTE" in val_j:
            current_date_header = "PENDIENTE EN RUTA"
            continue

        if str(cells[7].get('formattedValue', '')).strip() == query_clean:
            return {
                "tipo": "EN_RUTA",
                "status": f"📍 {current_date_header}",
                "cliente": str(cells[9].get('formattedValue', '')).upper(),
                "zona": str(cells[12].get('formattedValue', '')).upper() if len(cells) > 12 else "N/A",
                "fecha_asig": asig_map.get(query_clean).strftime('%d/%m/%y') if pd.notnull(asig_map.get(query_clean)) else "PENDIENTE"
            }
    return None

try:
    rows_asig, rows_ruta, df_raw_main = fetch_all_data()
    df, asig_map, p_realizar, p_adecuacion, asig_hoy, asig_ayer, ruta_hoy, ruta_ayer = process_data(rows_asig, rows_ruta, df_raw_main)
    
    with st.sidebar:
        st.markdown("### 🔍 Buscador de Contratos")
        search_query = st.text_input("Ingresa el número de contrato:")
        if search_query:
            res = hybrid_search(search_query, df, asig_map, rows_ruta, rows_asig)
        
            if res:
                if res["tipo"] == "INSTALADO":
                    disc = res.get('disclaimer') if res.get('disclaimer') else ""
                    disc_html = f"<p style='color:#ff9900; font-size:11px; font-weight:bold; margin-bottom:10px;'>{disc}</p>" if disc else ""
                    
                    card_instalado = f"""<div style="background: rgba(0, 212, 255, 0.1); border: 1px solid #00d4ff; padding: 15px; border-radius: 10px; margin-top: 10px;">
<p style='color:#00d4ff; font-weight:600; margin-bottom:5px;'>{res['status']}</p>
{disc_html}
<p style='font-size:12px; margin:0; color:white;'><b>CLIENTE:</b> {res['cliente']}</p>
<p style='font-size:12px; margin:0; color:white;'><b>FECHA ASIG:</b> {res['fecha_asig']}</p>
<p style='font-size:12px; margin:0; color:white;'><b>FECHA INST:</b> {res['fecha_inst']}</p>
<p style='color:#00ff00; font-size:11px; margin-top:5px; font-weight:bold;'>EL CLIENTE TARDÓ {res['tardo']} DÍAS</p>
<hr style='margin: 8px 0; border: 0; border-top: 1px solid rgba(255,255,255,0.1);'>
<p style='font-size:12px; margin:0; color:white;'><b>METRAJE:</b> {res['metros']} mts</p>
<p style='font-size:12px; margin:0; color:white;'><b>TENSORES:</b> {res['tensores']} und</p>
<p style='font-size:12px; margin:0; color:white;'><b>ONU:</b> {res['onu']}</p>
</div>"""
                    st.markdown(card_instalado, unsafe_allow_html=True)
                
                elif res["tipo"] == "ADECUACION":
                    card_adecu = f"""<div style="background: rgba(255, 255, 255, 0.05); border: 1px solid {res['color']}; padding: 15px; border-radius: 10px; margin-top: 10px;">
<p style='color:{res['color']}; font-weight:600; font-size:13px; margin-bottom:8px;'>{res['status']}</p>
<p style='font-size:12px; margin:0; color:white;'><b>ZONA:</b> {res['zona']}</p>
<p style='font-size:12px; margin:0; color:white;'><b>FECHA ASIG:</b> {res['fecha_asig']}</p>
<hr style='margin: 8px 0; border: 0; border-top: 1px solid rgba(255,255,255,0.1);'>
<p style='font-size:12px; margin:0; color:white;'><b>MOTIVO:</b> {res['motivo']}</p>
<p style='font-size:12px; margin:0; color:white;'><b>TRABAJO:</b> {res['trabajo']}</p>
</div>"""
                    st.markdown(card_adecu, unsafe_allow_html=True)
                
                else:
                    card_ruta = f"""<div style="background: rgba(255, 153, 0, 0.1); border: 1px solid #ff9900; padding: 15px; border-radius: 10px; margin-top: 10px;">
<p style='color:#ff9900; font-weight:600; margin-bottom:5px;'>{res['status']}</p>
<p style='font-size:12px; margin:0; color:white;'><b>CLIENTE:</b> {res['cliente']}</p>
<p style='font-size:12px; margin:0; color:white;'><b>FECHA ASIG:</b> {res['fecha_asig']}</p>
<p style='font-size:12px; margin:0; color:white;'><b>ZONA:</b> {res['zona']}</p>
</div>"""
                    st.markdown(card_ruta, unsafe_allow_html=True)
            else:
                st.warning("Contrato no encontrado.")

    # --- HEADER CON LOGOS ACERCADOS ---
    col_espacio, col_logo_izq, col_titulo, col_logo_der = st.columns([0.6, 1, 3.5, 1.5])

    with col_espacio:
        st.write("") 

    with col_logo_izq:
        try: 
            st.image("logo_izq.png", width=150) 
        except: 
            st.write("")
        
    with col_titulo:
        st.markdown("<h1 style='text-align: center; color: white; margin-bottom: 0;'>💎 FIBRA RAQ INTELLIGENCE</h1>", unsafe_allow_html=True)
        st.markdown(f"<p style='text-align: center; color: #00d4ff; margin-top: 0;'>{ahora_vzla.strftime('%d/%m/%Y %I:%M %p')}</p>", unsafe_allow_html=True)

    with col_logo_der:
        try: 
            st.image("logo_der.png", width=150)
        except: 
            st.write("")
    
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
    with k5: st.markdown(f"<div class='metric-container'><div class='m-label'>Asig. Hoy</div><div class='m-value'>{asig_hoy}</div></div>", unsafe_allow_html=True)
    with k6: st.markdown(f"<div class='metric-container'><div class='m-label'>Asig. Ayer Lab.</div><div class='m-value'>{asig_ayer}</div></div>", unsafe_allow_html=True)
    with k7:
        avg_s = df[(df['Fecha_Limpia'] >= i_s) & (df['Fecha_Limpia'] <= f_s)]['Dias_Realizacion'].mean()
        avg_s_str = f"{avg_s:.1f}" if pd.notnull(avg_s) else "0"
        st.markdown(f"<div class='metric-container'><div class='m-label'>Media Sem. Actual</div><div class='m-value'>{avg_s_str}</div><div class='m-sub'>Días de respuesta</div></div>", unsafe_allow_html=True)
    with k8:
        avg_p = df[(df['Fecha_Limpia'] >= i_p) & (df['Fecha_Limpia'] <= f_p)]['Dias_Realizacion'].mean()
        avg_p_str = f"{avg_p:.1f}" if pd.notnull(avg_p) else "0"
        st.markdown(f"<div class='metric-container'><div class='m-label'>Media Sem. Pasada</div><div class='m-value'>{avg_p_str}</div><div class='m-sub'>Días de respuesta</div></div>", unsafe_allow_html=True)

    st.markdown("<div class='section-title'>Consumo de Materiales</div>", unsafe_allow_html=True)
    m1, m2, m3, m4 = st.columns(4)
    def get_mat_str(df_filt):
        mts = df_filt['Metraje'].sum()
        und = df_filt['Tensores'].sum()
        return f"{mts:,.0f}m | {int(und)}⚙️"
    with m1: st.markdown(f"<div class='metric-container'><div class='m-label'>Gastado Hoy</div><div class='m-value' style='font-size:18px;'>{get_mat_str(df[df['Fecha_Limpia'] == hoy_vzla])}</div></div>", unsafe_allow_html=True)
    with m2: st.markdown(f"<div class='metric-container'><div class='m-label'>Gastado Ayer</div><div class='m-value' style='font-size:18px;'>{get_mat_str(df[df['Fecha_Limpia'] == (hoy_vzla - timedelta(days=1))])}</div></div>", unsafe_allow_html=True)
    with m3: st.markdown(f"<div class='metric-container'><div class='m-label'>Gastado Sem. Actual</div><div class='m-value' style='font-size:18px;'>{get_mat_str(df[(df['Fecha_Limpia'] >= i_s) & (df['Fecha_Limpia'] <= f_s)])}</div></div>", unsafe_allow_html=True)
    with m4: st.markdown(f"<div class='metric-container'><div class='m-label'>Gastado Sem. Pasada</div><div class='m-value' style='font-size:18px;'>{get_mat_str(df[(df['Fecha_Limpia'] >= i_p) & (df['Fecha_Limpia'] <= f_p)])}</div></div>", unsafe_allow_html=True)

    col_aud_1, col_aud_2 = st.columns(2)
    with col_aud_1:
        with st.expander("🔍 Auditoría: Semana Actual"):
            df_s_a = df[(df['Fecha_Limpia'] >= i_s) & (df['Fecha_Limpia'] <= f_s)].copy()
            if not df_s_a.empty:
                df_audit = df_s_a[['Contrato_Str', 'Nombre del cliente', 'Fecha_Asignacion', 'Fecha_Limpia', 'Dias_Realizacion']].copy()
                df_audit.columns = ['Contrato', 'Cliente', 'Asignado', 'Instalado', 'Días']
                st.dataframe(df_audit, use_container_width=True, hide_index=True)
    with col_aud_2:
        with st.expander("🔍 Auditoría: Semana Pasada"):
            df_s_p = df[(df['Fecha_Limpia'] >= i_p) & (df['Fecha_Limpia'] <= f_p)].copy()
            if not df_s_p.empty:
                df_audit_p = df_s_p[['Contrato_Str', 'Nombre del cliente', 'Fecha_Asignacion', 'Fecha_Limpia', 'Dias_Realizacion']].copy()
                df_audit_p.columns = ['Contrato', 'Cliente', 'Asignado', 'Instalado', 'Días']
                st.dataframe(df_audit_p, use_container_width=True, hide_index=True)

    st.markdown("<div class='section-title'>Estado de Asignaciones (General)</div>", unsafe_allow_html=True)
    a1, a2, a3, a4 = st.columns(4)
    with a1: st.markdown(f"<div class='metric-container'><div class='m-label'>PENDIENTES POR REALIZAR</div><div class='m-value'>{p_realizar}</div></div>", unsafe_allow_html=True)
    with a2: st.markdown(f"<div class='metric-container'><div class='m-label'>ADECUACIÓN O CAJA</div><div class='m-value'>{p_adecuacion}</div></div>", unsafe_allow_html=True)

    st.markdown("<div class='section-title'>Control de Ruta y Materiales</div>", unsafe_allow_html=True)
    c_r1, c_r2 = st.columns(2)
    def render_c(c): return f"<div class='cliente-item bg-{c['color']}'>{str(int(float(c['contrato'])))} | {c['nombre']} | {c['zona']} | ({c['tipo']})</div>"
    with c_r1:
        with st.expander(f"📍 RUTA HOY ({len(ruta_hoy)})", expanded=False):
            st.markdown(f"<div class='ruta-box'>{''.join([render_c(c) for c in ruta_hoy])}</div>", unsafe_allow_html=True)
    with c_r2:
        with st.expander(f"📍 RUTA AYER LAB. ({len(ruta_ayer)})", expanded=False):
            st.markdown(f"<div class='ruta-box'>{''.join([render_c(c) for c in ruta_ayer])}</div>", unsafe_allow_html=True)
    
    c_m1, c_m2 = st.columns(2)
    with c_m1:
        df_hoy_mat = df[df['Fecha_Limpia'] == hoy_vzla]
        with st.expander(f"📍 MATERIALES HOY ({len(df_hoy_mat)})", expanded=False):
            items_mat_hoy = "".join([f"<div class='cliente-item bg-green'>{str(int(float(r['Contrato_Str'])))} | {r['Nombre del cliente']} | 📏{int(r['Metraje'])}m | ⚙️{int(r['Tensores'])} | 🆔{str(r['ONU_Final'])[-6:]}</div>" for _, r in df_hoy_mat.iterrows()])
            st.markdown(f"<div class='ruta-box'>{items_mat_hoy}</div>", unsafe_allow_html=True)
    with c_m2:
        df_ayer_mat = df[df['Fecha_Limpia'] == ayer_laboral_vzla]
        with st.expander(f"📍 MATERIALES AYER ({len(df_ayer_mat)})", expanded=False):
            items_mat_ayer = "".join([f"<div class='cliente-item bg-green'>{str(int(float(r['Contrato_Str'])))} | {r['Nombre del cliente']} | 📏{int(r['Metraje'])}m | ⚙️{int(r['Tensores'])} | 🆔{str(r['ONU_Final'])[-6:]}</div>" for _, r in df_ayer_mat.iterrows()])
            st.markdown(f"<div class='ruta-box'>{items_mat_ayer}</div>", unsafe_allow_html=True)

    st.markdown("""<div class='legend-container'><div class='legend-item'><div class='legend-color' style='background:#00ff00;'></div><span>Finalizado</span></div><div class='legend-item'><div class='legend-color' style='background:#b7b7b7;'></div><span>Adecuación / Caja</span></div><div class='legend-item'><div class='legend-color' style='background:#00ffff;'></div><span>Devuelto / Inconv.</span></div><div class='legend-item'><div class='legend-color' style='background:#ffffff;'></div><span>Pendiente</span></div></div>""", unsafe_allow_html=True)

    st.markdown("<div class='section-title'>Análisis Histórico</div>", unsafe_allow_html=True)
    col_h1, col_h2 = st.columns([1, 2])
    with col_h1:
        df_hist = df.dropna(subset=['Fecha_DT']).copy()
        df_hist = df_hist[df_hist['Fecha_DT'].dt.date <= hoy_vzla]
        df_hist['Mes_Num'] = df_hist['Fecha_DT'].dt.month; df_hist['Año'] = df_hist['Fecha_DT'].dt.year.astype(int)
        meses_n = {1:'Enero', 2:'Febrero', 3:'Marzo', 4:'Abril', 5:'Mayo', 6:'Junio', 7:'Julio', 8:'Agosto', 9:'Septiembre', 10:'Octubre', 11:'Noviembre', 12:'Diciembre'}
        df_hist['Mes_Nombre'] = df_hist['Mes_Num'].map(meses_n)
        hist = df_hist.groupby(['Año', 'Mes_Num', 'Mes_Nombre']).agg(Total=('Contrato', 'size'), Media_Dias=('Dias_Realizacion', 'mean'), Total_Mts=('Metraje', 'sum'), Total_Und=('Tensores', 'sum')).reset_index()
        hist = hist.sort_values(['Año', 'Mes_Num'], ascending=False)
        for _, row in hist.iterrows():
            media_val = f"{row['Media_Dias']:.1f}" if pd.notnull(row['Media_Dias']) else "0"
            st.markdown(f"<div class='month-row'><span>{row['Mes_Nombre']} {int(row['Año'])}</span><span><span style='color:#00d4ff; font-weight:bold;'>{row['Total']}</span><span style='color:#8899a6; font-size:10px; margin-left:10px;'>Media: {media_val}d | 📏{row['Total_Mts']:,.0f}m | ⚙️{int(row['Total_Und'])}</span></span></div>", unsafe_allow_html=True)
    with col_h2: st.markdown(f"<div style='background: linear-gradient(135deg, #00d4ff 0%, #0072ff 100%); padding: 40px; border-radius: 20px; text-align: center; color: white;'><div style='font-size: 14px; text-transform: uppercase; opacity: 0.9;'>Total Global</div><div style='font-size: 72px; font-weight: 800;'>{len(df):,}</div><div style='font-size: 13px; opacity: 0.7;'>Récord acumulado</div></div>", unsafe_allow_html=True)
except Exception as e:
    st.error(f"Error detectado: {e}")
