-- Rollback for 001_safe_add_columns.sql
-- This script drops the columns added by the safe migration and removes created indexes

BEGIN;

-- Drop indexes created for offers
DROP INDEX IF EXISTS uniq_ofertas_cod_period;

-- Drop columns from mix_produtos
ALTER TABLE IF EXISTS mix_produtos
    DROP COLUMN IF EXISTS cod_interno,
    DROP COLUMN IF EXISTS nome_produto,
    DROP COLUMN IF EXISTS codigo_ean;

-- Drop columns from ofertas
ALTER TABLE IF EXISTS ofertas
    DROP COLUMN IF EXISTS cod_interno,
    DROP COLUMN IF EXISTS nome_produto;

-- Drop columns from pedidos_consolidados
ALTER TABLE IF EXISTS pedidos_consolidados
    DROP COLUMN IF EXISTS cod_interno,
    DROP COLUMN IF EXISTS nome_produto,
    DROP COLUMN IF EXISTS codigo_ean;

COMMIT;

-- IMPORTANT: Use this only if you are certain you want to remove the newly added columns.
