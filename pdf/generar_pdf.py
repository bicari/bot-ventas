from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet





def crear_Archivo(pedido: dict):
# Datos del pedido
    
    # Crear el PDF
    pdf_file = "pedido_cliente.pdf"

    doc = SimpleDocTemplate("invoice.pdf", pagesize=LETTER)

    styles = getSampleStyleSheet()
    elements = []
    # Encabezado
    elements.append(Paragraph("desta", styles['Title']))
    elements.append(Paragraph("[Street Address] [City, State, ZIP Code] [Phone] [Email] [Company Website]", styles['Normal']))
    elements.append(Spacer(1, 12))

    # Información de factura
    info_data = [
        ["BILL TO", "SHIP TO"],
        ["[Recipient Name]", "[Recipient Name]"],
        ["[Street Address]", "[Street Address]"],
        ["[City, State, ZIP Code]", "[City, State, ZIP Code]"],
        ["[Phone]", "[Phone]"]
    ]
    info_table = Table(info_data, colWidths=[270, 270])
    elements.append(info_table)
    elements.append(Spacer(1, 12))

    # Fechas y número de factura
    elements.append(Paragraph("Date: 01/01/1970 &nbsp;&nbsp;&nbsp; Invoice Nr: 00001 &nbsp;&nbsp;&nbsp; Due Date: 01/01/1970", styles['Normal']))
    elements.append(Spacer(1, 12))

    # Tabla de productos
    product_data = [
        ["DESCRIPTION", "PRICE", "QUANTITY", "TOTAL"],
        ["Mechanical Keyboard", "100", "3", "300"],
        ["USB-C Docking Station", "150", "1", "150"]
    ]
    product_table = Table(product_data, colWidths=[240, 100, 100, 100])
    product_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
    ]))
    elements.append(product_table)

    # Generar PDF
    doc.build(elements)

    # c = canvas.Canvas(pdf_file, pagesize=LETTER)
    # width, height = LETTER
    # print(width, height)
    # c.drawImage('geekodnaranja-04.png', x=10, y= height - 130 , width=200, height=150, mask='auto')
    
    # # Título
    # c.setFont("Helvetica-Bold", 16)
    # c.drawString(200, height - 50, "Pedido para Cliente")

    # # Información del cliente
    # c.setFont("Helvetica", 12)
    # c.drawString(50, height - 100, f"Cliente: {pedido['cliente']}")
    # c.drawString(50, height - 120, f"Comentario: {pedido['comentario']}")
    # c.drawString(50, height - 140, f"Precio aplicado: {pedido['precio']}")

    # # Tabla de productos
    # data = [["Código", "Cantidad"]]
    # for codigo, cantidad in pedido['productos'].items():
    #     data.append([codigo, cantidad])

    # # Crear tabla
    # table = Table(data, colWidths=[200, 100])
    # table.setStyle(TableStyle([
    #     ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
    #     ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
    #     ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    #     ('GRID', (0, 0), (-1, -1), 1, colors.black),
    #     ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    # ]))

    # # Posición de la tabla
    # table.wrapOn(c, width, height)
    # table.drawOn(c, 50, height - 300)

    # # Guardar PDF
    # c.save()

if __name__ == '__main__':
    crear_Archivo({'productos': {'01010001': '5', '01010002': '12', '01010003': '13', '01010004': '19', '01010005': '25'}, 'cliente': 'J507053180', 'comentario': 'COMPRA PARA EL CLIENTE DE TINAQUILLO', 'precio': 'P1'})