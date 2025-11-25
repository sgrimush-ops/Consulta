import streamlit as st
import pandas as pd
from datetime import datetime
import os
from sqlalchemy import text
import numpy as np
import unicodedata
import logging

# Configuração de Logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =========================================================
#  🧩 CONSTANTES
# =========================================================

LISTA_LOJAS = [
    "001", "002", "003", "004", "005", "006",
    "007", "008", "011", "012", "013", "014", "017", "018"
]

# =========================================================
#  📥 FUNÇÕES AUXILIARES
# =========================================================

def normalize_col(col):
    """Normaliza nomes de colunas para lower case sem acentos."""
    if not isinstance(col, str): 
        return str(col)
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
    """Converte string/float/Series para float seguro."""
    try:
        # Tratamento para Series ou Arrays (acontece se houver colunas duplicadas)
        if hasattr(val, 'squeeze'):
            # Se for Series/DataFrame com 1 valor, extrai o escalar
            try:
                val = val.squeeze()
            except:
                pass
        
        # Se ainda for Series/Array (múltiplos valores), pega o primeiro
        if hasattr(val, 'iloc'):
            if not val.empty:
                val = val.iloc[0]
            else:
                return 0.0
        elif isinstance(val, (list, tuple, np.ndarray)):
            val = val[0] if len(val) > 0 else 0.0

        # Verificação padrão de escalar
        if pd.isna(val) or str(val).strip() == '': 
            return 0.0
            
        if isinstance(val, (int, float)): 
            return float(val)
            
        val = str(val).strip()
        # Se tiver vírgula, assume decimal BR
        if ',' in val:
            val = val.replace('.', '').replace(',', '.')
            
        return float(val)
    except Exception:
        return 0.0

