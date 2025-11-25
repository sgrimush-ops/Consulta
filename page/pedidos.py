import streamlit as st
import pandas as pd
from datetime import datetime
import os
from sqlalchemy import text
import numpy as np
import unicodedata

# =========================================================

# 🧩 CONSTANTES

# =========================================================

LISTA_LOJAS = ["001", "002", "003", "004", "005", "006",
               "007", "008", "011", "012", "013", "014", "017", "018"]

# =========================================================

# 📥 FUNÇÕES AUXILIARES

# =========================================================

def normalize_col(col):
    if not isinstance(col, str):
        return str(col)
    n = unicodedata.normalize('NFKD', col).encode('ASCII', 'ignore').decode('utf-8')
    return ''.join(e for e in n if e.isalnum()).lower()

def format_br(val):
    """Formata número para padrão BR: 1.234,5"""
    try:
        v = float(val)
        if v == 0:
            return "0,0"
        s = f"{v:,.1f}"
        return s.replace(',', 'X').replace('.', ',').replace('X', '.')
    except:
        return "0,0"

@st.cache_data(ttl=300)
def load_database(base_path, _engine):
    def read_safe(filename):
        p = os.path.join(base_path, f"{filename}.parquet")
        if os.path.exists(p):
            return pd.read_parquet(p)
        return pd.DataFrame()

    df_mix = read_safe("__MixAtivoSistema")
    df_hist = read_safe("historico_solic")
    df_wms = read_safe("WMS")

    # --- MIX ---
    if not df_mix.empty:
        df_mix.columns = [normalize_col(c) for c in df_mix.columns]
        rename = {}
        for c in df_mix.columns:
            if 'codigoint' in c:
                rename[c] = 'Codigo'
            elif 'descri' in c or 'produto' in c:
                rename[c] = 'Produto'
            elif 'emb' in c and 'sep' in c:
                rename[c] = 'Emb'
            elif 'ean' in c:
                rename[c] = 'EAN'
        df_mix.rename(columns=rename, inplace=True)
        if 'Codigo' in df_mix.columns:
            df_mix['Codigo'] = pd.to_numeric(df_mix['Codigo'], errors='coerce').fillna(0).astype(int).astype(str).str.strip()
        df_mix = df_mix.drop_duplicates(subset=['Codigo'])

    # --- HISTÓRICO ---
    if not df_hist.empty:
        df_hist.columns = [normalize_col(c) for c in df_hist.columns]
        rename = {}
        for c in df_hist.columns:
            if 'codigoint' in c:
                rename[c] = 'Codigo'
            elif 'loja' in c:
                rename[c] = 'Loja'
            elif 'est' in c:
                rename[c] = 'Estoque_CX'
            elif 'ped' in c:
                rename[c] = 'Pendente_CX'
            elif 'vd' in c and '1' in c:
                rename[c] = 'Venda1Sem_CX'
            elif 'vd' in c and '2' in c:
                rename[c] = 'Venda2Sem_CX'
            elif 'vm' in c and '30' in c:
                rename[c] = 'Venda30d_CX'
        df_hist.rename(columns=rename, inplace=True)

        if 'Codigo' in df_hist.columns:
            df_hist['Codigo'] = pd.to_numeric(df_hist['Codigo'], errors='coerce').fillna(0).astype(int).astype(str).str.strip()
        if 'Loja' in df_hist.columns:
            df_hist['Loja'] = pd.to_numeric(df_hist['Loja'], errors='coerce').fillna(0).astype(int).astype(str).str.zfill(3)

        cols_to_sum = ['Estoque_CX', 'Pendente_CX', 'Venda1Sem_CX', 'Venda2Sem_CX', 'Venda30d_CX']
        existing_cols = [c for c in cols_to_sum if c in df_hist.columns]
        if 'Codigo' in df_hist.columns and 'Loja' in df_hist.columns and existing_cols:
            df_hist = df_hist.groupby(['Codigo', 'Loja'], as_index=False)[existing_cols].sum(numeric_only=True)

    # --- WMS ---
    if not df_wms.empty:
        df_wms.columns = [normalize_col(c) for c in df_wms.columns]
        col_qtd = next((c for c in df_wms.columns if 'qtd' in c or 'quant' in c), None)
        if col_qtd:
            df_wms.rename(columns={col_qtd: 'Qtd_CD', 'codigo': 'Codigo'}, inplace=True)
            if 'Codigo' in df_wms.columns:
                df_wms['Codigo'] = pd.to_numeric(df_wms['Codigo'], errors='coerce').fillna(0).astype(int).astype(str).str.strip()
                df_wms = df_wms.groupby('Codigo', as_index=False)['Qtd_CD'].sum()

    # --- OFERTAS ---
    df_ofertas = pd.DataFrame()
    try:
        with _engine.connect() as conn:
            q = text("SELECT codigo, oferta, data_inicio, data_final FROM ofertas WHERE data_final >= CURRENT_DATE")
            df_ofertas = pd.read_sql(q, conn)
            if not df_ofertas.empty:
                df_ofertas['codigo'] = pd.to_numeric(df_ofertas['codigo'], errors='coerce').fillna(0).astype(int).astype(str).str.strip()
                df_ofertas['data_inicio'] = pd.to_datetime(df_ofertas['data_inicio']).dt.date
                df_ofertas['data_final'] = pd.to_datetime(df_ofertas['data_final']).dt.date
    except:
        pass

    return df_mix, df_hist, df_wms, df_ofertas

