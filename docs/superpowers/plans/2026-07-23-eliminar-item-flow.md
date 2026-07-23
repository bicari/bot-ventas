# Eliminar Items del Carrito en el Flow de Pedido — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir que el vendedor elimine un item cargado por error en la pantalla PRODUCTO del Flow de pedido, con un Dropdown que borra al seleccionar, sin rehacer el pedido.

**Architecture:** Un `Dropdown` "🗑️ Eliminar item" en un `Form` propio de la pantalla PRODUCTO dispara `data_exchange` al seleccionar (`on-select-action`). El servidor infiere la acción `remove_product` por la presencia del campo `eliminar` en el payload (WhatsApp borra el literal `action`), quita el item del carrito en Redis y refresca la pantalla.

**Tech Stack:** WhatsApp Flow JSON 6.2, pywa 2.11.0, FastAPI, Redis, pytest.

**Spec:** `docs/superpowers/specs/2026-07-23-eliminar-item-flow-design.md`

## Global Constraints

- Rama base: `feat/precio-libre-flow` (commit `e4a2734`); trabajar en el worktree `worktree-eliminar-item-flow`.
- WhatsApp borra el literal `action` del payload de `data_exchange`: el ruteo se hace SOLO por pantalla + campos presentes (`flows/routing.py`).
- Referencias `${data.x}` y `${form.x}` deben ser el valor completo del campo (interpolación parcial no soportada — se pinta literal).
- Solo un `Footer` por pantalla (ya lo ocupa "Agregar Producto"); el borrado NO usa Footer.
- Retrocompatibilidad: todos los llamados existentes a `formato_carrito` / `data_producto` deben seguir funcionando sin cambios.
- Los tests corren sin WhatsApp, DBISAM ni Redis reales. Ejecutar con `python -m pytest tests/<archivo> -v`; si pytest no está disponible en el entorno, cada archivo de test también corre directo: `python tests/<archivo>.py`.
- Mensajes de commit en español, estilo del repo (`feat:`, `fix:`, `docs:`), con `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

---

### Task 1: Regla de ruteo `remove_product`

**Files:**
- Modify: `flows/routing.py:16-36`
- Test: `tests/test_routing.py`

**Interfaces:**
- Consumes: `inferir_accion_flow(accion, pantalla, data)` existente.
- Produces: `inferir_accion_flow(None, "PRODUCTO", {"eliminar": "<codigo>"})` → `"remove_product"`. Task 4 depende de este string exacto.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `tests/test_routing.py`, antes del bloque `if __name__`:

```python
def test_producto_eliminar_infiere_remove_product():
    assert inferir_accion_flow(None, "PRODUCTO", {"eliminar": "ABC123"}) == "remove_product"


def test_producto_codigo_gana_sobre_eliminar():
    """Un submit de add_product nunca trae 'eliminar'; si ambos llegaran,
    add_product tiene prioridad (regla existente primero)."""
    data = {"codigo": "ABC123", "cantidad": "5", "eliminar": "XYZ"}
    assert inferir_accion_flow(None, "PRODUCTO", data) == "add_product"


def test_producto_eliminar_vacio_es_refresco():
    assert inferir_accion_flow(None, "PRODUCTO", {"eliminar": ""}) is None
```

Y en el bloque `if __name__ == "__main__":`, antes del `print`:

```python
    test_producto_eliminar_infiere_remove_product()
    test_producto_codigo_gana_sobre_eliminar()
    test_producto_eliminar_vacio_es_refresco()
```

- [ ] **Step 2: Verificar que fallan**

Run: `python -m pytest tests/test_routing.py -v`
Expected: los 3 tests nuevos FAIL (`assert None == 'remove_product'`); los 7 existentes PASS.

- [ ] **Step 3: Implementar la regla**

En `flows/routing.py`, dentro de `inferir_accion_flow`, agregar después de la regla de `totalizar` (línea 35) y antes del `return None`:

```python
    if pantalla == "PRODUCTO" and data.get("eliminar"):
        return "remove_product"
