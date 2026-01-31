import streamlit as st
import pandas as pd
import os
import io
from datetime import datetime
from openpyxl import load_workbook

st.set_page_config(page_title="ERP Logística Pro", layout="wide")

# --- CARGA AUTOMÁTICA DEL INVENTARIO ---
@st.cache_data
def cargar_inventario():
    fichero = '200_referencias_con_EAN.xlsx'
    if os.path.exists(fichero):
        df = pd.read_excel(fichero, engine='openpyxl')
        df.columns = df.columns.str.strip()
        return df
    return None

df_inv = cargar_inventario()

# Inicializamos el carrito y el estado del buscador
if 'carrito' not in st.session_state:
    st.session_state.carrito = []
if 'busqueda_input' not in st.session_state:
    st.session_state.busqueda_input = ""

def limpiar_buscador():
    st.session_state.busqueda_input = ""

st.title("📦 Sistema de Peticiones Ágil")

# --- SECCIÓN 1: DATOS GENERALES ---
with st.container():
    col1, col2 = st.columns(2)
    with col1:
        ref_peticion = st.text_input("Ref. Petición", placeholder="Ej: PET-001")
        almacenes = ["ALM-CENTRAL", "ALM-NORTE", "ALM-SUR", "ALM-TIENDA"]
        origen = st.selectbox("Origen", almacenes)
    with col2:
        fecha_peticion = st.date_input("Fecha", datetime.now())
        destino = st.selectbox("Destino", almacenes)

st.divider()

# --- SECCIÓN 2: BUSCADOR RÁPIDO ---
if df_inv is not None:
    # Usamos st.session_state para poder limpiar el campo automáticamente
    busqueda = st.text_input("🔍 Buscar y Añadir", 
                             value=st.session_state.busqueda_input, 
                             key="buscador_principal",
                             placeholder="Escribe referencia o nombre...")

    if busqueda:
        mask = df_inv.apply(lambda row: row.astype(str).str.contains(busqueda, case=False).any(), axis=1)
        resultados = df_inv[mask].head(8)

        for _, fila in resultados.iterrows():
            col_info, col_btn = st.columns([4, 1])
            col_info.write(f"**{fila['Referencia']}** - {fila['Nombre']} ({fila['Talla']}/{fila['Color']})")
            
            # Al pulsar "Añadir", se guarda y se limpia el buscador
            if col_btn.button("Añadir", key=f"add_{fila['EAN']}", use_container_width=True):
                st.session_state.carrito.append({
                    'EAN': fila['EAN'],
                    'Origen': origen,
                    'Destino': destino,
                    'Referencia': fila['Referencia'],
                    'Unidades': 1 # Cantidad inicial por defecto
                })
                st.toast(f"✅ {fila['Referencia']} añadido")
                # Forzamos la limpieza para la siguiente búsqueda
                st.session_state.busqueda_input = ""
                st.rerun()

    # --- SECCIÓN 3: REVISIÓN DE CANTIDADES ---
    if st.session_state.carrito:
        st.divider()
        st.subheader("📋 Ajustar Cantidades Finales")
        
        for i, item in enumerate(st.session_state.carrito):
            cols = st.columns([2, 1, 0.5])
            cols[0].write(f"**{item['Referencia']}**")
            
            # Aquí es donde el usuario pone la cantidad real
            nueva_cant = cols[1].number_input("Cant.", min_value=1, value=int(item['Unidades']), key=f"edit_{i}")
            st.session_state.carrito[i]['Unidades'] = nueva_cant
            
            if cols[2].button("🗑️", key=f"del_{i}"):
                st.session_state.carrito.pop(i)
                st.rerun()

        # --- EXPORTACIÓN ---
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
                
                st.divider()
                st.download_button(
                    label="📥 CONFIRMAR Y GENERAR EXCEL",
                    data=output.getvalue(),
                    file_name=f"peticion_{ref_peticion}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"Error con la plantilla: {e}")
                
    with st.sidebar:
        if st.button("🚨 VACIAR LISTA"):
            st.session_state.carrito = []
            st.rerun()
else:
    st.error("❌ No se encontró el inventario.")
