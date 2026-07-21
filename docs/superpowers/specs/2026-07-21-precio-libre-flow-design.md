# Precio libre por ítem en el Flow de pedido

- **Fecha:** 2026-07-21
- **Estado:** aprobado, pendiente de plan de implementación
- **Componente:** `flows/pedido_flow.json`, módulo nuevo `flows/precio_libre.py`,
  módulo nuevo `handlers/calculo_item.py`, `main.py::flow_pedido_endpoint`
  (acción `add_product`), `handlers/Validar_Pedido.py::ProductoHandler`,
  `flows/carrito.py`

## Objetivo

Que el vendedor pueda escribir un precio negociado por producto en el mismo
formulario donde escribe el código, y que el sistema lo respete aplicando el
impuesto real del producto (16/8/0%) en bases, IVA y totales, igual que hace
con los precios de lista.

Hoy el precio sale siempre de `A2INVCOSTOSPRECIOS`
(`FIC_{P01|P02|P03}{CAMPO_PRECIO}`); no hay forma de vender a un precio
negociado.

## Decisiones tomadas

| Decisión | Valor |
|---|---|
| Alcance | Solo Flow guiado; el formato de texto no cambia |
| Semántica del número | El vendedor indica con un radio si su precio incluye IVA o no |
| Fuente de verdad guardada | La **base sin IVA** (si escribió con IVA, se descompone al agregar) |
| Descuento % | **Excluyente** con el precio libre; escribir ambos es error |
| Validación | Solo `precio > 0`; sin piso contra lista ni costo |
| Supervivencia a la re-validación | Flag `precio_manual` en el ítem, respetado por `ProductoHandler` |
| UI | Campo "Precio (opcional)" + radio "¿El precio incluye IVA?" |

Se evaluó y descartó congelar el carrito del Flow (confiar en los cálculos de
`add_product` y saltarse `ProductoHandler` al confirmar): perdía la
re-verificación de precios/productos para *todos* los pedidos por Flow y dejaba
la aritmética duplicada como única fuente.

## Diseño

### 1. Formulario (`flows/pedido_flow.json`, pantalla PRODUCTO)

Dos componentes nuevos en `form_producto`, ambos `required: false`:

```json
{ "type": "TextInput", "label": "Precio (opcional)",
  "name": "precio", "input-type": "number", "required": false },
{ "type": "RadioButtonsGroup", "label": "¿El precio incluye IVA?",
  "name": "precio_incluye_iva", "required": false,
  "data-source": [
    { "id": "con_iva", "title": "Sí, IVA incluido" },
    { "id": "sin_iva", "title": "No, es precio base" }
  ] }
```

El payload del Footer "Agregar Producto" suma `"precio": "${form.precio}"` y
`"precio_incluye_iva": "${form.precio_incluye_iva}"`.

**Nota operativa:** el JSON hay que republicarlo en Meta Flow Builder sobre el
flow `FLOW_ID_PEDIDO`, en la misma WABA del teléfono (véase memoria del error
131009). Los radios de Flows no pueden ser "required solo si hay precio": la
obligatoriedad condicional se valida en el servidor (abajo).

### 2. Interpretación de la entrada: `flows/precio_libre.py` (nuevo, puro)

Siguiendo el patrón de `flows/carrito.py` (lógica pura, sin BD/Redis/WhatsApp),
una sola función:

```
resolver_precio_manual(precio_raw, incluye_iva_raw, descuento, impuesto)
    -> float | None        # base sin IVA, o None si no hay precio manual
```

Reglas, en orden:

1. `precio_raw` vacío/None → `None` (flujo normal de lista; un radio marcado
   sin precio se ignora, no es error).
2. No numérico (tras normalizar coma decimal como hace `add_product`) →
   `ValueError` con mensaje claro.
3. `precio <= 0` → `ValueError`.
4. `descuento > 0` a la vez → `ValueError` "El precio manual y el descuento %
   son excluyentes; usa solo uno."
5. Radio sin elegir → `ValueError` "Indica si el precio incluye IVA."
6. `con_iva` → `round(precio / (1 + impuesto / 100), 2)`;
   `sin_iva` → `precio`.

La base sin IVA es lo que se guarda. El impuesto se pasa como argumento (viene
fresco de la fila de DBISAM que `add_product` ya consulta), así la función
sigue siendo pura.

### 3. Matemática unificada: `handlers/calculo_item.py` (nuevo, puro)

El spec de `CAMPO_PRECIO` (2026-07-16, "Fuera de alcance") dejó registrado que
este spec debía unificar la aritmética por ítem duplicada entre
`main.py:418-429` (`add_product`) y `handlers/Validar_Pedido.py:64-74`
(`ProductoHandler`). Este spec la unifica porque el precio manual la necesita:
sin unificar, la regla "manual vs lista" viviría copiada en dos sitios.

```
calcular_item(precio_sin_iva, cantidad, descuento, impuesto, peso) -> dict
```

