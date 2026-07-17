"""Pruebas de la lógica pura de resolución de códigos para consultar precios.

Ejecutar:  python -m pytest tests/test_consulta_precios.py
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.consulta_precios import codigos_para_fi_codigo, lista_sql


def test_lista_sql_cita_cada_valor():
    assert lista_sql(["A", "B"]) == "('A','B')"


def test_lista_sql_un_solo_valor():
    assert lista_sql(["PT0201001"]) == "('PT0201001')"


def test_lista_sql_escapa_comilla_simple():
    """Una comilla en el código cerraría el literal y rompería el SQL."""
    assert lista_sql(["O'Brien"]) == "('O''Brien')"


def test_lista_sql_vacia_lanza_error():
    """IN () es SQL inválido en DBISAM: fallar ruidosamente, no emitirlo."""
    with pytest.raises(ValueError):
        lista_sql([])


def test_codigos_para_fi_codigo_sin_ningun_codigo_de_barra():
    """EL BUG REPORTADO: sin barras, la lista salía vacía y producía 'IN ()'.

    Al unir lo tipeado, deja de poder quedar vacía.
    """
    assert codigos_para_fi_codigo(["PT0201001"], {}) == ["PT0201001"]


def test_codigos_para_fi_codigo_une_tipeados_y_resueltos_sin_duplicar():
    productos = ["0-320-038", "01010024"]
    por_barra = {"07110392": "0-320-038", "01010024": "01010024"}
    assert codigos_para_fi_codigo(productos, por_barra) == ["0-320-038", "01010024", "07110392"]
