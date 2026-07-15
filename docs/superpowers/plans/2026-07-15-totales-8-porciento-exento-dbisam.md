# Totales 8% y Exento en DBISAM — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clasificar correctamente la tasa de IVA (16/8/exento) y registrar las bases e impuestos del 8% en el INSERT a DBISAM (SOPERACIONINV/SDETALLEVENTA).

**Architecture:** Dos helpers puros nuevos en `database/impuestos.py` (testeables sin BD) que arman los campos de impuesto de cabecera y de línea; `insert_pedidos` los consume. La tasa efectiva se lee del `MONTO` real de A2 mediante un fragmento SQL único reutilizable.

**Tech Stack:** Python 3, pyodbc + DBISAM (ODBC), pytest.

## Global Constraints

- **DBISAM no soporta parámetros `?`** en `cursor.execute`: usar interpolación en el SQL (como el resto de `dbisam.py`).
- **DBISAM no soporta `TOP n`**: usar `fetchmany(n)` en Python.
- **La tasa efectiva vive en `FIC_IMP0xMONTO`** (0.0 / 8.0 / 16.0), NO es un literal.
- Cada producto tiene exactamente **una** tasa aplicable (16 XOR 8 XOR exento).
- **Exento no tiene campo propio** en SOPERACIONINV: es implícito = `TOTALBRUTO − BASEIMPONIBLE − BASEIMPONIBLE2`.
- `FDI_PORCENTIMPUESTO1` / `FDI_PORCENTIMPUESTO2` son booleanos ("es porcentaje") → valor `1`.
- El `pedido` en el INSERT ya trae `base_16 / base_8 / iva_16 / iva_8` (los pone `ProductoHandler`).
- No tocar el cálculo de totales (`_calcular_totales_y_resumen`, `ProductoHandler`) ni PostgreSQL: ya son correctos.
- Tests: `python -m pytest tests/test_impuestos.py -v`.

---

### Task 1: Helpers puros de impuesto (`database/impuestos.py`)

**Files:**
- Create: `database/impuestos.py`
- Test: `tests/test_impuestos.py`

**Interfaces:**
- Produces:
  - `slots_impuesto_linea(impuesto: float, monto_iva: float) -> dict` con claves `imp1, porc1, monto1, imp2, porc2, monto2`. Enruta 16%→slot 1, 8%→slot 2, exento→ceros.
  - `campos_impuesto_cabecera(pedido: dict) -> dict` con claves `base_imponible, imp1_porcent, imp1_monto, base_imponible2, imp2_porcent, imp2_monto`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_impuestos.py`:

```python
"""Pruebas de los helpers de impuesto para la persistencia a DBISAM.

Ejecutar:  python -m pytest tests/test_impuestos.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.impuestos import slots_impuesto_linea, campos_impuesto_cabecera


def test_slots_linea_16():
    assert slots_impuesto_linea(16, 25.0) == {
        "imp1": 16, "porc1": 1, "monto1": 25.0,
        "imp2": 0,  "porc2": 1, "monto2": 0.0,
    }


def test_slots_linea_8():
    assert slots_impuesto_linea(8, 4.0) == {
        "imp1": 0, "porc1": 1, "monto1": 0.0,
        "imp2": 8, "porc2": 1, "monto2": 4.0,
    }


def test_slots_linea_exento():
    assert slots_impuesto_linea(0, 0.0) == {
        "imp1": 0, "porc1": 1, "monto1": 0.0,
        "imp2": 0, "porc2": 1, "monto2": 0.0,
    }


def test_slots_linea_float_se_normaliza():
    """La tasa llega como float desde SQL (8.0) y debe enrutar al slot 2."""
    s = slots_impuesto_linea(8.0, 4.0)
    assert s["imp2"] == 8 and s["monto2"] == 4.0 and s["monto1"] == 0.0


def test_cabecera_mixta():
    pedido = {"base_16": 100.0, "iva_16": 16.0, "base_8": 50.0, "iva_8": 4.0}
    assert campos_impuesto_cabecera(pedido) == {
        "base_imponible": 100.0, "imp1_porcent": 16, "imp1_monto": 16.0,
        "base_imponible2": 50.0, "imp2_porcent": 8,  "imp2_monto": 4.0,
    }


def test_cabecera_defaults_sin_totales():
    assert campos_impuesto_cabecera({}) == {
        "base_imponible": 0.0, "imp1_porcent": 16, "imp1_monto": 0.0,
        "base_imponible2": 0.0, "imp2_porcent": 8,  "imp2_monto": 0.0,
    }


if __name__ == "__main__":
    test_slots_linea_16()
    test_slots_linea_8()
    test_slots_linea_exento()
    test_slots_linea_float_se_normaliza()
    test_cabecera_mixta()
    test_cabecera_defaults_sin_totales()
    print("OK: helpers de impuesto.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_impuestos.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'database.impuestos'`

- [ ] **Step 3: Write minimal implementation**

Create `database/impuestos.py`:

```python
"""Helpers puros para armar los campos de impuesto del INSERT a DBISAM.

