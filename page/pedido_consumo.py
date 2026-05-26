import streamlit as st
import pandas as pd
from sqlalchemy import text, inspect
import os
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
                query_ticket,
                {"username": username, "assunto": assunto, "now": now},
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


def _find_column(df, candidates):
    normalized = {col.lower().strip(): col for col in df.columns}
    for candidate in candidates:
        found = normalized.get(candidate.lower().strip())
        if found:
            return found
    return None


def _load_consumo_parquet():
    parquet_path = os.path.join("bdados", "consumo.parquet")
    if not os.path.exists(parquet_path):
        return None

    try:
        return pd.read_parquet(parquet_path)
    except Exception as e:
        st.error(f"Erro ao ler consumo.parquet local: {e}")
        return None


def load_products_from_consumo_table(engine):
    """Carrega produtos exclusivamente da tabela consumo no banco."""
    inspector = inspect(engine)
    consumo_schema = None
    if inspector.has_table("consumo"):
        consumo_schema = None
    else:
        for schema in inspector.get_schema_names():
            if schema in ("information_schema", "pg_catalog"):
                continue
            if inspector.has_table("consumo", schema=schema):
                consumo_schema = schema
                break

    if consumo_schema is None and not inspector.has_table("consumo"):
        df = _load_consumo_parquet()
        if df is None:
            st.error(
                "Tabela `consumo` nao encontrada no banco e "
                "consumo.parquet local inexistente. "
                "Carregue o arquivo em Admin Uploads."
            )
            return pd.DataFrame()
        st.warning(
            "Tabela `consumo` nao encontrada no banco. "
            "Usando consumo.parquet local."
        )
    else:
        try:
            with engine.connect() as conn:
                if consumo_schema:
                    query = text(f'SELECT * FROM "{consumo_schema}".consumo')
                else:
                    query = text("SELECT * FROM consumo")
                df = pd.read_sql(query, conn)
        except Exception as e:
            df = _load_consumo_parquet()
            if df is not None:
                st.warning(
                    "Falha ao ler tabela consumo no banco. "
                    "Usando consumo.parquet local."
                )
            else:
                st.error(f"Erro ao carregar tabela consumo: {e}")
                return pd.DataFrame()

    if df.empty:
        return pd.DataFrame()

    # Considera apenas nomes padronizados do consumo.parquet
    # Usar nomes exatos do CSV/parquet: 'codigo', 'descricao consinco', 'embalagem'
    required_columns = ["codigo", "descricao consinco", "embalagem"]
    for col in required_columns:
        if col not in df.columns:
            st.error(
                f"A tabela consumo precisa ter a coluna '{col}'. "
                "Verifique o arquivo consumo.parquet."
            )
            return pd.DataFrame()

    result = pd.DataFrame()
    result["codigo"] = pd.to_numeric(df["codigo"], errors="coerce")
    result["descricao consinco"] = df["descricao consinco"].astype(str)
    result["embalagem"] = pd.to_numeric(df["embalagem"], errors="coerce")

    result = result.dropna(subset=["codigo", "embalagem"])
    result["codigo"] = result["codigo"].astype(int)
    result["embalagem"] = result["embalagem"].astype(int)
    result = result.drop_duplicates(subset=["codigo"], keep="first")

    return result


def search_product(df_produtos, search_term, search_type="codigo"):
    """
    Busca produto por código, descrição ou descrição Consinco.
    """
    if df_produtos.empty:
        return pd.DataFrame()


    if search_type == "codigo":
        try:
            cod = int(search_term)
            return df_produtos[df_produtos["codigo"] == cod]
        except ValueError:
            return pd.DataFrame()

    if search_type == "descricao" or search_type == "descricao_consinco":
        mask = df_produtos["descricao consinco"].str.contains(
            search_term, case=False, na=False
        )
        return df_produtos[mask]

    return pd.DataFrame()


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


