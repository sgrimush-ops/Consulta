import streamlit as st
import pandas as pd
from sqlalchemy import text
import numpy as np
from datetime import datetime

# =========================================================
#  LOADERS DE DADOS (OTIMIZADO PARA NÃO TRAVAR)
# =========================================================

# O "_" antes de engine (_engine) é OBRIGATÓRIO para não dar erro de Hash
@st.cache_data(ttl=300, show_spinner="Buscando dados no banco...")
def load_data_from_db(_engine):
    """
    Carrega dados do Banco selecionando apenas colunas essenciais 
    para economizar memória RAM do servidor.
    """
    if _engine is None:
        return pd.DataFrame(), pd.DataFrame()

    try:
        with _engine.connect() as conn:
            # 1. Carregar WMS (Apenas colunas úteis)
            # EVITAMOS 'SELECT *' para não trazer lixo que enche a memória
            query_wms = text("""
                SELECT codigo, qtd, datasalva, endereco 
                FROM wms
            """)
            df_wms = pd.read_sql(query_wms, conn)
            
            # 2. Carregar MIX (Apenas colunas úteis)
            query_mix = text("""
                SELECT codigoint, descricao, embseparacao 
                FROM mix
            """)
            df_mix = pd.read_sql(query_mix, conn)

        return df_wms, df_mix

    except Exception as e:
        st.error(f"Erro ao ler banco: {e}")
        return pd.DataFrame(), pd.DataFrame()

# =========================================================
#  PROCESSAMENTO
# =========================================================

def process_wms(df):
    if df.empty:
        return df
    
    # Conversão otimizada
    if "datasalva" in df.columns:
        df["datasalva"] = pd.to_datetime(df["datasalva"], errors="coerce")
        df["datasalva_formatada"] = df["datasalva"].dt.date
    
    # Usa downcast para economizar memória (int32 gasta metade de int64)
    if "codigo" in df.columns:
        df["codigo"] = pd.to_numeric(df["codigo"], errors="coerce").fillna(0)
        df["codigo"] = df["codigo"].astype("int32") # Força inteiro menor

    if "qtd" in df.columns:
        df["qtd"] = pd.to_numeric(df["qtd"], errors="coerce").fillna(0)
        
    return df

def process_mix(df):
    if df.empty:
        return df
    
    # Normaliza nomes
    rename_map = {
        "codigoint": "codigo",
        "embseparacao": "embalagem"
    }
    df = df.rename(columns=rename_map)

    # Tipagem leve
    if "codigo" in df.columns:
        df["codigo"] = pd.to_numeric(df["codigo"], errors="coerce").fillna(0)
        df["codigo"] = df["codigo"].astype("int32")
    
    if "embalagem" in df.columns:
        df["embalagem"] = df["embalagem"].astype(str).str.replace(",", ".")
        df["embalagem"] = pd.to_numeric(df["embalagem"], errors="coerce").fillna(0).astype(int)

    # Remove duplicatas de código no Mix para o merge ser rápido
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

    # 1. Carrega dados do SQL (Passando engine como _engine implicitamente pelo decorador)
    df_wms_raw, df_mix_raw = load_data_from_db(engine)

    if df_wms_raw.empty:
        st.warning("⚠️ A tabela WMS está vazia ou não pôde ser carregada.")
        return

    # 2. Processa
    df_wms = process_wms(df_wms_raw)
    df_mix = process_mix(df_mix_raw)

    # 3. Filtro de Data
    try:
        # Pega datas únicas ordenadas
        datas_disponiveis = sorted(df_wms["datasalva_formatada"].dropna().unique(), reverse=True)
    except Exception:
        datas_disponiveis = []
    
    if not datas_disponiveis:
        st.error("Não há datas válidas no WMS.")
        return

    st.markdown("---")
    
    col_date, _ = st.columns([1, 3])
    with col_date:
        data_selecionada = st.selectbox(
            "Selecione a data do estoque:", 
            options=datas_disponiveis,
            index=0
        )

    # Filtra o dataframe pela data (Cria cópia apenas do necessário)
    df_dia = df_wms[df_wms["datasalva_formatada"] == data_selecionada].copy()
    
    # Libera memória do dataframe grande original (Opcional, mas ajuda)
    del df_wms_raw
    
    if df_dia.empty:
        st.info("Nenhum dado para esta data.")
        return

    # 4. Merge com Mix
    if not df_mix.empty:
        df_dia = df_dia.merge(df_mix[["codigo", "descricao", "embalagem"]], on="codigo", how="left")
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

    st.success(f"Estoque de: **{data_selecionada.strftime('%d/%m/%Y')}** — {len(df_dia)} itens")

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

    # Lógica de Busca
    if busca_cod.strip().isdigit():
        try:
            codigo_escolhido = int(busca_cod)
        except:
            pass

    elif busca_desc.strip():
        termo = busca_desc.lower()
        # Filtra localmente
        mask = (
            df_dia["descricao"].astype(str).str.lower().str.contains(termo) | 
            df_dia["codigo"].astype(str).str.contains(termo)
        )
        df_busca = df_dia[mask].copy()

        if df_busca.empty:
            st.warning("Nenhum produto encontrado.")
        else:
            # Limita a 50 resultados para não travar o selectbox
            if len(df_busca) > 50:
                st.caption("Muitos resultados encontrados. Mostrando os primeiros 50.")
                df_busca = df_busca.head(50)

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
            
            # Tratamento seguro para total de caixas
            total_cx_val = row.get("Qtd (Caixas)", 0)
            if isinstance(total_cx_val, pd.Series):
                total_cx = total_cx_val.sum()
            else:
                total_cx = total_cx_val

            st.markdown("---")
            st.header(f"{nome}")
            st.caption(f"Código: {codigo_escolhido} | Emb: {emb}")

            kpi1, kpi2, kpi3 = st.columns(3)
            kpi1.metric("Total Unidades", f"{total_un:,.0f}")
            kpi2.metric("Total Caixas", f"{total_cx:.1f} CX" if emb > 0 else "---")
            
            # Endereços
            if "endereco" in df_item.columns:
                enderecos = df_item["endereco"].dropna().unique()
                # Filtra endereços vazios ou 'nan'
                valid_ends = [str(e) for e in enderecos if str(e).lower() not in ['nan', 'none', '']]
                end_str = ", ".join(valid_ends)
                if not end_str: end_str = "Sem endereço"
                kpi3.metric("Endereços", end_str)

            st.subheader("Detalhes de Lote/Endereço")
            
            cols_show = ["codigo", "qtd", "endereco", "datasalva"]
            cols_final = [c for c in cols_show if c in df_item.columns]
            
            st.dataframe(
                df_item[cols_final],
                use_container_width=True,
                hide_index=True
            )
