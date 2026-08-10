import streamlit as st
import pandas as pd
import hashlib
import io
import os


def _normalizar_caminho(caminho):
    return os.path.abspath(os.path.normpath(caminho))


def _resolver_pasta_dados(base_data_path=None):
    """Resolve pasta de dados priorizando disco persistente no Render."""
    if base_data_path:
        return os.path.join(base_data_path, "bdados")

    render_disk = os.environ.get("RENDER_DISK_PATH")
    if render_disk:
        return os.path.join(render_disk, "bdados")

    return "bdados"


def _resolver_pastas_destino(base_data_path=None):
    """Resolve todas as pastas de destino uteis para manter compatibilidade."""
    caminhos = []

    # Pasta principal (persistente no Render quando BASE_DATA_PATH = RENDER_DISK_PATH).
    caminhos.append(_resolver_pasta_dados(base_data_path))

    # Pasta local do projeto para telas antigas que ainda leem "bdados" relativo.
    pasta_local_repo = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "bdados")
    )
    caminhos.append(pasta_local_repo)

    # Remove duplicados preservando ordem.
    caminhos = list(dict.fromkeys(_normalizar_caminho(c) for c in caminhos))
    return caminhos


def _salvar_em_todas_as_pastas(conteudo, nome_arquivo, base_data_path=None):
    """Salva o arquivo em todas as pastas de destino resolvidas."""
    caminhos_salvos = []
    for pasta in _resolver_pastas_destino(base_data_path):
        os.makedirs(pasta, exist_ok=True)
        destino = os.path.join(pasta, nome_arquivo)
        with open(destino, "wb") as f:
            f.write(conteudo)
        caminhos_salvos.append(_normalizar_caminho(destino))
    return caminhos_salvos


def _listar_parquets_em_pasta(pasta):
    """Lista arquivos parquet existentes na pasta informada."""
    if not os.path.isdir(pasta):
        return []
    arquivos = []
    for nome in sorted(os.listdir(pasta)):
        caminho = os.path.join(pasta, nome)
        if os.path.isfile(caminho) and nome.lower().endswith(".parquet"):
            arquivos.append(nome)
    return arquivos


def _normalizar_nomes_colunas(df):
    """Remove espaços extras e quebras de linha nos nomes de colunas."""
    df = df.copy()
    df.columns = [str(col).strip() for col in df.columns]
    return df