A2 modela dos slots de impuesto por línea (impuesto 1 = 16%, impuesto 2 = 8%)
y separa las bases gravadas por tasa en la cabecera. El exento no tiene campo:
es implícito (TOTALBRUTO - BASEIMPONIBLE - BASEIMPONIBLE2). Extraído para poder
testearlo sin conexión a BD.
"""


def slots_impuesto_linea(impuesto: float, monto_iva: float) -> dict:
    """Enruta la tasa de una línea a los dos slots de impuesto de A2.

    16% -> slot 1, 8% -> slot 2, exento -> ceros. ``porc1``/``porc2`` son el
    booleano "es porcentaje" (siempre 1). La tasa puede llegar como float
    (8.0) desde SQL, por eso se normaliza.
    """
    tasa = round(float(impuesto))
    es_16 = tasa == 16
    es_8 = tasa == 8
    return {
        "imp1": 16 if es_16 else 0,
        "porc1": 1,
        "monto1": monto_iva if es_16 else 0.0,
        "imp2": 8 if es_8 else 0,
        "porc2": 1,
        "monto2": monto_iva if es_8 else 0.0,
    }


def campos_impuesto_cabecera(pedido: dict) -> dict:
    """Arma los campos de impuesto de la cabecera SOPERACIONINV.

    ``base_imponible`` es la base gravada al 16% solamente; ``base_imponible2``
    la base gravada al 8%. Los porcentajes son fijos (16 y 8).
    """
    return {
        "base_imponible": pedido.get("base_16", 0.0),
        "imp1_porcent": 16,
        "imp1_monto": pedido.get("iva_16", 0.0),
        "base_imponible2": pedido.get("base_8", 0.0),
        "imp2_porcent": 8,
        "imp2_monto": pedido.get("iva_8", 0.0),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_impuestos.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add database/impuestos.py tests/test_impuestos.py
git commit -m "feat: helpers puros de slots e impuesto de cabecera para DBISAM"
```

---

### Task 2: Persistir slots 8% en `insert_pedidos` (dbisam.py)

**Files:**
- Modify: `database/dbisam.py` (`insert_pedidos`, ~181-247 detalle y ~271-299 cabecera)

**Interfaces:**
- Consumes: `slots_impuesto_linea(impuesto, monto_iva)` y `campos_impuesto_cabecera(pedido)` de Task 1.

Esta tarea escribe a la BD legada; no hay test automatizado del INSERT. La verificación es por revisión del SQL generado (`print(detalle_query[0])` ya existe) más, opcionalmente, una prueba manual end-to-end con un pedido de 8% + exento. Los valores provienen de los helpers ya probados en Task 1.

- [ ] **Step 1: Importar los helpers**

En `database/dbisam.py`, tras los imports existentes (después de `from pydbisam import PyDBISAM`), agregar:

```python
from database.impuestos import slots_impuesto_linea, campos_impuesto_cabecera
```

- [ ] **Step 2: Calcular slots por línea**

Dentro de `insert_pedidos`, en el bucle `for codigo, detalles in pedido['productos'].items():` (línea ~186), como primera instrucción del cuerpo del bucle (antes de `detalle_query.append(...)`), agregar:

```python
                slots = slots_impuesto_linea(detalles['impuesto'], detalles['monto_iva'])
```

- [ ] **Step 3: Añadir columnas del slot 2 en SDETALLEVENTA**

En el bloque de columnas del INSERT de SDETALLEVENTA, reemplazar:

```python
                                                        FDI_IMPUESTO1,
                                                        FDI_PORCENTIMPUESTO1,
                                                        FDI_MONTOIMPUESTO1,
```

por:

```python
                                                        FDI_IMPUESTO1,
                                                        FDI_PORCENTIMPUESTO1,
                                                        FDI_MONTOIMPUESTO1,
                                                        FDI_IMPUESTO2,
                                                        FDI_PORCENTIMPUESTO2,
                                                        FDI_MONTOIMPUESTO2,
```

- [ ] **Step 4: Enrutar los valores a los slots correctos**

En el bloque de `VALUES` del mismo INSERT, reemplazar:

```python
                                                        {detalles['impuesto']},
                                                        {1 if detalles['impuesto'] > 0 else 0},
                                                        {detalles['monto_iva']},
```

por:

```python
                                                        {slots['imp1']},
                                                        {slots['porc1']},
                                                        {slots['monto1']},
                                                        {slots['imp2']},
                                                        {slots['porc2']},
                                                        {slots['monto2']},
```

- [ ] **Step 5: Calcular campos de cabecera**

En `insert_pedidos`, tras `ID_PEDIDO = f"WS{uuid.uuid4().hex[:10].upper()}"` (línea ~185), agregar:

```python
            cab = campos_impuesto_cabecera(pedido)
```

- [ ] **Step 6: Añadir columnas del impuesto 2 en SOPERACIONINV**

En el bloque de columnas del INSERT de SOPERACIONINV, reemplazar:

```python
                                                                 FTI_BASEIMPONIBLE,
                                                                 FTI_IMPUESTO1PORCENT,
                                                                 FTI_IMPUESTO1MONTO,     
                                                                 FTI_TOTALNETO,
```

por:

```python
                                                                 FTI_BASEIMPONIBLE,
                                                                 FTI_IMPUESTO1PORCENT,
                                                                 FTI_IMPUESTO1MONTO,
                                                                 FTI_BASEIMPONIBLE2,
                                                                 FTI_IMPUESTO2PORCENT,
                                                                 FTI_IMPUESTO2MONTO,
                                                                 FTI_TOTALNETO,
```

- [ ] **Step 7: Enrutar los valores de cabecera**

En el bloque de `VALUES` del INSERT de SOPERACIONINV, reemplazar:

```python
                                                {pedido['baseimponible']},
                                                16,
                                                {pedido['iva_16']},
                                                {pedido['total_neto']},
```

por:

```python
                                                {cab['base_imponible']},
                                                {cab['imp1_porcent']},
                                                {cab['imp1_monto']},
                                                {cab['base_imponible2']},
                                                {cab['imp2_porcent']},
                                                {cab['imp2_monto']},
                                                {pedido['total_neto']},
```

- [ ] **Step 8: Verificar que Python compila y el resto de pruebas siguen verdes**

Run: `python -c "import ast; ast.parse(open('database/dbisam.py', encoding='utf-8').read()); print('OK sintaxis')"`
Expected: `OK sintaxis`

Run: `python -m pytest -q`
Expected: PASS (sin regresiones)

- [ ] **Step 9: Commit**

```bash
git add database/dbisam.py
git commit -m "feat: registrar base e impuesto del 8% en SOPERACIONINV/SDETALLEVENTA"
```

---

### Task 3: Fijar la tasa efectiva desde `FIC_IMP0xMONTO` (dbisam.py)

**Files:**
- Modify: `database/dbisam.py` (`consultar_precios`, `CASE` en ~110-114; nueva constante de módulo)
- Create: `scripts/verificar_impuestos.py`

**Interfaces:**
- Produces: constante de módulo `IMPUESTO_EFECTIVO_SQL` (fragmento SQL) reutilizada por `consultar_precios` y por el script de verificación.

La clasificación vive en SQL contra la BD, así que la verificación es un script de **solo lectura** que corre el fragmento contra los códigos conocidos (`01010030`→8, `01010029`→0). Un solo `IMPUESTO_EFECTIVO_SQL` evita duplicar la lógica (DRY).

- [ ] **Step 1: Definir el fragmento SQL único**

En `database/dbisam.py`, a nivel de módulo (tras los imports, antes de `class DBISAMDatabase`), agregar:

```python
# Tasa efectiva de IVA de un ítem: la tasa real vive en FIC_IMP0xMONTO
# (no es un literal 16/8). Cada impuesto se valida con SU propio flag exento.
# Un ítem tiene una sola tasa aplicable, así que la suma da la tasa efectiva.
IMPUESTO_EFECTIVO_SQL = (
    "(CASE WHEN FIC_IMP01ACTIVO = 1 AND FIC_IMP01EXENTO = 0 THEN FIC_IMP01MONTO ELSE 0 END)"
    " + (CASE WHEN FIC_IMP02ACTIVO = 1 AND FIC_IMP02EXENTO = 0 THEN FIC_IMP02MONTO ELSE 0 END)"
)
```

- [ ] **Step 2: Usar el fragmento en `consultar_precios`**

En el query de `consultar_precios`, reemplazar el bloque:

```python
                    query=f"""SELECT FI_CODIGO, 
                                        CASE WHEN FIC_IMP01ACTIVO = 1 AND FIC_IMP01EXENTO = 0 THEN 16
                                             WHEN FIC_IMP02ACTIVO = 1 AND FIC_IMP01EXENTO = 0 THEN 8
                                             WHEN FIC_IMP01ACTIVO = 0 AND FIC_IMP01EXENTO = 1 THEN 0
                                        ELSE 0
                                        END AS IMPUESTO,
