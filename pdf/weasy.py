# Shim de compatibilidad: el formato Marluis se movió a pdf/formato_marluis.py
from pdf.formato_marluis import generar as generar_factura

__all__ = ["generar_factura"]
