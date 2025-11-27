#!/usr/bin/env python3
"""
Script automatizado para aplicar a migração 002_direct_rename.sql
"""

import os
import sys
from sqlalchemy import create_engine, text, inspect


def get_engine():
    db_url = os.getenv("DATABASE_URL")

    if not db_url:
        print("ERRO: DATABASE_URL não está definida.", file=sys.stderr)
        print("\nPara definir, execute:", file=sys.stderr)
        print("export DATABASE_URL='sua_connection_string'", file=sys.stderr)
        sys.exit(1)

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


def main():
    print("Conectando ao banco de dados...")
    engine = get_engine()

    print("Verificando estrutura atual...")
    inspector = inspect(engine)

    if 'ofertas' not in inspector.get_table_names():
        print("ERRO: Tabela 'ofertas' não existe!")
        sys.exit(1)

    columns = [col['name'] for col in inspector.get_columns('ofertas')]
    print(f"Colunas atuais: {', '.join(columns)}")

    # Verifica se já foi migrada
    if 'codigo_interno' in columns and 'descricao' in columns:
        print("\n✓ Tabela já está migrada corretamente!")
        sys.exit(0)

    print("\nAplicando migração 002_direct_rename.sql...")

    migration_file = os.path.join(os.path.dirname(
        __file__), 'migrations', '002_direct_rename.sql')

    if not os.path.exists(migration_file):
        print(f"ERRO: Arquivo não encontrado: {migration_file}")
        sys.exit(1)

    try:
        with open(migration_file, 'r') as f:
            migration_sql = f.read()

        with engine.begin() as conn:
            conn.execute(text(migration_sql))

        print("✓ Migração aplicada com sucesso!")

        # Verifica novamente
        inspector = inspect(engine)
        new_columns = [col['name'] for col in inspector.get_columns('ofertas')]
        print(f"Novas colunas: {', '.join(new_columns)}")

        if 'codigo_interno' in new_columns:
            print("\n✓ SUCESSO! A tabela foi corrigida.")
        else:
            print("\n⚠ AVISO: A migração foi executada mas 'codigo_interno' não aparece.")

    except Exception as e:
        print(f"\nERRO ao executar migração: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
