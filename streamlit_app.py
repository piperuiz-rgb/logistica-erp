# -*- coding: utf-8 -*-
"""
streamlit_app.py — Asistente guiado de peticiones a almacén (v3)

Incluye:
- Paso 1 guiado: Origen/Destino (texto libre) + botones de sugerencia (no pisan salvo click)
- Importación opcional: auto-detección de columnas + selección manual si falla
- Manual: buscador por referencia / nombre / EAN / color / talla (por coincidencia parcial)
  + selector de número máximo de resultados + botón explícito "Buscar selección"
- Manual por lote: pegar referencias y confirmar variantes/cantidades con botón (sin Ctrl+Enter)
- Revisión rápida con st.data_editor (mejor rendimiento que widgets por fila)
- Rendimiento: caché de catálogo, columnas de búsqueda y construcción de índices
- Auto-guardado en fichero JSON local (evento a evento, no en cada render)

Requisitos:
- streamlit
- pandas
- openpyxl
"""

import io
import json
import os
import re
from datetime import date, datetime

import pandas as pd
import streamlit as st

APP_TITLE = "Asistente de Peticiones a Almacén"
AUTOSAVE_FILE = ".autosave_peticion.json"


# =========================
# Helpers de texto / matching
# =========================
def norm_txt(x):
    if x is None:
        return ""
    return re.sub(r"\s+", " ", str(x)).strip().upper()


def looks_like_talla(token: str) -> bool:
    t = norm_txt(token)
    if re.fullmatch(r"\d{2,3}", t):
        return True
    if t in {"XS", "S", "M", "L", "XL", "XXL", "XXXL", "T.U.", "TU", "U", "UNICA", "ÚNICA"}:
        return True
    return False


def _pick_unique(rows):
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
        color_n = norm_txt(a1)
        talla_n = norm_txt(a2)
        row, err = _pick_unique(idx_exact.get((ref_n, color_n, talla_n), []))
        return row, err, "EXACTO ref+color+talla"

    if n_attrs == 1 and a1:
        token = str(a1).strip()
        if looks_like_talla(token):
            talla_n = norm_txt(token)
            row, err = _pick_unique(idx_ref_talla.get((ref_n, talla_n), []))
            return row, err, "ref+talla"
        color_n = norm_txt(token)
        row, err = _pick_unique(idx_ref_color.get((ref_n, color_n), []))
        return row, err, "ref+color"

    return None, "NO_ENCONTRADO", "sin atributos"


