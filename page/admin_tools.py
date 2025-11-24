import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Tuple
import os

# --- Configurações e Path ---
COLUNA_DESCRICAO = 'Produto' 
COLUNA_ENDERECO = 'Endereço'

# --- Funções de Cache e Helpers ---

@st.cache_resource(ttl=timedelta(hours=24))
def get_today():
    """Retorna a data atual e força o cache a expirar a cada 24h."""
    return datetime.now().date()

def load_data_optimized(parquet_path, excel_path):
    """Tenta ler Parquet (rápido), cai para Excel (lento) se necessário."""
    if os.path.exists(parquet_path):
        # Leitura ultra-rápida
        return pd.read_parquet(parquet_path)
    else:
        # Fallback para Excel
        if 'Mix' in excel_path:
            return pd.read_excel(excel_path, dtype=str)
        return pd.read_excel(excel_path, sheet_name='WMS')

@st.cache_data
def load_data(base_path_no_ext: str) -> Optional[pd.DataFrame]:
    """Carrega dados do arquivo Excel especificado (ou Parquet)."""
    parquet_path = f"{base_path_no_ext}.parquet"
    excel_path = f"{base_path_no_ext}.xlsm" 
    
    if 'Mix' in base_path_no_ext:
        excel_path = f"{base_path_no_ext}.xlsx"

    try:
        return load_data_optimized(parquet_path, excel_path)
    except Exception as e:
        st.error(f"Erro ao carregar o arquivo: {e}")
        return None

