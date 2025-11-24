import streamlit as st
import pandas as pd
from datetime import datetime
import os
from sqlalchemy import text
import numpy as np
import unicodedata

# =========================================================
#  🧩 CONSTANTES
# =========================================================

LISTA_LOJAS = ["001", "002", "003", "004", "005", "006",
               "007", "008", "011", "012", "013", "014", "017", "018"]

# =========================================================
#  📥 FUNÇÕES AUXILIARES
# =========================================================

def normalize_col(col):
    if not isinstance(col, str): return str(col)
    n = unicodedata.normalize('NFKD', col).encode('ASCII', 'ignore').decode('utf-8')
    return ''.join(e for e in n if e.isalnum()).lower()

@st.cache_data(ttl=300)
def load_database(base_path):
    def read_safe(filename):
        p = os.path.join(base_path, f"{filename}.parquet")
        if os.path.exists(p): return pd.read_parquet(p)
        return pd.DataFrame()

    df_mix = read_safe("__MixAtivoSistema")
    df_hist = read_safe("historico_solic")
    df_wms = read_safe("WMS")

    # --- MIX ---
    if not df_mix.empty:
        df_mix.columns = [normalize_col(c) for c in df_mix.columns]
        rename = {}
        for c in df_mix.columns:
            if 'codigoint' in c: rename[c] = 'Codigo'
            elif 'descri' in c or 'produto' in c: rename[c] = 'Produto'
            elif 'emb' in c and 'sep' in c: rename[c] = 'Emb'
            elif 'ean' in c: rename[c] = 'EAN'
        df_mix.rename(columns=rename, inplace=True)
        
        if 'Codigo' in df_mix.columns:
            df_mix['Codigo'] = pd.to_numeric(df_mix['Codigo'], errors='coerce').fillna(0).astype(int).astype(str)
        
        df_mix = df_mix.drop_duplicates(subset=['Codigo'])

    # --- HISTÓRICO (AGORA COM AGREGAÇÃO DE VENDAS) ---
    if not df_hist.empty:
        df_hist.columns = [normalize_col(c) for c in df_hist.columns]
        rename = {}
        for c in df_hist.columns:
            if 'codigoint' in c: rename[c] = 'Codigo'
            elif 'loja' in c: rename[c] = 'Loja'
            elif 'est' in c: rename[c] = 'Estoque'
            elif 'ped' in c: rename[c] = 'Pendente'
            elif 'vd' in c and '1' in c: rename[c] = 'Venda1Sem' # Venda 1 semana atrás
            elif 'vd' in c and '2' in c: rename[c] = 'Venda2Sem' # Venda 2 semanas atrás
            elif 'vm' in c and '30' in c: rename[c] = 'Venda30d' # Média 30 dias
        df_hist.rename(columns=rename, inplace=True)
        
        if 'Codigo' in df_hist.columns:
            df_hist['Codigo'] = pd.to_numeric(df_hist['Codigo'], errors='coerce').fillna(0).astype(int).astype(str)
        if 'Loja' in df_hist.columns:
            df_hist['Loja'] = pd.to_numeric(df_hist['Loja'], errors='coerce').fillna(0).astype(int).astype(str).str.zfill(3)
            
        # AGREGAÇÃO: Soma vendas e estoques para o mesmo produto/loja
        # Isso resolve o problema de múltiplas linhas diárias
        cols_to_sum = ['Estoque', 'Pendente', 'Venda1Sem', 'Venda2Sem', 'Venda30d']
        # Garante que as colunas existem antes de agrupar
        existing_cols = [c for c in cols_to_sum if c in df_hist.columns]
        
        if 'Codigo' in df_hist.columns and 'Loja' in df_hist.columns:
            df_hist = df_hist.groupby(['Codigo', 'Loja'], as_index=False)[existing_cols].sum(numeric_only=True)

    # --- WMS ---
    if not df_wms.empty:
        df_wms.columns = [normalize_col(c) for c in df_wms.columns]
        col_qtd = next((c for c in df_wms.columns if 'qtd' in c or 'quant' in c), None)
        
        if col_qtd:
            df_wms.rename(columns={col_qtd: 'Qtd_CD', 'codigo': 'Codigo'}, inplace=True)
            if 'Codigo' in df_wms.columns:
                df_wms['Codigo'] = pd.to_numeric(df_wms['Codigo'], errors='coerce').fillna(0).astype(int).astype(str)
                df_wms = df_wms.groupby('Codigo', as_index=False)['Qtd_CD'].sum()

    return df_mix, df_hist, df_wms

