import streamlit as st
import pandas as pd
import os


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
    except Exception as e:
        st.error(f"Erro ao carregar arquivo de dados: {e}")
        st.stop()
    
    # Filtrar apenas produtos ativos
    df_mix_ativo = df_mix[df_mix['Mix'] == 'A'].copy()
    
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
        ["Por Código Consinco", "Por Descrição"],
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
                resultado = df_mix_ativo[df_mix_ativo['cod_consinco'] == codigo_int]
                
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
                        st.info(f"**Embalagem:** {produto['Emb']} unidades")
                    
                    # Exibir em formato de tabela também
                    st.markdown("### Detalhes Completos")
                    df_display = resultado.copy()
                    df_display.columns = ['Código Consinco', 'Descrição', 'Código Transição', 'Status', 'Embalagem']
                    st.dataframe(df_display, use_container_width=True, hide_index=True)
                else:
                    st.warning(f"⚠️ Produto com código {codigo_int} não encontrado no mix ativo.")
                    
                    # Verificar se existe mas está suspenso
                    resultado_suspenso = df_mix[(df_mix['cod_consinco'] == codigo_int) & (df_mix['Mix'] == 'S')]
                    if not resultado_suspenso.empty:
                        st.info("ℹ️ Este produto existe mas está **SUSPENSO** no sistema.")
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