```

por:

```python
                    query=f"""SELECT FI_CODIGO, 
                                        {IMPUESTO_EFECTIVO_SQL} AS IMPUESTO,
```

- [ ] **Step 3: Escribir el script de verificación (solo lectura)**

Create `scripts/verificar_impuestos.py`:

```python
"""Verificación de solo lectura de la clasificación de tasa de IVA.

Corre el fragmento IMPUESTO_EFECTIVO_SQL contra códigos conocidos y asserta:
  01010030 (8%)     -> 8
  01010029 (exento) -> 0

Ejecutar:  python scripts/verificar_impuestos.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.dbisam import DBISAMDatabase, IMPUESTO_EFECTIVO_SQL

ESPERADO = {"01010030": 8, "01010029": 0}

db = DBISAMDatabase()
codes = "(" + ",".join(f"'{c}'" for c in ESPERADO) + ")"
with db.connect_dbisam() as conn, conn.cursor() as cur:
    cur.execute(
        f"""SELECT FI_CODIGO, {IMPUESTO_EFECTIVO_SQL} AS IMPUESTO
            FROM SINVENTARIO
            INNER JOIN A2INVCOSTOSPRECIOS ON FIC_CODEITEM = FI_CODIGO
            WHERE FI_CODIGO IN {codes}"""
    )
    obtenido = {row[0]: round(float(row[1])) for row in cur.fetchall()}

