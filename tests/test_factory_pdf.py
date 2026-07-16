import pytest
from pdf import factory, formato_marluis, formato_ecograsas


def test_default_es_marluis(monkeypatch):
    monkeypatch.delenv("FORMATO_PDF", raising=False)
    monkeypatch.setattr(factory, "config", lambda k, default=None: default)
    assert factory.get_generador_pdf() is formato_marluis.generar


def test_selecciona_ecograsas(monkeypatch):
    monkeypatch.setattr(factory, "config", lambda k, default=None: "ecograsas")
    assert factory.get_generador_pdf() is formato_ecograsas.generar


def test_valor_invalido_lanza_error(monkeypatch):
    monkeypatch.setattr(factory, "config", lambda k, default=None: "inexistente")
    with pytest.raises(ValueError):
        factory.get_generador_pdf()
