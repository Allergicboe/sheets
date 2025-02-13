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

    # Formulario para editar datos (solo vista previa y checkboxes)
    st.write("**Seleccionar comentarios:**")
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

    # --- Botones de navegación ---
    nav_col1, nav_col2, nav_col3 = st.columns(3)
    with nav_col1:
        if st.button("Siguiente"):
            st.session_state.current_row += 1
            st.session_state.row_data = sheet.row_values(st.session_state.current_row)
            st.experimental_rerun()
    with nav_col2:
        if st.button("Volver"):
            if st.session_state.current_row > 1:
                st.session_state.current_row -= 1
                st.session_state.row_data = sheet.row_values(st.session_state.current_row)
                st.experimental_rerun()
    with nav_col3:
        if st.button("Seleccionar otra fila"):
            del st.session_state.row_data
            st.experimental_rerun()

if __name__ == "__main__":
    main()
