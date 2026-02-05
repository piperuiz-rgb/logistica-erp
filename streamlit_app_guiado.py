# =========================
# ASISTENTE DE PETICIONES (GUIADO)
# Charo Ruiz · Logistics
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
# Utilidades de normalización / matching (compatibles Py3.9)
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
    # heurística simple: tallas típicas / numéricas
    if re.fullmatch(r"\d{2,3}", t):
        return True
    if t in {"XS","S","M","L","XL","XXL","XXXL","T.U.","TU","U","UNICA","ÚNICA"}:
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
            "EAN": str(r.get("EAN","")).strip(),
            "Referencia": str(r.get("Referencia","")).strip(),
            "Nombre": str(r.get("Nombre","")).strip(),
            "Color": str(r.get("Color","")).strip(),
            "Talla": str(r.get("Talla","")).strip(),
            "ref_n": norm_txt(r.get("Referencia","")),
            "color_n": norm_color(r.get("Color","")),
            "talla_n": norm_talla(r.get("Talla","")),
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
        (row, err) = pick_unique(idx_exact.get((ref_n, color_n, talla_n), []))
        return row, err, "EXACTO ref+color+talla"

    if n_attrs == 1 and a1:
        token = str(a1).strip()
        if looks_like_talla(token):
            talla_n = norm_talla(token)
            (row, err) = pick_unique(idx_ref_talla.get((ref_n, talla_n), []))
            return row, err, "ref+talla"
        color_n = norm_color(token)
        (row, err) = pick_unique(idx_ref_color.get((ref_n, color_n), []))
        return row, err, "ref+color"

    return None, "NO_ENCONTRADO", "sin atributos"

