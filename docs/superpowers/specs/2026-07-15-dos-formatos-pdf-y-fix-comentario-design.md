# Dos formatos de impresión de pedidos + fix de comentario

**Fecha:** 2026-07-15
**Estado:** Aprobado (diseño)

## Contexto

El bot de pedidos por WhatsApp lo usarán dos clientes distintos (dos empresas).
Cada uno necesita su propio formato de impresión del pedido. El formato a usar se
selecciona por variable de entorno. Además, hay un bug: el comentario del pedido no
está llegando ni al PDF ni al sistema legado a2 (DBISAM).

Son dos piezas relacionadas (ambas tocan el render del pedido) pero independientes:

1. **Feature:** dos formatos de impresión seleccionables por variable de entorno.
2. **Bug:** el comentario no llega al PDF ni a a2.

## Objetivos

- Poder elegir el formato de impresión con una variable de entorno.
- Replicar fielmente el formato ECOGRASAS a partir del PDF de referencia
  (`C:\Users\arang\Documents\ECOGRASAS PEDIDOS.pdf`).
- Mantener el formato actual (Marluis) sin cambios de layout.
- Que el comentario del pedido llegue tanto al PDF como a a2 (`FTI_DETALLECOMENTARIO`).

## No-objetivos (YAGNI)

- No migrar a plantillas HTML / WeasyPrint. Se mantiene ReportLab.
- No parametrizar un único generador con "config de layout" abstracta.
- No agregar campos nuevos a la base de datos para Teléfono / Dirección de Despacho.
- No implementar el cálculo de "Fecha Límite de Entrega" (queda en blanco).

## Arquitectura (Opción 1: registro de generadores)

Cada formato es su propio módulo con la misma firma que ya usa el código:

```python
def generar(filename, pedido: dict, logo_path=None, preliminar: bool = False) -> bytes | None
```

### Estructura de archivos

```
pdf/
  factory.py             # get_generador_pdf() -> callable, lee FORMATO_PDF
  formato_marluis.py     # extraído de weasy.py (idéntico, sin cambios de layout)
  formato_ecograsas.py   # nuevo, replica el PDF de ECOGRASAS
  weasy.py               # shim: reexporta generar_factura para no romper imports viejos
```

### Factory

`pdf/factory.py` expone `get_generador_pdf()` que:

- Lee `FORMATO_PDF` del `.env` (`marluis` | `ecograsas`, default `marluis`).
- Devuelve la función `generar` del módulo correspondiente.
- Ante un valor desconocido, usa `marluis` (default seguro) o lanza error claro
  (a decidir en implementación; preferible fallar con mensaje explícito).

### Llamadores

Los dos puntos que hoy llaman `generar_factura` directo pasan a pedir el generador
a la factory:

- `main.py:185` (preliminar en memoria, `preliminar=True`).
- `strategy/response_strategy.py:61` (PDF final a disco).

De:

```python
generar_factura(filename=..., pedido=..., logo_path='pdf/marluis.png', ...)
```

a:

```python
get_generador_pdf()(filename=..., pedido=..., preliminar=...)
```

El `logo_path` deja de pasarse desde afuera: **cada formato conoce su propio logo**
e identidad de empresa (un formato = una empresa).

## Formato ECOGRASAS (`formato_ecograsas.py`)

Identidad hardcodeada en el módulo: **PROCESADORA ECOGRASAS, C.A.** / dirección
Tinaquillo (Calle 4, Parcela No. C, Zona Industrial Municipal Etapa I, Tinaquillo Edo.
Cojedes — Teléfonos (0258) 766.3191 / 766.5627) / RIF J-29801313-3 /
emails ventas@ecograsas.com, info@ecograsas.com.

### Encabezado

- Izquierda: logo + datos de empresa.
- Derecha: `PEDIDO`, `# {id rjust 8}`, `Fecha de Emisión`, `Fecha Límite Entrega:` (en blanco).

### Bloque cliente

