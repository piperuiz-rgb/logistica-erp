import streamlit as st
import pandas as pd
import re
import os
from io import BytesIO

# 1. CONFIGURACIÓN DE PÁGINA (Debe ser lo primero siempre)
st.set_page_config(page_title="Gestor de Reposición RGB", layout="wide", page_icon="📦")

# Estilo CSS para mejorar la apariencia y evitar errores visuales
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; }
    .section-header { 
        background-color: #001529; color: white; padding: 10px; 
        border-radius: 5px; margin-bottom: 20px; text-align: center;
    }
    </style>
""", unsafe_allow_html=True)

# 2. CARGA DEL CATÁLOGO (CON AUTODETECCIÓN DE ARCHIVO)
@st.cache_data
def load_catalog():
    archivo = "catalogue.xlsx"
    if not os.path.exists(archivo):
        # Si falla, buscamos cualquier archivo excel en la carpeta
        archivos = [f for f in os.listdir('.') if f.endswith('.xlsx')]
        if archivos:
            archivo = archivos[0]
        else:
            st.error("⚠️ No se encuentra 'catalogue.xlsx' en GitHub.")
            st.stop()
            
    try:
        df = pd.read_excel(archivo, engine='openpyxl')
        # Limpiamos nombres de columnas (espacios e invisibles)
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except Exception as e:
        st.error(f"Error crítico al leer el catálogo: {e}")
        st.stop()

df_cat = load_catalog()

# 3. INICIALIZACIÓN DEL ESTADO (CARRITO)
if 'carrito' not in st.session_state:
    st.session_state.carrito = {}

# --- CABECERA ---
st.markdown('<div class="section-header"><h1>SISTEMA DE REPOSICIÓN INTELIGENTE</h1></div>', unsafe_allow_html=True)

col1, col2 = st.columns([1, 1.2])

# --- COLUMNA IZQUIERDA: IMPORTADOR Y BUSCADOR ---
with col1:
    st.subheader("📂 Carga de Ventas (Gextia)")
    archivo_v = st.file_uploader("Sube el Excel de ventas con columnas 'EAN' y 'Cantidad'", type=['xlsx'])
    
    if archivo_v:
        # Usamos type="primary" para evitar el error Axios/Danger
        if st.button("🚀 PROCESAR REPOSICIÓN", type="primary"):
            df_v = pd.read_excel(archivo_v)
            df_v.columns = [str(c).strip() for c in df_v.columns]
            
            if 'EAN' in df_v.columns and 'Cantidad' in df_v.columns:
                # Normalizamos catálogo para el cruce rápido
                df_cat['Ref_Busca'] = df_cat['Referencia'].astype(str).str.strip().str.upper()
                df_cat['Col_Busca'] = df_cat['Color'].astype(str).str.strip().str.upper()
                df_cat['Tal_Busca'] = df_cat['Talla'].astype(str).str.strip().str.upper()

                contador = 0
                for _, fila in df_v.iterrows():
                    texto_sucio = str(fila['EAN']) # Ej: [249200] Shirt (AZUL, XS)
                    cant_v = int(fila['Cantidad'])
                    
                    # Regex para extraer datos
                    m_ref = re.search(r'\[(.*?)\]', texto_sucio)
                    m_specs = re.search(r'\((.*?)\)', texto_sucio)
                    
                    if m_ref and m_specs:
                        ref_v = m_ref.group(1).strip().upper()
                        specs = m_specs.group(1).split(',')
                        
                        if len(specs) >= 2:
                            col_v = specs[0].strip().upper()
                            tal_v = specs[1].strip().upper()
                            
                            # BUSQUEDA EN CATÁLOGO
                            match = df_cat[
                                (df_cat['Ref_Busca'] == ref_v) & 
                                (df_cat['Col_Busca'] == col_v) & 
                                (df_cat['Tal_Busca'] == tal_v)
                            ]
                            
                            if not match.empty:
                                p = match.iloc[0]
                                ean_real = str(p['EAN'])
                                if ean_real in st.session_state.carrito:
                                    st.session_state.carrito[ean_real]['Cantidad'] += cant_v
                                else:
                                    st.session_state.carrito[ean_real] = {
                                        'Ref': p['Referencia'], 'Nom': p.get('Nombre','-'),
                                        'Col': p['Color'], 'Tal': p['Talla'], 'Cantidad': cant_v
                                    }
                                contador += 1
                st.success(f"✅ Se han procesado {contador} líneas correctamente.")
                st.rerun()
            else:
                st.error("El archivo no tiene las columnas 'EAN' y 'Cantidad'")

    st.divider()
    st.subheader("🔍 Buscador Manual")
    ean_manual = st.text_input("Escanear EAN o escribir Referencia")
    if ean_manual:
        res = df_cat[(df_cat['EAN'].astype(str) == ean_manual) | (df_cat['Referencia'].astype(str) == ean_manual)]
        if not res.empty:
            for _, r in res.iterrows():
                if st.button(f"Añadir {r['Referencia']} - {r['Color']} ({r['Talla']})"):
                    e = str(r['EAN'])
                    if e in st.session_state.carrito:
                        st.session_state.carrito[e]['Cantidad'] += 1
                    else:
                        st.session_state.carrito[e] = {'Ref': r['Referencia'], 'Nom': r.get('Nombre','-'), 'Col': r['Color'], 'Tal': r['Talla'], 'Cantidad': 1}
                    st.rerun()

# --- COLUMNA DERECHA: LISTA DE REPOSICIÓN ---
with col2:
    st.subheader("🛒 Lista de Reposición")
    if not st.session_state.carrito:
        st.info("No hay productos en la lista.")
    else:
        # Convertir carrito a DataFrame para visualizar
        data_lista = []
        for e, d in st.session_state.carrito.items():
            data_lista.append({"EAN": e, "Referencia": d['Ref'], "Color": d['Col'], "Talla": d['Tal'], "Cant": d['Cantidad']})
        
        df_lista = pd.DataFrame(data_lista)
        st.dataframe(df_lista, use_container_width=True, hide_index=True)

        # Acciones
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🗑️ Vaciar Todo", type="primary"):
                st.session_state.carrito = {}
                st.rerun()
        with c2:
            # Generar Excel para Gextia
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # Gextia suele necesitar EAN y Cantidad
                df_lista[["EAN", "Cant"]].to_excel(writer, index=False, sheet_name='Sheet1')
            
            st.download_button(
                label="📥 Bajar Excel Gextia",
                data=output.getvalue(),
                file_name="reposicion_gextia.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
