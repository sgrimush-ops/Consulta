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
        
        # Mapeamento flexível
        rename_map = {}
        for col in df_mix.columns:
            if 'codigo' in col and 'ean' not in col: rename_map[col] = 'Codigo'
            elif 'descri' in col or 'produto' in col: rename_map[col] = 'Produto'
            elif 'emb' in col or 'separacao' in col: rename_map[col] = 'Emb'
            elif 'ean' in col: rename_map[col] = 'EAN'
        
        df_mix.rename(columns=rename_map, inplace=True)
        
        # Tratamento da Embalagem (Vital)
        if 'Emb' in df_mix.columns:
            df_mix['Emb'] = df_mix['Emb'].astype(str).str.replace(',', '.', regex=False)
            df_mix['Emb'] = pd.to_numeric(df_mix['Emb'], errors='coerce')
        
        if 'Codigo' in df_mix.columns:
            df_mix['Codigo'] = pd.to_numeric(df_mix['Codigo'], errors='coerce').fillna(0).astype(int).astype(str)

    # --- Padronização Histórico ---
    if not df_hist.empty:
        df_hist.columns = df_hist.columns.str.strip().str.lower()
        rename_map = {}
        for col in df_hist.columns:
            if 'codigo' in col: rename_map[col] = 'Codigo'
            elif 'loja' in col: rename_map[col] = 'Loja'
            elif 'est' in col: rename_map[col] = 'Estoque'
            elif 'ped' in col: rename_map[col] = 'Pendente'
            elif 'vd' in col and '30' in col: rename_map[col] = 'Venda30d'
        
        df_hist.rename(columns=rename_map, inplace=True)
        
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
#  💾 SALVAR NO BANCO
# =========================================================

