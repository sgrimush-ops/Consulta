import streamlit as st
import pandas as pd
from sqlalchemy import text

# ================================================
# 🔧 LEITURA INTELIGENTE DE EXCEL (.xls, .xlsx, .xlsm)
# ================================================
def safe_read_excel(uploaded_file):
    """
    Lê arquivos Excel detectando a extensão correta.
    Suporta: .xls (Excel 97-2003), .xlsx, .xlsm
    """
    try:
        filename = uploaded_file.name.lower()
        
        # Se for o formato antigo (.xls), usa a engine 'xlrd'
        if filename.endswith('.xls'):
            df = pd.read_excel(uploaded_file, engine='xlrd')
        
        # Se for formato novo (.xlsx ou .xlsm), usa a engine 'openpyxl'
        else:
            df = pd.read_excel(uploaded_file, engine='openpyxl')
        
        # Normaliza nomes das colunas (remove espaços e deixa minúsculo)
        df.columns = [str(c).strip().lower() for c in df.columns]
        
        return df
        
    except Exception as e:
        st.error(f"Erro ao ler o arquivo '{uploaded_file.name}': {e}")
        return None

# ================================================
# 💾 SALVAR DIRETO NO BANCO (CORRIGIDO)
# ================================================
def save_to_database(engine, df, table_name):
    """
    Escreve o DataFrame direto no PostgreSQL.
    Resolve problemas de colunas duplicadas antes de salvar.
    """
    if df is None or df.empty:
        return False
    
    try:
        rename_map = {}
        
        # --- REGRAS DE MAPEAMENTO ---
        # Tenta padronizar os nomes que vêm do Excel para o que o Banco espera
        
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
                # Mapeia as colunas de vendas/estoque se existirem no Excel
                elif "estcx" in c: rename_map[c] = "EstCX"
                elif "pedcx" in c: rename_map[c] = "PedCX"

        # 1. Aplica a renomeação
        if rename_map:
            df = df.rename(columns=rename_map)

        # 2. CRUCIAL: REMOVE COLUNAS DUPLICADAS
        # Se o Excel tinha "Codigo" e "CodigoInt", ambos viraram "codigoint".
        # Isso causava o erro. O comando abaixo mantém apenas o primeiro.
        df = df.loc[:, ~df.columns.duplicated()]

        # 3. Salva no banco (Substitui a tabela antiga)
        with engine.begin() as conn:
            df.to_sql(
                table_name, 
                engine, 
                if_exists='replace',  # Deleta a tabela antiga e cria uma nova limpa
                index=False, 
                chunksize=1000,       # Envia em pacotes para não travar a memória
                method='multi'
            )
            
        return True

    except Exception as e:
        st.error(f"Erro ao salvar no banco de dados ({table_name}): {e}")
        return False

# ================================================
# 🔧 INTERFACE DA PÁGINA
# ================================================
def show_admin_tools(engine=None, base_data_path=None):
    st.title("🔧 Upload de Arquivos (Banco de Dados)")
    st.info("Envie seus arquivos Excel (.xls, .xlsx, .xlsm). Os dados ficarão salvos permanentemente no Banco.")

    if engine is None:
        st.error("❌ Sem conexão com o banco de dados.")
        return

    # -------------------------------
    # 1. WMS
    # -------------------------------
    st.subheader("1. Atualizar WMS (Estoque CD)")
    uploaded_wms = st.file_uploader("Selecione o WMS", type=["xls", "xlsx", "xlsm"], key="wms")
    
    if uploaded_wms:
        if st.button("Processar WMS", type="primary"):
            with st.spinner("Lendo arquivo e salvando no banco..."):
                df = safe_read_excel(uploaded_wms)
                if save_to_database(engine, df, "wms"):
                    st.success("✅ Tabela WMS atualizada com sucesso!")
                    st.cache_data.clear() 

    st.markdown("---")

    # -------------------------------
    # 2. Histórico
    # -------------------------------
    st.subheader("2. Atualizar Histórico")
    uploaded_hist = st.file_uploader("Selecione o Histórico", type=["xls", "xlsx", "xlsm"], key="hist")
    
    if uploaded_hist:
        if st.button("Processar Histórico", type="primary"):
            with st.spinner("Processando Histórico..."):
                df = safe_read_excel(uploaded_hist)
                if save_to_database(engine, df, "historico"):
                    st.success("✅ Histórico atualizado com sucesso!")
                    st.cache_data.clear()

    st.markdown("---")

    # -------------------------------
    # 3. Mix
    # -------------------------------
    st.subheader("3. Atualizar Mix")
    uploaded_mix = st.file_uploader("Selecione o Mix", type=["xls", "xlsx", "xlsm"], key="mix")
    
    if uploaded_mix:
        if st.button("Processar Mix", type="primary"):
            with st.spinner("Atualizando Mix..."):
                df = safe_read_excel(uploaded_mix)
                if save_to_database(engine, df, "mix"):
                    st.success("✅ Mix de produtos atualizado com sucesso!")
                    st.cache_data.clear()
