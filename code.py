import streamlit as st
import gspread
from google.oauth2 import service_account
from math import ceil
import re

# --- Configuración de la página ---
st.set_page_config(page_title="Gestión de Planillas", layout="wide")

# --- Funciones para conversión de coordenadas DMS ---
def formatear_dms(dms):
    match = re.match(
        r"(\d{1,2})°\s*(\d{1,2})'\s*([\d.]+)\"\s*([NS])\s*(\d{1,3})°\s*(\d{1,2})'\s*([\d.]+)\"\s*([EW])",
        str(dms)
    )
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
        if any(comment in comentarios for comment in [
            "La sonda no existe o no está asociada",
            "La sonda no tiene sensores habilitados",
            "La cuenta no existe"
        ]):
            color = {"red": 1, "green": 0, "blue": 0}  # Rojo
        elif "Consultar datos faltantes" in comentarios:
            color = {"red": 0, "green": 1, "blue": 0}  # Verde
        else:
            color = {"red": 1, "green": 1, "blue": 0}  # Amarillo
        self.sheet.format(cell_address, {"backgroundColor": color})

    def save_changes(self):
        if self.modified_cells:
            cells = [
                gspread.Cell(self.current_row_number, col, value)
                for col, value in self.modified_cells.items()
            ]
            self.sheet.update_cells(cells)
            if 40 in self.modified_cells:
                self.update_cell_color(self.modified_cells[40])
            self.modified_cells = {}

# --- Conexión a Google Sheets ---
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

# Función para reiniciar la app
def rerun_app():
    try:
        st.experimental_rerun()
    except AttributeError:
        st.info("Por favor, refresca la página manualmente para ver los cambios.")

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

    row_manager = RowManager(sheet)

    # Control de la fila actual en session_state
    if "current_row" not in st.session_state:
        st.session_state.current_row = 1

    # Sidebar para selección de fila
    with st.sidebar:
        row_number = st.number_input("Número de fila", min_value=1, value=st.session_state.current_row, step=1)
        if st.button("Cargar fila"):
            st.session_state.row_data = row_manager.load_row(row_number)
            st.session_state.current_row = row_number
            rerun_app()

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
        st.write(f"**Comentario actual:** {row_data[39] if len(row_data) > 39 else ''}")

    st.markdown(f"[Link Cuenta](https://www.dropcontrol.com/site/dashboard/campo.do?cuentaId={row_data[0]}&campoId={row_data[2]})")
    st.markdown(f"[Link Sonda](https://www.dropcontrol.com/site/ha/suelo.do?cuentaId={row_data[0]}&campoId={row_data[2]}&sectorId={row_data[11]})")

    # Formulario para editar datos (usando keys en session_state)
    with st.form("edit_form"):
        col1, col2 = st.columns(2)
        with col1:
            ubicacion = st.text_input("Ubicación", value=row_data[12] if len(row_data) > 12 else "", key="ubicacion")
            latitud = st.text_input("Latitud", value=row_data[13] if len(row_data) > 13 else "", key="latitud", disabled=True)
            longitud = st.text_input("Longitud", value=row_data[14] if len(row_data) > 14 else "", key="longitud", disabled=True)
            cultivo = st.text_input("Cultivo", value=row_data[17] if len(row_data) > 17 else "", key="cultivo")
            variedad = st.text_input("Variedad", value=row_data[18] if len(row_data) > 18 else "", key="variedad")
            ano_plantacion = st.text_input("Año plantación", value=row_data[20] if len(row_data) > 20 else "", key="ano_plantacion")
        with col2:
            plantas_ha = st.text_input("Plantas/ha", value=row_data[22] if len(row_data) > 22 else "", key="plantas_ha")
            emisores_ha = st.text_input("Emisores/ha", value=row_data[23] if len(row_data) > 23 else "", key="emisores_ha")
            superficie_ha = st.text_input("Superficie (ha)", value=row_data[29] if len(row_data) > 29 else "", key="superficie_ha")
            superficie_m2 = st.text_input("Superficie (m2)", value=row_data[30] if len(row_data) > 30 else "", key="superficie_m2", disabled=True)
            caudal = st.text_input("Caudal teórico (m³/h)", value=row_data[31] if len(row_data) > 31 else "", key="caudal")
            ppeq = st.text_input("PPeq [mm/h]", value=row_data[32] if len(row_data) > 32 else "", key="ppeq")
        
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
        
        submit_form = st.form_submit_button("Guardar cambios")

    if submit_form:
        # Si se ingresó ubicación, se calcula latitud y longitud
        if st.session_state.ubicacion:
            coords = formatear_dms(st.session_state.ubicacion)
            if coords:
                lat_formateado, lon_formateado = coords
                lat_decimal = dms_a_decimal(lat_formateado)
                lon_decimal = dms_a_decimal(lon_formateado)
                st.session_state.latitud = str(lat_decimal).replace('.', ',') if lat_decimal is not None else ""
                st.session_state.longitud = str(lon_decimal).replace('.', ',') if lon_decimal is not None else ""

        # Actualizar superficie_m2 a partir de superficie (ha)
        try:
            superficie_ha_val = float(st.session_state.superficie_ha.replace(",", "."))
            st.session_state.superficie_m2 = str(ceil(superficie_ha_val * 10000))
        except Exception:
            st.session_state.superficie_m2 = ""
        
        # Actualizar plantas/ha y emisores/ha (si se pueden convertir a número)
        try:
            if superficie_ha_val > 0:
                try:
                    plantas_val = float(st.session_state.plantas_ha.replace(",", "."))
                    emisores_val = float(st.session_state.emisores_ha.replace(",", "."))
                    st.session_state.plantas_ha = str(ceil(plantas_val / superficie_ha_val))
                    st.session_state.emisores_ha = str(ceil(emisores_val / superficie_ha_val))
                except Exception:
                    pass
        except Exception:
            pass

        # Mapear y actualizar los valores en la hoja de cálculo
        updates = {
            13: st.session_state.ubicacion,
            14: st.session_state.latitud,
            15: st.session_state.longitud,
            18: st.session_state.cultivo,
            19: st.session_state.variedad,
            21: st.session_state.ano_plantacion,
            23: st.session_state.plantas_ha,
            24: st.session_state.emisores_ha,
            30: st.session_state.superficie_ha,
            31: st.session_state.superficie_m2,
            32: st.session_state.caudal,
            33: st.session_state.ppeq
        }
        for col, value in updates.items():
            row_manager.update_cell(col, value)
        if comentarios_seleccionados:
            comentarios_str = ", ".join(comentarios_seleccionados) + "."
            row_manager.update_cell(40, comentarios_str)
        try:
            row_manager.save_changes()
            st.success("✅ Cambios guardados correctamente.")
        except Exception as e:
            st.error(f"Error al guardar los cambios: {e}")

        # --- Botones de navegación ---
        nav_col1, nav_col2, nav_col3 = st.columns(3)
        with nav_col1:
            if st.button("Siguiente"):
                st.session_state.current_row += 1
                st.session_state.row_data = row_manager.load_row(st.session_state.current_row)
                rerun_app()
        with nav_col2:
            if st.button("Volver"):
                if st.session_state.current_row > 1:
                    st.session_state.current_row -= 1
                    st.session_state.row_data = row_manager.load_row(st.session_state.current_row)
                    rerun_app()
        with nav_col3:
            if st.button("Seleccionar otra fila"):
                del st.session_state.row_data
                rerun_app()

if __name__ == "__main__":
    main()
