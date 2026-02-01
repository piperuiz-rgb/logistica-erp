import streamlit as st
import pandas as pd
import os
import io
from datetime import datetime
from openpyxl import load_workbook

st.set_page_config(page_title="Peticiones", layout="wide")

# --- DISEÑO TÉCNICO FINAL (PC + MÓVIL) ---
st.markdown("""
    <style>
    html, body, .stApp, .main, .block-container, 
    div[data-testid="stExpander"], div[data-testid="stTab"], 
    div[data-testid="stHeader"], .stTabs, [data-testid="stVerticalBlock"] {
        background-color: #ffffff !important;
        color: #000000 !important;
    }
    .peticiones-title {
        font-size: 2.5rem; font-weight: 800; color: #000000;
        margin-top: 40px; margin-bottom: 20px;
        padding-bottom: 10px; border-bottom: 2px solid #000000; width: 100%;
    }
    .section-header {
        background: #000; color: #fff; padding: 8px; 
        font-weight: bold; margin-top: 20px; margin-bottom: 10px;
    }
    .table-row {
        border: 1px solid #000000; margin-top: -1px;
        background-color: #ffffff !important; display: flex; align-items: center; width: 100%;
    }
    .cell-content { padding: 8px 12px; display: flex; flex-direction: column; justify-content: center; }
    .stButton>button {
        width: 100% !important; border-radius: 0px !important; font-weight: 700 !important;
        height: 40px; text-transform: uppercase; border: 1px solid #000000 !important; font-size: 0.7rem !important;
    }
    .stButton>button[kind="secondary"] { background-color: #ffffff !important; color: #000000 !important; }
    .stButton>button[kind="primary"] { background-color: #0052FF !important; color: #ffffff !important; border: none !important; }
    .summary-box {
        border: 2px solid #000000; padding: 15px; margin-top: 20px;
        background-color: #ffffff !important; font-weight: bold;
        display: flex; justify-content: space-between; color: #000000 !important;
    }
    @media (max-width: 600px) {
        .peticiones-title { font-size: 1.8rem; margin-top: 20px; }
        .summary-box { flex-direction: column; gap: 5px; }
        .stButton>button { font-size: 0.75rem !important; height: 48px; }
    }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data
def get_catalogue():
    if not os.path.exists('catalogue.xlsx'): return None
    try:
        df = pd.read_excel('catalogue.xlsx', engine='openpyxl')
        df['EAN'] = df['EAN'].astype(str).str.replace('.0', '', regex=False).str.strip()
        return df
    except: return None

# --- ESTADO DE SESIÓN ---
if 'carrito' not in st.session_state: st.session_state.carrito = {}
if 'search_key' not in st.session_state: st.session_state.search_key = 0

df_cat = get_catalogue()
st.markdown('<div class="peticiones-title">Peticiones</div>', unsafe_allow_html=True)

if df_cat is not None:
    # 1. CABECERA LOGÍSTICA
    c1, c2, c3 = st.columns(3)
    fecha_str = c1.date_input("FECHA", datetime.now()).strftime('%Y-%m-%d')
    origen = c2.selectbox("ORIGEN", ["PET Almacén Badalona", "ALM-CENTRAL"])
    destino = c3.selectbox("DESTINO", ["PET T002 Marbella", "ALM-TIENDA"])
    ref_peticion = st.text_input("REFERENCIA PETICIÓN")

    st.write("---")

# --- INICIO DEL BLOQUE DE REPOSICIÓN ---
st.markdown("### 📂 Importación Masiva de Ventas")
archivo_v = st.file_uploader("Sube el informe de Gextia (Excel)", type=['xlsx'])

if archivo_v:
    # Mostramos el botón solo si hay archivo. Usamos type="primary" para evitar errores de red.
    if st.button("PROCESAR REPOSICIÓN ACTUAL", type="primary"):
        import re
        df_v = pd.read_excel(archivo_v)
        
        # Limpieza de nombres de columnas
        df_v.columns = [str(c).strip() for c in df_v.columns]
        
        if 'EAN' in df_v.columns and 'Cantidad' in df_v.columns:
            # Preparamos el catálogo para el cruce rápido
            df_cat['Ref_Busca'] = df_cat['Referencia'].astype(str).str.strip().str.upper()
            df_cat['Col_Busca'] = df_cat['Color'].astype(str).str.strip().str.upper()
            df_cat['Tal_Busca'] = df_cat['Talla'].astype(str).str.strip().str.upper()

            contador_ok = 0
            
            for _, fila in df_v.iterrows():
                # El "EAN" de tu excel realmente es: [249200] Shirt Ghisel (AZUL JAC, XS)
                texto_completo = str(fila['EAN'])
                cant_v = int(fila['Cantidad'])
                
                # Extraemos los datos con Regex
                res_ref = re.search(r'\[(.*?)\]', texto_completo)
                res_specs = re.search(r'\((.*?)\)', texto_completo)
                
                if res_ref and res_specs:
                    ref_extraida = res_ref.group(1).strip().upper()
                    # Separamos el contenido del paréntesis por la coma
                    partes = res_specs.group(1).split(',')
                    
                    if len(partes) >= 2:
                        color_extraido = partes[0].strip().upper()
                        talla_extraida = partes[1].strip().upper()
                        
                        # Buscamos la coincidencia exacta en el catálogo
                        match = df_cat[
                            (df_cat['Ref_Busca'] == ref_extraida) & 
                            (df_cat['Col_Busca'] == color_extraido) & 
                            (df_cat['Tal_Busca'] == talla_extraida)
                        ]
                        
                        if not match.empty:
                            producto = match.iloc[0]
                            ean_real = str(producto['EAN'])
                            
                            # Añadimos al carrito de la sesión
                            if ean_real in st.session_state.carrito:
                                st.session_state.carrito[ean_real]['Cantidad'] += cant_v
                            else:
                                st.session_state.carrito[ean_real] = {
                                    'Ref': producto['Referencia'],
                                    'Nom': producto.get('Nombre', 'Producto'),
                                    'Col': producto['Color'],
                                    'Tal': producto['Talla'],
                                    'Cantidad': cant_v
                                }
                            contador_ok += 1
                        else:
                            st.warning(f"No encontrado en catálogo: {ref_extraida} | {color_extraido} | {talla_extraida}")
            
            st.success(f"✅ ¡Proceso completado! Se han cargado {contador_ok} líneas correctamente.")
            st.rerun()
        else:
            st.error("El Excel debe tener las columnas 'EAN' y 'Cantidad'")
# --- FIN DEL BLOQUE DE REPOSICIÓN ---

    # 3. BUSCADOR Y FILTROS
    st.markdown('<div class="section-header">🔍 BUSCADOR MANUAL</div>', unsafe_allow_html=True)
    f1, f2 = st.columns([2, 1])
    busq_txt = f1.text_input("Buscar referencia, nombre o EAN...", key=f"busq_{st.session_state.search_key}")
    limite = f2.selectbox("Ver resultados:", [10, 25, 50, 100, 500], index=1, key=f"lim_{st.session_state.search_key}")

    filtros_activos = {}
    columnas_posibles = ["Colección", "Categoría", "Familia"]
    columnas_reales = [c for c in columnas_posibles if c in df_cat.columns]
    
    if columnas_reales:
        cols_f = st.columns(len(columnas_reales))
        for i, col in enumerate(columnas_reales):
            opciones = ["TODOS"] + sorted(df_cat[col].dropna().unique().tolist())
            filtros_activos[col] = cols_f[i].selectbox(f"{col}", opciones, key=f"f_{col}_{st.session_state.search_key}")

    df_res = df_cat.copy()
    if busq_txt:
        df_res = df_res[df_res.apply(lambda row: busq_txt.lower() in str(row.values).lower(), axis=1)]
    for col, val in filtros_activos.items():
        if val != "TODOS":
            df_res = df_res[df_res[col] == val]

    if busq_txt or any(v != "TODOS" for v in filtros_activos.values()):
        st.markdown(f"<div style='background: #000; color: #fff; padding: 4px; font-size: 0.7rem; text-align: center;'>{len(df_res)} COINCIDENCIAS</div>", unsafe_allow_html=True)
        for _, f in df_res.head(limite).iterrows():
            ean = f['EAN']
            en_car = ean in st.session_state.carrito
            st.markdown('<div class="table-row">', unsafe_allow_html=True)
            c1, c2 = st.columns([3, 1.5]) 
            with c1:
                st.markdown(f"<div class='cell-content'><strong>{f['Referencia']}</strong><br><small>{f.get('Nombre','')} ({f.get('Color','-')} / {f.get('Talla','-')})</small></div>", unsafe_allow_html=True)
            with c2:
                label = f"OK ({st.session_state.carrito[ean]['Cantidad']})" if en_car else "AÑADIR"
                if st.button(label, key=f"b_{ean}", type="primary" if en_car else "secondary"):
                    if en_car: st.session_state.carrito[ean]['Cantidad'] += 1
                    else: st.session_state.carrito[ean] = {'Ref': f['Referencia'], 'Nom': f.get('Nombre',''), 'Col': f.get('Color','-'), 'Tal': f.get('Talla','-'), 'Cantidad': 1}
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    # 4. LISTA FINAL Y GENERACIÓN
    if st.session_state.carrito:
        st.write("---")
        st.markdown('<div class="section-header">📋 LISTA DE REPOSICIÓN</div>', unsafe_allow_html=True)
        for ean, item in list(st.session_state.carrito.items()):
            st.markdown('<div class="table-row">', unsafe_allow_html=True)
            ca, cb, cc = st.columns([2.5, 1.2, 0.8])
            with ca: st.markdown(f"<div class='cell-content'><strong>{item['Ref']}</strong><br><small>{item['Nom']}</small></div>", unsafe_allow_html=True)
            with cb: item['Cantidad'] = st.number_input("C", 1, 9999, item['Cantidad'], key=f"q_{ean}", label_visibility="collapsed")
            with cc:
                if st.button("✕", key=f"d_{ean}"): del st.session_state.carrito[ean]; st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        uds = sum(it['Cantidad'] for it in st.session_state.carrito.values())
        st.markdown(f'<div class="summary-box"><div>PIEZAS: {uds}</div><div>MODELOS: {len(st.session_state.carrito)}</div><div>DESTINO: {destino}</div></div>', unsafe_allow_html=True)

        cv, cg = st.columns([1, 2])
        if cv.button("LIMPIAR TODO"):
            st.session_state.carrito = {}
            st.session_state.search_key += 1
            st.rerun()
            
        if os.path.exists('peticion.xlsx') and cg.button("GENERAR Y DESCARGAR EXCEL", type="primary"):
            wb = load_workbook('peticion.xlsx')
            ws = wb.active
            for ean, it in st.session_state.carrito.items():
                ws.append([fecha_str, origen, destino, ref_peticion, ean, it['Cantidad']])
            out = io.BytesIO(); wb.save(out)
            st.download_button("📥 GUARDAR ARCHIVO REPO", out.getvalue(), f"REPO_{destino}.xlsx", use_container_width=True)
else:
    st.error("Error: Asegúrate de tener el archivo 'catalogue.xlsx' en la carpeta.")
    
