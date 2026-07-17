"""Pruebas de la selección del campo de precio configurable por CAMPO_PRECIO.

Sigue el patrón de tests/test_factory_pdf.py: se monkeypatchea `config`, así que
no hace falta .env ni base de datos.

Ejecutar:  python -m pytest tests/test_campo_precio.py
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import campo_precio


def _con_valor(monkeypatch, valor):
    """Hace que config() devuelva `valor`, como si estuviera en el .env."""
    monkeypatch.setattr(campo_precio, "config", lambda k, default=None: valor)


def test_default_es_preciototalext(monkeypatch):
    """Sin CAMPO_PRECIO en el .env, nada cambia para las instalaciones actuales."""
    monkeypatch.delenv("CAMPO_PRECIO", raising=False)
    monkeypatch.setattr(campo_precio, "config", lambda k, default=None: default)
    assert campo_precio.get_campo_precio() == "PRECIOTOTALEXT"


def test_normaliza_minusculas_y_espacios(monkeypatch):
    """Las columnas de DBISAM son mayúsculas: normalizar, no castigar el typo."""
    _con_valor(monkeypatch, "  preciosinimpuesto  ")
    assert campo_precio.get_campo_precio() == "PRECIOSINIMPUESTO"


def test_espacio_interno_es_error(monkeypatch):
    _con_valor(monkeypatch, "PRECIO TOTAL")
    with pytest.raises(ValueError):
        campo_precio.get_campo_precio()


def test_comilla_simple_es_error(monkeypatch):
    """El valor se interpola en SQL: la comilla no puede pasar."""
    _con_valor(monkeypatch, "PRECIOTOTALEXT' OR '1'='1")
    with pytest.raises(ValueError):
        campo_precio.get_campo_precio()


def test_ipreciototal_rechazado_menciona_iva(monkeypatch):
    """Trae el IVA incluido y Validar_Pedido lo sumaría de nuevo."""
    _con_valor(monkeypatch, "IPRECIOTOTAL")
    with pytest.raises(ValueError, match="(?i)iva"):
        campo_precio.get_campo_precio()


def test_ipreciototal_rechazado_tambien_en_minusculas(monkeypatch):
    """El rechazo no se esquiva escribiéndolo distinto: se normaliza antes."""
    _con_valor(monkeypatch, "ipreciototal")
    with pytest.raises(ValueError, match="(?i)iva"):
        campo_precio.get_campo_precio()
