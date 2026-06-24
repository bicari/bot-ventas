"""Guard de regresion: ningun TextBody mezcla texto estatico con ${data.x}.

WhatsApp Flows solo resuelve ${data.x} cuando es el valor completo de 'text'.
Ejecutar:  python -m pytest tests/test_pedido_flow_json.py
       o:  python tests/test_pedido_flow_json.py
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RUTA = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "flows", "pedido_flow.json",
)

REF = re.compile(r"\$\{[^}]+\}")


def _cargar():
    with open(RUTA, encoding="utf-8") as fh:
        return json.load(fh)


def _textbodies(flow):
    for screen in flow["screens"]:
        for hijo in screen["layout"]["children"]:
            if hijo.get("type") == "TextBody":
                yield screen["id"], hijo["text"]


def test_ningun_textbody_mezcla_estatico_y_referencia():
    """Si un text contiene ${...}, el text debe ser SOLO esa referencia."""
    for screen_id, texto in _textbodies(_cargar()):
        refs = REF.findall(texto)
        if refs:
            assert texto.strip() == refs[0], (
                f"{screen_id}: '{texto}' mezcla estatico + referencia; "
                f"debe ser solo '{refs[0]}'"
            )


def test_producto_tiene_referencia_pura_de_items_texto():
    textos = [t for sid, t in _textbodies(_cargar()) if sid == "PRODUCTO"]
    assert "${data.items_texto}" in textos, (
        "PRODUCTO debe tener un TextBody con text exactamente '${data.items_texto}'"
    )


if __name__ == "__main__":
    test_ningun_textbody_mezcla_estatico_y_referencia()
    test_producto_tiene_referencia_pura_de_items_texto()
    print("OK: pedido_flow.json sin interpolacion parcial.")
