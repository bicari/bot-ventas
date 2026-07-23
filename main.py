import fastapi
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from typing import Dict
from collections import defaultdict
from pywa import WhatsApp, types, filters
from contextlib import asynccontextmanager
from pywa.types.template import Language
from pywa.types import CallbackData, FlowButton, Button, Template, FlowCompletion, FlowRequest, FlowResponse, FlowRequestActionType
from pywa.types.flows import FlowActionType
from strategy.response_strategy import CancelarStrategy, ConfirmarStrategy, PreliminarStrategy
from parser.parsear_pedido import ParserFactory
from handlers.Validar_Pedido import ClienteHandler, ProductoHandler#, PrecioHandler, ComentarioHandler
from dataclasses import dataclass
from database.dbisam import DBISAMDatabase
from filtros.UserFiltro import user_with_auth
from filtros.FlowFiltros import registrar_cliente, confirmar_pedido, nuevo_pedido_flow
from database.redis import PedidoCache
from flows.routing import inferir_accion_flow
from flows.carrito import data_producto, construir_pedido
from flows.precio_libre import resolver_precio_manual
from handlers.calculo_item import calcular_item
from database.postgres import create_tables_and_db
from database.campo_precio import get_campo_precio, validar_campo_precio
from sqlmodel import create_engine, Session
from pdf.factory import get_generador_pdf
from decouple import config
import uuid
import logging
logging.basicConfig(level=logging.DEBUG)
logging.getLogger('pywa').setLevel(logging.DEBUG)
#from llms.chat import OllamaChat


cache_pedidos: Dict[str, list] = defaultdict(list)
redis_cache = PedidoCache()
engine = create_engine(config('Postgres'),
                       echo=True,
                       pool_size=10,
                       max_overflow=20,
                       pool_timeout=30,
                       pool_recycle=1800)
def get_session():
    return Session(engine)

@asynccontextmanager
async def lifespan(app: fastapi.FastAPI):
    create_tables_and_db()
    # Un CAMPO_PRECIO mal escrito debe impedir arrancar, no reventar a mitad
    # de un pedido con un error de sintaxis de DBISAM.
    validar_campo_precio(get_campo_precio(), DBISAMDatabase().columnas_precio())
    yield

fastapi_app = fastapi.FastAPI()
wa = WhatsApp(
    phone_id=config('PHONE_ID'),
    token=config('TOKEN'),
    server=fastapi_app,
    verify_token=config('VERIFY_TOKEN'),
    business_private_key=open(config('FLOW_PRIVATE_KEY_PATH', default='flow_private_key.pem')).read(),
)
fastapi_app.mount("/static", StaticFiles(directory="static"), name="static")
# flows = wa.get_flows(waba_id='1152956486695534',phone_number_id='788035891058430')
# for flow in flows:
#     print(flow)

# ── Flow IDs de WhatsApp (definibles en .env para no hardcodear) ──────────────
# IMPORTANTE: cada flow_id DEBE pertenecer a la misma WABA del PHONE_ID emisor
# (actualmente "Ecograsas", 4537673366559764); enviar un flow de otra WABA da el
# error 131009 "flow_id is invalid". Los defaults apuntan a los flows de Ecograsas.
FLOW_ID_CONFIRMACION     = config('FLOW_ID_CONFIRMACION',     default='27306927625623441')
FLOW_ID_REGISTRO_CLIENTE = config('FLOW_ID_REGISTRO_CLIENTE', default='2190203981555327')
# FLOW_ID_PEDIDO: crear el Flow en Meta (Flow Builder) y definir en .env
# Prerrequisitos: par de claves RSA (clave pública en Meta, privada en .env FLOW_PRIVATE_KEY)
#                + endpoint HTTPS público que apunte a /flow/pedido
FLOW_ID_PEDIDO           = config('FLOW_ID_PEDIDO',           default='')

@dataclass(frozen=True, slots= True)
class UserResponsePedido(CallbackData):
    msg_id : str
    #response: str
    pedido: str
    user: str

@fastapi_app.get("/marluis/pdf/{pedido_document}")
def enviar_pdf(pedido_document:str):
    if os.path.exists(pedido_document):
        return FileResponse(
            path=pedido_document,
            media_type='application/pdf',
            filename=pedido_document
        )

