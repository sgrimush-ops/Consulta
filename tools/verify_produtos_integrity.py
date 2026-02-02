#!/usr/bin/env python3
"""
Script de verificação e proteção de integridade dos produtos customizados.
Garante que customizações nunca sejam perdidas.
"""
import os
import sys
from sqlalchemy import create_engine, text
from datetime import datetime


def get_engine():
    """Cria conexão com o banco de dados"""
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        print("❌ Erro: DATABASE_URL não encontrada.")
        sys.exit(1)
    
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    
    try:
        return create_engine(db_url, connect_args={"sslmode": "require"})
    except Exception as e:
        print(f"❌ Erro ao conectar ao banco: {e}")
        sys.exit(1)


def verify_table_integrity(engine):
    """Verifica a integridade da tabela produtos_custom"""
    print("\n" + "=" * 70)
    print("🔍 VERIFICAÇÃO DE INTEGRIDADE - PRODUTOS CUSTOMIZADOS")
    print("=" * 70)
    
    with engine.connect() as conn:
        # Verificar se tabela existe
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'produtos_custom'
            )
        """))
        
        existe = result.scalar()
        
        if not existe:
            print("\n⚠️  Tabela produtos_custom NÃO EXISTE!")
            print("   Criando tabela...")
            
            conn.execute(text("""
                CREATE TABLE produtos_custom (
                    cod_consinco INTEGER PRIMARY KEY,
                    descricao TEXT NOT NULL,
                    transicao INTEGER,
                    embalagem INTEGER NOT NULL CHECK (embalagem > 0),
                    status_mix CHAR(1) NOT NULL CHECK (status_mix IN ('A', 'S')),
                    data_criacao TIMESTAMP NOT NULL DEFAULT NOW(),
                    data_alteracao TIMESTAMP,
                    usuario_criacao TEXT NOT NULL,
                    usuario_alteracao TEXT
                );
                
                CREATE INDEX idx_produtos_custom_status ON produtos_custom(status_mix);
                
                COMMENT ON TABLE produtos_custom IS 
                'CRÍTICO: Produtos customizados. NUNCA deletar esta tabela!';
            """))
            conn.commit()
            
            print("✅ Tabela criada com sucesso!")
        else:
            print("\n✅ Tabela produtos_custom existe")
        
        # Verificar constraints
        result = conn.execute(text("""
            SELECT
                tc.constraint_name,
                tc.constraint_type
            FROM information_schema.table_constraints tc
            WHERE tc.table_name = 'produtos_custom'
            ORDER BY tc.constraint_type
        """))
        
        constraints = result.fetchall()
        
        print(f"\n📋 Constraints ativos:")
        for constraint in constraints:
            print(f"   • {constraint[1]}: {constraint[0]}")
        
        # Verificar índices
        result = conn.execute(text("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE tablename = 'produtos_custom'
        """))
        
        indices = result.fetchall()
        
        print(f"\n📊 Índices:")
        for idx in indices:
            print(f"   • {idx[0]}")
        
        # Contar registros
        total = conn.execute(text("SELECT COUNT(*) FROM produtos_custom")).scalar()
        ativos = conn.execute(text(
            "SELECT COUNT(*) FROM produtos_custom WHERE status_mix = 'A'"
        )).scalar()
        suspensos = conn.execute(text(
            "SELECT COUNT(*) FROM produtos_custom WHERE status_mix = 'S'"
        )).scalar()
        
        print(f"\n📈 Estatísticas:")
        print(f"   Total de customizações: {total}")
        print(f"   Produtos ativos: {ativos}")
        print(f"   Produtos suspensos: {suspensos}")
        
        if total > 0:
            # Mostrar os mais recentes
            result = conn.execute(text("""
                SELECT cod_consinco, descricao, 
                       TO_CHAR(COALESCE(data_alteracao, data_criacao), 'DD/MM/YYYY HH24:MI') as data,
                       COALESCE(usuario_alteracao, usuario_criacao) as usuario
                FROM produtos_custom
                ORDER BY COALESCE(data_alteracao, data_criacao) DESC
                LIMIT 5
            """))
            
            print(f"\n📝 Últimas customizações:")
            for row in result:
                print(f"   • Cód {row[0]}: {row[1][:40]}... ({row[3]} em {row[2]})")
    
    print("\n" + "=" * 70)
    print("✅ VERIFICAÇÃO CONCLUÍDA")
    print("=" * 70 + "\n")


