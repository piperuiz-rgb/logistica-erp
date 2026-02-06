import streamlit as st
import pandas as pd
import uuid
import re
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONFIG = {
    "app_title": "Asistente de Peticiones entre Almacenes",
    "max_upload_size": 10,  # MB
}

# ---- Helpers de sesión ----
def get_default_session_state():
    return {
        "cat_df": None,
        "req_df": None,
        "merged_df": None,
        "not_found_df": None,
        "current_step": 1,
        "session_id": uuid.uuid4().hex[:12],
    }

def init_session_state():
    defaults = get_default_session_state()
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

# ---- Parsing de referencias ----
REF_PATTERN = re.compile(r"\[([^\]]+)\]")
PAREN_PATTERN = re.compile(r"\(([^)]*)\)")

def parse_referencia(ref_str):
    """Devuelve dict con ref, color, talla. Color va antes de la coma, talla después. Ambos opcionales."""
    if not isinstance(ref_str, str):
        return {"ref": None, "color": None, "talla": None}
    ref_match = REF_PATTERN.search(ref_str)
    paren_match = PAREN_PATTERN.search(ref_str)
    ref = ref_match.group(1).strip() if ref_match else None
    color = talla = None
    if paren_match:
        inside = paren_match.group(1).strip()
        if "," in inside:
            parts = [p.strip() for p in inside.split(",", 1)]
            color = parts[0] or None
            talla = parts[1] or None
        else:
            color = inside or None  # puede ser solo color o solo talla; asumimos color si único
    return {"ref": ref, "color": color, "talla": talla}

# ---- Carga de archivos ----
def load_table(uploaded_file):
    if uploaded_file is None:
        return None
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    elif name.endswith((".xlsx", ".xls")):
        df = pd.read_excel(uploaded_file)
    else:
        raise ValueError("Formato no soportado")
    if df.empty:
        raise ValueError("Archivo vacío")
    df.columns = df.columns.str.strip().str.title()
    return df

# ---- Cruce petición vs catálogo ----
def enrich_request(req_df, cat_df):
    # Normalizar nombres de columnas clave
    req_cols = {c.lower(): c for c in req_df.columns}
    cat_cols = {c.lower(): c for c in cat_df.columns}

    # Columnas esperadas
    req_prod_col = req_cols.get("producto") or req_cols.get("referencia") or next(iter(req_df.columns))
    req_qty_col = req_cols.get("cantidad") or None
    cat_ref_col = cat_cols.get("referencia") or next(iter(cat_df.columns))
    cat_ean_col = cat_cols.get("ean") or cat_cols.get("codbarras") or None
    cat_color_col = cat_cols.get("color")
    cat_talla_col = cat_cols.get("talla")

    # Parseo de referencia en petición
    parsed = req_df[req_prod_col].apply(parse_referencia)
    req_df["_ref"] = parsed.apply(lambda x: x["ref"])
    req_df["_color"] = parsed.apply(lambda x: x["color"])
    req_df["_talla"] = parsed.apply(lambda x: x["talla"])

    # Catálogo: construir _ref, _color y _talla siempre, usando columnas existentes o parseando
    # Parse from reference if we need any of ref/color/talla
    need_parse = (cat_color_col is None or cat_talla_col is None)
    parsed_cat = cat_df[cat_ref_col].apply(parse_referencia) if need_parse else None
    
    # Build _ref: try to extract from reference column or use as-is
    if need_parse:
        cat_df["_ref"] = parsed_cat.apply(lambda x: x["ref"] if x["ref"] else None)
        # If parsed ref is None, fallback to original reference column value
        cat_df["_ref"] = cat_df["_ref"].fillna(cat_df[cat_ref_col])
    else:
        cat_df["_ref"] = cat_df[cat_ref_col]
    
    # Build _color: use existing column if present, otherwise parse
    if cat_color_col is not None:
        cat_df["_color"] = cat_df[cat_color_col]
    else:
        cat_df["_color"] = parsed_cat.apply(lambda x: x["color"])
    
    # Build _talla: use existing column if present, otherwise parse
    if cat_talla_col is not None:
        cat_df["_talla"] = cat_df[cat_talla_col]
    else:
        cat_df["_talla"] = parsed_cat.apply(lambda x: x["talla"])

    # Merge por ref + color + talla (color/talla opcionales: se usa fillna para permitir match parcial)
    merge_keys = ["_ref", "_color", "_talla"]
    merged = req_df.merge(
        cat_df,
        left_on=merge_keys,
        right_on=merge_keys,
        how="left",
        suffixes=("_req", "_cat"),
    )

    # EAN final
    merged["EAN"] = merged[cat_ean_col] if cat_ean_col else None

    # Estado de match
    merged["match"] = merged["EAN"].notna()

    not_found = merged[~merged["match"]].copy()

    return merged, not_found, {
        "req_rows": len(req_df),
        "matched": merged["match"].sum(),
        "not_matched": (~merged["match"]).sum(),
    }

