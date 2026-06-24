"""Guard del selector de sistema en la pantalla CLIENTE del flow.

Ejecutar:  python -m pytest tests/test_pedido_flow_sistema.py
       o:  python tests/test_pedido_flow_sistema.py
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


def _cliente(flow):
    return next(s for s in flow["screens"] if s["id"] == "CLIENTE")


def _radio_sistema(cliente):
    form = next(c for c in cliente["layout"]["children"] if c.get("type") == "Form")
    for hijo in form["children"]:
        if hijo.get("type") == "RadioButtonsGroup" and hijo.get("name") == "sistema":
            return hijo
    return None


def test_selector_sistema_obligatorio_con_ids_a_y_b():
    radio = _radio_sistema(_cliente(_cargar()))
    assert radio is not None, "Falta el RadioButtonsGroup name='sistema' en CLIENTE"
    assert radio.get("required") is True
    ids = {opt["id"] for opt in radio["data-source"]}
    assert ids == {"A", "B"}


def test_payload_select_client_incluye_sistema():
    cliente = _cliente(_cargar())
    footer = next(c for c in cliente["layout"]["children"] if c.get("type") == "Footer")
    payload = footer["on-click-action"]["payload"]
    assert payload.get("sistema") == "${form.sistema}"


if __name__ == "__main__":
    test_selector_sistema_obligatorio_con_ids_a_y_b()
    test_payload_select_client_incluye_sistema()
    print("OK: selector de sistema en CLIENTE.")
