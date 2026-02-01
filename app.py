import streamlit as st
import pandas as pd
import os
import io
from datetime import datetime
from openpyxl import load_workbook

st.set_page_config(page_title="Peticiones", layout="wide")

# --- CSS HÍBRIDO: FUERZA BLANCO EN PC Y ADAPTABILIDAD EN MÓVIL ---
st.markdown("""
    <style>
    /* 1. RESET DE COLOR Y FONDO (Nuclear White) */
    html, body, .stApp, .main, .block-container, 
    div[data-testid="stExpander"], div[data-testid="stTab"], 
    div[data-testid="stHeader"], .stTabs, [data-testid="stVerticalBlock"] {
        background-color: #ffffff !important;
        color: #000000 !important;
    }

    /* 2. TEXTO Y TABLA */
    h1, h2, h3, p, span, label, li, .stMarkdown, div {
        color: #000000 !important;
    }
    .table-row {
        border: 1px solid #000000;
        margin-top: -1px;
        background-color: #ffffff !important;
        display: flex;
        align-items: center;
        width: 100%;
    }
    .cell-content {
        padding: 8px 12px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }

    /* 3. BOTONES (Adaptables) */
    .stButton>button {
        width: 100% !important;
        border-radius: 0px !important;
        font-weight: 700 !important;
        height: 42px;
        text-transform: uppercase;
        border: 1px solid #000000 !important;
        font-size: 0.7rem !important;
        padding: 0px 2px !important;
    }
    .stButton>button[kind="secondary"] { background-color: #ffffff !important; color: #000000 !important; }
    .stButton>button[kind="primary"] { background-color: #0052FF !important; color: #ffffff !important; border: none !important; }

    /* 4. RESUMEN FINAL */
    .summary-box {
        border: 2px solid #000000;
        padding: 15px;
        margin-top: 20px;
        background-color: #ffffff !important;
        font-weight: bold;
        display: flex;
        justify-content: space-between;
        color: #000000 !important;
    }

    /* 5. AJUSTES ESPECÍFICOS PARA MÓVIL (Pantallas < 600px) */
    @media (max-width: 600px) {
        .block-container { padding: 10px !important; }
        .summary-box { flex-direction: column; gap: 5px; }
        .stButton>button { font-size: 0.8rem !important; height: 50px; } /* Botón más grande para dedos */
        .cell-content { padding: 5px; }
        h1 { font-size: 1.5rem !important; }
    }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data
def get_catalogue():
    if not os.path.exists('catalogue.xlsx'): return None
    df = pd.read_excel('catalogue.xlsx', engine='openpyxl')
    df['EAN'] = df['EAN'].astype(str).str.replace('.0', '', regex=False).str.strip()
    return df, df.set_index('EAN').to_dict('index')

if 'carrito' not in st.session_state: st.session_state.carrito = {}

data_pack = get_catalogue()

st.title("Peticiones")

if data_pack:
    df_cat, cat_dict = data_pack

    # CONFIGURACIÓN
    c1, c2, c3 = st.columns([1, 1, 1])
    fecha_str = c1.date_input("FECHA", datetime.now()).strftime('%Y-%m-%d')
    origen = c2.selectbox("ORIGEN", ["PET Almacén Badalona", "ALM-CENTRAL"])
    destino = c3.selectbox("DESTINO", ["PET T002 Marbella", "ALM-TIENDA"])
    ref_peticion = st.text_input("REFERENCIA PETICIÓN")

    if origen == destino:
        st.error("Error: Origen y Destino coinciden."); st.stop()

    st.write("---")

    # OPERATIVA
    t1, t2 = st.tabs(["📂 CARGA EXCEL", "🔍 BUSCADOR"])

    with t1:
        archivo_v = st.file_uploader("Subir ventas", type=['xlsx'])
        if archivo_v and st.button("IMPORTAR DATOS", type="secondary"):
            df_v = pd.read_excel(archivo_v)
            for _, f_v in df_v.iterrows():
                ean = str(f_v['EAN']).replace('.0', '').strip()
                cant = int(f_v.get('Cantidad', 1))
                if ean in cat_dict:
                    prod = cat_dict[ean]
                    if ean in st.session_state.carrito: st.session_state.carrito[ean]['Cantidad'] += cant
                    else: st.session_state.carrito[ean] = {'Ref': prod['Referencia'], 'Nom': prod.get('Nombre',''), 'Col': prod.get('Color','-'), 'Tal': prod.get('Talla','-'), 'Cantidad': cant}
            st.rerun()

    with t2:
        busq = st.text_input("Filtrar catálogo...", key="search_main")
        if busq:
            mask = df_cat.apply(lambda row: busq.lower() in str(row.values).lower(), axis=1)
            res = df_cat[mask].head(30)
            
            st.markdown("<div style='border: 1px solid #000; background: #000; color: #fff; padding: 5px; font-size: 0.75rem; text-align: center;'>CATÁLOGO</div>", unsafe_allow_html=True)
            
            for _, f in res.iterrows():
                ean = f['EAN']
                en_car = ean in st.session_state.carrito
                st.markdown('<div class="table-row">', unsafe_allow_html=True)
                c1, c2 = st.columns([3, 1.5]) # Ajuste de proporción para móvil
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

    # LISTA Y RESUMEN FINAL
    if st.session_state.carrito:
        st.write("###")
        st.markdown("<div style='background: #000; color: #fff; padding: 5px; font-weight: bold;'>LISTA DE REPOSICIÓN</div>", unsafe_allow_html=True)
        
        for ean, item in list(st.session_state.carrito.items()):
            st.markdown('<div class="table-row">', unsafe_allow_html=True)
            ca, cb, cc = st.columns([2.5, 1.2, 0.8])
            with ca:
                st.markdown(f"<div class='cell-content'><strong>{item['Ref']}</strong><br><small>{item['Nom']} ({item['Col']}/{item['Tal']})</small></div>", unsafe_allow_html=True)
            with cb:
                item['Cantidad'] = st.number_input("C", 1, 9999, item['Cantidad'], key=f"q_{ean}", label_visibility="collapsed")
            with cc:
                if st.button("✕", key=f"d_{ean}"):
                    del st.session_state.carrito[ean]; st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        # RESUMEN AL FINAL
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
            st.download_button("CLIC PARA GUARDAR EXCEL", out.getvalue(), f"REPO_{destino}.xlsx", use_container_width=True)
else:
    st.error("Archivo catálogo no encontrado.")
    
