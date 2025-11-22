import streamlit as st
import pandas as pd
from sqlalchemy import text
import numpy as np

# ================================================
# 🔧 LEITURA SEGURA DE EXCEL
# ================================================
def safe_read_excel(uploaded_file):
    """Lê Excel ou CSV e retorna DataFrame padronizado."""
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file, engine="openpyxl")
        
        # Normaliza colunas para minúsculas para evitar erros de SQL
        df.columns = [str(c).strip().lower() for c in df.columns]
        return df
    except Exception as e:
        st.error(f"Erro ao ler arquivo: {e}")
        return None

# ================================================
# 💾 SALVAR DIRETO NO BANCO (POSTGRES)
# ================================================
def save_to_database(engine, df, table_name):
    """Escreve o DataFrame direto no PostgreSQL, substituindo a tabela antiga."""
    if df is None or df.empty:
        return False
    
    try:
        # Mapeamento de colunas para garantir compatibilidade
        # Ajuste conforme as colunas reais dos seus Excels
        rename_map = {}
        
        # Regras para MIX
        if table_name == "mix":
            for c in df.columns:
                if "codigo" in c: rename_map[c] = "codigoint"
                if "descri" in c or "produto" in c: rename_map[c] = "descricao"
                if "emb" in c: rename_map[c] = "embseparacao"
                if "loja" in c: rename_map[c] = "loja"
        
        # Regras para WMS
        elif table_name == "wms":
            for c in df.columns:
                if "codigo" in c: rename_map[c] = "codigo"
                if "qtd" in c: rename_map[c] = "qtd"
                if "data" in c: rename_map[c] = "datasalva"
                if "ender" in c: rename_map[c] = "endereco"

        # Aplica renomeação
        if rename_map:
            df = df.rename(columns=rename_map)

        # Salva no banco (Chunksize ajuda a não estourar a memória)
        with engine.begin() as conn:
            # Limpa dados antigos (Opcional: depende se você quer acumular ou substituir)
            # Aqui estamos substituindo (REPLACE logic via Pandas to_sql não deleta a tabela, 
            # mas o if_exists='replace' recria a tabela)
            df.to_sql(
                table_name, 
                engine, 
                if_exists='replace', 
                index=False, 
                chunksize=1000, # Salva de 1000 em 1000 linhas para economizar memória
                method='multi'
            )
            
        return True
    except Exception as e:
        st.error(f"Erro ao salvar no banco de dados: {e}")
        return False

# ================================================
# 🔧 FUNÇÃO PRINCIPAL DA PÁGINA
# ================================================
def show_admin_tools(engine=None, base_data_path=None):
    st.title("🔧 Ferramentas de Admin — Atualizar Banco de Dados")
    st.info("Os arquivos enviados atualizarão diretamente o Banco de Dados (PostgreSQL).")

    if engine is None:
        st.error("Sem conexão com o banco de dados.")
        return

    # -------------------------------
    # 1. WMS
    # -------------------------------
    st.subheader("1. Atualizar WMS (Estoque CD)")
    uploaded_wms = st.file_uploader("Selecione o WMS (.xlsx)", type=["xlsx", "csv"], key="wms")
    
    if uploaded_wms:
        if st.button("Processar WMS", type="primary"):
            with st.spinner("Lendo arquivo e salvando no banco..."):
                df = safe_read_excel(uploaded_wms)
                if save_to_database(engine, df, "wms"):
                    st.success("✅ Tabela WMS atualizada no Banco de Dados!")
                    st.cache_data.clear() # Limpa o cache do Streamlit para ver dados novos

    st.markdown("---")

    # -------------------------------
    # 2. Histórico
    # -------------------------------
    st.subheader("2. Atualizar Histórico")
    uploaded_hist = st.file_uploader("Selecione o Histórico (.xlsx)", type=["xlsx", "csv"], key="hist")
    
    if uploaded_hist:
        if st.button("Processar Histórico", type="primary"):
            with st.spinner("Atualizando Histórico..."):
                df = safe_read_excel(uploaded_hist)
                if save_to_database(engine, df, "historico"):
                    st.success("✅ Tabela Historico atualizada no Banco de Dados!")
                    st.cache_data.clear()

    st.markdown("---")

    # -------------------------------
    # 3. Mix
    # -------------------------------
    st.subheader("3. Atualizar Mix")
    uploaded_mix = st.file_uploader("Selecione o Mix (.xlsx)", type=["xlsx", "csv"], key="mix")
    
    if uploaded_mix:
        if st.button("Processar Mix", type="primary"):
            with st.spinner("Atualizando Mix..."):
                df = safe_read_excel(uploaded_mix)
                if save_to_database(engine, df, "mix"):
                    st.success("✅ Tabela Mix atualizada no Banco de Dados!")
                    st.cache_data.clear()
