import streamlit as st
import gspread
from google.oauth2 import service_account

# --- 1. Configuración de la Página ---
st.set_page_config(page_title="Gestión de Planillas", layout="wide")


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


# --- 3. Función Principal ---
def main():
    """Función principal que gestiona la interfaz de usuario y el flujo de datos."""
    st.title("Gestión de Planillas")

    # Inicializar conexión y cargar hoja
    client = init_connection()
    if not client:
        return
    sheet = load_sheet(client)
    if not sheet:
        return

    # Control de la fila actual en session_state
    if "current_row" not in st.session_state:
        st.session_state.current_row = 1

    # --- 4. Sidebar: Selección de Fila ---
    with st.sidebar:
        row_number = st.number_input("Número de fila", min_value=1, value=st.session_state.current_row, step=1)
        if st.button("Cargar fila"):
            st.session_state.row_data = sheet.row_values(row_number)
            st.session_state.current_row = row_number
            st.experimental_rerun()

    if "row_data" not in st.session_state:
        st.info("Por favor, selecciona y carga una fila en la barra lateral.")
        return

    row_data = st.session_state.row_data

    # --- 5. Mostrar Información Básica de la Fila ---
    st.subheader("Información de la fila seleccionada")
    
    # Vista previa organizada con los datos solicitados
    col1, col2 = st.columns([1, 1])
    with col1:
        st.write(f"**Cuenta:** {row_data[1]} [ID: {row_data[0]}]")
        st.write(f"**Campo:** {row_data[3]} [ID: {row_data[2]}]")
    with col2:
        st.write(f"**Sonda:** {row_data[10]} [ID: {row_data[11]}]")
        st.write(f"**Comentario:** {row_data[39]}")  # Columna de comentario (columna 40)

    # Fila para el enlace de campo
    st.write(f"[Ver campo](https://www.dropcontrol.com/site/dashboard/campo.do?cuentaId={row_data[0]}&campoId={row_data[2]})")  # Enlace de campo

    # Fila para el enlace de sonda debajo del campo
    st.write(f"[Ver sonda](https://www.dropcontrol.com/site/ha/suelo.do?cuentaId={row_data[0]}&campoId={row_data[2]}&sectorId={row_data[11]})")  # Enlace de sonda

    # --- 6. Formulario de Edición ---
    st.subheader("Formulario de Edición")

    with st.form("formulario_edicion"):
        # Distribución en columnas
        col1, col2 = st.columns(2)

        # Entradas para las columnas solicitadas distribuidas entre las dos columnas
        with col1:
            ubicacion_sonda = st.text_input("Ubicación sonda google maps", value=row_data[12])
            latitud_sonda = st.text_input("Latitud sonda", value=row_data[13])
            longitud_sonda = st.text_input("Longitud Sonda", value=row_data[14])
            cultivo = st.text_input("Cultivo", value=row_data[17])  # Columna R
            variedad = st.text_input("Variedad", value=row_data[18])  # Columna S
            ano_plantacion = st.text_input("Año plantación", value=row_data[20])  # Columna U

        with col2:
            plantas_ha = st.text_input("Plantas/ha", value=row_data[21])  # Columna W
            emisores_ha = st.text_input("Emisores/ha", value=row_data[22])  # Columna X
            superficie_ha = st.text_input("Superficie (ha)", value=row_data[29])  # Columna AD
            superficie_m2 = st.text_input("Superficie (m2)", value=row_data[30])  # Columna AE
            caudal_teorico = st.text_input("Caudal teórico (m3/h)", value=row_data[31])  # Columna AF
            ppeq_mm_h = st.text_input("PPeq [mm/h]", value=row_data[32])  # Columna AG

        # Checkboxes para comentarios
        comentarios_lista = [
            "La cuenta no existe",
            "La sonda no existe o no está asociada",
            "Sonda no georreferenciable",
            "La sonda no tiene sensores habilitados",
            "La sonda no está operando",
            "No hay datos de cultivo",
            "Datos de cultivo incompletos",
            "Datos de cultivo no son reales",
            "Consultar datos faltantes"
        ]
        comentarios_seleccionados = []
        for comentario in comentarios_lista:
            if st.checkbox(comentario, key=f"cb_{comentario}"):
                comentarios_seleccionados.append(comentario)

        # Botón de guardar cambios
        submit_button = st.form_submit_button(label="Guardar cambios")
        if submit_button:
            # Actualizar la fila con los nuevos datos
            sheet.update_cell(st.session_state.current_row, 12, ubicacion_sonda)  # Ubicación sonda google maps
            sheet.update_cell(st.session_state.current_row, 13, latitud_sonda)    # Latitud sonda
            sheet.update_cell(st.session_state.current_row, 14, longitud_sonda)  # Longitud sonda
            sheet.update_cell(st.session_state.current_row, 17, cultivo)    # Cultivo
            sheet.update_cell(st.session_state.current_row, 18, variedad)   # Variedad
            sheet.update_cell(st.session_state.current_row, 20, ano_plantacion)  # Año plantación
            sheet.update_cell(st.session_state.current_row, 21, plantas_ha)  # Plantas/ha
            sheet.update_cell(st.session_state.current_row, 22, emisores_ha)  # Emisores/ha
            sheet.update_cell(st.session_state.current_row, 29, superficie_ha)  # Superficie (ha)
            sheet.update_cell(st.session_state.current_row, 30, superficie_m2)  # Superficie (m2)
            sheet.update_cell(st.session_state.current_row, 31, caudal_teorico)  # Caudal teórico (m3/h)
            sheet.update_cell(st.session_state.current_row, 32, ppeq_mm_h)  # PPeq [mm/h]

            # Guardar comentarios en la hoja
            comentarios = ", ".join(comentarios_seleccionados)
            sheet.update_cell(st.session_state.current_row, 40, comentarios)  # Columna "Comentarios"

            st.success("Los cambios se han guardado correctamente.")


# --- 8. Ejecución ---
if __name__ == "__main__":
    main()