def calculate_smart_suggestion(venda1sem, venda2sem, venda30d, estoque, pendente, emb, dias_cobertura=7, is_promo=False):
    """
    Calcula sugestão ponderada:
    - Dá mais peso para a venda da última semana (tendência recente).
    - Usa média de 30 dias como base estável.
    """
    if emb <= 0: return 0
    
    # Normaliza para venda semanal média
    # Venda1Sem e Venda2Sem já são semanais.
    # Venda30d é mensal, divide por 4 para ter base semanal.
    venda_media_mensal_semanalizada = venda30d / 4.0
    
    # Média Ponderada (Peso maior para o mais recente)
    # 50% última semana, 30% penúltima, 20% histórico mês
    venda_semanal_projetada = (venda1sem * 0.5) + (venda2sem * 0.3) + (venda_media_mensal_semanalizada * 0.2)
    
    # Converte para diária
    venda_diaria = venda_semanal_projetada / 7.0
    
    # Boost de Promoção (+20%)
    if is_promo:
        venda_diaria = venda_diaria * 1.2
        
    # Necessidade Total
    necessidade_total = venda_diaria * dias_cobertura
    
    # O que falta comprar (Necessidade - (Estoque Atual + O que já pedi))
    sugestao_un = max(0, necessidade_total - (estoque + pendente))
    
    # Arredonda para caixas
    sugestao_cx = int(np.ceil(sugestao_un / emb))
    
    return sugestao_cx

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
                try: emb = int(float(item.get("Emb", 0)))
                except: emb = 0
                try: tot = int(float(item.get("Total", 0)))
                except: tot = 0
                
                p = {"c": str(item.get("Codigo")), "p": str(item.get("Produto")), "e": emb, "d": now, "u": user, "t": tot}
                for l in LISTA_LOJAS:
                    try: p[l] = int(float(item.get(l, 0)))
                    except: p[l] = 0
                conn.execute(q, p)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False

# =========================================================
#  🖥️ PÁGINA PRINCIPAL
# =========================================================

