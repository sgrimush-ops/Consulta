import streamlit as st
import pandas as pd
from datetime import datetime
import os
from sqlalchemy import text
import numpy as np
import unicodedata

# === CONSTANTES ===
LISTA_LOJAS = ["001", "002", "003", "004", "005", "006",
               "007", "008", "011", "012", "013", "014", "017", "018"]

# === FUNÇÕES AUXILIARES ===

def normalize_col(col):
    """ Normaliza nome de coluna: remove acentos, mantém só alfanuméricos, lowercase. """
    if not isinstance(col, str):
        return str(col)
    n = unicodedata.normalize('NFKD', col).encode('ASCII', 'ignore').decode('utf-8')
    return ''.join(e for e in n if e.isalnum()).lower()

@st.cache_data(persist="disk")
def load_database(base_path):
    """Carrega dados de Mix, Histórico e WMS de arquivos Parquet de forma persistente."""
    def read_safe(name):
        p = os.path.join(base_path, f"{name}.parquet")
        if os.path.exists(p):
            return pd.read_parquet(p)
        return pd.DataFrame()

    df_mix = read_safe("__MixAtivoSistema")
    df_hist = read_safe("historico_solic")
    df_wms = read_safe("WMS")

    # --- Processa MIX ---
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
            df_mix['Codigo'] = (pd.to_numeric(df_mix['Codigo'], errors='coerce')
                                .fillna(0).astype(int).astype(str))
        df_mix = df_mix.drop_duplicates(subset=['Codigo'])

    # --- Processa HISTÓRICO ---
    if not df_hist.empty:
        df_hist.columns = [normalize_col(c) for c in df_hist.columns]
        rename = {}
        for c in df_hist.columns:
            if 'codigoint' in c:
                rename[c] = 'Codigo'
            elif 'loja' in c:
                rename[c] = 'Loja'
            elif 'est' in c:
                rename[c] = 'Estoque'
            elif 'ped' in c:
                rename[c] = 'Pendente'
            elif 'vd1sem' in c:
                rename[c] = 'Venda1Sem'
            elif 'vd2sem' in c:
                rename[c] = 'Venda2Sem'
            elif 'vm30' in c or 'venta30' in c:
                rename[c] = 'Venda30d'
        df_hist.rename(columns=rename, inplace=True)

        if 'Codigo' in df_hist.columns:
            df_hist['Codigo'] = (pd.to_numeric(df_hist['Codigo'], errors='coerce')
                                 .fillna(0).astype(int).astype(str))
        if 'Loja' in df_hist.columns:
            df_hist['Loja'] = (pd.to_numeric(df_hist['Loja'], errors='coerce')
                               .fillna(0).astype(int).astype(str).str.zfill(3))

        # Agrega somando valores para cada (Codigo, Loja)
        cols_to_sum = ['Estoque', 'Pendente', 'Venda1Sem', 'Venda2Sem', 'Venda30d']
        existing = [c for c in cols_to_sum if c in df_hist.columns]
        if 'Codigo' in df_hist.columns and 'Loja' in df_hist.columns and existing:
            df_hist = (df_hist
                       .groupby(['Codigo', 'Loja'], as_index=False)
                       .agg({c: "sum" for c in existing}))

    # --- Processa WMS ---
    if not df_wms.empty:
        df_wms.columns = [normalize_col(c) for c in df_wms.columns]
        col_qtd = next((c for c in df_wms.columns if 'qtd' in c or 'quant' in c), None)
        if col_qtd:
            df_wms.rename(columns={col_qtd: 'Qtd_CD', 'codigo': 'Codigo'}, inplace=True)
            if 'Codigo' in df_wms.columns:
                df_wms['Codigo'] = (pd.to_numeric(df_wms['Codigo'], errors='coerce')
                                   .fillna(0).astype(int).astype(str))
            df_wms = df_wms.groupby('Codigo', as_index=False)['Qtd_CD'].sum()

    return df_mix, df_hist, df_wms

