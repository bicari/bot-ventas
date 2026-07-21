# Precio libre por ítem en el Flow de pedido — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** El vendedor puede escribir un precio negociado (con o sin IVA) en el formulario de producto del Flow; el sistema lo respeta en carrito, re-validación, PDF e inserciones, aplicando el impuesto real del producto.

**Architecture:** Dos módulos puros nuevos (`handlers/calculo_item.py` unifica la aritmética por ítem duplicada entre `add_product` y `ProductoHandler`; `flows/precio_libre.py` interpreta la entrada del vendedor y devuelve la base sin IVA). El ítem del carrito lleva `precio_manual: True` y `ProductoHandler` respeta esa base en vez de sobreescribirla con el precio de lista. El JSON del Flow suma un campo de precio opcional y un radio "¿incluye IVA?".

**Tech Stack:** Python 3.11 (venv en `.\venv\`), FastAPI + pywa 2.11.0, WhatsApp Flows JSON 6.2, DBISAM vía ODBC, Redis, pytest (instalado en el venv, no declarado en requirements).

**Spec:** `docs/superpowers/specs/2026-07-21-precio-libre-flow-design.md`

## Global Constraints

- Mensajes de error al vendedor en español, con la redacción exacta del spec.
- El formato de pedido por **texto** (`parser/parsear_pedido.py`) NO se toca.
- La fuente de verdad del precio manual es la **base sin IVA**; el impuesto viene siempre fresco de DBISAM.
- Precio manual y descuento % son **excluyentes** (error si llegan ambos). Única validación de monto: `> 0`.
- Coma decimal se normaliza a punto (los vendedores escriben `12,50`), igual que hace hoy `add_product` con cantidad/descuento.
- Tests: scripts standalone con bootstrap `sys.path.insert(0, ...)`, funciones `test_*`, bloque `if __name__ == "__main__"` que imprime `OK: ...`; ejecutables con `python -m pytest tests/<archivo> -v` desde la raíz o como `python tests/<archivo>`.
- Comandos de test se corren desde la raíz del repo con el venv activado (`.\venv\Scripts\Activate.ps1`).
- Commits frecuentes, mensajes en español estilo repo (`feat:`, `fix:`, `test:`, `docs:`), terminados en `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Todo el trabajo va en la rama `feat/precio-libre-flow`, creada desde `feat/campo-precio-configurable` (Task 1, Step 0).

---

### Task 1: `handlers/calculo_item.py` — aritmética por ítem unificada

Hoy la misma matemática vive copiada en `main.py:418-429` (`add_product`) y
`handlers/Validar_Pedido.py:64-74` (`ProductoHandler`). Este módulo puro la
unifica; Tasks 5 y 6 lo consumen.

**Files:**
- Create: `handlers/calculo_item.py`
- Test: `tests/test_calculo_item.py`

**Interfaces:**
- Consumes: nada (módulo puro, sin imports del proyecto).
- Produces: `calcular_item(precio_sin_iva: float, cantidad: float, descuento: float, impuesto: int, peso: float) -> dict` con claves `precio_sin_iva`, `precio`, `precio_con_descuento`, `monto_iva`, `precio_venta`, `subtotal`, `total_sin_dcto`, `peso_item` (todas float redondeadas a 2 decimales). El llamador agrega él mismo `cantidad`, `descuento`, `descripcion`, `impuesto` y (si aplica) `precio_manual`.

- [ ] **Step 0: Crear la rama de trabajo**

```powershell
git checkout -b feat/precio-libre-flow
```

- [ ] **Step 1: Escribir los tests que fallan**

Crear `tests/test_calculo_item.py`:

```python
"""Pruebas de la aritmética por ítem unificada.

Los valores esperados reproducen EXACTAMENTE lo que hoy calculan
add_product (main.py) y ProductoHandler (handlers/Validar_Pedido.py),
incluidos los redondeos a 2 decimales.

Ejecutar:  python -m pytest tests/test_calculo_item.py
       o:  python tests/test_calculo_item.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from handlers.calculo_item import calcular_item


def test_item_16_sin_descuento():
    item = calcular_item(precio_sin_iva=10.0, cantidad=2.0, descuento=0,
                         impuesto=16, peso=1.5)
    assert item == {
        "precio_sin_iva": 10.0,
        "precio": 11.6,
        "precio_con_descuento": 10.0,
        "monto_iva": 1.6,
        "precio_venta": 11.6,
        "subtotal": 20.0,
        "total_sin_dcto": 20.0,
        "peso_item": 3.0,
    }


def test_item_16_con_descuento_10():
    item = calcular_item(precio_sin_iva=10.0, cantidad=2.0, descuento=10,
                         impuesto=16, peso=1.0)
    assert item["precio_con_descuento"] == 9.0
    assert item["monto_iva"] == 1.44          # 9.00 × 0.16
    assert item["precio_venta"] == 10.44      # 9.00 × 1.16
    assert item["subtotal"] == 18.0           # 9.00 × 2
    assert item["total_sin_dcto"] == 20.0     # sin descuento


def test_item_8_por_ciento():
    item = calcular_item(precio_sin_iva=10.0, cantidad=1.0, descuento=0,
                         impuesto=8, peso=0.5)
    assert item["precio"] == 10.8
    assert item["monto_iva"] == 0.8
    assert item["precio_venta"] == 10.8


def test_item_exento():
    item = calcular_item(precio_sin_iva=10.0, cantidad=3.0, descuento=0,
                         impuesto=0, peso=0.0)
    assert item["precio"] == 10.0
    assert item["monto_iva"] == 0.0
    assert item["precio_venta"] == 10.0
    assert item["subtotal"] == 30.0


def test_redondeos_a_dos_decimales():
    item = calcular_item(precio_sin_iva=3.333, cantidad=3.0, descuento=0,
                         impuesto=16, peso=1.0)
    assert item["precio_sin_iva"] == 3.33
    assert item["precio_con_descuento"] == 3.33   # round(3.333, 2)
    assert item["subtotal"] == 9.99               # round(3.33 × 3, 2)


if __name__ == "__main__":
    test_item_16_sin_descuento()
    test_item_16_con_descuento_10()
    test_item_8_por_ciento()
    test_item_exento()
    test_redondeos_a_dos_decimales()
    print("OK: calcular_item.")
```

- [ ] **Step 2: Verificar que fallan**

Run: `python -m pytest tests/test_calculo_item.py -v`
Expected: FAIL en el import — `ModuleNotFoundError: No module named 'handlers.calculo_item'`

- [ ] **Step 3: Implementación mínima**

Crear `handlers/calculo_item.py`:

```python
"""Aritmética por ítem de pedido, unificada.

Antes vivía copiada en main.py (add_product del Flow) y en
handlers/Validar_Pedido.py (ProductoHandler); el spec de CAMPO_PRECIO
(2026-07-16) dejó registrada la deuda y el precio libre la necesita
resuelta: la regla "manual vs lista" no puede vivir en dos sitios.

Puro a propósito: sin BD, sin Redis, sin WhatsApp.
"""


def calcular_item(precio_sin_iva: float, cantidad: float, descuento: float,
                  impuesto: int, peso: float) -> dict:
    """Deriva los montos de un ítem a partir de su precio base sin IVA.

    El llamador agrega por su cuenta cantidad, descuento, descripcion,
    impuesto y precio_manual; aquí solo se calculan los campos derivados.
    """
    precio_con_descuento = round(precio_sin_iva - precio_sin_iva * descuento / 100, 2)
    return {
        "precio_sin_iva": round(precio_sin_iva, 2),
        "precio": round(precio_sin_iva * (impuesto / 100 + 1), 2),
        "precio_con_descuento": precio_con_descuento,
        "monto_iva": round(precio_con_descuento * impuesto / 100, 2),
        "precio_venta": round(precio_con_descuento * (impuesto / 100 + 1), 2),
        "subtotal": round(precio_con_descuento * cantidad, 2),
        "total_sin_dcto": round(precio_sin_iva * cantidad, 2),
        "peso_item": round(cantidad * peso, 2),
    }
```

- [ ] **Step 4: Verificar que pasan**

Run: `python -m pytest tests/test_calculo_item.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```powershell
git add handlers/calculo_item.py tests/test_calculo_item.py
git commit -m "feat: calcular_item unifica la aritmetica por item de pedido"
```

---

### Task 2: `flows/precio_libre.py` — interpretar el precio manual

**Files:**
- Create: `flows/precio_libre.py`
- Test: `tests/test_precio_libre.py`

**Interfaces:**
- Consumes: nada (módulo puro).
- Produces: `resolver_precio_manual(precio_raw, incluye_iva_raw, descuento: float, impuesto: int) -> float | None` — devuelve la base **sin IVA** redondeada a 2 decimales, `None` si el vendedor no escribió precio, o lanza `ValueError` con mensaje para pantalla. `precio_raw` e `incluye_iva_raw` llegan crudos del payload del Flow (str o None); `incluye_iva_raw` vale `"con_iva"`, `"sin_iva"` o vacío.

- [ ] **Step 1: Escribir los tests que fallan**

Crear `tests/test_precio_libre.py`:

```python
"""Pruebas de resolver_precio_manual (precio libre del Flow).

Ejecutar:  python -m pytest tests/test_precio_libre.py
       o:  python tests/test_precio_libre.py
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flows.precio_libre import resolver_precio_manual


def test_sin_precio_devuelve_none():
    assert resolver_precio_manual(None, None, 0, 16) is None
    assert resolver_precio_manual("", None, 0, 16) is None
    assert resolver_precio_manual("   ", None, 0, 16) is None


def test_radio_marcado_sin_precio_se_ignora():
    assert resolver_precio_manual("", "con_iva", 0, 16) is None


def test_sin_iva_devuelve_el_precio_tal_cual():
    assert resolver_precio_manual("12.50", "sin_iva", 0, 16) == 12.5


def test_coma_decimal_aceptada():
    assert resolver_precio_manual("12,50", "sin_iva", 0, 16) == 12.5


def test_con_iva_16_descompone_la_base():
    assert resolver_precio_manual("11.60", "con_iva", 0, 16) == 10.0


def test_con_iva_8_descompone_la_base():
    assert resolver_precio_manual("10.80", "con_iva", 0, 8) == 10.0


def test_con_iva_exento_no_cambia():
    assert resolver_precio_manual("10", "con_iva", 0, 0) == 10.0


def test_no_numerico_es_error():
    with pytest.raises(ValueError, match="no es un número válido"):
        resolver_precio_manual("abc", "sin_iva", 0, 16)


def test_cero_y_negativo_son_error():
    with pytest.raises(ValueError, match="mayor que cero"):
        resolver_precio_manual("0", "sin_iva", 0, 16)
    with pytest.raises(ValueError, match="mayor que cero"):
        resolver_precio_manual("-5", "sin_iva", 0, 16)


def test_precio_y_descuento_son_excluyentes():
    with pytest.raises(ValueError, match="excluyentes"):
        resolver_precio_manual("12.50", "sin_iva", 10, 16)


def test_precio_sin_radio_es_error():
    with pytest.raises(ValueError, match="Indica si el precio incluye IVA"):
        resolver_precio_manual("12.50", None, 0, 16)
    with pytest.raises(ValueError, match="Indica si el precio incluye IVA"):
        resolver_precio_manual("12.50", "", 0, 16)


if __name__ == "__main__":
    test_sin_precio_devuelve_none()
    test_radio_marcado_sin_precio_se_ignora()
    test_sin_iva_devuelve_el_precio_tal_cual()
    test_coma_decimal_aceptada()
    test_con_iva_16_descompone_la_base()
    test_con_iva_8_descompone_la_base()
    test_con_iva_exento_no_cambia()
    test_no_numerico_es_error()
    test_cero_y_negativo_son_error()
    test_precio_y_descuento_son_excluyentes()
    test_precio_sin_radio_es_error()
    print("OK: resolver_precio_manual.")
```

- [ ] **Step 2: Verificar que fallan**

Run: `python -m pytest tests/test_precio_libre.py -v`
Expected: FAIL en el import — `ModuleNotFoundError: No module named 'flows.precio_libre'`

- [ ] **Step 3: Implementación mínima**

Crear `flows/precio_libre.py`:

```python
"""Interpretación del precio libre que el vendedor escribe en el Flow.

Pura a propósito (sin BD/Redis/WhatsApp), siguiendo el patrón de
flows/carrito.py. El impuesto llega como argumento: lo trae fresco la
fila de DBISAM que add_product ya consulta.
"""


def resolver_precio_manual(precio_raw, incluye_iva_raw, descuento: float,
                           impuesto: int):
    """Devuelve la base SIN IVA del precio manual, o None si no hay precio.

    Reglas (en orden): precio vacío -> None (el radio marcado se ignora);
    no numérico, <= 0, o combinado con descuento -> ValueError; radio sin
    elegir -> ValueError; 'con_iva' descompone la base con el impuesto del
    producto, 'sin_iva' toma el número tal cual.
    """
    texto = str(precio_raw or "").strip()
    if not texto:
        return None

    try:
        precio = float(texto.replace(",", "."))
    except ValueError:
        raise ValueError(f"El precio '{texto}' no es un número válido.")
    if precio <= 0:
        raise ValueError("El precio debe ser mayor que cero.")
    if descuento and float(descuento) > 0:
        raise ValueError(
            "El precio manual y el descuento % son excluyentes; usa solo uno.")

    modo = str(incluye_iva_raw or "").strip()
    if modo == "con_iva":
        return round(precio / (1 + impuesto / 100), 2)
    if modo == "sin_iva":
        return round(precio, 2)
    raise ValueError("Indica si el precio incluye IVA.")
```

- [ ] **Step 4: Verificar que pasan**

Run: `python -m pytest tests/test_precio_libre.py -v`
Expected: 11 passed

- [ ] **Step 5: Commit**

```powershell
git add flows/precio_libre.py tests/test_precio_libre.py
git commit -m "feat: resolver_precio_manual interpreta el precio libre del Flow"
```

---

### Task 3: campo de precio y radio en `flows/pedido_flow.json`

**Files:**
- Modify: `flows/pedido_flow.json` (pantalla `PRODUCTO`: `form_producto` líneas 120-145 y payload del Footer líneas 156-167)
- Test: `tests/test_pedido_flow_producto.py` (agregar guards)

**Interfaces:**
- Consumes: nada.
- Produces: el payload de `add_product` incluye `precio` (str, puede venir vacío) y `precio_incluye_iva` (`"con_iva"` | `"sin_iva"` | vacío). Task 6 los lee con `data.get("precio")` y `data.get("precio_incluye_iva")`.

- [ ] **Step 1: Escribir los guards que fallan**

Agregar al final de `tests/test_pedido_flow_producto.py` (antes del bloque `__main__`):

```python
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
```

Y en el bloque `__main__` del mismo archivo, agregar las tres llamadas antes del `print`:

```python
    test_form_tiene_campo_precio_opcional()
    test_form_tiene_radio_incluye_iva()
    test_footer_pasa_precio_y_radio()
```

- [ ] **Step 2: Verificar que fallan**

Run: `python -m pytest tests/test_pedido_flow_producto.py -v`
Expected: 4 passed (los guards viejos), 3 failed — los nuevos, con `AssertionError: Falta el TextInput 'precio' ...` etc.

- [ ] **Step 3: Editar el JSON**

En `flows/pedido_flow.json`, dentro de `form_producto`, después del TextInput de `descuento` (línea 137-143) agregar dos componentes:

```json
              {
                "type": "TextInput",
                "label": "Precio (opcional)",
                "name": "precio",
                "input-type": "number",
                "required": false
              },
              {
                "type": "RadioButtonsGroup",
                "label": "¿El precio incluye IVA?",
                "name": "precio_incluye_iva",
                "required": false,
                "data-source": [
                  { "id": "con_iva", "title": "Sí, IVA incluido" },
                  { "id": "sin_iva", "title": "No, es precio base" }
                ]
              }
```

Y en el payload del Footer "Agregar Producto" (línea 160-165) agregar las dos claves:

```json
              "payload": {
                "action":    "add_product",
                "codigo":    "${form.codigo}",
                "cantidad":  "${form.cantidad}",
                "descuento": "${form.descuento}",
                "precio":    "${form.precio}",
                "precio_incluye_iva": "${form.precio_incluye_iva}"
              }
```

- [ ] **Step 4: Verificar que pasan (incluidos los guards viejos)**

Run: `python -m pytest tests/test_pedido_flow_producto.py tests/test_pedido_flow_json.py -v`
Expected: todos passed (7 del primero, 2 del segundo). El segundo archivo protege contra interpolación parcial en TextBody; no debe romperse.

- [ ] **Step 5: Commit**

```powershell
git add flows/pedido_flow.json tests/test_pedido_flow_producto.py
git commit -m "feat: campo de precio opcional y radio de IVA en el Flow de pedido"
```

---

### Task 4: marcador ✏️ en el carrito (`flows/carrito.py`)

**Files:**
- Modify: `flows/carrito.py:27-31` (`formato_carrito`)
- Test: `tests/test_carrito.py` (agregar 2 tests)

**Interfaces:**
- Consumes: ítems del carrito; si un ítem tiene `precio_manual` truthy, lleva marcador.
- Produces: línea de carrito `• {cod} × {cant} ✏️ = ${subtotal}` para ítems manuales; el resto sin cambio.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar a `tests/test_carrito.py` (antes del bloque `__main__`):

```python
def test_item_con_precio_manual_lleva_marcador():
    c = _carrito(ABC123={"cantidad": 5, "descuento": 0, "subtotal": 62.5,
                         "precio_manual": True})
    assert formato_carrito(c) == "• ABC123 × 5 ✏️ = $62.50"


def test_item_sin_precio_manual_no_lleva_marcador():
    c = _carrito(ABC123={"cantidad": 5, "descuento": 0, "subtotal": 62.5,
                         "precio_manual": False})
    assert formato_carrito(c) == "• ABC123 × 5 = $62.50"
```

Y en el bloque `__main__`, agregar las dos llamadas antes del `print`:

```python
    test_item_con_precio_manual_lleva_marcador()
    test_item_sin_precio_manual_no_lleva_marcador()
```

- [ ] **Step 2: Verificar que fallan**

Run: `python -m pytest tests/test_carrito.py -v`
Expected: 11 passed, 1 failed — `test_item_con_precio_manual_lleva_marcador` con diff `'• ABC123 × 5 = $62.50' != '• ABC123 × 5 ✏️ = $62.50'` (el test "sin marcador" pasa desde ya: hoy nunca hay marcador).

- [ ] **Step 3: Implementación mínima**

En `flows/carrito.py`, reemplazar el bucle de líneas (27-31):

```python
    lineas = []
    for cod, p in prods.items():
        desc_str = f" (-{p['descuento']}%)" if p.get("descuento") else ""
        manual_str = " ✏️" if p.get("precio_manual") else ""
        lineas.append(f"• {cod} × {p['cantidad']}{desc_str}{manual_str} = ${p['subtotal']:.2f}")
    cuerpo = "\n".join(lineas)
```

- [ ] **Step 4: Verificar que pasan**

Run: `python -m pytest tests/test_carrito.py -v`
Expected: 12 passed

- [ ] **Step 5: Commit**

```powershell
git add flows/carrito.py tests/test_carrito.py
git commit -m "feat: marcador de precio manual en el texto del carrito"
```

---

### Task 5: `ProductoHandler` respeta el precio manual

**Files:**
- Modify: `handlers/Validar_Pedido.py:1-4` (import) y `:60-75` (bucle por producto)
- Test: `tests/test_producto_handler_codigos.py` (agregar helper y 3 tests)

**Interfaces:**
- Consumes: `calcular_item` de Task 1. Ítems del pedido: si traen `precio_manual` truthy, su `precio_sin_iva` es la base a usar.
- Produces: contrato externo intacto — `ProductoHandler.handle(pedido, user_id)` devuelve el pedido con los mismos campos por ítem y totales que hoy. Regla nueva: con `precio_manual`, el precio de lista (incluso 0) no bloquea ni pisa.

- [ ] **Step 1: Escribir los tests que fallan**

En `tests/test_producto_handler_codigos.py`, agregar después de `_pedido_con` (la clase `_FakeDB` existente no se toca):

```python
import pytest


def _fake_db(precio):
    """FakeDB con precio de lista configurable."""
    class _DB:
        def consultar_precios(self, productos, tipo_precio):
            filas = {c: (c, 16, precio, f"PRODUCTO {c}", 1.0, c) for c in productos}
            return filas, []
    return _DB


def _handle_con_db(db_cls, pedido):
    original = vp.DBISAMDatabase
    vp.DBISAMDatabase = db_cls
    try:
        return vp.ProductoHandler().handle(pedido, user_id="584140000000")
    finally:
        vp.DBISAMDatabase = original


def test_handle_respeta_precio_manual():
    """La BD dice 10.0 pero el vendedor negoció 8.0: gana el manual."""
    pedido = _pedido_con(["01010024"])
    pedido["productos"]["01010024"].update(
        {"precio_manual": True, "precio_sin_iva": 8.0})

    resultado = _handle_con_db(_fake_db(10.0), pedido)

    p = resultado["productos"]["01010024"]
    assert p["precio_sin_iva"] == 8.0
    assert p["subtotal"] == 16.0        # 8.0 × 2
    assert p["precio_venta"] == 9.28    # 8.0 × 1.16
    assert resultado["base_16"] == 16.0
    assert resultado["iva_16"] == 2.56
    assert resultado["total_neto"] == 18.56


def test_handle_lista_en_cero_con_manual_pasa():
    """Con precio manual, el precio de lista en 0 no bloquea."""
    pedido = _pedido_con(["01010024"])
    pedido["productos"]["01010024"].update(
        {"precio_manual": True, "precio_sin_iva": 8.0})

    resultado = _handle_con_db(_fake_db(0.0), pedido)

    assert resultado["productos"]["01010024"]["subtotal"] == 16.0


def test_handle_lista_en_cero_sin_manual_sigue_fallando():
    """La regla actual para precios de lista <= 0 queda intacta."""
    with pytest.raises(ValueError, match="menor o igual a cero"):
        _handle_con_db(_fake_db(0.0), _pedido_con(["01010024"]))
```

Y en el bloque `__main__`, agregar las tres llamadas antes del `print`:

```python
    test_handle_respeta_precio_manual()
    test_handle_lista_en_cero_con_manual_pasa()
    test_handle_lista_en_cero_sin_manual_sigue_fallando()
```

- [ ] **Step 2: Verificar que fallan**

Run: `python -m pytest tests/test_producto_handler_codigos.py -v`
Expected: 2 passed (el de regresión existente y `test_handle_lista_en_cero_sin_manual_sigue_fallando`, porque esa regla ya existe), 2 failed: en `test_handle_respeta_precio_manual` la BD pisa el manual (`assert p["precio_sin_iva"] == 8.0` falla con 10.0), y `test_handle_lista_en_cero_con_manual_pasa` revienta con el ValueError de precio ≤ 0.

- [ ] **Step 3: Implementación**

En `handlers/Validar_Pedido.py`, agregar el import (después de la línea 3):

```python
from handlers.calculo_item import calcular_item
```

Reemplazar el bucle de cálculo por producto (líneas 60-75, desde `print('Productos encontrados')` hasta el `else: raise ValueError(...)` inclusive) por:

```python
            print('Productos encontrados')
            for codigo_original, query in query_products.items():
                codigo, impuesto, precio, descripcion, peso, _ = query
                item = pedido["productos"].get(codigo)
                manual = bool(item and item.get("precio_manual"))
                if item is not None and (manual or precio > 0):
                    # Con precio manual, la base la puso el vendedor y la lista
                    # no la pisa; impuesto/descripción/peso van siempre frescos.
                    precio_item = item["precio_sin_iva"] if manual else precio
                    item["descripcion"] = descripcion
                    item["impuesto"] = impuesto
                    item.update(calcular_item(precio_item, item["cantidad"],
                                              item["descuento"], impuesto, peso))
                else: raise ValueError(f"El producto `{codigo}` tiene un precio menor o igual a cero, por favor verifique.")
```

- [ ] **Step 4: Verificar que pasan, y que nada más se rompió**

Run: `python -m pytest tests/test_producto_handler_codigos.py tests/test_calculo_item.py -v`
Expected: todos passed.

Run: `python -m pytest tests/ -v`
Expected: misma línea base que antes de la feature — el único fallo tolerado es el preexistente `test_campo_precio.py::test_default_es_preciototalext` (causado por un cambio local sin commitear del usuario en `database/campo_precio.py`, ajeno a este plan).

- [ ] **Step 5: Commit**

```powershell
git add handlers/Validar_Pedido.py tests/test_producto_handler_codigos.py
git commit -m "feat: ProductoHandler respeta el precio manual del vendedor"
```

---

### Task 6: cablear `add_product` en `main.py` y verificación final

**Files:**
- Modify: `main.py:21` (imports) y `main.py:398-438` (acción `add_product`)

**Interfaces:**
- Consumes: `resolver_precio_manual` (Task 2), `calcular_item` (Task 1), payload con `precio` / `precio_incluye_iva` (Task 3). El marcador del carrito (Task 4) y la re-validación (Task 5) actúan solos al guardar `precio_manual: True`.
- Produces: ítems del carrito en Redis con la forma que consumen Tasks 4 y 5.

`main.py` no tiene arnés de tests (importa el cliente WhatsApp, Redis y DBISAM
al cargar); toda la lógica nueva ya quedó probada pura en Tasks 1-5. Aquí solo
se cablea y se verifica con la suite completa + smoke de importación.

- [ ] **Step 1: Agregar imports**

En `main.py`, después de la línea 21 (`from flows.carrito import data_producto`):

```python
from flows.precio_libre import resolver_precio_manual
from handlers.calculo_item import calcular_item
```

- [ ] **Step 2: Reescribir la acción `add_product`**

En `main.py`, el bloque actual (líneas 399-438 antes de este cambio) es:

```python
    if action == "add_product":
        codigo        = (data.get("codigo") or "").strip().upper()
        cantidad_raw  = str(data.get("cantidad") or "0").replace(",", ".")
        descuento_raw = str(data.get("descuento") or "0").replace(",", ".")

        try:
            cantidad  = float(cantidad_raw)
            descuento = float(descuento_raw)
            if cantidad <= 0:
                raise ValueError("La cantidad debe ser mayor que cero.")
        except ValueError as exc:
            return req.respond(screen="PRODUCTO", data=data_producto(carrito, error=str(exc)))

        try:
            prods_query, not_found = db.consultar_precios([codigo], carrito.get("tipo_precio", "P1"))
            if not_found:
                raise ValueError(f"Producto '{codigo}' no encontrado o inactivo.")
            row = prods_query[codigo]
            fi_codigo, impuesto, precio, descripcion, peso, _ = row
            precio_con_desc = round(precio - precio * descuento / 100, 2)
            monto_iva       = round(precio_con_desc * impuesto / 100, 2)
            carrito["productos"][fi_codigo] = {
                "cantidad": cantidad, "descuento": descuento,
                "descripcion": descripcion, "impuesto": impuesto,
                "precio_sin_iva": precio,
                "precio_con_descuento": precio_con_desc,
                "monto_iva": monto_iva,
                "precio_venta": round(precio_con_desc * (impuesto / 100 + 1), 2),
                "subtotal": round(precio_con_desc * cantidad, 2),
                "total_sin_dcto": round(precio * cantidad, 2),
                "peso_item": round(cantidad * peso, 2),
            }
            redis_cache.guardar_carrito(req.flow_token, carrito)
        except Exception as exc:
            return req.respond(screen="PRODUCTO", data=data_producto(carrito, error=str(exc)))

        return req.respond(
            screen="PRODUCTO",
            data=data_producto(carrito, agregado=f"{fi_codigo} × {cantidad}"),
        )
```

Reemplazarlo por:

```python
    if action == "add_product":
        codigo        = (data.get("codigo") or "").strip().upper()
        cantidad_raw  = str(data.get("cantidad") or "0").replace(",", ".")
        descuento_raw = str(data.get("descuento") or "0").replace(",", ".")

        try:
            cantidad  = float(cantidad_raw)
            descuento = float(descuento_raw)
            if cantidad <= 0:
                raise ValueError("La cantidad debe ser mayor que cero.")
        except ValueError as exc:
            return req.respond(screen="PRODUCTO", data=data_producto(carrito, error=str(exc)))

        try:
            prods_query, not_found = db.consultar_precios([codigo], carrito.get("tipo_precio", "P1"))
            if not_found:
                raise ValueError(f"Producto '{codigo}' no encontrado o inactivo.")
            row = prods_query[codigo]
            fi_codigo, impuesto, precio, descripcion, peso, _ = row
            base_manual = resolver_precio_manual(
                data.get("precio"), data.get("precio_incluye_iva"),
                descuento, impuesto)
            if base_manual is not None:
                descuento = 0
            item = {
                "cantidad": cantidad, "descuento": descuento,
                "descripcion": descripcion, "impuesto": impuesto,
            }
            if base_manual is not None:
                item["precio_manual"] = True
            item.update(calcular_item(
                base_manual if base_manual is not None else precio,
                cantidad, descuento, impuesto, peso))
            carrito["productos"][fi_codigo] = item
            redis_cache.guardar_carrito(req.flow_token, carrito)
        except Exception as exc:
            return req.respond(screen="PRODUCTO", data=data_producto(carrito, error=str(exc)))

        return req.respond(
            screen="PRODUCTO",
            data=data_producto(carrito, agregado=f"{fi_codigo} × {cantidad}"),
        )
```

Notas del reemplazo:
- `resolver_precio_manual` va **dentro** del `try` que responde errores en
  pantalla: sus `ValueError` (excluyente, sin radio, ≤ 0, no numérico) se
  muestran igual que "producto no encontrado".
- Se llama después de tener la fila para pasarle el `impuesto` fresco.
- `descuento = 0` con precio manual: el ítem queda coherente para Task 4
  (sin `(-X%)` en el carrito) y Task 5 (base = precio_con_descuento).

- [ ] **Step 3: Smoke de importación y suite completa**

Run: `python -c "import ast; ast.parse(open('main.py', encoding='utf-8').read()); print('main.py OK')"`
Expected: `main.py OK` (main.py no puede importarse sin Redis/DBISAM vivos; con sintaxis validada, los módulos nuevos ya están probados por su cuenta).

Run: `python -m pytest tests/ -v`
Expected: misma línea base que al final de Task 5 (solo el fallo preexistente de `test_campo_precio.py`).

- [ ] **Step 4: Commit**

```powershell
git add main.py
git commit -m "feat: precio libre por item en add_product del Flow de pedido"
```

- [ ] **Step 5: Verificación manual (requiere el entorno real)**

1. Republicar `flows/pedido_flow.json` en Meta Flow Builder sobre el flow
   `FLOW_ID_PEDIDO` — **misma WABA del teléfono** (si no, error 131009).
2. Arrancar el servidor (`uvicorn main:fastapi_app --reload --host 0.0.0.0 --port 8000`)
   con Redis corriendo en `localhost:2576`.
3. Desde WhatsApp, armar un pedido con tres ítems: uno sin precio (lista),
   uno con precio "No, es precio base" y uno con precio "Sí, IVA incluido".
4. Comprobar: el carrito marca ✏️ los dos manuales; probar los errores
   (precio + descuento a la vez → mensaje de excluyentes; precio sin radio →
   "Indica si el precio incluye IVA").
5. Totalizar, confirmar, y verificar que el resumen, el PDF preliminar, el
   PDF final y los registros en PostgreSQL/DBISAM traen los precios manuales
   con sus bases e IVA correctos.
