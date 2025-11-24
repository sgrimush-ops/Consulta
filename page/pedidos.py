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
#  📥 CARREGAMENTO DE DADOS (COM CACHE ANTI-CRASH)
# =========================================================

@st.cache_data(ttl=300) # Cache de 5 min para evitar recarregar disco e travar
def load_database(base_path):
    """
    Carrega Mix, Histórico e WMS de uma vez só e deixa na memória.
    """
    
    def read_parquet_safe(filename):
        p = os.path.join(base_path, f"{filename}.parquet")
        if os.path.exists(p):
            return pd.read_parquet(p)
        return pd.DataFrame()

    df_mix = read_parquet_safe("__MixAtivoSistema")
    df_hist = read_parquet_safe("historico_solic")
    df_wms = read_parquet_safe("WMS")

    # --- 1. Padronização do MIX ---
    if not df_mix.empty:
        df_mix.columns = df_mix.columns.str.strip().str.lower()
        cols_map = {'codigoint': 'Codigo', 'descricao': 'Produto', 'embseparacao': 'Emb'}
        df_mix.rename(columns={k: v for k, v in cols_map.items() if k in df_mix.columns}, inplace=True)
        
        if 'Emb' in df_mix.columns:
            # Tratamento robusto da embalagem
            df_mix['Emb'] = df_mix['Emb'].astype(str).str.replace(',', '.', regex=False)
            df_mix['Emb'] = pd.to_numeric(df_mix['Emb'], errors='coerce').fillna(1)
        
        if 'Codigo' in df_mix.columns:
            df_mix['Codigo'] = pd.to_numeric(df_mix['Codigo'], errors='coerce').fillna(0).astype(int).astype(str)

    # --- 2. Padronização do Histórico ---
    if not df_hist.empty:
        df_hist.columns = df_hist.columns.str.strip().str.lower()
        cols_map = {'codigoint': 'Codigo', 'loja': 'Loja', 'estcx': 'Estoque', 
                    'pedcx': 'Pendente', 'vm30dcx': 'Venda30d'}
        df_hist.rename(columns={k: v for k, v in cols_map.items() if k in df_hist.columns}, inplace=True)
        
        if 'Codigo' in df_hist.columns:
            df_hist['Codigo'] = pd.to_numeric(df_hist['Codigo'], errors='coerce').fillna(0).astype(int).astype(str)
        if 'Loja' in df_hist.columns:
            df_hist['Loja'] = pd.to_numeric(df_hist['Loja'], errors='coerce').fillna(0).astype(int).astype(str).str.zfill(3)

    # --- 3. Padronização do WMS ---
    if not df_wms.empty:
        df_wms.columns = df_wms.columns.str.strip().str.lower()
        # Aceita 'qtd' ou 'Qtd'
        col_qtd = 'qtd' if 'qtd' in df_wms.columns else 'Qtd'
        
        if col_qtd in df_wms.columns:
            df_wms.rename(columns={col_qtd: 'Qtd_CD', 'codigo': 'Codigo'}, inplace=True)
            
            if df_wms['Qtd_CD'].dtype == object:
                df_wms['Qtd_CD'] = df_wms['Qtd_CD'].str.replace(',', '.', regex=False)
            df_wms['Qtd_CD'] = pd.to_numeric(df_wms['Qtd_CD'], errors='coerce').fillna(0)
            
            if 'Codigo' in df_wms.columns:
                df_wms['Codigo'] = pd.to_numeric(df_wms['Codigo'], errors='coerce').fillna(0).astype(int).astype(str)
                # Agrupa por código
                df_wms = df_wms.groupby('Codigo', as_index=False)['Qtd_CD'].sum()

    return df_mix, df_hist, df_wms

# =========================================================
#  💾 SALVAR
# =========================================================

def save_order_to_db(engine, pedido_dados):
    if not pedido_dados: return False
    
    username = st.session_state.get("username", "anon")
    now = datetime.now()
    
    cols_lojas = ", ".join([f"loja_{l}" for l in LISTA_LOJAS])
    vals_lojas = ", ".join([f":loja_{l}" for l in LISTA_LOJAS])
    
    query = text(f"""
        INSERT INTO pedidos_consolidados (
            codigo, produto, embseparacao, data_pedido, 
            usuario_pedido, status_item, total_cx, {cols_lojas}
        ) VALUES (
            :c, :p, :e, :d, :u, 'Ativo', :t, {vals_lojas}
        )
    """)
    
    try:
        with engine.begin() as conn:
            for item in pedido_dados:
                params = {
                    "c": item["Codigo"], "p": item["Produto"], "e": int(item["Emb"]),
                    "d": now, "u": username, "t": int(item["Total"])
                }
                for l in LISTA_LOJAS:
                    params[f"loja_{l}"] = int(item.get(l, 0))
                conn.execute(query, params)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False

