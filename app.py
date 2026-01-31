import streamlit as st
import pandas as pd

st.set_page_config(page_title="Buscador Predictivo", layout="wide")

st.markdown("""
    <style>
    .stTextInput > div > div > input { background-color: #f0f2f6; }
    </style>
    """, unsafe_allow_html=True)

st.title("🔍 Buscador Predictivo")

if 'carrito' not in st.session_state:
    st.session_state.carrito = []

# --- PANEL LATERAL ---
with st.sidebar:
    st.header("📦 Carga de Datos")
    archivo = st.file_uploader("Sube tu catálogo (CSV)", type=['csv'])
    st.divider()
    ref_ped = st.text_input("Referencia Pedido", "PED-001")
    if st.button("🗑️ Limpiar Carrito"):
        st.session_state.carrito = []
        st.rerun()

# --- LÓGICA DE BÚSQUEDA PREDICTIVA ---
if archivo:
    try:
        # Cargamos el CSV una sola vez
        df = pd.read_csv(archivo, sep=None, engine='python')
        
        # El buscador "mágico"
        query = st.text_input("Empieza a escribir (Ref, Color, Talla...)", placeholder="Ej: Camiseta Azul L").lower().strip()

        if query:
            # Esta línea hace la magia predictiva: busca en todas las columnas a la vez
            mask = df.apply(lambda row: row.astype(str).str.contains(query, case=False).any(), axis=1)
            resultados = df[mask].head(12) # Mostramos pocos para que vuele en el móvil

            if not resultados.empty:
                st.write(f"Resultados para '{query}':")
                for _, fila in resultados.iterrows():
                    # Cada resultado es un desplegable para ahorrar espacio
                    with st.expander(f"👕 {fila['Referencia']} - {fila['Color']} ({fila['Talla']})"):
                        c1, c2 = st.columns([1, 1])
                        with c1:
                            cant = st.number_input("Cantidad", min_value=0, key=f"n_{fila['EAN']}")
                        with c2:
                            if st.button("Añadir", key=f"b_{fila['EAN']}"):
                                if cant > 0:
                                    st.session_state.carrito.append({
                                        'EAN': fila['EAN'], 'Ref': fila['Referencia'], 
                                        'Cant': cant, 'Pedido': ref_ped
                                    })
                                    st.toast(f"Añadido: {fila['Referencia']}")
            else:
                st.info("No hay coincidencias exactas.")
        else:
            st.info("👋 Escribe algo arriba para empezar a filtrar el catálogo.")

        # --- RESUMEN DE COMPRA ---
        if st.session_state.carrito:
            st.divider()
            st.subheader("🛒 Pedido actual")
            df_car = pd.DataFrame(st.session_state.carrito)
            st.dataframe(df_car, use_container_width=True)
            
            csv_final = df_car.to_csv(index=False).encode('utf-8')
            st.download_button("📥 DESCARGAR PEDIDO CSV", data=csv_final, file_name=f"{ref_ped}.csv")

    except Exception as e:
        st.error("Error al leer el archivo. Asegúrate de que es un CSV válido.")
else:
    st.warning("👈 Por favor, sube el archivo CSV en el menú lateral.")
    
