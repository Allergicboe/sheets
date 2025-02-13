import streamlit as st
import gspread
from google.oauth2 import service_account
import pandas as pd
from math import ceil
import re

# --- Autenticación y configuración de Sheets ---
# Puedes utilizar st.secrets o un archivo JSON de credenciales.
if "gcp_service_account" in st.secrets:
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"]
    )
else:
    credentials = service_account.Credentials.from_service_account_file("service_account.json")

gc = gspread.authorize(credentials)
SPREADSHEET_URL = 'https://docs.google.com/spreadsheets/d/1_74Vt8KL0bscmSME5Evm6hn4DWytLdGDGb98tHyNwtc/edit?usp=drive_link'
sheet = gc.open_by_url(SPREADSHEET_URL).sheet1

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
    decimal = float(grados) + float(minutos) / 60 + float(segundos) / 3600
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

row_manager = RowManager(sheet)

# --- Lista de comentarios y función para gestionar estados de checkboxes ---
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

def update_checkbox_states():
    group_A = {"La cuenta no existe", "La sonda no existe o no está asociada", "Consultar datos faltantes"}
    group_B = {"La sonda no tiene sensores habilitados", "La sonda no está operando"}
    group_C_exclusive = {"No hay datos de cultivo"}
    group_C_non_exclusive = {"Datos de cultivo incompletos", "Datos de cultivo no son reales"}
    disabled_states = {desc: False for desc in comentarios_lista}
    
    group_A_selected = [desc for desc in group_A if st.session_state.get(desc, False)]
    if group_A_selected:
        for desc in group_A:
            if desc in group_A_selected:
                disabled_states[desc] = False
            else:
                st.session_state[desc] = False
                disabled_states[desc] = True
        for desc in comentarios_lista:
            if desc not in group_A:
                st.session_state[desc] = False
                disabled_states[desc] = True
    else:
        for desc in group_A:
            disabled_states[desc] = False
        group_B_selected = [desc for desc in group_B if st.session_state.get(desc, False)]
        if group_B_selected:
            for desc in group_B:
                if desc in group_B_selected:
                    disabled_states[desc] = False
                else:
                    st.session_state[desc] = False
                    disabled_states[desc] = True
        else:
            for desc in group_B:
                disabled_states[desc] = False
        if st.session_state.get("No hay datos de cultivo", False):
            for desc in group_C_non_exclusive:
                st.session_state[desc] = False
                disabled_states[desc] = True
        else:
            for desc in group_C_non_exclusive:
                disabled_states[desc] = False
        if any(st.session_state.get(desc, False) for desc in group_C_non_exclusive):
            st.session_state["No hay datos de cultivo"] = False
            disabled_states["No hay datos de cultivo"] = True
        else:
            disabled_states["No hay datos de cultivo"] = False
    return disabled_states

# --- Callbacks para actualizar campos ---
def on_ubicacion_change():
    new_val = st.session_state['ubicacion']
    if new_val:
        coords = formatear_dms(new_val)
        if coords:
            lat_formateado, lon_formateado = coords
            lat_decimal = dms_a_decimal(lat_formateado)
            lon_decimal = dms_a_decimal(lon_formateado)
            st.session_state['latitud'] = f"{lat_decimal:.8f}".replace('.', ',') if lat_decimal is not None else ""
            st.session_state['longitud'] = f"{lon_decimal:.8f}".replace('.', ',') if lon_decimal is not None else ""
        else:
            st.session_state['latitud'] = ""
            st.session_state['longitud'] = ""

def on_superficie_ha_change():
    try:
        superficie_ha_value = float(st.session_state['superficie_ha'].replace(",", "."))
        st.session_state['superficie_m2'] = str(ceil(superficie_ha_value * 10000))
    except ValueError:
        st.session_state['superficie_m2'] = ""

def actualizar_plantas_emisores():
    try:
        superficie_ha_value = float(st.session_state['superficie_ha'].replace(",", "."))
        if superficie_ha_value > 0:
            try:
                plantas_ha_val = float(st.session_state['plantas_ha'].replace(",", "."))
                emisores_ha_val = float(st.session_state['emisores_ha'].replace(",", "."))
                st.session_state['plantas_ha'] = str(ceil(plantas_ha_val / superficie_ha_value))
                st.session_state['emisores_ha'] = str(ceil(emisores_ha_val / superficie_ha_value))
                st.success("Plantas/ha y Emisores/ha actualizados.")
            except ValueError:
                st.error("Error: Plantas/ha y Emisores/ha deben ser numéricos.")
        else:
            st.error("Error: Superficie (ha) debe ser > 0.")
    except ValueError:
        st.error("Error: Superficie (ha) debe ser numérica.")

# --- Interfaz de la aplicación ---
st.title("Editor de Planilla - Streamlit")

# Inicializar variable de control para carga de fila
if "row_loaded" not in st.session_state:
    st.session_state.row_loaded = False

