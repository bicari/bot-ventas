from pywa import WhatsApp, types


def registrar_cliente(_: WhatsApp, msg: types.Message):
    return True if 'registrar' in msg.response else False

def confirmar_pedido(_: WhatsApp, msg: types.Message):
    return True if 'confirmacion' in msg.response else False

def nuevo_pedido_flow(_: WhatsApp, msg: types.Message):
    """Detecta el completion del Flow de toma de pedido guiada."""
    return True if 'nuevo_pedido' in msg.response else False