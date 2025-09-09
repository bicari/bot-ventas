from pywa import WhatsApp, types


def user_with_auth(_: WhatsApp, msg: types.Message):
    if msg.from_user.wa_id in ['584244915022']:
        return True
    else:
        _.send_message(
        to=msg.from_user.wa_id,
        text='Usuario no autorizado para esta acción, contacte al administrador',
        header='No autorizado',
    )
        return False