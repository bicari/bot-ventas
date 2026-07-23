"""Pruebas del ruteo de acciones del Flow de pedidos.

Ejecutar:  python -m pytest tests/test_routing.py
       o:  python tests/test_routing.py   (corre las aserciones directamente)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flows.routing import inferir_accion_flow


def test_cliente_submit_sin_action_infiere_select_client():
    """El caso real del bug: Meta borra 'action', llega solo el formulario."""
    data = {"cliente_id": "V6472827", "tipo_precio": "P1"}
    assert inferir_accion_flow(None, "CLIENTE", data) == "select_client"


def test_producto_submit_sin_action_infiere_add_product():
    data = {"codigo": "ABC123", "cantidad": "5"}
    assert inferir_accion_flow(None, "PRODUCTO", data) == "add_product"


def test_action_explicito_se_respeta():
    """Si algún día Meta sí conserva 'action', se honra tal cual."""
    assert inferir_accion_flow("select_client", "CLIENTE", {}) == "select_client"


def test_cliente_sin_datos_es_refresco():
    """Carga inicial / BACK a CLIENTE sin formulario -> None (refrescar)."""
    assert inferir_accion_flow(None, "CLIENTE", {}) is None


def test_producto_sin_datos_es_refresco():
    """BACK a PRODUCTO sin código -> None (refrescar carrito)."""
    assert inferir_accion_flow(None, "PRODUCTO", {}) is None


def test_producto_totalizar_infiere_totalizar():
    assert inferir_accion_flow(None, "PRODUCTO", {"totalizar": "1"}) == "totalizar"


def test_producto_con_codigo_sigue_siendo_add_product():
    data = {"codigo": "ABC123", "cantidad": "5"}
    assert inferir_accion_flow(None, "PRODUCTO", data) == "add_product"


def test_producto_eliminar_infiere_remove_product():
    assert inferir_accion_flow(None, "PRODUCTO", {"eliminar": "ABC123"}) == "remove_product"


def test_producto_codigo_gana_sobre_eliminar():
    """Un submit de add_product nunca trae 'eliminar'; si ambos llegaran,
    add_product tiene prioridad (regla existente primero)."""
    data = {"codigo": "ABC123", "cantidad": "5", "eliminar": "XYZ"}
    assert inferir_accion_flow(None, "PRODUCTO", data) == "add_product"


def test_producto_eliminar_vacio_es_refresco():
    assert inferir_accion_flow(None, "PRODUCTO", {"eliminar": ""}) is None


if __name__ == "__main__":
    test_cliente_submit_sin_action_infiere_select_client()
    test_producto_submit_sin_action_infiere_add_product()
    test_action_explicito_se_respeta()
    test_cliente_sin_datos_es_refresco()
    test_producto_sin_datos_es_refresco()
    test_producto_totalizar_infiere_totalizar()
    test_producto_con_codigo_sigue_siendo_add_product()
    test_producto_eliminar_infiere_remove_product()
    test_producto_codigo_gana_sobre_eliminar()
    test_producto_eliminar_vacio_es_refresco()
    print("OK: todas las pruebas de ruteo pasaron.")
