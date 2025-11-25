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

def format_br(val):
    """Formata número para padrão BR: 1.234,5"""
    try:
        v = float(val)
        if v == 0: return "0,0"
        s = f"{v:,.1f}"
        return s.replace(',', 'X').replace('.', ',').replace('X', '.')
    except:
        return "0,0"

def clean_float(val):
    """Converte string com ponto ou vírgula para float de forma segura."""
    if pd.isna(val) or val == '': return 0.0
    if isinstance(val, (int, float)): return float(val)
    # Remove espaços
    val = str(val).strip()
    # Se tiver vírgula e não tiver ponto, assume decimal BR e troca
    # Se tiver ponto, assume decimal US
    if ',' in val and '.' not in val:
        val = val.replace(',', '.')
    return float(val)

@st.cache_data(ttl=300)
def load_database(base_path, _engine):
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

    # --- HISTÓRICO (LÓGICA DE DATA MAIS RECENTE) ---
    if not df_hist.empty:
        df_hist.columns = [normalize_col(c) for c in df_hist.columns]
        rename = {}
        for c in df_hist.columns:
            if 'codigoint' in c: rename[c] = 'Codigo'
            elif 'loja' in c: rename[c] = 'Loja'
            elif 'est' in c: rename[c] = 'Estoque_CX'
            elif 'ped' in c: rename[c] = 'Pendente_CX'
            elif 'vd' in c and '1' in c: rename[c] = 'Venda1Sem_CX' 
            elif 'vd' in c and '2' in c: rename[c] = 'Venda2Sem_CX' 
            elif 'vm' in c and '30' in c: rename[c] = 'Venda30d_CX'
            # Mapeia a data da solicitação para podermos ordenar
            elif 'data' in c or 'solic' in c: rename[c] = 'Data_Solic'
        df_hist.rename(columns=rename, inplace=True)
        
        # Normalização de Tipos Chave
        if 'Codigo' in df_hist.columns:
            df_hist['Codigo'] = pd.to_numeric(df_hist['Codigo'], errors='coerce').fillna(0).astype(int).astype(str)
        if 'Loja' in df_hist.columns:
            df_hist['Loja'] = pd.to_numeric(df_hist['Loja'], errors='coerce').fillna(0).astype(int).astype(str).str.zfill(3)
        
        # Limpeza numérica das colunas de dados (garante float)
        cols_num = ['Estoque_CX', 'Pendente_CX', 'Venda1Sem_CX', 'Venda2Sem_CX', 'Venda30d_CX']
        for col in cols_num:
            if col in df_hist.columns:
                df_hist[col] = df_hist[col].apply(clean_float)

        # --- FILTRO: MANTER APENAS O REGISTRO MAIS RECENTE ---
        if 'Data_Solic' in df_hist.columns:
            # Tenta converter data. dayfirst=True ajuda com datas BR (DD/MM/AAAA)
            df_hist['Data_Solic'] = pd.to_datetime(df_hist['Data_Solic'], dayfirst=True, errors='coerce')
            
            # Ordena: Código ASC, Loja ASC, Data DESC (mais recente primeiro)
            df_hist = df_hist.sort_values(by=['Codigo', 'Loja', 'Data_Solic'], ascending=[True, True, False])
            
        # Remove duplicatas de (Codigo, Loja), mantendo a PRIMEIRA (que é a mais recente devido à ordenação)
        # Se não tiver coluna de data, assume que a ordem do arquivo traz os mais recentes por último/primeiro
        if 'Codigo' in df_hist.columns and 'Loja' in df_hist.columns:
            df_hist = df_hist.drop_duplicates(subset=['Codigo', 'Loja'], keep='first')

    # --- WMS ---
    if not df_wms.empty:
        df_wms.columns = [normalize_col(c) for c in df_wms.columns]
        col_qtd = next((c for c in df_wms.columns if 'qtd' in c or 'quant' in c), None)
        
        if col_qtd:
            df_wms.rename(columns={col_qtd: 'Qtd_CD', 'codigo': 'Codigo'}, inplace=True)
            if 'Codigo' in df_wms.columns:
                df_wms['Codigo'] = pd.to_numeric(df_wms['Codigo'], errors='coerce').fillna(0).astype(int).astype(str)
            
            if 'Qtd_CD' in df_wms.columns:
                 df_wms['Qtd_CD'] = df_wms['Qtd_CD'].apply(clean_float)

            # Soma estoque total do CD (vários endereços)
            df_wms = df_wms.groupby('Codigo', as_index=False)['Qtd_CD'].sum()

    # --- OFERTAS ---
    df_ofertas = pd.DataFrame()
    try:
        with _engine.connect() as conn:
            q = text("SELECT codigo, oferta, data_inicio, data_final FROM ofertas WHERE data_final >= CURRENT_DATE")
            df_ofertas = pd.read_sql(q, conn)
            if not df_ofertas.empty:
                df_ofertas['codigo'] = pd.to_numeric(df_ofertas['codigo'], errors='coerce').fillna(0).astype(int).astype(str)
                df_ofertas['data_inicio'] = pd.to_datetime(df_ofertas['data_inicio']).dt.date
                df_ofertas['data_final'] = pd.to_datetime(df_ofertas['data_final']).dt.date
    except: pass

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

