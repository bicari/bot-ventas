# Diseño: eliminar items del carrito en el Flow de pedido

**Fecha:** 2026-07-23
**Rama base:** `feat/precio-libre-flow` (e4a2734)

## Problema

Cuando un vendedor agrega un producto por error en la pantalla PRODUCTO del Flow
de pedido, no hay forma de quitarlo: tiene que cancelar y rehacer el pedido
completo. Se necesita un mecanismo para eliminar un item del carrito sin salir
del Flow.

## Restricciones de WhatsApp Flows

- El carrito se muestra como un solo `TextBody` (`${data.items_texto}`); no
  existe un componente de "botón por fila" junto a cada línea de texto.
- Solo se permite un `Footer` por pantalla (ya lo ocupa "Agregar Producto").
- WhatsApp descarta el literal `action` del payload de `data_exchange`; la
  acción se infiere en el servidor por pantalla activa + campos presentes
  (`flows/routing.py`).
- Las referencias `${data.x}` deben ser el valor completo del campo
  (interpolación parcial no soportada).

## Decisión de UX (aprobada)

Un `Dropdown` "🗑️ Eliminar item" con los productos del carrito. Al seleccionar
uno se elimina de inmediato (`on-select-action` → `data_exchange`) y la
pantalla se refresca con el carrito actualizado. Un solo toque, sin
confirmación: si el vendedor se equivoca, vuelve a agregar el producto (agregar
el mismo código sobreescribe el item, comportamiento ya existente).

Alternativas descartadas:
- **CheckboxGroup + enlace "Eliminar seleccionados"**: más seguro contra toques
  accidentales pero ocupa más pantalla y exige dos toques.
- **NavigationList en lugar del texto del carrito**: más nativo pero cambia la
  vista actual y el toque directo borra por accidente con más facilidad.

## Alcance

Solo eliminar items completos. No se editan cantidades ni descuentos: para
corregir, se elimina y se vuelve a agregar.

## Cambios

### 1. `flows/pedido_flow.json` — pantalla PRODUCTO

- Nuevo campo de data `items_eliminar`: array de `{id, title}` con
  `__example__`.
- Nuevo `Form` (`form_eliminar`) separado de `form_producto`, con un único
  `Dropdown`:
  - `label`: "🗑️ Eliminar item", `name`: `eliminar_item`,
    `data-source`: `${data.items_eliminar}` (referencia completa),
    `required`: false.
  - `visible`: `${data.tiene_items}` (igual que el enlace "Totalizar pedido").
  - `on-select-action`: `data_exchange` con payload
    `{"eliminar": "${form.eliminar_item}"}`.
- Vive en un formulario aparte para que el `on-select-action` no dependa de la
  validación de los campos requeridos (`codigo`, `cantidad`) de
  `form_producto`.
- Ubicación en el layout: entre el texto del carrito y `form_producto`.

### 2. `flows/routing.py`

Nueva regla en `inferir_accion_flow`, sin colisión con las existentes:

```python
if pantalla == "PRODUCTO" and data.get("eliminar"):
    return "remove_product"
```

### 3. `flows/carrito.py`

- `data_producto()` agrega la clave `items_eliminar`: lista
  `[{"id": codigo, "title": "<codigo> × <cantidad>"}]` construida de
  `carrito["productos"]` (lista vacía si no hay items).
- El prefijo de confirmación se generaliza: además de `agregado`
  (`✅ Agregado: ...`), se soporta una línea `🗑️ Eliminado: <codigo>`.
  `formato_carrito` y `data_producto` ganan un parámetro `eliminado`
  (opcional, retrocompatible con todos los llamados existentes).

### 4. `main.py` — handler del Flow

Nueva rama `remove_product` en el manejador de `data_exchange`:

1. `codigo = data.get("eliminar")`.
2. `carrito["productos"].pop(codigo, None)` — si el código no existe (carrera
   rara: doble toque, carrito expirado), se ignora silenciosamente.
3. Guardar carrito en Redis.
4. Responder `PRODUCTO` con `data_producto(carrito, eliminado=codigo)`.

### 5. Manejo de errores

- Redis sin carrito: se usa el carrito vacío por defecto (comportamiento
  actual del handler); el Dropdown ni siquiera es visible sin items.
- Código inexistente en el carrito: refresco silencioso, sin mensaje de error.

### 6. Pruebas

Unitarias, sin WhatsApp ni Redis reales, siguiendo el patrón existente:

- `tests/test_routing.py`: payload con `eliminar` en PRODUCTO →
  `"remove_product"`; verificar que no interfiere con `codigo`/`totalizar`.
- Tests de `flows/carrito.py`: `items_eliminar` con carrito vacío y con items;
  línea `🗑️ Eliminado:` en `formato_carrito`; retrocompatibilidad de llamados
  sin los parámetros nuevos.

### 7. Despliegue

El JSON del Flow debe republicarse en Meta Flow Builder, en la misma WABA del
teléfono (error 131009 si no). El backend es retrocompatible: con el Flow
viejo publicado, el campo `eliminar` simplemente nunca llega y nada cambia.