# --- Sección: Cargar Fila ---
if not st.session_state.row_loaded:
    st.subheader("Cargar Fila")
    row_number_input = st.number_input("Fila de inicio:", min_value=1, value=1, step=1, key="row_number_input")
    if st.button("Cargar fila"):
        try:
            row_manager.load_row(st.session_state.row_number_input)
            row_data = row_manager.current_row_data
            st.session_state.current_row_number = st.session_state.row_number_input
            # Inicializar campos a partir de la fila
            st.session_state["ubicacion"] = row_data[12] if len(row_data) > 12 else ""
            st.session_state["latitud"] = row_data[13] if len(row_data) > 13 else ""
            st.session_state["longitud"] = row_data[14] if len(row_data) > 14 else ""
            st.session_state["cultivo"] = row_data[17] if len(row_data) > 17 else ""
            st.session_state["variedad"] = row_data[18] if len(row_data) > 18 else ""
            st.session_state["año_plantacion"] = row_data[20] if len(row_data) > 20 else ""
            st.session_state["plantas_ha"] = row_data[22] if len(row_data) > 22 else ""
            st.session_state["emisores_ha"] = row_data[23] if len(row_data) > 23 else ""
            st.session_state["superficie_ha"] = row_data[29] if len(row_data) > 29 else ""
            st.session_state["superficie_m2"] = row_data[30] if len(row_data) > 30 else ""
            st.session_state["caudal"] = row_data[31] if len(row_data) > 31 else ""
            st.session_state["ppeq"] = row_data[32] if len(row_data) > 32 else ""
            # Inicializar checkboxes para comentarios si aún no existen
            for comentario in comentarios_lista:
                if comentario not in st.session_state:
                    st.session_state[comentario] = False
            st.session_state.row_loaded = True
        except Exception as e:
            st.error(f"Error al cargar la fila {st.session_state.row_number_input}: {e}")
    st.stop()

# --- Mostrar información de la fila cargada ---
st.subheader("Datos de la Fila")
row_data = row_manager.sheet.row_values(st.session_state.current_row_number)
if len(row_data) >= 12:
    st.write(f"**Cuenta:** {row_data[1]} [ID: {row_data[0]}]")
    st.write(f"**Campo:** {row_data[3]} [ID: {row_data[2]}]")
    st.write(f"**Sonda:** {row_data[10]} [ID: {row_data[11]}]")
    st.write(f"**Comentario:** {row_data[39]}")
    st.markdown(f"[Link Cuenta](www.dropcontrol.com/site/dashboard/campo.do?cuentaId={row_data[0]}&campoId={row_data[2]})")
    st.markdown(f"[Link Sonda](https://www.dropcontrol.com/site/ha/suelo.do?cuentaId={row_data[0]}&campoId={row_data[2]}&sectorId={row_data[11]})")
else:
    st.write("Fila sin datos suficientes.")

# --- Formulario para editar la fila ---
st.subheader("Editar Datos")
with st.form("edit_form"):
    col1, col2 = st.columns(2)
    with col1:
        st.text_input("Ubicación:", key="ubicacion", on_change=on_ubicacion_change)
        st.text_input("Latitud:", key="latitud", disabled=True)
        st.text_input("Longitud:", key="longitud", disabled=True)
        st.text_input("Superficie (ha):", key="superficie_ha", on_change=on_superficie_ha_change)
        st.text_input("Superficie (m2):", key="superficie_m2", disabled=True)
        st.text_input("Caudal teórico (m³/h):", key="caudal")
        st.text_input("PPeq [mm/h]:", key="ppeq")
    with col2:
        st.text_input("Plantas/ha:", key="plantas_ha")
        st.text_input("Emisores/ha:", key="emisores_ha")
        st.text_input("Cultivo:", key="cultivo")
        st.text_input("Variedad:", key="variedad")
        st.text_input("Año plantación:", key="año_plantacion")
    
    st.write("### Seleccionar comentarios:")
    disabled_states = update_checkbox_states()
    for comentario in comentarios_lista:
        st.checkbox(comentario, key=comentario, disabled=disabled_states[comentario])
    
    submitted = st.form_submit_button("Guardar cambios")
    if submitted:
        # Mapeo de campos a columnas (los índices se ajustan a la planilla)
        column_mapping = {
            'ubicacion': 13, 'latitud': 14, 'longitud': 15, 'cultivo': 18,
            'variedad': 19, 'año_plantacion': 21, 'plantas_ha': 23, 'emisores_ha': 24,
            'superficie_ha': 30, 'superficie_m2': 31, 'caudal': 32, 'ppeq': 33
        }
        for field, col_index in column_mapping.items():
            row_manager.update_cell(col_index, st.session_state.get(field, ""))
        comentarios_seleccionados = [comentario for comentario in comentarios_lista if st.session_state.get(comentario)]
        if comentarios_seleccionados:
            comentarios_str = ", ".join(comentarios_seleccionados) + "."
            row_manager.update_cell(40, comentarios_str)
        try:
            row_manager.save_changes()
            st.success("✅ Cambios guardados correctamente.")
        except Exception as e:
            st.error(f"Error al guardar cambios: {e}")

# --- Botón para actualizar Plantas/ha y Emisores/ha ---
if st.button("Actualizar Plantas/ha y Emisores/ha"):
    actualizar_plantas_emisores()

# --- Botones de navegación ---
st.write("### Navegación")
col_nav1, col_nav2, col_nav3 = st.columns(3)
if col_nav1.button("Siguiente"):
    st.session_state.row_loaded = False
    st.session_state.row_number_input = st.session_state.current_row_number + 1
    st.experimental_rerun()
if col_nav2.button("Volver"):
    st.session_state.row_loaded = False
    st.session_state.row_number_input = st.session_state.current_row_number
    st.experimental_rerun()
if col_nav3.button("Seleccionar otra fila"):
    new_row = st.number_input("Número de fila:", min_value=1, value=st.session_state.current_row_number, step=1, key="new_row_input")
    if st.button("Confirmar", key="confirm_button"):
        st.session_state.row_loaded = False
        st.session_state.row_number_input = new_row
        st.experimental_rerun()