| Campo ECOGRASAS       | Origen en `pedido`        |
|-----------------------|---------------------------|
| Cliente               | `descripcion_cliente`     |
| Dirección Fiscal      | `direccion_cliente`       |
| Dirección Despacho    | (en blanco — no lo tenemos)|
| RIF                   | `cliente` (el código ES el RIF) |
| Teléfono              | (en blanco — no lo tenemos)|
| Vendedor              | `nombre_vendedor`         |
| Observaciones         | `comentario`              |

Campos **eliminados** respecto al PDF original (por pedido del usuario):
Documento Origen, Condición de Pago, Condición de Venta.

### Tabla de ítems

Columnas: `Cód · Descripción · Cant · Precio Unit · Total`

| Columna     | Origen                    |
|-------------|---------------------------|
| Cód         | `codigo`                  |
| Descripción | `descripcion`             |
| Cant        | `cantidad`                |
| Precio Unit | `precio_sin_iva`          |
| Total       | `total_sin_dcto`          |

Columnas **eliminadas** respecto al PDF original: No. Lote, F.Vcmto Lote.

### Pie (3 columnas)

- **Izquierda:** SUB Total (`total_bruto`), Total Descuentos (suma real de descuentos),
  Total Bruto (`total_bruto`). Eliminados: Convenio Transporte, Convenio Prepago.
- **Centro:** Total Exento (`exento`), Base Imponible 16% (`base_16`) + IVA 16% (`iva_16`),
  Base Imponible 8% (`base_8`) + IVA 8% (`iva_8`).
- **Derecha:** **Total Pedido** (`total_neto`), destacado.

Validación de mapeo contra el PDF de muestra (todos cuadran con campos existentes):
`base_8` = 1.824,00 · `iva_8` = 145,92 · `exento` = 1.984,00 · `total_neto` = 3.953,92
(= 3.808,00 + 145,92). ✓

### Observaciones y firma

- **Observaciones:** `comentario`.
- **Elaborado por:** `nombre_vendedor` (por defecto). Alternativa: texto estático "MASTER".

## Fix del comentario (`parser/parsear_pedido.py`)

El comentario ya está cableado de punta a punta en la ruta de texto (parser → Redis →
PostgreSQL/a2 → PDF). El problema está en la **captura**. Cambios:

- Comparar `linea.strip() in ("P1", "P2")` en vez de `linea` — hoy `"P1\r"` o `"P1 "`
  caen como comentario y descuadran el pedido.
- Acumular el comentario en una lista y unir con `\n` — hoy `comentario += linea`
  pega las líneas sin separador.
- Blindar `PRODUCTOS_SOLO`: que una línea de comentario de una sola palabra con dígitos
  no invalide todo el pedido (p. ej. solo tratar como producto inválido cuando la línea
  realmente parezca un código, o cuando no se hayan capturado productos válidos).
- Verificación explícita de que `comentario` llega a los dos destinos:
  a2 (`FTI_DETALLECOMENTARIO`, `database/dbisam.py:266,306`) y PDF.
- Reproducir con un **mensaje real** que haya fallado antes de dar por cerrado el fix.

## Configuración

`.env`:

```
FORMATO_PDF=marluis    # marluis | ecograsas
```

Documentar la nueva variable en `CLAUDE.md`.

## Verificación

No hay suite formal en el proyecto. Plan:

- **PDFs:** script que llama a cada generador con un `pedido` de muestra (ya existe uno
  al final de `weasy.py`) y produce ambos PDFs a disco para comparar visualmente contra
  `ECOGRASAS PEDIDOS.pdf`.
- **Comentario:** prueba del parser con mensajes que incluyen comentarios de una y varias
  líneas y con `P1\r`, verificando que `comentario` no se pierde ni se pega sin separador.

## Decisiones abiertas / notas

- **Logo de Ecograsas:** pendiente el archivo de imagen. Hasta tenerlo se usa un
  placeholder de texto.
- **"Total Descuentos"** en el PDF de muestra mostraba un valor raro (igual al Total
  Pedido); se asume bug de su sistema y se pondrá la **suma real** de descuentos.
- **"03-PT PE"** (código de tier): omitido.
- **"Elaborado por"** = `nombre_vendedor` por defecto (fácil de cambiar a estático).
