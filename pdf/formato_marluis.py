from reportlab.lib.pagesizes import LETTER
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepInFrame
)
from io import BytesIO
from datetime import datetime

def generar(filename, pedido: dict, logo_path='pdf/marluis.png', preliminar: bool = False):
    buffer = BytesIO()
    if preliminar:
        doc = SimpleDocTemplate(buffer, pagesize=LETTER, leftMargin=30,   # en puntos (72 = 1 pulgada)
            rightMargin=30,
            topMargin=10,
            bottomMargin=10)
    else:
        doc = SimpleDocTemplate(filename, pagesize=LETTER, leftMargin=30,   # en puntos (72 = 1 pulgada)
            rightMargin=30,
            topMargin=10,
            bottomMargin=10)
    elements = []

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Center", alignment=1, fontSize=14, spaceAfter=8))
    styles.add(ParagraphStyle(name="Conditions", fontSize=9, leading=12, spaceBefore=20))

    # ---- Encabezado con logo + datos empresa ----
    logo = None
    if logo_path:
        logo = Image(logo_path, width=150, height=80)  # Tamaño variable
        logo.hAlign = "LEFT"



    empresa_info = [
        Paragraph("Tel: +57 123 456 789", styles["Normal"]),
        Paragraph("Email: info@empresa.com", styles["Normal"]),
        Paragraph(f"Vendedor: {pedido['nombre_vendedor']}", styles["Normal"]),
    ]
    nro_pedido = str(pedido['id']).rjust(7,'0')
    factura_datos = [Paragraph(f"<b>Pedido #{nro_pedido}</b>", styles["Heading1"]),
                    Paragraph(f"Fecha emisión: {datetime.now().strftime('%d-%m-%Y')}", styles["Normal"]),
                    Paragraph(f"Hora: {datetime.now().strftime('%H:%M')}")
    #Paragraph("Vencimiento: 10/09/2025", styles["Normal"])
    ]


    encabezado_data = [[logo, factura_datos]] if logo else [["", empresa_info]]
    tabla_encabezado = Table(encabezado_data, colWidths=[350,200])
    tabla_encabezado.setStyle(TableStyle([
        ("ALIGN", (0,0), (0, 0), "LEFT"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("ALIGN", (1,0), (1, 0), "RIGHT"),
        ("TOPPADDING", (0,0), (-1,-1), 0),
        #("ALIGN", (2,0), (2, 0), "RIGHT")
    ]))
    elements.append(tabla_encabezado)
    elements.append(Spacer(1, 10))
    empresa_info_table = Table([empresa_info])
    empresa_info_table.setStyle([("ALIGN", (0,0), (0, 0), "LEFT")])
    elements.append(empresa_info_table)

    # ---- Info factura ----
    # elements.append(Paragraph("<b>Factura #00001</b>", styles["Heading2"]))
    # elements.append(Paragraph("Fecha: 02/09/2025", styles["Normal"]))
    # elements.append(Paragraph("Vencimiento: 10/09/2025", styles["Normal"]))
    # elements.append(Spacer(1, 20))

    # ---- Bill To / Ship To ----
    data_clientes = [
        ["Cliente/Rif", "Dirección", "Comentario"],
        [Paragraph(pedido['descripcion_cliente']), Paragraph(pedido['direccion_cliente']), Paragraph(pedido['comentario'])],
        [Paragraph(pedido['cliente'])],
    ]
    tabla_clientes = Table(data_clientes, colWidths=[150, 270, 150])
    tabla_clientes.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ("TEXTCOLOR", (0,0), (-1,0), colors.black),
        ("ALIGN", (0,0), (-1,-1), "LEFT"),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0,0), (-1,0), 8)
    ]))
    elements.append(tabla_clientes)
    elements.append(Spacer(1, 20))

    # ---- Tabla de productos (ajustable en varias páginas) ----
    data_items = [["Código","Descripción", "Precio", "Cantidad", "Total", "Dcto", "Importe"]]

    for codigo in pedido["productos"].keys():
        data_items.append([codigo,
                           Paragraph(pedido["productos"][codigo]["descripcion"]),
                           f'{pedido["productos"][codigo]["precio_sin_iva"]:.2f}',
                           f'{pedido["productos"][codigo]["cantidad"]:.2f}',
                           f'{pedido["productos"][codigo]["total_sin_dcto"]:.2f}',
                           f'{pedido["productos"][codigo]["descuento"]:.2f}%',
                           f'{pedido["productos"][codigo]["subtotal"]:.2f}'])

    tabla_items = Table(data_items, colWidths=[80, 250, 50, 50, 50, 50, 50], repeatRows=1)  # repeatRows mantiene encabezado
    estilos_tabla = [
            ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
            ("TEXTCOLOR", (0,0), (-1,0), colors.black),
            ("ALIGN", (0,0), (-1,-1), "LEFT"),     # Código y Descripción
            ("ALIGN", (5,1), (-1,-1), "RIGHT"),
            ("ALIGN", (5,0), (-1,-1), "RIGHT"),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            #("GRID", (0,0), (-1,-1), 0.5, colors.grey),
            #Encabezado
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,0),  10),
            #Filas
            ("FONTNAME", (0,1), (-1,-1), "Helvetica"),
            ("FONTSIZE", (0,1), (-1,-1),  8.5),
            #Paddin o separacion de texto
            ("LEFTPADDING", (0,0), (-1,-1), 5),
            ("RIGHTPADDING", (0,0), (-1,-1), 5)

        ]
    tabla_items.setStyle(TableStyle(estilos_tabla))
    elements.append(tabla_items)
    elements.append(Spacer(1, 20))
    #print(data_items)
    # ---- Footer con desglose de impuestos por base ----
    peso_total = pedido['peso_total']
    filas_total = []
    if pedido.get('base_16', 0) > 0:
        filas_total.append(["", "", "Base 16%:", f"{pedido['base_16']:.2f}"])
        filas_total.append(["", "", "IVA 16%:", f"{pedido.get('iva_16', 0.0):.2f}"])
    if pedido.get('base_8', 0) > 0:
        filas_total.append(["", "", "Base 8%:", f"{pedido['base_8']:.2f}"])
        filas_total.append(["", "", "IVA 8%:", f"{pedido.get('iva_8', 0.0):.2f}"])
    if pedido.get('exento', 0) > 0:
        filas_total.append(["", "", "Exento:", f"{pedido['exento']:.2f}"])
    filas_total.append(["", "", "TOTAL NETO:", f"{pedido.get('total_neto', pedido.get('total_bruto', 0.0)):.2f}"])
    filas_total.append(["", "", "PESO:", f"{peso_total:.2f} Kg"])
    n = len(filas_total)
    tabla_total = Table(filas_total, colWidths=[80, 300, 80, 80])
    tabla_total.setStyle(TableStyle([
        ("TEXTCOLOR", (2, 0), (3, n - 1), colors.black),
        ("BACKGROUND", (2, 0), (3, n - 1), colors.lightgrey),
        ("ALIGN", (2, 0), (3, n - 1), "CENTER"),
        ("FONTNAME", (2, 0), (3, n - 1), "Helvetica-Bold"),
        ("GRID", (2, 0), (3, n - 1), 0.5, colors.grey),
    ]))
    elements.append(tabla_total)

    # ---- Sección de condiciones ----
    conditions_text = """
    <b>Condiciones:</b><br/>
    - El pago debe realizarse en un plazo máximo de 10 días.<br/>
    - No se aceptan devoluciones pasados 5 días hábiles.<br/>
    - Contacte a soporte@empresa.com para más información.
    """
    elements.append(Paragraph(conditions_text, styles["Conditions"]))

    # ---- Construir PDF ----
    doc.build(elements)
    if preliminar:
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes
