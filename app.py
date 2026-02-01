import streamlit as st
import pandas as pd
import os
import io
from datetime import datetime
from openpyxl import load_workbook

st.set_page_config(page_title="LogiFlow Ultra", layout="wide")

# --- CSS DE ALTO CONTRASTE Y LEGIBILIDAD ---
st.markdown("""
    <style>
    .stApp { background-color: #ffffff; }
    
    /* Forzar texto negro en toda la app */
    h1, h2, h3, p, span, label, .stMarkdown { color: #000000 !important; }

    /* Tarjeta de producto */
    .product-card {
        background-color: #fcfcfc;
        border: 1px solid #000000;
        padding: 12px;
        margin-bottom: 8px;
    }

    /* BOTONES: Estilo Base */
    .stButton>button {
        width: 100%;
        border-radius: 0px;
        border: 1px solid #000000 !important;
        font-weight: bold !important;
        transition: 0.2s;
    }

    /* Botón ANTES de añadir (Blanco) */
    .stButton>button[kind="secondary"] {
        background-color: #ffffff !important;
        color: #000000 !important;
    }

    /* Botón DESPUÉS de añadir (Gris claro para legibilidad total) */
    .stButton>button[kind="primary"] {
        background-color: #dddddd !important;
        color: #000000 !important;
        border: 1px solid #000000 !important;
    }

    .tag-style {
        background-color: #eeeeee;
        padding: 2px 6px;
        color: #000000;
        font-weight: bold;
        border: 1px solid #999999;
        font-size: 0.8em;
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
    with st.expander("⚙️ CONFIGURACIÓN", expanded=True):
        c1, c2, c3 = st.columns(3)
        fecha_str = c1.date_input("Fecha", datetime.now()).strftime('%Y-%m-%d')
        origen = c2.selectbox("Origen", ["PET Almacén Badalona", "ALM-CENTRAL"])
        destino = c3.selectbox("Destino", ["PET T002 Marbella", "ALM-TIENDA"])
        obs = st.text_input("Observaciones")

    if origen == destino:
        st.error("⚠️ Origen y Destino iguales.")
        st.stop()

    # 2. OPERATIVA
    t1, t2 = st.tabs(["📂 CARGA EXCEL", "🔍 BUSCADOR"])

    with t1:
        archivo_v = st.file_uploader("Excel de Ventas", type=['xlsx'])
        if archivo_v and st.button("PROCESAR", type="secondary"):
            df_v = pd.read_excel(archivo_v)
            for _, f_v in df_v.iterrows():
                ean = str(f_v['EAN']).replace('.0', '').strip()
                if ean in cat_dict:
                    prod = cat_dict[ean]
                    if ean in st.session_state.carrito: st.session_state.carrito[ean]['Cantidad'] += int(f_v['Cantidad'])
                    else: st.session_state.carrito[ean] = {'Ref': prod['Referencia'], 'Nom': prod.get('Nombre',''), 'Col': prod.get('Color','-'), 'Tal': prod.get('Talla','-'), 'Cantidad': int(f_v['Cantidad'])}
            st.rerun()

    with t2:
        busq = st.text_input("Escribe para buscar...")
        if busq:
            mask = df_cat.apply(lambda row: busq.lower() in str(row.values).lower(), axis=1)
            res = df_cat[mask].head(15)
            for _, f in res.iterrows():
                ean = f['EAN']
                en_car = ean in st.session_state.carrito
                
                st.markdown('<div class="product-card">', unsafe_allow_html=True)
                c1, c2 = st.columns([4, 1.2])
                c1.markdown(f"**{f['Referencia']}** — {f.get('Nombre','')}<br><span class='tag-style'>{f.get('Color','-')}</span> <span class='tag-style'>{f.get('Talla','-')}</span>", unsafe_allow_html=True)
                
                label = f"En lista ({st.session_state.carrito[ean]['Cantidad']})" if en_car else "Añadir"
                # Usamos primary para el estado "Añadido" y secondary para el "Normal"
                if c2.button(label, key=f"b_{ean}", type="primary" if en_car else "secondary"):
                    if en_car: st.session_state.carrito[ean]['Cantidad'] += 1
                    else: st.session_state.carrito[ean] = {'Ref': f['Referencia'], 'Nom': f.get('Nombre',''), 'Col': f.get('Color','-'), 'Tal': f.get('Talla','-'), 'Cantidad': 1}
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

    # 3. REVISIÓN
    if st.session_state.carrito:
        st.write("---")
        st.subheader(f"📋 LISTA ({sum(it['Cantidad'] for it in st.session_state.carrito.values())} Uds)")
        for ean, item in list(st.session_state.carrito.items()):
            ca, cb, cc = st.columns([3, 1, 0.5])
            ca.write(f"**{item['Ref']}** - {item['Nom']}")
            item['Cantidad'] = cb.number_input("Cant", 1, 1000, item['Cantidad'], key=f"q_{ean}", label_visibility="collapsed")
            if cc.button("✕", key=f"d_{ean}"):
                del st.session_state.carrito[ean]
                st.rerun()

        st.write("###")
        c_v, c_d = st.columns([1, 2])
        if c_v.button("🗑️ VACIAR"):
            st.session_state.carrito = {}
            st.rerun()
        if os.path.exists('peticion.xlsx') and c_d.button("📥 GENERAR EXCEL", type="primary"):
            wb = load_workbook('peticion.xlsx')
            ws = wb.active
            for ean, it in st.session_state.carrito.items():
                ws.append([fecha_str, origen, destino, obs, ean, it['Cantidad']])
            out = io.BytesIO()
            wb.save(out)
            st.download_button("⬇️ GUARDAR REPOSICIÓN", out.getvalue(), f"REPO_{destino}.xlsx")
else:
    st.error("Falta 'catalogue.xlsx'")
