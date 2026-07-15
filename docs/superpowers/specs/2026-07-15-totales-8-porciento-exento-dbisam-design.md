# Cálculo y persistencia de totales 8% y exento en DBISAM

**Fecha:** 2026-07-15
**Estado:** Aprobado

## Problema

Los pedidos que incluyen productos con IVA del **8%** o **exentos** se calculan y
persisten mal:

1. **Cálculo:** los totales `base_8` / `iva_8` / `exento` salen en cero aunque el
   pedido tenga productos de esas categorías.
2. **Persistencia:** el INSERT a DBISAM (SOPERACIONINV / SDETALLEVENTA) no registra
   los campos del 8%; escribe todo como si fuera 16%.

## Causa raíz (confirmada contra datos reales)

### Bug de clasificación

La tasa real de IVA **no** es un literal 16/8: vive en la columna
`FIC_IMP0xMONTO` de `A2INVCOSTOSPRECIOS`. Valores reales:

| Producto | `IMP01ACTIVO` | `IMP01EXENTO` | `IMP01MONTO` | `IMP02ACTIVO` | `IMP02EXENTO` | `IMP02MONTO` | Tasa real |
|---|---|---|---|---|---|---|---|
| `01010030` (8%)      | True | False | 0.0 | True | False | **8.0** | 8% |
| `01010029` (exento)  | True | True  | 0.0 | True | True  | 0.0     | 0% |

El `CASE` actual en `consultar_precios` (dbisam.py) clasifica por *flags activos*:

```sql
CASE WHEN FIC_IMP01ACTIVO = 1 AND FIC_IMP01EXENTO = 0 THEN 16
     WHEN FIC_IMP02ACTIVO = 1 AND FIC_IMP01EXENTO = 0 THEN 8
     WHEN FIC_IMP01ACTIVO = 0 AND FIC_IMP01EXENTO = 1 THEN 0
ELSE 0 END AS IMPUESTO
```

El producto de 8% cumple **exactamente** `FIC_IMP01ACTIVO=1 AND FIC_IMP01EXENTO=0`
→ se marca como **16%**, y `base_8` queda en cero. El exento cae al `ELSE 0` por
coincidencia. Además la rama del 8% valida `FIC_IMP01EXENTO` (del impuesto 1) en
lugar de `FIC_IMP02EXENTO`.

### Bug de persistencia (verificado contra doc real 00001755 de A2)

**Cabecera SOPERACIONINV** — A2 separa las bases por tasa:
- `FTI_BASEIMPONIBLE`  = base gravada al **16% solamente** (ej. 6485.91)
- `FTI_BASEIMPONIBLE2` = base gravada al **8%** (ej. 1045.80)
- `FTI_IMPUESTO1PORCENT` = 16, `FTI_IMPUESTO1MONTO` = IVA 16%
- `FTI_IMPUESTO2PORCENT` = 8,  `FTI_IMPUESTO2MONTO` = IVA 8%
- **Exento: no tiene campo propio.** Es implícito = `TOTALBRUTO − BASEIMPONIBLE − BASEIMPONIBLE2`.

El insert actual mete `base_16 + base_8` en `FTI_BASEIMPONIBLE` y **nunca escribe**
los campos `...2`.

**Detalle SDETALLEVENTA** — A2 usa **dos slots** de impuesto por línea:
- Línea 16%: `FDI_IMPUESTO1=16`, `FDI_MONTOIMPUESTO1`=monto; `FDI_IMPUESTO2=0`, `FDI_MONTOIMPUESTO2=0`
- Línea 8%:  `FDI_IMPUESTO1=0`,  `FDI_MONTOIMPUESTO1=0`;    `FDI_IMPUESTO2=8`, `FDI_MONTOIMPUESTO2`=monto
- Línea exento: ambos slots en cero
- `FDI_PORCENTIMPUESTO1` / `FDI_PORCENTIMPUESTO2` son booleanos ("es porcentaje") → `True` (1)

El insert actual mete cualquier impuesto en el **slot 1**.

## Alcance

- **Incluye:** corregir la clasificación de tasa y la persistencia a DBISAM
  (SOPERACIONINV + SDETALLEVENTA).
- **No incluye:** el cálculo de totales (`base_8`, `exento`, `iva_8` en
  `_calcular_totales_y_resumen` y `ProductoHandler`) — ya está correcto, solo
  heredaba la mala clasificación. Tampoco PostgreSQL (`Pedidos`) — ya persiste
  `base_16/base_8/iva_16/iva_8/exento` correctamente.

