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
        df = pd.read_excel(fichero, engine='openpyxl')
        df.columns = df.columns.str.strip()
        return df
    return None

df_inv = cargar_inventario()

if 'carrito' not in st.session_state:
    st.session_state.carrito = []

st.title("📦 Sistema de Pedidos Inteligente")

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
        # Filtro dinámico en todas las columnas
        mask = df_inv.apply(lambda row: row.astype(str).str.contains(busqueda, case=False).any(), axis=1)
        resultados = df_inv[mask].head(10)

        for _, fila in resultados.iterrows():
            with st.expander(f"➕ {fila['Referencia']} - {fila['Nombre']} ({fila['Talla']}/{fila['Color']})"):
                c1, c2 = st.columns([1, 1])
                with c1:
                    cant = st.number_input("Unidades", min_value=1, step=1, key=f"q_{fila['EAN']}")
                with c2:
                    if st.button("Añadir", key=f"b_{fila['EAN']}", use_container_width=True):
                        st.session_state.carrito.append({
                            'Almacén de Origen': origen,
                            'Almacén de Destino': destino,
                            'EAN': fila['EAN'],
                            'Unidades': cant
                        })
                        st.toast(f"EAN {fila['EAN']} añadido al carrito")
    else:
        st.info("Escribe en el buscador para filtrar las 200 referencias.")

    # --- GESTIÓN DE LA PLANTILLA Y DESCARGA ---
    if st.session_state.carrito:
        st.divider()
        st.subheader("📋 Resumen del Pedido")
        df_pedido = pd.DataFrame(st.session_state.carrito)
        st.dataframe(df_pedido, use_container_width=True)

        # Botón para procesar la plantilla
        if os.path.exists('plantilla.xlsx'):
            try:
                # Cargamos la plantilla
                wb = load_workbook('plantilla.xlsx')
                ws = wb.active # Usa la primera hoja disponible
                
                # Escribimos los datos (empezando en la fila 2)
                for i, row in enumerate(st.session_state.carrito):
                    ws.cell(row=i+2, column=1, value=row['Almacén de Origen'])
                    ws.cell(row=i+2, column=2, value=row['Almacén de Destino'])
                    ws.cell(row=i+2, column=3, value=row['EAN'])
                    ws.cell(row=i+2, column=4, value=row['Unidades'])

                output = io.BytesIO()
                wb.save(output)
                
                st.download_button(
                    label="📥 DESCARGAR EXCEL (PLANTILLA)",
                    data=output.getvalue(),
                    file_name=f"pedido_{origen}_{destino}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            except Exception as e:
                st.error(f"Error al procesar la plantilla: {e}")
        else:
            # Si no hay plantilla, descarga un Excel normal
            st.warning("No se detectó 'plantilla.xlsx'. Descargando Excel básico.")
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_pedido.to_excel(writer, index=False)
            st.download_button("📥 DESCARGAR EXCEL BÁSICO", data=output.getvalue(), file_name="pedido.xlsx")
else:
    st.error("No se encontró el archivo '200_referencias_con_EAN.xlsx' en GitHub.")
    
