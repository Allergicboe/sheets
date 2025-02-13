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

# --- 3. Función para mostrar los datos ---
def display_data(sheet, row):
    """Función para mostrar los datos de la fila seleccionada."""
    row_data = sheet.row_values(row)
    
    # Mostrar información de la fila seleccionada
    st.write(f"**Fila {row} - Cuenta**: {row_data[1]} (ID: {row_data[0]}) - **Campo**: {row_data[3]} (ID: {row_data[2]}) - **Sonda**: {row_data[5]} (ID: {row_data[4]})")
    st.write(f"**Comentario**: {row_data[40]}")
    
    # Mostrar detalles adicionales (se pueden añadir más columnas si es necesario)
    st.write(f"**Cultivo**: {row_data[17]}")
    st.write(f"**Variedad**: {row_data[18]}")
    st.write(f"**Año plantación**: {row_data[20]}")
    st.write(f"**Plantas/ha**: {row_data[22]}")
    st.write(f"**Emisores/ha**: {row_data[23]}")
    st.write(f"**Superficie (ha)**: {row_data[29]}")
    st.write(f"**Superficie (m2)**: {row_data[30]}")
    st.write(f"**Caudal teórico (m3/h)**: {row_data[31]}")
    st.write(f"**PPeq [mm/h]**: {row_data[32]}")
    

# --- 4. Función Principal ---
def main():
    """Función principal que gestiona la aplicación de Streamlit."""
    # Iniciar conexión con Google Sheets
    client = init_connection()
    if client is None:
        return
    
    # Cargar la hoja de trabajo
    sheet = load_sheet(client)
    if sheet is None:
        return

    # Obtener todas las filas de la hoja (excepto la primera)
    rows = sheet.get_all_values()
    
    # Crear un selector de fila (eliminamos la primera fila)
    row_options = [f"Fila {i} - Cuenta: {rows[i-1][1]} (ID: {rows[i-1][0]}) - Campo: {rows[i-1][3]} (ID: {rows[i-1][2]}) - Sonda: {rows[i-1][5]} (ID: {rows[i-1][4]})" for i in range(2, len(rows)+1)]
    selected_row = st.selectbox("Selecciona una fila:", row_options)
    
    # Obtener el número de fila seleccionada
    selected_row_number = int(selected_row.split(" ")[1])
    
    # Mostrar los datos de la fila seleccionada
    display_data(sheet, selected_row_number)

    # --- Formulario ---
    st.write("### Formulario de Edición")

    # Mostrar los detalles del formulario (en dos columnas)
    col1, col2 = st.columns(2)

    # Columna 1
    with col1:
        cultivo = st.text_input("Cultivo", value=rows[selected_row_number-1][17])
        variedad = st.text_input("Variedad", value=rows[selected_row_number-1][18])
        ano_plantacion = st.text_input("Año Plantación", value=rows[selected_row_number-1][20])
        plantas_ha = st.text_input("Plantas/ha", value=rows[selected_row_number-1][22])
        emisores_ha = st.text_input("Emisores/ha", value=rows[selected_row_number-1][23])
        superficie_ha = st.text_input("Superficie (ha)", value=rows[selected_row_number-1][29])
        superficie_m2 = st.text_input("Superficie (m2)", value=rows[selected_row_number-1][30])

    # Columna 2
    with col2:
        caudal_teorico = st.text_input("Caudal teórico (m3/h)", value=rows[selected_row_number-1][31])
        ppeq = st.text_input("PPeq [mm/h]", value=rows[selected_row_number-1][32])

    # --- Verificar cambios ---
    if st.button("Guardar cambios"):
        # Se debe actualizar la fila con los datos del formulario
        updated_values = [cultivo, variedad, ano_plantacion, plantas_ha, emisores_ha, superficie_ha, superficie_m2, caudal_teorico, ppeq]
        # El número de fila que debe actualizarse
        row_to_update = selected_row_number
        sheet.update(f"R{row_to_update}C17:R{row_to_update}C32", [updated_values])
        st.success("Los cambios se han guardado exitosamente.")

if __name__ == "__main__":
    main()
