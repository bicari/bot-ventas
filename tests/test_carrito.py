"""Pruebas del formateo del texto de carrito de la pantalla PRODUCTO.

Ejecutar:  python -m pytest tests/test_carrito.py
       o:  python tests/test_carrito.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flows.carrito import formato_carrito


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


if __name__ == "__main__":
    test_sin_productos()
    test_un_producto_sin_descuento()
    test_un_producto_con_descuento()
    test_varios_productos_en_orden()
    test_confirmacion_antepuesta()
    test_confirmacion_no_se_muestra_sin_productos()
    print("OK: formato_carrito.")
