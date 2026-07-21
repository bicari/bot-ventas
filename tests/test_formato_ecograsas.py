from reportlab.pdfbase.pdfmetrics import stringWidth

from pdf.formato_ecograsas import generar, _money, _fuente_total, TOTAL_BOX_ANCHO
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


def test_fuente_total_conserva_18_para_montos_normales():
    assert _fuente_total("3.953,92") == 18


def test_fuente_total_encoge_hasta_caber_en_la_caja():
    """Regresión: un total sin espacios no se envuelve y se salía de la caja."""
    disponible = TOTAL_BOX_ANCHO - 12  # 6pt de padding por lado
    monto = "999.999.999.999,99"
    # Premisa del bug: a 18pt este monto NO cabe en la caja.
    assert stringWidth(monto, "Helvetica-Bold", 18) > disponible
    tam = _fuente_total(monto)
    assert tam < 18
    assert stringWidth(monto, "Helvetica-Bold", tam) <= disponible


def test_ecograsas_genera_pdf_con_total_enorme():
    pedido = pedido_muestra()
    pedido["total_neto"] = 999999999999.99
    data = generar(filename=None, pedido=pedido, preliminar=True)
    assert data[:4] == b"%PDF"
