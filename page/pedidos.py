import streamlit as st
import pandas as pd
from datetime import datetime, date
import os
from sqlalchemy import text
import numpy as np

# =========================================================
#  🧩 CONSTANTES E MAPEAMENTOS
# =========================================================

LISTA_LOJAS = ["001", "002", "003", "004", "005", "006",
               "007", "008", "011", "012", "013", "014", "017", "018"]

# Mapeamento (Chaves em minúsculo para garantir match)
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
        # Loga o erro no terminal para debug, mas não para a aplicação
        print(f"Erro ao ler {filename_no_ext}: {e}") 
    return pd.DataFrame()

def prepare_data(base_data_path):
    """Carrega e prepara as 3 bases principais."""
    
    df_mix = load_parquet_data(base_data_path, "__MixAtivoSistema")
    df_hist = load_parquet_data(base_data_path, "historico_solic")
    df_wms = load_parquet_data(base_data_path, "WMS")

    # --- Padronização MIX ---
    if not df_mix.empty:
        df_mix.columns = df_mix.columns.str.strip().str.lower()
        df_mix.rename(columns=COLS_MIX_MAP, inplace=True)
        
        # Conversão segura de tipos
        if 'Codigo' in df_mix.columns:
            df_mix['Codigo'] = pd.to_numeric(df_mix['Codigo'], errors='coerce').fillna(0).astype(int).astype(str)
        
        if 'Loja' in df_mix.columns:
            # Tenta converter loja para número e depois string com zero à esquerda (ex: '1' -> '001')
            df_mix['Loja'] = pd.to_numeric(df_mix['Loja'], errors='coerce').fillna(0).astype(int).astype(str).str.zfill(3)

        # --- CORREÇÃO CRÍTICA DA EMBALAGEM ---
        if 'embseparacao' in df_mix.columns:
            # 1. Garante que é string para poder substituir vírgula
            df_mix['embseparacao'] = df_mix['embseparacao'].astype(str)
            # 2. Substitui vírgula por ponto (ex: "12,5" vira "12.5")
            df_mix['embseparacao'] = df_mix['embseparacao'].str.replace(',', '.', regex=False)
            # 3. Converte para numérico. Erros viram NaN (não crasha)
            df_mix['embseparacao'] = pd.to_numeric(df_mix['embseparacao'], errors='coerce')
            # NÃO preenchemos com 1. Se for NaN, deve ser tratado como erro de cadastro.

    # --- Padronização HISTÓRICO ---
    if not df_hist.empty:
        df_hist.columns = df_hist.columns.str.strip().str.lower()
        df_hist.rename(columns=COLS_HIST_MAP, inplace=True)
        
        if 'Codigo' in df_hist.columns:
            df_hist['Codigo'] = pd.to_numeric(df_hist['Codigo'], errors='coerce').fillna(0).astype(int).astype(str)
        
        if 'Loja' in df_hist.columns:
            df_hist['Loja'] = pd.to_numeric(df_hist['Loja'], errors='coerce').fillna(0).astype(int).astype(str).str.zfill(3)

    # --- Padronização WMS ---
    if not df_wms.empty:
        df_wms.columns = df_wms.columns.str.strip().str.lower()
        # Fallback para Qtd maiúsculo se qtd minúsculo não existir
        if 'qtd' not in df_wms.columns and 'Qtd' in df_wms.columns:
             df_wms.rename(columns={'Qtd': 'qtd'}, inplace=True)
             
        df_wms.rename(columns=COLS_WMS_MAP, inplace=True)
        
        if 'Codigo' in df_wms.columns:
            df_wms['Codigo'] = pd.to_numeric(df_wms['Codigo'], errors='coerce').fillna(0).astype(int).astype(str)
        
        # Agrupa por código
        if 'Codigo' in df_wms.columns and 'Qtd_CD' in df_wms.columns:
            # Garante que Qtd_CD seja numérico antes de somar
            if df_wms['Qtd_CD'].dtype == object:
                df_wms['Qtd_CD'] = df_wms['Qtd_CD'].astype(str).str.replace(',', '.', regex=False)
            
            df_wms['Qtd_CD'] = pd.to_numeric(df_wms['Qtd_CD'], errors='coerce').fillna(0)
            df_wms = df_wms.groupby('Codigo', as_index=False)['Qtd_CD'].sum()

    return df_mix, df_hist, df_wms

