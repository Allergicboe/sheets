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

# --- 1. Inicialización del estado de la sesión ---
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

# --- 2. Funciones de Conexión y Carga de Datos ---
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

# --- 3. Función para convertir DMS a DD ---
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

# --- 4. Funciones para la actualización periódica de datos ---
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
            f"Fila {i} - Cuenta: {all_data[i-1][1]} (ID: {all_data[i-1][0]}) - Campo: {all_data[i-1][3]} (ID: {all_data[i-1][2]}) - Sonda: {all_data[i-1][10]} (ID: {all_data[i-1][11]})"
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

# --- 5. Función Principal ---
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
                f"Fila {i} - Cuenta: {all_rows[i-1][1]} (ID: {all_rows[i-1][0]}) - Campo: {all_rows[i-1][3]} (ID: {all_rows[i-1][2]}) - Sonda: {all_rows[i-1][10]} (ID: {all_rows[i-1][11]})"
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
        st.write(f"**Cuenta:** {row_data[1]} [ID: {row_data[0]}]")
        st.write(f"**Campo:** {row_data[3]} [ID: {row_data[2]}]")
        st.write(f"**Sonda:** {row_data[10]} [ID: {row_data[11]}]")
        st.markdown(
            "[Ver Campo](https://www.dropcontrol.com/site/dashboard/campo.do"
            f"?cuentaId={row_data[0]}&campoId={row_data[2]})"
            " | "
            "[Ver Sonda](https://www.dropcontrol.com/site/ha/suelo.do"
            f"?cuentaId={row_data[0]}&campoId={row_data[2]}&sectorId={row_data[11]})"
             " | "
            f"[Ver Admin](https://admin.dropcontrol.com/farms/zone?farm={row_data[2]}&zone={row_data[11]})"
        )
        sidebar_comment = st.text_area("**Comentario Actual:**", value=row_data[41] if len(row_data) > 41 else "", key="sidebar_comment")
        
        # Botón para actualizar comentario desde la barra lateral
        if st.button("Actualizar comentario"):
            current_comment = row_data[41] if len(row_data) > 41 else ""
            if sidebar_comment != current_comment:
                try:
                    # Iniciamos una nueva conexión para actualizar el comentario
                    client = init_connection()
                    if client:
                        sheet = load_sheet(client)
                        if sheet:
                            # Actualiza la celda del comentario (columna AP)
                            sheet.update(f"AP{selected_row_index}", [[sidebar_comment]])
                            st.success("Comentario actualizado desde la barra lateral.")
                            
                            # Actualizar los datos locales
                            if len(row_data) > 41:
                                row_data[41] = sidebar_comment
                            elif len(row_data) == 41:
                                row_data.append(sidebar_comment)
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
    with st.form(key='edit_form'):
        col1, col2, col3 = st.columns(3)
        with col1:
            ubicacion_sonda = st.text_input(
                "Ubicación sonda google maps", 
                value=row_data[12] if len(row_data) > 12 else ""
            )
            cultivo = st.text_input(
                "Cultivo", 
                value=row_data[17] if len(row_data) > 17 else ""
            )
            variedad = st.text_input(
                "Variedad", 
                value=row_data[18] if len(row_data) > 18 else ""
            )
            ano_plantacion = st.text_input(
                "Año plantación", 
                value=row_data[20] if len(row_data) > 20 else ""
            )
        with col2:
            plantas_ha = st.text_input(
                "N° plantas", 
                value=row_data[22] if len(row_data) > 22 else ""
            )
            emisores_ha = st.text_input(
                "N° emisores", 
                value=row_data[24] if len(row_data) > 24 else ""
            )
            superficie_ha = st.text_input(
                "Superficie (ha)", 
                value=row_data[31] if len(row_data) > 31 else ""
            )
            caudal_teorico = st.text_input(
                "Caudal teórico (m3/h)", 
                value=row_data[33] if len(row_data) > 33 else ""
            )
            ppeq_mm_h = st.text_input(
                "PPeq [mm/h]", 
                value=row_data[34] if len(row_data) > 34 else ""
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
            comentarios_actuales = row_data[41].split(", ") if len(row_data) > 41 and row_data[41] else []
            comentarios_seleccionados = []
            for i, comentario in enumerate(comentarios_lista):
                is_checked = comentario in comentarios_actuales
                if st.checkbox(comentario, value=is_checked, key=f"cb_{i}"):
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
                current_ubicacion = row_data[12] if len(row_data) > 12 else ""
                if ubicacion_sonda.strip() != current_ubicacion.strip():
                    if ubicacion_sonda.strip():
                        lat_parts = ubicacion_sonda.split()
                        if len(lat_parts) >= 2:
                            try:
                                latitud_dd = dms_to_dd(lat_parts[0])
                                longitud_dd = dms_to_dd(lat_parts[1])
                                latitud_sonda = f"{latitud_dd:.8f}".replace(".", ",")
                                longitud_sonda = f"{longitud_dd:.8f}".replace(".", ",")
                                batch_data[f"M{selected_row_index}"] = ubicacion_sonda
                                batch_data[f"N{selected_row_index}"] = latitud_sonda
                                batch_data[f"O{selected_row_index}"] = longitud_sonda
                                cambios_realizados.append("Ubicación sonda actualizada")
                            except Exception as e:
                                st.warning(f"Error al convertir la ubicación: {str(e)}; se mantendrá el valor anterior.")
                    else:
                        batch_data[f"M{selected_row_index}"] = ""
                        batch_data[f"N{selected_row_index}"] = ""
                        batch_data[f"O{selected_row_index}"] = ""
                        cambios_realizados.append("Ubicación sonda actualizada")
                
                # --- Actualización de textos ---
                current_cultivo = row_data[17] if len(row_data) > 17 else ""
                if cultivo.strip() != current_cultivo.strip():
                    batch_data[f"R{selected_row_index}"] = cultivo
                    cambios_realizados.append("Cultivo actualizado")
                
                current_variedad = row_data[18] if len(row_data) > 18 else ""
                if variedad.strip() != current_variedad.strip():
                    batch_data[f"S{selected_row_index}"] = variedad
                    cambios_realizados.append("Variedad actualizada")
                
                # --- Procesar Año de plantación: eliminar comilla y convertir a número ---
                current_ano = row_data[20] if len(row_data) > 20 else ""
                cleaned_ano = ano_plantacion.strip().lstrip("'")
                if cleaned_ano:
                    try:
                        ano_val = int(cleaned_ano)
                    except Exception:
                        ano_val = cleaned_ano
                else:
                    ano_val = ""
                if str(ano_val) != current_ano.strip().lstrip("'"):
                    batch_data[f"U{selected_row_index}"] = ano_val
                    cambios_realizados.append("Año plantación actualizado")
                
                # --- Procesamiento de plantas por hectárea ---
                current_plantas = row_data[22] if len(row_data) > 22 else ""
                if plantas_ha.strip() != current_plantas.strip():
                    batch_data[f"W{selected_row_index}"] = plantas_ha.strip()
                    cambios_realizados.append("N° plantas actualizado")
                
                # --- Procesamiento de emisores por hectárea ---
                current_emisores = row_data[24] if len(row_data) > 24 else ""
                if emisores_ha.strip() != current_emisores.strip():
                    batch_data[f"Y{selected_row_index}"] = emisores_ha.strip()
                    cambios_realizados.append("N° emisores actualizado")
                
                # --- Procesamiento de Superficie (ha) y Superficie (m2) ---
                current_superficie = row_data[31] if len(row_data) > 31 else ""
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
                            batch_data[f"AF{selected_row_index}"] = superficie_val  # Superficie en ha (número)
                            batch_data[f"AG{selected_row_index}"] = superficie_m2   # Superficie en m2 (número)
                            cambios_realizados.append("Superficie actualizada")
                        except Exception as e:
                            st.warning(f"Error al procesar superficie: {str(e)}; se mantendrá el valor anterior.")
                    else:
                        batch_data[f"AF{selected_row_index}"] = ""
                        batch_data[f"AG{selected_row_index}"] = ""
                        cambios_realizados.append("Superficie actualizada")
                
                # --- Cálculo de densidades para N° plantas y N° emisores ---
                plantas_input = plantas_ha.strip().lstrip("'").replace(",", "")
                emisores_input = emisores_ha.strip().lstrip("'").replace(",", "")
                superficie_norm = superficie_ha.strip().replace(",", ".")
                
                current_plantas_val = current_plantas.strip().replace(",", "")
                current_emisores_val = current_emisores.strip().replace(",", "")
                current_superficie_norm = current_superficie.strip().replace(",", ".")
                
                if (plantas_input != current_plantas_val or
                    emisores_input != current_emisores_val or
                    superficie_norm != current_superficie_norm):
                    try:
                        if plantas_input and emisores_input and superficie_val not in ["", None, 0]:
                            plantas_int = int(plantas_input)
                            emisores_int = int(emisores_input)
                            densidad_plantas = math.ceil(plantas_int / float(superficie_val))
                            densidad_emisores = math.ceil(emisores_int / float(superficie_val))
                            batch_data[f"W{selected_row_index}"] = plantas_int
                            batch_data[f"X{selected_row_index}"] = densidad_plantas
                            batch_data[f"Y{selected_row_index}"] = emisores_int
                            batch_data[f"Z{selected_row_index}"] = densidad_emisores
                            cambios_realizados.append("Densidad (N° plantas y emisores) actualizada")
                        else:
                            # Solo actualizar los valores de entrada pero dejar en blanco los cálculos
                            if plantas_input != current_plantas_val:
                                batch_data[f"W{selected_row_index}"] = plantas_input if plantas_input else ""
                            if emisores_input != current_emisores_val:
                                batch_data[f"Y{selected_row_index}"] = emisores_input if emisores_input else ""
                            # Si falta algún dato para el cálculo, limpiar los campos calculados
                            if not plantas_input or not emisores_input or not superficie_val:
                                batch_data[f"X{selected_row_index}"] = ""  # Densidad plantas
                                batch_data[f"Z{selected_row_index}"] = ""  # Densidad emisores
                            cambios_realizados.append("Valores de plantas y emisores actualizados")
                    except Exception as e:
                        st.warning(f"Error al calcular densidad: {str(e)}")
                
                # --- Actualización de Caudal teórico (m3/h) ---
                current_caudal = row_data[33] if len(row_data) > 33 else ""
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
                    batch_data[f"AH{selected_row_index}"] = caudal_val
                    cambios_realizados.append("Caudal teórico actualizado")
                
                # --- Actualización de PPeq [mm/h] ---
                current_ppeq = row_data[34] if len(row_data) > 34 else ""
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
                    batch_data[f"AI{selected_row_index}"] = ppeq_val
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
