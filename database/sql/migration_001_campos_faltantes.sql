-- =============================================================================
-- migration_001_campos_faltantes.sql
--
-- Agrega a una BD existente los campos de fidelidad completa que faltaban en
-- pedidos y pedido_detalle. Idempotente y no destructivo (ADD COLUMN IF NOT
-- EXISTS). Aplicar UNA vez sobre una BD que ya tenga las tablas creadas por
-- create_all().
--
-- Uso:
--   psql "<connection-string>" -f database/sql/migration_001_campos_faltantes.sql
--
-- Refleja models/pedidos.py. Mantener en sincronía con schema.sql.
-- =============================================================================

-- ── pedidos ──────────────────────────────────────────────────────────────────
ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS descripcion_cliente VARCHAR;
ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS direccion_cliente   VARCHAR;
ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS nombre_vendedor     VARCHAR;
ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS tipo_precio         VARCHAR;
ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS comentario          VARCHAR;
ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS base_16_monto       DOUBLE PRECISION NOT NULL DEFAULT 0.0;
ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS iva_total           DOUBLE PRECISION NOT NULL DEFAULT 0.0;
ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS peso_total          DOUBLE PRECISION NOT NULL DEFAULT 0.0;

-- ── pedido_detalle ───────────────────────────────────────────────────────────
ALTER TABLE pedido_detalle ADD COLUMN IF NOT EXISTS descripcion    VARCHAR;
ALTER TABLE pedido_detalle ADD COLUMN IF NOT EXISTS precio_sin_iva DOUBLE PRECISION NOT NULL DEFAULT 0.0;
ALTER TABLE pedido_detalle ADD COLUMN IF NOT EXISTS precio_venta   DOUBLE PRECISION NOT NULL DEFAULT 0.0;
ALTER TABLE pedido_detalle ADD COLUMN IF NOT EXISTS total_sin_dcto DOUBLE PRECISION NOT NULL DEFAULT 0.0;
ALTER TABLE pedido_detalle ADD COLUMN IF NOT EXISTS peso_item      DOUBLE PRECISION NOT NULL DEFAULT 0.0;
