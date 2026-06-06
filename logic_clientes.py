import pandas as pd
import re
from datetime import datetime, timedelta
from fpdf import FPDF
import os


def motor_limpieza(df):

    df.columns = [str(c).strip() for c in df.columns]

    fecha_raw = df['FECHA ENTREGA'].iloc[0] if 'FECHA ENTREGA' in df.columns else "S/D"

    try:
        f_dt = pd.to_datetime(fecha_raw)
        fecha_tit_str = f_dt.strftime('%d/%m/%Y')
    except:
        fecha_tit_str = str(fecha_raw)

    def formatear_direccion_pro(row):

        calle = str(row.get('CALLE', '')).strip().title()

        dicc = {
            "Avenida": "Av.",
            "Boulevard": "Bv.",
            "Cortada": "Cda.",
            "Diagonal": "Diag.",
            "Pasaje": "Pje.",
            "Entre Rios": "E. Ríos",
            "Sargento": "Sgto.",
            "General": "Gral.",
            "Doctor": "Dr.",
            "Presidente": "Pres.",
            "Republica": "Rep.",
            "Batalla": "Bat.",
            "Manuel Belgrano": "M. Belgrano",
            "Carlos Pellegrini": "C. Pellegrini",
            "Jorge Newbery": "J. Newbery",
            "Juan Jose Paso": "J.J. Paso",
            "Juan Manuel De Rosas": "J.M. de Rosas",
            "Martin Rodriguez": "M. Rodriguez",
            "Ovidio": "Ov."
        }

        for k, v in dicc.items():
            calle = calle.replace(k, v)

        calle = re.sub(r'Pellegrini|Pelegrini', 'Pellegrini', calle, flags=re.IGNORECASE)

        nro = str(row.get('NUMERO', '')).strip()

        nro_str = f" {nro}" if nro.lower() != 'nan' and nro != '' else ""

        depto_raw = str(row.get('DEPTO', '')).upper().strip()

        excluir = ["DR", "NAN", "@ SC @ NRO @ DPTO", "@ SC", "@ NRO", "@ DPTO"]

        corchete = ""

        if depto_raw and not any(x == depto_raw for x in excluir):

            if any(pb in depto_raw for pb in ["PLANTA BAJA", "P.B", "P/B", "PB"]):

                corchete = " [P/B]"

            elif any(pa in depto_raw for pa in ["PLANTA ALTA", "P.ALTA", "P.A", "PLANTA.A", "PA"]):

                corchete = " [P/A]"

            else:

                piso_match = re.search(r'(?:PISO|P|PSO|P\.)\s*(\d+)', depto_raw)

                dpto_match = re.search(r'(?:DEPTO|DEPARTAMENTO|DPTO|DPT|D\.|D)\s*([A-Z0-9]+)', depto_raw)

                piso = piso_match.group(1) if piso_match else ""
                dpto = dpto_match.group(1) if dpto_match else ""

                if not piso and not dpto:

                    partes = re.findall(r'([A-Z0-9]+)', depto_raw)

                    if len(partes) >= 2:
                        piso = partes[0]
                        dpto = partes[1]

                    elif len(partes) == 1:
                        dpto = partes[0]

                if piso and dpto:

                    corchete = f" [{piso} - {dpto}]" if piso != dpto else f" [{piso}]"

                elif piso:

                    corchete = f" [{piso}]"

                elif dpto:

                    corchete = f" [{dpto}]"

        return f"{calle}{nro_str}{corchete}".strip()

    df['DIRECCIÓN'] = df.apply(formatear_direccion_pro, axis=1)

    df['CLIENTE'] = (
        df['NOMBRE CLIENTE']
        .fillna("")
        .astype(str)
        .str.title()
        .str.strip()
    )

    mapping = {
        "Domicilio | 10:00 a 14:00": 1,
        "Domicilio | 14:00 a 18:00": 2,
        "Domicilio | 18:00 a 21:00": 3,
        "Drive | 10:00 a 14:00": 4,
        "Sucursal | 10:00 a 14:00": 5,
        "Drive | 14:00 a 18:00": 6,
        "Sucursal | 14:00 a 18:00": 7,
        "Drive | 18:00 a 21:00": 8,
        "Sucursal | 18:00 a 21:00": 9
    }

    df['Prioridad'] = df.apply(
        lambda r: mapping.get(
            f"{r['MODALIDAD DE ENTREGA']} | {r['BANDA HORARIA']}",
            99
        ),
        axis=1
    )

    df.attrs['fecha_tit_str'] = fecha_tit_str

    return df.sort_values('Prioridad'), fecha_tit_str


class PlanillaPDF(FPDF):

    def __init__(self, fecha_tit):

        super().__init__(orientation='P', unit='mm', format='A4')

        self.fecha_tit = fecha_tit

        self.set_margins(left=7, top=10, right=7)

        self.set_auto_page_break(auto=True, margin=8)

    def header(self):

        if self.page_no() == 1:

            if os.path.exists('carrefour+logo.png'):
                self.image('carrefour+logo.png', x=7, y=8, w=55)

            self.set_font("Times", 'B', 11)

            self.set_xy(100, 10)

            self.multi_cell(
                100,
                5,
                f"Planilla operativa de Pedidos\nEntrega del día: {self.fecha_tit}\nTienda: [268]",
                align='R'
            )

            self.ln(6)

        self.set_fill_color(240, 240, 240)

        self.set_font("Times", 'B', 9)

        cols = [
            "Nro PEDIDO",
            "MODALIDAD",
            "BANDA HORARIA",
            "CLIENTE",
            "DIRECCIÓN",
            "TELÉFONO"
        ]

        widths = [28, 20, 32, 44, 47, 25]

        for i, col in enumerate(cols):
            self.cell(widths[i], 7.5, col, border=1, fill=True, align='C')

        self.ln()


def generar_pdf_clientes(df):

    fecha_tit = df.attrs.get('fecha_tit_str', '')

    def limpiar_texto_pdf(texto):

        try:
            return str(texto).encode('latin-1', 'replace').decode('latin-1')
        except:
            return str(texto)

    font_size = 9
    row_height = 5.5

    pdf = PlanillaPDF(fecha_tit)

    pdf.add_page()

    widths = [28, 20, 32, 44, 47, 25]

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
            limpiar_texto_pdf(str(banda)[:18]),
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
            limpiar_texto_pdf(str(row['DIRECCIÓN'])[:31]),
            border=1
        )

        pdf.cell(
            widths[5],
            row_height,
            limpiar_texto_pdf(str(row['TEL. PARTICULAR'])[:13]),
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

    return bytes(pdf.output())
