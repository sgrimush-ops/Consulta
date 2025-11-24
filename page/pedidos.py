import streamlit as st
import pandas as pd
from datetime import datetime, date
import os
from sqlalchemy import text

# =========================================================
#  🧩 CONSTANTES E MAPEAMENTOS
# =========================================================

LISTA_LOJAS = ["001", "002", "003", "004", "005", "006",
               "007", "008", "011", "012", "013", "014", "017", "018"]

# Mapeamento para padronizar nomes das colunas (Chave = Nome no CSV/Parquet, Valor = Nome no Sistema)
# As chaves aqui devem ser minúsculas, pois vamos forçar o dataframe para minúsculo antes do map.

COLS_MIX_MAP = {
    'codigoint': 'Codigo', 
    'codigoean': 'EAN', 
    'descricao': 'Produto',
    'loja': 'Loja', 
    'embseparacao': 'embseparacao'
}

COLS_HIST_MAP = {
    'codigoint': 'Codigo', 
    'loja': 'Loja', 
    'dtsolicitacao': 'Data',
    'estcx': 'Estoque_G', 
    'pedcx': 'Pedido_H', 
    'vd1sem-cx': 'Venda_I',
    'vd2sem-cx': 'Venda_J', 
    'vm30dcx': 'Venda_K',
}

# CORREÇÃO AQUI: 'qtd' em minúsculo para bater com o CSV processado
COLS_WMS_MAP = {
    'codigo': 'Codigo', 
    'qtd': 'Qtd_CD', 
    'datasalva': 'Data_WMS'
}

# =========================================================
#  📥 CARREGAMENTO DE DADOS
# =========================================================

def load_parquet_data(base_path, filename_no_ext):
    """Carrega o arquivo .parquet se existir, senão retorna DataFrame vazio."""
    path = os.path.join(base_path, f"{filename_no_ext}.parquet")
    try:
        if os.path.exists(path):
            return pd.read_parquet(path)
    except Exception as e:
        st.error(f"Erro ao ler {filename_no_ext}: {e}")
    return pd.DataFrame()

def prepare_data(base_data_path):
    """Carrega e prepara as 3 bases principais (Mix, Histórico, WMS)."""
    
    # 1. Carregar
    df_mix = load_parquet_data(base_data_path, "__MixAtivoSistema")
    df_hist = load_parquet_data(base_data_path, "historico_solic")
    df_wms = load_parquet_data(base_data_path, "WMS")

    # 2. Padronizar e Renomear MIX
    if not df_mix.empty:
        df_mix.columns = df_mix.columns.str.strip().str.lower()
        df_mix.rename(columns=COLS_MIX_MAP, inplace=True)
        # Garante tipos
        if 'Codigo' in df_mix.columns:
            df_mix['Codigo'] = pd.to_numeric(df_mix['Codigo'], errors='coerce').fillna(0).astype(int).astype(str)
        if 'Loja' in df_mix.columns:
            df_mix['Loja'] = df_mix['Loja'].fillna(0).astype(int).astype(str).str.zfill(3)

    # 3. Padronizar e Renomear HISTÓRICO
    if not df_hist.empty:
        df_hist.columns = df_hist.columns.str.strip().str.lower()
        df_hist.rename(columns=COLS_HIST_MAP, inplace=True)
        if 'Codigo' in df_hist.columns:
            df_hist['Codigo'] = pd.to_numeric(df_hist['Codigo'], errors='coerce').fillna(0).astype(int).astype(str)
        if 'Loja' in df_hist.columns:
            df_hist['Loja'] = df_hist['Loja'].fillna(0).astype(int).astype(str).str.zfill(3)

    # 4. Padronizar e Renomear WMS
    if not df_wms.empty:
        df_wms.columns = df_wms.columns.str.strip().str.lower()
        # Renomeia 'qtd' para 'Qtd_CD'
        if 'qtd' not in df_wms.columns and 'Qtd' in df_wms.columns:
             df_wms.rename(columns={'Qtd': 'qtd'}, inplace=True) # Fallback manual se o lower falhar
             
        df_wms.rename(columns=COLS_WMS_MAP, inplace=True)
        
        if 'Codigo' in df_wms.columns:
            df_wms['Codigo'] = pd.to_numeric(df_wms['Codigo'], errors='coerce').fillna(0).astype(int).astype(str)
        
        # Agrupa WMS por código (soma estoque de todos os endereços/lotes)
        if 'Codigo' in df_wms.columns and 'Qtd_CD' in df_wms.columns:
            df_wms = df_wms.groupby('Codigo', as_index=False)['Qtd_CD'].sum()

    return df_mix, df_hist, df_wms

# =========================================================
#  💾 SALVAR NO BANCO
# =========================================================

