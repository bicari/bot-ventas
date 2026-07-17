"""Lógica pura de resolución de códigos para la consulta de precios.

Vive separada de database/dbisam.py para poder probarse sin el motor legado,
igual que database/impuestos.py.
"""


def lista_sql(valores) -> str:
    """Arma una lista IN de SQL, citando y escapando cada valor.

    El driver ODBC de DBISAM no acepta parámetros (Invalid SQL data type 11047),
    así que hay que interpolar; escapar aquí es la única defensa.

    Lanza ValueError si no hay valores: `IN ()` es SQL inválido en DBISAM y era
    la causa del error # 11949.
    """
    valores = list(valores)
    if not valores:
        raise ValueError("lista_sql() sin valores: produciria 'IN ()', invalido en DBISAM")
    return "(" + ",".join("'" + str(v).replace("'", "''") + "'" for v in valores) + ")"


def codigos_para_fi_codigo(productos, por_barra) -> list:
    """Códigos a buscar contra FI_CODIGO: lo tipeado + lo resuelto desde SCODEBAR.

    Preserva el orden y no duplica. La unión es lo que arregla el DBISAM Engine
    Error # 11949: antes la lista salía SOLO de SCODEBAR, así que un pedido sin
    ningún código de barra la dejaba vacía y emitía 'IN ()'. Incluyendo siempre
    lo tipeado, no puede quedar vacía mientras haya productos.
    """
    return list(dict.fromkeys(list(productos) + list(por_barra)))
