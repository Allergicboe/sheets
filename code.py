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
    st.title("Gestión de Planillas")

    # Inicializar conexión y cargar hoja
    client = init_connection()
    if not client:
        return
    sheet = load_sheet(client)
    if not sheet:
        return

    # --- 5. Mostrar Fila Completa ---
    all_rows = sheet.get_all_values()
    row_options = [
        f"Fila {i} - Cuenta: {all_rows[i-1][1]} (ID: {all_rows[i-1][0]}) - Campo: {all_rows[i-1][3]} (ID: {all_rows[i-1][2]}) - Sonda: {all_rows[i-1][10]} (ID: {all_rows[i-1][11]})"
        for i in range(2, len(all_rows))
    ]

    search_term = st.text_input("Buscar fila por término (Ejemplo: Cuenta, Campo, Sonda...)", "")
    if search_term:
        row_options = [row for row in row_options if search_term.lower() in row.lower()]

    selected_row = st.selectbox("Selecciona una fila", row_options)
    selected_row_index = int(selected_row.split(" ")[1])
    row_data = sheet.row_values(selected_row_index)

    # --- 6. Mostrar Información Básica de la Fila ---
    st.subheader("Información de la fila seleccionada")
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.write(f"**Cuenta:** {row_data[1]} [ID: {row_data[0]}]")
        st.write(f"**Campo:** {row_data[3]} [ID: {row_data[2]}]")
        st.write(
            "[Ver Campo](https://www.dropcontrol.com/site/dashboard/campo.do"
            f"?cuentaId={row_data[0]}&campoId={row_data[2]})"
            ", "
            "[Ver Sonda](https://www.dropcontrol.com/site/ha/suelo.do"
            f"?cuentaId={row_data[0]}&campoId={row_data[2]}&sectorId={row_data[11]})"
        )
    
    with col2:
        st.write(f"**Sonda:** {row_data[10]} [ID: {row_data[11]}]")
        st.write(f"**Comentario:** {row_data[39]}")

    # --- 7. Formulario de Edición ---
    st.subheader("Formulario de Edición")
    
    with st.form("formulario_edicion"):
        col1, col2 = st.columns(2)
        with col1:
            ubicacion_sonda = st.text_input("Ubicación sonda google maps", value=row_data[12])
            cultivo = st.text_input("Cultivo", value=row_data[17])
            variedad = st.text_input("Variedad", value=row_data[18])
            ano_plantacion = st.text_input("Año plantación", value=row_data[20])
    
        with col2:
            plantas_ha = st.text_input("N° plantas", value=row_data[21])  # Cambiado a "N° plantas"
            emisores_ha = st.text_input("N° emisores", value=row_data[22])  # Cambiado a "N° emisores"
            superficie_ha = st.text_input("Superficie (ha)", value=row_data[29])
            caudal_teorico = st.text_input("Caudal teórico (m3/h)", value=row_data[31])
            ppeq_mm_h = st.text_input("PPeq [mm/h]", value=row_data[32])
    
        # Definir los grupos de checkboxes
        grupo_a = ["La cuenta no existe", "La sonda no existe o no está asociada", "Consultar datos faltantes"]
        grupo_b = ["La sonda no tiene sensores habilitados", "La sonda no está operando"]
        grupo_c = ["No hay datos de cultivo", "Datos de cultivo incompletos", "Datos de cultivo no son reales"]
    
        # Dividir los checkboxes en dos columnas
        col1_cb, col2_cb = st.columns(2)
    
        # Primera columna de checkboxes
        with col1_cb:
            comentarios_seleccionados = []
            for i, comentario in enumerate(grupo_a + grupo_b[:1] + grupo_c[:1]):  # Primera mitad de la lista
                # Generar una clave única basada en el grupo y el índice
                if comentario in grupo_a:
                    key = f"grupo_a_{i}"
                elif comentario in grupo_b:
                    key = f"grupo_b_{i}"
                elif comentario in grupo_c:
                    key = f"grupo_c_{i}"
                else:
                    key = f"otro_{i}"
    
                if comentario in grupo_a:
                    # Si un checkbox del Grupo A está seleccionado, deshabilitar los demás
                    if any(c in grupo_a for c in comentarios_seleccionados):
                        disabled = True
                    else:
                        disabled = False
                elif comentario in grupo_b:
                    # Si un checkbox del Grupo B está seleccionado, deshabilitar el otro
                    if any(c in grupo_b for c in comentarios_seleccionados):
                        disabled = True
                    else:
                        disabled = False
                elif comentario in grupo_c:
                    # Si "No hay datos de cultivo" está seleccionado, deshabilitar los demás del Grupo C
                    if "No hay datos de cultivo" in comentarios_seleccionados:
                        disabled = True
                    else:
                        disabled = False
                else:
                    disabled = False
    
                if st.checkbox(comentario, key=key, disabled=disabled):
                    comentarios_seleccionados.append(comentario)
    
        # Segunda columna de checkboxes
        with col2_cb:
            for i, comentario in enumerate(grupo_b[1:] + grupo_c[1:], start=len(grupo_a) + 1):  # Segunda mitad de la lista
                # Generar una clave única basada en el grupo y el índice
                if comentario in grupo_b:
                    key = f"grupo_b_{i}"
                elif comentario in grupo_c:
                    key = f"grupo_c_{i}"
                else:
                    key = f"otro_{i}"
    
                if comentario in grupo_b:
                    # Si un checkbox del Grupo B está seleccionado, deshabilitar el otro
                    if any(c in grupo_b for c in comentarios_seleccionados):
                        disabled = True
                    else:
                        disabled = False
                elif comentario in grupo_c:
                    # Si "No hay datos de cultivo" está seleccionado, deshabilitar los demás del Grupo C
                    if "No hay datos de cultivo" in comentarios_seleccionados:
                        disabled = True
                    else:
                        disabled = False
                else:
                    disabled = False
    
                if st.checkbox(comentario, key=key, disabled=disabled):
                    comentarios_seleccionados.append(comentario)
    
        submit_button = st.form_submit_button(label="Guardar cambios")
        if submit_button:
            # Resto del código para guardar los cambios...
            st.success("Cambios guardados correctamente.")
if __name__ == "__main__":
    main()
