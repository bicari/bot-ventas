"""Pruebas de resolver_precio_manual (precio libre del Flow).

Ejecutar:  python -m pytest tests/test_precio_libre.py
       o:  python tests/test_precio_libre.py
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flows.precio_libre import resolver_precio_manual


def test_sin_precio_devuelve_none():
    assert resolver_precio_manual(None, None, 0, 16) is None
    assert resolver_precio_manual("", None, 0, 16) is None
    assert resolver_precio_manual("   ", None, 0, 16) is None


def test_radio_marcado_sin_precio_se_ignora():
    assert resolver_precio_manual("", "con_iva", 0, 16) is None


def test_sin_iva_devuelve_el_precio_tal_cual():
    assert resolver_precio_manual("12.50", "sin_iva", 0, 16) == 12.5


def test_coma_decimal_aceptada():
    assert resolver_precio_manual("12,50", "sin_iva", 0, 16) == 12.5


def test_con_iva_16_descompone_la_base():
    assert resolver_precio_manual("11.60", "con_iva", 0, 16) == 10.0


def test_con_iva_8_descompone_la_base():
    assert resolver_precio_manual("10.80", "con_iva", 0, 8) == 10.0


def test_con_iva_exento_no_cambia():
    assert resolver_precio_manual("10", "con_iva", 0, 0) == 10.0


def test_no_numerico_es_error():
    with pytest.raises(ValueError, match="no es un número válido"):
        resolver_precio_manual("abc", "sin_iva", 0, 16)


def test_cero_y_negativo_son_error():
    with pytest.raises(ValueError, match="mayor que cero"):
        resolver_precio_manual("0", "sin_iva", 0, 16)
    with pytest.raises(ValueError, match="mayor que cero"):
        resolver_precio_manual("-5", "sin_iva", 0, 16)


def test_precio_y_descuento_son_excluyentes():
    with pytest.raises(ValueError, match="excluyentes"):
        resolver_precio_manual("12.50", "sin_iva", 10, 16)


def test_precio_sin_radio_es_error():
    with pytest.raises(ValueError, match="Indica si el precio incluye IVA"):
        resolver_precio_manual("12.50", None, 0, 16)
    with pytest.raises(ValueError, match="Indica si el precio incluye IVA"):
        resolver_precio_manual("12.50", "", 0, 16)


if __name__ == "__main__":
    test_sin_precio_devuelve_none()
    test_radio_marcado_sin_precio_se_ignora()
    test_sin_iva_devuelve_el_precio_tal_cual()
    test_coma_decimal_aceptada()
    test_con_iva_16_descompone_la_base()
    test_con_iva_8_descompone_la_base()
    test_con_iva_exento_no_cambia()
    test_no_numerico_es_error()
    test_cero_y_negativo_son_error()
    test_precio_y_descuento_son_excluyentes()
    test_precio_sin_radio_es_error()
    print("OK: resolver_precio_manual.")
