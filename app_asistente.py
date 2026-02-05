# -*- coding: utf-8 -*-
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

# =========================================================
# CONFIGURACIÓN
# =========================================================
st.set_page_config(page_title="Asistente de Peticiones", layout="wide")

APP_TITLE = "Asistente de Peticiones"
AUTOSAVE_FILE = ".autosave_peticion.json"

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

def norm_txt(x):
    if x is None:
        return ""
    s = str(x).strip().casefold()
    s = re.sub(r"\s+", " ", s)
    return s

def norm_color(x):
    s = norm_txt(x)
    s = s.replace(" - ", "-").replace(" / ", "/")
    return s

def norm_talla(x):
    s = norm_txt(x)
    return TALLA_MAP.get(s, s)

def looks_like_talla(token):
    t = norm_talla(token)
    if t in set(TALLA_MAP.values()):
        return True
    if re.fullmatch(r"(xs|s|m|l|xl|xxl|xxxl)", t):
        return True
    if re.fullmatch(r"\d{1,2}", t):
        return True
    return False

def _clean_ean(x):
    if pd.isna(x):
        return ""
    s = str(x).strip()
    if s.lower() == "nan":
        return ""
    if s.endswith(".0"):
        s = s[:-2]
    return s.strip()

def _find_col(df, candidates):
    low_map = {str(c).lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in low_map:
            return low_map[cand.lower()]
    for c in df.columns:
        cl = str(c).lower()
        for cand in candidates:
            if cand.lower() in cl:
                return c
    return None

def read_excel_any(uploaded_file):
    # openpyxl para xlsx, xlrd para xls (si está instalado)
    try:
        return pd.read_excel(uploaded_file, engine="openpyxl")
    except Exception:
        return pd.read_excel(uploaded_file, engine="xlrd")

def parse_producto_linea(raw):
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
# AUTOSAVE (no bloquea el rendimiento: solo por evento)
# =========================================================
def autosave_payload():
    cfg = st.session_state.get("config", {})
    cfg2 = dict(cfg)
    # serializa fecha
    if isinstance(cfg2.get("fecha"), (datetime, date)):
        cfg2["fecha"] = cfg2["fecha"].strftime("%Y-%m-%d")
    payload = {
        "step": int(st.session_state.get("step", 1)),
        "config": cfg2,
        "carrito": st.session_state.get("carrito", {}),
        "productos_procesados": st.session_state.get("productos_procesados", []),
        "incidencias": st.session_state.get("incidencias", []),
        "manual_q": st.session_state.get("manual_q", ""),
        "manual_limit": int(st.session_state.get("manual_limit", 10)),
    }
    return payload

def autosave_write():
    try:
        with open(AUTOSAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(autosave_payload(), f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def autosave_load():
    if not os.path.exists(AUTOSAVE_FILE):
        return False
    try:
        with open(AUTOSAVE_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:
        return False

    st.session_state.step = int(payload.get("step", 1))
    cfg = payload.get("config", {}) or {}
    if cfg.get("fecha"):
        try:
            cfg["fecha"] = datetime.strptime(cfg["fecha"], "%Y-%m-%d")
        except Exception:
            cfg["fecha"] = datetime.now()
    st.session_state.config = cfg
    st.session_state.carrito = payload.get("carrito", {}) or {}
    st.session_state.productos_procesados = payload.get("productos_procesados", []) or []
    st.session_state.incidencias = payload.get("incidencias", []) or []
    st.session_state.manual_q = payload.get("manual_q", "") or ""
    st.session_state.manual_limit = int(payload.get("manual_limit", 10))
    return True

def autosave_clear():
    try:
        if os.path.exists(AUTOSAVE_FILE):
            os.remove(AUTOSAVE_FILE)
    except Exception:
        pass

def sidebar_controls():
    with st.sidebar:
        st.markdown("### 💾 Progreso")
        if os.path.exists(AUTOSAVE_FILE):
            st.caption("Hay un guardado disponible.")
        if st.button("Recuperar guardado"):
            if autosave_load():
                st.success("Recuperado.")
                st.rerun()
            st.info("No hay guardado o no se pudo cargar.")
        if st.button("Guardar ahora"):
            autosave_write()
            st.success("Guardado.")
        if st.button("Reiniciar (borrar todo)"):
            autosave_clear()
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

# =========================================================
# CATÁLOGO (cache + columnas de búsqueda)
# =========================================================
@st.cache_data(show_spinner=False)
def load_catalogue(path="catalogue.xlsx"):
    if not os.path.exists(path):
        return None, f"No encuentro '{path}' en la carpeta de la app."

    try:
        df = pd.read_excel(path, engine="openpyxl")
        df.columns = [str(c).strip() for c in df.columns]

        ean_col = _find_col(df, ["EAN", "Ean", "codigo ean", "código ean", "ean code"])
        if not ean_col:
            return None, "Catálogo leído, pero NO encuentro columna EAN."

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

        # columnas UPPER para búsqueda rápida (una vez)
        for c in ["Referencia", "Nombre", "Color", "Talla", "EAN"]:
            df[c] = df[c].astype(str).fillna("").str.strip()
            df[c + "_U"] = df[c].str.upper()

        return df, None
    except Exception as e:
        return None, f"Error leyendo catálogo: {e}"

@st.cache_resource(show_spinner=False)
def build_catalog_indexes(df_cat):
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

def pick_unique(rows):
    if not rows:
        return None, "NO_ENCONTRADO"
    if len(rows) > 1:
        return None, "AMBIGUO"
    row = rows[0]
    if not row.get("EAN"):
        return None, "SIN_EAN"
    return row, None

def match_producto(ref_imp, a1, a2, n_attrs, idx_exact, idx_ref_color, idx_ref_talla):
    ref_n = norm_txt(ref_imp)

    if n_attrs == 2:
        color_n = norm_color(a1)
        talla_n = norm_talla(a2)
        row, err = pick_unique(idx_exact.get((ref_n, color_n, talla_n), []))
        return (row, err), "EXACTO ref+color+talla"

    if n_attrs == 1 and a1:
        token = a1.strip()
        if looks_like_talla(token):
            talla_n = norm_talla(token)
            row, err = pick_unique(idx_ref_talla.get((ref_n, talla_n), []))
            return (row, err), "ref+talla"
        color_n = norm_color(token)
        row, err = pick_unique(idx_ref_color.get((ref_n, color_n), []))
        return (row, err), "ref+color"

    return (None, "NO_ENCONTRADO"), "sin atributos"

# =========================================================
# IMPORTADOR DE VENTAS (más robusto)
# =========================================================
def detect_columns_ventas(df_v):
    # columna producto: la que más patrones [REF] o paréntesis tenga
    best_prod = None
    best_score = -1
    for c in df_v.columns:
        s = df_v[c].astype(str)
        score = s.str.contains(r"\[.*?\]", regex=True, na=False).mean() + s.str.contains(r"\(.*\)", regex=True, na=False).mean()
        if score > best_score:
            best_score = score
            best_prod = c

    # columna cantidad: numérica con más valores >0
    best_qty = None
    best_qscore = -1
    for c in df_v.columns:
        col = pd.to_numeric(df_v[c], errors="coerce")
        qscore = (col.fillna(0) > 0).mean()
        if qscore > best_qscore:
            best_qscore = qscore
            best_qty = c

    return best_prod, best_qty

# =========================================================
# GENERACIÓN DE ARCHIVO DE SALIDA
# =========================================================
def generar_archivo_peticion(carrito, fecha_str, origen, destino, ref_peticion):
    records = []
    for ean, item in carrito.items():
        records.append({
            "EAN": ean,
            "Referencia": item["Referencia"],
            "Nombre": item["Nombre"],
            "Color": item["Color"],
            "Talla": item["Talla"],
            "Cantidad": int(item["qty"]),
            "Origen": origen,
            "Destino": destino,
            "Fecha": fecha_str,
            "Ref_Peticion": ref_peticion or ""
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
        st.session_state.carrito = {}
    if "config" not in st.session_state:
        # OJO: NO TOCAR nombres de almacenes (se mantienen exactamente)
        st.session_state.config = {
            "fecha": datetime.now(),
            "origen": "PET Almacén Badalona",
            "destino": "PET T002 Marbella",
            "ref_peticion": ""
        }
    if "productos_procesados" not in st.session_state:
        st.session_state.productos_procesados = []
    if "incidencias" not in st.session_state:
        st.session_state.incidencias = []
    if "manual_q" not in st.session_state:
        st.session_state.manual_q = ""
    if "manual_limit" not in st.session_state:
        st.session_state.manual_limit = 10

init_session_state()
sidebar_controls()

# =========================================================
# INDICADOR DE PASOS
# =========================================================
def show_step_indicator(current_step):
    steps = ["Configuración", "Carga de datos", "Revisión", "Ajustes", "Exportar"]
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

show_step_indicator(st.session_state.step)

ALMACENES = ["PET Almacén Badalona", "PET Almacén Ibiza", "PET T001 Ibiza",
             "PET T002 Marbella", "PET T004 Madrid"]

# =========================================================
# PASO 1: CONFIGURACIÓN (SIN CAMBIAR NOMBRES)
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
            fecha = st.date_input("📅 Fecha", value=st.session_state.config["fecha"])
            origen = st.selectbox("📦 Almacén Origen", ALMACENES, index=ALMACENES.index(st.session_state.config["origen"]) if st.session_state.config["origen"] in ALMACENES else 0)

        with col2:
            destino = st.selectbox("🏪 Almacén Destino", ALMACENES, index=ALMACENES.index(st.session_state.config["destino"]) if st.session_state.config["destino"] in ALMACENES else 0)
            ref_peticion = st.text_input("🔖 Referencia de Petición (opcional)", value=st.session_state.config["ref_peticion"])

        submitted = st.form_submit_button("Continuar ➡️", type="primary")

        if submitted:
            if origen == destino:
                st.error("⚠️ El almacén de origen y destino no pueden ser el mismo")
            else:
                st.session_state.config = {"fecha": fecha, "origen": origen, "destino": destino, "ref_peticion": ref_peticion}
                st.session_state.step = 2
                autosave_write()
                st.rerun()

# =========================================================
# PASO 2: CARGA DE DATOS (IMPORT OPCIONAL)
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
        "📁 **Ahora necesito el archivo de ventas del TPV (opcional)**<br><br>"
        "Si lo tienes, súbelo y lo procesamos automáticamente.<br>"
        "Si NO lo tienes, puedes continuar y añadir productos manualmente."
    )

    archivo = st.file_uploader("Selecciona el archivo Excel", type=["xlsx", "xls"], key="upload_ventas")

    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        if st.button("⬅️ Volver", type="secondary"):
            st.session_state.step = 1
            autosave_write()
            st.rerun()

    with col2:
        if st.button("Continuar sin archivo ➡️", type="secondary"):
            # Permite uso 100% manual
            st.session_state.productos_procesados = []
            st.session_state.incidencias = []
            st.session_state.carrito = {}
            st.session_state.step = 4
            autosave_write()
            st.rerun()

    with col3:
        if archivo is not None:
            if st.button("Procesar archivo ➡️", type="primary"):
                with st.spinner("🔄 Procesando archivo..."):
                    try:
                        df_v = read_excel_any(archivo)

                        if df_v.shape[1] < 2:
                            st.error("❌ El Excel debe tener al menos 2 columnas")
                            st.stop()

                        prod_col_guess, qty_col_guess = detect_columns_ventas(df_v)

                        # Si la detección es dudosa, deja elegir
                        with st.expander("Opciones avanzadas (si tu Excel es especial)", expanded=False):
                            prod_col = st.selectbox("Columna de producto", options=list(df_v.columns), index=list(df_v.columns).index(prod_col_guess) if prod_col_guess in df_v.columns else 0)
                            qty_col = st.selectbox("Columna de cantidad", options=list(df_v.columns), index=list(df_v.columns).index(qty_col_guess) if qty_col_guess in df_v.columns else 1)
                        if "prod_col" not in locals():
                            prod_col = prod_col_guess
                            qty_col = qty_col_guess

                        prod_series = df_v[prod_col].astype(str)

                        qty_series = pd.to_numeric(df_v[qty_col], errors="coerce").fillna(0).astype(int)

                        work = pd.DataFrame({"prod_raw": prod_series, "qty": qty_series})
                        work["prod_raw"] = work["prod_raw"].astype(str).str.strip()
                        work = work[work["qty"] > 0].copy()

                        mask = work["prod_raw"].str.contains(r"\[.*?\]", regex=True, na=False)
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
                                qty = int(row["qty"])
                                if ean in carrito_temp:
                                    carrito_temp[ean]["qty"] += qty
                                else:
                                    carrito_temp[ean] = {
                                        "Referencia": match_row["Referencia"],
                                        "Nombre": match_row["Nombre"],
                                        "Color": match_row["Color"],
                                        "Talla": match_row["Talla"],
                                        "qty": qty
                                    }
                                productos_procesados.append({
                                    "EAN": ean,
                                    "Referencia": match_row["Referencia"],
                                    "Nombre": match_row["Nombre"],
                                    "Color": match_row["Color"],
                                    "Talla": match_row["Talla"],
                                    "qty": qty,
                                    "metodo": metodo
                                })
                            else:
                                incidencias.append({
                                    "producto_raw": row["prod_raw"],
                                    "ref_imp": row["ref_imp"],
                                    "qty": int(row["qty"]),
                                    "error": err_code,
                                    "metodo": metodo
                                })

                        st.session_state.productos_procesados = productos_procesados
                        st.session_state.incidencias = incidencias
                        st.session_state.carrito = carrito_temp
                        st.session_state.step = 3
                        autosave_write()
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
    total_unidades = sum(int(p.get("qty", 0)) for p in productos)

    asistente_mensaje(
        f"✅ **Archivo procesado correctamente**<br><br>"
        f"📊 **Resumen:**<br>"
        f"• Productos encontrados: **{total_procesados}**<br>"
        f"• Total unidades: **{total_unidades}**<br>"
        f"• Incidencias: **{total_incidencias}**"
    )

    if total_incidencias > 0:
        with st.expander(f"⚠️ Ver {total_incidencias} incidencias", expanded=False):
            st.dataframe(pd.DataFrame(incidencias), use_container_width=True)

    st.markdown("---")

    asistente_mensaje(
        "📦 **Productos a incluir en la petición:**<br><br>"
        "Revisa la lista. En el siguiente paso podrás ajustar las cantidades y añadir más productos."
    )

    for prod in productos[:10]:
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
            autosave_write()
            st.rerun()

    with col2:
        if st.button("Continuar ➡️", type="primary"):
            st.session_state.step = 4
            autosave_write()
            st.rerun()

# =========================================================
# PASO 4: AJUSTES + AÑADIR PRODUCTOS (MEJOR RENDIMIENTO)
# =========================================================
elif st.session_state.step == 4:
    asistente_mensaje(
        "✏️ **Ajusta las cantidades o añade productos adicionales**<br><br>"
        "Puedes modificar cantidades directamente en la tabla."
    )

    st.markdown("### 🛒 Carrito de Petición")

    # Tabla editable (mucho más rápida que un number_input por línea)
    carrito = st.session_state.carrito or {}
    if carrito:
        df_cart = pd.DataFrame(
            [{"EAN": ean,
              "Referencia": it.get("Referencia", ""),
              "Nombre": it.get("Nombre", ""),
              "Color": it.get("Color", ""),
              "Talla": it.get("Talla", ""),
              "qty": int(it.get("qty", 0))}
             for ean, it in carrito.items()]
        )
    else:
        df_cart = pd.DataFrame(columns=["EAN", "Referencia", "Nombre", "Color", "Talla", "qty"])

    df_edit = st.data_editor(
        df_cart,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "qty": st.column_config.NumberColumn("Cantidad", min_value=0, step=1),
            "EAN": st.column_config.TextColumn("EAN", disabled=True),
            "Referencia": st.column_config.TextColumn("Referencia", disabled=True),
            "Nombre": st.column_config.TextColumn("Nombre", disabled=True),
            "Color": st.column_config.TextColumn("Color", disabled=True),
            "Talla": st.column_config.TextColumn("Talla", disabled=True),
        },
        key="cart_editor",
    )

    # Reconstruye carrito (quita qty<=0)
    carrito_new = {}
    for _, r in df_edit.iterrows():
        ean = str(r.get("EAN", "")).strip()
        if not ean:
            continue
        try:
            qty = int(float(r.get("qty", 0)))
        except Exception:
            qty = 0
        if qty <= 0:
            continue
        carrito_new[ean] = {
            "Referencia": str(r.get("Referencia", "")).strip(),
            "Nombre": str(r.get("Nombre", "")).strip(),
            "Color": str(r.get("Color", "")).strip(),
            "Talla": str(r.get("Talla", "")).strip(),
            "qty": qty
        }
    st.session_state.carrito = carrito_new

    st.markdown("---")

    # Añadir productos manualmente
    with st.expander("➕ Añadir producto manualmente", expanded=True):
        st.info("Busca en el catálogo y añade a la petición.")

        st.session_state.manual_limit = st.selectbox(
            "Resultados a mostrar",
            options=[5, 10, 20, 50, 100],
            index=[5, 10, 20, 50, 100].index(int(st.session_state.manual_limit)) if int(st.session_state.manual_limit) in [5,10,20,50,100] else 1,
            key="manual_limit",
        )

        st.session_state.manual_q = st.text_input(
            "Buscar por referencia, nombre, color, talla o EAN",
            value=st.session_state.manual_q,
            key="manual_q",
        )

        if st.button("Buscar", type="primary"):
            autosave_write()

        q = (st.session_state.manual_q or "").strip()
        if q:
            qU = q.upper()
            mask = (
                df_cat["Referencia_U"].str.contains(qU, na=False) |
                df_cat["Nombre_U"].str.contains(qU, na=False) |
                df_cat["Color_U"].str.contains(qU, na=False) |
                df_cat["Talla_U"].str.contains(qU, na=False) |
                df_cat["EAN_U"].str.contains(qU, na=False)
            )
            resultados = df_cat.loc[mask, ["EAN", "Referencia", "Nombre", "Color", "Talla"]].head(int(st.session_state.manual_limit))

            if resultados.empty:
                st.warning("No hay resultados.")
            else:
                # selector de fila (más rápido que un botón por resultado)
                labels = resultados.apply(
                    lambda r: f"{r['Referencia']} - {r['Nombre']} ({r['Color']}, {r['Talla']}) | {r['EAN']}",
                    axis=1
                ).tolist()
                eans = resultados["EAN"].astype(str).tolist()

                sel = st.selectbox("Selecciona una variante", options=list(range(len(labels))), format_func=lambda i: labels[i])
                qty_add = st.number_input("Cantidad a añadir", 1, 9999, 1, step=1, key="qty_add_one")

                if st.button("Añadir al carrito", type="primary"):
                    ean = str(eans[sel]).strip()
                    row = resultados.iloc[sel]
                    if ean in st.session_state.carrito:
                        st.session_state.carrito[ean]["qty"] += int(qty_add)
                    else:
                        st.session_state.carrito[ean] = {
                            "Referencia": str(row["Referencia"]).strip(),
                            "Nombre": str(row["Nombre"]).strip(),
                            "Color": str(row["Color"]).strip(),
                            "Talla": str(row["Talla"]).strip(),
                            "qty": int(qty_add)
                        }
                    autosave_write()
                    st.rerun()

        st.markdown("#### 📋 Añadir por lote (pegar referencias)")
        refs_txt = st.text_area("Pega referencias (una por línea o separadas por coma/;)", height=120, key="refs_lote")
        qty_default = st.number_input("Cantidad por defecto (lote)", 1, 9999, 1, step=1, key="qty_lote")
        if st.button("Buscar referencias (lote)"):
            st.session_state.refs_lote_list = [r.strip() for r in re.split(r"[,\n;\t]+", refs_txt or "") if r.strip()]
        refs_list = st.session_state.get("refs_lote_list", [])
        if refs_list:
            sub = df_cat[df_cat["Referencia"].isin(refs_list)][["EAN", "Referencia", "Nombre", "Color", "Talla"]]
            if sub.empty:
                st.warning("No encontré esas referencias en catálogo.")
            else:
                st.dataframe(sub.head(200), use_container_width=True)
                if st.button("Añadir TODO lo encontrado (lote)", type="primary"):
                    for _, r in sub.iterrows():
                        ean = str(r["EAN"]).strip()
                        if not ean:
                            continue
                        if ean in st.session_state.carrito:
                            st.session_state.carrito[ean]["qty"] += int(qty_default)
                        else:
                            st.session_state.carrito[ean] = {
                                "Referencia": str(r["Referencia"]).strip(),
                                "Nombre": str(r["Nombre"]).strip(),
                                "Color": str(r["Color"]).strip(),
                                "Talla": str(r["Talla"]).strip(),
                                "qty": int(qty_default)
                            }
                    autosave_write()
                    st.rerun()

    st.markdown("---")

    total_items = len(st.session_state.carrito)
    total_unidades = sum(int(item["qty"]) for item in st.session_state.carrito.values())

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
            st.session_state.step = 3 if st.session_state.productos_procesados else 2
            autosave_write()
            st.rerun()

    with col2:
        if st.button("Generar archivo ➡️", type="primary"):
            if len(st.session_state.carrito) == 0:
                st.error("❌ No hay productos en el carrito")
            else:
                st.session_state.step = 5
                autosave_write()
                st.rerun()

# =========================================================
# PASO 5: EXPORTAR
# =========================================================
elif st.session_state.step == 5:
    config = st.session_state.config

    asistente_mensaje(
        "🎉 **¡Listo para exportar!**<br><br>"
        "Tu petición está completa y lista para importar."
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
            <strong>{sum(int(item["qty"]) for item in st.session_state.carrito.values())}</strong>
        </div>
    </div>
    """, unsafe_allow_html=True)

    fecha_str = config['fecha'].strftime('%Y-%m-%d')
    archivo_bytes, archivo_nombre = generar_archivo_peticion(
        st.session_state.carrito,
        fecha_str,
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

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("⬅️ Volver a ajustes"):
            st.session_state.step = 4
            autosave_write()
            st.rerun()

    with col2:
        if st.button("🔄 Crear nueva petición"):
            st.session_state.step = 1
            st.session_state.carrito = {}
            st.session_state.productos_procesados = []
            st.session_state.incidencias = []
            autosave_clear()
            st.rerun()
