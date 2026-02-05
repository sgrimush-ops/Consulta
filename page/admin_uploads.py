import os
import io
import hashlib
import streamlit as st
import pandas as pd


def show_admin_uploads_page(engine):
    """
    Cria a interface para upload do arquivo base con5cod.parquet.
    """
    st.title("⚙️ Administração de Uploads de Base")
    st.markdown(
        "Faça o upload do arquivo `con5cod.parquet` para atualizar a base de "
        "produtos. **Atenção:** o arquivo enviado substituirá completamente o "
        "arquivo existente em `bdados/`.")

    st.subheader("Upload do Arquivo con5cod.parquet")
    col_upload_actions, _ = st.columns([1, 3])
    with col_upload_actions:
        if st.button("Limpar upload / amostra"):
            st.session_state.pop("con5cod_uploader", None)
            st.session_state.pop("con5cod_preview_hash", None)
            st.rerun()

    uploaded_file = st.file_uploader(
        "Selecione o arquivo `con5cod.parquet`",
        type="parquet",
        key="con5cod_uploader"
    )

    if uploaded_file is not None:
        try:
            uploaded_bytes = uploaded_file.getvalue()
            if not uploaded_bytes:
                st.warning("Arquivo vazio. Verifique o upload e tente novamente.")
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
