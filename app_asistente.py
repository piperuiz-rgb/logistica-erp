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
from datetime import datetime
from openpyxl import load_workbook

# =========================================================
# CONFIGURACIÓN
# =========================================================
st.set_page_config(page_title="Asistente de Peticiones", layout="wide")


# =========================================================
# BOOTSTRAP ESTADO (antes de usar session_state)
# =========================================================
# Evita AttributeError si se carga un autosave antiguo o si se entra en el script
# antes de inicializar el estado.
if "wizard_step" not in st.session_state:
    # migración suave desde versiones antiguas
    st.session_state.wizard_step = int(st.session_state.get("step", 1) or 1)

if "carrito_import" not in st.session_state:
    st.session_state.carrito_import = {}
if "carrito_manual" not in st.session_state:
    st.session_state.carrito_manual = {}

if "config" not in st.session_state:
    st.session_state.config = {
        "fecha": datetime.now(),
        "origen": "PET Almacén Badalona",
        "destino": "PET T002 Marbella",
        "ref_peticion": ""
    }

if "productos_procesados" not in st.session_state:
    st.session_state.productos_procesados = 0
if "incidencias" not in st.session_state:
    st.session_state.incidencias = []

if "manual_query" not in st.session_state:
    st.session_state.manual_query = ""
if "manual_limit" not in st.session_state:
    st.session_state.manual_limit = 10
if "manual_selected_eans" not in st.session_state:
    st.session_state.manual_selected_eans = []
if "manual_ref_selected" not in st.session_state:
    st.session_state.manual_ref_selected = ""
if "manual_grid_qty" not in st.session_state:
    # cantidades temporales por EAN para el grid color/talla
    st.session_state.manual_grid_qty = {}

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

def _find_col(df: pd.DataFrame, candidates: list[str]):
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
    try:
        return pd.read_excel(uploaded_file, engine="openpyxl")
    except Exception:
        return pd.read_excel(uploaded_file, engine="xlrd")

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

def pick_unique(rows: list[dict]):
    if not rows:
        return None, "NO_ENCONTRADO"
    if len(rows) > 1:
        return None, "AMBIGUO"
    row = rows[0]
    if not row.get("EAN"):
        return None, "SIN_EAN"
    return row, None