# =========================================================
#  💾 SALVAR NO BANCO
# =========================================================

def save_order_to_db(engine, pedido_dados):
    if not pedido_dados:
        return False

    username = st.session_state.get("username", "anon")
    now = datetime.now()

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
                # Garante valores numéricos seguros
                emb_val = item.get("embseparacao")
                if not isinstance(emb_val, (int, float)):
                    emb_val = 0
                
                total_cx_val = item.get("Total_CX", 0)
                
                params = {
                    "codigo": item.get("Codigo"),
                    "produto": item.get("Produto"),
                    "ean": item.get("EAN"),
                    "embseparacao": int(float(emb_val)), 
                    "data_pedido": now,
                    "usuario_pedido": username,
                    "status_item": "Ativo",
                    "total_cx": int(float(total_cx_val))
                }
                for loja in LISTA_LOJAS:
                    val = item.get(loja, 0)
                    params[f"loja_{loja}"] = int(float(val)) if val else 0
                
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

    if "pedido_atual" not in st.session_state:
        st.session_state.pedido_atual = []

    with st.spinner("Carregando bases de dados..."):
        df_mix, df_hist, df_wms = prepare_data(base_data_path)

    if df_mix.empty:
        st.warning("⚠️ Base de Mix não encontrada. Faça o upload na área administrativa.")
    
    # ... Interface ...
    st.subheader("1. Selecionar Produto")
    
    col1, col2 = st.columns([1, 3])
    with col1:
        busca_cod = st.text_input("Buscar por Código:")
    with col2:
        busca_desc = st.text_input("Buscar por Descrição:")

    produto_selecionado = None

    if not df_mix.empty:
        if busca_cod:
            # Garante string para busca exata
            res = df_mix[df_mix['Codigo'] == str(busca_cod)]
            if not res.empty:
                produto_selecionado = res.iloc[0]
        elif busca_desc:
            if 'Produto' in df_mix.columns:
                # Busca parcial case insensitive
                mask = df_mix['Produto'].astype(str).str.lower().str.contains(busca_desc.lower(), na=False)
                res = df_mix[mask].head(20)
                
                if not res.empty:
                    opcoes = {f"{row['Codigo']} - {row['Produto']}": row['Codigo'] for _, row in res.iterrows()}
                    escolha = st.selectbox("Selecione o produto:", [""] + list(opcoes.keys()))
                    
                    if escolha:
                        cod_escolhido = opcoes[escolha]
                        produto_selecionado = df_mix[df_mix['Codigo'] == cod_escolhido].iloc[0]

    if produto_selecionado is not None:
        cod_prod = produto_selecionado['Codigo']
        nome_prod = produto_selecionado.get('Produto', 'N/D')
        
        # --- VALIDAÇÃO DA EMBALAGEM ---
        # Recupera o valor que foi processado no prepare_data
        emb_raw = produto_selecionado.get('embseparacao')
        
        # Se for NaN (não numérico no arquivo) ou <= 0, consideramos erro de cadastro
        if pd.isna(emb_raw) or emb_raw <= 0:
            emb = 0
            st.error(f"⛔ ERRO DE CADASTRO: A embalagem deste item não foi identificada no Mix Ativo.")
            st.caption("Verifique se a coluna 'embseparacao' no arquivo de Mix contém um número válido.")
        else:
            emb = int(emb_raw)

        st.divider()
        st.markdown(f"### 📦 {cod_prod} - {nome_prod}")
        
        # Busca Estoque CD
        qtd_cd = 0
        if not df_wms.empty and 'Codigo' in df_wms.columns:
            wms_item = df_wms[df_wms['Codigo'] == cod_prod]
            if not wms_item.empty:
                qtd_cd = wms_item['Qtd_CD'].sum()
        
        # Cálculo de Caixas no CD (Só calcula se emb > 0)
        cx_cd = (qtd_cd / emb) if emb > 0 else 0
        
        # Métricas
        m1, m2, m3 = st.columns(3)
        m1.metric("Embalagem", f"{emb}")
        m2.metric("Estoque CD (Un)", f"{qtd_cd:,.0f}")
        m3.metric("Estoque CD (Cx)", f"{cx_cd:,.1f}")

        # Se a embalagem for inválida (0), impede a digitação para evitar erros
        if emb <= 0:
            st.warning("Não é possível digitar pedidos para itens sem embalagem definida.")
        else:
            st.subheader("2. Definir Quantidades (Caixas)")
            
            lojas_data = []
            lojas_permitidas = st.session_state.get('lojas_acesso', LISTA_LOJAS)
            
            for loja in LISTA_LOJAS:
                if loja not in lojas_permitidas:
                    continue
                    
                # Busca histórico
                est_loja = 0
                ped_pend = 0
                venda_30d = 0
                
                if not df_hist.empty:
                    hist_item = df_hist[
                        (df_hist['Codigo'] == cod_prod) & 
                        (df_hist['Loja'] == str(loja).zfill(3))
                    ]
                    if not hist_item.empty:
                        try:
                            est_loja = float(hist_item['Estoque_G'].iloc[0])
                            ped_pend = float(hist_item['Pedido_H'].iloc[0])
                            venda_30d = float(hist_item['Venda_K'].iloc[0])
                        except:
                            pass

                lojas_data.append({
                    "Loja": loja,
                    "Estoque (Cx)": est_loja,
                    "Ped. Pend (Cx)": ped_pend,
                    "Venda 30d (Cx)": venda_30d,
                    "Sugestão": 0,
                    "Pedido": 0
                })
            
            if not lojas_data:
                st.warning("Sem acesso a lojas.")
            else:
                df_lojas = pd.DataFrame(lojas_data)
                
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

                total_pedido = edited_df['Pedido'].sum()
                
                c1, c2 = st.columns([1, 3])
                c1.metric("Total Pedido (Cx)", f"{total_pedido}")
                
                with c2:
                    st.write("")
                    if st.button("➕ Adicionar ao Carrinho", type="primary", use_container_width=True):
                        if total_pedido > 0:
                            item_pedido = {
                                "Codigo": cod_prod,
                                "Produto": nome_prod,
                                "EAN": produto_selecionado.get('EAN', ''),
                                "embseparacao": emb,
                                "Total_CX": total_pedido
                            }
                            for _, row in edited_df.iterrows():
                                item_pedido[row['Loja']] = row['Pedido']
                            
                            for l in LISTA_LOJAS:
                                if l not in item_pedido: item_pedido[l] = 0

                            st.session_state.pedido_atual.append(item_pedido)
                            st.success(f"Adicionado: {nome_prod}")
                        else:
                            st.warning("Quantidade deve ser maior que zero.")

    st.markdown("---")
    st.subheader(f"3. Carrinho ({len(st.session_state.pedido_atual)} itens)")

    if st.session_state.pedido_atual:
        df_car = pd.DataFrame(st.session_state.pedido_atual)
        cols_v = ["Codigo", "Produto", "Total_CX"] + [l for l in LISTA_LOJAS if l in df_car.columns and df_car[l].sum() > 0]
        st.dataframe(df_car[cols_v], hide_index=True, use_container_width=True)

        b1, b2 = st.columns(2)
        if b1.button("✅ Finalizar Pedido", type="primary", use_container_width=True):
            with st.spinner("Salvando..."):
                if save_order_to_db(engine, st.session_state.pedido_atual):
                    st.balloons()
                    st.success("Sucesso!")
                    st.session_state.pedido_atual = []
                    st.rerun()
        
        if b2.button("🗑️ Limpar", use_container_width=True):
            st.session_state.pedido_atual = []
            st.rerun()
