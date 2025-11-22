import streamlit as st
import pandas as pd
import os
import tempfile
import csv
from sqlalchemy import text
import openpyxl
import gc

# ================================================
# 1. CONVERSOR DE BAIXA MEMÓRIA (STREAMING)
# ================================================
def stream_excel_to_csv(uploaded_file):
    """
    Converte Excel (.xlsx) para CSV linha por linha, sem carregar tudo na RAM.
    Retorna o caminho do arquivo CSV temporário.
    """
    try:
        # Cria um arquivo temporário no disco
        temp_csv = tempfile.NamedTemporaryFile(delete=False, suffix='.csv', mode='w', newline='', encoding='utf-8')
        writer = csv.writer(temp_csv)
        
        # Se for .xlsx ou .xlsm (usa openpyxl em modo read_only = BAIXA MEMÓRIA)
        if uploaded_file.name.lower().endswith(('.xlsx', '.xlsm')):
            wb = openpyxl.load_workbook(uploaded_file, read_only=True, data_only=True)
            sheet = wb.active
            
            # Itera linha a linha (Generator) - O segredo está aqui!
            first_row = True
            for row in sheet.iter_rows(values_only=True):
                if not any(row): continue # Pula linhas vazias
                
                # Normaliza o cabeçalho (primeira linha)
                if first_row:
                    row = [str(cell).strip().lower() for cell in row if cell is not None]
                    first_row = False
                
                writer.writerow(row)
            
            wb.close()
        
        # Se for .xls antigo (infelizmente não tem modo streaming nativo bom, usamos pandas padrão)
        elif uploaded_file.name.lower().endswith('.xls'):
            df = pd.read_excel(uploaded_file, engine='xlrd')
            df.columns = [str(c).strip().lower() for c in df.columns]
            df.to_csv(temp_csv.name, index=False)
            del df
            
        temp_csv.close()
        return temp_csv.name

    except Exception as e:
        st.error(f"Erro na conversão automática: {e}")
        return None

# ================================================
# 2. SALVAR CSV NO BANCO (EM CHUNKS)
# ================================================
def process_csv_to_db(engine, csv_path, table_name):
    """
    Lê o CSV gerado em pedaços (Chunks) e salva no banco.
    Isso impede picos de memória.
    """
    try:
        # Mapeamento de colunas (Para garantir que o Banco entenda)
        rename_map = {}
        if table_name == "mix":
            base_cols = {'codigoint': 'codigoint', 'codigo': 'codigoint', 
                         'descricao': 'descricao', 'produto': 'descricao', 
                         'embseparacao': 'embseparacao', 'emb': 'embseparacao', 'loja': 'loja'}
        elif table_name == "wms":
            base_cols = {'codigo': 'codigo', 'qtd': 'qtd', 'data': 'datasalva', 'datasalva': 'datasalva', 'endereco': 'endereco'}
        elif table_name == "historico":
            base_cols = {'codigo': 'codigoint', 'codigoint': 'codigoint', 'loja': 'loja', 
                         'dtsolicitacao': 'dtsolicitacao', 'data': 'dtsolicitacao',
                         'estcx': 'EstCX', 'pedcx': 'PedCX'}
        else:
            base_cols = {}

        # Prepara a transação de banco (Limpa a tabela antiga antes de começar)
        with engine.begin() as conn:
            # Opcional: Limpar tabela antes de inserir
            # conn.execute(text(f"TRUNCATE TABLE {table_name}")) 
            
            # Lê o CSV em pedaços de 2000 linhas
            chunk_size = 2000
            first_chunk = True
            
            for chunk in pd.read_csv(csv_path, chunksize=chunk_size):
                
                # 1. Renomear colunas dinamicamente
                cols_to_rename = {}
                for col in chunk.columns:
                    for key, val in base_cols.items():
                        if key in col.lower():
                            cols_to_rename[col] = val
                            break
                
                if cols_to_rename:
                    chunk = chunk.rename(columns=cols_to_rename)

                # 2. Remover colunas duplicadas (se houver erro de mapeamento)
                chunk = chunk.loc[:, ~chunk.columns.duplicated()]
                
                # 3. Define se substitui (primeiro lote) ou adiciona (próximos lotes)
                if first_chunk:
                    mode = 'replace'
                    first_chunk = False
                else:
                    mode = 'append'

                # 4. Salva no banco
                chunk.to_sql(table_name, engine, if_exists=mode, index=False, method='multi')
                
                # Limpa memória do chunk
                del chunk
                gc.collect()

        return True

    except Exception as e:
        st.error(f"Erro ao salvar no banco: {e}")
        return False
    finally:
        # Remove o arquivo CSV temporário do disco para não encher o servidor
        if os.path.exists(csv_path):
            os.remove(csv_path)

# ================================================
# 3. INTERFACE DO USUÁRIO
# ================================================
def show_admin_tools(engine=None, base_data_path=None):
    st.title("🔧 Upload Otimizado (Smart Convert)")
    st.info("O sistema converterá automaticamente seus arquivos Excel para CSV antes de processar, economizando memória.")

    if engine is None:
        st.error("Sem conexão com o banco.")
        return

    # --- WMS ---
    st.subheader("1. WMS")
    file_wms = st.file_uploader("Arquivo WMS", type=["xlsx", "xlsm", "xls"], key="wms")
    if file_wms and st.button("Processar WMS"):
        with st.spinner("Convertendo e enviando..."):
            csv_path = stream_excel_to_csv(file_wms)
            if csv_path and process_csv_to_db(engine, csv_path, "wms"):
                st.success("WMS Atualizado!")
                st.cache_data.clear()

    # --- HISTÓRICO ---
    st.markdown("---")
    st.subheader("2. Histórico")
    file_hist = st.file_uploader("Arquivo Histórico", type=["xlsx", "xlsm", "xls"], key="hist")
    if file_hist and st.button("Processar Histórico"):
        with st.spinner("Convertendo e enviando..."):
            csv_path = stream_excel_to_csv(file_hist)
            if csv_path and process_csv_to_db(engine, csv_path, "historico"):
                st.success("Histórico Atualizado!")
                st.cache_data.clear()

    # --- MIX ---
    st.markdown("---")
    st.subheader("3. Mix")
    file_mix = st.file_uploader("Arquivo Mix", type=["xlsx", "xlsm", "xls"], key="mix")
    if file_mix and st.button("Processar Mix"):
        with st.spinner("Convertendo e enviando..."):
            csv_path = stream_excel_to_csv(file_mix)
            if csv_path and process_csv_to_db(engine, csv_path, "mix"):
                st.success("Mix Atualizado!")
                st.cache_data.clear()
