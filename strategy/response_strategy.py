from pywa import WhatsApp
from models.pedidos import Pedido_Detalle, Pedidos
from database.dbisam import DBISAMDatabase
from sqlmodel import Session
from datetime import datetime
from sqlmodel import SQLModel
from pdf.weasy import generar_factura

class RespuestaPedidoStrategy:
    def execute(self, client: WhatsApp, user: str): #btn: CallbackButton):
        raise NotImplementedError

class ConfirmarStrategy(RespuestaPedidoStrategy):
    def execute(self, client: WhatsApp, user: str, pedido: dict, session: Session):
        pedido_postgre = Pedidos(vendedor_id=pedido['vendedor'],
                                 cliente_id=pedido['cliente'],
                                 fecha=datetime.now(),
                                 total_bruto=pedido['total_bruto'],
                                 base_imponible=pedido['baseimponible'],
                                 total_neto=pedido['total_neto'],
                                 iva_16_monto=pedido['iva_16']
                                 )
        session.add(pedido_postgre)
        session.flush()
        id_pedido = pedido_postgre.id
        productos = [Pedido_Detalle(
                        pedido_id=pedido_postgre.id,
                        producto_id=producto[0],
                        cantidad=producto[1]['cantidad'],
                        precio_unitario=producto[1]['precio']
        ) for producto in pedido['productos'].items()]
        session.add_all(productos)
        session.commit()
        pedido["id"] = id_pedido
        #session.refresh(pedido_postgre)
        DBISAMDatabase().insert_pedidos(pedido)
        generar_factura(filename=f'static/media/pedido{pedido["id"]}.pdf', pedido=pedido, logo_path='pdf/marluis.png')
        client.send_document(
            to=user,
            document=f'static/media/pedido{pedido["id"]}.pdf',
            caption='Su pedido ha sido procesado con éxito',
            filename=f'Pedido nro:{id_pedido}.pdf'
        )
        client.send_message(
            to=user,
            header="Orden Procesada",
            text=f"Orden Procesada, su número de orden es: {id_pedido}",
            footer="Distribuidora Marluis",
        )

class CancelarStrategy(RespuestaPedidoStrategy):
    def execute(self, client: WhatsApp, user: str, pedido: dict):
        client.send_message(
            to=user,
            header="Cancelado",
            text="❌ Pedido Cancelado",
            footer="Distribuiora Marluis",
        )

class PreliminarStrategy(RespuestaPedidoStrategy):
    def execute(self, client: WhatsApp, user: str):
        #pedido = ast.literal_eval(btn.data.pedido)
        #print(pedido)
        #repo = PedidoRepository(DBISAMDatabase())
        #if repo.check_precios(list(pedido["productos"].keys()), pedido["precio"]):
        client.send_document(
                to=user,
                document="factura_reportlab_logo.pdf",
                filename="Preliminar",
                caption="Preliminar del pedido",
            )
        #else:
        #    print("Error al consultar precios")