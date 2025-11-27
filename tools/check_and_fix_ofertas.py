#!/usr/bin/env python3
"""
Script para verificar e corrigir a estrutura da tabela ofertas.
Este script:
1. Verifica quais colunas existem na tabela ofertas
2. Se necessário, executa a migração 002_direct_rename.sql
"""

import os
import sys
from sqlalchemy import create_engine, text, inspect


def get_engine():
    db_url = os.getenv("DATABASE_URL")

    if not db_url:
        print("ERRO: DATABASE_URL não está definida.", file=sys.stderr)
        sys.exit(1)

    # Substituição necessária para Postgres no Render
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    try:
        return create_engine(
            db_url,
            connect_args={"sslmode": "require"},
            pool_size=5,
            max_overflow=2
        )
    except Exception as e:
        print(f"ERRO ao criar engine: {e}", file=sys.stderr)
        sys.exit(1)


def check_table_structure(engine):
    """Verifica a estrutura atual da tabela ofertas."""
    print("\n=== Verificando estrutura da tabela 'ofertas' ===")

    inspector = inspect(engine)

    if 'ofertas' not in inspector.get_table_names():
        print("❌ Tabela 'ofertas' não existe!")
        return None

    columns = inspector.get_columns('ofertas')
    column_names = [col['name'] for col in columns]

    print(f"✓ Tabela 'ofertas' encontrada com {len(column_names)} colunas:")
    for col in columns:
        print(f"  - {col['name']} ({col['type']})")

    return column_names


def check_migration_needed(column_names):
    """Verifica se a migração é necessária."""
    print("\n=== Analisando necessidade de migração ===")

    # Verifica se já tem as colunas corretas
    has_codigo_interno = 'codigo_interno' in column_names
    has_descricao = 'descricao' in column_names

    # Verifica se tem as colunas antigas
    has_codigo = 'codigo' in column_names
    has_produto = 'produto' in column_names

    if has_codigo_interno and has_descricao:
        print("✓ Colunas 'codigo_interno' e 'descricao' já existem.")
        print("✓ Nenhuma migração necessária!")
        return False, "already_migrated"

    if has_codigo and has_produto:
        print("⚠ Colunas antigas encontradas: 'codigo' e 'produto'")
        print("✓ Migração 002_direct_rename.sql é necessária")
        return True, "need_rename"

    if has_codigo and not has_codigo_interno:
        print("⚠ Coluna 'codigo' existe mas 'codigo_interno' não")
        print("✓ Migração necessária (rename parcial)")
        return True, "need_rename"

    print("❌ Estrutura da tabela está em estado inconsistente!")
    print(f"   Colunas encontradas: {column_names}")
    return True, "inconsistent"


def run_migration(engine, migration_file):
    """Executa o arquivo de migração SQL."""
    print(f"\n=== Executando migração: {migration_file} ===")

    try:
        with open(migration_file, 'r') as f:
            migration_sql = f.read()

        with engine.begin() as conn:
            # Split por statement (usando BEGIN/COMMIT como delimitadores)
            # Vamos executar tudo de uma vez, pois o SQL já tem BEGIN/COMMIT
            conn.execute(text(migration_sql))

        print("✓ Migração executada com sucesso!")
        return True

    except Exception as e:
        print(f"❌ Erro ao executar migração: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False


def main():
    print("=" * 60)
    print("VERIFICAÇÃO E CORREÇÃO DA TABELA OFERTAS")
    print("=" * 60)

    # 1. Conecta ao banco
    engine = get_engine()
    print("✓ Conexão com o banco estabelecida")

    # 2. Verifica estrutura atual
    column_names = check_table_structure(engine)
    if column_names is None:
        print("\n❌ Não foi possível verificar a estrutura da tabela.")
        sys.exit(1)

    # 3. Verifica necessidade de migração
    need_migration, status = check_migration_needed(column_names)

    if not need_migration:
        print("\n" + "=" * 60)
        print("✓ TABELA JÁ ESTÁ CORRETA - NENHUMA AÇÃO NECESSÁRIA")
        print("=" * 60)
        return

    # 4. Pergunta se deve executar a migração
    print("\n" + "=" * 60)
    print("⚠ MIGRAÇÃO NECESSÁRIA")
    print("=" * 60)
    print("\nDeseja executar a migração 002_direct_rename.sql agora?")
    print("Esta operação irá renomear as colunas:")
    print("  - 'codigo' → 'codigo_interno'")
    print("  - 'produto' → 'descricao'")
    print("\n⚠ IMPORTANTE: Certifique-se de ter um backup do banco!")

    resposta = input("\nExecutar migração? (sim/nao): ").strip().lower()

    if resposta not in ['sim', 's', 'yes', 'y']:
        print("\n❌ Migração cancelada pelo usuário.")
        sys.exit(0)

    # 5. Executa a migração
    migration_file = os.path.join(os.path.dirname(
        __file__), 'migrations', '002_direct_rename.sql')

    if not os.path.exists(migration_file):
        print(f"\n❌ Arquivo de migração não encontrado: {migration_file}")
        sys.exit(1)

    if run_migration(engine, migration_file):
        # 6. Verifica novamente
        print("\n=== Verificando estrutura após migração ===")
        new_column_names = check_table_structure(engine)

        if new_column_names and 'codigo_interno' in new_column_names:
            print("\n" + "=" * 60)
            print("✓ MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
            print("=" * 60)
            print("\nAs colunas foram renomeadas corretamente.")
            print("A aplicação agora deve funcionar normalmente.")
        else:
            print("\n❌ Migração executada mas a estrutura ainda está incorreta!")
            sys.exit(1)
    else:
        print("\n❌ Falha ao executar a migração.")
        sys.exit(1)


if __name__ == "__main__":
    main()
