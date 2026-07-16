# Dos formatos de impresión PDF + fix de comentario — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir elegir el formato de impresión del pedido por variable de entorno (Marluis o ECOGRASAS) y corregir que el comentario del pedido no llega al PDF ni al sistema a2.

**Architecture:** Registro de generadores PDF (Opción 1 del spec): cada formato es un módulo con la firma común `generar(filename, pedido, logo_path=None, preliminar=False)`. Una factory lee `FORMATO_PDF` y devuelve el generador. El fix del comentario va en la captura del parser de texto.

**Tech Stack:** Python, ReportLab (generación PDF), python-decouple (`config`), pytest (pruebas).

## Global Constraints

- Motor de PDF: **ReportLab** (no migrar a WeasyPrint/HTML).
- Configuración vía `python-decouple` → `from decouple import config`.
- Variable de entorno nueva: `FORMATO_PDF` con valores `marluis` | `ecograsas`, default `marluis`.
- La identidad de empresa (nombre, RIF, dirección, emails, logo) vive **dentro** de cada módulo de formato (un formato = una empresa).
- No agregar columnas/campos a la base de datos. Teléfono, Dirección de Despacho y "Fecha Límite Entrega" quedan **en blanco**.
- Formato numérico ECOGRASAS: europeo `1.426,00` (miles con punto, decimales con coma).
- Logo de ECOGRASAS: **placeholder de texto** hasta tener el archivo.
- "Elaborado por" = `nombre_vendedor`.

---

### Task 1: Fix de captura del comentario en el parser

**Files:**
- Modify: `parser/parsear_pedido.py:30-70` (cuerpo del bucle de `PedidoTextoParser.parse`)
- Test: `tests/test_parsear_comentario.py`

**Interfaces:**
- Consumes: nada de tareas previas.
- Produces: `PedidoTextoParser().parse(text_msg: list[str]) -> dict` sigue devolviendo un `dict` (o una instancia `ValueError` en caso de error, sin lanzarla). La clave `comentario` contiene el comentario completo, con líneas unidas por `\n`.

- [ ] **Step 1: Escribir las pruebas que fallan**

Crear `tests/test_parsear_comentario.py`:

```python
from parser.parsear_pedido import PedidoTextoParser


def test_comentario_una_linea_despues_de_precio():
    msg = ["J123456", "01010001 5", "P1", "Entregar el viernes"]
    result = PedidoTextoParser().parse(msg)
    assert isinstance(result, dict)
    assert result["comentario"] == "Entregar el viernes"


def test_comentario_varias_lineas_se_unen_con_salto():
    msg = ["J123456", "01010001 5", "P1", "Despachar rapido", "Cliente urgente"]
    result = PedidoTextoParser().parse(msg)
    assert result["comentario"] == "Despachar rapido\nCliente urgente"


def test_precio_con_espacio_final_no_cae_en_comentario():
    msg = ["J123456", "01010001 5", "P1 ", "Nota final"]
    result = PedidoTextoParser().parse(msg)
    assert result["precio"] == "P1"
    assert result["comentario"] == "Nota final"


def test_comentario_una_palabra_con_digitos_no_invalida_pedido():
    msg = ["J123456", "01010001 5", "P1", "Factura2026"]
    result = PedidoTextoParser().parse(msg)
    assert isinstance(result, dict)
    assert result["comentario"] == "Factura2026"
```

- [ ] **Step 2: Correr las pruebas y verificar que fallan**

Run: `python -m pytest tests/test_parsear_comentario.py -v`
Expected: FAIL. `test_precio_con_espacio_final...` falla (con `"P1 "` el precio no se detecta y la línea cae como comentario); `test_comentario_varias_lineas...` falla (las líneas se pegan sin `\n`); `test_comentario_una_palabra_con_digitos...` falla (devuelve `ValueError`, no `dict`).
Si aparece `ModuleNotFoundError: pytest`, instalar: `pip install pytest`.

- [ ] **Step 3: Implementar el fix mínimo en el parser**

