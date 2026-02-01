import streamlit as st
import pandas as pd
import os
import io
from datetime import datetime
from openpyxl import load_workbook

# Configuración de la aplicación
st.set_page_config(page_title="LogiFlow Pro | ERP Sync", layout="wide", initial_sidebar_state="collapsed")

# --- ESTILOS CSS (Estética Industrial Blanco/Negro/Gris) ---
st.markdown("""
    <style>
    /* Fondo y tipografía */
    .stApp { background-color: #ffffff; }
    h1, h2, h3 { color: #000000 !important; font-family: 'Inter', sans-serif; letter-spacing: -0.5px; }
    
    /* Métricas de control al final */
    div[data-testid="stMetric"] {
        background-color: #fcfcfc;
        border: 1px solid #000000;
        border-radius: 0px;
        padding: 15px;
    }

    /* Personalización de botones */
    .stButton>button[kind="primary"] {
        background-color: #000000 !important;
        color: #ffffff !important;
        border-radius: 2px;
        border: none;
        font-weight: 600;
    }
    .stButton>button[kind="secondary"] {
        border-radius: 2px;
        border: 1px solid #d0d0d0;
    }
    
    /* Inputs y Selectores */
    .stTextInput>div>div>input, .stSelectbox>div>div>div {
        border-radius: 2px !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- LÓGICA DE DATOS ---
@st.cache_data
def cargar_inventario():
    fichero = '200_referencias_con_EAN.xlsx'
    if os.path.exists(fichero):
        df = pd.read_excel(fichero, engine='openpyxl')
        df.columns = df.columns.str.strip()
        if 'EAN' in df.columns:
            df['EAN'] = df['EAN'].astype(str).str.strip()
        return df
    return None

def agregar_al_carrito(ean, ref, cant, origen, destino):
    # Agrupación automática: si ya existe, suma la cantidad
    for item in st.session_state.carrito:
        if str(item['EAN']) == str(ean):
            item['Unidades'] += cant
            st.toast(f"Actualizado: {ref} ({item['Unidades']} uds)")
            return
    
    # Si es nuevo, lo añade
    st.session_state.carrito.append({
        'EAN': ean, 
        'Origen': origen, 
        'Destino': destino, 
        'Referencia': ref, 
        'Unidades': cant
    })
    st.toast(f"Añadido: {ref}")

# --- INICIALIZACIÓN DE ESTADO ---
if 'carrito' not in st.session_state:
    st.session_state.carrito = []

df_inv = cargar_inventario()

# --- INTERFAZ DE USUARIO ---
st.title("📦 LOGIFLOW PRO")
st.caption(f"Terminal de Reposición | {datetime.now().strftime('%d/%m/%Y')}")
st.write("---")

# 1. CABECERA: DATOS DEL MOVIMIENTO
with st.container():
    fecha_peticion = st.date_input("FECHA DE EMISIÓN", datetime.now())
    
    col_ref, col_o, col_d = st.columns([1.5, 1, 1])
    ref_peticion = col_ref.text_input("REFERENCIA PEDIDO ERP", placeholder="Ej: ORD-2024-001")
    
    almacenes = ["ALM-CENTRAL", "ALM-NORTE", "ALM-SUR", "ALM-TIENDA"]
    origen = col_o.selectbox("ALMACÉN ORIGEN", almacenes)
    destino = col_d.selectbox("ALMACÉN DESTINO", almacenes)

# Validación de seguridad
if origen == destino:
    st.error("❌ El origen y el destino no pueden ser el mismo almacén.")
    st.stop()

st.write("###")

# 2. OPERATIVA: CARGA Y BÚSQUEDA
tab_excel, tab_manual = st.tabs(["📊 CARGA MASIVA (VENTAS)", "🔍 SELECCIÓN MANUAL"])

with tab_excel:
    st.write("Importa los datos de ventas para generar la reposición automática.")
    archivo = st.file_uploader("Arrastra aquí tu archivo Excel", type=['xlsx'])
    if archivo and st.button("PROCESAR Y AÑADIR A LISTA", use_container_width=True, type="primary"):
        df_repo = pd.read_excel(archivo)
        df_repo.columns = df_repo.columns.str.strip()
        count = 0
        for _, fila in df_repo.iterrows():
            ean_buscado = str(fila['EAN']).strip()
            match = df_inv[df_inv['EAN'] == ean_buscado]
            if not match.empty:
                agregar_al_carrito(match.iloc[0]['EAN'], match.iloc[0]['Referencia'], int(fila['Cantidad']), origen, destino)
                count += 1
        st.success(f"Se han procesado {count} referencias correctamente.")
        st.rerun()

with tab_manual:
    busqueda = st.text_input("Buscador de Referencias 🎤", placeholder="Escribe referencia o nombre del producto...")
    if busqueda:
        # Búsqueda completa sin límites
        resultados = df_inv[df_inv.apply(lambda row: row.astype(str).str.contains(busqueda, case=False).any(), axis=1)]
        
        if not resultados.empty:
            st.caption(f"Mostrando {len(resultados)} coincidencias")
            for _, fila in resultados.iterrows():
                c_info, c_btn = st.columns([4, 1.5])
                c_info.markdown(f"**{fila['Referencia']}** \n<small style='color: #666;'>EAN: {fila['EAN']}</small>", unsafe_allow_html=True)
                
                # Estado del botón
                ya_esta = any(str(i['EAN']) == str(fila['EAN']) for i in st.session_state.carrito)
                btn_label = "Añadido (+1)" if ya_esta else "Añadir"
                btn_type = "primary" if ya_esta else "secondary"
                
                if c_btn.button(btn_label, key=f"btn_{fila['EAN']}", use_container_width=True, type=btn_type):
                    agregar_al_carrito(fila['EAN'], fila['Referencia'], 1, origen, destino)
                    st.rerun()
        else:
            st.info("No se han encontrado resultados.")

# 3. REVISIÓN, TOTALES Y EXPORTACIÓN (Al final del flujo)
if st.session_state.carrito:
    st.write("---")
    st.subheader("📋 REVISIÓN FINAL DEL PEDIDO")
    
    # Listado para ajustes finos
    for i, prod in enumerate(st.session_state.carrito):
        c_name, c_qty, c_del = st.columns([3, 1.5, 0.5])
        c_name.markdown(f"<div style='padding-top:10px;'>{prod['Referencia']}</div>", unsafe_allow_html=True)
        
        # Selector de cantidad
        nueva_q = c_qty.number_input("Cant.", min_value=1, value=int(prod['Unidades']), key=f"qty_{prod['EAN']}_{i}", label_visibility="collapsed")
        st.session_state.carrito[i]['Unidades'] = nueva_q
        
        # Eliminar línea
        if c_del.button("✕", key=f"del_{prod['EAN']}_{i}", help="Eliminar producto"):
            st.session_state.carrito.pop(i)
            st.rerun()

    st.write("###")
    
    # PANEL DE TOTALES (KPIs de confirmación)
    with st.container():
        st.markdown("**RESUMEN DE CARGA PARA ERP**")
        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric("TOTAL PIEZAS", sum(item['Unidades'] for item in st.session_state.carrito))
        kpi2.metric("REFS. ÚNICAS", len(st.session_state.carrito))
        kpi3.metric("DESTINO", destino)

    # ACCIONES FINALES
    if os.path.exists('plantilla.xlsx'):
        try:
            wb = load_workbook('plantilla.xlsx')
            ws = wb.active 
            # Escribir datos a partir de la fila 2
            for idx, r in enumerate(st.session_state.carrito):
                ws.cell(row=idx+2, column=1, value=r['EAN'])
                ws.cell(row=idx+2, column=2, value=r['Origen'])
                ws.cell(row=idx+2, column=3, value=r['Destino'])
                ws.cell(row=idx+2, column=4, value=r['Referencia'])
                ws.cell(row=idx+2, column=5, value=r['Unidades'])
            
            # Preparar descarga
            output = io.BytesIO()
            wb.save(output)
            
            st.write("###")
            c_clear, c_down = st.columns([1, 2])
            
            if c_clear.button("BORRAR TODO", use_container_width=True):
                st.session_state.carrito = []
                st.rerun()
                
            c_down.download_button(
                label="📥 GENERAR EXCEL PARA IMPORTAR",
                data=output.getvalue(),
                file_name=f"IMPORT_ERP_{ref_peticion}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                type="primary"
            )
        except Exception as e:
            st.error(f"Error al procesar la plantilla: {e}")
    else:
        st.error("⚠️ Error: No se encuentra 'plantilla.xlsx' en el repositorio.")

