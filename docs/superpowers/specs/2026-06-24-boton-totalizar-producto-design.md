# Diseño: botón "Totalizar pedido" en la pantalla PRODUCTO

**Fecha:** 2026-06-24
**Estado:** aprobado para implementación

## Problema / objetivo

Hoy, la única forma de pasar de PRODUCTO a RESUMEN (donde se ve el total en dólares
y el input de comentario) es marcar el checkbox "Este es el último producto"
(`es_ultimo`) al agregar un producto. Si el vendedor lo olvida, queda obligado a
agregar otro producto solo para poder marcarlo. Es lento e incómodo.

Objetivo: un botón **"Totalizar pedido"** en PRODUCTO que lleve a RESUMEN, que
**solo aparezca si hay al menos un ítem** en el pedido, y eliminar el checkbox
`es_ultimo`.

## Restricción técnica de WhatsApp Flows

Una pantalla admite un solo `Footer` (botón inferior). Para una segunda acción
condicionalmente visible se usa un `EmbeddedLink` con `visible` enlazado a datos
(los `caption-button` del Footer no admiten visibilidad condicional). El Footer
sigue siendo "Agregar Producto".

## Cambios

### 1. Flow — pantalla PRODUCTO (`flows/pedido_flow.json` + Meta)

- **Quitar** el `CheckboxGroup` `es_ultimo` del `Form` `form_producto`.
- **Quitar** `"es_ultimo": "${form.es_ultimo}"` del payload del Footer.
- **Declarar** en el `data` de PRODUCTO un nuevo booleano:
  ```json
  "tiene_items": { "type": "boolean", "__example__": false }
  ```
- **Añadir** un `EmbeddedLink` "Totalizar pedido", **fuera** del `Form` y como
  último hijo antes del `Footer` (pegado al botón inferior):
  ```json
  {
    "type": "EmbeddedLink",
    "text": "Totalizar pedido",
    "visible": "${data.tiene_items}",
    "on-click-action": {
      "name": "data_exchange",
      "payload": { "action": "totalizar", "totalizar": "1" }
    }
  }
  ```

Layout resultante (arriba→abajo): `Carrito:` → `${data.items_texto}` →
`${data.error}` → `Form (codigo/cantidad/descuento)` → `EmbeddedLink Totalizar` →
`Footer Agregar Producto`.

El `EmbeddedLink` va fuera del `Form`, así su payload no arrastra los campos del
formulario; solo envía `totalizar:"1"`. WhatsApp descarta el literal `action`, así
que el servidor enruta por la presencia de `totalizar` (igual que enruta
`add_product` por la presencia de `codigo`).

### 2. Ruteo (`flows/routing.py`)

Ampliar `inferir_accion_flow`: en la pantalla `PRODUCTO`, si `data.get("codigo")`
→ `"add_product"` (sin cambio); si `data.get("totalizar")` → `"totalizar"` (nuevo).
El resto igual.

### 3. Servidor (`main.py` `flow_pedido_endpoint`)

- **Quitar** del bloque `add_product` la línea `es_ultimo = bool(data.get("es_ultimo"))`
  y toda la rama `if es_ultimo:` (cálculo de totales + respuesta RESUMEN). Tras
  agregar, `add_product` siempre responde quedándose en PRODUCTO (con la
  confirmación "✅ Agregado").
- **Añadir** la rama `if action == "totalizar":` → calcula totales con
  `_calcular_totales_y_resumen`, guarda el carrito en Redis y responde
  `screen="RESUMEN"` con `resumen_texto`. Defensa: si el carrito no tiene productos
  (p. ej. expiró Redis), responde PRODUCTO con `error="⚠️ Agrega al menos un producto."`.
- **`tiene_items`**: todas las respuestas de PRODUCTO (refresco sin acción,
  `select_client`, éxito de `add_product`, ambos errores de `add_product`) incluyen
  `"tiene_items": bool(carrito.get("productos"))`. Para no repetir el dict, se
  extrae un helper interno que arma la data de PRODUCTO
  (`items_texto`/`error`/`show_error`/`tiene_items`).

El cálculo de totales (`_calcular_totales_y_resumen`) no cambia; solo se mueve su
disparador del checkbox al nuevo botón.

## Manejo de errores

- El `EmbeddedLink` solo aparece con `tiene_items=true`; en la práctica `totalizar`
  llega siempre con carrito no vacío.
- `totalizar` con carrito vacío → respuesta PRODUCTO con error, no un RESUMEN sin
  totales.
- Sin productos → `tiene_items=false` → enlace oculto.

## Pruebas

- **`tests/test_routing.py`** (extender): `inferir_accion_flow(None, "PRODUCTO",
  {"totalizar": "1"})` → `"totalizar"`; `{"codigo": "ABC", "cantidad": "5"}` sigue
  → `"add_product"`.
- **`tests/test_pedido_flow_producto.py`** (nuevo guard): PRODUCTO declara
  `tiene_items` en `data`; existe el `EmbeddedLink` "Totalizar pedido" con
  `visible="${data.tiene_items}"` y `on-click-action.name == "data_exchange"`;
  **no** existe el `CheckboxGroup` `es_ultimo`; el payload del Footer **no** incluye
  `es_ultimo`.
- **`tests/test_pedido_flow_json.py`** (guard de interpolación existente): debe
  seguir verde (el texto del `EmbeddedLink` es estático, sin `${...}` incrustado).
- **`main.py`** no es unit-testable (imports pesados): `python -m py_compile` +
  revisión del call-site.

## Despliegue manual

Subir la pantalla PRODUCTO actualizada a Meta Flow Builder y **publicar** la nueva
versión del flow. Sin esto, el botón no aparece en producción. El cambio de servidor
surte efecto al reiniciar.
