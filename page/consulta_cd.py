import streamlit as st
import pandas as pd
from sqlalchemy import text, exc
from page import (
    resolve_mix_codigo_col,
    resolve_mix_descricao_col,
)


def get_stock_data(engine, search_term="", search_type="interno"):
    """
    Busca dados de estoque na tabela 'mix_produtos'.
    search_type: 'interno' para código interno, 'ean' para código EAN
    """
    try:
        code_col = resolve_mix_codigo_col(engine)
        desc_col = resolve_mix_descricao_col(engine)
        query_str = f"""
            SELECT
                {code_col} AS codigo_interno,
                {desc_col} AS descricao,
                codigo_ean,
                loja_ativa_mix,
                estoque_cd,
                total_estoque
            FROM mix_produtos
        """
        params = {}
        if search_term:
            if search_type == "interno":
                query_str += f" WHERE CAST({code_col} AS TEXT) ILIKE :term"
            elif search_type == "ean":
                query_str += f" WHERE CAST(codigo_ean AS TEXT) ILIKE :term"
            params = {"term": f"%{search_term}%"}
        query_str += " ORDER BY descricao"

        with engine.connect() as conn:
            df = pd.read_sql(text(query_str), conn, params=params)
        return df

    except exc.ProgrammingError as e:
        st.error(f"Erro de Banco de Dados: {e}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Ocorreu um erro inesperado: {e}")
        return pd.DataFrame()


def show_consulta_cd_page(engine, base_data_path):
    st.title("📊 Consulta de Estoque e Mix (CD)")
    st.markdown(
        "Visualize o status do mix e os estoques diretamente da base de dados "
        "atualizada."
    )

    # --- SELEÇÃO DO TIPO DE BUSCA ---
    st.markdown("### 🔍 Selecione o tipo de código para buscar:")
    col1, col2 = st.columns(2)

    with col1:
        search_interno = st.text_input(
            "Código Interno (máx 7 dígitos):",
            placeholder="Ex: 1234567",
            max_chars=7,
            key="codigo_interno_search"
        )

    with col2:
        search_ean = st.text_input(
            "Código EAN (máx 14 dígitos):",
            placeholder="Ex: 12345678901234",
            max_chars=14,
            key="codigo_ean_search"
        )

    # Determinar qual busca usar
    search_term = ""
    search_type = "interno"

    if search_interno and search_ean:
        st.warning(
            "⚠️ Por favor, use apenas um tipo de código por vez. Limpe um dos campos.")
        return
    elif search_ean:
        search_term = search_ean
        search_type = "ean"
    elif search_interno:
        search_term = search_interno
        search_type = "interno"

    with st.spinner("Carregando dados de estoque..."):
        df_stock = get_stock_data(engine, search_term, search_type)

    if not df_stock.empty:
        st.dataframe(
            df_stock,
            column_config={
                # Alterado
                "codigo_interno": st.column_config.TextColumn("Cód. Interno"),
                "descricao": st.column_config.TextColumn(
                    "Descrição", width="large"
                ),
                "codigo_ean": st.column_config.TextColumn("EAN"),  # Alterado
                "loja_ativa_mix": st.column_config.CheckboxColumn(
                    "Mix Ativo?"
                ),
                "estoque_cd": st.column_config.NumberColumn("Estoque CD"),
                "total_estoque": st.column_config.NumberColumn(
                    "Estoque Total"
                ),
            },
            hide_index=True,
            use_container_width=True,
        )
        st.info(f"Exibindo **{len(df_stock)}** resultado(s).")
    else:
        if search_term:
            st.warning(
                "Nenhum produto encontrado com os critérios de busca."
            )
        else:
            st.info("Digite um código para buscar produtos.")