En `parser/parsear_pedido.py`, reemplazar el bucle `for linea in text_msg[1:]:` y su retorno (líneas ~34-70) por:

```python
        productos = {}
        productos_invalidos = []
        comentario_lineas: list[str] = []
        precio_visto = False
        for linea in text_msg[1:]:
            linea_limpia = linea.strip()
            if not linea_limpia:
                continue
            match = PRODUCTOS_REGEX.fullmatch(linea_limpia)
            if match:
                codigo, cantidad, descuento = match.groups()
                try:
                    productos[codigo.upper()] = {
                        'cantidad': float(cantidad.replace(',', '.')),
                        'descuento': float(descuento[0:-1].replace(',', '.')) if descuento else 0,
                    }
                except ValueError:
                    continue
                continue
            elif linea_limpia in ("P1", "P2"):
                precio = linea_limpia
                precio_visto = True
                continue
            elif not precio_visto and PRODUCTOS_SOLO.fullmatch(linea_limpia):
                productos_invalidos.append(f"* `{linea_limpia.split()[0]}`\n")
                continue
            else:
                comentario_lineas.append(linea_limpia)

        comentario = "\n".join(comentario_lineas)

        return Pedido(
            cliente=text_msg[0],
            productos=productos,
            precio=precio,
            comentario=comentario,
        ).__dict__ if not productos_invalidos else ValueError(
            f"Productos inválidos o cantidad incorrecta por favor verifique:\n{''.join(productos_invalidos)}"
        )
```

Nota: `precio_visto` hace que solo las líneas **antes** de `P1/P2` que parezcan un código suelto se marquen como producto inválido; cualquier línea posterior no reconocida es comentario. Esto elimina la falsa invalidación de comentarios de una sola palabra con dígitos.

- [ ] **Step 4: Correr las pruebas y verificar que pasan**

