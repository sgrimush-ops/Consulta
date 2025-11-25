import streamlit as st
import os
import pandas as pd
from datetime import datetime
import unicodedata

# =========================================================
# FUNÇÕES AUXILIARES
# =========================================================

def normalize_column_name(col_name):
    """Remove acentos, espaços e converte para minúsculo."""
    if not isinstance(col_name, str): return str(col_name)
    n = unicodedata.normalize('NFKD', col_name)
    return ''.join(e for e in n if e.isalnum()).lower()

def get_file_info(file_path):
    if os.path.exists(file_path):
        mod_time = os.path.getmtime(file_path)
        return datetime.fromtimestamp(mod_time).strftime('%d/%m/%Y às %H:%M:%S')
    return "Ainda não enviado"

def process_and_save_csv(uploaded_file, target_path_base, filename_csv):
    """
    Salva o CSV original e cria uma versão Parquet otimizada e limpa.
    Realiza limpeza inteligente de números (detecta formato BR vs INTL).
    """
    # Garante que o diretório existe
    os.makedirs(target_path_base, exist_ok=True)
    
    path_csv = os.path.join(target_path_base, filename_csv)
    # Nome do arquivo parquet baseado no nome do CSV (sem extensão)
    path_parquet = os.path.join(target_path_base, f"{os.path.splitext(filename_csv)[0]}.parquet")
    
    try:
        # 1. Salva o arquivo original
        uploaded_file.seek(0)
        with open(path_csv, "wb") as f:
            f.write(uploaded_file.getbuffer())
            
        # 2. Lê o CSV com robustez
        uploaded_file.seek(0)
        try:
            # Tenta separador ; (comum no Brasil) e encoding utf-8
            df = pd.read_csv(uploaded_file, sep=';', dtype=str, encoding='utf-8')
        except UnicodeDecodeError:
            uploaded_file.seek(0)
            # Tenta latin1
            df = pd.read_csv(uploaded_file, sep=';', dtype=str, encoding='latin1')
        except:
            uploaded_file.seek(0)
            # Tenta detecção automática
            df = pd.read_csv(uploaded_file, sep=None, engine='python', dtype=str, encoding='latin1')
        
        # 3. Normaliza nomes das colunas
        df.columns = [normalize_column_name(c) for c in df.columns]
        # Remove colunas "Unnamed"
        df = df.loc[:, ~df.columns.str.contains('^unnamed')]

        # 4. LIMPEZA DE DADOS NUMÉRICOS (Lógica Corrigida)
        # Lista de palavras-chave para identificar colunas numéricas
        cols_numericas = ['codigo', 'codigoint', 'loja', 'qtd', 'quantidade', 'total_cx', 
                          'est', 'estoque', 'ped', 'pendente', 'venda', 'vd', 'vm', 'embseparacao', 'emb']
        
        # Filtra as colunas que contêm os termos acima
        colunas_para_limpar = [c for c in df.columns if any(x in c for x in cols_numericas)]
        
        for col in colunas_para_limpar:
            try:
                # Garante que é string para manipulação
                df[col] = df[col].astype(str)

                # LÓGICA INTELIGENTE:
                # Verifica se existe vírgula na coluna.
                # Se EXISTE vírgula, assumimos padrão BR (1.000,50): Remove ponto milhar, troca vírgula por ponto.
                if df[col].str.contains(',', regex=False).any():
                    df[col] = df[col].str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
                
                # Se NÃO EXISTE vírgula, assumimos padrão Int'l (1000.50): Mantém o ponto como decimal.
                # Nenhuma ação de replace é necessária nesse caso.

                # Converte para numérico, erros viram NaN -> 0
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            except Exception as e:
                # Em caso de erro na conversão, apenas passa para a próxima
                print(f"Aviso na coluna {col}: {e}")
                pass

        # 5. Salva Parquet (MUITO mais rápido e leve)
        df.to_parquet(path_parquet, index=False)
        
        return True, df.head()
        
    except Exception as e:
        return False, f"Erro: {e}"

# =========================================================
# PÁGINA PRINCIPAL
# =========================================================

def show_admin_tools(engine, base_data_path):
    st.title("🔧 Upload de Arquivos (CSV)")
    st.info(f"Os arquivos serão salvos permanentemente em: `{base_data_path}`")

    # WMS
    st.markdown("---")
    st.subheader("1. Estoque CD (WMS)")
    path_wms = os.path.join(base_data_path, "WMS.parquet")
    if os.path.exists(path_wms): 
        st.caption(f"📅 Atualizado: **{get_file_info(path_wms)}**")
    else:
        st.warning("Arquivo WMS não encontrado no disco.")
    
    up_wms = st.file_uploader("Selecione WMS.csv", type=["csv"], key="wms")
    if up_wms and st.button("Processar WMS", type="primary"):
        with st.spinner("Processando..."):
            ok, res = process_and_save_csv(up_wms, base_data_path, "WMS.csv")
            if ok: 
                st.success("WMS Processado! Preview:")
                st.dataframe(res)
                st.cache_data.clear() # Limpa cache para atualizar outras telas
            else: st.error(res)

    # Histórico
    st.markdown("---")
    st.subheader("2. Histórico de Solicitações")
    path_hist = os.path.join(base_data_path, "historico_solic.parquet")
    if os.path.exists(path_hist): 
        st.caption(f"📅 Atualizado: **{get_file_info(path_hist)}**")
    else:
        st.warning("Arquivo Histórico não encontrado no disco.")

    up_hist = st.file_uploader("Selecione Histórico.csv", type=["csv"], key="hist")
    if up_hist and st.button("Processar Histórico", type="primary"):
        with st.spinner("Processando..."):
            ok, res = process_and_save_csv(up_hist, base_data_path, "historico_solic.csv")
            if ok: 
                st.success("Histórico Processado! Preview:")
                st.dataframe(res)
                st.cache_data.clear()
            else: st.error(res)

    # Mix
    st.markdown("---")
    st.subheader("3. Mix Ativo")
    path_mix = os.path.join(base_data_path, "__MixAtivoSistema.parquet")
    if os.path.exists(path_mix): 
        st.caption(f"📅 Atualizado: **{get_file_info(path_mix)}**")
    else:
        st.warning("Arquivo Mix não encontrado no disco.")

    up_mix = st.file_uploader("Selecione Mix.csv", type=["csv"], key="mix")
    if up_mix and st.button("Processar Mix", type="primary"):
        with st.spinner("Processando..."):
            ok, res = process_and_save_csv(up_mix, base_data_path, "__MixAtivoSistema.csv")
            if ok: 
                st.success("Mix Processado! Preview:")
                st.dataframe(res)
                st.cache_data.clear()
            else: st.error(res)