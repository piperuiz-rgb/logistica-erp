import streamlit as st
import pandas as pd
import os
import io
from datetime import datetime
from openpyxl import load_workbook

# Configuración de página
st.set_page_config(page_title="LogiFlow Pro | Gextia Sync", layout="wide", initial_sidebar_state="collapsed")

# --- ESTILOS CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #ffffff; }
    h1, h2, h3 { color: #000000 !important; font-family: 'Inter', sans-serif; }
    div[data-testid="stMetric"] { background-color: #fcfcfc; border: 1px solid #000000; border-radius: 0px; padding: 15px; }
    .stButton>button[kind="primary"] { background-color: #000000 !important; color: #ffffff !important; border-radius: 2px; border: none; }
    .stButton>button[kind="secondary"] { border-radius: 2px; }
    .tag-style { background-color: #f0f0f0; padding: 2px 8px; border-radius: 4px; font-size: 0.85em; color: #333; border: 1px solid #ddd; }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data
def cargar_inventario():
    fichero = '200_referencias_con_EAN.xlsx'
    if os.path.exists(fichero):
        df = pd.read_excel(fichero, engine='openpyxl')
        df.columns = df.columns.str.strip()
        for col in ['EAN', 'Talla', 'Color', 'Referencia']:
            if col not in df.columns: df[col] = "-"
        df['EAN'] = df['EAN'].astype(str).str.strip()
        return df
    return None

def agregar_al_carrito(item_data, cant, origen, destino, observaciones, fecha_str):
    for item in st.session_state.carrito:
        if str(item['EAN']) == str(item_data['EAN']):
            item['Cantidad'] += cant
            return
    
    st.session_state.carrito.append({
        'Fecha': fecha_str,
        'Almacén de origen': origen,
        'Almacén de destino': destino,
        'Observaciones': observaciones,
        'EAN': str(item_data['EAN']),
        'Cantidad': cant,
        'Referencia': item_data['Referencia'],
        'Talla': item_data['Talla'],
        'Color': item_data['Color']
    })
    st.toast(f"Añadido: {item_data['Referencia']}")

if 'carrito' not in st.session_state:
    st.session_state.carrito = []

df_inv = cargar_inventario()

# --- INTERFAZ ---
st.title("📦 LOGIFLOW PRO")
st.caption("Formato compatible con importador Odoo/Gextia")
st.write("---")

with st.container():
    fecha_peticion = st.date_input("FECHA", datetime.now())
    fecha_str = fecha_peticion.strftime('%Y-%m-%d')
    
    col_obs, col_o, col_d = st.columns([1.5, 1, 1])
    observaciones = col_obs.text_input("OBSERVACIONES", placeholder="Ej: Reposición semanal")
    
    # Almacenes sugeridos según tu Excel
    lista_almacenes = ["PET Almacén Badalona", "PET T002 Marbella", "ALM-CENTRAL", "ALM-NORTE"]
    origen = col_o.selectbox("ALMACÉN ORIGEN", lista_almacenes)
    destino = col_d.selectbox("ALMACÉN DESTINO", lista_almacenes)

if origen == destino:
    st.error("❌ El origen y destino no pueden ser iguales.")
    st.stop()

st.write("###")

t1, t2 = st.tabs(["📂 CARGA MASIVA", "🔍 BÚSQUEDA MANUAL"])

with t1:
    archivo = st.file_uploader("Subir Excel de Ventas", type=['xlsx'])
    if archivo and st.button("PROCESAR VENTAS", use_container_width=True, type="primary"):
        df_repo = pd.read_excel(archivo)
        df_repo.columns = df_repo.columns.str.strip()
        for _, fila in df_repo.iterrows():
            match = df_inv[df_inv['EAN'] == str(fila['EAN']).strip()]
            if not match.empty:
                agregar_al_carrito(match.iloc[0], int(fila['Cantidad']), origen, destino, observaciones, fecha_str)
        st.rerun()

with t2:
    busqueda = st.text_input("Buscar Ref, Color o Talla 🎤", placeholder="Ej: Camiseta Azul...")
    if busqueda:
        res = df_inv[df_inv.apply(lambda row: row.astype(str).str.contains(busqueda, case=False).any(), axis=1)]
        for _, f in res.iterrows():
            col_t, col_b = st.columns([4, 1.5])
            col_t.markdown(f"**{f['Referencia']}** <span class='tag-style'>{f['Color']}</span> <span class='tag-style'>{f['Talla']}</span>", unsafe_allow_html=True)
            ya = any(str(i['EAN']) == str(f['EAN']) for i in st.session_state.carrito)
            if col_b.button("Añadido (+1)" if ya else "Añadir", key=f"add_{f['EAN']}", use_container_width=True, type="primary" if ya else "secondary"):
                agregar_al_carrito(f, 1, origen, destino, observaciones, fecha_str)
                st.rerun()

# --- REVISIÓN Y EXPORTACIÓN ---
if st.session_state.carrito:
    st.write("---")
    st.subheader("📋 REVISIÓN FINAL")
    
    for i, item in enumerate(st.session_state.carrito):
        col_p, col_c, col_x = st.columns([3, 1.5, 0.5])
        col_p.markdown(f"**{item['Referencia']}** ({item['Color']} / {item['Talla']})")
        nueva_q = col_c.number_input("CANT", min_value=1, value=int(item['Cantidad']), key=f"q_{i}", label_visibility="collapsed")
        item['Cantidad'] = nueva_q
        if col_x.button("✕", key=f"d_{i}"):
            st.session_state.carrito.pop(i)
            st.rerun()

    st.write("###")
    with st.container():
        c1, c2, c3 = st.columns(3)
        c1.metric("TOTAL UDS", sum(item['Cantidad'] for item in st.session_state.carrito))
        c2.metric("REFS ÚNICAS", len(st.session_state.carrito))
        c3.metric("DESTINO", destino)

    # LÓGICA DE EXPORTACIÓN USANDO 'peticion.xlsx'
    if os.path.exists('peticion.xlsx'):
        try:
            wb = load_workbook('peticion.xlsx')
            ws = wb.active 
            # Limpiar filas previas si la plantilla no está vacía (opcional)
            # Para este caso, escribimos directamente sobre las celdas
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
            col_v, col_d = st.columns([1, 2])
            if col_v.button("LIMPIAR TODO"):
                st.session_state.carrito = []
                st.rerun()
                
            col_d.download_button(
                label="📥 DESCARGAR EXCEL PARA ERP",
                data=output.getvalue(),
                file_name=f"REPOSICION_{destino}_{fecha_str}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                type="primary"
            )
        except Exception as e:
            st.error(f"Error al procesar 'peticion.xlsx': {e}")
    else:
        st.error("⚠️ No se encontró el archivo 'peticion.xlsx' en el servidor.")
