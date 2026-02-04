import streamlit as st
import pandas as pd
import os
import io
import json
from datetime import datetime
from openpyxl import load_workbook
from streamlit_local_storage import LocalStorage

# =========================================
# CONFIG
# =========================================
st.set_page_config(page_title="Peticiones", layout="wide")

LS_KEY = "peticiones_estado_v1"
localS = LocalStorage()


# =========================================
# LOCAL STORAGE (compatibilidad entre firmas)
# =========================================
def ls_get(item_key: str, ss_key: str) -> str | None:
    """
    Hace get del LocalStorage de forma compatible con varias firmas:
      - getItem(itemKey, key="ss_key")  (keyword)
      - getItem(itemKey, ss_key)        (2 posicionales)
      - getItem(itemKey) -> devuelve valor
    Devuelve siempre el string recuperado (o None).
    """
    # 1) Firma con keyword "key="
    try:
        out = localS.getItem(item_key, key=ss_key)
        # algunas versiones devuelven None pero escriben en session_state
        if ss_key in st.session_state and st.session_state[ss_key]:
            return st.session_state[ss_key]
        return out
    except TypeError:
        pass

    # 2) Firma con 2 posicionales
    try:
        out = localS.getItem(item_key, ss_key)
        if ss_key in st.session_state and st.session_state[ss_key]:
            return st.session_state[ss_key]
        return out
    except TypeError:
        pass

    # 3) Firma que devuelve directamente
    try:
        return localS.getItem(item_key)
    except TypeError:
        return None


def ls_set(item_key: str, value: str) -> None:
    localS.setItem(item_key, value)


# =========================================
# STATE HELPERS
# =========================================
def _serialize_state() -> dict:
    return {
        "carrito": st.session_state.get("carrito", {}),
        "fecha_str": st.session_state.get("fecha_str"),
        "origen": st.session_state.get("origen"),
        "destino": st.session_state.get("destino"),
        "ref_peticion": st.session_state.get("ref_peticion", ""),
    }


def _apply_state(payload: dict) -> None:
    if not isinstance(payload, dict):
        return

    st.session_state.carrito = payload.get("carrito", {}) or {}

    if payload.get("origen") is not None:
        st.session_state.origen = payload["origen"]
    if payload.get("destino") is not None:
        st.session_state.destino = payload["destino"]
    if payload.get("ref_peticion") is not None:
        st.session_state.ref_peticion = payload["ref_peticion"]
    if payload.get("fecha_str") is not None:
        st.session_state.fecha_str = payload["fecha_str"]


def mark_dirty() -> None:
    st.session_state["_dirty"] = True


# =========================================
# STYLE (tu CSS)
# =========================================
st.markdown(
    """
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
""",
    unsafe_allow_html=True,
)

# =========================================
# DATA HELPERS (robusto con columnas)
# =========================================
def _norm_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    low_map = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in low_map:
            return low_map[cand.lower()]
    # fallback por "contiene"
    for c in df.columns:
        cl = c.lower()
        for cand in candidates:
            if cand.lower() in cl:
                return c
    return None


def _clean_ean(x) -> str:
    if pd.isna(x):
        return ""
    s = str(x).strip()
    if s.lower() == "nan":
        return ""
    if s.endswith(".0"):
        s = s[:-2]
    return s.strip()


def _safe_int(x, default=1) -> int:
    try:
        if pd.isna(x):
            return default
        return int(float(x))
    except Exception:
        return default


