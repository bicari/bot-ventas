# Corrección de `consultar_precios`: `IN ()` vacío, precedencia de `FI_STATUS` y `not_found`

- **Fecha:** 2026-07-16
- **Estado:** aprobado, pendiente de plan de implementación
- **Componente:** `database/dbisam.py::DBISAMDatabase.consultar_precios` (líneas 100-156)

## Problema

Un pedido falla con un error de sintaxis SQL de DBISAM cuando ninguno de los códigos
tipeados por el vendedor se resuelve contra `SCODEBAR`.

Reproducción (catálogo `C:\a2Softway12.36.ID\Empre001\Data`):

```
>>> DBISAMDatabase().consultar_precios(['PT0201001'], 'P1')
('PT0201001')        # parse_products
{}                   # productos_con_codigo_barra: vacío
pyodbc.DatabaseError: DBISAM Engine Error # 11949 SQL parsing error -
    Expected expression but instead found ) ... at line 9, column 76
```

### Causa raíz

`productos_referencia_codigo_barra` (línea 115) se construye iterando
`productos_con_codigo_barra`. Cuando ese dict está vacío, la expresión produce el
literal `()`, y el `WHERE` de la línea 127 emite `FI_CODIGO IN ()`, que DBISAM
rechaza al parsear.

Hay **dos rutas** que vacían el dict, no una:

1. El producto no tiene código de barra registrado.
2. El producto **sí** tiene código de barra, pero en `SCODEBAR` está almacenado con
   espacio inicial (`' 0-320-038'`, `' 001440'`, `' 0021-110199'`). Como el match es
   por igualdad exacta, nunca casa con lo que tipea el vendedor.

Ambas desembocan en el mismo `IN ()`.

## Bugs adicionales encontrados durante la investigación

Se corrigen en este mismo cambio por vivir en las líneas que ya se tocan.

### Bug 2 — La rama de referencia se salta el filtro de status

Línea 127:

```sql
WHERE FI_STATUS = 1 AND FI_CODIGO IN (...) OR FI_REFERENCIA IN (...)
```

`AND` precede a `OR`, así que se evalúa como
`(FI_STATUS = 1 AND FI_CODIGO IN (...)) OR (FI_REFERENCIA IN (...))`.
Un producto descontinuado tipeado por referencia se cotiza igual.

### Bug 3 — `not_found` ignora `FI_CODIGO`

Línea 133 compara los códigos tipeados solo contra las referencias devueltas y
contra los valores del dict de códigos de barra. Un producto encontrado por código
interno se reporta como no encontrado pese a estar en el resultado.

## Hipótesis descartada

La sospecha inicial fue que `FI_CODIGO IN (...)` recibía códigos de barra. **Es
falsa.** El dict se arma como `{x[1]: x[0]}` sobre `SELECT FBARRA_CODE,
FBARRA_PRODUCTO`, o sea `{código_interno: código_barra}`; al iterarlo salen las
claves, que son códigos internos. Verificado contra la base:

```
FBARRA_CODE ' 0-320-038' -> FBARRA_PRODUCTO '07110392'
FBARRA_PRODUCTO '07110392' casa contra SINVENTARIO.FI_CODIGO ? True
```

Queda registrado para que un futuro lector no "arregle" código que funciona.

## Restricción del motor

**El driver ODBC de DBISAM no acepta parámetros.** Verificado:

```
cursor.execute('... WHERE FBARRA_CODE IN (?, ?)', 'X1', 'X2')
-> ('HY004', '[HY004] [Elevate Software][DBISAM] Invalid SQL data type (11047) (SQLBindParameter)')
```

Esto descarta la solución habitual (placeholders en vez de f-strings). Hay que
seguir interpolando y escapar a mano. Los paréntesis en el `WHERE` sí están
soportados (verificado).

## Decisiones tomadas

| Decisión | Valor |
|---|---|
| Vías de identificación de un producto | código de barra, `FI_REFERENCIA` y `FI_CODIGO` (las tres tipeables) |
| Prioridad ante colisión | barra > interno > referencia |
| Estrategia de consulta | se conserva (pre-consulta a `SCODEBAR` + consulta a `SINVENTARIO`) |

## Diseño

### Arquitectura