# =========================================================
#  🖥️ PÁGINA PRINCIPAL
# =========================================================

def show_pedidos_page(engine, base_data_path):
    st.title("🛒 Digitação de Pedidos")

    if "pedido_atual" not in st.session_state:
        st.session_state.pedido_atual = []

    # Carrega com cache
    df_mix, df_hist, df_wms = load_database(base_data_path)

    if df_mix.empty:
        st.warning("⚠️ Base de Mix não carregada.")
        return

    # --- 1. Busca ---
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
            if sel:
                prod = df_mix[df_mix['Codigo'] == opts[sel]].iloc[0]

    # --- 2. Detalhes ---
    if prod is not None:
        codigo = prod['Codigo']
        nome = prod['Produto']
        
        # Embalagem Segura
        try:
            emb = int(float(prod['Emb']))
            if emb <= 0: emb = 1
        except:
            emb = 1
        
        st.divider()
        st.markdown(f"**Produto:** {codigo} - {nome} | **Emb:** {emb}")
        
        # Estoque CD
        qtd_cd = 0
        if not df_wms.empty:
            w_item = df_wms[df_wms['Codigo'] == codigo]
            if not w_item.empty: qtd_cd = w_item['Qtd_CD'].iloc[0]
        
        cx_cd = int(qtd_cd / emb)
        st.info(f"Estoque CD: {int(qtd_cd)} un | **{cx_cd} cx**")

        # Grade Lojas
        lojas_permitidas = st.session_state.get('lojas_acesso', [])
        dados_grade = []
        
        subset_hist = pd.DataFrame()
        if not df_hist.empty:
            subset_hist = df_hist[df_hist['Codigo'] == codigo].set_index('Loja')

        for loja in LISTA_LOJAS:
            if loja not in lojas_permitidas: continue
            
            est = pend = venda = 0
            if loja in subset_hist.index:
                row = subset_hist.loc[loja]
                est = row.get('Estoque', 0)
                pend = row.get('Pendente', 0)
                venda = row.get('Venda30d', 0)
            
            dados_grade.append({
                "Loja": loja, "Est.": round(est, 1), "Pend.": round(pend, 1), 
                "Venda": round(venda, 1), "PEDIDO": 0
            })

        if dados_grade:
            df_grade = pd.DataFrame(dados_grade)
            
            editado = st.data_editor(
                df_grade,
                column_config={
                    "Loja": st.column_config.TextColumn(disabled=True),
                    "Est.": st.column_config.NumberColumn(disabled=True),
                    "Pend.": st.column_config.NumberColumn(disabled=True),
                    "Venda": st.column_config.NumberColumn(disabled=True),
                    "PEDIDO": st.column_config.NumberColumn(min_value=0, step=1, required=True)
                },
                hide_index=True, use_container_width=True, key=f"grid_{codigo}"
            )
            
            total = editado["PEDIDO"].sum()
            
            col_add1, col_add2 = st.columns([3, 1])
            with col_add2:
                st.write(f"**Total: {total} cx**")
                if st.button("Adicionar", type="primary", use_container_width=True):
                    if total > 0:
                        item = {"Codigo": codigo, "Produto": nome, "Emb": emb, "Total": total}
                        for _, row in editado.iterrows():
                            item[row['Loja']] = row['PEDIDO']
                        st.session_state.pedido_atual.append(item)
                        st.success("Adicionado!")
                    else:
                        st.warning("Qtd zerada.")

    # --- 3. Carrinho ---
    st.divider()
    if st.session_state.pedido_atual:
        st.write("### Carrinho")
        df_cart = pd.DataFrame(st.session_state.pedido_atual)
        st.dataframe(df_cart[["Codigo", "Produto", "Total"]], hide_index=True, use_container_width=True)
        
        cb1, cb2 = st.columns(2)
        if cb1.button("✅ Finalizar", type="primary", use_container_width=True):
            if save_order_to_db(engine, st.session_state.pedido_atual):
                st.success("Enviado!")
                st.session_state.pedido_atual = []
                st.rerun()
        
        if cb2.button("🗑️ Limpar", use_container_width=True):
            st.session_state.pedido_atual = []
            st.rerun()
