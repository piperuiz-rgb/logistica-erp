import streamlit as st
import pandas as pd
import os
import io
from datetime import datetime
from openpyxl import load_workbook

# Configuración con estética limpia
st.set_page_config(page_title="LogiFlow Pro | Dark & White", layout="wide")

# --- ESTILOS CSS PERSONALIZADOS (Blanco, Negro y Grises) ---
st.markdown("""
    <style>
    /* Fondo general */
    .stApp { background-color: #fcfcfc; }
    
    /* Títulos y fuentes */
    h1, h2, h3 { color: #1a1a1a !important; font-family: 'Inter', sans-serif; font-weight: 700; }
    
    /* Tarjetas de Métricas */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 4px;
        padding: 20px;
    }

    /* Botón Principal (Negro) */
    .stButton>button[kind="primary"] {
        background-color: #000000 !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 4px;
        height: 3em;
    }

    /* Botones Secundarios (Grises) */
    .stButton>button {
        background-color: #ffffff;
        color: #333333;
        border: 1px solid #d0d0d0;
        border-radius: 4px;
    }

    /* Contenedores de productos */
    .product-card {
        background-color: #ffffff;
        padding: 15px;
        border-bottom: 1px solid #eeeeee;
        margin-bottom: 5px;
    }
    </style>
    """, unsafe_allow_html=True)

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
            return
    st.session_state.carrito.append({'EAN': ean, 'Origen': origen, 'Destino': destino, 'Referencia': ref, 'Unidades': cant})

# --- INTERFAZ ---
st.title("📦 LOGIFLOW PRO")
st.write("---")

# Resumen rápido en escala de grises
if st.session_state.carrito:
    c1, c2, c3 = st.columns(3)
    c1.metric("UNIDADES", sum(item['Unidades'] for item in st.session_state.carrito))
    c2.metric("REFS", len(st.session_state.carrito))
    c3.metric("DESTINO", st.session_state.carrito[0]['Destino'])

# --- ENTRADA DE DATOS ---
with st.container():
    col_date, col_ref = st.columns([1, 1])
    fecha_peticion = col_date.date_input("FECHA", datetime.now())
    ref_peticion = col_ref.text_input("REF. PEDIDO", placeholder="EJ: 2024-X")
    
    col_o, col_d = st.columns(2)
    almacenes = ["ALM-CENTRAL", "ALM-NORTE", "ALM-SUR", "ALM-TIENDA"]
    origen = col_o.selectbox("ORIGEN", almacenes)
    destino = col_d.selectbox("DESTINO", almacenes)

if origen == destino:
    st.warning("⚠️ Selecciona almacenes distintos.")
    st.stop()

st.write("###")

# --- PESTAÑAS TÉCNICAS ---
t1, t2 = st.tabs(["📂 CARGA MASIVA", "⌨️ BÚSQUEDA MANUAL"])

with t1:
    archivo = st.file_uploader("Subir Excel de Ventas", type=['xlsx'], help="Debe contener columnas 'EAN' y 'Cantidad'")
    if archivo and st.button("PROCESAR EXCEL", use_container_width=True, kind="primary"):
        df_repo = pd.read_excel(archivo)
        df_repo.columns = df_repo.columns.str.strip()
        for _, f in df_repo.iterrows():
            match = df_inv[df_inv['EAN'].astype(str) == str(f['EAN']).strip()]
            if not match.empty:
                agregar_al_carrito(match.iloc[0]['EAN'], match.iloc[0]['Referencia'], int(f['Cantidad']), origen, destino)
        st.success("Cargado.")
        st.rerun()

with t2:
    busqueda = st.text_input("Buscar referencia (o usa micrófono teclado 🎤)", placeholder="Ej: 101...")
    if busqueda:
        res = df_inv[df_inv.apply(lambda row: row.astype(str).str.contains(busqueda, case=False).any(), axis=1)].head(6)
        for _, f in res.iterrows():
            col_t, col_b = st.columns([4, 1])
            col_t.markdown(f"**{f['Referencia']}** \n<small style='color: #666;'>{f['Nombre']}</small>", unsafe_allow_html=True)
            if col_b.button("AÑADIR", key=f"add_{f['EAN']}", use_container_width=True):
                agregar_al_carrito(f['EAN'], f['Referencia'], 1, origen, destino)
                st.rerun()

# --- REVISIÓN FINAL ---
if st.session_state.carrito:
    st.write("---")
    st.write("### REVISIÓN DE PEDIDO")
    
    for i, item in enumerate(st.session_state.carrito):
        col_p, col_c, col_x = st.columns([3, 2, 0.5])
        col_p.markdown(f"<div style='padding-top:10px;'><b>{item['Referencia']}</b></div>", unsafe_allow_html=True)
        nueva_cant = col_c.number_input("CANT", min_value=1, value=int(item['Unidades']), key=f"e_{item['EAN']}", label_visibility="collapsed")
        item['Unidades'] = nueva_cant
        if col_x.button("✕", key=f"d_{item['EAN']}"):
            st.session_state.carrito.pop(i)
            st.rerun()

    # --- BOTONES DE ACCIÓN ---
    st.write("###")
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
            
            c_v, c_d = st.columns([1, 2])
            if c_v.button("BORRAR TODO", use_container_width=True):
                st.session_state.carrito = []
                st.rerun()
            c_d.download_button("DESCARGAR EXCEL FINAL", data=out.getvalue(), 
                               file_name=f"PEDIDO_{ref_peticion}.xlsx", use_container_width=True, kind="primary")
        except: st.error("Error con plantilla.xlsx")