# =========================================
# LOAD CATALOGUE
# =========================================
@st.cache_data
def load_catalogue(path: str = "catalogue.xlsx") -> tuple[pd.DataFrame | None, str | None]:
    if not os.path.exists(path):
        return None, f"No encuentro '{path}' en la carpeta de la app."

    try:
        df = pd.read_excel(path, engine="openpyxl")
        df = _norm_cols(df)

        ean_col = _find_col(df, ["EAN", "Ean", "codigo ean", "código ean", "ean code"])
        if not ean_col:
            return None, f"Catálogo leído, pero NO encuentro columna EAN. Columnas: {list(df.columns)}"

        df["EAN"] = df[ean_col].apply(_clean_ean)
        df = df[df["EAN"] != ""].copy()

        # Referencia
        ref_col = _find_col(df, ["Referencia", "ref", "reference"])
        if ref_col and ref_col != "Referencia":
            df["Referencia"] = df[ref_col].astype(str).str.strip()
        elif "Referencia" in df.columns:
            df["Referencia"] = df["Referencia"].astype(str).str.strip()
        else:
            df["Referencia"] = ""

        # Opcionales
        for opt in ["Nombre", "Color", "Talla", "Colección", "Categoría", "Familia"]:
            col = _find_col(df, [opt])
            if col and col != opt:
                df[opt] = df[col]
            if opt not in df.columns:
                df[opt] = ""

        # Campo de búsqueda
        df["search_blob"] = (
            df["EAN"].astype(str)
            + " "
            + df["Referencia"].astype(str)
            + " "
            + df["Nombre"].astype(str)
            + " "
            + df["Color"].astype(str)
            + " "
            + df["Talla"].astype(str)
        ).str.lower()

        return df, None
    except Exception as e:
        return None, f"Error leyendo catálogo: {e}"


# =========================================
# SESSION STATE INIT
# =========================================
st.session_state.setdefault("carrito", {})
st.session_state.setdefault("search_key", 0)
st.session_state.setdefault("_dirty", False)
st.session_state.setdefault("_hydrated", False)

st.session_state.setdefault("origen", "PET Almacén Badalona")
st.session_state.setdefault("destino", "PET T002 Marbella")
st.session_state.setdefault("ref_peticion", "")
st.session_state.setdefault("fecha_str", datetime.now().strftime("%Y-%m-%d"))


# =========================================
# HYDRATE ONCE FROM LOCALSTORAGE
# =========================================
if not st.session_state._hydrated:
    val = ls_get(LS_KEY, "__ls_payload")
    if val:
        try:
            _apply_state(json.loads(val))
        except Exception:
            pass
    st.session_state._hydrated = True


# =========================================
# UI
# =========================================
st.markdown('<div class="peticiones-title">Peticiones</div>', unsafe_allow_html=True)

# Diagnóstico útil (puedes dejarlo colapsado)
with st.expander("🛠️ Diagnóstico (si algo no carga)", expanded=False):
    st.write("Archivos en la carpeta actual:")
    try:
        st.code("\n".join(sorted(os.listdir("."))))
    except Exception as e:
        st.write(e)

df_cat, cat_err = load_catalogue("catalogue.xlsx")
if cat_err:
    st.error(cat_err)
    st.stop()

with st.expander("📚 Diagnóstico catálogo", expanded=False):
    st.write("Columnas detectadas:", list(df_cat.columns))
    st.dataframe(df_cat.head(10), use_container_width=True)

# 1) CABECERA
c1, c2, c3 = st.columns(3)

try:
    fecha_default = datetime.strptime(st.session_state.fecha_str, "%Y-%m-%d")
except Exception:
    fecha_default = datetime.now()
    st.session_state.fecha_str = fecha_default.strftime("%Y-%m-%d")

fecha = c1.date_input("FECHA", fecha_default, key="fecha_widget", on_change=mark_dirty)
st.session_state.fecha_str = fecha.strftime("%Y-%m-%d")

c2.selectbox("ORIGEN", ["PET Almacén Badalona", "ALM-CENTRAL"], key="origen", on_change=mark_dirty)
c3.selectbox("DESTINO", ["PET T002 Marbella", "ALM-TIENDA"], key="destino", on_change=mark_dirty)
st.text_input("REFERENCIA PETICIÓN", key="ref_peticion", on_change=mark_dirty)

fecha_str = st.session_state.fecha_str
origen = st.session_state.origen
destino = st.session_state.destino
ref_peticion = st.session_state.ref_peticion

st.write("---")