# @wa.on_message()
# def respuesta_generica(client:WhatsApp, msg: types.Message):
#     llm = OllamaChat()
#     llm_response = llm.chat_response(msg.text)
#     client.send_message(
#              to=msg.from_user,
#              text=f"{llm_response}",
#              header='Asistente de Pedidos',
#              footer='Dist Marluis',
#              reply_to_message_id=msg.id
#          )
        
@wa.on_flow_completion(filters.new(registrar_cliente) & filters.new(user_with_auth))
def registro_cliente(client: WhatsApp, flow: FlowCompletion):
    db = DBISAMDatabase()
    result = db.insert_cliente(flow.response, flow.from_user.wa_id)
    if isinstance(result, int):
        client.send_message(
            to=flow.from_user.wa_id,
            text=f"✅ ¡El cliente {flow.response['registrar']['name'].upper()} ha sido registrado satisfactoriamente! Ya puede proceder con la realización de su pedido."
            )
    else:
        client.send_message(
            header="🔴 Error 🔴",
            to=flow.from_user.wa_id,
            text="Ha ocurrido un error al momento de la creacion del cliente, por favor contacte al administrador de la app o intente de nuevo",
            footer="Distribuidora Marluis"
        )
    

@wa.on_flow_completion(filters.new(confirmar_pedido))
def confirmar_pedido(_: WhatsApp, flow: FlowCompletion):
    respuestas = {
        'Confirmado': ConfirmarStrategy(),
        'Cancelado': CancelarStrategy(),
        'Preliminar': PreliminarStrategy()
    }
    respuestas_user = flow.response.get('confirmacion')
    handle_response = respuestas.get(respuestas_user)
    #pedido = list(filter(lambda d: flow.reply_to_message.message_id in d, redis_cache.obtener_pedido_user(flow.from_user.wa_id)))
    pedido = redis_cache.buscar_pedido_por_msg_id(flow.from_user.wa_id, str(flow.reply_to_message.message_id))
    
    if respuestas_user == 'Confirmado':
        handle_response.execute(_, 
                                flow.from_user.wa_id,  
                                pedido,#pedido[0][flow.reply_to_message.message_id], 
                                get_session())
        return    
    handle_response.execute(_, 
                            flow.from_user.wa_id, 
                            pedido#pedido[0][flow.reply_to_message.message_id]
                            )
#@wa.on_message
#def message(_: WhatsApp, msg: types.Message):
#    print(msg)

@wa.on_message(
    filters.new(user_with_auth)
    & ~filters.startswith(r"\nuevo_pedido", ignore_case=True)
    & ~filters.startswith(r"\crear_cliente", ignore_case=True)
)
def handle_message(client: WhatsApp, msg: types.Message):
     user_id = msg.from_user.wa_id
     text_msg= msg.text.splitlines()
     print(text_msg)
     pedido = ParserFactory.get_parser('texto').parse(text_msg)

     if isinstance(pedido, ValueError):
         client.send_message(
             to=msg.from_user,
             text=str(pedido),
             header='Error en el pedido',
             footer='Dist Marluis',
             buttons=[
                 Button(title='Pedido ejemplo', callback_data='pedido_ejemplo')
             ],
             reply_to_message_id=msg.id
         )
        
         return
     handler_chain = ClienteHandler(
         ProductoHandler()
     )
     try:
         handler_chain.handle(pedido, user_id)
     except ValueError as e:
         client.send_message(
             to=msg.from_user,
             text=str(e),
             header='Error en el pedido',
             footer='Dist Marluis',
             reply_to_message_id=msg.id
         )
         return
        
     pedido['id'] = 'PRELIMINAR'
     pdf_buffer = get_generador_pdf()(filename='static/media/pedido_preliminar.pdf', pedido=pedido, preliminar=True)
     
     items = (list(map(
                 lambda x: """📦Código: {code}\nCantidad: {qty}\nPrecio: ${price}\n{precio_con_descuento}Subtotal: ${sub}\n""".format(code=x, qty=pedido['productos'][x]['cantidad'], price=pedido['productos'][x]['precio'], sub=pedido['productos'][x]['subtotal'], precio_con_descuento=f"`Precio Descuento:${pedido['productos'][x]['precio_venta'] }`\n" if pedido['productos'][x]['descuento'] > 0 else '' ), pedido['productos'].keys())))
     # ── Desglose de impuestos por base (omite líneas en cero) ────────────────
     lineas_resumen = [f"Hola {msg.from_user.name}, Por favor confirma tu pedido!!"]
     if pedido.get('base_16', 0) > 0:
         lineas_resumen.append(f"```💰Base 16%```: ${round(pedido['base_16'], 2)}")
         lineas_resumen.append(f"```💰IVA 16%```: ${round(pedido['iva_16'], 2)}")
     if pedido.get('base_8', 0) > 0:
         lineas_resumen.append(f"```💰Base 8%```: ${round(pedido['base_8'], 2)}")
         lineas_resumen.append(f"```💰IVA 8%```: ${round(pedido['iva_8'], 2)}")
     if pedido.get('exento', 0) > 0:
         lineas_resumen.append(f"```💰Exento```: ${round(pedido['exento'], 2)}")
     lineas_resumen.append(f"```💰Total Neto```: ${round(pedido['total_neto'], 2)}")
     lineas_resumen.append("_En caso de no confirmar el pedido se eliminará luego de 1 hora⏳_")
     resumen_impuestos = "\n".join(lineas_resumen)

     response_user = client.send_message(
          header='Preliminar de Pedido',
          to=msg.from_user,
          text=resumen_impuestos,
          footer='Dist Marluis',
          buttons=FlowButton(
               title='Confirmar Pedido',
               flow_id=FLOW_ID_CONFIRMACION,
            )
         )
     client.send_document(
          to=msg.from_user,
          document=pdf_buffer,
          filename=f'Preliminar{uuid.uuid4().hex[:10]}.pdf',
          caption='Descargue el preliminar de su pedido aquí',
          mime_type='application/pdf'
     )   
     redis_cache.agregar_pedido(user_id, pedido, response_user.id)
     #add_pedido(user_id, pedido, response_user.id)


