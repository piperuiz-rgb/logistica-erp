import streamlit as st
import pandas as pd
import os
import io
from datetime import datetime
from openpyxl import load_workbook

st.set_page_config(page_title="LogiFlow Pro", layout="wide")

# --- DISEÑO MODERNO, SOBRIO Y FUNCIONAL (PC/MÓVIL) ---
st.markdown("""
    <style>
    /* Reset de fuentes y fondo */
    .stApp { background-color: #ffffff; font-family: 'Inter', -apple-system, sans-serif; }
    
    /* Contraste máximo para textos */
    h1, h2, h3, p, span, label, .stMarkdown { color: #000000 !important; }

    /* Tarjetas de producto: Limpias y separadas */
    .product-card {
        border-bottom: 1px solid #e0e0e0;
        padding: 15px 0px;
        margin-bottom: 5px;
    }

    /* Botones Estilo Minimalista */
    .stButton>button {
        width: 100%;
        border-radius: 4px;
        transition: all 0.2s ease;
        font-weight: 600 !important;
        height: 45px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        font-size: 0.85rem !important;
    }

    /* BOTÓN ESTADO NORMAL: Blanco con borde negro (Muy sobrio) */
    .stButton>button[kind="secondary"] {
        background-color: #ffffff !important;
        color: #000000 !important;
        border: 1.5px solid #000000 !important;
    }

    /* BOTÓN ESTADO AÑADIDO: Azul intenso con texto blanco (Máximo contraste) */
    .stButton>button[kind="primary"] {
        background-color: #0052FF !important;
        color: #ffffff !important;
        border: none !important;
    }

    /* Tags de información técnica */
    .tag-style {
        display: inline-block;
        background-color: #f2f2f2;
        color: #333333;
        padding: 2px 8px;
        border-radius: 2px;
        font-size: 0.75rem;
        margin-top: 5px;
        margin-right: 5px;
        border: 1px solid #ddd;
    }
    
    /* Mejora visibilidad en móviles */
    @media (max-width: 640px) {
        .product-card { padding: 20px 5px; }
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

    # 1. CONFIGURACIÓN (Expander sobrio)
    with st.expander("DATOS DE ENVÍO", expanded=True):
        c1, c2, c3 = st.columns(3)
        fecha_str = c1.date_input("FECHA", datetime.now()).strftime('%Y-%m-%d')
        origen = c2.selectbox("ORIGEN", ["PET Almacén Badalona", "ALM-CENTRAL"])
        destino = c3.selectbox("DESTINO", ["PET T002 Marbella", "ALM-TIENDA"])
        obs = st.text_input("OBSERVACIONES (OPCIONAL)")

    if origen == destino:
        st.error("⚠️ El almacén de origen y destino no pueden coincidir.")
        st.stop()

    st.write("---")

    # 2. OPERATIVA
    t1, t2 = st.tabs(["📂 CARGA EXCEL", "🔍 BUSCADOR MANUAL"])

    with t1:
        archivo_v = st.file_uploader("Subir archivo de ventas", type=['xlsx'])
        if archivo_v and st.button("CARGAR PRODUCTOS", type="secondary"):
            df_v = pd.read_excel(archivo_v)
            for _, f_v in df_v.iterrows():
                ean = str(f_v['EAN']).replace('.0', '').strip()
                if ean in cat_dict:
                    prod = cat_dict[ean]
                    cant_v = int(f_v.get('Cantidad', 1))
                    if ean in st.session_state.carrito: st.session_state.carrito[ean]['Cantidad'] += cant_v
                    else: st.session_state.carrito[ean] = {'Ref': prod['Referencia'], 'Nom': prod.get('Nombre',''), 'Col': prod.get('Color','-'), 'Tal': prod.get('Talla','-'), 'Cantidad': cant_v}
            st.success("Excel procesado correctamente.")
            st.rerun()

    with t2:
        c_bus, c_lim = st.columns([3, 1])
        busq = c_bus.text_input("Referencia, nombre, talla...", placeholder="Ej: Angélica")
        limite = c_lim.selectbox("Mostrar", [20, 50, 100, 500])
        
        if busq:
            mask = df_cat.apply(lambda row: busq.lower() in str(row.values).lower(), axis=1)
            res = df_cat[mask].head(int(limite))
            
            for _, f in res.iterrows():
                ean = f['EAN']
                en_car = ean in st.session_state.carrito
                
                st.markdown('<div class="product-card">', unsafe_allow_html=True)
                c1, c2 = st.columns([4, 1.5])
                c1.markdown(f"""
                    <div style='font-size: 1rem; font-weight: 700;'>{f['Referencia']}</div>
                    <div style='color: #444; font-size: 0.9rem;'>{f.get('Nombre','')}</div>
                    <span class='tag-style'>COL: {f.get('Color','-')}</span>
                    <span class='tag-style'>TALLA: {f.get('Talla','-')}</span>
                """, unsafe_allow_html=True)
                
                label = f"LLEVAS {st.session_state.carrito[ean]['Cantidad']}" if en_car else "AÑADIR"
                if c2.button(label, key=f"b_{ean}", type="primary" if en_car else "secondary"):
                    if en_car: st.session_state.carrito[ean]['Cantidad'] += 1
                    else: st.session_state.carrito[ean] = {'Ref': f['Referencia'], 'Nom': f.get('Nombre',''), 'Col': f.get('Color','-'), 'Tal': f.get('Talla','-'), 'Cantidad': 1}
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

    # 3. CARRITO
    if st.session_state.carrito:
        st.write("###")
        st.subheader(f"REVISIÓN ({sum(it['Cantidad'] for it in st.session_state.carrito.values())} UDS)")
        
        for ean, item in list(st.session_state.carrito.items()):
            ca, cb, cc = st.columns([3, 1, 0.5])
            ca.markdown(f"**{item['Ref']}** — {item['Nom']}<br><small>{item['Col']} / {item['Tal']}</small>", unsafe_allow_html=True)
            item['Cantidad'] = cb.number_input("CANT", 1, 5000, item['Cantidad'], key=f"q_{ean}", label_visibility="collapsed")
            if cc.button("✕", key=f"d_{ean}"):
                del st.session_state.carrito[ean]
                st.rerun()

        st.write("---")
        c_vac, c_gen = st.columns([1, 2])
        if c_vac.button("VACIAR CARRITO"):
            st.session_state.carrito = {}
            st.rerun()
            
        if os.path.exists('peticion.xlsx') and c_gen.button("GENERAR EXCEL PARA GEXTIA", type="primary"):
            wb = load_workbook('peticion.xlsx')
            ws = wb.active
            for ean, it in st.session_state.carrito.items():
                ws.append([fecha_str, origen, destino, obs, ean, it['Cantidad']])
            out = io.BytesIO()
            wb.save(out)
            st.download_button("CLIC PARA DESCARGAR REPOSICIÓN", out.getvalue(), f"REPO_{destino}.xlsx", use_container_width=True)
else:
    st.error("Error: catalogue.xlsx no encontrado.")
