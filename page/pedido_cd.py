import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import datetime, date

# --- Funções de Chamado (Copiado de contato.py) ---
def create_new_ticket(engine, username, assunto, mensagem):
    """Cria um novo ticket e a primeira mensagem."""
    now = datetime.now()
    try:
        with engine.begin() as conn: # Inicia uma transação
            # 1. Cria o chamado
            query_ticket = text("""
                INSERT INTO contato_chamados (usuario_username, assunto, data_criacao, ultimo_update, status)
                VALUES (:username, :assunto, :now, :now, 'Aguardando Retorno')
                RETURNING id;
            """)
            result = conn.execute(query_ticket, {"username": username, "assunto": assunto, "now": now})
            new_ticket_id = result.scalar_one()
            
            # 2. Insere a primeira mensagem
            query_msg = text("""
                INSERT INTO contato_mensagens (chamado_id, remetente_username, mensagem, data_envio)
                VALUES (:chamado_id, :username, :mensagem, :now)
            """)
            conn.execute(query_msg, {
                "chamado_id": new_ticket_id,
                "username": username,
                "mensagem": mensagem,
                "now": now
            })
        return True, new_ticket_id
    except Exception as e:
        return False, f"Erro ao criar chamado: {e}"

# --- Funções de Banco de Dados ---
def search_product_by_code(engine, code):
    """Busca um produto na tabela 'mix_produtos' pelo código interno ou EAN."""
    query = text("""
        SELECT * FROM mix_produtos 
        WHERE CAST(codigo_interno AS TEXT) = :code OR CAST(codigo_ean AS TEXT) = :code
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"code": str(code)})
    return df

def get_product_history(engine, code):
    """Busca o histórico de solicitações de um produto."""
    query = text("SELECT * FROM historico_solicitacoes WHERE CAST(cod_interno AS TEXT) = :code")
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"code": str(code)})
    return df

def get_future_offers(engine, code):
    """Busca ofertas futuras para um produto."""
    today = date.today()
    query = text("""
        SELECT oferta, data_inicio, data_final FROM ofertas 
        WHERE CAST(cod_interno AS TEXT) = :code AND data_final >= :today
        ORDER BY data_inicio
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"code": str(code), "today": today})
    return df

def save_pedido_consolidado(engine, pedido_df):
    """Salva os dados do pedido na tabela de consolidados."""
    try:
        with engine.begin() as conn:
            pedido_df.to_sql('pedidos_consolidados', con=conn, if_exists='append', index=False)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar o pedido: {e}")
        return False

