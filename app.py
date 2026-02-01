import streamlit as st
import pandas as pd
import os
import io
from datetime import datetime
from openpyxl import load_workbook

st.set_page_config(page_title="LogiFlow Ultra", layout="wide")

# --- CSS MINIMALISTA ---
st.markdown("""
    <style>
    .stApp { background-color: #ffffff; }
    .stButton>button { width: 100%; border-radius: 2px; }
    .added-btn { background-color: #000000 !important; color: white !important; }
    .tag-style { background-color: #f0f0f0; padding: 2px 6px; border-radius: 3px; font-size: 0.8em; border: 1px solid #ddd; }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data
def get_data():
    if not os.path.exists('catalogue.xlsx'): return None
    df = pd.read_excel('catalogue.xlsx', engine='openpyxl')
    df['EAN'] = df['EAN'].astype(str).str.replace('.0', '', regex=False).str.strip()
    return df

# Inicializar sesión
if 'carrito' not in st.session_state: st.session_state.carrito = {}

df_cat = get_data()

st.title("📦 LOGIFLOW PRO")

if df_cat is not None:
    # 1. CABECERA (Configuración fija)
    with st.expander("⚙️ CONFIGURACIÓN DE ENVÍO", expanded=True):
        col1, col2, col3 = st.columns(3)
        fecha_str = col1.date_input("Fecha", datetime.now()).strftime('%Y-%m-%d')
        origen = col2.selectbox("Origen", ["PET Almacén Badalona", "ALM-CENTRAL"])
        destino = col3.selectbox("Destino", ["PET T002 Marbella", "ALM-TIENDA"])
        obs = st.text_input("Observaciones")

    if origen == destino:
        st.error("⚠️ El origen y destino coinciden.")
        st.stop()

    # 2. BUSCADOR (Optimizado)
    st.subheader("🔍 BUSCADOR")
    busqueda = st.text_input("Escribe Ref, Nombre, Color o Talla...", key="main_search")

    if busqueda:
        # Filtro rápido
        mask = df_cat.apply(lambda row: busqueda.lower() in str(row.values).lower(), axis=1)
        resultados = df_cat[mask].head(20) # Limitamos a 20 para máxima velocidad

        for _, f in resultados.iterrows():
            ean = f['EAN']
            en_carrito = ean in st.session_state.carrito
            
            c1, c2 = st.columns([4, 1])
            c1.markdown(f"**{f['Referencia']}** - {f.get('Nombre','')} <br> <span class='tag-style'>{f.get('Color','-')}</span> <span class='tag-style'>{f.get('Talla','-')}</span>", unsafe_allow_html=True)
            
            # El botón cambia de color y texto si ya está
            label = f"Añadido ({st.session_state.carrito[ean]['Cantidad']})" if en_carrito else "Añadir"
            if c2.button(label, key=f"btn_{ean}", type="primary" if en_carrito else "secondary"):
                if en_carrito:
                    st.session_state.carrito[ean]['Cantidad'] += 1
                else:
                    st.session_state.carrito[ean] = {
                        'Ref': f['Referencia'], 'Nom': f.get('Nombre',''),
                        'Col': f.get('Color','-'), 'Tal': f.get('Talla','-'), 'Cantidad': 1
                    }
                st.rerun()

    # 3. REVISIÓN Y EXPORTACIÓN
    if st.session_state.carrito:
        st.write("---")
        st.subheader("📋 LISTA ACTUAL")
        
        for ean, item in list(st.session_state.carrito.items()):
            col_a, col_b, col_c = st.columns([3, 1, 0.5])
            col_a.write(f"**{item['Ref']}** ({item['Col']}/{item['Tal']})")
            item['Cantidad'] = col_b.number_input("Cant", 1, 1000, item['Cantidad'], key=f"q_{ean}", label_visibility="collapsed")
            if col_c.button("✕", key=f"del_{ean}"):
                del st.session_state.carrito[ean]
                st.rerun()

        if os.path.exists('peticion.xlsx'):
            if st.button("📥 FINALIZAR Y DESCARGAR", type="primary"):
                wb = load_workbook('peticion.xlsx')
                ws = wb.active
                for ean, it in st.session_state.carrito.items():
                    ws.append([fecha_str, origen, destino, obs, ean, it['Cantidad']])
                
                output = io.BytesIO()
                wb.save(output)
                st.download_button("⬇️ Guardar Excel", output.getvalue(), f"REPO_{destino}.xlsx", "application/vnd.ms-excel")