def show_admin_uploads_page(engine=None, base_data_path=None):
    """
    Cria a interface para upload dos arquivos
    ean_dun.parquet, query.parquet e consumo.parquet.
    """
    if engine is None:
        from app import get_engine
        engine = get_engine()
    
    st.title("⚙️ Administração de Uploads de Base")
    
    pasta_dados = _resolver_pasta_dados(base_data_path)
    pastas_destino = _resolver_pastas_destino(base_data_path)
    for pasta in pastas_destino:
        os.makedirs(pasta, exist_ok=True)

    st.markdown(
        "Faça o upload dos arquivos `ean_dun.parquet`, "
        "`query.parquet` e `consumo.parquet`."
    )
    st.caption(f"Pasta principal de armazenamento: {os.path.abspath(pasta_dados)}")
    st.caption("Pastas sincronizadas para compatibilidade: " + " | ".join(pastas_destino))

    st.subheader("Diagnóstico de Arquivos Parquet")
    for pasta in pastas_destino:
        arquivos = _listar_parquets_em_pasta(pasta)
        arquivos_txt = ", ".join(arquivos) if arquivos else "(nenhum .parquet)"
        st.caption(f"{pasta}: {arquivos_txt}")

    st.subheader("Upload do Arquivo ean_dun.parquet")

    col_ean_actions, _ = st.columns([1, 3])
    with col_ean_actions:
        if st.button("Limpar upload EAN/DUN", key="clear_ean_dun_upload"):
            st.session_state.pop("ean_dun_uploader", None)
            st.session_state.pop("ean_dun_preview_hash", None)
            st.rerun()

    uploaded_ean_dun = st.file_uploader(
        "Selecione o arquivo `ean_dun.parquet`",
        type="parquet",
        key="ean_dun_uploader"
    )

    if uploaded_ean_dun is not None:
        try:
            ean_dun_bytes = uploaded_ean_dun.getvalue()
            if not ean_dun_bytes:
                st.warning("Arquivo EAN/DUN vazio. Verifique o upload e tente novamente.")
                return

            ean_dun_hash = hashlib.sha256(ean_dun_bytes).hexdigest()
            st.session_state["ean_dun_preview_hash"] = ean_dun_hash

            st.caption(
                f"Arquivo carregado: {uploaded_ean_dun.name} | "
                f"Tamanho: {len(ean_dun_bytes):,} bytes | "
                f"Hash: {ean_dun_hash[:12]}"
            )

            df_ean_dun = _normalizar_nomes_colunas(
                pd.read_parquet(io.BytesIO(ean_dun_bytes))
            )
            st.write("Amostra dos dados EAN/DUN (upload atual):")
            st.dataframe(df_ean_dun.head())
            st.info(f"📊 Total de linhas: {len(df_ean_dun):,}")
            st.caption("Colunas detectadas: " + ", ".join(df_ean_dun.columns.astype(str).tolist()))

            if st.button("Salvar ean_dun em bdados", type="primary", key="save_ean_dun"):
                with st.spinner("Salvando ean_dun.parquet..."):
                    destinos_salvos = _salvar_em_todas_as_pastas(
                        ean_dun_bytes,
                        "ean_dun.parquet",
                        base_data_path=base_data_path,
                    )

                    st.cache_data.clear()
                    st.success("✅ Arquivo ean_dun.parquet atualizado com sucesso!")
                    st.caption("Arquivos salvos em: " + " | ".join(destinos_salvos))
                    st.caption(
                        "Se estiver no Render, configure EAN_DUN_PARQUET_PATH "
                        f"com este caminho: {destinos_salvos[0]}"
                    )
                    st.balloons()
        except Exception as e:
            st.error(
                "Ocorreu um erro ao processar o arquivo `ean_dun.parquet`: "
                f"{e}"
            )

    st.divider()
    st.subheader("Upload do Arquivo query.parquet")

    col_query_actions, _ = st.columns([1, 3])
    with col_query_actions:
        if st.button("Limpar upload query", key="clear_query_upload"):
            st.session_state.pop("query_uploader", None)
            st.session_state.pop("query_preview_hash", None)
            st.rerun()

    uploaded_query = st.file_uploader(
        "Selecione o arquivo `query.parquet`",
        type="parquet",
        key="query_uploader"
    )

    if uploaded_query is not None:
        try:
            query_bytes = uploaded_query.getvalue()
            if not query_bytes:
                st.warning("Arquivo query vazio. Verifique o upload e tente novamente.")
                return

            query_hash = hashlib.sha256(query_bytes).hexdigest()
            st.session_state["query_preview_hash"] = query_hash

            st.caption(
                f"Arquivo carregado: {uploaded_query.name} | "
                f"Tamanho: {len(query_bytes):,} bytes | "
                f"Hash: {query_hash[:12]}"
            )

            df_query = _normalizar_nomes_colunas(
                pd.read_parquet(io.BytesIO(query_bytes))
            )
            st.write("Amostra dos dados query (upload atual):")
            st.dataframe(df_query.head())
            st.info(f"📊 Total de linhas: {len(df_query):,}")
            st.caption("Colunas detectadas: " + ", ".join(df_query.columns.astype(str).tolist()))

            if st.button("Salvar query em bdados", type="primary", key="save_query"):
                with st.spinner("Salvando query.parquet..."):
                    destinos_salvos = _salvar_em_todas_as_pastas(
                        query_bytes,
                        "query.parquet",
                        base_data_path=base_data_path,
                    )

                    st.cache_data.clear()
                    st.success("✅ Arquivo query.parquet atualizado com sucesso!")
                    st.caption("Arquivos salvos em: " + " | ".join(destinos_salvos))
                    st.balloons()
        except Exception as e:
            st.error(
                "Ocorreu um erro ao processar o arquivo `query.parquet`: "
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
                    _ = _salvar_em_todas_as_pastas(
                        consumo_bytes,
                        "consumo.parquet",
                        base_data_path=base_data_path,
                    )

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
