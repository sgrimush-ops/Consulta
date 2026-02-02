import streamlit as st
import pandas as pd
import os
from sqlalchemy import text
from datetime import datetime


# ============================================================================
# FUNÇÕES DE BANCO DE DADOS
# ============================================================================


def create_produtos_table(engine):
    """Cria a tabela de produtos personalizados se não existir."""
    try:
        query = text("""
            CREATE TABLE IF NOT EXISTS produtos_custom (
                cod_consinco INTEGER PRIMARY KEY,
                descricao TEXT NOT NULL,
                transicao INTEGER,
                embalagem INTEGER NOT NULL,
                status_mix CHAR(1) NOT NULL CHECK (status_mix IN ('A', 'S')),
                data_criacao TIMESTAMP NOT NULL DEFAULT NOW(),
                data_alteracao TIMESTAMP,
                usuario_criacao TEXT NOT NULL,
                usuario_alteracao TEXT
            )
        """)
        
        with engine.begin() as conn:
            conn.execute(query)
        
        return True
    except Exception as e:
        st.error(f"Erro ao criar tabela: {e}")
        return False


def load_all_products(engine):
    """Carrega todos os produtos (parquet + customizados) mesclados."""
    # Carregar do parquet
    parquet_path = os.path.join("bdados", "con5cod.parquet")
    
    if os.path.exists(parquet_path):
        try:
            df_parquet = pd.read_parquet(parquet_path)
            df_parquet['cod_consinco'] = df_parquet['cod_consinco'].astype(int)
            df_parquet['origem'] = 'Parquet'
        except Exception as e:
            st.error(f"Erro ao carregar parquet: {e}")
            df_parquet = pd.DataFrame()
    else:
        df_parquet = pd.DataFrame()
    
    # Carregar produtos customizados do banco
    try:
        query = text("""
            SELECT cod_consinco, descricao, transicao, embalagem as Emb, 
                   status_mix as Mix, 'Banco' as origem
            FROM produtos_custom
        """)
        
        with engine.connect() as conn:
            df_custom = pd.read_sql(query, conn)
    except Exception:
        df_custom = pd.DataFrame()
    
    # Mesclar (produtos do banco sobrescrevem os do parquet)
    if not df_parquet.empty and not df_custom.empty:
        # Remover do parquet os códigos que existem no banco
        df_parquet = df_parquet[~df_parquet['cod_consinco'].isin(df_custom['cod_consinco'])]
        df_final = pd.concat([df_parquet, df_custom], ignore_index=True)
    elif not df_custom.empty:
        df_final = df_custom
    elif not df_parquet.empty:
        df_final = df_parquet
    else:
        df_final = pd.DataFrame()
    
    return df_final


def save_product(engine, cod_consinco, descricao, transicao, embalagem, status_mix, usuario):
    """Salva um novo produto no banco de dados."""
    try:
        query = text("""
            INSERT INTO produtos_custom 
                (cod_consinco, descricao, transicao, embalagem, status_mix, 
                 data_criacao, usuario_criacao)
            VALUES (:cod, :desc, :trans, :emb, :status, :data, :usuario)
        """)
        
        with engine.begin() as conn:
            conn.execute(query, {
                "cod": int(cod_consinco),
                "desc": descricao,
                "trans": int(transicao) if transicao else None,
                "emb": int(embalagem),
                "status": status_mix,
                "data": datetime.now(),
                "usuario": usuario
            })
        
        return True
    except Exception as e:
        st.error(f"Erro ao salvar produto: {e}")
        return False


def update_product(engine, cod_consinco, descricao, transicao, embalagem, status_mix, usuario):
    """Atualiza um produto existente no banco de dados."""
    try:
        query = text("""
            UPDATE produtos_custom
            SET descricao = :desc,
                transicao = :trans,
                embalagem = :emb,
                status_mix = :status,
                data_alteracao = :data,
                usuario_alteracao = :usuario
            WHERE cod_consinco = :cod
        """)
        
        with engine.begin() as conn:
            result = conn.execute(query, {
                "cod": int(cod_consinco),
                "desc": descricao,
                "trans": int(transicao) if transicao else None,
                "emb": int(embalagem),
                "status": status_mix,
                "data": datetime.now(),
                "usuario": usuario
            })
        
        return result.rowcount > 0
    except Exception as e:
        st.error(f"Erro ao atualizar produto: {e}")
        return False


def delete_product(engine, cod_consinco):
    """Deleta um produto do banco de dados."""
    try:
        query = text("DELETE FROM produtos_custom WHERE cod_consinco = :cod")
        
        with engine.begin() as conn:
            result = conn.execute(query, {"cod": int(cod_consinco)})
        
        return result.rowcount > 0
    except Exception as e:
        st.error(f"Erro ao deletar produto: {e}")
        return False


