"""Resolución del CatalogName de DBISAM según el sistema (A/B) elegido.

El sistema seleccionado en el Flow determina a qué catálogo se ESCRIBE el
pedido. Las lecturas siguen usando config('CatalogName'). Esta función es pura
y nunca lanza: ante un sistema vacío, desconocido o sin ruta configurada,
devuelve el catálogo por defecto.
"""

from decouple import config


def mapa_catalogos() -> dict:
    """Construye el mapa sistema -> CatalogName desde el entorno."""
    return {
        "A": config("CATALOG_SISTEMA_A", default=""),
        "B": config("CATALOG_SISTEMA_B", default=""),
    }


def catalogo_de_sistema(sistema, mapa=None, default=None) -> str:
    """Resuelve el CatalogName para el sistema elegido (fallback al por defecto)."""
    if mapa is None:
        mapa = mapa_catalogos()
    if default is None:
        default = config("CatalogName")
    ruta = mapa.get((sistema or "").strip().upper())
    if not ruta:
        return default
    return ruta
