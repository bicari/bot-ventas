"""Formateo del carrito y armado de la data de la pantalla PRODUCTO del Flow.

Extraido de main.py para poder testearlo sin importar el cliente WhatsApp
ni las conexiones a BD/Redis. La pantalla PRODUCTO enlaza este texto con la
referencia pura ${data.items_texto} (WhatsApp Flows no resuelve referencias
incrustadas en texto estatico).
"""

from typing import Optional


def formato_carrito(carrito: dict, agregado: Optional[str] = None) -> str:
    """Genera el texto del carrito.

    Args:
        carrito: dict con clave ``productos`` (dict de codigo -> datos).
        agregado: etiqueta del producto recien agregado (p.ej. ``"ABC123 × 5"``)
            para anteponer una linea de confirmacion; ``None`` para no mostrarla.

    Returns:
        Texto multilinea del carrito, o el mensaje de carrito vacio.
    """
    prods = carrito.get("productos", {})
    if not prods:
        return "Sin productos agregados aún."

    lineas = []
    for cod, p in prods.items():
        desc_str = f" (-{p['descuento']}%)" if p.get("descuento") else ""
        manual_str = " ✏️" if p.get("precio_manual") else ""
        lineas.append(f"• {cod} × {p['cantidad']}{desc_str}{manual_str} = ${p['subtotal']:.2f}")
    cuerpo = "\n".join(lineas)

    if agregado:
        return f"✅ Agregado: {agregado}\n\n{cuerpo}"
    return cuerpo


def construir_pedido(carrito: dict, respuesta: dict) -> dict:
    """Arma el pedido del completion del Flow a partir del carrito de Redis.

    El comentario NO está en el carrito: el vendedor lo escribe en la pantalla
    RESUMEN y llega en la respuesta del Flow (``nuevo_pedido.comentario``).
    Tomarlo del carrito era el bug que dejaba el PDF sin observaciones.
    """
    return {
        "cliente": carrito.get("cliente", ""),
        "productos": carrito.get("productos", {}),
        "precio": carrito.get("tipo_precio", "P1"),
        "comentario": respuesta.get("comentario") or carrito.get("comentario", ""),
        "sistema": carrito.get("sistema", ""),
        "total": 0.0,
    }


def data_producto(carrito: dict, error: Optional[str] = None, agregado: Optional[str] = None) -> dict:
    """Arma el bloque ``data`` de la pantalla PRODUCTO del Flow.

    Incluye ``tiene_items``, que controla la visibilidad del botón "Totalizar".
    """
    return {
        "items_texto": formato_carrito(carrito, agregado=agregado),
        "error": f"⚠️ {error}" if error else " ",
        "show_error": bool(error),
        "tiene_items": bool(carrito.get("productos")),
    }