@st.cache_data(ttl=300)
def load_database(base_path, _engine):
    """Carrega e processa os DataFrames necessários."""
    
    def read_safe(filename):
        p = os.path.join(base_path, f"{filename}.parquet")
        if os.path.exists(p): 
            try:
                return pd.read_parquet(p)
            except Exception as e:
                logger.error(f"Erro ao ler {filename}: {e}")
                return pd.DataFrame()
        return pd.DataFrame()

    df_mix = read_safe("__MixAtivoSistema")
    df_hist = read_safe("historico_solic")
    df_wms = read_safe("WMS")

    # --- PROCESSAMENTO MIX ---
    if not df_mix.empty:
        df_mix.columns = [normalize_col(c) for c in df_mix.columns]
        # Remove colunas duplicadas (evita retorno de Series em gets)
        df_mix = df_mix.loc[:, ~df_mix.columns.duplicated()]
        
        rename_map = {}
        for c in df_mix.columns:
            if 'codigoint' in c: rename_map[c] = 'Codigo'
            elif 'descri' in c or 'produto' in c: rename_map[c] = 'Produto'
            elif 'emb' in c and 'sep' in c: rename_map[c] = 'Emb'
            elif 'ean' in c: rename_map[c] = 'EAN'
        
        df_mix.rename(columns=rename_map, inplace=True)
        
        if 'Codigo' in df_mix.columns:
            df_mix['Codigo'] = pd.to_numeric(df_mix['Codigo'], errors='coerce').fillna(0).astype(int).astype(str)
            df_mix = df_mix.drop_duplicates(subset=['Codigo'])

    # --- PROCESSAMENTO HISTÓRICO ---
    if not df_hist.empty:
        df_hist.columns = [normalize_col(c) for c in df_hist.columns]
        # Remove colunas duplicadas IMEDIATAMENTE após normalizar
        df_hist = df_hist.loc[:, ~df_hist.columns.duplicated()]

        rename_map = {}
        for c in df_hist.columns:
            if 'codigoint' in c: rename_map[c] = 'Codigo'
            elif 'loja' in c: rename_map[c] = 'Loja'
            elif 'est' in c: rename_map[c] = 'Estoque_CX'
            elif 'ped' in c: rename_map[c] = 'Pendente_CX'
            elif 'vd' in c and '1' in c: rename_map[c] = 'Venda1Sem_CX' 
            elif 'vd' in c and '2' in c: rename_map[c] = 'Venda2Sem_CX' 
            elif 'vm' in c and '30' in c: rename_map[c] = 'Venda30d_CX'
            elif 'data' in c or 'solic' in c: rename_map[c] = 'Data_Solic'
        
        df_hist.rename(columns=rename_map, inplace=True)
        
        if 'Codigo' in df_hist.columns:
            df_hist['Codigo'] = pd.to_numeric(df_hist['Codigo'], errors='coerce').fillna(0).astype(int).astype(str)
        
        if 'Loja' in df_hist.columns:
            df_hist['Loja'] = pd.to_numeric(df_hist['Loja'], errors='coerce').fillna(0).astype(int).astype(str).str.zfill(3)
            
        # Garante limpeza numérica
        cols_num = ['Estoque_CX', 'Pendente_CX', 'Venda1Sem_CX', 'Venda2Sem_CX', 'Venda30d_CX']
        for col in cols_num:
            if col in df_hist.columns:
                # Aplica clean_float elemento a elemento
                df_hist[col] = df_hist[col].apply(clean_float)
        
        # Filtra registro mais recente
        if 'Data_Solic' in df_hist.columns:
            df_hist['Data_Solic'] = pd.to_datetime(df_hist['Data_Solic'], dayfirst=True, errors='coerce')
            df_hist = df_hist.sort_values(by=['Codigo', 'Loja', 'Data_Solic'], ascending=[True, True, False])
            
        if 'Codigo' in df_hist.columns and 'Loja' in df_hist.columns:
            df_hist = df_hist.drop_duplicates(subset=['Codigo', 'Loja'], keep='first')

    # --- PROCESSAMENTO WMS ---
    if not df_wms.empty:
        df_wms.columns = [normalize_col(c) for c in df_wms.columns]
        # Remove duplicadas
        df_wms = df_wms.loc[:, ~df_wms.columns.duplicated()]

        col_qtd = next((c for c in df_wms.columns if 'qtd' in c or 'quant' in c), None)
        
        if col_qtd:
            df_wms.rename(columns={col_qtd: 'Qtd_CD', 'codigo': 'Codigo'}, inplace=True)
            if 'Codigo' in df_wms.columns:
                df_wms['Codigo'] = pd.to_numeric(df_wms['Codigo'], errors='coerce').fillna(0).astype(int).astype(str)
            
            if 'Qtd_CD' in df_wms.columns:
                 df_wms['Qtd_CD'] = df_wms['Qtd_CD'].apply(clean_float)

            df_wms = df_wms.groupby('Codigo', as_index=False)['Qtd_CD'].sum()

    # --- PROCESSAMENTO OFERTAS ---
    df_ofertas = pd.DataFrame()
    try:
        if _engine:
            with _engine.connect() as conn:
                q = text("SELECT codigo, oferta, data_inicio, data_final FROM ofertas WHERE data_final >= CURRENT_DATE")
                df_ofertas = pd.read_sql(q, conn)
                if not df_ofertas.empty:
                    df_ofertas['codigo'] = pd.to_numeric(df_ofertas['codigo'], errors='coerce').fillna(0).astype(int).astype(str)
                    df_ofertas['data_inicio'] = pd.to_datetime(df_ofertas['data_inicio']).dt.date
                    df_ofertas['data_final'] = pd.to_datetime(df_ofertas['data_final']).dt.date
    except Exception as e:
        logger.warning(f"Erro ao carregar ofertas: {e}")

    return df_mix, df_hist, df_wms, df_ofertas

def save_order(engine, dados):
    if not dados: return False
    try:
        with engine.begin() as conn:
            cols = ", ".join([f"loja_{l}" for l in LISTA_LOJAS])
            vals = ", ".join([f":loja_{l}" for l in LISTA_LOJAS])
            
            q = text(f"""
                INSERT INTO pedidos_consolidados 
                (codigo, produto, embseparacao, data_pedido, usuario_pedido, status_item, total_cx, {cols}) 
                VALUES (:c, :p, :e, :d, :u, 'Ativo', :t, {vals})
            """)
            
            now = datetime.now()
            user = st.session_state.get("username", "anonimo")
            
            for item in dados:
                emb = int(clean_float(item.get("Emb")))
                tot = int(clean_float(item.get("Total")))
                
                params = {
                    "c": str(item.get("Codigo")), 
                    "p": str(item.get("Produto")), 
                    "e": emb, 
                    "d": now, 
                    "u": user, 
                    "t": tot
                }
                
                for l in LISTA_LOJAS:
                    qtd_loja = int(clean_float(item.get(l)))
                    params[f"loja_{l}"] = qtd_loja
                
                conn.execute(q, params)
        return True
    except Exception as e:
        st.error(f"Erro crítico ao salvar no banco: {e}")
        logger.error(f"Erro save_order: {e}")
        return False

# =========================================================
#  🖥️ PÁGINA PRINCIPAL
# =========================================================

