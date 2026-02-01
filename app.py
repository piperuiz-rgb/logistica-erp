import streamlit as st
import pandas as pd
import os
import io
from datetime import datetime
from openpyxl import load_workbook

st.set_page_config(page_title="LogiFlow Pro", layout="wide")

# --- CSS TÉCNICO: TABLA PURA Y ALTO CONTRASTE ---
st.markdown("""
    <style>
    /* Fondo Blanco Nieve */
    .stApp, div[data-testid="stExpander"], div[data-testid="stTab"] { 
        background-color: #ffffff !important; 
    }
    
    /* Forzar Texto Negro */
    h1, h2, h3, p, span, label, .stMarkdown { color: #000000 !important; }

    /* Estructura de Tabla con Bordes Laterales */
    .table-row {
        border: 1px solid #000000;
        margin-top: -1px;
        padding: 0px; /* Controlado por columnas */
        background-color: #ffffff;
    }
    
    .cell-content {
        padding: 10px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        height: 100%;
    }

    /* Centrado del Botón */
    div[data-testid="column"] {
        display: flex;
        align-items: center;
        justify-content: center;
    }

    /* Botones Cuadrados */
    .stButton>button {
        width: 90% !important;
        border-radius: 0px !important;
        font-weight: 700 !important;
        height: 45px;
        text-transform: uppercase;
        border: 1px solid #000000 !important;
    }

    /* Botón Secundario (Blanco) y Primario (Azul Eléctrico) */
    .stButton>button[kind="secondary"] { background-color: #ffffff !important; color: #000000 !important; }
    .stButton>button[kind="primary"] { background-color: #0052FF !important; color: #ffffff !important; border: none !important; }

    /* Panel de Resumen Superior */
    .summary-box {
        border: 2px solid #000000;
        padding: 15px;
        margin-bottom: 20px;
        display: flex;
        justify-content: space-between;
        background-color: #fdfdfd;
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

st.title("📦 LOGIFLOW PRO")

if data_pack:
    df_cat, cat_dict = data_pack

    # 1. CONFIGURACIÓN
    with st.container():
        c1, c2, c3 = st.columns(3)
        fecha_str = c1.date_input("FECHA", datetime.now()).strftime('%Y-%m-%d')
        origen = c2.selectbox("ORIGEN", ["PET Almacén Badalona", "ALM-CENTRAL"])
        destino = c3.selectbox("DESTINO", ["PET T002 Marbella", "ALM-TIENDA"])
        obs = st.text_input("OBSERVACIONES")

    if origen == destino:
        st.error("Error: Origen y Destino coinciden."); st.stop()

    # --- RESUMEN DE UNIDADES (Cuadro de Mando) ---
    total_uds = sum(it['Cantidad'] for it in st.session_state.carrito.values())
    total_refs = len(st.session_state.carrito)
    
    st.markdown(f"""
    <div class="summary-box">
        <div><strong>UNIDADES:</strong> {total_uds}</div>
        <div><strong>REFERENCIAS:</strong> {total_refs}</div>
        <div><strong>DESTINO:</strong> {destino}</div>
    </div>
    """, unsafe_allow_html=True)

    # 2. OPERATIVA
    t1, t2 = st.tabs(["📂 CARGA EXCEL", "🔍 BUSCADOR MANUAL"])

    with t1:
        archivo_v = st.file_uploader("Subir ventas", type=['xlsx'])
        if archivo_v and st.button("IMPORTAR", type="secondary"):
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
        busq = st.text_input("Buscar...", placeholder="Ref, Nombre...")
        if busq:
            mask = df_cat.apply(lambda row: busq.lower() in str(row.values).lower(), axis=1)
            res = df_cat[mask].head(25)
            
            # Cabecera de tabla
            st.markdown("<div style='border: 1px solid #000; border-bottom: none; background: #000; color: #fff; padding: 5px; font-size: 0.8rem; text-align: center;'>CATÁLOGO DISPONIBLE</div>", unsafe_allow_html=True)
            
            for _, f in res.iterrows():
                ean = f['EAN']
                en_car = ean in st.session_state.carrito
                
                # Fila con bordes laterales y centrado
                st.markdown('<div class="table-row">', unsafe_allow_html=True)
                c1, c2 = st.columns([4, 1.2])
                with c1:
                    st.markdown(f"""<div class='cell-content'>
                        <strong>{f['Referencia']}</strong>
                        <span style='font-size: 0.85rem;'>{f.get('Nombre','')}</span>
                        <span style='font-size: 0.75rem; color: #666;'>{f.get('Color','-')} / {f.get('Talla','-')}</span>
                    </div>""", unsafe_allow_html=True)
                with c2:
                    label = f"OK ({st.session_state.carrito[ean]['Cantidad']})" if en_car else "AÑADIR"
                    if st.button(label, key=f"b_{ean}", type="primary" if en_car else "secondary"):
                        if en_car: st.session_state.carrito[ean]['Cantidad'] += 1
                        else: st.session_state.carrito[ean] = {'Ref': f['Referencia'], 'Nom': f.get('Nombre',''), 'Col': f.get('Color','-'), 'Tal': f.get('Talla','-'), 'Cantidad': 1}
                        st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

    # 3. LISTA DE REVISIÓN
    if st.session_state.carrito:
        st.write("###")
        st.markdown("<div style='background: #000; color: #fff; padding: 5px; font-weight: bold;'>PREPARACIÓN DE ENVÍO</div>", unsafe_allow_html=True)
        
        for ean, item in list(st.session_state.carrito.items()):
            st.markdown('<div class="table-row">', unsafe_allow_html=True)
            ca, cb, cc = st.columns([3, 1, 0.5])
            with ca:
                st.markdown(f"<div class='cell-content'><strong>{item['Ref']}</strong><br><small>{item['Nom']} ({item['Col']}/{item['Tal']})</small></div>", unsafe_allow_html=True)
            with cb:
                item['Cantidad'] = st.number_input("C", 1, 9999, item['Cantidad'], key=f"q_{ean}", label_visibility="collapsed")
            with cc:
                if st.button("✕", key=f"d_{ean}"):
                    del st.session_state.carrito[ean]; st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        st.write("###")
        cv, cg = st.columns([1, 2])
        if cv.button("LIMPIAR TODO"):
            st.session_state.carrito = {}; st.rerun()
            
        if os.path.exists('peticion.xlsx') and cg.button("GENERAR EXCEL GEXTIA", type="primary"):
            wb = load_workbook('peticion.xlsx')
            ws = wb.active
            for ean, it in st.session_state.carrito.items():
                ws.append([fecha_str, origen, destino, obs, ean, it['Cantidad']])
            out = io.BytesIO(); wb.save(out)
            st.download_button("📥 DESCARGAR", out.getvalue(), f"REPO_{destino}.xlsx", use_container_width=True)
else:
    st.error("No se encontró el catálogo.")
