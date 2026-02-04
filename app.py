import streamlit as st
import pandas as pd
import os
import re
from datetime import datetime

# =========================
# CONFIGURACIÓN Y ESTILOS
# =========================
st.set_page_config(page_title="Peticiones RGB", layout="wide")

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
    unsafe_allow_html=True
)

# =========================
# HELPERS
# =========================
def normalize_ean(x) -> str:
    """
    Normaliza EAN a SOLO DÍGITOS.
    Maneja floats, notación científica, espacios, guiones, etc.
    """
    if pd.isna(x):
        return ""
    s = str(x).strip()

    # Caso típico: 1234567890123.0
    s = s.replace(".0", "")

    # Caso notación científica tipo 8.41423E+12
    # Intentamos convertir a int si parece numérico
    try:
        if re.fullmatch(r"[-+]?(\d+(\.\d+)?([eE][-+]?\d+)?)", s):
            s = str(int(float(s)))
    except:
        pass

    # Solo dígitos
    s = re.sub(r"\D", "", s)
    return s

@st.cache_data
def get_catalogue():
    if not os.path.exists("catalogue.xlsx"):
        return None
    df = pd.read_excel("catalogue.xlsx", engine="openpyxl")
    df.columns = [str(c).strip() for c in df.columns]
    if "EAN" not in df.columns:
        return None

    df["EAN_NORM"] = df["EAN"].apply(normalize_ean)
    return df

# =========================
# ESTADO
# =========================
if "carrito" not in st.session_state:
    st.session_state.carrito = {}
if "search_key" not in st.session_state:
    st.session_state.search_key = 0

df_cat = get_catalogue()

# =========================
# UI
# =========================
tab1, tab2 = st.tabs(["🛒 GESTIÓN DE PETICIONES", "🔄 CONVERSOR GEXTIA"])

