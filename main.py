import fastapi
from typing import Dict
from collections import defaultdict
from pywa import WhatsApp, types, filters
from pywa.listeners import ListenerStopped, ListenerCanceled
from contextlib import asynccontextmanager
from pywa.types import FlowCompletion
from database.dbisam import DBISAMDatabase
from pywa.types import CallbackData, CallbackButton, Button, FlowButton
from strategy.response_strategy import CancelarStrategy, ConfirmarStrategy, PreliminarStrategy
from parser.parsear_pedido import ParserFactory
from handlers.Validar_Pedido import ClienteHandler, ProductoHandler#, PrecioHandler, ComentarioHandler
from dataclasses import dataclass
from filtros.UserFiltro import user_with_auth
from pdf.weasy import generar_factura
from handle_msg import procesar_preliminar


cache_pedidos: Dict[str, list] = defaultdict(list)

def add_pedido(user_id: str, pedido: dict, msg_id):
    cache_pedidos[user_id].append({msg_id : pedido})
    print(cache_pedidos)

def get_pedidos(user_id: str) -> list:
    return cache_pedidos.get(user_id, [])

def clear_pedidos(user_id: str):
    cache_pedidos.pop(user_id, None)


fastapi_app = fastapi.FastAPI()
wa = WhatsApp(
    phone_id='788035891058430',
    token='EAAR6yERULLYBPHkeuV3aRnZCZBCtW0RkYssTx4OTO7BsCDmvJntOANocRREVGyR7jZBOIpGaeVtGusSkvZCde9qk4ZBZCMRI2SXI4BHqv9Lhn65XgySrPg2jgUv0Y8foUmJbzeytfM3xKuZAK3wA3xdNQKsmS3ZApStEmeLztn58qe252josZCfCqGxsplcDMokZC5IQZDZD',
    server=fastapi_app,
    verify_token='XYZ123',
)
flows = wa.get_flows(waba_id='1152956486695534',phone_number_id='788035891058430')
for flow in flows:
    print(flow)

@dataclass(frozen=True, slots= True)
class UserResponsePedido(CallbackData):
    msg_id : str
    #response: str
    pedido: str
    user: str

@wa.on_callback_button(factory=UserResponsePedido)
def on_response_pedido(_: WhatsApp, btn: CallbackButton[UserResponsePedido]) :
    respuestas = {
        'Sí': ConfirmarStrategy(),
        'No': CancelarStrategy(),
        'Preliminar': PreliminarStrategy()
    }
    handle_response = respuestas.get(btn.data.response)
    if handle_response:
        handle_response.execute(_, btn)
    

@wa.on_flow_completion
def on_flow_completion(_: WhatsApp, flow: FlowCompletion):
    respuestas = {
        'Confirmado': ConfirmarStrategy(),
        'Cancelado': CancelarStrategy(),
        'Preliminar': PreliminarStrategy()
    }
    handle_response = respuestas.get(flow.response['confirmacion'])
    pedido = list(filter(lambda d: flow.reply_to_message.message_id in d, get_pedidos(flow.from_user.wa_id)))

    if handle_response:
        handle_response.execute(_, flow.from_user.wa_id, pedido[0][flow.reply_to_message.message_id])

@wa.on_message(filters.startswith('J', 'G', 'V') & filters.new(user_with_auth))#filters.startswith("Pedido", ignore_case=True))
def handle_message(client: WhatsApp, msg: types.Message):
    user_id = msg.from_user.wa_id
    text_msg= msg.text.splitlines()
  
    pedido = ParserFactory.get_parser('texto').parse(text_msg)

    if isinstance(pedido, ValueError):
        client.send_message(
            to=msg.from_user,
            text=str(pedido),
            header='Error en el pedido',
            footer='Dist Marluis',
            reply_to_message_id=msg.id
        )
        return
    handler_chain = ClienteHandler(
        ProductoHandler()
    )
    try:
        handler_chain.handle(pedido)
    except ValueError as e:
        client.send_message(
            to=msg.from_user,
            text=str(e),
            header='Error en el pedido',
            footer='Dist Marluis',
            reply_to_message_id=msg.id
        )
        return
        
    
    #try:
    
    response_user = client.send_message(
         to=msg.from_user,
         header='Pedido Recibido',
         text='Hola {user}, Por favor confirma tu pedido!!\n{items}\n```💰Base Imponible```: ${baseimponible}\n```💰Exento```: ${exento}\n```💰IVA 16%```: ${iva_16}\n```💰Total Neto%```: ${total_neto}\n\n_En caso de no confirmar el pedido se eliminará luego de 1 hora⏳_'.format(user=msg.from_user.name, exento=(pedido.get('exento')) ,iva_16=round(pedido.get('iva_16'),2) ,total_neto=round(pedido.get('total_neto'),2),baseimponible=round(pedido.get('baseimponible'), 2), items='\n'.join(list(map(lambda x: '📦Código: {code}\nCantidad: {qty}\nPrecio: ${price}\nSubtotal: ${sub}\n'.format(code=x, qty=pedido['productos'][x]['cantidad'], price=pedido['productos'][x]['precio'], sub=pedido['productos'][x]['subtotal']), pedido['productos'].keys())))),
         footer='Distribuidora Marluis',
          buttons=FlowButton(
              title='Confirmar Pedido',
              flow_id= '1114349466876600'
          )#Button(title='Sí', callback_data=UserResponsePedido(response='Sí', pedido=str(pedido), user=user_id)), 
                   #Button(title='No', callback_data=UserResponsePedido(response='No', pedido=str(pedido), user=user_id)),
                   ,#Button(title='Preliminar', callback_data=UserResponsePedido(response='Preliminar', pedido=str(pedido), user=user_id))],
         #reply_to_message_id=msg.id
        )#.wait_for_click(timeout=1)
    # except ListenerStopped | ListenerCanceled:
    #     client.send_message(
    #         to=msg.from_user,
    #         text='No se recibió una respuesta a tiempo. Por favor, envía tu pedido nuevamente si deseas continuar.',
    #         header='Tiempo agotado',
    #         footer='Dist Marluis',
    #         reply_to_message_id=msg.id
    #     )        
    #pedido = UserResponsePedido(msg_id=response_user.id, pedido=str(pedido), user=user_id)
    add_pedido(user_id, pedido, response_user.id)
    
@wa.on_message(filters.startswith("/crear_cliente", ignore_case=True) & filters.new(user_with_auth))
def crear_cliente(client: WhatsApp, msg: types.Message):
    client.send_message(
        to=msg.from_user,
        text='Funcionalidad en desarrollo',
        header='Crear Cliente',
        footer='Dist Marluis',
        reply_to_message_id=msg.id
    )
    