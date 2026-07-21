"""Pruebas del formateo del texto de carrito de la pantalla PRODUCTO.

Ejecutar:  python -m pytest tests/test_carrito.py
       o:  python tests/test_carrito.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flows.carrito import formato_carrito, data_producto, construir_pedido


def _carrito(**prods):
    return {"productos": prods}


def test_sin_productos():
    assert formato_carrito({"productos": {}}) == "Sin productos agregados aún."


def test_un_producto_sin_descuento():
    c = _carrito(ABC123={"cantidad": 5, "descuento": 0, "subtotal": 1250.0})
    assert formato_carrito(c) == "• ABC123 × 5 = $1250.00"


def test_un_producto_con_descuento():
    c = _carrito(ABC123={"cantidad": 2, "descuento": 10, "subtotal": 480.0})
    assert formato_carrito(c) == "• ABC123 × 2 (-10%) = $480.00"


def test_varios_productos_en_orden():
    c = _carrito(
        ABC123={"cantidad": 1, "descuento": 0, "subtotal": 10.0},
        XYZ={"cantidad": 3, "descuento": 0, "subtotal": 30.0},
    )
    assert formato_carrito(c) == "• ABC123 × 1 = $10.00\n• XYZ × 3 = $30.00"


def test_confirmacion_antepuesta():
    c = _carrito(ABC123={"cantidad": 5, "descuento": 0, "subtotal": 1250.0})
    out = formato_carrito(c, agregado="ABC123 × 5")
    assert out == "✅ Agregado: ABC123 × 5\n\n• ABC123 × 5 = $1250.00"


def test_confirmacion_no_se_muestra_sin_productos():
    assert formato_carrito({"productos": {}}, agregado="X") == "Sin productos agregados aún."


def test_data_producto_vacio():
    d = data_producto({"productos": {}})
    assert d == {
        "items_texto": "Sin productos agregados aún.",
        "error": " ",
        "show_error": False,
        "tiene_items": False,
    }


def test_data_producto_con_items_marca_tiene_items():
    c = _carrito(ABC123={"cantidad": 5, "descuento": 0, "subtotal": 1250.0})
    d = data_producto(c)
    assert d["tiene_items"] is True
    assert d["items_texto"] == "• ABC123 × 5 = $1250.00"
    assert d["show_error"] is False
    assert d["error"] == " "


def test_data_producto_con_error():
    d = data_producto({"productos": {}}, error="Agrega al menos un producto.")
    assert d["error"] == "⚠️ Agrega al menos un producto."
    assert d["show_error"] is True
    assert d["tiene_items"] is False


def test_data_producto_con_agregado():
    c = _carrito(ABC123={"cantidad": 5, "descuento": 0, "subtotal": 1250.0})
    d = data_producto(c, agregado="ABC123 × 5")
    assert d["items_texto"].startswith("✅ Agregado: ABC123 × 5")
    assert d["tiene_items"] is True


def test_construir_pedido_toma_comentario_del_completion():
    """Regresión: el comentario viene en la respuesta del Flow (pantalla
    RESUMEN), no en el carrito de Redis; se perdía y el PDF salía sin
    observaciones."""
    carrito = {"cliente": "V123", "productos": {"A": {"cantidad": 1}},
               "tipo_precio": "P2", "sistema": "A"}
    pedido = construir_pedido(carrito, {"comentario": "CREDITO 10 DIAS"})
    assert pedido["comentario"] == "CREDITO 10 DIAS"
    assert pedido["cliente"] == "V123"
    assert pedido["productos"] == {"A": {"cantidad": 1}}
    assert pedido["precio"] == "P2"
    assert pedido["sistema"] == "A"
    assert pedido["total"] == 0.0


def test_construir_pedido_fallback_al_comentario_del_carrito():
    pedido = construir_pedido({"comentario": "DEL CARRITO"}, {})
    assert pedido["comentario"] == "DEL CARRITO"


def test_construir_pedido_sin_comentario_queda_vacio():
    pedido = construir_pedido({}, {})
    assert pedido["comentario"] == ""
    assert pedido["precio"] == "P1"


def test_item_con_precio_manual_lleva_marcador():
    c = _carrito(ABC123={"cantidad": 5, "descuento": 0, "subtotal": 62.5,
                         "precio_manual": True})
    assert formato_carrito(c) == "• ABC123 × 5 ✏️ = $62.50"


def test_item_sin_precio_manual_no_lleva_marcador():
    c = _carrito(ABC123={"cantidad": 5, "descuento": 0, "subtotal": 62.5,
                         "precio_manual": False})
    assert formato_carrito(c) == "• ABC123 × 5 = $62.50"


if __name__ == "__main__":
    test_sin_productos()
    test_un_producto_sin_descuento()
    test_un_producto_con_descuento()
    test_varios_productos_en_orden()
    test_confirmacion_antepuesta()
    test_confirmacion_no_se_muestra_sin_productos()
    test_data_producto_vacio()
    test_data_producto_con_items_marca_tiene_items()
    test_data_producto_con_error()
    test_data_producto_con_agregado()
    test_construir_pedido_toma_comentario_del_completion()
    test_construir_pedido_fallback_al_comentario_del_carrito()
    test_construir_pedido_sin_comentario_queda_vacio()
    test_item_con_precio_manual_lleva_marcador()
    test_item_sin_precio_manual_no_lleva_marcador()
    print("OK: formato_carrito.")