def match_producto(ref_imp: str, a1: str | None, a2: str | None, n_attrs: int,
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
    if "wizard_step" not in st.session_state:
        st.session_state.wizard_step = 1

    # Carritos separados
    if "carrito_import" not in st.session_state:
        st.session_state.carrito_import = {}
    if "carrito_manual" not in st.session_state:
        st.session_state.carrito_manual = {}

    # Config (NO tocamos nombres: usamos los mismos por defecto y lista original)
    if "config" not in st.session_state:
        st.session_state.config = {
            "fecha": datetime.now(),
            "origen": "PET Almacén Badalona",
            "destino": "PET T002 Marbella",
            "ref_peticion": ""
        }

    # Resultados de importación
    if "productos_procesados" not in st.session_state:
        st.session_state.productos_procesados = []
    if "incidencias" not in st.session_state:
        st.session_state.incidencias = []

    # UI manual
    if "manual_query" not in st.session_state:
        st.session_state.manual_query = ""
    if "manual_limit" not in st.session_state:
        st.session_state.manual_limit = 10
    if "manual_selected_eans" not in st.session_state:
        st.session_state.manual_selected_eans = []
    if "manual_ref_selected" not in st.session_state:
        st.session_state.manual_ref_selected = ""
    if "manual_grid_qty" not in st.session_state:
        # cantidades temporales por EAN para el grid color/talla
        st.session_state.manual_grid_qty = {}

# =========================================================
# INDICADOR DE PASOS
# =========================================================
def show_step_indicator(current_step):
    steps = ["Quién pide", "Quién envía", "Importación", "Selección manual", "Revisión y exportar"]
    
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
show_step_indicator(st.session_state.wizard_step)


# =========================================================
# ASISTENTE GUIADO (NUEVO FLUJO)
# 1) Quién pide (Destino)
# 2) Quién envía (Origen)
# 3) Importación (opcional)
# 4) Selección manual (multi + cantidades) — SEPARADA de importados
# 5) Revisión final (unión + cantidades definitivas) y exportación
# =========================================================

ALMACENES = ["PET Almacén Badalona", "PET Almacén Ibiza", "PET T001 Ibiza",
             "PET T002 Marbella", "PET T004 Madrid"]

# -------------------------
# Auto-guardado simple (JSON)
# -------------------------
AUTOSAVE_FILE = ".autosave_peticion.json"

def _autosave_payload():
    cfg = st.session_state.config.copy()
    # fecha a string
    try:
        cfg["fecha"] = cfg["fecha"].isoformat()
    except Exception:
        cfg["fecha"] = str(cfg.get("fecha", ""))
    return {
        "wizard_step": int(st.session_state.wizard_step),
        "config": cfg,
        "carrito_import": st.session_state.carrito_import,
        "carrito_manual": st.session_state.carrito_manual,
        "incidencias": st.session_state.incidencias,
    }

def autosave_write():
    try:
        with open(AUTOSAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(_autosave_payload(), f, ensure_ascii=False, indent=2)
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

    st.session_state.wizard_step = int(payload.get("wizard_step", 1))
    cfg = payload.get("config", {}) or {}
    # fecha desde iso
    try:
        cfg["fecha"] = datetime.fromisoformat(cfg.get("fecha"))
    except Exception:
        cfg["fecha"] = datetime.now()
    # Mantener nombres tal cual
    st.session_state.config = {
        "fecha": cfg.get("fecha", datetime.now()),
        "origen": cfg.get("origen", "PET Almacén Badalona"),
        "destino": cfg.get("destino", "PET T002 Marbella"),
        "ref_peticion": cfg.get("ref_peticion", ""),
    }
    st.session_state.carrito_import = payload.get("carrito_import", {}) or {}
    st.session_state.carrito_manual = payload.get("carrito_manual", {}) or {}
    st.session_state.incidencias = payload.get("incidencias", []) or []
    return True

def autosave_clear():
    try:
        if os.path.exists(AUTOSAVE_FILE):
            os.remove(AUTOSAVE_FILE)
    except Exception:
        pass

# Sidebar de progreso
with st.sidebar:
    st.markdown("### 💾 Progreso")
    if os.path.exists(AUTOSAVE_FILE):
        st.info("Hay un guardado disponible.")
        c1, c2 = st.columns(2)
        if c1.button("Recuperar", type="primary"):
            if autosave_load():
                st.rerun()
        if c2.button("Empezar nuevo"):
            autosave_clear()
            # reinicia estado sin tocar catálogo
            st.session_state.wizard_step = 1
            st.session_state.carrito_import = {}
            st.session_state.carrito_manual = {}
            st.session_state.incidencias = []
            st.session_state.productos_procesados = []
            st.session_state.config = {
                "fecha": datetime.now(),
                "origen": "PET Almacén Badalona",
                "destino": "PET T002 Marbella",
                "ref_peticion": ""
            }
            st.rerun()

# Atajo: si no hay config mínima, forzar paso 1
cfg = st.session_state.config
if not cfg.get("destino") or not cfg.get("origen"):
    st.session_state.wizard_step = 1

# =========================================================
# PASO 1: Quién pide (Destino)
# =========================================================
if st.session_state.wizard_step == 1:
    asistente_mensaje(
        "👋 Vamos paso a paso.<br><br>"
        "**1/5 — ¿Qué almacén pide la mercancía?** (Destino)"
    )

    with st.form("paso1_destino"):
        col1, col2 = st.columns(2)
        with col1:
            destino = st.selectbox("🏪 Almacén que pide (Destino)", ALMACENES,
                                   index=ALMACENES.index(cfg.get("destino")) if cfg.get("destino") in ALMACENES else 0,
                                   key="ui_destino")
        with col2:
            fecha = st.date_input("📅 Fecha", value=cfg.get("fecha", datetime.now()),
                                  key="ui_fecha")
            ref_peticion = st.text_input("🔖 Referencia (opcional)", value=cfg.get("ref_peticion",""),
                                         key="ui_ref")
        submitted = st.form_submit_button("Continuar ➡️", type="primary")
        if submitted:
            st.session_state.config["destino"] = destino
            st.session_state.config["fecha"] = datetime.combine(fecha, datetime.min.time())
            st.session_state.config["ref_peticion"] = ref_peticion
            st.session_state.wizard_step = 2
            autosave_write()
            st.rerun()

# =========================================================
# PASO 2: Quién envía (Origen)
# =========================================================
elif st.session_state.wizard_step == 2:
    asistente_mensaje("**2/5 — ¿Qué almacén envía la mercancía?** (Origen)")

    with st.form("paso2_origen"):
        origen = st.selectbox("📦 Almacén que envía (Origen)", ALMACENES,
                              index=ALMACENES.index(cfg.get("origen")) if cfg.get("origen") in ALMACENES else 0,
                              key="ui_origen")
        submitted = st.form_submit_button("Continuar ➡️", type="primary")
        if submitted:
            if origen == cfg.get("destino"):
                st.error("⚠️ El almacén que envía y el que pide no pueden ser el mismo.")
            else:
                st.session_state.config["origen"] = origen
                st.session_state.wizard_step = 3
                autosave_write()
                st.rerun()

    if st.button("⬅️ Volver", type="secondary"):
        st.session_state.wizard_step = 1
        autosave_write()
        st.rerun()

# =========================================================
# PASO 3: Importación (opcional)
# =========================================================
elif st.session_state.wizard_step == 3:
    config = st.session_state.config
    asistente_mensaje(
        f"✅ Configuración:<br>"
        f"🏪 Pide: {config['destino']}<br>"
        f"📦 Envía: {config['origen']}<br><br>"
        "**3/5 — Importación (opcional)**: puedes subir Excel o saltarlo."
    )

    archivo = st.file_uploader("📁 Subir Excel de ventas (opcional)", type=["xlsx", "xls"], key="upload_ventas")

    c1, c2, c3 = st.columns([1, 1, 1])
    if c1.button("⬅️ Volver", type="secondary"):
        st.session_state.wizard_step = 2
        autosave_write()
        st.rerun()

    if c2.button("Saltar importación ➡️", type="secondary"):
        st.session_state.carrito_import = {}
        st.session_state.productos_procesados = []
        st.session_state.incidencias = []
        st.session_state.wizard_step = 4
        autosave_write()
        st.rerun()

    if c3.button("Procesar archivo ➡️", type="primary", disabled=(archivo is None)):
        with st.spinner("🔄 Procesando archivo..."):
            try:
                df_v = read_excel_any(archivo)

                if df_v.shape[1] < 2:
                    st.error("❌ El Excel debe tener al menos 2 columnas.")
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
                    st.error("❌ No se encontraron productos válidos en el archivo.")
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
                            "qty": int(row["qty"]),
                            "metodo": metodo
                        })
                        if ean in carrito_temp:
                            carrito_temp[ean]["qty"] += int(row["qty"])
                        else:
                            carrito_temp[ean] = {
                                "EAN": ean,
                                "Referencia": match_row["Referencia"],
                                "Nombre": match_row["Nombre"],
                                "Color": match_row["Color"],
                                "Talla": match_row["Talla"],
                                "qty": int(row["qty"])
                            }
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
                st.session_state.carrito_import = carrito_temp
                st.session_state.wizard_step = 4
                autosave_write()
                st.rerun()

            except Exception as e:
                st.error(f"❌ Error procesando el archivo: {e}")

    if st.session_state.incidencias:
        st.warning("Incidencias detectadas (no añadidas):")
        st.dataframe(pd.DataFrame(st.session_state.incidencias), use_container_width=True)

