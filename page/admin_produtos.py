import streamlit as st
import pandas as pd
import os
from sqlalchemy import text
from datetime import datetime

def load_products_from_parquet():
    """Carrega produtos do arquivo parquet."""
    parquet_path = os.path.join("bdados", "con5cod.parquet")
    
    if not os.path.exists(parquet_path):
        st.error("Arquivo parquet não encontrado!")
        return pd.DataFrame()
    
    try:
        df = pd.read_parquet(parquet_path)
        df['cod_consinco'] = df['cod_consinco'].astype(int)
        df['Emb'] = df['Emb'].astype(int)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar parquet: {e}")
        return pd.DataFrame()


def get_correcoes_embalagens(engine):
    """Busca correções de embalagens do banco de dados."""
    try:
        query = text("""
            SELECT cod_consinco, embalagem_corrigida, 
                   data_alteracao, usuario_alteracao
            FROM produtos_correcoes
            ORDER BY data_alteracao DESC
        """)
        
        with engine.connect() as conn:
            df = pd.read_sql(query, conn)
        
        return df
    except Exception as e:
        # Tabela ainda não existe
        return pd.DataFrame()


def create_correcoes_table(engine):
    """Cria a tabela de correções de produtos se não existir."""
    try:
        query = text("""
            CREATE TABLE IF NOT EXISTS produtos_correcoes (
                cod_consinco INTEGER PRIMARY KEY,
                embalagem_corrigida INTEGER NOT NULL,
                data_alteracao TIMESTAMP NOT NULL,
                usuario_alteracao TEXT NOT NULL
            )
        """)
        
        with engine.begin() as conn:
            conn.execute(query)
        
        return True
    except Exception as e:
        st.error(f"Erro ao criar tabela: {e}")
        return False


def salvar_correcao_embalagem(engine, cod_consinco, embalagem_nova, usuario):
    """Salva ou atualiza a correção de embalagem."""
    try:
        query = text("""
            INSERT INTO produtos_correcoes 
                (cod_consinco, embalagem_corrigida, data_alteracao, usuario_alteracao)
            VALUES (:cod, :emb, :data, :usuario)
            ON CONFLICT (cod_consinco) 
            DO UPDATE SET 
                embalagem_corrigida = :emb,
                data_alteracao = :data,
                usuario_alteracao = :usuario
        """)
        
        with engine.begin() as conn:
            conn.execute(query, {
                "cod": int(cod_consinco),
                "emb": int(embalagem_nova),
                "data": datetime.now(),
                "usuario": usuario
            })
        
        return True
    except Exception as e:
        st.error(f"Erro ao salvar correção: {e}")
        return False


def remover_correcao(engine, cod_consinco):
    """Remove uma correção de embalagem (volta ao valor original do parquet)."""
    try:
        query = text("DELETE FROM produtos_correcoes WHERE cod_consinco = :cod")
        
        with engine.begin() as conn:
            conn.execute(query, {"cod": int(cod_consinco)})
        
        return True
    except Exception as e:
        st.error(f"Erro ao remover correção: {e}")
        return False