@wa.on_message(filters.startswith("\crear_cliente", ignore_case=True) & filters.new(user_with_auth))
def crear_cliente(client: WhatsApp, msg: types.Message):
    client.send_message(
        to=msg.from_user,
        text='Complete el formulario para crear cliente en el sistema\n\nPosterior a la creación estará disponible para realizar un pedido\n\n\n_*Debe poseer permisos para realizar esta acción*_',
        header='Creación de Clientes',
        footer='Dist Marluis',
        reply_to_message_id=msg.id,
        buttons=FlowButton(
            title='Crear Cliente',
            flow_id=FLOW_ID_REGISTRO_CLIENTE,
        )
    )
@wa.on_callback_button(filters.new(user_with_auth))
def handle_callback_button(client: WhatsApp, btn: types.CallbackButton):
    if btn.data == 'pedido_ejemplo':
        client.send_template(
            to=btn.from_user,
            template=Template(
                name='address_update',
                language=Language.ENGLISH_US
            )
        )


# ══════════════════════════════════════════════════════════════════════════════
# FASE B — Flow de toma de pedido guiada (formulario completo)
#
# PREREQUISITOS (deben estar listos antes de habilitar):
#   1. Par de claves RSA generado. Subir la pública a Meta con la API de WhatsApp.
#      Agregar al .env:  FLOW_PRIVATE_KEY=<clave privada PEM>
#      Pasar al cliente WhatsApp:  business_private_key=config('FLOW_PRIVATE_KEY')
#   2. Endpoint público HTTPS alcanzable por Meta (ngrok/deploy).
#   3. Flow JSON creado en el Flow Builder de Meta (pantallas CLIENTE → PRODUCTO → RESUMEN)
#      con endpoint URI apuntando a /flow/pedido. Obtener el flow_id y definir:
#      FLOW_ID_PEDIDO=<id> en .env
#   4. La clave de respuesta del Flow debe incluir 'nuevo_pedido' (ver FlowFiltros).
# ══════════════════════════════════════════════════════════════════════════════

