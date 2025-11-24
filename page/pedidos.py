import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date # MUDANÇA: Importado 'date'
import json
import re
import os
from sqlalchemy import create_engine, text
import numpy as np

# =========================================================
#  🧩 CONSTANTES E MAPEAMENTOS
# =========================================================
MIX_FILE_PATH = 'data/__MixAtivoSistema.xlsx'
HIST_FILE_PATH = 'data/historico_solic.xlsm'
WMS_FILE_PATH = 'data/WMS.xlsm'

LISTA_LOJAS = ["001", "002", "003", "004", "005", "006",
               "007", "008", "011", "012", "013", "014", "017", "018"]

COLS_MIX_MAP = {
    'codigoint': 'Codigo', 'codigoean': 'EAN', 'descricao': 'Produto',
    'loja': 'Loja', 'embseparacao': 'embseparacao'
}

COLS_HIST_MAP = {
    'codigoint': 'Codigo', 'loja': 'Loja', 'dtsolicitacao': 'data',
    'estcx': 'estoque_G', 'pedcx': 'Pedido_H', 'vd1sem-cx': 'Venda_I',
    'vd2sem-cx': 'Venda_J', 'vm30dcx': 'Venda_K',
}

COLS_WMS_MAP = {
    'codigo': 'Codigo', 'qtd': 'Qtd_CD', 'datasalva': 'Data'
}

# =========================================================
#  📂 FUNÇÕES DE LEITURA DE DADOS (COM CACHE)
# =========================================================
# MUDANÇA: Adicionado 'mod_time' para quebrar o cache em novo upload
@st.cache_data
def load_mix_data(file_path: str, mod_time: float):
    """Carrega dados do Mix de produtos."""
    try:
        df = pd.read_excel(file_path, dtype=str)
        df.rename(columns=COLS_MIX_MAP, inplace=True)
        df['Codigo'] = pd.to_numeric(df['Codigo'], errors='coerce').fillna(0).astype(int)
        df['embseparacao'] = pd.to_numeric(
            df['embseparacao'].astype(str).str.split(
                ',').str[0].str.split('.').str[0].str.strip(),
            errors='coerce'
        ).fillna(0).astype(int)
        df['Loja'] = df['Loja'].astype(str).str.zfill(3)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar Mix: {e}")
        return pd.DataFrame()

# MUDANÇA: Adicionado 'mod_time' para quebrar o cache em novo upload
@st.cache_data
def load_historico_data(file_path: str, mod_time: float):
    """MUDANÇA: Carrega dados do Histórico, incluindo colunas G a K."""
    try:
        use_cols = list(COLS_HIST_MAP.keys())
        df = pd.read_excel(file_path, sheet_name=0, usecols=use_cols)
        df.rename(columns=COLS_HIST_MAP, inplace=True)
        df['Codigo'] = pd.to_numeric(df['Codigo'], errors='coerce').fillna(0).astype(int)
        df['Loja'] = df['Loja'].astype(str).str.zfill(3)
        df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
        
        metric_cols = ['Estoque_G', 'Pedido_H', 'Venda_I', 'Venda_J', 'Venda_K']
        for col in metric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
        df.dropna(subset=['Data'], inplace=True)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar Histórico: {e}")
        return pd.DataFrame()

# MUDANÇA: Adicionado 'mod_time' para quebrar o cache em novo upload
@st.cache_data
def load_wms_data(file_path: str, mod_time: float):
    """MUDANÇA: Carrega dados do WMS e filtra pelo último dia de upload."""
    try:
        df = pd.read_excel(file_path, sheet_name='WMS', usecols=COLS_WMS_MAP.keys())
        df.rename(columns=COLS_WMS_MAP, inplace=True)
        
        df['Codigo'] = pd.to_numeric(df['Codigo'], errors='coerce').fillna(0).astype(int)
        df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
        df['Qtd_CD'] = pd.to_numeric(df['Qtd_CD'], errors='coerce').fillna(0)
        df.dropna(subset=['Data'], inplace=True)

        latest_date = df['Data'].max()
        df_latest = df[df['Data'] == latest_date]
        return df_latest
        
    except Exception as e:
        st.error(f"Erro ao carregar WMS: {e}")
        return pd.DataFrame(columns=['Codigo', 'Qtd_CD', 'Data'])

# MUDANÇA: Nova função para carregar ofertas ativas
@st.cache_data(ttl=300) # Cache de 5 minutos
def load_active_offers(_engine):
    """Busca ofertas do banco de dados que estão ativas hoje OU no futuro."""
    today = date.today()
    query = text("""
        SELECT codigo, oferta, data_inicio, data_final
        FROM ofertas
        WHERE data_final >= :today
    """) # MUDANÇA: Removido 'data_inicio' para pegar também ofertas futuras
    try:
        with _engine.connect() as conn:
            df = pd.read_sql(query, conn, params={"today": today})
        
        # Indexa por código para busca rápida. Remove duplicados se houver.
        if not df.empty:
            df = df.drop_duplicates(subset=['codigo'], keep='last').set_index('codigo')
        return df
    except Exception as e:
        st.error(f"Erro ao carregar ofertas: {e}")
        return pd.DataFrame()

# =========================================================
#  💾 SALVAR PEDIDO NO BANCO (Sem alterações)
# =========================================================
def save_order_to_db(engine, pedido_final: list[dict]):
    try:
        data_pedido = datetime.now()
        usuario = st.session_state.get('username', 'desconhecido')
        cols_lojas = ", ".join([f"loja_{l}" for l in LISTA_LOJAS])
        params_lojas = ", ".join([f":loja_{l}" for l in LISTA_LOJAS])

        query = text(f"""
            INSERT INTO pedidos_consolidados (
                codigo, produto, ean, embseparacao,
                data_pedido, data_aprovacao, usuario_pedido,
                status_item, {cols_lojas}, total_cx, status_aprovacao
            ) VALUES (
                :codigo, :produto, :ean, :embseparacao,
                :data_pedido, :data_aprovacao, :usuario_pedido,
                :status_item, {params_lojas}, :total_cx, :status_aprovacao
            )
        """)

        params_list = []
        for item in pedido_final:
            vals_lojas = {f"loja_{l}": item.get(
                f"loja_{l}", 0) for l in LISTA_LOJAS}
            emb_val = int(pd.to_numeric(
                item.get("embseparacao", 0), errors="coerce") or 0)
            
            params_list.append({
                "codigo": item["Codigo"], "produto": item["Produto"], "ean": item["EAN"],
                "embseparacao": emb_val, "data_pedido": data_pedido, "data_aprovacao": None,
                "usuario_pedido": usuario, "status_item": item["Status"],
                **vals_lojas, "total_cx": item["Total_CX"], "status_aprovacao": "Pendente"
            })

        with engine.begin() as conn:
            conn.execute(query, params_list)
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False

# =========================================================
#  📊 HISTÓRICO DE PEDIDOS (Sem alterações)
# =========================================================
def get_recent_orders_display(engine, username: str) -> pd.DataFrame:
    try:
        dt_lim = (datetime.now() - timedelta(days=3)
                  ).strftime('%Y-%m-%d 00:00:00')
        q = text("""
            SELECT codigo AS "Cód", produto AS "Produto",
                   embseparacao AS "Emb", total_cx AS "Total",
                   status_aprovacao AS "Status",
                   data_pedido AS "Data"
            FROM pedidos_consolidados
            WHERE usuario_pedido = :username
              AND data_pedido >= :dt_lim
            ORDER BY data_pedido DESC
        """)
        df = pd.read_sql_query(q, con=engine, params={
                               "username": username, "dt_lim": dt_lim})
        df["Emb"] = pd.to_numeric(
            df["Emb"], errors='coerce').fillna(0).astype(int)
        return df
    except Exception as e:
        st.error(f"Erro ao ler histórico: {e}")
        return pd.DataFrame()

