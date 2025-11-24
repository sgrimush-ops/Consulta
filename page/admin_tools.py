import streamlit as st
import os
import pandas as pd
from datetime import datetime
import unicodedata

# =========================================================
# FUNÇÕES AUXILIARES
# =========================================================

def normalize_column_name(col_name):
    """Remove acentos, espaços e coloca em minúsculo."""
    if not isinstance(col_name, str): return str(col_name)
    n = unicodedata.normalize('NFKD', col_name)
    only_ascii = n.encode('ASCII', 'ignore').decode('utf-8')
    return ''.join(e for e in only_ascii if e.isalnum()).lower()

def get_file_info(file_path):
    if os.path.exists(file_path):
        mod_time = os.path.getmtime(file_path)
        return datetime.fromtimestamp(mod_time).strftime('%d/%m/%Y às %H:%M:%S')
    return "Ainda não enviado"

def process_and_save_csv(uploaded_file, target_path_base, filename_csv):
    path_csv = os.path.join(target_path_base, filename_csv)
    path_parquet = os.path.join(target_path_base, f"{os.path.splitext(filename_csv)[0]}.parquet")
    
    try:
        # 1. Salva original
        uploaded_file.seek(0)
        with open(path_csv, "wb") as f:
            f.write(uploaded_file.getbuffer())
            
        # 2. Lê CSV (detecta separador)
        uploaded_file.seek(0)
        try:
            df = pd.read_csv(uploaded_file, sep=';', dtype=str, encoding='utf-8')
        except UnicodeDecodeError:
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, sep=';', dtype=str, encoding='latin1')
        except:
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, sep=None, engine='python', dtype=str, encoding='latin1')
        
        # 3. Normaliza Colunas
        df.columns = [normalize_column_name(c) for c in df.columns]
        df = df.loc[:, ~df.columns.str.contains('^unnamed')]

        # 4. LIMPEZA DE DADOS (CRUCIAL)
        
        # Embalagem (Mix)
        if 'embseparacao' in df.columns:
            df['embseparacao'] = df['embseparacao'].str.replace(',', '.', regex=False)
            df['embseparacao'] = pd.to_numeric(df['embseparacao'], errors='coerce')

        # Colunas Numéricas Genéricas
        for col in ['codigo', 'codigoint', 'qtd', 'quantidade', 'total_cx']:
            if col in df.columns:
                # Remove pontos de milhar se houver e troca vírgula decimal
                 df[col] = df[col].str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
                 df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)

        # 5. Salva Parquet Limpo
        df.to_parquet(path_parquet, index=False)
        
        return True, df.head()
        
    except Exception as e:
        return False, f"Erro: {e}"

# =========================================================
# PÁGINA PRINCIPAL
# =========================================================

def show_admin_tools(engine, base_data_path):
    st.title("🔧 Upload de Arquivos (CSV)")
    st.info("O sistema normaliza colunas e corrige números automaticamente.")

    os.makedirs(base_data_path, exist_ok=True)

    # WMS
    st.markdown("---")
    st.subheader("1. Estoque CD (WMS)")
    path_wms = os.path.join(base_data_path, "WMS.parquet")
    if os.path.exists(path_wms): st.caption(f"📅 Atualizado: **{get_file_info(path_wms)}**")
    
    up_wms = st.file_uploader("WMS.csv", type=["csv"], key="wms")
    if up_wms and st.button("Processar WMS", type="primary"):
        with st.spinner("Processando..."):
            ok, res = process_and_save_csv(up_wms, base_data_path, "WMS.csv")
            if ok: 
                st.success("Sucesso! Preview:")
                st.dataframe(res)
                st.cache_data.clear()
            else: st.error(res)

    # Histórico
    st.markdown("---")
    st.subheader("2. Histórico")
    path_hist = os.path.join(base_data_path, "historico_solic.parquet")
    if os.path.exists(path_hist): st.caption(f"📅 Atualizado: **{get_file_info(path_hist)}**")

    up_hist = st.file_uploader("Histórico.csv", type=["csv"], key="hist")
    if up_hist and st.button("Processar Histórico", type="primary"):
        with st.spinner("Processando..."):
            ok, res = process_and_save_csv(up_hist, base_data_path, "historico_solic.csv")
            if ok: 
                st.success("Sucesso! Preview:")
                st.dataframe(res)
                st.cache_data.clear()
            else: st.error(res)

    # Mix
    st.markdown("---")
    st.subheader("3. Mix Ativo")
    path_mix = os.path.join(base_data_path, "__MixAtivoSistema.parquet")
    if os.path.exists(path_mix): st.caption(f"📅 Atualizado: **{get_file_info(path_mix)}**")

    up_mix = st.file_uploader("Mix.csv", type=["csv"], key="mix")
    if up_mix and st.button("Processar Mix", type="primary"):
        with st.spinner("Processando..."):
            ok, res = process_and_save_csv(up_mix, base_data_path, "__MixAtivoSistema.csv")
            if ok: 
                st.success("Sucesso! Preview (Verifique a coluna 'embseparacao'):")
                st.dataframe(res)
                st.cache_data.clear()
            else: st.error(res)
