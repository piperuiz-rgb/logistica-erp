import streamlit as st
import pandas as pd
import os
import io
from datetime import datetime
from openpyxl import load_workbook

st.set_page_config(page_title="LogiFlow Ultra", layout="wide")

# --- CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #ffffff; }
    .stButton>button { width: 100%; border-radius: 2px; }
    .tag-style { background-color: #f0f0f0; padding: 2px 6px; border-radius: 3px; font-size: 0.8em; border: 1px solid #ddd; }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data
def get_catalogue():
    if not os.path.exists('catalogue.xlsx'): return None
    df = pd.read_excel('catalogue.xlsx', engine='openpyxl')
    df['EAN'] = df['EAN'].astype(str).str.replace('.0', '', regex=False).str.strip()
    # Creamos un diccionario para búsqueda instantánea por EAN
    return df, df.set_index('EAN').to_dict('index')

# Inicializar sesión
if 'carrito' not in st.session_state: st.session_state.carrito = {}

# Carga de datos
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
        obs = st.text_input("Observaciones")

    if origen == destino:
        st.error("⚠️ El origen y destino coinciden.")
        st.stop()

    # 2. OPERATIVA (Pestañas)
    t1, t2 = st.tabs(["📂 CARGA MASIVA (EXCEL)", "🔍 BUSCADOR MANUAL"])

    with t1:
        st.write("Sube un Excel con columnas **EAN** y **Cantidad**")
        archivo_v = st.file_uploader("Seleccionar archivo", type=['xlsx'], key="uploader")
        if archivo_v and st.button("PROCESAR Y AÑADIR", type="primary"):
            df_v = pd.read_excel(archivo_v)
            df_v.columns = df_v.columns.str.strip()
            
            exitos = 0
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
                    exitos += 1
            st.success(f"Se han añadido {exitos} productos al carrito.")
            st.rerun()

    with t2:
        busqueda = st.text_input("Escribe Ref, Nombre, Color o Talla...", key="main_search")
        if busqueda:
            # Filtro optimizado
            mask = df_cat.apply(lambda row: busqueda.lower() in str(row.values).lower(), axis=1)
            resultados = df_cat[mask].head(15) 

            for _, f in resultados.iterrows():
                ean = f['EAN']
                en_carrito = ean in st.session_state.carrito
                
                c1, c2 = st.columns([4, 1.2])
                c1.markdown(f"**{f['Referencia']}** - {f.get('Nombre','')} <br> <span class='tag-style'>{f.get('Color','-')}</span> <span class='tag-style'>{f.get('Talla','-')}</span>", unsafe_allow_html=True)
                
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
        st.subheader("📋 REVISIÓN")
        
        for ean, item in list(st.session_state.carrito.items()):
            col_a, col_b, col_c = st.columns([3, 1, 0.5])
            col_a.write(f"**{item['Ref']}** ({item['Col']}/{item['Tal']})")
            item['Cantidad'] = col_b.number_input("Cant", 1, 1000, item['Cantidad'], key=f"q_{ean}", label_visibility="collapsed")
            if col_c.button("✕", key=f"del_{ean}"):
                del st.session_state.carrito[ean]
                st.rerun()

        if os.path.exists('peticion.xlsx'):
            if st.button("📥 FINALIZAR Y GENERAR EXCEL", type="primary"):
                wb = load_workbook('peticion.xlsx')
                ws = wb.active
                for ean, it in st.session_state.carrito.items():
                    ws.append([fecha_str, origen, destino, obs, ean, it['Cantidad']])
                
                output = io.BytesIO()
                wb.save(output)
                st.download_button("⬇️ GUARDAR REPOSICIÓN", output.getvalue(), f"REPO_{destino}.xlsx")
else:
    st.error("⚠️ Sube 'catalogue.xlsx' a GitHub.")