# =========================================================
#  🧭 INTERFACE PRINCIPAL
# =========================================================
def show_pedidos_page(engine, base_data_path):
    st.title("🛒 Digitação de Pedidos")

    if 'pedido_atual' not in st.session_state:
        st.session_state.pedido_atual = []

    mix_file_path = os.path.join(base_data_path, "__MixAtivoSistema.xlsx")
    hist_file_path = os.path.join(base_data_path, "historico_solic.xlsm")
    wms_file_path = os.path.join(base_data_path, "WMS.xlsm")
    
    # MUDANÇA: Obter a data de modificação dos arquivos
    try:
        mix_mod_time = os.path.getmtime(mix_file_path)
        hist_mod_time = os.path.getmtime(hist_file_path)
        wms_mod_time = os.path.getmtime(wms_file_path)
    except FileNotFoundError:
        st.error("Arquivos de dados (Mix, WMS ou Histórico) não encontrados. Faça o upload na página 'Atualização de Dependências'.")
        return
    except Exception as e:
        st.error(f"Erro ao verificar arquivos de dados: {e}")
        return
    
    # Carrega todos os dados (funções cacheadas)
    # MUDANÇA: Passa os 'mod_time' para quebrar o cache
    df_mix = load_mix_data(mix_file_path, mix_mod_time)
    df_hist = load_historico_data(hist_file_path, hist_mod_time)
    df_wms = load_wms_data(wms_file_path, wms_mod_time) 
    df_ofertas = load_active_offers(engine) # MUDANÇA: Carrega ofertas ativas

    if df_mix.empty:
        st.warning("Falha ao carregar o Mix de Produtos.")
        st.stop()

    lojas_user = st.session_state.get('lojas_acesso', [])
    if not lojas_user:
        st.warning("Sem acesso a lojas.")
        st.stop()

    st.subheader("1. Buscar Produto")
    df_mix_user = df_mix[df_mix['Loja'].isin(lojas_user)].copy()

    # MUDANÇA: Ordem das abas alterada
    tab_cod, tab_prod, tab_ean = st.tabs(["Por Código", "Por Produto", "Por EAN"])
    prod_sel = None

    with tab_cod:
        # Lógica da "Por Código" (veio primeiro)
        busca_cod = st.text_input("Código:")
        if busca_cod:
            try:
                cod = int(busca_cod.strip())
                res = df_mix[df_mix['Codigo'] == cod]
                if not res.empty:
                    prod_sel = res.iloc[0]
                else:
                    st.warning("Código não encontrado.")
            except ValueError:
                st.warning("Código deve ser numérico.")

    with tab_prod:
        # Lógica da "Por Produto" (veio em segundo)
        busca_nome = st.text_input("Nome do Produto:")
        if busca_nome:
            res = df_mix_user[df_mix_user['Produto'].str.contains(
                busca_nome, case=False, na=False)]
            unicos = res.drop_duplicates(subset=['Codigo'])
            unicos['Show'] = unicos['Produto'] + \
                " (Cód: " + unicos['Codigo'].astype(str) + ")"
            sel = st.selectbox(
                "Selecione:", ["Selecione..."] + unicos['Show'].tolist())
            if sel != "Selecione...":
                cod_str = re.search(r'\(Cód: (\d+)\)', sel).group(1)
                cod = int(cod_str)
                prod_sel = df_mix[df_mix['Codigo'] == cod].iloc[0]

    with tab_ean:
        # Lógica da "Por EAN" (veio em terceiro)
        busca_ean = st.text_input("EAN:")
        if busca_ean:
            res = df_mix[df_mix['EAN'] == busca_ean.strip()]
            if not res.empty:
                prod_sel = res.iloc[0]
            else:
                st.warning("EAN não encontrado.")
    # FIM DA MUDANÇA DE ORDEM

    st.markdown("---")

    if prod_sel is not None:
        st.subheader("2. Distribuir Quantidades (Caixas)")
        
        cod = int(prod_sel['Codigo'])
        emb = int(prod_sel.get('embseparacao', 0))

        # Lógica do Estoque CD (barra azul)
        stock_cd_units = df_wms[df_wms['Codigo'] == cod]['Qtd_CD'].sum()
        stock_display = "Esta em falta"
        
        if emb > 0 and stock_cd_units > 0:
            stock_cd_cases = int(stock_cd_units // emb)
            if stock_cd_cases > 0:
                stock_display = f"{stock_cd_cases:,.0f} CX"
        
        # Barra de informação padrão
        st.info(f"**Item:** {prod_sel['Produto']} (Cód: {cod}) | **Emb:** {emb} un/cx | **Estoque CD:** {stock_display}")
        
        # MUDANÇA: Lógica para buscar e exibir a oferta (ativa OU futura)
        try:
            today = date.today() # Pega a data de hoje
            if not df_ofertas.empty and cod in df_ofertas.index:
                # .loc[cod] pega a linha onde o índice é o código do produto
                oferta_data = df_ofertas.loc[cod] 
                preco = f"R$ {oferta_data['oferta']:.2f}"
                inicio = oferta_data['data_inicio'] # Pega como objeto data
                fim = oferta_data['data_final']       # Pega como objeto data
                
                inicio_str = inicio.strftime('%d/%m')
                fim_str = fim.strftime('%d/%m/%Y')
                
                if today >= inicio:
                    # A oferta está ativa HOJE
                    st.success(f"🛍️ **OFERTA ATIVA:** Este item está em promoção por **{preco}** (Vigência: de {inicio_str} até {fim_str})")
                else:
                    # A oferta é FUTURA
                    st.warning(f"📣 **OFERTA FUTURA:** Este item entrará em promoção por **{preco}** (Vigência: de {inicio_str} até {fim_str})")
        except Exception as e:
            # Se der erro (ex: múltiplas ofertas, o que não deve acontecer), ignora
            pass 
        # FIM DA MUDANÇA DA OFERTA

        # Preparar dados históricos para o item
        if not df_hist.empty:
            latest_hist_date = df_hist['Data'].max()
            df_hist_item_raw = df_hist[ # MUDANÇA: Renomeado para 'raw'
                (df_hist['Codigo'] == cod) & 
                (df_hist['Data'] == latest_hist_date)
            ]
            
            # MUDANÇA: Remove duplicatas por 'Loja', mantendo a primeira ocorrência
            # Isso garante que o índice 'Loja' será único
            df_hist_item = df_hist_item_raw.drop_duplicates(subset=['Loja'], keep='first')
            
            # Agora .set_index('Loja') é seguro
            hist_item_map = df_hist_item.set_index('Loja').to_dict('index') 
            data_atualizacao = latest_hist_date.strftime('%d/%m/%Y')
        else:
            hist_item_map = {}
            data_atualizacao = "N/A"

        with st.form("form_qty"):
            qtys, total = {}, 0
            cols = st.columns(min(len(lojas_user), 3))
            
            for i, loja in enumerate(lojas_user):
                col_render = cols[i % len(cols)]
                
                sugestao_int = 0
                caption_text = f"Sem dados históricos (Atu: {data_atualizacao})"
                
                if loja in hist_item_map:
                    row = hist_item_map[loja]
                    est_g = row['Estoque_G']
                    ped_h = row['Pedido_H']
                    vd_i = row['Venda_I']
                    vd_j = row['Venda_J']
                    vm_k = row['Venda_K']
                    
                    sugestao_float = (vm_k / 7 * 4) - est_g
                    sugestao_int = int(np.round(sugestao_float)) 
                    
                    if sugestao_int < 1:
                        sugestao_int = 0 
                    
                    caption_text = (
                        f"Est: {est_g:.1f} | Ult.Ped: {ped_h:.0f} | "
                        f"Vd1: {vd_i:.1f} | Vd2: {vd_j:.1f} | VM30: {vm_k:.1f} | "
                        f"(Atu: {data_atualizacao})"
                    )

                q = col_render.number_input(
                    f"Loja {loja}", 
                    min_value=0, 
                    step=1, 
                    value=sugestao_int,
                    key=f"q_{cod}_{loja}"
                )
                
                col_render.caption(caption_text)
                
                if q > 0:
                    qtys[f"loja_{loja}"] = q
                    total += q

            if st.form_submit_button("Adicionar ao Pedido"):
                if total > 0:
                    st.session_state.pedido_atual.append({
                        "Codigo": str(cod), "Produto": prod_sel["Produto"],
                        "EAN": prod_sel["EAN"], "embseparacao": emb,
                        "Status": "Ativo", "Total_CX": total, **qtys
                    })
                    st.success("Item adicionado!")
                else:
                    st.warning("Digite ao menos uma quantidade.")

    st.markdown("---")
    st.subheader("3. Pedido Atual")
    if st.session_state.pedido_atual:
        df_ped = pd.DataFrame(st.session_state.pedido_atual)
        st.dataframe(df_ped, hide_index=True, use_container_width=True)
        c1, c2 = st.columns(2)
        if c1.button("Salvar Pedido", type="primary"):
            if save_order_to_db(engine, st.session_state.pedido_atual):
                st.success("Salvo com sucesso!")
                st.session_state.pedido_atual = []
                st.rerun()
            else:
                st.error("Erro ao salvar.")
        if c2.button("Limpar"):
            st.session_state.pedido_atual = []
            st.rerun()
    else:
        st.info("Carrinho vazio.")

    st.markdown("---")
    st.subheader("4. Histórico Recente")
    df_rec = get_recent_orders_display(engine, st.session_state.get('username', ''))
    if not df_rec.empty:
        st.dataframe(df_rec, hide_index=True, use_container_width=True)
    else:
        st.info("Sem pedidos recentes.")

