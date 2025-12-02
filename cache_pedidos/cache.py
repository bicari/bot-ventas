from typing import Dict
from collections import defaultdict

# Estructura: { user_id: [pedidos] }
cache_pedidos: Dict[str, list] = defaultdict(list)

def add_pedido(user_id: str, pedido: dict):
    cache_pedidos[user_id].append(pedido)

def get_pedidos(user_id: str) -> list:
    return cache_pedidos.get(user_id, [])

def clear_pedidos(user_id: str):
    cache_pedidos.pop(user_id, None)
