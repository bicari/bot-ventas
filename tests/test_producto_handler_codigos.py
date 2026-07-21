"""Regresión: ProductoHandler debe aceptar códigos alfanuméricos.

Bug de producción: ordenar los códigos con ``sort(key=int)`` reventaba con
"invalid literal for int() with base 10: 'PT0201001'" en cuanto un pedido
incluía un código con letras (FI_REFERENCIA o FI_CODIGO alfanumérico).

Ejecutar:  python -m pytest tests/test_producto_handler_codigos.py
       o:  python tests/test_producto_handler_codigos.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import handlers.Validar_Pedido as vp


class _FakeDB:
    """Sustituye DBISAMDatabase: responde una fila válida por cada código."""

    def consultar_precios(self, productos, tipo_precio):
        filas = {c: (c, 16, 10.0, f"PRODUCTO {c}", 1.0, c) for c in productos}
        return filas, []


def _pedido_con(codigos):
    return {
        "cliente": "V6472827",
        "precio": "P1",
        "productos": {c: {"cantidad": 2.0, "descuento": 0} for c in codigos},
    }


def test_handle_acepta_codigos_alfanumericos():
    """El caso real del bug: un código con letras no debe romper el handler."""
    original = vp.DBISAMDatabase
    vp.DBISAMDatabase = _FakeDB
    try:
        pedido = vp.ProductoHandler().handle(
            _pedido_con(["PT0201001", "01010024"]), user_id="584140000000"
        )
    finally:
        vp.DBISAMDatabase = original

    assert pedido["productos"]["PT0201001"]["subtotal"] == 20.0
    assert pedido["productos"]["01010024"]["subtotal"] == 20.0


if __name__ == "__main__":
    test_handle_acepta_codigos_alfanumericos()
    print("OK: ProductoHandler acepta codigos alfanumericos.")
