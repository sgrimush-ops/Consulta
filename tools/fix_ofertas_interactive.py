#!/usr/bin/env python3
"""
Script interativo para configurar e corrigir a tabela ofertas.
"""

import os
import sys
import getpass


def main():
    print("=" * 70)
    print("  ASSISTENTE DE CORREÇÃO DA TABELA OFERTAS")
    print("=" * 70)
    print()
    print("Este assistente irá:")
    print("1. Solicitar as credenciais do banco de dados")
    print("2. Verificar a estrutura da tabela ofertas")
    print("3. Aplicar a migração se necessário")
    print()

    # Pergunta se o usuário quer continuar
    resposta = input("Deseja continuar? (s/n): ").strip().lower()
    if resposta not in ['s', 'sim', 'y', 'yes']:
        print("\n❌ Operação cancelada.")
        sys.exit(0)

    print("\n" + "=" * 70)
    print("  CONFIGURAÇÃO DO BANCO DE DADOS")
    print("=" * 70)
    print()
    print("Digite as informações de conexão do PostgreSQL:")
    print("(Exemplo: postgresql://usuario:senha@host:5432/nome_banco)")
    print()

    # Opção 1: URL completa
    print("Opção 1: Cole a URL completa de conexão")
    database_url = input("DATABASE_URL: ").strip()

    if not database_url:
        # Opção 2: Informações separadas
        print("\nOpção 2: Digite as informações separadamente")
        host = input("Host (ex: localhost ou render.com): ").strip()
        port = input("Porta (padrão 5432): ").strip() or "5432"
        database = input("Nome do banco: ").strip()
        user = input("Usuário: ").strip()
        password = getpass.getpass("Senha: ").strip()

        database_url = f"postgresql://{user}:{password}@{host}:{port}/{database}"

    # Substitui postgres:// por postgresql://
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    # Valida a URL
    if not database_url.startswith("postgresql://"):
        print("\n❌ URL inválida! Deve começar com 'postgresql://'")
        sys.exit(1)

    print("\n✓ URL de conexão configurada")

    # Define temporariamente a variável de ambiente
    os.environ['DATABASE_URL'] = database_url

    # Importa e executa o script de correção
    print("\n" + "=" * 70)
    print("  EXECUTANDO CORREÇÃO")
    print("=" * 70)
    print()

    try:
        # Importa o script de correção
        sys.path.insert(0, os.path.dirname(__file__))
        from fix_ofertas_now import main as fix_main

        # Executa
        fix_main()

    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Operação cancelada pelo usuário.")
        sys.exit(1)
