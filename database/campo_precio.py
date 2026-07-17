"""Selección del campo de precio de A2INVCOSTOSPRECIOS, configurable por .env.

Sigue el patrón de pdf/factory.py: lee config con un default y valida
ruidosamente. La lógica es pura para poder probarse sin DBISAM.
"""

import re

from decouple import config

CAMPO_PRECIO_DEFAULT = "PRECIOTOTALEXT"

# Tiers que consultar_precios mapea (P1/P2/P3 -> P01/P02/P03). El esquema tiene
# hasta P06, pero habilitarlos es otra feature.
TIERS = ("P01", "P02", "P03")

# El valor se interpola en el SQL porque el driver ODBC de DBISAM no acepta
# parámetros. Esta regex es la defensa contra inyección, no un detalle estético.
_FORMATO = re.compile(r"^[A-Z0-9]+$")

# IPRECIOTOTAL trae el IVA incluido (IPRECIOTOTAL/PRECIOSINIMPUESTO = 1.1600,
# medido contra la base). Validar_Pedido.py:69-70 suma el IVA sobre el precio,
# así que configurarlo facturaría con IVA doble sin ningún error visible.
_CON_IVA_INCLUIDO = "IPRECIOTOTAL"


def get_campo_precio() -> str:
    """Devuelve la variante de precio indicada por CAMPO_PRECIO, normalizada."""
    campo = config("CAMPO_PRECIO", default=CAMPO_PRECIO_DEFAULT).strip().upper()

    if not _FORMATO.match(campo):
        raise ValueError(
            f"CAMPO_PRECIO={campo!r} no es valido: solo letras y digitos. "
            "El valor se interpola en SQL, asi que no se aceptan espacios, "
            "comillas, guiones ni punto y coma."
        )

    if campo == _CON_IVA_INCLUIDO:
        raise ValueError(
            f"CAMPO_PRECIO={campo!r} trae el IVA ya incluido y el sistema lo "
            "suma de nuevo: facturaria con IVA doble. Use PRECIOTOTALEXT o "
            "PRECIOSINIMPUESTO, que vienen sin impuesto."
        )

    return campo


def _variantes_disponibles(columnas) -> list:
    """Deriva las variantes de precio sugeribles a partir de las columnas reales.

    Convierte {'FIC_P01PRECIOTOTALEXT', ...} en ['PRECIOTOTALEXT', ...], que es
    lo que el usuario escribe en CAMPO_PRECIO. Volcar las ~30 columnas crudas no
    le serviria de nada.

    Filtra dos veces, y ambas importan:

    - Solo las que contienen PRECIO. El prefijo FIC_P01 lo comparten columnas
      que no son precios (TIPOROUND, PORCENTUTILIDAD, IMTOIMPUESTO01); existen,
      asi que pasarian la validacion de existencia, pero cotizarian con basura.
    - Sin _CON_IVA_INCLUIDO, que get_campo_precio rechaza y mandaria al IVA doble.

    Sugerir una opcion que va a fallar es peor que no sugerir ninguna. Esto no
    restringe que se configure: la validacion sigue siendo por existencia real.
    """
    prefijo = "FIC_" + TIERS[0]
    variantes = (c[len(prefijo):] for c in columnas if c.startswith(prefijo))
    return sorted(v for v in variantes if "PRECIO" in v and v != _CON_IVA_INCLUIDO)


def validar_campo_precio(campo, columnas_existentes) -> None:
    """Verifica que FIC_{tier}{campo} exista para todos los tiers en uso.

    columnas_existentes: nombres de columna de A2INVCOSTOSPRECIOS.
    Lanza ValueError si falta alguna.
    """
    columnas = {c.upper() for c in columnas_existentes}
    faltantes = [f"FIC_{t}{campo}" for t in TIERS if f"FIC_{t}{campo}" not in columnas]
    if faltantes:
        raise ValueError(
            f"CAMPO_PRECIO={campo!r} no existe en A2INVCOSTOSPRECIOS: "
            f"faltan {', '.join(faltantes)}. "
            f"Variantes disponibles: {', '.join(_variantes_disponibles(columnas))}"
        )
