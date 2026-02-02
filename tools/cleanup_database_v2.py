#!/usr/bin/env python3
"""
Script de limpeza do banco de dados - Versão 2.0.0

Remove dados obsoletos do sistema antigo de ofertas e prepara
o banco para a nova estrutura do sistema Consinco.

ATENÇÃO: Este script faz alterações permanentes no banco de dados.
Um backup automático será criado antes de qualquer modificação.

Uso:
    export DATABASE_URL='postgresql://user:pass@host:5432/db'
    python3 tools/cleanup_database_v2.py [--dry-run]
"""

import os
import sys
from datetime import datetime
from sqlalchemy import create_engine, text, inspect
import argparse


def create_backup(engine, backup_dir="backups"):
    """Cria um backup do banco de dados usando pg_dump"""
    db_url = os.getenv("DATABASE_URL")
    
    # Criar diretório de backup se não existir
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"{backup_dir}/backup_before_cleanup_{timestamp}.sql"
    
    print(f"\n📦 Criando backup em: {backup_file}")
    
    # Construir comando pg_dump
    cmd = f"pg_dump {db_url} > {backup_file}"
    result = os.system(cmd)
    
    if result == 0:
        print(f"✅ Backup criado com sucesso!")
        return backup_file
    else:
        print(f"❌ Erro ao criar backup!")
        return None


def get_table_info(engine):
    """Obtém informações sobre as tabelas existentes"""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    print("\n📊 Tabelas encontradas no banco de dados:")
    print("━" * 60)
    
    with engine.connect() as conn:
        for table in sorted(tables):
            try:
                count_query = text(f"SELECT COUNT(*) FROM {table}")
                count = conn.execute(count_query).scalar()
                print(f"  📋 {table:<35} {count:>10} registros")
            except Exception as e:
                print(f"  ⚠️  {table:<35} (erro ao contar)")
    
    print("━" * 60)
    return tables


def cleanup_ofertas_table(engine, dry_run=False):
    """Remove ou limpa a tabela de ofertas"""
    print("\n🗑️  LIMPEZA: Tabela 'ofertas'")
    print("━" * 60)
    
    with engine.connect() as conn:
        # Verificar se existe
        check = text("SELECT COUNT(*) FROM ofertas")
        try:
            count = conn.execute(check).scalar()
            print(f"  Registros atuais: {count}")
            
            if count > 0:
                if dry_run:
                    print(f"  [DRY-RUN] Seria deletado: {count} registros")
                else:
                    # Deletar todos os registros
                    delete_query = text("DELETE FROM ofertas")
                    with engine.begin() as trans_conn:
                        result = trans_conn.execute(delete_query)
                        print(f"  ✅ Deletados: {result.rowcount} registros")
            else:
                print(f"  ℹ️  Tabela já está vazia")
        except Exception as e:
            print(f"  ℹ️  Tabela não existe ou erro: {e}")


def cleanup_old_pedidos(engine, days=90, dry_run=False):
    """Remove pedidos aprovados muito antigos (mantém últimos 90 dias)"""
    print(f"\n🗑️  LIMPEZA: Pedidos aprovados com mais de {days} dias")
    print("━" * 60)
    
    with engine.connect() as conn:
        try:
            # Contar pedidos antigos aprovados
            count_query = text("""
                SELECT COUNT(*) 
                FROM pedidos_consolidados
                WHERE status_aprovacao = 'Aprovado'
                AND COALESCE(CAST(data_aprovacao AS DATE), CAST(data_pedido AS DATE)) 
                    < CURRENT_DATE - INTERVAL ':days days'
            """)
            count = conn.execute(count_query, {"days": days}).scalar()
            
            if count > 0:
                print(f"  Pedidos aprovados antigos encontrados: {count}")
                
                if dry_run:
                    print(f"  [DRY-RUN] Seria deletado: {count} registros")
                else:
                    delete_query = text("""
                        DELETE FROM pedidos_consolidados
                        WHERE status_aprovacao = 'Aprovado'
                        AND COALESCE(CAST(data_aprovacao AS DATE), CAST(data_pedido AS DATE)) 
                            < CURRENT_DATE - INTERVAL ':days days'
                    """)
                    with engine.begin() as trans_conn:
                        result = trans_conn.execute(delete_query, {"days": days})
                        print(f"  ✅ Deletados: {result.rowcount} pedidos antigos")
            else:
                print(f"  ℹ️  Nenhum pedido antigo para remover")
        except Exception as e:
            print(f"  ⚠️  Erro: {e}")


def drop_unused_tables(engine, dry_run=False):
    """Remove tabelas que não são mais usadas"""
    print("\n🗑️  REMOÇÃO: Tabelas obsoletas")
    print("━" * 60)
    
    # Lista de tabelas que podem ser removidas (se existirem)
    obsolete_tables = [
        'mix_produtos',  # Se existir da versão antiga
        'estoque_cd',    # Se existir
    ]
    
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    
    for table in obsolete_tables:
        if table in existing_tables:
            print(f"  Tabela obsoleta encontrada: {table}")
            if dry_run:
                print(f"    [DRY-RUN] Seria removida")
            else:
                try:
                    with engine.begin() as conn:
                        conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
                    print(f"    ✅ Removida com sucesso")
                except Exception as e:
                    print(f"    ⚠️  Erro ao remover: {e}")
        else:
            print(f"  ℹ️  Tabela {table} não existe")


