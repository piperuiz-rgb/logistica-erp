import streamlit as st
import pandas as pd
import os
import io
from datetime import datetime
from openpyxl import load_workbook

st.set_page_config(page_title="LogiFlow Ultra", layout="wide")

# --- CSS DE ALTO CONTRASTE ---
st.markdown("""
    <style>
    /* Fondo principal blanco puro */
    .stApp { background-color: #ffffff; }
    
    /* Textos en negro puro para legibilidad */
    h1, h2, h3, p, span, label { color: #000000 !important; font-weight: 500; }
    
    /* Tarjetas de productos con fondo gris muy claro y borde negro */
    .product-card {
        background-color: #f8f9fa;
        border: 1px solid #000000;
        padding: 15px;
        border-radius: 4px;
        margin-bottom: 10px;
    }

    /* Estilo para las etiquetas (Color/Talla) en negrita */
    .tag-style {
        background-color: #e9ecef;
        padding: 3px 8px;
        border-radius: 3px;
        font-size: 0.85em;
        color: #000000 !important;
        border: 1px solid #adb5bd;
        font-weight: bold;
    }

    /* Botón estándar (Negro sobre blanco) */
    .stButton>button {
        width: 100%;
        border-radius: 2px;
        border: 2px solid #000000 !important;
        background-color: #ffffff !important;
        color: #000000 !important;
        font-weight: bold !important;
    }

    /* Botón cuando ya está añadido (Invertido: Blanco sobre negro) */
    .stButton>button[kind="primary"] {
        background-color: #000000 !important;
        color: #ffffff !important;
    }

    /* Inputs y Selectores con borde marcado */
    .stTextInput>div>div>input, .stSelectbox>div>div>div {
        border: 2px solid #000000 !important;
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
    with st.expander("⚙️ CONFIGURACIÓN DE ENVÍO", expanded=True):
        col1, col2, col3 = st.columns(3)
        fecha_str = col1.date_input("Fecha", datetime.now()).strftime('%Y-%m-%d')
        origen = col2.selectbox("Origen", ["PET Almacén Badalona", "ALM-CENTRAL"])
        destino = col3.selectbox("Destino", ["PET T002 Marbella", "ALM-TIENDA"])
        obs = st.text_input("Observaciones (Opcional)")

    if origen == destino:
        st.error("⚠️ El origen y destino no pueden ser iguales.")
        st.stop()

    st.write("---")

    # 2. OPERATIVA
    t1, t2 = st.tabs(["📂 CARGA MASIVA", "🔍 BUSCADOR MANUAL"])

    with t1:
        archivo_v = st.file_uploader("Sube Excel con EAN y Cantidad", type=['xlsx'])
        if archivo_v and st.button("PROCESAR EXCEL", type="secondary"):
            df_v = pd.read_excel(archivo_v)
            for _, f_v in df_v.iterrows():
                ean = str(f_v['EAN']).replace('.0', '').strip()
                cant = int(f_v['Cantidad'])
                if ean in cat_dict:
                    prod = cat_dict[ean]
                    if ean in st.session_state.carrito:
                        st.session_state.carrito[ean]['Cantidad'] += cant
                    else:
                        st.session_state.carrito[ean] = {
                            'Ref': prod['Referencia'], 'Nom': prod.get('Nombre',''),
                            'Col': prod.get('Color','-'), 'Tal': prod.get('Talla','-'), 
                            'Cantidad': cant
                        }
            st.rerun()

    with t2:
        busqueda = st.text_input("Buscar producto...", placeholder="Escribe referencia o nombre...")
        if busqueda:
            mask = df_cat.apply(lambda row: busqueda.lower() in str(row.values).lower(), axis=1)
            resultados = df_cat[mask].head(15) 

            for _, f in resultados.iterrows():
                ean = f['EAN']
                en_carrito = ean in st.session_state.carrito
                
                with st.container():
                    st.markdown('<div class="product-card">', unsafe_allow_html=True)
                    c1, c2 = st.columns([4, 1.2])
                    c1.markdown(f"""
                        <span style="font-size: 1.1em; font-weight: bold;">{f['Referencia']}</span> — {f.get('Nombre','')} <br>
                        <span class="tag-style">COLOR: {f.get('Color','-')}</span> 
                        <span class="tag-style">TALLA: {f.get('Talla','-')}</span>
                    """, unsafe_allow_html=True)
                    
                    label = f"Añadido ({st.session_state.carrito[ean]['Cantidad']})" if en_carrito else "Añadir"
                    if c2.button(label, key=f"btn_{ean}", type="primary" if en_carrito else "secondary"):
                        if en_carrito: st.session_state.carrito[ean]['Cantidad'] += 1
                        else:
                            st.session_state.carrito[ean] = {'Ref': f['Referencia'], 'Nom': f.get('Nombre',''), 'Col': f.get('Color','-'), 'Tal': f.get('Talla','-'), 'Cantidad': 1}
                        st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)

    # 3. REVISIÓN Y EXPORTACIÓN
    if st.session_state.carrito:
        st.write("---")
        st.subheader(f"📋 RESUMEN DE CARGA ({sum(it['Cantidad'] for it in st.session_state.carrito.values())} Uds)")
        
        for ean, item in list(st.session_state.carrito.items()):
            col_a, col_b, col_c = st.columns([3, 1, 0.5])
            col_a.markdown(f"**{item['Ref']}** - {item['Nom']} <br> <small>{item['Col']} / {item['Tal']}</small>", unsafe_allow_html=True)
            item['Cantidad'] = col_b.number_input("Cant.", 1, 1000, item['Cantidad'], key=f"q_{ean}")
            if col_c.button("✕", key=f"del_{ean}"):
                del st.session_state.carrito[ean]
                st.rerun()

        st.write("###")
        c_vaciar, c_descarga = st.columns([1, 2])
        
        if c_vaciar.button("🗑️ VACIAR TODO"):
            st.session_state.carrito = {}
            st.rerun()

        if os.path.exists('peticion.xlsx'):
            if c_descarga.button("📥 FINALIZAR Y DESCARGAR EXCEL", type="primary"):
                wb = load_workbook('peticion.xlsx')
                ws = wb.active
                for ean, it in st.session_state.carrito.items():
                    ws.append([fecha_str, origen, destino, obs, ean, it['Cantidad']])
                
                output = io.BytesIO()
                wb.save(output)
                st.download_button("⬇️ GUARDAR REPOSICIÓN", output.getvalue(), f"REPO_{destino}.xlsx", use_container_width=True)
else:
    st.error("⚠️ Sube 'catalogue.xlsx' a GitHub.")
