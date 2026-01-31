import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Buscador Logístico", layout="wide")

st.title("📦 Sistema de Peticiones Inteligente")

if 'carrito' not in st.session_state:
    st.session_state.carrito = []

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("1. Cargar Catálogo")
    archivo = st.file_uploader("Sube tu Excel o CSV", type=['xlsx', 'csv'])
    st.divider()
    ref_ped = st.text_input("Referencia Pedido", "PED-001")
    origen = st.text_input("Almacén Origen", "ALM-01")
    destino = st.text_input("Almacén Destino", "ALM-02")
    
    if st.button("🗑️ Vaciar Carrito"):
        st.session_state.carrito = []
        st.rerun()

# --- LÓGICA DE BÚSQUEDA Y REJILLA ---
if archivo:
    # Cargar datos
    df = pd.read_excel(archivo) if archivo.name.endswith('xlsx') else pd.read_csv(archivo)
    
    # Buscador en vivo (Escribe y filtra)
    st.subheader("🔍 Buscador de variantes")
    busqueda = st.text_input("Escribe referencia, nombre, color o talla...", "").strip().lower()
    
    if busqueda:
        # Filtra en todas las columnas relevantes
        mask = (
            df['Referencia'].astype(str).str.lower().str.contains(busqueda) |
            df['Nombre'].astype(str).str.lower().str.contains(busqueda) |
            df['Talla'].astype(str).str.lower().str.contains(busqueda) |
            df['Color'].astype(str).str.lower().str.contains(busqueda)
        )
        resultados = df[mask].head(15) # Limitamos a 15 para velocidad en móvil
        
        if not resultados.empty:
            for _, fila in resultados.iterrows():
                with st.container():
                    col_info, col_cant, col_btn = st.columns([3, 1, 1])
                    with col_info:
                        st.write(f"**{fila['Referencia']}** | {fila['Nombre']}\n({fila['Talla']} - {fila['Color']})")
                    with col_cant:
                        c = st.number_input(f"Cant.", min_value=0, step=1, key=f"q_{fila['EAN']}")
                    with col_btn:
                        if st.button("Añadir", key=f"add_{fila['EAN']}"):
                            if c > 0:
                                st.session_state.carrito.append({
                                    'EAN': fila['EAN'], 'Origen': origen, 'Destino': destino,
                                    'Referencia_Pedido': ref_ped, 'Cantidad': c
                                })
                                st.toast(f"Añadido EAN {fila['EAN']}")
        else:
            st.warning("No hay coincidencias.")
    
    # --- RESUMEN Y EXPORTACIÓN ---
    if st.session_state.carrito:
        st.divider()
        st.subheader("📋 Resumen para Exportar")
        df_res = pd.DataFrame(st.session_state.carrito)
        st.dataframe(df_res, use_container_width=True)
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_res.to_excel(writer, index=False)
        
        st.download_button(
            label="📥 DESCARGAR EXCEL PARA ERP",
            data=output.getvalue(),
            file_name=f"{ref_ped}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
else:
    st.info("👈 Abre el menú lateral izquierdo para subir tu catálogo.")
  
