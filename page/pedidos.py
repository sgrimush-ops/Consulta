import streamlit as st
import pandas as pd
from datetime import datetime, date
import re
import os
from sqlalchemy import text
import numpy as np

# =========================================================
#  🧩 CONSTANTES E MAPEAMENTOS
# =========================================================

LISTA_LOJAS = ["001", "002", "003", "004", "005", "006",
               "007", "008", "011", "012", "013", "014", "017", "018"]

COLS_MIX_MAP = {
    'CODIGOINT': 'Codigo', 'CODIGOEAN': 'EAN', 'DESCRICAO': 'Produto',
    'LOJA': 'Loja', 'EmbSeparacao': 'embseparacao'
}

COLS_HIST_MAP = {
    'CODIGOINT': 'Codigo', 'LOJA': 'Loja', 'DtSolicitacao': 'Data',
    'EstCX': 'Estoque_G', 'PedCX': 'Pedido_H', 'Vd1sem-CX': 'Venda_I',
    'Vd2sem-CX': 'Venda_J', 'VM30dCX': 'Venda_K',
}

COLS_WMS_MAP = {
    'codigo': 'Codigo', 'Qtd': 'Qtd_CD', 'datasalva': 'Data'
}

# =========================================================
#  📂 FUNÇÕES DE LEITURA DE DADOS (OTIMIZADAS)
# =========================================================

def safe_load_parquet_or_excel(parquet_path, excel_path, usecols=None):
    """Leitura segura com fallback e proteção de erros."""
    try:
        if os.path.exists(parquet_path):
            return pd.read_parquet(parquet_path)
        if excel_path.endswith(".csv"):
            return pd.read_csv(excel_path)
        return pd.read_excel(excel_path, engine="openpyxl", usecols=usecols)
    except Exception:
        return pd.DataFrame()

def load_data_optimized(parquet_path, excel_path, usecols_map=None, dtype=None):
    """Tenta ler Parquet rapidamente, cai pra Excel se necessário."""
    df = safe_load_parquet_or_excel(parquet_path, excel_path, usecols=list(usecols_map.keys()) if usecols_map else None)
    if df.empty:
        return df
    if usecols_map:
        cols = {k: v for k, v in usecols_map.items() if k in df.columns}
        df.rename(columns=cols, inplace=True)
    return df

@st.cache_data
def load_mix_data(base_path_no_ext: str, mod_time: float):
    parquet = f"{base_path_no_ext}.parquet"
    excel = f"{base_path_no_ext}.xlsx"
    df = load_data_optimized(parquet, excel, usecols_map=COLS_MIX_MAP)

    if df.empty:
        return df

    df["Codigo"] = pd.to_numeric(df["Codigo"], errors="coerce").fillna(0).astype(int)
    
    # CORREÇÃO AQUI: Adicionado .str antes de .zfill
    df["Loja"] = df["Loja"].astype(str).str.zfill(3)

    if "embseparacao" in df.columns:
        df["embseparacao"] = (
            df["embseparacao"]
            .astype(str)
            .str.split(",")
            .str[0]
            .str.strip()
        )
        df["embseparacao"] = pd.to_numeric(df["embseparacao"], errors="coerce").fillna(0).astype(int)

    return df

