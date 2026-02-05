# Complete Refactored Streamlit Application Code

import streamlit as st
import pandas as pd
import os
import tempfile
import uuid
import re

# Logging setup
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Centralized CONFIG dictionary
CONFIG = {
    'app_title': 'Asistente de Catálogo - ERP Logística',
    'max_upload_size': 10,  # in MB
}

# Function for initializing session state
def get_default_session_state():
    default_state = {
        'data': None,
        'processed_data': None,
        'ean_valid': False,
        'metrics': {},
        'current_step': 1,
        'uploaded_file_name': None,
        'session_id': uuid.uuid4().hex[:12],  # Unique session identifier
    }
    return default_state

# Initialize session state
def init_session_state():
    """Initialize session state with defaults if not already set."""
    defaults = get_default_session_state()
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

# Clean EAN function
def _clean_ean(ean):
    """Normalize EAN strings and reject invalid (non-digit) inputs."""
    if pd.isna(ean):
        return None
    if isinstance(ean, (int, float)):
        ean_str = str(int(ean))
    elif isinstance(ean, str):
        ean_str = ean.replace('-', '').replace(' ', '').strip()
    else:
        return None
    
    # Check if it's all digits
    if ean_str.isdigit() and len(ean_str) > 0:
        return ean_str
    return None

# Updated regex pattern for product parsing
product_pattern = re.compile(r"\[.*?\]\s+.*\([^)]+\)")

def parse_product(product_str):
    """
    Extract bracketed code, name, and value from product string.
    Example: "[CODE] Product Name (Value)" -> {'code': 'CODE', 'name': 'Product Name', 'value': 'Value'}
    """
    if not isinstance(product_str, str):
        return None
    
    try:
        # Extract code in brackets
        code_match = re.search(r'\[([^\]]+)\]', product_str)
        code = code_match.group(1) if code_match else None
        
        # Extract value in parentheses
        value_match = re.search(r'\(([^)]+)\)', product_str)
        value = value_match.group(1) if value_match else None
        
        # Extract name (between brackets and parentheses)
        if code_match and value_match:
            start = code_match.end()
            end = value_match.start()
            name = product_str[start:end].strip()
        else:
            name = None
        
        return {'code': code, 'name': name, 'value': value}
    except Exception as e:
        logger.warning(f"Error parsing product string '{product_str}': {e}")
        return None

# Function for loading catalog fallback
@st.cache_data
def load_catalog_fallback(uploaded_file):
    """
    Load CSV/Excel file into pandas DataFrame with column standardization.
    Handles empty/invalid files gracefully.
    """
    if uploaded_file is None:
        return None
    
    try:
        # Get file extension
        file_name = uploaded_file.name.lower()
        
        # Read file based on extension
        if file_name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        elif file_name.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(uploaded_file)
        else:
            raise ValueError(f"Unsupported file format: {file_name}")
        
        # Check if DataFrame is empty
        if df.empty:
            raise pd.errors.EmptyDataError("The uploaded file is empty")
        
        # Standardize column names (strip whitespace, convert to title case)
        df.columns = df.columns.str.strip().str.title()
        
        logger.info(f"Successfully loaded file with {len(df)} rows and columns: {df.columns.tolist()}")
        return df
        
    except pd.errors.EmptyDataError as e:
        logger.error(f"Empty data error: {e}")
        st.error("El archivo está vacío. Por favor, carga un archivo con datos.")
        return None
    except pd.errors.ParserError as e:
        logger.error(f"Parser error: {e}")
        st.error("Error al analizar el archivo. Verifica que el formato sea correcto.")
        return None
    except Exception as e:
        logger.error(f"Error loading file: {e}")
        st.error(f"Error al cargar el archivo: {str(e)}")
        return None

