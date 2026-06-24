# Diseño: la pantalla PRODUCTO no muestra el carrito

**Fecha:** 2026-06-24
**Estado:** aprobado para implementación

## Problema

En el Flow de pedidos, al agregar productos en la pantalla **PRODUCTO**, el carrito
no se muestra. En lugar del listado de productos, la pantalla pinta el texto
**literal** `${data.items_texto}` (con el prefijo estático `Carrito:` y un salto de
línea antes). Tampoco hay confirmación visible cuando un producto se agrega con éxito.

Restricción del usuario: **no tocar la estructura del flow de pedidos** (pantallas,
navegación, formularios y acciones se mantienen).

## Causa raíz

**WhatsApp Flows no soporta interpolación parcial de cadenas.** Una referencia
`${data.x}` solo se resuelve cuando es el **valor completo** de la propiedad `text`.
Si se incrusta dentro de una cadena con texto estático, WhatsApp la renderiza
literal.

El TextBody del carrito en PRODUCTO usa `"text": "Carrito:\n${data.items_texto}"`
(estático + referencia). Por eso se ve `Carrito:` + salto de línea + el literal
`${data.items_texto}`: el prefijo estático se pinta, la referencia no se resuelve.

Evidencia confirmada descargando el `flow.json` **publicado** en Meta (Graph API
`GET /<FLOW_ID_PEDIDO>/assets`), idéntico al local:

| Pantalla | `text` del TextBody | Resuelve |
|---|---|---|
| PRODUCTO | `"Carrito:\n${data.items_texto}"` — estático + referencia | ❌ literal |
| RESUMEN  | `"${data.resumen_texto}"` — referencia pura | ✅ |
| error    | `"${data.error}"` — referencia pura | ✅ |

El único TextBody que falla es el único que mezcla texto estático con la referencia.
Los campos `items_texto`/`error`/`show_error` **ya están declarados** en el `data` de
PRODUCTO (no hay drift ni falta de declaración).

**El bug NO está en el código Python, ni en la declaración de datos, ni en un drift
con Meta: está en que el binding del carrito no es una referencia pura.**

## Estrategia elegida

Corrección **manual en Meta Flow Builder** (el usuario la aplica). En el repo no se
añade un script de publicación. El repo se mantiene como fuente de verdad fiel a lo
publicado.

## Cambios

| # | Cambio | Dónde | Quién aplica |
|---|--------|-------|--------------|
| 1 | Dividir el carrito en dos `TextBody`: estático `"Carrito:"` + referencia pura `"${data.items_texto}"` | Meta + `pedido_flow.json` | Usuario (Meta) / Claude (repo) |
| 2 | Anteponer línea "✅ Agregado: …" a `items_texto` | `main.py` | Claude |

El bloque `data` de PRODUCTO ya declara `items_texto`/`error`/`show_error`; **no se
toca**. El único cambio en el flow es convertir la referencia incrustada en una
referencia pura.

### Cambio 1 — JSON corregido de la pantalla PRODUCTO (subir a Meta)

Reemplazar la pantalla `PRODUCTO` completa en Flow Builder por esto. El único cambio
respecto a lo publicado es que el `TextBody` del carrito se divide en dos: uno
estático `"Carrito:"` y otro con referencia pura `"${data.items_texto}"`.
**`data`, pantallas, navegación, formulario y footer no cambian.**

```json
{
  "id": "PRODUCTO",
  "title": "Agregar Productos",
  "data": {
    "items_texto": {
      "type": "string",
      "__example__": "Sin productos agregados aun."
    },
    "error": {
      "type": "string",
      "__example__": " "
    },
    "show_error": {
      "type": "boolean",
      "__example__": false
    }
  },
  "layout": {
    "type": "SingleColumnLayout",
    "children": [
      {
        "type": "TextBody",
        "text": "Carrito:"
      },
      {
        "type": "TextBody",
        "text": "${data.items_texto}"
      },
      {
        "type": "TextBody",
        "text": "${data.error}",
        "visible": "${data.show_error}"
      },
      {
        "type": "Form",
        "name": "form_producto",
        "children": [
          {
            "type": "TextInput",
            "label": "Codigo de producto",
            "name": "codigo",
            "input-type": "text",
            "required": true
          },
          {
            "type": "TextInput",
            "label": "Cantidad",
            "name": "cantidad",
            "input-type": "number",
            "required": true
          },
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
      {
        "type": "Footer",
        "label": "Agregar Producto",
        "on-click-action": {
          "name": "data_exchange",
          "payload": {
            "action":    "add_product",
            "codigo":    "${form.codigo}",
            "cantidad":  "${form.cantidad}",
            "descuento": "${form.descuento}",
            "es_ultimo": "${form.es_ultimo}"
          }
        }
      }
    ]
  }
}
```

> Nota: el `payload` mantiene `"action": "add_product"` aunque WhatsApp lo descarte;
> el servidor deduce la acción por pantalla (`flows/routing.py`). No se cambia.

Tras pegarlo, **guardar y publicar** el flow en Meta. Si el flow ya está publicado,
Meta crea una nueva versión; asegurarse de que la versión activa sea la corregida.

### Cambio 2 — Confirmación de "producto agregado" (servidor)

En `main.py`, la respuesta de `add_product` antepone una línea de confirmación al
texto del carrito (sin campos de datos nuevos en el flow):

```
✅ Agregado: COD123 × 5

• COD123 × 5 = $1,250.00
• COD456 × 2 = $480.00
```

Implementación: pasar el código recién agregado a `_formato_carrito` (o componer la
línea en el bloque `add_product`) para anteponerla solo en la respuesta exitosa de un
producto agregado. El refresco sin acción y los errores siguen mostrando el carrito
sin la línea de confirmación.

### Cambio 1 (repo) — `flows/pedido_flow.json`

Actualizar la pantalla PRODUCTO del archivo local para reflejar el split en dos
`TextBody`, de modo que repo y Meta no diverjan.

## Alternativas descartadas

- **Script de publicación vía Graph API**: el usuario prefiere editar en Flow Builder.
- **Campo `success`/`show_success` nuevo en el flow**: duplicaría el patrón de `error`
  y añadiría datos al flow. YAGNI: la línea dentro de `items_texto` basta.
- **Mantener un solo `TextBody` con interpolación-con-prefijo**: descartado — es
  precisamente la causa del bug. WhatsApp no resuelve `${data.x}` incrustado en una
  cadena con texto estático.
- **Incluir el rótulo "Carrito:" dentro de `items_texto` en el servidor** (un solo
  `TextBody` con referencia pura): alternativa válida, pero el split en dos `TextBody`
  mantiene la presentación en el flow y deja al servidor solo la lista de productos.

## Verificación

- Tras publicar en Meta: abrir el Flow, seleccionar cliente → PRODUCTO debe mostrar
  "Carrito:" seguido de "Sin productos agregados aún." (ya no el literal `${...}`).
- Agregar un producto → el carrito lista el producto y aparece "✅ Agregado: …".
- Agregar un segundo producto → ambos aparecen en el listado.
- Marcar "último producto" → navega a RESUMEN con totales.