```

Actualizar también el docstring de la función: en la línea de Returns, la lista de acciones queda `"select_client"`, `"add_product"`, `"totalizar"`, `"remove_product"` o `None`.

- [ ] **Step 4: Verificar que pasan**

Run: `python -m pytest tests/test_routing.py -v`
Expected: 10 PASS.

- [ ] **Step 5: Commit**

```bash
git add flows/routing.py tests/test_routing.py
git commit -m "feat: ruteo remove_product al recibir 'eliminar' en PRODUCTO

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: `carrito.py` — confirmación de borrado e `items_eliminar`

**Files:**
- Modify: `flows/carrito.py`
- Test: `tests/test_carrito.py`

**Interfaces:**
- Consumes: `formato_carrito(carrito, agregado=None)` y `data_producto(carrito, error=None, agregado=None)` existentes.
- Produces (Task 4 los usa con estas firmas exactas):
  - `formato_carrito(carrito: dict, agregado: Optional[str] = None, eliminado: Optional[str] = None) -> str`
  - `data_producto(carrito: dict, error: Optional[str] = None, agregado: Optional[str] = None, eliminado: Optional[str] = None) -> dict` — el dict retornado gana la clave `"items_eliminar"`: lista de `{"id": <codigo>, "title": "<codigo> × <cantidad>"}` (vacía sin productos).

- [ ] **Step 1: Escribir los tests que fallan**

Agregar a `tests/test_carrito.py`, antes del bloque `if __name__`:

```python
def test_eliminado_antepuesto():
    c = _carrito(XYZ={"cantidad": 3, "descuento": 0, "subtotal": 30.0})
    out = formato_carrito(c, eliminado="ABC123")
    assert out == "🗑️ Eliminado: ABC123\n\n• XYZ × 3 = $30.00"


def test_eliminado_del_ultimo_item_se_muestra_con_carrito_vacio():
    """A diferencia de 'agregado', borrar el último item deja el carrito
    vacío y la confirmación SÍ debe verse."""
    out = formato_carrito({"productos": {}}, eliminado="ABC123")
    assert out == "🗑️ Eliminado: ABC123\n\nSin productos agregados aún."


def test_data_producto_items_eliminar_vacio():
    d = data_producto({"productos": {}})
    assert d["items_eliminar"] == []


def test_data_producto_items_eliminar_con_items():
    c = _carrito(
        ABC123={"cantidad": 5, "descuento": 0, "subtotal": 1250.0},
        XYZ={"cantidad": 3, "descuento": 0, "subtotal": 30.0},
    )
    d = data_producto(c)
    assert d["items_eliminar"] == [
        {"id": "ABC123", "title": "ABC123 × 5"},
        {"id": "XYZ", "title": "XYZ × 3"},
    ]


def test_data_producto_con_eliminado():
    c = _carrito(XYZ={"cantidad": 3, "descuento": 0, "subtotal": 30.0})
    d = data_producto(c, eliminado="ABC123")
    assert d["items_texto"].startswith("🗑️ Eliminado: ABC123")
    assert d["tiene_items"] is True
```

Y en el bloque `if __name__ == "__main__":`, antes del `print`:

```python
    test_eliminado_antepuesto()
    test_eliminado_del_ultimo_item_se_muestra_con_carrito_vacio()
    test_data_producto_items_eliminar_vacio()
    test_data_producto_items_eliminar_con_items()
    test_data_producto_con_eliminado()
```

- [ ] **Step 2: Verificar que fallan**

Run: `python -m pytest tests/test_carrito.py -v`
Expected: los 5 tests nuevos FAIL (TypeError por kwarg `eliminado` desconocido / KeyError `items_eliminar`); los 15 existentes PASS.

- [ ] **Step 3: Implementar**

Reemplazar `formato_carrito` en `flows/carrito.py` por:

