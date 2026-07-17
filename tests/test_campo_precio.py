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


# Columnas de A2INVCOSTOSPRECIOS tal como las devuelve el esquema real.
# Incluye las que NO son precios (TIPOROUND, PORCENTUTILIDAD, IMTOIMPUESTO01):
# comparten el prefijo FIC_P01 pero no son variantes de precio, y ofrecerlas
# como opcion mandaria a cotizar con basura.
COLUMNAS_REALES = {
    "FIC_CODEITEM",
    "FIC_P01PRECIOSINIMPUESTO", "FIC_P01IPRECIOTOTAL", "FIC_P01PRECIOTOTALEXT",
    "FIC_P02PRECIOSINIMPUESTO", "FIC_P02IPRECIOTOTAL", "FIC_P02PRECIOTOTALEXT",
    "FIC_P03PRECIOSINIMPUESTO", "FIC_P03IPRECIOTOTAL", "FIC_P03PRECIOTOTALEXT",
    "FIC_P01TIPOROUND", "FIC_P01PORCENTUTILIDAD", "FIC_P01IMTOIMPUESTO01",
    "FIC_P01UTILIDAD", "FIC_P01UTILIDADEXT",
}


def test_campo_valido_en_los_tres_tiers_pasa():
    assert campo_precio.validar_campo_precio("PRECIOTOTALEXT", COLUMNAS_REALES) is None


def test_campo_inexistente_es_error():
    with pytest.raises(ValueError):
        campo_precio.validar_campo_precio("PRECIOTOTALEX", COLUMNAS_REALES)


def test_error_lista_las_variantes_no_las_columnas_crudas():
    """El mensaje debe ser accionable: las variantes, no las ~30 columnas."""
    with pytest.raises(ValueError) as exc:
        campo_precio.validar_campo_precio("NOEXISTE", COLUMNAS_REALES)
    mensaje = str(exc.value)
    assert "PRECIOTOTALEXT" in mensaje
    assert "PRECIOSINIMPUESTO" in mensaje
    assert "FIC_CODEITEM" not in mensaje  # no vuelca columnas que no son variantes


def test_las_variantes_sugeridas_no_incluyen_ipreciototal():
    """No sugerir la única columna que get_campo_precio rechaza.

    Existe en el esquema, pero mandaría al usuario derecho al IVA doble.
    """
    with pytest.raises(ValueError) as exc:
        campo_precio.validar_campo_precio("NOEXISTE", COLUMNAS_REALES)
    assert "IPRECIOTOTAL" not in str(exc.value)


def test_las_variantes_sugeridas_solo_incluyen_columnas_de_precio():
    """El prefijo FIC_P01 lo comparten columnas que no son precios.

    TIPOROUND, PORCENTUTILIDAD e IMTOIMPUESTO01 existen y pasarian la
    validacion de existencia, pero cotizarian con basura: no sugerirlas.
    """
    with pytest.raises(ValueError) as exc:
        campo_precio.validar_campo_precio("NOEXISTE", COLUMNAS_REALES)
    mensaje = str(exc.value)
    assert "TIPOROUND" not in mensaje
    assert "PORCENTUTILIDAD" not in mensaje
    assert "IMTOIMPUESTO01" not in mensaje
    assert "UTILIDAD" not in mensaje


def test_falta_en_un_tier_es_error():
    """Si existe para P01 pero no para P03, se sabe al arrancar y no cuando
    un vendedor pida P3."""
    columnas = COLUMNAS_REALES - {"FIC_P03PRECIOTOTALEXT"}
    with pytest.raises(ValueError, match="FIC_P03PRECIOTOTALEXT"):
        campo_precio.validar_campo_precio("PRECIOTOTALEXT", columnas)