# --- Lógica da Página ---
def show_pedidos_cd_page(engine, base_data_path):
    st.title("📝 Pedidos via CD (Mix Ativo)")
    st.markdown("Busque pelo Código Interno ou EAN para fazer um pedido do mix ativo.")

    # Inicializa o estado da sessão para o item pesquisado
    if 'searched_item' not in st.session_state:
        st.session_state.searched_item = None
    if 'pedido_details' not in st.session_state:
        st.session_state.pedido_details = {}
        
    # Definindo a lista global de lojas que será usada para salvar o pedido
    LISTA_LOJAS_GLOBAL = ['001', '002', '003', '004', '005', '006', '007', '008', '011', '012', '013', '014', '017', '018']

    # --- Formulário de Busca ---
    with st.form("search_form"):
        code_input = st.text_input("Digite o Código Interno ou EAN do produto:")
        submitted = st.form_submit_button("Buscar Produto")
        if submitted and code_input:
            st.session_state.searched_item = None # Limpa busca anterior
            st.session_state.pedido_details = {}
            
            with st.spinner("Buscando..."):
                product_df = search_product_by_code(engine, code_input)
                if not product_df.empty:
                    st.session_state.searched_item = product_df.iloc[0].to_dict()
                else:
                    st.warning("Produto não encontrado na base de dados (mix_produtos).")

    # --- Exibição do Produto e Pedido ---
    if st.session_state.searched_item:
        item = st.session_state.searched_item
        codigo_produto = str(item['cod_interno'])

        st.markdown("---")
        st.subheader(f"Produto Encontrado: {item.get('nome_produto', 'N/A')}")
        col1, col2, col3 = st.columns(3)
        col1.metric("Código Interno", codigo_produto)
        col2.metric("EAN", str(item.get('codigo_ean', 'N/A')))
        col3.metric("Embalagem Separação", str(item.get('embseparacao', 'N/A')))

        # Abas com informações adicionais
        tab1, tab2 = st.tabs(["Histórico de Solicitações", "Ofertas Futuras"])
        with tab1:
            history_df = get_product_history(engine, codigo_produto)
            if not history_df.empty:
                st.dataframe(history_df, use_container_width=True)
            else:
                st.info("Este produto não possui histórico de pedidos. Você pode ser o primeiro a solicitar!")
                # Cria um DataFrame vazio com a estrutura esperada para manter a consistência da UI
                lojas_cols = [f"loja_{loja}" for loja in LISTA_LOJAS_GLOBAL]
                placeholder_cols = ['cod_interno', 'nome_produto'] + lojas_cols
                placeholder_df = pd.DataFrame(columns=placeholder_cols)
                placeholder_df.loc[0] = [codigo_produto, item.get('nome_produto', 'N/A')] + [0] * len(lojas_cols)
                st.dataframe(placeholder_df, hide_index=True, use_container_width=True)
        
        with tab2:
            offers_df = get_future_offers(engine, codigo_produto)
            if not offers_df.empty:
                st.dataframe(offers_df, use_container_width=True)
            else:
                st.info("Nenhuma oferta futura cadastrada para este item.")

        st.markdown("---")
        st.subheader("Digite as quantidades por loja (em caixas):")

        # --- Formulário de Pedido ---
        lojas_acesso = st.session_state.get("lojas_acesso", [])
        if not lojas_acesso:
            st.error("Você não tem lojas associadas ao seu perfil. Contate um administrador.")
            return

        with st.form("pedido_form"):
            pedido_inputs = {}
            for loja in lojas_acesso:
                pedido_inputs[loja] = st.number_input(
                    f"Loja {loja}", min_value=0, step=1, 
                    key=f"loja_{loja}_{codigo_produto}" # Chave única para evitar conflitos
                )
            
            total_cx = sum(pedido_inputs.values())
            st.metric("Total de Caixas", total_cx)

            if st.form_submit_button("Enviar para Aprovação"):
                if total_cx > 0:
                    pedido_data = {
                        "cod_interno": [codigo_produto],
                        "nome_produto": [item.get('nome_produto', 'N/A')],
                        "codigo_ean": [item.get('codigo_ean', 'N/A')],
                        "embseparacao": [item.get('embseparacao', 0)],
                        "data_pedido": [datetime.now()],
                        "usuario_pedido": [st.session_state.get('username', 'unknown')],
                        "status_item": ["Pendente"],
                        "status_aprovacao": ["Pendente"],
                        "total_cx": [total_cx]
                    }
                    for loja in LISTA_LOJAS_GLOBAL:
                        col_name = f"loja_{loja}"
                        pedido_data[col_name] = [pedido_inputs.get(loja, 0)]
                    
                    df_to_save = pd.DataFrame(pedido_data)

                    if save_pedido_consolidado(engine, df_to_save):
                        st.success("Pedido enviado com sucesso para aprovação!")
                        st.session_state.searched_item = None # Limpa para nova busca
                        st.session_state.pedido_details = {}
                        st.rerun()
                else:
                    st.warning("Nenhuma quantidade foi digitada. O pedido não foi enviado.")

    # --- Componente de Chamado ---
    st.markdown("---")
    with st.expander("❔ Precisa de ajuda ou quer fazer uma observação? Abra um chamado."):
        with st.form("chamado_form_cd", clear_on_submit=True):
            mensagem = st.text_area("Digite sua mensagem para o administrador:")
            if st.form_submit_button("Enviar Chamado"):
                if mensagem:
                    username = st.session_state.get('username', 'unknown')
                    # Assunto padrão para identificar a origem
                    assunto = f"Chamado via Tela de Pedido por Código"
                    success, message = create_new_ticket(engine, username, assunto, mensagem)
                    if success:
                        st.success("Chamado enviado com sucesso! Você pode acompanhar na tela de Contato.")
                    else:
                        st.error(f"Não foi possível enviar o chamado: {message}")
                else:
                    st.warning("Por favor, digite uma mensagem antes de enviar.")