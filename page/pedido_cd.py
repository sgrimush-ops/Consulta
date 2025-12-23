import streamlit as st
import pandas as pd
from sqlalchemy import text
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
                query_ticket, {"username": username,
                               "assunto": assunto, "now": now}
            )
            new_ticket_id = result.scalar_one()

            # 2. Insere a primeira mensagem
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


# --- Funções de Banco de Dados ---


def search_product_by_code(engine, code):
    """Busca um produto na tabela 'mix_produtos' pelo código interno ou EAN."""
    code_col = resolve_mix_codigo_col(engine)
    query = text(
        f"""
        SELECT * FROM mix_produtos
        WHERE CAST({code_col} AS TEXT) = :code
           OR CAST(codigo_ean AS TEXT) = :code
    """
    )
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"code": str(code)})
    return df


def get_product_history(engine, code):
    """Busca histórico derivado de `pedidos_consolidados` para o produto.

    Remove a dependência da tabela `historico_solicitacoes` e reconstrói
    uma visão de histórico a partir dos pedidos salvos, expandindo as colunas
    por loja (loja_XXX) em linhas.
    """
    pedidos_code_col = resolve_pedidos_codigo_col(engine)
    pedidos_desc_col = resolve_pedidos_descricao_col(engine)
    pedidos_emb_col = resolve_pedidos_emb_col(engine)

    base_cols = [
        pedidos_code_col,
        pedidos_desc_col,
        "codigo_ean",
        pedidos_emb_col,
        "data_pedido",
        "usuario_pedido",
        "status_item",
        "status_aprovacao",
        "total_cx",
    ]

    # Monta SELECT tolerante: algumas colunas podem não existir
    select_cols_sql = ", ".join(
        [c for c in base_cols]
    )
    query = text(
        f"""
        SELECT {select_cols_sql}, *
        FROM pedidos_consolidados
        WHERE CAST({pedidos_code_col} AS TEXT) = :code
        ORDER BY data_pedido DESC
        """
    )

    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"code": str(code)})

    if df.empty:
        return df

    # Detecta colunas de lojas
    loja_cols = [c for c in df.columns if c.startswith("loja_")]
    if not loja_cols:
        # Sem colunas de loja: retorna visão compacta do consolidado
        # com nomes normalizados.
        out = df.copy()
        # Normaliza nomes para a UI
        if pedidos_code_col != "codigo_interno" and pedidos_code_col in out.columns:
            out = out.rename(columns={pedidos_code_col: "codigo_interno"})
        if pedidos_desc_col != "descricao" and pedidos_desc_col in out.columns:
            out = out.rename(columns={pedidos_desc_col: "descricao"})
        if pedidos_emb_col != "embalagem" and pedidos_emb_col in out.columns:
            out = out.rename(columns={pedidos_emb_col: "embalagem"})
        return out[
            [c for c in [
                "codigo_interno",
                "descricao",
                "data_pedido",
                "status_aprovacao",
                "total_cx",
            ] if c in out.columns]
        ]

    # Expande por loja
    id_cols = [c for c in [
        pedidos_code_col,
        pedidos_desc_col,
        "data_pedido",
        "status_aprovacao",
        "total_cx",
    ] if c in df.columns]

    df_melt = df.melt(
        id_vars=id_cols,
        value_vars=loja_cols,
        var_name="loja",
        value_name="pedido_do_dia_cx",
    )

    # Limpa e normaliza
    df_melt["loja"] = df_melt["loja"].str.replace("loja_", "", regex=False)
    # Mantém apenas pedidos > 0
    try:
        df_melt["pedido_do_dia_cx"] = pd.to_numeric(
            df_melt["pedido_do_dia_cx"]).fillna(0).astype(int)
    except Exception:
        pass
    df_melt = df_melt[df_melt["pedido_do_dia_cx"] > 0]

    # Renomeia colunas resolvidas para nomes esperados
    rename_map = {}
    if pedidos_code_col in df_melt.columns and pedidos_code_col != "codigo_interno":
        rename_map[pedidos_code_col] = "codigo_interno"
    if pedidos_desc_col in df_melt.columns and pedidos_desc_col != "descricao":
        rename_map[pedidos_desc_col] = "descricao"
    df_out = df_melt.rename(columns=rename_map)

    # Ordena por data mais recente
    if "data_pedido" in df.columns:
        df_out = df_out.sort_values(by=["data_pedido"], ascending=False)

    # Seleção final de colunas para a UI
    final_cols = [c for c in [
        "codigo_interno",
        "descricao",
        "loja",
        "pedido_do_dia_cx",
        "status_aprovacao",
        "total_cx",
        "data_pedido",
    ] if c in df_out.columns]

    return df_out[final_cols]


def get_future_offers(engine, code):
    """Busca ofertas futuras para um produto."""
    today = date.today()
    ofertas_col = resolve_ofertas_codigo_col(engine)
    query = text(
        f"""
        SELECT oferta, data_inicio, data_final FROM ofertas
        WHERE CAST({ofertas_col} AS TEXT) = :code AND data_final >= :today
        ORDER BY data_inicio
    """
    )
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={
                         "code": str(code), "today": today})
    return df