```python
def formato_carrito(
    carrito: dict,
    agregado: Optional[str] = None,
    eliminado: Optional[str] = None,
) -> str:
    """Genera el texto del carrito.

    Args:
        carrito: dict con clave ``productos`` (dict de codigo -> datos).
        agregado: etiqueta del producto recien agregado (p.ej. ``"ABC123 × 5"``)
            para anteponer una linea de confirmacion; ``None`` para no mostrarla.
        eliminado: codigo del producto recien eliminado, para anteponer la
            linea ``🗑️ Eliminado: ...``. A diferencia de ``agregado``, se
            muestra aunque el carrito quede vacio (caso: borrar el ultimo item).

    Returns:
        Texto multilinea del carrito, o el mensaje de carrito vacio.
    """
    prods = carrito.get("productos", {})

    prefijo = ""
    if agregado and prods:
        prefijo = f"✅ Agregado: {agregado}\n\n"
    elif eliminado:
        prefijo = f"🗑️ Eliminado: {eliminado}\n\n"

    if not prods:
        return f"{prefijo}Sin productos agregados aún."

    lineas = []
    for cod, p in prods.items():
        desc_str = f" (-{p['descuento']}%)" if p.get("descuento") else ""
        manual_str = " ✏️" if p.get("precio_manual") else ""
        lineas.append(f"• {cod} × {p['cantidad']}{desc_str}{manual_str} = ${p['subtotal']:.2f}")
    return prefijo + "\n".join(lineas)
```

Y reemplazar `data_producto` por:

```python
def data_producto(
    carrito: dict,
    error: Optional[str] = None,
    agregado: Optional[str] = None,
    eliminado: Optional[str] = None,
) -> dict:
    """Arma el bloque ``data`` de la pantalla PRODUCTO del Flow.

    Incluye ``tiene_items`` (visibilidad de "Totalizar" y del Dropdown de
    borrado) e ``items_eliminar`` (data-source del Dropdown "Eliminar item").
    """
    prods = carrito.get("productos", {})
    return {
        "items_texto": formato_carrito(carrito, agregado=agregado, eliminado=eliminado),
        "error": f"⚠️ {error}" if error else " ",
        "show_error": bool(error),
        "tiene_items": bool(prods),
        "items_eliminar": [
            {"id": cod, "title": f"{cod} × {p['cantidad']}"} for cod, p in prods.items()
        ],
    }
```

Nota: `test_data_producto_vacio` compara el dict completo con `==`; ahora incluye `"items_eliminar": []`, hay que actualizar ese test existente agregando la clave:

```python
def test_data_producto_vacio():
    d = data_producto({"productos": {}})
    assert d == {
        "items_texto": "Sin productos agregados aún.",
        "error": " ",
        "show_error": False,
        "tiene_items": False,
        "items_eliminar": [],
    }
```

- [ ] **Step 4: Verificar que pasan**

Run: `python -m pytest tests/test_carrito.py -v`
Expected: 20 PASS.

- [ ] **Step 5: Commit**

```bash
git add flows/carrito.py tests/test_carrito.py
git commit -m "feat: data del Dropdown de borrado y confirmacion de eliminado en carrito

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Flow JSON — Dropdown "🗑️ Eliminar item" en PRODUCTO

**Files:**
- Modify: `flows/pedido_flow.json` (pantalla PRODUCTO)
- Test: `tests/test_pedido_flow_producto.py`

**Interfaces:**
- Consumes: la clave de data `items_eliminar` que el servidor envía (Task 2).
- Produces: payload `data_exchange` `{"eliminar": "${form.eliminar_item}"}` que el ruteo (Task 1) convierte en `remove_product`.

- [ ] **Step 1: Actualizar helpers de tests y escribir los tests que fallan**

En `tests/test_pedido_flow_producto.py` habrá DOS Forms en PRODUCTO; los helpers que toman "el primer Form" deben seleccionar por nombre.

Reemplazar el helper `_form` (línea 62):

```python
def _form(prod, nombre="form_producto"):
    return next(
        c for c in _hijos(prod)
        if c.get("type") == "Form" and c.get("name") == nombre
    )
