from pywa import WhatsApp, types


def registrar_cliente(_: WhatsApp, msg: types.Message):
    return True if 'registrar' in msg.response else False

def confirmar_pedido(_: WhatsApp, msg: types.message):
    return True if 'confirmacion' in msg.response else False