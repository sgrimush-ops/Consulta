import streamlit as st
import pandas as pd
from datetime import datetime
import os
from sqlalchemy import text
import unicodedata

# =========================================================
#  🧩 CONSTANTES E MAPEAMENTOS
# =========================================================

LISTA_LOJAS = ["001", "002", "003", "004", "005", "006",
               "007", "008", "011", "012", "013", "014", "017", "018"]

# Função para garantir que nomes de colunas batam (remove acentos/maiúsculas)
def normalize_col(col):
    n = unicodedata.normalize('NFKD', str(col)).encode('ASCII', 'ignore').decode('utf-8')
    return ''.join(e for e in n if e.isalnum()).lower()

# =========================================================
#  📥 CARREGAMENTO DE DADOS
# =========================================================

@st.cache_data(ttl=300)
def load_data_frames(base_path):
    """Carrega os dados convertidos (Parquet) de forma otimizada."""
    
    def read_file(name):
        p = os.path.join(base_path, f"{name}.parquet")
        if os.path.exists(p): return pd.read_parquet(p)
        return pd.DataFrame()

    df_mix = read_file("__MixAtivoSistema")
    df_hist = read_file("historico_solic")
    df_wms = read_file("WMS")

    # --- 1. PREPARA MIX ---
    if not df_mix.empty:
        df_mix.columns = [normalize_col(c) for c in df_mix.columns]
        # Mapeia colunas do arquivo original para o padrão do código
        rename_map = {}
        for c in df_mix.columns:
            if 'codigoint' in c: rename_map[c] = 'Codigo'
            elif 'codigoean' in c: rename_map[c] = 'EAN'
            elif 'descri' in c or 'produto' in c: rename_map[c] = 'Produto'
            elif 'emb' in c: rename_map[c] = 'embseparacao'
            elif 'loja' in c: rename_map[c] = 'Loja'
        df_mix.rename(columns=rename_map, inplace=True)
        
        # Garante tipos
        if 'Codigo' in df_mix.columns:
            df_mix['Codigo'] = pd.to_numeric(df_mix['Codigo'], errors='coerce').fillna(0).astype(int).astype(str)
        
        # Correção: Remove duplicatas de código no Mix para evitar erro na busca
        df_mix = df_mix.drop_duplicates(subset=['Codigo'])
        
        # Correção: Garante que embseparacao é número (troca vírgula por ponto)
        if 'embseparacao' in df_mix.columns:
             df_mix['embseparacao'] = df_mix['embseparacao'].astype(str).str.replace(',', '.', regex=False)
             df_mix['embseparacao'] = pd.to_numeric(df_mix['embseparacao'], errors='coerce')

    # --- 2. PREPARA HISTÓRICO ---
    if not df_hist.empty:
        df_hist.columns = [normalize_col(c) for c in df_hist.columns]
        rename_map = {}
        for c in df_hist.columns:
            if 'codigoint' in c: rename_map[c] = 'Codigo'
            elif 'loja' in c: rename_map[c] = 'Loja'
            elif 'est' in c: rename_map[c] = 'Estoque_G'
            elif 'ped' in c: rename_map[c] = 'Pedido_H'
            elif 'vd' in c and '30' in c: rename_map[c] = 'Venda_K'
        df_hist.rename(columns=rename_map, inplace=True)

        if 'Codigo' in df_hist.columns:
            df_hist['Codigo'] = pd.to_numeric(df_hist['Codigo'], errors='coerce').fillna(0).astype(int).astype(str)
        if 'Loja' in df_hist.columns:
            df_hist['Loja'] = pd.to_numeric(df_hist['Loja'], errors='coerce').fillna(0).astype(int).astype(str).str.zfill(3)

        # Correção Vital: Remove duplicatas de Loja+Produto para evitar o erro "Ambiguous truth value"
        if 'Codigo' in df_hist.columns and 'Loja' in df_hist.columns:
            df_hist = df_hist.groupby(['Codigo', 'Loja'], as_index=False).sum(numeric_only=True)

    # --- 3. PREPARA WMS ---
    if not df_wms.empty:
        df_wms.columns = [normalize_col(c) for c in df_wms.columns]
        # Procura coluna de quantidade (qtd ou Qtd)
        col_qtd = next((c for c in df_wms.columns if 'qtd' in c or 'quant' in c), None)
        
        if col_qtd:
            df_wms.rename(columns={col_qtd: 'Qtd_CD', 'codigo': 'Codigo'}, inplace=True)
            if 'Codigo' in df_wms.columns:
                df_wms['Codigo'] = pd.to_numeric(df_wms['Codigo'], errors='coerce').fillna(0).astype(int).astype(str)
                # Agrupa para somar estoque total do item no CD
                df_wms = df_wms.groupby('Codigo', as_index=False)['Qtd_CD'].sum()

    return df_mix, df_hist, df_wms

