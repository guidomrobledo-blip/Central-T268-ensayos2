from fpdf import FPDF
from datetime import datetime, timedelta
import os

from logic_clientes import motor_limpieza


class PlanillaPDFSeguridad(FPDF):

    def __init__(self, fecha_tit):

        super().__init__(orientation='P', unit='mm', format='A4')

        self.fecha_tit = fecha_tit

        self.set_margins(left=7, top=10, right=7)

        self.set_auto_page_break(auto=True, margin=8)

    def header(self):

        if self.page_no() == 1:

            if os.path.exists('carrefour+logo.png'):
                self.image('carrefour+logo.png', x=7, y=8, w=55)

            if os.path.exists('checklist_seguridad.png'):
                self.set_xy(85, 4)
                self.image('checklist_seguridad.png', w=26)

            self.set_font("Times", 'B', 11)

            self.set_xy(100, 10)

            self.multi_cell(
                100,
                5,
                f"Auditoría de Seguridad: Pedidos Online\nEntrega del día: {self.fecha_tit}\nTienda: [268]",
                align='R'
            )

            self.ln(6)

        self.set_fill_color(240, 240, 240)

        self.set_font("Times", 'B', 9)

        cols = [
            "Nro PEDIDO",
            "MODALIDAD",
            "BANDA",
            "CLIENTE",
            "DIRECCIÓN",
            "PICKEADOR",
            "Art."
        ]

        widths = [27, 20, 21, 44, 44, 28, 12]

        for i, col in enumerate(cols):
            self.cell(widths[i], 7.5, col, border=1, fill=True, align='C')

        self.ln()


def generar_pdf_seguridad(df, fecha_tit):

    def limpiar_texto_pdf(texto):

        try:
            return str(texto).encode('latin-1', 'replace').decode('latin-1')
        except:
            return str(texto)

    font_size = 9.5

    row_height = 5

    while font_size > 6.5:

        pdf = PlanillaPDFSeguridad(fecha_tit)

        pdf.add_page()

        widths = [27, 20, 21, 44, 44, 28, 12]

        ultima_llave = None

        resumen = {}

        df_render = df.copy()

        orden_final = {
            "Domicilio | 10:00 a 14:00": 1,
            "Domicilio | 14:00 a 18:00": 2,
            "Domicilio | 18:00 a 21:00": 3,
            "Drive/Sucursal | 10:00 a 14:00": 4,
            "Drive/Sucursal | 14:00 a 18:00": 5,
            "Drive/Sucursal | 18:00 a 21:00": 6
        }

        def obtener_llave(row):

            if row['MODALIDAD DE ENTREGA'] == "Domicilio":
                return f"Domicilio | {row['BANDA HORARIA']}"

            return f"Drive/Sucursal | {row['BANDA HORARIA']}"

        df_render['llave_grupo'] = df_render.apply(obtener_llave, axis=1)

        df_render['orden_final'] = df_render['llave_grupo'].map(orden_final)

        df_render = df_render.sort_values(
            by=['orden_final', 'Prioridad']
        )

        def insertar_filas_vacias(cantidad=3):

            for _ in range(cantidad):

                if (pdf.h - pdf.get_y()) < 20:
                    pdf.add_page()

                for w in widths:
                    pdf.cell(w, row_height, "", border=1)

                pdf.ln()

        grupos_con_espacio = [
            "Domicilio | 10:00 a 14:00",
            "Domicilio | 14:00 a 18:00",
            "Domicilio | 18:00 a 21:00",
            "Drive/Sucursal | 18:00 a 21:00"
        ]

        for _, row in df_render.iterrows():

            modalidad = row['MODALIDAD DE ENTREGA']

            banda = row['BANDA HORARIA']

            llave = row['llave_grupo']

            if llave != ultima_llave:

                if ultima_llave in grupos_con_espacio:
                    insertar_filas_vacias(2)

            if (pdf.h - pdf.get_y()) < (row_height + 3):
                pdf.add_page()

            resumen[llave] = resumen.get(llave, 0) + 1

            if llave != ultima_llave:

                pdf.set_fill_color(64, 64, 64)

                pdf.set_text_color(255, 255, 255)

                pdf.set_font("Times", 'B', font_size + 2)

                pdf.cell(
                    sum(widths),
                    row_height + 1.5,
                    limpiar_texto_pdf(f"--- {llave} ---"),
                    border=1,
                    ln=True,
                    align='C',
                    fill=True
                )

                pdf.set_text_color(0, 0, 0)

                pdf.set_font("Times", '', font_size)

                ultima_llave = llave

            pdf.cell(
                widths[0],
                row_height,
                limpiar_texto_pdf(str(row['NUMERO PEDIDO']).replace(".0", "")),
                border=1,
                align='C'
            )

            pdf.cell(
                widths[1],
                row_height,
                limpiar_texto_pdf(str(modalidad)[:10]),
                border=1
            )

            pdf.cell(
                widths[2],
                row_height,
                limpiar_texto_pdf(str(banda)[:15]),
                border=1
            )

            pdf.cell(
                widths[3],
                row_height,
                limpiar_texto_pdf(str(row['CLIENTE'])[:28]),
                border=1
            )

            pdf.cell(
                widths[4],
                row_height,
                limpiar_texto_pdf(str(row['DIRECCIÓN'])[:30]),
                border=1
            )

            pdf.cell(
                widths[5],
                row_height,
                "",
                border=1
            )

            pdf.cell(
                widths[6],
                row_height,
                "",
                border=1
            )

            pdf.ln()

        if ultima_llave in grupos_con_espacio:
            insertar_filas_vacias(2)

        if (pdf.h - pdf.get_y()) < 35:
            pdf.add_page()

        pdf.ln(4)

        hora_arg = (datetime.utcnow() - timedelta(hours=3)).strftime("%H:%M")

        pdf.set_font("Times", 'B', font_size + 1.5)

        pdf.cell(
            0,
            6,
            limpiar_texto_pdf(f"Informe de pedidos al momento [{hora_arg} hs]"),
            ln=True,
            align='R'
        )

        pdf.set_font("Times", '', font_size + 0.5)

        orden_resumen = [
            "Domicilio | 10:00 a 14:00",
            "Domicilio | 14:00 a 18:00",
            "Domicilio | 18:00 a 21:00",
            "Drive/Sucursal | 10:00 a 14:00",
            "Drive/Sucursal | 14:00 a 18:00",
            "Drive/Sucursal | 18:00 a 21:00"
        ]

        for clave in orden_resumen:

            if clave in resumen:

                pdf.cell(
                    0,
                    4.5,
                    limpiar_texto_pdf(f"{clave}: [{resumen[clave]}]"),
                    ln=True,
                    align='R'
                )

        pdf.set_font("Times", 'B', font_size + 2)

        pdf.cell(
            0,
            8,
            limpiar_texto_pdf(f"TOTAL: [{len(df)}]"),
            ln=True,
            align='R'
        )

        y_firma = pdf.get_y() - 35

        pdf.set_xy(8, y_firma)

        pdf.set_font("Arial", "", 10)

        pdf.cell(0, 8, "Responsable del control:", 0, 1)

        pdf.set_x(8)

        pdf.cell(0, 10, "Firma: __________________________", 0, 1)

        pdf.set_x(8)

        pdf.cell(0, 8, "Nombre: _________________________", 0, 1)

        if pdf.page_no() <= 2:
            break

        font_size -= 0.5

        row_height -= 0.3

    return bytes(pdf.output())
