-- =============================================================================
-- schema.sql — Esquema PostgreSQL para la persistencia de pedidos
--
-- Refleja los modelos SQLModel de models/pedidos.py (fuente de verdad).
-- Si modificas los modelos, actualiza también este archivo y migration_001.
--
-- Uso (instalación nueva):
--   psql "<connection-string>" -f database/sql/schema.sql
--
-- Idempotente: usa CREATE TABLE IF NOT EXISTS. No destruye datos existentes.
-- Orden: pedidos primero, luego pedido_detalle (dependencia de clave foránea).
-- =============================================================================

-- ── Tabla: pedidos ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pedidos (
    id                  SERIAL PRIMARY KEY,
    vendedor_id         VARCHAR,
    cliente_id          VARCHAR,
    fecha               TIMESTAMP,
    estado              VARCHAR          NOT NULL DEFAULT 'Pendiente',
    descripcion_cliente VARCHAR,                              -- nombre del cliente
    direccion_cliente   VARCHAR,
    nombre_vendedor     VARCHAR,
    tipo_precio         VARCHAR,                              -- tier de precio (P1/P2)
    comentario          VARCHAR,
    total_bruto         DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    base_imponible      DOUBLE PRECISION NOT NULL DEFAULT 0.0, -- base gravada total (16% + 8%)
    base_16_monto       DOUBLE PRECISION NOT NULL DEFAULT 0.0, -- base gravada al 16%
    base_8_monto        DOUBLE PRECISION NOT NULL DEFAULT 0.0, -- base gravada al 8%
    total_neto          DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    iva_16_monto        DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    iva_8_monto         DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    iva_total           DOUBLE PRECISION NOT NULL DEFAULT 0.0, -- iva_16 + iva_8
    exento_monto        DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    peso_total          DOUBLE PRECISION NOT NULL DEFAULT 0.0
);

-- ── Tabla: pedido_detalle ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pedido_detalle (
    id                   SERIAL PRIMARY KEY,
    pedido_id            INTEGER          NOT NULL REFERENCES pedidos(id),
    producto_id          VARCHAR,
    descripcion          VARCHAR,                              -- descripción del producto
    cantidad             DOUBLE PRECISION NOT NULL DEFAULT 1.0, -- soporta cantidades decimales
    precio_unitario      DOUBLE PRECISION NOT NULL DEFAULT 0.0, -- precio con IVA, sin descuento
    precio_sin_iva       DOUBLE PRECISION NOT NULL DEFAULT 0.0, -- precio base sin IVA, sin descuento
    precio_sin_descuento DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    precio_con_descuento DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    precio_venta         DOUBLE PRECISION NOT NULL DEFAULT 0.0, -- precio con descuento e IVA
    descuento            DOUBLE PRECISION NOT NULL DEFAULT 0.0, -- porcentaje de descuento
    porcent_descuento    DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    impuesto             DOUBLE PRECISION NOT NULL DEFAULT 0.0, -- tasa de impuesto (0, 8 ó 16)
    monto_iva            DOUBLE PRECISION NOT NULL DEFAULT 0.0, -- monto de IVA de esta línea
    total                DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    total_sin_dcto       DOUBLE PRECISION NOT NULL DEFAULT 0.0, -- cantidad * precio_sin_iva
    peso_item            DOUBLE PRECISION NOT NULL DEFAULT 0.0  -- cantidad * peso del producto
);

CREATE INDEX IF NOT EXISTS ix_pedido_detalle_pedido_id ON pedido_detalle (pedido_id);
