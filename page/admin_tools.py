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
        # Isso evita erro de "Coluna não encontrada" no banco
        df.columns = [str(c).strip().lower() for c in df.columns]
        
        return df
        
    except Exception as e:
        st.error(f"Erro ao ler o arquivo '{uploaded_file.name}': {e}")
        return None

# ================================================
# 💾 SALVAR DIRETO NO BANCO (POSTGRES)
# ================================================
def save_to_database(engine, df, table_name):
    """
    Escreve o DataFrame direto no PostgreSQL.
    Isso impede que os dados sumam quando o Render reinicia.
    """
    if df is None or df.empty:
        return False
    
    try:
        # Mapeamento de colunas para garantir que o Banco entenda
        rename_map = {}
        
        # Regras de mapeamento para MIX
        if table_name == "mix":
            for c in df.columns:
                # Tenta adivinhar o nome da coluna no Excel e mapear para o Banco
                if "codigo" in c: rename_map[c] = "codigoint"
                elif "descri" in c or "produto" in c: rename_map[c] = "descricao"
                elif "emb" in c: rename_map[c] = "embseparacao"
                elif "loja" in c: rename_map[c] = "loja"
        
        # Regras de mapeamento para WMS
        elif table_name == "wms":
            for c in df.columns:
                if "codigo" in c: rename_map[c] = "codigo"
                elif "qtd" in c: rename_map[c] = "qtd"
                elif "data" in c: rename_map[c] = "datasalva"
                elif "ender" in c: rename_map[c] = "endereco"
        
        # Regras de mapeamento para HISTORICO
        elif table_name == "historico":
            for c in df.columns:
                if "codigo" in c: rename_map[c] = "codigoint"
                elif "loja" in c: rename_map[c] = "loja"
                elif "data" in c or "solic" in c: rename_map[c] = "dtsolicitacao"
                # Adicione outros mapeamentos se necessário para estcx, pedcx, etc.

        # Aplica a renomeação se encontrou colunas correspondentes
        if rename_map:
            df = df.rename(columns=rename_map)

        # Salva no banco em pedaços (Chunks) de 1000 linhas
        # Isso EVITA O CRASH por falta de memória RAM
        with engine.begin() as conn:
            df.to_sql(
                table_name, 
                engine, 
                if_exists='replace',  # Substitui a tabela antiga
                index=False, 
                chunksize=1000,       # O segredo para não travar o Render
                method='multi'
            )
            
        return True

    except Exception as e:
        st.error(f"Erro ao salvar no banco de dados: {e}")
        return False

# ================================================
# 🔧 INTERFACE DA PÁGINA
# ================================================
def show_admin_tools(engine=None, base_data_path=None):
    st.title("🔧 Upload de Arquivos (Banco de Dados)")
    st.info("Envie seus arquivos Excel (.xls, .xlsx, .xlsm). Os dados serão salvos de forma segura no Banco.")

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
                    st.cache_data.clear() # Força o sistema a ler os dados novos

    st.markdown("---")

    # -------------------------------
    # 2. Histórico
    # -------------------------------
    st.subheader("2. Atualizar Histórico")
    uploaded_hist = st.file_uploader("Selecione o Histórico", type=["xls", "xlsx", "xlsm"], key="hist")
    
    if uploaded_hist:
        if st.button("Processar Histórico", type="primary"):
            with st.spinner("Processando Histórico (isso pode demorar um pouco)..."):
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
