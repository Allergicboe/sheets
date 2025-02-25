import streamlit as st
import streamlit.components.v1 as components
import gspread
from google.oauth2 import service_account
import re
import math
import time
import threading
import pandas as pd
from datetime import datetime

# Configuración de la página
st.set_page_config(
    page_title="Formulario de Planilla",
    page_icon="📄",
    layout="wide"
)

# Inyectar CSS para compactar la interfaz
st.markdown(
    """
    <style>
    /* Reducir márgenes y padding en el contenedor principal */
    .reportview-container .main .block-container {
        padding: 1rem;
        max-width: 800px;
    }
    /* Estilo para mostrar la hora de última actualización */
    .last-update {
        font-size: 12px;
        color: #888;
        text-align: right;
        margin-bottom: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# --- 1. Definición de mapeo de columnas ---
# Mapeo de nombres de campo a letras de columnas
COLUMNAS = {
    'cuenta_id': 0,            # A
    'cuenta_nombre': 1,        # B
    'campo_id': 2,             # C
    'campo_nombre': 3,         # D
    'sonda_id': 11,            # L
    'sonda_nombre': 10,        # K
    'ubicacion_sonda': 12,     # M
    'latitud_sonda': 13,       # N
    'longitud_sonda': 14,      # O
    'cultivo': 17,             # R
    'variedad': 18,            # S
    'ano_plantacion': 20,      # U
    'plantas_ha': 22,          # W - Ahora será densidad plantas/ha
    'plantas_total': 23,       # X - Ahora será número total de plantas
    'emisores_ha': 24,         # Y - Ahora será densidad emisores/ha
    'emisores_total': 25,      # Z - Ahora será número total de emisores
    'superficie_ha': 31,       # AF
    'superficie_m2': 32,       # AG
    'caudal_teorico': 33,      # AH
    'ppeq_mm_h': 34,           # AI
    'comentario': 41,          # AP
}

# --- 2. Inicialización del estado de la sesión ---
if 'current_row_index' not in st.session_state:
    st.session_state.current_row_index = 0
if 'sheet_data' not in st.session_state:
    st.session_state.sheet_data = []
if 'last_update_time' not in st.session_state:
    st.session_state.last_update_time = None
if 'update_running' not in st.session_state:
    st.session_state.update_running = False
if 'search_term' not in st.session_state:
    st.session_state.search_term = ""
if 'filtered_options' not in st.session_state:
    st.session_state.filtered_options = []

# --- 3. Funciones de Conexión y Carga de Datos ---
def init_connection():
    """Inicializa la conexión con Google Sheets."""
    try:
        credentials = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=[
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
        )
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        st.error(f"Error en la conexión: {str(e)}")
        return None

def load_sheet(client):
    """Carga la hoja de trabajo de Google Sheets."""
    try:
        return client.open_by_url(st.secrets["spreadsheet_url"]).sheet1
    except Exception as e:
        st.error(f"Error al cargar la planilla: {str(e)}")
        return None

# --- 4. Función para convertir DMS a DD ---
def dms_to_dd(dms):
    """Convierte coordenadas en formato DMS (grados, minutos, segundos) a DD (grados decimales)."""
    parts = re.split('[°\'"]+', dms)
    degrees = float(parts[0])
    minutes = float(parts[1])
    seconds = float(parts[2])
    direction = parts[3].strip()
    dd = degrees + minutes / 60 + seconds / 3600
    if direction in ['S', 'W']:
        dd *= -1
    return dd

# --- 5. Funciones para la actualización periódica de datos ---
def load_all_data():
    """Carga todos los datos de la planilla y actualiza el estado de la sesión."""
    client = init_connection()
    if not client:
        return False
    
    sheet = load_sheet(client)
    if not sheet:
        return False
    
    try:
        # Cargar todos los datos de la hoja
        all_data = sheet.get_all_values()
        
        # Actualizar el estado de la sesión
        st.session_state.sheet_data = all_data
        st.session_state.last_update_time = datetime.now()
        
        # Generar opciones de fila (omitiendo la fila de encabezados)
        row_options = [
            f"Fila {i} - Cuenta: {all_data[i-1][COLUMNAS['cuenta_nombre']]} (ID: {all_data[i-1][COLUMNAS['cuenta_id']]}) - Campo: {all_data[i-1][COLUMNAS['campo_nombre']]} (ID: {all_data[i-1][COLUMNAS['campo_id']]}) - Sonda: {all_data[i-1][COLUMNAS['sonda_nombre']]} (ID: {all_data[i-1][COLUMNAS['sonda_id']]})"
            for i in range(2, len(all_data))
        ]
        
        # Aplicar filtro si existe un término de búsqueda
        if st.session_state.search_term:
            st.session_state.filtered_options = [
                row for row in row_options 
                if st.session_state.search_term.lower() in row.lower()
            ]
        else:
            st.session_state.filtered_options = row_options
            
        return True
    except Exception as e:
        st.error(f"Error al cargar datos: {str(e)}")
        return False

def background_update():
    """Función para actualizar los datos en segundo plano."""
    while st.session_state.update_running:
        # Actualizar los datos
        success = load_all_data()
        if not success:
            st.warning("Error en la actualización automática de datos.")
        
        # Esperar 120 segundos antes de la próxima actualización
        time.sleep(120)

def start_background_update():
    """Inicia el hilo de actualización en segundo plano."""
    if not st.session_state.update_running:
        st.session_state.update_running = True
        update_thread = threading.Thread(target=background_update)
        update_thread.daemon = True  # El hilo terminará cuando el programa principal termine
        update_thread.start()

# --- 6. Función de acceso seguro a datos ---
def get_safe_value(row_data, col_key, default=''):
    """Obtiene de forma segura un valor de la fila de datos por su clave del mapeo."""
    col_idx = COLUMNAS.get(col_key)
    if col_idx is None:
        return default
    if len(row_data) > col_idx:
        return row_data[col_idx]
    return default

# --- 7. Función para obtener la letra de columna a partir del índice ---
def get_column_letter(col_idx):
    """Convierte un índice numérico a letra de columna de Excel."""
    result = ""
    while col_idx >= 0:
        remainder = col_idx % 26
        result = chr(65 + remainder) + result
        col_idx = col_idx // 26 - 1
    return result

# --- 8. Función Principal ---
def main():
    """Función principal que gestiona la interfaz de usuario y el flujo de datos."""
    
    # Cargar datos si aún no se han cargado
    if not st.session_state.sheet_data:
        with st.spinner("Cargando datos de la planilla..."):
            load_all_data()
    
    # Iniciar la actualización en segundo plano si aún no se ha iniciado
    start_background_update()
    
    # Verificar si tenemos datos cargados
    if not st.session_state.sheet_data:
        st.error("No se pudieron cargar los datos. Por favor, recarga la página.")
        return
    
    all_rows = st.session_state.sheet_data
    
    # Barra lateral: búsqueda, selección y edición del comentario
    with st.sidebar:
        st.subheader("Buscar Fila")
        search_term = st.text_input(
            "Buscar por término (Cuenta, Campo, Sonda...)", 
            value=st.session_state.search_term,
            key="search_input"
        )
        
        # Actualizar término de búsqueda si cambió
        if search_term != st.session_state.search_term:
            st.session_state.search_term = search_term
            # Regenerar opciones filtradas
            row_options = [
                f"Fila {i} - Cuenta: {all_rows[i-1][COLUMNAS['cuenta_nombre']]} (ID: {all_rows[i-1][COLUMNAS['cuenta_id']]}) - Campo: {all_rows[i-1][COLUMNAS['campo_nombre']]} (ID: {all_rows[i-1][COLUMNAS['campo_id']]}) - Sonda: {all_rows[i-1][COLUMNAS['sonda_nombre']]} (ID: {all_rows[i-1][COLUMNAS['sonda_id']]})"
                for i in range(2, len(all_rows))
            ]
            if search_term:
                st.session_state.filtered_options = [row for row in row_options if search_term.lower() in row.lower()]
            else:
                st.session_state.filtered_options = row_options
        
        filtered_options = st.session_state.filtered_options
        
        if len(filtered_options) > 0:
            # Mostrar la hora de la última actualización
            if st.session_state.last_update_time:
                st.markdown(
                    f"<div class='last-update'>Última actualización: {st.session_state.last_update_time.strftime('%H:%M:%S')}</div>",
                    unsafe_allow_html=True
                )
            
            selected_row = st.selectbox(
                "Selecciona una fila", 
                filtered_options,
                index=min(st.session_state.current_row_index, len(filtered_options) - 1),
                key="row_selector"
            )
            st.session_state.current_row_index = filtered_options.index(selected_row)
        else:
            st.warning("No se encontraron filas que coincidan con el término de búsqueda.")
            return
    
    # Obtener datos de la fila seleccionada
    selected_row_index = int(selected_row.split(" ")[1])
    row_data = all_rows[selected_row_index - 1]  # -1 porque los índices en la UI comienzan en 1
    
    # Información de la fila y comentario editable en la barra lateral
    with st.sidebar:
        st.subheader("Información de la fila seleccionada")
        st.write(f"**Cuenta:** {get_safe_value(row_data, 'cuenta_nombre')} [ID: {get_safe_value(row_data, 'cuenta_id')}]")
        st.write(f"**Campo:** {get_safe_value(row_data, 'campo_nombre')} [ID: {get_safe_value(row_data, 'campo_id')}]")
        st.write(f"**Sonda:** {get_safe_value(row_data, 'sonda_nombre')} [ID: {get_safe_value(row_data, 'sonda_id')}]")
        
        cuenta_id = get_safe_value(row_data, 'cuenta_id')
        campo_id = get_safe_value(row_data, 'campo_id')
        sonda_id = get_safe_value(row_data, 'sonda_id')
        
        st.markdown(
            "[Ver Campo](https://www.dropcontrol.com/site/dashboard/campo.do"
            f"?cuentaId={cuenta_id}&campoId={campo_id})"
            " | "
            "[Ver Sonda](https://www.dropcontrol.com/site/ha/suelo.do"
            f"?cuentaId={cuenta_id}&campoId={campo_id}&sectorId={sonda_id})"
             " | "
            f"[Ver Admin](https://admin.dropcontrol.com/farms/zone?farm={campo_id}&zone={sonda_id})"
        )
        
        sidebar_comment = st.text_area(
            "**Comentario Actual:**", 
            value=get_safe_value(row_data, 'comentario'), 
            key=f"sidebar_comment_{selected_row_index}"  # Clave única
        )
        
        # Botón para actualizar comentario desde la barra lateral
        if st.button("Actualizar comentario"):
            current_comment = get_safe_value(row_data, 'comentario')
            if sidebar_comment != current_comment:
                try:
                    # Iniciamos una nueva conexión para actualizar el comentario
                    client = init_connection()
                    if client:
                        sheet = load_sheet(client)
                        if sheet:
                            # Actualiza la celda del comentario
                            col_letter = get_column_letter(COLUMNAS['comentario'])
                            sheet.update(f"{col_letter}{selected_row_index}", [[sidebar_comment]])
                            st.success("Comentario actualizado desde la barra lateral.")
                            
                            # Forzar recarga de datos
                            load_all_data()
                except Exception as e:
                    st.error("Error actualizando comentario: " + str(e))
            else:
                st.info("No se detectaron cambios en el comentario.")
    
    # Formulario de edición en la zona principal
    st.subheader("Formulario de Edición")
    
    # --- BOTÓN PARA ACCEDER A LA PLANILLA DE GOOGLE ---
    SPREADSHEET_URL = st.secrets["spreadsheet_url"]
    html_button = f"""
    <div style="text-align: left; margin-bottom: 10px;">
        <a href="{SPREADSHEET_URL}" target="_blank">
            <button style="
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 6px 12px;
                text-align: center;
                text-decoration: none;
                display: inline-block;
                font-size: 14px;
                border-radius: 5px;
                cursor: pointer;">
                Abrir Planilla de Google
            </button>
        </a>
    </div>
    """
    components.html(html_button, height=50)
    
        # Inicio del formulario de edición
    form_key = f"edit_form_{selected_row_index}"  # Clave única para el formulario basada en la fila
    with st.form(key=form_key):
        col1, col2, col3 = st.columns(3)
        with col1:
            ubicacion_sonda = st.text_input(
                "Ubicación sonda google maps", 
                value=get_safe_value(row_data, 'ubicacion_sonda'),
                key=f"ubicacion_{selected_row_index}"  # Clave única
            )
            cultivo = st.text_input(
                "Cultivo", 
                value=get_safe_value(row_data, 'cultivo'),
                key=f"cultivo_{selected_row_index}"  # Clave única
            )
            variedad = st.text_input(
                "Variedad", 
                value=get_safe_value(row_data, 'variedad'),
                key=f"variedad_{selected_row_index}"  # Clave única
            )
            ano_plantacion = st.text_input(
                "Año plantación", 
                value=get_safe_value(row_data, 'ano_plantacion'),
                key=f"ano_{selected_row_index}"  # Clave única
            )
        with col2:
            plantas_total = st.text_input(
                "N° plantas (total)", 
                value=get_safe_value(row_data, 'plantas_total'),
                key=f"plantas_{selected_row_index}"  # Clave única
            )
            emisores_total = st.text_input(
                "N° emisores (total)", 
                value=get_safe_value(row_data, 'emisores_total'),
                key=f"emisores_{selected_row_index}"  # Clave única
            )
            superficie_ha = st.text_input(
                "Superficie (ha)", 
                value=get_safe_value(row_data, 'superficie_ha'),
                key=f"superficie_{selected_row_index}"  # Clave única
            )
            caudal_teorico = st.text_input(
                "Caudal teórico (m3/h)", 
                value=get_safe_value(row_data, 'caudal_teorico'),
                key=f"caudal_{selected_row_index}"  # Clave única
            )
            ppeq_mm_h = st.text_input(
                "PPeq [mm/h]", 
                value=get_safe_value(row_data, 'ppeq_mm_h'),
                key=f"ppeq_{selected_row_index}"  # Clave única
            )
        with col3:
            st.markdown("**Comentarios (selección rápida):**")
            comentarios_lista = [
                "La cuenta no existe", "La sonda no existe o no está asociada",
                "Sonda no georreferenciable", "La sonda no tiene sensores habilitados",
                "La sonda no está operando", "No hay datos de cultivo",
                "Datos de cultivo incompletos", "Datos de cultivo no son reales",
                "Consultar datos faltantes"
            ]
            comentarios_actuales = get_safe_value(row_data, 'comentario').split(", ") if get_safe_value(row_data, 'comentario') else []
            comentarios_seleccionados = []
            for i, comentario in enumerate(comentarios_lista):
                is_checked = comentario in comentarios_actuales
                if st.checkbox(comentario, value=is_checked, key=f"cb_{i}_{selected_row_index}"):  # Clave única
                    comentarios_seleccionados.append(comentario)
        
        # Botones de acción en el formulario principal
        c1, c2 = st.columns(2)
        with c1:
            submit_button = st.form_submit_button(label="Guardar cambios", type="primary")
        with c2:
            next_button = st.form_submit_button(
                label="Siguiente fila",
                help="Ir a la siguiente fila en la lista filtrada"
            )
        
        # Procesar los envíos del formulario
        if submit_button or next_button:
            # Si se presiona "Siguiente fila", se salta el guardado y se avanza a la siguiente fila
            if next_button:
                if st.session_state.current_row_index < len(filtered_options) - 1:
                    st.session_state.current_row_index += 1
                    st.rerun()
                else:
                    st.warning("Ya estás en la última fila de la lista filtrada.")
            else:
                # Iniciar conexión para guardar cambios
                client = init_connection()
                if not client:
                    st.error("No se pudo establecer conexión para guardar cambios.")
                    return
                
                sheet = load_sheet(client)
                if not sheet:
                    st.error("No se pudo cargar la hoja para guardar cambios.")
                    return
                
                cambios_realizados = []
                batch_data = {}
                
                # --- Ubicación y conversión de coordenadas (DMS a DD) ---
                current_ubicacion = get_safe_value(row_data, 'ubicacion_sonda')
                if ubicacion_sonda.strip() != current_ubicacion.strip():
                    if ubicacion_sonda.strip():
                        lat_parts = ubicacion_sonda.split()
                        if len(lat_parts) >= 2:
                            try:
                                latitud_dd = dms_to_dd(lat_parts[0])
                                longitud_dd = dms_to_dd(lat_parts[1])
                                latitud_sonda = f"{latitud_dd:.8f}".replace(".", ",")
                                longitud_sonda = f"{longitud_dd:.8f}".replace(".", ",")
                                batch_data[f"{get_column_letter(COLUMNAS['ubicacion_sonda'])}{selected_row_index}"] = ubicacion_sonda
                                batch_data[f"{get_column_letter(COLUMNAS['latitud_sonda'])}{selected_row_index}"] = latitud_sonda
                                batch_data[f"{get_column_letter(COLUMNAS['longitud_sonda'])}{selected_row_index}"] = longitud_sonda
                                cambios_realizados.append("Ubicación sonda actualizada")
                            except Exception as e:
                                st.warning(f"Error al convertir la ubicación: {str(e)}; se mantendrá el valor anterior.")
                    else:
                        batch_data[f"{get_column_letter(COLUMNAS['ubicacion_sonda'])}{selected_row_index}"] = ""
                        batch_data[f"{get_column_letter(COLUMNAS['latitud_sonda'])}{selected_row_index}"] = ""
                        batch_data[f"{get_column_letter(COLUMNAS['longitud_sonda'])}{selected_row_index}"] = ""
                        cambios_realizados.append("Ubicación sonda actualizada")
                
                # --- Actualización de textos ---
                current_cultivo = get_safe_value(row_data, 'cultivo')
                if cultivo.strip() != current_cultivo.strip():
                    batch_data[f"{get_column_letter(COLUMNAS['cultivo'])}{selected_row_index}"] = cultivo
                    cambios_realizados.append("Cultivo actualizado")
                
                current_variedad = get_safe_value(row_data, 'variedad')
                if variedad.strip() != current_variedad.strip():
                    batch_data[f"{get_column_letter(COLUMNAS['variedad'])}{selected_row_index}"] = variedad
                    cambios_realizados.append("Variedad actualizada")
                
                # --- Procesar Año de plantación: eliminar comilla y convertir a número ---
                current_ano = get_safe_value(row_data, 'ano_plantacion')
                cleaned_ano = ano_plantacion.strip().lstrip("'")
                if cleaned_ano:
                    try:
                        ano_val = int(cleaned_ano)
                    except Exception:
                        ano_val = cleaned_ano
                else:
                    ano_val = ""
                if str(ano_val) != current_ano.strip().lstrip("'"):
                    batch_data[f"{get_column_letter(COLUMNAS['ano_plantacion'])}{selected_row_index}"] = ano_val
                    cambios_realizados.append("Año plantación actualizado")
                
                # --- Procesamiento de N° plantas y N° emisores (total) ---
                current_plantas_total = get_safe_value(row_data, 'plantas_total')
                current_emisores_total = get_safe_value(row_data, 'emisores_total')
                
                # Limpiar y procesar valores de entrada
                plantas_cleaned = plantas_total.strip().lstrip("'").replace(",", "")
                emisores_cleaned = emisores_total.strip().lstrip("'").replace(",", "")
                
                # Actualizar plantas total si cambió
                if plantas_cleaned != current_plantas_total.strip():
                    batch_data[f"{get_column_letter(COLUMNAS['plantas_total'])}{selected_row_index}"] = plantas_cleaned if plantas_cleaned else ""
                    cambios_realizados.append("N° plantas actualizado")
                
                # Actualizar emisores total si cambió
                if emisores_cleaned != current_emisores_total.strip():
                    batch_data[f"{get_column_letter(COLUMNAS['emisores_total'])}{selected_row_index}"] = emisores_cleaned if emisores_cleaned else ""
                    cambios_realizados.append("N° emisores actualizado")
                
                # --- Procesamiento de Superficie (ha) y Superficie (m2) ---
                current_superficie = get_safe_value(row_data, 'superficie_ha')
                cleaned_superficie = superficie_ha.strip().lstrip("'").replace(",", ".")
                try:
                    superficie_val = float(cleaned_superficie) if cleaned_superficie else ""
                except Exception:
                    superficie_val = cleaned_superficie
                
                row_data_superficie = current_superficie.strip().lstrip("'").replace(",", ".")
                try:
                    current_superficie_val = float(row_data_superficie) if row_data_superficie else ""
                except Exception:
                    current_superficie_val = row_data_superficie
                
                if superficie_val != current_superficie_val:
                    if superficie_val != "":
                        try:
                            superficie_m2 = float(superficie_val) * 10000
                            batch_data[f"{get_column_letter(COLUMNAS['superficie_ha'])}{selected_row_index}"] = superficie_val
                            batch_data[f"{get_column_letter(COLUMNAS['superficie_m2'])}{selected_row_index}"] = superficie_m2
                            cambios_realizados.append("Superficie actualizada")
                        except Exception as e:
                            st.warning(f"Error al procesar superficie: {str(e)}; se mantendrá el valor anterior.")
                    else:
                        batch_data[f"{get_column_letter(COLUMNAS['superficie_ha'])}{selected_row_index}"] = ""
                        batch_data[f"{get_column_letter(COLUMNAS['superficie_m2'])}{selected_row_index}"] = ""
                        cambios_realizados.append("Superficie actualizada")
                
                # --- Cálculo de densidades para N° plantas/ha y N° emisores/ha ---
                # Solo calculamos densidades si tenemos superficie y los valores correspondientes
                if (plantas_cleaned or emisores_cleaned) and superficie_val not in ["", None, 0]:
                    try:
                        # Calcular densidad de plantas/ha si tenemos datos de plantas
                        if plantas_cleaned:
                            plantas_int = int(plantas_cleaned)
                            densidad_plantas = math.ceil(plantas_int / float(superficie_val))
                            batch_data[f"{get_column_letter(COLUMNAS['plantas_ha'])}{selected_row_index}"] = densidad_plantas
                            cambios_realizados.append("Densidad plantas/ha actualizada")
                        
                        # Calcular densidad de emisores/ha si tenemos datos de emisores
                        if emisores_cleaned:
                            emisores_int = int(emisores_cleaned)
                            densidad_emisores = math.ceil(emisores_int / float(superficie_val))
                            batch_data[f"{get_column_letter(COLUMNAS['emisores_ha'])}{selected_row_index}"] = densidad_emisores
                            cambios_realizados.append("Densidad emisores/ha actualizada")
                            
                    except Exception as e:
                        st.warning(f"Error al calcular densidades: {str(e)}")
                else:
                    # Si no tenemos superficie o valores, limpiamos los campos de densidad
                    if not superficie_val or superficie_val in ["", None, 0]:
                        batch_data[f"{get_column_letter(COLUMNAS['plantas_ha'])}{selected_row_index}"] = ""
                        batch_data[f"{get_column_letter(COLUMNAS['emisores_ha'])}{selected_row_index}"] = ""
                        cambios_realizados.append("Densidades limpiadas (falta superficie)")
                
                # --- Actualización de Caudal teórico (m3/h) ---
                current_caudal = get_safe_value(row_data, 'caudal_teorico')
                cleaned_caudal = caudal_teorico.strip().lstrip("'").replace(",", ".")
                try:
                    caudal_val = float(cleaned_caudal) if cleaned_caudal else ""
                except Exception:
                    caudal_val = cleaned_caudal
                
                row_data_caudal = current_caudal.strip().lstrip("'").replace(",", ".")
                try:
                    current_caudal_val = float(row_data_caudal) if row_data_caudal else ""
                except Exception:
                    current_caudal_val = row_data_caudal
                
                if caudal_val != current_caudal_val:
                    batch_data[f"{get_column_letter(COLUMNAS['caudal_teorico'])}{selected_row_index}"] = caudal_val
                    cambios_realizados.append("Caudal teórico actualizado")
                
                # --- Actualización de PPeq [mm/h] ---
                current_ppeq = get_safe_value(row_data, 'ppeq_mm_h')
                cleaned_ppeq = ppeq_mm_h.strip().lstrip("'").replace(",", ".")
                try:
                    ppeq_val = float(cleaned_ppeq) if cleaned_ppeq else ""
                except Exception:
                    ppeq_val = cleaned_ppeq
                
                row_data_ppeq = current_ppeq.strip().lstrip("'").replace(",", ".")
                try:
                    current_ppeq_val = float(row_data_ppeq) if row_data_ppeq else ""
                except Exception:
                    current_ppeq_val = row_data_ppeq
                
                if ppeq_val != current_ppeq_val:
                    batch_data[f"{get_column_letter(COLUMNAS['ppeq_mm_h'])}{selected_row_index}"] = ppeq_val
                    cambios_realizados.append("PPeq actualizado")
                
                # --- Actualización de comentarios vía checkboxes ---
                if comentarios_seleccionados:
                    nuevo_comentario = ", ".join(comentarios_seleccionados)
                    current_comment = row_data[41] if len(row_data) > 41 else ""
                    if nuevo_comentario != current_comment.strip():
                        batch_data[f"AP{selected_row_index}"] = nuevo_comentario
                        cambios_realizados.append("Comentarios actualizados (checkboxes)")
                
                # Actualizar solo si se detectaron cambios
                if batch_data:
                    try:
                        sheet.batch_update([{"range": k, "values": [[v]]} for k, v in batch_data.items()])
                        st.success("Cambios guardados correctamente:")
                        for cambio in cambios_realizados:
                            st.write(f"- {cambio}")
                        
                        # Forzar una recarga de datos después de guardar cambios
                        load_all_data()
                    except Exception as e:
                        st.error(f"Error al guardar cambios: {str(e)}")
                else:
                    st.info("No se detectaron cambios para guardar.")

# Punto de entrada de la aplicación
if __name__ == "__main__":
    main()
