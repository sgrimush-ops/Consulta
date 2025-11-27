import streamlit as st
from sqlalchemy import text, create_engine
import os

# Pega a engine (assumindo a mesma lógica do seu projeto)
def get_engine():
    db_url = os.getenv("DATABASE_URL")
    if db_url and db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    return create_engine(db_url, connect_args={"sslmode": "require"})

def run_patch():
    engine = get_engine()
    st.info("Iniciando Patch de migração de colunas...")
    
    with engine.begin() as conn:
        # 1. Ajustar tabela 'ofertas'
        try:
            conn.execute(text("ALTER TABLE ofertas RENAME COLUMN codigo TO codigo_interno;"))
            st.success("Tabela 'ofertas': Coluna renomeada para 'codigo_interno'.")
        except Exception as e:
            st.warning(f"Tabela 'ofertas': {e}")

        # 2. Ajustar tabela 'pedidos_consolidados'
        try:
            conn.execute(text("ALTER TABLE pedidos_consolidados RENAME COLUMN codigo TO codigo_interno;"))
            st.success("Tabela 'pedidos_consolidados': Coluna renomeada para 'codigo_interno'.")
        except Exception as e:
            st.warning(f"Tabela 'pedidos_consolidados': {e}")
            
        # 3. Ajustar tabela 'historico_solicitacoes' (se existir)
        try:
            conn.execute(text("ALTER TABLE historico_solicitacoes RENAME COLUMN codigo TO codigo_interno;"))
            st.success("Tabela 'historico_solicitacoes': Coluna renomeada para 'codigo_interno'.")
        except Exception as e:
            pass # Tabela pode não existir

if __name__ == "__main__":
    run_patch()