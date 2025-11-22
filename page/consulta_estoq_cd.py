import streamlit as st
import pandas as pd
from sqlalchemy import text
import numpy as np

# =========================================================
#  LOADERS DE DADOS
# =========================================================

@st.cache_data(ttl=60, show_spinner="Lendo banco de dados...")
def load_data_from_db(_engine):
    if _engine is None:
        return pd.DataFrame(), pd.DataFrame()

    try:
        with _engine.connect() as conn:
            # Busca o WMS bruto
            try:
                # Tenta buscar todas as colunas relevantes
                # Convertendo nomes para minúsculo no SQL para garantir
                query_wms = text("SELECT * FROM wms")
                df_wms = pd.read_sql(query_wms, conn)
            except Exception as e:
                st.error(f"Erro ao ler tabela WMS: {e}")
                df_wms = pd.DataFrame()
            
            # Busca o MIX
            try:
                query_mix = text("SELECT codigoint, descricao, embseparacao FROM mix")
                df_mix = pd.read_sql(query_mix, conn)
            except Exception:
                df_mix = pd.DataFrame()

        return df_wms, df_mix

    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return pd.DataFrame(), pd.DataFrame()

# =========================================================
#  PROCESSAMENTO ROBUSTO
# =========================================================

def process_wms(df):
    if df.empty:
        return df
    
    # 1. Normalizar nomes de colunas para garantir que acharemos a data
    # O admin_tools salva tudo em minúsculo, mas vamos garantir
    df.columns = [str(c).lower().strip() for c in df.columns]
    
    # 2. CORREÇÃO DE DATA (O PULO DO GATO)
    if "datasalva" in df.columns:
        # dayfirst=True força o Python a entender 22/11 como Dia 22, não Mês 22
        df["datasalva"] = pd.to_datetime(df["datasalva"], dayfirst=True, errors="coerce")
        df["datasalva_formatada"] = df["datasalva"].dt.date
    else:
        # Se não achar a coluna 'datasalva', tenta achar qualquer coluna com 'data'
        col_data = next((c for c in df.columns if "data" in c), None)
        if col_data:
            df["datasalva"] = pd.to_datetime(df[col_data], dayfirst=True, errors="coerce")
            df["datasalva_formatada"] = df["datasalva"].dt.date
        else:
            st.error("Coluna de DATA não encontrada no WMS.")

    # 3. Conversão de Código e Qtd
    if "codigo" in df.columns:
        df["codigo"] = pd.to_numeric(df["codigo"], errors="coerce").fillna(0).astype("int64") # int64 para códigos grandes

    if "qtd" in df.columns:
        df["qtd"] = pd.to_numeric(df["qtd"], errors="coerce").fillna(0)
        
    return df

def process_mix(df):
    if df.empty:
        return df
    
    # Normaliza colunas
    df.columns = [str(c).lower().strip() for c in df.columns]
    
    # Renomeia para padronizar
    rename_map = {}
    if "codigoint" in df.columns: rename_map["codigoint"] = "codigo"
    if "embseparacao" in df.columns: rename_map["embseparacao"] = "embalagem"
    
    df = df.rename(columns=rename_map)

    if "codigo" in df.columns:
        df["codigo"] = pd.to_numeric(df["codigo"], errors="coerce").fillna(0).astype("int64")
    
    if "embalagem" in df.columns:
        df["embalagem"] = df["embalagem"].astype(str).str.replace(",", ".")
        df["embalagem"] = pd.to_numeric(df["embalagem"], errors="coerce").fillna(0).astype(int)

    df = df.drop_duplicates(subset=["codigo"])
    return df

# =========================================================
#  PÁGINA PRINCIPAL
# =========================================================

