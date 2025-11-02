from pywa import WhatsApp, types
from database.dbisam import DBISAMDatabase

def user_with_auth(_: WhatsApp, msg: types.Message):
    
    if msg.from_user.wa_id in DBISAMDatabase().consultar_vendedores_con_acceso():
        return True
    else:
        _.send_message(
        to=msg.from_user.wa_id,
        text='Usuario no autorizado para esta acción, contacte al administrador de la app *soporte@geekcod.com*',
        header='No autorizado',
    )
        return False