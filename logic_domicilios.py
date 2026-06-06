import pandas as pd
from fpdf import FPDF
import os

class PDFLogistica(FPDF):
    def __init__(self, fecha_tit):
        super().__init__(orientation='P', unit='mm', format='A4')
        self.fecha_tit = fecha_tit
        self.set_margins(left=10, top=7, right=10)
        self.set_auto_page_break(False)
        self.mostrar_header = True  # control

    def header(self):
        if not self.mostrar_header:
            return

        if os.path.exists("carrefour+logo.png"):
            self.image("carrefour+logo.png", 10, 7, 45)
        if os.path.exists("imagen_5.png"):
            self.image("imagen_5.png", 63, 2, 30)

        self.set_font('Arial', 'B', 13)
        self.set_text_color(40, 40, 40)
        self.set_xy(100, 7)

        info_header = f"Domicilios por visitar hoy: {self.fecha_tit}\nTienda: [268]"
        self.multi_cell(100, 6, info_header, 0, 'R')
        self.ln(10)


def dibujar_encabezado(pdf, h_celda, f_size_datos, w_num, w_pedido, w_mod, w_banda, w_dir):
    pdf.set_fill_color(220, 220, 220)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('Arial', 'B', f_size_datos - 1)

    pdf.cell(w_num, h_celda, '#', 1, 0, 'C', True)
    pdf.cell(w_pedido, h_celda, 'Nro PEDIDO', 1, 0, 'C', True)
    pdf.cell(w_mod, h_celda, 'MODALIDAD', 1, 0, 'C', True)
    pdf.cell(w_banda, h_celda, 'BANDA HORARIA', 1, 0, 'C', True)
    pdf.cell(w_dir, h_celda, 'DIRECCIÓN', 1, 1, 'C', True)


def generar_pdf_domicilios(df, fecha_tit):
    df_logistica = df[df['MODALIDAD DE ENTREGA'].str.contains('Domicilio', case=False, na=False)].copy()

    if df_logistica.empty:
        pdf_v = FPDF()
        pdf_v.add_page()
        pdf_v.set_font("Arial", 'B', 15)
        pdf_v.cell(190, 50, "SIN PEDIDOS DE DOMICILIO", 0, 1, 'C')
        return bytes(pdf_v.output())

    prioridad_map = {
        "10:00 a 14:00": 1, "14:00 a 18:00": 2, "09:00 a 13:00": 3,
        "13:00 a 18:00": 4, "18:00 a 21:00": 5, "07:00 a 11:00": 6,
        "08:00 a 12:00": 7, "11:00 a 15:00": 8
    }

    df_logistica['Prioridad_L'] = df_logistica['BANDA HORARIA'].map(prioridad_map).fillna(99)
    df_logistica = df_logistica.sort_values('Prioridad_L')

    pdf = PDFLogistica(fecha_tit)

    # 🔥 ORDEN CORRECTO (CLAVE)
    pdf.mostrar_header = True
    pdf.add_page()  # Primera página con header
    pdf.mostrar_header = False  # Las siguientes SIN header

    # Configuración fija
    h_celda = 7
    f_size_datos = 9

    # Márgenes
    MARGEN_INFERIOR = 10
    LIMITE_Y = 297 - MARGEN_INFERIOR

    # Anchos
    w_num, w_pedido, w_mod, w_banda, w_dir = 10, 32, 25, 33, 90

    for banda in df_logistica['BANDA HORARIA'].unique():
        df_banda = df_logistica[df_logistica['BANDA HORARIA'] == banda].reset_index(drop=True)

        # Control antes del bloque
        if pdf.get_y() + (h_celda * 2) > LIMITE_Y:
            pdf.add_page()
            dibujar_encabezado(pdf, h_celda, f_size_datos, w_num, w_pedido, w_mod, w_banda, w_dir)

        # Zócalo azul SOLO inicio de banda
        pdf.set_fill_color(0, 70, 145)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font('Arial', 'B', f_size_datos + 2)
        pdf.cell(0, h_celda + 1, f"--- Domicilios | {banda} ---", 1, 1, 'C', True)

        # Encabezado gris
        dibujar_encabezado(pdf, h_celda, f_size_datos, w_num, w_pedido, w_mod, w_banda, w_dir)

        # Filas
        for i, row in df_banda.iterrows():

            # 🔴 CORTE DE PÁGINA LIMPIO
            if pdf.get_y() + h_celda > LIMITE_Y:
                pdf.add_page()

                # SOLO encabezado gris
                dibujar_encabezado(pdf, h_celda, f_size_datos, w_num, w_pedido, w_mod, w_banda, w_dir)

            fill = (i % 2 == 1)
            pdf.set_fill_color(245, 245, 245)

            pdf.set_font('Arial', '', f_size_datos)
            pdf.cell(w_num, h_celda, str(i + 1), 1, 0, 'C', fill)

            pdf.set_font('Arial', 'B', f_size_datos)
            pdf.cell(w_pedido, h_celda, str(row['NUMERO PEDIDO']).replace(".0", ""), 1, 0, 'C', fill)

            pdf.set_font('Arial', '', f_size_datos)
            valor_original = str(row['MODALIDAD DE ENTREGA'])
            pdf.cell(w_mod, h_celda, valor_original[:15], 1, 0, 'C', fill)

            pdf.cell(w_banda, h_celda, str(row['BANDA HORARIA']), 1, 0, 'C', fill)

            dir_texto = str(row['DIRECCIÓN'])[:65]
            x_actual = pdf.get_x()
            y_actual = pdf.get_y()
            pdf.cell(w_dir, h_celda, '', 1, 0, 'L', fill)  # dibuja el borde
            pdf.set_xy(x_actual + 3, y_actual)  # ← sangría de 2mm
            pdf.cell(w_dir - 3, h_celda, dir_texto, 0, 1, 'L')  # texto sin borde

        pdf.ln(2)

    return bytes(pdf.output())
