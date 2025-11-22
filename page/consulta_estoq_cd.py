import streamlit as st
import pandas as pd
from sqlalchemy import text
import numpy as np
from datetime import datetime

# =========================================================
#  LOADERS DE DADOS (DO BANCO)
# =========================================================

@st.cache_data(ttl=300)
def load_data_from_db(_engine):
    """Carrega WMS e MIX diretamente do Banco de Dados."""
    if _engine is None:
        return pd.DataFrame(), pd.DataFrame()

    try:
        with _engine.connect() as conn:
            # 1. Carregar WMS
            # Seleciona tudo. O admin_tools já salvou com colunas em minúsculo.
            df_wms = pd.read_sql(text("SELECT * FROM wms"), conn)
            
            # 2. Carregar MIX
            df_mix = pd.read_sql(text("SELECT * FROM mix"), conn)

        return df_wms, df_mix

    except Exception as e:
        # Se a tabela não existir ainda, retorna vazio sem crashar
        return pd.DataFrame(), pd.DataFrame()

# =========================================================
#  PROCESSAMENTO
# =========================================================

def process_wms(df):
    if df.empty:
        return df
    
    # Garante tipos corretos
    # O admin_tools salva como: datasalva, codigo, qtd, endereco
    
    if "datasalva" in df.columns:
        df["datasalva"] = pd.to_datetime(df["datasalva"], errors="coerce")
        df["datasalva_formatada"] = df["datasalva"].dt.date
    
    if "codigo" in df.columns:
        df["codigo"] = pd.to_numeric(df["codigo"], errors="coerce").fillna(0).astype(int)

    if "qtd" in df.columns:
        df["qtd"] = pd.to_numeric(df["qtd"], errors="coerce").fillna(0)
        
    return df

def process_mix(df):
    if df.empty:
        return df
    
    # O admin_tools salva como: codigoint, descricao, embseparacao, loja
    
    # Normaliza nomes para facilitar o merge
    rename_map = {
        "codigoint": "codigo",
        "embseparacao": "embalagem"
    }
    df = df.rename(columns=rename_map)

    if "codigo" in df.columns:
        df["codigo"] = pd.to_numeric(df["codigo"], errors="coerce").fillna(0).astype(int)
    
    if "embalagem" in df.columns:
        # Trata caso venha como string com vírgula "12,0"
        df["embalagem"] = df["embalagem"].astype(str).str.replace(",", ".")
        df["embalagem"] = pd.to_numeric(df["embalagem"], errors="coerce").fillna(0).astype(int)

    # Remove duplicatas de código no Mix (pega o primeiro que aparecer)
    df = df.drop_duplicates(subset=["codigo"])
    
    return df

# =========================================================
#  PÁGINA PRINCIPAL
# =========================================================

