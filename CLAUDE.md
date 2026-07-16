# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Propósito del Proyecto

Sistema de gestión de pedidos para **Distribuidora Marluis** vía WhatsApp Business API. Los vendedores envían pedidos en texto plano; el sistema los parsea, valida, genera un PDF preliminar, y tras confirmación del usuario, los inserta en dos bases de datos (DBISAM legado + PostgreSQL).

## Comandos de Desarrollo

```bash
# Instalar dependencias
pip install -r requirements.txt

# Ejecutar servidor FastAPI (modo desarrollo)
uvicorn main:fastapi_app --reload --host 0.0.0.0 --port 8000

# Activar entorno virtual (PowerShell)
.\venv\Scripts\Activate.ps1
```

No existe suite de pruebas automatizadas. Las pruebas son manuales vía WhatsApp; `test.py` envía un mensaje de prueba básico.

## Arquitectura

### Flujo principal: Procesamiento de pedido

```
Mensaje WhatsApp (texto)
  → filtros/UserFiltro.py       # Verifica que el remitente es vendedor autorizado
  → parser/parsear_pedido.py    # Regex: extrae cliente, productos, cantidades, descuento, tier de precio
  → handlers/Validar_Pedido.py  # Cadena: ClienteHandler → ProductoHandler (consulta DBISAM)
  → database/redis.py           # Guarda pedido en caché (TTL 1 hora)
  → pdf/weasy.py                # Genera PDF preliminar en buffer BytesIO
  → Respuesta al usuario        # Resumen + botón Flow de confirmación
```

### Flujo de confirmación

```
Usuario responde al Flow de WhatsApp
  → strategy/response_strategy.py
    ├─ ConfirmarStrategy  → PostgreSQL (pedidos + pedido_detalle) + DBISAM (SOPERACIONINV + SDETALLEVENTA) + PDF final a disco
    ├─ CancelarStrategy   → Mensaje de cancelación
    └─ PreliminarStrategy → Reenvía PDF preliminar
```

### Flujo de registro de cliente

```
Mensaje "\crear_cliente"
  → handler crear_cliente()      # Envía Flow de WhatsApp (formulario)
  → handler registro_cliente()   # Inserta en DBISAM tabla SCLIENTES
```

### Patrones de diseño utilizados

- **Cadena de responsabilidad** — `handlers/Validar_Pedido.py`: `ClienteHandler → ProductoHandler`
- **Estrategia** — `strategy/response_strategy.py`: `ConfirmarStrategy / CancelarStrategy / PreliminarStrategy`
- **Fábrica** — `ParserFactory` en `parser/parsear_pedido.py` (extensible para otros formatos)
- **Filtros** — `filtros/UserFiltro.py` (autorización) y `filtros/FlowFiltros.py` (completitud de flows)

## Stack Tecnológico

| Componente | Tecnología |
|---|---|
| Framework web | FastAPI (async) |
| WhatsApp API | pywa 2.11.0 |
| Base de datos legada | DBISAM vía ODBC (`pydbisam`, `pyodbc`) |
| Base de datos moderna | PostgreSQL + SQLModel ORM |
| Caché | Redis (localhost:2576) |
| Generación de PDF | ReportLab |
| Configuración | python-decouple (`.env`) |
| LLM opcional | Ollama + LangChain + Chroma (desactivado) |

## Variables de Entorno (`.env`)

```
DSN=A2GKC                                        # DSN ODBC para DBISAM
CatalogName=C:\a2Softway12.36.ID\Empre001\Data   # Ruta al catálogo DBISAM
FORMATO_PDF=marluis                              # Formato de impresión: marluis | ecograsas
Postgres=postgresql://user:pass@localhost:5432/appksa
PHONE_ID=<WhatsApp Business Phone ID>
TOKEN=<WhatsApp Business API token>
VERIFY_TOKEN=<Webhook verification token>
FLOW_PRIVATE_KEY_PATH=flow_private_key.pem       # Clave RSA privada para cifrado de Flows
FLOW_ID_CONFIRMACION=1114349466876600            # Flow de confirmación de pedido
FLOW_ID_REGISTRO_CLIENTE=1418891859657565        # Flow de registro de cliente
FLOW_ID_PEDIDO=<ID del Flow de toma de pedido>   # Obtener desde Meta Flow Builder
```

