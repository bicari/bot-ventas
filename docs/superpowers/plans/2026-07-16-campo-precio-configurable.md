# Campo de precio configurable — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que el campo de `A2INVCOSTOSPRECIOS` del que salen los precios se elija desde el `.env` con `CAMPO_PRECIO`, validado al arrancar el servidor.

**Architecture:** Módulo nuevo `database/campo_precio.py` calcado de `pdf/factory.py`: lee config con default y valida ruidosamente. La lógica es pura (se prueba sin DBISAM); la única parte impura es `DBISAMDatabase.columnas_precio()`, que solo trae nombres de columna. La validación se engancha en el `lifespan` de FastAPI, así un typo impide arrancar en vez de reventar a mitad de un pedido.

**Tech Stack:** Python 3.11, python-decouple, pyodbc + DBISAM (ODBC), FastAPI, pytest.

**Spec:** `docs/superpowers/specs/2026-07-16-campo-precio-configurable-design.md`

**Rama:** `feat/campo-precio-configurable` (ya creada; el spec está commiteado ahí).

## Global Constraints

- **`CAMPO_PRECIO` default `PRECIOTOTALEXT`.** Sin la variable en el `.env`, el comportamiento no cambia en absoluto. Esto no es negociable: hay instalaciones corriendo.
- **El driver ODBC de DBISAM NO acepta parámetros** (`Invalid SQL data type (11047)`). El valor se interpola en el SQL, así que la validación de formato es la defensa contra inyección, no un detalle estético.
- **Normalizar, no rechazar.** El valor pasa por `.strip().upper()` ANTES de validar el formato, siguiendo el precedente de `pdf/factory.py` (que hace `.strip().lower()`). Minúsculas y espacios alrededor son válidos. El `.strip()` importa de verdad: el `.env` de este proyecto ya tiene `DSN= A2GKC` con espacio inicial.
- **`IPRECIOTOTAL` se rechaza siempre.** Trae el IVA incluido (ratio 1.1600 medido contra la base) y `handlers/Validar_Pedido.py:69-70` lo sumaría de nuevo: facturaría con IVA doble sin error visible.
- **Tiers usados: `P01`, `P02`, `P03`.** Son los que `consultar_precios` mapea desde `P1/P2/P3`. Los seis que existen en el esquema no están en alcance.
- **Las pruebas son puras**, sin base de datos ni `.env`, con monkeypatch de `config` siguiendo `tests/test_factory_pdf.py`.
- **pytest corre con el Python del sistema** (`python -m pytest`), no con el del venv — el venv no tiene pytest. Las verificaciones contra DBISAM sí van con `./venv/Scripts/python.exe`.

---

## File Structure

| Archivo | Responsabilidad |
|---|---|
| `database/campo_precio.py` *(nuevo)* | Lógica pura: leer y normalizar `CAMPO_PRECIO`, validar formato, rechazar `IPRECIOTOTAL`, y verificar existencia contra un conjunto de columnas que recibe por parámetro. Sin imports de pyodbc. |
| `tests/test_campo_precio.py` *(nuevo)* | Pruebas puras del módulo anterior. |
| `database/dbisam.py` *(modificar)* | `columnas_precio()` nuevo (trae nombres de columna, sin lógica) y una línea de `consultar_precios` que pasa a usar el campo configurado. |
| `main.py:44-47` *(modificar)* | El `lifespan` valida al arrancar. |

---

### Task 1: `get_campo_precio` — leer, normalizar y rechazar

**Files:**
- Create: `database/campo_precio.py`
- Test: `tests/test_campo_precio.py`

**Interfaces:**
- Consumes: nada.
- Produces:
  - `CAMPO_PRECIO_DEFAULT: str` = `"PRECIOTOTALEXT"`
  - `TIERS: tuple[str, ...]` = `("P01", "P02", "P03")`
  - `get_campo_precio() -> str`. Devuelve la variante normalizada. Lanza `ValueError` si el formato es inválido o si es `IPRECIOTOTAL`.

- [ ] **Step 1: Write the failing tests**

Crear `tests/test_campo_precio.py`:

