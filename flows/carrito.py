"""Formateo del carrito y armado de la data de la pantalla PRODUCTO del Flow.

Extraido de main.py para poder testearlo sin importar el cliente WhatsApp
ni las conexiones a BD/Redis. La pantalla PRODUCTO enlaza este texto con la
referencia pura ${data.items_texto} (WhatsApp Flows no resuelve referencias
incrustadas en texto estatico).
"""

from typing import Optional


def formato_carrito(
    carrito: dict,
    agregado: Optional[str] = None,
    eliminado: Optional[str] = None,
) -> str:
    """Genera el texto del carrito.

    Args:
        carrito: dict con clave ``productos`` (dict de codigo -> datos).
        agregado: etiqueta del producto recien agregado (p.ej. ``"ABC123 × 5"``)
            para anteponer una linea de confirmacion; ``None`` para no mostrarla.
        eliminado: codigo del producto recien eliminado, para anteponer la
            linea ``🗑️ Eliminado: ...``. A diferencia de ``agregado``, se
            muestra aunque el carrito quede vacio (caso: borrar el ultimo item).

    Returns:
        Texto multilinea del carrito, o el mensaje de carrito vacio.
    """
    prods = carrito.get("productos", {})

    prefijo = ""
    if agregado and prods:
        prefijo = f"✅ Agregado: {agregado}\n\n"
    elif eliminado:
        prefijo = f"🗑️ Eliminado: {eliminado}\n\n"

    if not prods:
        return f"{prefijo}Sin productos agregados aún."

    lineas = []
    for cod, p in prods.items():
        desc_str = f" (-{p['descuento']}%)" if p.get("descuento") else ""
        manual_str = " ✏️" if p.get("precio_manual") else ""
        lineas.append(f"• {cod} × {p['cantidad']}{desc_str}{manual_str} = ${p['subtotal']:.2f}")
    return prefijo + "\n".join(lineas)


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


def data_producto(
    carrito: dict,
    error: Optional[str] = None,
    agregado: Optional[str] = None,
    eliminado: Optional[str] = None,
) -> dict:
    """Arma el bloque ``data`` de la pantalla PRODUCTO del Flow.

    Incluye ``tiene_items`` (visibilidad de "Totalizar" y del Dropdown de
    borrado) e ``items_eliminar`` (data-source del Dropdown "Eliminar item").
    """
    prods = carrito.get("productos", {})
    return {
        "items_texto": formato_carrito(carrito, agregado=agregado, eliminado=eliminado),
        "error": f"⚠️ {error}" if error else " ",
        "show_error": bool(error),
        "tiene_items": bool(prods),
        "items_eliminar": [
            {"id": cod, "title": f"{cod} × {p['cantidad']}"} for cod, p in prods.items()
        ],
    }
