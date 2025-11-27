-- Direct rename migration (higher risk) - Renames existing columns to new standardized names
-- WARNING: This alters schema in-place; run on a maintenance window and ensure full backup.

BEGIN;

-- mix_produtos: only rename if old column exists and new does not
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='mix_produtos' AND column_name='codigo') AND
       NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='mix_produtos' AND column_name='codigo_interno') THEN
        EXECUTE 'ALTER TABLE mix_produtos RENAME COLUMN codigo TO codigo_interno';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='mix_produtos' AND column_name='produto') AND
       NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='mix_produtos' AND column_name='descricao') THEN
        EXECUTE 'ALTER TABLE mix_produtos RENAME COLUMN produto TO descricao';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='mix_produtos' AND column_name='ean') AND
       NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='mix_produtos' AND column_name='codigo_ean') THEN
        EXECUTE 'ALTER TABLE mix_produtos RENAME COLUMN ean TO codigo_ean';
    END IF;
END$$;

-- ofertas
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='ofertas' AND column_name='codigo') AND
       NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='ofertas' AND column_name='codigo_interno') THEN
        EXECUTE 'ALTER TABLE ofertas RENAME COLUMN codigo TO codigo_interno';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='ofertas' AND column_name='produto') AND
       NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='ofertas' AND column_name='descricao') THEN
        EXECUTE 'ALTER TABLE ofertas RENAME COLUMN produto TO descricao';
    END IF;
END$$;

-- pedidos_consolidados
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='pedidos_consolidados' AND column_name='codigo') AND
       NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='pedidos_consolidados' AND column_name='codigo_interno') THEN
        EXECUTE 'ALTER TABLE pedidos_consolidados RENAME COLUMN codigo TO codigo_interno';
    END IF;

    -- Remove the conditional rename; application expects `codigo_interno`

    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='pedidos_consolidados' AND column_name='produto') AND
       NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='pedidos_consolidados' AND column_name='descricao') THEN
        EXECUTE 'ALTER TABLE pedidos_consolidados RENAME COLUMN produto TO descricao';
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='pedidos_consolidados' AND column_name='ean') AND
       NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='pedidos_consolidados' AND column_name='codigo_ean') THEN
        EXECUTE 'ALTER TABLE pedidos_consolidados RENAME COLUMN ean TO codigo_ean';
    END IF;
END$$;

-- (If there is a constraint UNIQUE(codigo, data_inicio, data_final) we must drop and recreate using codigo_interno.)
DO $$
BEGIN
    -- Example: drop old unique constraint if exists and add the new one
    IF EXISTS (SELECT 1 FROM information_schema.table_constraints tc WHERE tc.table_name='ofertas' AND tc.constraint_type='UNIQUE') THEN
        -- This tries to find any unique constraint on the same set and recreates, but be cautious!
        ALTER TABLE ofertas DROP CONSTRAINT IF EXISTS ofertas_codigo_data_period;
        ALTER TABLE ofertas ADD CONSTRAINT ofertas_cod_period UNIQUE (codigo_interno, data_inicio, data_final);
    END IF;
END$$;

COMMIT;

-- After running this script, update any DB-level constraints, indexes, or external integrations that referenced the old column names.
