import streamlit as st
import os
import re
import pandas as pd

# Caminhos Base do Equipes_agentes (Um nível acima da pasta app_python)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BD_ENTRADA = os.path.join(BASE_DIR, 'bd_entrada')
BD_SAIDA = os.path.join(BASE_DIR, 'bd_saida')

# Configuração da Página Web
st.set_page_config(
    page_title="Varejo Insight | AI Dashboard",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilização CSS Extra para Streamlit
st.markdown("""
    <style>
    .main { background-color: #0b1120; color: #e0e0e0; }
    h1, h2, h3 { color: #89b4fa !important; }
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; background: linear-gradient(135deg, #89b4fa, #3B82F6); color: white; border: none;}
    .report-card { background: #1a1a24; padding: 20px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.05); margin-bottom: 20px; }
    .metric-card { background: #11111b; padding: 15px; border-radius: 8px; border-left: 5px solid #89b4fa; }
    .chart-container { background: #1a1a24; padding: 20px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.05); }
    </style>
""", unsafe_allow_html=True)

# Menu Lateral (Sidebar) de Navegação
st.sidebar.title("🛒 Varejo Insight")
st.sidebar.caption("Squad AI de Alta Performance")
st.sidebar.markdown("---")
page = st.sidebar.radio("Comando da Squad", [
    "📥 1. Intake de Dados (Entradas)", 
    "📊 2. Mesa da Diretoria (Resultados)"
])
st.sidebar.markdown("---")

# ----------------------------------------------------------------------------------
# TELA 1: INTAKE DE DADOS
# ----------------------------------------------------------------------------------
if page == "📥 1. Intake de Dados (Entradas)":
    st.header("📥 Gestão de Bases de Operação")
    st.write("Insira seus Arquivos CSV (separador `;` e codificação `UTF-8`) para alimentar a pasta `bd_entrada` da equipe.")
    
    uploaded_files = st.file_uploader(
        "Arraste as planilhas do seu ERP: Estoque Filial, Vendas Históricas e Estoque CD (.csv)", 
        type="csv", 
        accept_multiple_files=True
    )
    
    if uploaded_files:
        if st.button("Salvar Bases na Pasta bd_entrada"):
            for f in uploaded_files:
                file_path = os.path.join(BD_ENTRADA, f.name)
                with open(file_path, "wb") as disk_file:
                    disk_file.write(f.getbuffer())
            st.success(f"Sucesso! {len(uploaded_files)} bases gravadas com sucesso!")
    
    st.subheader("📚 Arquivos Atuais na Doca (bd_entrada)")
    try:
        if not os.path.exists(BD_ENTRADA):
            os.makedirs(BD_ENTRADA)
            
        arquivos = [f for f in os.listdir(BD_ENTRADA) if f.endswith('.csv')]
        if not arquivos:
            st.info("A pasta bd_entrada está limpa. Nenhum fornecimento agendado.")
        else:
            for f in arquivos:
                st.markdown(f"- 📄 `{f}`")
    except Exception as e:
        st.error(f"Erro ao acessar bd_entrada: {e}")


# ----------------------------------------------------------------------------------
# TELA 2: MESA DA DIRETORIA (Resultados)
# ----------------------------------------------------------------------------------
elif page == "📊 2. Mesa da Diretoria (Resultados)":
    st.header("📊 Mesa da Diretoria - Apuração e Visualização")
    st.write("Visualização consolidada de indicadores e gráficos de faturamento e reposição sugerida.")
    
    # --- PROCESSAMENTO DE DADOS PARA GRÁFICOS ---
    all_data = []
    try:
        if os.path.exists(BD_SAIDA):
            csv_files = [f for f in os.listdir(BD_SAIDA) if f.endswith('.csv')]
            for f_csv in csv_files:
                path_csv = os.path.join(BD_SAIDA, f_csv)
                df_temp = pd.read_csv(path_csv, sep=';', encoding='utf-8')
                
                # Normalização de colunas
                if 'Sugestão (Caixas)' in df_temp.columns:
                    df_temp['Qtd Sugerida'] = df_temp['Sugestão (Caixas)']
                elif 'Sugestão' in df_temp.columns:
                    df_temp['Qtd Sugerida'] = df_temp['Sugestão']
                
                if 'Qtd Sugerida' in df_temp.columns:
                    all_data.append(df_temp)
    except Exception as e:
        st.error(f"Erro ao processar dados para gráficos: {e}")

    if all_data:
        full_df = pd.concat(all_data, ignore_index=True)
        
        # --- INDICADORES ---
        st.subheader("📈 Indicadores Operacionais")
        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("Total de Itens Sugeridos", len(full_df))
        with m2:
            st.metric("Volume Total (Unidades/Cx)", int(full_df['Qtd Sugerida'].sum()))
        with m3:
            st.metric("Filiais Atendidas", full_df['filial'].nunique())
            
        st.markdown("---")
        
        # --- GRÁFICOS ---
        c1, c2 = st.columns(2)
        
        with c1:
            st.subheader("📍 Sugestão por Filial")
            chart_data = full_df.groupby('filial')['Qtd Sugerida'].sum().reset_index()
            chart_data['filial'] = chart_data['filial'].astype(str)
            st.bar_chart(chart_data.set_index('filial'), color="#89b4fa")
            st.caption("Volume de reposição distribuído por ponto de venda (PDV) e CD.")

        with c2:
            st.subheader("📦 Top Itens Solicitados")
            top_itens = full_df.groupby('descrição')['Qtd Sugerida'].sum().sort_values(ascending=False).head(10)
            st.bar_chart(top_itens, color="#a6e3a1", horizontal=True)
            st.caption("Os 10 itens com maior volume de sugestão em toda a squad.")
            
    else:
        st.info("Aguardando geração de dados (BD_SAIDA) para apresentar indicadores visuais.")

    st.markdown("---")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📝 Relatório Estratégico (Markdown)")
        try:
            if not os.path.exists(BD_SAIDA):
                os.makedirs(BD_SAIDA)
                
            arquivos_saida = [f for f in os.listdir(BD_SAIDA) if f.endswith('.md')]
            if arquivos_saida:
                ultimo_md = sorted(arquivos_saida)[-1]
                path_md = os.path.join(BD_SAIDA, ultimo_md)
                with open(path_md, "r", encoding="utf-8") as f_md:
                    st.markdown(f"<div class='report-card'>", unsafe_allow_html=True)
                    st.markdown(f"**Checkpoint Atual:** `{ultimo_md}`")
                    st.write("---")
                    st.markdown(f_md.read())
                    st.markdown(f"</div>", unsafe_allow_html=True)
            else:
                st.info("Nenhum Resumo `.md` encontrado.")
        except Exception as e:
             st.error(f"Erro ao ler relatórios: {e}")

    with col2:
        st.subheader("💾 Carga para o ERP (Download)")
        st.write("Arquivos CSV preparados para injeção no sistema raiz.")
        
        try:
            arquivos_csv = [f for f in os.listdir(BD_SAIDA) if f.endswith('.csv')]
            if arquivos_csv:
                for f_csv in arquivos_csv:
                    st.markdown(f"### 📄 `{f_csv}`")
                    path_csv = os.path.join(BD_SAIDA, f_csv)
                    with open(path_csv, "rb") as file_to_dwl:
                        st.download_button(
                            label=f"⬇️ Baixar {f_csv}",
                            data=file_to_dwl,
                            file_name=f_csv,
                            mime="text/csv",
                            key=f"dwl_{f_csv}"
                        )
                    st.markdown("---")
            else:
                st.warning("Nenhum Lote CSV na Doca de Saída.")
        except Exception as e:
            st.error(f"Erro ao carregar lista de downloads: {e}")
