# Diseño: selector de Sistema (A/B) que enruta la escritura DBISAM a distinto CatalogName

**Fecha:** 2026-06-24
**Estado:** aprobado para implementación

## Problema / objetivo

El Flow de pedidos debe incluir un **selector obligatorio** que permita elegir
**Sistema A** o **Sistema B**. El sistema elegido determina el `CatalogName` de
DBISAM al que se **escribe** el pedido. Las lecturas (clientes, productos, precios)
**no cambian**: siguen usando el catálogo por defecto del `.env`.

## Alcance (decidido)

- El sistema afecta **solo la escritura** del pedido (inserción en
  `SOPERACIONINV` / `SDETALLEVENTA` vía `DBISAMDatabase.insert_pedidos`).
- Las lecturas siguen apuntando a `config('CatalogName')`.
- El flujo de texto plano (parser, sin selector) **no** se modifica; cae al
  catálogo por defecto.

## Arquitectura

Enfoque elegido (de tres evaluados): parametrizar `DBISAMDatabase` con un catálogo
opcional y resolver el catálogo del sistema con un helper puro en el punto de
escritura. Descartados: pasar el `catalog` solo a `insert_pedidos` (riega el
parámetro) y mutar `CatalogName` global por request (efectos colaterales, frágil).

Flujo del dato `sistema`:

```
CLIENTE (RadioButtonsGroup "sistema", required)
  → payload select_client incluye "sistema"
  → main.py select_client: carrito["sistema"] = data.get("sistema", "")  [Redis]
  → main.py completar_pedido_flow: pedido["sistema"] = carrito.get("sistema", "")
  → pedido viaja por Redis hasta la confirmación
  → ConfirmarStrategy: DBISAMDatabase(catalog=catalogo_de_sistema(pedido["sistema"]))
                       .insert_pedidos(pedido)
```

## Cambios

### 1. Flow — selector en la pantalla CLIENTE (`flows/pedido_flow.json` + Meta)

Añadir, dentro de `form_cliente` y **después** del `RadioButtonsGroup` de "Lista de
precios", un nuevo `RadioButtonsGroup` obligatorio:

```json
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
```

Y en el `on-click-action` del `Footer` "Siguiente" de CLIENTE, añadir al `payload`:

```json
"sistema": "${form.sistema}"
```

No cambia ninguna otra pantalla, navegación ni campo. Debe **subirse a Meta Flow
Builder y publicarse** (paso manual; sin esto el selector no aparece en producción).

### 2. Propagación en `main.py`

- En `select_client` (donde hoy se guardan `cliente` y `tipo_precio`):
  ```python
  carrito["sistema"] = data.get("sistema", "")
  ```
- En `completar_pedido_flow`, en el dict `pedido` (actual líneas 494-500), añadir:
  ```python
  "sistema": carrito.get("sistema", ""),
  ```

### 3. Nuevo módulo `database/catalogos.py` (helper puro, testeable)

```python
from decouple import config


def mapa_catalogos() -> dict:
    """Construye el mapa sistema -> CatalogName desde el entorno."""
    return {
        "A": config("CATALOG_SISTEMA_A", default=""),
        "B": config("CATALOG_SISTEMA_B", default=""),
    }


def catalogo_de_sistema(sistema, mapa=None, default=None):
    """Resuelve el CatalogName de DBISAM para el sistema elegido.

    Devuelve el catálogo por defecto si el sistema es vacío/desconocido o si la
    ruta del sistema no está configurada. Nunca lanza.
    """
    if mapa is None:
        mapa = mapa_catalogos()
    if default is None:
        default = config("CatalogName")
    ruta = mapa.get((sistema or "").strip().upper())
    if not ruta:
        return default
    return ruta
```

La función pura (`catalogo_de_sistema` recibiendo `mapa` y `default` explícitos) se
testea sin tocar `.env`.

### 4. `database/dbisam.py` — catálogo opcional

```python
class DBISAMDatabase:
    def __init__(self, catalog: str | None = None):
        self.dsn = config('DSN')
        self.catalog = catalog if catalog else config('CatalogName')
        print('INIT', self.catalog, self.dsn)
```

`connect_dbisam` y el uso de `self.catalog` quedan iguales. Sin argumento, el
comportamiento es idéntico al actual.

### 5. `strategy/response_strategy.py` — resolver catálogo en la escritura

Reemplazar (línea 59):

```python
DBISAMDatabase().insert_pedidos(pedido)
```

por:

```python
DBISAMDatabase(catalog=catalogo_de_sistema(pedido.get("sistema"))).insert_pedidos(pedido)
```

con el import correspondiente `from database.catalogos import catalogo_de_sistema`.

### 6. `.env` — dos variables nuevas

```
CATALOG_SISTEMA_A=<ruta del catálogo del Sistema A>
CATALOG_SISTEMA_B=<ruta del catálogo del Sistema B>
```

`CatalogName` se mantiene como fallback por defecto.

## Manejo de errores

- Selector `required: true` → WhatsApp obliga a elegir antes de avanzar.
- Defensa en servidor: `sistema` vacío o desconocido → catálogo por defecto.
- Variable de entorno del sistema ausente/vacía → catálogo por defecto.
- El flujo de texto plano (sin `sistema`) → catálogo por defecto.

## Pruebas

`tests/test_catalogos.py` (patrón de `tests/test_routing.py`: `sys.path.insert` +
bloque `__main__`). Casos para `catalogo_de_sistema` con `mapa` y `default`
explícitos (sin tocar `.env`):

- `"A"` → ruta A; `"B"` → ruta B.
- minúsculas / espacios (`" a "`) → ruta A (normaliza).
- `""`, `None`, `"C"` (desconocido) → default.
- sistema cuyo valor en el mapa es `""` (no configurado) → default.

`DBISAMDatabase`, `main.py` y `response_strategy.py` no son unit-testables (imports
pesados / ODBC); se verifican con `python -m py_compile` y revisión del call-site.

## Despliegue manual

Subir la pantalla CLIENTE corregida a Meta Flow Builder y **publicar** la nueva
versión del flow. Definir `CATALOG_SISTEMA_A` y `CATALOG_SISTEMA_B` en el `.env` del
servidor. El cambio de servidor surte efecto al reiniciar; el selector solo aparece
tras publicar el flow.
