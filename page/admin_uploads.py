import streamlit as st
import pandas as pd
import hashlib
import io
import os


def validate_con5cod_schema(df):
    """
    Valida se o arquivo con5cod.parquet tem a estrutura correta.
    Retorna (valido: bool, mensagem: str, colunas_mapeadas: dict)
    """
    # Colunas esperadas (antigos e novos nomes)
    col_cod = {'codigoconsinco', 'Código Produto', 'cod_consinco', 'codigo_produto'}
    col_desc = {'descricao', 'Empresa : Produto', 'produto', 'empresa_produto'}
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


def show_admin_uploads_page(engine=None):
    """
    Cria a interface para upload dos arquivos
    con5cod.parquet e consumo.parquet.
    """
    if engine is None:
        from app import get_engine
        engine = get_engine()
    
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
                    os.makedirs("bdados", exist_ok=True)
                    destino = os.path.join("bdados", "con5cod.parquet")
                    with open(destino, "wb") as f:
                        f.write(uploaded_bytes)

                    st.cache_data.clear()

                    st.success(
                        "✅ Arquivo con5cod.parquet atualizado com sucesso!"
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
                    os.makedirs("bdados", exist_ok=True)
                    consumo_destino = os.path.join("bdados", "consumo.parquet")
                    with open(consumo_destino, "wb") as f:
                        f.write(consumo_bytes)

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
