import os
import sys
from sqlalchemy import create_engine, text

# Configuração
DB_URL = os.environ.get("DATABASE_URL")

# Lista exata de lojas usada no seu pedidos.py
LISTA_LOJAS = ["001", "002", "003", "004", "005", "006",
               "007", "008", "011", "012", "013", "014", "017", "018"]

def log(msg):
    print(f"[SETUP] {msg}")

def main():
    if not DB_URL:
        log("❌ Erro: DATABASE_URL não encontrada.")
        return

    engine = create_engine(DB_URL)
    
    log("Verificando estrutura da tabela 'pedidos_consolidados'...")

    # 1. Definição das colunas dinâmicas das lojas
    cols_lojas_sql = ",\n    ".join([f"loja_{loja} INTEGER DEFAULT 0" for loja in LISTA_LOJAS])

    # 2. SQL de Criação da Tabela (se não existir)
    ddl_create_table = f"""
    CREATE TABLE IF NOT EXISTS pedidos_consolidados (
        id SERIAL PRIMARY KEY,
        codigo TEXT,
        produto TEXT,
        ean TEXT,
        embseparacao INTEGER,
        data_pedido TIMESTAMP,
        data_aprovacao TIMESTAMP,
        usuario_pedido TEXT,
        status_item TEXT,
        status_aprovacao TEXT,
        total_cx INTEGER,
        {cols_lojas_sql}
    );
    """

    with engine.begin() as conn:
        # Criar tabela
        conn.execute(text(ddl_create_table))
        log("✅ Tabela 'pedidos_consolidados' garantida.")

        # 3. Verificar colunas ausentes (Migração simples)
        # Caso você adicione lojas no futuro, isso evita que o app quebre
        for loja in LISTA_LOJAS:
            col_name = f"loja_{loja}"
            check_col = text(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='pedidos_consolidados' AND column_name='{col_name}';
            """)
            res = conn.execute(check_col).fetchone()
            
            if not res:
                log(f"⚠️ Coluna {col_name} faltando. Adicionando...")
                conn.execute(text(f"ALTER TABLE pedidos_consolidados ADD COLUMN {col_name} INTEGER DEFAULT 0;"))
    
    log("🎉 Estrutura de Pedidos corrigida com sucesso!")

if __name__ == "__main__":
    main()
