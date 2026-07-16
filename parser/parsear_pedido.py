from typing import Optional, Dict, Literal
from decimal import Decimal
from dataclasses import dataclass, field
import re

@dataclass
class Pedido:
    #wa_id: str 
    #message_id: str
    cliente: str
    productos: Dict[str, dict] = field(default_factory=dict)
    precio: Literal["P1", "P2"] = "P1"
    comentario: Optional[str] = ""
    total: Optional[Decimal] = 0.0

class PedidoParser:
    def parse(self, text_msg: list[str]) -> dict:
        raise NotImplementedError


class PedidoTextoParser(PedidoParser):
    def parse(self, text_msg: list[str]) -> dict:
        #PRODUCTOS_REGEX = re.compile(r"^([A-Z0-9]+)\s+(?!0\.00$)([1-9]\d*(?:\.\d{2})?|0\.\d{2})$", re.IGNORECASE)
        PRODUCTOS_REGEX = re.compile(
            r"^([A-Z0-9]+)\s+"
            r"(?!0\.00$)"
            r"([1-9]\d*(?:[.,]\d{1,2})?|0[.,]\d{1,2})"
            r"(?:\s+(\d+(?:[.,]\d+)?%))?$", re.IGNORECASE)
        PRODUCTOS_SOLO = re.compile(r"^(?=.*\d)[A-Z0-9]+$", re.IGNORECASE)#re.compile(r"^(?=.*\d)[A-Z0-9]+(?:\s+.*)?$", re.IGNORECASE)
        precio: str = "P1"
        comentario: str = ""
        if len(text_msg) < 2:
            return ValueError("Formato de pedido inválido: \n El formato correcto es:\n```<Código cliente:J12544888>\n<Código del producto> <Cantidad>\n<Código del producto> <Cantidad>\n...\n<P1|P2>\n<Comentario opcional>\n```")
        productos = {}
        productos_invalidos = []
        comentario_lineas: list[str] = []
        precio_visto = False
        for linea in text_msg[1:]:
            linea_limpia = linea.strip()
            if not linea_limpia:
                continue
            match = PRODUCTOS_REGEX.fullmatch(linea_limpia)
            if match:
                codigo, cantidad, descuento = match.groups()
                try:
                    productos[codigo.upper()] = {
                        'cantidad': float(cantidad.replace(',', '.')),
                        'descuento': float(descuento[0:-1].replace(',', '.')) if descuento else 0,
                    }
                except ValueError:
                    continue
                continue
            elif linea_limpia in ("P1", "P2"):
                precio = linea_limpia
                precio_visto = True
                continue
            elif not precio_visto and PRODUCTOS_SOLO.fullmatch(linea_limpia):
                productos_invalidos.append(f"* `{linea_limpia.split()[0]}`\n")
                continue
            else:
                comentario_lineas.append(linea_limpia)

        comentario = "\n".join(comentario_lineas)

        return Pedido(
            cliente=text_msg[0],
            productos=productos,
            precio=precio,
            comentario=comentario,
        ).__dict__ if not productos_invalidos else ValueError(
            f"Productos inválidos o cantidad incorrecta por favor verifique:\n{''.join(productos_invalidos)}"
        )
    
class ParserFactory:
    @staticmethod
    def get_parser(tipo: str) -> PedidoParser:
        if tipo == "texto":
            return PedidoTextoParser()
        raise ValueError("Tipo de mensaje no soportado")
