import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import datetime
import gc

# ================================================
# 🚀 PROCESSAMENTO RÁPIDO E DIRETO
# ================================================
def process_file_fast(engine, uploaded_file, table_name):
    """
    Lê o Excel diretamente para a memória (Rápido) e salva no banco.
    """
    try:
        # 1. Leitura Rápida (Pandas Nativo)
        # Engine openpyxl é o padrão para xlsx/xlsm
        if uploaded_file.name.endswith('.xls'):
            df = pd.read_excel(uploaded_file, engine='xlrd')
        else:
            df = pd.read_excel(uploaded_file, engine='openpyxl')

        # Normaliza nomes das colunas
        df.columns = [str(c).strip().lower() for c in df.columns]

        # 2. Mapeamento de Colunas (Garante que o Banco aceite)
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

        # 3. Remove colunas duplicadas (Segurança)
        df = df.loc[:, ~df.columns.duplicated()]

        # 4. Salva no Banco
        with engine.begin() as conn:
            # Chunksize 2000 é um bom equilíbrio entre velocidade e estabilidade de rede
            df.to_sql(table_name, engine, if_exists='replace', index=False, chunksize=2000, method='multi')

        # Limpa memória imediatamente
        del df
        gc.collect()
        
        return True

    except Exception as e:
        st.error(f"Erro ao processar {table_name}: {e}")
        return False

# ================================================
# 🖥️ INTERFACE (AUTOMÁTICA)
# ================================================
def show_admin_tools(engine=None, base_data_path=None):
    st.title("⚡ Upload Automático")
    st.info("Basta selecionar o arquivo. O processamento iniciará automaticamente.")

    if engine is None:
        st.error("Sem conexão com o banco.")
        return

    # Inicializa histórico de uploads na sessão se não existir
    if "upload_history" not in st.session_state:
        st.session_state.upload_history = {}

    # --- Função auxiliar para o Widget de Upload ---
    def handle_upload(key_name, table_name, label):
        uploaded_file = st.file_uploader(label, type=["xlsx", "xlsm", "xls"], key=key_name)
        
        if uploaded_file is not None:
            # Cria uma chave única baseada no nome e tamanho para saber se já processamos esse arquivo específico
            file_id = f"{uploaded_file.name}_{uploaded_file.size}"
            
            # Se ainda não foi processado nesta sessão, processa agora
            if file_id not in st.session_state.upload_history:
                with st.status(f"Processando {uploaded_file.name}...", expanded=True) as status:
                    st.write("Lendo arquivo...")
                    if process_file_fast(engine, uploaded_file, table_name):
                        timestamp = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
                        st.session_state.upload_history[file_id] = timestamp
                        status.update(label="Concluído!", state="complete", expanded=False)
                        st.cache_data.clear() # Limpa cache para atualizar as consultas
                        st.rerun() # Atualiza a tela para mostrar o timestamp
                    else:
                        status.update(label="Falha no processamento", state="error")
            
            # Se já foi processado, mostra quando foi
            else:
                ts = st.session_state.upload_history[file_id]
                st.success(f"✅ **{uploaded_file.name}** processado em: **{ts}**")

    # --- 1. WMS ---
    st.subheader("1. WMS (Estoque)")
    handle_upload("u_wms", "wms", "Selecione arquivo WMS")

    st.markdown("---")

    # --- 2. Histórico ---
    st.subheader("2. Histórico")
    handle_upload("u_hist", "historico", "Selecione arquivo Histórico")

    st.markdown("---")

    # --- 3. Mix ---
    st.subheader("3. Mix")
    handle_upload("u_mix", "mix", "Selecione arquivo Mix")
