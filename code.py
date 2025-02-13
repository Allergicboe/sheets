import streamlit as st
import gspread
from google.oauth2 import service_account
import pandas as pd
from math import ceil
import re

# --- Configuración de la página ---
st.set_page_config(page_title="Gestión de Planillas", layout="wide")

# --- Funciones para conversión de coordenadas DMS ---
def formatear_dms(dms):
    match = re.match(r"(\d{1,2})°\s*(\d{1,2})'\s*([\d.]+)\"\s*([NS])\s*(\d{1,3})°\s*(\d{1,2})'\s*([\d.]+)\"\s*([EW])", str(dms))
    if not match:
        return None
    lat_g, lat_m, lat_s, lat_dir, lon_g, lon_m, lon_s, lon_dir = match.groups()
    lat_s = round(float(lat_s), 1)
    lon_s = round(float(lon_s), 1)
    if lat_s == 60.0:
        lat_s = 0.0
        lat_m = int(lat_m) + 1
    if lon_s == 60.0:
        lon_s = 0.0
        lon_m = int(lon_m) + 1
    lat = f"{int(lat_g):02d}°{int(lat_m):02d}'{lat_s:04.1f}\"{lat_dir}"
    lon = f"{int(lon_g)}°{int(lon_m):02d}'{lon_s:04.1f}\"{lon_dir}"
    return lat, lon

def dms_a_decimal(dms):
    match = re.match(r"(\d{1,3})°(\d{1,2})'([\d.]+)\"([NSWE])", str(dms))
    if not match:
        return None
    grados, minutos, segundos, direccion = match.groups()
    decimal = float(grados) + float(minutos)/60 + float(segundos)/3600
    if direccion in ['S', 'W']:
        decimal = -decimal
    return round(decimal, 8)

# --- Clase para gestionar la fila en Sheets ---
class RowManager:
    def __init__(self, sheet):
        self.sheet = sheet
        self.current_row_data = None
        self.current_row_number = None
        self.modified_cells = {}

    def load_row(self, row_number):
        self.current_row_data = self.sheet.row_values(row_number)
        self.current_row_number = row_number
        self.modified_cells = {}
        return self.current_row_data

    def update_cell(self, col_index, value):
        self.modified_cells[col_index] = value

    def update_cell_color(self, comentarios):
        cell_address = f'A{self.current_row_number}'
        if any(comment in comentarios for comment in ["La sonda no existe o no está asociada", "La sonda no tiene sensores habilitados", "La cuenta no existe"]):
            color = {"red": 1, "green": 0, "blue": 0}  # Rojo
        elif "Consultar datos faltantes" in comentarios:
            color = {"red": 0, "green": 1, "blue": 0}  # Verde
        else:
            color = {"red": 1, "green": 1, "blue": 0}  # Amarillo
        self.sheet.format(cell_address, {"backgroundColor": color})

    def save_changes(self):
        if self.modified_cells:
            cells = [gspread.Cell(self.current_row_number, col, value) for col, value in self.modified_cells.items()]
            self.sheet.update_cells(cells)
            if 40 in self.modified_cells:
                self.update_cell_color(self.modified_cells[40])
            self.modified_cells = {}

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

