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
    .ruta-box { background: rgba(255, 255, 255, 0.02); border-radius: 10px; padding: 10px; height: 380px; overflow-y: auto; }
    .ruta-header { font-size: 11px; font-weight: 600; border-bottom: 1px solid #444; margin-bottom: 8px; display: flex; justify-content: space-between; padding-bottom: 3px;}
    .cliente-item { font-size: 9px; padding: 6px 10px; margin-bottom: 3px; border-radius: 4px; color: #000 !important; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; border: 1px solid rgba(0,0,0,0.1); }
    .bg-white { background-color: #ffffff; color: #000 !important; }
    .bg-green { background-color: #00ff00; color: #000 !important; }
    .bg-grey { background-color: #b7b7b7; color: #000 !important; }
    .bg-cyan { background-color: #00ffff; color: #000 !important; }
    .month-row { display: flex; justify-content: space-between; padding: 8px; background: rgba(255, 255, 255, 0.03); margin-bottom: 3px; border-radius: 6px; font-size: 14px; }
    .search-result-card { background: rgba(0, 212, 255, 0.1); border: 1px solid #00d4ff; padding: 15px; border-radius: 10px; margin-top: 10px; }
    [data-testid="stExpander"] { background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 10px; margin-bottom: 5px; }
    </style>
    """, unsafe_allow_html=True)

# 3. MOTOR DE CARGA OPTIMIZADO
@st.cache_data(ttl=5)
def fetch_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    creds_info = st.secrets["connections"]["gsheets"]
    creds = service_account.Credentials.from_service_account_info(creds_info)
    service = build('sheets', 'v4', credentials=creds)
    asig_id = "1KK1Ng6lF-dGSzOt46kVsqAnY0MG4v-Ggp4S8x1IZokQ"
    adecu_id = "1Y4AkWf4kSRrJcny9SUtW0qY5jzrcizpU3xjdBdjbmqY"
    
    asig_data = service.spreadsheets().get(spreadsheetId=asig_id, ranges=["ASIGNADOS!A:G", "RUTAS PRE PLANIFICADAS!A:S"], includeGridData=True).execute()
    rows_asig = asig_data['sheets'][0]['data'][0].get('rowData', [])
    rows_ruta = asig_data['sheets'][1]['data'][0].get('rowData', [])
    
    adecu_res = service.spreadsheets().values().get(spreadsheetId=adecu_id, range="A:B").execute()
    rows_adecu = adecu_res.get('values', [])
    
    df_raw = conn.read(worksheet="Base de Datos ", ttl=0)
    return rows_asig, rows_ruta, rows_adecu, df_raw

def hybrid_search(query, df_installed, asig_map, rows_ruta, rows_adecu):
    q_c = str(query).strip()
    match = df_installed[df_installed['Contrato_Str'] == q_c]
    f_asig = asig_map.get(q_c)
    f_asig_s = f_asig.strftime('%d/%m/%y') if pd.notnull(f_asig) else "N/A"
    
    adecu_msg = None
    for r in rows_adecu:
        if len(r) >= 1 and str(r[0]).strip() == q_c:
            adecu_msg = f"⚠️ EN ADECUACIÓN DESDE {r[1] if len(r)>1 else 'N/A'}"
            break

    if not match.empty:
        res = match.iloc[0]
        return {"status": "✅ 100% INSTALADO", "cliente": res['Nombre del cliente'], "fecha_asig": f_asig_s, "fecha_inst": res['Fecha_Limpia'].strftime('%d/%m/%y'), "tardo": res['Dias_Realizacion'], "metros": int(res['Metraje']), "tensores": int(res['Tensores']), "onu": res['ONU_Final'], "adecu_extra": adecu_msg}
    
    curr_date, is_pend = "DESCONOCIDA", False
    for row in rows_ruta:
        cells = row.get('values', [])
        if not cells: continue
        val_j = cells[9].get('formattedValue', '').lower().strip() if len(cells) > 9 else ""
        val_h = cells[7].get('formattedValue', '').strip() if len(cells) > 7 else ""
        if "pendiente" in val_j: is_pend = True
        if "/" in val_j and not val_h: curr_date = val_j; is_pend = False
        if val_h == q_c:
            zona = cells[12].get('formattedValue', '').upper() if len(cells) > 12 else "N/A"
            if is_pend:
                motivo = cells[17].get('formattedValue', 'SIN MOTIVO').strip() if len(cells) > 17 else "N/A"
                status = f"⚠️ PENDIENTE POR: {motivo.upper()}"
                if "adecuaci" in motivo.lower(): status += f" | TRABAJO: {cells[18].get('formattedValue', 'N/A').upper() if len(cells) > 18 else 'N/A'}"
                return {"status": status, "cliente": val_j.upper(), "zona": zona, "fecha_asig": f_asig_s, "adecu_extra": adecu_msg}
            return {"status": f"🗓️ EN RUTA ({curr_date})", "cliente": val_j.upper(), "zona": zona, "fecha_asig": f_asig_s, "adecu_extra": adecu_msg}
    return None

try:
    r_asig, r_ruta, r_adecu, df_raw = fetch_data()
    
    # Procesar Asignaciones
    asig_map = {}
    p_realizar, p_adecuacion, asig_hoy, asig_ayer = 0, 0, 0, 0
    v_hoy, v_ayer = get_fecha_variantes(ahora_vzla), get_fecha_variantes(ayer_laboral_dt)
    curr_d, f_h, f_a = None, False, False
    
    for row in r_asig:
        cells = row.get('values', [])
        if len(cells) < 7: continue
        bg = cells[6].get('effectiveFormat', {}).get('backgroundColor', {})
        val_g = cells[6].get('formattedValue', '').lower()
        if (abs(bg.get('red', 0)-1.0) < 0.1 and abs(bg.get('green', 0)-0.6) < 0.1) or "asignación raq" in val_g:
            try: curr_d = pd.to_datetime(val_g.split(' ')[-1], dayfirst=True).date()
            except: pass
            f_h = any(v in val_g for v in v_hoy); f_a = any(v in val_g for v in v_ayer)
            continue
        cont = cells[4].get('formattedValue', '').replace('.0', '').strip()
        if cont and curr_d: 
            asig_map[cont] = curr_d
            if f_h: asig_hoy += 1
            if f_a: asig_ayer += 1
        if len(cells) > 1 and 'userEnteredValue' in cells[1]:
            bg_gen = cells[1].get('effectiveFormat', {}).get('backgroundColor', {})
            r_val = bg_gen.get('red', 0.0)
            if r_val > 0.9: p_realizar += 1
            elif abs(r_val-0.851) < 0.05: p_adecuacion += 1

    # Procesar Base de Datos
    df = df_raw.dropna(subset=["Marca temporal"], how='all').copy()
    df['Fecha_Limpia'] = df["Marca temporal"].apply(parse_individual_date)
    df['Contrato_Str'] = df['Contrato'].astype(str).str.replace('.0', '', regex=False).str.strip()
    df['Fecha_Asignacion'] = df['Contrato_Str'].map(asig_map)
    df['Dias_Realizacion'] = (pd.to_datetime(df['Fecha_Limpia']) - pd.to_datetime(df['Fecha_Asignacion'])).dt.days
    df.loc[df['Dias_Realizacion'] < 0, 'Dias_Realizacion'] = 0
    df['Metraje'] = pd.to_numeric(df['Metros '], errors='coerce').fillna(0)
    df['Tensores'] = pd.to_numeric(df['Tensores'], errors='coerce').fillna(0)
    df['ONU_Final'] = df['Serial ONU'].astype(str) if 'Serial ONU' in df.columns else "N/A"

    with st.sidebar:
        st.markdown("### 🔍 Buscador Maestro")
        sq = st.text_input("Número de contrato:")
        if sq:
            res = hybrid_search(sq, df, asig_map, r_ruta, r_adecu)
            if res:
                adecu_html = f"<p style='color:#ff9900; font-size:11px; font-weight:bold; margin-top:5px;'>{res['adecu_extra']}</p>" if res.get('adecu_extra') else ""
                info = f"<p style='font-size:12px; margin:0;'><b>FECHA ASIG:</b> {res['fecha_asig']}</p>"
                if "INSTALADO" in res['status']:
                    info += f"<p style='font-size:12px; margin:0;'><b>FECHA INST:</b> {res['fecha_inst']}</p><p style='color:#00ff00; font-size:11px; margin-top:5px;'><b>TARDÓ {res['tardo']} DÍAS</b></p>"
                st.markdown(f"<div class='search-result-card'><p style='color:#00d4ff; font-weight:600; margin-bottom:5px;'>{res['status']}</p>{adecu_html}<p style='font-size:12px; margin:0;'><b>CLIENTE:</b> {res['cliente']}</p>{info}</div>", unsafe_allow_html=True)
            else: st.warning("No encontrado.")

    # HEADER CON LOGOS
    ce, cl, ct, cr = st.columns([0.6, 1, 3.5, 1.5])
    with cl: st.image("logo_izq.png", width=150)
    with ct:
        st.markdown("<h1 style='text-align: center; color: white; margin:0;'>💎 FIBRA RAQ INTELLIGENCE</h1>", unsafe_allow_html=True)
        st.markdown(f"<p style='text-align: center; color: #00d4ff;'>{ahora_vzla.strftime('%d/%m/%Y %I:%M %p')}</p>", unsafe_allow_html=True)
    with cr: st.image("logo_der.png", width=150)
    
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
    with k5: st.markdown(f"<div class='metric-container'><div class='m-label'>Asig. Hoy</div><div class='m-value'>{asig_hoy}</div></div>", unsafe_allow_html=True)
    with k6: st.markdown(f"<div class='metric-container'><div class='m-label'>Asig. Ayer Lab.</div><div class='m-value'>{asig_ayer}</div></div>", unsafe_allow_html=True)
    
    # CORRECCIÓN DE ERROR DE FORMATO
    with k7:
        avg_s = df[(df['Fecha_Limpia'] >= i_s) & (df['Fecha_Limpia'] <= f_s)]['Dias_Realizacion'].mean()
        avg_s_txt = f"{avg_s:.1f}" if pd.notnull(avg_s) else "0"
        st.markdown(f"<div class='metric-container'><div class='m-label'>Media Sem. Actual</div><div class='m-value'>{avg_s_txt}</div></div>", unsafe_allow_html=True)
    with k8:
        avg_p = df[(df['Fecha_Limpia'] >= i_p) & (df['Fecha_Limpia'] <= f_p)]['Dias_Realizacion'].mean()
        avg_p_txt = f"{avg_p:.1f}" if pd.notnull(avg_p) else "0"
        st.markdown(f"<div class='metric-container'><div class='m-label'>Media Sem. Pasada</div><div class='m-value'>{avg_p_txt}</div></div>", unsafe_allow_html=True)

    # Procesar Rutas para visualización
    def get_ruta(fecha_dt):
        vars = get_fecha_variantes(fecha_dt)
        f, cls = False, []
        for row in r_ruta:
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

    ruta_h, ruta_a = get_ruta(ahora_vzla), get_ruta(ayer_laboral_dt)
    st.markdown("<div class='section-title'>Control de Ruta y Materiales</div>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns([1, 1, 1, 0.6])
    def rend_c(c): return f"<div class='cliente-item bg-{c['color']}'>{str(int(float(c['contrato'])))} | {c['nombre']} | {c['zona']}</div>"
    with c1: st.markdown(f"<div class='ruta-box'><div class='ruta-header'>RUTA HOY ({len(ruta_h)})</div>{''.join([rend_c(c) for c in ruta_h])}</div>", unsafe_allow_html=True)
    with c2: st.markdown(f"<div class='ruta-box'><div class='ruta-header'>RUTA AYER ({len(ruta_a)})</div>{''.join([rend_c(c) for c in ruta_a])}</div>", unsafe_allow_html=True)
    with c3:
        df_a_m = df[df['Fecha_Limpia'] == ayer_laboral_vzla]
        itms = "".join([f"<div class='cliente-item bg-green'>{r['Contrato_Str']} | {r['Nombre del cliente']} | 📏{int(r['Metraje'])}m</div>" for _, r in df_a_m.iterrows()])
        st.markdown(f"<div class='ruta-box'><div class='ruta-header'>MATERIALES AYER ({len(df_a_m)})</div>{itms}</div>", unsafe_allow_html=True)
    with c4: st.markdown("<div class='ruta-box'><div class='ruta-header'>ADECUACIONES</div><div class='m-value' style='color:#ff9900; text-align:center; font-size:30px;'>"+str(p_adecuacion)+"</div><div class='ruta-header' style='margin-top:20px;'>PENDIENTES RUTA</div><div class='m-value' style='color:#ff4b4b; text-align:center; font-size:30px;'>"+str(p_realizar)+"</div></div>", unsafe_allow_html=True)

    # Histórico
    st.markdown("<div class='section-title'>Análisis Histórico</div>", unsafe_allow_html=True)
    df_hist = df.dropna(subset=['Fecha_Limpia']).copy()
    df_hist['Mes_N'] = pd.to_datetime(df_hist['Fecha_Limpia']).dt.month.map({1:'Enero', 2:'Febrero', 3:'Marzo', 4:'Abril', 5:'Mayo', 6:'Junio', 7:'Julio', 8:'Agosto', 9:'Septiembre', 10:'Octubre', 11:'Noviembre', 12:'Diciembre'})
    df_hist['Año'] = pd.to_datetime(df_hist['Fecha_Limpia']).dt.year
    hist = df_hist.groupby(['Año', df_hist['Fecha_DT'].dt.month, 'Mes_N']).agg(T=('Contrato', 'size'), M=('Dias_Realizacion', 'mean')).reset_index().sort_values(['Año', 'Fecha_DT'], ascending=False)
    for _, row in hist.iterrows():
        st.markdown(f"<div class='month-row'><span>{row['Mes_N']} {int(row['Año'])}</span><span><span style='color:#00d4ff; font-weight:bold;'>{row['T']}</span><span style='color:#8899a6; font-size:10px; margin-left:10px;'>Media: {row['M']:.1f} días</span></span></div>", unsafe_allow_html=True)

except Exception as e:
    st.error(f"Error detectado: {e}")