@st.cache_data
def load_historico_data(base_path_no_ext: str, mod_time: float):
    parquet = f"{base_path_no_ext}.parquet"
    excel = f"{base_path_no_ext}.xlsm"
    df = load_data_optimized(parquet, excel, usecols_map=COLS_HIST_MAP)

    if df.empty:
        return df

    df["Codigo"] = pd.to_numeric(df["Codigo"], errors="coerce").fillna(0).astype(int)
    
    # CORREÇÃO AQUI: Adicionado .str antes de .zfill
    df["Loja"] = df["Loja"].astype(str).str.zfill(3)
    
    df["Data"] = pd.to_datetime(df["Data"], errors="coerce")
    df.dropna(subset=["Data"], inplace=True)

    for c in ["Estoque_G", "Pedido_H", "Venda_I", "Venda_J", "Venda_K"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    return df

@st.cache_data
def load_wms_data(base_path_no_ext: str, mod_time: float):
    parquet = f"{base_path_no_ext}.parquet"
    excel = f"{base_path_no_ext}.xlsm"
    df = load_data_optimized(parquet, excel, usecols_map=COLS_WMS_MAP)

    if df.empty:
        return df

    df["Codigo"] = pd.to_numeric(df["Codigo"], errors="coerce").fillna(0).astype(int)
    df["Qtd_CD"] = pd.to_numeric(df["Qtd_CD"], errors="coerce").fillna(0)
    df["Data"] = pd.to_datetime(df["Data"], errors="coerce")
    df.dropna(subset=["Data"], inplace=True)

    if not df.empty:
        last = df["Data"].max()
        df = df[df["Data"] == last]

    return df

@st.cache_data(ttl=300)
def load_active_offers(engine):
    if engine is None:
        return pd.DataFrame()

    today = date.today()
    q = text("""
        SELECT codigo, oferta, data_inicio, data_final
        FROM ofertas
        WHERE data_final >= :today
    """)

    try:
        with engine.connect() as conn:
            df = pd.read_sql(q, conn, params={"today": today})
        if not df.empty:
            df = df.drop_duplicates(subset=["codigo"], keep="last").set_index("codigo")
        return df
    except Exception:
        return pd.DataFrame()

# =========================================================
#  🔎 BUSCAR HISTÓRICO RECENTE (FUNÇÃO QUE FALTAVA)
# =========================================================
def get_recent_orders_display(engine, username):
    """Busca os últimos 10 pedidos do usuário para exibição rápida."""
    if engine is None:
        return pd.DataFrame()
    
    try:
        query = text("""
            SELECT id, codigo, produto, data_pedido, total_cx, status_aprovacao
            FROM pedidos_consolidados
            WHERE usuario_pedido = :user
            ORDER BY data_pedido DESC
            LIMIT 10
        """)
        
        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params={"user": username})
            
        # Formatar data se existir
        if not df.empty and "data_pedido" in df.columns:
            df["data_pedido"] = pd.to_datetime(df["data_pedido"]).dt.strftime('%d/%m/%Y %H:%M')
            
        return df
    except Exception as e:
        # Retorna vazio se der erro (ex: tabela não existe ainda)
        return pd.DataFrame()

# =========================================================
#  💾 SALVAR PEDIDO
# =========================================================
def save_order_to_db(engine, pedido_final):
    if engine is None:
        st.error("Sem conexão com banco.")
        return False

    try:
        data_pedido = datetime.now()
        usuario = st.session_state.get("username", "desconhecido")

        cols = ", ".join([f"loja_{l}" for l in LISTA_LOJAS])
        params = ", ".join([f":loja_{l}" for l in LISTA_LOJAS])

        query = text(f"""
            INSERT INTO pedidos_consolidados
            (codigo, produto, ean, embseparacao,
             data_pedido, data_aprovacao, usuario_pedido,
             status_item, {cols}, total_cx, status_aprovacao)
            VALUES
            (:codigo, :produto, :ean, :embseparacao,
             :data_pedido, NULL, :usuario_pedido,
             :status_item, {params}, :total_cx, 'Pendente')
        """)

        params_list = []
        for item in pedido_final:
            lojas_vals = {f"loja_{l}": item.get(f"loja_{l}", 0) for l in LISTA_LOJAS}
            params_list.append({
                "codigo": item["Codigo"],
                "produto": item["Produto"],
                "ean": item["EAN"],
                "embseparacao": int(item.get("embseparacao", 0)),
                "data_pedido": data_pedido,
                "usuario_pedido": usuario,
                "status_item": item["Status"],
                "total_cx": item["Total_CX"],
                **lojas_vals
            })

        with engine.begin() as conn:
            conn.execute(query, params_list)

        return True

    except Exception as e:
        st.error(f"Erro ao salvar pedido: {e}")
        return False


