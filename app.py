import streamlit as st
import pandas as pd
import os
import io
from datetime import datetime
from openpyxl import load_workbook

st.set_page_config(page_title="ERP Logística Pro", layout="wide")

# --- CARGA DEL INVENTARIO MAESTRO ---
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

st.title("📦 Gestión de Peticiones y Reposición")

# --- SECCIÓN 1: DATOS GENERALES ---
with st.expander("📝 Datos del Movimiento", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        ref_peticion = st.text_input("Ref. Petición", placeholder="Ej: REP-SEMANA-42")
        almacenes = ["ALM-CENTRAL", "ALM-NORTE", "ALM-SUR", "ALM-TIENDA"]
        origen = st.selectbox("Origen", almacenes)
    with col2:
        fecha_peticion = st.date_input("Fecha", datetime.now())
        destino = st.selectbox("Destino", almacenes)

st.divider()

# --- SECCIÓN 2: CARGA MASIVA (REPOSICIÓN) ---
st.subheader("📊 Reposición Automática")
archivo_repo = st.file_uploader("Subir Excel de Ventas/Reposición (Columnas: EAN, Cantidad)", type=['xlsx'])

if archivo_repo is not None and st.button("Procesar Reposición"):
    df_repo = pd.read_excel(archivo_repo, engine='openpyxl')
    df_repo.columns = df_repo.columns.str.strip()
    
    # Cruzamos los datos del Excel subido con nuestro inventario maestro
    encontrados = 0
    for _, fila in df_repo.iterrows():
        ean_repo = str(fila['EAN']).strip()
        cant_repo = fila['Cantidad']
        
        # Buscar en el maestro
        match = df_inv[df_inv['EAN'].astype(str) == ean_repo]
        
        if not match.empty:
            info_prod = match.iloc[0]
            st.session_state.carrito.append({
                'EAN': info_prod['EAN'],
                'Origen': origen,
                'Destino': destino,
                'Referencia': info_prod['Referencia'],
                'Unidades': int(cant_repo)
            })
            encontrados += 1
    
    st.success(f"✅ Se han añadido {encontrados} productos desde el archivo de reposición.")
    st.rerun()

st.divider()

# --- SECCIÓN 3: BUSCADOR MANUAL ---
st.subheader("🔍 Añadir productos manualmente")
busqueda = st.text_input("Buscar...", placeholder="Escribe referencia o nombre...")

if busqueda:
    mask = df_inv.apply(lambda row: row.astype(str).str.contains(busqueda, case=False).any(), axis=1)
    resultados = df_inv[mask].head(5)

    for _, fila in resultados.iterrows():
        col_info, col_btn = st.columns([3, 1])
        col_info.write(f"**{fila['Referencia']}** - {fila['Nombre']}")
        
        ya_en_carrito = any(item['EAN'] == fila['EAN'] for item in st.session_state.carrito)
        
        if ya_en_carrito:
            col_btn.button("✅ En lista", key=f"btn_{fila['EAN']}", use_container_width=True, type="primary")
        else:
            if col_btn.button("Añadir", key=f"btn_{fila['EAN']}", use_container_width=True):
                st.session_state.carrito.append({
                    'EAN': fila['EAN'], 'Origen': origen, 'Destino': destino,
                    'Referencia': fila['Referencia'], 'Unidades': 1
                })
                st.rerun()

# --- SECCIÓN 4: REVISIÓN Y EXCEL FINAL ---
if st.session_state.carrito:
    st.divider()
    st.subheader("📋 Revisión de la Petición Final")
    
    for i, item in enumerate(st.session_state.carrito):
        cols = st.columns([2, 1, 0.5])
        cols[0].write(f"**{item['Referencia']}**")
        nueva_cant = cols[1].number_input("Cant.", min_value=1, value=int(item['Unidades']), key=f"edit_{i}")
        st.session_state.carrito[i]['Unidades'] = nueva_cant
        if cols[2].button("🗑️", key=f"del_{i}"):
            st.session_state.carrito.pop(i)
            st.rerun()

    if os.path.exists('plantilla.xlsx'):
        try:
            wb = load_workbook('plantilla.xlsx')
            ws = wb.active 
            for idx, row in enumerate(st.session_state.carrito):
                fila_excel = idx + 2
                ws.cell(row=fila_excel, column=1, value=row['EAN'])
                ws.cell(row=fila_excel, column=2, value=row['Origen'])
                ws.cell(row=fila_excel, column=3, value=row['Destino'])
                ws.cell(row=fila_excel, column=4, value=row['Referencia'])
                ws.cell(row=fila_excel, column=5, value=row['Unidades'])

            output = io.BytesIO()
            wb.save(output)
            st.download_button("📥 DESCARGAR PETICIÓN FINAL", data=output.getvalue(), 
                               file_name=f"peticion_{ref_peticion}.xlsx", use_container_width=True)
        except Exception as e:
            st.error(f"Error con la plantilla: {e}")

with st.sidebar:
    if st.button("🚨 VACIAR TODO"):
        st.session_state.carrito = []
        st.rerun()