# =========================================================
# =========================================================
# PASO 4: Selección manual (GRID por referencia → color/talla)
# =========================================================
elif st.session_state.wizard_step == 4:
    asistente_mensaje("**4/5 — Selección manual**: elige una referencia y marca unidades por Color/Talla. (No se mezclan aún con importados).")

    st.markdown("### 🛒 Carrito Importado (solo lectura)")
    if st.session_state.carrito_import:
        df_imp = pd.DataFrame(st.session_state.carrito_import.values())
        cols_show = [c for c in ["Referencia", "Nombre", "Color", "Talla", "qty", "EAN"] if c in df_imp.columns]
        st.dataframe(df_imp[cols_show], use_container_width=True, hide_index=True)
    else:
        st.info("No hay productos importados.")

    st.markdown("---")
    st.markdown("### ➕ Añadir productos manualmente (rápido)")
    st.caption("1) Busca y elige una **Referencia** · 2) Ajusta cantidades en el **grid Color/Talla** · 3) Pulsa **Añadir al bloque manual**")

    # --- Búsqueda de referencias (no por EAN)
    colq1, colq2, colq3 = st.columns([3, 1, 1])
    with colq1:
        manual_query = st.text_input(
            "Buscar referencia o nombre (coincidencia parcial)",
            value=st.session_state.manual_query,
            key="ui_manual_query",
            placeholder="Ej: 2401 / VESTIDO / IBIZA / NEGRO ...",
        )
    with colq2:
        manual_limit = st.selectbox(
            "Refs a mostrar",
            [10, 20, 50, 100, 200],
            index=[10, 20, 50, 100, 200].index(int(st.session_state.manual_limit)) if int(st.session_state.manual_limit) in [10, 20, 50, 100, 200] else 0,
            key="ui_manual_limit",
        )
    with colq3:
        st.write("")  # alineación
        limpiar = st.button("Limpiar", use_container_width=True, key="btn_manual_clear")

    if limpiar:
        st.session_state.manual_query = ""
        st.session_state.manual_ref_selected = ""
        st.session_state.manual_grid_qty = {}
        autosave_write()
        st.rerun()

    st.session_state.manual_query = manual_query
    st.session_state.manual_limit = int(manual_limit)

    q = (manual_query or "").strip()
    d = df_cat.copy()
    for c in ["Referencia", "Nombre", "Color", "Talla", "EAN"]:
        if c in d.columns:
            d[c] = d[c].astype(str).fillna("")

    if q:
        q_cf = q.casefold()
        mask = (
            d["Referencia"].str.casefold().str.contains(q_cf, na=False)
            | d["Nombre"].str.casefold().str.contains(q_cf, na=False)
        )
        d_ref = d.loc[mask, ["Referencia", "Nombre"]].drop_duplicates().head(int(manual_limit))
    else:
        d_ref = d.loc[:, ["Referencia", "Nombre"]].drop_duplicates().head(int(manual_limit))

    refs = d_ref["Referencia"].astype(str).tolist()
    ref_labels = {
        r: f"{r} — {d_ref.loc[d_ref['Referencia'] == r, 'Nombre'].iloc[0]}" if not d_ref.loc[d_ref['Referencia'] == r, 'Nombre'].empty else r
        for r in refs
    }

    if not refs:
        st.warning("No hay referencias que mostrar con ese filtro.")
    else:
        default_ref = st.session_state.manual_ref_selected if st.session_state.manual_ref_selected in refs else refs[0]
        ref_sel = st.selectbox(
            "Referencia",
            options=refs,
            format_func=lambda r: ref_labels.get(r, r),
            index=refs.index(default_ref),
            key="ui_ref_sel",
        )
        st.session_state.manual_ref_selected = ref_sel

        # Subconjunto por referencia elegida
        sub = d[d["Referencia"].astype(str) == str(ref_sel)].copy()
        if sub.empty:
            st.error("No he podido localizar esa referencia en el catálogo.")
        else:
            # Orden de tallas: numéricas primero, luego XS/S/M/L...
            def talla_sort_key(t):
                tt = str(t).strip().upper()
                if re.fullmatch(r"\d{2,3}", tt):
                    return (0, int(tt))
                order = {"XXS": 1, "XS": 2, "S": 3, "M": 4, "L": 5, "XL": 6, "XXL": 7, "XXXL": 8, "TU": 9, "T.U.": 9, "U": 9, "UNICA": 9, "ÚNICA": 9}
                return (1, order.get(tt, 99), tt)

            colors = sorted(sub["Color"].dropna().astype(str).unique().tolist())
            tallas = sorted(sub["Talla"].dropna().astype(str).unique().tolist(), key=talla_sort_key)

            if not colors:
                colors = ["(sin color)"]
                sub["Color"] = "(sin color)"
            if not tallas:
                tallas = ["(sin talla)"]
                sub["Talla"] = "(sin talla)"

            st.markdown("#### Grid Color / Talla")
            st.caption("Usa + / − para ajustar. Las cantidades quedan en borrador hasta que pulses **Añadir al bloque manual**.")

            # cabecera
            header_cols = st.columns([1.3] + [1] * len(colors))
            header_cols[0].markdown("**Talla \\ Color**")
            for j, colr in enumerate(colors, start=1):
                header_cols[j].markdown(f"**{colr}**")

            # grid
            for tal in tallas:
                row_cols = st.columns([1.3] + [1] * len(colors))
                row_cols[0].markdown(f"**{tal}**")
                for j, colr in enumerate(colors, start=1):
                    cell = sub[(sub["Color"].astype(str) == str(colr)) & (sub["Talla"].astype(str) == str(tal))]
                    if cell.empty:
                        row_cols[j].markdown("—")
                        continue

                    # si hay más de un EAN para la misma celda, tomamos el primero
                    ean = str(cell.iloc[0]["EAN"]).strip()
                    qty = int(st.session_state.manual_grid_qty.get(ean, 0))

                    cmin, cqty, cplus = row_cols[j].columns([1, 1.2, 1])
                    if cmin.button("−", key=f"minus_{ean}"):
                        st.session_state.manual_grid_qty[ean] = max(0, qty - 1)
                        autosave_write()
                        st.rerun()
                    cqty.markdown(f"<div style='text-align:center; font-weight:700;'>{qty}</div>", unsafe_allow_html=True)
                    if cplus.button("+", key=f"plus_{ean}"):
                        st.session_state.manual_grid_qty[ean] = qty + 1
                        autosave_write()
                        st.rerun()

            st.markdown("---")
            cA, cB, cC = st.columns([1.2, 1.2, 2.6])

            with cA:
                if st.button("Poner a 0 (esta referencia)", use_container_width=True, key="btn_grid_reset"):
                    # limpia solo EANs de esta referencia
                    for ean in sub["EAN"].astype(str).tolist():
                        st.session_state.manual_grid_qty.pop(str(ean).strip(), None)
                    autosave_write()
                    st.rerun()

            with cB:
                if st.button("Añadir al bloque manual", type="primary", use_container_width=True, key="btn_grid_commit"):
                    added = 0
                    for _, r in sub.iterrows():
                        ean = str(r["EAN"]).strip()
                        qty = int(st.session_state.manual_grid_qty.get(ean, 0))
                        if qty <= 0:
                            continue

                        # añade al carrito manual (separado)
                        car = st.session_state.carrito_manual
                        if ean in car:
                            car[ean]["qty"] = int(car[ean].get("qty", 0)) + qty
                        else:
                            car[ean] = {
                                "EAN": ean,
                                "Referencia": str(r.get("Referencia", "")).strip(),
                                "Nombre": str(r.get("Nombre", "")).strip(),
                                "Color": str(r.get("Color", "")).strip(),
                                "Talla": str(r.get("Talla", "")).strip(),
                                "qty": qty,
                            }
                        st.session_state.carrito_manual = car
                        added += 1

                        # limpia el borrador de esa celda
                        st.session_state.manual_grid_qty.pop(ean, None)

                    autosave_write()
                    st.success(f"✅ Añadidas {added} combinaciones (Color/Talla) al bloque manual.")

            with cC:
                st.markdown("**Bloque manual (separado)**")
                if st.session_state.carrito_manual:
                    df_man = pd.DataFrame(st.session_state.carrito_manual.values())
                    cols_show = [c for c in ["Referencia", "Nombre", "Color", "Talla", "qty", "EAN"] if c in df_man.columns]
                    st.dataframe(df_man[cols_show], use_container_width=True, hide_index=True)
                else:
                    st.info("Aún no has añadido nada al bloque manual.")

    st.markdown("---")
    cnav1, cnav2, cnav3 = st.columns([1, 1, 2])
    with cnav1:
        if st.button("⬅️ Volver", key="btn_step4_back"):
            st.session_state.wizard_step = 3
            autosave_write()
            st.rerun()
    with cnav2:
        if st.button("Unir y revisar cantidades ➡️", type="primary", key="btn_step4_next"):
            st.session_state.wizard_step = 5
            autosave_write()
            st.rerun()

