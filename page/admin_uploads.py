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


def validate_con5cod_schema(df):
    """
    Valida se o arquivo con5cod.parquet tem a estrutura correta.
    Retorna (valido: bool, mensagem: str, colunas_mapeadas: dict)
    """
    df = _normalizar_nomes_colunas(df)

    # Colunas esperadas (antigos e novos nomes)
    col_cod = {
        'codigoconsinco', 'Código Produto', 'Codigo Produto',
        'cod_consinco', 'codigo_produto'
    }
    col_desc = {
        'descricao', 'Empresa : Produto', 'Empresa: Produto',
        'produto', 'empresa_produto'
    }
    col_emb = {'Emb', 'embalagem', 'EmbSeparacao', 'emb_separacao'}
    col_mix = {'Mix', 'ltmix', 'status_mix'}
    col_trans = {'transicao', 'CODACESSO', 'codigo_transicao', 'transacao'}
    
    colunas_arquivo = set(df.columns)
    
    # Verificar colunas obrigatórias
    colunas_mapeadas = {}
    
    # Código do produto (OBRIGATÓRIO)
    match_cod = col_cod & colunas_arquivo
    if not match_cod:
        return False, f"❌ Coluna obrigatória 'Código do Produto' não encontrada. Disponíveis: {', '.join(colunas_arquivo)}", {}
    colunas_mapeadas['cod_consinco'] = match_cod.pop()
    
    # Descrição (OBRIGATÓRIO)
    match_desc = col_desc & colunas_arquivo
    if not match_desc:
        return False, f"❌ Coluna obrigatória 'Descrição/Empresa Produto' não encontrada. Disponíveis: {', '.join(colunas_arquivo)}", {}
    colunas_mapeadas['descricao'] = match_desc.pop()
    
    # Embalagem (OBRIGATÓRIO)
    match_emb = col_emb & colunas_arquivo
    if not match_emb:
        return False, f"❌ Coluna obrigatória 'Embalagem/EmbSeparacao' não encontrada. Disponíveis: {', '.join(colunas_arquivo)}", {}
    colunas_mapeadas['Emb'] = match_emb.pop()
    
    # Mix (OBRIGATÓRIO)
    match_mix = col_mix & colunas_arquivo
    if not match_mix:
        return False, f"❌ Coluna obrigatória 'Mix/ltmix' não encontrada. Disponíveis: {', '.join(colunas_arquivo)}", {}
    colunas_mapeadas['Mix'] = match_mix.pop()
    
    # Transição (RECOMENDADO)
    match_trans = col_trans & colunas_arquivo
    if match_trans:
        colunas_mapeadas['transicao'] = match_trans.pop()
    else:
        colunas_mapeadas['transicao'] = None
    
    # Capacidade (OPCIONAL)
    if 'CapacidadeGondola' in colunas_arquivo or 'capacidade' in colunas_arquivo:
        colunas_mapeadas['CapacidadeGondola'] = 'CapacidadeGondola' if 'CapacidadeGondola' in colunas_arquivo else 'capacidade'
    else:
        colunas_mapeadas['CapacidadeGondola'] = None
    
    # Validar conteúdo básico
    if len(df) == 0:
        return False, "❌ Arquivo vazio (0 linhas)", colunas_mapeadas
    
    # Validar tipos de dados
    try:
        pd.to_numeric(df[colunas_mapeadas['cod_consinco']], errors='coerce')
        pd.to_numeric(df[colunas_mapeadas['Emb']], errors='coerce')
    except Exception as e:
        return False, f"❌ Erro ao validar tipos de dados: {e}", colunas_mapeadas
    
    msg = f"✅ Schema válido!\n"
    msg += f"   • Código: '{colunas_mapeadas['cod_consinco']}'\n"
    msg += f"   • Descrição: '{colunas_mapeadas['descricao']}'\n"
    msg += f"   • Embalagem: '{colunas_mapeadas['Emb']}'\n"
    msg += f"   • Mix: '{colunas_mapeadas['Mix']}'\n"
    if colunas_mapeadas['transicao']:
        msg += f"   • Transição/Acesso: '{colunas_mapeadas['transicao']}'\n"
    if colunas_mapeadas['CapacidadeGondola']:
        msg += f"   • Capacidade Gôndola: '{colunas_mapeadas['CapacidadeGondola']}'\n"
    msg += f"   • Total: {len(df):,} registros"
    
    return True, msg, colunas_mapeadas


def show_admin_uploads_page(engine=None, base_data_path=None):
    """
    Cria a interface para upload dos arquivos
    con5cod.parquet e consumo.parquet.
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
        "Faça o upload dos arquivos `con5cod.parquet`, `ean_dun.parquet` "
        "`query.parquet` e `consumo.parquet`."
    )
    st.caption(f"Pasta principal de armazenamento: {os.path.abspath(pasta_dados)}")
    st.caption("Pastas sincronizadas para compatibilidade: " + " | ".join(pastas_destino))

    st.subheader("Diagnóstico de Arquivos Parquet")
    for pasta in pastas_destino:
        arquivos = _listar_parquets_em_pasta(pasta)
        arquivos_txt = ", ".join(arquivos) if arquivos else "(nenhum .parquet)"
        st.caption(f"{pasta}: {arquivos_txt}")

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

            df_preview = _normalizar_nomes_colunas(
                pd.read_parquet(io.BytesIO(uploaded_bytes))
            )
            
            # Validar schema
            is_valid, validation_msg, col_map = validate_con5cod_schema(df_preview)
            
            if is_valid:
                st.success(validation_msg)
            else:
                st.error(validation_msg)
                st.warning("❌ Arquivo não pode ser salvo. Corrija o schema e tente novamente.")
                return
            
            # Mapear colunas para preview
            col_mapping = {
                col_map['cod_consinco']: 'cod_consinco',
                col_map['descricao']: 'descricao',
                col_map['Emb']: 'Emb',
                col_map['Mix']: 'Mix',
            }
            if col_map.get('transicao'):
                col_mapping[col_map['transicao']] = 'transicao'
            if col_map.get('CapacidadeGondola'):
                col_mapping[col_map['CapacidadeGondola']] = 'CapacidadeGondola'
            
            df_preview_mapped = df_preview.rename(columns=col_mapping)
            
            st.write("Amostra dos dados do arquivo (upload atual):")
            st.dataframe(df_preview_mapped.head())
            st.info(f"📊 Total de linhas: {len(df_preview):,}")

            if st.button(
                "Salvar arquivo em bdados",
                type="primary",
                key="save_con5cod"
            ):
                # Validar novamente antes de salvar
                is_valid_final, _, _ = validate_con5cod_schema(df_preview)
                
                if not is_valid_final:
                    st.error("❌ Validação falhou na hora de salvar. O arquivo foi modificado? Recarregue.")
                    return
                
                with st.spinner(
                    "Salvando arquivo... Isso pode levar alguns minutos."
                ):
                    destinos_salvos = _salvar_em_todas_as_pastas(
                        uploaded_bytes,
                        "con5cod.parquet",
                        base_data_path=base_data_path,
                    )

                    st.cache_data.clear()

                    st.success(
                        "✅ Arquivo con5cod.parquet atualizado com sucesso!"
                    )

                    st.caption(
                        "Observacao: algumas telas podem sobrepor dados do "
                        "parquet com registros do banco (produtos_custom)."
                    )
                    st.caption("Arquivos salvos em: " + " | ".join(destinos_salvos))
                    st.balloons()
        except Exception as e:
            st.error(
                "Ocorreu um erro ao processar o arquivo `con5cod.parquet`: "
                f"{e}"
            )

    st.divider()
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
