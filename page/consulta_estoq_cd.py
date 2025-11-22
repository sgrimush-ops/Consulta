import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import numpy as np

# =========================================================
# CONFIGURAÇÕES GERAIS
# =========================================================

COLUNA_DESCRICAO = "Produto"
COLUNA_ENDERECO = "Endereço"

# =========================================================
# CACHE
# =========================================================

@st.cache_resource(ttl=24 * 3600)
def get_today():
    """Data do dia, com cache expira a cada 24h."""
    return datetime.now().date()

@st.cache_data
def load_parquet_data(path: str, mod_time: float):
    """Carrega arquivo Parquet com proteção total."""
    try:
        if os.path.exists(path):
            return pd.read_parquet(path)
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao ler Parquet: {e}")
        return pd.DataFrame()


# =========================================================
# PRÉ-PROCESSAMENTOS
# =========================================================

def preprocess_wms(df: pd.DataFrame):
    """Normaliza WMS: datas, Qtd, código, remoção de colunas inúteis."""
    if df.empty:
        return pd.DataFrame()

    df = df.copy()

    # Garantir colunas essenciais
    col_datasalva = next((c for c in df.columns if c.lower() == "datasalva"), None)
    col_codigo = next((c for c in df.columns if c.lower() == "codigo"), None)
    col_qtd = next((c for c in df.columns if c.lower() == "qtd"), None)

    if not col_datasalva or not col_codigo or not col_qtd:
        st.error("Colunas essenciais ausentes no WMS (datasalva, codigo, qtd).")
        return pd.DataFrame()

    # Normalização
    df[col_datasalva] = pd.to_datetime(df[col_datasalva], errors="coerce")
    df.dropna(subset=[col_datasalva], inplace=True)
    df["datasalva_formatada"] = df[col_datasalva].dt.date

    df[col_codigo] = pd.to_numeric(df[col_codigo], errors="coerce").fillna(0).astype(int)
    df[col_qtd] = pd.to_numeric(df[col_qtd], errors="coerce").fillna(0)

    # Remover colunas lixo
    drop_cols = ["Lote", "Almoxarifado"]
    for c in drop_cols:
        if c in df.columns:
            df.drop(columns=c, inplace=True)

    return df


def preprocess_mix(df: pd.DataFrame):
    """Normaliza Mix, trazendo código + embalagem."""
    if df.empty:
        return pd.DataFrame(columns=["codigo", "embalagem"])

    df = df.copy()

    # Normaliza nomes
    df.columns = df.columns.astype(str).str.upper().str.strip()

    col_codigo = next((c for c in df.columns if c in ["CODIGOINT", "CODIGO"]), None)
    col_emb = next((c for c in df.columns if c in ["EMBSEPARACAO", "EMBALAGEM"]), None)

    if not col_codigo or not col_emb:
        return pd.DataFrame(columns=["codigo", "embalagem"])

    df.rename(columns={col_codigo: "codigo", col_emb: "embalagem"}, inplace=True)

    df["codigo"] = pd.to_numeric(df["codigo"], errors="coerce").fillna(0).astype(int)
    df["embalagem"] = df["embalagem"].astype(str).str.replace(",", ".", regex=False)
    df["embalagem"] = pd.to_numeric(df["embalagem"], errors="coerce").fillna(0).astype(int)

    df = df[["codigo", "embalagem"]].drop_duplicates(subset=["codigo"])

    return df


# =========================================================
# PÁGINA PRINCIPAL
# =========================================================

def show_consulta_page(engine=None, base_data_path=None):

    st.title("🔍 Consulta de Itens — Estoque CD")

    if not base_data_path:
        st.error("Caminho base não informado.")
        return

    # -----------------------------------------------------
    # Caminhos dos arquivos
    # -----------------------------------------------------
    wms_path = os.path.join(base_data_path, "WMS.parquet")
    mix_path = os.path.join(base_data_path, "__MixAtivoSistema.parquet")

    # -----------------------------------------------------
    # mod_time → força recarregamento quando arquivo mudar
    # -----------------------------------------------------
    def mod(p):
        return os.path.getmtime(p) if os.path.exists(p) else 0

    wms_mod = mod(wms_path)
    mix_mod = mod(mix_path)

    # -----------------------------------------------------
    # Carregar dados
    # -----------------------------------------------------
    df_wms_raw = load_parquet_data(wms_path, wms_mod)
    if df_wms_raw.empty:
        st.error("WMS.parquet não encontrado. Carregue o arquivo em Admin Tools.")
        return

    df_mix_raw = load_parquet_data(mix_path, mix_mod)

    df_wms = preprocess_wms(df_wms_raw)
    df_mix = preprocess_mix(df_mix_raw)

    if df_wms.empty:
        st.error("Falha ao processar dados do WMS.")
        return

    # -----------------------------------------------------
    # Selecionar data
    # -----------------------------------------------------
    hoje = get_today()
    df_dia = df_wms[df_wms["datasalva_formatada"] == hoje]

    st.markdown("---")

    if df_dia.empty:
        st.warning(f"Não há dados para hoje ({hoje.strftime('%d/%m/%Y')}).")
        data_sel = st.date_input("Escolha uma data:", value=hoje)
        df_dia = df_wms[df_wms["datasalva_formatada"] == data_sel]

        if df_dia.empty:
            st.info("Sem dados para a data selecionada.")
            return
    else:
        data_sel = hoje

    st.success(f"Exibindo dados do dia **{data_sel.strftime('%d/%m/%Y')}**")

    # -----------------------------------------------------
    # Merge com Mix
    # -----------------------------------------------------
    if df_mix.empty:
        df_dia["embalagem"] = 0
    else:
        df_dia = df_dia.merge(df_mix, on="codigo", how="left")
        df_dia["embalagem"] = df_dia["embalagem"].fillna(0).astype(int)

    # cálculo de caixas
    df_dia["Qtd (Caixas)"] = np.where(
        df_dia["embalagem"] > 0,
        (df_dia["Qtd"] / df_dia["embalagem"]).round(1),
        0
    )

    # -----------------------------------------------------
    # BUSCA
    # -----------------------------------------------------
    st.markdown("---")
    st.subheader("Buscar Item")

    col1, col2 = st.columns(2)
    with col1:
        busca_desc = st.text_input("Descrição:")
    with col2:
        busca_cod = st.text_input("Código (numérico):")

    codigo_escolhido = None

    # Busca por código
    if busca_cod.strip().isdigit():
        codigo_escolhido = int(busca_cod)

    # Busca por descrição → exibe lista
    elif busca_desc.strip():
        termo = busca_desc.lower()

        if COLUNA_DESCRICAO not in df_dia.columns:
            st.error(f"Coluna '{COLUNA_DESCRICAO}' não existe no WMS.")
            return

        df_tmp = df_dia[
            df_dia[COLUNA_DESCRICAO].astype(str).str.lower().str.contains(termo)
        ].copy()

        if df_tmp.empty:
            st.warning("Nenhum produto encontrado.")
        else:
            # Lista única
            df_uniq = df_tmp.drop_duplicates(subset=["codigo"])
            df_uniq["label"] = df_uniq[COLUNA_DESCRICAO] + " (Código: " + df_uniq["codigo"].astype(str) + ")"

            escolha = st.selectbox("Selecione o item:", [""] + df_uniq["label"].tolist())
            if escolha:
                codigo_escolhido = int(escolha.split("Código: ")[1].replace(")", ""))

    # -----------------------------------------------------
    # RESULTADO
    # -----------------------------------------------------

    if codigo_escolhido is not None:
        df_item = df_dia[df_dia["codigo"] == codigo_escolhido]

        if df_item.empty:
            st.warning("Nenhum registro encontrado para esse código.")
            return

        nome = df_item[COLUNA_DESCRICAO].iloc[0]
        emb = df_item["embalagem"].iloc[0]
        total_un = df_item["Qtd"].sum()

        st.markdown("---")
        st.header(nome)

        c1, c2 = st.columns(2)
        c1.metric("Unidades", f"{total_un:,.0f}")

        if emb > 0:
            c2.metric("Caixas", f"{(total_un / emb):.1f} CX")
        else:
            c2.metric("Caixas", "---")

        # Endereços
        if COLUNA_ENDERECO in df_item.columns:
            st.subheader("Endereços")
            for e in df_item[COLUNA_ENDERECO].dropna().unique():
                st.write(f"- {e}")

        # Tabela
        st.subheader("Detalhamento")
        st.dataframe(
            df_item.drop(columns=["datasalva_formatada"]),
            use_container_width=True,
            hide_index=True,
        )

    else:
        # Preview
        st.subheader("Primeiras Linhas do Dia")
        st.dataframe(
            df_dia.drop(columns=["datasalva_formatada"]).head(20),
            use_container_width=True,
            hide_index=True,
        )