@wa.on_message(filters.startswith(r"\nuevo_pedido", ignore_case=True) & filters.new(user_with_auth))
def nuevo_pedido(client: WhatsApp, msg: types.Message):
    """Dispara el Flow de toma de pedido guiada."""
    if not FLOW_ID_PEDIDO:
        client.send_message(
            to=msg.from_user,
            header="Flow no configurado",
            text="El formulario de pedido aún no está disponible.\n\n"
                 "Mientras tanto, puedes enviar tu pedido en formato texto:\n"
                 "```<Código cliente>\n<CÓDIGO> <Cantidad> [Descuento%]\n...\n<P1|P2>```",
            footer="Dist Marluis",
            reply_to_message_id=msg.id,
        )
        return
    flow_token = uuid.uuid4().hex
    redis_cache.guardar_carrito(flow_token, {
        "productos": {},
        "tipo_precio": "P1",
        "cliente": "",
        "comentario": "",
        "vendedor_wa_id": msg.from_user.wa_id,
    })
    print(f"[NUEVO_PEDIDO] flow_token={flow_token} wa_id={msg.from_user.wa_id}")
    client.send_message(
        to=msg.from_user,
        header="Nuevo Pedido",
        text="Completa el formulario para armar tu pedido.\nPodrás agregar varios productos antes de confirmar.",
        footer="Dist Marluis",
        reply_to_message_id=msg.id,
        buttons=FlowButton(
            title="Armar Pedido",
            flow_id=FLOW_ID_PEDIDO,
            flow_token=flow_token,
            flow_action_type=FlowActionType.DATA_EXCHANGE,
        ),
    )


# ── Helpers del Flow ─────────────────────────────────────────────────────────

def _calcular_totales_y_resumen(carrito: dict) -> tuple[str, dict]:
    """Calcula los totales por base y devuelve (texto de resumen, carrito actualizado)."""
    prods = carrito.get("productos", {})

    def base_t(tasa: int) -> float:
        return round(sum(p["precio_con_descuento"] * p["cantidad"]
                         for p in prods.values() if p.get("impuesto") == tasa), 2)

    base_16 = base_t(16)
    base_8  = base_t(8)
    exento  = base_t(0)
    iva_16  = round(base_16 * 0.16, 2)
    iva_8   = round(base_8 * 0.08, 2)
    total_bruto = round(sum(p["precio_con_descuento"] * p["cantidad"] for p in prods.values()), 2)
    iva_total   = round(iva_16 + iva_8, 2)
    total_neto  = round(total_bruto + iva_total, 2)

    carrito.update({
        "base_16": base_16, "base_8": base_8, "exento": exento,
        "iva_16": iva_16,   "iva_8": iva_8,   "iva_total": iva_total,
        "baseimponible": round(base_16 + base_8, 2),
        "total_bruto": total_bruto, "total_neto": total_neto,
        "peso_total": round(sum(p.get("peso_item", 0) for p in prods.values()), 2),
    })

    lineas = []
    if base_16 > 0:
        lineas += [f"Base 16%: ${base_16:.2f}", f"IVA 16%:  ${iva_16:.2f}"]
    if base_8 > 0:
        lineas += [f"Base 8%:  ${base_8:.2f}", f"IVA 8%:   ${iva_8:.2f}"]
    if exento > 0:
        lineas.append(f"Exento:   ${exento:.2f}")
    lineas.append(f"─────────────────────")
    lineas.append(f"Total Neto: ${total_neto:.2f}")
    return "\n".join(lineas), carrito


