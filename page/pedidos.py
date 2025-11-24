import streamlit as st
import pandas as pd
from datetime import datetime
import os
from sqlalchemy import text

# =========================================================
#  🧩 CONSTANTES
# =========================================================

LISTA_LOJAS = ["001", "002", "003", "004", "005", "006",
               "007", "008", "011", "012", "013", "014", "017", "018"]

# =========================================================
#  📥 CARREGAMENTO DE DADOS (COM CACHE)
# =========================================================

@st.cache_data(ttl=300) # Cache de 5 min: SALVA A MEMÓRIA DO SERVIDOR
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
        
        # Tratamento da Embalagem (Respeita o cadastro)
        if 'Emb' in df_mix.columns:
            # Converte vírgula para ponto, mas mantém o valor real
            df_mix['Emb'] = df_mix['Emb'].astype(str).str.replace(',', '.', regex=False)
            df_mix['Emb'] = pd.to_numeric(df_mix['Emb'], errors='coerce')
            # NÃO PREENCHE COM 1 AQUI. Deixa NaN se tiver erro, para tratar na tela.
        
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
            
            if df_wms['Qtd_CD'].dtype == object:
                df_wms['Qtd_CD'] = df_wms['Qtd_CD'].str.replace(',', '.', regex=False)
            df_wms['Qtd_CD'] = pd.to_numeric(df_wms['Qtd_CD'], errors='coerce').fillna(0)
            
            if 'Codigo' in df_wms.columns:
                df_wms['Codigo'] = pd.to_numeric(df_wms['Codigo'], errors='coerce').fillna(0).astype(int).astype(str)
                df_wms = df_wms.groupby('Codigo', as_index=False)['Qtd_CD'].sum()

    return df_mix, df_hist, df_wms

# =========================================================
#  💾 SALVAR
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
                p = {"c": item["Codigo"], "p": item["Produto"], "e": item["Emb"], "d": now, "u": user, "t": item["Total"]}
                for l in LISTA_LOJAS: p[l] = int(item.get(l, 0))
                conn.execute(q, p)
        return True
    except Exception as e:
        st.error(f"Erro: {e}")
        return False

# =========================================================
#  🖥️ PÁGINA PRINCIPAL
# =========================================================

def show_pedidos_page(engine, base_data_path):
    st.title("🛒 Digitação de Pedidos")

    if "pedido_atual" not in st.session_state:
        st.session_state.pedido_atual = []

    # Carrega dados (com cache)
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
        
        # Validação da Embalagem (Respeitando cadastro)
        emb_val = prod.get('Emb')
        if pd.isna(emb_val) or emb_val <= 0:
            st.error(f"⛔ Erro de Cadastro: Embalagem inválida ({emb_val}). Verifique o arquivo de Mix.")
            # Não permite continuar se a embalagem estiver errada, para não gerar dados sujos
            return
        
        emb = int(emb_val) # Converte para int apenas para exibição/cálculo seguro

        st.markdown("---")
        st.markdown(f"**{codigo} - {nome}** (Emb: {emb})")
        
        qtd_cd = 0
        if not df_wms.empty:
            w = df_wms[df_wms['Codigo'] == codigo]
            if not w.empty: qtd_cd = w['Qtd_CD'].iloc[0]
        
        st.info(f"CD: {int(qtd_cd)} un | **{int(qtd_cd/emb)} cx**")

        # Tabela de Lojas
        lojas_ok = st.session_state.get('lojas_acesso', [])
        grade = []
        
        sub_hist = pd.DataFrame()
        if not df_hist.empty:
            sub_hist = df_hist[df_hist['Codigo'] == codigo].set_index('Loja')

        for l in LISTA_LOJAS:
            if l not in lojas_ok: continue
            est = pend = venda = 0
            if l in sub_hist.index:
                r = sub_hist.loc[l]
                est = r.get('Estoque', 0)
                pend = r.get('Pendente', 0)
                venda = r.get('Venda30d', 0)
            grade.append({"Loja": l, "Est": est, "Pend": pend, "Venda": venda, "PEDIDO": 0})

        if grade:
            df_g = pd.DataFrame(grade)
            edited = st.data_editor(
                df_g, 
                column_config={
                    "Loja": st.column_config.TextColumn(disabled=True),
                    "Est": st.column_config.NumberColumn(disabled=True, format="%.1f"),
                    "Pend": st.column_config.NumberColumn(disabled=True, format="%.1f"),
                    "Venda": st.column_config.NumberColumn(disabled=True, format="%.1f"),
                    "PEDIDO": st.column_config.NumberColumn(min_value=0, step=1)
                },
                hide_index=True, use_container_width=True, key=f"grid_{codigo}"
            )
            
            total = edited["PEDIDO"].sum()
            if st.button(f"Adicionar ({total} cx)", type="primary", use_container_width=True):
                if total > 0:
                    item = {"Codigo": codigo, "Produto": nome, "Emb": emb, "Total": total}
                    for _, r in edited.iterrows(): item[r['Loja']] = r['PEDIDO']
                    st.session_state.pedido_atual.append(item)
                    st.success("Adicionado!")
                else:
                    st.warning("Qtd zero.")

    # 3. Carrinho
    if st.session_state.pedido_atual:
        st.markdown("---")
        st.write("### Carrinho")
        cart = pd.DataFrame(st.session_state.pedido_atual)
        st.dataframe(cart[["Codigo", "Produto", "Total"]], hide_index=True, use_container_width=True)
        
        c1, c2 = st.columns(2)
        if c1.button("✅ Finalizar Pedido"):
            if save_order(engine, st.session_state.pedido_atual):
                st.balloons()
                st.session_state.pedido_atual = []
                st.rerun()
        if c2.button("🗑️ Limpar"):
            st.session_state.pedido_atual = []
            st.rerun()
