import streamlit as st
import pandas as pd
import os
from sqlalchemy import text
from utils.timezone import now_brazil

# --- Funções de Chamado ---


def create_new_ticket(engine, username, assunto, mensagem):
    """Cria um novo ticket e a primeira mensagem."""
    now = now_brazil()
    try:
        with engine.begin() as conn:
            query_ticket = text(
                """
                INSERT INTO contato_chamados (
                    usuario_username,
                    assunto,
                    data_criacao,
                    ultimo_update,
                    status
                )
                VALUES (:username, :assunto, :now, :now, 'Aguardando Retorno')
                RETURNING id;
            """
            )
            result = conn.execute(
                query_ticket, {"username": username, "assunto": assunto, "now": now}
            )
            new_ticket_id = result.scalar_one()

            query_msg = text(
                """
                INSERT INTO contato_mensagens (
                    chamado_id, remetente_username, mensagem, data_envio
                )
                VALUES (:chamado_id, :username, :mensagem, :now)
            """
            )
            conn.execute(
                query_msg,
                {
                    "chamado_id": new_ticket_id,
                    "username": username,
                    "mensagem": mensagem,
                    "now": now,
                },
            )
        return True, new_ticket_id
    except Exception as e:
        return False, f"Erro ao criar chamado: {e}"


# --- Funções de Carregamento de Dados ---


def get_correcoes_embalagens(engine):
    """Busca correções de embalagens do banco de dados."""
    try:
        query = text("""
            SELECT cod_consinco, embalagem_corrigida
            FROM produtos_correcoes
        """)
        
        with engine.connect() as conn:
            df = pd.read_sql(query, conn)
        
        return df
    except Exception:
        # Tabela não existe ou erro
        return pd.DataFrame()


def load_products_from_parquet(engine=None):
    """Carrega produtos do arquivo parquet e aplica correções do banco."""
    parquet_path = os.path.join("bdados", "con5cod.parquet")
    
    if not os.path.exists(parquet_path):
        return pd.DataFrame()
    
    try:
        df = pd.read_parquet(parquet_path)
        
        # Mapear colunas novas para nomes esperados
        column_mapping = {
            'codigoconsinco': 'cod_consinco',
            'Código Produto': 'cod_consinco',
            'codigo transicao': 'transicao',
            'CODACESSO': 'transicao',
            'Empresa : Produto': 'descricao',
            'embalagem': 'Emb',
            'EmbSeparacao': 'Emb',
            'ltmix': 'Mix',
            'capacidade': 'CapacidadeGondola',
            'CapacidadeGondola': 'CapacidadeGondola'
        }
        
        df.rename(columns=column_mapping, inplace=True)
        
        # Garantir colunas essenciais com valores padrao se ausentes
        if 'cod_consinco' not in df.columns:
            raise ValueError("Coluna 'cod_consinco' ou 'Código Produto' não encontrada no arquivo")
        if 'descricao' not in df.columns:
            df['descricao'] = 'SEM DESCRIÇÃO'
        if 'transicao' not in df.columns:
            df['transicao'] = 0
        if 'Emb' not in df.columns:
            df['Emb'] = 1
        if 'Mix' not in df.columns:
            df['Mix'] = 'A'
        if 'CapacidadeGondola' not in df.columns:
            df['CapacidadeGondola'] = 0
        
        # Garantir que cod_consinco é inteiro
        df['cod_consinco'] = df['cod_consinco'].astype(int)
        
        # Aplicar correções de embalagens se engine disponível
        if engine is not None:
            df_correcoes = get_correcoes_embalagens(engine)
            if not df_correcoes.empty:
                # Mesclar correções
                df = df.merge(
                    df_correcoes, 
                    on='cod_consinco', 
                    how='left'
                )
                # Usar embalagem corrigida se existir, senão usar original
                df['Emb'] = df['embalagem_corrigida'].fillna(df['Emb']).astype(int)
                df = df.drop(columns=['embalagem_corrigida'])
        
        return df
    except Exception as e:
        st.error(f"Erro ao carregar produtos: {e}")
        return pd.DataFrame()


def search_product(df_produtos, search_term, search_type='codigo'):
    """
    Busca produto por código ou descrição.
    
    Args:
        df_produtos: DataFrame com produtos
        search_term: Termo de busca
        search_type: 'codigo' ou 'descricao'
    
    Returns:
        DataFrame com resultados da busca
    """
    if df_produtos.empty:
        return pd.DataFrame()
    
    if search_type == 'codigo':
        try:
            cod = int(search_term)
            # Busca por cod_consinco ou transicao
            result = df_produtos[
                (df_produtos['cod_consinco'] == cod) |
                (df_produtos['transicao'] == cod)
            ]
            return result
        except ValueError:
            return pd.DataFrame()
    else:  # descrição
        # Busca case-insensitive na descrição
        mask = df_produtos['descricao'].str.contains(
            search_term, case=False, na=False
        )
        return df_produtos[mask]


def save_pedido_consolidado(engine, df_pedido):
    """Salva pedido no banco de dados."""
    try:
        with engine.begin() as conn:
            df_pedido.to_sql(
                "pedidos_consolidados",
                conn,
                if_exists="append",
                index=False,
                method="multi",
            )
        return True
    except Exception as e:
        st.error(f"Erro ao salvar pedido: {e}")
        return False


def get_orders_history_30d_cd(engine, username):
    """Retorna historico de pedidos CD dos ultimos 30 dias."""
    query = text(
        """
        SELECT
            id,
            codigo_interno,
            descricao,
            embseparacao,
            total_cx,
            TO_CHAR(data_pedido, 'DD/MM/YYYY HH24:MI') AS data_pedido,
            status_aprovacao,
            COALESCE(origem_pedido, 'Pedido por Código (CD)') AS origem_pedido
        FROM pedidos_consolidados
        WHERE usuario_pedido = :username
                    AND data_pedido >= (
                            CURRENT_TIMESTAMP AT TIME ZONE 'America/Sao_Paulo'
                    ) - INTERVAL '30 days'
          AND COALESCE(origem_pedido, 'Pedido por Código (CD)') = 'Pedido por Código (CD)'
        ORDER BY data_pedido DESC
        """
    )
    with engine.connect() as conn:
        return pd.read_sql(query, conn, params={"username": username})


def get_same_day_item_orders_cd(engine, username, codigo_produto):
    """Retorna quantidade de lançamentos e total de caixas do item no dia."""
    query = text(
        """
        SELECT
            COUNT(*) AS qtd_lancamentos,
            COALESCE(SUM(total_cx), 0) AS total_cx
        FROM pedidos_consolidados
        WHERE usuario_pedido = :username
          AND codigo_interno = :codigo
          AND COALESCE(origem_pedido, 'Pedido por Código (CD)')
              IN ('Pedido por Código (CD)', 'CD15', 'CD16')
          AND data_pedido >= DATE_TRUNC(
              'day',
              CURRENT_TIMESTAMP AT TIME ZONE 'America/Sao_Paulo'
          )
          AND data_pedido < DATE_TRUNC(
              'day',
              CURRENT_TIMESTAMP AT TIME ZONE 'America/Sao_Paulo'
          ) + INTERVAL '1 day'
        """
    )

    try:
        with engine.connect() as conn:
            row = conn.execute(
                query,
                {
                    "username": username,
                    "codigo": str(codigo_produto),
                },
            ).fetchone()

        if not row:
            return {"qtd_lancamentos": 0, "total_cx": 0}

        return {
            "qtd_lancamentos": int(row.qtd_lancamentos or 0),
            "total_cx": int(row.total_cx or 0),
        }
    except Exception:
        return {"qtd_lancamentos": 0, "total_cx": 0}


# --- Página Principal ---


