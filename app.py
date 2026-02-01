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
    .stButton>button[kind="primary"] { background-color: #000000 !important; color: #ffffff !important; border-radius: 2px; }
    .tag-style { background-color: #f0f0f0; padding: 2px 8px; border-radius: 4px; font-size: 0.85em; color: #333; border: 1px solid #ddd; }
    .product-name { color: #666666; font-size: 0.9em; margin-bottom: 5px; }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data
def cargar_catalogo():
    fichero = 'catalogue.xlsx'
    if os.path.exists(fichero):
        df = pd.read_excel(fichero, engine='openpyxl')
        df.columns = df.columns.str.strip()
        if 'EAN' in df.columns:
            df['EAN'] = df['EAN'].astype(str).str.replace('.0', '', regex=False).str.strip()
        return df
    return None

if 'carrito' not in st.session_state:
    st.session_state.carrito = []

df_cat = cargar_catalogo()

st.title("📦 LOGIFLOW PRO")
st.write("---")

if df_cat is not None:
    # 1. CABECERA Y VALIDACIÓN
    with st.container():
        fecha_peticion = st.date_input("FECHA", datetime.now())
        fecha_str = fecha_peticion.strftime('%Y-%m-%d')
        
        col_obs, col_o, col_d = st.columns([1.5, 1, 1])
        observaciones = col_obs.text_input("OBSERVACIONES")
        
        lista_almacenes = ["PET Almacén Badalona", "PET T002 Marbella", "ALM-CENTRAL", "ALM-TIENDA"]
        origen = col_o.selectbox("ALMACÉN ORIGEN", lista_almacenes)
        destino = col_d.selectbox("ALMACÉN DESTINO", lista_almacenes)

    # --- AVISO DE SEGURIDAD (BLOQUEO) ---
    if origen == destino:
        st.error(f"⚠️ **ERROR DE CONFIGURACIÓN**: El almacén de ORIGEN y DESTINO no pueden ser iguales ({origen}). Por favor, cambia uno de los dos para continuar.")
        st.stop() # Detiene la ejecución del resto de la app

    st.write("###")

    # 2. OPERATIVA
    t1, t2 = st.tabs(["📂 CARGA EXCEL", "🔍 BUSCADOR"])

    with t1:
        archivo_v = st.file_uploader("Subir ventas", type=['xlsx'])
        if archivo_v and st.button("PROCESAR", type="primary", use_container_width=True):
            df_v = pd.read_excel(archivo_v)
            for _, f in df_v.iterrows():
                ean_v = str(f['EAN']).replace('.0', '').strip()
                match = df_cat[df_cat['EAN'] == ean_v]
                if not match.empty:
                    st.session_state.carrito.append({
                        'Fecha': fecha_str, 'Almacén de origen': origen, 'Almacén de destino': destino,
                        'Observaciones': observaciones, 'EAN': ean_v, 'Cantidad': int(f['Cantidad']),
                        'Referencia': match.iloc[0]['Referencia'], 
                        'Nombre': match.iloc[0].get('Nombre', ''),
                        'Color': match.iloc[0].get('Color','-'), 
                        'Talla': match.iloc[0].get('Talla','-')
                    })
            st.rerun()

    with t2:
        busq = st.text_input("Buscar por Referencia, Nombre, Color o Talla")
        if busq:
            res = df_cat[df_cat.apply(lambda row: row.astype(str).str.contains(busq, case=False).any(), axis=1)]
            for _, f in res.iterrows():
                c1, c2 = st.columns([4, 1.2])
                c1.markdown(f"""
                    **{f['Referencia']}** - <span class='product-name'>{f.get('Nombre', '')}</span><br>
                    <span class='tag-style'>{f.get('Color','-')}</span> <span class='tag-style'>{f.get('Talla','-')}</span>
                """, unsafe_allow_html=True)
                
                if c2.button("Añadir", key=f"btn_{f['EAN']}", use_container_width=True):
                    st.session_state.carrito.append({
                        'Fecha': fecha_str, 'Almacén de origen': origen, 'Almacén de destino': destino,
                        'Observaciones': observaciones, 'EAN': str(f['EAN']), 'Cantidad': 1,
                        'Referencia': f['Referencia'], 'Nombre': f.get('Nombre', ''),
                        'Color': f.get('Color','-'), 'Talla': f.get('Talla','-')
                    })
                    st.rerun()

    # 3. REVISIÓN Y TOTALES
    if st.session_state.carrito:
        st.write("---")
        st.subheader("📋 LISTA DE CARGA")
        for i, item in enumerate(st.session_state.carrito):
            cp, cq, cx = st.columns([3, 1, 0.5])
            cp.markdown(f"**{item['Referencia']}** - {item['Nombre']}<br><small>{item['Color']} / {item['Talla']}</small>", unsafe_allow_html=True)
            item['Cantidad'] = cq.number_input("Cant", min_value=1, value=item['Cantidad'], key=f"edit_{i}", label_visibility="collapsed")
            if cx.button("✕", key=f"del_{i}"):
                st.session_state.carrito.pop(i)
                st.rerun()

        st.write("###")
        c1, c2, c3 = st.columns(3)
        c1.metric("TOTAL UDS", sum(it['Cantidad'] for it in st.session_state.carrito))
        c2.metric("LÍNEAS", len(st.session_state.carrito))
        c3.metric("DESTINO", destino)

        if os.path.exists('peticion.xlsx'):
            wb = load_workbook('peticion.xlsx')
            ws = wb.active
            for idx, r in enumerate(st.session_state.carrito):
                fila = idx + 2
                ws.cell(row=fila, column=1, value=r['Fecha'])
                ws.cell(row=fila, column=2, value=r['Almacén de origen'])
                ws.cell(row=fila, column=3, value=r['Almacén de destino'])
                ws.cell(row=fila, column=4, value=r['Observaciones'])
                ws.cell(row=fila, column=5, value=r['EAN'])
                ws.cell(row=fila, column=6, value=r['Cantidad'])
            
            output = io.BytesIO()
            wb.save(output)
            
            st.write("###")
            c_v, c_d = st.columns([1, 2])
            if c_v.button("VACIAR LISTA", use_container_width=True):
                st.session_state.carrito = []
                st.rerun()
                
            c_d.download_button(
                label="📥 DESCARGAR PARA GEXTIA",
                data=output.getvalue(),
                file_name=f"REPO_{destino}.xlsx",
                use_container_width=True,
                type="primary"
            )
        else:
            st.error("⚠️ No se encontró 'peticion.xlsx'")
else:
    st.error("⚠️ No se encuentra 'catalogue.xlsx' en GitHub.")
    
