import streamlit as st
import os
import pandas as pd
from datetime import datetime

# =========================================================
# FUNÇÕES AUXILIARES
# =========================================================

def get_file_info(file_path):
    """Retorna a data de modificação do arquivo formatada."""
    if os.path.exists(file_path):
        mod_time = os.path.getmtime(file_path)
        return datetime.fromtimestamp(mod_time).strftime('%d/%m/%Y às %H:%M:%S')
    return "Ainda não enviado"

def process_and_save_csv(uploaded_file, target_path_base, filename_csv):
    """
    Salva o CSV e converte para Parquet, tratando separador ';' e colunas.
    """
    path_csv = os.path.join(target_path_base, filename_csv)
    path_parquet = os.path.join(target_path_base, f"{os.path.splitext(filename_csv)[0]}.parquet")
    
    try:
        # 1. Salva o arquivo original
        uploaded_file.seek(0)
        with open(path_csv, "wb") as f:
            f.write(uploaded_file.getbuffer())
            
        # 2. Tenta ler o CSV (Forçando separador ';' para seus arquivos)
        uploaded_file.seek(0)
        try:
            # Tenta UTF-8 com ponto e vírgula
            df = pd.read_csv(uploaded_file, sep=';', dtype=str, encoding='utf-8')
        except UnicodeDecodeError:
            uploaded_file.seek(0)
            # Tenta Latin-1 (Excel padrão) com ponto e vírgula
            df = pd.read_csv(uploaded_file, sep=';', dtype=str, encoding='latin1')
        
        # 3. Padroniza nomes das colunas (tudo minúsculo e sem espaços)
        df.columns = df.columns.str.strip().str.lower()
        
        # Remove colunas estranhas/vazias
        df = df.loc[:, ~df.columns.str.contains('^unnamed')]

        # 4. Salva a versão otimizada (.parquet)
        df.to_parquet(path_parquet, index=False)
        
        return True, df.head()
        
    except Exception as e:
        return False, f"Erro: {e}"

# =========================================================
# PÁGINA PRINCIPAL (A função que estava faltando)
# =========================================================

def show_admin_tools(engine, base_data_path):
    st.title("🔧 Upload de Arquivos (CSV)")
    st.info("O sistema foi ajustado para ler seus arquivos CSV com separador ';'.")

    os.makedirs(base_data_path, exist_ok=True)

    # --- 1. Upload do WMS ---
    st.markdown("---")
    st.subheader("1. Estoque CD (WMS)")
    
    path_wms_parquet = os.path.join(base_data_path, "WMS.parquet")
    if os.path.exists(path_wms_parquet):
        st.caption(f"📅 Atualizado em: **{get_file_info(path_wms_parquet)}**")
    
    uploaded_wms = st.file_uploader("Selecione WMS.csv", type=["csv"], key="wms_uploader")
    
    if uploaded_wms:
        if st.button("Processar WMS", type="primary"):
            with st.spinner("Processando WMS..."):
                success, result = process_and_save_csv(uploaded_wms, base_data_path, "WMS.csv")
                if success:
                    st.success("WMS Atualizado! Confira as colunas abaixo:")
                    st.dataframe(result)
                    st.cache_data.clear() # Limpa cache para a consulta ver os dados novos
                else:
                    st.error(f"Erro: {result}")

    # --- 2. Upload do Histórico ---
    st.markdown("---")
    st.subheader("2. Histórico de Solicitações")
    
    path_hist_parquet = os.path.join(base_data_path, "historico_solic.parquet")
    if os.path.exists(path_hist_parquet):
        st.caption(f"📅 Atualizado em: **{get_file_info(path_hist_parquet)}**")

    uploaded_hist = st.file_uploader("Selecione Histórico.csv", type=["csv"], key="hist_uploader")
    
    if uploaded_hist:
        if st.button("Processar Histórico", type="primary"):
            with st.spinner("Processando Histórico..."):
                success, result = process_and_save_csv(uploaded_hist, base_data_path, "historico_solic.csv")
                if success:
                    st.success("Histórico Atualizado! Preview:")
                    st.dataframe(result)
                    st.cache_data.clear()
                else:
                    st.error(f"Erro: {result}")

    # --- 3. Upload do Mix ---
    st.markdown("---")
    st.subheader("3. Mix Ativo")
    
    path_mix_parquet = os.path.join(base_data_path, "__MixAtivoSistema.parquet")
    if os.path.exists(path_mix_parquet):
        st.caption(f"📅 Atualizado em: **{get_file_info(path_mix_parquet)}**")

    uploaded_mix = st.file_uploader("Selecione Mix.csv", type=["csv"], key="mix_uploader")
    
    if uploaded_mix:
        if st.button("Processar Mix", type="primary"):
            with st.spinner("Processando Mix..."):
                success, result = process_and_save_csv(uploaded_mix, base_data_path, "__MixAtivoSistema.csv")
                if success:
                    st.success("Mix Atualizado! Preview:")
                    st.dataframe(result)
                    st.cache_data.clear()
                else:
                    st.error(f"Erro: {result}")
