import streamlit as st
import pandas as pd
import os
import io
import json
from datetime import datetime
from openpyxl import load_workbook
from streamlit_local_storage import LocalStorage

st.set_page_config(page_title="Peticiones", layout="wide")

# =========================
#  LOCAL STORAGE (persistencia ante F5)
# =========================
LS_KEY = "peticiones_estado_v1"
localS = LocalStorage()


def _serialize_state():
    return {
        "carrito": st.session_state.get("carrito", {}),
        "fecha_str": st.session_state.get("fecha_str"),
        "origen": st.session_state.get("origen"),
        "destino": st.session_state.get("destino"),
        "ref_peticion": st.session_state.get("ref_peticion", ""),
    }


def _apply_state(payload: dict):
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


def mark_dirty():
    st.session_state["_dirty"] = True


# =========================
#  ESTILO
# =========================
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

# =========================
#  CATALOGO
# =========================
@st.cache_data
def get_catalogue():
    if not os.path.exists("catalogue.xlsx"):
        return None
    try:
        df = pd.read_excel("catalogue.xlsx", engine="openpyxl")
        if "EAN" not in df.columns:
            return None
        df["EAN"] = df["EAN"].astype(str).str.replace(".0", "", regex=False).str.strip()
        return df
    except Exception:
        return None


df_cat = get_catalogue()

# =========================
#  SESSION STATE INIT
# =========================
if "carrito" not in st.session_state:
    st.session_state.carrito = {}
if "search_key" not in st.session_state:
    st.session_state.search_key = 0
if "_dirty" not in st.session_state:
    st.session_state._dirty = False
if "_hydrated" not in st.session_state:
    st.session_state._hydrated = False

# Defaults de cabecera (por si no viene nada del LocalStorage)
if "origen" not in st.session_state:
    st.session_state.origen = "PET Almacén Badalona"
if "destino" not in st.session_state:
    st.session_state.destino = "PET T002 Marbella"
if "ref_peticion" not in st.session_state:
    st.session_state.ref_peticion = ""
if "fecha_str" not in st.session_state:
    st.session_state.fecha_str = datetime.now().strftime("%Y-%m-%d")

# =========================
#  HIDRATAR DESDE LOCAL STORAGE (1 vez)
# =========================
if not st.session_state._hydrated:
    # Vuelca el valor en st.session_state["__ls_payload"]
    localS.getItem(LS_KEY, key="__ls_payload")
    if "__ls_payload" in st.session_state and st.session_state["__ls_payload"]:
        try:
            payload = json.loads(st.session_state["__ls_payload"])
            _apply_state(payload)
        except Exception:
            pass
    st.session_state._hydrated = True

# =========================
#  UI
# =========================
st.markdown('<div class="peticiones-title">Peticiones</div>', unsafe_allow_html=True)

if df_cat is None:
    st.error("Error: Asegúrate de tener el archivo 'catalogue.xlsx' en la carpeta y que tenga columna 'EAN'.")
    st.stop()

# 1) CABECERA LOGÍSTICA (persistente)
c1, c2, c3 = st.columns(3)

# FECHA: guardamos como string ISO en session_state
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
        if "EAN" not in df_v.columns:
            st.error("El Excel subido debe tener una columna 'EAN'.")
        else:
            # Cantidad puede no existir: default 1
            for _, f_v in df_v.iterrows():
                ean_v = str(f_v.get("EAN", "")).replace(".0", "").strip()
                if not ean_v:
                    continue

                # Cantidad robusta
                raw_qty = f_v.get("Cantidad", 1)
                try:
                    cant_v = int(raw_qty) if pd.notna(raw_qty) else 1
                except Exception:
                    cant_v = 1
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
            mark_dirty()
            st.rerun()
    except Exception as e:
        st.error(f"No he podido leer el Excel: {e}")

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

filtros_activos = {}
columnas_posibles = ["Colección", "Categoría", "Familia"]
columnas_reales = [c for c in columnas_posibles if c in df_cat.columns]

if columnas_reales:
    cols_f = st.columns(len(columnas_reales))
    for i, col in enumerate(columnas_reales):
        opciones = ["TODOS"] + sorted(df_cat[col].dropna().unique().tolist())
        filtros_activos[col] = cols_f[i].selectbox(
            f"{col}", opciones, key=f"f_{col}_{st.session_state.search_key}"
        )

df_res = df_cat.copy()
if busq_txt:
    # Búsqueda simple (mantengo tu lógica), pero más robusta a nulos
    needle = busq_txt.lower().strip()
    df_res = df_res[df_res.apply(lambda row: needle in " ".join(map(lambda x: str(x).lower(), row.values)), axis=1)]

for col, val in filtros_activos.items():
    if val != "TODOS":
        df_res = df_res[df_res[col] == val]

if busq_txt or any(v != "TODOS" for v in filtros_activos.values()):
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
                f"<div class='cell-content'><strong>{f.get('Referencia','')}</strong><br><small>{f.get('Nombre','')} ({f.get('Color','-')} / {f.get('Talla','-')})</small></div>",
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

    # Pintar items
    for ean, item in list(st.session_state.carrito.items()):
        st.markdown('<div class="table-row">', unsafe_allow_html=True)
        ca, cb, cc = st.columns([2.5, 1.2, 0.8])

        with ca:
            st.markdown(
                f"<div class='cell-content'><strong>{item.get('Ref','')}</strong><br><small>{item.get('Nom','')}</small></div>",
                unsafe_allow_html=True,
            )

        with cb:
            # Si cambia cantidad, marcamos dirty
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

    # Botón opcional: borrar también el estado persistido en ESTE navegador
    if cv.button("🧹 OLVIDAR EN ESTE NAVEGADOR"):
        localS.setItem(LS_KEY, json.dumps({"carrito": {}, "ref_peticion": ""}))
        st.session_state.carrito = {}
        st.session_state.ref_peticion = ""
        st.session_state._dirty = False
        st.rerun()

    # Generar Excel (en memoria) partiendo de una plantilla si existe
    if cg.button("GENERAR Y DESCARGAR EXCEL", type="primary"):
        try:
            # Si hay plantilla, la usamos; si no, creamos workbook nuevo "simple"
            if os.path.exists("peticion.xlsx"):
                with open("peticion.xlsx", "rb") as f:
                    tpl_bytes = f.read()
                wb = load_workbook(io.BytesIO(tpl_bytes))
                ws = wb.active
            else:
                # fallback: workbook nuevo (sin formato)
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

# =========================
#  GUARDAR ESTADO EN LOCAL STORAGE SI HUBO CAMBIOS
# =========================
if st.session_state._dirty:
    try:
        payload = _serialize_state()
        localS.setItem(LS_KEY, json.dumps(payload))
        st.session_state._dirty = False
    except Exception:
        # Si falla localStorage por algún motivo, no bloqueamos la app
        st.session_state._dirty = False
```0
