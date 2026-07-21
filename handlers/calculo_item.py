"""Aritmética por ítem de pedido, unificada.

Antes vivía copiada en main.py (add_product del Flow) y en
handlers/Validar_Pedido.py (ProductoHandler); el spec de CAMPO_PRECIO
(2026-07-16) dejó registrada la deuda y el precio libre la necesita
resuelta: la regla "manual vs lista" no puede vivir en dos sitios.

Puro a propósito: sin BD, sin Redis, sin WhatsApp.
"""


def calcular_item(precio_sin_iva: float, cantidad: float, descuento: float,
                  impuesto: int, peso: float) -> dict:
    """Deriva los montos de un ítem a partir de su precio base sin IVA.

    El llamador agrega por su cuenta cantidad, descuento, descripcion,
    impuesto y precio_manual; aquí solo se calculan los campos derivados.
    """
    precio_con_descuento = round(precio_sin_iva - precio_sin_iva * descuento / 100, 2)
    return {
        "precio_sin_iva": round(precio_sin_iva, 2),
        "precio": round(precio_sin_iva * (impuesto / 100 + 1), 2),
        "precio_con_descuento": precio_con_descuento,
        "monto_iva": round(precio_con_descuento * impuesto / 100, 2),
        "precio_venta": round(precio_con_descuento * (impuesto / 100 + 1), 2),
        "subtotal": round(precio_con_descuento * cantidad, 2),
        "total_sin_dcto": round(precio_sin_iva * cantidad, 2),
        "peso_item": round(cantidad * peso, 2),
    }
