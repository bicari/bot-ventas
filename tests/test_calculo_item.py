"""Pruebas de la aritmética por ítem unificada.

Los valores esperados reproducen EXACTAMENTE lo que hoy calculan
add_product (main.py) y ProductoHandler (handlers/Validar_Pedido.py),
incluidos los redondeos a 2 decimales.

Ejecutar:  python -m pytest tests/test_calculo_item.py
       o:  python tests/test_calculo_item.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from handlers.calculo_item import calcular_item


def test_item_16_sin_descuento():
    item = calcular_item(precio_sin_iva=10.0, cantidad=2.0, descuento=0,
                         impuesto=16, peso=1.5)
    assert item == {
        "precio_sin_iva": 10.0,
        "precio": 11.6,
        "precio_con_descuento": 10.0,
        "monto_iva": 1.6,
        "precio_venta": 11.6,
        "subtotal": 20.0,
        "total_sin_dcto": 20.0,
        "peso_item": 3.0,
    }


def test_item_16_con_descuento_10():
    item = calcular_item(precio_sin_iva=10.0, cantidad=2.0, descuento=10,
                         impuesto=16, peso=1.0)
    assert item["precio_con_descuento"] == 9.0
    assert item["monto_iva"] == 1.44          # 9.00 × 0.16
    assert item["precio_venta"] == 10.44      # 9.00 × 1.16
    assert item["subtotal"] == 18.0           # 9.00 × 2
    assert item["total_sin_dcto"] == 20.0     # sin descuento


def test_item_8_por_ciento():
    item = calcular_item(precio_sin_iva=10.0, cantidad=1.0, descuento=0,
                         impuesto=8, peso=0.5)
    assert item["precio"] == 10.8
    assert item["monto_iva"] == 0.8
    assert item["precio_venta"] == 10.8


def test_item_exento():
    item = calcular_item(precio_sin_iva=10.0, cantidad=3.0, descuento=0,
                         impuesto=0, peso=0.0)
    assert item["precio"] == 10.0
    assert item["monto_iva"] == 0.0
    assert item["precio_venta"] == 10.0
    assert item["subtotal"] == 30.0


def test_redondeos_a_dos_decimales():
    item = calcular_item(precio_sin_iva=3.333, cantidad=3.0, descuento=0,
                         impuesto=16, peso=1.0)
    assert item["precio_sin_iva"] == 3.33
    assert item["precio_con_descuento"] == 3.33   # round(3.333, 2)
    assert item["subtotal"] == 9.99               # round(3.33 × 3, 2)


if __name__ == "__main__":
    test_item_16_sin_descuento()
    test_item_16_con_descuento_10()
    test_item_8_por_ciento()
    test_item_exento()
    test_redondeos_a_dos_decimales()
    print("OK: calcular_item.")