# =========================================================
#  🖥️ PÁGINA PRINCIPAL
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

    # 2. Filtros
    st.subheader("1. Selecionar Produto")
    c1, c2 = st.columns([1, 3])
    cod_input = c1.text_input("Código:")
    desc_input = c2.text_input("Descrição:")

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
            if sel: 
                cod = opts[sel]
                prod = df_mix[df_mix['Codigo'] == cod].iloc[0]

    # 3. Detalhes
    if prod is not None:
        codigo = prod['Codigo']
        nome = prod['Produto']
        
        try:
            emb_raw = prod.get('Emb')
            if pd.isna(emb_raw): emb = 0
            else: emb = int(float(str(emb_raw).replace(',', '.')))
        except: emb = 0

        if emb <= 0:
            st.error(f"⛔ Embalagem inválida ({emb_raw}). Verifique o Mix.")
            return

        st.divider()
        st.markdown(f"**{codigo} - {nome}** (Emb: {emb})")

        # --- INFO DE PROMOÇÃO ---
        if not df_ofertas.empty:
            promo = df_ofertas[df_ofertas['codigo'] == str(codigo)]
            if not promo.empty:
                promo = promo[promo['data_final'] >= datetime.now().date()]
                if not promo.empty:
                    promo_item = promo.sort_values('data_inicio').iloc[0]
                    inicio = promo_item['data_inicio'].strftime('%d/%m')
                    fim = promo_item['data_final'].strftime('%d/%m')
                    valor = float(promo_item['oferta'])
                    st.info(f"🔥 **EM OFERTA!** De {inicio} até {fim} por **R$ {valor:.2f}**")
        
        # WMS (Estoque CD)
        qtd_cd_un = 0.0
        if not df_wms.empty:
            w = df_wms[df_wms['Codigo'] == str(codigo)]
            if not w.empty: 
                qtd_cd_un = w['Qtd_CD'].iloc[0]
        
        cx_cd = int(qtd_cd_un / emb) if emb > 0 else 0
        st.info(f"CD: {int(qtd_cd_un):,} un | **{format_br(cx_cd).split(',')[0]} cx**")

        # Grade Lojas
        lojas_acesso = st.session_state.get('lojas_acesso', [])
        grade = []
        
        sub = pd.DataFrame()
        if not df_hist.empty: 
            sub = df_hist[df_hist['Codigo'] == str(codigo)].set_index('Loja')

        for l in LISTA_LOJAS:
            if l not in lojas_acesso: continue
            
            est_cx = pend_cx = v1_cx = v2_cx = v30_cx = 0.0
            
            if l in sub.index:
                r = sub.loc[l]
                if isinstance(r, pd.DataFrame): r = r.iloc[0]
                
                try: est_cx = float(r.get('Estoque_CX', 0) or 0)
                except: est_cx = 0.0
                try: pend_cx = float(r.get('Pendente_CX', 0) or 0)
                except: pend_cx = 0.0
                try: v1_cx = float(r.get('Venda1Sem_CX', 0) or 0)
                except: v1_cx = 0.0
                try: v2_cx = float(r.get('Venda2Sem_CX', 0) or 0)
                except: v2_cx = 0.0
                try: v30_cx = float(r.get('Venda30d_CX', 0) or 0)
                except: v30_cx = 0.0
            
            grade.append({
                "Loja": l, 
                "Est": format_br(est_cx), 
                "Pend": format_br(pend_cx), 
                "Vd 1Sm": format_br(v1_cx), 
                "Vd 2Sm": format_br(v2_cx), 
                "Vd 30d": format_br(v30_cx),
                "PEDIDO": 0
            })

        if grade:
            dfg = pd.DataFrame(grade)
            
            ed = st.data_editor(
                dfg, 
                hide_index=True, use_container_width=True, key=f"g_{codigo}",
                column_config={
                    "Loja": st.column_config.TextColumn(disabled=True),
                    "Est": st.column_config.TextColumn("Est (Cx)", disabled=True),
                    "Pend": st.column_config.TextColumn("Pend (Cx)", disabled=True),
                    "Vd 1Sm": st.column_config.TextColumn("Vd 1Sem (Cx)", disabled=True),
                    "Vd 2Sm": st.column_config.TextColumn("Vd 2Sem (Cx)", disabled=True),
                    "Vd 30d": st.column_config.TextColumn("Vd 30d (Cx)", disabled=True),
                    "PEDIDO": st.column_config.NumberColumn("PEDIDO (CX)", min_value=0, step=1)
                }
            )
            
            tot = ed["PEDIDO"].sum()
            
            col_info, col_btn = st.columns([3, 1])
            col_info.info(f"Total Pedido: **{tot:,.0f}** cx")
            
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
        
        st.dataframe(
            cart[["Codigo", "Produto", "Total"]], 
            hide_index=True,
            column_config={
                "Total": st.column_config.NumberColumn("Total (Cx)", format="%d")
            }
        )
        
        c1, c2 = st.columns(2)
        if c1.button("✅ Finalizar"):
            if save_order(engine, st.session_state.pedido_atual):
                st.balloons()
                st.session_state.pedido_atual = []
                st.rerun()
        if c2.button("🗑️ Limpar"):
            st.session_state.pedido_atual = []
            st.rerun()