def save_order(engine, dados):
    if not dados: return False
    try:
        with engine.begin() as conn:
            cols = ", ".join([f"loja_{l}" for l in LISTA_LOJAS])
            vals = ", ".join([f":{l}" for l in LISTA_LOJAS])
            q = text(f"""
                INSERT INTO pedidos_consolidados 
                (codigo, produto, embseparacao, data_pedido, usuario_pedido, status_item, total_cx, {cols}) 
                VALUES (:c, :p, :e, :d, :u, 'Ativo', :t, {vals})
            """)
            
            now = datetime.now()
            user = st.session_state.get("username", "anon")
            
            for item in dados:
                # Conversão ULTRA SEGURA para int nativo
                try:
                    emb_val = int(float(item.get("Emb", 0) or 0))
                    total_val = int(float(item.get("Total", 0) or 0))
                except:
                    emb_val = 1
                    total_val = 0

                p = {
                    "c": str(item.get("Codigo", "")), 
                    "p": str(item.get("Produto", "")), 
                    "e": emb_val,
                    "d": now, 
                    "u": user, 
                    "t": total_val
                }
                
                for l in LISTA_LOJAS: 
                    try:
                        val = item.get(l, 0)
                        p[l] = int(float(val))
                    except:
                        p[l] = 0
                
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

    # Inicialização segura do carrinho
    if "pedido_atual" not in st.session_state:
        st.session_state.pedido_atual = []

    # Carrega dados
    df_mix, df_hist, df_wms = load_database(base_data_path)

    if df_mix.empty:
        st.warning("⚠️ Base de Mix não encontrada. Faça o upload na área administrativa.")
        return

    # --- 1. Busca (Código Primeiro) ---
    st.subheader("1. Selecionar Produto")
    
    col1, col2 = st.columns([1, 3])
    with col1:
        busca_cod = st.text_input("Buscar por Código:", key="input_cod_ped")
    with col2:
        busca_desc = st.text_input("Buscar por Descrição:", key="input_desc_ped")

    produto_selecionado = None

    if busca_cod:
        # Garante string para busca exata
        res = df_mix[df_mix['Codigo'] == str(busca_cod)]
        if not res.empty:
            produto_selecionado = res.iloc[0]
        else:
            st.warning(f"Código {busca_cod} não encontrado no Mix.")
            
    elif busca_desc:
        # Busca parcial
        if 'Produto' in df_mix.columns:
            mask = df_mix['Produto'].astype(str).str.lower().str.contains(busca_desc.lower(), na=False)
            res = df_mix[mask].head(20)
            
            if not res.empty:
                opcoes = {f"{row['Codigo']} - {row['Produto']}": row['Codigo'] for _, row in res.iterrows()}
                escolha = st.selectbox("Selecione o produto:", [""] + list(opcoes.keys()))
                
                if escolha:
                    cod_escolhido = opcoes[escolha]
                    produto_selecionado = df_mix[df_mix['Codigo'] == cod_escolhido].iloc[0]
            else:
                st.warning("Nenhum produto encontrado.")

    # --- 2. Detalhes e Grade ---
    if produto_selecionado is not None:
        codigo = produto_selecionado['Codigo']
        nome = produto_selecionado.get('Produto', 'Nome Indisponível')
        
        # Validação da Embalagem
        emb_raw = produto_selecionado.get('Emb')
        
        # Se for inválido, para aqui
        if pd.isna(emb_raw) or emb_raw <= 0:
            st.error(f"⛔ ERRO DE CADASTRO: O produto **{codigo}** está com a embalagem inválida ou zerada no Mix.")
            st.info("Corrija o arquivo de Mix e faça o upload novamente.")
            return 
        
        emb = int(emb_raw)

        st.divider()
        st.markdown(f"### 📦 {codigo} - {nome}")
        
        # Estoque CD
        qtd_cd = 0
        if not df_wms.empty:
            w_item = df_wms[df_wms['Codigo'] == codigo]
            if not w_item.empty:
                qtd_cd = w_item['Qtd_CD'].iloc[0]
        
        cx_cd = int(qtd_cd / emb)
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Embalagem", f"{emb}")
        m2.metric("Estoque CD (Un)", f"{int(qtd_cd):,}")
        m3.metric("Estoque CD (Cx)", f"{cx_cd:,}")

        # Tabela de Lojas
        lojas_permitidas = st.session_state.get('lojas_acesso', LISTA_LOJAS)
        dados_grade = []
        
        # Otimização: Filtra histórico uma vez
        hist_produto = pd.DataFrame()
        if not df_hist.empty:
            hist_produto = df_hist[df_hist['Codigo'] == codigo].set_index('Loja')

        for loja in LISTA_LOJAS:
            if loja not in lojas_permitidas:
                continue
                
            est = pend = venda = 0
            if loja in hist_produto.index:
                row = hist_produto.loc[loja]
                est = row.get('Estoque', 0)
                pend = row.get('Pendente', 0)
                venda = row.get('Venda30d', 0)

            # Proteção contra NaN
            if pd.isna(est): est = 0
            if pd.isna(pend): pend = 0
            if pd.isna(venda): venda = 0

            dados_grade.append({
                "Loja": loja,
                "Estoque (Cx)": float(est),
                "Pend (Cx)": float(pend),
                "Venda 30d (Cx)": float(venda),
                "PEDIDO": 0 
            })
        
        if not dados_grade:
            st.warning("Você não tem lojas vinculadas.")
        else:
            df_grade = pd.DataFrame(dados_grade)
            
            edited_df = st.data_editor(
                df_grade, 
                column_config={
                    "Loja": st.column_config.TextColumn(disabled=True),
                    "Estoque (Cx)": st.column_config.NumberColumn(disabled=True, format="%.1f"),
                    "Pend (Cx)": st.column_config.NumberColumn(disabled=True, format="%.1f"),
                    "Venda 30d (Cx)": st.column_config.NumberColumn(disabled=True, format="%.1f"),
                    "PEDIDO": st.column_config.NumberColumn("PEDIDO (CX)", min_value=0, step=1, required=True)
                },
                hide_index=True, 
                use_container_width=True, 
                key=f"grid_{codigo}" # Chave única para não misturar produtos
            )
            
            total_pedido = edited_df['PEDIDO'].sum()
            
            c1, c2 = st.columns([2, 1])
            with c1:
                st.info(f"Total do Pedido: **{total_pedido} caixas**")
            
            with c2:
                # Botão Adicionar
                if st.button("➕ Adicionar ao Carrinho", type="primary", use_container_width=True):
                    if total_pedido > 0:
                        item_pedido = {
                            "Codigo": codigo, 
                            "Produto": nome, 
                            "Emb": emb, 
                            "Total": total_pedido
                        }
                        # Adiciona quantidades
                        for _, row in edited_df.iterrows(): 
                            item_pedido[row['Loja']] = row['PEDIDO']
                        
                        # Adiciona ao carrinho
                        st.session_state.pedido_atual.append(item_pedido)
                        st.success(f"**{nome}** adicionado com sucesso!")
                        
                    else:
                        st.warning("A quantidade total deve ser maior que zero.")

    # --- 3. Carrinho ---
    if st.session_state.pedido_atual:
        st.divider()
        st.subheader(f"3. Carrinho ({len(st.session_state.pedido_atual)} itens)")
        
        df_car = pd.DataFrame(st.session_state.pedido_atual)
        st.dataframe(
            df_car[["Codigo", "Produto", "Total"]], 
            hide_index=True, 
            use_container_width=True,
            column_config={"Total": st.column_config.NumberColumn("Total (Cx)", format="%d")}
        )
        
        b1, b2 = st.columns(2)
        if b1.button("✅ Finalizar Pedido", type="primary", use_container_width=True):
            with st.spinner("Salvando no banco de dados..."):
                if save_order(engine, st.session_state.pedido_atual):
                    st.balloons()
                    st.success("Pedido enviado com sucesso!")
                    st.session_state.pedido_atual = []
                    st.rerun()
        
        if b2.button("🗑️ Limpar Carrinho", use_container_width=True):
            st.session_state.pedido_atual = []
            st.rerun()