def save_order_to_db(engine, pedido_dados):
    """Salva a lista de itens do pedido no banco de dados."""
    if not pedido_dados:
        return False

    username = st.session_state.get("username", "anon")
    now = datetime.now()

    # Prepara a query de inserção
    # Colunas dinâmicas para as lojas
    cols_lojas = ", ".join([f"loja_{loja}" for loja in LISTA_LOJAS])
    vals_lojas = ", ".join([f":loja_{loja}" for loja in LISTA_LOJAS])

    query = text(f"""
        INSERT INTO pedidos_consolidados (
            codigo, produto, ean, embseparacao, 
            data_pedido, usuario_pedido, status_item, 
            total_cx, {cols_lojas}
        ) VALUES (
            :codigo, :produto, :ean, :embseparacao, 
            :data_pedido, :usuario_pedido, :status_item, 
            :total_cx, {vals_lojas}
        )
    """)

    try:
        with engine.begin() as conn:
            for item in pedido_dados:
                # Prepara dicionário de parâmetros
                params = {
                    "codigo": item.get("Codigo"),
                    "produto": item.get("Produto"),
                    "ean": item.get("EAN"),
                    "embseparacao": int(item.get("embseparacao", 1)),
                    "data_pedido": now,
                    "usuario_pedido": username,
                    "status_item": "Ativo", # Pode vir da lógica de Mix
                    "total_cx": int(item.get("Total_CX", 0))
                }
                # Adiciona quantidade de cada loja
                for loja in LISTA_LOJAS:
                    params[f"loja_{loja}"] = int(item.get(loja, 0))
                
                conn.execute(query, params)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar pedido: {e}")
        return False

# =========================================================
#  🖥️ PÁGINA PRINCIPAL
# =========================================================