# Robust autosave function with corruption detection
def autosave(data, session_id=None):
    """
    Persist the processed DataFrame to a temp directory (.cache/autosave_<session_id>.csv).
    Returns the path to the saved file or None on error.
    """
    if data is None or data.empty:
        logger.warning("No data to autosave")
        return None
    
    try:
        # Create cache directory if it doesn't exist
        cache_dir = os.path.join(os.getcwd(), '.cache')
        os.makedirs(cache_dir, exist_ok=True)
        
        # Use provided session_id or generate a new one
        if session_id is None:
            session_id = uuid.uuid4().hex[:12]
        
        autosave_path = os.path.join(cache_dir, f'autosave_{session_id}.csv')
        
        # Save to CSV
        data.to_csv(autosave_path, index=False)
        logger.info(f"Data autosaved to {autosave_path}")
        
        return autosave_path
        
    except PermissionError as e:
        error_msg = f"Permission denied when saving to {cache_dir}: {e}"
        logger.error(error_msg)
        st.error(f"Error de permisos al guardar: {str(e)}")
        return None
    except Exception as e:
        error_msg = f'Autosave failed: {e}'
        logger.error(error_msg)
        st.error(f"Error al guardar automáticamente: {str(e)}")
        return None

# Display metrics
def show_metrics(metrics):
    """Display metrics in a user-friendly format using Streamlit columns."""
    if not metrics:
        st.info("No hay métricas disponibles")
        return
    
    # Create columns for metrics
    cols = st.columns(len(metrics))
    
    metric_labels = {
        'total_rows': 'Total de Filas',
        'valid_eans': 'EANs Válidos',
        'missing_eans': 'EANs Faltantes',
        'duplicate_eans': 'EANs Duplicados',
    }
    
    for idx, (key, value) in enumerate(metrics.items()):
        with cols[idx]:
            label = metric_labels.get(key, key.replace('_', ' ').title())
            st.metric(label=label, value=value)

def compute_metrics(data, ean_column='Ean'):
    """
    Compute metrics: row count, valid EANs, missing EANs, duplicate EANs.
    """
    if data is None or data.empty:
        return {}
    
    # Create a copy to avoid modifying the original DataFrame
    data_copy = data.copy()
    
    metrics = {}
    metrics['total_rows'] = len(data_copy)
    
    # Check if EAN column exists (case-insensitive)
    ean_col = None
    for col in data_copy.columns:
        if col.lower() == ean_column.lower():
            ean_col = col
            break
    
    if ean_col:
        # Count valid EANs (non-null, cleaned successfully)
        data_copy['ean_cleaned'] = data_copy[ean_col].apply(_clean_ean)
        metrics['valid_eans'] = data_copy['ean_cleaned'].notna().sum()
        metrics['missing_eans'] = data_copy['ean_cleaned'].isna().sum()
        
        # Count duplicates (only among valid EANs)
        valid_eans = data_copy['ean_cleaned'].dropna()
        metrics['duplicate_eans'] = valid_eans.duplicated().sum()
    else:
        logger.warning(f"Column '{ean_column}' not found in data")
        metrics['valid_eans'] = 0
        metrics['missing_eans'] = metrics['total_rows']
        metrics['duplicate_eans'] = 0
    
    return metrics

