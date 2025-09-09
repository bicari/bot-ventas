import fastapi
from pywa import WhatsApp, types, filters
from contextlib import asynccontextmanager
from pywa.types import Template as temp
from database.dbisam import DBISAMDatabase
from pywa.types import CallbackData, CallbackButton, Button
from strategy.response_strategy import CancelarStrategy, ConfirmarStrategy, PreliminarStrategy
import ast
from dataclasses import dataclass
from filtros.UserFiltro import user_with_auth
from pdf.weasy import generar_factura
from handle_msg import procesar_preliminar


data = {}
# @asynccontextmanager
# async def lifespan(app: fastapi.FastAPI):
#     global data
#     data = await DBISAMDatabase().a2invcostosprecios()  # Initialize the database connection
#     #print(data)
#     yield
    # Aquí podrías cerrar conexiones o limpiar recursos si es necesario

fastapi_app = fastapi.FastAPI()


wa = WhatsApp(
    phone_id='788035891058430',
    token='EAAR6yERULLYBPHkeuV3aRnZCZBCtW0RkYssTx4OTO7BsCDmvJntOANocRREVGyR7jZBOIpGaeVtGusSkvZCde9qk4ZBZCMRI2SXI4BHqv9Lhn65XgySrPg2jgUv0Y8foUmJbzeytfM3xKuZAK3wA3xdNQKsmS3ZApStEmeLztn58qe252josZCfCqGxsplcDMokZC5IQZDZD',
    server=fastapi_app,
    verify_token='XYZ123',
)

@dataclass(frozen=True, slots= True)
class UserResponsePedido(CallbackData):
    response: str
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
    # if btn.data.response == 'Sí':
    #     _.send_message(
    #         to=btn.data.user,
    #         header='Procesando',
    #         text='Procesando orden, en breve recibira un mensaje con el numero de orden Correspondiente',
    #         footer='Dist Marluis'
    #     )
        
    # elif btn.data.response == 'No':
    #    _.send_message(
    #         to=btn.data.user,
    #         text='❌ Pedido Cancelado',
    #         header='Cancelado',
    #         footer='Dist Marluis'
    #     )
    # elif btn.data.response == 'Preliminar':
    #     _.send_document(
    #         to=btn.data.user,
    #         document='factura_reportlab_logo.pdf',
    #         filename='Preliminar',
    #         caption=''
            
    #     ) if DBISAMDatabase().consultar_precios(productos=list(pedido['productos'].keys()),tipo_precio=pedido['precio'] ) else print('Error')
        

        

@wa.on_message()#filters.startswith("Pedido", ignore_case=True))
def handle_message(client: WhatsApp, msg: types.Message):
    user_id = msg.from_user.wa_id
    text_msg= msg.text.splitlines()
    msg.react('👍')
    largo_mensaje = len(text_msg)
    products = {}
    pedido = {}
    print(user_id)
    for linea in text_msg:
        if not linea.startswith(('J', 'G', 'V', 'E', 'P')) and not text_msg.index(linea) == largo_mensaje - 1 : 
            list_products = linea.split()
            products[list_products[0]] = list_products[1]
    pedido["productos"]= products
    pedido["cliente"] = text_msg[0]
    pedido["comentario"] = text_msg[largo_mensaje - 1]
    pedido["precio"] = text_msg[largo_mensaje - 2]
    print(pedido)
    
    client.send_message(
         to=msg.from_user,
         header='Pedido Recibido',
         text='Hola {user}, Por favor confirma tu pedido!!'.format(user=msg.from_user.name),
         footer='Dist Marluis',
         buttons=[Button(title='Sí', callback_data=UserResponsePedido(response='Sí', pedido=str(pedido), user=user_id)), 
                  Button(title='No', callback_data=UserResponsePedido(response='No', pedido=str(pedido), user=user_id)),
                  Button(title='Preliminar', callback_data=UserResponsePedido(response='Preliminar', pedido=str(pedido), user=user_id))],
         reply_to_message_id=msg.id
     )
    
    

    