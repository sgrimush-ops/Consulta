#!/usr/bin/env python3
"""
Script para aplicar a migração 002_direct_rename.sql no banco de dados.
Este script tenta obter a DATABASE_URL de várias fontes.
"""

import os
import sys

# Adiciona o diretório pai ao path para importar módulos do projeto
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def get_database_url():
    """Tenta obter DATABASE_URL de várias fontes."""

    # 1. Variável de ambiente
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        print("✓ DATABASE_URL encontrada na variável de ambiente")
        return db_url

    # 2. Arquivo .env
    env_file = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        '.env'
    )
    if os.path.exists(env_file):
        print(f"✓ Arquivo .env encontrado: {env_file}")
        try:
            with open(env_file, 'r') as f:
                for line in f:
                    if line.startswith('DATABASE_URL='):
                        db_url = line.strip().split('=', 1)[1]
                        # Remove aspas se existirem
                        db_url = db_url.strip('"').strip("'")
                        print("✓ DATABASE_URL extraída do .env")
                        return db_url
        except Exception as e:
            print(f"⚠ Erro ao ler .env: {e}")

    # 3. Secrets do Streamlit
    secrets_file = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        '.streamlit',
        'secrets.toml'
    )
    if os.path.exists(secrets_file):
        print(f"✓ Arquivo secrets.toml encontrado: {secrets_file}")
        try:
            with open(secrets_file, 'r') as f:
                for line in f:
                    if 'DATABASE_URL' in line:
                        parts = line.split('=', 1)
                        if len(parts) == 2:
                            db_url = parts[1].strip().strip('"').strip("'")
                            print("✓ DATABASE_URL extraída do secrets.toml")
                            return db_url
        except Exception as e:
            print(f"⚠ Erro ao ler secrets.toml: {e}")

    return None


def check_table_structure(engine):
    """Verifica a estrutura da tabela ofertas."""
    from sqlalchemy import inspect

    inspector = inspect(engine)

    if 'ofertas' not in inspector.get_table_names():
        print("❌ Tabela 'ofertas' não existe!")
        return None

    columns = inspector.get_columns('ofertas')
    column_names = [col['name'] for col in columns]

    print(f"\n✓ Tabela 'ofertas' encontrada com {len(column_names)} colunas:")
    for col in columns:
        print(f"  - {col['name']} ({col['type']})")

    return column_names


def apply_migration(engine):
    """Aplica a migração 002_direct_rename.sql."""
    from sqlalchemy import text

    migration_file = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'migrations',
        '002_direct_rename.sql'
    )

    if not os.path.exists(migration_file):
        print(f"❌ Arquivo de migração não encontrado: {migration_file}")
        return False

    print(f"\n📄 Lendo migração: {migration_file}")

    try:
        with open(migration_file, 'r', encoding='utf-8') as f:
            migration_sql = f.read()

        print("⚙️  Executando migração...")
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
    print("=" * 70)
    print("  CORREÇÃO DA TABELA OFERTAS")
    print("=" * 70)

    # 1. Obter DATABASE_URL
    print("\n1. Buscando DATABASE_URL...")
    db_url = get_database_url()

    if not db_url:
        print("\n❌ DATABASE_URL não encontrada!")
        print("\nOpções:")
        print("1. Defina a variável de ambiente:")
        print("   export DATABASE_URL='postgresql://user:pass@host:port/db'")
        print("\n2. Ou crie um arquivo .env na raiz do projeto:")
        print("   DATABASE_URL=postgresql://user:pass@host:port/db")
        print("\n3. Ou execute a aplicação Streamlit e copie a URL de lá")
        sys.exit(1)

    # Substitui postgres:// por postgresql://
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    # 2. Conectar ao banco
    print("\n2. Conectando ao banco de dados...")
    try:
        from sqlalchemy import create_engine

        engine = create_engine(
            db_url,
            connect_args={"sslmode": "require"},
            pool_size=5,
            max_overflow=2
        )

        # Testa a conexão
        with engine.connect() as conn:
            print("✓ Conexão estabelecida com sucesso!")

    except Exception as e:
        print(f"❌ Erro ao conectar: {e}")
        sys.exit(1)

    # 3. Verificar estrutura
    print("\n3. Verificando estrutura da tabela ofertas...")
    columns = check_table_structure(engine)

    if columns is None:
        sys.exit(1)

    # 4. Verificar necessidade de migração
    print("\n4. Análise...")

    has_codigo_interno = 'codigo_interno' in columns
    has_descricao = 'descricao' in columns
    has_codigo = 'codigo' in columns
    has_produto = 'produto' in columns

    if has_codigo_interno and has_descricao:
        print("✓ Colunas corretas já existem!")
        print("  - codigo_interno ✓")
        print("  - descricao ✓")
        print("\n✅ Nenhuma migração necessária!")
        return

    if has_codigo or has_produto:
        print("⚠️  Colunas antigas detectadas:")
        if has_codigo:
            print(f"  - 'codigo' precisa ser renomeada para 'codigo_interno'")
        if has_produto:
            print(f"  - 'produto' precisa ser renomeada para 'descricao'")

        print("\n5. Aplicando migração...")
        if apply_migration(engine):
            print("\n6. Verificando resultado...")
            new_columns = check_table_structure(engine)

            if new_columns and 'codigo_interno' in new_columns:
                print("\n" + "=" * 70)
                print("  ✅ SUCESSO! TABELA CORRIGIDA!")
                print("=" * 70)
                print("\nA aplicação agora deve funcionar normalmente.")
            else:
                print("\n❌ Algo deu errado. Verifique manualmente.")
        else:
            print("\n❌ Falha ao aplicar migração.")
            sys.exit(1)
    else:
        print("❌ Estrutura da tabela está inconsistente!")
        print(f"Colunas encontradas: {columns}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Operação cancelada.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erro inesperado: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
