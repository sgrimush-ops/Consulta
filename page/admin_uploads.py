import streamlit as st
import pandas as pd
from sqlalchemy.exc import SQLAlchemyError


def show_admin_uploads_page(engine):
    """
    Cria a interface para upload dos arquivos base do sistema (mix e histórico).
    """
    st.title("⚙️ Administração de Uploads de Base")
    st.markdown(
        "Faça o upload dos arquivos `.parquet` para atualizar a base de dados primária do sistema. "
        "**Atenção:** O arquivo enviado substituirá completamente os dados existentes."
    )

    # --- UPLOAD MIX DE PRODUTOS ---
    st.subheader("1. Upload do Arquivo de Mix de Produtos")
    uploaded_mix = st.file_uploader(
        "Selecione o arquivo `mix.parquet`",
        type="parquet",
        key="mix_uploader"
    )

    if uploaded_mix is not None:
        try:
            df_mix = pd.read_parquet(uploaded_mix)
            st.write("Amostra dos dados do Mix de Produtos (`mix_produtos`):")
            st.dataframe(df_mix.head())

            if st.button("Salvar Mix no Banco de Dados", type="primary", key="save_mix"):
                with st.spinner("Salvando dados do Mix... Isso pode levar alguns minutos."):
                    try:
                        # Usar if_exists='replace' para apagar a tabela antiga e criar uma nova com os dados atualizados
                        df_mix.to_sql('mix_produtos', con=engine,
                                      if_exists='replace', index=False)
                        st.success(
                            "Arquivo de Mix de Produtos salvo com sucesso no banco de dados!")
                        st.balloons()
                    except SQLAlchemyError as e:
                        st.error(
                            f"Erro de banco de dados ao salvar o Mix: {e}")
                    except Exception as e:
                        st.error(
                            f"Ocorreu um erro inesperado ao salvar o Mix: {e}")

        except Exception as e:
            st.error(
                f"Ocorreu um erro ao processar o arquivo `mix.parquet`: {e}")

    st.markdown("---")

    # --- UPLOAD HISTÓRICO DE SOLICITAÇÕES ---
    st.subheader("2. Upload do Arquivo de Histórico de Solicitações")
    uploaded_historico = st.file_uploader(
        "Selecione o arquivo `historico.parquet`",
        type="parquet",
        key="hist_uploader"
    )

    if uploaded_historico is not None:
        try:
            df_historico = pd.read_parquet(uploaded_historico)
            st.write("Amostra dos dados do Histórico (`historico_solicitacoes`):")
            st.dataframe(df_historico.head())

            if st.button("Salvar Histórico no Banco de Dados", type="primary", key="save_historico"):
                with st.spinner("Salvando dados do Histórico... Isso pode levar alguns minutos."):
                    try:
                        df_historico.to_sql(
                            'historico_solicitacoes', con=engine, if_exists='replace', index=False)
                        st.success(
                            "Arquivo de Histórico de Solicitações salvo com sucesso no banco de dados!")
                        st.balloons()
                    except SQLAlchemyError as e:
                        st.error(
                            f"Erro de banco de dados ao salvar o Histórico: {e}")
                    except Exception as e:
                        st.error(
                            f"Ocorreu um erro inesperado ao salvar o Histórico: {e}")

        except Exception as e:
            st.error(
                f"Ocorreu um erro ao processar o arquivo `historico.parquet`: {e}")

    st.markdown("---")

    # --- UPLOAD SUGESTÕES IA ---
    st.subheader("3. Upload do Arquivo de Sugestões IA")
    uploaded_sugestao = st.file_uploader(
        "Selecione o arquivo `sugestao_ia.parquet`",
        type="parquet",
        key="sugestao_uploader"
    )

    if uploaded_sugestao is not None:
        try:
            df_sugestao = pd.read_parquet(uploaded_sugestao)
            st.write("Amostra dos dados de Sugestões IA (`sugestao_ia`):")
            st.dataframe(df_sugestao.head())

            if st.button("Salvar Sugestões IA no Banco de Dados", type="primary", key="save_sugestao"):
                with st.spinner("Salvando dados de Sugestões IA... Isso pode levar alguns minutos."):
                    try:
                        df_sugestao.to_sql(
                            'sugestao_ia', con=engine, if_exists='replace', index=False)
                        st.success(
                            "Arquivo de Sugestões IA salvo com sucesso no banco de dados!")
                        st.balloons()
                    except SQLAlchemyError as e:
                        st.error(
                            f"Erro de banco de dados ao salvar as Sugestões IA: {e}")
                    except Exception as e:
                        st.error(
                            f"Ocorreu um erro inesperado ao salvar as Sugestões IA: {e}")

        except Exception as e:
            st.error(
                f"Ocorreu um erro ao processar o arquivo `sugestao_ia.parquet`: {e}")
