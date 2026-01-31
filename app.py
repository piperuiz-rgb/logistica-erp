import streamlit as st
import pandas as pd

st.set_page_config(page_title="ERP Logística", layout="wide")

st.title("🚀 Gestión de Pedidos Predictivo")

if 'carrito' not in st.session_state:
    st.session_state.carrito = []

# --- PANEL LATERAL ---
with st.sidebar:
    st.header("⚙️ Configuración")
    archivo = st.file_uploader("1. Sube el Catálogo (CSV)", type=['csv'])
    
    st.divider()
    st.subheader("2. Datos del Movimiento")
    
    # Los 4 almacenes solicitados
    lista_almacenes = ["ALM-CENTRAL", "ALM-NORTE", "ALM-SUR", "ALM-TIENDA"]
    origen = st.selectbox("Almacén de Origen", options=lista_almacenes)
    destino = st.selectbox("Almacén de Destino", options=lista_almacenes)
    
    st.divider()
    if st.button("🗑️ Vaciar Carrito"):
        st.session_state.carrito = []
        st.rerun()

# --- BUSCADOR PREDICTIVO ---
if archivo:
    try:
        # Cargamos el catálogo
        df = pd.read_csv(archivo, sep=None, engine='python')
        df.columns = df.columns.str.strip()
        
        # Creamos la etiqueta de búsqueda combinada
        df['etiqueta'] = (
            df['Referencia'].astype(str) + " - " + 
            df['Nombre'].astype(str) + " (" + 
            df['Talla'].astype(str) + " / " + 
            df['Color'].astype(str) + ")"
        )
        
        st.subheader("🔍 Buscar Variante")
        seleccion = st.selectbox(
            "Empieza a escribir la referencia (6 dígitos) o nombre...",
            options=[""] + sorted(df['etiqueta'].unique()),
            format_func=lambda x: "🔎 Buscar..." if x == "" else x
        )

        if seleccion:
            # Extraemos los datos del producto seleccionado
            item = df[df['etiqueta'] == seleccion].iloc[0]
            
            with st.container():
                st.info(f"📍 Seleccionado: {item['Nombre']} | EAN: {item['EAN']}")
                c1, c2 = st.columns(2)
                with c1:
                    unidades = st.number_input("Unidades", min_value=1, step=1, key="uds")
                with c2:
                    if st.button("➕ Añadir al Pedido", use_container_width=True):
                        st.session_state.carrito.append({
                            'Almacén de Origen': origen,
                            'Almacén de Destino': destino,
                            'EAN': item['EAN'],
                            'Unidades': unidades
                        })
                        st.toast(f"EAN {item['EAN']} añadido")

        # --- EXPORTACIÓN PARA ERP ---
        if st.session_state.carrito:
            st.divider()
            st.subheader("📋 Pedido para Importar")
            df_res = pd.DataFrame(st.session_state.carrito)
            
            # Mostramos el resumen
            st.dataframe(df_res, use_container_width=True)
            
            # Generamos el CSV de salida con las columnas exactas
            csv_final = df_res.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 DESCARGAR CSV PARA ERP",
                data=csv_final,
                file_name=f"pedido_{origen}_{destino}.csv",
                mime="text/csv"
            )

    except Exception as e:
        st.error(f"Error: El CSV debe tener las columnas EAN, Referencia, Nombre, Talla, Color. {e}")
else:
    st.info("👈 Por favor, carga el catálogo CSV en el menú lateral.")
