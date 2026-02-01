import streamlit as st
import pandas as pd
import os
import io
import re
from datetime import datetime
from openpyxl import load_workbook

# --- CONFIGURACIÓN Y ESTILOS (Originales) ---
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
    .stButton>button[kind="primary"] { background-color: #0052FF !important; color: #ffffff !important; border: none !important; }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data
def get_catalogue():
    if not os.path.exists('catalogue.xlsx'): return None
    try:
        df = pd.read_excel('catalogue.xlsx', engine='openpyxl')
        df.columns = [str(c).strip() for c in df.columns]
        df['EAN'] = df['EAN'].astype(str).str.replace('.0', '', regex=False).str.strip()
        # Claves normalizadas para cruce ultra-rápido
        df['KEY'] = (df['Referencia'].astype(str).str.strip().str.upper() + "_" + 
                     df['Color'].astype(str).str.strip().str.upper() + "_" + 
                     df['Talla'].astype(str).str.strip().str.upper())
        return df
    except: return None

if 'carrito' not in st.session_state: st.session_state.carrito = {}
df_cat = get_catalogue()

tab1, tab2 = st.tabs(["🛒 GESTIÓN DE PETICIONES", "🔄 CONVERSOR GEXTIA"])

# --- PESTAÑA 1: GESTIÓN (IDÉNTICA A TU LÓGICA) ---
with tab1:
    st.markdown('<div class="peticiones-title">Peticiones</div>', unsafe_allow_html=True)
    if df_cat is not None:
        c1, c2, c3 = st.columns(3)
        fecha_str = c1.date_input("FECHA", datetime.now()).strftime('%Y-%m-%d')
        destino = c3.selectbox("DESTINO", ["PET T002 Marbella", "ALM-TIENDA"])
        
        st.markdown('<div class="section-header">📂 IMPORTACIÓN DIRECTA (EAN)</div>', unsafe_allow_html=True)
        archivo_v = st.file_uploader("Sube Excel con EAN y Cantidad", type=['xlsx'], key="u_repo")
        if archivo_v and st.button("CARGAR DATOS", type="primary", key="btn_repo"):
            df_v = pd.read_excel(archivo_v)
            df_v.columns = [str(c).strip() for c in df_v.columns]
            # Procesamiento optimizado
            for _, f_v in df_v.iterrows():
                ean_v = str(f_v['EAN']).replace('.0', '').strip()
                cant_v = int(f_v.get('Cantidad', 1))
                match = df_cat[df_cat['EAN'] == ean_v]
                if not match.empty:
                    p = match.iloc[0]
                    if ean_v in st.session_state.carrito: st.session_state.carrito[ean_v]['Cantidad'] += cant_v
                    else: st.session_state.carrito[ean_v] = {'Ref': p['Referencia'], 'Nom': p.get('Nombre',''), 'Col': p.get('Color','-'), 'Tal': p.get('Talla','-'), 'Cantidad': cant_v}
            st.rerun()
            
        # [Aquí va el resto de tu código de buscador manual]
    else:
        st.error("Falta catalogue.xlsx")

# --- PESTAÑA 2: CONVERSOR (ULTRA RÁPIDO PARA EVITAR AXIOS ERROR) ---
with tab2:
    st.markdown('<div class="peticiones-title">Conversor Gextia</div>', unsafe_allow_html=True)
    archivo_g = st.file_uploader("Sube informe sucio", type=['xlsx'], key="u_conv")
    
    if archivo_g and df_cat is not None:
        df_g = pd.read_excel(archivo_g)
        col_txt = st.selectbox("Columna Descripción", df_g.columns)
        col_can = st.selectbox("Columna Cantidad", df_g.columns)
        
        if st.button("PROCESAR CONVERSIÓN RÁPIDA", type="primary"):
            # 1. Función rápida para extraer datos del texto
            def extraer_datos(texto):
                texto = str(texto)
                m_ref = re.search(r'\[(.*?)\]', texto)
                m_specs = re.findall(r'\((.*?)\)', texto)
                if m_ref and m_specs:
                    ref = m_ref.group(1).strip().upper()
                    partes = m_specs[-1].split(',')
                    if len(partes) >= 2:
                        return f"{ref}_{partes[0].strip().upper()}_{partes[1].strip().upper()}"
                return None

            # 2. Aplicamos la extracción a toda la columna de golpe (Vectorizado)
            df_g['JOIN_KEY'] = df_g[col_txt].apply(extraer_datos)
            
            # 3. Cruzamos (Merge) el excel subido con el catálogo usando la KEY
            df_final = pd.merge(df_g, df_cat[['KEY', 'EAN']], left_on='JOIN_KEY', right_on='KEY', how='inner')
            
            if not df_final.empty:
                df_res = df_final[['EAN', col_can]].rename(columns={col_can: 'Cantidad'})
                st.success(f"✅ ¡Éxito! {len(df_res)} productos encontrados.")
                st.dataframe(df_res.head(10), hide_index=True)
                
                out_c = io.BytesIO()
                with pd.ExcelWriter(out_c, engine='openpyxl') as w:
                    df_res.to_excel(w, index=False)
                st.download_button("📥 DESCARGAR RESULTADO", out_c.getvalue(), "ean_limpios.xlsx", use_container_width=True)
            else:
                st.error("No se encontró ningún producto. Revisa los nombres de las columnas.")
                
