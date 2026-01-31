import streamlit as st
import pandas as pd
import os
import io
from datetime import datetime
from openpyxl import load_workbook
# Librería necesaria para el dictado (se debe añadir a requirements.txt)
from streamlit_mic_recorder import mic_recorder

st.set_page_config(page_title="ERP Logística Pro", layout="wide")

# --- CARGA DEL INVENTARIO ---
@st.cache_data
def cargar_inventario():
    fichero = '200_referencias_con_EAN.xlsx'
    if os.path.exists(fichero):
        df = pd.read_excel(fichero, engine='openpyxl')
        df.columns = df.columns.str.strip()
        return df
    return None

df_inv = cargar_inventario()

if 'carrito' not in st.session_state:
    st.session_state.carrito = []

def agregar_al_carrito(ean, ref, cant, origen, destino):
    for item in st.session_state.carrito:
        if item['EAN'] == ean:
            item['Unidades'] += cant
            st.toast(f"➕ Sumadas {cant} uds a {ref}")
            return
    st.session_state.carrito.append({
        'EAN': ean, 'Origen': origen, 'Destino': destino,
        'Referencia': ref, 'Unidades': cant
    })
    st.toast(f"✅ {ref} añadido")

st.title("📦 Sistema de Peticiones Inteligente")

# --- SECCIÓN 1: CABECERA ---
with st.container():
    fecha_peticion = st.date_input("📅 Fecha de Trabajo", datetime.now())
    col1, col2 = st.columns(2)
    with col1:
        ref_peticion = st.text_input("Ref. Petición", placeholder="Ej: REP-001")
        almacenes = ["ALM-CENTRAL", "ALM-NORTE", "ALM-SUR", "ALM-TIENDA"]
        origen = st.selectbox("Origen", almacenes)
    with col2:
        st.write("")
        st.write("")
        destino = st.selectbox("Destino", almacenes)

if origen == destino:
    st.error("⚠️ Origen y Destino no pueden ser iguales.")
    st.stop()

# --- SECCIÓN 2: OPERATIVA ---
tabs = st.tabs(["📊 Carga Masiva", "🔍 Añadir Manual / 🎤 Voz"])

with tabs[0]:
    archivo_repo = st.file_uploader("Subir Excel de Ventas", type=['xlsx'])
    if archivo_repo and st.button("🚀 Procesar Ventas", use_container_width=True):
        df_repo = pd.read_excel(archivo_repo)
        df_repo.columns = df_repo.columns.str.strip()
        for _, fila in df_repo.iterrows():
            match = df_inv[df_inv['EAN'].astype(str) == str(fila['EAN']).strip()]
            if not match.empty:
                agregar_al_carrito(match.iloc[0]['EAN'], match.iloc[0]['Referencia'], int(fila['Cantidad']), origen, destino)
        st.rerun()

with tabs[1]:
    st.write("Puedes escribir o usar el micrófono para buscar:")
    
    # COMPONENTE DE VOZ
    # El usuario pulsa, habla el nombre del producto, y el texto aparece
    voz = mic_recorder(start_prompt="🎤 Pulsa para hablar", stop_prompt="🛑 Detener", key='recorder')
    
    texto_voz = ""
    if voz:
        # Aquí se procesaría el audio si usaras una API de transcripción, 
        # pero para simplicidad móvil, la mayoría de teclados ya traen el micro.
        # Esta opción de mic_recorder es para grabar el audio. 
        st.info("Audio capturado. (Nota: Para dictado directo, usa el micro del teclado de tu móvil en el cuadro de abajo)")

    busqueda = st.text_input("🔍 Buscar producto...", placeholder="Di o escribe la referencia...")

    if busqueda:
        mask = df_inv.apply(lambda row: row.astype(str).str.contains(busqueda, case=False).any(), axis=1)
        res = df_inv[mask].head(5)
        for _, f in res.iterrows():
            c_inf, c_btn = st.columns([3, 1])
            c_inf.write(f"**{f['Referencia']}** - {f['Nombre']}")
            if c_btn.button("Añadir", key=f"b_{f['EAN']}", use_container_width=True):
                agregar_al_carrito(f['EAN'], f['Referencia'], 1, origen, destino)
                st.rerun()

# --- SECCIÓN 3: REVISIÓN ---
# (Mantenemos la lógica de totales y revisión que ya teníamos...)
if st.session_state.carrito:
    total_piezas = sum(item['Unidades'] for item in st.session_state.carrito)
    st.info(f"📊 **Total en pedido:** {len(st.session_state.carrito)} Refs | {total_piezas} Unidades")
    
    # ... (Resto del código de revisión y exportación igual que el anterior)
