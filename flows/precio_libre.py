"""Interpretación del precio libre que el vendedor escribe en el Flow.

Pura a propósito (sin BD/Redis/WhatsApp), siguiendo el patrón de
flows/carrito.py. El impuesto llega como argumento: lo trae fresco la
fila de DBISAM que add_product ya consulta.
"""


def resolver_precio_manual(precio_raw, incluye_iva_raw, descuento: float,
                           impuesto: int):
    """Devuelve la base SIN IVA del precio manual, o None si no hay precio.

    Reglas (en orden): precio vacío -> None (el radio marcado se ignora);
    no numérico, <= 0, o combinado con descuento -> ValueError; radio sin
    elegir -> ValueError; 'con_iva' descompone la base con el impuesto del
    producto, 'sin_iva' toma el número tal cual.
    """
    texto = str(precio_raw or "").strip()
    if not texto:
        return None

    try:
        precio = float(texto.replace(",", "."))
    except ValueError:
        raise ValueError(f"El precio '{texto}' no es un número válido.")
    if precio <= 0:
        raise ValueError("El precio debe ser mayor que cero.")
    if descuento and float(descuento) > 0:
        raise ValueError(
            "El precio manual y el descuento % son excluyentes; usa solo uno.")

    modo = str(incluye_iva_raw or "").strip()
    if modo == "con_iva":
        return round(precio / (1 + impuesto / 100), 2)
    if modo == "sin_iva":
        return round(precio, 2)
    raise ValueError("Indica si el precio incluye IVA.")