# -------------------------
# Catálogo
# -------------------------
def load_catalogue(path="catalogue.xlsx"):
    if not os.path.exists(path):
        st.error(f"❌ No encuentro el catálogo: {path} (debe estar en la raíz del repo)")
        st.stop()

    df = pd.read_excel(path, engine="openpyxl")
    # Normaliza nombres típicos
    rename = {}
    for c in df.columns:
        cu = norm_txt(c)
        if cu in {"REF","REFERENCIA","REFERENCE"}:
            rename[c] = "Referencia"
        elif cu in {"EAN","CODIGO","CÓDIGO","BARCODE"}:
            rename[c] = "EAN"
        elif cu in {"NOMBRE","NAME","DESCRIPCION","DESCRIPCIÓN"}:
            rename[c] = "Nombre"
        elif cu in {"COLOR","COL"}:
            rename[c] = "Color"
        elif cu in {"TALLA","TALLAS","SIZE","TAL"}:
            rename[c] = "Talla"
    df = df.rename(columns=rename)

    required = ["Referencia","EAN","Nombre","Color","Talla"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        st.error(f"❌ Al catálogo le faltan columnas: {', '.join(missing)}")
        st.stop()

    # Limpieza básica
    df["Referencia"] = df["Referencia"].astype(str).str.strip()
    df["EAN"] = df["EAN"].astype(str).str.strip()
    df["Nombre"] = df["Nombre"].astype(str).fillna("").str.strip()
    df["Color"] = df["Color"].astype(str).fillna("").str.strip()
    df["Talla"] = df["Talla"].astype(str).fillna("").str.strip()
    return df

# -------------------------
# Importación de fichero (opcional)
# -------------------------
def parse_import_file(uploaded_file):
    """
    Acepta Excel con al menos una columna de referencia y una de cantidad.
    Intentos de auto-detección: columnas tipo Ref/Referencia + Cantidad/Unidades.
    Si hay columnas con (Color) o (Talla) en el texto, intentará extraer 1 atributo.
    """
    name = uploaded_file.name.lower()
    if name.endswith(".xlsx"):
        df = pd.read_excel(uploaded_file, engine="openpyxl")
    elif name.endswith(".xls"):
        # En cloud, .xls puede requerir xlrd. Mejor pedir .xlsx.
        df = pd.read_excel(uploaded_file)  # puede fallar si no está xlrd
    else:
        st.error("❌ Formato no soportado. Sube un .xlsx (recomendado).")
        return None

    # Normaliza cabeceras
    cols = {c: norm_txt(c) for c in df.columns}
    ref_col = None
    qty_col = None
    for c, cu in cols.items():
        if ref_col is None and cu in {"REF","REFERENCIA","REFERENCE","SKU"}:
            ref_col = c
        if qty_col is None and cu in {"CANTIDAD","UNIDADES","QTY","CANT","UNITS"}:
            qty_col = c

    if ref_col is None:
        # fallback: primera columna
        ref_col = df.columns[0]
    if qty_col is None:
        # fallback: busca numérica
        for c in df.columns:
            if pd.api.types.is_numeric_dtype(df[c]):
                qty_col = c
                break

    if qty_col is None:
        st.error("❌ No he podido detectar la columna de cantidad (Cantidad/Unidades/QTY).")
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
        # Extrae atributo entre paréntesis si existe: "REF (COLOR)" o "REF (TALLA)"
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
            it["ref"], it.get("a1",""), it.get("a2",""), int(it.get("n_attrs",0)),
            idx_exact, idx_ref_color, idx_ref_talla
        )
        if err:
            incidencias.append({
                "Referencia": it["ref"],
                "Atributo": it.get("a1",""),
                "Cantidad": it["qty"],
                "Motivo": err,
                "Metodo": metodo,
            })
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
        records.append({
            "EAN": ean,
            "Referencia": item.get("Referencia",""),
            "Nombre": item.get("Nombre",""),
            "Color": item.get("Color",""),
            "Talla": item.get("Talla",""),
            "Cantidad": int(item.get("qty", 0)),
            "Origen": config.get("origen",""),
            "Destino": config.get("destino",""),
            "Fecha": config.get("fecha").strftime("%d/%m/%Y") if config.get("fecha") else "",
            "Ref_Peticion": config.get("ref_peticion","") or "",
        })
    df = pd.DataFrame(records)

    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="PETICION")
        meta = pd.DataFrame([{
            "Fecha": config.get("fecha").strftime("%d/%m/%Y") if config.get("fecha") else "",
            "Origen": config.get("origen",""),
            "Destino": config.get("destino",""),
            "Ref_Peticion": config.get("ref_peticion","") or "",
            "Generado": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        }])
        meta.to_excel(writer, index=False, sheet_name="META")
    out.seek(0)

    fecha_str = (config.get("fecha") or date.today()).strftime("%Y%m%d")
    ref = (config.get("ref_peticion") or "sin_ref").strip().replace(" ", "_")
    filename = f"peticion_{ref}_{fecha_str}.xlsx"
    return out.getvalue(), filename

