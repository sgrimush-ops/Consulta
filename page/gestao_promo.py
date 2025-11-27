import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import datetime, date
from page import (
    resolve_ofertas_codigo_col,
    resolve_mix_codigo_col,
    resolve_mix_descricao_col,
    resolve_mix_emb_col,
    resolve_pedidos_codigo_col,
    resolve_pedidos_descricao_col,
    resolve_pedidos_emb_col,
    has_table_column,
)

# --- Funções de Chamado (Copiado de contato.py) ---


def create_new_ticket(engine, username, assunto, mensagem):
    """Cria um novo ticket e a primeira mensagem."""
    now = datetime.now()
    try:
        with engine.begin() as conn:  # Inicia uma transação
            # 1. Cria o chamado
            query_ticket = text(
                """
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
                    """
            )
            result = conn.execute(
                query_ticket,
                {"username": username, "assunto": assunto, "now": now},
            )
            new_ticket_id = result.scalar_one()

            # 2. Insere a primeira mensagem
            query_msg = text(
                """
                    INSERT INTO contato_mensagens (
                        chamado_id,
                        remetente_username,
                        mensagem,
                        data_envio
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


# --- Funções de Banco de Dados ---


def get_active_and_future_promos(engine):
    """
    Busca ofertas ativas/futuras e junta com detalhes dos produtos.
    """
    today = date.today()
    ofertas_col = resolve_ofertas_codigo_col(engine)
    mix_code = resolve_mix_codigo_col(engine)
    mix_desc = resolve_mix_descricao_col(engine)
    mix_emb = resolve_mix_emb_col(engine)
    emb_select = (
        f", m.{mix_emb} AS embseparacao"
        if mix_emb
        else ", NULL::INTEGER AS embseparacao"
    )
    query = text(
        f"""
        SELECT
            m.{mix_code} AS codigo_interno,
            m.{mix_desc} AS descricao,
            m.codigo_ean
            {emb_select},
            o.oferta,
            o.data_inicio,
            o.data_final
        FROM ofertas AS o
        JOIN mix_produtos AS m
            ON CAST(o.{ofertas_col} AS TEXT) = CAST(m.{mix_code} AS TEXT)
        WHERE o.data_final >= :today AND m.estoque_cd > 0
        ORDER BY o.data_inicio, m.{mix_desc}
        """
    )
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"today": today})

    # Debug: mostra aviso se coluna não foi encontrada
    if mix_emb is None:
        st.warning(
            "⚠️ Coluna de embalagem não encontrada em mix_produtos. "
            "Verifique se existe 'embseparacao', 'emb_separacao', "
            "'embalagem' ou 'emb' no banco."
        )

    # Garante que embseparacao seja inteiro (0 se NULL)
    if "embseparacao" in df.columns:
        df["embseparacao"] = (
            pd.to_numeric(df["embseparacao"], errors="coerce")
            .fillna(0)
            .astype(int)
        )
    return df


def save_promo_pedidos(engine, pedidos_df):
    """Salva múltiplos pedidos da tela de gestão de promoções."""
    try:
        # Ajusta colunas para tabela real de pedidos_consolidados
        pedidos_code_col = resolve_pedidos_codigo_col(engine)
        pedidos_desc_col = resolve_pedidos_descricao_col(engine)
        pedidos_emb_col = resolve_pedidos_emb_col(engine)

        rename_map = {}
        if pedidos_code_col != "codigo_interno":
            rename_map["codigo_interno"] = pedidos_code_col
        if pedidos_desc_col != "descricao":
            rename_map["descricao"] = pedidos_desc_col
        if pedidos_emb_col and pedidos_emb_col != "embseparacao":
            rename_map["embseparacao"] = pedidos_emb_col

        df_real = pedidos_df.rename(columns=rename_map)
        if not pedidos_emb_col and "embseparacao" in df_real.columns:
            df_real = df_real.drop(columns=["embseparacao"])  # compat

        # Compat: preencher coluna 'codigo' quando existir
        try:
            if has_table_column(
                engine, "pedidos_consolidados", "codigo"
            ) and "codigo" not in df_real.columns:
                code_col = (
                    pedidos_code_col
                    if pedidos_code_col in df_real.columns
                    else "codigo_interno"
                )
                if code_col in df_real.columns:
                    df_real["codigo"] = df_real[code_col]
        except Exception:
            pass

        # Compat: colunas legadas de descrição
        try:
            desc_source = None
            for cand in [
                pedidos_desc_col,
                "descricao",
                "produto",
                "nome_produto",
            ]:
                if cand and cand in df_real.columns:
                    desc_source = cand
                    break

            if desc_source:
                for legacy_col in ["produto", "nome_produto", "descricao"]:
                    if (
                        has_table_column(
                            engine, "pedidos_consolidados", legacy_col
                        )
                        and legacy_col not in df_real.columns
                    ):
                        df_real[legacy_col] = df_real[desc_source]
        except Exception:
            pass

        with engine.begin() as conn:
            df_real.to_sql(
                "pedidos_consolidados",
                con=conn,
                if_exists="append",
                index=False,
            )
        return True
    except Exception as e:
        st.error(f"Erro ao salvar os pedidos: {e}")
        return False


# --- Lógica da Página ---


def show_gestao_promo_page(engine, base_data_path):
    st.title("🛍️ Gestão de Pedidos de Promoção")
    st.markdown(
        "Visualize promoções ativas/futuras e digite os pedidos para a loja."
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
            "Você não tem lojas associadas ao seu perfil. "
            "Contate um administrador."
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
        st.warning(
            "Nenhuma promoção ativa ou futura encontrada no banco de dados."
        )
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
            "codigo_ean": st.column_config.TextColumn(
                "EAN", disabled=True
            ),
            "embseparacao": st.column_config.NumberColumn(
                "Emb. (Un/Cx)", disabled=True, format="%d"
            ),
            "oferta": st.column_config.NumberColumn(
                "Preço Oferta", format="R$ %.2f", disabled=True
            ),
            "data_inicio": st.column_config.DateColumn(
                "Início", disabled=True
            ),
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
                # Garante conversão de embseparacao para inteiro
                emb_val = row.get("embseparacao")
                if pd.isna(emb_val) or emb_val is None:
                    emb_val = 0
                else:
                    emb_val = int(emb_val)

                pedido_dict = {
                    "codigo_interno": str(row["codigo_interno"]),
                    "descricao": row["descricao"],
                    "codigo_ean": str(row.get("codigo_ean", "")),
                    "embseparacao": emb_val,
                    "data_pedido": datetime.now(),
                    "usuario_pedido": username,
                    "status_item": "Pendente",
                    "status_aprovacao": "Pendente",
                    "total_cx": row["Qtde Caixas"],
                }
                # Adiciona colunas de todas as lojas
                for loja_global in LISTA_LOJAS_GLOBAL:
                    col_name = f"loja_{loja_global}"
                    pedido_dict[col_name] = (
                        row["Qtde Caixas"]
                        if loja_global == selected_loja
                        else 0
                    )

                pedidos_list.append(pedido_dict)

            df_final = pd.DataFrame(pedidos_list)

            with st.spinner("Salvando pedidos..."):
                if save_promo_pedidos(engine, df_final):
                    st.success(
                        "Pedidos com quantidade > 0 enviados para aprovação!"
                    )
                    st.balloons()
                else:
                    st.error(
                        "Falha ao salvar os pedidos. "
                        "Verifique os logs de erro."
                    )
        else:
            st.warning(
                "Nenhuma quantidade foi digitada. Nenhum pedido foi enviado."
            )

    st.markdown("---")
    st.info(
        "Se não há produtos: podem não pertencer ao CD15 "
        "ou não há estoque (> 0)."
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
                            "Chamado enviado com sucesso! "
                            "Acompanhe na tela de Contato."
                        )
                    else:
                        st.error(
                            f"Não foi possível enviar o chamado: {message}"
                        )
                else:
                    st.warning(
                        "Por favor, digite uma mensagem antes de enviar."
                    )
