"""
Módulo centralizado para carregamento de produtos.
Garante que produtos customizados sempre tenham prioridade sobre o parquet.
"""
import pandas as pd
import os
from sqlalchemy import text


def _normalizar_nomes_colunas(df):
    """Normaliza nomes de colunas vindas do parquet."""
    df = df.copy()
    df.columns = [str(col).strip() for col in df.columns]
    return df


def load_produtos_merged(engine):
    """
    Carrega produtos mesclando parquet + banco custom.
    Produtos customizados no banco SEMPRE têm prioridade.
    
    Retorna DataFrame com todos os produtos, onde:
    - Produtos do banco custom sobrescrevem produtos do parquet
    - Customizações são preservadas permanentemente
    """
    # 1. Carregar produtos customizados do banco (prioridade máxima)
    try:
        query = text("""
            SELECT 
                cod_consinco, 
                descricao, 
                transicao, 
                embalagem as Emb, 
                status_mix as Mix,
                'Custom' as origem,
                data_alteracao
            FROM produtos_custom
            ORDER BY cod_consinco
        """)
        
        with engine.connect() as conn:
            df_custom = pd.read_sql(query, conn)
        
        df_custom['cod_consinco'] = df_custom['cod_consinco'].astype(int)
        codigos_custom = set(df_custom['cod_consinco'].values)
    except Exception:
        df_custom = pd.DataFrame()
        codigos_custom = set()
    
    # 2. Carregar produtos do parquet
    parquet_path = os.path.join("bdados", "con5cod.parquet")
    
    if os.path.exists(parquet_path):
        try:
            df_parquet = _normalizar_nomes_colunas(
                pd.read_parquet(parquet_path)
            )
            
            # Mapear colunas novas
            column_mapping = {
                'codigoconsinco': 'cod_consinco',
                'Código Produto': 'cod_consinco',
                'Codigo Produto': 'cod_consinco',
                'codigo transicao': 'transicao',
                'CODACESSO': 'transicao',
                'Empresa : Produto': 'descricao',
                'Empresa: Produto': 'descricao',
                'embalagem': 'Emb',
                'EmbSeparacao': 'Emb',
                'ltmix': 'Mix',
                'capacidade': 'CapacidadeGondola',
                'CapacidadeGondola': 'CapacidadeGondola'
            }
            
            df_parquet.rename(columns=column_mapping, inplace=True)
            
            # Garantir colunas essenciais
            if 'cod_consinco' not in df_parquet.columns:
                raise ValueError("Coluna 'cod_consinco' não encontrada no parquet")
            if 'descricao' not in df_parquet.columns:
                df_parquet['descricao'] = 'SEM DESCRIÇÃO'
            if 'transicao' not in df_parquet.columns:
                df_parquet['transicao'] = 0
            if 'Emb' not in df_parquet.columns:
                df_parquet['Emb'] = 1
            if 'Mix' not in df_parquet.columns:
                df_parquet['Mix'] = 'A'
            if 'CapacidadeGondola' not in df_parquet.columns:
                df_parquet['CapacidadeGondola'] = 0
            
            df_parquet['cod_consinco'] = df_parquet['cod_consinco'].astype(int)
            df_parquet['origem'] = 'Parquet'
            
            # IMPORTANTE: Remover do parquet os códigos que existem no banco custom
            # Isso garante que customizações SEMPRE prevalecem
            if codigos_custom:
                df_parquet = df_parquet[~df_parquet['cod_consinco'].isin(codigos_custom)]
        except Exception as e:
            raise Exception(f"Erro ao carregar parquet: {e}")
    else:
        raise Exception("Arquivo parquet não encontrado: bdados/con5cod.parquet")
    
    # 3. Mesclar: Custom + Parquet (custom já filtrou duplicatas do parquet)
    if not df_custom.empty:
        # Garantir que as colunas sejam compatíveis
        cols_finais = ['cod_consinco', 'descricao', 'transicao', 'Emb', 'Mix', 'origem']
        df_final = pd.concat([
            df_custom[cols_finais],
            df_parquet[cols_finais]
        ], ignore_index=True)
    else:
        df_final = df_parquet
    
    # Garantir tipos corretos
    df_final['cod_consinco'] = df_final['cod_consinco'].astype(int)
    df_final['Emb'] = df_final['Emb'].astype(int)
    
    return df_final


def get_produto_info(engine, cod_consinco):
    """
    Busca informações de um produto específico.
    Prioriza sempre o banco custom.
    """
    try:
        # Verificar primeiro no banco custom
        query = text("""
            SELECT cod_consinco, descricao, transicao, embalagem as Emb, status_mix as Mix
            FROM produtos_custom
            WHERE cod_consinco = :cod
        """)
        
        with engine.connect() as conn:
            result = conn.execute(query, {"cod": int(cod_consinco)}).fetchone()
        
        if result:
            return dict(result._mapping)
    except Exception:
        pass
    
    # Se não encontrou no custom, buscar no parquet
    parquet_path = os.path.join("bdados", "con5cod.parquet")
    
    if os.path.exists(parquet_path):
        try:
            df = _normalizar_nomes_colunas(pd.read_parquet(parquet_path))
            
            # Mapear colunas novas
            column_mapping = {
                'codigoconsinco': 'cod_consinco',
                'Código Produto': 'cod_consinco',
                'Codigo Produto': 'cod_consinco',
                'codigo transicao': 'transicao',
                'CODACESSO': 'transicao',
                'Empresa : Produto': 'descricao',
                'Empresa: Produto': 'descricao',
                'embalagem': 'Emb',
                'EmbSeparacao': 'Emb',
                'ltmix': 'Mix'
            }
            
            df.rename(columns=column_mapping, inplace=True)
            
            if 'cod_consinco' not in df.columns:
                return None
            
            resultado = df[df['cod_consinco'] == int(cod_consinco)]
            
            if not resultado.empty:
                return resultado.iloc[0].to_dict()
        except Exception:
            pass
    
    return None


def ensure_produtos_custom_table(engine):
    """
    Garante que a tabela produtos_custom existe com todos os constraints.
    """
    try:
        query = text("""
            CREATE TABLE IF NOT EXISTS produtos_custom (
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
            
            -- Criar índice para otimizar buscas
            CREATE INDEX IF NOT EXISTS idx_produtos_custom_status 
            ON produtos_custom(status_mix);
            
            -- Comentários para documentação
            COMMENT ON TABLE produtos_custom IS 
            'Produtos customizados que sobrescrevem o parquet. Nunca deletar esta tabela!';
            
            COMMENT ON COLUMN produtos_custom.cod_consinco IS 
            'Código único do produto. Se existir aqui, sobrescreve o parquet.';
        """)
        
        with engine.begin() as conn:
            conn.execute(query)
        
        return True
    except Exception as e:
        print(f"Erro ao criar tabela: {e}")
        return False