Run: `python -m pytest tests/test_parsear_comentario.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Verificar que el comentario llega a a2 (revisión de código)**

Confirmar que `database/dbisam.py` sigue inyectando `pedido['comentario']` en `FTI_DETALLECOMENTARIO`:

Run: `git grep -n "FTI_DETALLECOMENTARIO\|comentario = pedido" database/dbisam.py`
Expected: aparece la línea `comentario = pedido['comentario'].replace(...)` y `FTI_DETALLECOMENTARIO` en el INSERT. No requiere cambios (el comentario ahora llega no vacío desde el parser).

- [ ] **Step 6: Commit**

```bash
git add tests/test_parsear_comentario.py parser/parsear_pedido.py
git commit -m "fix: capturar correctamente el comentario del pedido en el parser de texto"
```

---

### Task 2: Extraer el formato Marluis a su propio módulo

**Files:**
- Create: `pdf/formato_marluis.py`
- Modify: `pdf/weasy.py` (convertir en shim)
- Create: `tests/pedido_muestra.py` (fixture compartida de datos)
- Test: `tests/test_formato_marluis.py`

**Interfaces:**
- Consumes: nada.
- Produces:
  - `pdf.formato_marluis.generar(filename, pedido: dict, logo_path='pdf/marluis.png', preliminar: bool = False) -> bytes | None` — mismo layout actual, sin cambios visuales. Devuelve `bytes` cuando `preliminar=True`, si no escribe a `filename` y devuelve `None`.
  - `pdf.weasy.generar_factura` sigue existiendo (reexporta `generar`) para compatibilidad.
  - `tests.pedido_muestra.pedido_muestra() -> dict` — pedido de ejemplo con 16%, 8% y exento, reutilizable por las pruebas de PDF.

- [ ] **Step 1: Crear la fixture de datos compartida**

Crear `tests/pedido_muestra.py`:

```python
def pedido_muestra() -> dict:
    """Pedido de ejemplo (basado en el PDF de ECOGRASAS) con 8% y exento."""
    return {
        'id': 3610,
        'cliente': 'J-00028027-4',
        'descripcion_cliente': 'PANDOCK, C. A.',
        'direccion_cliente': ('AV ROMULO GALLEGOS EDIF PANDOCK PISO PB LOCAL 26 '
                              'SECTOR MONTE CRISTO CARACAS MIRANDA ZONA POSTAL 1071'),
        'nombre_vendedor': 'VENTAS INTERNAS',
        'vendedor': '04',
        'precio': 'P1',
        'comentario': 'PRECIO AUTORIZADO POR JUAN M. VILLEGAS\nCREDITO 10 DIAS',
        'productos': {
            'PT0304001': {'descripcion': 'MANTECA VEGETAL LA COJEDEÑA PANADERA CAJA 10 kg',
                          'cantidad': 20.0, 'descuento': 0, 'impuesto': 8,
                          'precio_sin_iva': 38.00, 'precio_con_descuento': 38.00,
                          'subtotal': 760.00, 'total_sin_dcto': 760.00,
                          'monto_iva': 3.04, 'precio_venta': 41.04, 'precio': 41.04, 'peso_item': 0},
            'PT0402001': {'descripcion': 'MARGARINA LA COJEDEÑA MULTIUSO BAJA EN SAL 05 kg (E)',
                          'cantidad': 92.0, 'descuento': 0, 'impuesto': 0,
                          'precio_sin_iva': 15.50, 'precio_con_descuento': 15.50,
                          'subtotal': 1426.00, 'total_sin_dcto': 1426.00,
                          'monto_iva': 0.0, 'precio_venta': 15.50, 'precio': 15.50, 'peso_item': 0},
            'PT0402003': {'descripcion': 'MARGARINA LA COJEDEÑA MULTIUSO CON SAL 05 kg (E)',
                          'cantidad': 36.0, 'descuento': 0, 'impuesto': 0,
                          'precio_sin_iva': 15.50, 'precio_con_descuento': 15.50,
                          'subtotal': 558.00, 'total_sin_dcto': 558.00,
                          'monto_iva': 0.0, 'precio_venta': 15.50, 'precio': 15.50, 'peso_item': 0},
            'PT0305003': {'descripcion': 'MANTECA VEGETAL LA COJEDEÑA COMPUESTA CAJA 10 Kg',
                          'cantidad': 38.0, 'descuento': 0, 'impuesto': 8,
                          'precio_sin_iva': 28.00, 'precio_con_descuento': 28.00,
                          'subtotal': 1064.00, 'total_sin_dcto': 1064.00,
                          'monto_iva': 2.24, 'precio_venta': 30.24, 'precio': 30.24, 'peso_item': 0},
        },
        'base_16': 0.0, 'iva_16': 0.0,
        'base_8': 1824.00, 'iva_8': 145.92,
        'exento': 1984.00,
        'baseimponible': 1824.00, 'iva_total': 145.92,
        'total_bruto': 3808.00, 'total_neto': 3953.92,
        'peso_total': 0.0,
    }
```

- [ ] **Step 2: Escribir la prueba que falla**

Crear `tests/test_formato_marluis.py`:

```python
from pdf.formato_marluis import generar
from tests.pedido_muestra import pedido_muestra


def test_marluis_genera_pdf_en_memoria():
    data = generar(filename=None, pedido=pedido_muestra(), preliminar=True)
    assert isinstance(data, bytes)
    assert data[:4] == b"%PDF"


def test_weasy_shim_sigue_exportando_generar_factura():
    from pdf.weasy import generar_factura
    data = generar_factura(filename=None, pedido=pedido_muestra(), preliminar=True)
    assert data[:4] == b"%PDF"
