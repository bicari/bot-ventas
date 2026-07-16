"""Contrato con pywa: FlowCompletion expone el token como `.token`, no `.flow_token`.

Este test documenta el bug que dejaba los pedidos sin productos: el handler de
completion leía `flow.flow_token` (inexistente, por `slots=True`), obtenía None y
caía a un fallback sin productos. El carrito real en Redis se indexa por el token,
así que el handler DEBE usar `flow.token`.

Ejecutar con el intérprete del venv (donde está instalado pywa):
    venv/Scripts/python.exe -m pytest tests/test_flow_completion_token.py
"""

import dataclasses

try:
    import pytest
except ModuleNotFoundError:  # ejecución directa sin pytest
    pytest = None

if pytest is not None:
    pywa_types = pytest.importorskip("pywa.types")
else:
    from pywa import types as pywa_types


def test_flowcompletion_usa_token_no_flow_token():
    FlowCompletion = pywa_types.FlowCompletion
    nombres = {f.name for f in dataclasses.fields(FlowCompletion)}
    assert "token" in nombres, "pywa cambió el contrato: ya no existe 'token'"
    assert "flow_token" not in nombres, (
        "FlowCompletion NO tiene 'flow_token'; el handler debe usar 'flow.token'"
    )


if __name__ == "__main__":
    test_flowcompletion_usa_token_no_flow_token()
    print("OK: FlowCompletion expone 'token' (no 'flow_token').")