## Diseño

### 1. Fijar la tasa efectiva (`consultar_precios`, dbisam.py)

Reemplazar el `CASE` por la lectura del `MONTO` real, validando cada impuesto con
**su propio** flag exento:

```sql
(CASE WHEN FIC_IMP01ACTIVO = 1 AND FIC_IMP01EXENTO = 0 THEN FIC_IMP01MONTO ELSE 0 END)
+ (CASE WHEN FIC_IMP02ACTIVO = 1 AND FIC_IMP02EXENTO = 0 THEN FIC_IMP02MONTO ELSE 0 END) AS IMPUESTO
```

Un producto tiene exactamente una tasa aplicable (16 XOR 8 XOR exento), por lo que
la suma de los montos activos/no-exentos da la tasa efectiva: `01010030`→8,
`01010029`→0, normal→16. Con esto, `base_t(8)` y `base_t(0)` de los cálculos
existentes encuentran los productos y la totalización se corrige sola.

### 2. Helper puro de slots de impuesto (`database/impuestos.py`, nuevo)

```python
def slots_impuesto_linea(impuesto: float, monto_iva: float) -> dict:
    """Enruta la tasa de una línea a los dos slots de impuesto de A2.

    16% -> slot 1, 8% -> slot 2, exento -> ceros.
    Devuelve {imp1, porc1, monto1, imp2, porc2, monto2}.
    """
    es_16 = impuesto == 16
    es_8  = impuesto == 8
    return {
        "imp1":   16 if es_16 else 0,
        "porc1":  1,
        "monto1": monto_iva if es_16 else 0.0,
        "imp2":   8 if es_8 else 0,
        "porc2":  1,
        "monto2": monto_iva if es_8 else 0.0,
    }
```

Función pura → tests unitarios sin BD (16%, 8%, exento).

### 3. Persistencia SDETALLEVENTA (`insert_pedidos`, dbisam.py)

Por cada línea, calcular `slots = slots_impuesto_linea(detalles['impuesto'], detalles['monto_iva'])`
y añadir al INSERT las columnas del slot 2, ajustando el slot 1:

- `FDI_IMPUESTO1` = `slots['imp1']`
- `FDI_PORCENTIMPUESTO1` = `slots['porc1']` (1)
- `FDI_MONTOIMPUESTO1` = `slots['monto1']`
- `FDI_IMPUESTO2` = `slots['imp2']`
- `FDI_PORCENTIMPUESTO2` = `slots['porc2']` (1)
- `FDI_MONTOIMPUESTO2` = `slots['monto2']`

### 4. Persistencia cabecera SOPERACIONINV (`insert_pedidos`, dbisam.py)

- `FTI_BASEIMPONIBLE`  = `pedido['base_16']`  (antes: `baseimponible` = base_16+base_8)
- `FTI_IMPUESTO1PORCENT` = 16 (sin cambio)
- `FTI_IMPUESTO1MONTO` = `pedido['iva_16']` (sin cambio)
- **añadir** `FTI_BASEIMPONIBLE2`  = `pedido['base_8']`
- **añadir** `FTI_IMPUESTO2PORCENT` = 8
- **añadir** `FTI_IMPUESTO2MONTO`  = `pedido['iva_8']`
- Exento: implícito, sin campo.

El `pedido` en el momento del INSERT ya trae `base_16/base_8/iva_16/iva_8`
(los pone `ProductoHandler` y se conservan en Redis hasta la confirmación).

## Verificación

- **Unitaria (pytest, sin BD):** `tests/test_impuestos.py` cubre
  `slots_impuesto_linea` para 16%, 8% y exento.
- **Integración (solo lectura, manual):** script que corre
  `consultar_precios(['01010030', '01010029'], 'P1')` y asserta `impuesto == 8` y
  `impuesto == 0` respectivamente.

## Ejemplo de correctitud

Carrito: producto 16% base 100, producto 8% base 50, producto exento base 10.

- Cálculo: `base_16=100, iva_16=16`; `base_8=50, iva_8=4`; `exento=10`;
  `total_bruto=160`; `total_neto=180`.
- Cabecera: `FTI_BASEIMPONIBLE=100, FTI_IMPUESTO1MONTO=16.00, FTI_BASEIMPONIBLE2=50,
  FTI_IMPUESTO2MONTO=4.00, FTI_TOTALBRUTO=160, FTI_TOTALNETO=180`.
- Exento implícito = `160 − 100 − 50 = 10`. ✓
