import pywa
from database.dbisam import DBISAMDatabase

def procesar_preliminar() -> bool:
    productos = DBISAMDatabase().consultar_precios()
    print(productos)