Los archivos `flow_private_key.pem` y `flow_public_key.pem` están en la raíz del proyecto y **no se commitean** (están en `.gitignore`). La clave pública debe subirse a Meta una sola vez:

```bash
# Subir clave pública RSA a Meta (Graph API v21)
curl -X POST "https://graph.facebook.com/v21.0/<PHONE_ID>/whatsapp_business_encryption" \
  -H "Authorization: Bearer <TOKEN>" \
  -F "business_public_key=@flow_public_key.pem"
```

## Notas Críticas

- **Redis** está hardcodeado a `localhost:2576` en `database/redis.py`. Debe estar corriendo antes de iniciar.
- **DBISAM** es un sistema legado con rutas Windows específicas; las consultas SQL están en `database/dbisam.py` y son sensibles al esquema de tablas `SVENDEDORES`, `SCLIENTES`, `SINVENTARIO`, `A2INVCOSTOSPRECIOS`, `SOPERACIONINV`, `SDETALLEVENTA`.
- **Flow IDs de WhatsApp** configurables en `.env` (antes estaban hardcodeados en `main.py`). Deben existir en la cuenta de WhatsApp Business.
- **PDF preliminares** se generan en memoria (`BytesIO`); los PDF finales se guardan en disco en `static/media/`.
- **Formato de mensaje** que parsea el sistema:
  ```
  <Código Cliente>
  <Código Producto> <Cantidad> [<Descuento%>]
  ... (más líneas de producto)
  <P1|P2>           ← tier de precio (obligatorio)
  [Comentarios opcionales]
  ```

## Problemas Conocidos y Parches

### pywa 2.11.0 + Pydantic 2.x + Python < 3.12

**Síntoma:** el servidor no arranca y lanza `PydanticUserError: Please use typing_extensions.TypedDict instead of typing.TypedDict on Python < 3.12` al registrar el endpoint `@wa.on_flow_request`.

**Causa:** pywa 2.11.0 define `EncryptedFlowRequestType(TypedDict)` importando `TypedDict` de `typing` en lugar de `typing_extensions`. Pydantic 2 lo rechaza al inspeccionar los parámetros del endpoint FastAPI.

**Parche:** editar `venv/Lib/site-packages/pywa/handlers.py` línea 58:

```python
# Antes (una línea):
from typing import TYPE_CHECKING, Any, Callable, cast, TypeAlias, Awaitable, TypedDict

# Después (dos líneas):
from typing import TYPE_CHECKING, Any, Callable, cast, TypeAlias, Awaitable
from typing_extensions import TypedDict
```

> Este parche se aplica al venv y se pierde si se reinstala pywa (`pip install --force-reinstall pywa`). En ese caso hay que reaplicarlo manualmente.


### Referencias pyodbc
- Documentación oficial: https://github.com/mkleehammer/pyodbc/wiki
- Guía de errores: https://github.com/mkleehammer/pyodbc/wiki/Exceptions
- Soporte de dbisam : https://www.elevatesoft.com/manual?action=topics&id=dbisam4&product=rsdelphi&version=XE&section=sql_reference
# Tablas de operaciones de base de datos
SOPERACIONINV = Aqui se encuentran las operaciones de Compras, Ventas, Pedidos, Devolucion de compras, devolucion de ventas, clasificadas por tipos
SDETALLECOMPRA = Esta tabla esta relacionada con SOPERACIONINV mediante FTI_AUTOINCREMENT = FDI_OPERACION_AUTOINCREMENT aqui se encuentran los productos relacionados a la compra y devolucion de compra
SDETALLEVENTA = Esta tabla esta relacionada con SOPERACIONINV mediante FTI_AUTOINCREMENT = FDI_OPERACION_AUTOINCREMENT aqui se encuentran los productos relacionados a la venta y devolucion de venta
SINVDEP = Esta tabla se encuentran los codigos de los productos por deposito con sus existencias actuales, se relaciona con las tablas SDETALLECOMPRA y SDETALLEVENTA mediante el codigo del producto.

# Referencia de tipos de operaciones en las tablas
1 : Traslados
2 : Cargos
3 : Descargos
4 : Ajustes
5 : Órdenes de Compras
6 : Compras
7 : Devolución de Compras
8 : Notas de Entrega en Compras
9 : Presupuestos
10 : Pedidos
11 : Facturas
12 : Devolución de Ventas
13 : Notas de Entrega en Ventas
14 : Apartados
23 : Órdenes de Servicios
