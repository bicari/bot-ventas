# Corrección de `consultar_precios` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminar el error de sintaxis de DBISAM (`IN ()`) al consultar precios, y de paso corregir el salto del filtro `FI_STATUS` y el `not_found` que ignora `FI_CODIGO`.

**Architecture:** Se extrae la lógica pura a `database/consulta_precios.py` (tres funciones: construcción de listas `IN`, unión de códigos a buscar, y resolución de resultados), siguiendo el precedente de `database/impuestos.py`. `consultar_precios` queda como cáscara que orquesta: valida, consulta, delega. La lista de `FI_CODIGO` pasa a ser la unión de *lo tipeado* + *lo resuelto desde `SCODEBAR`*, con lo que el `IN ()` se vuelve imposible por construcción.

**Tech Stack:** Python 3.11, pyodbc + DBISAM (ODBC), pytest.

**Spec:** `docs/superpowers/specs/2026-07-16-consulta-precios-in-vacio-design.md`

**Rama:** `fix/consulta-precios-in-vacio` (ya creada; el spec está commiteado ahí).

## Global Constraints

- **El driver ODBC de DBISAM NO acepta parámetros.** `cursor.execute(sql, args)` falla con `('HY004', 'Invalid SQL data type (11047) (SQLBindParameter)')`. Todo valor va interpolado y escapado a mano. No introducir placeholders `?`.
- **Toda lista `IN` de SQL se construye con `lista_sql()`.** Es el único lugar autorizado a citar valores.
- **Contrato público inalterable:** `consultar_precios(productos, tipo_precio)` devuelve `(result_map, not_found)`, donde `result_map` mapea *código tipeado por el vendedor* → *fila cruda del query*. `handlers/Validar_Pedido.py` depende de esto y no se toca.
- **Índices de la fila cruda:** `row[0]=FI_CODIGO`, `row[1]=IMPUESTO`, `row[2]=precio`, `row[3]=FI_DESCRIPCION`, `row[4]=FI_PESOPRODUCTO`, `row[5]=FI_REFERENCIA`.
- **Prioridad ante colisión:** barra > interno > referencia. Debe ser determinista, sin depender del orden de filas que devuelva DBISAM.
- **Las pruebas son puras**, sin base de datos ni `.env`, siguiendo `tests/test_impuestos.py`.
- **No normalizar (`TRIM`) códigos de barra.** Está explícitamente fuera de alcance en el spec.

---

## File Structure

| Archivo | Responsabilidad |
|---|---|
| `database/consulta_precios.py` *(nuevo)* | Lógica pura: `lista_sql` (listas `IN` escapadas), `codigos_para_fi_codigo` (unión tipeados + resueltos) y `mapear_resultados` (qué fila corresponde a cada código tipeado). Sin imports de pyodbc. |
| `tests/test_consulta_precios.py` *(nuevo)* | Pruebas puras del módulo anterior. |
| `database/dbisam.py:100-156` *(modificar)* | `consultar_precios` pasa a orquestar: valida `tipo_precio`, retorno temprano, dos consultas, delega en las funciones puras. |

---

### Task 1: Construcción segura de las listas `IN`

**Files:**
- Create: `database/consulta_precios.py`
- Test: `tests/test_consulta_precios.py`

**Interfaces:**
- Consumes: nada.
- Produces:
  - `lista_sql(valores: Iterable) -> str`. Devuelve `"('A','B')"`. Lanza `ValueError` si `valores` viene vacío.
  - `codigos_para_fi_codigo(productos: list[str], por_barra: dict) -> list[str]`. Unión sin duplicados de lo tipeado + lo resuelto desde `SCODEBAR`, preservando el orden.

**`codigos_para_fi_codigo` es el arreglo del bug reportado**, y por eso es una función propia en vez de una línea suelta dentro de `consultar_precios`: su invariante —nunca devuelve lista vacía si `productos` no lo está, aunque `por_barra` esté vacío— es justamente lo que hacía imposible el `IN ()`, y merece un test que la fije contra regresiones.

**Por qué `ValueError` y no `"()"`:** emitir `()` es exactamente el bug que este plan arregla. Fallar ruidosamente convierte una regresión futura en un error de programación visible, en vez de un error críptico de sintaxis SQL a 40 líneas de distancia.

- [ ] **Step 1: Write the failing tests**

Crear `tests/test_consulta_precios.py`:

