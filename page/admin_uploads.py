import os
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
    uploaded_file = st.file_uploader(
        "Selecione o arquivo `con5cod.parquet`",
        type="parquet",
        key="con5cod_uploader"
    )

    if uploaded_file is not None:
        try:
            df_preview = pd.read_parquet(uploaded_file)
            st.write("Amostra dos dados do arquivo:")
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
                    uploaded_file.seek(0)
                    with open(destino, "wb") as f:
                        f.write(uploaded_file.read())
                    st.success(
                        "Arquivo con5cod.parquet atualizado com sucesso!"
                    )
                    st.balloons()
        except Exception as e:
            st.error(
                "Ocorreu um erro ao processar o arquivo `con5cod.parquet`: "
                f"{e}"
            )
