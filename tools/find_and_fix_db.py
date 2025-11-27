#!/usr/bin/env python3
"""
Script que tenta encontrar DATABASE_URL em múltiplas fontes e aplica a correção
"""

import os
import sys


def find_database_url():
    """Tenta encontrar DATABASE_URL em várias fontes."""

    # 1. Variável de ambiente
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        print("✓ DATABASE_URL encontrada nas variáveis de ambiente")
        return db_url

    # 2. Arquivo .env na raiz
    env_file = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_file):
        print(f"✓ Arquivo .env encontrado: {env_file}")
        try:
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('DATABASE_URL='):
                        db_url = line.split('=', 1)[1].strip('"').strip("'")
                        print("✓ DATABASE_URL encontrada no arquivo .env")
                        return db_url
        except Exception as e:
            print(f"⚠ Erro ao ler .env: {e}")

    # 3. Arquivo secrets.toml do Streamlit
    secrets_file = os.path.expanduser('~/.streamlit/secrets.toml')
    if os.path.exists(secrets_file):
        print(f"✓ Arquivo secrets.toml encontrado: {secrets_file}")
        try:
            with open(secrets_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('DATABASE_URL'):
                        # Remove DATABASE_URL = "..." ou DATABASE_URL = '...'
                        db_url = line.split(
                            '=', 1)[1].strip().strip('"').strip("'")
                        print("✓ DATABASE_URL encontrada no secrets.toml")
                        return db_url
        except Exception as e:
            print(f"⚠ Erro ao ler secrets.toml: {e}")

    # 4. Pedir ao usuário
    print("\n" + "="*70)
    print("❌ DATABASE_URL não encontrada automaticamente!")
    print("="*70)
    print("\nPor favor, forneça a string de conexão do PostgreSQL.")
    print("\nFormato:")
    print("  postgresql://usuario:senha@host:porta/nome_banco")
    print("\nExemplo:")
    print("  postgresql://postgres:minhasenha@localhost:5432/baklizi")
    print("\n(Pressione Ctrl+C para cancelar)")
    print("="*70)

    try:
        db_url = input("\nDATABASE_URL: ").strip()
        if db_url:
            return db_url
    except KeyboardInterrupt:
        print("\n\n❌ Cancelado pelo usuário")
        sys.exit(1)

    return None


def main():
    print("\n" + "="*70)
    print("LOCALIZADOR E CORRETOR DA TABELA OFERTAS")
    print("="*70)

    # Tenta encontrar DATABASE_URL
    db_url = find_database_url()

    if not db_url:
        print("\n❌ Não foi possível obter DATABASE_URL")
        print("\nOpções:")
        print("1. Defina a variável de ambiente:")
        print("   export DATABASE_URL='postgresql://...'")
        print("2. Crie um arquivo .env com:")
        print("   DATABASE_URL=postgresql://...")
        print("3. Execute novamente e forneça quando solicitado")
        sys.exit(1)

    # Define no ambiente para uso posterior
    os.environ['DATABASE_URL'] = db_url

    # Importa e executa o script de diagnóstico
    print("\n" + "="*70)
    print("Executando diagnóstico...")
    print("="*70)

    try:
        # Importa o módulo de diagnóstico
        import diagnose_ofertas

        # Executa a função main
        diagnose_ofertas.main()

    except ImportError:
        print("❌ Erro: diagnose_ofertas.py não encontrado")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erro durante execução: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Operação cancelada pelo usuário")
        sys.exit(1)