def get_last_item_order_30d(engine, username, codigo_produto):
    """Busca o último pedido do item nos últimos 30 dias."""
    try:
        query = text(
            """
            SELECT *
            FROM pedidos_consolidados
            WHERE usuario_pedido = :username
              AND codigo_interno = :codigo
                            AND data_pedido >= (
                                    CURRENT_TIMESTAMP AT TIME ZONE 'America/Sao_Paulo'
                            ) - INTERVAL '30 days'
            ORDER BY data_pedido DESC
            LIMIT 1
            """
        )
        with engine.connect() as conn:
            df = pd.read_sql(
                query,
                conn,
                params={
                    "username": username,
                    "codigo": str(codigo_produto),
                },
            )

        if df.empty:
            return None

        return df.iloc[0].to_dict()
    except Exception:
        return None


def get_orders_history_30d(engine, username):
    """Retorna histórico de pedidos do usuário dos últimos 30 dias."""
    query = text(
        """
        SELECT
            id,
            codigo_interno,
            descricao,
            embseparacao,
            total_cx,
            TO_CHAR(data_pedido, 'DD/MM/YYYY HH24:MI') AS data_pedido,
            status_aprovacao
        FROM pedidos_consolidados
        WHERE usuario_pedido = :username
                AND COALESCE(origem_pedido, 'Pedido por Código (CD)') = 'Pedido de Consumo'
                    AND data_pedido >= (
                            CURRENT_TIMESTAMP AT TIME ZONE 'America/Sao_Paulo'
                    ) - INTERVAL '30 days'
        ORDER BY data_pedido DESC
        LIMIT 200
        """
    )

    with engine.connect() as conn:
        return pd.read_sql(query, conn, params={"username": username})


# --- Página Principal ---