def show_pedidos_cd_page(engine, base_data_path):
    """Página de pedidos por código usando arquivo parquet."""
    
    st.title("📦 Pedido por Código (CD)")
    st.markdown("Sistema de pedidos baseado no novo código Consinco")
    
    # Inicializar session_state
    if "searched_item" not in st.session_state:
        st.session_state.searched_item = None
    if "pedido_details" not in st.session_state:
        st.session_state.pedido_details = {}
    if "search_results" not in st.session_state:
        st.session_state.search_results = None
    
    # Lista de lojas
    LISTA_LOJAS_GLOBAL = [
        "001", "002", "003", "004", "005", "006",
        "007", "008", "011", "012", "013", "014", "016", "017", "018"
    ]
    
    # Carregar produtos
    df_produtos = load_products_from_parquet()
    
    if df_produtos.empty:
        st.error("❌ Não foi possível carregar a base de produtos!")
        st.info("Verifique se o arquivo bdados/con5cod.parquet existe.")
        return
    
    # Estatísticas do mix
    total_produtos = len(df_produtos)
    produtos_ativos = len(df_produtos[df_produtos['Mix'] == 'A'])
    produtos_suspensos = len(df_produtos[df_produtos['Mix'] == 'S'])
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total de Produtos", total_produtos)
    col2.metric("Produtos Ativos", produtos_ativos)
    col3.metric("Produtos Suspensos", produtos_suspensos)
    
    st.markdown("---")
    
    # --- Formulário de Busca ---
    st.markdown("### 🔍 Buscar Produto")
    
    with st.form("search_form"):
        search_type = st.radio(
            "Tipo de busca:",
            ["Por Código", "Por Descrição"],
            horizontal=True
        )
        
        if search_type == "Por Código":
            search_term = st.text_input(
                "Digite o código Consinco ou código de transição:",
                placeholder="Ex: 10480",
                max_chars=10
            )
        else:
            search_term = st.text_input(
                "Digite parte da descrição do produto:",
                placeholder="Ex: CERVEJA"
            )
        
        submitted = st.form_submit_button("🔍 Buscar")
        
        if submitted and search_term:
            st.session_state.searched_item = None
            st.session_state.pedido_details = {}
            
            search_mode = 'codigo' if search_type == "Por Código" else 'descricao'
            results = search_product(df_produtos, search_term, search_mode)
            
            if not results.empty:
                if len(results) == 1:
                    # Apenas um resultado, seleciona automaticamente
                    st.session_state.searched_item = results.iloc[0].to_dict()
                    st.session_state.search_results = None
                else:
                    # Múltiplos resultados, armazena para seleção
                    st.session_state.search_results = results
                    st.session_state.searched_item = None
            else:
                st.warning("❌ Nenhum produto encontrado com esse critério.")
                st.session_state.search_results = None
    
    # --- Seleção de Múltiplos Resultados ---
    if st.session_state.search_results is not None and not st.session_state.search_results.empty:
        st.markdown("### 📋 Resultados da Busca")
        st.info(f"Encontrados {len(st.session_state.search_results)} produtos. Selecione um:")
        
        results_display = st.session_state.search_results.copy()
        results_display['Status'] = results_display['Mix'].map({'A': 'Ativo', 'S': 'Suspenso'})
        results_display = results_display[['cod_consinco', 'descricao', 'transicao', 'Status', 'Emb']]
        results_display.columns = ['Código Consinco', 'Descrição', 'Cód. Transição', 'Status', 'Embalagem']
        
        # Usar selectbox para seleção
        selected_idx = st.selectbox(
            "Escolha o produto:",
            range(len(results_display)),
            format_func=lambda i: f"{results_display.iloc[i]['Código Consinco']} - {results_display.iloc[i]['Descrição']}"
        )
        
        if st.button("✅ Confirmar Seleção"):
            st.session_state.searched_item = st.session_state.search_results.iloc[selected_idx].to_dict()
            st.session_state.search_results = None
            st.rerun()
    
    # --- Exibição do Produto e Pedido ---
    if st.session_state.searched_item:
        item = st.session_state.searched_item
        codigo_produto = int(item['cod_consinco'])
        status_mix = item['Mix']
        username = st.session_state.get("username", "unknown")

        same_day_info = get_same_day_item_orders_cd(
            engine, username, codigo_produto
        )
        if same_day_info["qtd_lancamentos"] > 0:
            st.warning(
                "⚠️ Você já lançou este item hoje. "
                f"Lançamentos no dia: {same_day_info['qtd_lancamentos']} | "
                f"Total já lançado: {same_day_info['total_cx']} CX. "
                "Se enviar novamente, os pedidos serão somados."
            )
        
        st.markdown("---")
        st.subheader(f"Produto Selecionado: {item['descricao']}")
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Código Consinco", codigo_produto)
        col2.metric("Cód. Transição", item['transicao'])
        col3.metric("Emb. (Un/Cx)", int(item['Emb']))
        
        # Indicador de status
        if status_mix == 'A':
            col4.success("✅ ATIVO no Mix")
        else:
            col4.warning("⚠️ SUSPENSO no Mix")
        
        st.markdown("---")
        st.subheader("Digite as quantidades por loja (em caixas):")
        
        # Verificar lojas de acesso do usuário
        lojas_acesso = st.session_state.get("lojas_acesso", [])
        if not lojas_acesso:
            st.error("Você não tem lojas associadas ao seu perfil. Contate um administrador.")
            return
        
        # --- Formulário de Pedido ---
        with st.form("pedido_form"):
            pedido_inputs = {}
            
            # Organizar em 3 colunas
            cols_per_row = 3
            cols = st.columns(cols_per_row)
            
            for idx, loja in enumerate(lojas_acesso):
                col_idx = idx % cols_per_row
                with cols[col_idx]:
                    pedido_inputs[loja] = st.number_input(
                        f"Loja {loja}",
                        min_value=0,
                        step=1,
                        key=f"loja_{loja}_{codigo_produto}"
                    )
            
            st.markdown("---")
            total_cx = sum(pedido_inputs.values())
            total_un = total_cx * int(item['Emb'])
            
            col_total1, col_total2 = st.columns(2)
            col_total1.metric("Total de Caixas", total_cx)
            col_total2.metric("Total de Unidades", total_un)

            cd_abastecedor = st.selectbox(
                "CD abastecedor:",
                ["", "CD15", "CD16"],
                index=0,
                key=f"cd_abastecedor_{codigo_produto}"
            )
            
            submitted_pedido = st.form_submit_button("📤 Enviar para Aprovação", type="primary")
            
            if submitted_pedido:
                if not cd_abastecedor:
                    st.warning("⚠️ Pedido não será enviado, informe um CD.")
                elif total_cx > 0:
                    # Verificar se produto está suspenso
                    if status_mix == 'S':
                        st.session_state.pedido_details = {
                            "pedido_inputs": pedido_inputs,
                            "total_cx": total_cx,
                            "codigo_produto": codigo_produto,
                            "item": item,
                            "cd_abastecedor": cd_abastecedor,
                            "aguardando_confirmacao_suspenso": True
                        }
                        st.rerun()
                    else:
                        # Produto ativo, processa diretamente
                        st.session_state.pedido_details = {
                            "pedido_inputs": pedido_inputs,
                            "total_cx": total_cx,
                            "codigo_produto": codigo_produto,
                            "item": item,
                            "cd_abastecedor": cd_abastecedor,
                            "confirmar_pedido": True
                        }
                        st.rerun()
                else:
                    st.warning("Nenhuma quantidade foi digitada. O pedido não foi enviado.")
        
        # --- Confirmação para produto SUSPENSO ---
        if st.session_state.pedido_details.get("aguardando_confirmacao_suspenso", False):
            st.markdown("---")
            st.warning("### ⚠️ ATENÇÃO: Produto SUSPENSO no Mix")
            st.markdown(
                "**Este produto está marcado como SUSPENSO no sistema.**\n\n"
                "Isso significa que ele pode não fazer mais parte do mix regular.\n\n"
                "Deseja mesmo continuar com o pedido?"
            )
            
            col_sim, col_nao = st.columns(2)
            
            with col_sim:
                if st.button("✅ Sim, confirmar pedido", use_container_width=True, type="primary"):
                    st.session_state.pedido_details["confirmar_pedido"] = True
                    st.session_state.pedido_details["aguardando_confirmacao_suspenso"] = False
                    st.rerun()
            
            with col_nao:
                if st.button("❌ Não, cancelar", use_container_width=True):
                    st.session_state.pedido_details = {}
                    st.info("Pedido cancelado.")
                    st.rerun()
        
        # --- Processamento do pedido confirmado ---
        if st.session_state.pedido_details.get("confirmar_pedido", False):
            pedido_inputs = st.session_state.pedido_details["pedido_inputs"]
            total_cx = st.session_state.pedido_details["total_cx"]
            codigo_produto = st.session_state.pedido_details["codigo_produto"]
            item = st.session_state.pedido_details["item"]
            cd_abastecedor = st.session_state.pedido_details.get(
                "cd_abastecedor", "Pedido por Código (CD)"
            )
            
            pedido_data = {
                "codigo_interno": [codigo_produto],
                "descricao": [item['descricao']],
                "ean": [item['transicao']],  # Usando transição como referência
                "embseparacao": [int(item['Emb'])],
                "data_pedido": [now_brazil()],
                "usuario_pedido": [st.session_state.get("username", "unknown")],
                "status_item": ["Pendente"],
                "status_aprovacao": ["Pendente"],
                "total_cx": [total_cx],
                "origem_pedido": [cd_abastecedor],
            }
            
            # Adicionar quantidades por loja
            for loja in LISTA_LOJAS_GLOBAL:
                pedido_data[f"loja_{loja}"] = [pedido_inputs.get(loja, 0)]
            
            df_to_save = pd.DataFrame(pedido_data)
            
            if save_pedido_consolidado(engine, df_to_save):
                st.success("✅ Pedido enviado com sucesso para aprovação!")
                # Limpar para nova busca
                st.session_state.searched_item = None
                st.session_state.pedido_details = {}
                st.session_state.search_results = None
                st.rerun()
    
    # --- Meus Pedidos Pendentes ---
    st.markdown("---")
    st.subheader("📋 Meus Pedidos Pendentes (Aguardando Aprovação)")
    
    username = st.session_state.get("username", "unknown")
    try:
        query_pendentes = text(
            """
            SELECT
                id,
                codigo_interno,
                descricao,
                COALESCE(origem_pedido, 'Pedido por Código (CD)') AS origem_pedido,
                embseparacao,
                total_cx,
                TO_CHAR(data_pedido, 'DD/MM/YYYY HH24:MI') AS data_pedido,
                status_aprovacao
            FROM pedidos_consolidados
            WHERE usuario_pedido = :username
              AND status_aprovacao = 'Pendente'
            ORDER BY data_pedido DESC
            LIMIT 50
            """
        )
        
        with engine.connect() as conn:
            df_pendentes = pd.read_sql(
                query_pendentes, conn, params={"username": username}
            )
        
        if not df_pendentes.empty:
            st.info(f"Você tem {len(df_pendentes)} pedido(s) aguardando aprovação.")
            
            df_pendentes["Excluir"] = False
            
            df_editado = st.data_editor(
                df_pendentes,
                column_config={
                    "id": None,
                    "codigo_interno": st.column_config.NumberColumn(
                        "Código Consinco", disabled=True, format="%d"
                    ),
                    "descricao": st.column_config.TextColumn(
                        "Produto", width="large", disabled=True
                    ),
                    "origem_pedido": st.column_config.TextColumn(
                        "Origem/CD", disabled=True, width="small"
                    ),
                    "embseparacao": st.column_config.NumberColumn(
                        "Emb. (Un/Cx)", disabled=True, format="%d"
                    ),
                    "total_cx": st.column_config.NumberColumn(
                        "Total CX", disabled=True, format="%d"
                    ),
                    "data_pedido": st.column_config.TextColumn(
                        "Data/Hora", disabled=True
                    ),
                    "status_aprovacao": None,
                    "Excluir": st.column_config.CheckboxColumn(
                        "Excluir?", default=False
                    ),
                },
                hide_index=True,
                use_container_width=True,
                key="pendentes_cd_v2",
            )
            
            if st.button("🗑️ Excluir Selecionados", key="btn_excluir_cd_v2"):
                ids_excluir = df_editado[df_editado["Excluir"]]["id"].tolist()
                if ids_excluir:
                    try:
                        with engine.begin() as conn:
                            delete_q = text(
                                """
                                DELETE FROM pedidos_consolidados
                                WHERE id = ANY(:ids)
                                  AND usuario_pedido = :username
                                  AND status_aprovacao = 'Pendente'
                                """
                            )
                            conn.execute(
                                delete_q,
                                {"ids": ids_excluir, "username": username},
                            )
                        st.success(f"{len(ids_excluir)} pedido(s) excluído(s)!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao excluir pedidos: {e}")
                else:
                    st.warning("Nenhum pedido selecionado para exclusão.")
        else:
            st.info("Você não tem pedidos pendentes no momento.")
    except Exception as e:
        st.error(f"Erro ao buscar pedidos pendentes: {e}")
    
    # --- Componente de Chamado ---
    st.markdown("---")
    with st.expander("❔ Precisa de ajuda ou quer fazer uma observação? Abra um chamado."):
        with st.form("chamado_form_cd", clear_on_submit=True):
            mensagem = st.text_area("Digite sua mensagem para o administrador:")
            if st.form_submit_button("Enviar Chamado"):
                if mensagem:
                    username = st.session_state.get("username", "unknown")
                    assunto = "Chamado via Tela de Pedido por Código"
                    success, message = create_new_ticket(
                        engine, username, assunto, mensagem
                    )
                    if success:
                        st.success(
                            "Chamado enviado com sucesso! "
                            "Você pode acompanhar na tela de Contato."
                        )
                    else:
                        st.error(f"Não foi possível enviar o chamado: {message}")
                else:
                    st.warning("Por favor, digite uma mensagem antes de enviar.")

    # --- Historico de Pedidos ---
    st.markdown("---")
    st.subheader("📋 Histórico de Pedidos (Últimos 30 dias)")
    username = st.session_state.get("username", "unknown")
    try:
        df_historico = get_orders_history_30d_cd(engine, username)
        if not df_historico.empty:
            st.info(
                f"Você tem {len(df_historico)} pedido(s) registrados "
                "nos últimos 30 dias."
            )
            st.dataframe(df_historico, hide_index=True, use_container_width=True)
        else:
            st.info("Você não tem histórico de pedidos nos últimos 30 dias.")
    except Exception as e:
        st.error(f"Erro ao buscar histórico de pedidos: {e}")
