-- Rollback for 002_direct_rename.sql - renames back to original names
-- IMPORTANT: this assumes original names were 'codigo_interno', 'produto', 'ean', 'codigo' etc.

BEGIN;

DO $$
BEGIN
	IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='mix_produtos' AND column_name='cod_interno') AND
	   NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='mix_produtos' AND column_name='codigo_interno') THEN
		EXECUTE 'ALTER TABLE mix_produtos RENAME COLUMN cod_interno TO codigo_interno';
	END IF;
	IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='mix_produtos' AND column_name='descricao') AND
	   NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='mix_produtos' AND column_name='produto') THEN
		EXECUTE 'ALTER TABLE mix_produtos RENAME COLUMN descricao TO produto';
	END IF;
	IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='mix_produtos' AND column_name='codigo_ean') AND
	   NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='mix_produtos' AND column_name='ean') THEN
		EXECUTE 'ALTER TABLE mix_produtos RENAME COLUMN codigo_ean TO ean';
	END IF;
END$$;

DO $$
BEGIN
	IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='ofertas' AND column_name='cod_interno') AND
	   NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='ofertas' AND column_name='codigo') THEN
		EXECUTE 'ALTER TABLE ofertas RENAME COLUMN cod_interno TO codigo';
	END IF;
	IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='ofertas' AND column_name='descricao') AND
	   NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='ofertas' AND column_name='produto') THEN
		EXECUTE 'ALTER TABLE ofertas RENAME COLUMN descricao TO produto';
	END IF;
END$$;

DO $$
BEGIN
	IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='pedidos_consolidados' AND column_name='cod_interno') AND
	   NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='pedidos_consolidados' AND column_name='codigo') THEN
		EXECUTE 'ALTER TABLE pedidos_consolidados RENAME COLUMN cod_interno TO codigo';
	END IF;
	IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='pedidos_consolidados' AND column_name='descricao') AND
	   NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='pedidos_consolidados' AND column_name='produto') THEN
		EXECUTE 'ALTER TABLE pedidos_consolidados RENAME COLUMN descricao TO produto';
	END IF;
	IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='pedidos_consolidados' AND column_name='codigo_ean') AND
	   NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='pedidos_consolidados' AND column_name='ean') THEN
		EXECUTE 'ALTER TABLE pedidos_consolidados RENAME COLUMN codigo_ean TO ean';
	END IF;
END$$;

-- Recreate original constraints if necessary. Adjust constraint names as required.

COMMIT;
