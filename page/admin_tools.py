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
    1. Salva o CSV original.
    2. Lê o CSV (tentando várias codificações).
    3. Padroniza colunas (minúsculas).
    4. Salva como PARQUET para o sistema ler.
    """
    path_csv = os.path.join(target_path_base, filename_csv)
    path_parquet = os.path.join(target_path_base, f"{os.path.splitext(filename_csv)[0]}.parquet")
    
    try:
        # 1. Salva o arquivo original
        uploaded_file.seek(0)
        with open(path_csv, "wb") as f:
            f.write(uploaded_file.getbuffer())
            
        # 2. Tenta ler o CSV com tratamento de erro de codificação
        # Tenta UTF-8 primeiro (padrão web), depois Latin-1 (padrão Excel Brasil)
        uploaded_file.seek(0)
        try:
            df = pd.read_csv(uploaded_file, sep=None, engine='python', dtype=str, encoding='utf-8')
        except UnicodeDecodeError:
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, sep=None, engine='python', dtype=str, encoding='latin1')
        
        # 3. Limpeza Vital: Padroniza nomes das colunas
        # Remove espaços extras e transforma tudo em minúsculo (ex: "Data Salva " -> "datasalva")
        df.columns = df.columns.str.strip().str.lower()
        
        # Remove colunas vazias se houver
        df = df.loc[:, ~df.columns.str.contains('^unnamed')]

        # 4. Salva a versão otimizada
        df.to_parquet(path_parquet, index=False)
        
        return True, df.head() # Retorna as primeiras linhas para preview
        
    except Exception as e:
        return False, f"Erro: {e}"

# =========================================================
# PÁGINA PRINCIPAL
# =========================================================

def show_admin_tools(engine, base_data_path):
    st.title("🔧 Upload de Arquivos (CSV)")
    st.info("O sistema aceita arquivos .csv (separados por vírgula ou ponto e vírgula).")

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
            with st.spinner("Lendo e padronizando dados..."):
                success, result = process_and_save_csv(uploaded_wms, base_data_path, "WMS.csv")
                if success:
                    st.success("WMS Atualizado! Veja abaixo como o sistema leu os dados:")
                    st.dataframe(result) # Mostra preview
                    st.cache_data.clear() # LIMPA A MEMÓRIA ANTIGA
                else:
                    st.error(f"Erro ao processar: {result}")

    # --- 2. Upload do Histórico ---
    st.markdown("---")
    st.subheader("2. Histórico de Solicitações")
    
    path_hist_parquet = os.path.join(base_data_path, "historico_solic.parquet")
    if os.path.exists(path_hist_parquet):
        st.caption(f"📅 Atualizado em: **{get_file_info(path_hist_parquet)}**")

    uploaded_hist = st.file_uploader("Selecione Histórico.csv", type=["csv"], key="hist_uploader")
    
    if uploaded_hist:
        if st.button("Processar Histórico", type="primary"):
            with st.spinner("Processando..."):
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
            with st.spinner("Processando..."):
                success, result = process_and_save_csv(uploaded_mix, base_data_path, "__MixAtivoSistema.csv")
                if success:
                    st.success("Mix Atualizado! Preview:")
                    st.dataframe(result)
                    st.cache_data.clear()
                else:
                    st.error(f"Erro: {result}")
