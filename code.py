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

def clean_numeric_value(value):
    """
    Limpia y formatea valores numéricos.
    Retorna None si el valor no es válido.
    """
    if not value:
        return None
    # Eliminar espacios y reemplazar coma por punto
    cleaned = value.strip().replace(',', '.')
    try:
        return float(cleaned)
    except ValueError:
        return None

def format_cell_value(value):
    """
    Formatea el valor para la celda de Google Sheets.
    Los números se envían sin comillas, los strings con ellas.
    """
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return value
    return str(value)

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
            f"[Ver Admin](https://admin.dropcontrol.com/farms/zone?farm={row_data[2]}&zone={row_data[11]})"
        )
        sidebar_comment = st.text_area("**Comentario Actual:**", value=row_data[41], key="sidebar_comment")
        if st.button("Actualizar comentario"):
            if sidebar_comment != row_data[41]:
                try:
                    sheet.update(f"AP{selected_row_index}", [[sidebar_comment]])
                    st.success("Comentario actualizado desde la barra lateral.")
                except Exception as e:
                    st.error("Error actualizando comentario: " + str(e))
            else:
                st.info("No se detectaron cambios en el comentario.")

    # Formulario de edición en la zona principal
    st.subheader("Formulario de Edición")
    
    # Botón para acceder a la planilla de Google
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

                # Procesar ubicación
                if ubicacion_sonda.strip() != row_data[12].strip():
                    if ubicacion_sonda.strip():
                        lat_parts = ubicacion_sonda.split()
                        if len(lat_parts) >= 2:
                            try:
                                latitud_dd = dms_to_dd(lat_parts[0])
                                longitud_dd = dms_to_dd(lat_parts[1])
                                batch_data[f"M{selected_row_index}"] = ubicacion_sonda
                                batch_data[f"N{selected_row_index}"] = latitud_dd
                                batch_data[f"O{selected_row_index}"] = longitud_dd
                                cambios_realizados.append("Ubicación sonda actualizada")
                            except Exception as e:
                                st.warning("Error al convertir la ubicación; se mantendrá el valor anterior.")

                # Procesar campos de texto
                if cultivo.strip() != row_data[17].strip():
                    batch_data[f"R{selected_row_index}"] = cultivo.strip()
                    cambios_realizados.append("Cultivo actualizado")
                    
                if variedad.strip() != row_data[18].strip():
                    batch_data[f"S{selected_row_index}"] = variedad.strip()
                    cambios_realizados.append("Variedad actualizada")

                # Procesar año de plantación como número
                ano_value = clean_numeric_value(ano_plantacion)
                if ano_value and ano_value != clean_numeric_value(row_data[20]):
                    batch_data[f"U{selected_row_index}"] = int(ano_value)
                    cambios_realizados.append("Año plantación actualizado")

                # Procesar superficie
                superficie_value = clean_numeric_value(superficie_ha)
                if superficie_value:
                    superficie_m2 = superficie_value * 10000
                    batch_data[f"AD{selected_row_index}"] = superficie_value
                    batch_data[f"AE{selected_row_index}"] = superficie_m2
                    cambios_realizados.append("Superficie actualizada")

                # Procesar plantas y emisores
                plantas_value = clean_numeric_value(plantas_ha)
                emisores_value = clean_numeric_value(emisores_ha)
                
                if plantas_value:
                    batch_data[f"W{selected_row_index}"] = int(plantas_value)
                    cambios_realizados.append("N° plantas actualizado")
                    
                if emisores_value:
                    batch_data[f"X{selected_row_index}"] = int(emisores_value)
                    cambios_realizados.append("N° emisores actualizado")

                # Calcular densidades si tenemos todos los valores necesarios
                if plantas_value and emisores_value and superficie_value and superficie_value > 0:
                    densidad_plantas = math.ceil(plantas_value / superficie_value)
                    densidad_emisores = math.ceil(emisores_value / superficie_value)
                    batch_data[f"W{selected_row_index}"] = densidad_plantas
                    batch_data[f"X{selected_row_index}"] = densidad_emisores
                    cambios_realizados.append("Densidades actualizadas")

                # Procesar caudal teórico y PPeq
                caudal_value = clean_numeric_value(caudal_teorico)
                if caudal_value:
                    batch_data[f"AF{selected_row_index}"] = caudal_value
                    cambios_realizados.append("Caudal teórico actualizado")

                ppeq_value = clean_numeric_value(ppeq_mm_h)
                if ppeq_value:
                    batch_data[f"AG{selected_row_index}"] = ppeq_value
                    cambios_realizados.append("PPeq actualizado")

                # Procesar comentarios
                if comentarios_seleccionados:
                    nuevo_comentario = ", ".join(comentarios_seleccionados)
                    if nuevo_comentario != row_data[41].strip():
                        batch_data[f"AP{selected_row_index}"] = nuevo_comentario
                        cambios_realizados.append("Comentarios actualizados")

                # Actualizar la planilla
                                if batch_data:
                                    try:
                                        sheet.batch_update([{
                                            "range": k,
                                            "values": [[format_cell_value(v)]]
                                        } for k, v in batch_data.items()])
                                        st.success("Cambios guardados correctamente:")
                                        for cambio in cambios_realizados:
                                            st.write(f"- {cambio}")
                                    except Exception as e:
                                        st.error(f"Error al guardar los cambios: {str(e)}")
                                else:
                                    st.info("No se detectaron cambios para guardar.")
                
                if __name__ == "__main__":
                    main()