# 2) IMPORTADOR MASIVO
st.markdown('<div class="section-header">📂 IMPORTACIÓN DE VENTAS / REPOSICIÓN</div>', unsafe_allow_html=True)
archivo_v = st.file_uploader(
    "Sube el Excel con columnas EAN y Cantidad",
    type=["xlsx"],
    label_visibility="collapsed",
)

if archivo_v and st.button("CARGAR DATOS DEL EXCEL", type="primary"):
    try:
        df_v = pd.read_excel(archivo_v, engine="openpyxl")
        df_v = _norm_cols(df_v)

        ean_col = _find_col(df_v, ["EAN", "Ean", "codigo ean", "código ean", "ean code"])
        qty_col = _find_col(df_v, ["Cantidad", "cantidad", "qty", "quantity", "unidades", "uds"])

        if not ean_col:
            st.error(f"No encuentro columna EAN en el Excel subido. Columnas: {list(df_v.columns)}")
        else:
            if not qty_col:
                st.warning("No encuentro columna de Cantidad. Usaré 1 por fila.")
            added = 0
            for _, r in df_v.iterrows():
                ean_v = _clean_ean(r.get(ean_col))
                if not ean_v:
                    continue

                cant_v = _safe_int(r.get(qty_col), default=1) if qty_col else 1
                if cant_v <= 0:
                    continue

                match = df_cat[df_cat["EAN"] == ean_v]
                if not match.empty:
                    prod = match.iloc[0]
                    if ean_v in st.session_state.carrito:
                        st.session_state.carrito[ean_v]["Cantidad"] += cant_v
                    else:
                        st.session_state.carrito[ean_v] = {
                            "Ref": prod.get("Referencia", ""),
                            "Nom": prod.get("Nombre", ""),
                            "Col": prod.get("Color", "-"),
                            "Tal": prod.get("Talla", "-"),
                            "Cantidad": cant_v,
                        }
                    added += 1

            st.success(f"Importación OK. Líneas añadidas/actualizadas: {added}")
            mark_dirty()
            st.rerun()
    except Exception as e:
        st.error(f"No he podido leer el Excel subido: {e}")

# 3) BUSCADOR Y FILTROS
st.markdown('<div class="section-header">🔍 BUSCADOR MANUAL</div>', unsafe_allow_html=True)
f1, f2 = st.columns([2, 1])
busq_txt = f1.text_input("Buscar referencia, nombre o EAN...", key=f"busq_{st.session_state.search_key}")
limite = f2.selectbox(
    "Ver resultados:",
    [10, 25, 50, 100, 500],
    index=1,
    key=f"lim_{st.session_state.search_key}",
)

filtros_activos: dict[str, str] = {}
columnas_posibles = ["Colección", "Categoría", "Familia"]
columnas_reales = [c for c in columnas_posibles if c in df_cat.columns]

if columnas_reales:
    cols_f = st.columns(len(columnas_reales))
    for i, col in enumerate(columnas_reales):
        opciones = ["TODOS"] + sorted(
            [x for x in df_cat[col].dropna().astype(str).unique().tolist() if x.strip() != ""]
        )
        filtros_activos[col] = cols_f[i].selectbox(
            f"{col}", opciones, key=f"f_{col}_{st.session_state.search_key}"
        )

df_res = df_cat
needle = (busq_txt or "").strip().lower()
if needle:
    df_res = df_res[df_res["search_blob"].str.contains(needle, na=False)]

for col, val in filtros_activos.items():
    if val != "TODOS":
        df_res = df_res[df_res[col].astype(str) == str(val)]

