#!/usr/bin/env python3
"""
patch.py

Script idempotente para:
 - criar/atualizar tabelas auxiliares (mix, historico, wms, ofertas) a partir de .parquet
 - criar views: vw_pedidos_pendentes, vw_master_pedidos
 - criar índices recomendados
 - criar/refresh materialized view opcional vw_master_pedidos_mat

Uso:
  DATABASE_URL=postgresql://... BASE_DATA_PATH=/opt/render/project/src/data CREATE_MATERIALIZED_VIEW=true python patch.py
"""
import os
import sys
import time
import traceback
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# -----------------------
# Configurações
# -----------------------
DB_URL = os.environ.get("DATABASE_URL")
BASE_DATA_PATH = os.environ.get("RENDER_DISK_PATH", os.environ.get("BASE_DATA_PATH", "data"))
CREATE_MATVIEW = os.environ.get("CREATE_MATERIALIZED_VIEW", "false").lower() in ("1", "true", "yes")

# Parquet filenames (relative to BASE_DATA_PATH)
PARQUET_FILES = {
    "mix": "__MixAtivoSistema.parquet",
    "historico": "historico_solic.parquet",
    "wms": "WMS.parquet",
    # ofertas might be managed in DB already, but we allow a parquet import
    "ofertas": "ofertas.parquet",
}

# -----------------------
# Helpers
# -----------------------
def log(*args, **kwargs):
    print(*args, **kwargs)
    sys.stdout.flush()

def fail(msg, exc=None):
    log("ERROR:", msg)
    if exc:
        traceback.print_exception(type(exc), exc, exc.__traceback__)
    sys.exit(1)

def ensure_env():
    if not DB_URL:
        fail("A variável de ambiente DATABASE_URL não está definida. Abortando.")

def connect_engine():
    try:
        engine = create_engine(DB_URL)
        # quick test connect
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except Exception as e:
        fail("Falha ao conectar no banco de dados.", e)

def read_parquet_if_exists(path: Path):
    if not path.exists():
        log(f"Arquivo não encontrado: {path} — pulando.")
        return None
    try:
        log(f"Lendo parquet: {path}")
        df = pd.read_parquet(path)
        log(f"Linhas lidas: {len(df)}")
        return df
    except Exception as e:
        log(f"Falha ao ler parquet {path}: {e}")
        return None

def df_to_sql_replace(engine, df, table_name, dtype_map=None, chunksize=1000):
    """Escreve dataframe no Postgres substituindo a tabela (if_exists='replace')."""
    if df is None:
        log(f"No dataframe for {table_name}, skipping.")
        return False
    try:
        log(f"Escrevendo {table_name} ({len(df)} linhas) into DB...")
        df.to_sql(table_name, engine, if_exists="replace", index=False, method="multi", chunksize=chunksize)
        log(f"Tabela {table_name} atualizada com sucesso.")
        return True
    except Exception as e:
        log(f"Erro ao gravar tabela {table_name}: {e}")
        return False

# -----------------------
# SQL DDL for helper tables (if not present)
# We create lightweight schemas with flexible columns that match typical parquet files.
# -----------------------
DDL_CREATE_TABLES = {
    "mix": """
CREATE TABLE IF NOT EXISTS mix (
    codigoint TEXT,
    descricao TEXT,
    embseparacao NUMERIC,
    loja TEXT
);
""",
    "historico": """
CREATE TABLE IF NOT EXISTS historico (
    CODIGOINT TEXT,
    LOJA TEXT,
    DtSolicitacao TIMESTAMP,
    "EstCX" NUMERIC,
    "PedCX" NUMERIC,
    "Vd1sem-CX" NUMERIC,
    "Vd2sem-CX" NUMERIC,
    "VM30dCX" NUMERIC
);
""",
    "wms": """
CREATE TABLE IF NOT EXISTS wms (
    codigo TEXT,
    Qtd NUMERIC,
    datasalva TIMESTAMP,
    endereco TEXT
);
""",
    # ofertas: try-create only if doesn't exist
    "ofertas": """
CREATE TABLE IF NOT EXISTS ofertas (
    id SERIAL PRIMARY KEY,
    codigo INTEGER,
    produto TEXT,
    oferta NUMERIC,
    data_inicio DATE,
    data_final DATE
);
"""
}