```

Reemplazar `test_no_existe_checkbox_es_ultimo` (usaba el primer Form inline):

```python
def test_no_existe_checkbox_es_ultimo():
    form = _form(_producto(_cargar()))
    nombres = {h.get("name") for h in form["children"]}
    assert "es_ultimo" not in nombres
```

Agregar antes del bloque `if __name__`:

```python
def test_producto_declara_items_eliminar():
    prod = _producto(_cargar())
    campo = prod["data"].get("items_eliminar", {})
    assert campo.get("type") == "array"
    assert "__example__" in campo


def test_form_eliminar_con_dropdown():
    form = _form(_producto(_cargar()), nombre="form_eliminar")
    dd = next(h for h in form["children"] if h.get("type") == "Dropdown")
    assert dd["name"] == "eliminar_item"
    assert dd["data-source"] == "${data.items_eliminar}"
    assert dd.get("required") is False
    assert dd.get("visible") == "${data.tiene_items}"


def test_dropdown_eliminar_dispara_data_exchange():
    form = _form(_producto(_cargar()), nombre="form_eliminar")
    dd = next(h for h in form["children"] if h.get("type") == "Dropdown")
    accion = dd["on-select-action"]
    assert accion["name"] == "data_exchange"
    assert accion["payload"] == {"eliminar": "${form.eliminar_item}"}


def test_form_eliminar_antes_de_form_producto():
    """El selector de borrado va pegado al texto del carrito, encima del
    formulario de agregar."""
    hijos = _hijos(_producto(_cargar()))
    nombres = [c.get("name") for c in hijos if c.get("type") == "Form"]
    assert nombres == ["form_eliminar", "form_producto"]
```

Y en el bloque `if __name__ == "__main__":`, antes del `print`:

```python
    test_producto_declara_items_eliminar()
    test_form_eliminar_con_dropdown()
    test_dropdown_eliminar_dispara_data_exchange()
    test_form_eliminar_antes_de_form_producto()
```

- [ ] **Step 2: Verificar que fallan**

Run: `python -m pytest tests/test_pedido_flow_producto.py -v`
Expected: los 4 tests nuevos FAIL (`StopIteration` / KeyError `items_eliminar`); los 7 existentes PASS (los helpers por nombre siguen encontrando `form_producto`).

- [ ] **Step 3: Editar el Flow JSON**

En `flows/pedido_flow.json`, pantalla PRODUCTO:

(a) En el bloque `"data"`, después de `"tiene_items"`, agregar:

```json
"items_eliminar": {
  "type": "array",
  "items": {
    "type": "object",
    "properties": {
      "id":    { "type": "string" },
      "title": { "type": "string" }
    }
  },
  "__example__": [
    { "id": "ABC123", "title": "ABC123 × 5" }
  ]
}
```

(b) En `layout.children`, insertar entre el TextBody del error (`${data.error}`) y el Form `form_producto`:

```json
{
  "type": "Form",
  "name": "form_eliminar",
  "children": [
    {
      "type": "Dropdown",
      "label": "🗑️ Eliminar item",
      "name": "eliminar_item",
      "data-source": "${data.items_eliminar}",
      "required": false,
      "visible": "${data.tiene_items}",
      "on-select-action": {
        "name": "data_exchange",
        "payload": {
          "eliminar": "${form.eliminar_item}"
        }
      }
    }
  ]
}
```

- [ ] **Step 4: Verificar que pasan (incluye el resto de tests del JSON)**

Run: `python -m pytest tests/test_pedido_flow_producto.py tests/test_pedido_flow_json.py tests/test_pedido_flow_sistema.py -v`
Expected: todos PASS (11 en test_pedido_flow_producto más los de los otros dos archivos).

- [ ] **Step 5: Commit**

```bash
git add flows/pedido_flow.json tests/test_pedido_flow_producto.py
git commit -m "feat: Dropdown 'Eliminar item' en la pantalla PRODUCTO del Flow

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Handler `remove_product` en `main.py`