print("Obtenido:", obtenido)
for cod, tasa in ESPERADO.items():
    assert obtenido.get(cod) == tasa, f"{cod}: esperaba {tasa}, obtuvo {obtenido.get(cod)}"
print("OK: clasificación de tasa correcta.")
```

- [ ] **Step 4: Correr la verificación contra la BD**

Run: `venv/Scripts/python.exe scripts/verificar_impuestos.py`
Expected: `OK: clasificación de tasa correcta.`

- [ ] **Step 5: Confirmar que no hay regresiones en las pruebas puras**

Run: `python -m pytest -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add database/dbisam.py scripts/verificar_impuestos.py
git commit -m "fix: leer la tasa efectiva de IVA desde FIC_IMP0xMONTO"
```

---

## Notas de verificación final

Tras las 3 tareas, un pedido con un producto de 8% y uno exento debe:
1. Mostrar `base_8`, `iva_8` y `exento` distintos de cero en el RESUMEN/preliminar (corregido por Task 3).
2. Insertar en SOPERACIONINV `FTI_BASEIMPONIBLE2` = base 8% y `FTI_IMPUESTO2MONTO` = IVA 8% (Task 2).
3. Insertar cada línea de 8% con el impuesto en el slot 2 (`FDI_IMPUESTO2/MONTOIMPUESTO2`) (Task 2).

El exento queda implícito: `FTI_TOTALBRUTO − FTI_BASEIMPONIBLE − FTI_BASEIMPONIBLE2`.
