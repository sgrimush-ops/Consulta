import streamlit as st
import os
import pandas as pd
from datetime import datetime
import unicodedata

# =========================================================
# FUNÇÕES AUXILIARES
# =========================================================

def normalize_column_name(col_name):
    if not isinstance(col_name, str): return str(col_name)
    n = unicodedata.normalize('NFKD', col_name)
    return ''.join(e for e in n if e.isalnum()).lower()

def get_file_info(file_path):
    if os.path.exists(file_path):
        mod_time = os.path.getmtime(file_path)
        return datetime.fromtimestamp(mod_time).strftime('%d/%m/%Y às %H:%M:%S')
    return None

def load_existing_parquet(file_path):
    try:
        return pd.read_parquet(file_path)
    except:
        return None

def process_and_save_csv(uploaded_file, target_path_base, filename_csv):
    """
    Salva o CSV original e cria uma versão Parquet.
    O modo 'wb' (write binary) garante que o arquivo antigo seja SOBRESCRITO.
    """
    os.makedirs(target_path_base, exist_ok=True)
    
    path_csv = os.path.join(target_path_base, filename_csv)
    path_parquet = os.path.join(target_path_base, f"{os.path.splitext(filename_csv)[0]}.parquet")
    
    try:
        # 1. Salva CSV (Sobrescreve o anterior se existir)
        uploaded_file.seek(0)
        with open(path_csv, "wb") as f:
            f.write(uploaded_file.getbuffer())
            
        # 2. Leitura Robusta
        uploaded_file.seek(0)
        try:
            df = pd.read_csv(uploaded_file, sep=';', dtype=str, encoding='utf-8')
        except UnicodeDecodeError:
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, sep=';', dtype=str, encoding='latin1')
        except:
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, sep=None, engine='python', dtype=str, encoding='latin1')
        
        # 3. Limpeza Colunas
        df.columns = [normalize_column_name(c) for c in df.columns]
        df = df.loc[:, ~df.columns.str.contains('^unnamed')]

        # 4. Limpeza Numérica Inteligente
        cols_numericas = ['codigo', 'codigoint', 'loja', 'qtd', 'quantidade', 'total_cx', 
                          'est', 'estoque', 'ped', 'pendente', 'venda', 'vd', 'vm', 'embseparacao', 'emb']
        
        colunas_para_limpar = [c for c in df.columns if any(x in c for x in cols_numericas)]
        
        for col in colunas_para_limpar:
            try:
                df[col] = df[col].astype(str)
                if df[col].str.contains(',', regex=False).any():
                    df[col] = df[col].str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            except:
                pass

        # 5. Salva Parquet (Sobrescreve o anterior)
        df.to_parquet(path_parquet, index=False)
        return True, df
        
    except Exception as e:
        return False, f"Erro crítico: {e}"

# =========================================================
# COMPONENTE DE UPLOAD INTELIGENTE
# =========================================================

def render_upload_section(label, key_suffix, filename_csv, base_path):
    parquet_filename = f"{os.path.splitext(filename_csv)[0]}.parquet"
    full_path_parquet = os.path.join(base_path, parquet_filename)
    
    st.markdown("---")
    st.subheader(label)

    # 1. Checa se arquivo já existe
    file_info = get_file_info(full_path_parquet)
    
    # Variável para controlar o texto do botão
    label_uploader = f"Enviar arquivo {filename_csv}"
    
    if file_info:
        st.success(f"✅ Arquivo atual carregado (Data: {file_info})")
        label_uploader = f"🔄 Substituir {filename_csv} (Enviar novo)"
        
        if st.checkbox(f"Ver dados carregados ({key_suffix})", key=f"check_{key_suffix}"):
            df_loaded = load_existing_parquet(full_path_parquet)
            if df_loaded is not None:
                st.dataframe(df_loaded.head())
            else:
                st.error("Erro ao ler arquivo existente.")

    # 2. Upload sempre visível para permitir atualização
    uploaded = st.file_uploader(label_uploader, type=["csv"], key=f"up_{key_suffix}")
    
    # Se o usuário enviou algo novo, processamos
    if uploaded:
        # Botão para confirmar a troca
        if st.button(f"Confirmar Processamento ({key_suffix})", type="primary", key=f"btn_{key_suffix}"):
            with st.spinner("Substituindo arquivo antigo..."):
                ok, result = process_and_save_csv(uploaded, base_path, filename_csv)
                if ok:
                    st.success("✅ Arquivo atualizado com sucesso!")
                    st.dataframe(result.head())
                    # RERUN é essencial aqui: ele recarrega a página para atualizar a data lá em cima
                    st.rerun()
                else:
                    st.error(f"Falha: {result}")

# =========================================================
# PÁGINA PRINCIPAL
# =========================================================

def show_admin_tools(engine, base_data_path):
    st.title("🔧 Upload e Persistência")
    st.info(f"Diretório de salvamento: `{base_data_path}`")

    render_upload_section("1. Estoque CD (WMS)", "wms", "WMS.csv", base_data_path)
    render_upload_section("2. Histórico", "hist", "historico_solic.csv", base_data_path)
    render_upload_section("3. Mix Ativo", "mix", "__MixAtivoSistema.csv", base_data_path)