**Files:**
- Modify: `main.py:443` (entre el final de la rama `add_product` y el comentario de `totalizar`)

**Interfaces:**
- Consumes: `inferir_accion_flow` → `"remove_product"` (Task 1); `data_producto(carrito, eliminado=...)` (Task 2).
- Produces: respuesta `req.respond(screen="PRODUCTO", data=...)` con el carrito actualizado.

`main.py` importa pywa, DBISAM y Redis al cargar el módulo, por lo que (siguiendo el patrón del repo) esta rama no lleva test unitario propio: la lógica testeable vive en `routing.py` y `carrito.py` (Tasks 1-2). La verificación es la suite completa + prueba manual vía WhatsApp tras republicar el Flow.

- [ ] **Step 1: Implementar la rama**

En `main.py`, después del `return` que cierra la rama `add_product` (línea 442, `data=data_producto(carrito, agregado=...)`) y antes del comentario `# ── totalizar...` (línea 444), insertar:

```python
    # ── remove_product: quitar item del carrito ───────────────────────────────
    if action == "remove_product":
        codigo = (data.get("eliminar") or "").strip()
        # pop con default: doble toque o carrito expirado no deben reventar.
        carrito["productos"].pop(codigo, None)
        redis_cache.guardar_carrito(req.flow_token, carrito)
        print(f"[FLOW] remove_product codigo={codigo}")
        return req.respond(screen="PRODUCTO", data=data_producto(carrito, eliminado=codigo))
```

- [ ] **Step 2: Verificar sintaxis y correr la suite de tests puros**

Run: `python -m py_compile main.py && python -m pytest tests/test_routing.py tests/test_carrito.py tests/test_pedido_flow_producto.py tests/test_pedido_flow_json.py tests/test_pedido_flow_sistema.py -v`
Expected: compila sin error; todos los tests PASS.

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: rama remove_product elimina el item del carrito en Redis

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Verificación final y despliegue

**Files:**
- Ninguno nuevo; verificación y notas de despliegue.

- [ ] **Step 1: Correr toda la suite que no requiere servicios externos**

Run: `python -m pytest tests/ -v --ignore=tests/pedido_muestra.py`
Expected: PASS en los archivos puros. Si algún archivo falla, leer el traceback: solo es aceptable un `ImportError`/`ConnectionError` por servicios no disponibles en esta máquina (pywa/DBISAM/Redis) — un fallo de aserción en la lógica nueva es un bug que hay que corregir antes de seguir.

- [ ] **Step 2: Recordatorio de despliegue (manual, fuera del repo)**

El JSON actualizado debe republicarse en Meta Flow Builder sobre el Flow `FLOW_ID_PEDIDO`, en la misma WABA del teléfono (si no: error 131009). Mientras el Flow viejo siga publicado, el backend nuevo es retrocompatible (el campo `eliminar` nunca llega). Prueba manual: iniciar pedido por WhatsApp, agregar 2 productos, eliminar 1 con el Dropdown, verificar la línea `🗑️ Eliminado:` y que el total del RESUMEN excluye el item borrado.

- [ ] **Step 3: Push y PR draft**

```bash
git push -u origin worktree-eliminar-item-flow
gh pr create --draft --base feat/precio-libre-flow --title "feat: eliminar items del carrito en el Flow de pedido" --body "Dropdown '🗑️ Eliminar item' en la pantalla PRODUCTO del Flow: al seleccionar un item se elimina del carrito en Redis y la pantalla se refresca con la línea de confirmación. Ruteo por campo 'eliminar' (WhatsApp borra el literal 'action'). Requiere republicar flows/pedido_flow.json en Meta Flow Builder (misma WABA del teléfono). Spec: docs/superpowers/specs/2026-07-23-eliminar-item-flow-design.md

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

El PR va contra `feat/precio-libre-flow` (la rama base de este trabajo), no contra `master`.
