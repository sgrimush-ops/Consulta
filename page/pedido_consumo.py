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

    col_cod = _find_column(
        df,
        [
            "cod_consinco",
            "codigo_consinco",
            "codigo_interno",
            "codigo",
        ],
    )
    col_desc = _find_column(
        df,
        ["descricao", "descrição", "descricao sw", "descricao_sw"],
    )
    col_desc_consinco = _find_column(
        df,
        [
            "descricao_consinco",
            "descricao consinco",
            "descrição consinco",
            "desc_consinco",
        ],
    )
    col_emb = _find_column(df, ["Emb", "emb", "embalagem", "embseparacao"])
    col_setor = _find_column(
        df,
        ["setor", "secao", "seção", "departamento", "categoria"],
    )

    if not col_cod or not col_desc or not col_emb:
        st.error(
            "A tabela consumo precisa ter ao menos as colunas de código, "
            "descrição e embalagem."
        )
        return pd.DataFrame()

    result = pd.DataFrame()
    result["cod_consinco"] = pd.to_numeric(df[col_cod], errors="coerce")
    result["descricao"] = df[col_desc].astype(str)

    if col_desc_consinco:
        result["descricao_consinco"] = df[col_desc_consinco].astype(str)
    else:
        result["descricao_consinco"] = ""

    result["Emb"] = pd.to_numeric(df[col_emb], errors="coerce")
    if col_setor:
        result["setor"] = df[col_setor].astype(str).str.strip()
    else:
        result["setor"] = "Não informado"

    result = result.dropna(subset=["cod_consinco", "Emb"])
    result["cod_consinco"] = result["cod_consinco"].astype(int)
    result["Emb"] = result["Emb"].astype(int)
    result["setor"] = result["setor"].fillna("Não informado")
    result = result.drop_duplicates(subset=["cod_consinco"], keep="first")

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
            return df_produtos[df_produtos["cod_consinco"] == cod]
        except ValueError:
            return pd.DataFrame()

    if search_type == "descricao":
        mask = df_produtos["descricao"].str.contains(
            search_term, case=False, na=False
        )
        return df_produtos[mask]

    if search_type == "descricao_consinco":
        mask = df_produtos["descricao_consinco"].str.contains(
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
    _ = base_data_path

    st.title("📦 Pedido de Consumo")
    st.markdown("Sistema de pedidos alimentado pela tabela `consumo` do banco")

    if "consumo_searched_item" not in st.session_state:
        st.session_state.consumo_searched_item = None
    if "consumo_pedido_details" not in st.session_state:
        st.session_state.consumo_pedido_details = {}
    if "consumo_search_results" not in st.session_state:
        st.session_state.consumo_search_results = None

    lista_lojas_global = [
        "001", "002", "003", "004", "005", "006", "007", "008",
        "011", "012", "013", "014", "016", "017", "018",
        "F01", "F02", "F03", "F04", "F05", "F06", "F07", "F08",
        "F10", "F11", "M12", "M13", "ADM", "RH"
    ]

    df_produtos = load_products_from_consumo_table(engine)

    if df_produtos.empty:
        st.error("❌ Não foi possível carregar a base de consumo!")
        st.info(
            "Verifique se a tabela `consumo` foi carregada no Admin Uploads."
        )
        return

    total_produtos = len(df_produtos)

    col_total, _ = st.columns([1, 2])
    col_total.metric("Total de Produtos", total_produtos)

    st.markdown("---")
    st.markdown("### 🏷️ Pedido Rápido por Setor")

    lojas_acesso = st.session_state.get("lojas_acesso", [])
    lojas_autorizadas = [
        loja for loja in lista_lojas_global if loja in set(lojas_acesso)
    ]

    if not lojas_autorizadas:
        st.error(
            "Você não tem lojas associadas ao seu perfil. "
            "Contate um administrador."
        )
        return

    setores_disponiveis = sorted(
        [
            setor
            for setor in df_produtos["setor"].dropna().astype(str).unique()
            if setor.strip()
        ]
    )

    if not setores_disponiveis:
        st.info("Não há informação de setor na base de consumo.")
    else:
        col_setor, col_loja = st.columns([2, 1])
        with col_setor:
            setor_selecionado = st.selectbox(
                "Filtrar setor:",
                setores_disponiveis,
                key="consumo_setor_filter",
            )
        with col_loja:
            loja_setor = st.selectbox(
                "Loja do pedido:",
                lojas_autorizadas,
                key="consumo_setor_loja",
            )

        df_setor = df_produtos[
            df_produtos["setor"].astype(str) == str(setor_selecionado)
        ].copy()
        df_setor = df_setor[["cod_consinco", "descricao", "Emb"]]
        df_setor = df_setor.sort_values("descricao", ascending=True)
        busca_key = f"consumo_busca_setor_{setor_selecionado}"

        termo_setor = st.text_input(
            "Buscar item no setor (código ou descrição):",
            placeholder="Ex: 10480 ou CERVEJA",
            key=busca_key,
        ).strip()

        _, col_busca2, _ = st.columns([1, 1, 2])

        if termo_setor:
            mask_desc = df_setor["descricao"].str.contains(
                termo_setor,
                case=False,
                na=False,
            )
            mask_cod = (
                df_setor["cod_consinco"].astype(str).str.contains(
                    termo_setor,
                    case=False,
                    na=False,
                )
            )
            df_setor = df_setor[mask_desc | mask_cod]

        st.caption(f"Itens exibidos no setor: {len(df_setor)}")

        if df_setor.empty:
            st.info("Nenhum item encontrado para o filtro informado.")
        else:
            qtd_state_key = f"consumo_qtd_setor_{setor_selecionado}"
            if qtd_state_key not in st.session_state:
                st.session_state[qtd_state_key] = {}

            qtd_map = st.session_state[qtd_state_key]

            with col_busca2:
                if st.button(
                    "☑️ Selecionar todos (1 CX)",
                    key=f"consumo_select_all_{setor_selecionado}",
                ):
                    for cod in df_setor["cod_consinco"].tolist():
                        qtd_map[str(int(cod))] = 1
                    st.session_state[qtd_state_key] = qtd_map
                    st.rerun()

            col_qtd1, col_qtd2, _ = st.columns([1, 1, 2])
            with col_qtd1:
                if st.button(
                    "🧽 Zerar quantidades",
                    key=f"consumo_zerar_qtd_{setor_selecionado}",
                ):
                    for cod in df_setor["cod_consinco"].tolist():
                        qtd_map[str(int(cod))] = 0
                    st.session_state[qtd_state_key] = qtd_map
                    st.rerun()

            df_setor["qtd_cx"] = (
                df_setor["cod_consinco"]
                .astype(str)
                .map(lambda cod: int(qtd_map.get(cod, 0)))
            )

            st.caption(
                "Preencha apenas a coluna `Qtd CX` para os itens desejados e "
                "clique em enviar."
            )
            st.info(
                "Você pode alterar as quantidades a qualquer momento antes de "
                "clicar em `Enviar pedidos do setor`."
            )

            df_setor_editado = st.data_editor(
                df_setor,
                column_config={
                    "cod_consinco": st.column_config.NumberColumn(
                        "Código", disabled=True, format="%d"
                    ),
                    "descricao": st.column_config.TextColumn(
                        "Descrição", disabled=True, width="large"
                    ),
                    "Emb": st.column_config.NumberColumn(
                        "Embalagem", disabled=True, format="%d"
                    ),
                    "qtd_cx": st.column_config.NumberColumn(
                        "Qtd CX", min_value=0, step=1, format="%d"
                    ),
                },
                hide_index=True,
                use_container_width=True,
                key=f"consumo_editor_setor_{setor_selecionado}",
            )

            for _, row in df_setor_editado.iterrows():
                qtd_map[str(int(row["cod_consinco"]))] = int(
                    row["qtd_cx"] or 0
                )
            st.session_state[qtd_state_key] = qtd_map

            if st.button(
                "📤 Enviar pedidos do setor",
                key="consumo_enviar_setor",
                type="primary",
            ):
                if loja_setor not in lojas_autorizadas:
                    st.error(
                        "Loja selecionada sem autorização para o seu usuário."
                    )
                else:
                    itens_pedido = df_setor_editado[
                        df_setor_editado["qtd_cx"] > 0
                    ]
                    if itens_pedido.empty:
                        st.warning(
                            "Preencha ao menos uma quantidade para enviar."
                        )
                    else:
                        username = st.session_state.get("username", "unknown")
                        pedidos_lote = []
                        for _, row in itens_pedido.iterrows():
                            pedido_data = {
                                "codigo_interno": str(
                                    int(row["cod_consinco"])
                                ),
                                "descricao": row["descricao"],
                                "codigo_ean": "",
                                "origem_pedido": "Pedido de Consumo",
                                "embseparacao": int(row["Emb"]),
                                "data_pedido": now_brazil(),
                                "usuario_pedido": username,
                                "status_item": "Pendente",
                                "status_aprovacao": "Pendente",
                                "total_cx": int(row["qtd_cx"]),
                            }

                            for loja in lista_lojas_global:
                                col_loja_name = f"loja_{str(loja).lower()}"
                                if (
                                    loja == loja_setor
                                    and loja in lojas_autorizadas
                                ):
                                    pedido_data[col_loja_name] = int(
                                        row["qtd_cx"]
                                    )
                                else:
                                    pedido_data[col_loja_name] = 0

                            pedidos_lote.append(pedido_data)

                        df_lote = pd.DataFrame(pedidos_lote)
                        if save_pedido_consolidado(engine, df_lote):
                            st.session_state[qtd_state_key] = {}
                            st.success(
                                f"{len(df_lote)} item(ns) do setor "
                                "enviado(s) para "
                                "aprovação."
                            )
                            st.rerun()

    st.markdown("---")
    st.markdown("### 🔍 Buscar Produto")

    with st.form("consumo_search_form"):
        search_type = st.radio(
            "Tipo de busca:",
            ["Por Código", "Por Descrição", "Por Descrição Consinco"],
            horizontal=True,
        )

        if search_type == "Por Código":
            search_term = st.text_input(
                "Digite o código Consinco:",
                placeholder="Ex: 10480",
                max_chars=10,
            )
        elif search_type == "Por Descrição":
            search_term = st.text_input(
                "Digite parte da descrição do produto:",
                placeholder="Ex: CERVEJA",
            )
        else:
            search_term = st.text_input(
                "Digite parte da descrição Consinco:",
                placeholder="Ex: CERVEJA PILSEN",
            )

        submitted = st.form_submit_button("🔍 Buscar")

        if submitted and search_term:
            st.session_state.consumo_searched_item = None
            st.session_state.consumo_pedido_details = {}

            if search_type == "Por Código":
                search_mode = "codigo"
            elif search_type == "Por Descrição":
                search_mode = "descricao"
            else:
                search_mode = "descricao_consinco"

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
            "Encontrados "
            f"{len(st.session_state.consumo_search_results)} produtos. "
            "Selecione um:"
        )

        results_display = st.session_state.consumo_search_results.copy()
        results_display = results_display[
            [
                "cod_consinco",
                "descricao",
                "descricao_consinco",
                "Emb",
            ]
        ]
        results_display.columns = [
            "Código Consinco",
            "Descrição",
            "Descrição Consinco",
            "Embalagem",
        ]

        selected_idx = st.selectbox(
            "Escolha o produto:",
            range(len(results_display)),
            format_func=lambda i: (
                f"{results_display.iloc[i]['Código Consinco']} - "
                f"{results_display.iloc[i]['Descrição']}"
            ),
            key="consumo_select_result",
        )

        if st.button("✅ Confirmar Seleção", key="consumo_confirm_select"):
            st.session_state.consumo_searched_item = (
                st.session_state.consumo_search_results.iloc[
                    selected_idx
                ].to_dict()
            )
            st.session_state.consumo_search_results = None
            st.rerun()

    if st.session_state.consumo_searched_item:
        item = st.session_state.consumo_searched_item
        codigo_produto = int(item["cod_consinco"])
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
        st.subheader(f"Produto Selecionado: {item['descricao']}")

        col1, col2, col3 = st.columns(3)
        col1.metric("Código Consinco", codigo_produto)
        col2.metric("Descrição Consinco", item["descricao_consinco"])
        col3.metric("Emb. (Un/Cx)", int(item["Emb"]))

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
            total_un = total_cx * int(item["Emb"])

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
                "descricao": [item["descricao"]],
                "codigo_ean": [item["descricao_consinco"]],
                "origem_pedido": ["Pedido de Consumo"],
                "embseparacao": [int(item["Emb"])],
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
