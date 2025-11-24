import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Tuple
import os

# --- Configurações e Path ---
COLUNA_DESCRICAO = 'Produto' 
COLUNA_ENDERECO = 'Endereço'

# --- Funções de Cache e Helpers ---

@st.cache_resource(ttl=timedelta(minutes=5)) # Reduzi o cache para evitar dados presos
def get_today():
    """Retorna a data atual."""
    return datetime.now().date()

def load_data_optimized(parquet_path, excel_path):
    """Tenta ler Parquet (rápido), cai para Excel (lento) se necessário."""
    if os.path.exists(parquet_path):
        return pd.read_parquet(parquet_path)
    else:
        # Fallback
        if 'Mix' in excel_path:
            return pd.read_excel(excel_path, dtype=str)
        return pd.read_excel(excel_path, sheet_name='WMS')

@st.cache_data(ttl=60) # Cache curto para garantir atualização
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
    """Pré-processa o DataFrame do WMS com limpeza rigorosa."""
    df = df.copy()
    
    # 1. Padronização de Colunas
    df.columns = df.columns.str.strip().str.lower()
    
    # 2. Validação e Renomeação de colunas
    col_qtd = 'qtd' if 'qtd' in df.columns else 'Qtd'
    
    if 'datasalva' not in df.columns or 'codigo' not in df.columns or col_qtd not in df.columns:
        st.error(f"Colunas essenciais não encontradas. Lidas: {list(df.columns)}")
        return None

    if col_qtd != 'qtd':
        df.rename(columns={col_qtd: 'qtd'}, inplace=True)

    # 3. Limpeza Profunda de Dados (Vital para CSV)
    # Garante que datasalva seja string e remove espaços/quebras de linha que quebram o date parser
    if df['datasalva'].dtype == 'object':
        df['datasalva'] = df['datasalva'].astype(str).str.strip()

    # Converte Data (dayfirst=True para 24/11 ser 24 de Nov)
    df['datasalva'] = pd.to_datetime(df['datasalva'], dayfirst=True, errors='coerce')
    
    # Remove linhas onde a data falhou
    df.dropna(subset=['datasalva'], inplace=True)
    df['datasalva_formatada'] = df['datasalva'].dt.date
    
    # Converte Quantidade (troca vírgula por ponto se for string brasileira)
    if df['qtd'].dtype == 'object':
        df['qtd'] = df['qtd'].str.replace(',', '.', regex=False)
    df['qtd'] = pd.to_numeric(df['qtd'], errors='coerce').fillna(0)
    
    # Converte Código com segurança
    df['codigo'] = pd.to_numeric(df['codigo'], errors='coerce').fillna(0).astype(int)
    
    return df

