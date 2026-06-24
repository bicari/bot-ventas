# Selector de Sistema A/B → CatalogName DBISAM — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Añadir un selector obligatorio Sistema A/B en el Flow que enruta la escritura del pedido en DBISAM a un `CatalogName` distinto por sistema, sin afectar las lecturas.

**Architecture:** El campo `sistema` se captura en la pantalla CLIENTE, se propaga por el carrito (Redis) hasta el `pedido`, y en el punto de escritura (`ConfirmarStrategy`) se resuelve el catálogo con un helper puro `catalogo_de_sistema` y se pasa a un `DBISAMDatabase(catalog=...)` parametrizado. Las lecturas siguen usando el catálogo por defecto.

**Tech Stack:** Python 3, FastAPI, pywa, pyodbc/DBISAM, python-decouple, pytest (`python -m pytest`), WhatsApp Flows JSON 6.2.

## Global Constraints

- El sistema afecta **solo la escritura** del pedido; las lecturas (clientes, productos, precios) siguen usando `config('CatalogName')`.
- `catalogo_de_sistema` nunca lanza: sistema vacío/desconocido o ruta no configurada → catálogo por defecto.
- IDs del selector: `"A"` / `"B"`; títulos `"Sistema A"` / `"Sistema B"`; `required: true`.
- No alterar el flujo de texto plano (parser); sin `sistema` → catálogo por defecto.
- `DBISAMDatabase()` sin argumento debe comportarse exactamente igual que hoy.
- Tests siguen el patrón de `tests/test_routing.py`: `sys.path.insert(0, ...)` al raíz + bloque `if __name__ == "__main__"`.
- `main.py`, `database/dbisam.py` y `strategy/response_strategy.py` NO son unit-testables (imports pesados/ODBC); se verifican con `python -m py_compile` + revisión del call-site.
- No commitear `.env` (gitignored, con secretos). Las variables `CATALOG_SISTEMA_A`/`CATALOG_SISTEMA_B` se documentan; el usuario las define.

---

### Task 1: Helper `catalogo_de_sistema` (módulo puro)

**Files:**
- Create: `database/catalogos.py`
- Test: `tests/test_catalogos.py`

**Interfaces:**
- Produces:
  - `mapa_catalogos() -> dict` — `{"A": config("CATALOG_SISTEMA_A", default=""), "B": config("CATALOG_SISTEMA_B", default="")}`.
  - `catalogo_de_sistema(sistema, mapa=None, default=None) -> str` — resuelve el `CatalogName`. Normaliza `sistema` (`.strip().upper()`). Si `mapa`/`default` son `None`, los toma de `mapa_catalogos()` / `config("CatalogName")`. Devuelve `default` si el sistema es vacío/desconocido o su ruta está vacía. Nunca lanza.

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/test_catalogos.py`:

```python
"""Pruebas del resolutor de CatalogName por sistema.

Ejecutar:  python -m pytest tests/test_catalogos.py
       o:  python tests/test_catalogos.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.catalogos import catalogo_de_sistema

MAPA = {"A": r"C:\cat\A", "B": r"C:\cat\B"}
DEFECTO = r"C:\cat\default"


def test_sistema_a():
    assert catalogo_de_sistema("A", mapa=MAPA, default=DEFECTO) == r"C:\cat\A"


def test_sistema_b():
    assert catalogo_de_sistema("B", mapa=MAPA, default=DEFECTO) == r"C:\cat\B"


def test_normaliza_minusculas_y_espacios():
    assert catalogo_de_sistema(" a ", mapa=MAPA, default=DEFECTO) == r"C:\cat\A"


def test_vacio_va_a_default():
    assert catalogo_de_sistema("", mapa=MAPA, default=DEFECTO) == DEFECTO


def test_none_va_a_default():
    assert catalogo_de_sistema(None, mapa=MAPA, default=DEFECTO) == DEFECTO


def test_desconocido_va_a_default():
    assert catalogo_de_sistema("C", mapa=MAPA, default=DEFECTO) == DEFECTO


def test_ruta_vacia_va_a_default():
    assert catalogo_de_sistema("A", mapa={"A": ""}, default=DEFECTO) == DEFECTO


if __name__ == "__main__":
    test_sistema_a()
    test_sistema_b()
    test_normaliza_minusculas_y_espacios()
    test_vacio_va_a_default()
    test_none_va_a_default()
    test_desconocido_va_a_default()
    test_ruta_vacia_va_a_default()
    print("OK: catalogo_de_sistema.")
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_catalogos.py -v`
Expected: FALLA — `ModuleNotFoundError: No module named 'database.catalogos'`.

- [ ] **Step 3: Crear `database/catalogos.py`**

```python
"""Resolución del CatalogName de DBISAM según el sistema (A/B) elegido.