```python
"""Pruebas de la lógica pura de resolución de códigos para consultar precios.

Ejecutar:  python -m pytest tests/test_consulta_precios.py
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.consulta_precios import codigos_para_fi_codigo, lista_sql


def test_lista_sql_cita_cada_valor():
    assert lista_sql(["A", "B"]) == "('A','B')"


def test_lista_sql_un_solo_valor():
    assert lista_sql(["PT0201001"]) == "('PT0201001')"


def test_lista_sql_escapa_comilla_simple():
    """Una comilla en el código cerraría el literal y rompería el SQL."""
    assert lista_sql(["O'Brien"]) == "('O''Brien')"


def test_lista_sql_vacia_lanza_error():
    """IN () es SQL inválido en DBISAM: fallar ruidosamente, no emitirlo."""
    with pytest.raises(ValueError):
        lista_sql([])


def test_codigos_para_fi_codigo_sin_ningun_codigo_de_barra():
    """EL BUG REPORTADO: sin barras, la lista salía vacía y producía 'IN ()'.

    Al unir lo tipeado, deja de poder quedar vacía.
    """
    assert codigos_para_fi_codigo(["PT0201001"], {}) == ["PT0201001"]


def test_codigos_para_fi_codigo_une_tipeados_y_resueltos_sin_duplicar():
    productos = ["0-320-038", "01010024"]
    por_barra = {"07110392": "0-320-038", "01010024": "01010024"}
    assert codigos_para_fi_codigo(productos, por_barra) == ["0-320-038", "01010024", "07110392"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_consulta_precios.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'database.consulta_precios'`

- [ ] **Step 3: Write minimal implementation**

Crear `database/consulta_precios.py`:

```python
"""Lógica pura de resolución de códigos para la consulta de precios.

Vive separada de database/dbisam.py para poder probarse sin el motor legado,
igual que database/impuestos.py.
"""


def lista_sql(valores) -> str:
    """Arma una lista IN de SQL, citando y escapando cada valor.

    El driver ODBC de DBISAM no acepta parámetros (Invalid SQL data type 11047),
    así que hay que interpolar; escapar aquí es la única defensa.

    Lanza ValueError si no hay valores: `IN ()` es SQL inválido en DBISAM y era
    la causa del error # 11949.
    """
    valores = list(valores)
    if not valores:
        raise ValueError("lista_sql() sin valores: produciria 'IN ()', invalido en DBISAM")
    return "(" + ",".join("'" + str(v).replace("'", "''") + "'" for v in valores) + ")"


def codigos_para_fi_codigo(productos, por_barra) -> list:
    """Códigos a buscar contra FI_CODIGO: lo tipeado + lo resuelto desde SCODEBAR.

    Preserva el orden y no duplica. La unión es lo que arregla el DBISAM Engine
    Error # 11949: antes la lista salía SOLO de SCODEBAR, así que un pedido sin
    ningún código de barra la dejaba vacía y emitía 'IN ()'. Incluyendo siempre
    lo tipeado, no puede quedar vacía mientras haya productos.
    """
    return list(dict.fromkeys(list(productos) + list(por_barra)))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_consulta_precios.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add database/consulta_precios.py tests/test_consulta_precios.py
git commit -m "feat: construccion segura de las listas IN para consultar precios"
```

---

### Task 2: `mapear_resultados` — resolución determinista por prioridad

**Files:**
- Modify: `database/consulta_precios.py`
- Test: `tests/test_consulta_precios.py`

**Interfaces:**
- Consumes: nada de Task 1 (funciones independientes en el mismo módulo).
- Produces: `mapear_resultados(filas, productos, por_barra) -> tuple[dict, list]`
  - `filas`: iterable de filas crudas (`row[0]=FI_CODIGO`, `row[5]=FI_REFERENCIA`).
  - `productos`: `list[str]`, códigos tal como los tipeó el vendedor.
  - `por_barra`: `dict[str, str]`, `{código_interno: código_de_barra_tipeado}`.
  - Devuelve `(result_map, not_found)`: `result_map` es `{código_tipeado: fila}`, `not_found` es `list[str]` en el orden original de `productos`.

- [ ] **Step 1: Write the failing tests**

Añadir a `tests/test_consulta_precios.py` (el import de arriba pasa a ser `from database.consulta_precios import codigos_para_fi_codigo, lista_sql, mapear_resultados`):

