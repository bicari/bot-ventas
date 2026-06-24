# Diseño: Campos faltantes en persistencia de pedidos (PostgreSQL)

**Fecha:** 2026-06-24
**Estado:** Aprobado (diseño)

## Problema

El sistema calcula un dict `pedido` completo (en `handlers/Validar_Pedido.py`) con
datos del cliente, vendedor, impuestos por base y, por línea de producto, precios y
pesos. Al confirmar el pedido (`strategy/response_strategy.py::ConfirmarStrategy`),
solo un subconjunto de esos datos se persiste en PostgreSQL a través de los modelos
SQLModel `Pedidos` y `Pedido_Detalle`. El resto se pierde.

Además, `database/postgres.py::create_tables_and_db()` usa
`SQLModel.metadata.create_all()`, que **solo crea tablas inexistentes — no agrega
columnas a tablas ya creadas**. Por eso una BD existente no recibirá las columnas
nuevas sin una migración explícita.

## Objetivo

1. Persistir con **fidelidad completa** todo lo que el pedido calcula, agregando los
   campos faltantes a los modelos `Pedidos` y `Pedido_Detalle`.
2. Mapear esos campos en `ConfirmarStrategy`.
3. Entregar un `schema.sql` ordenado e idempotente para **instalaciones nuevas**.
4. Entregar un `migration_001` con `ALTER TABLE` para actualizar la **BD existente**
   sin pérdida de datos.

## Decisiones tomadas

- **Alcance:** fidelidad completa (persistir todo lo calculado).
- **Entregables SQL:** DDL completo (`schema.sql`) + migración `ALTER` (`migration_001`).
- **Descuento:** la columna `descuento` se mantiene como **porcentaje** (sin cambio de
  semántica). `porcent_descuento` se llena con el mismo valor.
- **Sin** columna de referencia a DBISAM (`SOPERACIONINV`) por ahora.
- **Fuente de verdad:** los modelos SQLModel (Enfoque A). El SQL es un espejo
  mantenido a mano que refleja `models/pedidos.py`.

## Enfoque elegido

**A — Modelos SQLModel como fuente de verdad + SQL espejo.** El arranque sigue usando
`create_all`. `schema.sql` y `migration_001` reflejan los modelos. Sin dependencias
nuevas. Mitigación de drift: cabecera en cada `.sql` que apunta a `models/pedidos.py`.

Descartados: **B (Alembic)** — pesado, YAGNI; **C (generar DDL desde metadata)** —
agrega un paso de generación y produce SQL menos legible/ordenado a mano.

## Cambios detallados

### 1. `models/pedidos.py`

Campos nuevos en `Pedidos` (se mantienen todos los existentes):

| Campo | Tipo | Default | Origen en dict `pedido` |
|---|---|---|---|
| `descripcion_cliente` | str \| None | None | `pedido['descripcion_cliente']` |
| `direccion_cliente` | str \| None | None | `pedido['direccion_cliente']` |
| `nombre_vendedor` | str \| None | None | `pedido['nombre_vendedor']` |
| `tipo_precio` | str \| None | None | `pedido['precio']` (P1/P2) |
| `comentario` | str \| None | None | `pedido['comentario']` |
| `peso_total` | float | 0.0 | `pedido['peso_total']` |
| `base_16_monto` | float | 0.0 | `pedido['base_16']` |
| `iva_total` | float | 0.0 | `pedido['iva_total']` |

Campos nuevos en `Pedido_Detalle`:

| Campo | Tipo | Default | Origen |
|---|---|---|---|
| `descripcion` | str \| None | None | `producto['descripcion']` |
| `precio_sin_iva` | float | 0.0 | `producto['precio_sin_iva']` |
| `precio_venta` | float | 0.0 | `producto['precio_venta']` |
| `total_sin_dcto` | float | 0.0 | `producto['total_sin_dcto']` |
| `peso_item` | float | 0.0 | `producto['peso_item']` |

Columnas existentes que se empezarán a llenar (hoy quedan en 0):
- `precio_sin_descuento` ← `producto['precio_sin_iva']`
- `porcent_descuento` ← `producto['descuento']` (el %)
- `descuento` se mantiene con el % (sin cambio).

### 2. `strategy/response_strategy.py` — `ConfirmarStrategy`

Mapear todos los campos nuevos al construir `Pedidos(...)` y cada
`Pedido_Detalle(...)`. Usar `.get(clave, default)` para tolerar pedidos antiguos en
caché Redis que no tengan las claves nuevas.

### 3. `database/sql/schema.sql`

DDL completo para instalaciones nuevas:
- Orden: `pedidos` primero, luego `pedido_detalle` (dependencia FK).
- `CREATE TABLE IF NOT EXISTS` (idempotente).
- Tipos espejo de los modelos: `SERIAL PRIMARY KEY`, `VARCHAR`, `DOUBLE PRECISION`,
  `TIMESTAMP`.
- `estado VARCHAR ... DEFAULT 'Pendiente'`.
- `FOREIGN KEY (pedido_id) REFERENCES pedidos(id)` en `pedido_detalle`.
- Cabecera-comentario indicando que refleja `models/pedidos.py`.

### 4. `database/sql/migration_001_campos_faltantes.sql`

`ALTER TABLE ... ADD COLUMN IF NOT EXISTS` para cada columna nueva en `pedidos` y
`pedido_detalle`, con los mismos tipos/defaults del `schema.sql`. Permite actualizar
una BD existente sin pérdida de datos.

## Tipos en SQL

Se usa `DOUBLE PRECISION` (equivalente a `float` del modelo) para no introducir drift
modelo↔SQL. Nota: para montos sería más correcto `NUMERIC(14,2)`, pero eso desviaría el
SQL de los modelos; se mantiene float salvo decisión contraria posterior.

## Verificación

No existe suite automatizada. Plan de verificación manual (con salida real, sin asumir):
1. Aplicar `migration_001` a la BD de desarrollo y confirmar que las columnas se agregan.
2. Correr `create_all` (arranque) y confirmar que no intenta recrear/alterar nada.
3. Opcional: validar `schema.sql` en una BD scratch limpia.

## Fuera de alcance

- Columna de referencia a documento DBISAM.
- Cambiar la semántica de `descuento` a monto.
- Migrar a Alembic.
- Tipos `NUMERIC` para montos.