```

- [ ] **Step 3: Correr la prueba y verificar que falla**

Run: `python -m pytest tests/test_formato_marluis.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'pdf.formato_marluis'`.

- [ ] **Step 4: Crear `pdf/formato_marluis.py` extrayendo el código actual**

Copiar **verbatim** el contenido de `pdf/weasy.py` a `pdf/formato_marluis.py`, con estos dos cambios:
1. Renombrar la función `def generar_factura(` → `def generar(`.
2. Cambiar la firma para que el logo sea propio del formato:

```python
def generar(filename, pedido: dict, logo_path='pdf/marluis.png', preliminar: bool = False):
```

Borrar del final del archivo las dos líneas comentadas de ejemplo (`#pedido = {...}` y `#generar_factura(...)`). El resto del cuerpo (encabezado, tablas, pie de impuestos, `doc.build`, retorno de `pdf_bytes`) queda **idéntico**.

- [ ] **Step 5: Convertir `pdf/weasy.py` en shim**

Reemplazar **todo** el contenido de `pdf/weasy.py` por:

```python
# Shim de compatibilidad: el formato Marluis se movió a pdf/formato_marluis.py
from pdf.formato_marluis import generar as generar_factura

__all__ = ["generar_factura"]
```

- [ ] **Step 6: Correr las pruebas y verificar que pasan**

Run: `python -m pytest tests/test_formato_marluis.py -v`
Expected: PASS (2 passed).

- [ ] **Step 7: Commit**

```bash
git add pdf/formato_marluis.py pdf/weasy.py tests/pedido_muestra.py tests/test_formato_marluis.py
git commit -m "refactor: extraer el formato Marluis a pdf/formato_marluis.py con shim de compatibilidad"
```

---

### Task 3: Crear el formato ECOGRASAS

**Files:**
- Create: `pdf/formato_ecograsas.py`
- Test: `tests/test_formato_ecograsas.py`

**Interfaces:**
- Consumes: `tests.pedido_muestra.pedido_muestra()` (Task 2).
- Produces: `pdf.formato_ecograsas.generar(filename, pedido: dict, logo_path=None, preliminar: bool = False) -> bytes | None` — misma firma común. Replica el PDF de ECOGRASAS.

- [ ] **Step 1: Escribir la prueba que falla**

Crear `tests/test_formato_ecograsas.py`:

```python
from pdf.formato_ecograsas import generar, _money
from tests.pedido_muestra import pedido_muestra


def test_money_formato_europeo():
    assert _money(1426.0) == "1.426,00"
    assert _money(3953.92) == "3.953,92"
    assert _money(0) == "0,00"


def test_ecograsas_genera_pdf_en_memoria():
    data = generar(filename=None, pedido=pedido_muestra(), preliminar=True)
    assert isinstance(data, bytes)
    assert data[:4] == b"%PDF"


def test_ecograsas_maneja_comentario_vacio():
    pedido = pedido_muestra()
    pedido["comentario"] = ""
    data = generar(filename=None, pedido=pedido, preliminar=True)
    assert data[:4] == b"%PDF"
```

- [ ] **Step 2: Correr la prueba y verificar que falla**

Run: `python -m pytest tests/test_formato_ecograsas.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'pdf.formato_ecograsas'`.

- [ ] **Step 3: Crear `pdf/formato_ecograsas.py`**

```python
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
```

- [ ] **Step 4: Correr las pruebas y verificar que pasan**

Run: `python -m pytest tests/test_formato_ecograsas.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Inspección visual del PDF**

Generar el PDF a disco y compararlo con `C:\Users\arang\Documents\ECOGRASAS PEDIDOS.pdf`:

```bash
python -c "from pdf.formato_ecograsas import generar; from tests.pedido_muestra import pedido_muestra; generar('static/media/_test_ecograsas.pdf', pedido_muestra(), preliminar=False)"
```

Expected: se crea `static/media/_test_ecograsas.pdf`. Abrirlo y confirmar: encabezado ECOGRASAS, bloque cliente sin los campos eliminados, tabla de ítems con 5 columnas, pie con Total Pedido = 3.953,92, Observaciones con el comentario. Borrar el archivo de prueba al terminar.

- [ ] **Step 6: Commit**

```bash
git add pdf/formato_ecograsas.py tests/test_formato_ecograsas.py
git commit -m "feat: agregar formato de impresion ECOGRASAS"
```

---

### Task 4: Factory de formatos + configuración + documentación

**Files:**
- Create: `pdf/factory.py`
- Modify: `.env` (agregar `FORMATO_PDF`)
- Modify: `CLAUDE.md` (documentar la variable)
- Test: `tests/test_factory_pdf.py`

**Interfaces:**
- Consumes: `pdf.formato_marluis.generar`, `pdf.formato_ecograsas.generar`.
- Produces: `pdf.factory.get_generador_pdf() -> callable` que devuelve la función `generar` del formato indicado por `FORMATO_PDF`.

- [ ] **Step 1: Escribir la prueba que falla**

Crear `tests/test_factory_pdf.py`:

```python
import pytest
from pdf import factory, formato_marluis, formato_ecograsas


def test_default_es_marluis(monkeypatch):
    monkeypatch.delenv("FORMATO_PDF", raising=False)
    monkeypatch.setattr(factory, "config", lambda k, default=None: default)
    assert factory.get_generador_pdf() is formato_marluis.generar


def test_selecciona_ecograsas(monkeypatch):
    monkeypatch.setattr(factory, "config", lambda k, default=None: "ecograsas")
    assert factory.get_generador_pdf() is formato_ecograsas.generar


def test_valor_invalido_lanza_error(monkeypatch):
    monkeypatch.setattr(factory, "config", lambda k, default=None: "inexistente")
    with pytest.raises(ValueError):
        factory.get_generador_pdf()
```

- [ ] **Step 2: Correr la prueba y verificar que falla**

Run: `python -m pytest tests/test_factory_pdf.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'pdf.factory'`.

- [ ] **Step 3: Crear `pdf/factory.py`**

```python
from decouple import config
from pdf import formato_marluis, formato_ecograsas

_GENERADORES = {
    "marluis": formato_marluis.generar,
    "ecograsas": formato_ecograsas.generar,
}


def get_generador_pdf():
    """Devuelve la función generar() del formato indicado por FORMATO_PDF."""
    nombre = config("FORMATO_PDF", default="marluis").strip().lower()
    try:
        return _GENERADORES[nombre]
    except KeyError:
        raise ValueError(
            f"FORMATO_PDF='{nombre}' no es válido. Opciones: {', '.join(_GENERADORES)}"
        )
```

- [ ] **Step 4: Correr la prueba y verificar que pasa**

Run: `python -m pytest tests/test_factory_pdf.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Agregar la variable al `.env`**

Añadir al archivo `.env` (raíz del proyecto):

```
FORMATO_PDF=marluis
```

- [ ] **Step 6: Documentar en `CLAUDE.md`**

En `CLAUDE.md`, en la sección "## Variables de Entorno (`.env`)", agregar dentro del bloque de código, después de la línea `CatalogName=...`:

```
FORMATO_PDF=marluis                              # Formato de impresión: marluis | ecograsas
```

- [ ] **Step 7: Commit**

```bash
git add pdf/factory.py tests/test_factory_pdf.py CLAUDE.md
git commit -m "feat: factory de formatos PDF seleccionable por FORMATO_PDF"
```

> Nota: `.env` no se commitea (está en `.gitignore`); el cambio del Step 5 es solo local.

---

### Task 5: Conectar los call sites a la factory

**Files:**
- Modify: `main.py:24` (import), `main.py:185`, `main.py:501`
- Modify: `strategy/response_strategy.py:8` (import), `strategy/response_strategy.py:61`
- Test: verificación por grep + smoke manual

**Interfaces:**
- Consumes: `pdf.factory.get_generador_pdf` (Task 4).
- Produces: los tres puntos de generación de PDF usan el formato configurado; ya no importan `generar_factura` directamente.

- [ ] **Step 1: Cambiar el import en `main.py`**

En `main.py:24`, reemplazar:

```python
from pdf.weasy import generar_factura
```

por:

```python
from pdf.factory import get_generador_pdf
```

- [ ] **Step 2: Actualizar el call site del preliminar por texto (`main.py:185`)**

Reemplazar:

```python
     pdf_buffer = generar_factura(filename=f'static/media/pedido_preliminar.pdf', pedido=pedido, logo_path='pdf/marluis.png', preliminar=True)
```

por:

```python
     pdf_buffer = get_generador_pdf()(filename='static/media/pedido_preliminar.pdf', pedido=pedido, preliminar=True)
```

- [ ] **Step 3: Actualizar el call site del preliminar por Flow (`main.py:501`)**

Reemplazar:

```python
    pdf_buffer = generar_factura(filename='static/media/pedido_preliminar.pdf',
                                 pedido=pedido, logo_path='pdf/marluis.png', preliminar=True)
```

por:

```python
    pdf_buffer = get_generador_pdf()(filename='static/media/pedido_preliminar.pdf',
                                     pedido=pedido, preliminar=True)
```

- [ ] **Step 4: Actualizar `strategy/response_strategy.py`**

En `strategy/response_strategy.py:8`, reemplazar:

```python
from pdf.weasy import generar_factura
```

por:

```python
from pdf.factory import get_generador_pdf
```

Y en la línea 61, reemplazar:

```python
        generar_factura(filename=f'static/media/pedido{pedido["id"]}.pdf', pedido=pedido, logo_path='pdf/marluis.png')
```

por:

```python
        get_generador_pdf()(filename=f'static/media/pedido{pedido["id"]}.pdf', pedido=pedido)
```

- [ ] **Step 5: Verificar que no quedan llamadas directas a `generar_factura`**

Run: `git grep -n "generar_factura" -- main.py strategy/response_strategy.py`
Expected: sin resultados (ninguna coincidencia). El shim `pdf/weasy.py` puede seguir teniendo la palabra; por eso se limita la búsqueda a esos dos archivos.

- [ ] **Step 6: Smoke test de la cadena completa por variable de entorno**

Run:
```bash
FORMATO_PDF=ecograsas python -c "from pdf.factory import get_generador_pdf; from tests.pedido_muestra import pedido_muestra; d=get_generador_pdf()(filename=None, pedido=pedido_muestra(), preliminar=True); print('ECOGRASAS OK', d[:4])"
FORMATO_PDF=marluis python -c "from pdf.factory import get_generador_pdf; from tests.pedido_muestra import pedido_muestra; d=get_generador_pdf()(filename=None, pedido=pedido_muestra(), preliminar=True); print('MARLUIS OK', d[:4])"
```
Expected: `ECOGRASAS OK b'%PDF'` y `MARLUIS OK b'%PDF'`.
(En PowerShell: `$env:FORMATO_PDF='ecograsas'; python -c "..."`.)

- [ ] **Step 7: Correr toda la suite**

Run: `python -m pytest tests/ -v`
Expected: todas las pruebas nuevas en verde (parser, marluis, ecograsas, factory).

- [ ] **Step 8: Commit**

```bash
git add main.py strategy/response_strategy.py
git commit -m "feat: seleccionar el formato de PDF via factory en todos los call sites"
```

---

## Self-Review

**Spec coverage:**
- Selección por env var → Task 4 (factory + `FORMATO_PDF`). ✓
- Formato ECOGRASAS fiel con campos/columnas eliminados → Task 3. ✓
- Marluis sin cambios de layout → Task 2 (extracción verbatim). ✓
- Comentario llega al PDF y a a2 → Task 1 (fix parser) + Task 1 Step 5 (verificación a2) + Task 3 (Observaciones). ✓
- Identidad de empresa por módulo → Task 2/Task 3 (constantes internas). ✓
- Documentar variable → Task 4 Step 6. ✓
- Campos en blanco (Teléfono, Despacho, Fecha Límite) → Task 3 (código los deja vacíos). ✓
- Total Descuentos = suma real → Task 3 (`sub_total - total_bruto`). ✓

**Placeholder scan:** El único `None`/placeholder deliberado es `LOGO_ECOGRASAS = None` (decisión del spec: placeholder de texto hasta tener el logo), no un placeholder de plan. Sin TODOs sin resolver.

**Type consistency:** `generar(filename, pedido, logo_path=..., preliminar=...)` idéntica en marluis y ecograsas; `get_generador_pdf()` devuelve esa función; los call sites la invocan sin `logo_path`. `_money`, `pedido_muestra` referenciados consistentemente. ✓