if needle or any(v != "TODOS" for v in filtros_activos.values()):
    st.markdown(
        f"<div style='background: #000; color: #fff; padding: 4px; font-size: 0.7rem; text-align: center;'>{len(df_res)} COINCIDENCIAS</div>",
        unsafe_allow_html=True,
    )

    for _, f in df_res.head(limite).iterrows():
        ean = str(f["EAN"]).strip()
        en_car = ean in st.session_state.carrito

        st.markdown('<div class="table-row">', unsafe_allow_html=True)
        c1r, c2r = st.columns([3, 1.5])

        with c1r:
            st.markdown(
                f"<div class='cell-content'><strong>{f.get('Referencia','')}</strong><br>"
                f"<small>{f.get('Nombre','')} ({f.get('Color','-')} / {f.get('Talla','-')})</small></div>",
                unsafe_allow_html=True,
            )

        with c2r:
            label = f"OK ({st.session_state.carrito[ean]['Cantidad']})" if en_car else "AÑADIR"
            if st.button(label, key=f"b_{ean}", type="primary" if en_car else "secondary"):
                if en_car:
                    st.session_state.carrito[ean]["Cantidad"] += 1
                else:
                    st.session_state.carrito[ean] = {
                        "Ref": f.get("Referencia", ""),
                        "Nom": f.get("Nombre", ""),
                        "Col": f.get("Color", "-"),
                        "Tal": f.get("Talla", "-"),
                        "Cantidad": 1,
                    }
                mark_dirty()
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

# 4) LISTA FINAL Y GENERACIÓN
if st.session_state.carrito:
    st.write("---")
    st.markdown('<div class="section-header">📋 LISTA DE REPOSICIÓN</div>', unsafe_allow_html=True)

    for ean, item in list(st.session_state.carrito.items()):
        st.markdown('<div class="table-row">', unsafe_allow_html=True)
        ca, cb, cc = st.columns([2.5, 1.2, 0.8])

        with ca:
            st.markdown(
                f"<div class='cell-content'><strong>{item.get('Ref','')}</strong><br><small>{item.get('Nom','')}</small></div>",
                unsafe_allow_html=True,
            )

        with cb:
            new_qty = st.number_input(
                "C",
                1,
                9999,
                int(item.get("Cantidad", 1)),
                key=f"q_{ean}",
                label_visibility="collapsed",
                on_change=mark_dirty,
            )
            item["Cantidad"] = int(new_qty)

        with cc:
            if st.button("✕", key=f"d_{ean}"):
                del st.session_state.carrito[ean]
                mark_dirty()
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

    uds = sum(int(it.get("Cantidad", 0)) for it in st.session_state.carrito.values())
    st.markdown(
        f'<div class="summary-box"><div>PIEZAS: {uds}</div><div>MODELOS: {len(st.session_state.carrito)}</div><div>DESTINO: {destino}</div></div>',
        unsafe_allow_html=True,
    )

    cv, cg = st.columns([1, 2])

    if cv.button("LIMPIAR TODO"):
        st.session_state.carrito = {}
        st.session_state.search_key += 1
        mark_dirty()
        st.rerun()

    if cv.button("🧹 OLVIDAR EN ESTE NAVEGADOR"):
        ls_set(LS_KEY, json.dumps({"carrito": {}, "ref_peticion": ""}))
        st.session_state.carrito = {}
        st.session_state.ref_peticion = ""
        st.session_state._dirty = False
        st.rerun()

    if cg.button("GENERAR Y DESCARGAR EXCEL", type="primary"):
        try:
            # Plantilla opcional
            if os.path.exists("peticion.xlsx"):
                with open("peticion.xlsx", "rb") as f:
                    tpl_bytes = f.read()
                wb = load_workbook(io.BytesIO(tpl_bytes))
                ws = wb.active
            else:
                from openpyxl import Workbook

                wb = Workbook()
                ws = wb.active
                ws.append(["Fecha", "Origen", "Destino", "Referencia", "EAN", "Cantidad"])

            for ean, it in st.session_state.carrito.items():
                ws.append([fecha_str, origen, destino, ref_peticion, ean, int(it["Cantidad"])])

            out = io.BytesIO()
            wb.save(out)
            out.seek(0)

            st.download_button(
                "📥 GUARDAR ARCHIVO REPO",
                out.getvalue(),
                file_name=f"REPO_{destino}.xlsx",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"No he podido generar el Excel: {e}")

# =========================================
# SAVE TO LOCAL STORAGE IF DIRTY
# =========================================
if st.session_state._dirty:
    try:
        payload = _serialize_state()
        ls_set(LS_KEY, json.dumps(payload))
        st.session_state._dirty = False
    except Exception:
        st.session_state._dirty = False
```0
