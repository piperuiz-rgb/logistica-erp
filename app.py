import streamlit as st
import pandas as pd
from io import StringIO

st.set_page_config(page_title="ERP Logística Móvil", layout="wide")

st.title("📦 Buscador en Vivo")

if 'carrito' not in st.session_state:
    st.session_state.carrito = []

# --- PANEL LATERAL ---
with st.sidebar:
    st.header("1. Cargar Datos")
    # Ahora aceptamos solo CSV para evitar el error de Python 3.13
    archivo = st.file_uploader("Sube tu catálogo (Formato CSV)", type=['csv'])
    st.info("💡 Consejo: Guarda tu Excel como 'CSV (delimitado por comas)'")
    
    st.divider()
    ref_ped = st.text_input("Ref. Pedido", "001")
    if st.button("🗑️ Vaciar"):
        st.session_state.carrito = []
        st.rerun()

# --- BUSCADOR ---
if archivo:
    # Leemos el CSV (delimitado por comas o puntos y comas)
    try:
        df = pd.read_csv(archivo, sep=None, engine='python')
        df.columns = df.columns.str.strip() # Limpiar espacios
        
        busqueda = st.text_input("🔍 Escribe Ref, Talla o Color:").lower().strip()

        if busqueda:
            # Filtra en todas las columnas
            mask = df.apply(lambda row: row.astype(str).str.contains(busqueda, case=False).any(), axis=1)
            res = df[mask].head(15)

            if not res.empty:
                for _, fila in res.iterrows():
                    with st.expander(f"➕ {fila['Referencia']} | {fila['Talla']} | {fila['Color']}"):
                        cant = st.number_input("Cantidad", min_value=0, step=1, key=f"q_{fila['EAN']}")
                        if st.button("Añadir", key=f"btn_{fila['EAN']}"):
                            if cant > 0:
                                st.session_state.carrito.append({
                                    'EAN': fila['EAN'], 'Ref': fila['Referencia'], 
                                    'Cant': cant, 'Pedido': ref_ped
                                })
                                st.toast("¡Añadido!")
            else:
                st.warning("No hay coincidencias.")

        # --- EXPORTAR ---
        if st.session_state.carrito:
            st.divider()
            df_res = pd.DataFrame(st.session_state.carrito)
            st.write("### Carrito:")
            st.dataframe(df_res, use_container_width=True)
            
            # Descarga en CSV (para que no falle nunca)
            csv_data = df_res.to_csv(index=False).encode('utf-8')
            st.download_button("📥 DESCARGAR PEDIDO (CSV)", data=csv_data, file_name=f"pedido_{ref_ped}.csv")

    except Exception as e:
        st.error(f"Error al leer el archivo: {e}")
else:
    st.warning("👈 Sube tu catálogo en formato CSV desde el menú lateral.")

  
