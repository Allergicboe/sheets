import streamlit as st
import gspread
from google.oauth2 import service_account
import re

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

    # Mover el buscador y selección de fila a la barra lateral
    with st.sidebar:
        st.subheader("Buscar Fila")
        search_term = st.text_input("Buscar por término (Cuenta, Campo, Sonda...)", "")
        if search_term:
            row_options = [row for row in row_options if search_term.lower() in row.lower()]
        selected_row = st.selectbox("Selecciona una fila", row_options)

    selected_row_index = int(selected_row.split(" ")[1])
    row_data = sheet.row_values(selected_row_index)

    # Mostrar información básica de la fila seleccionada en la barra lateral
    with st.sidebar:
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
    with st.form(key='edit_form'):
        col1, col2, col3 = st.columns(3)

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

        with col3:
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

        submit_button = st.form_submit_button(label="Guardar cambios", type="primary")

        if submit_button:
            # Inicializar diccionario de actualizaciones
            batch_data = {}
            
            # Procesar ubicación sonda solo si cambió
            if ubicacion_sonda != row_data[12]:
                if ubicacion_sonda.strip():
                    lat_parts = ubicacion_sonda.split()
                    if len(lat_parts) >= 2:
                        try:
                            latitud_dd = dms_to_dd(lat_parts[0])
                            longitud_dd = dms_to_dd(lat_parts[1])
                            batch_data[f"M{selected_row_index}"] = ubicacion_sonda
                            batch_data[f"N{selected_row_index}"] = f"{latitud_dd:.8f}".replace(".", ",")
                            batch_data[f"O{selected_row_index}"] = f"{longitud_dd:.8f}".replace(".", ",")
                        except Exception as e:
                            st.warning("Error al convertir la ubicación; se guardará como vacío.")
                            batch_data[f"M{selected_row_index}"] = ""
                            batch_data[f"N{selected_row_index}"] = ""
                            batch_data[f"O{selected_row_index}"] = ""
                else:
                    batch_data[f"M{selected_row_index}"] = ""
                    batch_data[f"N{selected_row_index}"] = ""
                    batch_data[f"O{selected_row_index}"] = ""

            # Procesar campos simples solo si cambiaron
            if cultivo != row_data[17]:
                batch_data[f"R{selected_row_index}"] = cultivo
            if variedad != row_data[18]:
                batch_data[f"S{selected_row_index}"] = variedad
            if ano_plantacion != row_data[20]:
                batch_data[f"U{selected_row_index}"] = ano_plantacion
            if caudal_teorico != row_data[31]:
                batch_data[f"AF{selected_row_index}"] = caudal_teorico
            if ppeq_mm_h != row_data[32]:
                batch_data[f"AG{selected_row_index}"] = ppeq_mm_h

            # Procesar superficie y cálculos relacionados solo si cambió la superficie
            superficie_cambio = superficie_ha != row_data[29]
            if superficie_cambio:
                batch_data[f"AD{selected_row_index}"] = superficie_ha
                if superficie_ha.strip():
                    try:
                        superficie_ha_float = float(superficie_ha.replace(",", "."))
                        # Calcular superficie en m2
                        superficie_m2 = superficie_ha_float * 10000
                        batch_data[f"AE{selected_row_index}"] = str(superficie_m2)

                        # Recalcular plantas/ha y emisores/ha solo si la superficie cambió
                        if superficie_ha_float > 0:
                            if plantas_ha.strip():
                                try:
                                    plantas_val = float(plantas_ha.replace(",", "."))
                                    batch_data[f"W{selected_row_index}"] = str(plantas_val / superficie_ha_float)
                                except:
                                    st.warning("Error al convertir N° plantas")
                            if emisores_ha.strip():
                                try:
                                    emisores_val = float(emisores_ha.replace(",", "."))
                                    batch_data[f"X{selected_row_index}"] = str(emisores_val / superficie_ha_float)
                                except:
                                    st.warning("Error al convertir N° emisores")
                    except:
                        st.warning("Error al procesar superficie")
            else:
                # Si la superficie no cambió, solo actualizar plantas y emisores si estos cambiaron
                if plantas_ha != row_data[22]:
                    batch_data[f"W{selected_row_index}"] = plantas_ha
                if emisores_ha != row_data[23]:
                    batch_data[f"X{selected_row_index}"] = emisores_ha

            # Actualizar comentarios
            nuevos_comentarios = ", ".join(comentarios_seleccionados)
            if nuevos_comentarios != row_data[39]:
                batch_data[f"AN{selected_row_index}"] = nuevos_comentarios

            # Realizar actualizaciones solo si hay cambios
            if batch_data:
                sheet.batch_update([{"range": k, "values": [[v]]} for k, v in batch_data.items()])
                st.success("Cambios guardados correctamente.")
            else:
                st.info("No se detectaron cambios para guardar.")

if __name__ == "__main__":
    main()
