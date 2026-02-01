import streamlit as st
import pandas as pd
import os
import io
from datetime import datetime
from openpyxl import load_workbook

# Configuración profesional
st.set_page_config(page_title="LogiFlow Pro | Tallas & Colores", layout="wide", initial_sidebar_state="collapsed")

# --- ESTILOS CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #ffffff; }
    h1, h2, h3 { color: #000000 !important; font-family: 'Inter', sans-serif; }
    div[data-testid="stMetric"] { background-color: #fcfcfc; border: 1px solid #000000; border-radius: 2px; padding: 15px; }
    .stButton>button[kind="primary"] { background-color: #000000 !important; color: #ffffff !important; border-radius: 2px; }
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
        # Aseguramos que existan las columnas para evitar errores
        for col in ['EAN', 'Talla', 'Color']:
            if col not in df.columns: df[col] = "-"
        df['EAN'] = df['EAN'].astype(str).str.strip()
        return df
    return None

def agregar_al_carrito(item_data, cant, origen, destino):
    for item in st.session_state.carrito:
        if str(item['EAN']) == str(item_data['EAN']):
            item['Unidades'] += cant
            st.toast(f"Actualizado: {item_data['Referencia']}")
            return
    
    st.session_state.carrito.append({
        'EAN': item_data['EAN'], 'Origen': origen, 'Destino': destino, 
        'Referencia': item_data['Referencia'], 'Talla': item_data['Talla'],
        'Color': item_data['Color'], 'Unidades': cant
    })
    st.toast(f"Añadido: {item_data['Referencia']}")

if 'carrito' not in st.session_state:
    st.session_state.carrito = []

df_inv = cargar_inventario()

# --- INTERFAZ ---
st.title("📦 LOGIFLOW PRO")
st.caption(f"Control de Reposición por Talla y Color | {datetime.now().strftime('%d/%m/%Y')}")
st.write("---")

with st.container():
    fecha_peticion = st.date_input("FECHA", datetime.now())
    col_ref, col_o, col_d = st.columns([1.5, 1, 1])
    ref_peticion = col_ref.text_input("REF. PEDIDO ERP", placeholder="Ej: ORD-2024")
    almacenes = ["ALM-CENTRAL", "ALM-NORTE", "ALM-SUR", "ALM-TIENDA"]
    origen = col_o.selectbox("ORIGEN", almacenes)
    destino = col_d.selectbox("DESTINO", almacenes)

if origen == destino:
    st.error("❌ El origen y el destino no pueden coincidir.")
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
                agregar_al_carrito(match.iloc[0], int(fila['Cantidad']), origen, destino)
        st.rerun()

with t2:
    busqueda = st.text_input("Buscar Ref, Color o Talla 🎤", placeholder="Ej: Camiseta Azul XL...")
    if busqueda:
        res = df_inv[df_inv.apply(lambda row: row.astype(str).str.contains(busqueda, case=False).any(), axis=1)]
        if not res.empty:
            for _, f in res.iterrows():
                col_t, col_b = st.columns([4, 1.5])
                # Mostramos Talla y Color con etiquetas grises modernas
                col_t.markdown(f"""
                    **{f['Referencia']}** <span class='tag-style'>Color: {f['Color']}</span> <span class='tag-style'>Talla: {f['Talla']}</span>
                """, unsafe_allow_html=True)
                
                ya = any(str(i['EAN']) == str(f['EAN']) for i in st.session_state.carrito)
                if col_b.button("Añadido (+1)" if ya else "Añadir", key=f"add_{f['EAN']}", 
                                use_container_width=True, type="primary" if ya else "secondary"):
                    agregar_al_carrito(f, 1, origen, destino)
                    st.rerun()

if st.session_state.carrito:
    st.write("---")
    st.subheader("📋 REVISIÓN DE PRODUCTOS")
    
    for i, item in enumerate(st.session_state.carrito):
        col_p, col_c, col_x = st.columns([3, 1.5, 0.5])
        # Detalle visual en la revisión
        col_p.markdown(f"**{item['Referencia']}** \n<small>{item['Color']} / {item['Talla']}</small>", unsafe_allow_html=True)
        nueva_q = col_c.number_input("Cant.", min_value=1, value=int(item['Unidades']), key=f"q_{i}_{item['EAN']}", label_visibility="collapsed")
        item['Unidades'] = nueva_q
        if col_x.button("✕", key=f"d_{i}_{item['EAN']}"):
            st.session_state.carrito.pop(i)
            st.rerun()

    st.write("###")
    with st.container():
        c1, c2, c3 = st.columns(3)
        c1.metric("UDS TOTALES", sum(item['Unidades'] for item in st.session_state.carrito))
        c2.metric("REFS ÚNICAS", len(st.session_state.carrito))
        c3.metric("DESTINO", destino)

    if os.path.exists('plantilla.xlsx'):
        try:
            wb = load_workbook('plantilla.xlsx'); ws = wb.active 
            for idx, r in enumerate(st.session_state.carrito):
                ws.cell(row=idx+2, column=1, value=r['EAN'])
                ws.cell(row=idx+2, column=2, value=r['Origen'])
                ws.cell(row=idx+2, column=3, value=r['Destino'])
                ws.cell(row=idx+2, column=4, value=r['Referencia'])
                ws.cell(row=idx+2, column=5, value=r['Unidades'])
            
            output = io.BytesIO()
            wb.save(output)
            
            st.write("###")
            c_v, c_d = st.columns([1, 2])
            if c_v.button("LIMPIAR", use_container_width=True):
                st.session_state.carrito = []
                st.rerun()
            c_d.download_button("📥 DESCARGAR PARA ERP", data=output.getvalue(), 
                               file_name=f"IMPORT_{ref_peticion}.xlsx", use_container_width=True, type="primary")
        except Exception as e: st.error(f"Error: {e}")
