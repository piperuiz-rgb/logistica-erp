import streamlit as st
import pandas as pd
import os
import io
from datetime import datetime
from openpyxl import load_workbook

# Configuración estética
st.set_page_config(page_title="LogiFlow Pro | Final Check", layout="wide")

# --- ESTILOS CSS (Blanco, Negro y Grises) ---
st.markdown("""
    <style>
    .stApp { background-color: #fcfcfc; }
    h1, h2, h3 { color: #1a1a1a !important; font-family: 'Inter', sans-serif; font-weight: 700; }
    /* Tarjetas de Totales al final */
    div[data-testid="stMetric"] {
        background-color: #f8f9fa;
        border: 1px solid #000000;
        border-radius: 4px;
        padding: 15px;
    }
    .stButton>button[kind="primary"] {
        background-color: #000000 !important;
        color: #ffffff !important;
        border: none !important;
    }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data
def cargar_inventario():
    fichero = '200_referencias_con_EAN.xlsx'
    if os.path.exists(fichero):
        df = pd.read_excel(fichero, engine='openpyxl')
        df.columns = df.columns.str.strip()
        if 'EAN' in df.columns:
            df['EAN'] = df['EAN'].astype(str).str.strip()
        return df
    return None

df_inv = cargar_inventario()

if 'carrito' not in st.session_state:
    st.session_state.carrito = []

def agregar_al_carrito(ean, ref, cant, origen, destino):
    for item in st.session_state.carrito:
        if str(item['EAN']) == str(ean):
            item['Unidades'] += cant
            st.toast(f"➕ {ref}: {item['Unidades']} uds.")
            return
    st.session_state.carrito.append({'EAN': ean, 'Origen': origen, 'Destino': destino, 'Referencia': ref, 'Unidades': cant})
    st.toast(f"✅ {ref} añadido")

# --- INTERFAZ ---
st.title("📦 LOGIFLOW PRO")
st.write("---")

# 1. ENTRADA DE DATOS (Cabecera)
with st.container():
    fecha_peticion = st.date_input("FECHA", datetime.now())
    col_ref, col_o, col_d = st.columns([1.5, 1, 1])
    ref_peticion = col_ref.text_input("REF. PEDIDO", placeholder="EJ: 2024-X")
    almacenes = ["ALM-CENTRAL", "ALM-NORTE", "ALM-SUR", "ALM-TIENDA"]
    origen = col_o.selectbox("ORIGEN", almacenes)
    destino = col_d.selectbox("DESTINO", almacenes)

if origen == destino:
    st.error("⚠️ El Origen y Destino no pueden coincidir.")
    st.stop()

st.write("###")

# 2. OPERATIVA (Carga y Búsqueda)
t1, t2 = st.tabs(["📂 CARGA MASIVA", "⌨️ BÚSQUEDA MANUAL"])

with t1:
    archivo = st.file_uploader("Subir Excel de Ventas", type=['xlsx'])
    if archivo and st.button("PROCESAR EXCEL", use_container_width=True, type="primary"):
        df_repo = pd.read_excel(archivo)
        df_repo.columns = df_repo.columns.str.strip()
        for _, f in df_repo.iterrows():
            ean_buscado = str(f['EAN']).strip()
            match = df_inv[df_inv['EAN'] == ean_buscado]
            if not match.empty:
                agregar_al_carrito(match.iloc[0]['EAN'], match.iloc[0]['Referencia'], int(f['Cantidad']), origen, destino)
        st.rerun()

with t2:
    busqueda = st.text_input("Buscar referencia o nombre 🎤", placeholder="Escribir aquí...")
    if busqueda:
        res = df_inv[df_inv.apply(lambda row: row.astype(str).str.contains(busqueda, case=False).any(), axis=1)].head(6)
        for _, f in res.iterrows():
            col_t, col_b = st.columns([4, 1.5])
            col_t.markdown(f"**{f['Referencia']}** \n<small style='color: #666;'>{f['Nombre']}</small>", unsafe_allow_html=True)
            ya_esta = any(str(i['EAN']) == str(f['EAN']) for i in st.session_state.carrito)
            
            if col_b.button("Añadido (+1)" if ya_esta else "Añadir", key=f"add_{f['EAN']}", 
                            use_container_width=True, type="primary" if ya_esta else "secondary"):
                agregar_al_carrito(f['EAN'], f['Referencia'], 1, origen, destino)
                st.rerun()

# 3. REVISIÓN Y TOTALES (Sección de Cierre)
if st.session_state.carrito:
    st.write("---")
    st.subheader("📋 REVISIÓN Y CIERRE DE PEDIDO")
    
    # Listado de productos para ajustar cantidades
    for i, item in enumerate(st.session_state.carrito):
        col_p, col_c, col_x = st.columns([3, 2, 0.5])
        col_p.markdown(f"<div style='padding-top:10px;'><b>{item['Referencia']}</b></div>", unsafe_allow_html=True)
        nueva_cant = col_c.number_input("CANT", min_value=1, value=int(item['Unidades']), key=f"e_{i}_{item['EAN']}", label_visibility="collapsed")
        item['Unidades'] = nueva_cant
        if col_x.button("✕", key=f"d_{i}_{item['EAN']}"):
            st.session_state.carrito.pop(i)
            st.rerun()

    st.write("###")
    
    # PANEL DE TOTALES FINALES (Justo antes de descargar)
    with st.container():
        st.markdown("#### Resumen Final")
        c1, c2, c3 = st.columns(3)
        c1.metric("TOTAL PIEZAS", sum(item['Unidades'] for item in st.session_state.carrito))
        c2.metric("REFS. DISTINTAS", len(st.session_state.carrito))
        c3.metric("ENTREGA EN", destino)

    # ACCIONES FINALES
    if os.path.exists('plantilla.xlsx'):
        try:
            wb = load_workbook('plantilla.xlsx'); ws = wb.active 
            for idx, r in enumerate(st.session_state.carrito):
                ws.cell(row=idx+2, column=1, value=r['EAN'])
                ws.cell(row=idx+2, column=2, value=r['Origen'])
                ws.cell(row=idx+2, column=3, value=r['Destino'])
                ws.cell(row=idx+2, column=4, value=r['Referencia'])
                ws.cell(row=idx+2, column=5, value=r['Unidades'])
            out = io.BytesIO(); wb.save(out)
            
            st.write("###")
            c_v, c_d = st.columns([1, 2])
            if c_v.button("LIMPIAR TODO", use_container_width=True):
                st.session_state.carrito = []
                st.rerun()
            c_d.download_button("📥 CONFIRMAR Y DESCARGAR EXCEL", data=out.getvalue(), 
                               file_name=f"PEDIDO_{ref_peticion}.xlsx", use_container_width=True, type="primary")
        except: st.error("Error al generar el archivo. Verifica plantilla.xlsx")