```python
"""Pruebas de la selección del campo de precio configurable por CAMPO_PRECIO.

Sigue el patrón de tests/test_factory_pdf.py: se monkeypatchea `config`, así que
no hace falta .env ni base de datos.

Ejecutar:  python -m pytest tests/test_campo_precio.py
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import campo_precio


def _con_valor(monkeypatch, valor):
    """Hace que config() devuelva `valor`, como si estuviera en el .env."""
    monkeypatch.setattr(campo_precio, "config", lambda k, default=None: valor)


def test_default_es_preciototalext(monkeypatch):
    """Sin CAMPO_PRECIO en el .env, nada cambia para las instalaciones actuales."""
    monkeypatch.delenv("CAMPO_PRECIO", raising=False)
    monkeypatch.setattr(campo_precio, "config", lambda k, default=None: default)
    assert campo_precio.get_campo_precio() == "PRECIOTOTALEXT"


def test_normaliza_minusculas_y_espacios(monkeypatch):
    """Las columnas de DBISAM son mayúsculas: normalizar, no castigar el typo."""
    _con_valor(monkeypatch, "  preciosinimpuesto  ")
    assert campo_precio.get_campo_precio() == "PRECIOSINIMPUESTO"


def test_espacio_interno_es_error(monkeypatch):
    _con_valor(monkeypatch, "PRECIO TOTAL")
    with pytest.raises(ValueError):
        campo_precio.get_campo_precio()


def test_comilla_simple_es_error(monkeypatch):
    """El valor se interpola en SQL: la comilla no puede pasar."""
    _con_valor(monkeypatch, "PRECIOTOTALEXT' OR '1'='1")
    with pytest.raises(ValueError):
        campo_precio.get_campo_precio()


def test_ipreciototal_rechazado_menciona_iva(monkeypatch):
    """Trae el IVA incluido y Validar_Pedido lo sumaría de nuevo."""
    _con_valor(monkeypatch, "IPRECIOTOTAL")
    with pytest.raises(ValueError, match="(?i)iva"):
        campo_precio.get_campo_precio()


def test_ipreciototal_rechazado_tambien_en_minusculas(monkeypatch):
    """El rechazo no se esquiva escribiéndolo distinto: se normaliza antes."""
    _con_valor(monkeypatch, "ipreciototal")
    with pytest.raises(ValueError, match="(?i)iva"):
        campo_precio.get_campo_precio()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_campo_precio.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'database.campo_precio'`

- [ ] **Step 3: Write minimal implementation**

Crear `database/campo_precio.py`:

```python
"""Selección del campo de precio de A2INVCOSTOSPRECIOS, configurable por .env.

Sigue el patrón de pdf/factory.py: lee config con un default y valida
ruidosamente. La lógica es pura para poder probarse sin DBISAM.
"""

import re

from decouple import config

CAMPO_PRECIO_DEFAULT = "PRECIOTOTALEXT"

# Tiers que consultar_precios mapea (P1/P2/P3 -> P01/P02/P03). El esquema tiene
# hasta P06, pero habilitarlos es otra feature.
TIERS = ("P01", "P02", "P03")

# El valor se interpola en el SQL porque el driver ODBC de DBISAM no acepta
# parámetros. Esta regex es la defensa contra inyección, no un detalle estético.
_FORMATO = re.compile(r"^[A-Z0-9]+$")

# IPRECIOTOTAL trae el IVA incluido (IPRECIOTOTAL/PRECIOSINIMPUESTO = 1.1600,
# medido contra la base). Validar_Pedido.py:69-70 suma el IVA sobre el precio,
# así que configurarlo facturaría con IVA doble sin ningún error visible.
_CON_IVA_INCLUIDO = "IPRECIOTOTAL"


def get_campo_precio() -> str:
    """Devuelve la variante de precio indicada por CAMPO_PRECIO, normalizada."""
    campo = config("CAMPO_PRECIO", default=CAMPO_PRECIO_DEFAULT).strip().upper()

    if not _FORMATO.match(campo):
        raise ValueError(
            f"CAMPO_PRECIO={campo!r} no es valido: solo letras y digitos. "
            "El valor se interpola en SQL, asi que no se aceptan espacios, "
            "comillas, guiones ni punto y coma."
        )

    if campo == _CON_IVA_INCLUIDO:
        raise ValueError(
            f"CAMPO_PRECIO={campo!r} trae el IVA ya incluido y el sistema lo "
            "suma de nuevo: facturaria con IVA doble. Use PRECIOTOTALEXT o "
            "PRECIOSINIMPUESTO, que vienen sin impuesto."
        )

    return campo
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_campo_precio.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add database/campo_precio.py tests/test_campo_precio.py
git commit -m "feat: get_campo_precio lee y valida CAMPO_PRECIO del .env"
```

