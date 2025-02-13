import streamlit as st
import gspread
from google.oauth2 import service_account
import re

# --- 1. Configuración de la Página ---
st.set_page_config(page_title="Gestión de Planillas", layout="centered")

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
    st.title("Gestión de Planillas")

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

    # Mover el buscador y selección de fila a la barra lateral para una interfaz más limpia
    with st.sidebar:
        st.subheader("Buscar Fila")
        search_term = st.text_input("Buscar por término (Cuenta, Campo, Sonda...)", "")
        if search_term:
            row_options = [row for row in row_options if search_term.lower() in row.lower()]
        selected_row = st.selectbox("Selecciona una fila", row_options)

    selected_row_index = int(selected_row.split(" ")[1])
    row_data = sheet.row_values(selected_row_index)

    # Mostrar información básica de la fila seleccionada
    st.subheader("Información de la fila seleccionada")
    st.write(f"**Cuenta:** {row_data[1]} [ID: {row_data[0]}]")
    st.write(f"**Campo:** {row_data[3]} [ID: {row_data[2]}]")
    st.write(f"**Sonda:** {row_data[10]} [ID: {row_data[11]}]")
    st.write(f"**Comentario:** {row_data[39]}")
    st.markdown(
        "[Ver Campo](https://www.dropcontrol.com/site/dashboard/campo.do"
        f"?cuentaId={row_data[0]}&campoId={row_data[2]})"
        " | "
        "[Ver Sonda](https://www.dropcontrol.com/site/ha/suelo.do"
        f"?cuentaId={row_data[0]}&campoId={row_data[2]}&sectorId={row_data[11]})"
    )
    
    # Formulario de edición
    st.subheader("Formulario de Edición")
    with st.form("formulario_edicion"):
        col1, col2 = st.columns(2)
        with col1:
            ubicacion_sonda = st.text_input("Ubicación sonda google maps", value=row_data[12])
            cultivo = st.text_input("Cultivo", value=row_data[17])
            variedad = st.text_input("Variedad", value=row_data[18])
            ano_plantacion = st.text_input("Año plantación", value=row_data[20])
        with col2:
            plantas_ha = st.text_input("N° plantas", value=row_data[22])
            emisores_ha = st.text_input("N° emisores", value=row_data[23])
            superficie_ha = st.text_input("Superficie (ha)", value=row_data[29])
            caudal_teorico = st.text_input("Caudal teórico (m3/h)", value=row_data[31])
            ppeq_mm_h = st.text_input("PPeq [mm/h]", value=row_data[32])

        # Dividir los checkboxes en dos columnas
        col1_cb, col2_cb = st.columns(2)
        comentarios_lista = [
            "La cuenta no existe", "La sonda no existe o no está asociada",
            "Sonda no georreferenciable", "La sonda no tiene sensores habilitados",
            "La sonda no está operando", "No hay datos de cultivo",
            "Datos de cultivo incompletos", "Datos de cultivo no son reales",
            "Consultar datos faltantes"
        ]
        comentarios_seleccionados = []
        with col1_cb:
            for i, comentario in enumerate(comentarios_lista[:5]):
                if st.checkbox(comentario, key=f"cb_{i}"):
                    comentarios_seleccionados.append(comentario)
        with col2_cb:
            for i, comentario in enumerate(comentarios_lista[5:], start=5):
                if st.checkbox(comentario, key=f"cb_{i}"):
                    comentarios_seleccionados.append(comentario)

        submit_button = st.form_submit_button(label="Guardar cambios")
        if submit_button:
            # Convertir DMS a DD
            try:
                latitud_dd = dms_to_dd(ubicacion_sonda.split()[0])
                longitud_dd = dms_to_dd(ubicacion_sonda.split()[1])
                latitud_sonda = f"{latitud_dd:.8f}".replace(".", ",")
                longitud_sonda = f"{longitud_dd:.8f}".replace(".", ",")
            except Exception as e:
                st.error(f"Error al convertir la ubicación: {str(e)}")
                return

            # Validar y calcular plantas/ha y emisores/ha
            try:
                superficie_ha_float = float(superficie_ha.replace(",", "."))
                if superficie_ha_float > 0:
                    plantas_ha_float = float(plantas_ha.replace(",", ".")) / superficie_ha_float
                    emisores_ha_float = float(emisores_ha.replace(",", ".")) / superficie_ha_float
                    plantas_ha = plantas_ha_float
                    emisores_ha = emisores_ha_float
                else:
                    st.warning("La superficie (ha) debe ser mayor que cero para calcular plantas/ha y emisores/ha. Se omitirá el cálculo.")
            except Exception as e:
                st.error(f"Error al calcular plantas/ha o emisores/ha: {str(e)}")
                return

            try:
                superficie_m2 = superficie_ha_float * 10000
            except Exception as e:
                st.warning(f"Error al calcular superficie (m2): {str(e)}. Se omitirá el cálculo.")
                superficie_m2 = row_data[30]

            # Actualizar datos en la hoja
            batch_data = {
                f"M{selected_row_index}": ubicacion_sonda,
                f"N{selected_row_index}": latitud_sonda,
                f"O{selected_row_index}": longitud_sonda,
                f"R{selected_row_index}": cultivo,
                f"S{selected_row_index}": variedad,
                f"U{selected_row_index}": ano_plantacion,
                f"W{selected_row_index}": plantas_ha,
                f"X{selected_row_index}": emisores_ha,
                f"AD{selected_row_index}": superficie_ha,
                f"AE{selected_row_index}": superficie_m2,
                f"AF{selected_row_index}": caudal_teorico,
                f"AG{selected_row_index}": ppeq_mm_h,
                f"AN{selected_row_index}": ", ".join(comentarios_seleccionados)
            }
            sheet.batch_update([{"range": k, "values": [[v]]} for k, v in batch_data.items()])
            st.success("Cambios guardados correctamente.")

if __name__ == "__main__":
    main()
