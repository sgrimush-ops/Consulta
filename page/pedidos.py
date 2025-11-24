import streamlit as st
import pandas as pd
from datetime import datetime
import os
from sqlalchemy import text
import numpy as np

# =========================================================
#  🧩 CONSTANTES
# =========================================================

LISTA_LOJAS = ["001", "002", "003", "004", "005", "006",
               "007", "008", "011", "012", "013", "014", "017", "018"]

# =========================================================
#  📥 CARREGAMENTO DE DADOS (COM CACHE)
# =========================================================

@st.cache_data(ttl=300)
def load_database(base_path):
    """Carrega Mix, Histórico e WMS de uma vez só."""
    
    def read_safe(filename):
        p = os.path.join(base_path, f"{filename}.parquet")
        if os.path.exists(p):
            return pd.read_parquet(p)
        return pd.DataFrame()

    df_mix = read_safe("__MixAtivoSistema")
    df_hist = read_safe("historico_solic")
    df_wms = read_safe("WMS")

    # --- Padronização MIX ---
    if not df_mix.empty:
        df_mix.columns = df_mix.columns.str.strip().str.lower()
        cols_map = {'codigoint': 'Codigo', 'descricao': 'Produto', 'embseparacao': 'Emb'}
        df_mix.rename(columns={k: v for k, v in cols_map.items() if k in df_mix.columns}, inplace=True)
        
        if 'Emb' in df_mix.columns:
            # Converte para numérico seguro
            df_mix['Emb'] = pd.to_numeric(df_mix['Emb'].astype(str).str.replace(',', '.', regex=False), errors='coerce')
        
        if 'Codigo' in df_mix.columns:
            df_mix['Codigo'] = pd.to_numeric(df_mix['Codigo'], errors='coerce').fillna(0).astype(int).astype(str)

    # --- Padronização Histórico ---
    if not df_hist.empty:
        df_hist.columns = df_hist.columns.str.strip().str.lower()
        cols_map = {'codigoint': 'Codigo', 'loja': 'Loja', 'estcx': 'Estoque', 
                    'pedcx': 'Pendente', 'vm30dcx': 'Venda30d'}
        df_hist.rename(columns={k: v for k, v in cols_map.items() if k in df_hist.columns}, inplace=True)
        
        if 'Codigo' in df_hist.columns:
            df_hist['Codigo'] = pd.to_numeric(df_hist['Codigo'], errors='coerce').fillna(0).astype(int).astype(str)
        if 'Loja' in df_hist.columns:
            df_hist['Loja'] = pd.to_numeric(df_hist['Loja'], errors='coerce').fillna(0).astype(int).astype(str).str.zfill(3)

    # --- Padronização WMS ---
    if not df_wms.empty:
        df_wms.columns = df_wms.columns.str.strip().str.lower()
        col_qtd = 'qtd' if 'qtd' in df_wms.columns else 'Qtd'
        
        if col_qtd in df_wms.columns:
            df_wms.rename(columns={col_qtd: 'Qtd_CD', 'codigo': 'Codigo'}, inplace=True)
            # Limpeza numérica
            df_wms['Qtd_CD'] = pd.to_numeric(df_wms['Qtd_CD'].astype(str).str.replace(',', '.', regex=False), errors='coerce').fillna(0)
            
            if 'Codigo' in df_wms.columns:
                df_wms['Codigo'] = pd.to_numeric(df_wms['Codigo'], errors='coerce').fillna(0).astype(int).astype(str)
                df_wms = df_wms.groupby('Codigo', as_index=False)['Qtd_CD'].sum()

    return df_mix, df_hist, df_wms

# =========================================================
#  💾 SALVAR (COM PROTEÇÃO CONTRA NUMPY)
# =========================================================

def save_order(engine, dados):
    if not dados: return False
    try:
        with engine.begin() as conn:
            cols = ", ".join([f"loja_{l}" for l in LISTA_LOJAS])
            vals = ", ".join([f":{l}" for l in LISTA_LOJAS])
            q = text(f"INSERT INTO pedidos_consolidados (codigo, produto, embseparacao, data_pedido, usuario_pedido, status_item, total_cx, {cols}) VALUES (:c, :p, :e, :d, :u, 'Ativo', :t, {vals})")
            
            now = datetime.now()
            user = st.session_state.get("username", "anon")
            
            for item in dados:
                # CONVERSÃO CRÍTICA: Garante que nada seja numpy.int64 ou numpy.float64
                # Tudo vira int nativo do Python
                
                emb_safe = int(float(item.get("Emb", 0) or 0))
                total_safe = int(float(item.get("Total", 0) or 0))
                
                p = {
                    "c": str(item["Codigo"]), 
                    "p": str(item["Produto"]), 
                    "e": emb_safe,
                    "d": now, 
                    "u": user, 
                    "t": total_safe
                }
                
                for l in LISTA_LOJAS: 
                    val = item.get(l, 0)
                    # Converte valor da loja para int nativo
                    p[l] = int(float(val or 0))
                
                conn.execute(q, p)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar no banco: {e}")
        return False

# =========================================================
#  🖥️ PÁGINA PRINCIPAL
# =========================================================

def show_pedidos_page(engine, base_data_path):
    st.title("🛒 Digitação de Pedidos")

    if "pedido_atual" not in st.session_state:
        st.session_state.pedido_atual = []

    # Carrega dados
    df_mix, df_hist, df_wms = load_database(base_data_path)

    if df_mix.empty:
        st.warning("⚠️ Mix não carregado.")
        return

    # 1. Busca
    c1, c2 = st.columns([1, 3])
    cod_input = c1.text_input("Código:")
    desc_input = c2.text_input("Descrição:")

    prod = None
    if cod_input:
        r = df_mix[df_mix['Codigo'] == str(cod_input)]
        if not r.empty: prod = r.iloc[0]
    elif desc_input:
        mask = df_mix['Produto'].astype(str).str.lower().str.contains(desc_input.lower(), na=False)
        r = df_mix[mask].head(50)
        if not r.empty:
            opts = {f"{row['Codigo']} - {row['Produto']}": row['Codigo'] for _, row in r.iterrows()}
            sel = st.selectbox("Selecione:", [""] + list(opts.keys()))
            if sel: prod = df_mix[df_mix['Codigo'] == opts[sel]].iloc[0]

    # 2. Detalhes e Grade
    if prod is not None:
        codigo = prod['Codigo']
        nome = prod['Produto']
        
        # Embalagem Segura
        emb_val = prod.get('Emb')
        # Se for NaN, Vazio ou 0 -> Erro
        if pd.isna(emb_val) or emb_val <= 0:
            st.error(f"⛔ Erro: Embalagem inválida ({emb_val}) no cadastro.")
            return
        
        emb = int(emb_val)

        st.divider()
        st.markdown(f"**{codigo} - {nome}** (Emb: {emb})")
        
        # Estoque CD
        qtd_cd = 0
        if not df_wms.empty:
            w = df_wms[df_wms['Codigo'] == codigo]
            if not w.empty: qtd_cd = w['Qtd_CD'].iloc[0]
        
        cx_cd = int(qtd_cd / emb)
        st.info(f"CD: {int(qtd_cd)} un | **{cx_cd} cx**")

        # Tabela de Lojas
        lojas_ok = st.session_state.get('lojas_acesso
