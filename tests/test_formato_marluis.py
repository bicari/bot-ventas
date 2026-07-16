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
