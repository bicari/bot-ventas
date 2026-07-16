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