def calculate_smart_suggestion(v1, v2, v30, estoque, pendente, emb, dias_cobertura=7, is_promo=False):
    """Calcula sugestão inteligente de pedido baseada em histórico de vendas, estoque e possível promoção."""
    if emb <= 0:
        return 0

    # Converte média de 30 dias para base semanal
    venda_media_semanal = v30 / 4.0

    # Média ponderada: mais peso para vendas recentes
    venda_semanal_projetada = v1 * 0.5 + v2 * 0.3 + venda_media_semanal * 0.2
    venda_diaria = venda_semanal_projetada / 7.0

    if is_promo:
        venda_diaria *= 1.2

    necessidade = venda_diaria * dias_cobertura
    faltando = max(0, necessidade - (estoque + pendente))
    sugestao_cx = int(np.ceil(faltando / emb))
    return sugestao_cx

def save_order(engine, dados):
    """Salva os itens do pedido no banco."""
    if not dados:
        return False
    try:
        with engine.begin() as conn:
            cols = ", ".join([f"loja_{l}" for l in LISTA_LOJAS])
            vals = ", ".join([f":{l}" for l in LISTA_LOJAS])
            q = text(f"""INSERT INTO pedidos_consolidados 
                        (codigo, produto, embseparacao, data_pedido, usuario_pedido, status_item, total_cx, {cols})
                        VALUES (:c, :p, :e, :d, :u, 'Ativo', :t, {vals})""")
            now = datetime.now()
            user = st.session_state.get("username", "anon")
            for item in dados:
                try:
                    emb = int(float(item.get("Emb", 0)))
                except Exception:
                    emb = 0
                try:
                    tot = int(float(item.get("Total", 0)))
                except Exception:
                    tot = 0

                params = {"c": str(item.get("Codigo")),
                          "p": str(item.get("Produto")),
                          "e": emb,
                          "d": now,
                          "u": user,
                          "t": tot}
                for l in LISTA_LOJAS:
                    try:
                        params[l] = int(float(item.get(l, 0)))
                    except:
                        params[l] = 0
                conn.execute(q, params)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar pedido: {e}")
        return False

