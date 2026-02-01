import streamlit as st
import pandas as pd
import os
import io
from datetime import datetime
from openpyxl import load_workbook

st.set_page_config(page_title="Peticiones", layout="wide")

# --- CSS TÉCNICO DEFINITIVO ---
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

if 'carrito' not in st.session_state: st.session_state.carrito = {}

df_cat = get_catalogue()
st.markdown('<div class="peticiones-title">Peticiones</div>', unsafe_allow_html=True)

if df_cat is not None:
    # 1. CONFIGURACIÓN INICIAL
    c1, c2, c3 = st.columns(3)
    fecha_str = c1.date_input("FECHA", datetime.now()).strftime('%Y-%m-%d')
    origen = c2.selectbox("ORIGEN", ["PET Almacén Badalona", "ALM-CENTRAL"])
    destino = c3.selectbox("DESTINO", ["PET T002 Marbella", "ALM-TIENDA"])
    ref_peticion = st.text_input("REFERENCIA PETICIÓN")

    st.write("---")

    # 2. SISTEMA DE FILTROS AVANZADOS
    with st.expander("🔍 FILTROS DE BÚSQUEDA", expanded=True):
        f1, f2, f3 = st.columns([2, 1, 1])
        busq_txt = f1.text_input("Buscar Referencia/Nombre/EAN", placeholder="Ej: Angélica...")
        
        # Filtros dinámicos basados en columnas extra si existen
        cols_interes = ["Colección", "Categoría", "Familia"]
        filtros_activos = {}
        
        col_selectores = st.columns(len([c for c in cols_interes if c in df_cat.columns]))
        idx = 0
        for col in cols_interes:
            if col in df_cat.columns:
                opciones = ["TODOS"] + sorted(df_cat[col].dropna().unique().tolist())
                filtros_activos[col] = col_selectores[idx].selectbox(f"Filtrar por {col}", opciones)
                idx += 1
        
        limite = st.select_slider("Número de resultados visibles", options=[10, 25, 50, 100, 500], value=25)

    # Aplicar Lógica de Filtros
    df_res = df_cat.copy()
    if busq_txt:
        df_res = df_res[df_res.apply(lambda row: busq_txt.lower() in str(row.values).lower(), axis=1)]
    for col, val in filtros_activos.items():
        if val != "TODOS":
            df_res = df_res[df_res[col] == val]

    # 3. OPERATIVA (TABS)
    t1, t2 = st.tabs(["📂 CARGA EXCEL", "🔍 RESULTADOS CATÁLOGO"])

    with t1:
        archivo_v = st.file_uploader("Subir ventas", type=['xlsx'])
        if archivo_v and st.button("IMPORTAR DATOS", type="secondary"):
            df_v = pd.read_excel(archivo_v)
            for _, f_v in df_v.iterrows():
                ean = str(f_v['EAN']).replace('.0', '').strip()
                if ean in df_cat['EAN'].values:
                    prod = df_cat[df_cat['EAN'] == ean].iloc[0]
                    cant = int(f_v.get('Cantidad', 1))
                    if ean in st.session_state.carrito: st.session_state.carrito[ean]['Cantidad'] += cant
                    else: st.session_state.carrito[ean] = {'Ref': prod['Referencia'], 'Nom': prod.get('Nombre',''), 'Col': prod.get('Color','-'), 'Tal': prod.get('Talla','-'), 'Cantidad': cant}
            st.rerun()

    with t2:
        st.markdown(f"<div style='border: 1px solid #000; background: #000; color: #fff; padding: 5px; font-size: 0.75rem; text-align: center;'>MOSTRANDO {min(len(df_res), limite)} DE {len(df_res)} PRODUCTOS</div>", unsafe_allow_html=True)
        
        for _, f in df_res.head(limite).iterrows():
            ean = f['EAN']
            en_car = ean in st.session_state.carrito
            st.markdown('<div class="table-row">', unsafe_allow_html=True)
            c1, c2 = st.columns([3, 1.5]) 
            with c1:
                st.markdown(f"""<div class='cell-content'>
                    <span style='font-weight: 800;'>{f['Referencia']}</span>
                    <span style='font-size: 0.8rem;'>{f.get('Nombre','')}</span>
                    <span style='font-size: 0.7rem;'>{f.get('Color','-')} / {f.get('Talla','-')}</span>
                </div>""", unsafe_allow_html=True)
            with c2:
                label = f"OK({st.session_state.carrito[ean]['Cantidad']})" if en_car else "AÑADIR"
                if st.button(label, key=f"b_{ean}", type="primary" if en_car else "secondary"):
                    if en_car: st.session_state.carrito[ean]['Cantidad'] += 1
                    else: st.session_state.carrito[ean] = {'Ref': f['Referencia'], 'Nom': f.get('Nombre',''), 'Col': f.get('Color','-'), 'Tal': f.get('Talla','-'), 'Cantidad': 1}
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    # 4. LISTA Y RESUMEN FINAL
    if st.session_state.carrito:
        st.write("###")
        st.markdown("<div style='background: #000; color: #fff; padding: 5px; font-weight: bold;'>LISTA DE REPOSICIÓN</div>", unsafe_allow_html=True)
        for ean, item in list(st.session_state.carrito.items()):
            st.markdown('<div class="table-row">', unsafe_allow_html=True)
            ca, cb, cc = st.columns([2.5, 1.2, 0.8])
            with ca: st.markdown(f"<div class='cell-content'><strong>{item['Ref']}</strong><br><small>{item['Nom']} ({item['Col']}/{item['Tal']})</small></div>", unsafe_allow_html=True)
            with cb: item['Cantidad'] = st.number_input("C", 1, 9999, item['Cantidad'], key=f"q_{ean}", label_visibility="collapsed")
            with cc:
                if st.button("✕", key=f"d_{ean}"): del st.session_state.carrito[ean]; st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        uds = sum(it['Cantidad'] for it in st.session_state.carrito.values())
        refs = len(st.session_state.carrito)
        st.markdown(f"""<div class="summary-box">
            <div>PIEZAS: {uds}</div><div>MODELOS: {refs}</div><div>DESTINO: {destino}</div>
        </div>""", unsafe_allow_html=True)

        cv, cg = st.columns([1, 2])
        if cv.button("LIMPIAR"):
            st.session_state.carrito = {}; st.rerun()
        if os.path.exists('peticion.xlsx') and cg.button("GENERAR Y DESCARGAR", type="primary"):
            wb = load_workbook('peticion.xlsx')
            ws = wb.active
            for ean, it in st.session_state.carrito.items():
                ws.append([fecha_str, origen, destino, ref_peticion, ean, it['Cantidad']])
            out = io.BytesIO(); wb.save(out)
            st.download_button("CLIC PARA DESCARGAR EXCEL", out.getvalue(), f"REPO_{destino}.xlsx", use_container_width=True)
else:
    st.error("Archivo catálogo no encontrado.")
    
