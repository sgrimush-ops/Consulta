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
    1. Salva o CSV original no disco.
    2. Lê esse CSV e converte para PARQUET (para o sistema ler rápido).
    """
    # Caminhos completos
    path_csv = os.path.join(target_path_base, filename_csv)
    path_parquet = os.path.join(target_path_base, f"{os.path.splitext(filename_csv)[0]}.parquet")
    
    try:
        # 1. Salvar o arquivo CSV original
        uploaded_file.seek(0)
        with open(path_csv, "wb") as f:
            f.write(uploaded_file.getbuffer())
            
        # 2. Converter para Parquet (Vital para o funcionamento do Pedidos.py)
        # Tenta ler o CSV detectando automaticamente o separador (; ou ,)
        # dtype=str garante que códigos como '00123' não virem '123'
        uploaded_file.seek(0) # Volta para o início do arquivo na memória
        df = pd.read_csv(uploaded_file, sep=None, engine='python', dtype=str)
        
        # Limpeza básica de espaços nos nomes das colunas
        df.columns = df.columns.str.strip()
        
        # Salva a versão otimizada
        df.to_parquet(path_parquet, index=False)
        
        return True, f"Sucesso! CSV salvo e base de dados otimizada atualizada."
        
    except Exception as e:
        return False, f"Erro ao processar o arquivo: {e}"

# =========================================================
# PÁGINA PRINCIPAL
# =========================================================

def show_admin_tools(engine, base_data_path):
    st.title("🔧 Ferramentas de Admin: Upload de Arquivos (CSV)")
    st.info(f"Os arquivos são salvos e convertidos automaticamente em: {base_data_path}")

    # Garante que a pasta existe
    os.makedirs(base_data_path, exist_ok=True)

    # --- 1. Upload do WMS ---
    st.markdown("---")
    st.subheader("1. Upload do WMS (Estoque CD)")
    
    # Mostra data da última atualização
    path_wms_parquet = os.path.join(base_data_path, "WMS.parquet")
    if os.path.exists(path_wms_parquet):
        st.caption(f"📅 Última atualização do sistema: **{get_file_info(path_wms_parquet)}**")
    
    uploaded_wms = st.file_uploader("Selecione o WMS (.csv)", type=["csv"], key="wms_uploader")
    
    if uploaded_wms:
        if st.button("Processar WMS", type="primary"):
            with st.spinner("Salvando e convertendo..."):
                # Usamos apenas a pasta base para o join interno da função
                success, msg = process_and_save_csv(uploaded_wms, base_data_path, "WMS.csv")
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

    # --- 2. Upload do Histórico ---
    st.markdown("---")
    st.subheader("2. Upload do Histórico de Solicitações")
    
    path_hist_parquet = os.path.join(base_data_path, "historico_solic.parquet")
    if os.path.exists(path_hist_parquet):
        st.caption(f"📅 Última atualização do sistema: **{get_file_info(path_hist_parquet)}**")

    uploaded_hist = st.file_uploader("Selecione o Histórico (.csv)", type=["csv"], key="hist_uploader")
    
    if uploaded_hist:
        if st.button("Processar Histórico", type="primary"):
            with st.spinner("Salvando e convertendo..."):
                success, msg = process_and_save_csv(uploaded_hist, base_data_path, "historico_solic.csv")
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

    # --- 3. Upload do Mix ---
    st.markdown("---")
    st.subheader("3. Upload do Mix Ativo")
    
    path_mix_parquet = os.path.join(base_data_path, "__MixAtivoSistema.parquet")
    if os.path.exists(path_mix_parquet):
        st.caption(f"📅 Última atualização do sistema: **{get_file_info(path_mix_parquet)}**")

    uploaded_mix = st.file_uploader("Selecione o Mix (.csv)", type=["csv"], key="mix_uploader")
    
    if uploaded_mix:
        if st.button("Processar Mix", type="primary"):
            with st.spinner("Salvando e convertendo..."):
                success, msg = process_and_save_csv(uploaded_mix, base_data_path, "__MixAtivoSistema.csv")
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
