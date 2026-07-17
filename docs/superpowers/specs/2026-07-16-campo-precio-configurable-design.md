# Campo de precio configurable desde `.env`

- **Fecha:** 2026-07-16
- **Estado:** aprobado, pendiente de plan de implementación
- **Componente:** `database/dbisam.py::consultar_precios`, módulo nuevo `database/campo_precio.py`

## Objetivo

Que el campo de `A2INVCOSTOSPRECIOS` del que salen los precios sea configurable
desde el `.env`, en vez de estar fijo en `PRECIOTOTALEXT`.

## Contexto: el esquema real

`A2INVCOSTOSPRECIOS` tiene los precios en **dos ejes**:

```
FIC_P01..P06  ×  {PRECIOSINIMPUESTO | IPRECIOTOTAL | PRECIOTOTALEXT}
     tier                    variante
```

Hoy el tier lo elige el vendedor (`P1`/`P2` en el mensaje; `consultar_precios`
mapea `P1/P2/P3` → `P01/P02/P03`) y la variante está fija en `PRECIOTOTALEXT`.
**Este spec hace configurable la variante.** El tier no se toca.

### Las tres variantes NO son equivalentes

Valores reales del producto `07110392`:

```
FIC_P01PRECIOSINIMPUESTO = 7473.75
FIC_P01IPRECIOTOTAL      = 8669.55   = 7473.75 × 1.16
FIC_P01PRECIOTOTALEXT    =   52.67
```

Dos hechos medidos contra la base, que sostienen las decisiones de abajo:

1. **`IPRECIOTOTAL` trae el IVA incluido.** `IPRECIOTOTAL / PRECIOSINIMPUESTO =
   1.1600` en toda la muestra.
2. **`PRECIOSINIMPUESTO` y `PRECIOTOTALEXT` no tienen relación aritmética.** El
   ratio entre ambos toma 6696 valores distintos entre 26388 productos activos
   (de 65 a 1035). No es una conversión de moneda ni un factor: son precios
   mantenidos por separado.

### Hipótesis descartada

Se sospechó que `PRECIOTOTALEXT` era el precio en moneda extranjera ("EXT" =
extranjera) y que el ratio contra `PRECIOSINIMPUESTO` sería la tasa de cambio.
**Falso:** el ratio no es constante (ver arriba). Queda registrado para que nadie
vuelva a asumirlo.

## Decisiones tomadas

| Decisión | Valor |
|---|---|
| Forma de configurar | Nombre de columna libre en el `.env` |
| Variable | `CAMPO_PRECIO` |
| Default | `PRECIOTOTALEXT` (comportamiento actual: sin `.env` nada cambia) |
| Cuándo falla un typo | Al arrancar el servidor, nunca en medio de un pedido |
| `IPRECIOTOTAL` | Rechazado explícitamente |
| Tiers validados | `P01`, `P02`, `P03` (los que `consultar_precios` mapea) |

Se evaluó y descartó una whitelist de columnas conocidas (estilo `pdf/factory.py`):
no permite el nombre libre que se pidió.

## Diseño

### Arquitectura

Módulo nuevo `database/campo_precio.py`, siguiendo el precedente de
`pdf/factory.py` (lee config con default, valida, lanza `ValueError` listando las
opciones válidas; probado con monkeypatch de `config`, sin `.env` ni base).

- **`get_campo_precio() -> str`** — lee `CAMPO_PRECIO`, default `PRECIOTOTALEXT`.
  Valida formato y rechaza `IPRECIOTOTAL`.
- **`validar_campo_precio(campo, columnas_existentes)`** — **puro**: recibe el
  conjunto de nombres de columna de `A2INVCOSTOSPRECIOS` y verifica que existan
  las tres que se usarán (`FIC_P01{campo}`, `FIC_P02{campo}`, `FIC_P03{campo}`).
  No consulta la base, así se prueba sin DBISAM.
- **`DBISAMDatabase.columnas_precio() -> set[str]`** — la parte impura: devuelve
  el conjunto de **todos** los nombres de columna de `A2INVCOSTOSPRECIOS`, sin
  filtrar. Toda la lógica vive en la función pura.

El reparto es deliberado: la parte que toca DBISAM es tonta (trae nombres), y la
que decide es pura (y por lo tanto testeable sin el motor legado).

`consultar_precios` cambia una sola línea: `FIC_{sufijo}PRECIOTOTALEXT` pasa a
`FIC_{sufijo}{get_campo_precio()}`. Su firma y su contrato no cambian.

### Flujo

```
lifespan (main.py:45)
  ├─ columnas = DBISAMDatabase().columnas_precio()   ← esquema real
  └─ validar_campo_precio(campo, columnas)           ← puro
       ok     → el server arranca
       falla  → ValueError, el server NO arranca

consultar_precios  →  FIC_{P01|P02|P03}{CAMPO_PRECIO}
```

