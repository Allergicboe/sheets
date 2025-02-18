import streamlit as st
import streamlit.components.v1 as components
import gspread
from google.oauth2 import service_account
import re
import math

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
    </style>
    """,
    unsafe_allow_html=True
)

# --- 2. Funciones de Conexión y Carga de Datos ---
def init_connection():
    """Función para inicializar la conexión con Google Sheets."""
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
    """Función para cargar la hoja de trabajo de Google Sheets."""
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

# --- 4. Función Principal ---
def main():
    """Función principal que gestiona la interfaz de usuario y el flujo de datos."""
    
    # Inicializar el estado de la sesión para el índice de fila seleccionada si no existe
    if 'current_row_index' not in st.session_state:
        st.session_state.current_row_index = 0

    # Inicializar conexión y cargar hoja
    client = init_connection()
    if not client:
        return
    sheet = load_sheet(client)
    if not sheet:
        return

    all_rows = sheet.get_all_values()
    # Generar lista de opciones para filas (omitimos la primera fila de encabezados)
    row_options = [
        f"Fila {i} - Cuenta: {all_rows[i-1][1]} (ID: {all_rows[i-1][0]}) - Campo: {all_rows[i-1][3]} (ID: {all_rows[i-1][2]}) - Sonda: {all_rows[i-1][10]} (ID: {all_rows[i-1][11]})"
        for i in range(2, len(all_rows))
    ]

    # Barra lateral: búsqueda, selección y edición del comentario
    with st.sidebar:
        st.subheader("Buscar Fila")
        search_term = st.text_input("Buscar por término (Cuenta, Campo, Sonda...)", "")
        filtered_options = row_options
        if search_term:
            filtered_options = [row for row in row_options if search_term.lower() in row.lower()]
        
        if len(filtered_options) > 0:
            selected_row = st.selectbox(
                "Selecciona una fila", 
                filtered_options,
                index=min(st.session_state.current_row_index, len(filtered_options) - 1)
            )
            st.session_state.current_row_index = filtered_options.index(selected_row)
        else:
            st.warning("No se encontraron filas que coincidan con el término de búsqueda.")
            return

    # Obtener datos de la fila seleccionada
    selected_row_index = int(selected_row.split(" ")[1])
    row_data = sheet.row_values(selected_row_index)

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
            "[Ver Admin](https://admin.dropcontrol.com/farms/zone?farm={row_data[2]}&zone={row_data[11]})"
        )
        sidebar_comment = st.text_area("**Comentario Actual:**", value=row_data[41], key="sidebar_comment")
        if st.button("Actualizar comentario"):
            if sidebar_comment != row_data[41]:
                try:
                    # Actualiza la celda del comentario (columna AN)
                    sheet.update(f"AN{selected_row_index}", [[sidebar_comment]])
                    st.success("Comentario actualizado desde la barra lateral.")
                except Exception as e:
                    st.error("Error actualizando comentario: " + str(e))
            else:
                st.info("No se detectaron cambios en el comentario.")

    # Formulario de edición en la zona principal
    st.subheader("Formulario de Edición")
    
    # --- BOTÓN PARA ACCEDER A LA PLANILLA DE GOOGLE (debajo del encabezado y más pequeño) ---
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
            ubicacion_sonda = st.text_input("Ubicación sonda google maps", value=row_data[12])
            cultivo = st.text_input("Cultivo", value=row_data[17])
            variedad = st.text_input("Variedad", value=row_data[18])
            ano_plantacion = st.text_input("Año plantación", value=row_data[20])
        with col2:
            plantas_ha = st.text_input("N° plantas", value=row_data[22])
            emisores_ha = st.text_input("N° emisores", value=row_data[24])
            superficie_ha = st.text_input("Superficie (ha)", value=row_data[31])
            caudal_teorico = st.text_input("Caudal teórico (m3/h)", value=row_data[33])
            ppeq_mm_h = st.text_input("PPeq [mm/h]", value=row_data[34])
        with col3:
            st.markdown("**Comentarios (selección rápida):**")
            comentarios_lista = [
                "La cuenta no existe", "La sonda no existe o no está asociada",
                "Sonda no georreferenciable", "La sonda no tiene sensores habilitados",
                "La sonda no está operando", "No hay datos de cultivo",
                "Datos de cultivo incompletos", "Datos de cultivo no son reales",
                "Consultar datos faltantes"
            ]
            comentarios_seleccionados = []
            for i, comentario in enumerate(comentarios_lista):
                if st.checkbox(comentario, key=f"cb_{i}"):
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
                cambios_realizados = []
                batch_data = {}

                # --- Ubicación y conversión de coordenadas (DMS a DD) ---
                if ubicacion_sonda.strip() != row_data[12].strip():
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
                                st.warning("Error al convertir la ubicación; se mantendrá el valor anterior.")
                    else:
                        batch_data[f"M{selected_row_index}"] = ""
                        batch_data[f"N{selected_row_index}"] = ""
                        batch_data[f"O{selected_row_index}"] = ""
                        cambios_realizados.append("Ubicación sonda actualizada")

                # --- Actualización de textos ---
                if cultivo.strip() != row_data[17].strip():
                    batch_data[f"R{selected_row_index}"] = cultivo
                    cambios_realizados.append("Cultivo actualizado")
                if variedad.strip() != row_data[18].strip():
                    batch_data[f"S{selected_row_index}"] = variedad
                    cambios_realizados.append("Variedad actualizada")
                if ano_plantacion.strip() != row_data[20].strip():
                    batch_data[f"U{selected_row_index}"] = ano_plantacion
                    cambios_realizados.append("Año plantación actualizado")

                # --- Procesamiento de superficie ---
                superficie_input = superficie_ha.strip().replace(",", ".")
                if superficie_input != row_data[31].strip().replace(",", "."):
                    if superficie_input:  # Si se ingresó un valor
                        try:
                            superficie_float = float(superficie_input)
                            superficie_m2 = superficie_float * 10000
                            batch_data[f"AD{selected_row_index}"] = superficie_ha.strip()
                            batch_data[f"AE{selected_row_index}"] = f"{superficie_m2}".replace(".", ",")
                            cambios_realizados.append("Superficie actualizada")
                        except Exception as e:
                            st.warning("Error al procesar superficie; se mantendrá el valor anterior.")
                    else:
                        batch_data[f"AD{selected_row_index}"] = ""
                        batch_data[f"AE{selected_row_index}"] = ""
                        cambios_realizados.append("Superficie actualizada")
                if superficie_input:
                    try:
                        superficie_float = float(superficie_input)
                    except Exception:
                        superficie_float = 0
                else:
                    superficie_float = None

                # --- Cálculo de densidades para N° plantas y N° emisores ---
                plantas_input = plantas_ha.strip().replace(",", "")
                emisores_input = emisores_ha.strip().replace(",", "")
                superficie_norm = superficie_ha.strip().replace(",", ".")
                if (plantas_input != row_data[22].strip().replace(",", "") or
                    emisores_input != row_data[24].strip().replace(",", "") or
                    superficie_norm != row_data[31].strip().replace(",", ".")):
                    try:
                        if plantas_input and emisores_input and superficie_input and superficie_float not in [None, 0]:
                            plantas_int = int(plantas_input)
                            emisores_int = int(emisores_input)
                            densidad_plantas = math.ceil(plantas_int / superficie_float)
                            densidad_emisores = math.ceil(emisores_int / superficie_float)
                            batch_data[f"W{selected_row_index}"] = str(densidad_plantas)
                            batch_data[f"X{selected_row_index}"] = str(densidad_emisores)
                            cambios_realizados.append("Densidad (N° plantas y emisores) actualizada")
                        else:
                            batch_data[f"W{selected_row_index}"] = ""
                            batch_data[f"X{selected_row_index}"] = ""
                            cambios_realizados.append("Densidad (N° plantas y emisores) actualizada")
                    except Exception as e:
                        st.warning("Error al calcular densidad: " + str(e))

                if caudal_teorico.strip() != row_data[33].strip():
                    batch_data[f"AF{selected_row_index}"] = caudal_teorico
                    cambios_realizados.append("Caudal teórico actualizado")
                if ppeq_mm_h.strip() != row_data[34].strip():
                    batch_data[f"AG{selected_row_index}"] = ppeq_mm_h
                    cambios_realizados.append("PPeq actualizado")

                # --- Actualización de comentarios vía checkboxes ---
                if comentarios_seleccionados:
                    nuevo_comentario = ", ".join(comentarios_seleccionados)
                    if nuevo_comentario != row_data[41].strip():
                        batch_data[f"AN{selected_row_index}"] = nuevo_comentario
                        cambios_realizados.append("Comentarios actualizados (checkboxes)")

                # Actualizar solo si se detectaron cambios
                if batch_data:
                    sheet.batch_update([{"range": k, "values": [[v]]} for k, v in batch_data.items()])
                    st.success("Cambios guardados correctamente:")
                    for cambio in cambios_realizados:
                        st.write(f"- {cambio}")
                else:
                    st.info("No se detectaron cambios para guardar.")

if __name__ == "__main__":
    main()
