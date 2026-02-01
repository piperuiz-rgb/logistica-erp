import streamlit as st
import pandas as pd
import os
import io
from datetime import datetime
from openpyxl import load_workbook

st.set_page_config(page_title="Peticiones", layout="wide")

# --- CSS DEFINITIVO ---
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
    }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data
def get_catalogue():
    if not os.path.exists('catalogue.xlsx'): return None
    df = pd.read_excel('catalogue.xlsx', engine='openpyxl')
    df['EAN'] = df['EAN'].astype(str).str.replace('.0', '', regex=False).str.strip()
    return df

# --- ESTADO DE LA SESIÓN ---
if 'carrito' not in st.session_state: st.session_state.carrito = {}
if 'search_key' not in st.session_state: st.session_state.search_key = 0

df_cat = get_catalogue()
st.markdown('<div class="peticiones-title">Peticiones</div>', unsafe_allow_html=True)

if df_cat is not None:
    # 1. CONFIGURACIÓN GENERAL
    c1, c2, c3 = st.columns(3)
    fecha_str = c1.date_input("FECHA", datetime.now()).strftime('%Y-%m-%d')
    origen = c2.selectbox("ORIGEN", ["PET Almacén Badalona", "ALM-CENTRAL"])
    destino = c3.selectbox("DESTINO", ["PET T002 Marbella", "ALM-TIENDA"])
    ref_peticion = st.text_input("REFERENCIA PETICIÓN")

    st.write("---")

    # 2. CARGA DE EXCEL (SIEMPRE VISIBLE)
    st.markdown('<div class="section-header">📂 CARGAR REPOSICIÓN POR EXCEL</div>', unsafe_allow_html=True)
    archivo_v = st.file_uploader("Subir Excel con columnas EAN y Cantidad", type=['xlsx'], label_visibility="collapsed")
    if archivo_v and st.button("IMPORTAR DATOS", type="primary"):
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

    # 3. BUSCADOR MANUAL
    st.markdown('<div class="section-header">🔍 BUSCADOR MANUAL DE CATÁLOGO</div>', unsafe_allow_html=True)
    f1, f2 = st.columns([2, 1])
    # Usamos la key dinámica para limpiar el input
    busq_txt = f1.text_input("Escribe Referencia, Nombre o EAN...", key=f"busq_{st.session_state.search_key}")
    limite = f2.selectbox("Resultados visibles:", [10, 25, 50, 100, 500], index=1, key=f"lim_{st.session_state.search_key}")

    filtros_activos = {}
    cols_opcionales = ["Colección", "Categoría", "Familia"]
    columnas_reales = [c for c in cols_opcionales if c in df_cat.columns]
    
    if columnas_reales:
        cols_f = st.columns(len(columnas_reales))
        for i, col in enumerate(columnas_reales):
            opciones = ["TODOS"] + sorted(df_cat[col].dropna().unique().tolist())
            filtros_activos[col] = cols_f[i].selectbox(f"Filtrar {col}", opciones, key=f"f_{col}_{st.session_state.search_key}")

    # Lógica de Filtrado
    df_res = df_cat.copy()
    if busq_txt:
        df_res = df_res[df_res.apply(lambda row: busq_txt.lower() in str(row.values).lower(), axis=1)]
    for col, val in filtros_activos.items():
        if val != "TODOS":
            df_res = df_res[df_res[col] == val]

    # TABLA DE RESULTADOS (Solo si hay búsqueda activa)
    if busq_txt or any(v != "TODOS" for v in filtros_activos.values()):
        st.markdown(f"<div style='background: #000; color: #fff; padding: 5px; font-size: 0.75rem; text-align: center; margin-top: 10px;'>{len(df_res)} ENCONTRADOS (MOSTRANDO {min(len(df_res), limite)})</div>", unsafe_allow_html=True)
        
        for _, f in df_res.head(limite).iterrows():
            ean = f['EAN']
            en_car = ean in st.session_state.carrito
            st.markdown('<div class="table-row">', unsafe_allow_html=True)
            c1, c2 = st.columns([3, 1.5]) 
            with c1:
                st.markdown(f"""<div class='cell-content'>
                    <span style='font-weight: 800;'>{f['Referencia']}</span>
                    <span style='font-size: 0.8rem;'>{f.get('Nombre','')} / {f.get('Color','-')} / {f.get('Talla','-')}</span>
                </div>""", unsafe_allow_html=True)
            with c2:
                label = f"OK ({st.session_state.carrito[ean]['Cantidad']})" if en_car else "AÑADIR"
                if st.button(label, key=f"b_{ean}", type="primary" if en_car else "secondary"):
                    if en_car: st.session_state.carrito[ean]['Cantidad'] += 1
                    else: st.session_state.carrito[ean] = {'Ref': f['Referencia'], 'Nom': f.get('Nombre',''), 'Col': f.get('Color','-'), 'Tal': f.get('Talla','-'), 'Cantidad': 1}
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    # 4. LISTA DE REPOSICIÓN FINAL
    if st.session_state.carrito:
        st.write("---")
        st.markdown('<div class="section-header">📋 LISTA DE REPOSICIÓN ACTUAL</div>', unsafe_allow_html=True)
        for ean, item in list(st.session_state.carrito.items()):
            st.markdown('<div class="table-row">', unsafe_allow_html=True)
            ca, cb, cc = st.columns([2.5, 1.2, 0.8])
            with ca: st.markdown(f"<div class='cell-content'><strong>{item['Ref']}</strong><br><small>{item['Nom']} ({item['Col']}/{item['Tal']})</small></div>", unsafe_allow_html=True)
            with cb: item['Cantidad'] = st.number_input("C", 1, 9999, item['Cantidad'], key=f"q_{ean}", label_visibility="collapsed")
            with cc:
                if st.button("✕", key=f"d_{ean}"): del st.session_state.carrito[ean]; st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        # RESUMEN DE UNIDADES AL FINAL
        uds = sum(it['Cantidad'] for it in st.session_state.carrito.values())
        refs = len(st.session_state.carrito)
        st.markdown(f"""<div class="summary-box">
            <div>PIEZAS: {uds}</div><div>MODELOS: {refs}</div><div>DESTINO: {destino}</div>
        </div>""", unsafe_allow_html=True)

        cv, cg = st.columns([1, 2])
        if cv.button("LIMPIAR TODO"):
            st.session_state.carrito = {}
            st.session_state.search_key += 1 # Esto resetea los inputs de búsqueda
            st.rerun()
            
        if os.path.exists('peticion.xlsx') and cg.button("GENERAR Y DESCARGAR", type="primary"):
            wb = load_workbook('peticion.xlsx')
            ws = wb.active
            for ean, it in st.session_state.carrito.items():
                ws.append([fecha_str, origen, destino, ref_peticion, ean, it['Cantidad']])
            out = io.BytesIO(); wb.save(out)
            st.download_button("📥 DESCARGAR EXCEL FINAL", out.getvalue(), f"REPO_{destino}.xlsx", use_container_width=True)
else:
    st.error("No se encontró 'catalogue.xlsx'.")
    
