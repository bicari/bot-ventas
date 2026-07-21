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


import pytest


def _fake_db(precio):
    """FakeDB con precio de lista configurable."""
    class _DB:
        def consultar_precios(self, productos, tipo_precio):
            filas = {c: (c, 16, precio, f"PRODUCTO {c}", 1.0, c) for c in productos}
            return filas, []
    return _DB


def _handle_con_db(db_cls, pedido):
    original = vp.DBISAMDatabase
    vp.DBISAMDatabase = db_cls
    try:
        return vp.ProductoHandler().handle(pedido, user_id="584140000000")
    finally:
        vp.DBISAMDatabase = original


def test_handle_respeta_precio_manual():
    """La BD dice 10.0 pero el vendedor negoció 8.0: gana el manual."""
    pedido = _pedido_con(["01010024"])
    pedido["productos"]["01010024"].update(
        {"precio_manual": True, "precio_sin_iva": 8.0})

    resultado = _handle_con_db(_fake_db(10.0), pedido)

    p = resultado["productos"]["01010024"]
    assert p["precio_sin_iva"] == 8.0
    assert p["subtotal"] == 16.0        # 8.0 × 2
    assert p["precio_venta"] == 9.28    # 8.0 × 1.16
    assert resultado["base_16"] == 16.0
    assert resultado["iva_16"] == 2.56
    assert resultado["total_neto"] == 18.56


def test_handle_lista_en_cero_con_manual_pasa():
    """Con precio manual, el precio de lista en 0 no bloquea."""
    pedido = _pedido_con(["01010024"])
    pedido["productos"]["01010024"].update(
        {"precio_manual": True, "precio_sin_iva": 8.0})

    resultado = _handle_con_db(_fake_db(0.0), pedido)

    assert resultado["productos"]["01010024"]["subtotal"] == 16.0


def test_handle_lista_en_cero_sin_manual_sigue_fallando():
    """La regla actual para precios de lista <= 0 queda intacta."""
    with pytest.raises(ValueError, match="menor o igual a cero"):
        _handle_con_db(_fake_db(0.0), _pedido_con(["01010024"]))


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
    test_handle_respeta_precio_manual()
    test_handle_lista_en_cero_con_manual_pasa()
    test_handle_lista_en_cero_sin_manual_sigue_fallando()
    print("OK: ProductoHandler acepta codigos alfanumericos y precio manual.")
