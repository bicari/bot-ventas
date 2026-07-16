"""Pruebas de los helpers de impuesto para la persistencia a DBISAM.

Ejecutar:  python -m pytest tests/test_impuestos.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.impuestos import slots_impuesto_linea, campos_impuesto_cabecera


def test_slots_linea_16():
    assert slots_impuesto_linea(16, 25.0) == {
        "imp1": 16, "porc1": 1, "monto1": 25.0,
        "imp2": 0,  "porc2": 1, "monto2": 0.0,
    }


def test_slots_linea_8():
    assert slots_impuesto_linea(8, 4.0) == {
        "imp1": 0, "porc1": 1, "monto1": 0.0,
        "imp2": 8, "porc2": 1, "monto2": 4.0,
    }


def test_slots_linea_exento():
    assert slots_impuesto_linea(0, 0.0) == {
        "imp1": 0, "porc1": 1, "monto1": 0.0,
        "imp2": 0, "porc2": 1, "monto2": 0.0,
    }


def test_slots_linea_float_se_normaliza():
    """La tasa llega como float desde SQL (8.0) y debe enrutar al slot 2."""
    s = slots_impuesto_linea(8.0, 4.0)
    assert s["imp2"] == 8 and s["monto2"] == 4.0 and s["monto1"] == 0.0


def test_cabecera_mixta():
    pedido = {"base_16": 100.0, "iva_16": 16.0, "base_8": 50.0, "iva_8": 4.0}
    assert campos_impuesto_cabecera(pedido) == {
        "base_imponible": 100.0, "imp1_porcent": 16, "imp1_monto": 16.0,
        "base_imponible2": 50.0, "imp2_porcent": 8,  "imp2_monto": 4.0,
    }


def test_cabecera_defaults_sin_totales():
    assert campos_impuesto_cabecera({}) == {
        "base_imponible": 0.0, "imp1_porcent": 16, "imp1_monto": 0.0,
        "base_imponible2": 0.0, "imp2_porcent": 8,  "imp2_monto": 0.0,
    }


if __name__ == "__main__":
    test_slots_linea_16()
    test_slots_linea_8()
    test_slots_linea_exento()
    test_slots_linea_float_se_normaliza()
    test_cabecera_mixta()
    test_cabecera_defaults_sin_totales()
    print("OK: helpers de impuesto.")