def preprocess_mix_data(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """Pré-processa o DataFrame do Mix."""
    df = df.copy()
    df.columns = df.columns.str.strip()
    
    # Mapa flexível de colunas
    rename_map = {}
    for col in df.columns:
        if col.lower() == 'codigoint': rename_map[col] = 'codigo'
        if col.lower() == 'embseparacao': rename_map[col] = 'embalagem'
    df.rename(columns=rename_map, inplace=True)
    
    if 'codigo' not in df.columns or 'embalagem' not in df.columns:
        return pd.DataFrame(columns=['codigo', 'embalagem'])
        
    df['codigo'] = pd.to_numeric(df['codigo'], errors='coerce').fillna(0).astype(int)
    
    # Tratamento da embalagem
    if df['embalagem'].dtype == 'object':
        df['embalagem'] = df['embalagem'].astype(str).str.replace(',', '.', regex=False)
        
    df['embalagem'] = pd.to_numeric(df['embalagem'], errors='coerce').fillna(1).astype(int)
    df.loc[df['embalagem'] <= 0, 'embalagem'] = 1
    
    return df.drop_duplicates(subset=['codigo'])

# --- Função Principal de Exibição ---

def show_consulta_page(engine, base_data_path):
    st.title("Consulta de Itens por Descrição/Código")

    # 1. Carregar WMS
    wms_base_path = os.path.join(base_data_path, "WMS")
    df_wms_raw = load_data(wms_base_path)
    
    if df_wms_raw is None:
        st.warning("Arquivo 'WMS' não encontrado.")
        return

    df_wms = preprocess_wms_data(df_wms_raw)
    if df_wms is None or df_wms.empty:
        st.error("O arquivo WMS foi lido mas não contém dados válidos após o processamento.")
        return

    # Debug discreto (pode remover depois)
    # st.caption(f"Total de registros carregados no sistema: {len(df_wms)}")

    # 2. Carregar Mix
    mix_base_path = os.path.join(base_data_path, "__MixAtivoSistema")
    df_mix_raw = load_data(mix_base_path)
    
    if df_mix_raw is not None:
        df_mix = preprocess_mix_data(df_mix_raw)
    else:
        df_mix = pd.DataFrame(columns=['codigo', 'embalagem'])

    # 3. Filtragem de Data Inteligente
    hoje = get_today() 
    datas_disponiveis = sorted(df_wms['datasalva_formatada'].unique(), reverse=True)
    
    if not datas_disponiveis:
        st.error("Não foi possível identificar nenhuma data válida no arquivo.")
        return

    # Se a data de hoje não existe, sugere a mais recente
    data_padrao = hoje if hoje in datas_disponiveis else datas_disponiveis[0]
    
    # Seletor de data melhorado
    col_data, col_info = st.columns([1, 2])
    with col_data:
        data_pesquisa = st.selectbox(
            "Data do Estoque:", 
            options=datas_disponiveis,
            index=datas_disponiveis.index(data_padrao)
        )
    
    df_filtrado = df_wms[df_wms['datasalva_formatada'] == data_pesquisa]
    
    # --- CRUZAMENTO COM MIX ---
    if not df_mix.empty:
        df_filtrado = pd.merge(df_filtrado, df_mix, on='codigo', how='left')
        df_filtrado['embalagem'] = df_filtrado['embalagem'].fillna(1).astype(int)
    else:
        df_filtrado['embalagem'] = 1

    st.divider()

    # --- CAMPOS DE BUSCA ---
    st.subheader("Buscar Produto")
    
    col_busca_desc, col_busca_cod = st.columns(2)
    with col_busca_desc:
        termo_busca = st.text_input("Descrição (Nome):")
    with col_busca_cod:
        codigo_direto = st.text_input("Código (Numérico):")

    item_selecionado_code = None
    
    # Identifica coluna de descrição
    col_desc_real = None
    possiveis_nomes = ['produto', 'descricao', 'descrição', 'nome']
    for c in df_filtrado.columns:
        if any(x in c for x in possiveis_nomes):
            col_desc_real = c
            break
    
    if codigo_direto and codigo_direto.isdigit():
        item_selecionado_code = int(codigo_direto)
        termo_busca = None 
        
    elif termo_busca and col_desc_real:
        df_filtrado['Descrição_Lower'] = df_filtrado[col_desc_real].astype(str).str.lower()
        termo_lower = termo_busca.lower()
        
        mask = df_filtrado['Descrição_Lower'].str.contains(termo_lower, na=False)
        resultados_parciais = df_filtrado[mask].sort_values(by=col_desc_real)

        opcoes_unicas = resultados_parciais.drop_duplicates(subset=['codigo'])
        
        lista_opcoes = opcoes_unicas.apply(
            lambda row: f"{row[col_desc_real]} (Cód: {row['codigo']})", axis=1
        ).tolist()
        
        if lista_opcoes:
            escolha = st.selectbox("Selecione:", options=[''] + lista_opcoes)
            if escolha:
                try:
                    item_selecionado_code = int(escolha.split('(Cód: ')[1].strip(')'))
                except: pass
        else:
            st.warning("Nenhum produto encontrado.")

    # --- EXIBIÇÃO ---
    if item_selecionado_code:
        res = df_filtrado[df_filtrado['codigo'] == item_selecionado_code].copy()
        if not res.empty:
            desc = res[col_desc_real].iloc[0] if col_desc_real else "Produto"
            emb = int(res['embalagem'].iloc[0])
            
            st.success(f"📦 **{desc}**")
            
            total_un = res['qtd'].sum()
            total_cx = total_un / emb
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Unidades", f"{total_un:,.0f}")
            m2.metric("Total Caixas", f"{total_cx:,.1f}")
            m3.metric("Embalagem", f"{emb}")
            
            res['Qtd (Caixas)'] = (res['qtd'] / emb).round(1)
            res.rename(columns={'qtd': 'Qtd'}, inplace=True)
            
            cols_view = [c for c in res.columns if c not in ['datasalva', 'datasalva_formatada', 'Descrição_Lower', 'embalagem']]
            st.dataframe(res[cols_view], hide_index=True, use_container_width=True)
        else:
            st.warning("Código não encontrado nesta data.")
            
    elif not termo_busca and not codigo_direto:
        st.caption(f"Exibindo primeiros 50 itens de {len(df_filtrado)} registros desta data.")
        df_prev = df_filtrado.head(50).copy()
        if 'qtd' in df_prev.columns:
            df_prev['Qtd (Caixas)'] = (df_prev['qtd'] / df_prev['embalagem']).round(1)
            df_prev.rename(columns={'qtd': 'Qtd'}, inplace=True)
            
        cols_view = [c for c in df_prev.columns if c not in ['datasalva', 'datasalva_formatada', 'Descrição_Lower', 'embalagem']]
        st.dataframe(df_prev[cols_view], hide_index=True)