def show_pedidos_page(engine, base_data_path):
    st.title("🛒 Digitação de Pedidos")
    
    # Inicialização de Estado
    if "pedido_atual" not in st.session_state:
        st.session_state.pedido_atual = []
    
    # Validação de acesso a lojas
    lojas_acesso = st.session_state.get('lojas_acesso', [])
    if not lojas_acesso:
        st.warning("⚠️ Seu usuário não possui lojas vinculadas para digitação. Contate o administrador.")
        
    # 1. Carregamento de Dados
    with st.spinner("Sincronizando dados..."):
        df_mix, df_hist, df_wms, df_ofertas = load_database(base_data_path, engine)

    if df_mix.empty:
        st.error("⚠️ Base de Mix não encontrada ou vazia. Verifique o caminho dos arquivos Parquet.")
        return

    # 2. Filtros de Busca
    st.subheader("1. Selecionar Produto")
    c1, c2 = st.columns([1, 4])
    cod_input = c1.text_input("Código Interno:", key="search_cod")
    desc_input = c2.text_input("Descrição ou Parte do Nome:", key="search_desc")

    prod = None
    
    # Lógica de Busca Prioritária
    if cod_input:
        # Busca exata por código
        r = df_mix[df_mix['Codigo'] == str(cod_input).strip()]
        if not r.empty: 
            prod = r.iloc[0]
        else: 
            st.warning("Código não encontrado no Mix Ativo.")
    elif desc_input:
        # Busca textual
        mask = df_mix['Produto'].astype(str).str.lower().str.contains(desc_input.lower(), na=False)
        r = df_mix[mask].head(100) # Limita resultados para performance
        
        if not r.empty:
            opts = {f"{row['Codigo']} - {row['Produto']}": row['Codigo'] for _, row in r.iterrows()}
            sel = st.selectbox("Selecione o produto:", [""] + list(opts.keys()))
            if sel: 
                cod = opts[sel]
                prod = df_mix[df_mix['Codigo'] == cod].iloc[0]
        else:
            st.info("Nenhum produto encontrado com esse termo.")

    # 3. Exibição dos Detalhes e Grade
    if prod is not None:
        codigo = prod['Codigo']
        nome = prod['Produto']
        emb = int(clean_float(prod.get('Emb')))

        if emb <= 0:
            st.error(f"⛔ Produto com cadastro de embalagem inválido (Emb: {emb}). Não é possível pedir.")
            return

        st.divider()
        st.markdown(f"### 📦 {codigo} - {nome}")
        st.caption(f"Embalagem de Separação: **{emb} un**")

        # --- INFO DE PROMOÇÃO ---
        if not df_ofertas.empty:
            promo = df_ofertas[df_ofertas['codigo'] == str(codigo)]
            if not promo.empty:
                # Filtra apenas ofertas válidas hoje
                hoje = datetime.now().date()
                promo = promo[promo['data_final'] >= hoje]
                
                if not promo.empty:
                    promo_item = promo.sort_values('data_inicio').iloc[0]
                    inicio = promo_item['data_inicio'].strftime('%d/%m')
                    fim = promo_item['data_final'].strftime('%d/%m')
                    valor = clean_float(promo_item['oferta'])
                    st.info(f"🔥 **EM OFERTA!** De {inicio} a {fim} por **R$ {valor:.2f}**")
        
        # --- INFO WMS (Estoque CD) ---
        qtd_cd_un = 0.0
        if not df_wms.empty:
            w = df_wms[df_wms['Codigo'] == str(codigo)]
            if not w.empty: 
                qtd_cd_un = w['Qtd_CD'].iloc[0]
        
        cx_cd = int(qtd_cd_un / emb) if emb > 0 else 0
        
        # Cor visual para estoque CD crítico
        cor_cd = "green" if cx_cd > 10 else "orange" if cx_cd > 0 else "red"
        st.markdown(f"Estoque CD: :{cor_cd}[**{format_br(cx_cd).split(',')[0]} cx**] ({int(qtd_cd_un):,} un)")

        # --- GRADE DE LOJAS ---
        grade = []
        
        # Indexa histórico para busca rápida
        sub = pd.DataFrame()
        if not df_hist.empty: 
            sub = df_hist[df_hist['Codigo'] == str(codigo)].set_index('Loja')

        for l in LISTA_LOJAS:
            if l not in lojas_acesso: 
                continue
            
            est_cx = pend_cx = v1_cx = v2_cx = v30_cx = 0.0
            
            if l in sub.index:
                r = sub.loc[l]
                # Se houver duplicidade no índice (loja repetida), pega a primeira ou soma
                if isinstance(r, pd.DataFrame): r = r.iloc[0]
                
                # clean_float já cuida se retornar Series
                est_cx = clean_float(r.get('Estoque_CX'))
                pend_cx = clean_float(r.get('Pendente_CX'))
                v1_cx = clean_float(r.get('Venda1Sem_CX'))
                v2_cx = clean_float(r.get('Venda2Sem_CX'))
                v30_cx = clean_float(r.get('Venda30d_CX'))
            
            grade.append({
                "Loja": l, 
                "Est": format_br(est_cx), 
                "Pend": format_br(pend_cx), 
                "Vd 1Sm": format_br(v1_cx), 
                "Vd 2Sm": format_br(v2_cx), 
                "Vd 30d": format_br(v30_cx),
                "PEDIDO": 0 # Valor inicial editável
            })

        if grade:
            dfg = pd.DataFrame(grade)
            
            # Editor de Dados
            ed = st.data_editor(
                dfg, 
                hide_index=True, 
                use_container_width=True, 
                key=f"editor_{codigo}",
                column_config={
                    "Loja": st.column_config.TextColumn(disabled=True),
                    "Est": st.column_config.TextColumn("Est (Cx)", disabled=True, help="Estoque Atual"),
                    "Pend": st.column_config.TextColumn("Pend (Cx)", disabled=True, help="Pedidos Pendentes"),
                    "Vd 1Sm": st.column_config.TextColumn("Vd 7d", disabled=True),
                    "Vd 2Sm": st.column_config.TextColumn("Vd 14d", disabled=True),
                    "Vd 30d": st.column_config.TextColumn("Vd 30d", disabled=True),
                    "PEDIDO": st.column_config.NumberColumn(
                        "PEDIDO (CX)", 
                        min_value=0, 
                        max_value=10000,
                        step=1,
                        required=True
                    )
                }
            )
            
            tot_pedido = ed["PEDIDO"].sum()
            
            # Barra de Ação
            col_info, col_btn = st.columns([3, 1])
            
            with col_info:
                if tot_pedido > cx_cd:
                    st.warning(f"⚠️ Pedido Total ({tot_pedido} cx) excede estoque do CD ({cx_cd} cx).")
                else:
                    st.info(f"Total Pedido: **{tot_pedido:,.0f}** cx")
            
            with col_btn:
                # Verifica se o item já está no carrinho para evitar duplicidade
                ja_no_carrinho = any(item['Codigo'] == codigo for item in st.session_state.pedido_atual)
                btn_label = "Atualizar" if ja_no_carrinho else "Adicionar"
                btn_type = "secondary" if ja_no_carrinho else "primary"

                if st.button(f"{btn_label}", type=btn_type, use_container_width=True):
                    if tot_pedido > 0:
                        # Remove se já existir para adicionar o novo
                        st.session_state.pedido_atual = [x for x in st.session_state.pedido_atual if x['Codigo'] != codigo]
                        
                        item_dict = {
                            "Codigo": codigo, 
                            "Produto": nome, 
                            "Emb": emb, 
                            "Total": tot_pedido
                        }
                        # Adiciona as quantidades por loja
                        for _, r in ed.iterrows(): 
                            item_dict[r['Loja']] = int(r['PEDIDO'])
                        
                        st.session_state.pedido_atual.append(item_dict)
                        st.success(f"{nome} adicionado com sucesso!")
                    else: 
                        st.warning("Quantidade total deve ser maior que zero.")
        else:
            st.warning("Nenhuma loja disponível para exibir dados.")

    # 4. Carrinho e Finalização
    if st.session_state.pedido_atual:
        st.divider()
        st.subheader(f"🛒 Carrinho ({len(st.session_state.pedido_atual)} itens)")
        
        cart_df = pd.DataFrame(st.session_state.pedido_atual)
        
        st.dataframe(
            cart_df[["Codigo", "Produto", "Total"]], 
            hide_index=True,
            use_container_width=True,
            column_config={
                "Total": st.column_config.NumberColumn("Total (Cx)", format="%d")
            }
        )
        
        c1, c2, c3 = st.columns([1, 1, 2])
        
        if c1.button("✅ Enviar Pedido", type="primary"):
            with st.spinner("Gravando pedido..."):
                if save_order(engine, st.session_state.pedido_atual):
                    st.balloons()
                    st.success("Pedido enviado com sucesso!")
                    st.session_state.pedido_atual = [] # Limpa carrinho
                    st.rerun()
        
        if c2.button("🗑️ Limpar Tudo"):
            st.session_state.pedido_atual = []
            st.rerun()