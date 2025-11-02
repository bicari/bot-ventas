from sqlmodel import Field, SQLModel
from enum import Enum
from datetime import datetime
from typing import Optional

class EstadoPedido(str, Enum):
    PENDIENTE = "Pendiente"
    CANCELADO = "Cancelado"
    FACTURADO = "Facturado"


class Pedidos(SQLModel, table=True):
    id : Optional[int] = Field(default=None, primary_key=True, unique=True, index=True)
    vendedor_id : str = Field(default=None)
    cliente_id : str = Field(default=None)
    fecha : datetime = Field(default_factory=datetime.now())
    estado : str = Field(default=EstadoPedido.PENDIENTE)
    total_bruto : float = Field(default=0.0)
    base_imponible : float = Field(default=0.0)
    total_neto : float = Field(default=0.0)
    iva_16_monto : float = Field(default=0.0)

class Pedido_Detalle(SQLModel, table=True):
    __tablename__ = 'pedido_detalle'
    
    id : Optional[int] = Field(default=None, primary_key=True, unique=True, index=True)
    pedido_id : int = Field(default=None, foreign_key="pedidos.id")
    producto_id : str = Field(default=None)
    cantidad : int = Field(default=1)
    precio_unitario : float = Field(default=0.0)
    precio_sin_descuento : float = Field(default=0.0)
    precio_con_descuento : float = Field(default = 0.0)
    descuento : float = Field(default=0.0)
    porcent_descuento : float = Field(default=0.0)   
    total : float = Field(default=0.0)