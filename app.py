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

if 'carrito' not in st.session_state:
    st.session_state.carrito = []

st.title("📦 Sistema de Peticiones Inteligente")

# --- SECCIÓN 1: DATOS GENERALES ---
st.subheader("📝 Datos del Movimiento")
with st.container():
    col1, col2 = st.columns(2)
    with col1:
        ref_peticion = st.text_input("Referencia de Petición (Informativo)", placeholder="Ej: PET-2024-001")
        almacenes = ["ALM-CENTRAL", "ALM-NORTE", "ALM-SUR", "ALM-TIENDA"]
        origen = st.selectbox("Almacén Origen", almacenes)
    with col2:
        fecha_peticion = st.date_input("Fecha de Petición", datetime.now())
        destino = st.selectbox("Almacén Destino", almacenes)

st.divider()

# --- SECCIÓN 2: BUSCADOR PREDICTIVO ---
if df_inv is not None:
    st.subheader("🔍 Buscador de Productos")
    busqueda = st.text_input("Escribe Ref, Nombre, Color...", placeholder="Buscar productos...").strip().lower()

    if busqueda:
        mask = df_inv.apply(lambda row: row.astype(str).str.contains(busqueda, case=False).any(), axis=1)
        resultados = df_inv[mask].head(10)

        if not resultados.empty:
            for _, fila in resultados.iterrows():
                with st.expander(f"➕ {fila['Referencia']} - {fila['Nombre']} ({fila['Talla']}/{fila['Color']})"):
                    c1, col_btn = st.columns([1, 1])
                    with c1:
                        cant = st.number_input("Unidades", min_value=1, step=1, key=f"add_{fila['EAN']}")
                    with col_btn:
                        if st.button("Añadir", key=f"btn_{fila['EAN']}", use_container_width=True):
                            st.session_state.carrito.append({
                                'EAN': fila['EAN'],
                                'Origen': origen,
                                'Destino': destino,
                                'Referencia': fila['Referencia'],
                                'Unidades': cant
                            })
                            st.toast(f"Añadido: {fila['Referencia']}")
        else:
            st.warning("No hay coincidencias.")
    
    # --- SECCIÓN 3: REVISIÓN DEL PEDIDO (SIN EAN) ---
    if st.session_state.carrito:
        st.divider()
        st.subheader("📋 Revisión de Líneas")
        
        # Iteramos sobre el carrito para permitir edición
        for i, item in enumerate(st.session_state.carrito):
            cols = st.columns([2, 1.5, 0.5])
            
            # Solo Referencia (El EAN sigue guardado internamente para el Excel)
            cols[0].write(f"**{item['Referencia']}**")
            
            # Editor de cantidad
            nueva_cant = cols[1].number_input("Cant.", min_value=1, value=int(item['Unidades']), key=f"edit_{i}_{item['EAN']}", label_visibility="collapsed")
            st.session_state.carrito[i]['Unidades'] = nueva_cant
            
            # Botón eliminar
            if cols[2].button("🗑️", key=f"del_{i}"):
                st.session_state.carrito.pop(i)
                st.rerun()

        # --- GESTIÓN DE EXPORTACIÓN ---
        if os.path.exists('plantilla.xlsx'):
            try:
                wb = load_workbook('plantilla.xlsx')
                ws = wb.active 
                
                # Rellenamos la plantilla: 1:EAN, 2:Origen, 3:Destino, 4:Ref, 5:Cant
                for i, row in enumerate(st.session_state.carrito):
                    fila_excel = i + 2
                    ws.cell(row=fila_excel, column=1, value=row['EAN'])
                    ws.cell(row=fila_excel, column=2, value=row['Origen'])
                    ws.cell(row=fila_excel, column=3, value=row['Destino'])
                    ws.cell(row=fila_excel, column=4, value=row['Referencia'])
                    ws.cell(row=fila_excel, column=5, value=row['Unidades'])

                output = io.BytesIO()
                wb.save(output)
                
                nombre_archivo = f"peticion_{ref_peticion if ref_peticion else 'sin_ref'}.xlsx"
                
                st.divider()
                st.download_button(
                    label="📥 CONFIRMAR Y DESCARGAR EXCEL",
                    data=output.getvalue(),
                    file_name=nombre_archivo,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"Error con la plantilla: {e}")
                
    # Lateral
    with st.sidebar:
        if st.button("🚨 VACIAR TODO EL PEDIDO"):
            st.session_state.carrito = []
            st.rerun()
else:
    st.error("❌ No se encontró el archivo '200_referencias_con_EAN.xlsx'.")
