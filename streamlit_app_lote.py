# =========================
# ASISTENTE DE PETICIONES
# Charo Ruiz · Logistics
# =========================
import streamlit as st
import pandas as pd
import os
import io
import json
import re
from datetime import datetime, date
from typing import List, Optional, Tuple, Dict, Any
from openpyxl import load_workbook

# =========================================================
# CONFIGURACIÓN
# =========================================================
st.set_page_config(page_title="Asistente de Peticiones", layout="wide")

# =========================================================
# ESTILOS
# =========================================================
st.markdown("""
<style>
html, body, .stApp, .main, .block-container {
    background-color: #ffffff !important;
    color: #111111 !important;
}
.main .block-container { 
    padding-top: 2rem; 
    padding-bottom: 3rem; 
    max-width: 900px; 
}

.asistente-header {
    font-size: 2.5rem; 
    font-weight: 800; 
    color: #0B2D5B;
    margin-bottom: 0.5rem;
    text-align: center;
}
.asistente-subtitle {
    font-size: 1rem; 
    color: rgba(17,17,17,0.6);
    margin-bottom: 2rem;
    text-align: center;
}

.step-indicator {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 12px;
    margin: 2rem 0;
    padding: 1.5rem;
    background: #F8F9FA;
    border-radius: 16px;
}
.step-dot {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: #E0E0E0;
}
.step-dot.active {
    background: #0B2D5B;
    width: 16px;
    height: 16px;
}
.step-dot.completed {
    background: #28A745;
}

.chat-message {
    padding: 1.2rem 1.5rem;
    margin: 1rem 0;
    border-radius: 18px;
    background: #F8F9FA;
    border-left: 4px solid #0B2D5B;
}
.chat-message.user {
    background: #E3F2FD;
    border-left: 4px solid #1976D2;
}

.summary-card {
    background: #F8F9FA;
    padding: 1.5rem;
    border-radius: 16px;
    margin: 1rem 0;
    border: 1px solid rgba(0,0,0,0.1);
}
.summary-card h4 {
    margin-top: 0;
    color: #0B2D5B;
    font-size: 1.1rem;
}
.summary-item {
    display: flex;
    justify-content: space-between;
    padding: 0.5rem 0;
    border-bottom: 1px solid rgba(0,0,0,0.05);
}

.producto-item {
    background: white;
    padding: 1rem;
    margin: 0.5rem 0;
    border-radius: 12px;
    border: 1px solid rgba(0,0,0,0.1);
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}

.stButton>button {
    width: 100% !important;
    border-radius: 12px !important;
    font-weight: 700 !important;
    height: 48px;
    font-size: 0.95rem !important;
}
.stButton>button[kind="primary"] {
    background: #0B2D5B !important;
    color: white !important;
}
.stButton>button[kind="secondary"] {
    background: white !important;
    color: #0B2D5B !important;
    border: 2px solid #0B2D5B !important;
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# UTILIDADES
# =========================================================
TALLA_MAP = {
    "x-small": "xs", "x small": "xs", "xs": "xs",
    "small": "s", "s": "s",
    "medium": "m", "m": "m",
    "large": "l", "l": "l",
    "x-large": "xl", "x large": "xl", "xl": "xl",
    "xxl": "xxl", "xxxl": "xxxl",
    "0": "0", "1": "1", "2": "2", "3": "3", "4": "4", "5": "5",
}

def norm_txt(x) -> str:
    if x is None:
        return ""
    s = str(x).strip().casefold()
    s = re.sub(r"\s+", " ", s)
    return s

def norm_color(x) -> str:
    s = norm_txt(x)
    s = s.replace(" - ", "-").replace(" / ", "/")
    return s

def norm_talla(x) -> str:
    s = norm_txt(x)
    return TALLA_MAP.get(s, s)

def looks_like_talla(token: str) -> bool:
    t = norm_talla(token)
    if t in set(TALLA_MAP.values()):
        return True
    if re.fullmatch(r"(xs|s|m|l|xl|xxl|xxxl)", t):
        return True
    if re.fullmatch(r"\d{1,2}", t):
        return True
    return False

def _clean_ean(x) -> str:
    if pd.isna(x):
        return ""
    s = str(x).strip()
    if s.lower() == "nan":
        return ""
    if s.endswith(".0"):
        s = s[:-2]
    return s.strip()

def _find_col(df: pd.DataFrame, candidates: List[str]):
    low_map = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in low_map:
            return low_map[cand.lower()]
    for c in df.columns:
        cl = c.lower()
        for cand in candidates:
            if cand.lower() in cl:
                return c
    return None

def read_excel_any(uploaded_file):
    """Lee xlsx/xls de forma robusta.

    - Para .xlsx usa openpyxl.
    - Para .xls intenta xlrd (si no está instalado, da un error claro).
    """
    name = getattr(uploaded_file, 'name', '') or ''
    ext = name.lower().rsplit('.', 1)[-1] if '.' in name else ''

    if ext == 'xls':
        try:
            return pd.read_excel(uploaded_file, engine='xlrd')
        except ImportError as e:
            raise ImportError(
                "Este archivo es .xls pero falta la dependencia 'xlrd'. "
                "Solución: convierte el Excel a .xlsx o añade xlrd==2.* en requirements.txt."
            ) from e

    # Por defecto, xlsx
    return pd.read_excel(uploaded_file, engine='openpyxl')

def parse_producto_linea(raw: str):
    """
    Formatos:
      [REF] Nombre (Color, Talla)
      [REF] Nombre (XS)
      [REF] Nombre (Blanco Lagoon)
    """
    if not isinstance(raw, str):
        return None, None, None, 0

    s = raw.strip()
    m = re.search(r"\[(.*?)\]", s)
    if not m:
        return None, None, None, 0
    ref = m.group(1).strip()

    pm = re.search(r"\((.*)\)\s*$", s)
    if not pm:
        return ref, None, None, 0

    inside = pm.group(1).strip()
    if not inside:
        return ref, None, None, 0

    if "," in inside:
        a1, a2 = inside.rsplit(",", 1)
        return ref, a1.strip(), a2.strip(), 2

    return ref, inside.strip(), None, 1

# =========================================================
# CATÁLOGO
# =========================================================
@st.cache_data
def load_catalogue(path="catalogue.xlsx"):
    if not os.path.exists(path):
        return None, f"No encuentro '{path}' en la carpeta de la app."

    try:
        df = pd.read_excel(path, engine="openpyxl")
        df.columns = [str(c).strip() for c in df.columns]

        ean_col = _find_col(df, ["EAN", "Ean", "codigo ean", "código ean", "ean code"])
        if not ean_col:
            return None, f"Catálogo leído, pero NO encuentro columna EAN."

        df["EAN"] = df[ean_col].apply(_clean_ean)

        ref_col = _find_col(df, ["Referencia", "ref", "reference"])
        if ref_col and ref_col != "Referencia":
            df["Referencia"] = df[ref_col].astype(str).str.strip()
        elif "Referencia" in df.columns:
            df["Referencia"] = df["Referencia"].astype(str).str.strip()
        else:
            df["Referencia"] = ""

        for opt in ["Nombre", "Color", "Talla", "Colección", "Categoría", "Familia"]:
            col = _find_col(df, [opt])
            if col and col != opt:
                df[opt] = df[col]
            if opt not in df.columns:
                df[opt] = ""

        df["ref_n"] = df["Referencia"].apply(norm_txt)
        df["color_n"] = df["Color"].apply(norm_color)
        df["talla_n"] = df["Talla"].apply(norm_talla)

        return df, None
    except Exception as e:
        return None, f"Error leyendo catálogo: {e}"

def build_catalog_indexes(df_cat: pd.DataFrame):
    exact, ref_color, ref_talla = {}, {}, {}

    def add(d, k, row):
        d.setdefault(k, []).append(row)

    for _, r in df_cat.iterrows():
        row = {
            "EAN": str(r.get("EAN", "")).strip(),
            "Referencia": r.get("Referencia", ""),
            "Nombre": r.get("Nombre", ""),
            "Color": r.get("Color", ""),
            "Talla": r.get("Talla", ""),
            "ref_n": r.get("ref_n", ""),
            "color_n": r.get("color_n", ""),
            "talla_n": r.get("talla_n", ""),
        }
        add(exact, (row["ref_n"], row["color_n"], row["talla_n"]), row)
        add(ref_color, (row["ref_n"], row["color_n"]), row)
        add(ref_talla, (row["ref_n"], row["talla_n"]), row)

    return exact, ref_color, ref_talla

def pick_unique(rows: List[Dict[str, Any]]):
    if not rows:
        return None, "NO_ENCONTRADO"
    if len(rows) > 1:
        return None, "AMBIGUO"
    row = rows[0]
    if not row.get("EAN"):
        return None, "SIN_EAN"
    return row, None

def match_producto(ref_imp: str, a1: Optional[str], a2: Optional[str], n_attrs: int,
                   idx_exact, idx_ref_color, idx_ref_talla):
    ref_n = norm_txt(ref_imp)

    if n_attrs == 2:
        color_n = norm_color(a1)
        talla_n = norm_talla(a2)
        return pick_unique(idx_exact.get((ref_n, color_n, talla_n), [])), "EXACTO ref+color+talla"

    if n_attrs == 1 and a1:
        token = a1.strip()
        if looks_like_talla(token):
            talla_n = norm_talla(token)
            return pick_unique(idx_ref_talla.get((ref_n, talla_n), [])), "ref+talla"
        color_n = norm_color(token)
        return pick_unique(idx_ref_color.get((ref_n, color_n), [])), "ref+color"

    return (None, "NO_ENCONTRADO"), "sin atributos"

# =========================================================
# GENERACIÓN DE ARCHIVO DE SALIDA
# =========================================================
def generar_archivo_peticion(carrito, fecha_str, origen, destino, ref_peticion):
    """Genera el Excel de importación para Odoo"""
    records = []
    for ean, item in carrito.items():
        records.append({
            "EAN": ean,
            "Referencia": item["Referencia"],
            "Nombre": item["Nombre"],
            "Color": item["Color"],
            "Talla": item["Talla"],
            "Cantidad": item["qty"]
        })
    
    df = pd.DataFrame(records)
    
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="PETICION")
    out.seek(0)
    
    filename = f"peticion_{ref_peticion or 'sin_ref'}_{fecha_str}.xlsx"
    return out.getvalue(), filename

# =========================================================
# ESTADO DE LA SESIÓN
# =========================================================
def init_session_state():
    if "step" not in st.session_state:
        st.session_state.step = 1
    if "carrito" not in st.session_state:
        st.session_state.carrito = {}  # carrito final (merge)
    if "carrito_import" not in st.session_state:
        st.session_state.carrito_import = {}  # productos cargados por importación
    if "carrito_manual" not in st.session_state:
        st.session_state.carrito_manual = {}  # productos añadidos manualmente
    if "manual_buffer" not in st.session_state:
        st.session_state.manual_buffer = {}  # selección temporal antes de unir
    if "config" not in st.session_state:
        st.session_state.config = {
            "fecha": date.today(),
            "origen": "PET Almacén Badalona",
            "destino": "PET T002 Marbella",
            "ref_peticion": ""
        }
    if "productos_procesados" not in st.session_state:
        st.session_state.productos_procesados = []
    if "incidencias" not in st.session_state:
        st.session_state.incidencias = []

init_session_state()

# =========================================================
# INDICADOR DE PASOS
# =========================================================
def show_step_indicator(current_step):
    steps = [
        "Configuración",
        "Carga de datos",
        "Revisión",
        "Ajustes",
        "Exportar"
    ]
    
    st.markdown('<div class="step-indicator">', unsafe_allow_html=True)
    for i, step_name in enumerate(steps, 1):
        if i < current_step:
            dot_class = "step-dot completed"
        elif i == current_step:
            dot_class = "step-dot active"
        else:
            dot_class = "step-dot"
        st.markdown(f'<div class="{dot_class}" title="{step_name}"></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# MENSAJE DEL ASISTENTE
# =========================================================
def asistente_mensaje(texto, tipo="asistente"):
    clase = "chat-message" if tipo == "asistente" else "chat-message user"
    st.markdown(f'<div class="{clase}">{texto}</div>', unsafe_allow_html=True)

# =========================================================
# MAIN
# =========================================================
st.markdown('<div class="asistente-header">🎯 Asistente de Peticiones</div>', unsafe_allow_html=True)
st.markdown('<div class="asistente-subtitle">Te guiaré paso a paso en el proceso de reposición</div>', unsafe_allow_html=True)

# Cargar catálogo
df_cat, cat_err = load_catalogue("catalogue.xlsx")
if cat_err:
    st.error(f"❌ {cat_err}")
    st.stop()

idx_exact, idx_ref_color, idx_ref_talla = build_catalog_indexes(df_cat)

# Mostrar indicador de pasos
show_step_indicator(st.session_state.step)

# =========================================================
# PASO 1: CONFIGURACIÓN
# =========================================================
if st.session_state.step == 1:
    asistente_mensaje(
        "👋 **¡Bienvenido!** Voy a ayudarte a crear una petición de reposición.<br><br>"
        "Primero necesito algunos datos básicos. Por favor, completa la información:"
    )
    
    with st.form("config_form"):
        st.markdown("### 📋 Información de la Petición")
        
        col1, col2 = st.columns(2)
        
        with col1:
            fecha = st.date_input(
                "📅 Fecha",
                value=st.session_state.config["fecha"]
            )
            origen = st.selectbox(
                "📦 Almacén Origen",
                ["PET Almacén Badalona", "PET Almacén Ibiza", "PET T001 Ibiza", 
                 "PET T002 Marbella", "PET T004 Madrid"],
                index=0
            )
        
        with col2:
            destino = st.selectbox(
                "🏪 Almacén Destino",
                ["PET Almacén Badalona", "PET Almacén Ibiza", "PET T001 Ibiza", 
                 "PET T002 Marbella", "PET T004 Madrid"],
                index=3
            )
            ref_peticion = st.text_input(
                "🔖 Referencia de Petición (opcional)",
                value=st.session_state.config["ref_peticion"]
            )
        
        submitted = st.form_submit_button("Continuar ➡️", type="primary")
        
        if submitted:
            if origen == destino:
                st.error("⚠️ El almacén de origen y destino no pueden ser el mismo")
            else:
                st.session_state.config = {
                    "fecha": fecha,
                    "origen": origen,
                    "destino": destino,
                    "ref_peticion": ref_peticion
                }
                st.session_state.step = 2
                st.rerun()

# =========================================================
# PASO 2: CARGA DE DATOS
# =========================================================
elif st.session_state.step == 2:
    config = st.session_state.config
    
    asistente_mensaje(
        f"✅ **Configuración guardada:**<br>"
        f"📅 Fecha: {config['fecha'].strftime('%d/%m/%Y')}<br>"
        f"📦 Origen: {config['origen']}<br>"
        f"🏪 Destino: {config['destino']}<br>"
        f"🔖 Referencia: {config['ref_peticion'] or 'Sin referencia'}"
    )
    
    st.markdown("---")
    
    asistente_mensaje(
        "📁 **Ahora necesito el archivo de ventas del TPV**<br><br>"
        "Sube el archivo Excel que contiene:<br>"
        "• **Columna A**: Productos en formato [REF] Nombre (Color, Talla)<br>"
        "• **Columna B o C**: Cantidades vendidas"
    )
    
    archivo = st.file_uploader(
        "Selecciona el archivo Excel",
        type=["xlsx", "xls"],
        key="upload_ventas"
    )
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if st.button("⬅️ Volver", type="secondary"):
            st.session_state.step = 1
            st.rerun()
    
    with col2:
        if archivo is not None:
            if st.button("Procesar archivo ➡️", type="primary"):
                with st.spinner("🔄 Procesando archivo..."):
                    try:
                        df_v = read_excel_any(archivo)
                        
                        if df_v.shape[1] < 2:
                            st.error("❌ El Excel debe tener al menos 2 columnas")
                            st.stop()
                        
                        prod_series = df_v.iloc[:, 0].astype(str)
                        
                        qty_b = pd.to_numeric(df_v.iloc[:, 1], errors="coerce")
                        qty_c = None
                        use_c = False
                        if df_v.shape[1] >= 3:
                            qty_c = pd.to_numeric(df_v.iloc[:, 2], errors="coerce")
                            if qty_c.notna().any() and (qty_c.fillna(0) > 0).any():
                                use_c = True
                        
                        qty_series = (qty_c if use_c else qty_b).fillna(0).astype(int)
                        
                        work = pd.DataFrame({"prod_raw": prod_series, "qty": qty_series})
                        work["prod_raw"] = work["prod_raw"].astype(str).str.strip()
                        work = work[work["qty"] > 0].copy()
                        
                        mask = work["prod_raw"].str.contains(r"\[.*?\].*\(.*\)", regex=True, na=False)
                        work = work[mask].copy()
                        
                        if work.empty:
                            st.error("❌ No se encontraron productos válidos en el archivo")
                            st.stop()
                        
                        parsed = work["prod_raw"].apply(parse_producto_linea)
                        work["ref_imp"] = parsed.apply(lambda t: t[0])
                        work["a1"] = parsed.apply(lambda t: t[1])
                        work["a2"] = parsed.apply(lambda t: t[2])
                        work["n_attrs"] = parsed.apply(lambda t: t[3])
                        
                        productos_procesados = []
                        incidencias = []
                        carrito_temp = {}
                        
                        for _, row in work.iterrows():
                            (match_row, err_code), metodo = match_producto(
                                row["ref_imp"], row["a1"], row["a2"], row["n_attrs"],
                                idx_exact, idx_ref_color, idx_ref_talla
                            )
                            
                            if match_row:
                                ean = match_row["EAN"]
                                productos_procesados.append({
                                    "EAN": ean,
                                    "Referencia": match_row["Referencia"],
                                    "Nombre": match_row["Nombre"],
                                    "Color": match_row["Color"],
                                    "Talla": match_row["Talla"],
                                    "qty": row["qty"],
                                    "metodo": metodo
                                })
                                carrito_temp[ean] = {
                                    "Referencia": match_row["Referencia"],
                                    "Nombre": match_row["Nombre"],
                                    "Color": match_row["Color"],
                                    "Talla": match_row["Talla"],
                                    "qty": row["qty"]
                                }
                            else:
                                incidencias.append({
                                    "producto_raw": row["prod_raw"],
                                    "ref_imp": row["ref_imp"],
                                    "qty": row["qty"],
                                    "error": err_code,
                                    "metodo": metodo
                                })
                        
                        st.session_state.productos_procesados = productos_procesados
                        st.session_state.incidencias = incidencias
                        st.session_state.carrito_import = carrito_temp
                        st.session_state.carrito = carrito_temp.copy()
                        # no tocamos carrito_manual aquí
                        st.session_state.step = 3
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"❌ Error procesando el archivo: {e}")

# =========================================================
# PASO 3: REVISIÓN
# =========================================================
elif st.session_state.step == 3:
    productos = st.session_state.productos_procesados
    incidencias = st.session_state.incidencias
    
    total_procesados = len(productos)
    total_incidencias = len(incidencias)
    total_unidades = sum(p["qty"] for p in productos)
    
    asistente_mensaje(
        f"✅ **Archivo procesado correctamente**<br><br>"
        f"📊 **Resumen:**<br>"
        f"• Productos encontrados: **{total_procesados}**<br>"
        f"• Total unidades: **{total_unidades}**<br>"
        f"• Incidencias: **{total_incidencias}**"
    )
    
    if total_incidencias > 0:
        with st.expander(f"⚠️ Ver {total_incidencias} incidencias", expanded=False):
            for inc in incidencias:
                st.warning(
                    f"**{inc['producto_raw']}**\n\n"
                    f"Cantidad: {inc['qty']} | Error: {inc['error']}"
                )
    
    st.markdown("---")
    
    asistente_mensaje(
        "📦 **Productos a incluir en la petición:**<br><br>"
        "Revisa la lista. En el siguiente paso podrás ajustar las cantidades."
    )
    
    for prod in productos[:10]:  # Mostrar solo los primeros 10
        st.markdown(f"""
        <div class="producto-item">
            <strong>{prod['Referencia']}</strong> - {prod['Nombre']}<br>
            <small>Color: {prod['Color']} | Talla: {prod['Talla']} | Cantidad: <strong>{prod['qty']}</strong></small>
        </div>
        """, unsafe_allow_html=True)
    
    if len(productos) > 10:
        st.info(f"... y {len(productos) - 10} productos más")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if st.button("⬅️ Volver", type="secondary"):
            st.session_state.step = 2
            st.rerun()
    
    with col2:
        if st.button("Continuar ➡️", type="primary"):
            st.session_state.step = 4
            st.rerun()

# =========================================================
# PASO 4: AJUSTES Y AÑADIR PRODUCTOS
# =========================================================
elif st.session_state.step == 4:
    asistente_mensaje(
        "✏️ **Ajusta las cantidades o añade productos adicionales**<br><br>"
        "Puedes modificar las cantidades antes de generar el archivo final."
    )
    
st.markdown("### 📥 Productos importados")
carrito_import = st.session_state.carrito_import.copy()

items_to_remove = []
for ean, item in carrito_import.items():
    col1, col2, col3 = st.columns([3, 1, 1])

    with col1:
        st.markdown(f"""
        <div style="padding: 8px 0;">
            <strong>{item['Referencia']}</strong> - {item['Nombre']}<br>
            <small>{item['Color']} | {item['Talla']}</small>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        nueva_qty = st.number_input(
            "Cantidad",
            min_value=0,
            value=int(item.get("qty", 0)),
            key=f"qty_imp_{ean}",
            label_visibility="collapsed"
        )
        carrito_import[ean]["qty"] = int(nueva_qty)

    with col3:
        if st.button("🗑️", key=f"del_imp_{ean}"):
            items_to_remove.append(ean)

for ean in items_to_remove:
    del carrito_import[ean]

st.session_state.carrito_import = carrito_import

st.markdown("---")

st.markdown("### ✍️ Productos añadidos manualmente")
carrito_manual = st.session_state.carrito_manual.copy()

items_to_remove = []
for ean, item in carrito_manual.items():
    col1, col2, col3 = st.columns([3, 1, 1])

    with col1:
        st.markdown(f"""
        <div style="padding: 8px 0;">
            <strong>{item['Referencia']}</strong> - {item['Nombre']}<br>
            <small>{item['Color']} | {item['Talla']}</small>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        nueva_qty = st.number_input(
            "Cantidad",
            min_value=0,
            value=int(item.get("qty", 0)),
            key=f"qty_man_{ean}",
            label_visibility="collapsed"
        )
        carrito_manual[ean]["qty"] = int(nueva_qty)

    with col3:
        if st.button("🗑️", key=f"del_man_{ean}"):
            items_to_remove.append(ean)

for ean in items_to_remove:
    del carrito_manual[ean]

st.session_state.carrito_manual = carrito_manual

st.markdown("---")

# ---------------------------------------------------------
# AÑADIR EN LOTE (POR REFERENCIAS)
# ---------------------------------------------------------
with st.expander("➕ Añadir productos en lote (pegar referencias)", expanded=True):
    st.info("Pega referencias separadas por salto de línea, coma, punto y coma o espacios. Luego elige variante (color/talla) y cantidades.")

    refs_text = st.text_area("Referencias", height=120, placeholder="Ejemplo:\nA1234\nA5678, A9012; A3456")
    col_a, col_b = st.columns([1, 2])

    def _parse_refs(txt: str):
        if not txt:
            return []
        tokens = re.split(r"[\n,;\t ]+", txt.strip())
        tokens = [t.strip() for t in tokens if t.strip()]
        # mantener orden y quitar duplicados
        seen = set()
        out = []
        for t in tokens:
            if t not in seen:
                seen.add(t)
                out.append(t)
        return out

    with col_a:
        if st.button("🔎 Preparar selección", key="prep_lote"):
            st.session_state.manual_buffer = {}  # resetea selección temporal
            st.session_state.refs_lote = _parse_refs(refs_text)

    refs_lote = st.session_state.get("refs_lote", [])
    if refs_lote:
        st.write(f"Referencias detectadas: **{len(refs_lote)}**")

        for ref in refs_lote:
            df_ref = df_cat[df_cat["Referencia"].astype(str).str.upper() == str(ref).upper()].copy()

            if df_ref.empty:
                st.error(f"❌ No encontrada en catálogo: **{ref}**")
                continue

            # Si hay varias variantes, elige una por referencia
            opciones = []
            for _, r in df_ref.iterrows():
                opciones.append({
                    "label": f"{r.get('Color','')} | {r.get('Talla','')} | EAN {r.get('EAN','')}",
                    "ean": str(r.get("EAN", "")),
                    "Referencia": r.get("Referencia", ""),
                    "Nombre": r.get("Nombre", ""),
                    "Color": r.get("Color", ""),
                    "Talla": r.get("Talla", "")
                })

            col1, col2 = st.columns([3, 1])
            with col1:
                if len(opciones) == 1:
                    sel = opciones[0]
                    st.write(f"**{ref}** → {sel['label']}")
                else:
                    labels = [o["label"] for o in opciones]
                    pick = st.selectbox(f"**{ref}**: elige variante", labels, key=f"pick_{ref}")
                    sel = next(o for o in opciones if o["label"] == pick)

            with col2:
                qty = st.number_input("Cant.", min_value=0, value=1, step=1, key=f"qty_lote_{ref}")

            # guarda en buffer por EAN
            if sel["ean"]:
                st.session_state.manual_buffer[sel["ean"]] = {
                    "Referencia": sel["Referencia"],
                    "Nombre": sel["Nombre"],
                    "Color": sel["Color"],
                    "Talla": sel["Talla"],
                    "qty": int(qty),
                }

        if st.button("✅ Añadir selección al bloque manual", type="primary", key="add_lote"):
            added = 0
            for ean, it in st.session_state.manual_buffer.items():
                if int(it.get("qty", 0)) <= 0:
                    continue
                if ean in st.session_state.carrito_manual:
                    st.session_state.carrito_manual[ean]["qty"] += int(it["qty"])
                else:
                    st.session_state.carrito_manual[ean] = it
                added += 1

            st.success(f"Se añadieron **{added}** referencias al bloque manual.")
            st.session_state.manual_buffer = {}
            st.session_state.refs_lote = []
            st.rerun()

# ---------------------------------------------------------
# BÚSQUEDA (SE MANTIENE, PERO AÑADE AL BLOQUE MANUAL)
# ---------------------------------------------------------
with st.expander("🔎 Buscar y añadir (uno a uno)", expanded=False):
    st.info("Busca productos del catálogo para añadirlos al bloque manual")

    busqueda = st.text_input("Buscar por referencia, nombre, color...")

    if busqueda:
        mask = df_cat["Referencia"].str.contains(busqueda, case=False, na=False) | \
               df_cat["Nombre"].str.contains(busqueda, case=False, na=False) | \
               df_cat["Color"].str.contains(busqueda, case=False, na=False)

        resultados = df_cat[mask].head(20)

        if not resultados.empty:
            for _, row in resultados.iterrows():
                col1, col2 = st.columns([4, 1])

                with col1:
                    st.write(f"**{row['Referencia']}** - {row['Nombre']} ({row['Color']}, {row['Talla']})")

                with col2:
                    if st.button("Añadir", key=f"add_man_{row['EAN']}"):
                        ean = str(row['EAN'])
                        if ean in st.session_state.carrito_manual:
                            st.session_state.carrito_manual[ean]["qty"] += 1
                        else:
                            st.session_state.carrito_manual[ean] = {
                                "Referencia": row["Referencia"],
                                "Nombre": row["Nombre"],
                                "Color": row["Color"],
                                "Talla": row["Talla"],
                                "qty": 1
                            }
                        st.rerun()

st.markdown("---")
# Carrito final (sin mezclar visualmente): se usa para el resumen y la exportación
carrito_final = {}
for ean, it in st.session_state.carrito_import.items():
    carrito_final[ean] = dict(it)
for ean, it in st.session_state.carrito_manual.items():
    if ean in carrito_final:
        carrito_final[ean]["qty"] = int(carrito_final[ean].get("qty", 0)) + int(it.get("qty", 0))
    else:
        carrito_final[ean] = dict(it)

total_items = len(carrito_final)
total_unidades = sum(int(item.get("qty", 0)) for item in carrito_final.values())
    
    st.markdown(f"""
    <div class="summary-card">
        <h4>📊 Resumen Final</h4>
        <div class="summary-item">
            <span>Total de referencias:</span>
            <strong>{total_items}</strong>
        </div>
        <div class="summary-item">
            <span>Total de unidades:</span>
            <strong>{total_unidades}</strong>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if st.button("⬅️ Volver", type="secondary"):
            st.session_state.step = 3
            st.rerun()
    
    with col2:
        if st.button("Generar archivo ➡️", type="primary"):
            # Une importados + manuales para exportar
            st.session_state.carrito = carrito_final
            if len(carrito_final) == 0:
                st.error("❌ No hay productos en el carrito")
            else:
                st.session_state.step = 5
                st.rerun()

# =========================================================
# PASO 5: EXPORTAR
# =========================================================
elif st.session_state.step == 5:
    config = st.session_state.config
    
    asistente_mensaje(
        "🎉 **¡Listo para exportar!**<br><br>"
        "Tu petición está completa y lista para importar en Odoo/Gestia."
    )
    
    st.markdown(f"""
    <div class="summary-card">
        <h4>📋 Resumen de la Petición</h4>
        <div class="summary-item">
            <span>Fecha:</span>
            <strong>{config['fecha'].strftime('%d/%m/%Y')}</strong>
        </div>
        <div class="summary-item">
            <span>Origen:</span>
            <strong>{config['origen']}</strong>
        </div>
        <div class="summary-item">
            <span>Destino:</span>
            <strong>{config['destino']}</strong>
        </div>
        <div class="summary-item">
            <span>Referencia:</span>
            <strong>{config['ref_peticion'] or 'Sin referencia'}</strong>
        </div>
        <div class="summary-item">
            <span>Total referencias:</span>
            <strong>{len(st.session_state.carrito)}</strong>
        </div>
        <div class="summary-item">
            <span>Total unidades:</span>
            <strong>{sum(item["qty"] for item in st.session_state.carrito.values())}</strong>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Generar archivo
    archivo_bytes, archivo_nombre = generar_archivo_peticion(
        st.session_state.carrito,
        config['fecha'].strftime('%Y-%m-%d'),
        config['origen'],
        config['destino'],
        config['ref_peticion']
    )
    
    st.download_button(
        label="📥 Descargar archivo de petición",
        data=archivo_bytes,
        file_name=archivo_nombre,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary"
    )
    
    st.markdown("---")
    
    if st.button("🔄 Crear nueva petición"):
        st.session_state.step = 1
        st.session_state.carrito = {}
        st.session_state.carrito_import = {}
        st.session_state.carrito_manual = {}
        st.session_state.manual_buffer = {}
        st.session_state.productos_procesados = []
        st.session_state.incidencias = []
        st.rerun()
