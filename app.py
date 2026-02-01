import streamlit as st
import pandas as pd
import os
import io
import re
from datetime import datetime
from openpyxl import load_workbook

# --- CONFIGURACIÓN Y ESTILOS ---
st.set_page_config(page_title="Peticiones RGB", layout="wide")

st.markdown("""
    <style>
    html, body, .stApp, .main, .block-container, 
    div[data-testid="stExpander"], div[data-testid="stTab"], 
    div[data-testid="stHeader"], .stTabs, [data-testid="stVerticalBlock"] {
        background-color: #ffffff !important;
        color: #000000 !important;
    }
    .peticiones-title {
        font-size: 2.5rem; font-weight: 800; color: #000000;
        margin-top: 40px; margin-bottom: 20px;
        padding-bottom: 10px; border-bottom: 2px solid #000000; width: 100%;
    }
    .section-header {
        background: #000; color: #fff; padding: 8px; 
        font-weight: bold; margin-top: 20px; margin-bottom: 10px;
    }
    .table-row {
        border: 1px solid #000000; margin-top: -1px;
        background-color: #ffffff !important; display: flex; align-items: center; width: 100%;
    }
    .cell-content { padding: 8px 12px; display: flex; flex-direction: column; justify-content: center; }
    .stButton>button {
        width: 100% !important; border-radius: 0px !important; font-weight: 700 !important;
        height: 40px; text-transform: uppercase; border: 1px solid #000000 !important; font-size: 0.7rem !important;
    }
    .stButton>button[kind="secondary"] { background-color: #ffffff !important; color: #000000 !important; }
    .stButton>button[kind="primary"] { background-color: #0052FF !important; color: #ffffff !important; border: none !important; }
    .summary-box {
        border: 2px solid #000000; padding: 15px; margin-top: 20px;
        background-color: #ffffff !important; font-weight: bold;
        display: flex; justify-content: space-between; color: #000000 !important;
    }
    @media (max-width: 600px) {
        .peticiones-title { font-size: 1.8rem; margin-top: 20px; }
        .summary-box { flex-direction: column; gap: 5px; }
        .stButton>button { font-size: 0.75rem !important; height: 48px; }
    }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data
def get_catalogue():
    if not os.path.exists('catalogue.xlsx'): return None
    try:
        df = pd.read_excel('catalogue.xlsx', engine='openpyxl')
        df.columns = [str(c).strip() for c in df.columns]
        df['EAN'] = df['EAN'].astype(str).str.replace('.0', '', regex=False).str.strip()
        # Generar KEY maestra para cruce: REF_COLOR_TALLA
        df['KEY_MASTER'] = (df['Referencia'].astype(str).str.strip().str.upper() + "_" + 
                            df['Color'].astype(str).str.strip().str.upper() + "_" + 
                            df['Talla'].astype(str).str.strip().str.upper())
        return df[['KEY_MASTER', 'EAN']] 
    except: return None

# --- ESTADO DE SESIÓN ---
if 'carrito' not in st.session_state: st.session_state.carrito = {}
if 'search_key' not in st.session_state: st.session_state.search_key = 0

df_cat = get_catalogue()

tab1, tab2 = st.tabs(["🛒 GESTIÓN DE PETICIONES", "🔄 CONVERSOR GEXTIA"])

# ==========================================
# PESTAÑA 1: PETICIONES (Sin cambios, usa EAN limpio)
# ==========================================
with tab1:
    st.markdown('<div class="peticiones-title">Peticiones</div>', unsafe_allow_html=True)
    df_full = pd.read_excel('catalogue.xlsx', engine='openpyxl') if os.path.exists('catalogue.xlsx') else None
    
    if df_full is not None:
        df_full.columns = [str(c).strip() for c in df_full.columns]
        df_full['EAN'] = df_full['EAN'].astype(str).str.replace('.0', '', regex=False).str.strip()
        
        c1, c2, c3 = st.columns(3)
        fecha_str = c1.date_input("FECHA", datetime.now()).strftime('%Y-%m-%d')
        origen = c2.selectbox("ORIGEN", ["PET Almacén Badalona", "ALM-CENTRAL"])
        destino = c3.selectbox("DESTINO", ["PET T002 Marbella", "ALM-TIENDA"])
        ref_peticion = st.text_input("REFERENCIA PETICIÓN")

        st.markdown('<div class="section-header">📂 IMPORTACIÓN DE EXCEL LIMPIO (EAN)</div>', unsafe_allow_html=True)
        archivo_v = st.file_uploader("Sube el archivo 'ean_limpios.xlsx'", type=['xlsx'], key="u_peticiones")
        if archivo_v and st.button("CARGAR EN CARRITO", type="primary"):
            df_v = pd.read_excel(archivo_v)
            # Buscamos columnas EAN y Cantidad (o las dos primeras)
            c_ean = "EAN" if "EAN" in df_v.columns else df_v.columns[0]
            c_qty = "Cantidad" if "Cantidad" in df_v.columns else df_v.columns[1]
            
            for _, f_v in df_v.iterrows():
                ean_v = str(f_v[c_ean]).replace('.0', '').strip()
                cant_v = int(f_v[c_qty])
                match = df_full[df_full['EAN'] == ean_v]
                if not match.empty:
                    prod = match.iloc[0]
                    if ean_v in st.session_state.carrito: st.session_state.carrito[ean_v]['Cantidad'] += cant_v
                    else: st.session_state.carrito[ean_v] = {
                        'Ref': prod['Referencia'], 'Nom': prod.get('Nombre',''), 
                        'Col': prod.get('Color','-'), 'Tal': prod.get('Talla','-'), 'Cantidad': cant_v
                    }
            st.rerun()

        # ... (Resto de la lógica del buscador manual se mantiene igual)

# ==========================================
# PESTAÑA 2: CONVERSOR (Optimizado para "Variante")
# ==========================================
with tab2:
    st.markdown('<div class="peticiones-title">Conversor Gextia</div>', unsafe_allow_html=True)
    st.info("Sube el Excel con columnas 'Variante' (texto largo) y 'Cantidad'.")
    
    archivo_conv = st.file_uploader("Sube el Excel sucio", type=['xlsx'], key="u_conversor")
    
    if archivo_conv and df_cat is not None:
        df_sucio = pd.read_excel(archivo_conv)
        
        if st.button("LIMPIAR Y CONVERTIR A EAN", type="primary"):
            # Detectar columnas: busca "Variante" o usa la primera columna
            col_var = "Variante" if "Variante" in df_sucio.columns else df_sucio.columns[0]
            col_can = "Cantidad" if "Cantidad" in df_sucio.columns else df_sucio.columns[1]

            def extraer_llave(t):
                t = str(t)
                ref = re.search(r'\[(.*?)\]', t)
                specs = re.findall(r'\((.*?)\)', t)
                if ref and specs:
                    r = ref.group(1).strip().upper()
                    p = specs[-1].split(',')
                    if len(p) >= 2:
                        return f"{r}_{p[0].strip().upper()}_{p[1].strip().upper()}"
                return None

            df_sucio['JOIN_KEY'] = df_sucio[col_var].apply(extraer_llave)
            
            # Cruce limpio: Al llamarse 'Variante' y no 'EAN', el merge no choca
            res = pd.merge(df_sucio, df_cat, left_on='JOIN_KEY', right_on='KEY_MASTER', how='inner')

            if not res.empty:
                # El EAN real viene directamente del catálogo sin sufijos (_x, _y)
                df_final = res[['EAN', col_can]].rename(columns={col_can: 'Cantidad'})
                
                st.success(f"✅ ¡Éxito! {len(df_final)} líneas listas.")
                
                out_c = io.BytesIO()
                with pd.ExcelWriter(out_c, engine='openpyxl') as writer:
                    df_final.to_excel(writer, index=False)
                
                st.download_button("📥 DESCARGAR EXCEL LIMPIO", out_c.getvalue(), "ean_limpios.xlsx", use_container_width=True)
            else:
                st.error("No hay coincidencias. Revisa que el catálogo tenga las mismas Referencias, Colores y Tallas.")
                
