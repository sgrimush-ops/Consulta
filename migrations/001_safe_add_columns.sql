-- Safe migration: add new standardized columns and copy data from old columns
-- Usage: run in a transaction on a test/staging DB first, then on production

BEGIN;

-- 1) mix_produtos: add cod_interno, nome_produto, codigo_ean as TEXT (if not exists)
ALTER TABLE IF EXISTS mix_produtos
    ADD COLUMN IF NOT EXISTS cod_interno TEXT,
    ADD COLUMN IF NOT EXISTS nome_produto TEXT,
    ADD COLUMN IF NOT EXISTS codigo_ean TEXT;

-- Copy values from older columns if present
DO $$
BEGIN
    -- cod_interno <- codigo_interno
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='mix_produtos' AND column_name='codigo_interno') THEN
        UPDATE mix_produtos SET cod_interno = CAST(codigo_interno AS TEXT) WHERE cod_interno IS NULL OR cod_interno = '';
    END IF;

    -- nome_produto <- produto
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='mix_produtos' AND column_name='produto') THEN
        UPDATE mix_produtos SET nome_produto = produto WHERE nome_produto IS NULL OR nome_produto = '';
    END IF;

    -- codigo_ean <- ean
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='mix_produtos' AND column_name='ean') THEN
        UPDATE mix_produtos SET codigo_ean = CAST(ean AS TEXT) WHERE codigo_ean IS NULL OR codigo_ean = '';
    END IF;
END$$;

-- 2) ofertas: add cod_interno, nome_produto as TEXT
ALTER TABLE IF EXISTS ofertas
    ADD COLUMN IF NOT EXISTS cod_interno TEXT,
    ADD COLUMN IF NOT EXISTS nome_produto TEXT;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='ofertas' AND column_name='codigo') THEN
        UPDATE ofertas SET cod_interno = CAST(codigo AS TEXT) WHERE cod_interno IS NULL OR cod_interno = '';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='ofertas' AND column_name='produto') THEN
        UPDATE ofertas SET nome_produto = produto WHERE nome_produto IS NULL OR nome_produto = '';
    END IF;
END$$;

-- Ensure there's a unique constraint/index on (cod_interno, data_inicio, data_final) for offers
-- Ensure there's a unique constraint/index on (cod_interno, data_inicio, data_final) for offers
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes WHERE tablename='ofertas' AND indexname='uniq_ofertas_cod_period'
    ) THEN
        -- Creating an index concurrently is not allowed inside a transaction block, so create normally here.
        -- If you need to avoid exclusive locks on large tables, run the following command OUTSIDE a transaction:
        -- CREATE UNIQUE INDEX CONCURRENTLY uniq_ofertas_cod_period ON ofertas (cod_interno, data_inicio, data_final);
        EXECUTE 'CREATE UNIQUE INDEX uniq_ofertas_cod_period ON ofertas (cod_interno, data_inicio, data_final)';
    END IF;
END$$;

-- 3) pedidos_consolidados: add cod_interno, nome_produto, codigo_ean
ALTER TABLE IF EXISTS pedidos_consolidados
    ADD COLUMN IF NOT EXISTS cod_interno TEXT,
    ADD COLUMN IF NOT EXISTS nome_produto TEXT,
    ADD COLUMN IF NOT EXISTS codigo_ean TEXT;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='pedidos_consolidados' AND column_name='codigo') THEN
        UPDATE pedidos_consolidados SET cod_interno = CAST(codigo AS TEXT) WHERE cod_interno IS NULL OR cod_interno = '';
    ELSIF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='pedidos_consolidados' AND column_name='codigo_interno') THEN
        UPDATE pedidos_consolidados SET cod_interno = CAST(codigo_interno AS TEXT) WHERE cod_interno IS NULL OR cod_interno = '';
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='pedidos_consolidados' AND column_name='produto') THEN
        UPDATE pedidos_consolidados SET nome_produto = produto WHERE nome_produto IS NULL OR nome_produto = '';
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='pedidos_consolidados' AND column_name='ean') THEN
        UPDATE pedidos_consolidados SET codigo_ean = CAST(ean AS TEXT) WHERE codigo_ean IS NULL OR codigo_ean = '';
    END IF;
END$$;

COMMIT;

-- Notes:
-- * Run this first on a staging/test DB.
-- * After running, validate that application code can read the new columns (cod_interno, nome_produto, codigo_ean).
-- * When validation is complete, you can create application-level migrations that start writing to the new columns.
