import streamlit as st
import pandas as pd
import os
from sqlalchemy import text


def get_correcoes_embalagens(engine):
    """Busca correções de embalagens do banco de dados."""
    try:
        query = text("""
            SELECT cod_consinco, embalagem_corrigida
            FROM produtos_correcoes
        """)

        with engine.connect() as conn:
            df = pd.read_sql(query, conn)

        return df
    except Exception:
        # Tabela não existe ou erro
        return pd.DataFrame()


def get_produtos_custom(engine):
    """Busca produtos customizados do banco para sobrepor ao parquet."""
    try:
        query = text("""
            SELECT cod_consinco, descricao, transicao,
                   embalagem AS Emb, status_mix AS Mix
            FROM produtos_custom
        """)
        with engine.connect() as conn:
            df = pd.read_sql(query, conn)
        return df
    except Exception:
        return pd.DataFrame()


def show_consulta_mix_page(engine, base_data_path):
    """
    Página para consulta de produtos do mix ativo.
    Permite busca por código Consinco ou por descrição.
    """
    st.title("🔍 Consulta de Mix de Produtos")
    st.markdown("---")

    # Carregar o arquivo parquet
    parquet_path = os.path.join("bdados", "con5cod.parquet")

    if not os.path.exists(parquet_path):
        st.error(f"Arquivo de dados não encontrado: {parquet_path}")
        st.stop()

    try:
        df_mix = pd.read_parquet(parquet_path)
        df_mix["origem"] = "Parquet"

        # Sobrepor produtos customizados (quando existirem)
        df_custom = get_produtos_custom(engine)
        if not df_custom.empty:
            df_custom["origem"] = "Banco"
            if (
                "Emb" not in df_custom.columns
                and "embalagem" in df_custom.columns
            ):
                df_custom = df_custom.rename(columns={"embalagem": "Emb"})
            if (
                "Mix" not in df_custom.columns
                and "status_mix" in df_custom.columns
            ):
                df_custom = df_custom.rename(columns={"status_mix": "Mix"})

            # Remove do parquet os códigos que existem no banco
            df_mix = df_mix[
                ~df_mix["cod_consinco"].isin(df_custom["cod_consinco"])
            ].copy()
            df_mix = pd.concat([df_mix, df_custom], ignore_index=True)

        # Normalizações básicas
        if "cod_consinco" in df_mix.columns:
            df_mix["cod_consinco"] = pd.to_numeric(
                df_mix["cod_consinco"], errors="coerce"
            )
            df_mix = df_mix.dropna(subset=["cod_consinco"]).copy()
            df_mix["cod_consinco"] = df_mix["cod_consinco"].astype(int)
        if "Mix" in df_mix.columns:
            df_mix["Mix"] = (
                df_mix["Mix"].astype(str).str.strip().str.upper()
            )
        if "transicao" in df_mix.columns:
            df_mix["transicao"] = pd.to_numeric(
                df_mix["transicao"], errors="coerce"
            )

        # Aplicar correções de embalagens do banco de dados
        df_correcoes = get_correcoes_embalagens(engine)
        if not df_correcoes.empty:
            df_mix = df_mix.merge(
                df_correcoes,
                on="cod_consinco",
                how="left"
            )
            # Usar embalagem corrigida se existir (somente para Parquet)
            df_mix["Emb_Original"] = df_mix["Emb"]
            aplicar = (
                df_mix["embalagem_corrigida"].notna()
                & (df_mix["origem"] == "Parquet")
            )
            df_mix.loc[aplicar, "Emb"] = df_mix.loc[
                aplicar, "embalagem_corrigida"
            ]
            df_mix["Tem_Correcao"] = aplicar
            df_mix = df_mix.drop(columns=["embalagem_corrigida"])
        else:
            df_mix["Tem_Correcao"] = False

    except Exception as e:
        st.error(f"Erro ao carregar arquivo de dados: {e}")
        st.stop()

    # Filtrar apenas produtos ativos
    df_mix_ativo = df_mix[df_mix["Mix"] == "A"].copy()
    
    # Exibir estatísticas
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total de Produtos no Mix", len(df_mix_ativo))
    with col2:
        st.metric("Total de Produtos (Incluindo Suspensos)", len(df_mix))
    with col3:
        produtos_suspensos = len(df_mix[df_mix['Mix'] == 'S'])
        st.metric("Produtos Suspensos", produtos_suspensos)
    
    st.markdown("---")
    
    # Tipo de busca
    st.subheader("Buscar Produto")
    tipo_busca = st.radio(
        "Tipo de busca:",
        ["Por Código Consinco", "Por Código Transição", "Por Descrição"],
        horizontal=True
    )
    
    if tipo_busca == "Por Código Consinco":
        # Busca por código
        codigo_busca = st.text_input(
            "Digite o código Consinco:",
            placeholder="Ex: 10480"
        )
        
        if codigo_busca:
            try:
                codigo_int = int(codigo_busca)
                codigo_norm = str(codigo_int)
                cod_series = (
                    df_mix["cod_consinco"]
                    .astype(str)
                    .str.replace(r"\.0$", "", regex=True)
                    .str.strip()
                    .str.lstrip("0")
                )
                resultado_all = df_mix[
                    (df_mix["cod_consinco"] == codigo_int)
                    | (cod_series == codigo_norm)
                ]
                resultado = resultado_all[resultado_all["Mix"] == "A"]
                
                if not resultado.empty:
                    st.success(f"✅ Produto encontrado!")
                    
                    # Exibir informações do produto
                    produto = resultado.iloc[0]
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.info(f"**Código Consinco:** {produto['cod_consinco']}")
                        st.info(f"**Descrição:** {produto['descricao']}")
                        st.info(f"**Código Transição (Antigo):** {produto['transicao']}")
                    with col2:
                        st.info(f"**Status:** {'Ativo' if produto['Mix'] == 'A' else 'Suspenso'}")
                        
                        # Mostrar embalagem com indicador se foi corrigida
                        emb_text = f"**Embalagem:** {produto['Emb']} unidades"
                        if produto.get('Tem_Correcao', False):
                            emb_text += f" ⚠️ (Original: {produto.get('Emb_Original', produto['Emb'])})"
                        st.info(emb_text)
                    
                    # Exibir em formato de tabela também
                    st.markdown("### Detalhes Completos")
                    df_display = resultado.copy()
                    df_display.columns = ['Código Consinco', 'Descrição', 'Código Transição', 'Status', 'Embalagem']
                    st.dataframe(df_display, use_container_width=True, hide_index=True)
                else:
                    if not resultado_all.empty:
                        produto = resultado_all.iloc[0]
                        status_raw = produto.get("Mix")
                        if status_raw == "S":
                            status_label = "Suspenso"
                        elif status_raw == "A":
                            status_label = "Ativo"
                        else:
                            status_label = "Indefinido"

                        st.warning(
                            "⚠️ Produto encontrado, mas não está ativo. "
                            f"Status: {status_label}."
                        )
                        st.info(
                            f"Origem: {produto.get('origem', 'N/A')}"
                        )
                    else:
                        st.warning(
                            "⚠️ Produto com código "
                            f"{codigo_int} não encontrado."
                        )
            except ValueError:
                st.error("❌ Por favor, digite apenas números no código.")

    elif tipo_busca == "Por Código Transição":
        codigo_transicao = st.text_input(
            "Digite o código de transição:",
            placeholder="Ex: 3612"
        )

        if codigo_transicao:
            try:
                codigo_int = int(codigo_transicao)
                codigo_norm = str(codigo_int)
                trans_series = (
                    df_mix["transicao"]
                    .astype(str)
                    .str.replace(r"\.0$", "", regex=True)
                    .str.strip()
                    .str.lstrip("0")
                )
                resultado_all = df_mix[
                    (df_mix["transicao"] == codigo_int)
                    | (trans_series == codigo_norm)
                ]
                resultado = resultado_all[resultado_all["Mix"] == "A"]

                if not resultado.empty:
                    st.success("✅ Produto encontrado!")
                    produto = resultado.iloc[0]

                    col1, col2 = st.columns(2)
                    with col1:
                        st.info(
                            f"**Código Consinco:** {produto['cod_consinco']}"
                        )
                        st.info(f"**Descrição:** {produto['descricao']}")
                        st.info(
                            f"**Código Transição (Antigo):** {produto['transicao']}"
                        )
                    with col2:
                        st.info(
                            "**Status:** "
                            f"{'Ativo' if produto['Mix'] == 'A' else 'Suspenso'}"
                        )
                        emb_text = (
                            f"**Embalagem:** {produto['Emb']} unidades"
                        )
                        if produto.get("Tem_Correcao", False):
                            emb_text += (
                                " ⚠️ (Original: "
                                f"{produto.get('Emb_Original', produto['Emb'])})"
                            )
                        st.info(emb_text)

                    st.markdown("### Detalhes Completos")
                    df_display = resultado.copy()
                    df_display.columns = [
                        "Código Consinco",
                        "Descrição",
                        "Código Transição",
                        "Status",
                        "Embalagem"
                    ]
                    st.dataframe(
                        df_display,
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    if not resultado_all.empty:
                        produto = resultado_all.iloc[0]
                        status_raw = produto.get("Mix")
                        if status_raw == "S":
                            status_label = "Suspenso"
                        elif status_raw == "A":
                            status_label = "Ativo"
                        else:
                            status_label = "Indefinido"

                        st.warning(
                            "⚠️ Produto encontrado, mas não está ativo. "
                            f"Status: {status_label}."
                        )
                        st.info(
                            f"Origem: {produto.get('origem', 'N/A')}"
                        )
                    else:
                        st.warning(
                            "⚠️ Produto com código de transição "
                            f"{codigo_int} não encontrado."
                        )
            except ValueError:
                st.error("❌ Por favor, digite apenas números no código.")
    
    else:  # Busca por descrição
        descricao_busca = st.text_input(
            "Digite a descrição do produto:",
            placeholder="Ex: CERVEJA"
        )
        
        if descricao_busca and len(descricao_busca) >= 3:
            # Buscar produtos que contenham o termo (case-insensitive)
            mascara = df_mix_ativo['descricao'].str.contains(
                descricao_busca,
                case=False,
                na=False
            )
            resultado = df_mix_ativo[mascara].copy()
            
            if not resultado.empty:
                st.success(f"✅ Encontrado(s) {len(resultado)} produto(s)")
                
                # Renomear colunas para exibição
                df_display = resultado.copy()
                df_display = df_display[['cod_consinco', 'descricao', 'transicao', 'Mix', 'Emb']]
                df_display.columns = ['Código Consinco', 'Descrição', 'Código Transição', 'Status', 'Embalagem']
                
                # Adicionar filtros adicionais
                st.markdown("#### Filtros Adicionais")
                col1, col2 = st.columns(2)
                
                with col1:
                    # Filtro por embalagem
                    embalagens_unicas = sorted(df_display['Embalagem'].unique())
                    filtro_emb = st.multiselect(
                        "Filtrar por Embalagem:",
                        options=embalagens_unicas,
                        default=embalagens_unicas
                    )
                
                if filtro_emb:
                    df_display = df_display[df_display['Embalagem'].isin(filtro_emb)]
                
                # Exibir resultados
                st.markdown("### Resultados da Busca")
                st.dataframe(
                    df_display,
                    use_container_width=True,
                    hide_index=True,
                    height=400
                )
                
                # Opção de download
                csv = df_display.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 Baixar Resultados (CSV)",
                    data=csv,
                    file_name=f"consulta_mix_{descricao_busca}.csv",
                    mime="text/csv"
                )
            else:
                st.warning(f"⚠️ Nenhum produto encontrado com a descrição '{descricao_busca}' no mix ativo.")
        elif descricao_busca:
            st.info("ℹ️ Digite pelo menos 3 caracteres para realizar a busca.")
    
    # Opção de visualizar todos os produtos ativos
    st.markdown("---")
    if st.checkbox("📋 Visualizar todos os produtos do mix ativo"):
        st.markdown("### Todos os Produtos Ativos")
        
        df_display_all = df_mix_ativo.copy()
        df_display_all = df_display_all[['cod_consinco', 'descricao', 'transicao', 'Mix', 'Emb']]
        df_display_all.columns = ['Código Consinco', 'Descrição', 'Código Transição', 'Status', 'Embalagem']
        
        st.dataframe(
            df_display_all,
            use_container_width=True,
            hide_index=True,
            height=500
        )
        
        # Download de todos os produtos
        csv_all = df_display_all.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 Baixar Lista Completa (CSV)",
            data=csv_all,
            file_name="mix_completo_ativo.csv",
            mime="text/csv"
        )