---

### Task 2: `validar_campo_precio` — existencia contra el esquema

**Files:**
- Modify: `database/campo_precio.py`
- Test: `tests/test_campo_precio.py`

**Interfaces:**
- Consumes: `TIERS` y `_CON_IVA_INCLUIDO` de Task 1.
- Produces: `validar_campo_precio(campo: str, columnas_existentes) -> None`. Lanza `ValueError` si falta `FIC_{tier}{campo}` para algún tier de `TIERS`. El mensaje lista las variantes derivadas (excluyendo `IPRECIOTOTAL`), no las columnas crudas.

**Por qué recibe las columnas por parámetro:** mantiene la función pura y testeable sin DBISAM. La parte que toca la base (`columnas_precio()`, Task 3) queda tonta: solo trae nombres.

- [ ] **Step 1: Write the failing tests**

Añadir a `tests/test_campo_precio.py`:

```python
# Columnas de A2INVCOSTOSPRECIOS tal como las devuelve el esquema real,
# recortadas a lo que importa para estas pruebas.
COLUMNAS_REALES = {
    "FIC_CODEITEM",
    "FIC_P01PRECIOSINIMPUESTO", "FIC_P01IPRECIOTOTAL", "FIC_P01PRECIOTOTALEXT",
    "FIC_P02PRECIOSINIMPUESTO", "FIC_P02IPRECIOTOTAL", "FIC_P02PRECIOTOTALEXT",
    "FIC_P03PRECIOSINIMPUESTO", "FIC_P03IPRECIOTOTAL", "FIC_P03PRECIOTOTALEXT",
}


def test_campo_valido_en_los_tres_tiers_pasa():
    assert campo_precio.validar_campo_precio("PRECIOTOTALEXT", COLUMNAS_REALES) is None


def test_campo_inexistente_es_error():
    with pytest.raises(ValueError):
        campo_precio.validar_campo_precio("PRECIOTOTALEX", COLUMNAS_REALES)


def test_error_lista_las_variantes_no_las_columnas_crudas():
    """El mensaje debe ser accionable: las variantes, no las ~30 columnas."""
    with pytest.raises(ValueError) as exc:
        campo_precio.validar_campo_precio("NOEXISTE", COLUMNAS_REALES)
    mensaje = str(exc.value)
    assert "PRECIOTOTALEXT" in mensaje
    assert "PRECIOSINIMPUESTO" in mensaje
    assert "FIC_CODEITEM" not in mensaje  # no vuelca columnas que no son variantes


def test_las_variantes_sugeridas_no_incluyen_ipreciototal():
    """No sugerir la unica columna que get_campo_precio rechaza.

    Existe en el esquema, pero mandaria al usuario derecho al IVA doble.
    """
    with pytest.raises(ValueError) as exc:
        campo_precio.validar_campo_precio("NOEXISTE", COLUMNAS_REALES)
    assert "IPRECIOTOTAL" not in str(exc.value)


def test_falta_en_un_tier_es_error():
    """Si existe para P01 pero no para P03, se sabe al arrancar y no cuando
    un vendedor pida P3."""
    columnas = COLUMNAS_REALES - {"FIC_P03PRECIOTOTALEXT"}
    with pytest.raises(ValueError, match="FIC_P03PRECIOTOTALEXT"):
        campo_precio.validar_campo_precio("PRECIOTOTALEXT", columnas)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_campo_precio.py -v`
Expected: FAIL con `AttributeError: module 'database.campo_precio' has no attribute 'validar_campo_precio'`

- [ ] **Step 3: Write minimal implementation**

Añadir a `database/campo_precio.py`:

