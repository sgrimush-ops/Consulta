import streamlit as st
import pandas as pd
from datetime import datetime
import os
from sqlalchemy import text
import numpy as np
import unicodedata

# --- CONSTANTES ---
LISTA_LOJAS = ["001", "002", "003", "004", "005", "006",
               "007", "008", "011", "012", "013", "014", "017", "018"]

# --- FUNÇÕES AUXILIARES ---

def normalize_col(col):
    if not isinstance(col, str):
        return str(col)
    n = unicodedata.normalize('NFKD', col).encode('ASCII', 'ignore').decode('utf-8')
    return ''.join(e for e in n if e.isalnum()).lower()

@st.cache_data(ttl=300)
def load_database(base_path, engine):
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
            if 'codigoint' in c: rename[c] = 'Codigo'
            elif 'descri' in c or 'produto' in c: rename[c] = 'Produto'
            elif 'emb' in c and 'sep' in c: rename[c] = 'Emb'
            elif 'ean' in c: rename[c] = 'EAN'
        df_mix.rename(columns=rename, inplace=True)
        if 'Codigo' in df_mix.columns:
            df_mix['Codigo'] = (pd.to_numeric(df_mix['Codigo'], errors='coerce')
                                .fillna(0).astype(int).astype(str))
        df_mix = df_mix.drop_duplicates(subset=['Codigo'])

    # --- HISTÓRICO ---
    if not df_hist.empty:
        df_hist.columns = [normalize_col(c) for c in df_hist.columns]
        rename = {}
        for c in df_hist.columns:
            if 'codigoint' in c: rename[c] = 'Codigo'
            elif 'loja' in c: rename[c] = 'Loja'
            elif 'vd1sem' in c: rename[c] = 'Venda1Sem'
            elif 'vd2sem' in c: rename[c] = 'Venda2Sem'
            elif 'vm30d' in c or 'vm30' in c: rename[c] = 'Venda30d'
            elif 'est' in c: rename[c] = 'Estoque'
            elif 'ped' in c: rename[c] = 'Pendente'
        df_hist.rename(columns=rename, inplace=True)

        # Padroniza tipos
        if 'Codigo' in df_hist.columns:
            df_hist['Codigo'] = (pd.to_numeric(df_hist['Codigo'], errors='coerce')
                                 .fillna(0).astype(int).astype(str))
        if 'Loja' in df_hist.columns:
            df_hist['Loja'] = (pd.to_numeric(df_hist['Loja'], errors='coerce')
                               .fillna(0).astype(int).astype(str).str.zfill(3))

        # Agrega por Codigo + Loja somando métricas (venda, estoque, pendente)
        group_cols = ['Codigo', 'Loja']
        agg_dict = {}
        for m in ['Venda1Sem', 'Venda2Sem', 'Venda30d', 'Estoque', 'Pendente']:
            if m in df_hist.columns:
                agg_dict[m] = 'sum'
        df_hist = df_hist.groupby(group_cols, as_index=False).agg(agg_dict)

    # --- WMS ---
    if not df_wms.empty:
        df_wms.columns = [normalize_col(c) for c in df_wms.columns]
        col_qtd = next((c for c in df_wms.columns if 'qtd' in c or 'quant' in c), None)
        if col_qtd:
            df_wms.rename(columns={col_qtd: 'Qtd_CD', 'codigo': 'Codigo'}, inplace=True)
            if 'Codigo' in df_wms.columns:
                df_wms['Codigo'] = (pd.to_numeric(df_wms['Codigo'], errors='coerce')
                                   .fillna(0).astype(int).astype(str))
            df_wms['Qtd_CD'] = pd.to_numeric(df_wms['Qtd_CD'], errors='coerce').fillna(0)
            df_wms = df_wms.groupby('Codigo', as_index=False)['Qtd_CD'].sum()

    # --- OFERTAS (PROMOÇÕES) ---
    df_ofertas = pd.DataFrame()
    try:
        with engine.connect() as conn:
            q = text("SELECT codigo, data_inicio, data_final FROM ofertas")
            df_ofertas = pd.read_sql(q, conn)
        df_ofertas['data_inicio'] = pd.to_datetime(df_ofertas['data_inicio'])
        df_ofertas['data_final']  = pd.to_datetime(df_ofertas['data_final'])
    except Exception as e:
        st.warning(f"Erro ao carregar ofertas: {e}")

    return df_mix, df_hist, df_wms, df_ofertas

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

def calcular_sugestao_ponderada(v1, v2, v30, emb, boost_promo=False):
    """
    Calcula sugestão com base em média ponderada das vendas históricas.
    v1 = venda 1 semana, v2 = venda 2 semanas, v30 = média 30 dias.
    boost_promo = se True, aplica aumento (ex: +20%) na sugestão final.
    """
    # ponderação
    sugestao_unidades = v1 * 0.5 + v2 * 0.3 + (v30 / 4) * 0.2
    if boost_promo:
        sugestao_unidades *= 1.2  # +20% para promoção
    # converte para caixas
    caixas = sugestao_unidades / emb if emb > 0 else 0
    return max(0, int(round(caixas)))

