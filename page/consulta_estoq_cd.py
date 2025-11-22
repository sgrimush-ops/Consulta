import streamlit as st
import pandas as pd
from sqlalchemy import text
import numpy as np
from datetime import datetime

# =========================================================
#  LOADERS DE DADOS (BLINDADO CONTRA COLUNAS FALTANTES)
# =========================================================

@st.cache_data(ttl=300, show_spinner="Buscando dados no banco...")
def load_data_from_db(_engine):
    if _engine is None:
        return pd.DataFrame(), pd.DataFrame()

    try:
        with _engine.connect() as conn:
            # --- 1. Carregar WMS (Com proteção contra falta de coluna) ---
            try:
                # Tenta buscar COM endereço
                query_wms = text("SELECT codigo, qtd, datasalva, endereco FROM wms")
                df_wms = pd.read_sql(query_wms, conn)
            except Exception:
                # SE FALHAR (porque não tem endereço), busca SEM endereço
                query_wms_fallback = text("SELECT codigo, qtd, datasalva FROM wms")
                df_wms = pd.read_sql(query_wms_fallback, conn)
                # Cria a coluna manualmente para o código não quebrar depois
                df_wms["endereco"] = "Não informado"
            
            # --- 2. Carregar MIX ---
            try:
                query_mix = text("SELECT codigoint, descricao, embseparacao FROM mix")
                df_mix = pd.read_sql(query_mix, conn)
            except Exception:
                # Fallback se o mix estiver com nomes diferentes
                df_mix = pd.DataFrame()

        return df_wms, df_mix

    except Exception as e:
        st.error(f"Erro crítico ao conectar no banco: {e}")
        return pd.DataFrame(), pd.DataFrame()

# =========================================================
#  PROCESSAMENTO
# =========================================================

def process_wms(df):
    if df.empty:
        return df
    
    # Conversão segura de datas
    if "datasalva" in df.columns:
        df["datasalva"] = pd.to_datetime(df["datasalva"], errors="coerce")
        df["datasalva_formatada"] = df["datasalva"].dt.date
    
    # Conversão segura de códigos
    if "codigo" in df.columns:
        df["codigo"] = pd.to_numeric(df["codigo"], errors="coerce").fillna(0)
        df["codigo"] = df["codigo"].astype("int32")

    if "qtd" in df.columns:
        df["qtd"] = pd.to_numeric(df["qtd"], errors="coerce").fillna(0)
        
    return df

def process_mix(df):
    if df.empty:
        return df
    
    rename_map = {
        "codigoint": "codigo",
        "embseparacao": "embalagem"
    }
    df = df.rename(columns=rename_map)

    if "codigo" in df.columns:
        df["codigo"] = pd.to_numeric(df["codigo"], errors="coerce").fillna(0)
        df["codigo"] = df["codigo"].astype("int32")
    
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
        st.error("Sem conexão com o Banco de Dados.")
        return

    # 1. Carrega dados (Engine passado implicitamente como _engine pelo decorador)
    df_wms_raw, df_mix_raw = load_data_from_db(engine)

    if df_wms_raw.empty:
        st.warning("⚠️ A tabela WMS está vazia ou ilegível. Faça o upload no menu 'Ferramentas Admin'.")
        return

    # 2. Processa
    df_wms = process_wms(df_wms_raw)
    df_mix = process_mix(df_mix_raw)

    # 3. Filtro de Data
    try:
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

    # Filtra e otimiza memória
    df_dia = df_wms[df_wms["datasalva_formatada"] == data_selecionada].copy()
    del df_wms_raw
    
    if df_dia.empty:
        st.info("Nenhum dado para esta data.")
        return

    # 4. Merge
    if not df_mix.empty:
        df_dia = df_dia.merge(df_mix[["codigo", "descricao", "embalagem"]], on="codigo", how="left")
        df_dia["descricao"] = df_dia["descricao"].fillna("Produto não cadastrado no Mix")
        df_dia["embalagem"] = df_dia["embalagem"].fillna(0).astype(int)
    else:
        df_dia["descricao"] = "Mix não carregado"
        df_dia["embalagem"] = 0

    # Cálculo Caixas
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

    if busca_cod.strip().isdigit():
        try:
            codigo_escolhido = int(busca_cod)
        except: pass

    elif busca_desc.strip():
        termo = busca_desc.lower()
        mask = (
            df_dia["descricao"].astype(str).str.lower().str.contains(termo) | 
            df_dia["codigo"].astype(str).str.contains(termo)
        )
        df_busca = df_dia[mask].copy()

        if df_busca.empty:
            st.warning("Nenhum produto encontrado.")
        else:
            if len(df_busca) > 50:
                st.caption("Muitos resultados. Mostrando os primeiros 50.")
                df_busca = df_busca.head(50)

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
            st.warning(f"Código {codigo_escolhido} não encontrado nesta data.")
        else:
            row = df_item.iloc[0]
            nome = row.get("descricao", "Desconhecido")
            emb = row.get("embalagem", 0)
            total_un = df_item["qtd"].sum()
            
            total_cx_val = row.get("Qtd (Caixas)", 0)
            if isinstance(total_cx_val, pd.Series): total_cx = total_cx_val.sum()
            else: total_cx = total_cx_val

            st.markdown("---")
            st.header(f"{nome}")
            st.caption(f"Código: {codigo_escolhido} | Emb: {emb}")

            kpi1, kpi2, kpi3 = st.columns(3)
            kpi1.metric("Total Unidades", f"{total_un:,.0f}")
            kpi2.metric("Total Caixas", f"{total_cx:.1f} CX" if emb > 0 else "---")
            
            # Endereços (Seguro)
            if "endereco" in df_item.columns:
                enderecos = df_item["endereco"].dropna().unique()
                valid_ends = [str(e) for e in enderecos if str(e).lower() not in ['nan', 'none', '', 'não informado']]
                end_str = ", ".join(valid_ends)
                if not end_str: end_str = "Sem endereço cadastrado"
                kpi3.metric("Endereços", end_str)
            else:
                kpi3.metric("Endereços", "---")

            st.subheader("Detalhamento")
            cols_show = ["codigo", "qtd", "endereco", "datasalva"]
            cols_final = [c for c in cols_show if c in df_item.columns]
            
            st.dataframe(df_item[cols_final], use_container_width=True, hide_index=True)
