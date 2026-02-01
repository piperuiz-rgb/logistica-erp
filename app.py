import streamlit as st
import pandas as pd
import os
import io
from datetime import datetime
from openpyxl import load_workbook

# Configuración de página
st.set_page_config(page_title="LogiFlow Pro | Gextia", layout="wide", initial_sidebar_state="collapsed")

# --- ESTILOS CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #ffffff; }
    h1, h2, h3 { color: #000000 !important; font-family: 'Inter', sans-serif; }
    div[data-testid="stMetric"] { background-color: #fcfcfc; border: 1px solid #000000; padding: 15px; }
    /* Botón Añadido (Negro) */
    .stButton>button[kind="primary"] { background-color: #000000 !important; color: #ffffff !important; border-radius: 2px; border: none; }
    /* Botón Normal (Gris/Blanco) */
    .stButton>button[kind="secondary"] { border-radius: 2px; background-color: #ffffff; color: #000000; border: 1px solid #000000; }
    .tag-style { background-color: #f0f0f0; padding: 2px 8px; border-radius: 4px; font-size: 0.85em; color: #333; border: 1px solid #ddd; }
    .product-name { color: #666666; font-size: 0.9em; margin-bottom: 5px; }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data
def cargar_catalogo():
    if os.path.exists('catalogue.xlsx'):
        df = pd.read_excel('catalogue.xlsx', engine='openpyxl')
        df.columns = df.columns.str.strip()
        if 'EAN' in df.columns:
            df['EAN'] = df['EAN'].astype(str).str.replace('.0', '', regex=False).str.strip()
        return df
    return None

# Inicialización rápida del carrito
if 'carrito' not in st.session_state:
    st.session_state.carrito = {}

df_cat = cargar_catalogo()

st.title("📦 LOGIFLOW PRO")
st.write("---")

if df_cat is not None:
    # 1. CABECERA
    with st.container():
        fecha_peticion = st.date_input("FECHA", datetime.now())
        fecha_str = fecha_peticion.strftime('%Y-%m-%d')
        col_obs, col_o, col_d = st.columns([1.5, 1, 1])
        obs = col_obs.text_input("OBSERVACIONES")
        almacenes = ["PET Almacén Badalona", "PET T002 Marbella", "ALM-CENTRAL", "ALM-TIENDA"]
        origen = col_o.selectbox("ALMACÉN ORIGEN", almacenes)
        destino = col_d.selectbox("ALMACÉN DESTINO", almacenes)

    if origen == destino:
        st.error(f"⚠️ El origen y el destino no pueden ser iguales ({origen}).")
        st.stop()

    st.write("###")

    # 2. OPERATIVA
    t1, t2 = st.tabs(["📂 CARGA EXCEL", "🔍 BUSCADOR"])

    with t1:
        archivo_v = st.file_uploader("Subir ventas", type=['xlsx'])
        if archivo_v and st.button("PROCESAR EXCEL", type="primary"):
            df_v = pd.read_excel(archivo_v)
            for _, f in df_v.iterrows():
                ean = str(f['EAN']).replace('.0', '').strip()
                if ean in df_cat['EAN'].values:
                    if ean in st.session_state.carrito:
                        st.session_state.carrito[ean]['Cantidad'] += int(f['Cantidad'])
                    else:
                        match = df_cat[df_cat['EAN'] == ean].iloc[0]
                        st.session_state.carrito[ean] = {
                            'Referencia': match['Referencia'], 'Nombre': match.get('Nombre',''),
                            'Color': match.get('Color','-'), 'Talla': match.get('Talla','-'),
                            'Cantidad': int(f['Cantidad'])
                        }
            st.rerun()

    with t2:
        busq = st.text_input("Buscar producto...", key="search_input")
        if busq:
            # Filtro ultra-rápido
            res = df_cat[df_cat.apply(lambda row: row.astype(str).str.contains(busq, case=False).any(), axis=1)]
            for _, f in res.iterrows():
                ean_str = str(f['EAN'])
                ya_esta = ean_str in st.session_state.carrito
                
                c1, c2 = st.columns([4, 1.2])
                c1.markdown(f"**{f['Referencia']}** - <span class='product-name'>{f.get('Nombre', '')}</span><br><span class='tag-style'>{f.get('Color','-')}</span> <span class='tag-style'>{f.get('Talla','-')}</span>", unsafe_allow_html=True)
                
                # Cambio de color dinámico: Si está en el carrito, tipo "primary" (Negro)
                if c2.button("Añadido" if ya_esta else "Añadir", key=f"btn_{ean_str}", use_container_width=True, type="primary" if ya_esta else "secondary"):
                    if ya_esta:
                        st.session_state.carrito[ean_str]['Cantidad'] += 1
                    else:
                        st.session_state.carrito[ean_str] = {
                            'Referencia': f['Referencia'], 'Nombre': f.get('Nombre',''),
                            'Color': f.get('Color','-'), 'Talla': f.get('Talla','-'),
                            'Cantidad': 1
                        }
                    st.rerun()

    # 3. REVISIÓN
    if st.session_state.carrito:
        st.write("---")
        st.subheader("📋 REVISIÓN")
        items_para_borrar = []
        
        for ean, item in st.session_state.carrito.items():
            cp, cq, cx = st.columns([3, 1, 0.5])
            cp.markdown(f"**{item['Referencia']}** - {item['Nombre']}<br><small>{item['Color']} / {item['Talla']}</small>", unsafe_allow_html=True)
            item['Cantidad'] = cq.number_input("Cant", min_value=1, value=item['Cantidad'], key=f"edit_{ean}", label_visibility="collapsed")
            if cx.button("✕", key=f"del_{ean}"):
                items_para_borrar.append(ean)
        
        for ean in items_para_borrar:
            del st.session_state.carrito[ean]
            st.rerun()

        if os.path.exists('peticion.xlsx'):
            # Preparación de datos para Excel
            if st.button("📥 GENERAR Y DESCARGAR", type="primary", use_container_width=True):
                wb = load_workbook('peticion.xlsx')
                ws = wb.active
                for idx, (ean, it) in enumerate(st.session_state.carrito.items()):
                    ws.append([fecha_str, origen, destino, obs, ean, it['Cantidad']])
                
                output = io.BytesIO()
                wb.save(output)
                st.download_button("Click aquí para guardar archivo", data=output.getvalue(), file_name=f"REPO_{destino}.xlsx", use_container_width=True)
                # Opcional: st.session_state.carrito = {} despues de descargar
else:
    st.error("Sube 'catalogue.xlsx' a GitHub")
