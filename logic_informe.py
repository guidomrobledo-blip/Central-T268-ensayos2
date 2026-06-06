import pandas as pd
from fpdf import FPDF
import os
from datetime import datetime

class PDFInforme(FPDF):
    def __init__(self, fecha_reporte):
        super().__init__(orientation='P', unit='mm', format='A4')
        self.fecha_reporte = fecha_reporte
        self.set_margins(10, 7, 10)
        self.set_auto_page_break(False)

    def header(self):
        # Logos nivelados
        if os.path.exists("carrefour+logo.png"):
            self.image("carrefour+logo.png", 10, 6, 45)

        self.set_y(10)
        self.set_font('Arial', 'B', 11)
        self.set_text_color(0)
        self.cell(0, 6, f"INFORME DE ESTADO DE PEDIDOS: {self.fecha_reporte}", 0, 1, 'R')
        self.cell(0, 6, "TIENDA: [268]", 0, 1, 'R')
        self.ln(5)

def normalizar_estado(val):
    v = str(val).strip().lower()
    if v == "picking en proceso": return "Controlado con faltante"
    if v in ["pendiente de picking", "pendiente de preparación"]: return "Pendiente de preparación"
    return v.capitalize()

def obtener_orden(row):
    mod, banda, est = str(row['MODALIDAD']).upper(), str(row['BANDA HORARIA']).upper(), str(row['ESTADO_NORM']).upper()
    if "DOMICILIO" in mod:
        if "10:00 A 14:00" in banda: return 1 if "CONTROLADO" == est else 2 if "FALTANTE" in est else 3 if "PREPARACIÓN" in est else 4
        if "14:00 A 18:00" in banda: return 5 if "CONTROLADO" == est else 6 if "FALTANTE" in est else 7 if "PREPARACIÓN" in est else 8
    base = 0
    if "09:00 A 13:00" in banda: base = 9
    elif "13:00 A 18:00" in banda: base = 17
    elif "18:00 A 21:00" in banda: base = 25
    if base > 0:
        offset = 0 if "CONTROLADO" == est else 2 if "FALTANTE" in est else 4 if "PREPARACIÓN" in est else 6
        sub_offset = 0 if "DRIVE" in mod else 1
        return base + offset + sub_offset
    return 999

def generar_pdf_informe(df, obs_usuario):
    df_inf = df[['NUMERO PEDIDO', 'MODALIDAD DE ENTREGA', 'BANDA HORARIA', 'FECHA ENTREGA', 'ESTADO']].copy()
    df_inf.columns = ['Nro PEDIDO', 'MODALIDAD', 'BANDA HORARIA', 'FECHA', 'ESTADO']
    df_inf['ESTADO_NORM'] = df_inf['ESTADO'].apply(normalizar_estado)
    df_inf['ORDEN'] = df_inf.apply(obtener_orden, axis=1)
    df_inf = df_inf.sort_values('ORDEN').reset_index(drop=True)

    try:
        val_fecha = df_inf['FECHA'].iloc[0]
        fecha_rep = val_fecha.strftime('%d/%m/%Y') if hasattr(val_fecha, 'strftime') else str(val_fecha)
    except:
        fecha_rep = datetime.now().strftime('%d/%m/%Y')

    total_filas = len(df_inf)
    espacio_disponible = 480
    h_normal = 5.0
    f_datos = 9.0

    if (total_filas * h_normal) > espacio_disponible:
        factor = espacio_disponible / (total_filas * h_normal)
        h_normal = max(4.0, h_normal * factor)
        f_datos = max(7.5, f_datos * factor)

    h_zocalo = h_normal * 0.4
    w = [8, 32, 32, 45, 30, 43]
    pdf = PDFInforme(fecha_rep)
    pdf.add_page()

    # Tabla
    pdf.set_font('Arial', 'B', 9)
    pdf.cell(w[0], 7, "#", 0, 0, 'C')
    pdf.set_fill_color(31, 78, 121); pdf.set_text_color(255)
    pdf.cell(w[1], 7, "Nro PEDIDO", 1, 0, 'L', True)
    pdf.cell(w[2], 7, "MODALIDAD", 1, 0, 'L', True)
    pdf.cell(w[3], 7, "BANDA HORARIA", 1, 0, 'L', True)
    pdf.cell(w[4], 7, "FECHA", 1, 0, 'L', True)
    pdf.cell(w[5], 7, "ESTADO", 1, 1, 'L', True)

    pdf.set_text_color(0)
    banda_actual = ""
    contador_banda = 0

    for i, row in df_inf.iterrows():
        if pdf.get_y() > 275: pdf.add_page()
        if row['BANDA HORARIA'] != banda_actual:
            if i > 0:
                pdf.cell(w[0], h_zocalo, "", 0, 0)
                pdf.set_fill_color(80, 80, 80)
                pdf.cell(sum(w[1:]), h_zocalo, "", 1, 1, 'C', True)
            banda_actual = row['BANDA HORARIA']
            contador_banda = 1
        else: contador_banda += 1

        pdf.set_font('Arial', '', f_datos)
        pdf.cell(w[0], h_normal, str(contador_banda), 0, 0, 'C')
        pdf.cell(w[1], h_normal, str(row['Nro PEDIDO']).replace(".0",""), 1, 0, 'L')
        pdf.cell(w[2], h_normal, str(row['MODALIDAD']).capitalize(), 1, 0, 'L')
        pdf.cell(w[3], h_normal, str(row['BANDA HORARIA']), 1, 0, 'L')
        f_v = row['FECHA'].strftime('%d/%m/%y') if hasattr(row['FECHA'], 'strftime') else str(row['FECHA'])
        pdf.cell(w[4], h_normal, f_v, 1, 0, 'L')

        e_u = str(row['ESTADO_NORM']).upper()
        color = (144, 238, 144) if "CONTROLADO" == e_u else (255, 215, 0) if "FALTANTE" in e_u else (255, 120, 120) if "PREPARACIÓN" in e_u else (255, 255, 255)
        pdf.set_fill_color(*color)
        pdf.cell(w[5], h_normal, f" {row['ESTADO_NORM']}", 1, 1, 'L', True)

    # --- SECCIÓN OBSERVACIONES (COLOR ROJO) ---
    pdf.ln(5)
    pdf.set_draw_color(0, 100, 0); pdf.set_text_color(0, 100, 0); pdf.set_font('Arial', 'B', 11)
    pdf.cell(0, 9, f"PEDIDOS TOTALES HASTA EL MOMENTO: {len(df_inf)}", 1, 1, 'C')

    if obs_usuario:
        pdf.ln(3)
        pdf.set_draw_color(200, 0, 0); pdf.set_text_color(200, 0, 0); pdf.set_font('Arial', 'B', 10)
        pdf.set_line_width(0.6)
        pdf.cell(0, 7, "OBSERVACIONES:", "LTR", 1, 'L')
        # --- AJUSTE: Texto ahora es rojo como el recuadro ---
        pdf.set_font('Arial', '', 10)
        pdf.multi_cell(0, 5, obs_usuario, "LBR", 'L')

    return bytes(pdf.output())