def main():
    st.title("Gestión de Planillas")

    # Inicializar conexión
    client = init_connection()
    if not client:
        return

    sheet = load_sheet(client)
    if not sheet:
        return

    # Inicializar el gestor de filas
    row_manager = RowManager(sheet)

    # Sidebar para selección de fila
    with st.sidebar:
        row_number = st.number_input("Número de fila", min_value=1, value=1)
        if st.button("Cargar fila"):
            st.session_state.row_data = row_manager.load_row(row_number)
            st.session_state.current_row = row_number

    # Lista de comentarios
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

    if 'row_data' in st.session_state:
        row_data = st.session_state.row_data

        # Mostrar información básica
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Cuenta:** {row_data[1]} [ID: {row_data[0]}]")
            st.write(f"**Campo:** {row_data[3]} [ID: {row_data[2]}]")
        with col2:
            st.write(f"**Sonda:** {row_data[10]} [ID: {row_data[11]}]")
            st.write(f"**Comentario actual:** {row_data[39] if len(row_data) > 39 else ''}")

        # Links
        st.markdown(f"[Link Cuenta](www.dropcontrol.com/site/dashboard/campo.do?cuentaId={row_data[0]}&campoId={row_data[2]})")
        st.markdown(f"[Link Sonda](https://www.dropcontrol.com/site/ha/suelo.do?cuentaId={row_data[0]}&campoId={row_data[2]}&sectorId={row_data[11]})")

        # Formulario principal
        with st.form("edit_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                ubicacion = st.text_input("Ubicación", value=row_data[12] if len(row_data) > 12 else "")
                latitud = st.text_input("Latitud", value=row_data[13] if len(row_data) > 13 else "", disabled=True)
                longitud = st.text_input("Longitud", value=row_data[14] if len(row_data) > 14 else "", disabled=True)
                cultivo = st.text_input("Cultivo", value=row_data[17] if len(row_data) > 17 else "")
                variedad = st.text_input("Variedad", value=row_data[18] if len(row_data) > 18 else "")
                año_plantacion = st.text_input("Año plantación", value=row_data[20] if len(row_data) > 20 else "")

            with col2:
                plantas_ha = st.text_input("Plantas/ha", value=row_data[22] if len(row_data) > 22 else "")
                emisores_ha = st.text_input("Emisores/ha", value=row_data[23] if len(row_data) > 23 else "")
                superficie_ha = st.text_input("Superficie (ha)", value=row_data[29] if len(row_data) > 29 else "")
                superficie_m2 = st.text_input("Superficie (m2)", value=row_data[30] if len(row_data) > 30 else "", disabled=True)
                caudal = st.text_input("Caudal teórico (m³/h)", value=row_data[31] if len(row_data) > 31 else "")
                ppeq = st.text_input("PPeq [mm/h]", value=row_data[32] if len(row_data) > 32 else "")

            # Comentarios
            st.write("**Seleccionar comentarios:**")
            comentarios_seleccionados = []
            for comentario in comentarios_lista:
                if st.checkbox(comentario, key=f"cb_{comentario}"):
                    comentarios_seleccionados.append(comentario)

            if st.form_submit_button("Guardar cambios"):
                try:
                    # Actualizar coordenadas si cambió la ubicación
                    if ubicacion:
                        coords = formatear_dms(ubicacion)
                        if coords:
                            lat_formateado, lon_formateado = coords
                            lat_decimal = dms_a_decimal(lat_formateado)
                            lon_decimal = dms_a_decimal(lon_formateado)
                            latitud = str(lat_decimal).replace('.', ',') if lat_decimal is not None else ""
                            longitud = str(lon_decimal).replace('.', ',') if lon_decimal is not None else ""

                    # Actualizar valores
                    updates = {
                        13: ubicacion,
                        14: latitud,
                        15: longitud,
                        18: cultivo,
                        19: variedad,
                        21: año_plantacion,
                        23: plantas_ha,
                        24: emisores_ha,
                        30: superficie_ha,
                        31: superficie_m2,
                        32: caudal,
                        33: ppeq
                    }

                    for col, value in updates.items():
                        row_manager.update_cell(col, value)

                    if comentarios_seleccionados:
                        comentarios_str = ", ".join(comentarios_seleccionados) + "."
                        row_manager.update_cell(40, comentarios_str)

                    row_manager.save_changes()
                    st.success("✅ Cambios guardados correctamente.")
                    
                    # Botones de navegación
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button("Anterior"):
                            st.session_state.current_row -= 1
                            st.experimental_rerun()
                    with col2:
                        if st.button("Siguiente"):
                            st.session_state.current_row += 1
                            st.experimental_rerun()
                    with col3:
                        if st.button("Ir a otra fila"):
                            st.session_state.pop('row_data', None)
                            st.experimental_rerun()

                except Exception as e:
                    st.error(f"Error al guardar los cambios: {str(e)}")

if __name__ == "__main__":
    main()
