# Botón "Totalizar pedido" en PRODUCTO — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Añadir un botón "Totalizar pedido" (visible solo con ≥1 ítem) que lleve de PRODUCTO a RESUMEN, eliminando el checkbox `es_ultimo`.

**Architecture:** El botón es un `EmbeddedLink` con `visible="${data.tiene_items}"` que dispara un `data_exchange` con acción `totalizar`; el servidor calcula totales y responde RESUMEN. Las respuestas de PRODUCTO ganan `tiene_items`, centralizado en un helper puro `data_producto` en `flows/carrito.py`. El ruteo distingue `totalizar` por la presencia de la clave `totalizar` en el payload.

**Tech Stack:** Python 3, FastAPI, pywa, python-decouple, pytest (`python -m pytest`), WhatsApp Flows JSON 6.2.

## Global Constraints

- Una pantalla de WhatsApp Flows admite un solo `Footer`; la segunda acción condicional es un `EmbeddedLink` con `visible` enlazado a datos.
- El `EmbeddedLink` va **fuera** del `Form` (su payload no arrastra campos del formulario); solo envía `totalizar:"1"`.
- WhatsApp descarta el literal `action` del payload; el ruteo se hace por la presencia de claves (`codigo` → add_product, `totalizar` → totalizar).
- `tiene_items = bool(carrito.get("productos"))` en TODAS las respuestas de PRODUCTO.
- `totalizar` con carrito vacío → respuesta PRODUCTO con error, no RESUMEN.
- Se elimina el `CheckboxGroup` `es_ultimo` y toda su lógica.
- `_calcular_totales_y_resumen` no cambia; solo cambia su disparador.
- Tests siguen el patrón de `tests/test_routing.py`: `sys.path.insert(0, ...)` al raíz + bloque `if __name__ == "__main__"`.
- `main.py` no es unit-testable (imports pesados); se verifica con `python -m py_compile` + revisión del call-site.
- Despliegue manual: subir/publicar la pantalla PRODUCTO en Meta Flow Builder.

---

### Task 1: Helper `data_producto` en `flows/carrito.py`

**Files:**
- Modify: `flows/carrito.py` (añadir función `data_producto` + actualizar docstring del módulo)
- Test: `tests/test_carrito.py` (extender)

**Interfaces:**
- Consumes: `formato_carrito(carrito, agregado=None)` (ya existe en el módulo).
- Produces: `data_producto(carrito: dict, error: str | None = None, agregado: str | None = None) -> dict` — devuelve el bloque `data` de la pantalla PRODUCTO con claves `items_texto`, `error`, `show_error`, `tiene_items`. Si `error` es truthy: `error` = `f"⚠️ {error}"`, `show_error` = `True`; si no: `error` = `" "`, `show_error` = `False`. `tiene_items` = `bool(carrito.get("productos"))`.

- [ ] **Step 1: Escribir los tests que fallan**

En `tests/test_carrito.py`, añadir el import y las funciones de test. Cambiar la línea de import existente:

```python
from flows.carrito import formato_carrito
```

por:

```python
from flows.carrito import formato_carrito, data_producto
```

Y añadir estas funciones de test (antes del bloque `if __name__`):

```python
def test_data_producto_vacio():
    d = data_producto({"productos": {}})
    assert d == {
        "items_texto": "Sin productos agregados aún.",
        "error": " ",
        "show_error": False,
        "tiene_items": False,
    }


def test_data_producto_con_items_marca_tiene_items():
    c = _carrito(ABC123={"cantidad": 5, "descuento": 0, "subtotal": 1250.0})
    d = data_producto(c)
    assert d["tiene_items"] is True
    assert d["items_texto"] == "• ABC123 × 5 = $1250.00"
    assert d["show_error"] is False
    assert d["error"] == " "


def test_data_producto_con_error():
    d = data_producto({"productos": {}}, error="Agrega al menos un producto.")
    assert d["error"] == "⚠️ Agrega al menos un producto."
    assert d["show_error"] is True
    assert d["tiene_items"] is False


def test_data_producto_con_agregado():
    c = _carrito(ABC123={"cantidad": 5, "descuento": 0, "subtotal": 1250.0})
    d = data_producto(c, agregado="ABC123 × 5")
    assert d["items_texto"].startswith("✅ Agregado: ABC123 × 5")
    assert d["tiene_items"] is True
```

Y añadir sus llamadas dentro del bloque `if __name__ == "__main__":` (después de las existentes, antes del `print`):

```python
    test_data_producto_vacio()
    test_data_producto_con_items_marca_tiene_items()
    test_data_producto_con_error()
    test_data_producto_con_agregado()
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `python -m pytest tests/test_carrito.py -q`
Expected: FALLA — `ImportError: cannot import name 'data_producto'`.

- [ ] **Step 3: Implementar `data_producto`**

En `flows/carrito.py`, añadir al final del archivo:

```python
def data_producto(carrito: dict, error: str | None = None, agregado: str | None = None) -> dict:
    """Arma el bloque `data` de la pantalla PRODUCTO del Flow.

    Incluye `tiene_items`, que controla la visibilidad del botón "Totalizar".
    """
    return {
        "items_texto": formato_carrito(carrito, agregado=agregado),
        "error": f"⚠️ {error}" if error else " ",
        "show_error": bool(error),
        "tiene_items": bool(carrito.get("productos")),
    }
```

Y actualizar el docstring del módulo (primera línea) para reflejar que ahora también arma la data de la pantalla:

```python
"""Formateo del carrito y armado de la data de la pantalla PRODUCTO del Flow.
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `python -m pytest tests/test_carrito.py -q`
Expected: PASS (10 passed).

- [ ] **Step 5: Commit**

```bash
git add flows/carrito.py tests/test_carrito.py
git commit -m "feat: helper data_producto arma la data de PRODUCTO con tiene_items"
```

---

### Task 2: Acción `totalizar` en el ruteo (`flows/routing.py`)

**Files:**
- Modify: `flows/routing.py` (`inferir_accion_flow`)
- Test: `tests/test_routing.py` (extender)

**Interfaces:**
- Produces: `inferir_accion_flow(accion, pantalla, data)` devuelve `"totalizar"` cuando `pantalla == "PRODUCTO"` y `data` tiene `totalizar` (y no `codigo`). `add_product` sigue detectándose por `codigo`.

- [ ] **Step 1: Escribir los tests que fallan**

En `tests/test_routing.py`, añadir estas funciones de test (antes del bloque `if __name__`):

```python
def test_producto_totalizar_infiere_totalizar():
    assert inferir_accion_flow(None, "PRODUCTO", {"totalizar": "1"}) == "totalizar"


def test_producto_con_codigo_sigue_siendo_add_product():
    data = {"codigo": "ABC123", "cantidad": "5"}
    assert inferir_accion_flow(None, "PRODUCTO", data) == "add_product"
```

Y añadir sus llamadas dentro del `if __name__ == "__main__":`:

```python
    test_producto_totalizar_infiere_totalizar()
    test_producto_con_codigo_sigue_siendo_add_product()
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `python -m pytest tests/test_routing.py -q`
Expected: FALLA — `test_producto_totalizar_infiere_totalizar` falla (hoy devuelve `None`).

- [ ] **Step 3: Implementar la detección de `totalizar`**

En `flows/routing.py`, en `inferir_accion_flow`, después de la línea que detecta `add_product`, añadir la detección de `totalizar`. Reemplazar:

```python
    if pantalla == "PRODUCTO" and data.get("codigo"):
        return "add_product"
    return None
```

por:

```python
    if pantalla == "PRODUCTO" and data.get("codigo"):
        return "add_product"
    if pantalla == "PRODUCTO" and data.get("totalizar"):
        return "totalizar"
    return None
```

Y actualizar el docstring de `Returns:` para mencionar `"totalizar"`:

```python
        ``"select_client"``, ``"add_product"``, ``"totalizar"`` o ``None`` si es un
        refresco/BACK sin datos de formulario que procesar.
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `python -m pytest tests/test_routing.py -q`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add flows/routing.py tests/test_routing.py
git commit -m "feat: ruteo de la accion totalizar en la pantalla PRODUCTO"
```

---

### Task 3: Pantalla PRODUCTO en el flow (`flows/pedido_flow.json`)

**Files:**
- Modify: `flows/pedido_flow.json` (pantalla PRODUCTO: `data`, `Form`, nuevo `EmbeddedLink`, payload del Footer)
- Test: `tests/test_pedido_flow_producto.py`

**Interfaces:**
- Produces: PRODUCTO declara `tiene_items` (boolean) en `data`; tiene un `EmbeddedLink` "Totalizar pedido" con `visible="${data.tiene_items}"` y `on-click-action.name == "data_exchange"` cuyo payload incluye `totalizar`; **sin** `CheckboxGroup` `es_ultimo`; el payload del Footer **sin** `es_ultimo`.

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/test_pedido_flow_producto.py`:

```python
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


if __name__ == "__main__":
    test_producto_declara_tiene_items()
    test_embedded_link_totalizar_condicional()
    test_no_existe_checkbox_es_ultimo()
    test_footer_sin_es_ultimo()
    print("OK: boton Totalizar en PRODUCTO.")
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `python -m pytest tests/test_pedido_flow_producto.py -q`
Expected: FALLA — los 4 tests fallan (falta `tiene_items`, falta el link, y `es_ultimo` aún existe).

- [ ] **Step 3: Declarar `tiene_items` en el `data` de PRODUCTO**

En `flows/pedido_flow.json`, en el `data` de la pantalla PRODUCTO, reemplazar:

```json
        "show_error": {
          "type": "boolean",
          "__example__": false
        }
      },
```

por:

```json
        "show_error": {
          "type": "boolean",
          "__example__": false
        },
        "tiene_items": {
          "type": "boolean",
          "__example__": false
        }
      },
```

- [ ] **Step 4: Quitar el `CheckboxGroup` `es_ultimo` del `Form`**

Reemplazar:

```json
              {
                "type": "TextInput",
                "label": "Descuento %",
                "name": "descuento",
                "input-type": "number",
                "required": false
              },
              {
                "type": "CheckboxGroup",
                "label": "Finalizar pedido",
                "name": "es_ultimo",
                "required": false,
                "data-source": [
                  { "id": "si", "title": "Este es el ultimo producto" }
                ]
              }
            ]
          },
```

por:

```json
              {
                "type": "TextInput",
                "label": "Descuento %",
                "name": "descuento",
                "input-type": "number",
                "required": false
              }
            ]
          },
          {
            "type": "EmbeddedLink",
            "text": "Totalizar pedido",
            "visible": "${data.tiene_items}",
            "on-click-action": {
              "name": "data_exchange",
              "payload": { "action": "totalizar", "totalizar": "1" }
            }
          },
```

(Esto elimina el checkbox y añade el `EmbeddedLink` justo después del `Form`, antes del `Footer`.)

- [ ] **Step 5: Quitar `es_ultimo` del payload del Footer**

Reemplazar:

```json
              "payload": {
                "action":    "add_product",
                "codigo":    "${form.codigo}",
                "cantidad":  "${form.cantidad}",
                "descuento": "${form.descuento}",
                "es_ultimo": "${form.es_ultimo}"
              }
```

por:

```json
              "payload": {
                "action":    "add_product",
                "codigo":    "${form.codigo}",
                "cantidad":  "${form.cantidad}",
                "descuento": "${form.descuento}"
              }
```

- [ ] **Step 6: Verificar JSON válido y guards en verde**

Run: `python -c "import json; json.load(open('flows/pedido_flow.json', encoding='utf-8')); print('JSON OK')"`
Expected: `JSON OK`

Run: `python -m pytest tests/test_pedido_flow_producto.py tests/test_pedido_flow_json.py -q`
Expected: PASS (el guard de interpolación sigue verde porque el texto del EmbeddedLink es estático).

- [ ] **Step 7: Commit**

```bash
git add flows/pedido_flow.json tests/test_pedido_flow_producto.py
git commit -m "feat: boton Totalizar condicional en PRODUCTO, elimina checkbox es_ultimo"
```

---

### Task 4: Servidor — usar `data_producto`, eliminar `es_ultimo`, añadir `totalizar` (`main.py`)

**Files:**
- Modify: `main.py` (`flow_pedido_endpoint`: respuestas de PRODUCTO, bloque `add_product`, nueva rama `totalizar`, import)

**Interfaces:**
- Consumes: `data_producto(carrito, error=None, agregado=None)` (Task 1); acción `"totalizar"` (Task 2).
- Produces: todas las respuestas de PRODUCTO usan `data_producto`; `add_product` ya no maneja `es_ultimo`; nueva rama `totalizar` → RESUMEN.

- [ ] **Step 1: Importar `data_producto`**

En `main.py`, cambiar:

```python
from flows.carrito import formato_carrito
```

por:

```python
from flows.carrito import formato_carrito, data_producto
```

- [ ] **Step 2: Refresco de PRODUCTO usa `data_producto`**

Reemplazar:

```python
        if current_screen == "PRODUCTO":
            return req.respond(screen="PRODUCTO", data={
                "items_texto": formato_carrito(carrito),
                "error": " ",
                "show_error": False,
            })
```

por:

```python
        if current_screen == "PRODUCTO":
            return req.respond(screen="PRODUCTO", data=data_producto(carrito))
```

- [ ] **Step 3: `select_client` usa `data_producto`**

Reemplazar:

```python
        return req.respond(screen="PRODUCTO", data={
            "items_texto": formato_carrito(carrito),
            "error": " ",
            "show_error": False,
        })
```

por:

```python
        return req.respond(screen="PRODUCTO", data=data_producto(carrito))
```

- [ ] **Step 4: Quitar `es_ultimo` y usar `data_producto` en `add_product`**

En el bloque `if action == "add_product":`, eliminar la línea:

```python
        es_ultimo     = bool(data.get("es_ultimo"))
```

Reemplazar el primer bloque de error (cantidad inválida):

```python
        except ValueError as exc:
            return req.respond(screen="PRODUCTO", data={
                "items_texto": formato_carrito(carrito),
                "error": f"⚠️ {exc}",
                "show_error": True,
            })
```

por:

```python
        except ValueError as exc:
            return req.respond(screen="PRODUCTO", data=data_producto(carrito, error=str(exc)))
```

Reemplazar el segundo bloque de error (excepción de consulta):

```python
        except Exception as exc:
            return req.respond(screen="PRODUCTO", data={
                "items_texto": formato_carrito(carrito),
                "error": f"⚠️ {exc}",
                "show_error": True,
            })
```

por:

```python
        except Exception as exc:
            return req.respond(screen="PRODUCTO", data=data_producto(carrito, error=str(exc)))
```

- [ ] **Step 5: Eliminar la rama `es_ultimo` + el `print` de depuración y usar `data_producto` en el éxito**

Reemplazar:

```python
        if es_ultimo:
            resumen_txt, carrito = _calcular_totales_y_resumen(carrito)
            redis_cache.guardar_carrito(req.flow_token, carrito)
            return req.respond(screen="RESUMEN", data={"resumen_texto": resumen_txt})
        print({
            "items_texto": formato_carrito(carrito, agregado=f"{fi_codigo} × {cantidad}"),
            "error": " ",
            "show_error": False,
        })
        return req.respond(screen="PRODUCTO", data={
            "items_texto": formato_carrito(carrito, agregado=f"{fi_codigo} × {cantidad}"),
            "error": " ",
            "show_error": False,
        })
```

por:

```python
        return req.respond(
            screen="PRODUCTO",
            data=data_producto(carrito, agregado=f"{fi_codigo} × {cantidad}"),
        )
```

- [ ] **Step 6: Añadir la rama `totalizar`**

Justo antes de la línea final `return req.respond(screen="CLIENTE", data={}, error_message="Acción desconocida.")`, añadir:

```python
    # ── totalizar: calcular totales y navegar a RESUMEN ───────────────────────
    if action == "totalizar":
        if not carrito.get("productos"):
            return req.respond(
                screen="PRODUCTO",
                data=data_producto(carrito, error="Agrega al menos un producto."),
            )
        resumen_txt, carrito = _calcular_totales_y_resumen(carrito)
        redis_cache.guardar_carrito(req.flow_token, carrito)
        return req.respond(screen="RESUMEN", data={"resumen_texto": resumen_txt})

```

- [ ] **Step 7: Verificar que `main.py` compila y no quedan restos de `es_ultimo`**

Run: `python -m py_compile main.py && echo "COMPILA OK"`
Expected: `COMPILA OK`

Run: `grep -nE 'es_ultimo|formato_carrito\(carrito\)' main.py`
Expected: sin resultados (ni `es_ultimo` ni llamadas directas a `formato_carrito(carrito)` — ya todo pasa por `data_producto`).

Run: `grep -nE 'action == "totalizar"|data_producto' main.py`
Expected: la rama `totalizar` y varios usos de `data_producto`.

- [ ] **Step 8: Correr toda la suite**

Run: `python -m pytest tests/ -q`
Expected: todos en verde (routing, carrito, pedido_flow_json, pedido_flow_sistema, pedido_flow_producto, catalogos, flow_completion_token).

- [ ] **Step 9: Commit**

```bash
git add main.py
git commit -m "feat: PRODUCTO usa data_producto y la accion totalizar; elimina es_ultimo"
```

---

## Despliegue manual (fuera del código)

Subir la pantalla PRODUCTO actualizada a Meta Flow Builder (sin checkbox `es_ultimo`, con el `EmbeddedLink` "Totalizar pedido" y el `data` con `tiene_items`) y **publicar** la nueva versión del flow. Sin esto, el botón no aparece en producción. El cambio de servidor surte efecto al reiniciar.

## Self-Review

- **Cobertura del spec:** EmbeddedLink condicional + quitar es_ultimo + tiene_items en data → Task 3; ruteo `totalizar` → Task 2; servidor (rama totalizar, quitar es_ultimo, tiene_items en respuestas vía helper) → Task 1 (helper) + Task 4 (cableado); manejo de error carrito vacío → Task 4 Step 6 (lógica) + Task 1 (formato error); publicación en Meta → Despliegue manual. ✔
- **Placeholders:** ninguno; todos los pasos llevan código/comandos concretos. ✔
- **Consistencia de tipos:** `data_producto(carrito, error=None, agregado=None) -> dict` definido en Task 1 y consumido en Task 4 con esos mismos nombres de parámetro. Acción `"totalizar"` producida en Task 2 y consumida en Task 4 Step 6. Clave `tiene_items` consistente entre flow (Task 3), helper (Task 1) y data del flow. ✔