```python
def _variantes_disponibles(columnas) -> list:
    """Deriva las variantes legibles quitando el prefijo FIC_P01 de las columnas.

    Convierte {'FIC_P01PRECIOTOTALEXT', ...} en ['PRECIOTOTALEXT', ...], que es
    lo que el usuario escribe en CAMPO_PRECIO. Volcar las ~30 columnas crudas no
    le serviria de nada.

    Excluye _CON_IVA_INCLUIDO: existe en el esquema, pero get_campo_precio lo
    rechaza, y sugerirlo mandaria al usuario derecho al IVA doble.
    """
    prefijo = "FIC_" + TIERS[0]
    return sorted(
        c[len(prefijo):]
        for c in columnas
        if c.startswith(prefijo) and c[len(prefijo):] != _CON_IVA_INCLUIDO
    )


def validar_campo_precio(campo, columnas_existentes) -> None:
    """Verifica que FIC_{tier}{campo} exista para todos los tiers en uso.

    columnas_existentes: nombres de columna de A2INVCOSTOSPRECIOS.
    Lanza ValueError si falta alguna.
    """
    columnas = {c.upper() for c in columnas_existentes}
    faltantes = [f"FIC_{t}{campo}" for t in TIERS if f"FIC_{t}{campo}" not in columnas]
    if faltantes:
        raise ValueError(
            f"CAMPO_PRECIO={campo!r} no existe en A2INVCOSTOSPRECIOS: "
            f"faltan {', '.join(faltantes)}. "
            f"Variantes disponibles: {', '.join(_variantes_disponibles(columnas))}"
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_campo_precio.py -v`
Expected: PASS (11 passed)

- [ ] **Step 5: Commit**

```bash
git add database/campo_precio.py tests/test_campo_precio.py
git commit -m "feat: validar_campo_precio verifica la columna contra el esquema"
```

---

### Task 3: Enganchar en `consultar_precios` y en el arranque

**Files:**
- Modify: `database/dbisam.py` (import, `columnas_precio()` nuevo, una línea de `consultar_precios`)
- Modify: `main.py` (import y `lifespan`)

**Interfaces:**
- Consumes: `get_campo_precio() -> str` y `validar_campo_precio(campo, columnas_existentes) -> None` de Tasks 1 y 2.
- Produces: `DBISAMDatabase.columnas_precio() -> set[str]` — todos los nombres de columna de `A2INVCOSTOSPRECIOS`, en mayúsculas.

- [ ] **Step 1: Añadir el import en `database/dbisam.py`**

Junto a los imports existentes de `database.*` (líneas 7-8):

```python
from database.impuestos import slots_impuesto_linea, campos_impuesto_cabecera
from database.consulta_precios import codigos_para_fi_codigo, lista_sql, mapear_resultados
from database.campo_precio import get_campo_precio
```

- [ ] **Step 2: Añadir `columnas_precio()` a `DBISAMDatabase`**

Insertar justo después del método `connect_dbisam` (que termina con `return conn`):

```python
    def columnas_precio(self) -> set:
        """Nombres de columna de A2INVCOSTOSPRECIOS, para validar CAMPO_PRECIO.

        Sin logica: solo trae nombres. Quien decide es validar_campo_precio, que
        es pura y se prueba sin DBISAM.
        """
        with self.connect_dbisam() as conn:
            with conn.cursor() as cursor:
                return {
                    c.column_name.upper()
                    for c in cursor.columns(table="A2INVCOSTOSPRECIOS")
                }
```

- [ ] **Step 3: Usar el campo configurado en `consultar_precios`**

En el `query` de `consultar_precios`, reemplazar la línea del precio:

```python
                                       FIC_{sufijo}PRECIOTOTALEXT,
```

por:

```python
                                       FIC_{sufijo}{get_campo_precio()},
```

- [ ] **Step 4: Validar al arrancar en `main.py`**

Añadir el import junto a los otros de `database.*` (líneas 16-22):

```python
from database.campo_precio import get_campo_precio, validar_campo_precio
```

Y reemplazar el `lifespan` (líneas 44-47):

```python
@asynccontextmanager
async def lifespan(app: fastapi.FastAPI):
    create_tables_and_db()
    # Un CAMPO_PRECIO mal escrito debe impedir arrancar, no reventar a mitad
    # de un pedido con un error de sintaxis de DBISAM.
    validar_campo_precio(get_campo_precio(), DBISAMDatabase().columnas_precio())
    yield
```

- [ ] **Step 5: Correr la suite completa**

Run: `python -m pytest tests/ -q`
Expected: PASS — 76 passed, 1 skipped (los 65 previos + 11 nuevos)

- [ ] **Step 6: Verificar contra DBISAM real — el default no cambia nada**

```bash
./venv/Scripts/python.exe -c "
from database.campo_precio import get_campo_precio, validar_campo_precio
from database.dbisam import DBISAMDatabase
db = DBISAMDatabase()
print('campo:', get_campo_precio())
validar_campo_precio(get_campo_precio(), db.columnas_precio())
print('validacion: OK')
print('07110392 ->', db.consultar_precios(['07110392'], 'P1')[0]['07110392'][2])
"
```

