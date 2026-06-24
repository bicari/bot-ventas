"""Ruteo de acciones del Flow de pedidos.

WhatsApp descarta la clave estática ``action`` del payload de las peticiones
``data_exchange`` porque colisiona con el campo ``action`` de nivel superior de
la propia petición (INIT / data_exchange). Por eso el servidor no puede confiar
en ``data["action"]`` para decidir qué hacer: aunque el Flow publicado en Meta
defina ``"action": "select_client"`` en el payload, ese literal nunca llega.

La solución es deducir la acción a partir de la pantalla activa y de los campos
del formulario presentes en el payload.
"""

from typing import Optional


def inferir_accion_flow(accion: Optional[str], pantalla: str, data: dict) -> Optional[str]:
    """Determina la acción del Flow a ejecutar.

    Args:
        accion: valor de ``data["action"]`` si Meta lo conservó (normalmente None).
        pantalla: pantalla activa del Flow (``req.raw["screen"]``).
        data: payload recibido (``req.raw["data"]``).

    Returns:
        ``"select_client"``, ``"add_product"``, ``"totalizar"`` o ``None`` si es un
        refresco/BACK sin datos de formulario que procesar.
    """
    if accion:
        return accion
    if pantalla == "CLIENTE" and data.get("cliente_id"):
        return "select_client"
    if pantalla == "PRODUCTO" and data.get("codigo"):
        return "add_product"
    if pantalla == "PRODUCTO" and data.get("totalizar"):
        return "totalizar"
    return None