# =========================================================
#  💾 SALVAR NO BANCO
# =========================================================

def save_order_to_db(engine, pedido_dados):
    """Salva o pedido no banco com segurança de tipos."""
    if not pedido_dados: return False
    
    try:
        with engine.begin() as conn:
            cols = ", ".join([f"loja_{l}" for l in LISTA_LOJAS])
            params_cols = ", ".join([f":loja_{l}" for l in LISTA_LOJAS])
            
            query = text(f"""
                INSERT INTO pedidos_consolidados (
                    codigo, produto, ean, embseparacao, 
                    data_pedido, usuario_pedido, status_item, 
                    total_cx, {cols}
                ) VALUES (
                    :codigo, :produto, :ean, :embseparacao, 
                    :data_pedido, :usuario_pedido, :status_item, 
                    :total_cx, {params_cols}
                )
            """)
            
            now = datetime.now()
            user = st.session_state.get("username", "anon")
            
            for item in pedido_dados:
                # Conversão explícita para Python nativo (evita erro numpy.int64)
                try: emb = int(float(item.get("embseparacao", 0)))
                except: emb = 0
                
                try: tot = int(float(item.get("Total_CX", 0)))
                except: tot = 0

                params = {
                    "codigo": str(item.get("Codigo")),
                    "produto": str(item.get("Produto")),
                    "ean": str(item.get("EAN", "")),
                    "embseparacao": emb,
                    "data_pedido": now,
                    "usuario_pedido": user,
                    "status_item": "Ativo",
                    "total_cx": tot
                }
                
                for loja in LISTA_LOJAS:
                    try: val = int(float(item.get(loja, 0)))
                    except: val = 0
                    params[f"loja_{loja}"] = val
                
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

    # 1. Carregar dados
    with st.spinner("Carregando bases..."):
        df_mix, df_hist, df_wms = load_data_frames(base_data_path)

    if df_mix.empty:
        st.error("⚠️ Mix não encontrado. Faça o upload no Admin.")
        return

    # 2. Filtros (Código primeiro, como solicitado)
    st.subheader("1. Selecionar Produto")
    col1, col2 = st.columns([1, 3])
    busca_cod = col1.text_input("Buscar por Código:")
    busca_desc = col2.text_input("Buscar por Descrição:")

    prod_sel = None
    
    if busca_cod:
        res = df_mix[df_mix['Codigo'] == str(busca_cod)]
        if not res.empty: prod_sel = res.iloc[0]
    elif busca_desc:
        # Busca parcial insensível a maiúsculas
        if 'Produto' in df_mix.columns:
            mask = df_mix['Produto'].astype(str).str.lower().str.contains(busca_desc.lower(), na=False)
            res = df_mix[mask].head(20)
            if not res.empty:
                opts = {f"{r['Codigo']} - {r['Produto']}": r['Codigo'] for _, r in res.iterrows()}
                sel = st.selectbox("Selecione:", [""] + list(opts.keys()))
                if sel: 
                    cod = opts[sel]
                    prod_sel = df_mix[df_mix['Codigo'] == cod].iloc[0]

    # 3. Exibição e Grade
    if prod_sel is not None:
        cod = prod_sel['Codigo']
        nome = prod_sel.get('Produto', 'N/D')
        
        # Validação rigorosa da embalagem
        try:
            emb_raw = prod_sel.get('embseparacao')
            if pd.isna(emb_raw): emb = 0
            else: emb = int(float(emb_raw))
        except: emb = 0

        if emb <= 0:
            st.error(f"⛔ Embalagem inválida ({emb_raw}) para o produto {cod}. Verifique o cadastro.")
            return

        st.markdown("---")
        st.markdown(f"### 📦 {cod} - {nome}")
        
        # WMS
        qtd_cd = 0
        if not df_wms.empty:
            w = df_wms[df_wms['Codigo'] == cod]
            if not w.empty: qtd_cd = w['Qtd_CD'].iloc[0]
        
        # Métricas
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Embalagem", emb)
        col_m2.metric("Estoque CD (Un)", f"{int(qtd_cd):,}")
        col_m3.metric("Estoque CD (Cx)", f"{int(qtd_cd/emb):,}")

        st.subheader("2. Grade de Lojas")
        
        # Monta dados da grade
        lojas_acesso = st.session_state.get('lojas_acesso', LISTA_LOJAS)
        grade_data = []
        
        sub_hist = pd.DataFrame()
        if not df_hist.empty:
            # Usa set_index para busca rápida e segura
            sub_hist = df_hist[df_hist['Codigo'] == cod].set_index('Loja')

        for loja in LISTA_LOJAS:
            if loja not in lojas_acesso: continue
            
            est = pend = vend = 0.0
            if loja in sub_hist.index:
                # Acessa direto pelo índice (rápido)
                # Se houver duplicata no índice, sub_hist.loc[loja] retorna DataFrame
                # O drop_duplicates no load_data previne isso, mas aqui garantimos:
                row = sub_hist.loc[loja]
                if isinstance(row, pd.DataFrame): row = row.iloc[0] # Pega a primeira se duplicou
                
                est = float(row.get('Estoque_G', 0) or 0)
                pend = float(row.get('Pedido_H', 0) or 0)
                vend = float(row.get('Venda_K', 0) or 0)
            
            grade_data.append({
                "Loja": loja,
                "Estoque": est,
                "Pendente": pend,
                "Venda 30d": vend,
                "Sugestão": 0.0,
                "Pedido": 0 # Inteiro
            })

        if grade_data:
            df_grade = pd.DataFrame(grade_data)
            
            # Tabela Editável
            edited = st.data_editor(
                df_grade,
                column_config={
                    "Loja": st.column_config.TextColumn(disabled=True),
                    "Estoque": st.column_config.NumberColumn(disabled=True, format="%.1f"),
                    "Pendente": st.column_config.NumberColumn(disabled=True, format="%.1f"),
                    "Venda 30d": st.column_config.NumberColumn(disabled=True, format="%.1f"),
                    "Sugestão": st.column_config.NumberColumn(disabled=True, format="%.1f"),
                    "Pedido": st.column_config.NumberColumn("PEDIDO (CX)", min_value=0, step=1, required=True)
                },
                hide_index=True,
                use_container_width=True,
                key=f"editor_{cod}"
            )
            
            total_cx = edited["Pedido"].sum()
            
            c_tot, c_btn = st.columns([3, 1])
            c_tot.info(f"Total: **{total_cx}** caixas")
            
            if c_btn.button("➕ Adicionar Item", type="primary", use_container_width=True):
                if total_cx > 0:
                    item_dict = {
                        "Codigo": cod, "Produto": nome, 
                        "EAN": prod_sel.get('EAN', ''), "embseparacao": emb,
                        "Total_CX": total_cx
                    }
                    # Adiciona lojas
                    for _, r in edited.iterrows():
                        item_dict[r['Loja']] = r['Pedido']
                    
                    # Completa lojas faltantes com 0
                    for l in LISTA_LOJAS:
                        if l not in item_dict: item_dict[l] = 0
                        
                    st.session_state.pedido_atual.append(item_dict)
                    st.success("Item adicionado!")
                else:
                    st.warning("Quantidade zerada.")

    # 4. Pedido Atual (Carrinho)
    st.markdown("---")
    st.subheader("3. Pedido Atual")
    
    if st.session_state.pedido_atual:
        df_ped = pd.DataFrame(st.session_state.pedido_atual)
        # Mostra colunas relevantes
        cols_view = ["Codigo", "Produto", "Total_CX"] + [l for l in LISTA_LOJAS if l in df_ped.columns and df_ped[l].sum() > 0]
        st.dataframe(df_ped[cols_view], hide_index=True, use_container_width=True)
        
        bt1, bt2 = st.columns(2)
        if bt1.button("💾 Salvar Pedido", type="primary", use_container_width=True):
            if save_order_to_db(engine, st.session_state.pedido_atual):
                st.success("Pedido Salvo com Sucesso!")
                st.balloons()
                st.session_state.pedido_atual = []
                st.rerun()
        
        if bt2.button("🗑️ Limpar Lista", use_container_width=True):
            st.session_state.pedido_atual = []
            st.rerun()
    else:
        st.info("Nenhum item no carrinho.")