def create_backup_trigger(engine):
    """Cria trigger para backup automático antes de qualquer UPDATE/DELETE"""
    print("\n🛡️  Criando proteção automática...")
    
    try:
        with engine.begin() as conn:
            # Criar tabela de auditoria se não existir
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS produtos_custom_audit (
                    id SERIAL PRIMARY KEY,
                    operacao VARCHAR(10) NOT NULL,
                    cod_consinco INTEGER NOT NULL,
                    descricao_old TEXT,
                    embalagem_old INTEGER,
                    status_mix_old CHAR(1),
                    data_operacao TIMESTAMP NOT NULL DEFAULT NOW(),
                    usuario_operacao TEXT
                );
                
                COMMENT ON TABLE produtos_custom_audit IS 
                'Auditoria de alterações em produtos_custom. Backup automático.';
            """))
            
            # Criar função de trigger
            conn.execute(text("""
                CREATE OR REPLACE FUNCTION audit_produtos_custom()
                RETURNS TRIGGER AS $$
                BEGIN
                    IF (TG_OP = 'DELETE') THEN
                        INSERT INTO produtos_custom_audit 
                            (operacao, cod_consinco, descricao_old, embalagem_old, status_mix_old, usuario_operacao)
                        VALUES 
                            ('DELETE', OLD.cod_consinco, OLD.descricao, OLD.embalagem, OLD.status_mix, OLD.usuario_alteracao);
                        RETURN OLD;
                    ELSIF (TG_OP = 'UPDATE') THEN
                        INSERT INTO produtos_custom_audit 
                            (operacao, cod_consinco, descricao_old, embalagem_old, status_mix_old, usuario_operacao)
                        VALUES 
                            ('UPDATE', OLD.cod_consinco, OLD.descricao, OLD.embalagem, OLD.status_mix, OLD.usuario_alteracao);
                        RETURN NEW;
                    END IF;
                    RETURN NULL;
                END;
                $$ LANGUAGE plpgsql;
            """))
            
            # Criar trigger
            conn.execute(text("""
                DROP TRIGGER IF EXISTS trigger_audit_produtos_custom ON produtos_custom;
                
                CREATE TRIGGER trigger_audit_produtos_custom
                AFTER UPDATE OR DELETE ON produtos_custom
                FOR EACH ROW
                EXECUTE FUNCTION audit_produtos_custom();
            """))
        
        print("✅ Proteção automática ativada!")
        print("   • Tabela produtos_custom_audit criada")
        print("   • Trigger de auditoria instalado")
        print("   • Backup automático antes de UPDATE/DELETE")
        
    except Exception as e:
        print(f"⚠️  Erro ao criar proteção: {e}")


def main():
    print("\n" + "=" * 70)
    print("🛠️  FERRAMENTA DE INTEGRIDADE DE PRODUTOS")
    print("=" * 70)
    print(f"\n📅 Executado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    
    engine = get_engine()
    
    try:
        verify_table_integrity(engine)
        create_backup_trigger(engine)
        
        print("\n✅ Sistema protegido com sucesso!")
        print("\n💡 Dicas:")
        print("   • Customizações sempre têm prioridade sobre o parquet")
        print("   • Alterações são auditadas automaticamente")
        print("   • Backup antes de qualquer exclusão/alteração")
        print("   • NUNCA delete a tabela produtos_custom manualmente!")
        
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