# ── Endpoint de datos del Flow (data_exchange) ───────────────────────────────
# pywa lo llama en cada interacción del usuario con el Flow (INIT y DATA_EXCHANGE).
# ACTIVAR: (1) añadir business_private_key al cliente WhatsApp en este archivo,
#          (2) definir FLOW_ID_PEDIDO en .env con el id obtenido de Meta.
@wa.on_flow_request("/flow/pedido")
def flow_pedido_endpoint(_: WhatsApp, req: FlowRequest) -> FlowResponse:
    db = DBISAMDatabase()
    print(f"[FLOW] action={req.action} flow_token={req.flow_token} raw_keys={list(req.raw.keys())}")

    def _clientes_de_carrito(token: str) -> list:
        """Obtiene la lista de clientes del vendedor usando el carrito de Redis."""
        carrito_tmp = redis_cache.obtener_carrito(token) or {}
        wa_id = carrito_tmp.get("vendedor_wa_id", "")
        print(f"[FLOW] vendedor_wa_id={wa_id!r} carrito_keys={list(carrito_tmp.keys())}")
        if not wa_id:
            return []
        row = db.consultar_vendedor(wa_id)
        print(f"[FLOW] consultar_vendedor -> {row}")
        if not row:
            return []
        return db.listar_clientes_de_vendedor(row[0])

    # ── INIT: cargar lista de clientes del vendedor para el Dropdown ──────────
    if req.action == FlowRequestActionType.INIT:
        clientes = _clientes_de_carrito(req.flow_token)
        print(f"[FLOW] INIT -> {len(clientes)} clientes")
        return req.respond(screen="CLIENTE", data={"clientes": clientes})

    # req.data es None cuando raw['data'] == {} (pywa convierte dict vacío a None).
    # Usamos raw directamente para obtener el payload real y la pantalla activa.
    data           = req.raw.get("data") or {}
    current_screen = req.raw.get("screen") or "CLIENTE"
    # WhatsApp descarta el literal 'action' del payload (colisiona con el campo
    # 'action' de nivel superior), así que lo deducimos desde la pantalla activa.
    action         = inferir_accion_flow(data.get("action"), current_screen, data)
    carrito        = redis_cache.obtener_carrito(req.flow_token) or {"productos": {}, "tipo_precio": "P1", "cliente": ""}

    # Sin acción (DATA_EXCHANGE vacío de carga inicial o BACK): refrescar pantalla actual.
    if not action:
        if current_screen == "PRODUCTO":
            return req.respond(screen="PRODUCTO", data=data_producto(carrito))
        clientes = _clientes_de_carrito(req.flow_token)
        print(f"[FLOW] DATA_EXCHANGE sin acción -> {len(clientes)} clientes")
        return req.respond(screen="CLIENTE", data={"clientes": clientes})

    # ── select_client: guardar cliente+precio, navegar a PRODUCTO ────────────
    if action == "select_client":
        carrito["cliente"]     = data.get("cliente_id", "")
        carrito["tipo_precio"] = data.get("tipo_precio", "P1")
        carrito["sistema"]     = data.get("sistema", "")
        print(f"[FLOW] select_client cliente={carrito['cliente']} precio={carrito['tipo_precio']} sistema={carrito['sistema']}")
        redis_cache.guardar_carrito(req.flow_token, carrito)
        return req.respond(screen="PRODUCTO", data=data_producto(carrito))

    # ── add_product: validar producto en DBISAM y agregar al carrito ──────────
    if action == "add_product":
        codigo        = (data.get("codigo") or "").strip().upper()
        cantidad_raw  = str(data.get("cantidad") or "0").replace(",", ".")
        descuento_raw = str(data.get("descuento") or "0").replace(",", ".")

        try:
            cantidad  = float(cantidad_raw)
            descuento = float(descuento_raw)
            if cantidad <= 0:
                raise ValueError("La cantidad debe ser mayor que cero.")
        except ValueError as exc:
            return req.respond(screen="PRODUCTO", data=data_producto(carrito, error=str(exc)))

        try:
            prods_query, not_found = db.consultar_precios([codigo], carrito.get("tipo_precio", "P1"))
            if not_found:
                raise ValueError(f"Producto '{codigo}' no encontrado o inactivo.")
            row = prods_query[codigo]
            fi_codigo, impuesto, precio, descripcion, peso, _ = row
            base_manual = resolver_precio_manual(
                data.get("precio"), data.get("precio_incluye_iva"),
                descuento, impuesto)
            if base_manual is not None:
                descuento = 0
            item = {
                "cantidad": cantidad, "descuento": descuento,
                "descripcion": descripcion, "impuesto": impuesto,
            }
            if base_manual is not None:
                item["precio_manual"] = True
            item.update(calcular_item(
                base_manual if base_manual is not None else precio,
                cantidad, descuento, impuesto, peso))
            carrito["productos"][fi_codigo] = item
            redis_cache.guardar_carrito(req.flow_token, carrito)
        except Exception as exc:
            return req.respond(screen="PRODUCTO", data=data_producto(carrito, error=str(exc)))

        return req.respond(
            screen="PRODUCTO",
            data=data_producto(carrito, agregado=f"{fi_codigo} × {cantidad}"),
        )

    # ── remove_product: quitar item del carrito ───────────────────────────────
    if action == "remove_product":
        # Sin .upper(): el valor viene del Dropdown con las claves exactas del
        # carrito (emitidas por el servidor), no es texto libre como en add_product.
        codigo = (data.get("eliminar") or "").strip()
        # pop con default: doble toque o carrito expirado no deben reventar.
        carrito["productos"].pop(codigo, None)
        redis_cache.guardar_carrito(req.flow_token, carrito)
        print(f"[FLOW] remove_product codigo={codigo}")
        return req.respond(screen="PRODUCTO", data=data_producto(carrito, eliminado=codigo))

    # ── totalizar: calcular totales y navegar a RESUMEN ───────────────────────
    if action == "totalizar":
        if not carrito.get("productos"):
            return req.respond(
                screen="PRODUCTO",
                data=data_producto(carrito, error="Agrega al menos un producto."),
            )
        resumen_txt, carrito = _calcular_totales_y_resumen(carrito)
        redis_cache.guardar_carrito(req.flow_token, carrito)
        return req.respond(screen="RESUMEN", data={"resumen_texto": resumen_txt})

    return req.respond(screen="CLIENTE", data={}, error_message="Acción desconocida.")