El sistema seleccionado en el Flow determina a qué catálogo se ESCRIBE el
pedido. Las lecturas siguen usando config('CatalogName'). Esta función es pura
y nunca lanza: ante un sistema vacío, desconocido o sin ruta configurada,
devuelve el catálogo por defecto.
"""

from decouple import config


def mapa_catalogos() -> dict:
    """Construye el mapa sistema -> CatalogName desde el entorno."""
    return {
        "A": config("CATALOG_SISTEMA_A", default=""),
        "B": config("CATALOG_SISTEMA_B", default=""),
    }


def catalogo_de_sistema(sistema, mapa=None, default=None) -> str:
    """Resuelve el CatalogName para el sistema elegido (fallback al por defecto)."""
    if mapa is None:
        mapa = mapa_catalogos()
    if default is None:
        default = config("CatalogName")
    ruta = mapa.get((sistema or "").strip().upper())
    if not ruta:
        return default
    return ruta
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `python -m pytest tests/test_catalogos.py -v`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add database/catalogos.py tests/test_catalogos.py
git commit -m "feat: helper catalogo_de_sistema resuelve CatalogName por sistema A/B"
```

---

### Task 2: Selector `sistema` en la pantalla CLIENTE del flow

**Files:**
- Modify: `flows/pedido_flow.json` (pantalla CLIENTE: `form_cliente` y payload del Footer)
- Test: `tests/test_pedido_flow_sistema.py`

**Interfaces:**
- Produces: pantalla CLIENTE con un `RadioButtonsGroup` `name="sistema"`, `required: true`, ids `A`/`B`; y el payload de `select_client` incluye `"sistema": "${form.sistema}"`.

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/test_pedido_flow_sistema.py`:

```python
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
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_pedido_flow_sistema.py -v`
Expected: FALLA — ambos tests fallan (no existe el radio `sistema` ni el campo en el payload).

- [ ] **Step 3: Añadir el RadioButtonsGroup en `form_cliente`**

En `flows/pedido_flow.json`, dentro del `Form` `form_cliente` de la pantalla CLIENTE, reemplazar el cierre del RadioButtonsGroup de "Lista de precios":

```json
              {
                "type": "RadioButtonsGroup",
                "label": "Lista de precios",
                "name": "tipo_precio",
                "required": false,
                "data-source": [
                  { "id": "P1", "title": "P1 - Lista 1" },
                  { "id": "P2", "title": "P2 - Lista 2" }
                ]
              }
            ]
```

por (añade el nuevo radio después del de precios, dentro del mismo `children`):

```json
              {
                "type": "RadioButtonsGroup",
                "label": "Lista de precios",
                "name": "tipo_precio",
                "required": false,
                "data-source": [
                  { "id": "P1", "title": "P1 - Lista 1" },
                  { "id": "P2", "title": "P2 - Lista 2" }
                ]
              },
              {
                "type": "RadioButtonsGroup",
                "label": "Sistema",
                "name": "sistema",
                "required": true,
                "data-source": [
                  { "id": "A", "title": "Sistema A" },
                  { "id": "B", "title": "Sistema B" }
                ]
              }
            ]
```

- [ ] **Step 4: Añadir `sistema` al payload del Footer de CLIENTE**

En el `on-click-action.payload` del Footer "Siguiente", reemplazar:

```json
              "payload": {
                "action":      "select_client",
                "cliente_id":  "${form.cliente_id}",
                "tipo_precio": "${form.tipo_precio}"
              }
```

por:

```json
              "payload": {
                "action":      "select_client",
                "cliente_id":  "${form.cliente_id}",
                "tipo_precio": "${form.tipo_precio}",
                "sistema":     "${form.sistema}"
              }
```

- [ ] **Step 5: Verificar JSON válido y que el test pasa**

Run: `python -c "import json; json.load(open('flows/pedido_flow.json', encoding='utf-8')); print('JSON OK')"`
Expected: `JSON OK`

Run: `python -m pytest tests/test_pedido_flow_sistema.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add flows/pedido_flow.json tests/test_pedido_flow_sistema.py
git commit -m "feat: selector obligatorio de Sistema A/B en la pantalla CLIENTE del flow"
```

---

### Task 3: Propagar `sistema` en `main.py`

**Files:**
- Modify: `main.py` (`select_client` ~líneas 390-394; dict `pedido` en `completar_pedido_flow` ~líneas 494-500)

**Interfaces:**
- Consumes: campo `sistema` del payload `select_client` (Task 2).
- Produces: `carrito["sistema"]` y `pedido["sistema"]` poblados para que Task 4 los lea.

- [ ] **Step 1: Guardar `sistema` en el carrito en `select_client`**

En `main.py`, en el bloque `if action == "select_client":`, después de la línea `carrito["tipo_precio"] = data.get("tipo_precio", "P1")`, añadir:

```python
        carrito["sistema"] = data.get("sistema", "")
```

(Queda justo antes del `print(f"[FLOW] select_client ...")`.)

- [ ] **Step 2: Incluir `sistema` en el dict `pedido` de `completar_pedido_flow`**

En `main.py`, en el dict `pedido = { ... }` de `completar_pedido_flow`, añadir la clave `"sistema"` tomada del carrito. Reemplazar:

```python
    pedido = {
        "cliente": carrito.get("cliente", ""),
        "productos": carrito.get("productos", {}),
        "precio": carrito.get("tipo_precio", "P1"),
        "comentario": carrito.get("comentario", ""),
        "total": 0.0,
    }
```

por:

```python
    pedido = {
        "cliente": carrito.get("cliente", ""),
        "productos": carrito.get("productos", {}),
        "precio": carrito.get("tipo_precio", "P1"),
        "comentario": carrito.get("comentario", ""),
        "sistema": carrito.get("sistema", ""),
        "total": 0.0,
    }
```

- [ ] **Step 3: Verificar que `main.py` compila**

Run: `python -m py_compile main.py && echo "COMPILA OK"`
Expected: `COMPILA OK`

- [ ] **Step 4: Verificar que `sistema` quedó cableado**

Run: `grep -nE 'carrito\["sistema"\]|"sistema": carrito.get' main.py`
Expected: dos líneas (la del carrito en `select_client` y la del dict `pedido`).

- [ ] **Step 5: Correr toda la suite (no debe romperse nada)**

Run: `python -m pytest tests/ -q`
Expected: todos los tests previos + nuevos en verde.

- [ ] **Step 6: Commit**

```bash
git add main.py
git commit -m "feat: propaga sistema desde el carrito hasta el pedido"
```

---

### Task 4: `DBISAMDatabase` con catálogo opcional + enrutado en `ConfirmarStrategy`

**Files:**
- Modify: `database/dbisam.py` (`DBISAMDatabase.__init__`, líneas 9-12)
- Modify: `strategy/response_strategy.py` (import + línea `DBISAMDatabase().insert_pedidos(pedido)`)

**Interfaces:**
- Consumes: `catalogo_de_sistema` de `database/catalogos.py` (Task 1); `pedido["sistema"]` (Task 3).
- Produces: la escritura del pedido usa el catálogo del sistema elegido; `DBISAMDatabase()` sin argumento mantiene el comportamiento por defecto.

- [ ] **Step 1: Parametrizar `DBISAMDatabase.__init__` con `catalog` opcional**

En `database/dbisam.py`, reemplazar:

```python
class DBISAMDatabase:
    def __init__(self):
        self.dsn = config('DSN')
        self.catalog = config('CatalogName')
        print('INIT', self.catalog, self.dsn)
```

por:

```python
class DBISAMDatabase:
    def __init__(self, catalog: str | None = None):
        self.dsn = config('DSN')
        self.catalog = catalog if catalog else config('CatalogName')
        print('INIT', self.catalog, self.dsn)
```

- [ ] **Step 2: Enrutar el catálogo en `ConfirmarStrategy`**

En `strategy/response_strategy.py`, añadir el import junto a los otros de `database`:

```python
from database.catalogos import catalogo_de_sistema
```

y reemplazar la línea:

```python
        DBISAMDatabase().insert_pedidos(pedido)
```

por:

```python
        DBISAMDatabase(catalog=catalogo_de_sistema(pedido.get("sistema"))).insert_pedidos(pedido)
```

- [ ] **Step 3: Verificar que ambos módulos compilan**

Run: `python -m py_compile database/dbisam.py strategy/response_strategy.py && echo "COMPILA OK"`
Expected: `COMPILA OK`

- [ ] **Step 4: Verificar el cableado**

Run: `grep -nE 'def __init__\(self, catalog|catalogo_de_sistema' database/dbisam.py strategy/response_strategy.py`
Expected: la firma `__init__(self, catalog...` en dbisam.py y el import + uso de `catalogo_de_sistema` en response_strategy.py.

- [ ] **Step 5: Correr toda la suite**

Run: `python -m pytest tests/ -q`
Expected: todos en verde (los tests de catálogos + el resto).

- [ ] **Step 6: Commit**

```bash
git add database/dbisam.py strategy/response_strategy.py
git commit -m "feat: la escritura del pedido usa el catalogo del sistema elegido"
```

---

## Despliegue manual (fuera del código)

1. **Meta Flow Builder:** subir la pantalla CLIENTE con el nuevo `RadioButtonsGroup` "Sistema" y el payload actualizado, y **publicar** la nueva versión del flow. Sin esto, el selector no aparece en producción.
2. **`.env` del servidor:** definir las rutas reales (no se commitean):
   ```
   CATALOG_SISTEMA_A=<ruta del catálogo del Sistema A>
   CATALOG_SISTEMA_B=<ruta del catálogo del Sistema B>
   ```
   `CatalogName` se mantiene como fallback. Reiniciar el servidor.

## Self-Review

- **Cobertura del spec:** selector en CLIENTE → Task 2; propagación carrito→pedido → Task 3; helper `catalogo_de_sistema` → Task 1; `DBISAMDatabase` catálogo opcional + enrutado en `ConfirmarStrategy` → Task 4; `.env` y publicación en Meta → sección Despliegue manual; manejo de errores (fallback) → Task 1 (lógica) cubierto por tests. ✔
- **Placeholders:** las únicas marcas `<ruta...>` están en el despliegue manual (datos del usuario), no en pasos de código. ✔
- **Consistencia de tipos:** `catalogo_de_sistema(sistema, mapa=None, default=None) -> str` se define en Task 1 y se consume en Task 4 como `catalogo_de_sistema(pedido.get("sistema"))` (un solo arg, usa env por defecto). `DBISAMDatabase(catalog=...)` definido en Task 4 Step 1 y usado en Step 2. Campo `"sistema"` consistente en flow (Task 2), carrito/pedido (Task 3) y resolución (Task 4). ✔
