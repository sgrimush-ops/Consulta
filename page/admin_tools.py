import streamlit as st
import pandas as pd
import gc  # Garbage Collector (Limpeza de memória)
from sqlalchemy import text

# ================================================
# 🔧 LEITURA OTIMIZADA (MENOS MEMÓRIA)
# ================================================
def safe_read_excel(uploaded_file):
    try:
        filename = uploaded_file.name.lower()
        
        # Ler apenas colunas necessárias e converter tipos para economizar memória
        # Se possível, especifique dtypes (ex: int32 em vez de int64)
        if filename.endswith('.xls'):
            df = pd.read_excel(uploaded_file, engine='xlrd')
        else:
            df = pd.read_excel(uploaded_file, engine='openpyxl')
        
        # Normaliza colunas
        df.columns = [str(c).strip().lower() for c in df.columns]
        
        return df
    except Exception as e:
        st.error(f"Erro de leitura: {e}")
        return None

# ================================================
# 💾 SALVAR COM TRANSAÇÃO SEGURA
# ================================================
def save_to_database(engine, df, table_name):
    if df is None or df.empty:
        return False
    
    try:
        # 1. Mapeamento (Igual ao anterior)
        rename_map = {}
        if table_name == "mix":
            for c in df.columns:
                if "codigo" in c: rename_map[c] = "codigoint"
                elif "descri" in c or "produto" in c: rename_map[c] = "descricao"
                elif "emb" in c: rename_map[c] = "embseparacao"
                elif "loja" in c: rename_map[c] = "loja"
        elif table_name == "wms":
            for c in df.columns:
                if "codigo" in c: rename_map[c] = "codigo"
                elif "qtd" in c: rename_map[c] = "qtd"
                elif "data" in c: rename_map[c] = "datasalva"
                elif "ender" in c: rename_map[c] = "endereco"
        elif table_name == "historico":
            for c in df.columns:
                if "codigo" in c: rename_map[c] = "codigoint"
                elif "loja" in c: rename_map[c] = "loja"
                elif "data" in c or "solic" in c: rename_map[c] = "dtsolicitacao"
                elif "estcx" in c: rename_map[c] = "EstCX"
                elif "pedcx" in c: rename_map[c] = "PedCX"

        if rename_map:
            df = df.rename(columns=rename_map)

        # 2. Remove duplicatas de colunas
        df = df.loc[:, ~df.columns.duplicated()]

        # 3. Otimização de Tipos (Downcasting) para economizar RAM antes do upload
        for col in df.select_dtypes(include=['float64']).columns:
            df[col] = pd.to_numeric(df[col], downcast='float')
        for col in df.select_dtypes(include=['int64']).columns:
            df[col] = pd.to_numeric(df[col], downcast='integer')

        # 4. Salva no banco
        with engine.begin() as conn:
            # Deleta dados antigos primeiro (mais leve que replace em alguns casos)
            # conn.execute(text(f"TRUNCATE TABLE {table_name}")) # Cuidado: Truncate é agressivo
            
            df.to_sql(
                table_name, 
                engine, 
                if_exists='replace', 
                index=False, 
                chunksize=500,  # Reduzi para 500 para ser mais leve ainda
                method='multi'
            )
        
        # 5. LIMPEZA FORÇADA DE MEMÓRIA
        del df
        gc.collect()
            
        return True

    except Exception as e:
        st.error(f"Erro no banco ({table_name}): {e}")
        return False

# ================================================
# 🔧 INTERFACE
# ================================================
def show_admin_tools(engine=None, base_data_path=None):
    st.title("🔧 Upload Otimizado")
    st.warning("⚠️ Arquivos grandes podem levar alguns segundos. Não feche a aba.")

    if engine is None:
        st.error("Sem banco de dados.")
        return

    # WMS
    st.subheader("1. WMS")
    uploaded_wms = st.file_uploader("Arquivo WMS", type=["xls", "xlsx", "xlsm"], key="wms")
    if uploaded_wms and st.button("Enviar WMS"):
        with st.spinner("Processando..."):
            df = safe_read_excel(uploaded_wms)
            if save_to_database(engine, df, "wms"):
                st.success("Sucesso!")
                st.cache_data.clear()
                gc.collect() # Limpa memória extra

    # Histórico
    st.markdown("---")
    st.subheader("2. Histórico")
    uploaded_hist = st.file_uploader("Arquivo Histórico", type=["xls", "xlsx", "xlsm"], key="hist")
    if uploaded_hist and st.button("Enviar Histórico"):
        with st.spinner("Processando..."):
            df = safe_read_excel(uploaded_hist)
            if save_to_database(engine, df, "historico"):
                st.success("Sucesso!")
                st.cache_data.clear()
                gc.collect()

    # Mix
    st.markdown("---")
    st.subheader("3. Mix")
    uploaded_mix = st.file_uploader("Arquivo Mix", type=["xls", "xlsx", "xlsm"], key="mix")
    if uploaded_mix and st.button("Enviar Mix"):
        with st.spinner("Processando..."):
            df = safe_read_excel(uploaded_mix)
            if save_to_database(engine, df, "mix"):
                st.success("Sucesso!")
                st.cache_data.clear()
                gc.collect()
