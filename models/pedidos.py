from sqlmodel import Field, SQLModel
from enum import Enum
from datetime import datetime
from typing import Optional

class EstadoPedido(str, Enum):
    PENDIENTE = "Pendiente"
    CANCELADO = "Cancelado"
    FACTURADO = "Facturado"


class Pedidos(SQLModel, table=True):
    id : int | None = Field(default=None, primary_key=True, unique=True, index=True)
    vendedor_id : str | None = Field(default=None)
    cliente_id : str | None = Field(default=None)
    fecha : datetime | None = Field(default_factory=datetime.now)
    estado : str = Field(default=EstadoPedido.PENDIENTE)
    descripcion_cliente : str | None = Field(default=None)   # nombre del cliente
    direccion_cliente : str | None = Field(default=None)
    nombre_vendedor : str | None = Field(default=None)
    tipo_precio : str | None = Field(default=None)            # tier de precio (P1/P2)
    comentario : str | None = Field(default=None)
    total_bruto : float = Field(default=0.0)
    base_imponible : float = Field(default=0.0)   # base gravada total (16% + 8%)
    base_16_monto : float = Field(default=0.0)    # base gravada al 16%
    base_8_monto : float = Field(default=0.0)     # base gravada al 8%
    total_neto : float = Field(default=0.0)
    iva_16_monto : float = Field(default=0.0)
    iva_8_monto : float = Field(default=0.0)
    iva_total : float = Field(default=0.0)        # iva_16 + iva_8
    exento_monto : float = Field(default=0.0)
    peso_total : float = Field(default=0.0)

class Pedido_Detalle(SQLModel, table=True):
    __tablename__ = 'pedido_detalle'

    id : int | None = Field(default=None, primary_key=True, unique=True, index=True)
    pedido_id : int = Field(default=None, foreign_key="pedidos.id")
    producto_id : str | None = Field(default=None)
    descripcion : str | None = Field(default=None)  # descripción del producto
    cantidad : float = Field(default=1.0)          # float para soportar cantidades decimales
    precio_unitario : float = Field(default=0.0)   # precio con IVA, sin descuento
    precio_sin_iva : float = Field(default=0.0)    # precio base sin IVA, sin descuento
    precio_sin_descuento : float = Field(default=0.0)
    precio_con_descuento : float = Field(default = 0.0)
    precio_venta : float = Field(default=0.0)      # precio con descuento e IVA
    descuento : float = Field(default=0.0)         # porcentaje de descuento
    porcent_descuento : float = Field(default=0.0)
    impuesto : float = Field(default=0.0)          # tasa de impuesto del producto (0, 8 ó 16)
    monto_iva : float = Field(default=0.0)         # monto de IVA de esta línea
    total : float = Field(default=0.0)
    total_sin_dcto : float = Field(default=0.0)    # cantidad * precio_sin_iva
    peso_item : float = Field(default=0.0)         # cantidad * peso del producto