def show_admin_produtos_page(engine, base_data_path):
    """Página de administração de produtos e embalagens."""
    
    st.title("🔧 Administração de Produtos")
    st.markdown("Corrigir embalagens de produtos do sistema")
    
    # Verificar se usuário é admin
    if not st.session_state.get("is_admin", False):
        st.error("❌ Acesso negado. Esta página é exclusiva para administradores.")
        return
    
    # Criar tabela se não existir
    create_correcoes_table(engine)
    
    # Tabs para organizar funcionalidades
    tab1, tab2, tab3 = st.tabs(["🔍 Buscar e Editar", "📋 Correções Ativas", "📊 Todos os Produtos"])
    
    # --- TAB 1: Buscar e Editar ---
    with tab1:
        st.subheader("Buscar Produto para Editar Embalagem")
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            termo_busca = st.text_input(
                "Digite o código Consinco ou descrição do produto:",
                key="busca_admin_prod"
            )
        
        with col2:
            tipo_busca = st.radio(
                "Buscar por:",
                ["Código", "Descrição"],
                key="tipo_busca_admin"
            )
        
        if termo_busca:
            df_produtos = load_products_from_parquet()
            
            if not df_produtos.empty:
                if tipo_busca == "Código":
                    try:
                        cod = int(termo_busca)
                        resultado = df_produtos[df_produtos['cod_consinco'] == cod]
                    except:
                        resultado = pd.DataFrame()
                else:
                    termo_upper = termo_busca.upper()
                    resultado = df_produtos[
                        df_produtos['descricao'].str.contains(termo_upper, na=False)
                    ]
                
                if not resultado.empty:
                    st.success(f"✅ {len(resultado)} produto(s) encontrado(s)")
                    
                    # Buscar correções existentes
                    df_correcoes = get_correcoes_embalagens(engine)
                    
                    # Mesclar com correções
                    if not df_correcoes.empty:
                        resultado = resultado.merge(
                            df_correcoes[['cod_consinco', 'embalagem_corrigida']], 
                            on='cod_consinco', 
                            how='left'
                        )
                        resultado['Emb_Atual'] = resultado['embalagem_corrigida'].fillna(resultado['Emb'])
                        resultado['Tem_Correcao'] = resultado['embalagem_corrigida'].notna()
                    else:
                        resultado['Emb_Atual'] = resultado['Emb']
                        resultado['Tem_Correcao'] = False
                    
                    # Exibir produtos encontrados
                    for idx, row in resultado.iterrows():
                        with st.expander(
                            f"{'⚠️' if row['Tem_Correcao'] else '📦'} {row['cod_consinco']} - {row['descricao']}"
                        ):
                            col_info, col_edit = st.columns([2, 1])
                            
                            with col_info:
                                st.markdown(f"**Código Consinco:** {row['cod_consinco']}")
                                st.markdown(f"**Descrição:** {row['descricao']}")
                                st.markdown(f"**Transição (EAN):** {row['transicao']}")
                                st.markdown(f"**Status Mix:** {row['Mix']}")
                                st.markdown(f"**Embalagem Original:** {row['Emb']} un/cx")
                                
                                if row['Tem_Correcao']:
                                    st.warning(f"**Embalagem Corrigida:** {int(row['Emb_Atual'])} un/cx")
                            
                            with col_edit:
                                nova_emb = st.number_input(
                                    "Nova Embalagem:",
                                    min_value=1,
                                    value=int(row['Emb_Atual']),
                                    key=f"emb_{row['cod_consinco']}"
                                )
                                
                                if st.button(
                                    "💾 Salvar Correção",
                                    key=f"salvar_{row['cod_consinco']}",
                                    use_container_width=True
                                ):
                                    if salvar_correcao_embalagem(
                                        engine, 
                                        row['cod_consinco'], 
                                        nova_emb,
                                        st.session_state.get("username", "admin")
                                    ):
                                        st.success("✅ Embalagem atualizada!")
                                        st.rerun()
                                
                                if row['Tem_Correcao']:
                                    if st.button(
                                        "🔄 Restaurar Original",
                                        key=f"remover_{row['cod_consinco']}",
                                        use_container_width=True
                                    ):
                                        if remover_correcao(engine, row['cod_consinco']):
                                            st.success("✅ Voltou ao valor original!")
                                            st.rerun()
                else:
                    st.warning("Nenhum produto encontrado.")
    
    # --- TAB 2: Correções Ativas ---
    with tab2:
        st.subheader("Produtos com Embalagens Corrigidas")
        
        df_correcoes = get_correcoes_embalagens(engine)
        
        if not df_correcoes.empty:
            df_produtos = load_products_from_parquet()
            
            # Mesclar com informações do parquet
            df_completo = df_correcoes.merge(
                df_produtos[['cod_consinco', 'descricao', 'Emb']], 
                on='cod_consinco', 
                how='left'
            )
            
            df_completo = df_completo.rename(columns={
                'Emb': 'Emb_Original',
                'embalagem_corrigida': 'Emb_Corrigida'
            })
            
            st.dataframe(
                df_completo[[
                    'cod_consinco', 'descricao', 'Emb_Original', 
                    'Emb_Corrigida', 'data_alteracao', 'usuario_alteracao'
                ]],
                column_config={
                    "cod_consinco": "Código Consinco",
                    "descricao": "Descrição",
                    "Emb_Original": "Emb. Original",
                    "Emb_Corrigida": "Emb. Corrigida",
                    "data_alteracao": st.column_config.DatetimeColumn(
                        "Data Alteração",
                        format="DD/MM/YYYY HH:mm"
                    ),
                    "usuario_alteracao": "Usuário"
                },
                hide_index=True,
                use_container_width=True
            )
            
            st.info(f"📊 Total: {len(df_completo)} produto(s) com embalagem corrigida")
        else:
            st.info("Nenhuma correção de embalagem registrada ainda.")
    
    # --- TAB 3: Todos os Produtos ---
    with tab3:
        st.subheader("Visualizar Todos os Produtos")
        
        if st.button("🔄 Carregar Todos os Produtos"):
            df_produtos = load_products_from_parquet()
            df_correcoes = get_correcoes_embalagens(engine)
            
            if not df_produtos.empty:
                # Mesclar com correções
                if not df_correcoes.empty:
                    df_produtos = df_produtos.merge(
                        df_correcoes[['cod_consinco', 'embalagem_corrigida']], 
                        on='cod_consinco', 
                        how='left'
                    )
                    df_produtos['Emb_Exibir'] = df_produtos['embalagem_corrigida'].fillna(df_produtos['Emb'])
                    df_produtos['Status_Emb'] = df_produtos['embalagem_corrigida'].apply(
                        lambda x: '⚠️ Corrigida' if pd.notna(x) else '📦 Original'
                    )
                else:
                    df_produtos['Emb_Exibir'] = df_produtos['Emb']
                    df_produtos['Status_Emb'] = '📦 Original'
                
                st.dataframe(
                    df_produtos[[
                        'cod_consinco', 'descricao', 'transicao', 
                        'Mix', 'Emb_Exibir', 'Status_Emb'
                    ]],
                    column_config={
                        "cod_consinco": "Código Consinco",
                        "descricao": "Descrição",
                        "transicao": "Transição",
                        "Mix": "Status Mix",
                        "Emb_Exibir": "Embalagem",
                        "Status_Emb": "Status"
                    },
                    hide_index=True,
                    use_container_width=True
                )
                
                st.info(f"📊 Total: {len(df_produtos)} produtos no sistema")