# =========================================================
#  🧭 INTERFACE PRINCIPAL
# =========================================================
def show_pedidos_page(engine=None, base_data_path=None):
    st.title("🛒 Digitação de Pedidos")

    if engine is None:
        st.warning("⚠️ Sem conexão com banco. Algumas funções ficarão limitadas.")

    if base_data_path is None:
        st.error("Caminho base dos dados não informado.")
        return

    if "pedido_atual" not in st.session_state:
        st.session_state.pedido_atual = []

    # Caminhos dos datasets
    mix_base = os.path.join(base_data_path, "__MixAtivoSistema")
    hist_base = os.path.join(base_data_path, "historico_solic")
    wms_base = os.path.join(base_data_path, "WMS")

    def mod(path, ext):
        p = f"{path}.parquet"
        if os.path.exists(p):
            return os.path.getmtime(p)
        p2 = f"{path}.{ext}"
        return os.path.getmtime(p2) if os.path.exists(p2) else 0.0

    mix_mod = mod(mix_base, "xlsx")
    hist_mod = mod(hist_base, "xlsm")
    wms_mod = mod(wms_base, "xlsm")

    # Carregamentos
    df_mix = load_mix_data(mix_base, mix_mod)
    df_hist = load_historico_data(hist_base, hist_mod)
    df_wms = load_wms_data(wms_base, wms_mod)
    df_ofertas = load_active_offers(engine)

    if df_mix.empty:
        st.error("Falha ao carregar MIX.")
        return

    lojas_user = st.session_state.get("lojas_acesso", [])
    if not lojas_user:
        st.error("Você não possui lojas vinculadas.")
        return

    # ==============================
    # BUSCA DO PRODUTO
    # ==============================
    st.subheader("1. Buscar Produto")
    df_mix_user = df_mix[df_mix["Loja"].isin(lojas_user)].copy()

    tab_cod, tab_nome, tab_ean = st.tabs(["Código", "Descrição", "EAN"])

    prod_sel = None

    with tab_cod:
        codigo_txt = st.text_input("Código:")
        if codigo_txt:
            try:
                codigo_num = int(codigo_txt)
                res = df_mix[df_mix["Codigo"] == codigo_num]
                if not res.empty:
                    prod_sel = res.iloc[0]
                else:
                    st.warning("Produto não encontrado.")
            except:
                st.warning("Código inválido.")

    with tab_nome:
        nome = st.text_input("Nome do Produto:")
        if nome:
            res = df_mix_user[df_mix_user["Produto"].str.contains(nome, case=False, na=False)]
            lista = res.drop_duplicates(subset=["Codigo"])
            lista["Mostrar"] = lista["Produto"] + " (Cód: " + lista["Codigo"].astype(str) + ")"

            sel = st.selectbox(
                "Selecionar:",
                ["Selecione..."] + lista["Mostrar"].tolist()
            )
            if sel != "Selecione...":
                codigo = int(re.search(r'\(Cód: (\d+)\)', sel).group(1))
                prod_sel = df_mix[df_mix["Codigo"] == codigo].iloc[0]

    with tab_ean:
        ean = st.text_input("EAN:")
        if ean:
            res = df_mix[df_mix["EAN"] == ean]
            if not res.empty:
                prod_sel = res.iloc[0]
            else:
                st.warning("EAN não encontrado.")

    st.markdown("---")

    # ==============================
    # INSERÇÃO DE QUANTIDADES
    # ==============================
    if prod_sel is not None:
        st.subheader("2. Distribuição")

        codigo = int(prod_sel["Codigo"])
        emb = int(prod_sel.get("embseparacao", 0))

        estoque_un = df_wms[df_wms["Codigo"] == codigo]["Qtd_CD"].sum()
        if emb > 0 and estoque_un > 0:
            estoque_cx = estoque_un // emb
            estoque_txt = f"{estoque_cx:,.0f} CX"
        else:
            estoque_txt = "Sem estoque"

        st.info(f"**{prod_sel['Produto']}** (Cód: {codigo}) | Emb: {emb} un/cx | CD: {estoque_txt}")

        # OFERTAS
        if not df_ofertas.empty and codigo in df_ofertas.index:
            dados = df_ofertas.loc[codigo]
            if isinstance(dados, pd.DataFrame):
                dados = dados.iloc[-1]
            preco = f"R$ {dados['oferta']:.2f}"
            ini = dados["data_inicio"].strftime("%d/%m")
            fim = dados["data_final"].strftime("%d/%m/%Y")
            hoje = date.today()

            if hoje >= dados["data_inicio"]:
                st.success(f"OFERTA ATIVA: **{preco}** até {fim}")
            else:
                st.warning(f"OFERTA FUTURA: **{preco}** → inicia em {ini}")

        # HISTÓRICO
        if not df_hist.empty:
            ultima = df_hist["Data"].max()
            df_hist_item = df_hist[(df_hist["Codigo"] == codigo) & (df_hist["Data"] == ultima)].drop_duplicates(subset=["Loja"])
            hist_map = df_hist_item.set_index("Loja").to_dict("index")
            atualizacao = ultima.strftime("%d/%m/%Y")
        else:
            hist_map = {}
            atualizacao = "N/A"

        # FORM
        with st.form("form_qty"):
            total = 0
            quantidades = {}
            cols = st.columns(3)

            for i, loja in enumerate(lojas_user):
                c = cols[i % 3]

                sugestao = 0
                legenda = f"Sem dados ({atualizacao})"
                if loja in hist_map:
                    h = hist_map[loja]
                    vm = h["Venda_K"]
                    est = h["Estoque_G"]
                    sugestao = max(0, int(np.round((vm / 7 * 4) - est)))
                    legenda = (
                        f"Est:{est:.1f} | Ped:{h['Pedido_H']:.0f} | "
                        f"V1:{h['Venda_I']:.1f} | V2:{h['Venda_J']:.1f} | VM:{vm:.1f} "
                        f"({atualizacao})"
                    )

                q = c.number_input(f"Loja {loja}", min_value=0, step=1, value=sugestao)
                c.caption(legenda)

                if q > 0:
                    quantidades[f"loja_{loja}"] = q
                    total += q

            if st.form_submit_button("Adicionar"):
                if total > 0:
                    st.session_state.pedido_atual.append({
                        "Codigo": str(codigo),
                        "Produto": prod_sel["Produto"],
                        "EAN": prod_sel["EAN"],
                        "embseparacao": emb,
                        "Status": "Ativo",
                        "Total_CX": total,
                        **quantidades
                    })
                    st.success("Item incluído!")
                else:
                    st.warning("Informe ao menos 1 unidade.")

    # ==============================
    # PEDIDO ATUAL
    # ==============================
    st.markdown("---")
    st.subheader("3. Pedido Atual")

    if st.session_state.pedido_atual:
        df_ped = pd.DataFrame(st.session_state.pedido_atual)
        st.dataframe(df_ped, use_container_width=True, hide_index=True)

        c1, c2 = st.columns(2)

        if c1.button("Salvar Pedido", type="primary"):
            if save_order_to_db(engine, st.session_state.pedido_atual):
                st.success("Pedido salvo!")
                st.session_state.pedido_atual = []
                st.rerun()

        if c2.button("Limpar Pedido"):
            st.session_state.pedido_atual = []
            st.rerun()

    else:
        st.info("Carrinho vazio.")

    # ==============================
    # HISTÓRICO
    # ==============================
    st.markdown("---")
    st.subheader("4. Histórico Recente")

    if engine:
        # Aqui é onde a nova função é chamada
        df_hist_rec = get_recent_orders_display(engine, st.session_state.get("username", ""))
        if not df_hist_rec.empty:
            st.dataframe(df_hist_rec, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum pedido recente.")
    else:
        st.warning("Histórico indisponível sem conexão com banco.")
