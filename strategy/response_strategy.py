from pywa import WhatsApp
from models.pedidos import Pedido_Detalle, Pedidos
from database.dbisam import DBISAMDatabase
from database.catalogos import catalogo_de_sistema
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
                                 descripcion_cliente=pedido.get('descripcion_cliente'),
                                 direccion_cliente=pedido.get('direccion_cliente'),
                                 nombre_vendedor=pedido.get('nombre_vendedor'),
                                 tipo_precio=pedido.get('precio'),
                                 comentario=pedido.get('comentario'),
                                 total_bruto=pedido['total_bruto'],
                                 base_imponible=pedido.get('baseimponible', 0.0),
                                 base_16_monto=pedido.get('base_16', 0.0),
                                 base_8_monto=pedido.get('base_8', 0.0),
                                 total_neto=pedido['total_neto'],
                                 iva_16_monto=pedido.get('iva_16', 0.0),
                                 iva_8_monto=pedido.get('iva_8', 0.0),
                                 iva_total=pedido.get('iva_total', 0.0),
                                 exento_monto=pedido.get('exento', 0.0),
                                 peso_total=pedido.get('peso_total', 0.0),
                                 )
        session.add(pedido_postgre)
        session.flush()
        id_pedido = pedido_postgre.id
        productos = [Pedido_Detalle(
                        pedido_id=pedido_postgre.id,
                        producto_id=producto[0],
                        descripcion=producto[1].get('descripcion'),
                        cantidad=producto[1]['cantidad'],
                        precio_unitario=producto[1].get('precio', 0.0),
                        precio_sin_iva=producto[1].get('precio_sin_iva', 0.0),
                        precio_sin_descuento=producto[1].get('precio_sin_iva', 0.0),
                        precio_con_descuento=producto[1].get('precio_con_descuento', 0.0),
                        precio_venta=producto[1].get('precio_venta', 0.0),
                        descuento=producto[1].get('descuento', 0.0),
                        porcent_descuento=producto[1].get('descuento', 0.0),
                        impuesto=producto[1].get('impuesto', 0.0),
                        monto_iva=producto[1].get('monto_iva', 0.0),
                        total=producto[1].get('subtotal', 0.0),
                        total_sin_dcto=producto[1].get('total_sin_dcto', 0.0),
                        peso_item=producto[1].get('peso_item', 0.0),
        ) for producto in pedido['productos'].items()]
        session.add_all(productos)
        session.commit()
        pedido["id"] = id_pedido
        #session.refresh(pedido_postgre)
        DBISAMDatabase(catalog=catalogo_de_sistema(pedido.get("sistema"))).insert_pedidos(pedido)
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