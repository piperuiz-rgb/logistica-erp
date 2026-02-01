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

# --- CARGA DE DATOS ---
@st.cache_data
def get_catalogue():
    if not os.path.exists('catalogue.xlsx'): return None
    try:
        df = pd.read_excel('catalogue.xlsx', engine='openpyxl')
        df.columns = [str(c).strip() for c in df.columns]
        df['EAN'] = df['EAN'].astype(str).str.replace('.0', '', regex=False).str.strip()
        # Key Maestra para el conversor
        df['KEY_MASTER'] = (df['Referencia'].astype(str).str.strip().str.upper() + "_" + 
                            df['Color'].astype(str).str.strip().str.upper() + "_" + 
                            df['Talla'].astype(str).str.strip().str.upper())
        return df
    except: return None

# --- ESTADO DE SESIÓN ---
if 'carrito' not in st.session_state: st.session_state.carrito = {}
if 'search_key' not in st.session_state: st.session_state.search_key = 0

df_cat = get_catalogue()

# --- PESTAÑAS ---
tab1, tab2 = st.tabs(["🛒 GESTIÓN DE PETICIONES", "🔄 CONVERSOR GEXTIA"])

# ==========================================
# PESTAÑA 1: TU CÓDIGO ORIGINAL
# ==========================================
with tab1:
    st.markdown('<div class="peticiones-title">Peticiones</div>', unsafe_allow_html=True)

    if df_cat is not None:
        # 1. CABECERA LOGÍSTICA
        c1, c2, c3 = st.columns(3)
        fecha_str = c1.date_input("FECHA", datetime.now()).strftime('%Y-%m-%d')
        origen = c2.selectbox("ORIGEN", ["PET Almacén Badalona", "ALM-CENTRAL"])
        destino = c3.selectbox("DESTINO", ["PET T002 Marbella", "ALM-TIENDA"])
        ref_peticion = st.text_input("REFERENCIA PETICIÓN")

        st.write("---")

        # 2. IMPORTADOR MASIVO
        st.markdown('<div class="section-header">📂 IMPORTACIÓN DE VENTAS / REPOSICIÓN</div>', unsafe_allow_html=True)
        archivo_v = st.file_uploader("Sube el Excel con columnas EAN y Cantidad", type=['xlsx'], label_visibility="collapsed", key="u1")
        if archivo_v and st.button("CARGAR DATOS DEL EXCEL", type="primary", key="b1"):
            df_v = pd.read_excel(archivo_v)
            for _, f_v in df_v.iterrows():
                ean_v = str(f_v['EAN']).replace('.0', '').strip()
                cant_v = int(f_v.get('Cantidad', 1))
                match = df_cat[df_cat['EAN'] == ean_v]
                if not match.empty:
                    prod = match.iloc[0]
                    if ean_v in st.session_state.carrito: st.session_state.carrito[ean_v]['Cantidad'] += cant_v
                    else: st.session_state.carrito[ean_v] = {
                        'Ref': prod['Referencia'], 'Nom': prod.get('Nombre',''), 
                        'Col': prod.get('Color','-'), 'Tal': prod.get('Talla','-'), 'Cantidad': cant_v
                    }
            st.rerun()

        # 3. BUSCADOR Y FILTROS
        st.markdown('<div class="section-header">🔍 BUSCADOR MANUAL</div>', unsafe_allow_html=True)
        f1, f2 = st.columns([2, 1])
        busq_txt = f1.text_input("Buscar referencia, nombre o EAN...", key=f"busq_{st.session_state.search_key}")
        limite = f2.selectbox("Ver resultados:", [10, 25, 50, 100, 500], index=1, key=f"lim_{st.session_state.search_key}")

        filtros_activos = {}
        columnas_posibles = ["Colección", "Categoría", "Familia"]
        columnas_reales = [c for c in columnas_posibles if c in df_cat.columns]
        
        if columnas_reales:
            cols_f = st.columns(len(columnas_reales))
            for i, col in enumerate(columnas_reales):
                opciones = ["TODOS"] + sorted(df_cat[col].dropna().unique().tolist())
                filtros_activos[col] = cols_f[i].selectbox(f"{col}", opciones, key=f"f_{col}_{st.session_state.search_key}")

        df_res = df_cat.copy()
        if busq_txt:
            df_res = df_res[df_res.apply(lambda row: busq_txt.lower() in str(row.values).lower(), axis=1)]
        for col, val in filtros_activos.items():
            if val != "TODOS":
                df_res = df_res[df_res[col] == val]

        if busq_txt or any(v != "TODOS" for v in filtros_activos.values()):
            st.markdown(f"<div style='background: #000; color: #fff; padding: 4px; font-size: 0.7rem; text-align: center;'>{len(df_res)} COINCIDENCIAS</div>", unsafe_allow_html=True)
            for _, f in df_res.head(limite).iterrows():
                ean = f['EAN']
                en_car = ean in st.session_state.carrito
                st.markdown('<div class="table-row">', unsafe_allow_html=True)
                c1_res, c2_res = st.columns([3, 1.5]) 
                with c1_res:
                    st.markdown(f"<div class='cell-content'><strong>{f['Referencia']}</strong><br><small>{f.get('Nombre','')} ({f.get('Color','-')} / {f.get('Talla','-')})</small></div>", unsafe_allow_html=True)
                with c2_res:
                    label = f"OK ({st.session_state.carrito[ean]['Cantidad']})" if en_car else "AÑADIR"
                    if st.button(label, key=f"b_{ean}", type="primary" if en_car else "secondary"):
                        if en_car: st.session_state.carrito[ean]['Cantidad'] += 1
                        else: st.session_state.carrito[ean] = {'Ref': f['Referencia'], 'Nom': f.get('Nombre',''), 'Col': f.get('Color','-'), 'Tal': f.get('Talla','-'), 'Cantidad': 1}
                        st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

        # 4. LISTA FINAL Y GENERACIÓN
        if st.session_state.carrito:
            st.write("---")
            st.markdown('<div class="section-header">📋 LISTA DE REPOSICIÓN</div>', unsafe_allow_html=True)
            for ean, item in list(st.session_state.carrito.items()):
                st.markdown('<div class="table-row">', unsafe_allow_html=True)
                ca, cb, cc = st.columns([2.5, 1.2, 0.8])
                with ca: st.markdown(f"<div class='cell-content'><strong>{item['Ref']}</strong><br><small>{item['Nom']}</small></div>", unsafe_allow_html=True)
                with cb: item['Cantidad'] = st.number_input("C", 1, 9999, item['Cantidad'], key=f"q_{ean}", label_visibility="collapsed")
                with cc:
                    if st.button("✕", key=f"d_{ean}"): del st.session_state.carrito[ean]; st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

            uds = sum(it['Cantidad'] for it in st.session_state.carrito.values())
            st.markdown(f'<div class="summary-box"><div>PIEZAS: {uds}</div><div>MODELOS: {len(st.session_state.carrito)}</div><div>DESTINO: {destino}</div></div>', unsafe_allow_html=True)

            cv, cg = st.columns([1, 2])
            if cv.button("LIMPIAR TODO", key="clear_all"):
                st.session_state.carrito = {}
                st.session_state.search_key += 1
                st.rerun()
                
            if os.path.exists('peticion.xlsx') and cg.button("GENERAR Y DESCARGAR EXCEL", type="primary", key="gen_btn"):
                wb = load_workbook('peticion.xlsx')
                ws = wb.active
                for ean, it in st.session_state.carrito.items():
                    ws.append([fecha_str, origen, destino, ref_peticion, ean, it['Cantidad']])
                out = io.BytesIO(); wb.save(out)
                st.download_button("📥 GUARDAR ARCHIVO REPO", out.getvalue(), f"REPO_{destino}.xlsx", use_container_width=True)
    else:
        st.error("Error: Asegúrate de tener el archivo 'catalogue.xlsx' en la carpeta.")