with tab1:
    st.markdown('<div class="peticiones-title">Peticiones</div>', unsafe_allow_html=True)

    if df_cat is None:
        st.error("No se ha podido cargar 'catalogue.xlsx' o no contiene columna EAN.")
        st.stop()

    # 1. CABECERA LOGÍSTICA
    c1, c2, c3 = st.columns(3)
    fecha_str = c1.date_input("FECHA", datetime.now()).strftime("%Y-%m-%d")
    origen = c2.selectbox("ORIGEN", [
        "PET Almacén Badalona", "PET Almacén Ibiza", "PET T001Ibiza",
        "PET T002 Marbella", "PET T004 Madrid", "PET Almacén Portugal"
    ])
    destino = c3.selectbox("DESTINO", [
        "PET Almacén Badalona", "PET Almacén Ibiza", "PET T001Ibiza",
        "PET T002 Marbella", "PET T004 Madrid", "PET Almacén Portugal"
    ])
    ref_peticion = st.text_input("REFERENCIA PETICIÓN")

    same_wh = (origen == destino)
    if same_wh:
        st.warning("⚠️ El almacén de ORIGEN y DESTINO son el mismo. Cambia uno para poder cargar/generar la petición.")

    st.write("---")

    # 2. IMPORTADOR MASIVO (ROBUSTO)
    st.markdown('<div class="section-header">📂 IMPORTACIÓN DE VENTAS / REPOSICIÓN</div>', unsafe_allow_html=True)
    archivo_v = st.file_uploader("Sube el Excel con columnas EAN y Cantidad", type=["xlsx"], label_visibility="collapsed", key="u1")

    if archivo_v and st.button("CARGAR DATOS DEL EXCEL", type="primary", key="b1", disabled=same_wh):
        df_v = pd.read_excel(archivo_v)
        df_v.columns = [str(c).strip() for c in df_v.columns]

        if "EAN" not in df_v.columns:
            st.error(f"El Excel no tiene columna 'EAN'. Columnas detectadas: {list(df_v.columns)}")
            st.stop()

        # Normalizamos EANs del Excel
        df_v["EAN_NORM"] = df_v["EAN"].apply(normalize_ean)

        # Creamos diccionario del catálogo para match rápido
        cat_map = {}
        for _, r in df_cat.iterrows():
            e = r.get("EAN_NORM", "")
            if e:
                cat_map[e] = r  # si hay duplicados, se queda el último

        added_lines = 0
        added_units = 0
        not_found = 0
        not_found_samples = []

        for _, f_v in df_v.iterrows():
            ean_norm = f_v.get("EAN_NORM", "")
            if not ean_norm:
                continue

            try:
                cant_v = int(f_v.get("Cantidad", 1) or 1)
            except:
                cant_v = 1

            if cant_v == 0:
                continue

            prod = cat_map.get(ean_norm)
            if prod is None:
                not_found += 1
                if len(not_found_samples) < 10:
                    not_found_samples.append(ean_norm)
                continue

            key = ean_norm  # usamos EAN normalizado como clave del carrito

            if key in st.session_state.carrito:
                st.session_state.carrito[key]["Cantidad"] += cant_v
            else:
                st.session_state.carrito[key] = {
                    "Ref": prod.get("Referencia", ""),
                    "Nom": prod.get("Nombre", ""),
                    "Col": prod.get("Color", "-"),
                    "Tal": prod.get("Talla", "-"),
                    "Cantidad": cant_v,
                }

            added_lines += 1
            added_units += cant_v

        # Feedback MUY claro
        if added_lines == 0:
            st.error("❌ No se ha añadido ningún producto al carrito. Revisa coincidencias EAN vs catálogo.")
            st.info(f"Ejemplos EAN (Excel normalizado): {df_v['EAN_NORM'].dropna().astype(str).head(10).tolist()}")
            st.info(f"Ejemplos EAN (Catálogo normalizado): {df_cat['EAN_NORM'].dropna().astype(str).head(10).tolist()}")
        else:
            st.success(f"✅ Añadidas/actualizadas {added_lines} líneas ({added_units} unidades) al carrito.")

        if not_found > 0:
            st.warning(f"⚠️ {not_found} EAN no encontrados en catálogo. Ejemplos: {not_found_samples}")

        st.rerun()

    # 3. BUSCADOR (igual que antes)
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
        st.markdown(
            f"<div style='background: #000; color: #fff; padding: 4px; font-size: 0.7rem; text-align: center;'>{len(df_res)} COINCIDENCIAS</div>",
            unsafe_allow_html=True
        )

        for _, f in df_res.head(limite).iterrows():
            ean_norm = f.get("EAN_NORM", "")
            en_car = ean_norm in st.session_state.carrito

            st.markdown('<div class="table-row">', unsafe_allow_html=True)
            c1_res, c2_res = st.columns([3, 1.5])

            with c1_res:
                st.markdown(
                    f"<div class='cell-content'><strong>{f.get('Referencia','')}</strong><br>"
                    f"<small>{f.get('Nombre','')} ({f.get('Color','-')} / {f.get('Talla','-')})</small><br>"
                    f"<small>EAN: {f.get('EAN','')}</small></div>",
                    unsafe_allow_html=True
                )

            with c2_res:
                label = f"OK ({st.session_state.carrito[ean_norm]['Cantidad']})" if en_car else "AÑADIR"
                if st.button(label, key=f"b_{ean_norm}", type="primary" if en_car else "secondary"):
                    if en_car:
                        st.session_state.carrito[ean_norm]["Cantidad"] += 1
                    else:
                        st.session_state.carrito[ean_norm] = {
                            "Ref": f.get("Referencia", ""),
                            "Nom": f.get("Nombre", ""),
                            "Col": f.get("Color", "-"),
                            "Tal": f.get("Talla", "-"),
                            "Cantidad": 1,
                        }
                    st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)

    # 4. CARRITO
    if st.session_state.carrito:
        st.write("---")
        st.markdown('<div class="section-header">📋 LISTA DE REPOSICIÓN</div>', unsafe_allow_html=True)

        total_lineas = len(st.session_state.carrito)
        total_unidades = sum(int(v.get("Cantidad", 0)) for v in st.session_state.carrito.values())
        st.markdown(
            f"<div class='summary-box'><div>Líneas: {total_lineas}</div><div>Unidades: {total_unidades}</div></div>",
            unsafe_allow_html=True
        )

        for ean, item in list(st.session_state.carrito.items()):
            st.markdown('<div class="table-row">', unsafe_allow_html=True)
            ca, cb, cc = st.columns([3, 1, 0.5])

            with ca:
                st.markdown(
                    f"<div class='cell-content'>"
                    f"<strong>{item.get('Ref','')}</strong><br>"
                    f"<small>{item.get('Nom','')} ({item.get('Col','-')} / {item.get('Tal','-')})</small><br>"
                    f"<small>EAN: {ean}</small>"
                    f"</div>",
                    unsafe_allow_html=True
                )

            with cb:
                new_qty = st.number_input(
                    "Cantidad",
                    min_value=0,
                    value=int(item.get("Cantidad", 0)),
                    step=1,
                    key=f"qty_{ean}",
                    label_visibility="collapsed",
                )
                st.session_state.carrito[ean]["Cantidad"] = int(new_qty)

            with cc:
                if st.button("🗑️", key=f"del_{ean}", type="secondary"):
                    st.session_state.carrito.pop(ean, None)
                    st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)

        st.write("---")
        cA, cB = st.columns([1, 1])
        with cA:
            if st.button("VACIAR CARRITO", type="secondary"):
                st.session_state.carrito = {}
                st.rerun()
        with cB:
            if st.button("GENERAR PETICIÓN", type="primary", disabled=same_wh):
                if same_wh:
                    st.error("No puedes generar una petición con el mismo origen y destino.")
                    st.stop()
                st.success("Petición generada (placeholder).")

    else:
        st.info("El carrito está vacío.")

with tab2:
    st.markdown('<div class="peticiones-title">Conversor Gextia</div>', unsafe_allow_html=True)
    st.info("Aquí iría tu conversor. (No se ha modificado en esta versión.)")
