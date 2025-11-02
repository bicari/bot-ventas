from redis import Redis, ConnectionPool
import json

class PedidoCache:
    def __init__(self, host='localhost', port=2576, db=0, prefix='pedidos'):
        self.pool = ConnectionPool(host=host, port=port, db=db, max_connections=20)
        self.client = Redis(connection_pool=self.pool)
        self.prefix = prefix

    def _key_prefix(self, user_id: str, msg_id:str) -> str:
        return f"{self.prefix}:{user_id}:{msg_id}"
    
    def agregar_pedido(self, user_id: str, pedido:dict, msg_id:str, ttl:int = 3600):
        key = self._key_prefix(user_id, msg_id)
        #data =json.dumps({msg_id: pedido})
        data= json.dumps(pedido)
        self.client.setex(key, ttl, data)  

    def buscar_pedido_por_msg_id(self, user_id: str, msg_id: str):
        key = f"{self.prefix}:{user_id}:{msg_id}"
        data = self.client.get(key)
        if data:
            return json.loads(data)
        return None      

    def obtener_pedido_user(self, user_id: str):
        key = self._key_prefix(user_id)
        pedidos = self.client.lrange(key, 0, -1)
        return [json.loads(pedido) for pedido in pedidos]    
    
    def eliminar_pedido_user(self, user_id: str):
        pass