def show_consulta_page(engine=None, base_data_path=None):

    st.title("🔍 Consulta de Itens — Estoque CD")

    if engine is None:
        st.error("Sem conexão com o Banco de Dados.")
        return

    # 1. Carrega dados do SQL
    df_wms_raw, df_mix_raw = load_data_from_db(engine)

    if df_wms_raw.empty:
        st.warning("⚠️ A tabela WMS está vazia no Banco de Dados. Faça o upload no menu 'Ferramentas Admin'.")
        return

    # 2. Processa
    df_wms = process_wms(df_wms_raw)
    df_mix = process_mix(df_mix_raw)

    # 3. Filtro de Data
    # Tenta pegar a data mais recente do banco
    datas_disponiveis = sorted(df_wms["datasalva_formatada"].dropna().unique(), reverse=True)
    
    if not datas_disponiveis:
        st.error("Não há datas válidas no WMS.")
        return

    st.markdown("---")
    
    col_date, _ = st.columns([1, 3])
    with col_date:
        data_selecionada = st.selectbox(
            "Selecione a data do estoque:", 
            options=datas_disponiveis,
            index=0 # Pega a mais recente por padrão
        )

    # Filtra o dataframe pela data
    df_dia = df_wms[df_wms["datasalva_formatada"] == data_selecionada].copy()
    
    if df_dia.empty:
        st.info("Nenhum dado para esta data.")
        return

    # 4. Merge com Mix (para pegar Descrição e Embalagem)
    # O WMS tem 'codigo', o Mix agora tem 'codigo' (renomeado)
    if not df_mix.empty:
        df_dia = df_dia.merge(df_mix[["codigo", "descricao", "embalagem"]], on="codigo", how="left")
        
        # Preenche nulos
        df_dia["descricao"] = df_dia["descricao"].fillna("Produto não cadastrado no Mix")
        df_dia["embalagem"] = df_dia["embalagem"].fillna(0).astype(int)
    else:
        df_dia["descricao"] = "Mix não carregado"
        df_dia["embalagem"] = 0

    # Cálculo de Caixas
    df_dia["Qtd (Caixas)"] = np.where(
        df_dia["embalagem"] > 0,
        (df_dia["qtd"] / df_dia["embalagem"]).round(1),
        0
    )

    st.success(f"Visualizando estoque de: **{data_selecionada.strftime('%d/%m/%Y')}** — Total de itens: {len(df_dia)}")

    # -----------------------------------------------------
    # BUSCA
    # -----------------------------------------------------
    st.markdown("---")
    st.subheader("Buscar Item")

    col1, col2 = st.columns(2)
    with col1:
        busca_desc = st.text_input("Descrição do Produto:")
    with col2:
        busca_cod = st.text_input("Código (numérico):")

    codigo_escolhido = None

    # Prioridade para busca por código exato
    if busca_cod.strip().isdigit():
        codigo_escolhido = int(busca_cod)

    # Busca por descrição (parcial)
    elif busca_desc.strip():
        termo = busca_desc.lower()
        # Filtra localmente
        df_busca = df_dia[
            df_dia["descricao"].astype(str).str.lower().str.contains(termo) | 
            df_dia["codigo"].astype(str).str.contains(termo)
        ].copy()

        if df_busca.empty:
            st.warning("Nenhum produto encontrado com esse termo.")
        else:
            # Cria lista para selectbox
            df_unique = df_busca.drop_duplicates(subset=["codigo"])
            options = {f"{row['descricao']} (Cód: {row['codigo']})": row['codigo'] for _, row in df_unique.iterrows()}
            
            escolha = st.selectbox("Selecione o item encontrado:", ["Selecione..."] + list(options.keys()))
            
            if escolha != "Selecione...":
                codigo_escolhido = options[escolha]

    # -----------------------------------------------------
    # EXIBIÇÃO DO RESULTADO
    # -----------------------------------------------------
    if codigo_escolhido is not None:
        df_item = df_dia[df_dia["codigo"] == codigo_escolhido]

        if df_item.empty:
            st.warning(f"O código {codigo_escolhido} não existe no estoque desta data.")
        else:
            # Dados principais
            row = df_item.iloc[0]
            nome = row.get("descricao", "Desconhecido")
            emb = row.get("embalagem", 0)
            total_un = df_item["qtd"].sum()
            total_cx = row.get("Qtd (Caixas)", 0)
            if isinstance(total_cx, pd.Series): 
                total_cx = total_cx.sum() # Garante escalar se houver duplicidade estranha

            st.markdown("---")
            st.header(f"{nome}")
            st.caption(f"Código: {codigo_escolhido} | Emb: {emb}")

            kpi1, kpi2, kpi3 = st.columns(3)
            kpi1.metric("Total Unidades", f"{total_un:,.0f}")
            kpi2.metric("Total Caixas", f"{total_cx:.1f} CX" if emb > 0 else "---")
            
            # Endereços
            if "endereco" in df_item.columns:
                enderecos = df_item["endereco"].dropna().unique()
                end_str = ", ".join([str(e) for e in enderecos if str(e).strip() != ""])
                if not end_str: end_str = "Sem endereço"
                kpi3.metric("Endereços", end_str)

            st.subheader("Detalhes de Lote/Endereço")
            # Mostra tabela limpa
            cols_show = ["codigo", "qtd", "endereco", "datasalva"]
            # Filtra apenas colunas que existem
            cols_final = [c for c in cols_show if c in df_item.columns]
            
            st.dataframe(
                df_item[cols_final],
                use_container_width=True,
                hide_index=True
            )