# ---- UI ----
def main():
    init_session_state()
    st.set_page_config(page_title=CONFIG["app_title"], page_icon="📦", layout="wide")
    st.title(CONFIG["app_title"])
    st.markdown("---")

    # Barra lateral: estado
    with st.sidebar:
        st.header("Estado")
        st.write(f"Paso {st.session_state.current_step} de 5")
        st.write(f"Sesión: {st.session_state.session_id}")

    step = st.session_state.current_step

    # Paso 1: almacenes
    if step == 1:
        st.header("Paso 1: Selecciona almacenes")
        origen = st.text_input("Almacén origen", value="ALM-ORIGEN")
        destino = st.text_input("Almacén destino", value="ALM-DESTINO")
        if st.button("Continuar", type="primary"):
            st.session_state.origen = origen
            st.session_state.destino = destino
            st.session_state.current_step = 2
            st.rerun()

    # Paso 2: catálogo
    elif step == 2:
        st.header("Paso 2: Carga catálogo (Referencia, EAN, Color/Talla opc.)")
        cat_file = st.file_uploader("Archivo catálogo (CSV/Excel)", type=["csv", "xlsx", "xls"])
        if cat_file:
            try:
                cat_df = load_table(cat_file)
                st.session_state.cat_df = cat_df
                st.success(f"Catálogo cargado: {len(cat_df)} filas")
                st.dataframe(cat_df.head(10), use_container_width=True)
                if st.button("Continuar", type="primary"):
                    st.session_state.current_step = 3
                    st.rerun()
            except Exception as e:
                st.error(f"Error cargando catálogo: {e}")
        st.button("Volver", on_click=lambda: st.session_state.update(current_step=1))

    # Paso 3: petición
    elif step == 3:
        st.header("Paso 3: Carga petición (Producto/Referencia, Cantidad)")
        req_file = st.file_uploader("Archivo petición (CSV/Excel)", type=["csv", "xlsx", "xls"])
        if req_file:
            try:
                req_df = load_table(req_file)
                st.session_state.req_df = req_df
                st.success(f"Petición cargada: {len(req_df)} filas")
                st.dataframe(req_df.head(10), use_container_width=True)
                if st.button("Continuar", type="primary"):
                    st.session_state.current_step = 4
                    st.rerun()
            except Exception as e:
                st.error(f"Error cargando petición: {e}")
        st.button("Volver", on_click=lambda: st.session_state.update(current_step=2))

    # Paso 4: cruce
    elif step == 4:
        st.header("Paso 4: Cruce catálogo vs petición")
        if st.session_state.cat_df is None or st.session_state.req_df is None:
            st.error("Falta catálogo o petición. Vuelve atrás.")
        else:
            merged, not_found, stats = enrich_request(st.session_state.req_df.copy(), st.session_state.cat_df.copy())
            st.session_state.merged_df = merged
            st.session_state.not_found_df = not_found
            st.write(f"Coincidencias: {stats['matched']} / {stats['req_rows']}. No encontrados: {stats['not_matched']}.")
            st.subheader("Vista previa")
            st.dataframe(merged.head(20), use_container_width=True)
            if len(not_found) > 0:
                st.warning(f"No encontrados: {len(not_found)}")
                st.dataframe(not_found.head(10), use_container_width=True)
            if st.button("Continuar", type="primary"):
                st.session_state.current_step = 5
                st.rerun()
        st.button("Volver", on_click=lambda: st.session_state.update(current_step=3))

    # Paso 5: descarga
    elif step == 5:
        st.header("Paso 5: Descarga")
        merged = st.session_state.get("merged_df")
        not_found = st.session_state.get("not_found_df")
        origen = st.session_state.get("origen", "ORIGEN")
        destino = st.session_state.get("destino", "DESTINO")

        if merged is None:
            st.error("No hay datos procesados.")
            return

        # Añadir origen/destino
        merged_out = merged.copy()
        merged_out["Origen"] = origen
        merged_out["Destino"] = destino

        csv_all = merged_out.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Descargar consolidado",
            data=csv_all,
            file_name=f"pedido_{origen}_{destino}_{st.session_state.session_id}.csv",
            mime="text/csv",
            type="primary",
        )

        if not_found is not None and not not_found.empty:
            csv_nf = not_found.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Descargar no encontrados",
                data=csv_nf,
                file_name=f"no_encontrados_{st.session_state.session_id}.csv",
                mime="text/csv",
            )

        if st.button("🔄 Nuevo proceso"):
            for k, v in get_default_session_state().items():
                st.session_state[k] = v
            st.rerun()

if __name__ == "__main__":
    main()