# -------------------------
# Autosave (simple)
# -------------------------
def _state_to_jsonable():
    ss = st.session_state
    cfg = ss.get("config", {})
    def ser_cfg(v):
        if isinstance(v, date):
            return v.isoformat()
        return v
    cfg_j = {k: ser_cfg(v) for k,v in cfg.items()}

    payload = {
        "step": int(ss.get("step", 1)),
        "config": cfg_j,
        "carrito_import": ss.get("carrito_import", {}),
        "carrito_manual": ss.get("carrito_manual", {}),
        "manual_buffer": ss.get("manual_buffer", {}),
        "incidencias": ss.get("incidencias", []),
        "ui": {
            "import_skipped": bool(ss.get("import_skipped", False)),
        }
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
    st.session_state.incidencias = payload.get("incidencias", []) or []
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
    st.caption("Flujo guiado · Importación opcional · Añadido manual por lote · Auto-guardado")

def sidebar_controls():
    with st.sidebar:
        st.markdown("### 🧭 Progreso")
        step = int(st.session_state.step)
        labels = {
            1: "1) Datos de la petición",
            2: "2) Importación (opcional)",
            3: "3) Añadir manual (lote)",
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
    if "incidencias" not in st.session_state:
        st.session_state.incidencias = []
    if "import_skipped" not in st.session_state:
        st.session_state.import_skipped = False

# -------------------------
# Manual lote
# -------------------------
def parse_refs_text(txt):
    if not txt:
        return []
    # separadores: salto línea, coma, punto y coma, tab, espacio múltiple
    raw = re.split(r"[,\n;\t]+", txt)
    refs = [r.strip() for r in raw if r and r.strip()]
    # mantiene orden, elimina duplicados exactos
    seen = set()
    out = []
    for r in refs:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out

def merge_carritos(carrito_import, carrito_manual):
    final = {}
    for ean, it in carrito_import.items():
        final[ean] = dict(it)
    for ean, it in carrito_manual.items():
        if ean in final:
            final[ean]["qty"] = int(final[ean].get("qty",0)) + int(it.get("qty",0))
        else:
            final[ean] = dict(it)
    return final

# =========================
# APP
# =========================
header()
init_state()
sidebar_controls()

df_cat = load_catalogue("catalogue.xlsx")
idx_exact, idx_ref_color, idx_ref_talla = build_indexes(df_cat)

# Autosave "ligero" en cada rerun: si existe guardado y el usuario está en estado inicial, cárgalo
if st.session_state.step == 1 and not st.session_state.config.get("origen") and os.path.exists(AUTOSAVE_FILE):
    # no forzar; mostrar opción visible arriba
    st.info("💡 Hay un auto-guardado disponible. Puedes recuperarlo desde la barra lateral.")

step = int(st.session_state.step)

# ---------------------------------------------------------
# PASO 1: Datos petición (muy guiado)
# ---------------------------------------------------------
if step == 1:
    st.subheader("Paso 1 · Datos de la petición")

    colA, colB = st.columns(2)

    with colA:
        st.session_state.config["destino"] = st.selectbox(
            "¿Qué almacén está solicitando la mercancía? (Destino)",
            options=["", "TIENDA", "ALMACEN CENTRAL", "OUTLET", "USA", "OTRO"],
            index=0 if st.session_state.config.get("destino","") == "" else None,
        )
        if st.session_state.config["destino"] == "OTRO":
            st.session_state.config["destino"] = st.text_input("Especifica destino", value="")

    with colB:
        st.session_state.config["origen"] = st.selectbox(
            "¿Qué almacén la envía? (Origen)",
            options=["", "ALMACEN CENTRAL", "PROVEEDOR", "OUTLET", "USA", "OTRO"],
            index=0 if st.session_state.config.get("origen","") == "" else None,
        )
        if st.session_state.config["origen"] == "OTRO":
            st.session_state.config["origen"] = st.text_input("Especifica origen", value="")

    colC, colD = st.columns(2)
    with colC:
        st.session_state.config["fecha"] = st.date_input(
            "Fecha de la petición",
            value=st.session_state.config.get("fecha", date.today()),
        )
    with colD:
        st.session_state.config["ref_peticion"] = st.text_input(
            "Referencia / Nota interna (opcional)",
            value=st.session_state.config.get("ref_peticion",""),
            placeholder="Ej: Reposición NY · Semana 06",
        )

    st.markdown("---")
    can_continue = bool(st.session_state.config.get("destino")) and bool(st.session_state.config.get("origen"))
    if not can_continue:
        st.warning("Para continuar, elige **Destino** y **Origen**.")
    cols = st.columns([1,1,2])
    with cols[0]:
        if st.button("Siguiente ➡️", disabled=not can_continue):
            st.session_state.step = 2
            autosave_write()
            st.rerun()

# ---------------------------------------------------------
# PASO 2: Importación opcional
# ---------------------------------------------------------
elif step == 2:
    st.subheader("Paso 2 · Importación (opcional)")

    st.write("Puedes **importar un Excel** para acelerar la carga, o **saltarte** este paso y pedir todo manualmente.")

    up = st.file_uploader("Sube Excel (.xlsx recomendado)", type=["xlsx","xls"])
    col1, col2 = st.columns([1,1])
    with col1:
        if st.button("Saltar importación (quiero pedir manualmente)"):
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

            st.success(f"✅ Importación procesada. Productos encontrados: {len(carrito_import)} · Incidencias: {len(incidencias)}")

            if incidencias:
                st.warning("Hay líneas con incidencias (no se han añadido).")
                st.dataframe(pd.DataFrame(incidencias), use_container_width=True)

            with col2:
                if st.button("Continuar ➡️"):
                    st.session_state.step = 3
                    autosave_write()
                    st.rerun()

    st.markdown("---")
    if st.button("⬅️ Volver"):
        st.session_state.step = 1
        autosave_write()
        st.rerun()

# ---------------------------------------------------------
# PASO 3: Añadido manual por lote
# ---------------------------------------------------------
elif step == 3:
    st.subheader("Paso 3 · Añadir productos manualmente (modo lote)")

    st.write("Pega una lista de referencias, selecciona la variante (si aplica) y asigna cantidades.")

    refs_text = st.text_area(
        "Referencias (una por línea o separadas por coma/;)",
        height=140,
        placeholder="Ejemplo:\nA1234\nA5678, A9012; A3456",
        key="manual_refs_text",
    )

    refs = parse_refs_text(refs_text)
    if refs:
        st.caption(f"Referencias detectadas: {len(refs)}")

    # Construye buffer de selección por referencia
    buf = st.session_state.manual_buffer or {}
    for ref in refs:
        # opciones de variantes por referencia
        sub = df_cat[df_cat["Referencia"].astype(str).str.strip() == ref]
        if sub.empty:
            # intenta por normalizado
            sub = df_cat[df_cat["Referencia"].astype(str).str.strip().str.upper() == ref.upper()]
        if sub.empty:
            st.error(f"❌ No encuentro la referencia en catálogo: {ref}")
            continue

        opts = []
        for _, r in sub.iterrows():
            ean = str(r["EAN"]).strip()
            label = f"{r['Color']} | {r['Talla']} | {ean}"
            opts.append((label, ean, r["Nombre"], r["Color"], r["Talla"], r["Referencia"]))

        if ref not in buf:
            buf[ref] = {"selected_ean": opts[0][1], "qty": 1}

        st.markdown(f"**{ref}**")
        c1, c2 = st.columns([3,1])
        with c1:
            labels = [o[0] for o in opts]
            # map label -> ean
            label_to_ean = {o[0]: o[1] for o in opts}
            current_ean = buf[ref].get("selected_ean", opts[0][1])
            current_label = None
            for o in opts:
                if o[1] == current_ean:
                    current_label = o[0]
                    break
            if current_label is None:
                current_label = opts[0][0]
            chosen_label = st.selectbox(f"Variante ({ref})", labels, index=labels.index(current_label), key=f"var_{ref}")
            buf[ref]["selected_ean"] = label_to_ean[chosen_label]
        with c2:
            buf[ref]["qty"] = int(st.number_input("Cantidad", min_value=1, max_value=9999, value=int(buf[ref].get("qty",1)), key=f"qty_{ref}"))

        st.markdown("")

    st.session_state.manual_buffer = buf

    st.markdown("---")
    colA, colB, colC = st.columns([1,1,2])
    with colA:
        if st.button("⬅️ Volver"):
            st.session_state.step = 2
            autosave_write()
            st.rerun()
    with colB:
        if st.button("Añadir selección al bloque manual"):
            added = 0
            for ref, sel in (st.session_state.manual_buffer or {}).items():
                ean = sel.get("selected_ean")
                qty = int(sel.get("qty", 0))
                if not ean or qty <= 0:
                    continue
                r = df_cat[df_cat["EAN"].astype(str).str.strip() == str(ean).strip()]
                if r.empty:
                    continue
                rr = r.iloc[0]
                carrito_manual = st.session_state.carrito_manual
                if ean in carrito_manual:
                    carrito_manual[ean]["qty"] = int(carrito_manual[ean].get("qty",0)) + qty
                else:
                    carrito_manual[ean] = {
                        "EAN": str(ean).strip(),
                        "Referencia": str(rr["Referencia"]).strip(),
                        "Nombre": str(rr["Nombre"]).strip(),
                        "Color": str(rr["Color"]).strip(),
                        "Talla": str(rr["Talla"]).strip(),
                        "qty": qty,
                    }
                added += 1

            st.session_state.carrito_manual = st.session_state.carrito_manual
            st.session_state.manual_buffer = {}
            st.success(f"✅ Añadidos {added} productos al bloque manual.")
            autosave_write()
            st.rerun()

    with colC:
        if st.button("Revisar y unir ➡️", type="primary"):
            st.session_state.step = 4
            autosave_write()
            st.rerun()

# ---------------------------------------------------------
# PASO 4: Revisión y unión (separado por origen)
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
                a,b,c = st.columns([3,1,1])
                with a:
                    st.write(f"**{item.get('Referencia','')}** — {item.get('Nombre','')}")
                    st.caption(f"{item.get('Color','')} | {item.get('Talla','')} | {ean}")
                with b:
                    newq = st.number_input("Cantidad", min_value=0, value=int(item.get("qty",0)), key=f"impq_{ean}", label_visibility="collapsed")
                    imp[ean]["qty"] = int(newq)
                with c:
                    if st.button("🗑️", key=f"impdel_{ean}"):
                        remove.append(ean)
            for ean in remove:
                imp.pop(ean, None)
            # limpia qty=0
            imp = {k:v for k,v in imp.items() if int(v.get("qty",0))>0}
            st.session_state.carrito_import = imp

    with col2:
        st.markdown("### ✍️ Productos añadidos manualmente")
        man = st.session_state.carrito_manual or {}
        if not man:
            st.info("No hay productos manuales.")
        else:
            remove = []
            for ean, item in man.items():
                a,b,c = st.columns([3,1,1])
                with a:
                    st.write(f"**{item.get('Referencia','')}** — {item.get('Nombre','')}")
                    st.caption(f"{item.get('Color','')} | {item.get('Talla','')} | {ean}")
                with b:
                    newq = st.number_input("Cantidad", min_value=0, value=int(item.get("qty",0)), key=f"manq_{ean}", label_visibility="collapsed")
                    man[ean]["qty"] = int(newq)
                with c:
                    if st.button("🗑️", key=f"mandel_{ean}"):
                        remove.append(ean)
            for ean in remove:
                man.pop(ean, None)
            man = {k:v for k,v in man.items() if int(v.get("qty",0))>0}
            st.session_state.carrito_manual = man

    st.markdown("---")
    carrito_final = merge_carritos(st.session_state.carrito_import, st.session_state.carrito_manual)
    total_items = len(carrito_final)
    total_unidades = sum(int(v.get("qty",0)) for v in carrito_final.values())

    st.info(f"📊 **Resumen** · {total_items} referencias · {total_unidades} unidades (importados + manuales)")

    colA, colB = st.columns([1,1])
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
        st.write(f"**Fecha:** {cfg.get('fecha').strftime('%d/%m/%Y') if cfg.get('fecha') else ''}")
        st.write(f"**Origen:** {cfg.get('origen','')}")
        st.write(f"**Destino:** {cfg.get('destino','')}")
        st.write(f"**Referencia:** {cfg.get('ref_peticion','') or '—'}")
        st.write(f"**Total referencias:** {len(carrito_final)}")
        st.write(f"**Total unidades:** {sum(int(v.get('qty',0)) for v in carrito_final.values())}")

        file_bytes, filename = generar_archivo_peticion(carrito_final, cfg)
        st.download_button("⬇️ Descargar Excel", data=file_bytes, file_name=filename, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        st.markdown("---")
        colA, colB = st.columns([1,1])
        with colA:
            if st.button("⬅️ Volver"):
                st.session_state.step = 4
                autosave_write()
                st.rerun()
        with colB:
            if st.button("✅ Marcar como finalizado (limpiar auto-guardado)"):
                autosave_clear()
                st.success("Auto-guardado eliminado. Puedes reiniciar desde la barra lateral si quieres.")

    # autosave final por si refrescan
    autosave_write()

else:
    st.session_state.step = 1
    autosave_write()
    st.rerun()
