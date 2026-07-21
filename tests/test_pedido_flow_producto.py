"""Guard del boton Totalizar y la eliminacion de es_ultimo en PRODUCTO.

Ejecutar:  python -m pytest tests/test_pedido_flow_producto.py
       o:  python tests/test_pedido_flow_producto.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RUTA = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "flows", "pedido_flow.json",
)


def _cargar():
    with open(RUTA, encoding="utf-8") as fh:
        return json.load(fh)


def _producto(flow):
    return next(s for s in flow["screens"] if s["id"] == "PRODUCTO")


def _hijos(producto):
    return producto["layout"]["children"]


def test_producto_declara_tiene_items():
    prod = _producto(_cargar())
    assert prod["data"].get("tiene_items", {}).get("type") == "boolean"


def test_embedded_link_totalizar_condicional():
    link = next(
        (c for c in _hijos(_producto(_cargar()))
         if c.get("type") == "EmbeddedLink" and c.get("text") == "Totalizar pedido"),
        None,
    )
    assert link is not None, "Falta el EmbeddedLink 'Totalizar pedido'"
    assert link.get("visible") == "${data.tiene_items}"
    assert link["on-click-action"]["name"] == "data_exchange"
    assert link["on-click-action"]["payload"].get("totalizar") == "1"


def test_no_existe_checkbox_es_ultimo():
    prod = _producto(_cargar())
    form = next(c for c in _hijos(prod) if c.get("type") == "Form")
    nombres = {h.get("name") for h in form["children"]}
    assert "es_ultimo" not in nombres


def test_footer_sin_es_ultimo():
    prod = _producto(_cargar())
    footer = next(c for c in _hijos(prod) if c.get("type") == "Footer")
    assert "es_ultimo" not in footer["on-click-action"]["payload"]


def _form(prod):
    return next(c for c in _hijos(prod) if c.get("type") == "Form")


def test_form_tiene_campo_precio_opcional():
    form = _form(_producto(_cargar()))
    precio = next((h for h in form["children"] if h.get("name") == "precio"), None)
    assert precio is not None, "Falta el TextInput 'precio' en form_producto"
    assert precio["type"] == "TextInput"
    assert precio["input-type"] == "number"
    assert precio["required"] is False


def test_form_tiene_radio_incluye_iva():
    form = _form(_producto(_cargar()))
    radio = next((h for h in form["children"]
                  if h.get("name") == "precio_incluye_iva"), None)
    assert radio is not None, "Falta el RadioButtonsGroup 'precio_incluye_iva'"
    assert radio["type"] == "RadioButtonsGroup"
    assert radio["required"] is False
    assert [o["id"] for o in radio["data-source"]] == ["con_iva", "sin_iva"]


def test_footer_pasa_precio_y_radio():
    footer = next(c for c in _hijos(_producto(_cargar()))
                  if c.get("type") == "Footer")
    payload = footer["on-click-action"]["payload"]
    assert payload.get("precio") == "${form.precio}"
    assert payload.get("precio_incluye_iva") == "${form.precio_incluye_iva}"


if __name__ == "__main__":
    test_producto_declara_tiene_items()
    test_embedded_link_totalizar_condicional()
    test_no_existe_checkbox_es_ultimo()
    test_footer_sin_es_ultimo()
    test_form_tiene_campo_precio_opcional()
    test_form_tiene_radio_incluye_iva()
    test_footer_pasa_precio_y_radio()
    print("OK: boton Totalizar en PRODUCTO.")
