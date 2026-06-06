import pandas as pd
from fpdf import FPDF
import os

class FaltantesPDF(FPDF):
    def __init__(self, fecha_tit):
        super().__init__(orientation='P', unit='mm', format='A4')
        self.fecha_tit = fecha_tit
        self.set_margins(left=7, top=10, right=7)
        self.set_auto_page_break(auto=True, margin=15)

    def header(self):
        if os.path.exists('carrefour+logo.png'):
            self.image('carrefour+logo.png', x=7, y=8, w=45)
        self.set_font("Times", 'B', 11)
        self.set_xy(110, 10)
        self.multi_cell(90, 5, f"Planilla control de Faltantes\nEntrega del día: {self.fecha_tit}\nTienda: [268]", align='R')
        self.ln(6)
        self.set_fill_color(240, 240, 240)
        self.set_font("Times", 'B', 9)
        cols = ["Nro PEDIDO", "MODALIDAD", "BANDA HORARIA", "ESTADO", "PICKEADOR ENCARGADO"]
        widths = [28, 25, 35, 53, 55]
        for i, col in enumerate(cols):
            self.cell(widths[i], 8, col, border=1, fill=True, align='C')
        self.ln()

def generar_pdf_faltantes(df, fecha_tit):
    estados_validos = ["CONTROLADO CON FALTANTE", "PICKING EN PROCESO"]
    df_faltantes = df[df['ESTADO'].str.upper().str.contains('|'.join(estados_validos), na=False)].copy()

    pdf = FaltantesPDF(fecha_tit)
    pdf.add_page()

    if df_faltantes.empty:
        pdf.set_font("Times", 'B', 14)
        pdf.set_text_color(255, 0, 0)
        pdf.cell(196, 20, "NO SE DETECTARON PEDIDOS CON FALTANTES", border=1, align='C')
        return bytes(pdf.output())

    widths = [28, 25, 35, 53, 55]
    ultima_llave = None

    for _, r in df_faltantes.iterrows():
        llave = str(r['BANDA HORARIA'])
        if llave != ultima_llave:
            pdf.set_fill_color(64, 64, 64)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Times", 'B', 11)
            pdf.cell(sum(widths), 7, f"--- {llave} ---", border=1, ln=True, align='C', fill=True)
            pdf.set_text_color(0, 0, 0)
            ultima_llave = llave

        estado_texto = str(r['ESTADO']).capitalize()

        # --- LÓGICA DE SOMBREADO PARA IMPRESIÓN B/N ---
        if "PROCESO" in estado_texto.upper():
            pdf.set_fill_color(225, 225, 225) # Gris medio/claro
            pdf.set_font("Times", 'B', 10)     # Tu ajuste de tamaño 10 + Negrita
            pinto_celda = True
        else:
            pdf.set_fill_color(255, 255, 255) # Blanco
            pdf.set_font("Times", '', 10)      # Tu ajuste de tamaño 10 normal
            pinto_celda = False

        pdf.set_text_color(0, 0, 0) # Siempre negro para máxima legibilidad

        pdf.cell(widths[0], 7, str(r['NUMERO PEDIDO']).replace(".0",""), border=1, align='C', fill=pinto_celda)
        pdf.cell(widths[1], 7, str(r['MODALIDAD DE ENTREGA'])[:15], border=1, align='C', fill=pinto_celda)
        pdf.cell(widths[2], 7, str(r['BANDA HORARIA']), border=1, align='C', fill=pinto_celda)
        pdf.cell(widths[3], 7, estado_texto[:32], border=1, align='L', fill=pinto_celda)
        pdf.cell(widths[4], 7, "", border=1, fill=pinto_celda)
        pdf.ln()

    # Nota Final con tu tamaño 12
    pdf.ln(5)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Times", 'B', 12)
    nota = ("AVISO IMPORTANTE: Los pedidos resaltados en gris deben ser verificados en el CDP. "
            "Confirme si presentan faltantes reales o si están siendo pickeados actualmente por un colaborador.")
    pdf.multi_cell(sum(widths), 5, nota, border=0, align='L')

    return bytes(pdf.output())
