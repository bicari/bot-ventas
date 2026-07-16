from reportlab.lib.pagesizes import LETTER
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
)
from io import BytesIO
from datetime import datetime

# Identidad de la empresa para este formato (un formato = una empresa)
EMPRESA_NOMBRE = "PROCESADORA ECOGRASAS, C.A."
EMPRESA_DIRECCION = ("Calle 4, Parcela No. C, Zona Industrial Municipal Etapa I, "
                     "Tinaquillo Edo. Cojedes Teléfonos: (0258) 766.3191 - 766.5627")
EMPRESA_RIF = "J-29801313-3"
EMPRESA_EMAILS = "ventas@ecograsas.com  info@ecograsas.com"
LOGO_ECOGRASAS = None  # placeholder de texto hasta tener el archivo del logo


def _money(valor, dec=2):
    """Formato europeo: 1.426,00 (miles con punto, decimales con coma)."""
    s = f"{valor:,.{dec}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def generar(filename, pedido: dict, logo_path=None, preliminar: bool = False):
    buffer = BytesIO()
    destino = buffer if preliminar else filename
    doc = SimpleDocTemplate(
        destino, pagesize=LETTER,
        leftMargin=30, rightMargin=30, topMargin=15, bottomMargin=15,
    )
    elements = []
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="EmpresaNombre", fontName="Helvetica-Bold", fontSize=16, leading=18))
    styles.add(ParagraphStyle(name="EmpresaSmall", fontName="Helvetica", fontSize=7, leading=8))
    styles.add(ParagraphStyle(name="TituloDoc", fontName="Helvetica-Bold", fontSize=18, alignment=2))
    styles.add(ParagraphStyle(name="SubTituloDoc", fontName="Helvetica-Bold", fontSize=13, alignment=2))
    styles.add(ParagraphStyle(name="DerNormal", fontName="Helvetica", fontSize=9, alignment=2))
    styles.add(ParagraphStyle(name="Etiqueta", fontName="Helvetica-Bold", fontSize=8, leading=10))
    styles.add(ParagraphStyle(name="Valor", fontName="Helvetica", fontSize=8, leading=10))
    styles.add(ParagraphStyle(name="ValorSmall", fontName="Helvetica", fontSize=7, leading=8))

    # ---- Encabezado: empresa (izq) + datos del documento (der) ----
    logo = Image(LOGO_ECOGRASAS, width=70, height=55) if LOGO_ECOGRASAS else Paragraph("PE", styles["EmpresaNombre"])
    empresa_col = [
        Paragraph(EMPRESA_NOMBRE, styles["EmpresaNombre"]),
        Paragraph(EMPRESA_DIRECCION, styles["EmpresaSmall"]),
        Paragraph(f"R.I.F. {EMPRESA_RIF}", styles["EmpresaSmall"]),
        Spacer(1, 3),
        Paragraph(f"<b>e-mail:</b> {EMPRESA_EMAILS}", styles["EmpresaSmall"]),
    ]
    empresa_tbl = Table([[logo, empresa_col]], colWidths=[75, 285])
    empresa_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))
    nro = str(pedido.get("id", "")).rjust(8, "0")
    doc_col = [
        Paragraph("PEDIDO", styles["TituloDoc"]),
        Spacer(1, 4),
        Paragraph(f"# {nro}", styles["SubTituloDoc"]),
        Spacer(1, 6),
        Paragraph(f"Fecha de Emision: {datetime.now().strftime('%d/%m/%Y')}", styles["DerNormal"]),
        Paragraph("Fecha Límite Entrega : ", styles["DerNormal"]),
    ]
    encabezado = Table([[empresa_tbl, doc_col]], colWidths=[365, 190])
    encabezado.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    elements.append(encabezado)
    elements.append(Spacer(1, 10))

    # ---- Bloque cliente (sin Documento Origen / Condición de Pago / Condición de Venta) ----
    cliente_data = [
        [Paragraph("Cliente:", styles["Etiqueta"]), Paragraph(pedido.get("descripcion_cliente", ""), styles["Valor"]),
         Paragraph("Dirección<br/>Despacho:", styles["Etiqueta"]), Paragraph("", styles["Valor"])],
        [Paragraph("Direccion<br/>Fiscal:", styles["Etiqueta"]), Paragraph(pedido.get("direccion_cliente", ""), styles["ValorSmall"]),
         Paragraph("", styles["Valor"]), Paragraph("", styles["Valor"])],
        [Paragraph("RIF:", styles["Etiqueta"]), Paragraph(pedido.get("cliente", ""), styles["Valor"]),
         Paragraph("Teléfono :", styles["Etiqueta"]), Paragraph("", styles["Valor"])],
        [Paragraph("Vendedor :", styles["Etiqueta"]), Paragraph(pedido.get("nombre_vendedor", ""), styles["Valor"]),
         Paragraph("", styles["Valor"]), Paragraph("", styles["Valor"])],
    ]
    cliente_tbl = Table(cliente_data, colWidths=[70, 210, 70, 205])
    cliente_tbl.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.black),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    elements.append(cliente_tbl)
    elements.append(Spacer(1, 10))

    # ---- Tabla de ítems (sin No. Lote / F.Vcmto Lote) ----
    data_items = [["Cód.", "Descripción", "Cant.", "Precio Unit.", "Total"]]
    for codigo, det in pedido["productos"].items():
        data_items.append([
            codigo,
            Paragraph(det.get("descripcion", ""), styles["Valor"]),
            _money(det.get("cantidad", 0)),
            _money(det.get("precio_sin_iva", 0)),
            _money(det.get("total_sin_dcto", 0)),
        ])
    items_tbl = Table(data_items, colWidths=[85, 275, 55, 70, 70], repeatRows=1)
    items_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black),
        ("TOPPADDING", (0, 1), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 1),
    ]))
    elements.append(items_tbl)
    elements.append(Spacer(1, 15))

    # ---- Pie de totales en 3 columnas (sin Convenio Transporte / Prepago) ----
    prods = pedido["productos"].values()
    sub_total = round(sum(p.get("total_sin_dcto", 0) for p in prods), 2)
    total_descuentos = round(sub_total - pedido.get("total_bruto", 0), 2)

    col_izq = [
        ["SUB Total", _money(sub_total)],
        ["Total Descuentos :", _money(total_descuentos, 4)],
        ["Total Bruto", _money(pedido.get("total_bruto", 0))],
    ]
    col_centro = [
        ["Total Exento $.", _money(pedido.get("exento", 0), 4)],
        ["Base Imponible 16,00 %", _money(pedido.get("base_16", 0))],
        ["I.V.A. 16,00 %", _money(pedido.get("iva_16", 0))],
        ["Base Imponible 8,00 %", _money(pedido.get("base_8", 0))],
        ["I.V.A. 8,00 %", _money(pedido.get("iva_8", 0))],
    ]
    izq_tbl = Table(col_izq, colWidths=[110, 80])
    izq_tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 2), (0, 2), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, 0), "Helvetica-Bold"),
        ("FONTNAME", (1, 2), (1, 2), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
    ]))
    centro_tbl = Table(col_centro, colWidths=[110, 80])
    centro_tbl.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
    ]))
    total_box = Table([[Paragraph("Total Pedido $.", styles["Etiqueta"])],
                       [Paragraph(_money(pedido.get("total_neto", 0)), styles["TituloDoc"])]],
                      colWidths=[150])
    total_box.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.black),
        ("BACKGROUND", (0, 0), (-1, -1), colors.lightgrey),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    pie = Table([[izq_tbl, centro_tbl, total_box]], colWidths=[195, 195, 165])
    pie.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    elements.append(pie)
    elements.append(Spacer(1, 10))

    # ---- Observaciones (comentario) + firma ----
    obs = pedido.get("comentario", "") or ""
    obs_html = obs.replace("\n", "<br/>")
    observaciones = Table([[
        Paragraph(f"<b>Observaciones :</b><br/>{obs_html}", styles["ValorSmall"]),
        Paragraph(f"<i>Elaborado por: {pedido.get('nombre_vendedor', '')}</i>", styles["ValorSmall"]),
    ]], colWidths=[380, 175])
    observaciones.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
    ]))
    elements.append(observaciones)

    doc.build(elements)
    if preliminar:
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes
