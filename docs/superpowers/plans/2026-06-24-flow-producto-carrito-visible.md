# Carrito visible en pantalla PRODUCTO — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que la pantalla PRODUCTO del Flow muestre el carrito al agregar productos, convirtiendo el binding incrustado en una referencia pura y añadiendo una confirmación "✅ Agregado: …".

**Architecture:** El bug es de WhatsApp Flows: `${data.x}` solo se resuelve si es el valor completo de `text`. Se divide el `TextBody` del carrito en dos (estático + referencia pura) en el flow, y se extrae el formateo del carrito de `main.py` a un módulo puro `flows/carrito.py` (mismo patrón que `flows/routing.py`) para poder testearlo y añadir la línea de confirmación.

**Tech Stack:** Python 3, FastAPI, pywa, pytest (`python -m pytest`), WhatsApp Flows JSON 6.2.

## Global Constraints

- No modificar la **estructura del flow**: pantallas (CLIENTE/PRODUCTO/RESUMEN), `routing_model`, formularios, footers y `on-click-action` se mantienen idénticos.
- El bloque `data` de PRODUCTO ya declara `items_texto`/`error`/`show_error`: **no se toca**.
- `${data.x}` debe ser **el valor completo** de `text` (referencia pura), nunca incrustado en texto estático.
- Tests siguen el patrón de `tests/test_routing.py`: `sys.path.insert(0, ...)` al raíz + bloque `if __name__ == "__main__"`.
- Mensaje "Sin productos agregados aún." (con tilde) se mantiene textual.
- El JSON corregido debe subirse **manualmente** a Meta Flow Builder (paso de despliegue, no de código).

---

### Task 1: Corregir el TextBody del carrito en `flows/pedido_flow.json` + guard de regresión

**Files:**
- Modify: `flows/pedido_flow.json` (pantalla PRODUCTO, `layout.children`, líneas 91-94)
- Test: `tests/test_pedido_flow_json.py`

**Interfaces:**
- Consumes: nada.
- Produces: `flows/pedido_flow.json` con un `TextBody` cuyo `text` es exactamente `"${data.items_texto}"` (referencia pura) en la pantalla PRODUCTO.

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/test_pedido_flow_json.py`:

```python
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
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_pedido_flow_json.py -v`
Expected: FALLA — `test_ningun_textbody_mezcla_estatico_y_referencia` y `test_producto_tiene_referencia_pura_de_items_texto` fallan porque hoy el text es `"Carrito:\n${data.items_texto}"` (mezcla).

- [ ] **Step 3: Aplicar el cambio mínimo en el JSON**

En `flows/pedido_flow.json`, dentro de la pantalla PRODUCTO, reemplazar el primer `TextBody` del `layout.children`:

```json
          {
            "type": "TextBody",
            "text": "Carrito:\n${data.items_texto}"
          },
```

por dos componentes:

```json
          {
            "type": "TextBody",
            "text": "Carrito:"
          },
          {
            "type": "TextBody",
            "text": "${data.items_texto}"
          },
```

No tocar el `data`, ni el segundo `TextBody` (`${data.error}`), ni el `Form`, ni el `Footer`.

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `python -m pytest tests/test_pedido_flow_json.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Verificar que el JSON sigue siendo válido**

Run: `python -c "import json; json.load(open('flows/pedido_flow.json', encoding='utf-8')); print('JSON OK')"`
Expected: `JSON OK`

- [ ] **Step 6: Commit**

```bash
git add flows/pedido_flow.json tests/test_pedido_flow_json.py
git commit -m "fix: carrito de PRODUCTO usa referencia pura (interpolacion parcial no resuelve en Flows)"
```

---

### Task 2: Extraer el formateo del carrito a `flows/carrito.py` con confirmación

**Files:**
- Create: `flows/carrito.py`
- Test: `tests/test_carrito.py`

**Interfaces:**
- Consumes: nada (función pura sobre el dict `carrito`).
- Produces: `formato_carrito(carrito: dict, agregado: str | None = None) -> str`.
  - Sin productos → `"Sin productos agregados aún."`.
  - Con productos → una línea por producto: `"• {codigo} × {cantidad}{desc} = ${subtotal:.2f}"` donde `{desc}` es `" (-{descuento}%)"` si hay descuento, si no `""`.
  - Si `agregado` no es `None` y hay productos → antepone `"✅ Agregado: {agregado}\n\n"` al listado.

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/test_carrito.py`:

```python
"""Pruebas del formateo del texto de carrito de la pantalla PRODUCTO.

Ejecutar:  python -m pytest tests/test_carrito.py
       o:  python tests/test_carrito.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flows.carrito import formato_carrito


def _carrito(**prods):
    return {"productos": prods}


def test_sin_productos():
    assert formato_carrito({"productos": {}}) == "Sin productos agregados aún."


def test_un_producto_sin_descuento():
    c = _carrito(ABC123={"cantidad": 5, "descuento": 0, "subtotal": 1250.0})
    assert formato_carrito(c) == "• ABC123 × 5 = $1250.00"


def test_un_producto_con_descuento():
    c = _carrito(ABC123={"cantidad": 2, "descuento": 10, "subtotal": 480.0})
    assert formato_carrito(c) == "• ABC123 × 2 (-10%) = $480.00"


def test_varios_productos_en_orden():
    c = _carrito(
        ABC123={"cantidad": 1, "descuento": 0, "subtotal": 10.0},
        XYZ={"cantidad": 3, "descuento": 0, "subtotal": 30.0},
    )
    assert formato_carrito(c) == "• ABC123 × 1 = $10.00\n• XYZ × 3 = $30.00"


def test_confirmacion_antepuesta():
    c = _carrito(ABC123={"cantidad": 5, "descuento": 0, "subtotal": 1250.0})
    out = formato_carrito(c, agregado="ABC123 × 5")
    assert out == "✅ Agregado: ABC123 × 5\n\n• ABC123 × 5 = $1250.00"


def test_confirmacion_no_se_muestra_sin_productos():
    assert formato_carrito({"productos": {}}, agregado="X") == "Sin productos agregados aún."


if __name__ == "__main__":
    test_sin_productos()
    test_un_producto_sin_descuento()
    test_un_producto_con_descuento()
    test_varios_productos_en_orden()
    test_confirmacion_antepuesta()
    test_confirmacion_no_se_muestra_sin_productos()
    print("OK: formato_carrito.")
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_carrito.py -v`
Expected: FALLA — `ModuleNotFoundError: No module named 'flows.carrito'`.

- [ ] **Step 3: Crear el módulo `flows/carrito.py`**

```python
"""Formateo del texto del carrito que se muestra en la pantalla PRODUCTO.

Extraido de main.py para poder testearlo sin importar el cliente WhatsApp
ni las conexiones a BD/Redis. La pantalla PRODUCTO enlaza este texto con la
referencia pura ${data.items_texto} (WhatsApp Flows no resuelve referencias
incrustadas en texto estatico).
"""

from typing import Optional


def formato_carrito(carrito: dict, agregado: Optional[str] = None) -> str:
    """Genera el texto del carrito.

    Args:
        carrito: dict con clave ``productos`` (dict de codigo -> datos).
        agregado: etiqueta del producto recien agregado (p.ej. ``"ABC123 × 5"``)
            para anteponer una linea de confirmacion; ``None`` para no mostrarla.

    Returns:
        Texto multilinea del carrito, o el mensaje de carrito vacio.
    """
    prods = carrito.get("productos", {})
    if not prods:
        return "Sin productos agregados aún."

    lineas = []
    for cod, p in prods.items():
        desc_str = f" (-{p['descuento']}%)" if p.get("descuento") else ""
        lineas.append(f"• {cod} × {p['cantidad']}{desc_str} = ${p['subtotal']:.2f}")
    cuerpo = "\n".join(lineas)

    if agregado:
        return f"✅ Agregado: {agregado}\n\n{cuerpo}"
    return cuerpo
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `python -m pytest tests/test_carrito.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add flows/carrito.py tests/test_carrito.py
git commit -m "feat: extrae formato_carrito a flows/carrito.py con linea de confirmacion"
```

---

### Task 3: Conectar `main.py` al nuevo módulo y enviar confirmación al agregar

**Files:**
- Modify: `main.py` (import ~línea 20; eliminar `_formato_carrito` líneas 302-311; usos en líneas 391-392, 406-410, 425-426, 452-453, 463-467)

**Interfaces:**
- Consumes: `formato_carrito(carrito, agregado=None)` de `flows/carrito.py` (Task 2).
- Produces: respuestas del endpoint `/flow/pedido` usando `formato_carrito`; la respuesta exitosa de `add_product` pasa `agregado=f"{fi_codigo} × {cantidad}"`.

- [ ] **Step 1: Añadir el import**

En `main.py`, junto a los otros imports de `flows` (después de la línea `from flows.routing import inferir_accion_flow`), añadir:

```python
from flows.carrito import formato_carrito
```

- [ ] **Step 2: Eliminar el helper local `_formato_carrito`**

Borrar de `main.py` la función completa (actualmente líneas 302-311):

```python
def _formato_carrito(carrito: dict) -> str:
    """Genera el texto de carrito que se muestra en la pantalla PRODUCTO."""
    prods = carrito.get("productos", {})
    if not prods:
        return "Sin productos agregados aún."
    lineas = []
    for cod, p in prods.items():
        desc_str = f" (-{p['descuento']}%)" if p.get("descuento") else ""
        lineas.append(f"• {cod} × {p['cantidad']}{desc_str} = ${p['subtotal']:.2f}")
    return "\n".join(lineas)
```

- [ ] **Step 3: Reemplazar los usos en respuestas que NO agregan producto**

En el bloque "sin acción" (refresco de PRODUCTO), cambiar:

```python
        if current_screen == "PRODUCTO":
            return req.respond(screen="PRODUCTO", data={
                "items_texto": _formato_carrito(carrito),
                "error": " ",
                "show_error": False,
            })
```

por:

```python
        if current_screen == "PRODUCTO":
            return req.respond(screen="PRODUCTO", data={
                "items_texto": formato_carrito(carrito),
                "error": " ",
                "show_error": False,
            })
```

En `select_client`, cambiar el literal hardcodeado por la función (DRY; carrito vacío → mismo texto):

```python
        return req.respond(screen="PRODUCTO", data={
            "items_texto": "Sin productos agregados aún.",
            "error": " ",
            "show_error": False,
        })
```

por:

```python
        return req.respond(screen="PRODUCTO", data={
            "items_texto": formato_carrito(carrito),
            "error": " ",
            "show_error": False,
        })
```

En los DOS bloques de error de `add_product` (cantidad inválida y excepción de consulta), cambiar `_formato_carrito(carrito)` por `formato_carrito(carrito)`:

```python
            return req.respond(screen="PRODUCTO", data={
                "items_texto": formato_carrito(carrito),
                "error": f"⚠️ {exc}",
                "show_error": True,
            })
```

- [ ] **Step 4: Enviar la confirmación en la respuesta exitosa de `add_product`**

En la respuesta final de `add_product` (cuando NO es el último producto), cambiar:

```python
        return req.respond(screen="PRODUCTO", data={
            "items_texto": _formato_carrito(carrito),
            "error": " ",
            "show_error": False,
        })
```

por (antepone la confirmación del producto recién agregado):

```python
        return req.respond(screen="PRODUCTO", data={
            "items_texto": formato_carrito(carrito, agregado=f"{fi_codigo} × {cantidad}"),
            "error": " ",
            "show_error": False,
        })
```

`fi_codigo` y `cantidad` ya existen en ese scope (se definieron al construir el producto). No tocar la rama `if es_ultimo:` (navega a RESUMEN).

- [ ] **Step 5: Verificar que no quedan referencias al helper viejo**

Run: `grep -n "_formato_carrito" main.py`
Expected: sin resultados (exit code 1 / ninguna línea).

- [ ] **Step 6: Verificar que `main.py` compila**

Run: `python -m py_compile main.py && echo "COMPILA OK"`
Expected: `COMPILA OK` (sin errores de sintaxis).

- [ ] **Step 7: Correr toda la suite de tests**

Run: `python -m pytest tests/ -v`
Expected: PASS — `test_routing.py`, `test_flow_completion_token.py`, `test_pedido_flow_json.py`, `test_carrito.py` todos verdes.

- [ ] **Step 8: Commit**

```bash
git add main.py
git commit -m "feat: PRODUCTO usa formato_carrito y confirma producto agregado"
```

---

## Despliegue manual (fuera del código)

Tras mergear, el usuario debe **subir el JSON corregido de la pantalla PRODUCTO a Meta Flow Builder** (split del `TextBody` descrito en la Task 1 y en el spec) y **publicar** el flow. Sin este paso, el flow en producción sigue mostrando el literal `${data.items_texto}`. El cambio de `main.py` no requiere republicar el flow.

## Self-Review

- **Cobertura del spec:** Cambio 1 (split TextBody) → Task 1 + Task 3 (repo) + despliegue manual. Cambio 2 (confirmación "✅ Agregado") → Task 2 + Task 3. Causa raíz (referencia pura) → Task 1 con guard de regresión. ✔
- **Placeholders:** ninguno; todos los pasos llevan código y comandos concretos.
- **Consistencia de tipos:** `formato_carrito(carrito: dict, agregado: Optional[str]) -> str` se define en Task 2 y se consume con esa misma firma en Task 3 (`formato_carrito(carrito)` y `formato_carrito(carrito, agregado=...)`). ✔
