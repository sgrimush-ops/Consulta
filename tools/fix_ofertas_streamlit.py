"""
Script para ser executado DENTRO da aplicação Streamlit.
Este script usa a engine já existente da aplicação.

Como usar:
1. Adicione este código temporariamente no início de qualquer página
2. Execute a aplicação
3. O script verificará e corrigirá automaticamente
4. Remova o código após a correção
"""

import streamlit as st
from sqlalchemy import text, inspect


def fix_ofertas_table(engine):
    """Verifica e corrige a tabela ofertas."""

    st.write("### 🔧 Verificação da Tabela Ofertas")

    # Verifica estrutura atual
    inspector = inspect(engine)

    if 'ofertas' not in inspector.get_table_names():
        st.error("❌ Tabela 'ofertas' não existe!")
        return False

    columns = [col['name'] for col in inspector.get_columns('ofertas')]

    st.write("**Colunas atuais:**")
    for col in columns:
        st.write(f"  - {col}")

    # Verifica se precisa migração
    has_codigo_interno = 'codigo_interno' in columns
    has_descricao = 'descricao' in columns
    has_codigo = 'codigo' in columns
    has_produto = 'produto' in columns

    if has_codigo_interno and has_descricao:
        st.success("✅ Tabela já está correta!")
        return True

    if has_codigo or has_produto:
        st.warning("⚠️ Tabela precisa ser atualizada")

        if st.button("🔧 Aplicar Correção Agora", type="primary"):
            try:
                # Lê o arquivo de migração
                import os
                migration_file = os.path.join(
                    os.path.dirname(os.path.dirname(__file__)),
                    'migrations',
                    '002_direct_rename.sql'
                )

                with open(migration_file, 'r', encoding='utf-8') as f:
                    migration_sql = f.read()

                # Executa migração
                with st.spinner("Aplicando migração..."):
                    with engine.begin() as conn:
                        conn.execute(text(migration_sql))

                st.success("✅ Migração aplicada com sucesso!")
                st.info("🔄 Recarregue a página para usar a aplicação normalmente")

                # Verifica novamente
                new_columns = [
                    col['name']
                    for col in inspector.get_columns('ofertas')
                ]

                st.write("**Novas colunas:**")
                for col in new_columns:
                    st.write(f"  - ✓ {col}")

                return True

            except Exception as e:
                st.error(f"❌ Erro ao aplicar migração: {e}")
                st.exception(e)
                return False

    st.error("❌ Estrutura da tabela está em estado inconsistente")
    return False


# ==============================================================
# COMO USAR:
#
# 1. Adicione estas linhas NO INÍCIO de qualquer página
#    (ex: no início de upload_ofertas.py):
#
#    from tools.fix_ofertas_streamlit import fix_ofertas_table
#    from app import get_engine
#
#    engine = get_engine()
#    fix_ofertas_table(engine)
#    st.stop()  # Para aqui até corrigir
#
# 2. Execute a aplicação normalmente
# 3. Clique no botão "Aplicar Correção"
# 4. Após sucesso, REMOVA essas linhas
# 5. Recarregue a aplicação
# ==============================================================
