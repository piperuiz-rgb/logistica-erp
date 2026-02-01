import streamlit as st
import pandas as pd
import os
from io import BytesIO

# 1. CONFIGURACIÓN
st.set_page_config(page_title="Reposición RGB", layout="wide")

# 2. CARGA DEL CATÁLOGO (Versión simplificada)
@st.cache_data
def load_data():
    archivo = "catalogue.xlsx"
    if os.path.exists(archivo):
        df = pd.read_excel(archivo, engine='openpyxl')
        # Limpieza de columnas: pasamos a string y quitamos espacios
        df.columns = [str(c).strip() for c in df.columns]
        # Aseguramos que el EAN sea tratado como texto para que el cruce sea exacto
        if 'EAN' in df.columns:
            df['EAN'] = df['EAN'].astype(str).str.strip()
        return df
    else:
        st.error(f"No se encuentra el archivo '{archivo}' en GitHub.")
        st.stop()

df_cat = load_data()

# 3. ESTADO DE LA APP
if 'carrito' not in st.session_state:
    st.session_state.carrito = {}

st.title("📦 Gestión de Reposición Directa")

col1, col2 = st.columns([1, 1.2])

with col1:
    st.subheader("📂 Importador de Ventas")
    archivo_v = st.file_uploader("Sube el Excel (Columnas: EAN, Cantidad)", type=['xlsx'])
    
    if archivo_v:
        if st.button("CARGAR EN LISTA", type="primary"):
            df_v = pd.read_excel(archivo_v)
            df_v.columns = [str(c).strip() for c in df_v.columns]
            
            if 'EAN' in df_v.columns and 'Cantidad' in df_v.columns:
                # Convertimos EAN de ventas a string para comparar
                df_v['EAN'] = df_v['EAN'].astype(str).str.strip()
                
                encontrados = 0
                no_encontrados = 0

                for _, fila in df_v.iterrows():
                    ean_venta = fila['EAN']
                    cant_venta = int(fila['Cantidad'])
                    
                    # BUSQUEDA DIRECTA POR EAN
                    match = df_cat[df_cat['EAN'] == ean_venta]
                    
                    if not match.empty:
                        prod = match.iloc[0]
                        if ean_venta in st.session_state.carrito:
                            st.session_state.carrito[ean_venta]['Cantidad'] += cant_venta
                        else:
                            st.session_state.carrito[ean_venta] = {
                                'Ref': prod.get('Referencia', 'S/R'),
                                'Nom': prod.get('Nombre', 'Producto'),
                                'Col': prod.get('Color', '-'),
                                'Tal': prod.get('Talla', '-'),
                                'Cantidad': cant_venta
                            }
                        encontrados += 1
                    else:
                        no_encontrados += 1
                
                st.success(f"✅ {encontrados} productos añadidos.")
                if no_encontrados > 0:
                    st.warning(f"⚠️ {no_encontrados} EANs no se encontraron en el catálogo.")
                st.rerun()
            else:
                st.error("El Excel debe tener columnas llamadas 'EAN' y 'Cantidad'")

    st.divider()
    st.subheader("🔍 Buscador Manual")
    busqueda = st.text_input("Escribe EAN o Referencia")
    if busqueda:
        # Busca por EAN o por Referencia
        res = df_cat[(df_cat['EAN'] == busqueda) | (df_cat['Referencia'].astype(str) == busqueda)]
        if not res.empty:
            for _, r in res.iterrows():
                if st.button(f"Añadir: {r['Referencia']} - {r['Color']} ({r['Talla']})"):
                    cod = str(r['EAN'])
                    if cod in st.session_state.carrito:
                        st.session_state.carrito[cod]['Cantidad'] += 1
                    else:
                        st.session_state.carrito[cod] = {
                            'Ref': r['Referencia'], 'Nom': r.get('Nombre','-'), 
                            'Col': r['Color'], 'Tal': r['Talla'], 'Cantidad': 1
                        }
                    st.success("Añadido")
                    st.rerun()

with col2:
    st.subheader("🛒 Lista de Reposición")
    if st.session_state.carrito:
        # Crear tabla para visualizar
        lista_final = []
        for k, v in st.session_state.carrito.items():
            lista_final.append({
                "EAN": k, "Referencia": v['Ref'], "Color": v['Col'], "Talla": v['Tal'], "Cantidad": v['Cantidad']
            })
        
        df_lista = pd.DataFrame(lista_final)
        st.dataframe(df_lista, use_container_width=True, hide_index=True)

        if st.button("🗑️ Vaciar Lista", type="primary"):
            st.session_state.carrito = {}
            st.rerun()

        # Botón para descargar lo acumulado
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_lista[["EAN", "Cantidad"]].to_excel(writer, index=False)
        
        st.download_button(
            label="📥 Descargar Excel para Gextia",
            data=output.getvalue(),
            file_name="reposicion_gextia.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