# PASO 5: Unión + cantidades definitivas + exportación
# =========================================================
elif st.session_state.wizard_step == 5:
    config = st.session_state.config
    asistente_mensaje("**5/5 — Revisión final**: se unen importados + manuales y ajustas cantidades definitivas.")

    # unir
    merged = {}
    for ean, it in (st.session_state.carrito_import or {}).items():
        merged[ean] = dict(it)
    for ean, it in (st.session_state.carrito_manual or {}).items():
        if ean in merged:
            merged[ean]["qty"] = int(merged[ean].get("qty",0)) + int(it.get("qty",0))
        else:
            merged[ean] = dict(it)

    if not merged:
        st.error("❌ No hay productos para exportar (ni importados ni manuales).")
    else:
        df = pd.DataFrame(merged.values())
        # ordenar
        cols = ["EAN","Referencia","Nombre","Color","Talla","qty"]
        for c in cols:
            if c not in df.columns:
                df[c] = ""
        df = df[cols].sort_values(["Referencia","Color","Talla"], kind="stable")

        st.markdown("### Cantidades definitivas (edita aquí)")
        df_edit = st.data_editor(df, num_rows="dynamic", use_container_width=True,
                                 column_config={"qty": st.column_config.NumberColumn("qty", min_value=0, step=1)})

        # reconstruir carrito_final
        carrito_final = {}
        for _, r in df_edit.iterrows():
            ean = str(r["EAN"]).strip()
            if not ean:
                continue
            try:
                qty = int(r["qty"])
            except Exception:
                qty = 0
            if qty <= 0:
                continue
            carrito_final[ean] = {
                "EAN": ean,
                "Referencia": str(r["Referencia"]),
                "Nombre": str(r["Nombre"]),
                "Color": str(r["Color"]),
                "Talla": str(r["Talla"]),
                "qty": qty
            }

        st.markdown("---")
        st.markdown("### Exportación")
        st.write(f"📅 Fecha: {config['fecha'].strftime('%d/%m/%Y')}")
        st.write(f"🏪 Pide: {config['destino']}")
        st.write(f"📦 Envía: {config['origen']}")
        st.write(f"🔖 Ref: {config['ref_peticion'] or 'Sin referencia'}")

        archivo_bytes, nombre = generar_archivo_peticion(
            carrito_final,
            config["fecha"],
            config["origen"],
            config["destino"],
            config["ref_peticion"]
        )
        st.download_button("⬇️ Descargar Excel", data=archivo_bytes, file_name=nombre,
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           type="primary")

    c1, c2 = st.columns([1,1])
    if c1.button("⬅️ Volver", type="secondary"):
        st.session_state.wizard_step = 4
        autosave_write()
        st.rerun()
    if c2.button("✅ Finalizar (limpiar guardado)", type="secondary"):
        autosave_clear()
        st.success("Guardado eliminado.")
