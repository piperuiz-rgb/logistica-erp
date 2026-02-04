import streamlit as st
import pandas as pd
import os
import io
import json
import re
from datetime import datetime
from openpyxl import load_workbook
from streamlit_local_storage import LocalStorage

# =========================================================
# CONFIG
# =========================================================
st.set_page_config(page_title="Peticiones · Charo Ruiz", layout="wide")

LS_KEY = "peticiones_estado_v1"
localS = LocalStorage()

# =========================================================
# LOCAL STORAGE (compatibilidad)
# =========================================================
def ls_get(item_key: str, ss_key: str):
    try:
        return localS.getItem(item_key, key=ss_key)
    except TypeError:
        try:
            return localS.getItem(item_key, ss_key)
        except TypeError:
            try:
                return localS.getItem(item_key)
            except TypeError:
                return None


def ls_set(item_key: str, value: str):
    localS.setItem(item_key, value)


# =========================================================
# CSS · LOOK CHARO RUIZ
# =========================================================
st.markdown("""
<style>
html, body, .stApp {
  background: #FFFFFF !important;
  color: #111111 !important;
  font-family: ui-serif, Georgia, "Times New Roman", serif !important;
}

.main .block-container {
  padding-top: 2rem;
  padding-bottom: 3rem;
  max-width: 1200px;
}

#MainMenu, footer, header { visibility: hidden; }

.peticiones-title {
  font-size: 2.6rem;
  font-weight: 700;
  letter-spacing: 0.03em;
  margin-bottom: 10px;
  border-bottom: 1px solid rgba(0,0,0,0.15);
  padding-bottom: 12px;
}

.subtitle {
  font-size: 0.9rem;
  letter-spacing: 0.15em;
  color: rgba(0,0,0,0.55);
  margin-bottom: 30px;
}

.section-header {
  font-size: 0.75rem;
  letter-spacing: 0.18em;
  font-weight: 700;
  text-transform: uppercase;
  margin-top: 30px;
  margin-bottom: 12px;
}

.section-header::after {
  content: "";
  display: block;
  height: 1px;
  background: rgba(0,0,0,0.15);
  margin-top: 8px;
}

.table-row {
  border: 1px solid rgba(0,0,0,0.12);
  border-radius: 14px;
  margin: 10px 0;
  box-shadow: 0 6px 18px rgba(0,0,0,0.04);
}

.cell-content {
  padding: 12px 14px;
}

.stButton>button {
  border-radius: 12px !important;
  height: 44px;
  font-size: 0.7rem !important;
  letter-spacing: 0.12em;
  font-weight: 700;
}

.stButton>button[kind="primary"] {
  background: linear-gradient(135deg, #0B2D5B, #123B73) !important;
  color: white !important;
  border: none !important;
}

.summary-box {
  background: #FAF7F2;
  border-radius: 16px;
  padding: 16px;
  margin-top: 20px;
  font-weight: 700;
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# UTILIDADES
# =========================================================
TALLA_MAP = {
    "xs": "xs", "s": "s", "m": "m", "l": "l", "xl": "xl",
    "xxl": "xxl", "xxxl": "xxxl",
    "x-small": "xs", "small": "s", "medium": "m",
    "large": "l", "x-large": "xl"
}

def norm_txt(x):
    if x is None:
        return ""
    return re.sub(r"\s+", " ", str(x).strip().lower())

def norm_talla(x):
    t = norm_txt(x)
    return TALLA_MAP.get(t, t)

def norm_color(x):
    return norm_txt(x)

def looks_like_talla(x):
    return norm_talla(x) in TALLA_MAP.values()

def read_excel_any(f):
    try:
        return pd.read_excel(f, engine="openpyxl")
    except Exception:
        return pd.read_excel(f, engine="xlrd")

def parse_producto_linea(txt):
    if not isinstance(txt, str):
        return None, None, None, 0

    ref_m = re.search(r"\[(.*?)\]", txt)
    par_m = re.search(r"\((.*?)\)$", txt)

    if not ref_m or not par_m:
        return None, None, None, 0

    ref = ref_m.group(1).strip()
    inside = par_m.group(1)

    if "," in inside:
        a1, a2 = inside.rsplit(",", 1)
        return ref, a1.strip(), a2.strip(), 2

    return ref, inside.strip(), None, 1

# =========================================================
# CATÁLOGO
# =========================================================
@st.cache_data
def load_catalogue():
    df = pd.read_excel("catalogue.xlsx", engine="openpyxl")
    df["EAN"] = df["EAN"].astype(str).str.replace(".0", "", regex=False)
    df["ref_n"] = df["Referencia"].apply(norm_txt)
    df["color_n"] = df["Color"].apply(norm_color)
    df["talla_n"] = df["Talla"].apply(norm_talla)
    return df

def build_indexes(df):
    exact, ref_color, ref_talla = {}, {}, {}

    for _, r in df.iterrows():
        row = r.to_dict()
        exact.setdefault((r.ref_n, r.color_n, r.talla_n), []).append(row)
        ref_color.setdefault((r.ref_n, r.color_n), []).append(row)
        ref_talla.setdefault((r.ref_n, r.talla_n), []).append(row)

    return exact, ref_color, ref_talla

def pick_unique(rows):
    if not rows:
        return None, "NO_ENCONTRADO"
    if len(rows) > 1:
        return None, "AMBIGUO"
    if not rows[0].get("EAN"):
        return None, "SIN_EAN"
    return rows[0], None

def match_producto(ref, a1, a2, n, exact, rc, rt):
    ref_n = norm_txt(ref)

    if n == 2:
        return pick_unique(exact.get((ref_n, norm_color(a1), norm_talla(a2)), []))

    if n == 1:
        if looks_like_talla(a1):
            return pick_unique(rt.get((ref_n, norm_talla(a1)), []))
        return pick_unique(rc.get((ref_n, norm_color(a1)), []))

    return None, "NO_ENCONTRADO"

# =========================================================
# APP
# =========================================================
df_cat = load_catalogue()
idx_exact, idx_ref_color, idx_ref_talla = build_indexes(df_cat)

st.session_state.setdefault("carrito", {})

st.markdown('<div class="peticiones-title">Peticiones</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">CHARO RUIZ · Logistics Request</div>', unsafe_allow_html=True)

st.markdown('<div class="section-header">Importar ventas / reposición</div>', unsafe_allow_html=True)

file = st.file_uploader("Excel TPV", type=["xlsx", "xls"])

if file and st.button("Inyectar al carrito", type="primary"):
    df = read_excel_any(file)
    prod = df.iloc[:, 0]
    qty = pd.to_numeric(df.iloc[:, 1], errors="coerce").fillna(0).astype(int)

    for p, q in zip(prod, qty):
        ref, a1, a2, n = parse_producto_linea(p)
        if not ref or q <= 0:
            continue

        row, err = match_producto(ref, a1, a2, n, idx_exact, idx_ref_color, idx_ref_talla)
        if row:
            ean = row["EAN"]
            st.session_state.carrito.setdefault(ean, {
                "Ref": row["Referencia"],
                "Nom": row["Nombre"],
                "Cantidad": 0
            })
            st.session_state.carrito[ean]["Cantidad"] += q

st.markdown('<div class="section-header">Carrito</div>', unsafe_allow_html=True)

for ean, it in st.session_state.carrito.items():
    st.markdown(f"""
    <div class="table-row">
        <div class="cell-content">
            <strong>{it['Ref']}</strong><br>
            {it['Nom']} · {it['Cantidad']} uds
        </div>
    </div>
    """, unsafe_allow_html=True)

if st.session_state.carrito:
    st.markdown('<div class="summary-box">Pedido listo para exportar</div>', unsafe_allow_html=True)