def save_pedido_consolidado(engine, pedido_df):
    """Salva os dados do pedido na tabela de consolidados."""
    try:
        with engine.begin() as conn:
            pedido_df.to_sql(
                "pedidos_consolidados",
                con=conn,
                if_exists="append",
                index=False,
            )
        return True
    except Exception as e:
        st.error(f"Erro ao salvar o pedido: {e}")
        return False


# --- Lógica da Página ---


def show_pedidos_cd_page(engine, base_data_path):
    st.title("📝 Pedidos via CD (Mix Ativo)")
    st.markdown(
        "Busque pelo Código Interno ou EAN para fazer um pedido do mix ativo.")

    # Inicializa o estado da sessão para o item pesquisado
    if "searched_item" not in st.session_state:
        st.session_state.searched_item = None
    if "pedido_details" not in st.session_state:
        st.session_state.pedido_details = {}

    # Definindo a lista global de lojas que será usada para salvar o pedido
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

    # --- Formulário de Busca ---
    st.markdown("### 🔍 Selecione o tipo de código para buscar:")

    with st.form("search_form"):
        col1, col2 = st.columns(2)

        with col1:
            code_interno = st.text_input(
                "Código Interno (máx 7 dígitos):",
                placeholder="Ex: 1234567",
                max_chars=7,
                key="codigo_interno_pedido"
            )

        with col2:
            code_ean = st.text_input(
                "Código EAN (máx 14 dígitos):",
                placeholder="Ex: 12345678901234",
                max_chars=14,
                key="codigo_ean_pedido"
            )

        submitted = st.form_submit_button("Buscar Produto")

        if submitted:
            st.session_state.searched_item = None  # Limpa busca anterior
            st.session_state.pedido_details = {}

            # Validar que apenas um campo foi preenchido
            if code_interno and code_ean:
                st.warning(
                    "⚠️ Por favor, use apenas um tipo de código por vez. "
                    "Limpe um dos campos."
                )
            elif code_interno or code_ean:
                code_input = code_ean if code_ean else code_interno

                with st.spinner("Buscando..."):
                    product_df = search_product_by_code(engine, code_input)
                    if not product_df.empty:
                        st.session_state.searched_item = (
                            product_df.iloc[0].to_dict()
                        )
                    else:
                        st.warning(
                            "Produto não encontrado no banco (mix_produtos)."
                        )
            else:
                st.info("Digite um código para buscar o produto.")

    # --- Exibição do Produto e Pedido ---
    if st.session_state.searched_item:
        item = st.session_state.searched_item
        mix_code_col = resolve_mix_codigo_col(engine)
        mix_desc_col = resolve_mix_descricao_col(engine)
        mix_emb_col = resolve_mix_emb_col(engine)
        codigo_produto = str(item.get(mix_code_col, ""))

        st.markdown("---")
        st.subheader(f"Produto Encontrado: {item.get(mix_desc_col, 'N/A')}")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Código Interno", codigo_produto)
        col2.metric("EAN", str(item.get("codigo_ean", "N/A")))

        # Embalagem (Un/Cx)
        emb_val = (
            item.get(mix_emb_col)
            if mix_emb_col
            else item.get("embalagem")
        )
        if pd.isna(emb_val) or emb_val is None:
            emb_val = "N/A"
        else:
            emb_val = int(emb_val)
        col3.metric("Emb. (Un/Cx)", str(emb_val))

        # Estoque CD (em caixas)
        estoque_val = item.get("estoque_cd", 0)
        if pd.isna(estoque_val) or estoque_val is None:
            estoque_val = 0
        else:
            estoque_val = int(estoque_val)
        col4.metric("Estoque CD (Cx)", str(estoque_val))

        # Abas com informações adicionais
        tab1, tab2 = st.tabs(["Histórico de Solicitações", "Ofertas Futuras"])
        with tab1:
            history_df = get_product_history(engine, codigo_produto)
            if not history_df.empty:
                st.dataframe(history_df, use_container_width=True)
            else:
                st.info(
                    "Este produto não possui histórico de pedidos. "
                    "Você pode ser o primeiro a solicitar!"
                )
                # Cria um DataFrame vazio com a estrutura esperada para a UI
                lojas_cols = [f"loja_{loja}" for loja in LISTA_LOJAS_GLOBAL]
                placeholder_cols = ["codigo_interno", "descricao"] + lojas_cols
                placeholder_df = pd.DataFrame(columns=placeholder_cols)
                placeholder_df.loc[0] = [
                    codigo_produto,
                    item.get(mix_desc_col, "N/A"),
                ] + [
                    0
                ] * len(lojas_cols)
                st.dataframe(placeholder_df, hide_index=True,
                             use_container_width=True)

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
            st.error(
                "Você não tem lojas associadas ao seu perfil. "
                "Contate um administrador."
            )
            return

        with st.form("pedido_form"):
            pedido_inputs = {}
            for loja in lojas_acesso:
                pedido_inputs[loja] = st.number_input(
                    f"Loja {loja}",
                    min_value=0,
                    step=1,
                    # Chave única para evitar conflitos
                    key=f"loja_{loja}_{codigo_produto}",
                )

            total_cx = sum(pedido_inputs.values())
            st.metric("Total de Caixas", total_cx)

            if st.form_submit_button("Enviar para Aprovação"):
                if total_cx > 0:
                    # Busca embalagem do item
                    emb_val = item.get(mix_emb_col, 0)
                    if pd.isna(emb_val) or emb_val is None:
                        emb_val = 0
                    else:
                        emb_val = int(emb_val)

                    pedido_data = {
                        "codigo_interno": [codigo_produto],
                        "descricao": [item.get(mix_desc_col, "N/A")],
                        "codigo_ean": [item.get("codigo_ean", "N/A")],
                        "embalagem": [emb_val],
                        "data_pedido": [datetime.now()],
                        "usuario_pedido": [
                            st.session_state.get("username", "unknown")
                        ],
                        "status_item": ["Pendente"],
                        "status_aprovacao": ["Pendente"],
                        "total_cx": [total_cx],
                    }
                    for loja in LISTA_LOJAS_GLOBAL:
                        col_name = f"loja_{loja}"
                        pedido_data[col_name] = [pedido_inputs.get(loja, 0)]

                    df_to_save = pd.DataFrame(pedido_data)

                    # Ajusta colunas para a tabela real de pedidos_consolidados
                    pedidos_code_col = resolve_pedidos_codigo_col(engine)
                    pedidos_desc_col = resolve_pedidos_descricao_col(engine)
                    pedidos_emb_col = resolve_pedidos_emb_col(engine)

                    rename_map = {}
                    if pedidos_code_col != "codigo_interno":
                        rename_map["codigo_interno"] = pedidos_code_col
                    if pedidos_desc_col != "descricao":
                        rename_map["descricao"] = pedidos_desc_col
                    if pedidos_emb_col != "embalagem":
                        rename_map["embalagem"] = pedidos_emb_col

                    df_real = df_to_save.rename(columns=rename_map)

                    # Compatibilidade: se a tabela exigir coluna 'codigo'
                    # (NOT NULL), popular com o mesmo valor do código real.
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
                        # Não bloquear salvamento em caso de detecção falhar
                        pass

                    # Compat: colunas legadas de descrição
                    # Ex.: produto/nome_produto NOT NULL
                    try:
                        # Coluna fonte para descrição no DataFrame
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
                            for legacy_col in [
                                "produto",
                                "nome_produto",
                                "descricao",
                            ]:
                                if (
                                    has_table_column(
                                        engine,
                                        "pedidos_consolidados",
                                        legacy_col,
                                    )
                                    and legacy_col not in df_real.columns
                                ):
                                    df_real[legacy_col] = df_real[desc_source]
                    except Exception:
                        pass

                    if save_pedido_consolidado(engine, df_real):
                        st.success(
                            "Pedido enviado com sucesso para aprovação!"
                        )
                        # Limpa para nova busca
                        st.session_state.searched_item = None
                        st.session_state.pedido_details = {}
                        st.rerun()
                else:
                    st.warning(
                        "Nenhuma quantidade foi digitada. "
                        "O pedido não foi enviado."
                    )

    # --- Meus Pedidos Pendentes ---
    st.markdown("---")
    st.subheader("📋 Meus Pedidos Pendentes (Aguardando Aprovação)")

    username = st.session_state.get("username", "unknown")
    try:
        p_code = resolve_pedidos_codigo_col(engine)
        p_desc = resolve_pedidos_descricao_col(engine)
        p_emb = resolve_pedidos_emb_col(engine)

        query_pendentes = text(
            f"""
            SELECT
                id,
                {p_code} AS codigo_interno,
                {p_desc} AS descricao,
                {p_emb} AS embalagem,
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
            st.info(
                f"Você tem {len(df_pendentes)} pedido(s) aguardando aprovação."
            )

            # Adiciona checkbox para exclusão
            df_pendentes["Excluir"] = False

            df_editado = st.data_editor(
                df_pendentes,
                column_config={
                    "id": None,
                    "codigo_interno": st.column_config.TextColumn(
                        "Código", disabled=True
                    ),
                    "descricao": st.column_config.TextColumn(
                        "Produto", width="large", disabled=True
                    ),
                    "embalagem": st.column_config.NumberColumn(
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
                key="pendentes_cd",
            )

            if st.button("🗑️ Excluir Selecionados", key="btn_excluir_cd"):
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
                        st.success(
                            f"{len(ids_excluir)} pedido(s) excluído(s)!"
                        )
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
    with st.expander(
        "❔ Precisa de ajuda ou quer fazer uma observação? Abra um chamado."
    ):
        with st.form("chamado_form_cd", clear_on_submit=True):
            mensagem = st.text_area(
                "Digite sua mensagem para o administrador:")
            if st.form_submit_button("Enviar Chamado"):
                if mensagem:
                    username = st.session_state.get("username", "unknown")
                    # Assunto padrão para identificar a origem
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
                        st.error(
                            f"Não foi possível enviar o chamado: {message}")
                else:
                    st.warning(
                        "Por favor, digite uma mensagem antes de enviar.")


