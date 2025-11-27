import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import datetime, date

# --- Funções de Chamado (Copiado de contato.py) ---


def create_new_ticket(engine, username, assunto, mensagem):
    """Cria um novo ticket e a primeira mensagem."""
    now = datetime.now()
    try:
        with engine.begin() as conn:  # Inicia uma transação
            # 1. Cria o chamado
            query_ticket = text(
                """
                INSERT INTO contato_chamados (usuario_username, assunto, data_criacao, ultimo_update, status)
                VALUES (:username, :assunto, :now, :now, 'Aguardando Retorno')
                RETURNING id;
            """
            )
            result = conn.execute(
                query_ticket, {"username": username, "assunto": assunto, "now": now}
            )
            new_ticket_id = result.scalar_one()

            # 2. Insere a primeira mensagem
            query_msg = text(
                """
                INSERT INTO contato_mensagens (chamado_id, remetente_username, mensagem, data_envio)
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


# --- Funções de Banco de Dados ---


def get_active_and_future_promos(engine):
    """
    Busca todas as ofertas ativas e futuras e junta com os detalhes dos produtos.
    """
    today = date.today()
    query = text(
        """
        SELECT 
            o.codigo_interno,
            m.produto AS descricao,
            m.ean AS codigo_ean,
            m.embseparacao,
            o.oferta,
            o.data_inicio,
            o.data_final
        FROM ofertas AS o
        JOIN mix_produtos AS m
            ON CAST(o.codigo_interno AS TEXT) = CAST(m.codigo_interno AS TEXT)
        WHERE o.data_final >= :today AND m.estoque_cd > 0
        ORDER BY o.data_inicio, m.produto
    """
    )
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"today": today})
    return df


def save_promo_pedidos(engine, pedidos_df):
    """Salva múltiplos pedidos da tela de gestão de promoções."""
    try:
        with engine.begin() as conn:
            pedidos_df.to_sql(
                "pedidos_consolidados", con=conn, if_exists="append", index=False
            )
        return True
    except Exception as e:
        st.error(f"Erro ao salvar os pedidos: {e}")
        return False


# --- Lógica da Página ---


def show_gestao_promo_page(engine, base_data_path):
    st.title("🛍️ Gestão de Pedidos de Promoção")
    st.markdown(
        "Visualize as promoções ativas/futuras e digite os pedidos para a loja desejada."
    )

    lojas_acesso = st.session_state.get("lojas_acesso", [])
    LISTA_LOJAS_GLOBAL = [
        "001",
        "002",
        "003",
        "004",
        "005",
        "006",
        "007",
        "008",
        "011",
        "012",
        "013",
        "014",
        "017",
        "018",
    ]

    if not lojas_acesso:
        st.error(
            "Você não tem lojas associadas ao seu perfil. Contate um administrador."
        )
        return

    # --- Seletor de Loja ---
    if len(lojas_acesso) > 1:
        selected_loja = st.selectbox(
            "Selecione a loja para digitar os pedidos:",
            lojas_acesso,
            index=None,
            placeholder="Escolha uma loja...",
        )
    else:
        selected_loja = lojas_acesso[0]
        st.info(f"Pedidos para a Loja: **{selected_loja}**")

    if not selected_loja:
        st.info("Por favor, selecione uma loja para começar.")
        return

    # --- Exibição das Promoções ---
    promo_df = get_active_and_future_promos(engine)

    if promo_df.empty:
        st.warning("Nenhuma promoção ativa ou futura encontrada no banco de dados.")
        return

    # Adiciona a coluna editável para a quantidade
    promo_df["Qtde Caixas"] = 0

    st.markdown("---")
    st.subheader(f"Promoções para a Loja {selected_loja}")
    st.info("Digite a quantidade de caixas desejada na coluna 'Qtde Caixas'.")

    # Utiliza o data_editor para permitir a digitação direta
    edited_df = st.data_editor(
        promo_df,
        column_config={
            "codigo_interno": st.column_config.TextColumn(
                "Código Interno", disabled=True
            ),
            "descricao": st.column_config.TextColumn(
                "Produto", width="large", disabled=True
            ),
            "oferta": st.column_config.NumberColumn(
                "Preço Oferta", format="R$ %.2f", disabled=True
            ),
            "data_inicio": st.column_config.DateColumn("Início", disabled=True),
            "data_final": st.column_config.DateColumn("Final", disabled=True),
            "Qtde Caixas": st.column_config.NumberColumn(
                "Qtde Caixas", min_value=0, step=1
            ),
        },
        hide_index=True,
        key=f"promo_editor_{selected_loja}",
    )

    # --- Botão de Envio ---
    if st.button("Enviar Todos os Pedidos para Aprovação", type="primary"):
        pedidos_para_salvar = edited_df[edited_df["Qtde Caixas"] > 0]

        if not pedidos_para_salvar.empty:
            pedidos_list = []
            username = st.session_state.get("username", "unknown")

            for _, row in pedidos_para_salvar.iterrows():
                pedido_dict = {
                    "codigo_interno": str(row["codigo_interno"]),
                    "descricao": row["descricao"],
                    "codigo_ean": str(row.get("codigo_ean", "")),
                    "embseparacao": row.get("embseparacao", 0),
                    "data_pedido": datetime.now(),
                    "usuario_pedido": username,
                    "status_item": "Pendente",
                    "status_aprovacao": "Pendente",
                    "total_cx": row["Qtde Caixas"],
                }
                # Adiciona colunas de todas as lojas, preenchendo a selecionada
                for loja_global in LISTA_LOJAS_GLOBAL:
                    col_name = f"loja_{loja_global}"
                    pedido_dict[col_name] = (
                        row["Qtde Caixas"] if loja_global == selected_loja else 0
                    )

                pedidos_list.append(pedido_dict)

            df_final = pd.DataFrame(pedidos_list)

            with st.spinner("Salvando pedidos..."):
                if save_promo_pedidos(engine, df_final):
                    st.success(
                        "Todos os pedidos com quantidade maior que zero foram enviados para aprovação!"
                    )
                    st.balloons()
                    # A lógica de resetar o estado pode ser complexa com data_editor,
                    # por isso, uma abordagem simples é deixar os valores digitados
                    # para que o usuário possa ajustar se necessário. Um st.rerun() pode ser útil
                    # se quisermos forçar uma recarga completa.
                else:
                    st.error("Falha ao salvar os pedidos. Verifique os logs de erro.")
        else:
            st.warning("Nenhuma quantidade foi digitada. Nenhum pedido foi enviado.")

    st.markdown("---")
    st.info(
        "Caso não tenha produtos em oferta para digitar, é porque eles não pertencem ao estoque abastecido pelo CD15 ou não há estoque disponível (> 0)."
    )

    # --- Componente de Chamado ---
    with st.expander(
        "❔ Precisa de ajuda ou quer fazer uma observação? Abra um chamado."
    ):
        with st.form("chamado_form_promo", clear_on_submit=True):
            mensagem = st.text_area(
                "Digite sua mensagem para o administrador:", key="msg_promo"
            )
            if st.form_submit_button("Enviar Chamado"):
                if mensagem:
                    username = st.session_state.get("username", "unknown")
                    assunto = "Chamado via Tela de Gestão de Promoções"
                    success, message = create_new_ticket(
                        engine, username, assunto, mensagem
                    )
                    if success:
                        st.success(
                            "Chamado enviado com sucesso! Você pode acompanhar na tela de Contato."
                        )
                    else:
                        st.error(f"Não foi possível enviar o chamado: {message}")
                else:
                    st.warning("Por favor, digite uma mensagem antes de enviar.")
