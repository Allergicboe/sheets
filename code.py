import streamlit as st
import gspread
from google.oauth2 import service_account
import re

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

# --- 3. Función para convertir DMS a Decimal ---
def dms_to_decimal(dms):
    """Convierte coordenadas en formato DMS (Grados, Minutos, Segundos) a Decimal."""
    try:
        # Regex para dividir grados, minutos, segundos y dirección
        dms_pattern = re.compile(r"(\d+)°(\d+)'(\d+\.\d+)([NSWE])")
        match = dms_pattern.match(dms.strip())

        if match:
            degrees = int(match.group(1))
            minutes = int(match.group(2))
            seconds = float(match.group(3))
            direction = match.group(4)

            decimal = degrees + (minutes / 60) + (seconds / 3600)
            if direction in ['S', 'W']:
                decimal = -decimal
            return round(decimal, 8)
        else:
            return None
    except Exception as e:
        st.error(f"Error al convertir DMS a decimal: {str(e)}")
        return None


# --- 4. Función Principal ---
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

    # --- 5. Mostrar Fila Completa ---
    all_rows = sheet.get_all_values()  # Obtener todas las filas de la hoja
    row_options = [f"Fila {i} - Cuenta: {all_rows[i-1][1]} (ID: {all_rows[i-1][0]}), Campo: {all_rows[i-1][3]} (ID: {all_rows[i-1][2]}), Sonda: {all_rows[i-1][10]} (ID: {all_rows[i-1][11]})" for i in range(2, len(all_rows))]  # Opciones para seleccionar por fila

    # Agregar opción de búsqueda rápida por cualquier término
    search_term = st.text_input("Buscar fila por término (puede ser cualquier texto o número)", "")
    if search_term:
        row_options = [row for row in row_options if search_term.lower() in row.lower()]  # Filtrar sin restricciones de formato

    selected_row = st.selectbox("Selecciona una fila", row_options)  # Desplegable de filas

    # Buscar la fila seleccionada en base al número de fila
    selected_row_index = int(selected_row.split(" ")[1])  # Extraer el número de fila
    row_data = sheet.row_values(selected_row_index)  # Obtener los valores de la fila seleccionada
    st.session_state.row_data = row_data

    # --- 6. Mostrar Información Básica de la Fila ---
    st.subheader("Información de la fila seleccionada")
    
    # Vista previa organizada con los datos solicitados
    col1, col2 = st.columns([1, 1])
    with col1:
        st.write(f"**Cuenta:** {row_data[1]} [ID: {row_data[0]}]")
        st.write(f"**Campo:** {row_data[3]} [ID: {row_data[2]}]")
    with col2:
        st.write(f"**Sonda:** {row_data[10]} [ID: {row_data[11]}]")
        st.write(f"**Comentario:** {row_data[39]}")  # Columna AN para comentarios

    # Fila para el enlace de campo
    st.write(f"[Ver campo](https://www.dropcontrol.com/site/dashboard/campo.do?cuentaId={row_data[0]}&campoId={row_data[2]})")  # Enlace de campo

    # Fila para el enlace de sonda debajo del campo
    st.write(f"[Ver sonda](https://www.dropcontrol.com/site/ha/suelo.do?cuentaId={row_data[0]}&campoId={row_data[2]}&sectorId={row_data[11]})")  # Enlace de sonda

    # --- 7. Formulario de Edición ---
    st.subheader("Formulario de Edición")

    with st.form("formulario_edicion"):
        # Distribución en columnas
        col1, col2 = st.columns(2)

        # Entradas para las columnas solicitadas distribuidas entre las dos columnas
        with col1:
            ubicacion_sonda = st.text_input("Ubicación sonda google maps", value=row_data[12])
            if ubicacion_sonda:  # Si la ubicación sonda es modificada
                # Convertir la nueva ubicación en DMS a latitud y longitud
                latitud_sonda = dms_to_decimal(ubicacion_sonda.split()[0])  # Extraer la latitud
                longitud_sonda = dms_to_decimal(ubicacion_sonda.split()[1])  # Extraer la longitud
            else:
                latitud_sonda = row_data[13]  # Si no se cambia, conservar el valor actual
                longitud_sonda = row_data[14]  # Si no se cambia, conservar el valor actual

            # Convertir superficie (ha) a superficie (m2)
            superficie_ha = float(row_data[29]) if row_data[29] else 0
            superficie_m2 = superficie_ha * 10000  # Superficie en m2

            cultivo = st.text_input("Cultivo", value=row_data[17])  # Columna R
            variedad = st.text_input("Variedad", value=row_data[18])  # Columna S
            ano_plantacion = st.text_input("Año plantación", value=row_data[20])  # Columna U

        with col2:
            plantas_ha = st.text_input("Plantas/ha", value=row_data[21])  # Columna W
            emisores_ha = st.text_input("Emisores/ha", value=row_data[22])  # Columna X
            superficie_ha_input = st.text_input("Superficie (ha)", value=row_data[29])  # Columna AD
            caudal_teorico = st.text_input("Caudal teórico (m3/h)", value=row_data[30])  # Columna AF
            ppeq = st.text_input("PPeq [mm/h]", value=row_data[31])  # Columna AG

        # Botón para actualizar plantas/ha y emisores/ha
        actualizar_button = st.form_submit_button(label="Actualizar/ha")
        if actualizar_button:
            try:
                superficie_ha_float = float(superficie_ha_input)
                if superficie_ha_float > 0:
                    plantas_ha_actualizado = float(plantas_ha) / superficie_ha_float
                    emisores_ha_actualizado = float(emisores_ha) / superficie_ha_float

                    st.success(f"Plantas/ha actualizado a: {plantas_ha_actualizado:.2f} / Emisores/ha actualizado a: {emisores_ha_actualizado:.2f}")
                else:
                    st.error("La superficie (ha) debe ser mayor a 0 para realizar el cálculo.")
            except ValueError:
                st.error("Error en el cálculo, por favor asegúrate de que todos los valores sean numéricos.")

        # Botón de guardar cambios
        submit_button = st.form_submit_button(label="Guardar cambios")
        if submit_button:
            # Actualizar la fila con los nuevos datos
            sheet.update_cell(selected_row_index, 12, ubicacion_sonda)  # Ubicación sonda google maps
            sheet.update_cell(selected_row_index, 13, latitud_sonda)    # Latitud sonda
            sheet.update_cell(selected_row_index, 14, longitud_sonda)  # Longitud sonda
            sheet.update_cell(selected_row_index, 17, cultivo)    # Cultivo
            sheet.update_cell(selected_row_index, 18, variedad)   # Variedad
            sheet.update_cell(selected_row_index, 20, ano_plantacion)  # Año plantación
            sheet.update_cell(selected_row_index, 21, plantas_ha_actualizado)  # Plantas/ha
            sheet.update_cell(selected_row_index, 22, emisores_ha_actualizado)  # Emisores/ha
            sheet.update_cell(selected_row_index, 29, superficie_ha_input)  # Superficie (ha)
            sheet.update_cell(selected_row_index, 30, superficie_m2)  # Superficie (m2)
            sheet.update_cell(selected_row_index, 30, caudal_teorico)  # Caudal teórico (m3/h)
            sheet.update_cell(selected_row_index, 31, ppeq)  # PPeq [mm/h]

            st.success("Cambios guardados correctamente.")


if __name__ == "__main__":
    main()
