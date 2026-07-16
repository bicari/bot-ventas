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