```python
def fila(fi_codigo, fi_referencia):
    """Fila cruda del query: (FI_CODIGO, IMPUESTO, PRECIO, DESC, PESO, FI_REFERENCIA)."""
    return (fi_codigo, 16, 10.0, "DESCRIPCION", 1.0, fi_referencia)


def test_hallado_por_referencia():
    filas = [fila("07110392", "PT0201001")]
    result_map, not_found = mapear_resultados(filas, ["PT0201001"], {})
    assert result_map == {"PT0201001": filas[0]}
    assert not_found == []


def test_hallado_por_codigo_de_barra_se_indexa_por_lo_tipeado():
    """El vendedor tipeó la barra; el result_map debe indexarse por la barra."""
    filas = [fila("07110392", "2661012025306")]
    result_map, not_found = mapear_resultados(filas, ["0-320-038"], {"07110392": "0-320-038"})
    assert result_map == {"0-320-038": filas[0]}
    assert not_found == []


def test_hallado_por_fi_codigo_no_aparece_en_not_found():
    """Regresión Bug 3: not_found ignoraba FI_CODIGO."""
    filas = [fila("01010024", "REF-X")]
    result_map, not_found = mapear_resultados(filas, ["01010024"], {})
    assert result_map == {"01010024": filas[0]}
    assert not_found == []


def test_not_found_lista_los_ausentes_en_orden():
    filas = [fila("01010024", "REF-X")]
    _, not_found = mapear_resultados(filas, ["ZZZ", "01010024", "AAA"], {})
    assert not_found == ["ZZZ", "AAA"]


def test_filas_no_reclamadas_se_descartan():
    """El OR del query puede traer filas que nadie pidió."""
    filas = [fila("01010024", "REF-X"), fila("99999999", "REF-Y")]
    result_map, _ = mapear_resultados(filas, ["01010024"], {})
    assert list(result_map) == ["01010024"]


def test_prioridad_interno_gana_sobre_referencia():
    """'535' es FI_CODIGO de A y FI_REFERENCIA de B: gana el interno."""
    fila_interno = fila("535", "REF-A")
    fila_referencia = fila("88888888", "535")
    result_map, _ = mapear_resultados([fila_interno, fila_referencia], ["535"], {})
    assert result_map == {"535": fila_interno}


def test_prioridad_no_depende_del_orden_de_filas():
    """DBISAM no garantiza orden: el resultado debe ser el mismo al invertirlo."""
    fila_interno = fila("535", "REF-A")
    fila_referencia = fila("88888888", "535")
    directo, _ = mapear_resultados([fila_interno, fila_referencia], ["535"], {})
    invertido, _ = mapear_resultados([fila_referencia, fila_interno], ["535"], {})
    assert directo == invertido == {"535": fila_interno}


def test_prioridad_barra_gana_sobre_interno():
    fila_barra = fila("07110392", "REF-A")
    fila_interno = fila("0-320-038", "REF-B")
    filas = [fila_interno, fila_barra]
    result_map, _ = mapear_resultados(filas, ["0-320-038"], {"07110392": "0-320-038"})
    assert result_map == {"0-320-038": fila_barra}


def test_pedido_vacio():
    assert mapear_resultados([], [], {}) == ({}, [])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_consulta_precios.py -v`
Expected: FAIL con `ImportError: cannot import name 'mapear_resultados'`

- [ ] **Step 3: Write minimal implementation**

Añadir a `database/consulta_precios.py`:

```python
# Rango de prioridad ante colisión: barra > interno > referencia.
# Se resuelve por rango y no por orden de fila porque DBISAM no garantiza
# el orden del resultado: hacerlo por orden sería no determinista.
_RANGO_BARRA = 0
_RANGO_INTERNO = 1
_RANGO_REFERENCIA = 2


def mapear_resultados(filas, productos, por_barra):
    """Resuelve qué fila corresponde a cada código tipeado por el vendedor.

    filas:     filas crudas del query (row[0]=FI_CODIGO, row[5]=FI_REFERENCIA).
    productos: códigos tal como los tipeó el vendedor.
    por_barra: {código_interno: código_de_barra_tipeado}.

    Devuelve (result_map, not_found).
    """
    tipeados = set(productos)
    mejor = {}  # código tipeado -> (rango, fila)

    for fila in filas:
        fi_codigo, fi_referencia = fila[0], fila[5]
        if fi_codigo in por_barra:
            original, rango = por_barra[fi_codigo], _RANGO_BARRA
        elif fi_codigo in tipeados:
            original, rango = fi_codigo, _RANGO_INTERNO
        elif fi_referencia in tipeados:
            original, rango = fi_referencia, _RANGO_REFERENCIA
        else:
            continue  # fila que no reclama ningún código tipeado

        actual = mejor.get(original)
        if actual is None or rango < actual[0]:
            mejor[original] = (rango, fila)

    result_map = {original: fila for original, (_, fila) in mejor.items()}
    not_found = [p for p in productos if p not in result_map]
    return result_map, not_found
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_consulta_precios.py -v`
Expected: PASS (15 passed)