Expected: `campo: PRECIOTOTALEXT`, `validacion: OK`, y el precio `52.67` — el mismo de antes del cambio.

- [ ] **Step 7: Verificar contra DBISAM real — el typo no deja arrancar**

```bash
CAMPO_PRECIO=PRECIOTOTALEX ./venv/Scripts/python.exe -c "
from database.campo_precio import get_campo_precio, validar_campo_precio
from database.dbisam import DBISAMDatabase
try:
    validar_campo_precio(get_campo_precio(), DBISAMDatabase().columnas_precio())
    print('ERROR: deberia haber fallado')
except ValueError as e:
    print('typo detectado:', e)
"
```

Expected: un `ValueError` que mencione `FIC_P01PRECIOTOTALEX` y liste las variantes disponibles (`PRECIOSINIMPUESTO, PRECIOTOTALEXT`) — **sin** `IPRECIOTOTAL`, que existe en el esquema pero está rechazado.

- [ ] **Step 8: Verificar contra DBISAM real — la otra escala**

```bash
CAMPO_PRECIO=PRECIOSINIMPUESTO ./venv/Scripts/python.exe -c "
from database.campo_precio import get_campo_precio, validar_campo_precio
from database.dbisam import DBISAMDatabase
db = DBISAMDatabase()
validar_campo_precio(get_campo_precio(), db.columnas_precio())
print('campo:', get_campo_precio())
print('07110392 ->', db.consultar_precios(['07110392'], 'P1')[0]['07110392'][2])
"
```

Expected: `campo: PRECIOSINIMPUESTO` y el precio `7473.75` en vez de `52.67`. Esto prueba que la feature realmente cambia el origen del precio.

- [ ] **Step 9: Verificar contra DBISAM real — IPRECIOTOTAL rechazado**

```bash
CAMPO_PRECIO=IPRECIOTOTAL ./venv/Scripts/python.exe -c "
from database.campo_precio import get_campo_precio
try:
    get_campo_precio()
    print('ERROR: deberia haber fallado')
except ValueError as e:
    print('rechazado:', e)
"
```

Expected: un `ValueError` explicando el IVA doble. Nótese que falla en `get_campo_precio()`, antes de tocar la base.

- [ ] **Step 10: Documentar `CAMPO_PRECIO` en `CLAUDE.md`**

En la sección "Variables de Entorno (`.env`)", añadir debajo de la línea de `FORMATO_PDF`:

```
CAMPO_PRECIO=PRECIOTOTALEXT                      # Variante de precio en A2INVCOSTOSPRECIOS
```

Y en "Notas Críticas", añadir al final de la lista:

```markdown
- **`CAMPO_PRECIO`** elige la variante de precio de `A2INVCOSTOSPRECIOS` (`FIC_{P01|P02|P03}{CAMPO_PRECIO}`). Default `PRECIOTOTALEXT`. Se valida al arrancar: un typo impide levantar el servidor. `IPRECIOTOTAL` está rechazado a propósito porque trae el IVA incluido y `Validar_Pedido` lo sumaría de nuevo. Ojo: las variantes no son equivalentes — para el mismo producto, `PRECIOTOTALEXT` da 52.67 y `PRECIOSINIMPUESTO` da 7473.75.
```

- [ ] **Step 11: Commit**

```bash
git add database/dbisam.py main.py CLAUDE.md
git commit -m "feat: el campo de precio se elige con CAMPO_PRECIO en el .env

consultar_precios pasa a leer FIC_{tier}{CAMPO_PRECIO} en vez de tener
PRECIOTOTALEXT fijo. El default mantiene el comportamiento actual, asi
que las instalaciones existentes no cambian.

La validacion corre en el lifespan de FastAPI: un typo impide arrancar
en vez de reventar a mitad de un pedido con un error de sintaxis de
DBISAM. IPRECIOTOTAL se rechaza porque trae el IVA incluido y
Validar_Pedido lo sumaria de nuevo."
```

---

## Verificación final

- [ ] `python -m pytest tests/ -q` → 75 passed, 1 skipped
- [ ] Sin `CAMPO_PRECIO` en el `.env`, el precio de `07110392` sigue siendo `52.67`
- [ ] `git status --short` no muestra `database/`, `tests/` ni `main.py` sin commitear
  (`requirements.txt` y `scripts/patch_pywa.py` siguen pendientes por decisión aparte del usuario — **no commitearlos**)
