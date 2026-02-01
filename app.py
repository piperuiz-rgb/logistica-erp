import streamlit as st
import pandas as pd
import os
from io import BytesIO

# 1. CONFIGURACIÓN
st.set_page_config(page_title="RGB Logística", layout="wide")

# 2. CARGA DEL CATÁLOGO
@st.cache_data
def load_data():
    archivo = "catalogue.xlsx"
    if os.path.exists(archivo):
        df = pd.read_excel(archivo, engine='openpyxl')
        df.columns = [str(c).strip() for c in df.columns]
        # Forzamos EAN a texto para evitar errores de formato
        if 'EAN' in df.columns:
            df['EAN'] = df['EAN'].astype(str).str.replace('.0', '', regex=False).str.strip()
        return df
    else:
        st.error("⚠️ Archivo 'catalogue.xlsx' no encontrado en GitHub.")
        st.stop()

df_cat = load_data()

# 3. ESTADO DEL CARRITO
if 'carrito' not in st.session_state:
    st.session_state.carrito = {}

# --- INTERFAZ ---
st.title("📦 Gestión de Reposición RGB")

col1, col2 = st.columns([1, 1.2])

# --- COLUMNA IZQUIERDA: IMPORTADOR Y BUSCADOR ---
with col1:
    with st.expander("📂 IMPORTAR EXCEL DE VENTAS", expanded=True):
        archivo_v = st.file_uploader("Subir Excel (EAN y Cantidad)", type=['xlsx'])
        if archivo_v and st.button("PROCESAR ARCHIVO", type="primary"):
            df_v = pd.read_excel(archivo_v)
            df_v.columns = [str(c).strip() for c in df_v.columns]
            
            if 'EAN' in df_v.columns and 'Cantidad' in df_v.columns:
                df_v['EAN'] = df_v['EAN'].astype(str).str.replace('.0', '', regex=False).str.strip()
                exitos = 0
                for _, fila in df_v.iterrows():
                    ean_v = fila['EAN']
                    cant_v = int(fila['Cantidad'])
                    
                    match = df_cat[df_cat['EAN'] == ean_v]
                    if not match.empty:
                        p = match.iloc[0]
                        if ean_v in st.session_state.carrito:
                            st.session_state.carrito[ean_v]['Cantidad'] += cant_v
                        else:
                            st.session_state.carrito[ean_v] = {
                                'Ref': p['Referencia'], 'Col': p.get('Color','-'),
                                'Tal': p.get('Talla','-'), 'Cantidad': cant_v
                            }
                        exitos += 1
                st.success(f"✅ Añadidos {exitos} productos.")
                st.rerun()

    st.divider()
    
    st.subheader("🔍 Añadir Manualmente")
    busqueda = st.text_input("Buscar por Referencia o EAN")
    if busqueda:
        res = df_cat[(df_cat['EAN'] == busqueda) | (df_cat['Referencia'].astype(str).str.contains(busqueda, case=False))]
        if not res.empty:
            for _, r in res.iterrows():
                with st.container(border=True):
                    c_a, c_b, c_c = st.columns([2, 1, 1])
                    c_a.write(f"**{r['Referencia']}** - {r['Color']} ({r['Talla']})")
                    cant_sel = c_b.number_input("Cant.", min_value=1, value=1, key=f"n_{r['EAN']}")
                    if c_c.button("Añadir", key=f"btn_{r['EAN']}"):
                        cod = str(r['EAN'])
                        if cod in st.session_state.carrito:
                            st.session_state.carrito[cod]['Cantidad'] += cant_sel
                        else:
                            st.session_state.carrito[cod] = {
                                'Ref': r['Referencia'], 'Col': r['Color'], 
                                'Tal': r['Talla'], 'Cantidad': cant_sel
                            }
                        st.rerun()

# --- COLUMNA DERECHA: CARRITO EDITABLE ---
with col2:
    st.subheader("🛒 Lista de Reposición")
    if not st.session_state.carrito:
        st.info("Lista vacía.")
    else:
        # Generamos una tabla con botones para editar o eliminar
        for ean, datos in list(st.session_state.carrito.items()):
            with st.container(border=True):
                ca, cb, cc, cd = st.columns([2, 1, 1, 0.5])
                ca.write(f"**{datos['Ref']}**\n{datos['Col']} / {datos['Tal']}")
                
                # Modificar cantidad directamente
                nueva_cant = cb.number_input("Cant.", min_value=1, value=datos['Cantidad'], key=f"edit_{ean}")
                st.session_state.carrito[ean]['Cantidad'] = nueva_cant
                
                if cd.button("❌", key=f"del_{ean}"):
                    del st.session_state.carrito[ean]
                    st.rerun()

        st.divider()
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            if st.button("🗑️ VACIAR TODO", type="primary"):
                st.session_state.carrito = {}
                st.rerun()
        
        with col_btn2:
            # Exportación
            final_df = pd.DataFrame([
                {'EAN': k, 'Cantidad': v['Cantidad']} 
                for k, v in st.session_state.carrito.items()
            ])
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                final_df.to_excel(writer, index=False)
            
            st.download_button(
                label="📥 DESCARGAR EXCEL",
                data=output.getvalue(),
                file_name="reposicion_gextia.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