# Main application
def main():
    """Main Streamlit application with wizard-like flow."""
    
    # Initialize session state
    init_session_state()
    
    # Page configuration
    st.set_page_config(
        page_title=CONFIG['app_title'],
        page_icon="📊",
        layout="wide"
    )
    
    # Title and description
    st.title(CONFIG['app_title'])
    st.markdown("---")
    
    # Sidebar help
    with st.sidebar:
        st.header("ℹ️ Ayuda")
        st.markdown("""
        ### Instrucciones
        
        **Paso 1: Cargar Archivo**
        - Sube un archivo CSV o Excel
        - Tamaño máximo: {} MB
        
        **Paso 2: Vista Previa**
        - Revisa los datos cargados
        
        **Paso 3: Validar EANs**
        - Limpia y valida los códigos EAN
        
        **Paso 4: Métricas**
        - Visualiza estadísticas del catálogo
        
        **Paso 5: Descargar**
        - Descarga el archivo procesado
        """.format(CONFIG['max_upload_size']))
        
        st.markdown("---")
        st.markdown("### Estado Actual")
        st.write(f"**Paso:** {st.session_state.current_step} de 5")
        if st.session_state.uploaded_file_name:
            st.write(f"**Archivo:** {st.session_state.uploaded_file_name}")
    
    # Progress indicator
    progress = (st.session_state.current_step - 1) / 4
    st.progress(progress)
    
    try:
        # Step 1: Upload
        if st.session_state.current_step == 1:
            st.header("📤 Paso 1: Cargar Archivo")
            st.write("Sube tu archivo de catálogo (CSV o Excel)")
            
            uploaded_file = st.file_uploader(
                "Selecciona un archivo",
                type=['csv', 'xlsx', 'xls'],
                help=f"Tamaño máximo: {CONFIG['max_upload_size']} MB"
            )
            
            if uploaded_file:
                # Check file size
                file_size_mb = uploaded_file.size / (1024 * 1024)
                if file_size_mb > CONFIG['max_upload_size']:
                    st.error(f"❌ El archivo es demasiado grande ({file_size_mb:.2f} MB). "
                            f"El tamaño máximo permitido es {CONFIG['max_upload_size']} MB.")
                else:
                    st.success(f"✅ Archivo cargado: {uploaded_file.name} ({file_size_mb:.2f} MB)")
                    
                    if st.button("Continuar al Paso 2", type="primary"):
                        # Load data
                        data = load_catalog_fallback(uploaded_file)
                        if data is not None:
                            st.session_state.data = data
                            st.session_state.uploaded_file_name = uploaded_file.name
                            st.session_state.current_step = 2
                            st.rerun()
        
        # Step 2: Preview
        elif st.session_state.current_step == 2:
            st.header("👀 Paso 2: Vista Previa de Datos")
            
            if st.session_state.data is not None:
                data = st.session_state.data
                st.write(f"**Total de filas:** {len(data)}")
                st.write(f"**Columnas:** {', '.join(data.columns.tolist())}")
                
                st.subheader("Primeras filas")
                st.dataframe(data.head(10), use_container_width=True)
                
                col1, col2 = st.columns([1, 4])
                with col1:
                    if st.button("← Volver", type="secondary"):
                        st.session_state.current_step = 1
                        st.rerun()
                with col2:
                    if st.button("Continuar al Paso 3 →", type="primary"):
                        st.session_state.current_step = 3
                        st.rerun()
            else:
                st.error("No hay datos cargados. Vuelve al Paso 1.")
                if st.button("← Volver al Paso 1"):
                    st.session_state.current_step = 1
                    st.rerun()
        
        # Step 3: Validate EANs
        elif st.session_state.current_step == 3:
            st.header("✅ Paso 3: Validar EANs")
            
            if st.session_state.data is not None:
                data = st.session_state.data.copy()
                
                # Find EAN column
                ean_col = None
                for col in data.columns:
                    if col.lower() == 'ean':
                        ean_col = col
                        break
                
                if ean_col:
                    st.write(f"Columna EAN detectada: **{ean_col}**")
                    
                    # Apply EAN cleaning
                    data['EAN_Limpio'] = data[ean_col].apply(_clean_ean)
                    
                    # Show sample of cleaned EANs
                    st.subheader("Muestra de EANs limpios")
                    sample_df = data[[ean_col, 'EAN_Limpio']].head(10)
                    st.dataframe(sample_df, use_container_width=True)
                    
                    # Update session state
                    st.session_state.processed_data = data
                    st.session_state.ean_valid = True
                    
                    col1, col2 = st.columns([1, 4])
                    with col1:
                        if st.button("← Volver", type="secondary"):
                            st.session_state.current_step = 2
                            st.rerun()
                    with col2:
                        if st.button("Continuar al Paso 4 →", type="primary"):
                            st.session_state.current_step = 4
                            st.rerun()
                else:
                    st.warning("⚠️ No se encontró una columna 'EAN'. Los datos se procesarán sin validación de EAN.")
                    st.session_state.processed_data = data
                    
                    col1, col2 = st.columns([1, 4])
                    with col1:
                        if st.button("← Volver", type="secondary"):
                            st.session_state.current_step = 2
                            st.rerun()
                    with col2:
                        if st.button("Continuar al Paso 4 →", type="primary"):
                            st.session_state.current_step = 4
                            st.rerun()
            else:
                st.error("No hay datos cargados. Vuelve al Paso 1.")
                if st.button("← Volver al Paso 1"):
                    st.session_state.current_step = 1
                    st.rerun()
        
        # Step 4: Metrics
        elif st.session_state.current_step == 4:
            st.header("📊 Paso 4: Métricas del Catálogo")
            
            if st.session_state.processed_data is not None:
                data = st.session_state.processed_data
                
                # Compute metrics
                metrics = compute_metrics(data)
                st.session_state.metrics = metrics
                
                # Display metrics
                st.subheader("Resumen de Métricas")
                show_metrics(metrics)
                
                # Additional info
                st.markdown("---")
                st.subheader("Información Adicional")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Columnas totales:** {len(data.columns)}")
                    st.write(f"**Tipo de datos:**")
                    for col in data.columns[:5]:  # Show first 5 columns
                        st.write(f"  - {col}: {data[col].dtype}")
                
                with col2:
                    if 'EAN_Limpio' in data.columns:
                        valid_pct = 0.0
                        total = metrics.get('total_rows', 0)
                        if total > 0:
                            valid_pct = (metrics.get('valid_eans', 0) / total) * 100
                        st.write(f"**Porcentaje de EANs válidos:** {valid_pct:.1f}%")
                        
                        if metrics.get('duplicate_eans', 0) > 0:
                            st.warning(f"⚠️ Se encontraron {metrics['duplicate_eans']} EANs duplicados")
                
                col1, col2 = st.columns([1, 4])
                with col1:
                    if st.button("← Volver", type="secondary"):
                        st.session_state.current_step = 3
                        st.rerun()
                with col2:
                    if st.button("Continuar al Paso 5 →", type="primary"):
                        st.session_state.current_step = 5
                        st.rerun()
            else:
                st.error("No hay datos procesados. Vuelve al Paso 1.")
                if st.button("← Volver al Paso 1"):
                    st.session_state.current_step = 1
                    st.rerun()
        
        # Step 5: Download
        elif st.session_state.current_step == 5:
            st.header("💾 Paso 5: Descargar Archivo Procesado")
            
            if st.session_state.processed_data is not None:
                data = st.session_state.processed_data
                
                st.success("✅ Datos listos para descargar")
                
                # Autosave
                st.subheader("Guardado Automático")
                if st.button("Guardar en caché local"):
                    autosave_path = autosave(data, session_id=st.session_state.get('session_id'))
                    if autosave_path:
                        st.success(f"✅ Archivo guardado en: {autosave_path}")
                
                # Download button
                st.subheader("Descargar Archivo")
                csv_data = data.to_csv(index=False).encode('utf-8')
                
                # Use session_id for consistent filename
                session_id = st.session_state.get('session_id', uuid.uuid4().hex[:12])
                
                st.download_button(
                    label="📥 Descargar CSV Procesado",
                    data=csv_data,
                    file_name=f"catalogo_procesado_{session_id}.csv",
                    mime="text/csv",
                    type="primary"
                )
                
                # Summary
                st.markdown("---")
                st.subheader("Resumen del Proceso")
                if st.session_state.metrics:
                    show_metrics(st.session_state.metrics)
                
                # Reset button
                st.markdown("---")
                if st.button("🔄 Procesar Nuevo Archivo", type="secondary"):
                    # Reset session state
                    for key in get_default_session_state().keys():
                        st.session_state[key] = get_default_session_state()[key]
                    st.rerun()
            else:
                st.error("No hay datos procesados. Vuelve al Paso 1.")
                if st.button("← Volver al Paso 1"):
                    st.session_state.current_step = 1
                    st.rerun()
    
    except pd.errors.EmptyDataError:
        logger.error('No data found in file.')
        st.error('❌ No se encontraron datos en el archivo.')
    except pd.errors.ParserError:
        logger.error('Data parsing error.')
        st.error('❌ Hubo un error al analizar los datos. Verifica el formato del archivo.')
    except Exception as e:
        logger.error(f'Unexpected error: {e}', exc_info=True)
        st.error(f'❌ Error inesperado: {str(e)}')
        if st.button("🔄 Reiniciar Aplicación"):
            for key in get_default_session_state().keys():
                st.session_state[key] = get_default_session_state()[key]
            st.rerun()

if __name__ == "__main__":
    main()
