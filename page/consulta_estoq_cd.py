import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Tuple
import os
import unicodedata

# --- Funções de Cache e Helpers ---

@st.cache_resource(ttl=timedelta(minutes=5))
def get_today():
    return datetime.now().date()

def load_data_optimized(parquet_path):
    if os.path.exists(parquet_path):
        return pd.read_parquet(parquet_path)
    return None

@st.cache_data(ttl=60)
def load_data(base_path_no_ext: str) -> Optional[pd.DataFrame]:
    parquet_path = f"{base_path_no_ext}.parquet"
    try:
        return load_data_optimized(parquet_path)
    except Exception as e:
        # st.error(f"Erro ao carregar arquivo: {e}") 
        return None

def normalize_col(col):
    # Normalização para garantir match (remove acentos, espaços, minúsculo)
    n = unicodedata.normalize('NFKD', str(col)).encode('ASCII', 'ignore').decode('utf-8')
    return ''.join(e for e in n if e.isalnum()).lower()

def preprocess_wms_data(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    df = df.copy()
    # Normaliza nomes das colunas do DataFrame
    df.columns = [normalize_col(c) for c in df.columns]
    
    # Mapeamento Inteligente (Busca substrings para encontrar as colunas)
    col_map = {}
    for col in df.columns:
        if 'datasalva' in col: col_map[col] = 'datasalva'
        elif 'cod' in col and 'int' not in col: col_map[col] = 'codigo'
        elif 'qtd' in col or 'quant' in col or 'saldo' in col: col_map[col] = 'qtd'
        elif 'prod' in col or 'desc' in col: col_map[col] = 'produto'
        elif 'ender' in col: col_map[col] = 'endereco'
        elif 'lote' in col and 'entr' not in col: col_map[col] = 'lote'
        elif 'valid' in col: col_map[col] = 'validade'

    df.rename(columns=col_map, inplace=True)

    # Verifica se as colunas essenciais foram encontradas
    missing = [c for c in ['datasalva', 'codigo', 'qtd'] if c not in df.columns]
    if missing:
        st.error(f"Colunas não identificadas no WMS: {missing}. Colunas disponíveis: {list(df.columns)}")
        return None
        
    # Limpeza de Dados
    if df['datasalva'].dtype == 'object':
        df['datasalva'] = df['datasalva'].astype(str).str.strip()
    
    # Tenta converter data com dayfirst=True (Brasil)
    df['datasalva'] = pd.to_datetime(df['datasalva'], dayfirst=True, errors='coerce')
    df.dropna(subset=['datasalva'], inplace=True)
    df['datasalva_formatada'] = df['datasalva'].dt.date
    
    if df['qtd'].dtype == 'object':
        df['qtd'] = df['qtd'].astype(str).str.replace(',', '.', regex=False)
    df['qtd'] = pd.to_numeric(df['qtd'], errors='coerce').fillna(0)
    
    # Garante código como int
    df['codigo'] = pd.to_numeric(df['codigo'], errors='coerce').fillna(0).astype(int)
    
    return df

def preprocess_mix_data(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    df = df.copy()
    df.columns = [normalize_col(c) for c in df.columns]
    
    rename_map = {}
    for col in df.columns:
        if 'codigoint' in col: rename_map[col] = 'codigo'
        if 'embseparacao' in col or 'emb' in col: rename_map[col] = 'embalagem'
    df.rename(columns=rename_map, inplace=True)
    
    if 'codigo' not in df.columns:
        return pd.DataFrame()
        
    df['codigo'] = pd.to_numeric(df['codigo'], errors='coerce').fillna(0).astype(int)
    
    if 'embalagem' in df.columns:
        if df['embalagem'].dtype == 'object':
            df['embalagem'] = df['embalagem'].astype(str).str.replace(',', '.', regex=False)
        df['embalagem'] = pd.to_numeric(df['embalagem'], errors='coerce').fillna(1)
        df.loc[df['embalagem'] <= 0, 'embalagem'] = 1
    else:
        df['embalagem'] = 1
        
    return df.drop_duplicates(subset=['codigo'])

def show_consulta_page(engine, base_data_path):
    st.title("🔎 Consulta de Estoque CD")

    wms_path = os.path.join(base_data_path, "WMS")
    df_wms_raw = load_data(wms_path)
    
    if df_wms_raw is None:
        st.warning("Arquivo WMS não encontrado. Faça o upload no Admin.")
        return

    df_wms = preprocess_wms_data(df_wms_raw)
    if df_wms is None or df_wms.empty:
        st.error("Arquivo WMS vazio ou com colunas incorretas.")
        return

    mix_path = os.path.join(base_data_path, "__MixAtivoSistema")
    df_mix_raw = load_data(mix_path)
    df_mix = preprocess_mix_data(df_mix_raw) if df_mix_raw is not None else pd.DataFrame()

    hoje = get_today()
    datas = sorted(df_wms['datasalva_formatada'].unique(), reverse=True)
    
    if not datas:
        st.error("Nenhuma data válida encontrada.")
        return
        
    data_padrao = hoje if hoje in datas else datas[0]
    
    col_d, _ = st.columns([1, 2])
    with col_d:
        data_sel = st.selectbox("Data do Estoque:", options=datas, index=datas.index(data_padrao))
        
    df_filt = df_wms[df_wms['datasalva_formatada'] == data_sel].copy()
    
    if not df_mix.empty:
        df_filt = pd.merge(df_filt, df_mix[['codigo', 'embalagem']], on='codigo', how='left')
        df_filt['embalagem'] = df_filt['embalagem'].fillna(1).astype(int)
    else:
        df_filt['embalagem'] = 1

    st.divider()
    
    # Busca
    c1, c2 = st.columns(2)
    cod = c1.text_input("Código (Numérico):")
    termo = c2.text_input("Descrição (Nome):")
    
    sel_code = None
    col_desc = next((c for c in df_filt.columns if c == 'produto'), None)
    
    if cod and cod.isdigit():
        sel_code = int(cod)
    elif termo and col_desc:
        mask = df_filt[col_desc].astype(str).str.lower().str.contains(termo.lower(), na=False)
        res = df_filt[mask].sort_values(by=col_desc)
        
        opcoes = res.drop_duplicates(subset=['codigo'])
        lista = opcoes.apply(lambda x: f"{x[col_desc]} (Cód: {x['codigo']})", axis=1).tolist()
        
        if lista:
            escolha = st.selectbox("Selecione:", [""] + lista)
            if escolha:
                try: sel_code = int(escolha.split('(Cód: ')[1].strip(')'))
                except: pass
        elif termo:
            st.warning("Nenhum item encontrado.")
    
    if sel_code:
        final = df_filt[df_filt['codigo'] == sel_code].copy()
        if not final.empty:
            nome = final[col_desc].iloc[0] if col_desc else "Produto"
            emb = int(final['embalagem'].iloc[0])
            
            st.success(f"📦 **{nome}**")
            
            tot_un = final['qtd'].sum()
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Un", f"{tot_un:,.0f}")
            m2.metric("Total Cx", f"{tot_un/emb:,.1f}")
            m3.metric("Emb", emb)
            
            final['Qtd (Cx)'] = (final['qtd']/emb).round(1)
            
            rename = {'qtd': 'Qtd (Un)', 'codigo': 'Código', 'produto': 'Produto', 'endereco': 'Endereço', 'lote': 'Lote', 'validade': 'Validade'}
            final.rename(columns=rename, inplace=True)
            
            ignorar = ['datasalva', 'datasalva_formatada', 'embalagem']
            cols = [c for c in final.columns if c not in ignorar]
            st.dataframe(final[cols], hide_index=True, use_container_width=True)
        else:
            st.warning("Não encontrado nesta data.")
