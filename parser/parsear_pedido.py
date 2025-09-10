from typing import Optional, Dict, Literal
from dataclasses import dataclass, field
import re

@dataclass
class Pedido:
    cliente: str
    productos: Dict[str, int] = field(default_factory=dict)
    precio: Literal["P1", "P2"] = "P1"
    comentario: Optional[str] = ""

class PedidoParser:
    def parse(self, text_msg: list[str]) -> dict:
        raise NotImplementedError


class PedidoTextoParser(PedidoParser):
    def parse(self, text_msg: list[str]) -> dict:
        PRODUCTOS_REGEX = re.compile(r"^([A-Z0-9]+)\s+(?!0\.00$)([1-9]\d*(?:\.\d{2})?|0\.\d{2})$", re.IGNORECASE)
        PRODUCTOS_SOLO = re.compile(r"^[A-Z0-9]+\s+\S+$", re.IGNORECASE)
        precio: str = "P1"
        comentario: str = ""
        if len(text_msg) < 2:
            return ValueError("Formato de pedido inválido")
        productos = {}
        productos_invalidos = ''
        for linea in text_msg[1:]:
            match = PRODUCTOS_REGEX.fullmatch(linea.strip())
            if match:
                codigo, cantidad = match.groups()
                try:
                    productos[codigo.upper()] = int(cantidad)
                except ValueError:
                    continue
                continue
            #     productos_invalidos.append(linea.strip())
            #     print('No cumple', linea)    

            elif linea in ("P1", "P2"):
                precio = linea
                continue
            elif PRODUCTOS_SOLO.fullmatch(linea):
                productos_invalidos += ''.join(linea.split()) + ','
                continue
            else:
                comentario += linea
            # Si no es producto ni precio, lo consideramos comentario
            #comentario = linea if not PRODUCTOS_REGEX.match(linea.strip()) else comentario
            #print(linea.split(), len(comentario), comentario, linea.strip())
                


        return Pedido(
            cliente=text_msg[0],
            productos=productos,
            precio=precio,
            comentario=comentario
        ).__dict__ if not productos_invalidos else ValueError(f"Códigos de producto inválidos: {productos_invalidos}")
    
class ParserFactory:
    @staticmethod
    def get_parser(tipo: str) -> PedidoParser:
        if tipo == "texto":
            return PedidoTextoParser()
        raise ValueError("Tipo de mensaje no soportado")
