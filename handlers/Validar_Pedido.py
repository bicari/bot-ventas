from abc import ABC, abstractmethod
from parser.parsear_pedido import Pedido
from database.dbisam import DBISAMDatabase
from pyodbc import DatabaseError

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
        productos.sort(key=int)
        try:
            query_products, not_found = DBISAMDatabase().consultar_precios(productos=productos, tipo_precio=pedido['precio'])
        except DatabaseError as e:
            raise ValueError(f"Ha ocurrido un error en la busqueda de los productos:\nMensaje de error:`{e}`")   
        #valores_query = {q[0] for q in query_products} | {q[4] for q in query_products}
        #not_found = #list(filter(lambda x: x not in list(map(lambda x: x[0] or x[4], query_products)), productos))
        #not_found = [p for p in productos if p not in valores_query]
        if not_found:
            raise ValueError(f"Los siguientes productos no fueron encontrados o se encuentran inactivos:\n" + ''.join(list(map(lambda x: '❌ `{product}`\n'.format(product=x), not_found))))
        else:
            # query_products ahora es un dict {codigo_original → fila}
            # Renombrar claves del pedido al FI_CODIGO interno cuando difieren
            for codigo_original, query in query_products.items():
                fi_codigo = query[0]
                print(codigo_original, fi_codigo)
                if fi_codigo != codigo_original and codigo_original in pedido["productos"]:
                    pedido["productos"][fi_codigo] = pedido["productos"].pop(codigo_original)

            print('Productos encontrados')
            for codigo_original, query in query_products.items():
                codigo, impuesto, precio, descripcion, peso, _ = query
                if codigo in pedido["productos"] and precio > 0:
                    precio_item = precio
                    pedido["productos"][codigo]["descripcion"] = descripcion
                    pedido["productos"][codigo]["impuesto"] =  impuesto
                    pedido["productos"][codigo]["precio_sin_iva"] = round(precio_item, 2)
                    pedido["productos"][codigo]["precio"] = round(precio_item * (pedido["productos"][codigo]["impuesto"] / 100 + 1), 2)
                    pedido["productos"][codigo]["precio_con_descuento"] = round(precio_item - (precio_item * (pedido["productos"][codigo]["descuento"]/ 100)), 2)
                    pedido["productos"][codigo]["monto_iva"]= round(pedido["productos"][codigo]["precio_con_descuento"] * (impuesto / 100),2)
                    pedido["productos"][codigo]["precio_venta"] = round((pedido["productos"][codigo]["precio_con_descuento"] * (pedido["productos"][codigo]["impuesto"] / 100 + 1)),2)
                    pedido["productos"][codigo]["subtotal"]= round(pedido["productos"][codigo]["precio_con_descuento"] * pedido["productos"][codigo]["cantidad"], 2)
                    pedido["productos"][codigo]["total_sin_dcto"]= round(pedido["productos"][codigo]["precio_sin_iva"] * pedido["productos"][codigo]["cantidad"], 2)
                    pedido["productos"][codigo]["peso_item"] = round(pedido["productos"][codigo]["cantidad"] * peso, 2)
                else: raise ValueError(f"El producto `{codigo}` tiene un precio menor o igual a cero, por favor verifique.")    
            
            prods = pedido["productos"]

            def base_por_tasa(tasa: int) -> float:
                return round(sum(p["precio_con_descuento"] * p["cantidad"]
                                 for p in prods.values() if p["impuesto"] == tasa), 2)

            pedido["peso_total"]    = round(sum(p["peso_item"] for p in prods.values()), 2)
            pedido["base_16"]       = base_por_tasa(16)
            pedido["base_8"]        = base_por_tasa(8)
            pedido["exento"]        = base_por_tasa(0)
            pedido["iva_16"]        = round(pedido["base_16"] * 0.16, 2)
            pedido["iva_8"]         = round(pedido["base_8"] * 0.08, 2)
            pedido["baseimponible"] = round(pedido["base_16"] + pedido["base_8"], 2)  # base gravada total (16% + 8%)
            pedido["iva_total"]     = round(pedido["iva_16"] + pedido["iva_8"], 2)
            pedido["total_bruto"]   = round(sum(p["precio_con_descuento"] * p["cantidad"] for p in prods.values()), 2)
            pedido["total_neto"]    = round(pedido["total_bruto"] + pedido["iva_total"], 2)
            
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