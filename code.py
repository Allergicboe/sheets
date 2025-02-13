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
    
    # Vista previa organizada
    col1, col2 = st.columns([1, 1])
    with col1:
        st.write(f"**Campo:** {row_data[3]} [ID: {row_data[2]}]")
        st.write(f"[Ver campo](https://www.dropcontrol.com/site/dashboard/campo.do?cuentaId={row_data[0]}&campoId={row_data[2]})")  # Enlace de campo
    with col2:
        st.write(f"**Sonda:** {row_data[10]} [ID: {row_data[11]}]")
        st.write(f"[Ver sonda](https://www.dropcontrol.com/site/ha/suelo.do?cuentaId={row_data[0]}&campoId={row_data[2]}&sectorId={row_data[11]})")  # Enlace de sonda

    # Información adicional
    st.write(f"**Región:** {row_data[7]}")
    st.write(f"**Provincia:** {row_data[8]}")
    st.write(f"**Localidad:** {row_data[9]}")
    st.write(f"**Cultivo:** {row_data[17]} - {row_data[18]}")  # Cultivo y variedad
    st.write(f"**Área:** {row_data[34]} ha")
    st.write(f"**Caudal teórico:** {row_data[35]} m³/h")

    # Mostrar comentario actual
    comentario_actual = row_data[39] if len(row_data) > 39 else "Sin comentarios"
    st.write(f"**Comentario actual:** {comentario_actual}")


# --- 6. Formulario de Edición ---
    st.subheader("Formulario de Edición")

    with st.form("formulario_edicion"):
        # Entradas de texto para editar la cuenta, campo y sonda
        cuenta = st.text_input("Cuenta", value=row_data[1])
        campo = st.text_input("Campo", value=row_data[3])
        sonda = st.text_input("Sonda", value=row_data[10])

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
            sheet.update_cell(st.session_state.current_row, 2, cuenta)  # Cuenta
            sheet.update_cell(st.session_state.current_row, 4, campo)    # Campo
            sheet.update_cell(st.session_state.current_row, 11, sonda)   # Sonda

            # Guardar comentarios en la hoja
            comentarios = ", ".join(comentarios_seleccionados)
            sheet.update_cell(st.session_state.current_row, 40, comentarios)  # Columna "Comentarios"

            st.success("Los cambios se han guardado correctamente.")


# --- 7. Ejecución ---
if __name__ == "__main__":
    main()
