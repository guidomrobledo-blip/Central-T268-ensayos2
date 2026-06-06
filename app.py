import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logic_clientes, logic_faltantes, logic_domicilios, logic_informe, logic_seguridad
import os
import json
import hashlib

if "pedidos_manual" not in st.session_state:
    st.session_state.pedidos_manual = []
    
if "pedido_a_mover" not in st.session_state:
    st.session_state.pedido_a_mover = None

# 🎨 ESTILOS PERSONALIZADOS
st.markdown("""
<style>

/* Nombre archivo */
[data-testid="stFileUploader"] span {
    color: #FFFFFF !important;
    font-weight: 500;
    text-shadow: 0 0 8px rgba(139, 92, 246, 0.25);
}

/* Tamaño archivo */
[data-testid="stFileUploader"] small {
    color: #A78BFA !important;
}

/* Botón agregar pedido */
div.stButton > button {
    height: 25px;
    margin-top: 10px;
    font-size: 8px;
}
</style>
""", unsafe_allow_html=True)

# --- CONFIGURACION ---
st.set_page_config(
    page_title="Panel Operaciones Online Carrefour",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- FECHA ARGENTINA (UTC-3) ---
fecha_ar_ahora = datetime.utcnow() - timedelta(hours=3)
hoy_ar = fecha_ar_ahora.date()
manana_ar_obj = hoy_ar + timedelta(days=1)
manana_txt = manana_ar_obj.strftime("%d/%m/%Y")

# --- ARCHIVO DE PERSISTENCIA PARA DATOS MENSUALES ---
DATA_FILE = "pedidos_mensuales.json"

# Diccionario para traducir dias de la semana
DIAS_SEMANA_ES = {
    0: "Lun", 1: "Mar", 2: "Mie", 3: "Jue", 4: "Vie", 5: "Sab", 6: "Dom"
}

def cargar_datos_mensuales():
    """Carga los datos del mes desde el archivo JSON. Reinicia si cambia de mes."""
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                datos = json.load(f)
            # Verificar si es el mismo mes
            mes_guardado = datos.get("mes", "")
            mes_actual = hoy_ar.strftime("%Y-%m")
            if mes_guardado != mes_actual:
                # Nuevo mes, reiniciar datos
                return {"mes": mes_actual, "pedidos_por_dia": {}, "archivos_procesados": [], "modalidades": {"DOMICILIOS": 0, "DRIVE": 0, "SUCURSAL": 0}}
            return datos
        else:
            return {"mes": hoy_ar.strftime("%Y-%m"), "pedidos_por_dia": {}, "archivos_procesados": [], "modalidades": {"DOMICILIOS": 0, "DRIVE": 0, "SUCURSAL": 0}}
    except Exception:
        return {"mes": hoy_ar.strftime("%Y-%m"), "pedidos_por_dia": {}, "archivos_procesados": [], "modalidades": {"DOMICILIOS": 0, "DRIVE": 0, "SUCURSAL": 0}}

def guardar_datos_mensuales(datos):
    """Guarda los datos del mes en el archivo JSON."""
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(datos, f)
    except Exception:
        pass

def reiniciar_contador_mensual():
    """Reinicia el contador mensual."""
    datos = {"mes": hoy_ar.strftime("%Y-%m"), "pedidos_por_dia": {}, "archivos_procesados": [], "modalidades": {"DOMICILIOS": 0, "DRIVE": 0, "SUCURSAL": 0}}
    guardar_datos_mensuales(datos)
    return datos

def obtener_hash_archivo(archivo_bytes):
    """Genera un hash unico para identificar archivos duplicados."""
    return hashlib.md5(archivo_bytes).hexdigest()

def extraer_fecha_entrega(df):
    """Extrae la fecha de la columna FECHA ENTREGA del DataFrame."""
    col_fecha = None
    for col in df.columns:
        if "FECHA" in str(col).upper() and "ENTREGA" in str(col).upper():
            col_fecha = col
            break

    if col_fecha is None:
        return None

    try:
        fecha_val = df[col_fecha].dropna().iloc[0]
        fecha_str = str(fecha_val).strip()

        # 🔥 FORZAR interpretación argentina SIEMPRE
        fecha = pd.to_datetime(
            fecha_str,
            dayfirst=True,
            errors='coerce'
        )

        if pd.isna(fecha):
            return None

        return fecha.date()

    except Exception:
        return None

def contar_modalidades(df):
    """Cuenta las modalidades de entrega del DataFrame."""
    modalidades_conteo = {"DOMICILIOS": 0, "DRIVE": 0, "SUCURSAL": 0}
    
    # Buscar la columna de modalidad de entrega (priorizar "MODALIDAD DE ENTREGA")
    col_modalidad = None
    
    # Primera busqueda: columna exacta o similar a "MODALIDAD DE ENTREGA"
    for col in df.columns:
        col_upper = str(col).upper().strip()
        if "MODALIDAD" in col_upper and "ENTREGA" in col_upper:
            col_modalidad = col
            break
    
    # Segunda busqueda: solo "MODALIDAD"
    if col_modalidad is None:
        for col in df.columns:
            col_upper = str(col).upper().strip()
            if "MODALIDAD" in col_upper and "FECHA" not in col_upper:
                col_modalidad = col
                break
    
    # Tercera busqueda: "TIPO ENTREGA" o "CANAL"
    if col_modalidad is None:
        for col in df.columns:
            col_upper = str(col).upper().strip()
            if ("TIPO" in col_upper and "ENTREGA" in col_upper) or "CANAL" in col_upper:
                col_modalidad = col
                break
    
    if col_modalidad is not None:
        for valor in df[col_modalidad].dropna():
            valor_upper = str(valor).upper().strip()
            # Detectar DOMICILIO/DOMICILIOS
            if "DOMICILIO" in valor_upper or "A DOMICILIO" in valor_upper:
                modalidades_conteo["DOMICILIOS"] += 1
            # Detectar DRIVE
            elif "DRIVE" in valor_upper:
                modalidades_conteo["DRIVE"] += 1
            # Detectar SUCURSAL (retiro en tienda, pick up, etc.)
            elif "SUCURSAL" in valor_upper or "RETIRO" in valor_upper or "PICK" in valor_upper or "TIENDA" in valor_upper:
                modalidades_conteo["SUCURSAL"] += 1
    
    return modalidades_conteo


def registrar_pedidos_cdp(archivo_bytes, df):
    """Registra los pedidos del archivo CDP si no fue procesado antes."""
    datos = cargar_datos_mensuales()
    
    # Verificar si el archivo ya fue procesado
    archivo_hash = obtener_hash_archivo(archivo_bytes)
    if archivo_hash in datos["archivos_procesados"]:
        return datos, False  # Ya fue procesado, no registrar de nuevo
    
    # Extraer la fecha de entrega del Excel
    fecha_entrega = extraer_fecha_entrega(df)
    if fecha_entrega is None:
        return datos, False
    
    # Solo registrar si la fecha es del mes actual
    if fecha_entrega.strftime("%Y-%m") != datos["mes"]:
        return datos, False
    
    # Registrar los pedidos para esa fecha
    fecha_str = fecha_entrega.strftime("%Y-%m-%d")
    cantidad_pedidos = len(df)

    # Guardar la cantidad de pedidos para esa fecha
    datos["pedidos_por_dia"][fecha_str] = cantidad_pedidos
    datos["archivos_procesados"].append(archivo_hash)
    
    # Contar modalidades y acumular al total mensual
    modalidades_archivo = contar_modalidades(df)
    if "modalidades" not in datos:
        datos["modalidades"] = {"DOMICILIOS": 0, "DRIVE": 0, "SUCURSAL": 0}
    
    datos["modalidades"]["DOMICILIOS"] += modalidades_archivo["DOMICILIOS"]
    datos["modalidades"]["DRIVE"] += modalidades_archivo["DRIVE"]
    datos["modalidades"]["SUCURSAL"] += modalidades_archivo["SUCURSAL"]
    
    guardar_datos_mensuales(datos)
    return datos, True

def obtener_datos_semana(datos_mensuales, inicio_semana):
    """Obtiene los datos de pedidos para la semana especificada."""
    pedidos_semana = []
    dias_labels = []
    
    for i in range(7):
        dia = inicio_semana + timedelta(days=i)
        fecha_str = dia.strftime("%Y-%m-%d")
        dia_semana = DIAS_SEMANA_ES[dia.weekday()]
        dia_num = dia.day
        
        # Formato: "Lun-9", "Mar-10", etc.
        label = f"{dia_semana}-{dia_num}"
        dias_labels.append(label)
        
        # Obtener pedidos de ese dia (0 si no hay datos)
        pedidos = datos_mensuales.get("pedidos_por_dia", {}).get(fecha_str, 0)
        pedidos_semana.append(pedidos)
    
    return dias_labels, pedidos_semana

def obtener_datos_mes(datos_mensuales):
    """Obtiene los datos de pedidos para todo el mes."""
    pedidos_mes = []
    dias_labels = []
    
    # Obtener el primer dia del mes actual
    primer_dia_mes = hoy_ar.replace(day=1)
    
    # Calcular el ultimo dia del mes
    if hoy_ar.month == 12:
        ultimo_dia_mes = hoy_ar.replace(day=31)
    else:
        ultimo_dia_mes = (hoy_ar.replace(month=hoy_ar.month + 1, day=1) - timedelta(days=1))
    
    dia_actual = primer_dia_mes
    while dia_actual <= ultimo_dia_mes:
        fecha_str = dia_actual.strftime("%Y-%m-%d")
        dias_labels.append(dia_actual.day)
        pedidos = datos_mensuales.get("pedidos_por_dia", {}).get(fecha_str, 0)
        pedidos_mes.append(pedidos)
        dia_actual += timedelta(days=1)
    
    return dias_labels, pedidos_mes

    def calcular_total_mes(datos_mensuales):
        """Calcula el total de pedidos del mes (solo dias con datos)."""
        pedidos_por_dia = datos_mensuales.get("pedidos_por_dia", {})
        return sum(pedidos_por_dia.values())
    
    with open("styles_corporativo.css", "r", encoding="utf-8") as f:
        css = f.read()
    
    st.markdown(
        f"<style>{css}</style>",
        unsafe_allow_html=True
    )

# --- LOADING SCREEN ---
import base64

def get_image_base64(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except:
        return None

# Show loading screen briefly
loading_logo_base64 = get_image_base64("logo.png.webp")
if loading_logo_base64:
    st.markdown(f"""
        <div class="loading-screen" id="loadingScreen">
            <img src="data:image/webp;base64,{loading_logo_base64}" class="loading-logo" style="max-width: 200px; height: auto;" alt="Carrefour">
        </div>
    """, unsafe_allow_html=True)

# --- HEADER ---
logo_base64 = get_image_base64("carrefour+logo.png")
logo_html = ""
if logo_base64:
    logo_html = f'<img src="data:image/png;base64,{logo_base64}" class="header-logo" alt="Carrefour">'
else:
    logo_html = '<span style="color: #9CA3AF;">Carrefour</span>'

st.markdown(f"""
    <div class="header-container">
        <div class="header-left">
            {logo_html}
            <div class="header-text">
                <h1 class="title-main">Panel Operaciones Online Carrefour</h1>
                <p class="subtitle-main">Tienda 268 - Rosario | {hoy_ar.strftime("%d/%m/%Y")}</p>
            </div>
        </div>
    </div>
    <div class="header-divider"></div>
""", unsafe_allow_html=True)

# --- BUTTON ROW ---
st.write("")
b1, b2, b3, b4, b5, b6 = st.columns(6)
with b1: 
    btn_1 = st.button("CLIENTES", key="top_1", use_container_width=True)
with b2:  
    btn_seguridad = st.button("PERSONAL SEGURIDAD", key="top_seguridad", use_container_width=True)
with b3:  
    btn_2 = st.button("FALTANTES", key="top_2", use_container_width=True)
with b4:  
    btn_3 = st.button("DOMICILIOS", key="top_3", use_container_width=True)
with b5:  
    btn_4 = st.button("INFORME", key="top_4", use_container_width=True)
with b6:  
    st.link_button("PLANILLA MEC", "https://docs.google.com/spreadsheets/d/1v0Rls8fg_uIGfhA1t3CzINq3VfAUvPY3DY8_m_ZSmM8/edit#gid=0", use_container_width=True)
   
# --- MAIN BODY ---
st.write("")
col_izq, col_der = st.columns([1, 1], gap="large")

with col_izq:
    # --- CARD 1: CDP UPLOAD ---
    st.markdown('''
        <div class="glass-card">
            <div class="card-title"><span class="card-icon">📂</span> CARGAR EXCEL.JANIS</div>
    ''', unsafe_allow_html=True)
    archivo_cdp = st.file_uploader("Subir CDP", type=["xlsx"], label_visibility="collapsed", key="cdp_upload")
    
    # Variables para almacenar datos del CDP
    df_clean = None
    fecha_tit = None
    archivo_cdp_bytes = None
    
if archivo_cdp:

    # Leer archivo como bytes
    archivo_cdp_bytes = archivo_cdp.read()
    archivo_cdp.seek(0)

    with st.spinner("Procesando archivo..."):

        df_raw = pd.read_excel(archivo_cdp)

        # =========================================
        # NORMALIZADOR JANIS
        # =========================================

        columnas_janis = [
            "displayId",
            "shippingType",
            "dropoffStreet",
            "dropoffNumber",
            "scheduleStart",
            "scheduleEnd",
            "receiverFullname",
            "receiverPhone"
        ]

        es_janis = all(col in df_raw.columns for col in columnas_janis)

        if es_janis:

            df_janis = pd.DataFrame()

            # NUMERO PEDIDO
            df_janis["NUMERO PEDIDO"] = (
                df_raw["orderCommerceIds"]
                .astype(str)
                .str.split("-")
                .str[0]
            )
            # MODALIDAD
            df_janis["MODALIDAD DE ENTREGA"] = (
                df_raw["carrierName"]
                .replace({
                    "Envío a Domicilio 0268 - Hiper Rosario Pueyrredón": "Domicilio",
                    "Drive 0268 - Hiper Rosario Pueyrredón": "Drive",
                    "Retiro en Tienda 0268 - Hiper Rosario Pueyrredón": "Sucursal"
                })
            )
            
            # DIRECCION
            # CALLE
            df_janis["CALLE"] = df_raw["dropoffStreet"]
            
            # NUMERO
            df_janis["NUMERO"] = df_raw["dropoffNumber"]
            
            # DEPTO
            df_janis["DEPTO"] = df_raw["dropoffComplement"]

            # FECHA ENTREGA
            df_janis["FECHA ENTREGA"] = pd.to_datetime(
                df_raw["scheduleStart"],
                errors="coerce"
            )

            # BANDA HORARIA
            hora_inicio = pd.to_datetime(
                df_raw["scheduleStart"],
                errors="coerce"
            ).dt.strftime("%H:%M")

            hora_fin = pd.to_datetime(
                df_raw["scheduleEnd"],
                errors="coerce"
            ).dt.strftime("%H:%M")

            df_janis["BANDA HORARIA"] = (
                hora_inicio + " a " + hora_fin
            )

            # CLIENTE COMPLETO
            df_janis["NOMBRE CLIENTE"] = (
                df_raw["receiverFullname"]
                .fillna("")
                .astype(str)
                .str.strip()
            )
            
            # TELEFONO CLIENTE
            df_janis["TELEFONO CLIENTE"] = (
                df_raw["receiverPhone"]
            )
            
            # TEL. PARTICULAR
            df_janis["TEL. PARTICULAR"] = (
                df_raw["receiverPhone"]
            )

            # Reemplazar dataframe original
            df_raw = df_janis.copy()

        # =========================================
        # LIMPIEZA FINAL
        # =========================================

        df_raw['FECHA ENTREGA'] = pd.to_datetime(
            df_raw['FECHA ENTREGA'],
            dayfirst=True,
            errors='coerce'
        )

        df_clean, fecha_tit = logic_clientes.motor_limpieza(df_raw)

        # Registrar pedidos para el grafico
        datos_actualizados, fue_registrado = registrar_pedidos_cdp(
            archivo_cdp_bytes,
            df_clean
        )

        # Evitar duplicados
        if fue_registrado:
            st.rerun()

    st.success(f"Janis.xlsx CARGADO: {fecha_tit}")

    # BOTONES
    if btn_1:
        with st.spinner("Procesando archivo..."):
            pdf = logic_clientes.generar_pdf_clientes(df_clean)

        st.download_button(
            "DESCARGAR PDF CLIENTES",
            bytes(pdf),
            f"Clientes_{fecha_tit}.pdf",
            use_container_width=True
        )

    if btn_seguridad:
        with st.spinner("Procesando archivo..."):
            pdf = logic_seguridad.generar_pdf_seguridad(
                df_clean,
                fecha_tit
            )

        st.download_button(
            "DESCARGAR PDF SEGURIDAD",
            bytes(pdf),
            f"Seguridad_{fecha_tit}.pdf",
            use_container_width=True
        )

    if btn_2:
        with st.spinner("Procesando archivo..."):
            pdf = logic_faltantes.generar_pdf_faltantes(
                df_clean,
                fecha_tit
            )

        st.download_button(
            "DESCARGAR PDF FALTANTES",
            bytes(pdf),
            f"Faltantes_{fecha_tit}.pdf",
            use_container_width=True
        )

    if btn_3:
        with st.spinner("Procesando archivo..."):
            pdf = logic_domicilios.generar_pdf_domicilios(
                df_clean,
                fecha_tit
            )

        st.download_button(
            "DESCARGAR PDF DOMICILIOS",
            bytes(pdf),
            f"Domicilios_{fecha_tit}.pdf",
            use_container_width=True
        )

    st.markdown('</div>', unsafe_allow_html=True)
    
    st.write("")

with col_der:

    st.markdown("""
    <div class="glass-card">
        <div class="card-title">
            <span class="card-icon">🚚</span>
            PANEL DE RUTEO
        </div>
    """, unsafe_allow_html=True)
    
    st.subheader("➕ Agregar pedido manual")

    col1, col2, col3, col4, col5 = st.columns(
        [2.5, 1.7, 1.4, 1.5, 1.2]
    )
    
    with col1:
        direccion_manual = st.text_input(
            "Dirección",
            key="direccion_manual"
        )
    
    with col2:
        numero_manual = st.text_input(
            "Nro Pedido",
            key="numero_manual"
        )
    
    with col3:
        tipo_manual = st.selectbox(
            "Tipo",
            [
                "Caja",
                "Reclamo",
                "Reprogramado",
                "NonFood",
                "Transferencia"
            ],
            key="tipo_manual"
        )
    
    with col4:
        banda_manual = st.selectbox(
            "Banda",
            [
                "10:00 a 14:00",
                "14:00 a 18:00",
                "18:00 a 21:00"
            ],
            key="banda_manual"
        )
    
    with col5:
        st.write("")
        btn_agregar_manual = st.button(
            "Agregar",
            use_container_width=True
        )
    if btn_agregar_manual:

        prefijos = {
            "Caja": "LC-",
            "Reclamo": "R-",
            "Reprogramado": "RP-",
            "NonFood": "NF-",
            "Transferencia": "TR-"
        }
    
        pedido_final = f"{prefijos[tipo_manual]}{numero_manual}"
    
        pedido_existente = None
    
        for pedido in st.session_state.pedidos_manual:
    
            if pedido["pedido"] == pedido_final:
    
                pedido_existente = pedido
                break
    
        if pedido_existente:

            st.session_state.pedido_a_mover = {
                "pedido": pedido_final,
                "direccion": direccion_manual,
                "tipo": tipo_manual,
                "banda_actual": pedido_existente["banda"],
                "banda_nueva": banda_manual
            }
    
        else:
    
            st.session_state.pedidos_manual.append({
                "direccion": direccion_manual,
                "pedido": pedido_final,
                "tipo": tipo_manual,
                "banda": banda_manual,
                "estado": "Pendiente"
            })

            mensaje = st.empty()

            mensaje.success("Pedido agregado")
            
            import time
            time.sleep(1)
            
            mensaje.empty()
            
            st.rerun()

    if st.session_state.pedido_a_mover:

        datos = st.session_state.pedido_a_mover
    
        if datos["banda_actual"] == datos["banda_nueva"]:
    
            st.warning(
                "⚠️ El pedido ya existe en esta banda horaria."
            )
    
        else:
    
            st.warning(
                f"⚠️ El pedido ya existe en la banda "
                f"{datos['banda_actual']}"
            )
    
            col_a, col_b = st.columns(2)
    
            with col_a:
                mover = st.button(
                    "Mover pedido",
                    key="btn_mover_pedido"
                )
    
            with col_b:
                cancelar = st.button(
                    "Cancelar",
                    key="btn_cancelar_mover"
                )
    
            if cancelar:
    
                st.session_state.pedido_a_mover = None
    
                st.rerun()
    
            if mover:
    
                st.session_state.pedidos_manual = [
    
                    p for p in st.session_state.pedidos_manual
    
                    if p["pedido"] != datos["pedido"]
    
                ]
    
                st.session_state.pedidos_manual.append({
    
                    "direccion": datos["direccion"],
                    "pedido": datos["pedido"],
                    "tipo": datos["tipo"],
                    "banda": datos["banda_nueva"],
                    "estado": "Pendiente"
    
                })
    
                st.session_state.pedido_a_mover = None
    
                st.rerun()

    if archivo_cdp and df_clean is not None:

        df_rutas = df_clean[
            df_clean["MODALIDAD DE ENTREGA"]
            .str.contains("Domicilio", case=False, na=False)
        ].copy()

        bandas = sorted(df_rutas["BANDA HORARIA"].dropna().unique())

        for banda in bandas:

            df_banda = df_rutas[
                df_rutas["BANDA HORARIA"] == banda
            ]
        
            cantidad_ecommerce = len(df_banda)

            manuales_banda = []

            for pedido in st.session_state.pedidos_manual:
            
                if pedido["banda"] == banda:
            
                    manuales_banda.append({
                        "ORDEN": "-",
                        "DIRECCIÓN": pedido["direccion"],
                        "PEDIDO": pedido["pedido"],
                        "TIPO": pedido["tipo"],
                        "ESTADO": pedido["estado"]
                    })
            
            cantidad_manuales = len(manuales_banda)

            titulo_banda = (
                f"📍 {banda} "
                f"[{cantidad_ecommerce} Ecomm]"
            )
            
            if cantidad_manuales > 0:
                titulo_banda += f" [{cantidad_manuales} manuales]"
        
            with st.expander(
                titulo_banda,
                expanded=False
            ):
        
                tabla_banda = pd.DataFrame({
                    "ORDEN": ["-"] * len(df_banda),
                    "DIRECCIÓN": df_banda["DIRECCIÓN"],
                    "PEDIDO": df_banda["NUMERO PEDIDO"],
                    "TIPO": ["Ecommerce"] * len(df_banda),
                    "ESTADO": ["Pendiente"] * len(df_banda)
                })
                
                if manuales_banda:
                
                    tabla_manual = pd.DataFrame(manuales_banda)
                
                    tabla_banda = pd.concat(
                        [tabla_banda, tabla_manual],
                        ignore_index=True
                    )
                
                st.dataframe(
                    tabla_banda,
                    use_container_width=True,
                    hide_index=True
                )
              
    else:

        st.info(
            "Cargue archivo.JANIS para visualizar los domicilios."
        )

    st.markdown("</div>", unsafe_allow_html=True)
    
# --- FOOTER ---
st.markdown('''
    <div class="footer">
        CENTRAL DE ARMADO T268 | CARREFOUR ONLINE | ROSARIO
    </div>
''', unsafe_allow_html=True)