@wa.on_flow_completion(filters.new(nuevo_pedido_flow) & filters.new(user_with_auth))
def completar_pedido_flow(client: WhatsApp, flow: FlowCompletion):
    """Maneja el completion del Flow de pedido guiado (Fase B).

    Construye el pedido desde la respuesta del Flow, lo valida, genera el PDF
    preliminar y lo envía al vendedor igual que el flujo de texto.
    """
    user_id  = flow.from_user.wa_id
    respuesta = flow.response.get('nuevo_pedido', {})

    # El Flow debe enviar: cliente, tipo_precio, comentario, y los productos
    # en la misma estructura que usa el flujo de texto.
    # pywa expone el token del Flow como `flow.token` (FlowCompletion), no `flow_token`.
    # El carrito real (con los productos) está en Redis indexado por ese token.
    carrito = redis_cache.obtener_carrito(flow.token) if flow.token else None
    if not carrito:
        # Fallback: intentar construir desde flow.response directamente
        carrito = respuesta

    if not carrito or not carrito.get('productos'):
        client.send_message(
            to=user_id,
            header="Error en el pedido",
            text="No se encontraron productos en el pedido. Por favor intenta de nuevo.",
            footer="Dist Marluis",
        )
        return

    # Re-validar con la cadena de handlers (por si los precios cambiaron)
    pedido = construir_pedido(carrito, respuesta)
    handler_chain = ClienteHandler(ProductoHandler())
    try:
        handler_chain.handle(pedido, user_id)
    except ValueError as e:
        client.send_message(
            to=user_id,
            text=str(e),
            header='Error en el pedido',
            footer='Dist Marluis',
        )
        return

    # Generar preliminar y enviar (mismo flujo que texto)
    pedido['id'] = 'PRELIMINAR'
    pdf_buffer = get_generador_pdf()(filename='static/media/pedido_preliminar.pdf',
                                     pedido=pedido, preliminar=True)

    lineas_resumen = [f"Hola {flow.from_user.name}, Por favor confirma tu pedido!!"]
    if pedido.get('base_16', 0) > 0:
        lineas_resumen.append(f"```💰Base 16%```: ${round(pedido['base_16'], 2)}")
        lineas_resumen.append(f"```💰IVA 16%```: ${round(pedido['iva_16'], 2)}")
    if pedido.get('base_8', 0) > 0:
        lineas_resumen.append(f"```💰Base 8%```: ${round(pedido['base_8'], 2)}")
        lineas_resumen.append(f"```💰IVA 8%```: ${round(pedido['iva_8'], 2)}")
    if pedido.get('exento', 0) > 0:
        lineas_resumen.append(f"```💰Exento```: ${round(pedido['exento'], 2)}")
    lineas_resumen.append(f"```💰Total Neto```: ${round(pedido['total_neto'], 2)}")
    lineas_resumen.append("_En caso de no confirmar el pedido se eliminará luego de 1 hora⏳_")

    response_msg = client.send_message(
        header='Preliminar de Pedido',
        to=user_id,
        text="\n".join(lineas_resumen),
        footer='Dist Marluis',
        buttons=FlowButton(title='Confirmar Pedido', flow_id=FLOW_ID_CONFIRMACION),
    )
    client.send_document(
        to=user_id,
        document=pdf_buffer,
        filename=f'Preliminar{uuid.uuid4().hex[:10]}.pdf',
        caption='Descargue el preliminar de su pedido aquí',
        mime_type='application/pdf',
    )
    redis_cache.agregar_pedido(user_id, pedido, response_msg.id)
    if flow.token:
        redis_cache.eliminar_carrito(flow.token)