def preprocess_wms_data(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """Pré-processa o DataFrame do WMS."""
    df = df.copy()
    
    # 1. Padronização de Colunas (Resolve o problema de Qtd vs qtd)
    # Transforma tudo em minúsculo e remove espaços
    df.columns = df.columns.str.strip().str.lower()
    
    # 2. Validação das colunas essenciais (agora em minúsculo)
    # Aceita 'qtd' (que é o padrão do seu novo CSV)
    col_qtd = 'qtd' if 'qtd' in df.columns else 'Qtd'
    
    if 'datasalva' not in df.columns or 'codigo' not in df.columns or col_qtd not in df.columns:
        st.error(f"Colunas essenciais do WMS não encontradas. Colunas lidas: {list(df.columns)}")
        return None

    # Renomeia para padronizar internamente se necessário
    if col_qtd != 'qtd':
        df.rename(columns={col_qtd: 'qtd'}, inplace=True)

    df.dropna(axis=1, how='all', inplace=True)

    colunas_para_remover = ['lote', 'almoxarifado']
    df.drop(columns=[col for col in colunas_para_remover if col in df.columns], inplace=True)

    # 3. Tratamento de Data (IMPORTANTE: dayfirst=True para datas BR)
    df['datasalva'] = pd.to_datetime(df['datasalva'], dayfirst=True, errors='coerce')
    df.dropna(subset=['datasalva'], inplace=True)
    df['datasalva_formatada'] = df['datasalva'].dt.date
    
    # 4. Tratamento de Quantidade
    df['qtd'] = pd.to_numeric(df['qtd'], errors='coerce').fillna(0)
    
    # Garante que a coluna 'codigo' é int
    df['codigo'] = df['codigo'].fillna(0).astype(int)
    
    return df

def preprocess_mix_data(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """Pré-processa o DataFrame do Mix para pegar a embalagem."""
    df = df.copy()
    
    # Limpeza de nomes das colunas (para garantir match)
    df.columns = df.columns.str.strip()
    
    # Tenta encontrar colunas mesmo se estiverem em minúsculo/maiúsculo
    cols_map_search = {'codigoint': 'codigo', 'embseparacao': 'embalagem'}
    
    # Cria um mapa real baseado nas colunas existentes
    rename_map = {}
    for col in df.columns:
        col_lower = col.lower()
        if col_lower in cols_map_search:
            rename_map[col] = cols_map_search[col_lower]
            
    df.rename(columns=rename_map, inplace=True)
    
    if 'codigo' not in df.columns or 'embalagem' not in df.columns:
        return pd.DataFrame(columns=['codigo', 'embalagem'])
        
    df['codigo'] = pd.to_numeric(df['codigo'], errors='coerce').fillna(0).astype(int)
    
    # Tratamento da embalagem
    df['embalagem'] = pd.to_numeric(
        df['embalagem'].astype(str).str.split(',').str[0].str.split('.').str[0].str.strip(),
        errors='coerce'
    ).fillna(1).astype(int) 
    
    df.loc[df['embalagem'] <= 0, 'embalagem'] = 1
    
    # Remove duplicatas
    df = df[['codigo', 'embalagem']].drop_duplicates(subset=['codigo'])
    
    return df

# --- Função Principal de Exibição ---

def show_consulta_page(engine, base_data_path):
    """Cria a interface da página de consulta de produtos com busca por descrição."""
    st.title("Consulta de Itens por Descrição/Código")

    # 1. Carregar WMS (caminho sem extensão)
    wms_base_path = os.path.join(base_data_path, "WMS")
    df_wms_raw = load_data(wms_base_path)
    
    if df_wms_raw is None:
        st.error(f"Arquivo 'WMS' não encontrado. Faça o upload na página de Admin.")
        return

    df_wms = preprocess_wms_data(df_wms_raw)
    if df_wms is None:
        return

    # 2. Carregar Mix (caminho sem extensão)
    mix_base_path = os.path.join(base_data_path, "__MixAtivoSistema")
    df_mix_raw = load_data(mix_base_path)
    
    # Prepara o Mix (se existir)
    if df_mix_raw is not None:
        df_mix = preprocess_mix_data(df_mix_raw)
    else:
        df_mix = pd.DataFrame(columns=['codigo', 'embalagem'])

    # 3. Filtragem de Data
    hoje = get_today() 
    
    # Verifica se temos dados de hoje
    df_hoje = df_wms[df_wms['datasalva_formatada'] == hoje]

    # Se não tiver dados de hoje, pega a ÚLTIMA data disponível no arquivo
    ultima_data_disponivel = df_wms['datasalva_formatada'].max()

    if df_hoje.empty:
        st.warning(f"Não há informações para a data de hoje ({hoje.strftime('%d/%m/%Y')}).")
        
        if pd.notnull(ultima_data_disponivel):
             st.info(f"A data mais recente encontrada no sistema é: {ultima_data_disponivel.strftime('%d/%m/%Y')}")
             data_pesquisa = st.date_input("Escolha a data da pesquisa:", value=ultima_data_disponivel)
        else:
             data_pesquisa = st.date_input("Escolha a data da pesquisa:", value=hoje)
             
        df_filtrado = df_wms[df_wms['datasalva_formatada'] == data_pesquisa]
    else:
        df_filtrado = df_hoje
    
    if df_filtrado.empty:
        st.info("Nenhum dado encontrado para a data selecionada.")
        return
        
    # --- CRUZAMENTO COM MIX ---
    if not df_mix.empty:
        df_filtrado = pd.merge(df_filtrado, df_mix, on='codigo', how='left')
        df_filtrado['embalagem'] = df_filtrado['embalagem'].fillna(1).astype(int)
    else:
        df_filtrado['embalagem'] = 1

    st.markdown("---")
    st.write(f"Dados exibidos para a data: **{df_filtrado['datasalva_formatada'].iloc[0].strftime('%d/%m/%Y')}**")

    # --- CAMPOS DE BUSCA ---
    st.subheader("Buscar Item")
    
    col_busca_desc, col_busca_cod = st.columns(2)

    with col_busca_desc:
        termo_busca = st.text_input("Digite a descrição ou parte dela:")

    with col_busca_cod:
        codigo_direto = st.text_input("Ou digite o Código (apenas números):")

    item_selecionado_code = None
    
    # Ajuste de nome da coluna de descrição (pode variar minúsculo/maiúsculo)
    # Procura uma coluna que pareça ser 'produto' ou 'descricao'
    col_desc_real = 'produto' if 'produto' in df_filtrado.columns else None
    if not col_desc_real:
         # Tenta achar qualquer coluna de texto que não seja data
         for c in df_filtrado.columns:
             if df_filtrado[c].dtype == 'object' and c not in ['datasalva', 'endereco']:
                 col_desc_real = c
                 break
    
    if codigo_direto and codigo_direto.isdigit():
        item_selecionado_code = int(codigo_direto)
        termo_busca = None 
        
    elif termo_busca:
        if not col_desc_real:
             st.error(f"Coluna de descrição do produto não identificada no arquivo.")
             return

        df_filtrado['Descrição_Lower'] = df_filtrado[col_desc_real].astype(str).str.lower()
        termo_lower = termo_busca.lower()
        
        mask = df_filtrado['Descrição_Lower'].str.contains(termo_lower, na=False)
        resultados_parciais = df_filtrado[mask].sort_values(by=col_desc_real, ascending=True)

        opcoes_unicas = resultados_parciais.drop_duplicates(subset=['codigo'])
        
        lista_opcoes = opcoes_unicas.apply(
            lambda row: f"{row[col_desc_real]} (Código: {row['codigo']})", 
            axis=1
        ).tolist()
        
        if lista_opcoes:
            escolha = st.selectbox(
                "Selecione o produto na lista:",
                options=[''] + lista_opcoes,
                index=0
            )
            
            if escolha:
                try:
                    code_str = escolha.split('(Código: ')[1].strip(')')
                    item_selecionado_code = int(float(code_str))
                except Exception as e:
                    pass 
        else:
            st.warning("Nenhum produto encontrado com o termo digitado.")

    # --- EXIBIÇÃO FINAL DO RESULTADO ---

    if item_selecionado_code:
        resultados_finais = df_filtrado[df_filtrado['codigo'] == item_selecionado_code].copy()

        if not resultados_finais.empty:
            st.write("### Resultado da Busca")
            
            descricao_produto = results_desc = resultados_finais[col_desc_real].iloc[0] if col_desc_real else "Item sem descrição"
            emb_produto = int(resultados_finais['embalagem'].iloc[0])
            
            st.markdown(f"#### {descricao_produto}")
            
            if emb_produto == 1:
                st.warning(f"⚠️ Embalagem unitária ou não encontrada no Mix (1 un/cx).")
            else:
                st.caption(f"Embalagem: {emb_produto} un/cx")

            # Cálculos usando a coluna padronizada 'qtd'
            total_unidades = resultados_finais['qtd'].sum()
            total_caixas = total_unidades / emb_produto
            
            col_metric1, col_metric2 = st.columns(2)
            col_metric1.metric(label="Total (Unidades)", value=f"{total_unidades:,.0f}")
            col_metric2.metric(label="Total (Caixas)", value=f"{total_caixas:,.1f} CX")
            
            resultados_finais['Qtd (Caixas)'] = (resultados_finais['qtd'] / resultados_finais['embalagem']).round(1)

            # Exibe colunas formatadas
            col_end_real = 'endereço' if 'endereço' in resultados_finais.columns else 'endereco'
            if col_end_real in resultados_finais.columns:
                enderecos_encontrados = resultados_finais[col_end_real].unique()
                st.write("### Endereços")
                for endereco in enderecos_encontrados:
                    st.write(f"- {endereco}")
            
            st.write("---")
            
            # Tabela Detalhada
            # Renomeia 'qtd' para 'Qtd' para ficar bonito na tabela
            resultados_finais.rename(columns={'qtd': 'Qtd'}, inplace=True)
            
            cols_to_show = [c for c in resultados_finais.columns if c not in ['datasalva', 'datasalva_formatada', 'Descrição_Lower', 'embalagem']]
            
            # Ordenação visual das colunas
            if 'Qtd' in cols_to_show and 'Qtd (Caixas)' in cols_to_show:
                cols_to_show.remove('Qtd (Caixas)')
                try:
                    idx_qtd = cols_to_show.index('Qtd')
                    cols_to_show.insert(idx_qtd + 1, 'Qtd (Caixas)')
                except: pass
                
            st.dataframe(resultados_finais[cols_to_show], hide_index=True)
        else:
            st.warning(f"Nenhum item encontrado com o código {item_selecionado_code} na data exibida.")
    
    elif not termo_busca and not codigo_direto:
        st.write("### Planilha do Dia (Primeiras Linhas)")
        df_preview = df_filtrado.head(10).copy()
        df_preview['Qtd (Caixas)'] = (df_preview['qtd'] / df_preview['embalagem']).round(1)
        df_preview.rename(columns={'qtd': 'Qtd'}, inplace=True)
        
        cols_to_show = [c for c in df_preview.columns if c not in ['datasalva', 'datasalva_formatada', 'Descrição_Lower', 'embalagem']]
        
        st.dataframe(df_preview[cols_to_show], hide_index=True)