- [ ] **Step 5: Commit**

```bash
git add database/consulta_precios.py tests/test_consulta_precios.py
git commit -m "feat: mapear_resultados con prioridad determinista barra>interno>referencia"
```

---

### Task 3: Rehacer `consultar_precios` sobre las funciones puras

**Files:**
- Modify: `database/dbisam.py:100-156`

**Interfaces:**
- Consumes: `lista_sql(valores) -> str` y `codigos_para_fi_codigo(productos, por_barra) -> list[str]` de Task 1; `mapear_resultados(filas, productos, por_barra) -> (dict, list)` de Task 2.
- Produces: `consultar_precios(productos: list[str], tipo_precio: str) -> tuple[dict, list]` — contrato sin cambios.

**Los tres bugs que cierra este task:**
1. `IN ()` — la lista de `FI_CODIGO` la arma `codigos_para_fi_codigo`, que une lo tipeado + lo resuelto desde `SCODEBAR`, así que nunca queda vacía mientras haya productos.
2. Precedencia — el `OR` va entre paréntesis, y `FI_STATUS = 1` pasa a aplicar a ambas ramas.
3. `not_found` — se deriva de `result_map` dentro de `mapear_resultados`.

- [ ] **Step 1: Añadir el import**

En `database/dbisam.py`, junto al import existente de `database.impuestos` (línea 7):

```python
from database.impuestos import slots_impuesto_linea, campos_impuesto_cabecera
from database.consulta_precios import codigos_para_fi_codigo, lista_sql, mapear_resultados
```

- [ ] **Step 2: Reemplazar el cuerpo completo de `consultar_precios` (líneas 100-156)**

```python
    def consultar_precios(self, productos: list[str], tipo_precio: str):
        """Consulta precios de los códigos tipeados por el vendedor.

        Un código puede ser un código de barra (SCODEBAR), un FI_CODIGO interno
        o una FI_REFERENCIA. Devuelve (result_map, not_found).
        """
        precios = {'P1': 'P01', 'P2': 'P02', 'P3': 'P03'}
        sufijo = precios.get(tipo_precio)
        if sufijo is None:
            # Antes esto producía FIC_NonePRECIOTOTALEXT y un error de sintaxis
            # de DBISAM imposible de rastrear hasta acá.
            raise ValueError(
                f"tipo_precio invalido: {tipo_precio!r}. Esperado uno de {sorted(precios)}"
            )
        if not productos:
            return {}, []

        try:
            lista_tipeados = lista_sql(productos)
            with self.connect_dbisam() as conn:
                with conn.cursor() as cursor:
                    codebar = cursor.execute(
                        f"""SELECT FBARRA_CODE, FBARRA_PRODUCTO
                            FROM SCODEBAR
                            WHERE FBARRA_CODE IN {lista_tipeados}"""
                    ).fetchall()
                    por_barra = {x[1]: x[0] for x in codebar}

                    codigos_internos = codigos_para_fi_codigo(productos, por_barra)

                    query = f"""SELECT FI_CODIGO,
                                       {IMPUESTO_EFECTIVO_SQL} AS IMPUESTO,
                                       FIC_{sufijo}PRECIOTOTALEXT,
                                       FI_DESCRIPCION,
                                       FI_PESOPRODUCTO,
                                       FI_REFERENCIA
                                FROM SINVENTARIO
                                INNER JOIN A2INVCOSTOSPRECIOS ON FIC_CODEITEM = FI_CODIGO
                                WHERE FI_STATUS = 1
                                  AND (FI_CODIGO IN {lista_sql(codigos_internos)}
                                       OR FI_REFERENCIA IN {lista_tipeados})"""
                    filas = cursor.execute(query).fetchall()
                    return mapear_resultados(filas, productos, por_barra)
        except pyodbc.Error as e:
            print("Error en lectura de precios", str(e))
            raise pyodbc.DatabaseError(e)
```

