"""Helpers puros para armar los campos de impuesto del INSERT a DBISAM.

A2 modela dos slots de impuesto por línea (impuesto 1 = 16%, impuesto 2 = 8%)
y separa las bases gravadas por tasa en la cabecera. El exento no tiene campo:
es implícito (TOTALBRUTO - BASEIMPONIBLE - BASEIMPONIBLE2). Extraído para poder
testearlo sin conexión a BD.
"""


def slots_impuesto_linea(impuesto: float, monto_iva: float) -> dict:
    """Enruta la tasa de una línea a los dos slots de impuesto de A2.

    16% -> slot 1, 8% -> slot 2, exento -> ceros. ``porc1``/``porc2`` son el
    booleano "es porcentaje" (siempre 1). La tasa puede llegar como float
    (8.0) desde SQL, por eso se normaliza.
    """
    tasa = round(float(impuesto))
    es_16 = tasa == 16
    es_8 = tasa == 8
    return {
        "imp1": 16 if es_16 else 0,
        "porc1": 1,
        "monto1": monto_iva if es_16 else 0.0,
        "imp2": 8 if es_8 else 0,
        "porc2": 1,
        "monto2": monto_iva if es_8 else 0.0,
    }


def campos_impuesto_cabecera(pedido: dict) -> dict:
    """Arma los campos de impuesto de la cabecera SOPERACIONINV.

    ``base_imponible`` es la base gravada al 16% solamente; ``base_imponible2``
    la base gravada al 8%. Los porcentajes son fijos (16 y 8).
    """
    return {
        "base_imponible": pedido.get("base_16", 0.0),
        "imp1_porcent": 16,
        "imp1_monto": pedido.get("iva_16", 0.0),
        "base_imponible2": pedido.get("base_8", 0.0),
        "imp2_porcent": 8,
        "imp2_monto": pedido.get("iva_8", 0.0),
    }
