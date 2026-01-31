import streamlit as st
import pandas as pd

st.set_page_config(page_title="ERP Logística", layout="wide")

st.title("🚀 Buscador Predictivo de Variantes")

if 'carrito' not in st.session_state:
    st.session_state.carrito = []

# --- PANEL LATERAL ---
with st.sidebar:
    st.header("⚙️ Configuración")
    archivo = st.file_uploader("1. Sube el Catálogo (CSV)", type=['csv'])
    
    st.divider()
    st.subheader("2. Datos del Movimiento")
    lista_almacenes = ["ALM-CENTRAL", "ALM-NORTE", "ALM-SUR", "ALM-TIENDA"]
    origen = st.selectbox("Almacén de Origen", options=lista_almacenes)
    destino = st.selectbox("Almacén de Destino", options=lista_almacenes)
    
    st.divider()
    if st.button("🗑️ Vaciar Carrito"):
        st.session_state.carrito = []
        st.rerun()

# --- BUSCADOR DINÁMICO REAL ---
if archivo:
    try:
        df = pd.read_csv(archivo, sep=None, engine='python')
        df.columns = df.columns.str.strip()
        
        # Caja de texto para búsqueda libre
        st.subheader("🔍 Buscar Variante")
        busqueda = st.text_input("Escribe referencia, talla o color...", placeholder="Ej: 100101 o Azul").strip().lower()

        if busqueda:
            # Filtramos el dataframe en tiempo real según lo que escribes
            mask = (
                df['Referencia'].astype(str).str.contains(busqueda, case=False) |
                df['Nombre'].astype(str).str.contains(busqueda, case=False) |
                df['Color'].astype(str).str.contains(busqueda, case=False) |
                df['Talla'].astype(str).str.contains(busqueda, case=False)
            )
            resultados = df[mask].head(10) # Limitamos a 10 para no colapsar el móvil

            if not resultados.empty:
                st.write("### Sugerencias encontradas:")
                for _, fila in resultados.iterrows():
                    # Formato de "Tarjeta" para cada resultado
                    with st.expander(f"📍 {fila['Referencia']} - {fila['Nombre']} ({fila['Talla']}/{fila['Color']})"):
                        st.write(f"**EAN:** {fila['EAN']}")
                        col_cant, col_btn = st.columns([1, 1])
                        with col_cant:
                            unidades = st.number_input("Unidades", min_value=1, step=1, key=f"u_{fila['EAN']}")
                        with col_btn:
                            if st.button("➕ Añadir", key=f"b_{fila['EAN']}", use_container_width=True):
                                st.session_state.carrito.append({
                                    'Almacén de Origen': origen,
                                    'Almacén de Destino': destino,
                                    'EAN': fila['EAN'],
                                    'Unidades': unidades
                                })
                                st.success(f"EAN {fila['EAN']} añadido")
            else:
                st.warning("No hay coincidencias.")
        else:
            st.info("Escribe algo arriba para ver opciones...")

        # --- EXPORTACIÓN ---
        if st.session_state.carrito:
            st.divider()
            st.subheader("📋 Resumen Pedido")
            df_res = pd.DataFrame(st.session_state.carrito)
            st.dataframe(df_res, use_container_width=True)
            
            csv_final = df_res.to_csv(index=False).encode('utf-8')
            st.download_button("📥 DESCARGAR CSV PARA ERP", data=csv_final, file_name=f"pedido_{origen}_{destino}.csv")

    except Exception as e:
        st.error(f"Error: Revisa que el CSV tenga EAN, Referencia, Nombre, Talla, Color. {e}")
else:
    st.info("👈 Sube el catálogo CSV en el menú lateral.")