def check_product_exists(engine, cod_consinco):
    """Verifica se um produto já existe no banco customizado."""
    try:
        query = text("SELECT COUNT(*) FROM produtos_custom WHERE cod_consinco = :cod")
        
        with engine.connect() as conn:
            count = conn.execute(query, {"cod": int(cod_consinco)}).scalar()
        
        return count > 0
    except Exception:
        return False


# ============================================================================
# PÁGINA PRINCIPAL
# ============================================================================


def show_admin_produtos_page(engine, base_data_path):
    """Página de administração de produtos (CRUD completo)."""
    
    st.title("🔧 Administração de Produtos")
    st.markdown("Gerenciar produtos do sistema (Criar, Editar, Excluir)")
    
    # Verificar se usuário é admin
    if st.session_state.get("role") != "admin":
        st.error("❌ Acesso negado. Esta página é exclusiva para administradores.")
        return
    
    # Criar tabela se não existir
    create_produtos_table(engine)
    
    # Tabs para organizar funcionalidades
    tab1, tab2, tab3 = st.tabs(["➕ Criar Produto", "✏️ Editar Produto", "📋 Listar Produtos"])
    
    # ========================================================================
    # TAB 1: CRIAR NOVO PRODUTO
    # ========================================================================
    with tab1:
        st.subheader("Cadastrar Novo Produto")
        
        with st.form("form_criar_produto"):
            col1, col2 = st.columns(2)
            
            with col1:
                novo_cod = st.number_input(
                    "Código Consinco *",
                    min_value=1,
                    step=1,
                    help="Código único do produto"
                )
                novo_desc = st.text_input(
                    "Descrição *",
                    max_chars=200,
                    help="Descrição do produto"
                )
            
            with col2:
                novo_trans = st.number_input(
                    "Código Transição (EAN)",
                    min_value=0,
                    step=1,
                    help="Código de transição/EAN (opcional)"
                )
                novo_emb = st.number_input(
                    "Embalagem (un/cx) *",
                    min_value=1,
                    step=1,
                    help="Unidades por caixa"
                )
            
            novo_status = st.radio(
                "Status no Mix *",
                options=["A", "S"],
                format_func=lambda x: "Ativo (A)" if x == "A" else "Suspenso (S)",
                horizontal=True
            )
            
            submitted = st.form_submit_button("💾 Salvar Produto", type="primary", use_container_width=True)
            
            if submitted:
                # Validações
                if not novo_desc or novo_desc.strip() == "":
                    st.error("❌ Descrição é obrigatória!")
                elif novo_cod <= 0:
                    st.error("❌ Código Consinco deve ser maior que zero!")
                elif check_product_exists(engine, novo_cod):
                    st.warning(f"⚠️ Produto com código {novo_cod} já existe no banco!")
                else:
                    # Salvar
                    if save_product(
                        engine, novo_cod, novo_desc.strip().upper(), 
                        novo_trans if novo_trans > 0 else None,
                        novo_emb, novo_status,
                        st.session_state.get("username", "admin")
                    ):
                        st.success(f"✅ Produto {novo_cod} cadastrado com sucesso!")
                        st.balloons()
                        st.rerun()
    
    # ========================================================================
    # TAB 2: EDITAR PRODUTO
    # ========================================================================
    with tab2:
        st.subheader("Editar Produto Existente")
        
        # Buscar produto
        busca_cod = st.number_input(
            "Digite o Código Consinco do produto:",
            min_value=1,
            step=1,
            key="busca_editar"
        )
        
        if st.button("🔍 Buscar Produto"):
            df_produtos = load_all_products(engine)
            
            if not df_produtos.empty:
                resultado = df_produtos[df_produtos['cod_consinco'] == busca_cod]
                
                if not resultado.empty:
                    produto = resultado.iloc[0]
                    st.session_state.produto_editar = produto.to_dict()
                    st.success("✅ Produto encontrado!")
                else:
                    st.warning(f"⚠️ Produto {busca_cod} não encontrado.")
                    st.session_state.produto_editar = None
        
        # Formulário de edição
        if "produto_editar" in st.session_state and st.session_state.produto_editar:
            produto = st.session_state.produto_editar
            
            st.markdown("---")
            st.markdown("### 📝 Dados do Produto")
            
            with st.form("form_editar_produto"):
                st.info(f"**Código Consinco:** {produto['cod_consinco']} | **Origem:** {produto.get('origem', 'N/A')}")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    edit_desc = st.text_input(
                        "Descrição *",
                        value=produto['descricao'],
                        max_chars=200
                    )
                    edit_trans = st.number_input(
                        "Código Transição",
                        value=int(produto.get('transicao', 0)) if pd.notna(produto.get('transicao')) else 0,
                        min_value=0,
                        step=1
                    )
                
                with col2:
                    edit_emb = st.number_input(
                        "Embalagem (un/cx) *",
                        value=int(produto['Emb']),
                        min_value=1,
                        step=1
                    )
                    edit_status = st.radio(
                        "Status no Mix *",
                        options=["A", "S"],
                        index=0 if produto['Mix'] == "A" else 1,
                        format_func=lambda x: "Ativo (A)" if x == "A" else "Suspenso (S)",
                        horizontal=True
                    )
                
                col_salvar, col_excluir = st.columns(2)
                
                with col_salvar:
                    btn_salvar = st.form_submit_button(
                        "💾 Salvar Alterações",
                        type="primary",
                        use_container_width=True
                    )
                
                with col_excluir:
                    btn_excluir = st.form_submit_button(
                        "🗑️ Excluir Produto",
                        use_container_width=True
                    )
                
                if btn_salvar:
                    if not edit_desc or edit_desc.strip() == "":
                        st.error("❌ Descrição é obrigatória!")
                    else:
                        # Confirmar alteração
                        if "confirmar_alteracao" not in st.session_state:
                            st.session_state.confirmar_alteracao = True
                            st.warning("⚠️ Tem certeza que deseja alterar este produto?")
                            st.info("Clique novamente em 'Salvar Alterações' para confirmar.")
                        else:
                            # Produto do banco: UPDATE
                            if produto.get('origem') == 'Banco':
                                if update_product(
                                    engine, produto['cod_consinco'],
                                    edit_desc.strip().upper(), edit_trans if edit_trans > 0 else None,
                                    edit_emb, edit_status,
                                    st.session_state.get("username", "admin")
                                ):
                                    st.success("✅ Produto atualizado com sucesso!")
                                    del st.session_state.confirmar_alteracao
                                    del st.session_state.produto_editar
                                    st.rerun()
                            else:
                                # Produto do parquet: INSERT (sobrescreve)
                                if save_product(
                                    engine, produto['cod_consinco'],
                                    edit_desc.strip().upper(), edit_trans if edit_trans > 0 else None,
                                    edit_emb, edit_status,
                                    st.session_state.get("username", "admin")
                                ):
                                    st.success("✅ Produto customizado salvo no banco!")
                                    del st.session_state.confirmar_alteracao
                                    del st.session_state.produto_editar
                                    st.rerun()
                
                if btn_excluir:
                    if produto.get('origem') != 'Banco':
                        st.error("❌ Não é possível excluir produtos do parquet!")
                    else:
                        if "confirmar_exclusao" not in st.session_state:
                            st.session_state.confirmar_exclusao = True
                            st.error("⚠️ ATENÇÃO: Este produto será EXCLUÍDO do banco de dados!")
                            st.warning("Clique novamente em 'Excluir Produto' para confirmar.")
                        else:
                            if delete_product(engine, produto['cod_consinco']):
                                st.success("✅ Produto excluído com sucesso!")
                                del st.session_state.confirmar_exclusao
                                del st.session_state.produto_editar
                                st.rerun()
    
    # ========================================================================
    # TAB 3: LISTAR TODOS OS PRODUTOS
    # ========================================================================
    with tab3:
        st.subheader("Lista de Produtos")
        
        col_filtro1, col_filtro2 = st.columns([3, 1])
        
        with col_filtro1:
            filtro_desc = st.text_input("Filtrar por descrição:", key="filtro_lista")
        
        with col_filtro2:
            filtro_status = st.selectbox(
                "Status:",
                options=["Todos", "Ativos (A)", "Suspensos (S)"]
            )
        
        if st.button("🔄 Carregar/Atualizar Lista"):
            df_produtos = load_all_products(engine)
            
            if not df_produtos.empty:
                # Aplicar filtros
                if filtro_desc:
                    df_produtos = df_produtos[
                        df_produtos['descricao'].str.contains(filtro_desc.upper(), na=False)
                    ]
                
                if filtro_status == "Ativos (A)":
                    df_produtos = df_produtos[df_produtos['Mix'] == 'A']
                elif filtro_status == "Suspensos (S)":
                    df_produtos = df_produtos[df_produtos['Mix'] == 'S']
                
                # Exibir
                st.dataframe(
                    df_produtos[[
                        'cod_consinco', 'descricao', 'transicao', 
                        'Emb', 'Mix', 'origem'
                    ]],
                    column_config={
                        "cod_consinco": "Código Consinco",
                        "descricao": "Descrição",
                        "transicao": "Transição",
                        "Emb": "Embalagem",
                        "Mix": "Status",
                        "origem": "Origem"
                    },
                    hide_index=True,
                    use_container_width=True
                )
                
                st.info(f"📊 Total: {len(df_produtos)} produto(s)")
                
                # Download
                csv = df_produtos.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 Baixar Lista (CSV)",
                    data=csv,
                    file_name=f"produtos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
            else:
                st.info("Nenhum produto encontrado.")
