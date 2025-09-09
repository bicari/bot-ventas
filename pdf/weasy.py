from reportlab.lib.pagesizes import LETTER
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
)

def generar_factura(filename, items: dict, logo_path=None):
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
    ]
    factura_datos = [Paragraph("<b>Factura #00001</b>", styles["Heading2"]),
    Paragraph("Fecha: 02/09/2025", styles["Normal"]),
    Paragraph("Vencimiento: 10/09/2025", styles["Normal"])

    ]

    encabezado_data = [[logo, factura_datos]] if logo else [["", empresa_info]]
    tabla_encabezado = Table(encabezado_data, colWidths=[350,200])
    tabla_encabezado.setStyle(TableStyle([
        ("ALIGN", (0,0), (0, 0), "LEFT"),
        ("ALIGN", (1,0), (1, 0), "RIGHT"),
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
        ["Cliente/Rif", "Dirección"],
        [Paragraph("Carlos Aranguren"), Paragraph("Av 101 Diaz Moreno, Edif Oficentro 108, Piso 2 OF-2A, Valencia Carabobo")],
        ["V25635859", "Av. 456, Medellín"],
    ]
    tabla_clientes = Table(data_clientes, colWidths=[150, 410])
    tabla_clientes.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ("TEXTCOLOR", (0,0), (-1,0), colors.black),
        ("ALIGN", (0,0), (-1,-1), "LEFT"),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0,0), (-1,0), 8),
    ]))
    elements.append(tabla_clientes)
    elements.append(Spacer(1, 20))

    # ---- Tabla de productos (ajustable en varias páginas) ----
    data_items = [["Código","Descripción", "Precio", "Cantidad", "Total"]] 
    
    for codigo, cantidad in pedido["productos"].items():
        precio_unitario = 10.0  # <- reemplaza con búsqueda en DB si lo tienes
        subtotal = precio_unitario * int(cantidad)
        data_items.append([codigo, "Producto generico", f"{precio_unitario:.2f}", cantidad, f"{subtotal:.2f}"])

    tabla_items = Table(data_items, colWidths=[80, 250, 80, 80, 80], repeatRows=1)  # repeatRows mantiene encabezado
    tabla_items.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ("TEXTCOLOR", (0,0), (-1,0), colors.black),
        ("ALIGN", (1,1), (-1,-1), "CENTER"),
        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
    ]))
    elements.append(tabla_items)
    elements.append(Spacer(1, 20))
    print(data_items)
    # ---- Footer con total ----
    total_value = sum(10.0 * int(cant) for cant in pedido["productos"].values())
    total = [["", "", "TOTAL:", f"{total_value:.2f}"]]
    tabla_total = Table(total, colWidths=[80, 300, 80, 80, 80])
    tabla_total.setStyle(TableStyle([
        ("TEXTCOLOR", (2,0), (2,0), colors.black),
        ("BACKGROUND", (2,0), (3,0), colors.lightgrey),
        ("ALIGN", (2,0), (3,0), "CENTER"),
        ("FONTNAME", (2,0), (3,0), "Helvetica-Bold"),
        ("GRID", (2,0), (3,0), 0.5, colors.grey),
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

# Datos de prueba
# items = [
#     ["Mechanical Keyboard", "100", "3", "300"],
#     ["USB-C Docking Station", "150", "1", "150"],
# ] + [["Producto Extra", "50", "2", "100"]] * 30  # simular lista larga
pedido = {'productos': {'01010001': '5', '01010002': '12', '01010003': '13', '01010004': '19', '01010005': '25'}, 'cliente': 'J507053180', 'comentario': 'COMPRA PARA EL CLIENTE DE TINAQUILLO', 'precio': 'P1'}

#generar_factura("factura_reportlab_logo.pdf", pedido, logo_path="geekodnaranja-04.png")
