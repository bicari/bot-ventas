from pywa import WhatsApp
from pywa.types import CallbackButton
import ast
from database.dbisam import DBISAMDatabase


class RespuestaPedidoStrategy:
    def execute(self, client: WhatsApp, btn: CallbackButton):
        raise NotImplementedError

class ConfirmarStrategy(RespuestaPedidoStrategy):
    def execute(self, client: WhatsApp, btn: CallbackButton):
        client.send_message(
            to=btn.data.user,
            header="Procesando",
            text="Procesando orden, en breve recibirá un mensaje con el número de orden correspondiente",
            footer="Dist Marluis",
        )

class CancelarStrategy(RespuestaPedidoStrategy):
    def execute(self, client: WhatsApp, btn: CallbackButton):
        client.send_message(
            to=btn.data.user,
            header="Cancelado",
            text="❌ Pedido Cancelado",
            footer="Dist Marluis",
        )

class PreliminarStrategy(RespuestaPedidoStrategy):
    def execute(self, client: WhatsApp, btn: CallbackButton):
        pedido = ast.literal_eval(btn.data.pedido)
        print(pedido)
        #repo = PedidoRepository(DBISAMDatabase())
        #if repo.check_precios(list(pedido["productos"].keys()), pedido["precio"]):
        client.send_document(
                to=btn.data.user,
                document="factura_reportlab_logo.pdf",
                filename="Preliminar",
                caption="Preliminar del pedido",
            )
        #else:
        #    print("Error al consultar precios")