# -----------------------
# Views SQL (Postgres 17)
# -----------------------
SQL_VW_PENDENTES = """
CREATE OR REPLACE VIEW vw_pedidos_pendentes AS
SELECT
    pc.id,
    pc.codigo,
    pc.produto,
    pc.ean,
    pc.embseparacao,
    pc.data_pedido,
    pc.data_aprovacao,
    pc.usuario_pedido,
    pc.status_item,
    pc.status_aprovacao,
    pc.loja_001,
    pc.loja_002,
    pc.loja_003,
    pc.loja_004,
    pc.loja_005,
    pc.loja_006,
    pc.loja_007,
    pc.loja_008,
    pc.loja_011,
    pc.loja_012,
    pc.loja_013,
    pc.loja_014,
    pc.loja_017,
    pc.loja_018,
    pc.total_cx,
    ( COALESCE(pc.loja_001,0)
    + COALESCE(pc.loja_002,0)
    + COALESCE(pc.loja_003,0)
    + COALESCE(pc.loja_004,0)
    + COALESCE(pc.loja_005,0)
    + COALESCE(pc.loja_006,0)
    + COALESCE(pc.loja_007,0)
    + COALESCE(pc.loja_008,0)
    + COALESCE(pc.loja_011,0)
    + COALESCE(pc.loja_012,0)
    + COALESCE(pc.loja_013,0)
    + COALESCE(pc.loja_014,0)
    + COALESCE(pc.loja_017,0)
    + COALESCE(pc.loja_018,0)
    ) AS soma_lojas
FROM pedidos_consolidados pc
WHERE pc.status_aprovacao = 'Pendente'
ORDER BY pc.data_pedido ASC;
"""

SQL_VW_MASTER = """
CREATE OR REPLACE VIEW vw_master_pedidos AS
WITH ult_wms AS (
    SELECT 
        codigo::bigint AS codigo_num,
        SUM(COALESCE(qtd,0)) AS qtd_cd,
        MAX(datasalva) AS data_wms
    FROM wms
    GROUP BY codigo::bigint
),
ult_hist AS (
    SELECT DISTINCT ON (CAST(CODIGOINT AS bigint), LOJA)
        CAST(CODIGOINT AS bigint) AS codigo_num,
        LOJA,
        "EstCX" AS estoque_g,
        "PedCX" AS pedido_h,
        "Vd1sem-CX" AS venda_i,
        "Vd2sem-CX" AS venda_j,
        "VM30dCX" AS vm30
    FROM historico
    ORDER BY CAST(CODIGOINT AS bigint), LOJA, DtSolicitacao DESC
),
mix_clean AS (
    SELECT
        CASE WHEN codigoint ~ '^[0-9]+$' THEN CAST(codigoint AS bigint) ELSE NULL END AS codigo_num,
        descricao AS produto_mix,
        embseparacao::integer AS emb_mix
    FROM mix
),
oferta_atual AS (
    SELECT DISTINCT ON (codigo)
        codigo,
        oferta,
        data_inicio,
        data_final
    FROM ofertas
    WHERE data_final >= CURRENT_DATE
    ORDER BY codigo, data_inicio DESC
)

SELECT
    pc.*,
    m.produto_mix,
    m.emb_mix,
    w.qtd_cd,
    w.data_wms,
    h.estoque_g,
    h.pedido_h,
    h.venda_i,
    h.venda_j,
    h.vm30,
    o.oferta AS preco_oferta,
    o.data_inicio AS oferta_inicio,
    o.data_final AS oferta_final,
    ( COALESCE(pc.loja_001,0)
    + COALESCE(pc.loja_002,0)
    + COALESCE(pc.loja_003,0)
    + COALESCE(pc.loja_004,0)
    + COALESCE(pc.loja_005,0)
    + COALESCE(pc.loja_006,0)
    + COALESCE(pc.loja_007,0)
    + COALESCE(pc.loja_008,0)
    + COALESCE(pc.loja_011,0)
    + COALESCE(pc.loja_012,0)
    + COALESCE(pc.loja_013,0)
    + COALESCE(pc.loja_014,0)
    + COALESCE(pc.loja_017,0)
    + COALESCE(pc.loja_018,0)
    ) AS soma_lojas
FROM pedidos_consolidados pc
LEFT JOIN mix_clean m ON m.codigo_num = CAST(pc.codigo AS bigint)
LEFT JOIN ult_wms w ON w.codigo_num = CAST(pc.codigo AS bigint)
LEFT JOIN ult_hist h ON h.codigo_num = CAST(pc.codigo AS bigint)
LEFT JOIN oferta_atual o ON o.codigo = CAST(pc.codigo AS INTEGER)
ORDER BY pc.data_pedido DESC;
"""

SQL_MATVIEW = """
CREATE MATERIALIZED VIEW IF NOT EXISTS vw_master_pedidos_mat AS
SELECT * FROM vw_master_pedidos;
"""

# Indexes to speed common queries
INDEXES = [
    ("idx_pedidos_status_aprovacao", "CREATE INDEX IF NOT EXISTS idx_pedidos_status_aprovacao ON pedidos_consolidados(status_aprovacao)"),
    ("idx_pedidos_data_pedido", "CREATE INDEX IF NOT EXISTS idx_pedidos_data_pedido ON pedidos_consolidados(data_pedido)"),
    ("idx_mix_codigoint", "CREATE INDEX IF NOT EXISTS idx_mix_codigoint ON mix(codigoint)"),
    ("idx_wms_codigo", "CREATE INDEX IF NOT EXISTS idx_wms_codigo ON wms(codigo)"),
    ("idx_historico_codigo", "CREATE INDEX IF NOT EXISTS idx_historico_codigo ON historico(CODIGOINT)")
]