# ==========================================
# PESTAÑA 2: CONVERSOR GEXTIA (Variante -> EAN)
# ==========================================
with tab2:
    st.markdown('<div class="peticiones-title">Conversor Gextia</div>', unsafe_allow_html=True)
    st.info("Sube el Excel con la columna 'Variante' para convertirla a EAN limpio.")
    
    archivo_conv = st.file_uploader("Sube el Excel sucio", type=['xlsx'], key="u2")
    
    if archivo_conv and df_cat is not None:
        df_sucio = pd.read_excel(archivo_conv)
        
        if st.button("LIMPIAR Y CONVERTIR A EAN", type="primary", key="b2"):
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
            
            # Cruce con el catálogo
            res = pd.merge(df_sucio, df_cat[['KEY_MASTER', 'EAN']], left_on='JOIN_KEY', right_on='KEY_MASTER', how='inner')

            if not res.empty:
                df_final = res[['EAN', col_can]].rename(columns={col_can: 'Cantidad'})
                
                st.success(f"✅ Conversión realizada: {len(df_final)} líneas.")
                
                out_c = io.BytesIO()
                with pd.ExcelWriter(out_c, engine='openpyxl') as writer:
                    df_final.to_excel(writer, index=False)
                
                st.download_button("📥 DESCARGAR EAN LIMPIOS", out_c.getvalue(), "ean_limpios.xlsx", use_container_width=True)
            else:
                st.error("No se encontraron coincidencias en el catálogo.")
                
