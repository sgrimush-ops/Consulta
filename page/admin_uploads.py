import os
import io
import hashlib
import streamlit as st
import pandas as pd


def show_admin_uploads_page(engine):
    """
    Cria a interface para upload dos arquivos
    con5cod.parquet e consumo.parquet.
    """
    st.title("⚙️ Administração de Uploads de Base")
    st.markdown(
        "Faça o upload dos arquivos `con5cod.parquet` (base local) e "
        "`consumo.parquet` (carga no banco)."
    )

    st.subheader("Upload do Arquivo con5cod.parquet")
    col_upload_actions, _ = st.columns([1, 3])
    with col_upload_actions:
        if st.button("Limpar upload / amostra"):
            st.session_state.pop("con5cod_uploader", None)
            st.session_state.pop("con5cod_preview_hash", None)
            st.rerun()

        if st.button("Limpar cache do mix"):
            st.cache_data.clear()
            st.success("Cache limpo. Reabra a pagina de mix para atualizar.")

    uploaded_file = st.file_uploader(
        "Selecione o arquivo `con5cod.parquet`",
        type="parquet",
        key="con5cod_uploader"
    )

    if uploaded_file is not None:
        try:
            uploaded_bytes = uploaded_file.getvalue()
            if not uploaded_bytes:
                st.warning(
                    "Arquivo vazio. Verifique o upload e tente novamente."
                )
                return

            preview_hash = hashlib.sha256(uploaded_bytes).hexdigest()
            st.session_state["con5cod_preview_hash"] = preview_hash

            st.caption(
                f"Arquivo carregado: {uploaded_file.name} | "
                f"Tamanho: {len(uploaded_bytes):,} bytes | "
                f"Hash: {preview_hash[:12]}"
            )

            df_preview = pd.read_parquet(io.BytesIO(uploaded_bytes))
            st.write("Amostra dos dados do arquivo (upload atual):")
            st.dataframe(df_preview.head())
            st.info(f"📊 Total de linhas: {len(df_preview):,}")

            if st.button(
                "Salvar arquivo em bdados",
                type="primary",
                key="save_con5cod"
            ):
                with st.spinner(
                    "Salvando arquivo... Isso pode levar alguns minutos."
                ):
                    os.makedirs("bdados", exist_ok=True)
                    destino = os.path.join("bdados", "con5cod.parquet")
                    with open(destino, "wb") as f:
                        f.write(uploaded_bytes)

                    st.cache_data.clear()

                    st.success(
                        "Arquivo con5cod.parquet atualizado com sucesso!"
                    )

                    st.caption(
                        "Observacao: algumas telas podem sobrepor dados do "
                        "parquet com registros do banco (produtos_custom)."
                    )
                    st.balloons()
        except Exception as e:
            st.error(
                "Ocorreu um erro ao processar o arquivo `con5cod.parquet`: "
                f"{e}"
            )

    st.divider()
    st.subheader("Upload do Arquivo consumo.parquet para Banco de Dados")

    col_consumo_actions, _ = st.columns([1, 3])
    with col_consumo_actions:
        if st.button("Limpar upload consumo", key="clear_consumo_upload"):
            st.session_state.pop("consumo_uploader", None)
            st.session_state.pop("consumo_preview_hash", None)
            st.rerun()

    uploaded_consumo = st.file_uploader(
        "Selecione o arquivo `consumo.parquet`",
        type="parquet",
        key="consumo_uploader"
    )

    if uploaded_consumo is not None:
        try:
            consumo_bytes = uploaded_consumo.getvalue()
            if not consumo_bytes:
                st.warning(
                    "Arquivo de consumo vazio. Verifique o upload e tente "
                    "novamente."
                )
                return

            consumo_hash = hashlib.sha256(consumo_bytes).hexdigest()
            st.session_state["consumo_preview_hash"] = consumo_hash

            st.caption(
                f"Arquivo carregado: {uploaded_consumo.name} | "
                f"Tamanho: {len(consumo_bytes):,} bytes | "
                f"Hash: {consumo_hash[:12]}"
            )

            df_consumo = pd.read_parquet(io.BytesIO(consumo_bytes))
            st.write("Amostra dos dados de consumo (upload atual):")
            st.dataframe(df_consumo.head())
            st.info(f"📊 Total de linhas: {len(df_consumo):,}")

            if st.button(
                "Salvar consumo no banco",
                type="primary",
                key="save_consumo_db"
            ):
                with st.spinner(
                    "Enviando consumo para o banco... Isso pode levar alguns "
                    "minutos."
                ):
                    with engine.begin() as conn:
                        df_consumo.to_sql(
                            "consumo",
                            conn,
                            if_exists="replace",
                            index=False,
                            method="multi",
                            chunksize=5000
                        )

                    st.cache_data.clear()
                    st.success(
                        "Tabela `consumo` atualizada com sucesso no banco "
                        "de dados!"
                    )
                    st.balloons()
        except Exception as e:
            st.error(
                "Ocorreu um erro ao processar o arquivo `consumo.parquet`: "
                f"{e}"
            )