def show_pedido_consumo_page(engine, base_data_path):
    """Página de pedido de consumo usando exclusivamente a tabela consumo."""
    # Definição das listas de lojas
    from app import LISTA_LOJAS
    lista_lojas_global = LISTA_LOJAS
    lojas_autorizadas = st.session_state.get("lojas_acesso", LISTA_LOJAS)
    _ = base_data_path


    st.title("📦 Pedido de Consumo")
    st.markdown("Sistema de pedidos alimentado pela tabela `consumo`.")

    if "consumo_searched_item" not in st.session_state:
        st.session_state.consumo_searched_item = None
    if "consumo_pedido_details" not in st.session_state:
        st.session_state.consumo_pedido_details = {}
    if "consumo_search_results" not in st.session_state:
        st.session_state.consumo_search_results = None

    df_produtos = load_products_from_consumo_table(engine)

    if df_produtos.empty:
        st.error("❌ Não foi possível carregar a base de consumo!")
        st.info(
            "Verifique se a tabela `consumo` foi carregada no Admin Uploads."
        )
        return

    total_produtos = len(df_produtos)
    st.metric("Total de Produtos", total_produtos)

    with st.form("consumo_search_form"):
        search_type = st.radio(
            "Tipo de busca:",
            ["Por Código", "Por Descrição"],
            horizontal=True,
        )

        if search_type == "Por Código":
            search_term = st.text_input(
                "Digite o código Consinco:",
                placeholder="Ex: 10480",
                max_chars=10,
            )
        else:
            search_term = st.text_input(
                "Digite parte da descrição do produto:",
                placeholder="Ex: CERVEJA",
            )

        submitted = st.form_submit_button("🔍 Buscar")

        if submitted and search_term:
            st.session_state.consumo_searched_item = None
            st.session_state.consumo_pedido_details = {}

            if search_type == "Por Código":
                search_mode = "codigo"
            else:
                search_mode = "descricao"

            results = search_product(df_produtos, search_term, search_mode)

            if not results.empty:
                if len(results) == 1:
                    st.session_state.consumo_searched_item = (
                        results.iloc[0].to_dict()
                    )
                    st.session_state.consumo_search_results = None
                else:
                    st.session_state.consumo_search_results = results
                    st.session_state.consumo_searched_item = None
            else:
                st.warning("❌ Nenhum produto encontrado com esse critério.")
                st.session_state.consumo_search_results = None

    if (
        st.session_state.consumo_search_results is not None
        and not st.session_state.consumo_search_results.empty
    ):
        st.markdown("### 📋 Resultados da Busca")
        st.info(
            f"Encontrados {len(st.session_state.consumo_search_results)} produtos. Selecione um:"
        )

        results_display = st.session_state.consumo_search_results.copy()
        results_display = results_display[[
            "codigo",
            "descricao consinco",
            "embalagem",
        ]]
        results_display.columns = [
            "Código",
            "Descrição Consinco",
            "Embalagem",
        ]

        selected_idx = st.selectbox(
            "Escolha o produto:",
            range(len(results_display)),
            format_func=lambda i: (
                f"{results_display.iloc[i]['Código']} - "
                f"{results_display.iloc[i]['Descrição Consinco']}"
            ),
            key="consumo_select_result",
        )

        if st.button("✅ Confirmar Seleção", key="consumo_confirm_select"):
            st.session_state.consumo_searched_item = (
                st.session_state.consumo_search_results.iloc[selected_idx].to_dict()
            )
            st.session_state.consumo_search_results = None
            st.rerun()

    if st.session_state.consumo_searched_item:
        item = st.session_state.consumo_searched_item
        codigo_produto = int(item["codigo"])
        username = st.session_state.get("username", "unknown")

        last_order = get_last_item_order_30d(engine, username, codigo_produto)
        default_qtd_por_loja = {}
        if last_order:
            st.info(
                "Último pedido deste item encontrado nos últimos 30 dias. "
                "As quantidades foram pré-preenchidas."
            )
            for key, value in last_order.items():
                if key.startswith("loja_"):
                    try:
                        default_qtd_por_loja[key.replace("loja_", "")] = int(
                            value or 0
                        )
                    except Exception:
                        default_qtd_por_loja[key.replace("loja_", "")] = 0
        else:
            st.warning(
                "Primeiro pedido deste item para você nos últimos 30 dias."
            )

        st.markdown("---")
        st.subheader(f"Produto Selecionado: {item['descricao consinco']}")

        col1, col2, col3 = st.columns(3)
        col1.metric("Código", codigo_produto)
        col2.metric("Descrição Consinco", item["descricao consinco"])
        col3.metric("Emb. (Un/Cx)", int(item["embalagem"]))

        st.markdown("---")
        st.subheader("Digite as quantidades por loja (em caixas):")
        st.info(
            "Você pode alterar as quantidades a qualquer momento antes de "
            "clicar em `Enviar para Aprovação`."
        )
        st.caption(
            "Somente lojas autorizadas para o seu usuário ficam disponíveis "
            "para pedido."
        )

        with st.form("consumo_pedido_form"):
            pedido_inputs = {}

            cols_per_row = 3
            cols = st.columns(cols_per_row)

            for idx, loja in enumerate(lojas_autorizadas):
                col_idx = idx % cols_per_row
                with cols[col_idx]:
                    pedido_inputs[loja] = st.number_input(
                        f"Loja {loja}",
                        min_value=0,
                        value=default_qtd_por_loja.get(loja, 0),
                        step=1,
                        key=f"consumo_loja_{loja}_{codigo_produto}",
                    )

            st.markdown("---")
            total_cx = sum(pedido_inputs.values())
            total_un = total_cx * int(item["embalagem"])

            col_total1, col_total2 = st.columns(2)
            col_total1.metric("Total de Caixas", total_cx)
            col_total2.metric("Total de Unidades", total_un)

            submitted_pedido = st.form_submit_button(
                "📤 Enviar para Aprovação",
                type="primary",
            )

            if submitted_pedido:
                if total_cx > 0:
                    st.session_state.consumo_pedido_details = {
                        "pedido_inputs": pedido_inputs,
                        "total_cx": total_cx,
                        "codigo_produto": codigo_produto,
                        "item": item,
                        "confirmar_pedido": True,
                    }
                    st.rerun()
                else:
                    st.warning(
                        "Nenhuma quantidade foi digitada. "
                        "O pedido não foi enviado."
                    )

        if st.session_state.consumo_pedido_details.get(
            "confirmar_pedido", False
        ):
            pedido_inputs = st.session_state.consumo_pedido_details[
                "pedido_inputs"
            ]
            total_cx = st.session_state.consumo_pedido_details["total_cx"]
            codigo_produto = st.session_state.consumo_pedido_details[
                "codigo_produto"
            ]
            item = st.session_state.consumo_pedido_details["item"]

            pedido_data = {
                "codigo_interno": [codigo_produto],
                "descricao": [item["descricao consinco"]],
                "codigo_ean": [""] ,  # Sem EAN disponível
                "origem_pedido": ["Pedido de Consumo"],
                "embseparacao": [int(item["embalagem"])],
                "data_pedido": [now_brazil()],
                "usuario_pedido": [
                    st.session_state.get("username", "unknown")
                ],
                "status_item": ["Pendente"],
                "status_aprovacao": ["Pendente"],
                "total_cx": [total_cx],
            }

            lojas_nao_autorizadas = set(lista_lojas_global) - set(
                lojas_autorizadas
            )
            for loja in lojas_nao_autorizadas:
                pedido_inputs[loja] = 0

            for loja in lista_lojas_global:
                pedido_data[f"loja_{str(loja).lower()}"] = [
                    pedido_inputs.get(loja, 0)
                ]

            df_to_save = pd.DataFrame(pedido_data)

            if save_pedido_consolidado(engine, df_to_save):
                st.success("✅ Pedido enviado com sucesso para aprovação!")
                st.session_state.consumo_searched_item = None
                st.session_state.consumo_pedido_details = {}
                st.session_state.consumo_search_results = None
                st.rerun()

    st.markdown("---")
    st.subheader("📋 Histórico de Pedidos (Últimos 30 dias)")

    username = st.session_state.get("username", "unknown")
    try:
        df_historico = get_orders_history_30d(engine, username)

        if not df_historico.empty:
            st.info(
                f"Você tem {len(df_historico)} pedido(s) registrados "
                "nos últimos 30 dias."
            )

            st.dataframe(
                df_historico,
                column_config={
                    "id": None,
                    "codigo_interno": st.column_config.TextColumn(
                        "Código Consinco"
                    ),
                    "descricao": st.column_config.TextColumn(
                        "Produto", width="large"
                    ),
                    "embseparacao": st.column_config.NumberColumn(
                        "Emb. (Un/Cx)", format="%d"
                    ),
                    "total_cx": st.column_config.NumberColumn(
                        "Total CX", format="%d"
                    ),
                    "data_pedido": st.column_config.TextColumn("Data/Hora"),
                    "status_aprovacao": st.column_config.TextColumn(
                        "Status"
                    ),
                },
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.info("Você não tem histórico de pedidos nos últimos 30 dias.")
    except Exception as e:
        st.error(f"Erro ao buscar histórico de pedidos: {e}")

    st.markdown("---")
    with st.expander(
        "❔ Precisa de ajuda ou quer fazer uma observação? Abra um chamado."
    ):
        with st.form("chamado_form_consumo", clear_on_submit=True):
            mensagem = st.text_area(
                "Digite sua mensagem para o administrador:"
            )
            if st.form_submit_button("Enviar Chamado"):
                if mensagem:
                    username = st.session_state.get("username", "unknown")
                    assunto = "Chamado via Tela de Pedido de Consumo"
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
                            "Não foi possível enviar o chamado: "
                            f"{message}"
                        )
                else:
                    st.warning(
                        "Por favor, digite uma mensagem antes de enviar."
                    )