def show_consulta_page(engine=None, base_data_path=None):

    st.title("🔍 Consulta de Itens — Estoque CD")

    if engine is None:
        st.error("Sem conexão com Banco de Dados.")
        return

    # Carrega TUDO que está no banco
    df_wms_raw, df_mix_raw = load_data_from_db(engine)

    # ====================================================
    # 🛠️ ÁREA DE DIAGNÓSTICO (PARA VOCÊ VER O QUE ESTÁ ROLANDO)
    # ====================================================
    total_linhas_brutas = len(df_wms_raw)
    
    if total_linhas_brutas == 0:
        st.error("⚠️ A tabela WMS no banco está vazia! O upload falhou ou foi salvo com outro nome.")
        return

    # Processa os dados
    df_wms = process_wms(df_wms_raw)
    df_mix = process_mix(df_mix_raw)

    # Verifica quantas linhas perderam a data
    linhas_sem_data = df_wms["datasalva_formatada"].isna().sum()
    
    # Mostra o diagnóstico no topo
    k1, k2, k3 = st.columns(3)
    k1.metric("Total Linhas no Banco", f"{total_linhas_brutas}")
    if linhas_sem_data > 0:
        k2.metric("⚠️ Linhas com Data Inválida", f"{linhas_sem_data}", delta_color="inverse")
    
    # ====================================================

    # Filtro de Data
    try:
        datas_disponiveis = sorted(df_wms["datasalva_formatada"].dropna().unique(), reverse=True)
    except:
        datas_disponiveis = []
    
    if not datas_disponiveis:
        st.warning("Não foi possível identificar nenhuma data válida no arquivo enviado.")
        st.dataframe(df_wms.head()) # Mostra o que tem pra ajudar a debugar
        return

    st.markdown("---")
    col_date, _ = st.columns([1, 3])
    with col_date:
        data_selecionada = st.selectbox("Selecione a data:", options=datas_disponiveis, index=0)

    # Filtra pelo dia
    df_dia = df_wms[df_wms["datasalva_formatada"] == data_selecionada].copy()
    
    # Libera memória
    del df_wms_raw 

    # Merge com Mix
    if not df_mix.empty and "codigo" in df_dia.columns:
        df_dia = df_dia.merge(df_mix[["codigo", "descricao", "embalagem"]], on="codigo", how="left")
        df_dia["descricao"] = df_dia["descricao"].fillna("Produto fora do Mix")
        df_dia["embalagem"] = df_dia["embalagem"].fillna(0).astype(int)
    else:
        df_dia["descricao"] = "Mix não carregado"
        df_dia["embalagem"] = 0

    # Cálculos
    if "qtd" in df_dia.columns:
        df_dia["Qtd (Caixas)"] = np.where(
            df_dia["embalagem"] > 0,
            (df_dia["qtd"] / df_dia["embalagem"]).round(1),
            0
        )
    else:
        df_dia["qtd"] = 0
        df_dia["Qtd (Caixas)"] = 0

    # KPI do dia
    k3.metric(f"Itens em {data_selecionada}", f"{len(df_dia)}")

    # -----------------------------------------------------
    # BUSCA
    # -----------------------------------------------------
    st.markdown("---")
    st.subheader("Buscar Item")

    col1, col2 = st.columns(2)
    with col1:
        busca_desc = st.text_input("Descrição:")
    with col2:
        busca_cod = st.text_input("Código:")

    codigo_escolhido = None

    # Lógica de Busca
    if busca_cod.strip().isdigit():
        codigo_escolhido = int(busca_cod)

    elif busca_desc.strip():
        termo = busca_desc.lower()
        # Garante que as colunas existem antes de buscar
        col_desc = "descricao" if "descricao" in df_dia.columns else None
        col_cod = "codigo" if "codigo" in df_dia.columns else None
        
        if col_desc and col_cod:
            mask = (
                df_dia[col_desc].astype(str).str.lower().str.contains(termo) | 
                df_dia[col_cod].astype(str).str.contains(termo)
            )
            df_busca = df_dia[mask].copy()

            if df_busca.empty:
                st.warning("Nenhum produto encontrado.")
            else:
                if len(df_busca) > 100:
                    df_busca = df_busca.head(100) # Limite visual

                df_unique = df_busca.drop_duplicates(subset=["codigo"])
                options = {f"{row['descricao']} (Cód: {row['codigo']})": row['codigo'] for _, row in df_unique.iterrows()}
                
                escolha = st.selectbox("Selecione:", ["Selecione..."] + list(options.keys()))
                if escolha != "Selecione...":
                    codigo_escolhido = options[escolha]

    # -----------------------------------------------------
    # RESULTADO
    # -----------------------------------------------------
    if codigo_escolhido is not None:
        df_item = df_dia[df_dia["codigo"] == codigo_escolhido]

        if df_item.empty:
            st.warning(f"Código {codigo_escolhido} não encontrado na data {data_selecionada}.")
        else:
            row = df_item.iloc[0]
            nome = row.get("descricao", "---")
            emb = row.get("embalagem", 0)
            total_un = df_item["qtd"].sum()
            
            # Tratamento seguro total caixas
            cx_val = row.get("Qtd (Caixas)", 0)
            if isinstance(cx_val, pd.Series): cx_val = cx_val.sum()
            
            st.markdown("---")
            st.header(f"{nome}")
            
            kp1, kp2, kp3 = st.columns(3)
            kp1.metric("Total Unidades", f"{total_un:,.0f}")
            kp2.metric("Total Caixas", f"{cx_val:.1f} CX")
            
            # Endereços
            if "endereco" in df_item.columns:
                ends = df_item["endereco"].dropna().unique()
                valid_ends = [str(e) for e in ends if str(e).lower() not in ['nan', 'none', '', '0']]
                kp3.metric("Endereços", ", ".join(valid_ends) if valid_ends else "---")

            st.subheader("Detalhes")
            cols_show = ["codigo", "qtd", "endereco", "datasalva"]
            cols_final = [c for c in cols_show if c in df_item.columns]
            st.dataframe(df_item[cols_final], use_container_width=True, hide_index=True)
