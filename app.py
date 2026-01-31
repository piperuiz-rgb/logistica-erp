import streamlit as st
import pandas as pd
import os
import io
from datetime import datetime
from openpyxl import load_workbook

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

# --- FUNCIÓN PARA VACIAR ---
def vaciar_pedido():
    st.session_state.carrito = []
    if "confirmar_vaciar" in st.session_state:
        del st.session_state.confirmar_vaciar

st.title("📦 Sistema de Peticiones Ágil")

# --- SECCIÓN 1: DATOS GENERALES (FECHA PRIMERO) ---
with st.container():
    # La fecha ocupa todo el ancho arriba para resaltar el día de trabajo
    fecha_peticion = st.date_input("📅 Fecha de la Petición", datetime.now())
    
    col1, col2 = st.columns(2)
    with col1:
        ref_peticion = st.text_input("Ref. Petición", placeholder="Ej: REP-001")
        almacenes = ["ALM-CENTRAL", "ALM-NORTE", "ALM-SUR", "ALM-TIENDA"]
        origen = st.selectbox("Origen", almacenes)
    with col2:
        # Espacio vacío para alinear visualmente si es necesario
        st.write("") 
        st.write("")
        destino = st.selectbox("Destino", almacenes)

# --- VALIDACIÓN DE ALMACENES ---
if origen == destino:
    st.error("⚠️ **Error:** Origen y Destino son iguales. Selecciona almacenes distintos para habilitar el sistema.")
    st.stop()

st.divider()

# --- SECCIÓN 2: CARGA Y BÚSQUEDA ---
tabs = st.tabs(["📊 Carga Masiva (Excel)", "🔍 Añadir Manual"])

with tabs[0]:
    archivo_repo = st.file_uploader("Subir Excel de Ventas (EAN, Cantidad)", type=['xlsx'])
    if archivo_repo and st.button("🚀 Procesar Reposición", use_container_width=True):
        df_repo = pd.read_excel(archivo_repo)
        df_repo.columns = df_repo.columns.str.strip()
        cont = 0
        for _, fila in df_repo.iterrows():
            ean_val = str(fila['EAN']).strip()
            match = df_inv[df_inv['EAN'].astype(str) == ean_val]
            if not match.empty:
                st.session_state.carrito.append({
                    'EAN': match.iloc[0]['EAN'], 'Origen': origen, 'Destino': destino,
                    'Referencia': match.iloc[0]['Referencia'], 'Unidades': int(fila['Cantidad'])
                })
                cont += 1
        st.success(f"Añadidos {cont} productos desde el archivo.")
        st.rerun()

with tabs[1]:
    busqueda = st.text_input("🔍 Buscar por Ref o Nombre", placeholder="Escribe aquí...")
    if busqueda:
        mask = df_inv.apply(lambda row: row.astype(str).str.contains(busqueda, case=False).any(), axis=1)
        res = df_inv[mask].head(5)
        for _, f in res.iterrows():
            c_inf, c_btn = st.columns([3, 1])
            c_inf.write(f"**{f['Referencia']}** - {f['Nombre']}")
            ya = any(i['EAN'] == f['EAN'] for i in st.session_state.carrito)
            if c_btn.button("Añadir" if not ya else "✅", key=f"b_{f['EAN']}", type="primary" if ya else "secondary"):
                if not ya:
                    st.session_state.carrito.append({
                        'EAN': f['EAN'], 'Origen': origen, 'Destino': destino,
                        'Referencia': f['Referencia'], 'Unidades': 1
                    })
                    st.rerun()

# --- SECCIÓN 3: REVISIÓN Y VACIADO ---
if st.session_state.carrito:
    st.divider()
    col_t, col_v = st.columns([3, 1])
    col_t.subheader("📋 Revisión Final")
    
    if col_v.button("🗑️ VACIAR", use_container_width=True):
        st.session_state.confirmar_vaciar = True

    if st.session_state.get("confirmar_vaciar"):
        st.warning("⚠️ ¿Borrar todo?")
        if st.button("SÍ, BORRAR", type="primary", use_container_width=True):
            vaciar_pedido()
            st.rerun()
        if st.button("NO, CANCELAR", use_container_width=True):
            st.session_state.confirmar_vaciar = False
            st.rerun()

    for i, item in enumerate(st.session_state.carrito):
        cols = st.columns([2, 1, 0.5])
        cols[0].write(f"**{item['Referencia']}**")
        nueva_cant = cols[1].number_input("Cant.", min_value=1, value=int(item['Unidades']), key=f"e_{i}")
        st.session_state.carrito[i]['Unidades'] = nueva_cant
        if cols[2].button("❌", key=f"d_{i}"):
            st.session_state.carrito.pop(i)
            st.rerun()

    # --- EXPORTACIÓN ---
    if os.path.exists('plantilla.xlsx'):
        try:
            wb = load_workbook('plantilla.xlsx')
            ws = wb.active 
            for idx, r in enumerate(st.session_state.carrito):
                ws.cell(row=idx+2, column=1, value=r['EAN'])
                ws.cell(row=idx+2, column=2, value=r['Origen'])
                ws.cell(row=idx+2, column=3, value=r['Destino'])
                ws.cell(row=idx+2, column=4, value=r['Referencia'])
                ws.cell(row=idx+2, column=5, value=r['Unidades'])
            out = io.BytesIO()
            wb.save(out)
            st.divider()
            st.download_button("📥 GENERAR EXCEL REPOSICIÓN", data=out.getvalue(), 
                               file_name=f"pedido_{ref_peticion}_{fecha_peticion}.xlsx", 
                               use_container_width=True, type="primary")
        except: st.error("Error al acceder a plantilla.xlsx")
