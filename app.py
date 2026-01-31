import streamlit as st
import pandas as pd
import os
import io
from openpyxl import load_workbook

st.set_page_config(page_title="ERP Logística Pro", layout="wide")

# --- CARGA AUTOMÁTICA DEL INVENTARIO ---
@st.cache_data
def cargar_inventario():
    fichero = '200_referencias_con_EAN.xlsx'
    if os.path.exists(fichero):
        # Cargamos el Excel de referencias
        df = pd.read_excel(fichero, engine='openpyxl')
        df.columns = df.columns.str.strip()
        return df
    return None

df_inv = cargar_inventario()

if 'carrito' not in st.session_state:
    st.session_state.carrito = []

st.title("Peticiones entre almacenes Charo Ruiz")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("⚙️ Configuración")
    almacenes = ["ALM-CENTRAL", "ALM-NORTE", "ALM-SUR", "ALM-TIENDA"]
    origen = st.selectbox("Almacén Origen", almacenes)
    destino = st.selectbox("Almacén Destino", almacenes)
    
    st.divider()
    if st.button("🗑️ Vaciar Pedido Actual"):
        st.session_state.carrito = []
        st.rerun()

# --- BUSCADOR PREDICTIVO ---
if df_inv is not None:
    st.subheader("🔍 Buscador de Productos")
    busqueda = st.text_input("Escribe Ref, Nombre, Color...", placeholder="Ej: 100101").strip().lower()

    if busqueda:
        # Filtro dinámico que busca en todas las columnas
        mask = df_inv.apply(lambda row: row.astype(str).str.contains(busqueda, case=False).any(), axis=1)
        resultados = df_inv[mask].head(10)

        if not resultados.empty:
            for _, fila in resultados.iterrows():
                with st.expander(f"➕ {fila['Referencia']} - {fila['Nombre']} ({fila['Talla']}/{fila['Color']})"):
                    c1, c2 = st.columns([1, 1])
                    with c1:
                        cant = st.number_input("Unidades", min_value=1, step=1, key=f"q_{fila['EAN']}")
                    with c2:
                        if st.button("Añadir", key=f"b_{fila['EAN']}", use_container_width=True):
                            # Guardamos todos los datos necesarios para la plantilla
                            st.session_state.carrito.append({
                                'EAN': fila['EAN'],
                                'Almacén de Origen': origen,
                                'Almacén de Destino': destino,
                                'Referencia': fila['Referencia'],
                                'Unidades': cant
                            })
                            st.toast(f"Añadido: {fila['Referencia']}")
        else:
            st.warning("No se encontraron coincidencias.")
    else:
        st.info("Escribe en el buscador para filtrar los productos del inventario.")

    # --- GESTIÓN DE LA PLANTILLA Y DESCARGA ---
    if st.session_state.carrito:
        st.divider()
        st.subheader("📋 Resumen del Pedido")
        df_pedido = pd.DataFrame(st.session_state.carrito)
        st.dataframe(df_pedido, use_container_width=True)

        # Procesamiento de la plantilla Excel
        if os.path.exists('plantilla.xlsx'):
            try:
                wb = load_workbook('plantilla.xlsx')
                ws = wb.active 
                
                # REGLAS DE COLUMNAS SEGÚN TU SOLICITUD:
                # Col 1: EAN | Col 2: Origen | Col 3: Destino | Col 4: Ref | Col 5: Cantidad
                for i, row in enumerate(st.session_state.carrito):
                    fila_excel = i + 2 # Empezamos en la fila 2 (debajo de cabeceras)
                    ws.cell(row=fila_excel, column=1, value=row['EAN'])
                    ws.cell(row=fila_excel, column=2, value=row['Almacén de Origen'])
                    ws.cell(row=fila_excel, column=3, value=row['Almacén de Destino'])
                    ws.cell(row=fila_excel, column=4, value=row['Referencia'])
                    ws.cell(row=fila_excel, column=5, value=row['Unidades'])

                output = io.BytesIO()
                wb.save(output)
                
                st.download_button(
                    label="📥 DESCARGAR EXCEL PARA Gextia",
                    data=output.getvalue(),
                    file_name=f"pedido_{origen}_{destino}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            except Exception as e:
                st.error(f"Error al procesar la plantilla: {e}")
        else:
            st.error("⚠️ No se encontró 'plantilla.xlsx' en el repositorio.")
else:
    st.error("❌ No se encontró el archivo de inventario '200_referencias_con_EAN.xlsx'.")
    
