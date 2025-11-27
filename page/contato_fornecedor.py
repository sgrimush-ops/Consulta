import streamlit as st
from sqlalchemy import text
from datetime import datetime
import pandas as pd


# =========================================================
# FUNÇÕES DE BANCO DE DADOS
# =========================================================


def get_fornecedor_tickets(engine, username):
    """Busca os tickets de um fornecedor específico."""
    query = text("""
        SELECT id, assunto, status, ultimo_update
        FROM contato_chamados
        WHERE usuario_username = :username
        ORDER BY ultimo_update DESC
    """)
    with engine.connect() as conn:
        df = pd.read_sql_query(query, conn, params={"username": username})
    return df


def create_fornecedor_ticket(engine, username, assunto, mensagem):
    """Cria um novo ticket para fornecedor."""
    now = datetime.now()
    try:
        with engine.begin() as conn:
            # 1. Cria o chamado
            query_ticket = text("""
                INSERT INTO contato_chamados (
                    usuario_username,
                    assunto,
                    data_criacao,
                    ultimo_update,
                    status
                )
                VALUES (:username, :assunto, :now, :now,
                    'Aguardando Retorno')
                RETURNING id;
            """)
            result = conn.execute(
                query_ticket,
                {"username": username, "assunto": assunto, "now": now}
            )
            new_ticket_id = result.scalar_one()

            # 2. Insere a primeira mensagem
            query_msg = text("""
                INSERT INTO contato_mensagens (
                    chamado_id,
                    remetente_username,
                    mensagem,
                    data_envio
                )
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


def get_ticket_messages(engine, ticket_id):
    """Busca todas as mensagens de um ticket específico."""
    query = text("""
        SELECT remetente_username, mensagem, data_envio
        FROM contato_mensagens
        WHERE chamado_id = :ticket_id
        ORDER BY data_envio ASC
    """)
    with engine.connect() as conn:
        df = pd.read_sql_query(query, conn, params={"ticket_id": ticket_id})
    return df


def add_message_to_ticket(engine, ticket_id, username, mensagem,
                          new_status):
    """Adiciona uma nova mensagem e atualiza o status do ticket."""
    now = datetime.now()
    try:
        with engine.begin() as conn:
            # 1. Adiciona a mensagem
            query_msg = text("""
                INSERT INTO contato_mensagens (
                    chamado_id,
                    remetente_username,
                    mensagem,
                    data_envio
                )
                VALUES (:chamado_id, :username, :mensagem, :now)
            """)
            conn.execute(query_msg, {
                "chamado_id": ticket_id,
                "username": username,
                "mensagem": mensagem,
                "now": now
            })

            # 2. Atualiza o ticket
            query_ticket = text("""
                UPDATE contato_chamados
                SET status = :status, ultimo_update = :now
                WHERE id = :ticket_id
            """)
            conn.execute(query_ticket, {
                "status": new_status,
                "now": now,
                "ticket_id": ticket_id
            })
        return True
    except Exception as e:
        st.error(f"Erro ao enviar mensagem: {e}")
        return False


def get_ticket_info(engine, ticket_id):
    """Busca informações básicas do ticket."""
    query = text("""
        SELECT usuario_username, assunto, status
        FROM contato_chamados
        WHERE id = :ticket_id
    """)
    with engine.connect() as conn:
        result = conn.execute(query, {"ticket_id": ticket_id})
        data = result.fetchone()
        if data:
            return {
                "usuario_username": data[0],
                "assunto": data[1],
                "status": data[2]
            }
    return None


# =========================================================
# INTERFACE DA PÁGINA
# =========================================================


def show_chat_view_fornecedor(engine, ticket_id, username):
    """Mostra a interface de chat para um ticket selecionado."""

    # Busca informações do ticket
    ticket_info = get_ticket_info(engine, ticket_id)
    if not ticket_info:
        st.error("Ticket não encontrado.")
        return

    st.markdown(f"### 💬 {ticket_info['assunto']}")
    st.caption(f"Status: {ticket_info['status']}")

    col1, col2 = st.columns([1, 4])

    with col1:
        if st.button("← Voltar"):
            if 'selected_ticket_id_fornecedor' in st.session_state:
                del st.session_state['selected_ticket_id_fornecedor']
            st.rerun()

    messages = get_ticket_messages(engine, ticket_id)

    # Exibe o histórico de chat
    for _, row in messages.iterrows():
        # Verifica se é mensagem do fornecedor ou do admin
        is_fornecedor = row['remetente_username'] == username
        avatar = "📦" if is_fornecedor else "🛡️"

        with st.chat_message(
            row['remetente_username'],
            avatar=avatar
        ):
            st.write(row['mensagem'])
            st.caption(
                f"Enviado em: "
                f"{row['data_envio'].strftime('%d/%m/%Y %H:%M')}"
            )

    # Input para nova mensagem
    prompt = st.chat_input("Digite sua resposta...")
    if prompt:
        new_status = "Aguardando Retorno"

        if add_message_to_ticket(
            engine,
            ticket_id,
            username,
            prompt,
            new_status
        ):
            st.rerun()
        else:
            st.error("Não foi possível enviar sua mensagem.")


def show_contato_fornecedor_page(engine):
    """Página de contato para fornecedores."""
    st.title("📞 Contato / Suporte")

    username = st.session_state.get("fornecedor_username", "")

    if 'selected_ticket_id_fornecedor' in st.session_state:
        ticket_id = st.session_state['selected_ticket_id_fornecedor']
        show_chat_view_fornecedor(engine, ticket_id, username)

    else:
        # Seção para criar novo chamado
        st.subheader("✉️ Novo Chamado")
        st.markdown(
            "Use este formulário para entrar em contato com o "
            "suporte ou tirar dúvidas sobre pedidos."
        )

        with st.form("new_fornecedor_ticket_form", clear_on_submit=True):
            assunto = st.text_input(
                "Assunto",
                placeholder="Ex: Dúvida sobre pedido, Problema no sistema..."
            )
            mensagem = st.text_area(
                "Sua Mensagem",
                placeholder="Descreva sua dúvida ou problema..."
            )

            if st.form_submit_button("Enviar Mensagem", type="primary"):
                if assunto and mensagem:
                    success, new_id = create_fornecedor_ticket(
                        engine,
                        username,
                        assunto,
                        mensagem
                    )
                    if success:
                        st.session_state['selected_ticket_id_fornecedor'] = (
                            new_id
                        )
                        st.success("Chamado criado com sucesso!")
                        st.rerun()
                    else:
                        st.error(f"Erro: {new_id}")
                else:
                    st.warning(
                        "Por favor, preencha o assunto e a mensagem."
                    )

        st.markdown("---")
        st.subheader("📋 Meus Chamados")

        df_fornecedor_tickets = get_fornecedor_tickets(engine, username)

        if df_fornecedor_tickets.empty:
            st.info("Você ainda não abriu nenhum chamado.")
        else:
            st.write("Clique em 'Ver' para abrir a conversa.")

            for _, row in df_fornecedor_tickets.iterrows():
                # Colorir status
                status = row['status']
                if status == 'Aguardando Retorno':
                    status_colorido = f":orange[{status}]"
                else:
                    status_colorido = f":blue[{status}]"

                col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                col1.text(row['assunto'])
                col2.markdown(status_colorido, unsafe_allow_html=True)
                col3.text(row['ultimo_update'].strftime('%d/%m/%Y'))
                if col4.button("Ver", key=f"view_forn_{row['id']}"):
                    st.session_state['selected_ticket_id_fornecedor'] = (
                        row['id']
                    )
                    st.rerun()
