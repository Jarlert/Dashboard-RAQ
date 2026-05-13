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

st_autorefresh(interval=60000, key="datarefresh")

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
    .metric-container { 
        background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); 
        padding: 15px; border-radius: 10px; text-align: center; height: 110px;
        display: flex; flex-direction: column; justify-content: center; align-items: center;
        margin-bottom: 10px;
    }
    .m-label { color: #8899a6; font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 5px; }
    .m-value { color: #ffffff; font-size: 22px; font-weight: 700; line-height: 1; }
    .m-sub { color: #00d4ff; font-size: 9px; margin-top: 5px; font-weight: 400; }
    @media (max-width: 768px) {
        .metric-container { height: 90px !important; }
        .m-value { font-size: 18px !important; }
    }
    .ruta-box { background: rgba(255, 255, 255, 0.02); border-radius: 10px; padding: 10px; height: 380px; overflow-y: auto; }
    .ruta-header { font-size: 11px; font-weight: 600; border-bottom: 1px solid #444; margin-bottom: 8px; display: flex; justify-content: space-between; padding-bottom: 3px;}
    .cliente-item { font-size: 9px; padding: 6px 10px; margin-bottom: 3px; border-radius: 4px; color: #000 !important; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; border: 1px solid rgba(0,0,0,0.1); }
    .bg-white { background-color: #ffffff; color: #000 !important; }
    .bg-green { background-color: #00ff00; color: #000 !important; }
    .bg-grey { background-color: #b7b7b7; color: #000 !important; }
    .bg-cyan { background-color: #00ffff; color: #000 !important; }
    .month-row { display: flex; justify-content: space-between; padding: 8px; background: rgba(255, 255, 255, 0.03); margin-bottom: 3px; border-radius: 6px; font-size: 14px; }
    .search-result-card { background: rgba(0, 212, 255, 0.1); border: 1px solid #00d4ff; padding: 15px; border-radius: 10px; margin-top: 10px; }
    .legend-item { display: flex; align-items: center; margin-bottom: 8px; font-size: 12px; }
    .legend-color { width: 15px; height: 15px; border-radius: 3px; margin-right: 10px; border: 1px solid rgba(255,255,255,0.2); }
    [data-testid="stExpander"] { background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 10px; margin-bottom: 5px; }
    </style>
    """, unsafe_allow_html=True)

# 3. MOTOR DE CARGA (CONGELADO - Protegiendo Febrero/Marzo)
@st.cache_data(ttl=5)
def load_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    creds_info = st.secrets["connections"]["gsheets"]
    creds = service_account.Credentials.from_service_account_info(creds_info)
    service = build('sheets', 'v4', credentials=creds)
    asig_id = "1KK1Ng6lF-dGSzOt46kVsqAnY0MG4v-Ggp4S8x1IZokQ"
    
    asig_data = service.spreadsheets().values().get(spreadsheetId=asig_id, range="ASIGNADOS!A:G").execute()
    rows_asig = asig_data.get('values', [])
    asig_map = {}
    current_date = None
    for row in rows_asig:
        if len(row) < 7: continue
        val_g = str(row[6]).lower()
        if "asignación raq" in val_g:
            try: current_date = pd.to_datetime(val_g.split(' ')[-1], dayfirst=True).date()
            except: pass
        contrato = str(row[4]).replace('.0', '').strip()
        if contrato and current_date and contrato not in asig_map: asig_map[contrato] = current_date

    df_raw = conn.read(worksheet="Base de Datos ", ttl=0) 
    df = df_raw.dropna(subset=["Marca temporal"], how='all').copy()
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

    df['Fecha_Limpia'] = df["Marca temporal"].apply(parse_individual_date)
    df['Fecha_DT'] = pd.to_datetime(df['Fecha_Limpia'], errors='coerce')
    df['Contrato_Str'] = df['Contrato'].astype(str).str.replace('.0', '', regex=False).str.strip()
    df['Fecha_Asignacion'] = df['Contrato_Str'].map(asig_map)
    
    f_inst = pd.to_datetime(df['Fecha_Limpia'], errors='coerce')
    f_asig = pd.to_datetime(df['Fecha_Asignacion'], errors='coerce')
    df['Dias_Realizacion'] = (f_inst - f_asig).dt.days
    df.loc[df['Dias_Realizacion'] < 0, 'Dias_Realizacion'] = 0

    df['Metraje'] = pd.to_numeric(df['Metros '], errors='coerce').fillna(0)
    df['Tensores'] = pd.to_numeric(df['Tensores'], errors='coerce').fillna(0)
    col_onu = [c for c in df.columns if 'Serial ONU' in c or 'Serial' in c]
    df['ONU_Final'] = df[col_onu[0]] if col_onu else "N/A"
    return df, asig_map

# 4. AGREGADOS ASIGNADOS
@st.cache_data(ttl=30)
def load_asignados_aggregates(asig_map):
    try:
        creds_info = st.secrets["connections"]["gsheets"]
        creds = service_account.Credentials.from_service_account_info(creds_info)
        service = build('sheets', 'v4', credentials=creds)
        spreadsheet_id = "1KK1Ng6lF-dGSzOt46kVsqAnY0MG4v-Ggp4S8x1IZokQ"
        result = service.spreadsheets().get(spreadsheetId=spreadsheet_id, ranges=["ASIGNADOS!A:G"], includeGridData=True).execute()
        rows = result['sheets'][0]['data'][0].get('rowData', [])
        p_realizar, p_adecuacion, asig_hoy, asig_ayer = 0, 0, 0, 0
        v_hoy, v_ayer = get_fecha_variantes(ahora_vzla), get_fecha_variantes(ayer_laboral_dt)
        f_h, f_a = False, False
        for row in rows:
            cells = row.get('values', [])
            if not cells: continue
            f_val = cells[6].get('formattedValue', '').lower().strip() if len(cells) > 6 else ""
            if any(v in f_val for v in v_hoy): f_h = True; f_a = False; continue
            if any(v in f_val for v in v_ayer): f_a = True; f_h = False; continue
            if f_h or f_a:
                if "/" in f_val and any(d in f_val for d in ["lunes","martes","miércoles","jueves","viernes","sábado","domingo"]):
                    f_h = f_a = False; continue
                has_contract = len(cells) > 4 and cells[4].get('formattedValue', '').strip() != ""
                if has_contract:
                    if f_h: asig_hoy += 1
                    if f_a: asig_ayer += 1
            if len(cells) > 1 and 'userEnteredValue' in cells[1]:
                bg_gen = cells[1].get('effectiveFormat', {}).get('backgroundColor', {})
                r, g, b = bg_gen.get('red', 0.0), bg_gen.get('green', 0.0), bg_gen.get('blue', 0.0)
                if not bg_gen: r = g = b = 1.0
                if (abs(r-0.937) < 0.02) or (r > 0.9 and g < 0.1 and b > 0.9): p_realizar += 1
                elif abs(r-0.851) < 0.03 and abs(g-0.851) < 0.03: p_adecuacion += 1
        return p_realizar, p_adecuacion, asig_hoy, asig_ayer
    except: return 0, 0, 0, 0

# 5. MOTOR RUTA POR FECHA
@st.cache_data(ttl=30)
def get_ruta_by_date(fecha_dt):
    try:
        creds_info = st.secrets["connections"]["gsheets"]
        creds = service_account.Credentials.from_service_account_info(creds_info)
        service = build('sheets', 'v4', credentials=creds)
        spreadsheet_id = "1KK1Ng6lF-dGSzOt46kVsqAnY0MG4v-Ggp4S8x1IZokQ"
        result = service.spreadsheets().get(spreadsheetId=spreadsheet_id, ranges=["RUTAS PRE PLANIFICADAS!A:N"], includeGridData=True).execute()
        rows = result['sheets'][0]['data'][0].get('rowData', [])
        variantes = get_fecha_variantes(fecha_dt)
        dias_semana = ["lunes", "martes", "miercoles", "miércoles", "jueves", "viernes", "sabado", "sábado", "domingo"]
        found, clientes = False, []
        for row in rows:
            cells = row.get('values', [])
            if not cells or len(cells) < 13: continue
            val_j, val_h = cells[9].get('formattedValue', '').lower().strip(), cells[7].get('formattedValue', '').strip()
            if any(v in val_j for v in variantes) and not val_h: found = True; continue
            if found:
                if "/" in val_j and any(d in val_j for d in dias_semana) and not val_h: break
                if val_h and len(val_j) > 2:
                    try:
                        tipo = "M" if "mudanza" in cells[4].get('formattedValue', '').lower() else "N"
                        bg = cells[9].get('effectiveFormat', {}).get('backgroundColor', {})
                        if not bg: r = g = b = 1.0
                        else: r, g, b = bg.get('red', 0.0), bg.get('green', 0.0), bg.get('blue', 0.0)
                        color_key = "white"
                        if g > 0.8 and r < 0.5 and b < 0.5: color_key = "green"
                        elif abs(r-0.851) < 0.05: color_key = "grey"
                        elif g > 0.9 and b > 0.9 and r < 0.2: color_key = "cyan"
                        elif r > 0.9 and g < 0.2 and b > 0.9: color_key = "white"
                        clientes.append({'contrato': val_h, 'nombre': val_j.upper(), 'zona': cells[12].get('formattedValue', '').strip().upper(), 'tipo': tipo, 'color': color_key})
                    except: continue
        return clientes
    except: return []

# 6. MOTOR DE BÚSQUEDA HÍBRIDO
def hybrid_search(query, df_installed, asig_map):
    query_clean = query.strip()
    match = df_installed[df_installed['Contrato_Str'] == query_clean]
    fecha_asig_dt = asig_map.get(query_clean)
    fecha_asig_str = fecha_asig_dt.strftime('%d/%m/%y') if pd.notnull(fecha_asig_dt) else "N/A"
    if not match.empty:
        res = match.iloc[0]
        f_inst_str = res['Fecha_Limpia'].strftime('%d/%m/%y') if pd.notnull(res['Fecha_Limpia']) else "N/A"
        tardo_val = res['Dias_Realizacion'] if pd.notnull(res['Dias_Realizacion']) else "N/A"
        return {"status": "✅ 100% INSTALADO", "cliente": res['Nombre del cliente'], "fecha_asig": fecha_asig_str, "fecha_inst": f_inst_str, "tardo": tardo_val, "metros": int(res['Metraje']), "tensores": int(res['Tensores']), "onu": res['ONU_Final']}
    try:
        creds_info = st.secrets["connections"]["gsheets"]
        creds = service_account.Credentials.from_service_account_info(creds_info)
        service = build('sheets', 'v4', credentials=creds)
        spreadsheet_id = "1KK1Ng6lF-dGSzOt46kVsqAnY0MG4v-Ggp4S8x1IZokQ"
        result = service.spreadsheets().get(spreadsheetId=spreadsheet_id, ranges=["RUTAS PRE PLANIFICADAS!A:S"], includeGridData=True).execute()
        rows = result['sheets'][0]['data'][0].get('rowData', [])
        curr_date, is_pend = "DESCONOCIDA", False
        for row in rows:
            cells = row.get('values', [])
            if not cells: continue
            val_j, val_h = cells[9].get('formattedValue', '').lower().strip() if len(cells) > 9 else "", cells[7].get('formattedValue', '').strip() if len(cells) > 7 else ""
            if "pendiente" in val_j: is_pend = True
            if "/" in val_j and any(d in val_j for d in ["lunes","martes","miércoles","jueves","viernes","sábado","domingo"]) and not val_h:
                curr_date = val_j; is_pend = False
            if val_h == query_clean:
                zona = cells[12].get('formattedValue', '').upper() if len(cells) > 12 else "N/A"
                if is_pend:
                    motivo = cells[17].get('formattedValue', 'SIN MOTIVO').strip() if len(cells) > 17 else "N/A"
                    status = f"⚠️ PENDIENTE POR: {motivo.upper()}"
                    if "adecuaci" in motivo.lower():
                        trabajo = cells[18].get('formattedValue', 'N/A').strip() if len(cells) > 18 else "N/A"
                        status += f" | TRABAJO: {trabajo.upper()}"
                    return {"status": status, "cliente": val_j.upper(), "zona": zona, "fecha_asig": fecha_asig_str}
                v_hoy, v_mañana = get_fecha_variantes(ahora_vzla), get_fecha_variantes(hoy_vzla + timedelta(days=1))
                if any(v in curr_date for v in v_hoy): f_status = "🚚 EN RUTA DE HOY"
                elif any(v in curr_date for v in v_mañana): f_status = "📅 EN RUTA DE MAÑANA"
                else: f_status = f"🗓️ EN RUTA PARA {curr_date.split(' ')[-1]}"
                return {"status": f_status, "cliente": val_j.upper(), "zona": zona, "fecha_asig": fecha_asig_str}
    except: pass
    return None

try:
    df, asig_map = load_data()
    p_realizar, p_adecuacion, asig_hoy, asig_ayer = load_asignados_aggregates(asig_map)
    ruta_hoy, ruta_ayer_lab = get_ruta_by_date(ahora_vzla), get_ruta_by_date(ayer_laboral_dt)
    
    with st.sidebar:
        st.markdown("### 🔍 Buscador de Contratos")
        search_query = st.text_input("Ingresa el número de contrato:")
        if search_query:
            res = hybrid_search(search_query, df, asig_map)
            if res:
                if "INSTALADO" in res['status']:
                    info_extra = f"<p style='font-size:12px; margin:0;'><b>FECHA ASIG:</b> {res['fecha_asig']}</p><p style='font-size:12px; margin:0;'><b>FECHA INST:</b> {res['fecha_inst']}</p><p style='color:#00ff00; font-size:11px; margin-top:5px;'><b>EL CLIENTE TARDÓ {res['tardo']} DÍAS EN REALIZARSE</b></p><p style='font-size:12px; margin:0;'><b>METRAJE:</b> {res['metros']} mts</p><p style='font-size:12px; margin:0;'><b>TENSORES:</b> {res['tensores']} und</p><p style='font-size:12px; margin:0;'><b>ONU:</b> {res['onu']}</p>"
                else:
                    info_extra = f"<p style='font-size:12px; margin:0;'><b>FECHA ASIG:</b> {res['fecha_asig']}</p><p style='font-size:12px; margin:0;'><b>ZONA:</b> {res['zona']}</p>"
                st.markdown(f"<div class='search-result-card'><p style='color:#00d4ff; font-weight:600; margin-bottom:5px;'>{res['status']}</p><p style='font-size:12px; margin:0;'><b>CLIENTE:</b> {res['cliente']}</p>{info_extra}</div>", unsafe_allow_html=True)
            else: st.warning("Contrato no encontrado.")

    st.markdown(f"<h1 style='text-align: center; color: white;'>💎 FIBRA RAQ INTELLIGENCE</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align: center; color: #00d4ff;'>{ahora_vzla.strftime('%d/%m/%Y %I:%M %p')}</p>", unsafe_allow_html=True)
    
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

    col_aud_1, col_aud_2 = st.columns(2)
    with col_aud_1:
        with st.expander("🔍 Auditoría: Semana Actual"):
            df_s_a = df[(df['Fecha_Limpia'] >= i_s) & (df['Fecha_Limpia'] <= f_s)].copy()
            if not df_s_a.empty:
                df_audit = df_s_a[['Contrato_Str', 'Nombre del cliente', 'Fecha_Asignacion', 'Fecha_Limpia', 'Dias_Realizacion']].copy()
                df_audit.columns = ['Contrato', 'Cliente', 'Asignado', 'Instalado', 'Días']
                st.dataframe(df_audit, use_container_width=True, hide_index=True)
            else: st.info("Sin registros esta semana.")
    with col_aud_2:
        with st.expander("🔍 Auditoría: Semana Pasada"):
            df_s_p = df[(df['Fecha_Limpia'] >= i_p) & (df['Fecha_Limpia'] <= f_p)].copy()
            if not df_s_p.empty:
                df_audit_p = df_s_p[['Contrato_Str', 'Nombre del cliente', 'Fecha_Asignacion', 'Fecha_Limpia', 'Dias_Realizacion']].copy()
                df_audit_p.columns = ['Contrato', 'Cliente', 'Asignado', 'Instalado', 'Días']
                st.dataframe(df_audit_p, use_container_width=True, hide_index=True)
            else: st.info("Sin registros la semana pasada.")

    st.markdown("<div class='section-title'>Estado de Asignaciones (General)</div>", unsafe_allow_html=True)
    a1, a2, a3, a4 = st.columns(4)
    with a1: st.markdown(f"<div class='metric-container'><div class='m-label'>PENDIENTES POR REALIZAR</div><div class='m-value'>{p_realizar}</div></div>", unsafe_allow_html=True)
    with a2: st.markdown(f"<div class='metric-container'><div class='m-label'>ADECUACIÓN O CAJA</div><div class='m-value'>{p_adecuacion}</div></div>", unsafe_allow_html=True)

    st.markdown("<div class='section-title'>Control de Ruta y Materiales</div>", unsafe_allow_html=True)
    c_hoy, c_ayer, c_mat, c_leg = st.columns([1, 1, 1, 0.6])
    def render_c(c): return f"<div class='cliente-item bg-{c['color']}'>{str(int(float(c['contrato'])))} | {c['nombre']} | {c['zona']} | ({c['tipo']})</div>"
    with c_hoy: st.markdown(f"<div class='ruta-box'><div class='ruta-header'><span>RUTA HOY</span><span>TOTAL: {len(ruta_hoy)}</span></div>{''.join([render_c(c) for c in ruta_hoy])}</div>", unsafe_allow_html=True)
    with c_ayer: st.markdown(f"<div class='ruta-box'><div class='ruta-header'><span>RUTA AYER LABORAL</span><span>TOTAL: {len(ruta_ayer_lab)}</span></div>{''.join([render_c(c) for c in ruta_ayer_lab])}</div>", unsafe_allow_html=True)
    with c_mat:
        df_ayer_mat = df[df['Fecha_Limpia'] == ayer_laboral_vzla]
        items_mat = "".join([f"<div class='cliente-item bg-green'>{str(int(float(r['Contrato_Str'])))} | {r['Nombre del cliente']} | 📏{int(r['Metraje'])}m | ⚙️{int(r['Tensores'])} | 🆔{str(r['ONU_Final'])[-6:]}</div>" for _, r in df_ayer_mat.iterrows()])
        st.markdown(f"<div class='ruta-box'><div class='ruta-header'><span>MATERIALES AYER</span><span>TOTAL: {len(df_ayer_mat)}</span></div>{items_mat}</div>", unsafe_allow_html=True)
    with c_leg:
        st.markdown("""<div class='ruta-box' style='height:380px;'><div class='ruta-header'>LEYENDA</div><div class='legend-item'><div class='legend-color' style='background:#00ff00;'></div><span>Finalizado</span></div><div class='legend-item'><div class='legend-color' style='background:#b7b7b7;'></div><span>Adecuación / Caja</span></div><div class='legend-item'><div class='legend-color' style='background:#00ffff;'></div><span>Devuelto / Inconv.</span></div><div class='legend-item'><div class='legend-color' style='background:#ffffff;'></div><span>Pendiente</span></div><hr style='margin:10px 0; opacity:0.2;'><div style='font-size:10px; color:#8899a6;'>Ayer Laboral: Muestra el último día de trabajo (Viernes si hoy es Lunes).</div></div>""", unsafe_allow_html=True)

    st.markdown("<div class='section-title'>Análisis Histórico</div>", unsafe_allow_html=True)
    col_h1, col_h2 = st.columns([1, 2])
    with col_h1:
        df_hist = df.dropna(subset=['Fecha_DT']).copy()
        df_hist = df_hist[df_hist['Fecha_DT'].dt.date <= hoy_vzla]
        df_hist['Mes_Num'] = df_hist['Fecha_DT'].dt.month; df_hist['Año'] = df_hist['Fecha_DT'].dt.year.astype(int)
        meses_n = {1:'Enero', 2:'Febrero', 3:'Marzo', 4:'Abril', 5:'Mayo', 6:'Junio', 7:'Julio', 8:'Agosto', 9:'Septiembre', 10:'Octubre', 11:'Noviembre', 12:'Diciembre'}
        df_hist['Mes_Nombre'] = df_hist['Mes_Num'].map(meses_n)
        hist = df_hist.groupby(['Año', 'Mes_Num', 'Mes_Nombre']).agg(Total=('Contrato', 'size'), Media_Dias=('Dias_Realizacion', 'mean')).reset_index()
        hist = hist.sort_values(['Año', 'Mes_Num'], ascending=False)
        for _, row in hist.iterrows():
            media_val = f"{row['Media_Dias']:.1f}" if pd.notnull(row['Media_Dias']) else "0"
            st.markdown(f"<div class='month-row'><span>{row['Mes_Nombre']} {int(row['Año'])}</span><span><span style='color:#00d4ff; font-weight:bold;'>{row['Total']}</span><span style='color:#8899a6; font-size:10px; margin-left:10px;'>Media: {media_val} días</span></span></div>", unsafe_allow_html=True)
    with col_h2: st.markdown(f"<div style='background: linear-gradient(135deg, #00d4ff 0%, #0072ff 100%); padding: 40px; border-radius: 20px; text-align: center; color: white;'><div style='font-size: 14px; text-transform: uppercase; opacity: 0.9;'>Total Global</div><div style='font-size: 72px; font-weight: 800;'>{len(df):,}</div><div style='font-size: 13px; opacity: 0.7;'>Récord acumulado</div></div>", unsafe_allow_html=True)
except Exception as e:
    st.error(f"Error detectado: {e}")