Devuelve el dict con los campos que hoy calculan ambos sitios de forma
idéntica: `precio_sin_iva`, `precio_con_descuento`, `monto_iva`,
`precio_venta`, `subtotal`, `total_sin_dcto`, `peso_item` (y `precio` con IVA,
que hoy solo calcula `ProductoHandler`). `add_product` y `ProductoHandler`
pasan a llamar esta función; ninguno cambia su contrato hacia afuera.

### 4. `add_product` (`main.py`)

Tras consultar la fila en DBISAM (se sigue consultando siempre: valida
existencia y trae impuesto/descripción/peso):

- `base = resolver_precio_manual(...)`; sus `ValueError` se muestran en la
  pantalla PRODUCTO vía `data_producto(carrito, error=...)`, como los errores
  actuales.
- Si `base is not None`: el ítem se guarda con `precio_manual: True`,
  `descuento: 0` y los campos de `calcular_item(base, ...)`.
- Si `base is None`: comportamiento actual con el precio de lista
  (`precio_manual` ausente).

### 5. Carrito visible (`flows/carrito.py`)

`formato_carrito` marca los ítems con precio manual con `✏️`:

```
• 01010024 × 5 ✏️ = $62.50
```

para que el vendedor distinga qué precios tocó a mano antes de totalizar.

### 6. Re-validación (`handlers/Validar_Pedido.py::ProductoHandler`)

Cambio quirúrgico en el bucle por producto:

```
item = pedido["productos"][codigo]
precio_item = item["precio_sin_iva"] if item.get("precio_manual") else precio_bd
```

- La validación "precio ≤ 0 → error" aplica **solo al precio de lista cuando
  no hay precio manual**: con precio manual, el precio de lista es irrelevante
  (un producto con lista en 0 se puede vender a precio manual).
- Todo lo demás sigue igual: existencia del producto, impuesto, descripción y
  peso se toman frescos de DBISAM; bases 16/8/exento, IVA y totales se
  calculan con la misma aritmética (ahora vía `calcular_item`).
- Aguas abajo no cambia nada: PDF, PostgreSQL (`pedidos`/`pedido_detalle`) y
  DBISAM (`SOPERACIONINV`/`SDETALLEVENTA`) consumen los mismos campos ya
  calculados del pedido.

### Flujo completo

```
Flow PRODUCTO (precio + radio)
  → add_product: fila DBISAM (impuesto fresco)
      → resolver_precio_manual → base sin IVA | None | error en pantalla
      → calcular_item → ítem en carrito (precio_manual=True, descuento=0)
  → totalizar / RESUMEN: sin cambios (usa precio_con_descuento del ítem)
  → completion: ProductoHandler re-valida
      → respeta precio_sin_iva si precio_manual, recalcula IVA/bases/totales
  → PDF preliminar → confirmación → PostgreSQL + DBISAM + PDF final
```

### Casos borde

- **Precio de lista en 0 + precio manual** → permitido (la lista no bloquea).
- **El impuesto cambia entre agregar y confirmar** → la base sin IVA guardada
  es la fuente de verdad; el IVA se recalcula con el impuesto vigente al
  confirmar. Si el vendedor escribió "con IVA", el precio final puede variar
  en ese caso extremo; es el comportamiento deseado (el impuesto manda).
- **Re-agregar el mismo código** → sobrescribe el ítem (comportamiento actual);
  sirve también para pasar de precio manual a lista o viceversa.
- **Radio marcado, precio vacío** → se ignora el radio; no es error.

## Pruebas

TDD con el patrón de tests puros del proyecto (`sys.path.insert`, funciones
`test_*`, ejecutables con pytest o como script):

1. `tests/test_precio_libre.py` — `resolver_precio_manual`: vacío → `None`;
   `con_iva` al 16% y al 8% (descomposición correcta); `sin_iva`; radio sin
   elegir → error; precio + descuento → error; ≤ 0 → error; no numérico →
   error; coma decimal aceptada; radio marcado sin precio → `None`.
2. `tests/test_calculo_item.py` — `calcular_item` reproduce exactamente los
   valores que hoy calculan `add_product` y `ProductoHandler` (paridad con el
   comportamiento actual, incluidos redondeos a 2 decimales).
3. Ampliar el patrón de `tests/test_producto_handler_codigos.py` (FakeDB):
   - `ProductoHandler` respeta `precio_manual` (el precio de la BD no lo pisa).
   - Producto con lista en 0 + precio manual → pasa.
   - Producto con lista en 0 sin precio manual → error (regla actual intacta).
4. `formato_carrito` — ítem con `precio_manual` lleva `✏️`; sin él, no.

Verificación manual contra el sistema real: republicar el Flow en Meta, armar
un pedido con un ítem a precio manual "con IVA" y otro "sin IVA", comprobar
resumen, PDF preliminar y totales tras confirmar.

## Fuera de alcance

- **Precio libre en el formato de texto** (`parser/parsear_pedido.py` no cambia).
- **Pisos o autorización de precio** (contra lista, costo o porcentaje): la
  única validación es `> 0`.
- **Tiers `P04`..`P06`** (igual que en el spec de `CAMPO_PRECIO`).
