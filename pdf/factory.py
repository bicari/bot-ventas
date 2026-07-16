from decouple import config
from pdf import formato_marluis, formato_ecograsas

_GENERADORES = {
    "marluis": formato_marluis.generar,
    "ecograsas": formato_ecograsas.generar,
}


def get_generador_pdf():
    """Devuelve la función generar() del formato indicado por FORMATO_PDF."""
    nombre = config("FORMATO_PDF", default="marluis").strip().lower()
    try:
        return _GENERADORES[nombre]
    except KeyError:
        raise ValueError(
            f"FORMATO_PDF='{nombre}' no es válido. Opciones: {', '.join(_GENERADORES)}"
        )