def show_pedidos_page(engine, base_data_path):
    st.title("🛒 Digitação de Pedidos (Sugestão Inteligente)")

    # Carrega DataFrames do cache ou da session_state
    if "df_mix" in st.session_state:
        df_mix = st.session_state["df_mix"]
        df_hist = st.session_state["df_hist"]
        df_wms = st.session_state["df_wms"]
    else:
        df_mix, df_hist, df_wms = load_database(base_data_path)
        st.session_state["df_mix"] = df_mix
        st.session_state["df_hist"] = df_hist
        st.session_state["df_wms"] = df_wms

    if df_mix.empty:
        st.warning("Mix não encontrado. Faça upload via admin.")
        return

    if "pedido_atual" not in st.session_state:
        st.session_state["pedido_atual"] = []

    # 1. Busca de produto
    c1, c2, c3 = st.columns([1, 2, 1])
    cod_input = c1.text_input("Código:")
    desc_input = c2.text_input("Descrição:")
    dias_cob = c3.number_input("Dias de Estoque:", min_value=1, value=7)
    is_promo = st.checkbox("🔥 Considerar Promoção")

    prod = None
    if cod_input:
        df_find = df_mix[df_mix['Codigo'] == str(cod_input)]
        if not df_find.empty:
            prod = df_find.iloc[0]
        else:
            st.warning("Código não encontrado no Mix.")
    elif desc_input:
        mask = df_mix['Produto'].astype(str).str.lower().str.contains(desc_input.lower(), na=False)
        resultado = df_mix[mask].head(50)
        if not resultado.empty:
            opts = {f"{row['Codigo']} - {row['Produto']}": row['Codigo'] for _, row in resultado.iterrows()}
            sel = st.selectbox("Selecione:", [""] + list(opts.keys()))
            if sel:
                prod = df_mix[df_mix['Codigo'] == opts[sel]].iloc[0]
        else:
            st.warning("Nenhuma descrição correspondente encontrada.")

    # 2. Se produto selecionado, mostra grade com sugestão
    if prod is not None:
        codigo = prod['Codigo']
        nome = prod['Produto']
        emb_val = prod.get('Emb', 0)
        try:
            emb = int(float(str(emb_val).replace(",", ".")))
        except Exception as e:
            st.error(f"Erro convertendo embalagem: {e}")
            emb = 0

        if emb <= 0:
            st.error(f"Embalagem inválida para {codigo}: {emb_val}")
            return

        st.divider()
        st.markdown(f"**{codigo} — {nome}** (Emb: {emb} un/cx)")

        # Estoque CD
        qtd_cd = 0
        if not df_wms.empty:
            w = df_wms[df_wms['Codigo'] == codigo]
            if not w.empty:
                qtd_cd = int(w['Qtd_CD'].iloc[0])
        st.info(f"Estoque CD: {qtd_cd} un | {qtd_cd // emb if emb>0 else 0} cx")

        # Busca histórico por loja
        grade = []
        sub = pd.DataFrame()
        if not df_hist.empty:
            sub = df_hist[df_hist['Codigo'] == codigo].set_index('Loja')

        for loja in LISTA_LOJAS:
            if loja not in st.session_state.get('lojas_acesso', []):
                continue
            est = pend = v1 = v2 = v30 = 0.0
            if loja in sub.index:
                row = sub.loc[loja]
                if isinstance(row, pd.DataFrame):
                    row = row.iloc[0]
                est = float(row.get('Estoque', 0) or 0)
                pend = float(row.get('Pendente', 0) or 0)
                v1 = float(row.get('Venda1Sem', 0) or 0)
                v2 = float(row.get('Venda2Sem', 0) or 0)
                v30 = float(row.get('Venda30d', 0) or 0)

            sugest = calculate_smart_suggestion(v1, v2, v30, est, pend, emb, dias_cob, is_promo)
            grade.append({
                "Loja": loja,
                "Estoque": est,
                "Pendente": pend,
                "Venda1Sem": v1,
                "Venda2Sem": v2,
                "Sugestão": sugest,
                "PEDIDO": 0
            })

        if grade:
            df_grade = pd.DataFrame(grade)
            ed = st.data_editor(
                df_grade,
                hide_index=True,
                use_container_width=True,
                key=f"editor_{codigo}",
                column_config={
                    "Loja": st.column_config.TextColumn(disabled=True),
                    "Estoque": st.column_config.NumberColumn(disabled=True, format="%.0f"),
                    "Pendente": st.column_config.NumberColumn(disabled=True, format="%.0f"),
                    "Venda1Sem": st.column_config.NumberColumn(disabled=True, format="%.1f"),
                    "Venda2Sem": st.column_config.NumberColumn(disabled=True, format="%.1f"),
                    "Sugestão": st.column_config.NumberColumn(disabled=True, format="%d"),
                    "PEDIDO": st.column_config.NumberColumn(min_value=0, step=1)
                }
            )

            total_pedido = int(ed["PEDIDO"].sum())
            total_sug = int(df_grade["Sugestão"].sum())
            c_info, c_btn = st.columns([3, 1])
            c_info.info(f"Total Pedido: **{total_pedido}** cx  |  Sugestão Inteligente: **{total_sug}** cx")

            if c_btn.button("Adicionar ao Pedido", use_container_width=True):
                if total_pedido > 0:
                    item = {"Codigo": codigo, "Produto": nome, "Emb": emb, "Total": total_pedido}
                    for _, row in ed.iterrows():
                        item[row["Loja"]] = int(row["PEDIDO"])
                    st.session_state.pedido_atual.append(item)
                    st.success("Item adicionado!")
                else:
                    st.warning("Quantidade de pedido é zero.")

    # 3. Exibe carrinho (pedido atual)
    if st.session_state.pedido_atual:
        st.divider()
        st.write("### Carrinho de Pedidos")
        cart = pd.DataFrame(st.session_state.pedido_atual)
        st.dataframe(cart[["Codigo", "Produto", "Total"]], hide_index=True)

        c1, c2 = st.columns(2)
        if c1.button("✅ Salvar Pedido"):
            if save_order(engine, st.session_state.pedido_atual):
                st.balloons()
                st.session_state.pedido_atual = []
                st.rerun()
        if c2.button("🗑 Limpar Carrinho"):
            st.session_state.pedido_atual = []
            st.rerun()
