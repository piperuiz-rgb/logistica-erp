# =========================
# streamlit_app.py (GUIADO v2)
# - Almacenes sin renombrar (texto libre + sugerencias)
# - Importador: detección flexible de columnas
# - Manual: buscador por ref/nombre/EAN/color/talla + botón "Buscar selección"
# - Manual: lote por referencias con botón (sin Ctrl+Enter)
# - Autosave para no perder progreso
# =========================

import io
import json
import os
import re
from datetime import date, datetime

import pandas as pd
import streamlit as st


APP_TITLE = "Asistente de Peticiones a Almacén"
AUTOSAVE_FILE = ".autosave_peticion.json"


# -------------------------
# Normalización / matching (Py3.9 safe)
# -------------------------
def norm_txt(x):
    if x is None:
        return ""
    return re.sub(r"\s+", " ", str(x)).strip().upper()


def norm_color(x):
    return norm_txt(x)


def norm_talla(x):
    return norm_txt(x)


def looks_like_talla(token):
    t = norm_txt(token)
    if re.fullmatch(r"\d{2,3}", t):
        return True
    if t in {"XS", "S", "M", "L", "XL", "XXL", "XXXL", "T.U.", "TU", "U", "UNICA", "ÚNICA"}:
        return True
    return False


def build_indexes(df_cat):
    """
    Crea índices para buscar por:
      - ref+color+talla
      - ref+color
      - ref+talla
    """
    exact = {}
    ref_color = {}
    ref_talla = {}

    def add(d, key, row):
        d.setdefault(key, []).append(row)

    for _, r in df_cat.iterrows():
        row = {
            "EAN": str(r.get("EAN", "")).strip(),
            "Referencia": str(r.get("Referencia", "")).strip(),
            "Nombre": str(r.get("Nombre", "")).strip(),
            "Color": str(r.get("Color", "")).strip(),
            "Talla": str(r.get("Talla", "")).strip(),
            "ref_n": norm_txt(r.get("Referencia", "")),
            "color_n": norm_color(r.get("Color", "")),
            "talla_n": norm_talla(r.get("Talla", "")),
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
        return row, err, "EXACTO ref+color+talla"

    if n_attrs == 1 and a1:
        token = str(a1).strip()
        if looks_like_talla(token):
            talla_n = norm_talla(token)
            row, err = pick_unique(idx_ref_talla.get((ref_n, talla_n), []))
            return row, err, "ref+talla"
        color_n = norm_color(token)
        row, err = pick_unique(idx_ref_color.get((ref_n, color_n), []))
        return row, err, "ref+color"

    return None, "NO_ENCONTRADO", "sin atributos"


# -------------------------
# Catálogo
# -------------------------
def load_catalogue(path="catalogue.xlsx"):
    if not os.path.exists(path):
        st.error("❌ No encuentro el catálogo: {} (debe estar en la raíz del repo)".format(path))
        st.stop()

    df = pd.read_excel(path, engine="openpyxl")

    # Normaliza nombres típicos
    rename = {}
    for c in df.columns:
        cu = norm_txt(c)
        if cu in {"REF", "REFERENCIA", "REFERENCE", "SKU"}:
            rename[c] = "Referencia"
        elif cu in {"EAN", "CODIGO", "CÓDIGO", "BARCODE"}:
            rename[c] = "EAN"
        elif cu in {"NOMBRE", "NAME", "DESCRIPCION", "DESCRIPCIÓN"}:
            rename[c] = "Nombre"
        elif cu in {"COLOR", "COL"}:
            rename[c] = "Color"
        elif cu in {"TALLA", "TALLAS", "SIZE", "TAL"}:
            rename[c] = "Talla"
    df = df.rename(columns=rename)

    required = ["Referencia", "EAN", "Nombre", "Color", "Talla"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        st.error("❌ Al catálogo le faltan columnas: {}".format(", ".join(missing)))
        st.stop()

    # Limpieza
    df["Referencia"] = df["Referencia"].astype(str).str.strip()
    df["EAN"] = df["EAN"].astype(str).str.strip()
    df["Nombre"] = df["Nombre"].astype(str).fillna("").str.strip()
    df["Color"] = df["Color"].astype(str).fillna("").str.strip()
    df["Talla"] = df["Talla"].astype(str).fillna("").str.strip()

    return df


# -------------------------
# Importación (opcional) - detección flexible de columnas
# -------------------------
def _find_col_by_keywords(df, keywords):
    """
    Devuelve la primera columna cuyo nombre (normalizado) CONTENGA alguno de keywords.
    keywords: lista de strings ya normalizados (p.ej. ["REF", "REFERENCIA"])
    """
    cols = list(df.columns)
    norm_map = {c: norm_txt(c) for c in cols}
    for c in cols:
        cu = norm_map[c]
        for kw in keywords:
            if kw in cu:
                return c
    return None


def parse_import_file(uploaded_file):
    """
    Acepta Excel con al menos referencia y cantidad.
    - Detecta columnas por "contiene" (no por igualdad exacta).
    - Si la ref viene como "REF (COLOR)" o "REF (TALLA)" intenta usar 1 atributo.
    """
    name = (uploaded_file.name or "").lower()

    if name.endswith(".xlsx"):
        df = pd.read_excel(uploaded_file, engine="openpyxl")
    elif name.endswith(".xls"):
        # si falla en cloud, convertir a .xlsx
        df = pd.read_excel(uploaded_file)
    else:
        st.error("❌ Formato no soportado. Sube un .xlsx (recomendado).")
        return None

    if df is None or df.empty:
        st.error("❌ El fichero está vacío o no se pudo leer.")
        return None

    # referencia: ref / referencia / sku / article / item
    ref_col = _find_col_by_keywords(df, ["REF", "REFERENC", "SKU", "ARTICLE", "ITEM", "COD"])
    # cantidad: cantidad / unidades / qty / units
    qty_col = _find_col_by_keywords(df, ["CANT", "UNIDAD", "QTY", "UNIT", "UNITS"])

    if ref_col is None:
        ref_col = df.columns[0]

    if qty_col is None:
        # fallback: primera columna numérica
        for c in df.columns:
            if pd.api.types.is_numeric_dtype(df[c]):
                qty_col = c
                break

    if qty_col is None:
        st.error("❌ No he podido detectar la columna de cantidad (Cantidad/Unidades/QTY/Units).")
        return None

    out = []
    for _, r in df.iterrows():
        ref_raw = r.get(ref_col, "")
        qty_raw = r.get(qty_col, 0)

        if pd.isna(ref_raw) or str(ref_raw).strip() == "":
            continue

        try:
            qty = int(float(qty_raw))
        except Exception:
            qty = 0
        if qty <= 0:
            continue

        ref_txt = str(ref_raw).strip()

        # 1 atributo en paréntesis: "REF (AZUL)" o "REF (M)"
        m = re.match(r"^(.*?)\s*\((.*?)\)\s*$", ref_txt)
        if m:
            ref_base = m.group(1).strip()
            a1 = m.group(2).strip()
            out.append({"ref": ref_base, "a1": a1, "a2": "", "n_attrs": 1, "qty": qty})
        else:
            out.append({"ref": ref_txt, "a1": "", "a2": "", "n_attrs": 0, "qty": qty})

    return out


def import_to_carrito(import_rows, idx_exact, idx_ref_color, idx_ref_talla):
    carrito = {}
    incidencias = []

    for it in import_rows:
        row, err, metodo = match_producto(
            it["ref"],
            it.get("a1", ""),
            it.get("a2", ""),
            int(it.get("n_attrs", 0)),
            idx_exact,
            idx_ref_color,
            idx_ref_talla,
        )

        if err:
            incidencias.append(
                {
                    "Referencia": it["ref"],
                    "Atributo": it.get("a1", ""),
                    "Cantidad": it["qty"],
                    "Motivo": err,
                    "Metodo": metodo,
                }
            )
            continue

        ean = row["EAN"]
        if ean in carrito:
            carrito[ean]["qty"] = int(carrito[ean]["qty"]) + int(it["qty"])
        else:
            carrito[ean] = {
                "EAN": ean,
                "Referencia": row["Referencia"],
                "Nombre": row["Nombre"],
                "Color": row["Color"],
                "Talla": row["Talla"],
                "qty": int(it["qty"]),
            }

    return carrito, incidencias


# -------------------------
# Exportación
# -------------------------
def generar_archivo_peticion(carrito_final, config):
    records = []
    for ean, item in carrito_final.items():
        records.append(
            {
                "EAN": ean,
                "Referencia": item.get("Referencia", ""),
                "Nombre": item.get("Nombre", ""),
                "Color": item.get("Color", ""),
                "Talla": item.get("Talla", ""),
                "Cantidad": int(item.get("qty", 0)),
                "Origen": config.get("origen", ""),
                "Destino": config.get("destino", ""),
                "Fecha": config.get("fecha").strftime("%d/%m/%Y") if config.get("fecha") else "",
                "Ref_Peticion": config.get("ref_peticion", "") or "",
            }
        )

    df = pd.DataFrame(records)

    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="PETICION")
        meta = pd.DataFrame(
            [
                {
                    "Fecha": config.get("fecha").strftime("%d/%m/%Y") if config.get("fecha") else "",
                    "Origen": config.get("origen", ""),
                    "Destino": config.get("destino", ""),
                    "Ref_Peticion": config.get("ref_peticion", "") or "",
                    "Generado": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                }
            ]
        )
        meta.to_excel(writer, index=False, sheet_name="META")

    out.seek(0)

    fecha_str = (config.get("fecha") or date.today()).strftime("%Y%m%d")
    ref = (config.get("ref_peticion") or "sin_ref").strip().replace(" ", "_")
    filename = "peticion_{}_{}.xlsx".format(ref, fecha_str)
    return out.getvalue(), filename

# -------------------------
# Autosave
# -------------------------
def _state_to_jsonable():
    ss = st.session_state
    cfg = ss.get("config", {})

    def ser_cfg(v):
        if isinstance(v, date):
            return v.isoformat()
        return v

    cfg_j = {k: ser_cfg(v) for k, v in cfg.items()}

    payload = {
        "step": int(ss.get("step", 1)),
        "config": cfg_j,
        "carrito_import": ss.get("carrito_import", {}),
        "carrito_manual": ss.get("carrito_manual", {}),
        "manual_buffer": ss.get("manual_buffer", {}),
        "manual_refs_text": ss.get("manual_refs_text", ""),
        "incidencias": ss.get("incidencias", []),
        "ui": {
            "import_skipped": bool(ss.get("import_skipped", False)),
        },
    }
    return payload


def autosave_write():
    try:
        with open(AUTOSAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(_state_to_jsonable(), f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.warning("⚠️ No he podido auto-guardar: {}".format(e))


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
            cfg["fecha"] = date.fromisoformat(cfg["fecha"])
        except Exception:
            cfg["fecha"] = date.today()
    st.session_state.config = cfg

    st.session_state.carrito_import = payload.get("carrito_import", {}) or {}
    st.session_state.carrito_manual = payload.get("carrito_manual", {}) or {}
    st.session_state.manual_buffer = payload.get("manual_buffer", {}) or {}
    st.session_state.manual_refs_text = payload.get("manual_refs_text", "") or ""
    st.session_state.incidencias = payload.get("incidencias", []) or {}

    ui = payload.get("ui", {}) or {}
    st.session_state.import_skipped = bool(ui.get("import_skipped", False))
    return True


def autosave_clear():
    try:
        if os.path.exists(AUTOSAVE_FILE):
            os.remove(AUTOSAVE_FILE)
    except Exception:
        pass


# -------------------------
# UI helpers
# -------------------------
def header():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    st.title(APP_TITLE)
    st.caption("Flujo guiado · Importación opcional · Manual (buscador + lote) · Auto-guardado")


def sidebar_controls():
    with st.sidebar:
        st.markdown("### 🧭 Progreso")
        step = int(st.session_state.step)
        labels = {
            1: "1) Datos de la petición",
            2: "2) Importación (opcional)",
            3: "3) Añadir manual (buscador / lote)",
            4: "4) Revisión y unión",
            5: "5) Exportar",
        }
        st.write(labels.get(step, "Paso {}".format(step)))

        st.markdown("---")
        if st.button("💾 Guardar ahora"):
            autosave_write()
            st.success("Guardado.")

        if st.button("🔄 Recuperar guardado"):
            ok = autosave_load()
            if ok:
                st.success("Recuperado.")
                st.rerun()
            else:
                st.info("No hay guardado previo.")

        if st.button("🧹 Reiniciar (borrar guardado y estado)"):
            autosave_clear()
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()


# -------------------------
# Estado inicial
# -------------------------
def init_state():
    if "step" not in st.session_state:
        st.session_state.step = 1
    if "config" not in st.session_state:
        st.session_state.config = {
            "fecha": date.today(),
            "origen": "",
            "destino": "",
            "ref_peticion": "",
        }
    if "carrito_import" not in st.session_state:
        st.session_state.carrito_import = {}
    if "carrito_manual" not in st.session_state:
        st.session_state.carrito_manual = {}
    if "manual_buffer" not in st.session_state:
        st.session_state.manual_buffer = {}
    if "manual_refs_text" not in st.session_state:
        st.session_state.manual_refs_text = ""
    if "incidencias" not in st.session_state:
        st.session_state.incidencias = []
    if "import_skipped" not in st.session_state:
        st.session_state.import_skipped = False


# -------------------------
# Manual helpers
# -------------------------
def parse_refs_text(txt):
    if not txt:
        return []
    raw = re.split(r"[,\n;\t]+", txt)
    refs = [r.strip() for r in raw if r and r.strip()]
    seen = set()
    out = []
    for r in refs:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def merge_carritos(carrito_import, carrito_manual):
    final = {}
    for ean, it in (carrito_import or {}).items():
        final[ean] = dict(it)
    for ean, it in (carrito_manual or {}).items():
        if ean in final:
            final[ean]["qty"] = int(final[ean].get("qty", 0)) + int(it.get("qty", 0))
        else:
            final[ean] = dict(it)
    return final


def add_ean_to_manual(df_cat, ean, qty):
    ean = str(ean).strip()
    qty = int(qty)
    if not ean or qty <= 0:
        return False

    r = df_cat[df_cat["EAN"].astype(str).str.strip() == ean]
    if r.empty:
        return False

    rr = r.iloc[0]
    carrito_manual = st.session_state.carrito_manual

    if ean in carrito_manual:
        carrito_manual[ean]["qty"] = int(carrito_manual[ean].get("qty", 0)) + qty
    else:
        carrito_manual[ean] = {
            "EAN": ean,
            "Referencia": str(rr["Referencia"]).strip(),
            "Nombre": str(rr["Nombre"]).strip(),
            "Color": str(rr["Color"]).strip(),
            "Talla": str(rr["Talla"]).strip(),
            "qty": qty,
        }
    st.session_state.carrito_manual = carrito_manual
    return True

# =========================
# APP
# =========================
header()
init_state()
sidebar_controls()

df_cat = load_catalogue("catalogue.xlsx")
idx_exact, idx_ref_color, idx_ref_talla = build_indexes(df_cat)

# Aviso si hay autosave
if st.session_state.step == 1 and not st.session_state.config.get("origen") and os.path.exists(AUTOSAVE_FILE):
    st.info("💡 Hay un auto-guardado disponible. Puedes recuperarlo desde la barra lateral.")

step = int(st.session_state.step)

# ---------------------------------------------------------
# PASO 1: Datos petición (más realista: texto libre)
# ---------------------------------------------------------
if step == 1:
    st.subheader("Paso 1 · Datos de la petición")

    suger_dest = ["", "ALMACÉN CENTRAL", "TIENDA", "OUTLET", "USA"]
    suger_orig = ["", "ALMACÉN CENTRAL", "PROVEEDOR", "OUTLET", "USA"]

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("**Destino (almacén que pide)**")
        sug = st.selectbox("Sugerencia (opcional)", options=suger_dest, key="sug_destino")
        val = st.session_state.config.get("destino", "")
        if not val and sug:
            val = sug
        st.session_state.config["destino"] = st.text_input(
            "Escribe el nombre exacto del destino",
            value=val,
            placeholder="Ej: Almacén Ibiza / Tienda Madrid / USA DC ...",
            key="destino_txt",
        )

    with c2:
        st.markdown("**Origen (almacén que envía)**")
        sug = st.selectbox("Sugerencia (opcional)", options=suger_orig, key="sug_origen")
        val = st.session_state.config.get("origen", "")
        if not val and sug:
            val = sug
        st.session_state.config["origen"] = st.text_input(
            "Escribe el nombre exacto del origen",
            value=val,
            placeholder="Ej: Almacén Central / Proveedor / USA ...",
            key="origen_txt",
        )

    c3, c4 = st.columns(2)
    with c3:
        st.session_state.config["fecha"] = st.date_input(
            "Fecha de la petición",
            value=st.session_state.config.get("fecha", date.today()),
            key="fecha_in",
        )
    with c4:
        st.session_state.config["ref_peticion"] = st.text_input(
            "Referencia / Nota interna (opcional)",
            value=st.session_state.config.get("ref_peticion", ""),
            placeholder="Ej: Reposición NY · Semana 06",
            key="ref_in",
        )

    st.markdown("---")
    can_continue = bool(st.session_state.config.get("destino", "").strip()) and bool(
        st.session_state.config.get("origen", "").strip()
    )
    if not can_continue:
        st.warning("Para continuar, completa **Destino** y **Origen** (texto libre).")

    colx = st.columns([1, 1, 2])
    with colx[0]:
        if st.button("Siguiente ➡️", disabled=not can_continue):
            st.session_state.step = 2
            autosave_write()
            st.rerun()

# ---------------------------------------------------------
# PASO 2: Importación opcional
# ---------------------------------------------------------
elif step == 2:
    st.subheader("Paso 2 · Importación (opcional)")

    st.write(
        "Puedes **importar un Excel** para acelerar la carga, o **saltarte** este paso y pedir todo manualmente."
    )

    up = st.file_uploader("Sube Excel (.xlsx recomendado)", type=["xlsx", "xls"])

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("⬅️ Volver"):
            st.session_state.step = 1
            autosave_write()
            st.rerun()

    with col2:
        if st.button("Saltar importación (pedir manualmente)"):
            st.session_state.import_skipped = True
            st.session_state.carrito_import = {}
            st.session_state.incidencias = []
            st.session_state.step = 3
            autosave_write()
            st.rerun()

    if up is not None:
        import_rows = parse_import_file(up)
        if import_rows is not None:
            carrito_import, incidencias = import_to_carrito(import_rows, idx_exact, idx_ref_color, idx_ref_talla)
            st.session_state.carrito_import = carrito_import
            st.session_state.incidencias = incidencias

            st.success(
                "✅ Importación procesada. Productos encontrados: {} · Incidencias: {}".format(
                    len(carrito_import), len(incidencias)
                )
            )

            if incidencias:
                st.warning("Hay líneas con incidencias (no se han añadido).")
                st.dataframe(pd.DataFrame(incidencias), use_container_width=True)

            with col3:
                if st.button("Continuar ➡️", type="primary"):
                    st.session_state.step = 3
                    autosave_write()
                    st.rerun()

# ---------------------------------------------------------
# PASO 3: Manual (buscador + lote)
# ---------------------------------------------------------
elif step == 3:
    st.subheader("Paso 3 · Añadir productos manualmente")

    st.write("Puedes añadir por **buscador** (más guiado) o por **lote** pegando referencias.")

    tab1, tab2 = st.tabs(["🔎 Buscador (ref / nombre / EAN)", "📋 Lote (pegar referencias)"])

    # --------
    # TAB 1: Buscador guiado con botón (no Ctrl+Enter)
    # --------
    with tab1:
        q = st.text_input(
            "Buscar",
            value=st.session_state.get("manual_search_q", ""),
            placeholder="Escribe referencia, nombre, EAN, color o talla…",
            key="manual_search_q",
        )

        colb1, colb2, colb3 = st.columns([1, 1, 2])
        with colb1:
            do_search = st.button("Buscar selección", type="primary", key="btn_search_one")
        with colb2:
            if st.button("Limpiar búsqueda", key="btn_clear_search"):
                st.session_state.manual_search_q = ""
                st.session_state.manual_search_results = []
                autosave_write()
                st.rerun()

        if do_search:
            qq = (q or "").strip()
            if not qq:
                st.warning("Escribe algo para buscar.")
                st.session_state.manual_search_results = []
            else:
                qq_u = qq.upper()
                d = df_cat.copy()
                # filtro por contiene en varias columnas
                mask = (
                    d["Referencia"].astype(str).str.upper().str.contains(qq_u, na=False)
                    | d["Nombre"].astype(str).str.upper().str.contains(qq_u, na=False)
                    | d["EAN"].astype(str).str.upper().str.contains(qq_u, na=False)
                    | d["Color"].astype(str).str.upper().str.contains(qq_u, na=False)
                    | d["Talla"].astype(str).str.upper().str.contains(qq_u, na=False)
                )
                res = d[mask].head(100)
                st.session_state.manual_search_results = res.to_dict("records")

        results = st.session_state.get("manual_search_results", []) or []
        if results:
            st.caption("Resultados: {} (máx. 100)".format(len(results)))

            labels = []
            eans = []
            for r in results:
                ean = str(r.get("EAN", "")).strip()
                ref = str(r.get("Referencia", "")).strip()
                nom = str(r.get("Nombre", "")).strip()
                col = str(r.get("Color", "")).strip()
                tal = str(r.get("Talla", "")).strip()
                labels.append("{} — {} | {} | {} | {}".format(ref, nom, col, tal, ean))
                eans.append(ean)

            chosen = st.selectbox("Elige una variante", options=list(range(len(labels))), format_func=lambda i: labels[i])
            qty = st.number_input("Cantidad a añadir", min_value=1, max_value=9999, value=1, key="qty_search_one")

            if st.button("Añadir esta selección al bloque manual", key="btn_add_one"):
                ok = add_ean_to_manual(df_cat, eans[chosen], qty)
                if ok:
                    st.success("✅ Añadido.")
                    autosave_write()
                    st.rerun()
                else:
                    st.error("❌ No se pudo añadir (EAN no encontrado).")

        else:
            st.info("Usa el botón **Buscar selección** para obtener resultados.")

    # --------
    # TAB 2: Lote por referencias con botón
    # --------
    with tab2:
        st.session_state.manual_refs_text = st.text_area(
            "Pega referencias (una por línea o separadas por coma/;)",
            height=160,
            value=st.session_state.get("manual_refs_text", ""),
            placeholder="Ejemplo:\nA1234\nA5678, A9012; A3456",
            key="manual_refs_text_area",
        )

        colL1, colL2, colL3 = st.columns([1, 1, 2])
        with colL1:
            do_lote = st.button("Buscar selección (por referencias)", type="primary", key="btn_lote_search")
        with colL2:
            if st.button("Limpiar lote", key="btn_lote_clear"):
                st.session_state.manual_refs_text = ""
                st.session_state.manual_buffer = {}
                autosave_write()
                st.rerun()

if do_lote:
            refs = parse_refs_text(st.session_state.get("manual_refs_text", "") or st.session_state.get("manual_refs_text_area", ""))
            if not refs:
                st.warning("No he detectado referencias.")
                st.session_state.manual_buffer = {}
            else:
                buf = {}
                for ref in refs:
                    sub = df_cat[df_cat["Referencia"].astype(str).str.strip() == ref]
                    if sub.empty:
                        sub = df_cat[df_cat["Referencia"].astype(str).str.strip().str.upper() == ref.upper()]

                    if sub.empty:
                        buf[ref] = {"error": "NO_ENCONTRADO"}
                        continue

                    opts = []
                    for _, r in sub.iterrows():
                        ean = str(r["EAN"]).strip()
                        label = "{} | {} | {}".format(r["Color"], r["Talla"], ean)
                        opts.append(
                            {
                                "label": label,
                                "ean": ean,
                                "nombre": str(r["Nombre"]).strip(),
                                "color": str(r["Color"]).strip(),
                                "talla": str(r["Talla"]).strip(),
                                "ref": str(r["Referencia"]).strip(),
                            }
                        )

                    buf[ref] = {"error": "", "opts": opts, "selected_ean": opts[0]["ean"], "qty": 1}

                st.session_state.manual_buffer = buf
                autosave_write()

        # Render del buffer (si existe)
        buf = st.session_state.get("manual_buffer", {}) or {}
        if buf:
            for ref, item in buf.items():
                if item.get("error") == "NO_ENCONTRADO":
                    st.error("❌ No encuentro la referencia en catálogo: {}".format(ref))
                    continue

                st.markdown("**{}**".format(ref))
                opts = item.get("opts", []) or []
                labels = [o["label"] for o in opts]
                label_to_ean = {o["label"]: o["ean"] for o in opts}

                # Label actual
                current_ean = item.get("selected_ean", opts[0]["ean"])
                current_label = labels[0]
                for o in opts:
                    if o["ean"] == current_ean:
                        current_label = o["label"]
                        break

                cA, cB = st.columns([3, 1])
                with cA:
                    chosen_label = st.selectbox(
                        "Variante ({})".format(ref),
                        options=labels,
                        index=labels.index(current_label),
                        key="var_{}".format(ref),
                    )
                    item["selected_ean"] = label_to_ean[chosen_label]
                with cB:
                    item["qty"] = int(
                        st.number_input(
                            "Cantidad",
                            min_value=1,
                            max_value=9999,
                            value=int(item.get("qty", 1)),
                            key="qty_{}".format(ref),
                        )
                    )

                st.session_state.manual_buffer[ref] = item
                st.markdown("")

            if st.button("Añadir selección al bloque manual", key="btn_add_lote"):
                added = 0
                for ref, sel in (st.session_state.manual_buffer or {}).items():
                    if sel.get("error"):
                        continue
                    ean = sel.get("selected_ean")
                    qty = int(sel.get("qty", 0))
                    if add_ean_to_manual(df_cat, ean, qty):
                        added += 1
                st.session_state.manual_buffer = {}
                st.success("✅ Añadidos {} productos al bloque manual.".format(added))
                autosave_write()
                st.rerun()

        else:
            st.info("Pega referencias y pulsa **Buscar selección (por referencias)**.")

    st.markdown("---")
    cnav1, cnav2, cnav3 = st.columns([1, 1, 2])
    with cnav1:
        if st.button("⬅️ Volver"):
            st.session_state.step = 2
            autosave_write()
            st.rerun()
    with cnav2:
        if st.button("Revisar y unir ➡️", type="primary"):
            st.session_state.step = 4
            autosave_write()
            st.rerun()

# ---------------------------------------------------------
# PASO 4: Revisión y unión
# ---------------------------------------------------------
elif step == 4:
    st.subheader("Paso 4 · Revisión (importados vs manuales)")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 📥 Productos importados")
        imp = st.session_state.carrito_import or {}
        if not imp:
            st.info("No hay productos importados.")
        else:
            remove = []
            for ean, item in imp.items():
                a, b, c = st.columns([3, 1, 1])
                with a:
                    st.write("**{}** — {}".format(item.get("Referencia", ""), item.get("Nombre", "")))
                    st.caption("{} | {} | {}".format(item.get("Color", ""), item.get("Talla", ""), ean))
                with b:
                    newq = st.number_input(
                        "Cantidad",
                        min_value=0,
                        value=int(item.get("qty", 0)),
                        key="impq_{}".format(ean),
                        label_visibility="collapsed",
                    )
                    imp[ean]["qty"] = int(newq)
                with c:
                    if st.button("🗑️", key="impdel_{}".format(ean)):
                        remove.append(ean)
            for ean in remove:
                imp.pop(ean, None)
            imp = {k: v for k, v in imp.items() if int(v.get("qty", 0)) > 0}
            st.session_state.carrito_import = imp

    with col2:
        st.markdown("### ✍️ Productos añadidos manualmente")
        man = st.session_state.carrito_manual or {}
        if not man:
            st.info("No hay productos manuales.")
        else:
            remove = []
            for ean, item in man.items():
                a, b, c = st.columns([3, 1, 1])
                with a:
                    st.write("**{}** — {}".format(item.get("Referencia", ""), item.get("Nombre", "")))
                    st.caption("{} | {} | {}".format(item.get("Color", ""), item.get("Talla", ""), ean))
                with b:
                    newq = st.number_input(
                        "Cantidad",
                        min_value=0,
                        value=int(item.get("qty", 0)),
                        key="manq_{}".format(ean),
                        label_visibility="collapsed",
                    )
                    man[ean]["qty"] = int(newq)
                with c:
                    if st.button("🗑️", key="mandel_{}".format(ean)):
                        remove.append(ean)
            for ean in remove:
                man.pop(ean, None)
            man = {k: v for k, v in man.items() if int(v.get("qty", 0)) > 0}
            st.session_state.carrito_manual = man

    st.markdown("---")
    carrito_final = merge_carritos(st.session_state.carrito_import, st.session_state.carrito_manual)
    total_items = len(carrito_final)
    total_unidades = sum(int(v.get("qty", 0)) for v in carrito_final.values())

    st.info("📊 **Resumen** · {} referencias · {} unidades (importados + manuales)".format(total_items, total_unidades))

    colA, colB = st.columns([1, 1])
    with colA:
        if st.button("⬅️ Volver"):
            st.session_state.step = 3
            autosave_write()
            st.rerun()
    with colB:
        if st.button("Exportar ➡️", type="primary", disabled=(total_items == 0)):
            st.session_state.step = 5
            autosave_write()
            st.rerun()

# ---------------------------------------------------------
# PASO 5: Exportar
# ---------------------------------------------------------
elif step == 5:
    st.subheader("Paso 5 · Exportar")

    carrito_final = merge_carritos(st.session_state.carrito_import, st.session_state.carrito_manual)
    if not carrito_final:
        st.error("❌ No hay productos para exportar.")
    else:
        cfg = st.session_state.config

        st.markdown("### 📋 Resumen de la petición")
        st.write("**Fecha:** {}".format(cfg.get("fecha").strftime("%d/%m/%Y") if cfg.get("fecha") else ""))
        st.write("**Origen:** {}".format(cfg.get("origen", "")))
        st.write("**Destino:** {}".format(cfg.get("destino", "")))
        st.write("**Referencia:** {}".format(cfg.get("ref_peticion", "") or "—"))
        st.write("**Total referencias:** {}".format(len(carrito_final)))
        st.write("**Total unidades:** {}".format(sum(int(v.get("qty", 0)) for v in carrito_final.values())))

        file_bytes, filename = generar_archivo_peticion(carrito_final, cfg)
        st.download_button(
            "⬇️ Descargar Excel",
            data=file_bytes,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        st.markdown("---")
        colA, colB = st.columns([1, 1])
        with colA:
            if st.button("⬅️ Volver"):
                st.session_state.step = 4
                autosave_write()
                st.rerun()
        with colB:
            if st.button("✅ Marcar como finalizado (limpiar auto-guardado)"):
                autosave_clear()
                st.success("Auto-guardado eliminado. Puedes reiniciar desde la barra lateral si quieres.")

    autosave_write()

else:
    st.session_state.step = 1
    autosave_write()
    st.rerun()