# =========================
# Catálogo (cacheado)
# =========================
@st.cache_data(show_spinner=False)
def load_catalogue_cached(path="catalogue.xlsx"):
    if not os.path.exists(path):
        raise FileNotFoundError(path)

    df = pd.read_excel(path, engine="openpyxl")

    # Renombrado robusto
    rename = {}
    for c in df.columns:
        cu = norm_txt(c)
        if cu in {"REF", "REFERENCIA", "REFERENCE", "SKU"} or "REFEREN" in cu or cu.endswith("REF"):
            rename[c] = "Referencia"
        elif cu in {"EAN", "BARCODE"} or "EAN" in cu or "BARRA" in cu:
            rename[c] = "EAN"
        elif cu in {
            "NOMBRE",
            "NAME",
            "DESCRIPCION",
            "DESCRIPCIÓN",
            "DENOMINACION",
            "DENOMINACIÓN",
            "ARTICULO",
            "ARTÍCULO",
        } or "DESCRIP" in cu or "DENOM" in cu:
            rename[c] = "Nombre"
        elif cu in {"COLOR", "COL"} or "COLOR" in cu:
            rename[c] = "Color"
        elif cu in {"TALLA", "TALLAS", "SIZE", "TAL"} or "TALLA" in cu or "SIZE" in cu:
            rename[c] = "Talla"
    df = df.rename(columns=rename)

    required = ["Referencia", "EAN", "Nombre", "Color", "Talla"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError("Al catálogo le faltan columnas: " + ", ".join(missing))

    # Limpieza
    for c in required:
        df[c] = df[c].astype(str).fillna("").str.strip()

    return df


@st.cache_data(show_spinner=False)
def prepare_search_cols(df):
    d = df.copy()
    for c in ["Referencia", "Nombre", "EAN", "Color", "Talla"]:
        d[c] = d[c].astype(str).fillna("")
        d[c + "_U"] = d[c].str.upper()
    return d


@st.cache_resource(show_spinner=False)
def build_indexes_cached(df_cat):
    """
    Índices para matching rápido por ref+color+talla, ref+color, ref+talla.
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
            "color_n": norm_txt(r.get("Color", "")),
            "talla_n": norm_txt(r.get("Talla", "")),
        }
        add(exact, (row["ref_n"], row["color_n"], row["talla_n"]), row)
        add(ref_color, (row["ref_n"], row["color_n"]), row)
        add(ref_talla, (row["ref_n"], row["talla_n"]), row)

    return exact, ref_color, ref_talla


# =========================
# Importación (columna flexible + fallback selección)
# =========================
def _find_col_by_keywords(df, keywords):
    cols = list(df.columns)
    norm_map = {c: norm_txt(c) for c in cols}
    for c in cols:
        cu = norm_map[c]
        cu2 = (
            cu.replace("SUM OF ", "")
            .replace("TOTAL ", "")
            .replace("SUMA DE ", "")
            .replace("TOTAL DE ", "")
        )
        for kw in keywords:
            if kw in cu2:
                return c
    return None


def parse_import_file(uploaded_file):
    name = (uploaded_file.name or "").lower()

    if name.endswith(".xlsx"):
        df = pd.read_excel(uploaded_file, engine="openpyxl")
    elif name.endswith(".xls"):
        # Para .xls puede requerir xlrd; si falla, el usuario debe convertir a .xlsx
        df = pd.read_excel(uploaded_file)
    else:
        st.error("❌ Formato no soportado. Sube un .xlsx (recomendado).")
        return None

    if df is None or df.empty:
        st.error("❌ El fichero está vacío o no se pudo leer.")
        return None

    ref_col = _find_col_by_keywords(df, ["REF", "REFERENC", "SKU", "ARTICLE", "ITEM", "COD", "ARTIC"])
    qty_col = _find_col_by_keywords(df, ["CANT", "UNIDAD", "QTY", "UNIT", "UNITS", "UD", "UDS", "PIEZ"])

    if ref_col is None or qty_col is None:
        st.warning("No he podido detectar automáticamente las columnas. Selección manual:")
        cols = list(df.columns)
        ref_col = st.selectbox("Columna de Referencia", options=cols, index=0, key="imp_ref_col_sel")
        num_candidates = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
        default_qty = cols.index(num_candidates[0]) if num_candidates else min(1, len(cols) - 1)
        qty_col = st.selectbox("Columna de Cantidad", options=cols, index=default_qty, key="imp_qty_col_sel")

    if ref_col is None or qty_col is None:
        st.error("❌ Selecciona columnas válidas de referencia y cantidad.")
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


# =========================
# Exportación
# =========================
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
    filename = f"peticion_{ref}_{fecha_str}.xlsx"
    return out.getvalue(), filename


# =========================
# Autosave (evento a evento)
# =========================
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
            "manual_search_q": ss.get("manual_search_q", ""),
            "max_res": int(ss.get("max_res", 100)),
            "manual_search_results": ss.get("manual_search_results", []),
        },
    }
    return payload


def autosave_write():
    try:
        with open(AUTOSAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(_state_to_jsonable(), f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.warning(f"⚠️ No he podido auto-guardar: {e}")


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
    st.session_state.incidencias = payload.get("incidencias", []) or []
    ui = payload.get("ui", {}) or {}
    st.session_state.import_skipped = bool(ui.get("import_skipped", False))
    st.session_state.manual_search_q = ui.get("manual_search_q", "")
    st.session_state.max_res = int(ui.get("max_res", 100))
    st.session_state.manual_search_results = ui.get("manual_search_results", [])
    return True


def autosave_clear():
    try:
        if os.path.exists(AUTOSAVE_FILE):
            os.remove(AUTOSAVE_FILE)
    except Exception:
        pass


# =========================
# UI helpers / Estado
# =========================
def header():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    st.title(APP_TITLE)
    st.caption("Guiado · Importación opcional · Manual (buscador + lote) · Auto-guardado")


def init_state():
    if "step" not in st.session_state:
        st.session_state.step = 1
    if "config" not in st.session_state:
        st.session_state.config = {"fecha": date.today(), "origen": "", "destino": "", "ref_peticion": ""}
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
    if "manual_search_q" not in st.session_state:
        st.session_state.manual_search_q = ""
    if "max_res" not in st.session_state:
        st.session_state.max_res = 100
    if "manual_search_results" not in st.session_state:
        st.session_state.manual_search_results = []


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
        st.write(labels.get(step, f"Paso {step}"))

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


# =========================
# Manual helpers
# =========================
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
    # limpia qty <= 0
    final = {k: v for k, v in final.items() if int(v.get("qty", 0)) > 0}
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
    car = st.session_state.carrito_manual
    if ean in car:
        car[ean]["qty"] = int(car[ean].get("qty", 0)) + qty
    else:
        car[ean] = {
            "EAN": ean,
            "Referencia": str(rr["Referencia"]).strip(),
            "Nombre": str(rr["Nombre"]).strip(),
            "Color": str(rr["Color"]).strip(),
            "Talla": str(rr["Talla"]).strip(),
            "qty": qty,
        }
    st.session_state.carrito_manual = car
    return True


def carrito_to_df(car):
    if not car:
        return pd.DataFrame(columns=["EAN", "Referencia", "Nombre", "Color", "Talla", "qty"])
    df = pd.DataFrame(list(car.values()))
    cols = ["EAN", "Referencia", "Nombre", "Color", "Talla", "qty"]
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    return df[cols]


def df_to_carrito(df):
    if df is None or df.empty:
        return {}
    records = df.to_dict("records")
    out = {}
    for r in records:
        ean = str(r.get("EAN", "")).strip()
        if not ean:
            continue
        try:
            qty = int(float(r.get("qty", 0)))
        except Exception:
            qty = 0
        if qty <= 0:
            continue
        out[ean] = {
            "EAN": ean,
            "Referencia": str(r.get("Referencia", "")).strip(),
            "Nombre": str(r.get("Nombre", "")).strip(),
            "Color": str(r.get("Color", "")).strip(),
            "Talla": str(r.get("Talla", "")).strip(),
            "qty": qty,
        }
    return out


# =========================
# APP
# =========================
header()
init_state()
sidebar_controls()

# Carga catálogo + índices (cacheados)
try:
    df_cat = load_catalogue_cached("catalogue.xlsx")
except FileNotFoundError:
    st.error("❌ No encuentro **catalogue.xlsx** en la raíz del repo.")
    st.stop()
except Exception as e:
    st.error(f"❌ Error leyendo catálogo: {e}")
    st.stop()

df_cat_s = prepare_search_cols(df_cat)
idx_exact, idx_ref_color, idx_ref_talla = build_indexes_cached(df_cat)

# Aviso autosave disponible
if st.session_state.step == 1 and not st.session_state.config.get("origen") and os.path.exists(AUTOSAVE_FILE):
    st.info("💡 Hay un auto-guardado disponible. Puedes recuperarlo desde la barra lateral.")

step = int(st.session_state.step)

# -------------------------
# PASO 1
# -------------------------
if step == 1:
    st.subheader("Paso 1 · Datos de la petición")

    cfg = st.session_state.config

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Destino (almacén que pide)**")
        cfg["destino"] = st.text_input(
            "Nombre exacto (Destino)",
            value=cfg.get("destino", ""),
            placeholder="Escribe EXACTAMENTE el nombre interno",
            key="destino_txt",
        )
        st.caption("Sugerencias rápidas (opcional):")
        b1, b2, b3, b4 = st.columns(4)
        if b1.button("ALMACÉN CENTRAL", key="dest_sug_1"):
            cfg["destino"] = "ALMACÉN CENTRAL"; st.session_state.config = cfg; autosave_write(); st.rerun()
        if b2.button("TIENDA", key="dest_sug_2"):
            cfg["destino"] = "TIENDA"; st.session_state.config = cfg; autosave_write(); st.rerun()
        if b3.button("OUTLET", key="dest_sug_3"):
            cfg["destino"] = "OUTLET"; st.session_state.config = cfg; autosave_write(); st.rerun()
        if b4.button("USA", key="dest_sug_4"):
            cfg["destino"] = "USA"; st.session_state.config = cfg; autosave_write(); st.rerun()

    with c2:
        st.markdown("**Origen (almacén que envía)**")
        cfg["origen"] = st.text_input(
            "Nombre exacto (Origen)",
            value=cfg.get("origen", ""),
            placeholder="Escribe EXACTAMENTE el nombre interno",
            key="origen_txt",
        )
        st.caption("Sugerencias rápidas (opcional):")
        b1, b2, b3, b4 = st.columns(4)
        if b1.button("ALMACÉN CENTRAL", key="org_sug_1"):
            cfg["origen"] = "ALMACÉN CENTRAL"; st.session_state.config = cfg; autosave_write(); st.rerun()
        if b2.button("PROVEEDOR", key="org_sug_2"):
            cfg["origen"] = "PROVEEDOR"; st.session_state.config = cfg; autosave_write(); st.rerun()
        if b3.button("OUTLET", key="org_sug_3"):
            cfg["origen"] = "OUTLET"; st.session_state.config = cfg; autosave_write(); st.rerun()
        if b4.button("USA", key="org_sug_4"):
            cfg["origen"] = "USA"; st.session_state.config = cfg; autosave_write(); st.rerun()

    c3, c4 = st.columns(2)
    with c3:
        cfg["fecha"] = st.date_input("Fecha de la petición", value=cfg.get("fecha", date.today()), key="fecha_in")
    with c4:
        cfg["ref_peticion"] = st.text_input(
            "Referencia / Nota interna (opcional)",
            value=cfg.get("ref_peticion", ""),
            placeholder="Ej: Reposición NY · Semana 06",
            key="ref_in",
        )

    st.session_state.config = cfg

    st.markdown("---")
    can_continue = bool(cfg.get("destino", "").strip()) and bool(cfg.get("origen", "").strip())
    if not can_continue:
        st.warning("Para continuar, completa **Destino** y **Origen**.")

    if st.button("Siguiente ➡️", disabled=not can_continue, type="primary"):
        st.session_state.step = 2
        autosave_write()
        st.rerun()

# -------------------------
# PASO 2
# -------------------------
elif step == 2:
    st.subheader("Paso 2 · Importación (opcional)")
    st.write("Puedes **importar un Excel** o **saltarte** y pedir todo manualmente.")

    up = st.file_uploader("Sube Excel (.xlsx recomendado)", type=["xlsx", "xls"])

    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        if st.button("⬅️ Volver"):
            st.session_state.step = 1
            autosave_write()
            st.rerun()
    with c2:
        if st.button("Saltar importación (manual)"):
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

            st.success(f"✅ Importación procesada. Encontrados: {len(carrito_import)} · Incidencias: {len(incidencias)}")
            if incidencias:
                st.warning("Hay líneas con incidencias (no se han añadido).")
                st.dataframe(pd.DataFrame(incidencias), use_container_width=True)

            with c3:
                if st.button("Continuar ➡️", type="primary"):
                    st.session_state.step = 3
                    autosave_write()
                    st.rerun()

# -------------------------
# PASO 3
# -------------------------
elif step == 3:
    st.subheader("Paso 3 · Añadir productos manualmente")
    st.write("Añade por **buscador** (ref/nombre/EAN/color/talla) o por **lote** pegando referencias.")

    tab1, tab2 = st.tabs(["🔎 Buscador", "📋 Lote (pegar refs)"])

    # --- BUSCADOR
    with tab1:
        st.session_state.max_res = st.selectbox(
            "Nº máximo de resultados",
            options=[20, 50, 100, 200, 500],
            index=[20, 50, 100, 200, 500].index(int(st.session_state.max_res)) if int(st.session_state.max_res) in [20, 50, 100, 200, 500] else 2,
            key="max_res",
        )

        q = st.text_input(
            "Buscar (parte del texto)",
            value=st.session_state.manual_search_q,
            placeholder="Ej: 'vestido', 'ibiza', 'A1234', '840...', 'negro', 'M'...",
            key="manual_search_q",
        )

        b1, b2, _ = st.columns([1, 1, 3])
        do_search = b1.button("Buscar selección", type="primary")
        if b2.button("Limpiar"):
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
                d = df_cat_s
                mask = (
                    d["Referencia_U"].str.contains(qq_u, na=False)
                    | d["Nombre_U"].str.contains(qq_u, na=False)
                    | d["EAN_U"].str.contains(qq_u, na=False)
                    | d["Color_U"].str.contains(qq_u, na=False)
                    | d["Talla_U"].str.contains(qq_u, na=False)
                )
                res = d.loc[mask, ["EAN", "Referencia", "Nombre", "Color", "Talla"]].head(int(st.session_state.max_res))
                st.session_state.manual_search_results = res.to_dict("records")
                autosave_write()

        results = st.session_state.manual_search_results or []
        if results:
            st.caption(f"Resultados: {len(results)} (máx. {int(st.session_state.max_res)})")

            labels = []
            eans = []
            for r in results:
                ean = str(r.get("EAN", "")).strip()
                ref = str(r.get("Referencia", "")).strip()
                nom = str(r.get("Nombre", "")).strip()
                col = str(r.get("Color", "")).strip()
                tal = str(r.get("Talla", "")).strip()
                labels.append(f"{ref} — {nom} | {col} | {tal} | {ean}")
                eans.append(ean)

            chosen = st.selectbox("Elige una variante", options=list(range(len(labels))), format_func=lambda i: labels[i])
            qty = st.number_input("Cantidad", min_value=1, max_value=9999, value=1, key="qty_search_one")

            if st.button("Añadir al bloque manual", type="primary"):
                ok = add_ean_to_manual(df_cat, eans[chosen], qty)
                if ok:
                    st.success("✅ Añadido.")
                    autosave_write()
                    st.rerun()
                st.error("❌ No se pudo añadir (EAN no encontrado).")
        else:
            st.info("Pulsa **Buscar selección** para ver resultados.")

    # --- LOTE
    with tab2:
        st.session_state.manual_refs_text = st.text_area(
            "Pega referencias (una por línea o separadas por coma/;).",
            height=160,
            value=st.session_state.manual_refs_text,
            placeholder="Ej:\nA1234\nA5678, A9012; A3456",
        )

        do_lote = st.button("Buscar selección (por referencias)", type="primary")
        if do_lote:
            refs = parse_refs_text(st.session_state.manual_refs_text)
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
                        label = f'{r["Color"]} | {r["Talla"]} | {ean}'
                        opts.append({"label": label, "ean": ean})
                    buf[ref] = {"error": "", "opts": opts, "selected_ean": opts[0]["ean"], "qty": 1}

                st.session_state.manual_buffer = buf
            autosave_write()

        buf = st.session_state.manual_buffer or {}
        if buf:
            for ref, item in buf.items():
                if item.get("error") == "NO_ENCONTRADO":
                    st.error(f"❌ No encuentro la referencia en catálogo: {ref}")
                    continue

                st.markdown(f"**{ref}**")
                opts = item.get("opts", []) or []
                labels = [o["label"] for o in opts]
                label_to_ean = {o["label"]: o["ean"] for o in opts}

                current_ean = item.get("selected_ean", opts[0]["ean"])
                current_label = labels[0]
                for o in opts:
                    if o["ean"] == current_ean:
                        current_label = o["label"]
                        break

                cA, cB = st.columns([3, 1])
                with cA:
                    chosen_label = st.selectbox(
                        f"Variante ({ref})",
                        options=labels,
                        index=labels.index(current_label),
                        key=f"var_{ref}",
                    )
                    item["selected_ean"] = label_to_ean[chosen_label]
                with cB:
                    item["qty"] = int(st.number_input("Cantidad", 1, 9999, int(item.get("qty", 1)), key=f"qty_{ref}"))

                st.session_state.manual_buffer[ref] = item

            if st.button("Añadir selección al bloque manual", type="primary"):
                added = 0
                for _, sel in (st.session_state.manual_buffer or {}).items():
                    if sel.get("error"):
                        continue
                    ean = sel.get("selected_ean")
                    qty = int(sel.get("qty", 0))
                    if add_ean_to_manual(df_cat, ean, qty):
                        added += 1
                st.session_state.manual_buffer = {}
                st.success(f"✅ Añadidos {added} productos al bloque manual.")
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

# -------------------------
# PASO 4 (rápido con data_editor)
# -------------------------
elif step == 4:
    st.subheader("Paso 4 · Revisión (importados vs manuales)")
    st.write("Edita cantidades o elimina filas. Luego pasa a exportar.")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 📥 Importados")
        df_imp = carrito_to_df(st.session_state.carrito_import)
        if df_imp.empty:
            st.info("No hay importados.")
        else:
            df_imp2 = st.data_editor(
                df_imp,
                use_container_width=True,
                num_rows="dynamic",
                column_config={"qty": st.column_config.NumberColumn("qty", min_value=0, step=1)},
                key="edit_imp",
            )
            st.session_state.carrito_import = df_to_carrito(df_imp2)

    with col2:
        st.markdown("### ✍️ Manuales")
        df_man = carrito_to_df(st.session_state.carrito_manual)
        if df_man.empty:
            st.info("No hay manuales.")
        else:
            df_man2 = st.data_editor(
                df_man,
                use_container_width=True,
                num_rows="dynamic",
                column_config={"qty": st.column_config.NumberColumn("qty", min_value=0, step=1)},
                key="edit_man",
            )
            st.session_state.carrito_manual = df_to_carrito(df_man2)

    st.markdown("---")
    carrito_final = merge_carritos(st.session_state.carrito_import, st.session_state.carrito_manual)
    st.info(f"📊 Resumen · {len(carrito_final)} referencias · {sum(int(v.get('qty',0)) for v in carrito_final.values())} unidades")

    cA, cB = st.columns([1, 1])
    with cA:
        if st.button("⬅️ Volver"):
            st.session_state.step = 3
            autosave_write()
            st.rerun()
    with cB:
        if st.button("Exportar ➡️", type="primary", disabled=(len(carrito_final) == 0)):
            st.session_state.step = 5
            autosave_write()
            st.rerun()

# -------------------------
# PASO 5
# -------------------------
elif step == 5:
    st.subheader("Paso 5 · Exportar")
    carrito_final = merge_carritos(st.session_state.carrito_import, st.session_state.carrito_manual)
    if not carrito_final:
        st.error("❌ No hay productos para exportar.")
    else:
        cfg = st.session_state.config
        st.markdown("### 📋 Resumen")
        st.write(f"**Fecha:** {cfg.get('fecha').strftime('%d/%m/%Y') if cfg.get('fecha') else ''}")
        st.write(f"**Origen:** {cfg.get('origen','')}")
        st.write(f"**Destino:** {cfg.get('destino','')}")
        st.write(f"**Referencia:** {cfg.get('ref_peticion','') or '—'}")
        st.write(f"**Total referencias:** {len(carrito_final)}")
        st.write(f"**Total unidades:** {sum(int(v.get('qty',0)) for v in carrito_final.values())}")

        file_bytes, filename = generar_archivo_peticion(carrito_final, cfg)
        st.download_button(
            "⬇️ Descargar Excel",
            data=file_bytes,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        st.markdown("---")
        cA, cB = st.columns([1, 1])
        with cA:
            if st.button("⬅️ Volver"):
                st.session_state.step = 4
                autosave_write()
                st.rerun()
        with cB:
            if st.button("✅ Finalizar (limpiar auto-guardado)"):
                autosave_clear()
                st.success("Auto-guardado eliminado.")

else:
    st.session_state.step = 1
    autosave_write()
    st.rerun()
