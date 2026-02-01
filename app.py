import streamlit as st
import pandas as pd
import os
import io
from datetime import datetime
from openpyxl import load_workbook

st.set_page_config(page_title="LogiFlow Pro", layout="wide")

# --- DISEÑO TIPO TABLA TÉCNICA (PC/MÓVIL) ---
st.markdown("""
    <style>
    .stApp { background-color: #ffffff !important; }
    
    /* Forzar contraste máximo */
    h1, h2, h3, p, span, label, .stMarkdown { color: #000000 !important; }

    /* Estructura de Celda de Tabla */
    .table-row {
        border: 1px solid #000000;
        margin-top: -1px; /* Solapa bordes para parecer una tabla única */
        padding: 10px;
        background-color: #ffffff;
        display: flex;
        align-items: center;
    }

    /* Botones cuadrados y sobrios */
    .stButton>button {
        width: 100%;
        border-radius: 0px;
        font-weight: 700 !important;
        height: 40px;
        text-transform: uppercase;
        font-size: 0.75rem !important;
    }

    /* Botón añadir (Blanco) */
    .stButton>button[kind="secondary"] {
        background-color: #ffffff !important;
        color: #000000 !important;
        border: 1px solid #000000 !important;
    }

    /* Botón añadido (Azul funcional) */
    .stButton>button[kind="primary"] {
        background-color: #0052FF !important;
        color: #ffffff !important;
        border: 1px solid #000000 !important;
    }

    /* Etiquetas de datos técnicos */
    .data-label {
        font-size: 0.75rem;
        color: #444;
        text-transform: uppercase;
        font-weight: bold;
        margin-right: 15px;
    }
    
    /* Ajuste para que los inputs no tengan sombras */
    .stTextInput>div>div>input { border: 1px solid #000 !important; border-radius: 0px !important; }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data
def get_catalogue():
    if not os.path.exists('catalogue.xlsx'): return None
    df = pd.read_excel('catalogue.xlsx', engine='openpyxl')
    df['EAN'] = df['EAN'].astype(str).str.replace('.0', '', regex=False).str.strip()
    return df, df.set_index('EAN').to_dict('index')

if 'carrito' not in st.session_state: st.session_state.carrito = {}

data_pack = get_catalogue()

st.title("📦 LOGIFLOW PRO")

if data_pack:
    df_cat, cat_dict = data_pack

    # 1. CABECERA
    with st.expander("DATOS DE LA OPERACIÓN", expanded=True):
        c1, c2, c3 = st.columns(3)
        fecha_str = c1.date_input("FECHA", datetime.now()).strftime('%Y-%m-%d')
        origen = c2.selectbox("ORIGEN", ["PET Almacén Badalona", "ALM-CENTRAL"])
        destino = c3.selectbox("DESTINO", ["PET T002 Marbella", "ALM-TIENDA"])
        obs = st.text_input("OBSERVACIONES")

    if origen == destino:
        st.error("Error: Origen y Destino coinciden.")
        st.stop()

    # 2. SECCIÓN DE BÚSQUEDA
    t1, t2 = st.tabs(["CARGA EXCEL", "BÚSQUEDA MANUAL"])

    with t1:
        archivo_v = st.file_uploader("Subir Excel", type=['xlsx'])
        if archivo_v and st.button("IMPORTAR DATOS", type="secondary"):
            df_v = pd.read_excel(archivo_v)
            for _, f_v in df_v.iterrows():
                ean = str(f_v['EAN']).replace('.0', '').strip()
                if ean in cat_dict:
                    prod = cat_dict[ean]
                    cant_v = int(f_v.get('Cantidad', 1))
                    if ean in st.session_state.carrito: st.session_state.carrito[ean]['Cantidad'] += cant_v
                    else: st.session_state.carrito[ean] = {'Ref': prod['Referencia'], 'Nom': prod.get('Nombre',''), 'Col': prod.get('Color','-'), 'Tal': prod.get('Talla','-'), 'Cantidad': cant_v}
            st.rerun()

    with t2:
        c_search, c_num = st.columns([3, 1])
        busq = c_search.text_input("Filtrar catálogo...", placeholder="Ref, Nombre, Color...")
        limite = c_num.selectbox("Ver", [25, 50, 100, "Todos"])
        
        if busq:
            mask = df_cat.apply(lambda row: busq.lower() in str(row.values).lower(), axis=1)
            res = df_cat[mask]
            if limite != "Todos": res = res.head(int(limite))
            
            # Encabezado "Simulado" de Tabla
            st.markdown("<div style='border: 1px solid #000; background: #eee; padding: 5px; font-weight: bold; font-size: 0.8rem;'>RESULTADOS DEL CATÁLOGO</div>", unsafe_allow_html=True)
            
            for _, f in res.iterrows():
                ean = f['EAN']
                en_car = ean in st.session_state.carrito
                
                # Fila tipo Celda de Tabla
                st.markdown('<div class="table-row">', unsafe_allow_html=True)
                c1, c2 = st.columns([4, 1.5])
                c1.markdown(f"""
                    <div style='font-weight: 800; font-size: 0.95rem;'>{f['Referencia']}</div>
                    <div style='font-size: 0.85rem; margin-bottom: 2px;'>{f.get('Nombre','')}</div>
                    <span class="data-label">COL: {f.get('Color','-')}</span>
                    <span class="data-label">TAL: {f.get('Talla','-')}</span>
                """, unsafe_allow_html=True)
                
                btn_label = f"LLEVAS {st.session_state.carrito[ean]['Cantidad']}" if en_car else "AÑADIR"
                if c2.button(btn_label, key=f"b_{ean}", type="primary" if en_car else "secondary"):
                    if en_car: st.session_state.carrito[ean]['Cantidad'] += 1
                    else: st.session_state.carrito[ean] = {'Ref': f['Referencia'], 'Nom': f.get('Nombre',''), 'Col': f.get('Color','-'), 'Tal': f.get('Talla','-'), 'Cantidad': 1}
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

    # 3. LISTA DE REVISIÓN
    if st.session_state.carrito:
        st.write("###")
        st.markdown(f"<div style='border: 2px solid #000; padding: 10px; font-weight: bold;'>REVISIÓN FINAL: {sum(it['Cantidad'] for it in st.session_state.carrito.values())} UNIDADES</div>", unsafe_allow_html=True)
        
        for ean, item in list(st.session_state.carrito.items()):
            # Usamos el mismo estilo de fila para coherencia
            st.markdown('<div class="table-row" style="border-width: 1px 2px;">', unsafe_allow_html=True)
            ca, cb, cc = st.columns([3, 1, 0.5])
            ca.markdown(f"**{item['Ref']}**<br><small>{item['Nom']} ({item['Col']}/{item['Tal']})</small>", unsafe_allow_html=True)
            item['Cantidad'] = cb.number_input("CANT", 1, 9999, item['Cantidad'], key=f"q_{ean}", label_visibility="collapsed")
            if cc.button("✕", key=f"d_{ean}"):
                del st.session_state.carrito[ean]
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        st.write("###")
        cv, cg = st.columns([1, 2])
        if cv.button("LIMPIAR TODO"):
            st.session_state.carrito = {}
            st.rerun()
            
        if os.path.exists('peticion.xlsx') and cg.button("GENERAR EXCEL GEXTIA", type="primary"):
            wb = load_workbook('peticion.xlsx')
            ws = wb.active
            for ean, it in st.session_state.carrito.items():
                ws.append([fecha_str, origen, destino, obs, ean, it['Cantidad']])
            out = io.BytesIO()
            wb.save(out)
            st.download_button("📥 DESCARGAR ARCHIVO", out.getvalue(), f"REPO_{destino}.xlsx", use_container_width=True)
else:
    st.error("Falta el archivo 'catalogue.xlsx'")