def optimize_database(engine, dry_run=False):
    """Executa VACUUM e ANALYZE para otimizar o banco"""
    print("\n⚡ OTIMIZAÇÃO: Limpeza e análise do banco")
    print("━" * 60)
    
    if dry_run:
        print("  [DRY-RUN] Seria executado: VACUUM ANALYZE")
        return
    
    try:
        # VACUUM precisa ser executado fora de uma transação
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            print("  Executando VACUUM ANALYZE...")
            conn.execute(text("VACUUM ANALYZE"))
            print("  ✅ Otimização concluída")
    except Exception as e:
        print(f"  ⚠️  Erro na otimização: {e}")


def show_final_stats(engine):
    """Mostra estatísticas finais do banco"""
    print("\n📊 ESTATÍSTICAS FINAIS")
    print("━" * 60)
    
    tables_to_check = [
        'users',
        'pedidos_consolidados',
        'ofertas',
        'contato_chamados',
        'contato_mensagens',
        'fornecedores_users'
    ]
    
    with engine.connect() as conn:
        for table in tables_to_check:
            try:
                count_query = text(f"SELECT COUNT(*) FROM {table}")
                count = conn.execute(count_query).scalar()
                print(f"  📋 {table:<30} {count:>10} registros")
            except Exception as e:
                print(f"  ⚠️  {table:<30} (não existe)")
    
    print("━" * 60)


def main():
    parser = argparse.ArgumentParser(
        description='Limpa o banco de dados removendo dados obsoletos do sistema antigo'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Executa sem fazer modificações (apenas mostra o que seria feito)'
    )
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='Não cria backup antes da limpeza (NÃO RECOMENDADO!)'
    )
    parser.add_argument(
        '--keep-pedidos-days',
        type=int,
        default=90,
        help='Dias de pedidos aprovados a manter (padrão: 90)'
    )
    
    args = parser.parse_args()
    
    # Banner
    print("╔" + "═" * 62 + "╗")
    print("║" + " " * 10 + "LIMPEZA DO BANCO DE DADOS - v2.0.0" + " " * 17 + "║")
    print("╚" + "═" * 62 + "╝")
    
    if args.dry_run:
        print("\n⚠️  MODO DRY-RUN: Nenhuma modificação será feita\n")
    
    # Verificar DATABASE_URL
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ ERRO: DATABASE_URL não configurada")
        print("\nConfigure a variável de ambiente:")
        print("  export DATABASE_URL='postgresql://user:pass@host:5432/db'")
        sys.exit(1)
    
    # Ajustar URL se necessário
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    
    print(f"\n🔌 Conectando ao banco de dados...")
    
    try:
        engine = create_engine(db_url, pool_pre_ping=True)
        
        # Testar conexão
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✅ Conexão estabelecida com sucesso!")
        
    except Exception as e:
        print(f"❌ ERRO ao conectar: {e}")
        sys.exit(1)
    
    # Mostrar estado atual
    get_table_info(engine)
    
    # Criar backup (se não for dry-run e não for --no-backup)
    if not args.dry_run and not args.no_backup:
        backup_file = create_backup(engine, "tools/backups")
        if not backup_file:
            print("\n⚠️  AVISO: Não foi possível criar backup!")
            response = input("Deseja continuar mesmo assim? (digite 'SIM' para confirmar): ")
            if response != 'SIM':
                print("❌ Operação cancelada pelo usuário")
                sys.exit(1)
    
    # Confirmar operação
    if not args.dry_run:
        print("\n" + "⚠️ " * 20)
        print("\n⚠️  ATENÇÃO: Esta operação irá deletar dados permanentemente!")
        print("\nOperações que serão realizadas:")
        print("  1. Limpar TODOS os registros da tabela 'ofertas'")
        print(f"  2. Remover pedidos aprovados com mais de {args.keep_pedidos_days} dias")
        print("  3. Remover tabelas obsoletas (mix_produtos, estoque_cd)")
        print("  4. Otimizar banco de dados (VACUUM ANALYZE)")
        print("\n" + "⚠️ " * 20)
        
        response = input("\nDigite 'CONFIRMO' para prosseguir: ")
        if response != 'CONFIRMO':
            print("❌ Operação cancelada pelo usuário")
            sys.exit(0)
    
    # Executar limpezas
    print("\n" + "🔧 " * 20)
    print("\n🚀 INICIANDO LIMPEZA DO BANCO DE DADOS\n")
    
    cleanup_ofertas_table(engine, args.dry_run)
    cleanup_old_pedidos(engine, args.keep_pedidos_days, args.dry_run)
    drop_unused_tables(engine, args.dry_run)
    optimize_database(engine, args.dry_run)
    
    # Mostrar estatísticas finais
    show_final_stats(engine)
    
    # Finalização
    print("\n" + "═" * 64)
    if args.dry_run:
        print("\n✅ DRY-RUN CONCLUÍDO - Nenhuma modificação foi feita")
        print("\nPara executar de verdade, remova o flag --dry-run")
    else:
        print("\n✅ LIMPEZA CONCLUÍDA COM SUCESSO!")
        print("\nO banco de dados foi limpo e otimizado.")
        print("Dados do sistema antigo de ofertas foram removidos.")
    print("\n" + "═" * 64 + "\n")


if __name__ == "__main__":
    main()
