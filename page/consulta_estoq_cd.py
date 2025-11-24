import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
import os

# --- Funções de Cache e Helpers ---

@st.cache_resource(ttl=timedelta(minutes=5))
def get_today():
    return datetime.now().date()

def load_data_optimized(parquet_path, excel_path):
    if os.path.exists(parquet_path):
        return pd.read_parquet(parquet_path)
    else:
        if 'Mix' in excel_path:
            return pd.read_excel(excel_path, dtype=str)
        return pd.read_excel(excel_path, sheet_name='WMS')

@st.cache_data(ttl=60)
def load_data(base_path_no_ext: str) -> Optional[pd.DataFrame]:
    parquet_path = f"{base_path_no_ext}.parquet"
    excel_path = f"{base_path_no_ext}.xlsm" 
    if 'Mix' in base_path_no_ext:
        excel_path = f"{base_path_no_ext}.xlsx"

    try:
        return load_data_optimized(parquet_path, excel_path)
    except Exception as e:
        st.error(f"Erro ao carregar arquivo: {e}")
        return None

def preprocess_wms_data(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    df = df.copy()
    # Padroniza colunas para minúsculo
    df.columns = df.columns.str.strip().str.lower()
    
    # Verifica colunas essenciais (agora minúsculas)
    if 'datasalva' not in df.columns or 'codigo' not in df.columns:
        st.error(f"Colunas 'datasalva' ou 'codigo' não encontradas. Colunas: {list(df.columns)}")
        return None
        
    # Compatibilidade Qtd vs qtd
    col_qtd = 'qtd' if 'qtd' in df.columns else 'Qtd'
    if col_qtd != 'qtd' and col_qtd in df.columns:
        df.rename(columns={col_qtd: 'qtd'}, inplace=True)
        
    # Limpeza de Data (Vital para CSV)
    if df['datasalva'].dtype == 'object':
        df['datasalva'] = df['datasalva'].astype(str).str.strip()
    
    # Converte data (dayfirst=True é essencial para 24/11)
    df['datasalva'] = pd.to_datetime(df['datasalva'], dayfirst=True, errors='coerce')
    df.dropna(subset=['datasalva'], inplace=True)
    df['datasalva_formatada'] = df['datasalva'].dt.date
    
    # Limpeza de números (vírgula para ponto)
    for col in ['qtd', 'codigo']:
        if col in df.columns and df[col].dtype == 'object':
            df[col] = df[col].str.replace(',', '.', regex=False)
            
    df['qtd'] = pd.to_numeric(df['qtd'], errors='coerce').fillna(0)
    df['codigo'] = pd.to_numeric(df['codigo'], errors='coerce').fillna(0).astype(int)
    
    return df

def preprocess_mix_data(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    df = df.copy()
    df.columns = df.columns.str.strip().str.lower()
    
    # Mapeamento flexível
    rename_map = {}
    if 'codigoint' in df.columns: rename_map['codigoint'] = 'codigo'
    if 'embseparacao' in df.columns: rename_map['embseparacao'] = 'embalagem'
    df.rename(columns=rename_map, inplace=True)
    
    if 'codigo' not in df.columns:
        return pd.DataFrame()
        
    df['codigo'] = pd.to_numeric(df['codigo'], errors='coerce').fillna(0).astype(int)
    
    if 'embalagem' in df.columns:
        if df['embalagem'].dtype == 'object':
            df['embalagem'] = df['embalagem'].astype(str).str.replace(',', '.', regex=False)
        df['embalagem'] = pd.to_numeric(df['embalagem'], errors='coerce').fillna(1).astype(int)
        df.loc[df['embalagem'] <= 0, 'embalagem'] = 1
    else:
        df['embalagem'] = 1
        
    return df.drop_duplicates(subset=['codigo'])

def show_consulta_page(engine, base_data_path):
    st.title("Consulta de Itens por Descrição/Código")

    wms_path = os.path.join(base_data_path, "WMS")
    df_wms_raw = load_data(wms_path)
    
    if df_wms_raw is None:
        st.warning("Arquivo WMS não encontrado.")
        return

    df_wms = preprocess_wms_data(df_wms_raw)
    if df_wms is None or df_wms.empty:
        st.warning("Arquivo WMS vazio ou com dados inválidos.")
        return

    mix_path = os.path.join(base_data_path, "__MixAtivoSistema")
    df_mix_raw = load_data(mix_path)
    df_mix = preprocess_mix_data(df_mix_raw) if df_mix_raw is not None else pd.DataFrame()

    # Filtro de Data
    hoje = get_today()
    datas = sorted(df_wms['datasalva_formatada'].unique(), reverse=True)
    
    if not datas:
        st.error("Nenhuma data válida encontrada no arquivo WMS.")
        return
        
    data_padrao = hoje if hoje in datas else datas[0]
    
    col_d, _ = st.columns([1, 2])
    with col_d:
        data_sel = st.selectbox("Data:", options=datas, index=datas.index(data_padrao))
        
    df_filt = df_wms[df_wms['datasalva_formatada'] == data_sel]
    
    if not df_mix.empty:
        df_filt = pd.merge(df_filt, df_mix[['codigo', 'embalagem']], on='codigo', how='left')
        df_filt['embalagem'] = df_filt['embalagem'].fillna(1).astype(int)
    else:
        df_filt['embalagem'] = 1

    st.divider()
    
    # Busca
    c1, c2 = st.columns(2)
    termo = c1.text_input("Descrição:")
    cod = c2.text_input("Código:")
    
    sel_code = None
    
    # Identifica coluna de descrição (produto/descricao/etc)
    col_desc = next((c for c in df_filt.columns if 'produto' in c or 'desc' in c), None)
    
    if cod and cod.isdigit():
        sel_code = int(cod)
    elif termo and col_desc:
        mask = df_filt[col_desc].astype(str).str.lower().str.contains(termo.lower(), na=False)
        res_parcial = df_filt[mask].head(50) # Limita busca
        opts = res_parcial.apply(lambda x: f"{x[col_desc]} (Cód: {x['codigo']})", axis=1).unique()
        if len(opts) > 0:
            escolha = st.selectbox("Selecione:", [""] + list(opts))
            if escolha:
                try: sel_code = int(escolha.split('(Cód: ')[1].strip(')'))
                except: pass
    
    if sel_code:
        final = df_filt[df_filt['codigo'] == sel_code].copy()
        if not final.empty:
            emb = final['embalagem'].iloc[0]
            st.success(f"📦 {final[col_desc].iloc[0] if col_desc else 'Item'}")
            
            m1, m2, m3 = st.columns(3)
            qtd_un = final['qtd'].sum()
            m1.metric("Total Unidades", f"{qtd_un:,.0f}")
            m2.metric("Total Caixas", f"{qtd_un/emb:,.1f}")
            m3.metric("Embalagem", emb)
            
            final['Qtd (Caixas)'] = (final['qtd']/emb).round(1)
            cols = [c for c in final.columns if c not in ['datasalva', 'datasalva_formatada', 'embalagem']]
            st.dataframe(final[cols], hide_index=True, use_container_width=True)
        else:
            st.warning("Não encontrado.")
    elif not termo and not cod:
        # Preview inicial
        prev = df_filt.head(20).copy()
        prev['Qtd (Caixas)'] = (prev['qtd']/prev['embalagem']).round(1)
        cols = [c for c in prev.columns if c not in ['datasalva', 'datasalva_formatada', 'embalagem']]
        st.dataframe(prev[cols], hide_index=True)