def show_pedidos_page(engine, base_data_path):
    st.title("🛒 Digitação de Pedidos (Sugestão Inteligente)")
    if "pedido_atual" not in st.session_state: st.session_state.pedido_atual = []

    df_mix, df_hist, df_wms = load_database(base_data_path)
    if df_mix.empty:
        st.warning("Mix não carregado.")
        return

    # 1. Busca e Config
    c1, c2, c3 = st.columns([1, 2, 1])
    cod_input = c1.text_input("Código:")
    desc_input = c2.text_input("Descrição:")
    
    # Dias de cobertura configurável
    dias_cob = c3.number_input("Dias de Estoque:", min_value=1, value=7)
    is_promo = st.checkbox("🔥 Produto em Promoção (Aumenta Sugestão)")

    prod = None
    if cod_input:
        r = df_mix[df_mix['Codigo'] == str(cod_input)]
        if not r.empty: prod = r.iloc[0]
        else: st.warning("Código não encontrado.")
    elif desc_input:
        mask = df_mix['Produto'].astype(str).str.lower().str.contains(desc_input.lower(), na=False)
        r = df_mix[mask].head(50)
        if not r.empty:
            opts = {f"{row['Codigo']} - {row['Produto']}": row['Codigo'] for _, row in r.iterrows()}
            sel = st.selectbox("Selecione:", [""] + list(opts.keys()))
            if sel: prod = df_mix[df_mix['Codigo'] == opts[sel]].iloc[0]

    # 2. Detalhes
    if prod is not None:
        codigo = prod['Codigo']
        nome = prod['Produto']
        emb_val = prod.get('Emb')
        
        try:
            if pd.isna(emb_val): emb = 0
            else: emb = int(float(str(emb_val).replace(',', '.')))
        except: emb = 0

        if emb <= 0:
            st.error(f"⛔ Embalagem inválida ({emb_val}).")
            return

        st.divider()
        st.markdown(f"**{codigo} - {nome}** (Emb: {emb})")
        
        qtd_cd = 0
        if not df_wms.empty:
            w = df_wms[df_wms['Codigo'] == codigo]
            if not w.empty: qtd_cd = w['Qtd_CD'].iloc[0]
        
        st.info(f"CD: {int(qtd_cd)} un | **{int(qtd_cd/emb)} cx**")

        lojas = st.session_state.get('lojas_acesso', [])
        grade = []
        
        sub = pd.DataFrame()
        if not df_hist.empty: 
            sub = df_hist[df_hist['Codigo'] == codigo].set_index('Loja')

        for l in LISTA_LOJAS:
            if l not in lojas: continue
            
            est = pend = v1 = v2 = v30 = 0.0
            
            if l in sub.index:
                r = sub.loc[l]
                if isinstance(r, pd.DataFrame): r = r.iloc[0]
                
                try: est = float(r.get('Estoque', 0) or 0)
                except: est = 0.0
                try: pend = float(r.get('Pendente', 0) or 0)
                except: pend = 0.0
                try: v1 = float(r.get('Venda1Sem', 0) or 0)
                except: v1 = 0.0
                try: v2 = float(r.get('Venda2Sem', 0) or 0)
                except: v2 = 0.0
                try: v30 = float(r.get('Venda30d', 0) or 0)
                except: v30 = 0.0
            
            # Calcula sugestão inteligente
            sug = calculate_smart_suggestion(v1, v2, v30, est, pend, emb, dias_cob, is_promo)
            
            grade.append({
                "Loja": l, 
                "Est": est, "Pend": pend, 
                "Venda 1Sem": v1, "Venda 2Sem": v2, 
                "Sugestão": int(sug), 
                "PEDIDO": 0
            })

        if grade:
            dfg = pd.DataFrame(grade)
            ed = st.data_editor(
                dfg, 
                hide_index=True, use_container_width=True, key=f"g_{codigo}",
                column_config={
                    "Loja": st.column_config.TextColumn(disabled=True),
                    "Est": st.column_config.NumberColumn(format="%.0f", disabled=True),
                    "Pend": st.column_config.NumberColumn(format="%.0f", disabled=True),
                    "Venda 1Sem": st.column_config.NumberColumn(format="%.1f", disabled=True, help="Venda 7 dias"),
                    "Venda 2Sem": st.column_config.NumberColumn(format="%.1f", disabled=True, help="Venda 14 dias"),
                    "Sugestão": st.column_config.NumberColumn(format="%d", disabled=True, help="Sugestão Inteligente"),
                    "PEDIDO": st.column_config.NumberColumn(min_value=0, step=1)
                }
            )
            
            tot = ed["PEDIDO"].sum()
            tot_sug = dfg["Sugestão"].sum()
            
            col_info, col_btn = st.columns([3, 1])
            col_info.info(f"Total Pedido: **{tot}** cx (Sugestão Inteligente: {tot_sug} cx)")
            
            if col_btn.button(f"Adicionar", type="primary", use_container_width=True):
                if tot > 0:
                    it = {"Codigo": codigo, "Produto": nome, "Emb": emb, "Total": tot}
                    for _, r in ed.iterrows(): it[r['Loja']] = int(r['PEDIDO'])
                    st.session_state.pedido_atual.append(it)
                    st.success("Adicionado!")
                else: st.warning("Qtd zero.")

    # 3. Carrinho
    if st.session_state.pedido_atual:
        st.divider()
        st.write("### Carrinho")
        cart = pd.DataFrame(st.session_state.pedido_atual)
        st.dataframe(cart[["Codigo", "Produto", "Total"]], hide_index=True)
        
        c1, c2 = st.columns(2)
        if c1.button("✅ Finalizar"):
            if save_order(engine, st.session_state.pedido_atual):
                st.balloons()
                st.session_state.pedido_atual = []
                st.rerun()
        if c2.button("🗑️ Limpar"):
            st.session_state.pedido_atual = []
            st.rerun()
