#!/usr/bin/env python3
"""
Script para limpar pedidos aprovados do sistema antigo
Remove todos os pedidos anteriores a hoje (data de hoje)

Uso:
    export DATABASE_URL='postgresql://user:pass@host:5432/db'
    python3 tools/cleanup_pedidos_antigos.py [--dry-run]
"""

import os
import sys
from sqlalchemy import create_engine, text, event
import argparse
from utils.timezone import now_brazil, today_brazil


def get_engine():
    """Cria conexão com o banco de dados"""
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        print("❌ Erro: DATABASE_URL não encontrada.")
        print("   Configure a variável de ambiente DATABASE_URL")
        sys.exit(1)
    
    # Substituição para Postgres no Render
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    
    try:
        engine = create_engine(
            db_url,
            connect_args={"sslmode": "require"}
        )
        @event.listens_for(engine, "connect")
        def _set_postgres_timezone(dbapi_connection, _connection_record):
            with dbapi_connection.cursor() as cursor:
                cursor.execute("SET TIME ZONE 'America/Sao_Paulo'")
        return engine
    except Exception as e:
        print(f"❌ Erro ao conectar ao banco: {e}")
        sys.exit(1)


def cleanup_pedidos_antigos(engine, dry_run=False):
    """Remove todos os pedidos anteriores a hoje"""
    print("\n" + "=" * 70)
    print("🗑️  LIMPEZA DE PEDIDOS DO SISTEMA ANTIGO")
    print("=" * 70)
    print(f"\n📅 Data de referência: {today_brazil()}")
    print("🎯 Alvo: TODOS os pedidos anteriores a hoje")
    
    if dry_run:
        print("\n⚠️  MODO DRY-RUN: Nenhuma alteração será feita no banco")
    
    print("\n" + "-" * 70)
    
    with engine.connect() as conn:
        # Contar pedidos antigos
        count_query = text("""
            SELECT COUNT(*) 
            FROM pedidos_consolidados
            WHERE CAST(data_pedido AS DATE) < (
                CURRENT_TIMESTAMP AT TIME ZONE 'America/Sao_Paulo'
            )::date
        """)
        
        total_antigos = conn.execute(count_query).scalar()
        
        print(f"\n📊 ESTATÍSTICAS:")
        print(f"   • Total de pedidos antigos: {total_antigos}")
        
        if total_antigos == 0:
            print("\n✅ Nenhum pedido antigo para remover.")
            return
        
        # Buscar detalhes dos pedidos a serem removidos
        detail_query = text("""
            SELECT 
                MIN(data_pedido) as data_mais_antiga,
                MAX(data_pedido) as data_mais_recente,
                COUNT(DISTINCT usuario_pedido) as total_usuarios,
                COUNT(CASE WHEN status_aprovacao = 'Aprovado' THEN 1 END) as total_aprovados,
                COUNT(CASE WHEN status_aprovacao = 'Pendente' THEN 1 END) as total_pendentes,
                COUNT(CASE WHEN status_aprovacao IN ('Reprovado', 'Rejeitado') THEN 1 END) as total_rejeitados
            FROM pedidos_consolidados
            WHERE CAST(data_pedido AS DATE) < (
                CURRENT_TIMESTAMP AT TIME ZONE 'America/Sao_Paulo'
            )::date
        """)
        
        result = conn.execute(detail_query).fetchone()
        
        if result:
            print(f"   • Período: {result[0]} até {result[1]}")
            print(f"   • Usuários envolvidos: {result[2]}")
            print(f"   • Status: {result[3]} aprovados, {result[4]} pendentes, {result[5]} rejeitados")
        
        print("\n" + "-" * 70)
        
        if dry_run:
            print(f"\n[DRY-RUN] Seriam removidos: {total_antigos} pedidos (todos os status)")
            print("\n💡 Execute sem --dry-run para realizar a limpeza definitiva")
        else:
            # Confirmar ação
            print(f"\n⚠️  ATENÇÃO: Esta ação irá remover {total_antigos} pedidos permanentemente (todos os status)!")
            confirmacao = input("\n   Digite 'CONFIRMO' para prosseguir: ")
            
            if confirmacao.strip() != "CONFIRMO":
                print("\n❌ Operação cancelada pelo usuário.")
                return
            
            # Realizar a limpeza
            print("\n🔄 Removendo pedidos antigos...")
            
            delete_query = text("""
                DELETE FROM pedidos_consolidados
                WHERE CAST(data_pedido AS DATE) < (
                    CURRENT_TIMESTAMP AT TIME ZONE 'America/Sao_Paulo'
                )::date
            """)
            
            with engine.begin() as trans_conn:
                result = trans_conn.execute(delete_query)
                removidos = result.rowcount
            
            print(f"\n✅ Limpeza concluída!")
            print(f"   • Pedidos removidos: {removidos}")
            
            # Otimizar tabela após deleção (VACUUM precisa estar fora de transação)
            print("\n🔧 Otimizando tabela...")
            try:
                conn.connection.set_isolation_level(0)  # AUTOCOMMIT mode
                conn.execute(text("VACUUM ANALYZE pedidos_consolidados"))
                conn.connection.set_isolation_level(1)  # Restore
                print("✅ Otimização concluída!")
            except Exception as e:
                print(f"⚠️  Otimização não foi possível: {e}")
                print("   (Isto não afeta a limpeza dos pedidos)")
    
    print("\n" + "=" * 70)
    print("✅ PROCESSO FINALIZADO")
    print("=" * 70 + "\n")


def main():
    """Função principal"""
    parser = argparse.ArgumentParser(
        description='Limpa TODOS os pedidos do sistema antigo (anteriores a hoje)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simula a execução sem fazer alterações no banco'
    )
    
    args = parser.parse_args()
    
    print("\n" + "=" * 70)
    print("🛠️  FERRAMENTA DE LIMPEZA DE PEDIDOS ANTIGOS")
    print("=" * 70)
    print(f"\n📅 Executado em: {now_brazil().strftime('%d/%m/%Y %H:%M:%S')}")
    
    engine = get_engine()
    
    try:
        cleanup_pedidos_antigos(engine, args.dry_run)
    except KeyboardInterrupt:
        print("\n\n⚠️  Operação interrompida pelo usuário.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erro durante a execução: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