def show_pedidos_page(engine, base_data_path):
    st.title("🛒 Digitação de Pedidos")

    # --- 1. Inicialização ---
    if "pedido_atual" not in st.session_state:
        st.session_state.pedido_atual = []

    # --- 2. Carregamento ---
    with st.spinner("Carregando bases de dados..."):
        df_mix, df_hist, df_wms = prepare_data(base_data_path)

    if df_mix.empty:
        st.error("⚠️ Base de Mix não encontrada ou vazia. Faça o upload na área administrativa.")
        return

    # --- 3. Filtros e Busca ---
    st.subheader("1. Selecionar Produto")
    
    col1, col2 = st.columns([1, 3])
    with col1:
        busca_cod = st.text_input("Buscar por Código:")
    with col2:
        busca_desc = st.text_input("Buscar por Descrição:")

    produto_selecionado = None

    if busca_cod:
        # Filtra exato pelo código
        res = df_mix[df_mix['Codigo'] == busca_cod]
        if not res.empty:
            produto_selecionado = res.iloc[0]
    elif busca_desc:
        # Filtra pela descrição (contém)
        if 'Produto' in df_mix.columns:
            mask = df_mix['Produto'].astype(str).str.lower().str.contains(busca_desc.lower(), na=False)
            res = df_mix[mask].head(20) # Limita a 20 resultados
            
            if not res.empty:
                opcoes = {f"{row['Codigo']} - {row['Produto']}": row['Codigo'] for _, row in res.iterrows()}
                escolha = st.selectbox("Selecione o produto:", [""] + list(opcoes.keys()))
                
                if escolha:
                    cod_escolhido = opcoes[escolha]
                    produto_selecionado = df_mix[df_mix['Codigo'] == cod_escolhido].iloc[0]

    # --- 4. Exibição dos Dados do Produto ---
    if produto_selecionado is not None:
        cod_prod = produto_selecionado['Codigo']
        nome_prod = produto_selecionado.get('Produto', 'N/D')
        emb = float(produto_selecionado.get('embseparacao', 1))
        emb = int(emb) if emb > 0 else 1

        st.divider()
        st.markdown(f"### 📦 {cod_prod} - {nome_prod}")
        
        # Busca Estoque CD
        qtd_cd = 0
        if not df_wms.empty and 'Codigo' in df_wms.columns:
            wms_item = df_wms[df_wms['Codigo'] == cod_prod]
            if not wms_item.empty:
                qtd_cd = wms_item['Qtd_CD'].sum()
        
        # Cálculo de Caixas no CD
        cx_cd = qtd_cd / emb
        
        # Métricas
        m1, m2, m3 = st.columns(3)
        m1.metric("Embalagem", f"{emb}")
        m2.metric("Estoque CD (Un)", f"{qtd_cd:,.0f}")
        m3.metric("Estoque CD (Cx)", f"{cx_cd:,.1f}")

        # --- 5. Grade de Pedidos por Loja ---
        st.subheader("2. Definir Quantidades (Caixas)")
        
        # Prepara dados históricos para exibir na grade
        lojas_data = []
        
        # Apenas lojas que o usuário tem acesso
        lojas_permitidas = st.session_state.get('lojas_acesso', LISTA_LOJAS)
        
        for loja in LISTA_LOJAS:
            if loja not in lojas_permitidas:
                continue
                
            # Busca dados do histórico para esta loja e produto
            hist_item = pd.DataFrame()
            if not df_hist.empty:
                hist_item = df_hist[
                    (df_hist['Codigo'] == cod_prod) & 
                    (df_hist['Loja'] == loja)
                ]
            
            # Extrai métricas ou 0 se não tiver
            est_loja = hist_item['Estoque_G'].iloc[0] if not hist_item.empty else 0
            ped_pend = hist_item['Pedido_H'].iloc[0] if not hist_item.empty else 0
            venda_30d = hist_item['Venda_K'].iloc[0] if not hist_item.empty else 0
            sugestao = 0 # Poderia implementar lógica de sugestão aqui

            lojas_data.append({
                "Loja": loja,
                "Estoque (Cx)": est_loja,
                "Ped. Pend (Cx)": ped_pend,
                "Venda 30d (Cx)": venda_30d,
                "Sugestão": sugestao,
                "Pedido": 0  # Campo editável inicia zerado
            })
        
        if not lojas_data:
            st.warning("Você não tem acesso a nenhuma loja ou o mix não está cadastrado para suas lojas.")
        else:
            df_lojas = pd.DataFrame(lojas_data)
            
            # Configuração da tabela editável
            config_cols = {
                "Loja": st.column_config.TextColumn("Loja", disabled=True),
                "Estoque (Cx)": st.column_config.NumberColumn("Estoque", format="%.1f", disabled=True),
                "Ped. Pend (Cx)": st.column_config.NumberColumn("Pendente", format="%.1f", disabled=True),
                "Venda 30d (Cx)": st.column_config.NumberColumn("Venda 30d", format="%.1f", disabled=True),
                "Sugestão": st.column_config.NumberColumn("Sugestão", format="%.1f", disabled=True),
                "Pedido": st.column_config.NumberColumn("PEDIDO (CX)", min_value=0, step=1, required=True)
            }

            edited_df = st.data_editor(
                df_lojas, 
                column_config=config_cols, 
                use_container_width=True,
                hide_index=True,
                key=f"editor_{cod_prod}"
            )

            # Botão de Adicionar
            total_pedido = edited_df['Pedido'].sum()
            
            col_act1, col_act2 = st.columns([1, 3])
            with col_act1:
                st.metric("Total do Pedido (Cx)", f"{total_pedido}")
            
            with col_act2:
                st.write("") # Spacer
                if st.button("➕ Adicionar ao Carrinho", type="primary", use_container_width=True):
                    if total_pedido > 0:
                        # Cria objeto do item
                        item_pedido = {
                            "Codigo": cod_prod,
                            "Produto": nome_prod,
                            "EAN": produto_selecionado.get('EAN', ''),
                            "embseparacao": emb,
                            "Total_CX": total_pedido
                        }
                        # Adiciona qtd de cada loja
                        for _, row in edited_df.iterrows():
                            item_pedido[row['Loja']] = row['Pedido']
                        
                        # Adiciona as lojas que não estavam na lista com 0
                        for loja in LISTA_LOJAS:
                            if loja not in item_pedido:
                                item_pedido[loja] = 0

                        st.session_state.pedido_atual.append(item_pedido)
                        st.success(f"Adicionado: {nome_prod} ({total_pedido} cx)")
                        # st.rerun() # Opcional: recarregar para limpar campos
                    else:
                        st.warning("Digite uma quantidade maior que zero.")

    # --- 6. Carrinho e Finalização ---
    st.markdown("---")
    st.subheader(f"3. Carrinho ({len(st.session_state.pedido_atual)} itens)")

    if st.session_state.pedido_atual:
        df_carrinho = pd.DataFrame(st.session_state.pedido_atual)
        
        # Mostra colunas principais
        cols_view = ["Codigo", "Produto", "Total_CX"] + [l for l in LISTA_LOJAS if l in df_carrinho.columns and df_carrinho[l].sum() > 0]
        st.dataframe(df_carrinho[cols_view], hide_index=True, use_container_width=True)

        c_btn1, c_btn2 = st.columns(2)
        with c_btn1:
            if st.button("✅ Finalizar e Salvar Pedido", type="primary", use_container_width=True):
                with st.spinner("Salvando no banco de dados..."):
                    if save_order_to_db(engine, st.session_state.pedido_atual):
                        st.balloons()
                        st.success("Pedido salvo com sucesso!")
                        st.session_state.pedido_atual = [] # Limpa carrinho
                        st.rerun()
        
        with c_btn2:
            if st.button("🗑️ Limpar Carrinho", use_container_width=True):
                st.session_state.pedido_atual = []
                st.rerun()