def show_pedidos_page(engine, base_data_path):
    st.title("🛒 Digitação de Pedidos")
    if "pedido_atual" not in st.session_state:
        st.session_state.pedido_atual = []

    df_mix, df_hist, df_wms, df_ofertas = load_database(base_data_path, engine)
    if df_mix.empty:
        st.warning("Mix não carregado. Faça upload no Admin.")
        return

    # 1. Busca de produto
    c1, c2 = st.columns([1, 3])
    cod_input = c1.text_input("Código:", key="search_cod")
    desc_input = c2.text_input("Descrição:", key="search_desc")

    prod = None
    if cod_input:
        r = df_mix[df_mix['Codigo'] == str(cod_input)]
        if not r.empty:
            prod = r.iloc[0]
        else:
            st.warning("Código não encontrado.")
    elif desc_input:
        mask = df_mix['Produto'].astype(str).str.lower().str.contains(desc_input.lower(), na=False)
        r = df_mix[mask].head(50)
        if not r.empty:
            opts = {f"{row['Codigo']} - {row['Produto']}": row['Codigo'] for _, row in r.iterrows()}
            sel = st.selectbox("Selecione:", [""] + list(opts.keys()))
            if sel:
                prod = df_mix[df_mix['Codigo'] == opts[sel]].iloc[0]
        else:
            st.warning("Descrição não encontrada.")

    # 2. Detalhes e grade de pedido sugerido
    if prod is not None:
        codigo = prod['Codigo']
        nome = prod['Produto']
        emb_val = prod.get('Emb')
        try:
            emb = int(float(str(emb_val).replace(',', '.')))
        except:
            emb = 0
        if emb <= 0:
            st.error(f"⛔ Embalagem inválida ({emb_val}). Verifique o Mix.")
            return

        st.divider()
        st.markdown(f"**{codigo} - {nome}** (Emb: {emb})")

        qtd_cd = 0
        if not df_wms.empty:
            w = df_wms[df_wms['Codigo'] == codigo]
            if not w.empty:
                qtd_cd = w['Qtd_CD'].iloc[0]
        st.info(f"CD: {int(qtd_cd)} un | **{int(qtd_cd/emb) if emb>0 else 0} cx**")

        lojas_acesso = st.session_state.get('lojas_acesso', [])
        grade = []

        hist_sub = df_hist[df_hist['Codigo'] == str(codigo)].set_index('Loja') if not df_hist.empty else pd.DataFrame()

        # Obter lista de promoções para esse código
        ofertas_do_codigo = df_ofertas[df_ofertas['codigo'].astype(str) == str(codigo)]
        # Verifica se há uma promoção futura ou atual
        def tem_promo(loja=None):
            # Usamos apenas oferta por código; se quiser por loja, adaptar
            hoje = datetime.now()
            for _, row in ofertas_do_codigo.iterrows():
                if row['data_inicio'] <= hoje <= row['data_final']:
                    return True
            return False

        boost = tem_promo()

        for l in LISTA_LOJAS:
            if l not in lojas_acesso:
                continue
            est = pend = v1 = v2 = v30 = 0.0
            if l in hist_sub.index:
                r = hist_sub.loc[l]
                if isinstance(r, pd.DataFrame):
                    r = r.iloc[0]
                est = float(r.get('Estoque', 0) or 0)
                pend = float(r.get('Pendente', 0) or 0)
                v1 = float(r.get('Venda1Sem', 0) or 0)
                v2 = float(r.get('Venda2Sem', 0) or 0)
                v30 = float(r.get('Venda30d', 0) or 0)

            sugestao = calcular_sugestao_ponderada(v1, v2, v30, emb, boost_promo=boost)
            grade.append({
                "Loja": l,
                "Est": est,
                "Pend": pend,
                "Venda1Sem": v1,
                "Venda2Sem": v2,
                "Venda30d": v30,
                "Sugestão": sugestao,
                "PEDIDO": 0
            })

        dfg = pd.DataFrame(grade)
        ed = st.data_editor(
            dfg,
            hide_index=True,
            use_container_width=True,
            key=f"g_{codigo}",
            column_config={
                "Loja": st.column_config.TextColumn(disabled=True),
                "Est": st.column_config.NumberColumn(format="%.1f", disabled=True),
                "Pend": st.column_config.NumberColumn(format="%.1f", disabled=True),
                "Venda1Sem": st.column_config.NumberColumn(format="%.1f", disabled=True),
                "Venda2Sem": st.column_config.NumberColumn(format="%.1f", disabled=True),
                "Venda30d": st.column_config.NumberColumn(format="%.1f", disabled=True),
                "Sugestão": st.column_config.NumberColumn(format="%.0f", disabled=True),
                "PEDIDO": st.column_config.NumberColumn(min_value=0, step=1)
            }
        )

        tot = ed["PEDIDO"].sum()
        total_sug = dfg["Sugestão"].sum()
        st.markdown(f"**Sugestão total (ponderada): {int(total_sug)} caixas**")

        if st.button(f"Adicionar ({tot} cx)", type="primary", use_container_width=True):
            if tot > 0:
                item = {"Codigo": codigo, "Produto": nome, "Emb": emb, "Total": tot}
                for _, r in ed.iterrows():
                    item[r["Loja"]] = int(r["PEDIDO"])
                st.session_state.pedido_atual.append(item)
                st.success("Adicionado!")
            else:
                st.warning("Quantidade zerada.")

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
