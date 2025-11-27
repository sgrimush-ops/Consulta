import streamlit as st
import pandas as pd
from sqlalchemy import text, exc

def get_stock_data(engine, search_term=""):
    """
    Busca dados de estoque na tabela 'mix_produtos'.
    """
    try:
        # CORREÇÃO: codigo -> codigo_interno
        # Note que também adicionei 'codigo_ean' para garantir
        query_str = """
            SELECT 
                codigo_interno, 
                produto AS nome_produto, 
                codigo_ean, 
                loja_ativa_mix, 
                estoque_cd, 
                total_estoque 
            FROM mix_produtos
        """
        params = {}
        if search_term:
            # CORREÇÃO: WHERE usa codigo_interno e codigo_ean
            query_str += """
                WHERE 
                        CAST(codigo_interno AS TEXT) ILIKE :term OR 
                    CAST(codigo_ean AS TEXT) ILIKE :term
            """
            params = {"term": f"%{search_term}%"}
        
        query_str += " ORDER BY nome_produto"

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
    st.markdown("Visualize o status do mix e os estoques diretamente da base de dados atualizada.")

    search_term = st.text_input(
        "Buscar por Código Interno ou EAN:",
        placeholder="Digite o código para filtrar..."
    )

    with st.spinner("Carregando dados de estoque..."):
        df_stock = get_stock_data(engine, search_term)

    if not df_stock.empty:
        st.dataframe(
            df_stock,
            column_config={
                "codigo_interno": st.column_config.TextColumn("Cód. Interno"), # Alterado
                "nome_produto": st.column_config.TextColumn("Produto", width="large"),
                "codigo_ean": st.column_config.TextColumn("EAN"), # Alterado
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