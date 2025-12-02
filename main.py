import fastapi
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from typing import Dict
from collections import defaultdict
from pywa import WhatsApp, types, filters
from contextlib import asynccontextmanager
from pywa.types.template import Language
from pywa.types import CallbackData, FlowButton, Button, Template, FlowCompletion
from strategy.response_strategy import CancelarStrategy, ConfirmarStrategy, PreliminarStrategy
from parser.parsear_pedido import ParserFactory
from handlers.Validar_Pedido import ClienteHandler, ProductoHandler#, PrecioHandler, ComentarioHandler
from dataclasses import dataclass
from database.dbisam import DBISAMDatabase
from filtros.UserFiltro import user_with_auth
from filtros.FlowFiltros import registrar_cliente, confirmar_pedido
from database.redis import PedidoCache
from database.postgres import create_tables_and_db
from sqlmodel import create_engine, Session
from pdf.weasy import generar_factura
from decouple import config

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
    yield

fastapi_app = fastapi.FastAPI()
wa = WhatsApp(
    phone_id=config('PHONE_ID'),
    token=config('TOKEN'),
    server=fastapi_app,
    verify_token=config('VERIFY_TOKEN'),
)
fastapi_app.mount("/static", StaticFiles(directory="static"), name="static")
# flows = wa.get_flows(waba_id='1152956486695534',phone_number_id='788035891058430')
# for flow in flows:
#     print(flow)

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

@wa.on_message(filters.new(user_with_auth))
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
     pdf_buffer = generar_factura(filename=f'static/media/pedido_preliminar.pdf', pedido=pedido, logo_path='pdf/marluis.png', preliminar=True)
     
     items = (list(map(
                 lambda x: """📦Código: {code}\nCantidad: {qty}\nPrecio: ${price}\n{precio_con_descuento}Subtotal: ${sub}\n""".format(code=x, qty=pedido['productos'][x]['cantidad'], price=pedido['productos'][x]['precio'], sub=pedido['productos'][x]['subtotal'], precio_con_descuento=f"`Precio Descuento:${pedido['productos'][x]['precio_venta'] }`\n" if pedido['productos'][x]['descuento'] > 0 else '' ), pedido['productos'].keys())))
     response_user = client.send_message(
          header='Preliminar de Pedido',
          to=msg.from_user,
          text='Hola {user}, Por favor confirma tu pedido!!\n```💰Base Imponible```: ${baseimponible}\n```💰Exento```: ${exento}\n```💰IVA 16%```: ${iva_16}\n```💰Total Neto%```: ${total_neto}\n\n_En caso de no confirmar el pedido se eliminará luego de 1 hora⏳_'.format(user=msg.from_user.name, exento=(pedido.get('exento')) ,iva_16=round(pedido.get('iva_16'),2) ,total_neto=round(pedido.get('total_neto'),2),baseimponible=round(pedido.get('baseimponible'), 2)),
          footer='Dist Marluis',
          buttons=FlowButton(
               title='Confirmar Pedido',
               flow_id= '1114349466876600' 
            )
         )
     client.send_document(
          to=msg.from_user,
          document=pdf_buffer,
          filename='Preliminar.pdf',
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
            flow_id="1418891859657565"
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