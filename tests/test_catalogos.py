"""Pruebas del resolutor de CatalogName por sistema.

Ejecutar:  python -m pytest tests/test_catalogos.py
       o:  python tests/test_catalogos.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.catalogos import catalogo_de_sistema

MAPA = {"A": r"C:\cat\A", "B": r"C:\cat\B"}
DEFECTO = r"C:\cat\default"


def test_sistema_a():
    assert catalogo_de_sistema("A", mapa=MAPA, default=DEFECTO) == r"C:\cat\A"


def test_sistema_b():
    assert catalogo_de_sistema("B", mapa=MAPA, default=DEFECTO) == r"C:\cat\B"


def test_normaliza_minusculas_y_espacios():
    assert catalogo_de_sistema(" a ", mapa=MAPA, default=DEFECTO) == r"C:\cat\A"


def test_vacio_va_a_default():
    assert catalogo_de_sistema("", mapa=MAPA, default=DEFECTO) == DEFECTO


def test_none_va_a_default():
    assert catalogo_de_sistema(None, mapa=MAPA, default=DEFECTO) == DEFECTO


def test_desconocido_va_a_default():
    assert catalogo_de_sistema("C", mapa=MAPA, default=DEFECTO) == DEFECTO


def test_ruta_vacia_va_a_default():
    assert catalogo_de_sistema("A", mapa={"A": ""}, default=DEFECTO) == DEFECTO


if __name__ == "__main__":
    test_sistema_a()
    test_sistema_b()
    test_normaliza_minusculas_y_espacios()
    test_vacio_va_a_default()
    test_none_va_a_default()
    test_desconocido_va_a_default()
    test_ruta_vacia_va_a_default()
    print("OK: catalogo_de_sistema.")