Módulo nuevo `database/consulta_precios.py` con la lógica pura, siguiendo el
precedente de `database/impuestos.py` (probado sin base en
`tests/test_impuestos.py`). `consultar_precios` queda como cáscara que orquesta:
valida, consulta, delega.

- **`lista_sql(valores) -> str`** — arma la lista `IN` citada, escapando comillas
  simples duplicándolas (`O'Brien` → `'O''Brien'`). Único lugar que construye
  listas SQL.
- **`mapear_resultados(filas, productos, por_barra) -> (result_map, not_found)`** —
  resuelve qué fila corresponde a cada código tipeado y qué quedó sin encontrar.

### Flujo de datos

```
productos ──> lista_sql ──> SCODEBAR ──> por_barra {interno: barra}
                                             │
             productos ∪ por_barra.keys() ───┴──> lista_sql ──> SINVENTARIO
                                                                    │
                                                       mapear_resultados
                                                                    │
                                                    (result_map, not_found)
```

La clave es la unión: `FI_CODIGO` recibe *lo tipeado* más *lo resuelto desde
`SCODEBAR`*. Como los códigos tipeados siempre entran en esa lista, **nunca queda
vacía mientras haya productos**: el `IN ()` se vuelve imposible por construcción,
no por un caso especial. El guard de lista vacía se reduce al *early return* de
pedido sin productos.

`WHERE` parentizado, que corrige el Bug 2:

```sql
WHERE FI_STATUS = 1 AND (FI_CODIGO IN (...) OR FI_REFERENCIA IN (...))
```

### Resolución de prioridad

La prioridad **no puede aplicarse por orden de fila**. En una colisión ('535' es
`FI_CODIGO` de A y `FI_REFERENCIA` de B) ambas filas reclaman el mismo código
tipeado, y cuál gana dependería del orden que devuelva DBISAM: no determinista.

Cada fila recibe un rango según cómo fue reclamada — barra=0, interno=1,
referencia=2 — y gana el menor, sin depender del orden. Las filas que no reclama
ningún código tipeado se descartan.

### Manejo de errores

- `productos` vacío → `({}, [])` sin tocar la base.
- `tipo_precio` inválido → hoy produce `FIC_NonePRECIOTOTALEXT` y un error de
  sintaxis incomprensible; pasa a lanzar `ValueError` explícito.
- `not_found` se deriva de `result_map`: `[p for p in productos if p not in result_map]`.
  Corrige el Bug 3 y elimina las dos listas intermedias.
- Los errores de DBISAM siguen propagando como `pyodbc.DatabaseError`, que es lo
  que `handlers/Validar_Pedido.py` ya atrapa.

### Contrato preservado

`consultar_precios` sigue devolviendo `(result_map, not_found)` con la misma forma
(`result_map` mapea código tipeado → fila cruda del query, `FI_REFERENCIA` en el
índice 5). No cambia nada para `handlers/Validar_Pedido.py`.

## Pruebas

`tests/test_consulta_precios.py`, puro, sin base, siguiendo el patrón de
`tests/test_impuestos.py`:

1. `lista_sql` escapa comillas simples.
2. `lista_sql` cita cada valor por separado.
3. Ningún código con barra → se genera SQL válido, no `IN ()` *(el bug reportado)*.
4. Prioridad barra > interno > referencia.
5. Colisión resuelta de forma determinista, sin depender del orden de filas.
6. Producto hallado por `FI_CODIGO` no aparece en `not_found` *(regresión del Bug 3)*.
7. Filas no reclamadas por ningún código tipeado se descartan.
8. Pedido vacío → `({}, [])`.

Verificación manual adicional contra DBISAM real con el caso `PT0201001`, ya que
el `WHERE` parentizado es SQL que ningún test puro cubre.

## Fuera de alcance

- **Normalizar (`TRIM`) el match de códigos de barra.** Los espacios iniciales en
  `SCODEBAR` son un problema de datos real, pero no se sabe cuántos de los 72.362
  registros afecta y tocar el match tiene alcance propio. El arreglo de este spec
  ya elimina el crash en ese caso. Medir antes de decidir.
- Reescribir la consulta como `LEFT JOIN SCODEBAR` (evaluado y descartado:
  `SCODEBAR` admite varios códigos por producto, el join duplicaría filas).
- El `except` que enmascara errores de DBISAM en `consultar_vendedores_con_acceso`
  (problema aparte, ya diagnosticado).