Se validan los tres tiers al arrancar. Si la columna existe para `P01` pero no
para `P03`, se sabe al bootear y no cuando un vendedor pida `P3`.

### Las tres capas de validación

**1. Formato** — el valor se normaliza con `.strip().upper()` y después se exige
`^[A-Z0-9]+$`. Se normaliza en vez de rechazar, siguiendo el precedente de
`pdf/factory.py` (que hace `.strip().lower()`): las columnas de DBISAM son
mayúsculas, así que `preciototalext` es un typo inofensivo y se acepta. El
`.strip()` no es de adorno — el `.env` de este proyecto ya tiene valores con
espacio inicial (`DSN= A2GKC`).

Lo que la regex rechaza es todo lo que no sea alfanumérico: espacios internos,
comillas, guiones, punto y coma. No es cosmético — el valor se interpola en el
SQL (el driver ODBC de DBISAM no acepta parámetros), y esta regex es lo que
impide que el `.env` inyecte SQL.

**2. `IPRECIOTOTAL` rechazado** — trae el IVA incluido, y `Validar_Pedido.py:69-70`
lo sumaría otra vez sobre el precio. Configurarlo facturaría con IVA doble sin
ningún error visible. Es la única columna donde hay prueba (ratio 1.1600 medido).

**3. Existencia real** — contra el esquema de `A2INVCOSTOSPRECIOS`. El mensaje de
error lista las **variantes** disponibles, no las columnas crudas: se derivan
tomando las columnas que empiezan con `FIC_P01` y quitándoles ese prefijo, lo que
produce `PRECIOSINIMPUESTO, PRECIOTOTALEXT` en vez de volcar las ~30 columnas de
la tabla. Es la misma idea que `factory.py` listando los formatos válidos. Esa
derivación es lógica pura y va en `validar_campo_precio`.

La lista **excluye `IPRECIOTOTAL`** aunque exista en el esquema: la capa 2 lo
rechaza, y sugerirlo mandaría al usuario derecho al IVA doble. Un mensaje de
error que ofrece la única opción prohibida es peor que no dar opciones.

### Manejo de errores

- Sin `CAMPO_PRECIO` en el `.env` → `PRECIOTOTALEXT` → **nada cambia para las
  instalaciones actuales**.
- Formato inválido → `ValueError` al arrancar.
- `IPRECIOTOTAL` → `ValueError` al arrancar, explicando el IVA doble.
- Columna inexistente → `ValueError` al arrancar, listando las disponibles.

### Lo que la validación NO hace

Si se configura `PRECIOSINIMPUESTO`, los precios pasan de ~52 a ~7473 por
producto. Es un cambio de escala enorme, pero es exactamente lo que la feature
permite, y el sistema no puede distinguirlo de un cambio legítimo de política de
precios. **La validación protege de escribir mal la columna elegida, no de elegir
la columna equivocada.**

## Pruebas

`tests/test_campo_precio.py`, puro, con monkeypatch de `config` siguiendo el
patrón de `tests/test_factory_pdf.py`:

1. Sin `CAMPO_PRECIO` → default `PRECIOTOTALEXT`.
2. Minúsculas y espacios alrededor → se normaliza (`" preciototalext "` →
   `PRECIOTOTALEXT`), no es error.
3. Formato inválido: espacio interno → `ValueError`.
4. Formato inválido: comilla simple (intento de inyección) → `ValueError`.
5. `IPRECIOTOTAL` → `ValueError` cuyo mensaje menciona el IVA.
6. `ipreciototal` en minúsculas → también rechazado (se normaliza antes de
   comparar, así que el rechazo no se esquiva escribiéndolo distinto).
7. Columna inexistente → `ValueError` cuyo mensaje lista las variantes derivadas
   (`PRECIOSINIMPUESTO, PRECIOTOTALEXT`) y no las columnas crudas.
8. Las variantes sugeridas no incluyen `IPRECIOTOTAL`, que está rechazado.
9. Columna válida presente en las tres tiers → pasa.
10. Columna válida en `P01` pero ausente en `P03` → `ValueError`.

Verificación manual contra DBISAM real: arrancar el servidor con
`CAMPO_PRECIO=PRECIOTOTALEX` (typo) y comprobar que no levanta; arrancar con
`CAMPO_PRECIO=PRECIOSINIMPUESTO` y comprobar que un pedido cotiza con la otra
escala.

## Fuera de alcance

- **Precio libre en el Flow.** Es la otra mitad de lo pedido y tiene su propio
  spec: toca el JSON del Flow, `add_product` y `ProductoHandler`, y exige unificar
  la matemática de precios duplicada entre `handlers/Validar_Pedido.py:60-73` y
  `main.py:413-426`.
- **Tiers `P04`..`P06`.** Existen en el esquema pero el parser solo acepta `P1|P2`
  y `consultar_precios` mapea `P1/P2/P3`. Habilitarlos es una feature aparte.
- **Unificar la matemática duplicada de precios.** Pertenece al spec de precio
  libre, que es el que la necesita.
