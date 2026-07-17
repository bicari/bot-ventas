"""Pruebas de la lógica pura de resolución de códigos para consultar precios.

Ejecutar:  python -m pytest tests/test_consulta_precios.py
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.consulta_precios import codigos_para_fi_codigo, lista_sql, mapear_resultados


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


def fila(fi_codigo, fi_referencia):
    """Fila cruda del query: (FI_CODIGO, IMPUESTO, PRECIO, DESC, PESO, FI_REFERENCIA)."""
    return (fi_codigo, 16, 10.0, "DESCRIPCION", 1.0, fi_referencia)


def test_hallado_por_referencia():
    filas = [fila("07110392", "PT0201001")]
    result_map, not_found = mapear_resultados(filas, ["PT0201001"], {})
    assert result_map == {"PT0201001": filas[0]}
    assert not_found == []


def test_hallado_por_codigo_de_barra_se_indexa_por_lo_tipeado():
    """El vendedor tipeó la barra; el result_map debe indexarse por la barra."""
    filas = [fila("07110392", "2661012025306")]
    result_map, not_found = mapear_resultados(filas, ["0-320-038"], {"07110392": "0-320-038"})
    assert result_map == {"0-320-038": filas[0]}
    assert not_found == []


def test_hallado_por_fi_codigo_no_aparece_en_not_found():
    """Regresión Bug 3: not_found ignoraba FI_CODIGO."""
    filas = [fila("01010024", "REF-X")]
    result_map, not_found = mapear_resultados(filas, ["01010024"], {})
    assert result_map == {"01010024": filas[0]}
    assert not_found == []


def test_not_found_lista_los_ausentes_en_orden():
    filas = [fila("01010024", "REF-X")]
    _, not_found = mapear_resultados(filas, ["ZZZ", "01010024", "AAA"], {})
    assert not_found == ["ZZZ", "AAA"]


def test_filas_no_reclamadas_se_descartan():
    """El OR del query puede traer filas que nadie pidió."""
    filas = [fila("01010024", "REF-X"), fila("99999999", "REF-Y")]
    result_map, _ = mapear_resultados(filas, ["01010024"], {})
    assert list(result_map) == ["01010024"]


def test_prioridad_interno_gana_sobre_referencia():
    """'535' es FI_CODIGO de A y FI_REFERENCIA de B: gana el interno."""
    fila_interno = fila("535", "REF-A")
    fila_referencia = fila("88888888", "535")
    result_map, _ = mapear_resultados([fila_interno, fila_referencia], ["535"], {})
    assert result_map == {"535": fila_interno}


def test_prioridad_no_depende_del_orden_de_filas():
    """DBISAM no garantiza orden: el resultado debe ser el mismo al invertirlo."""
    fila_interno = fila("535", "REF-A")
    fila_referencia = fila("88888888", "535")
    directo, _ = mapear_resultados([fila_interno, fila_referencia], ["535"], {})
    invertido, _ = mapear_resultados([fila_referencia, fila_interno], ["535"], {})
    assert directo == invertido == {"535": fila_interno}


def test_prioridad_barra_gana_sobre_interno():
    fila_barra = fila("07110392", "REF-A")
    fila_interno = fila("0-320-038", "REF-B")
    filas = [fila_interno, fila_barra]
    result_map, _ = mapear_resultados(filas, ["0-320-038"], {"07110392": "0-320-038"})
    assert result_map == {"0-320-038": fila_barra}


def test_pedido_vacio():
    assert mapear_resultados([], [], {}) == ({}, [])