# -----------------------
# Main flow
# -----------------------
def main():
    ensure_env()
    engine = connect_engine()
    base = Path(BASE_DATA_PATH)
    log(f"BASE_DATA_PATH = {base.resolve()}")
    # 1. Create helper tables if not exists (lightweight)
    with engine.begin() as conn:
        for name, ddl in DDL_CREATE_TABLES.items():
            log(f"Creating table if not exists: {name}")
            conn.execute(text(ddl))

    # 2. Load parquet files into tables (replace)
    for tbl, fname in PARQUET_FILES.items():
        path = Path(base) / fname
        df = read_parquet_if_exists(path)
        if df is None:
            continue

        # quick fix: lower-case column names for safety
        df.columns = [c if isinstance(c, str) else c for c in df.columns]
        # For "mix", try to map columns to expected names
        if tbl == "mix":
            # keep original names (we created mix with codigoint, descricao, embseparacao, loja)
            # ensure column names exist
            rename_map = {}
            cols_lower = {c.lower(): c for c in df.columns}
            if "codigoint" in cols_lower:
                rename_map[cols_lower["codigoint"]] = "codigoint"
            elif "codigo" in cols_lower:
                rename_map[cols_lower["codigo"]] = "codigoint"
            if "descricao" in cols_lower:
                rename_map[cols_lower["descricao"]] = "descricao"
            elif "produto" in cols_lower:
                rename_map[cols_lower["produto"]] = "descricao"
            if "embseparacao" in cols_lower:
                rename_map[cols_lower["embseparacao"]] = "embseparacao"
            elif "embalagem" in cols_lower:
                rename_map[cols_lower["embalagem"]] = "embseparacao"
            if "loja" in cols_lower:
                rename_map[cols_lower["loja"]] = "loja"
            if rename_map:
                df = df.rename(columns=rename_map)
        elif tbl == "wms":
            # standardize common columns
            rename_map = {}
            cols_lower = {c.lower(): c for c in df.columns}
            if "codigo" in cols_lower:
                rename_map[cols_lower["codigo"]] = "codigo"
            if "qtd" in cols_lower:
                rename_map[cols_lower["qtd"]] = "qtd"
            if "datasalva" in cols_lower:
                rename_map[cols_lower["datasalva"]] = "datasalva"
            if "endereco" in cols_lower:
                rename_map[cols_lower["endereco"]] = "endereco"
            if rename_map:
                df = df.rename(columns=rename_map)
        elif tbl == "historico":
            # keep as-is but ensure typical names exist; no heavy mapping attempted
            pass
        elif tbl == "ofertas":
            # expected: codigo, produto, oferta, data_inicio, data_final
            rename_map = {}
            cols_lower = {c.lower(): c for c in df.columns}
            if "codigo" in cols_lower:
                rename_map[cols_lower["codigo"]] = "codigo"
            if "produto" in cols_lower:
                rename_map[cols_lower["produto"]] = "produto"
            if "oferta" in cols_lower:
                rename_map[cols_lower["oferta"]] = "oferta"
            if "data_inicio" in cols_lower or "data_inicio" in cols_lower:
                # leave as-is if present
                pass
            if rename_map:
                df = df.rename(columns=rename_map)

        # write to DB (replace)
        ok = df_to_sql_replace(engine, df, tbl)
        if not ok:
            log(f"Falha ao atualizar a tabela {tbl} — continue para as views (tabela pode não existir).")

    # 3. Create views
    with engine.begin() as conn:
        log("Criando view vw_pedidos_pendentes ...")
        conn.execute(text(SQL_VW_PENDENTES))
        log("vw_pedidos_pendentes criada/atualizada.")

        log("Criando view vw_master_pedidos ...")
        conn.execute(text(SQL_VW_MASTER))
        log("vw_master_pedidos criada/atualizada.")

        # create indexes
        for name, stmt in INDEXES:
            try:
                log(f"Criando index: {name}")
                conn.execute(text(stmt))
            except Exception as e:
                log(f"Falha ao criar index {name}: {e}")

        # materialized view optional
        if CREATE_MATVIEW:
            try:
                log("Criando/atualizando materialized view vw_master_pedidos_mat ...")
                conn.execute(text(SQL_MATVIEW))
                # refresh to ensure it's populated
                conn.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY vw_master_pedidos_mat;"))
                log("Materialized view criada e atualizada.")
            except SQLAlchemyError as e:
                log("Erro ao criar/atualizar materialized view (pode ser por privilégios ou versão). Tentando REFRESH sem CONCURRENTLY ...")
                try:
                    conn.execute(text("REFRESH MATERIALIZED VIEW vw_master_pedidos_mat;"))
                    log("Materialized view atualizada.")
                except Exception as e2:
                    log(f"Falha ao atualizar materialized view: {e2}")

    log("Tudo concluído com sucesso.")

if __name__ == "__main__":
    main()
