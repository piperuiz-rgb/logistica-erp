import streamlit as st
import pandas as pd
import os
import io
from datetime import datetime
from openpyxl import load_workbook

st.set_page_config(page_title="LogiFlow Ultra", layout="wide")

# --- CSS DE CONTRASTE DINÁMICO ---
st.markdown("""
    <style>
    .stApp { background-color: #ffffff; }
    h1, h2, h3, p, span, label, .stMarkdown { color: #000000 !important; }

    .product-card {
        background-color: #fcfcfc;
        border: 1px solid #000000;
        padding: 12px;
        margin-bottom: 8px;
    }

    .stButton>button {
        width: 100%;
        border-radius: 2px;
        border: 1px solid #000000 !important;
        font-weight: bold !important;
    }

    /* BOTÓN NO AÑADIDO: Fondo claro, texto oscuro */
    .stButton>button[kind="secondary"] {
        background-color: #ffffff !important;
        color: #000000 !important;
    }

    /* BOTÓN AÑADIDO: Fondo oscuro, texto claro (Blanco sobre Gris Carbón) */
    .stButton>button[kind="primary"] {
        background-color: #333333 !important;
        color: #ffffff !important;
    }

    .tag-style {
        background-color: #000000;
        color: #ffffff !important;
        padding: 2px 8px;
        font-weight: bold;
        font-size: 0.8em;
        margin-right: 5px;
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
        st.error("⚠️ El origen y destino coinciden.")
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
                    cant_v = int(f_v.get('Cantidad', 1))
                    if ean in st.session_state.carrito: st.session_state.carrito[ean]['Cantidad'] += cant_v
                    else: st.session_state.carrito[ean] = {'Ref': prod['Referencia'], 'Nom': prod.get('Nombre',''), 'Col': prod.get('Color','-'), 'Tal': prod.get('Talla','-'), 'Cantidad': cant_v}
            st.rerun()

    with t2:
        col_busq, col_lim = st.columns([3, 1])
        busq = col_busq.text_input("Buscar producto...")
        limite = col_lim.selectbox("Ver resultados", [20, 50, 100, "Todos"])
        
        if busq:
            mask = df_cat.apply(lambda row: busq.lower() in str(row.values).lower(), axis=1)
            res = df_cat[mask]
            
            # Aplicar límite
            if limite != "Todos":
                res = res.head(int(limite))
            
            for _, f in res.iterrows():
                ean = f['EAN']
                en_car = ean in st.session_state.carrito
                
                st.markdown('<div class="product-card">', unsafe_allow_html=True)
                c1, c2 = st.columns([4, 1.2])
                c1.markdown(f"**{f['Referencia']}** — {f.get('Nombre','')}<br><span class='tag-style'>{f.get('Color','-')}</span> <span class='tag-style'>{f.get('Talla','-')}</span>", unsafe_allow_html=True)
                
                label = f"Llevas {st.session_state.carrito[ean]['Cantidad']}" if en_car else "Añadir"
                if c2.button(label, key=f"b_{ean}", type="primary" if en_car else "secondary"):
                    if en_car: st.session_state.carrito[ean]['Cantidad'] += 1
                    else: st.session_state.carrito[ean] = {'Ref': f['Referencia'], 'Nom': f.get('Nombre',''), 'Col': f.get('Color','-'), 'Tal': f.get('Talla','-'), 'Cantidad': 1}
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

    # 3. REVISIÓN Y EXPORTACIÓN
    if st.session_state.carrito:
        st.write("---")
        total_p = sum(it['Cantidad'] for it in st.session_state.carrito.values())
        st.subheader(f"📋 RESUMEN ({total_p} piezas)")
        
        for ean, item in list(st.session_state.carrito.items()):
            ca, cb, cc = st.columns([3, 1, 0.5])
            ca.write(f"**{item['Ref']}** - {item['Nom']} ({item['Col']}/{item['Tal']})")
            item['Cantidad'] = cb.number_input("Uds", 1, 1000, item['Cantidad'], key=f"q_{ean}", label_visibility="collapsed")
            if cc.button("✕", key=f"d_{ean}"):
                del st.session_state.carrito[ean]
                st.rerun()

        st.write("###")
        c_v, c_d = st.columns([1, 2])
        if c_v.button("🗑️ VACIAR CARRITO"):
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
    st.error("Falta 'catalogue.xlsx' en GitHub.")
