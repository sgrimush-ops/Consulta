import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Tuple
import os

# --- Configurações Iniciais ---
FILE_PATH = 'data/WMS.xlsm'
# IMPORTANTE: Mantenha o nome exato das colunas da sua planilha
COLUNA_DESCRICAO = 'Descrição' 
COLUNA_CODIGO = 'codigo'
COLUNA_QTD = 'Qtd'

# Lista de meses para o seletor
MESES_DISPONIVEIS = {
    #"Janeiro": 1, "Fevereiro": 2, "Março": 3, "Abril": 4, "Maio": 5, "Junho": 6,"Julho": 7, "Agosto": 8, "Setembro": 9,
      "Outubro": 10, "Novembro": 11, "Dezembro": 12
}

# --- Funções de Carregamento e Pré-Processamento ---

@st.cache_data
def load_data(file_path: str) -> Optional[pd.DataFrame]:
    """Carrega dados do arquivo Excel especificado."""
    try:
        # Use a aba correta (assumindo 'WMS' como no código anterior)
        return pd.read_excel(file_path, sheet_name='WMS')
    except Exception as e:
        st.error(f"Erro ao carregar o arquivo {file_path}. Verifique o caminho e a aba. Erro: {e}")
        return None

def preprocess_data(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """Preprocessa o DataFrame, garantindo que as colunas de data e quantidade existam."""
    df = df.copy()
    
    # 1. Checa colunas essenciais
    if 'datasalva' not in df.columns or COLUNA_QTD not in df.columns or COLUNA_CODIGO not in df.columns or COLUNA_DESCRICAO not in df.columns:
        st.error(f"Colunas essenciais (datasalva, {COLUNA_QTD}, {COLUNA_CODIGO}, {COLUNA_DESCRICAO}) não encontradas.")
        return None

    # 2. Converte datas e limpa
    df['datasalva'] = pd.to_datetime(df['datasalva'], errors='coerce')
    df.dropna(subset=['datasalva', COLUNA_QTD], inplace=True) 
    df['Data_Dia'] = df['datasalva'].dt.date
    
    # 3. Garante que 'Qtd' e 'codigo' são numéricas
    df[COLUNA_QTD] = pd.to_numeric(df[COLUNA_QTD], errors='coerce')
    df[COLUNA_CODIGO] = df[COLUNA_CODIGO].fillna(0).astype(int)
    
    return df

# --- Função Principal de Análise ---

# RENOMEADA para show_ae_page() para o sistema de navegação (app.py)
def show_ae_page():
    st.title("📈 Evolução de Estoque Mensal")

    # Garante que a importação do Optional e Tuple foi feita no topo
    try:
        if 'Optional' not in globals() and 'Tuple' not in globals():
             from typing import Optional, Tuple
    except ImportError:
        pass # Ignora, pois pode já ter sido importado

    df_raw = load_data(FILE_PATH)
    if df_raw is None:
        return

    df_processed = preprocess_data(df_raw)
    if df_processed is None:
        return

    # Extrai anos únicos para o seletor
    anos_disponiveis = sorted(df_processed['datasalva'].dt.year.unique(), reverse=True)
    
    # --- ENTRADAS DE FILTRAGEM DE DATA ---
    col1, col2 = st.columns(2)
    
    with col1:
        ano_selecionado = st.selectbox("Selecione o Ano", anos_disponiveis)
    with col2:
        # Pega a lista de meses para o seletor
        meses_disponiveis_filtrados = [
            m for m, n in MESES_DISPONIVEIS.items() if n in df_processed[df_processed['datasalva'].dt.year == ano_selecionado]['datasalva'].dt.month.unique()
        ]
        if not meses_disponiveis_filtrados:
             meses_disponiveis_filtrados = list(MESES_DISPONIVEIS.keys())

        mes_selecionado = st.selectbox("Selecione o Mês", meses_disponiveis_filtrados)
    
    mes_num = MESES_DISPONIVEIS[mes_selecionado]

    # --- FILTRAGEM DE DATAS ---
    df_mensal = df_processed[
        (df_processed['datasalva'].dt.year == ano_selecionado) &
        (df_processed['datasalva'].dt.month == mes_num)
    ]

    if df_mensal.empty:
        st.warning(f"Não há dados para {mes_selecionado} de {ano_selecionado}.")
        return

    st.markdown("---")
    
    # --- FILTRO POR PRODUTO ESPECÍFICO (Autocomplete/Código) ---
    st.subheader("Filtro por Produto")
    
    col_busca_desc, col_busca_cod = st.columns(2)

    with col_busca_desc:
        termo_busca = st.text_input("Digite a descrição ou parte dela:")

    with col_busca_cod:
        codigo_direto = st.text_input("Ou digite o Código (apenas números):")

    item_selecionado_code = None
    
    if codigo_direto and codigo_direto.isdigit():
        # 1. Busca direta pelo código
        item_selecionado_code = int(codigo_direto)
        termo_busca = None
        
    elif termo_busca:
        # 2. Busca pela descrição (Autocomplete)
        
        # Cria uma coluna temporária para busca sem case sensitive
        df_mensal[f'{COLUNA_DESCRICAO}_Lower'] = df_mensal[COLUNA_DESCRICAO].astype(str).str.lower()
        termo_lower = termo_busca.lower()
        
        # Filtra
        mask = df_mensal[f'{COLUNA_DESCRICAO}_Lower'].str.contains(termo_lower, na=False)
        resultados_parciais = df_mensal[mask].sort_values(by=COLUNA_DESCRICAO, ascending=True)

        # Remove duplicatas para o dropdown
        opcoes_unicas = resultados_parciais.drop_duplicates(subset=[COLUNA_CODIGO])
        
        # Cria a lista de strings formatadas
        lista_opcoes = opcoes_unicas.apply(
            lambda row: f"{row[COLUNA_DESCRICAO]} (Código: {row[COLUNA_CODIGO]})", 
            axis=1
        ).tolist()
        
        if lista_opcoes:
            escolha = st.selectbox(
                "Selecione o produto na lista:",
                options=[''] + lista_opcoes,
                index=0
            )
            
            if escolha:
                try:
                    code_str = escolha.split('(Código: ')[1].strip(')')
                    item_selecionado_code = int(float(code_str)) # Conversão segura
                except:
                    st.error("Erro ao processar o código selecionado.") 
                    pass 
        else:
            st.warning("Nenhum produto encontrado com o termo digitado no mês selecionado.")

    
    # --- FILTRAGEM E EXIBIÇÃO DO GRÁFICO ---
    
    if item_selecionado_code:
        # Filtra o dataframe para o item específico
        df_final = df_mensal[df_mensal[COLUNA_CODIGO] == item_selecionado_code]
        
        if df_final.empty:
            st.warning(f"Nenhum item com código {item_selecionado_code} encontrado no mês.")
            return

        # Agrupa e soma a quantidade do item específico
        estoque_dia = df_final.groupby('Data_Dia')[COLUNA_QTD].sum().reset_index()
        estoque_dia.columns = ['Data', 'Estoque Item']
        
        # Exibe o título
        descricao = df_final[COLUNA_DESCRICAO].iloc[0]
        st.subheader(f"Evolução do Item: {descricao} ({item_selecionado_code})")
        
        # Exibe o gráfico do item específico
        st.line_chart(
            estoque_dia,
            x='Data',
            y='Estoque Item',
            use_container_width=True
        )
        st.dataframe(estoque_dia.tail())
        
    else:
        # Se nenhum código foi selecionado, mostra o estoque TOTAL do mês
        
        st.subheader(f"Estoque Total - {mes_selecionado}/{ano_selecionado}")
        
        # Agrupa por dia e soma a quantidade total
        estoque_total_dia = df_mensal.groupby('Data_Dia')[COLUNA_QTD].sum().reset_index()
        estoque_total_dia.columns = ['Data', 'Estoque Total']

        # Mostra o gráfico da evolução total
        st.line_chart(
            estoque_total_dia,
            x='Data',
            y='Estoque Total',
            use_container_width=True
        )
        st.dataframe(estoque_total_dia.tail())