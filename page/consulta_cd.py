import streamlit as st
import pandas as pd
from sqlalchemy import text, exc

def get_stock_data(engine, search_term=""):
    """
    Busca dados de estoque na tabela 'mix_produtos', com um filtro opcional.
    """
    try:
        # A consulta base seleciona todas as colunas relevantes
        query_str = """
            SELECT 
                codigo, 
                produto, 
                ean, 
                loja_ativa_mix, 
                estoque_cd, 
                total_estoque 
            FROM mix_produtos
        """
        params = {}
        # Se um termo de busca for fornecido, adiciona a cláusula WHERE
        if search_term:
            query_str += """
                WHERE 
                    CAST(codigo AS TEXT) ILIKE :term OR 
                    CAST(ean AS TEXT) ILIKE :term
            """
            params = {"term": f"%{search_term}%"}
        
        query_str += " ORDER BY produto"

        with engine.connect() as conn:
            df = pd.read_sql(text(query_str), conn, params=params)
        return df

    except exc.ProgrammingError as e:
        # Erro comum se as colunas esperadas não existirem (ex: após um novo upload)
        st.error(
            "Erro de Banco de Dados: Uma ou mais colunas esperadas (`loja_ativa_mix`, `estoque_cd`, `total_estoque`) "
            "não foram encontradas na tabela `mix_produtos`. Verifique o arquivo `mix.parquet` mais recente."
        )
        return pd.DataFrame() # Retorna um dataframe vazio em caso de erro
    except Exception as e:
        st.error(f"Ocorreu um erro inesperado ao consultar o banco de dados: {e}")
        return pd.DataFrame()

def show_consulta_cd_page(engine, base_data_path):
    """
    Cria a interface para a consulta de estoque do CD.
    """
    st.title("📊 Consulta de Estoque e Mix (CD)")
    st.markdown("Visualize o status do mix e os estoques diretamente da base de dados atualizada.")

    # --- Barra de Busca ---
    search_term = st.text_input(
        "Buscar por Código Interno ou EAN:",
        placeholder="Digite o código para filtrar..."
    )

    # --- Exibição dos Dados ---
    with st.spinner("Carregando dados de estoque..."):
        df_stock = get_stock_data(engine, search_term)

    if not df_stock.empty:
        st.dataframe(
            df_stock,
            column_config={
                "codigo": st.column_config.TextColumn("Código"),
                "produto": st.column_config.TextColumn("Produto", width="large"),
                "ean": st.column_config.TextColumn("EAN"),
                "loja_ativa_mix": st.column_config.CheckboxColumn("Mix Ativo?"),
                "estoque_cd": st.column_config.NumberColumn("Estoque CD"),
                "total_estoque": st.column_config.NumberColumn("Estoque Total")
            },
            hide_index=True,
            use_container_width=True
        )
        st.info(f"Exibindo **{len(df_stock)}** resultado(s).")
    else:
        st.warning("Nenhum produto encontrado com os critérios de busca ou a base de dados está vazia.")
