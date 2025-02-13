import streamlit as st
import gspread
from google.oauth2 import service_account
import re

# --- Configuración de la página ---
st.set_page_config(page_title="Gestión de Planillas", layout="wide")

# --- Función de conexión ---
def init_connection():
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
    try:
        return client.open_by_url(st.secrets["spreadsheet_url"]).sheet1
    except Exception as e:
        st.error(f"Error al cargar la planilla: {str(e)}")
        return None

# --- Función principal ---
def main():
    st.title("Gestión de Planillas")

    # Inicializar conexión y hoja
    client = init_connection()
    if not client:
        return
    sheet = load_sheet(client)
    if not sheet:
        return

    # Control de la fila actual en session_state
    if "current_row" not in st.session_state:
        st.session_state.current_row = 1

    # Sidebar para selección de fila
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

    # Mostrar información básica
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Cuenta:** {row_data[1]} [ID: {row_data[0]}]")
        st.write(f"**Campo:** {row_data[3]} [ID: {row_data[2]}]")
    with col2:
        st.write(f"**Sonda:** {row_data[10]} [ID: {row_data[11]}]")

    # --- Formulario de edición ---
    st.write("**Formulario de Edición:**")

    # Entradas de texto para editar
    with st.form("formulario_edicion"):
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

if __name__ == "__main__":
    main()