def calculate_smart_suggestion(v1_cx, v2_cx, v30_cx, est_cx, pend_cx, emb, dias_cobertura=4):
    if emb <= 0:
        return 0
    v1_un = v1_cx * emb
    v2_un = v2_cx * emb
    v30_un = v30_cx * emb
    est_un = est_cx * emb
    pend_un = pend_cx * emb
    venda_semanal_pond_un = (v1_un * 0.5) + (v2_un * 0.3) + ((v30_un / 4.0) * 0.2)
    venda_diaria_un = venda_semanal_pond_un / 7.0
    necessidade_un = venda_diaria_un * dias_cobertura
    sugestao_un = max(0, necessidade_un - (est_un + pend_un))
    return int(np.ceil(sugestao_un / emb))

def save_order(engine, dados):
    if not dados:
        return False
    try:
        with engine.begin() as conn:
            cols = ", ".join([f"loja_{l}" for l in LISTA_LOJAS])
            vals = ", ".join([f":{l}" for l in LISTA_LOJAS])
            q = text(f"INSERT INTO pedidos_consolidados (codigo, produto, embseparacao, data_pedido, usuario_pedido, status_item, total_cx, {cols}) VALUES (:c, :p, :e, :d, :u, 'Ativo', :t, {vals})")
            now = datetime.now()
            user = st.session_state.get("username", "anon")
            for item in dados:
                try:
                    emb = int(float(item.get("Emb", 0)))
                except:
                    emb = 0
                try:
                    tot = int(float(item.get("Total", 0)))
                except:
                    tot = 0
                p = {"c": str(item.get("Codigo")), "p": str(item.get("Produto")), "e": emb, "d": now, "u": user, "t": tot}
                for l in LISTA_LOJAS:
                    try:
                        p[l] = int(float(item.get(l, 0)))
                    except:
                        p[l] = 0
                conn.execute(q, p)
            return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False

# =========================================================

# 🖥️ PÁGINA PRINCIPAL

# =========================================================

def show_pedidos_page(engine, base_data_path):
    st.title("🛒 Digitação de Pedidos")
    if "pedido_atual" not in st.session_state:
        st.session_state.pedido_atual = []

    with st.spinner("Carregando dados..."):
        df_mix, df_hist, df_wms, df_ofertas = load_database(base_data_path, engine)

    if df_mix.empty:
        st.error("⚠️ Base de Mix não encontrada. Faça o upload em 'Ferramentas Admin'.")
        return

    st.subheader("1. Selecionar Produto")
    c1, c2, c3 = st.columns([1, 2, 1])
    cod_input = c1.text_input("Código:")
    desc_input = c2.text_input("Descrição:")
    c3.info(f"🎯 Meta: **4 dias** de estoque")

    prod = None
    if cod_input:
        r = df_mix[df_mix['Codigo'] == str(cod_input)]
        if not r.empty:
            prod = r.iloc[0]
        else:
            st.warning("Código não encontrado.")
    elif desc_input:
        mask = df_mix['Produto'].astype(str).str.contains(desc_input, case=False, na=False)
        r = df_mix[mask]
        if not r.empty:
            prod = r.iloc[0]
        else:
            st.warning("Descrição não encontrada.")

    if prod is None:
        st.info("Digite o código ou descrição para buscar o produto.")
        return

    st.write(f"Produto selecionado: **{prod['Produto']}**")
    emb = int(prod.get('Emb', 1))

    # Busca histórico e WMS
    df_h = df_hist[df_hist['Codigo'] == prod['Codigo']]
    df_w = df_wms[df_wms['Codigo'] == prod['Codigo']] if not df_wms.empty else pd.DataFrame()
    est_cx = df_h['Estoque_CX'].sum() if 'Estoque_CX' in df_h.columns else 0
    pend_cx = df_h['Pendente_CX'].sum() if 'Pendente_CX' in df_h.columns else 0
    venda1 = df_h['Venda1Sem_CX'].sum() if 'Venda1Sem_CX' in df_h.columns else 0
    venda2 = df_h['Venda2Sem_CX'].sum() if 'Venda2Sem_CX' in df_h.columns else 0
    venda30 = df_h['Venda30d_CX'].sum() if 'Venda30d_CX' in df_h.columns else 0
    qtd_cd = df_w['Qtd_CD'].sum() if not df_w.empty and 'Qtd_CD' in df_w.columns else 0

    sugestao = calculate_smart_suggestion(venda1, venda2, venda30, est_cx, pend_cx, emb)

    st.subheader("2. Sugestão de Pedido")
    st.write(f"Estoque atual (lojas + CD): {est_cx + qtd_cd} cx")
    st.write(f"Pendente: {pend_cx} cx")
    st.write(f"Sugestão de pedido: {sugestao} cx")

    # Botão de salvar pedido
    if st.button("✅ Salvar Pedido"):
        dados = [{
            "Codigo": prod['Codigo'],
            "Produto": prod['Produto'],
            "Emb": emb,
            "Total": sugestao,
        }]
        if save_order(engine, dados):
            st.success("Pedido salvo com sucesso!")
        else:
            st.error("Erro ao salvar pedido.")