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


# Rango de prioridad ante colisión: barra > interno > referencia.
# Se resuelve por rango y no por orden de fila porque DBISAM no garantiza
# el orden del resultado: hacerlo por orden sería no determinista.
_RANGO_BARRA = 0
_RANGO_INTERNO = 1
_RANGO_REFERENCIA = 2


def mapear_resultados(filas, productos, por_barra):
    """Resuelve qué fila corresponde a cada código tipeado por el vendedor.

    filas:     filas crudas del query (row[0]=FI_CODIGO, row[5]=FI_REFERENCIA).
    productos: códigos tal como los tipeó el vendedor.
    por_barra: {código_interno: código_de_barra_tipeado}.

    Devuelve (result_map, not_found).
    """
    tipeados = set(productos)
    mejor = {}  # código tipeado -> (rango, fila)

    for fila in filas:
        fi_codigo, fi_referencia = fila[0], fila[5]
        if fi_codigo in por_barra:
            original, rango = por_barra[fi_codigo], _RANGO_BARRA
        elif fi_codigo in tipeados:
            original, rango = fi_codigo, _RANGO_INTERNO
        elif fi_referencia in tipeados:
            original, rango = fi_referencia, _RANGO_REFERENCIA
        else:
            continue  # fila que no reclama ningún código tipeado

        actual = mejor.get(original)
        if actual is None or rango < actual[0]:
            mejor[original] = (rango, fila)

    result_map = {original: fila for original, (_, fila) in mejor.items()}
    not_found = [p for p in productos if p not in result_map]
    return result_map, not_found