Notas sobre el reemplazo:
- La validación de `tipo_precio` va **fuera** del `try`: el `except` original atrapaba `Exception` y habría convertido el `ValueError` en `DatabaseError`.
- El `except` pasa de `Exception` a `pyodbc.Error` para no disfrazar de error de base un bug de Python. `handlers/Validar_Pedido.py` sigue atrapando `pyodbc.DatabaseError` igual.
- Se eliminan los `print()` de depuración de las líneas 104, 113 y 152, y los cinco comentarios muertos de las líneas 114-118.

- [ ] **Step 3: Correr la suite completa**

Run: `python -m pytest tests/ -q`
Expected: PASS — 65 passed, 1 skipped (los 50 previos + 15 nuevos)

- [ ] **Step 4: Verificar contra DBISAM real — el bug reportado**

El `WHERE` parentizado es SQL que ningún test puro cubre. Este es el caso exacto que fallaba:

```bash
./venv/Scripts/python.exe -c "
from database.dbisam import DBISAMDatabase
result_map, not_found = DBISAMDatabase().consultar_precios(['PT0201001'], 'P1')
print('result_map:', result_map)
print('not_found :', not_found)
"
```

Expected: **no lanza excepción.** Antes moría con `DBISAM Engine Error # 11949 SQL parsing error - Expected expression but instead found )`. En el catálogo local `PT0201001` no existe, así que lo correcto es `result_map: {}` y `not_found: ['PT0201001']`.

- [ ] **Step 5: Verificar contra DBISAM real — un caso que sí resuelve**

```bash
./venv/Scripts/python.exe -c "
from database.dbisam import DBISAMDatabase
db = DBISAMDatabase()
# '07110392' es un FI_CODIGO real; '2661012025306' es su FI_REFERENCIA.
for codigos in (['07110392'], ['2661012025306'], ['07110392', 'NO-EXISTE']):
    result_map, not_found = db.consultar_precios(codigos, 'P1')
    print(codigos, '-> hallados:', list(result_map), '| not_found:', not_found)
"
```

Expected:
```
['07110392']                -> hallados: ['07110392']     | not_found: []
['2661012025306']           -> hallados: ['2661012025306'] | not_found: []
['07110392', 'NO-EXISTE']   -> hallados: ['07110392']     | not_found: ['NO-EXISTE']
```

La primera línea es la que prueba el Bug 3: antes `07110392` aparecía en `not_found` pese a estar hallado.

- [ ] **Step 6: Verificar `tipo_precio` inválido y pedido vacío**

```bash
./venv/Scripts/python.exe -c "
from database.dbisam import DBISAMDatabase
db = DBISAMDatabase()
print('pedido vacio ->', db.consultar_precios([], 'P1'))
try:
    db.consultar_precios(['07110392'], 'P9')
except ValueError as e:
    print('tipo_precio invalido ->', e)
"
```

Expected:
```
pedido vacio -> ({}, [])
tipo_precio invalido -> tipo_precio invalido: 'P9'. Esperado uno de ['P1', 'P2', 'P3']
```

- [ ] **Step 7: Commit**

```bash
git add database/dbisam.py
git commit -m "fix: consultar_precios ya no emite IN () ni se salta FI_STATUS

La lista de FI_CODIGO pasa a ser la union de lo tipeado por el vendedor
mas lo resuelto desde SCODEBAR, con lo que nunca queda vacia y el
'IN ()' que disparaba el DBISAM Engine Error # 11949 se vuelve imposible
por construccion.

Ademas: el OR va entre parentesis, asi FI_STATUS = 1 aplica tambien a la
rama de FI_REFERENCIA (antes un producto descontinuado tipeado por
referencia se cotizaba igual); not_found se deriva de result_map, asi un
producto hallado por FI_CODIGO deja de reportarse como no encontrado; y
un tipo_precio invalido lanza ValueError en vez de un error de sintaxis
SQL incomprensible."
```

---

## Verificación final

- [ ] `python -m pytest tests/ -q` → 65 passed, 1 skipped
- [ ] `git log --oneline fix/consulta-precios-in-vacio` muestra el spec + 3 commits
- [ ] `git status --short` no muestra `database/` ni `tests/` sin commitear
  (`requirements.txt` y `scripts/patch_pywa.py` siguen pendientes por decisión aparte del usuario — **no commitearlos**)
