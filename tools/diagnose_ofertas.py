#!/usr/bin/env python3
"""
Script para verificar e aplicar a migração usando Python puro
"""

import os
import sys


def check_database_url():
    """Verifica se DATABASE_URL está definida."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("\n" + "="*70)
        print("ERRO: DATABASE_URL não está definida!")
        print("="*70)
        print("\nVocê precisa definir a variável de ambiente DATABASE_URL.")
        print("\nOpções:")
        print("\n1. Para definir temporariamente (válido apenas nesta sessão):")
        print("   export DATABASE_URL='postgresql://user:pass@host:port/dbname'")
        print("\n2. Para definir permanentemente, adicione ao seu ~/.bashrc ou ~/.bash_profile:")
        print("   echo 'export DATABASE_URL=\"postgresql://...\"' >> ~/.bashrc")
        print("   source ~/.bashrc")
        print("\n3. Ou crie um arquivo .env na raiz do projeto:")
        print("   DATABASE_URL=postgresql://user:pass@host:port/dbname")
        print("="*70)
        return None
    return db_url


def run_sql_query(db_url, query):
    """Executa uma query SQL e retorna os resultados."""
    try:
        from sqlalchemy import create_engine, text

        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)

        engine = create_engine(db_url, connect_args={"sslmode": "require"})

        with engine.connect() as conn:
            result = conn.execute(text(query))
            return result.fetchall()
    except Exception as e:
        print(f"Erro ao executar query: {e}")
        return None


def check_table_columns(db_url):
    """Verifica quais colunas existem na tabela ofertas."""
    print("\n" + "="*70)
    print("VERIFICANDO ESTRUTURA DA TABELA 'ofertas'")
    print("="*70)

    query = """
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'ofertas' 
    ORDER BY ordinal_position;
    """

    results = run_sql_query(db_url, query)

    if results is None:
        print("❌ Erro ao verificar estrutura da tabela")
        return None

    if not results:
        print("❌ Tabela 'ofertas' não encontrada!")
        return None

    columns = {}
    print("\nColunas encontradas:")
    for row in results:
        col_name, col_type = row
        columns[col_name] = col_type
        print(f"  ✓ {col_name} ({col_type})")

    return columns


def apply_migration(db_url, migration_file):
    """Aplica o arquivo de migração SQL."""
    print("\n" + "="*70)
    print(f"APLICANDO MIGRAÇÃO: {migration_file}")
    print("="*70)

    if not os.path.exists(migration_file):
        print(f"❌ Arquivo não encontrado: {migration_file}")
        return False

    try:
        with open(migration_file, 'r', encoding='utf-8') as f:
            migration_sql = f.read()

        from sqlalchemy import create_engine, text

        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)

        engine = create_engine(db_url, connect_args={"sslmode": "require"})

        print("\nExecutando migração...")
        with engine.begin() as conn:
            conn.execute(text(migration_sql))

        print("✓ Migração executada com sucesso!")
        return True

    except Exception as e:
        print(f"❌ Erro ao aplicar migração: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("\n" + "="*70)
    print("DIAGNÓSTICO E CORREÇÃO DA TABELA 'ofertas'")
    print("="*70)

    # 1. Verifica DATABASE_URL
    db_url = check_database_url()
    if not db_url:
        sys.exit(1)

    print(f"\n✓ DATABASE_URL encontrada")

    # 2. Verifica estrutura da tabela
    columns = check_table_columns(db_url)
    if columns is None:
        sys.exit(1)

    # 3. Analisa se precisa migração
    print("\n" + "="*70)
    print("ANÁLISE")
    print("="*70)

    has_codigo_interno = 'codigo_interno' in columns
    has_descricao = 'descricao' in columns
    has_codigo = 'codigo' in columns
    has_produto = 'produto' in columns

    if has_codigo_interno and has_descricao:
        print("\n✓ Tabela já possui as colunas corretas:")
        print("  - codigo_interno ✓")
        print("  - descricao ✓")
        print("\n✓ NENHUMA MIGRAÇÃO NECESSÁRIA!")
        print("\nSe você ainda está tendo erros, verifique:")
        print("1. Se a aplicação está usando a DATABASE_URL correta")
        print("2. Se há múltiplas instâncias do banco de dados")
        print("3. Se o cache da aplicação precisa ser limpo")
        return

    if has_codigo or has_produto:
        print("\n⚠ Tabela possui colunas antigas que precisam ser renomeadas:")
        if has_codigo:
            print(
                f"  - 'codigo' ({columns['codigo']}) → deve ser 'codigo_interno'")
        if has_produto:
            print(
                f"  - 'produto' ({columns['produto']}) → deve ser 'descricao'")

        print("\n" + "="*70)
        print("APLICANDO CORREÇÃO")
        print("="*70)

        migration_file = os.path.join(
            os.path.dirname(__file__),
            'migrations',
            '002_direct_rename.sql'
        )

        if apply_migration(db_url, migration_file):
            # Verifica novamente
            print("\n" + "="*70)
            print("VERIFICAÇÃO PÓS-MIGRAÇÃO")
            print("="*70)

            new_columns = check_table_columns(db_url)

            if new_columns and 'codigo_interno' in new_columns and 'descricao' in new_columns:
                print("\n" + "="*70)
                print("✓✓✓ MIGRAÇÃO CONCLUÍDA COM SUCESSO! ✓✓✓")
                print("="*70)
                print("\nA tabela 'ofertas' agora possui as colunas corretas.")
                print("A aplicação deve funcionar normalmente.")
            else:
                print("\n⚠ A migração foi executada mas algo não está correto.")
                print("Verifique manualmente a estrutura da tabela.")
        else:
            print("\n❌ Falha ao aplicar migração.")
            sys.exit(1)
    else:
        print("\n❌ Estrutura da tabela está em estado inconsistente!")
        print("Colunas esperadas não encontradas.")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Operação cancelada pelo usuário.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erro inesperado: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
