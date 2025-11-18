from abc import ABC, abstractmethod
from parser.parsear_pedido import Pedido
from database.dbisam import DBISAMDatabase

class Handler(ABC):
    def __init__(self, next_handler: "Handler" = None):
        self._next = next_handler

    @abstractmethod
    def handle(self, pedido: Pedido, user_id: str) -> None:
       ...

    def next(self, pedido: Pedido, user_id: str) -> None:
        if self._next:
          return self._next.handle(pedido, user_id)
        return pedido
            

class ClienteHandler(Handler):
    def handle(self, pedido: Pedido, user_id: str) -> None:
        vendedor = DBISAMDatabase().consultar_vendedor(user_id)
        cliente_desc = DBISAMDatabase().consultar_cliente(pedido['cliente'], vendedor[0])
        #print(codigo_vendedor, cliente_desc)
        #Validación de código de cliente desactivado temporalmente
        #if not pedido['cliente'].startswith(("J", "G", "V", "E", "P")):  # Cliente
        #    raise ValueError("Código de cliente inválido. Debe comenzar con J, G, V, E o P.")
        if cliente_desc is None:
            raise ValueError(f"El cliente `{pedido['cliente']}` no está asignado a tus clientes o se encuentra inactivo. \n\nPuedes solicitar la creación del cliente comunicándote con el departamento de administración o usando el comando de creación `\crear_cliente` y llenando el formulario.")
        pedido['descripcion_cliente'] = cliente_desc[0]
        pedido['direccion_cliente'] = cliente_desc[1]
        pedido['vendedor'] = vendedor[0]
        pedido['nombre_vendedor']= vendedor[1]
        return self.next(pedido, user_id)


class ProductoHandler(Handler):
    def handle(self, pedido: Pedido, user_id: str) -> ValueError | bool:
        productos = [producto for producto in pedido['productos'].keys()]
        query_products = DBISAMDatabase().consultar_precios(productos=productos, tipo_precio=pedido['precio'])
        not_found = list(filter(lambda x: x not in list(map(lambda x: x[0], query_products)), productos))
        if not_found:
            raise ValueError(f"Los siguientes productos no fueron encontrados o se encuentran inactivos:\n" + ''.join(list(map(lambda x: '❌ `{product}`\n'.format(product=x), not_found))))
        else:
            print('Productos encontrados')
            # base_imponible16 = sum([item[2] * pedido['productos'][item[0]]['cantidad'] for item in query_products if item[1] == 16])
            # base_imponible8  = sum([item[2]  * pedido['productos'][item[0]]['cantidad'] for item in query_products if item[1] == 8])
            # exento = sum([item[2]  * pedido['productos'][item[0]]['cantidad'] for item in query_products if item[1] == 0])
            # iva_16 = round(base_imponible16 * 0.16, 2)
            # iva_8 = round(base_imponible8 * 0.08, 2)
            # total_bruto = sum([item[2] * pedido['productos'][item[0]]['cantidad'] for item in query_products])
            # pedido["total_bruto"] = total_bruto
            # pedido["baseimponible"] = base_imponible16 
            # pedido["total_neto"] = round(total_bruto + iva_16 + iva_8, 2)
            # pedido["iva_16"] = iva_16
            # pedido["exento"] = exento
            for codigo, impuesto, precio, descripcion in query_products:
                if codigo in pedido["productos"] and precio > 0:
                    precio_item = precio
                    pedido["productos"][codigo]["descripcion"] = descripcion
                    pedido["productos"][codigo]["impuesto"] =  impuesto
                    pedido["productos"][codigo]["precio_sin_iva"] = precio_item
                    pedido["productos"][codigo]["precio"] = round(precio_item * (pedido["productos"][codigo]["impuesto"] / 100 + 1), 2)
                    pedido["productos"][codigo]["precio_con_descuento"] = round(precio_item - (precio_item * (pedido["productos"][codigo]["descuento"]/ 100)), 2)
                    pedido["productos"][codigo]["monto_iva"]= round(pedido["productos"][codigo]["precio_con_descuento"] * (impuesto / 100),2)
                    pedido["productos"][codigo]["precio_venta"] = round((pedido["productos"][codigo]["precio_con_descuento"] * (pedido["productos"][codigo]["impuesto"] / 100 + 1)),2)
                    pedido["productos"][codigo]["subtotal"]= round(pedido["productos"][codigo]["precio_venta"] * pedido["productos"][codigo]["cantidad"], 2)
                else: raise ValueError(f"El producto `{codigo}` tiene un precio menor o igual a cero, por favor verifique.")    
            
            pedido["baseimponible"] = round(sum(pedido["productos"][item]["precio_con_descuento"] * pedido["productos"][item]["cantidad"] for item in pedido["productos"].keys() if pedido["productos"][item]["impuesto"] == 16), 2)
            pedido["exento"] = round(sum(pedido["productos"][item]["subtotal"] for item in pedido["productos"].keys() if pedido["productos"][item]["impuesto"] == 0),2)
            pedido["total_bruto"] = round(sum(pedido["productos"][item]["precio_con_descuento"] * pedido["productos"][item]["cantidad"]  for item in pedido["productos"].keys()),2)
            pedido["iva_16"] = round(pedido["baseimponible"] * 0.16, 2)
            pedido["total_neto"] = round(pedido["total_bruto"] + pedido["iva_16"], 2)
            
            print(pedido)
            return self.next(pedido, user_id)
            

# class PrecioHandler(Handler):
#     def handle(self, pedido: Pedido) -> None:
#         if line in ("P1", "P2", "P3"):
#             pedido.precio = line
#         else:
#             self.next(line, pedido)


# class ComentarioHandler(Handler):
#     def handle(self, pedido: Pedido) -> None:
#         # Si no encaja en nada, lo consideramos comentario
#         pedido.comentario = line.strip()            