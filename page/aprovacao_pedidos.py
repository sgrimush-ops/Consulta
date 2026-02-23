import streamlit as st
import pandas as pd
import os
from sqlalchemy import text
from datetime import datetime, timedelta, date
import io
from utils.timezone import now_brazil, today_brazil

# --- Configurações ---
LISTA_LOJAS = [
    "001", "002", "003", "004", "005", "006",
    "007", "008", "011", "012", "013", "014", "016", "017", "018"
]
COLUNAS_LOJAS_PEDIDO = [f"loja_{loja}" for loja in LISTA_LOJAS]


# --- Funções Auxiliares ---


def formatar_tipos_df(df: pd.DataFrame) -> pd.DataFrame:
    """Formata tipos de dados e corrige valores numéricos."""
    int_cols = COLUNAS_LOJAS_PEDIDO + [
        "total_cx",
        "embseparacao",
        "embalagem",
        "codigo_interno",
    ]
    
    for col in int_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    
    return df


def load_products_from_parquet():
    """Carrega produtos do arquivo parquet."""
    parquet_path = os.path.join("bdados", "con5cod.parquet")
    
    if not os.path.exists(parquet_path):
        return pd.DataFrame()
    
    try:
        df = pd.read_parquet(parquet_path)        
        # Mapear colunas novas
        column_mapping = {
            'codigoconsinco': 'cod_consinco',
            'Código Produto': 'cod_consinco',
            'codigo transicao': 'transicao',
            'CODACESSO': 'transicao',
            'Empresa : Produto': 'descricao',
            'embalagem': 'Emb',
            'EmbSeparacao': 'Emb',
            'ltmix': 'Mix',
            'capacidade': 'CapacidadeGondola',
            'CapacidadeGondola': 'CapacidadeGondola'
        }
        
        df.rename(columns=column_mapping, inplace=True)
        
        # Garantir colunas minimas
        if 'cod_consinco' not in df.columns:
            raise ValueError("Coluna 'cod_consinco' não encontrada")
        if 'descricao' not in df.columns:
            df['descricao'] = 'SEM DESCRIÇÃO'
        if 'Emb' not in df.columns:
            df['Emb'] = 1
        if 'Mix' not in df.columns:
            df['Mix'] = 'A'
        if 'CapacidadeGondola' not in df.columns:
            df['CapacidadeGondola'] = 0
        df['cod_consinco'] = df['cod_consinco'].astype(int)
        return df
    except Exception:
        return pd.DataFrame()


def get_product_info(df_produtos, codigo):
    """Retorna informações do produto do parquet."""
    if df_produtos.empty:
        return None
    
    try:
        cod = int(codigo)
        result = df_produtos[df_produtos['cod_consinco'] == cod]
        if not result.empty:
            return result.iloc[0].to_dict()
    except:
        pass
    return None


def get_pedidos_para_aprovacao(
    engine,
    date_start,
    date_end,
    only_pending: bool,
    origem_filtro: str = "Todas",
) -> pd.DataFrame:
    """Busca pedidos para aprovação."""
    try:
        start_str = datetime.combine(date_start, datetime.min.time()).strftime("%Y-%m-%d %H:%M:%S")
        end_str = datetime.combine(date_end, datetime.max.time()).strftime("%Y-%m-%d %H:%M:%S")
        lojas_sql = ", ".join(COLUNAS_LOJAS_PEDIDO)
        
        query = text(
            f"""
            SELECT
                p.id AS id_pedido,
                TO_CHAR(p.data_pedido, 'DD/MM/YYYY HH24:MI') AS data_pedido_str,
                p.usuario_pedido,
                p.codigo_interno,
                p.descricao,
                p.embseparacao,
                p.{lojas_sql},
                p.total_cx,
                COALESCE(
                    p.origem_pedido,
                    'Pedido por Código (CD)'
                ) AS origem_pedido,
                p.status_item,
                p.status_aprovacao
            FROM pedidos_consolidados p
            WHERE p.data_pedido BETWEEN :start_str AND :end_str
        """
        )
        
        params = {"start_str": start_str, "end_str": end_str}
        
        if only_pending:
            query = text(str(query) + " AND status_aprovacao = 'Pendente'")

        if origem_filtro == "Pedido de Consumo":
            query = text(
                str(query)
                + " AND COALESCE(origem_pedido, 'Pedido por Código (CD)') "
                + "= 'Pedido de Consumo'"
            )
        elif origem_filtro == "Pedido por Código (CD)":
            query = text(
                str(query)
                + " AND COALESCE(origem_pedido, 'Pedido por Código (CD)') "
                + "IN ('Pedido por Código (CD)', 'CD15', 'CD16')"
            )
        
        query = text(str(query) + " ORDER BY data_pedido ASC")
        
        df_pedidos = pd.read_sql_query(query, con=engine, params=params)
        df_pedidos = formatar_tipos_df(df_pedidos)
        
        return df_pedidos
    
    except Exception as e:
        st.error(f"Erro ao buscar pedidos: {e}")
        return pd.DataFrame()


def update_pedidos_aprovados(engine, df_editado_selecionado):
    """Atualiza o banco com quantidades editadas e aprova os itens."""
    try:
        data_aprovacao_dt = now_brazil()
        set_lojas_sql = ", ".join([f"{col} = :{col}" for col in COLUNAS_LOJAS_PEDIDO])
        
        query = text(
            f"""
            UPDATE pedidos_consolidados
            SET
                {set_lojas_sql},
                total_cx = :total_cx,
                data_aprovacao = :data_aprovacao,
                status_aprovacao = 'Aprovado'
            WHERE id = :id_pedido
        """
        )
        
        with engine.begin() as conn:
            for _, row in df_editado_selecionado.iterrows():
                params = {"id_pedido": row["id_pedido"], "data_aprovacao": data_aprovacao_dt}
                params["total_cx"] = row["total_cx"]
                
                for col in COLUNAS_LOJAS_PEDIDO:
                    params[col] = row[col]
                
                conn.execute(query, params)
        
        return True
    except Exception as e:
        st.error(f"Erro ao aprovar pedidos: {e}")
        return False


def reprovar_pedidos(engine, ids_list):
    """Reprova pedidos (altera status para 'Reprovado')."""
    try:
        query = text(
            """
            UPDATE pedidos_consolidados
            SET status_aprovacao = 'Reprovado', data_aprovacao = :data_aprovacao
            WHERE id = ANY(:ids)
        """
        )
        
        with engine.begin() as conn:
            conn.execute(query, {"ids": ids_list, "data_aprovacao": now_brazil()})
        
        return True
    except Exception as e:
        st.error(f"Erro ao reprovar pedidos: {e}")
        return False


# --- Página Principal ---


def show_aprovacao_page(engine, base_data_path):
    """Página de aprovação de pedidos."""
    
    st.title("✅ Aprovação de Pedidos")
    st.markdown("Aprovar ou reprovar pedidos enviados pelos usuários")
    
    # Carregar produtos
    df_produtos = load_products_from_parquet()
    
    # --- Filtros ---
    st.markdown("### 🔍 Filtros")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        date_start = st.date_input(
            "Data Início:",
            value=today_brazil() - timedelta(days=7),
            key="date_start_aprov"
        )
    
    with col2:
        date_end = st.date_input(
            "Data Fim:",
            value=today_brazil(),
            key="date_end_aprov"
        )
    
    with col3:
        only_pending = st.checkbox("Apenas Pendentes", value=True)

    with col4:
        origem_filtro = st.selectbox(
            "Origem:",
            ["Todas", "Pedido de Consumo", "Pedido por Código (CD)"],
            index=0,
            key="origem_filtro_aprov",
        )
    
    # Buscar pedidos
    df_pedidos = get_pedidos_para_aprovacao(
        engine,
        date_start,
        date_end,
        only_pending,
        origem_filtro,
    )
    
    if df_pedidos.empty:
        st.info("Nenhum pedido encontrado no período selecionado.")
        return
    
    st.markdown(f"### 📊 {len(df_pedidos)} pedido(s) encontrado(s)")
    
    # Adicionar informações do mix
    if not df_produtos.empty:
        df_pedidos['Status Mix'] = df_pedidos['codigo_interno'].apply(
            lambda x: get_product_info(df_produtos, x)['Mix'] if get_product_info(df_produtos, x) else 'N/A'
        )
        df_pedidos['Status Mix'] = df_pedidos['Status Mix'].map({'A': '✅ Ativo', 'S': '⚠️ Suspenso', 'N/A': '❓ N/A'})
    else:
        df_pedidos['Status Mix'] = '❓ N/A'
    
    # Adicionar checkbox para seleção
    df_pedidos.insert(0, "Selecionar", False)

    # Marcador visual de origem
    if "origem_pedido" in df_pedidos.columns:
        df_pedidos["Origem"] = df_pedidos["origem_pedido"].apply(
            lambda origem: (
                "🛒 Pedido de Consumo"
                if str(origem) == "Pedido de Consumo"
                else f"📦 {str(origem).strip() if str(origem).strip() else 'Pedido por Código (CD)'}"
            )
        )
    else:
        df_pedidos["Origem"] = "📦 Pedido por Código (CD)"
    
    # Preparar colunas para exibição
    cols_exibicao = [
        "Selecionar", "id_pedido", "data_pedido_str", "usuario_pedido",
        "Origem", "codigo_interno", "descricao", "Status Mix",
        "embseparacao", "total_cx",
        "status_aprovacao"
    ] + COLUNAS_LOJAS_PEDIDO
    
    # Filtrar apenas colunas que existem
    cols_exibicao = [col for col in cols_exibicao if col in df_pedidos.columns]
    
    df_para_editar = df_pedidos[cols_exibicao].copy()

    # Persistir seleção entre reruns (por id_pedido)
    selection_key = "aprovacao_selected_ids"
    if selection_key not in st.session_state:
        st.session_state[selection_key] = []

    ids_visiveis = df_para_editar["id_pedido"].tolist()
    selecionados_atuais = set(st.session_state.get(selection_key, []))
    selecionados_atuais = selecionados_atuais.intersection(ids_visiveis)
    st.session_state[selection_key] = list(selecionados_atuais)
    
    # Botões de seleção rápida
    st.markdown("### ⚡ Seleção Rápida")
    col_marcar, col_desmarcar = st.columns(2)
    
    with col_marcar:
        if st.button("☑️ Marcar Todos", use_container_width=True):
            st.session_state[selection_key] = ids_visiveis.copy()
    
    with col_desmarcar:
        if st.button("⬜ Desmarcar Todos", use_container_width=True):
            st.session_state[selection_key] = []

    df_para_editar["Selecionar"] = df_para_editar["id_pedido"].isin(
        st.session_state[selection_key]
    )
    
    st.markdown("---")
    
    # Configuração do editor
    column_config = {
        "Selecionar": st.column_config.CheckboxColumn("Selecionar", default=False),
        "id_pedido": None,  # Ocultar
        "data_pedido_str": st.column_config.TextColumn("Data/Hora", disabled=True),
        "usuario_pedido": st.column_config.TextColumn("Usuário", disabled=True, width="small"),
        "Origem": st.column_config.TextColumn(
            "Origem",
            disabled=True,
            width="medium"
        ),
        "codigo_interno": st.column_config.NumberColumn("Cód. Consinco", disabled=True, format="%d"),
        "descricao": st.column_config.TextColumn("Produto", disabled=True, width="large"),
        "Status Mix": st.column_config.TextColumn("Mix", disabled=True, width="small"),
        "embseparacao": st.column_config.NumberColumn("Emb", disabled=True, format="%d"),
        "total_cx": st.column_config.NumberColumn("Total CX", format="%d"),
        "status_aprovacao": st.column_config.TextColumn("Status", disabled=True, width="small"),
    }
    
    # Configurar colunas de lojas como editáveis
    for col in COLUNAS_LOJAS_PEDIDO:
        if col in df_para_editar.columns:
            loja_num = col.replace("loja_", "")
            column_config[col] = st.column_config.NumberColumn(
                loja_num, min_value=0, step=1, format="%d"
            )
    
    # Editor de dados
    df_editado = st.data_editor(
        df_para_editar,
        column_config=column_config,
        hide_index=True,
        use_container_width=True,
        key="editor_aprovacao_v2"
    )

    # Sincronizar seleção manual do editor com session_state
    selecionados_editor = df_editado.loc[
        df_editado["Selecionar"] == True, "id_pedido"
    ].tolist()
    st.session_state[selection_key] = selecionados_editor
    
    # Recalcular total_cx baseado nas quantidades editadas
    for idx in df_editado.index:
        soma = sum(df_editado.loc[idx, col] for col in COLUNAS_LOJAS_PEDIDO if col in df_editado.columns)
        df_editado.loc[idx, "total_cx"] = soma
    
    # Botões de ação
    st.markdown("---")
    col_aprovar, col_reprovar = st.columns(2)
    
    with col_aprovar:
        if st.button("✅ Aprovar Selecionados", type="primary", use_container_width=True):
            selecionados = df_editado[df_editado["Selecionar"] == True]
            
            if selecionados.empty:
                st.warning("Nenhum pedido selecionado.")
            else:
                if update_pedidos_aprovados(engine, selecionados):
                    st.success(f"✅ {len(selecionados)} pedido(s) aprovado(s) com sucesso!")
                    st.rerun()
    
    with col_reprovar:
        if st.button("❌ Reprovar Selecionados", use_container_width=True):
            selecionados = df_editado[df_editado["Selecionar"] == True]
            
            if selecionados.empty:
                st.warning("Nenhum pedido selecionado.")
            else:
                ids_reprovar = selecionados["id_pedido"].tolist()
                if reprovar_pedidos(engine, ids_reprovar):
                    st.success(f"❌ {len(selecionados)} pedido(s) reprovado(s)!")
                    st.rerun()
    
    # --- Download de Pedidos Aprovados ---
    st.markdown("---")
    st.subheader("📥 Download de Pedidos Aprovados")
    
    if st.button("Gerar Excel de Pedidos Aprovados"):
        try:
            limite_aprovacao = now_brazil() - timedelta(minutes=5)

            query = text(
                f"""
                SELECT
                    p.id,
                    TO_CHAR(p.data_pedido, 'DD/MM/YYYY') AS data_pedido,
                    TO_CHAR(p.data_aprovacao, 'DD/MM/YYYY') AS data_aprovacao,
                    p.usuario_pedido,
                    p.codigo_interno,
                    p.descricao,
                    p.embseparacao,
                    p.{", p.".join(COLUNAS_LOJAS_PEDIDO)},
                    p.total_cx
                FROM pedidos_consolidados p
                WHERE p.status_aprovacao = 'Aprovado'
                  AND p.data_aprovacao >= :limite_aprovacao
                ORDER BY p.data_aprovacao DESC
                """
            )
            
            df_aprovados = pd.read_sql_query(
                query,
                con=engine,
                params={"limite_aprovacao": limite_aprovacao}
            )
            
            if not df_aprovados.empty:
                lojas_presentes = [
                    col for col in COLUNAS_LOJAS_PEDIDO
                    if col in df_aprovados.columns
                ]

                for col in lojas_presentes:
                    df_aprovados[col] = pd.to_numeric(
                        df_aprovados[col], errors="coerce"
                    ).fillna(0)

                df_lojas = df_aprovados.melt(
                    id_vars=[
                        "id",
                        "data_pedido",
                        "usuario_pedido",
                        "codigo_interno",
                        "descricao",
                        "embseparacao",
                    ],
                    value_vars=lojas_presentes,
                    var_name="loja_col",
                    value_name="qtd_cx_loja",
                )

                df_lojas = df_lojas[df_lojas["qtd_cx_loja"] > 0].copy()

                if df_lojas.empty:
                    st.info(
                        "Nenhum item com quantidade por loja nos pedidos "
                        "aprovados dos últimos 5 minutos."
                    )
                    return

                df_lojas["loja"] = (
                    df_lojas["loja_col"].astype(str).str.replace(
                        "loja_", "", regex=False
                    )
                )

                def formatar_usuarios(series_usuarios):
                    contagem = (
                        series_usuarios.astype(str)
                        .str.strip()
                        .replace("", "unknown")
                        .value_counts()
                    )
                    return ", ".join(
                        [
                            f"{usuario} ({qtd})" if qtd > 1 else usuario
                            for usuario, qtd in contagem.items()
                        ]
                    )

                df_export = (
                    df_lojas.groupby(
                        [
                            "data_pedido",
                            "loja",
                            "codigo_interno",
                            "descricao",
                            "embseparacao",
                        ],
                        as_index=False,
                    )
                    .agg(
                        total_cx=("qtd_cx_loja", "sum"),
                        usuarios_pedido=("usuario_pedido", formatar_usuarios),
                        qtd_lancamentos=("id", "count"),
                    )
                    .sort_values(
                        by=["data_pedido", "loja", "descricao"],
                        ascending=[False, True, True],
                    )
                )

                df_export = df_export.rename(
                    columns={
                        "data_pedido": "Data Pedido",
                        "loja": "Loja",
                        "codigo_interno": "Código Consinco",
                        "descricao": "Descrição",
                        "embseparacao": "Emb",
                        "total_cx": "Total CX",
                        "usuarios_pedido": "Usuários",
                        "qtd_lancamentos": "Qtd Lançamentos",
                    }
                )

                # Criar arquivo Excel em memória
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_export.to_excel(
                        writer,
                        sheet_name='Pedidos Aprovados',
                        index=False
                    )
                
                output.seek(0)
                
                st.download_button(
                    label="📥 Baixar Pedidos Aprovados (Excel)",
                    data=output,
                    file_name="pedido.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.info("Nenhum pedido aprovado nos últimos 5 minutos.")
        
        except Exception as e:
            st.error(f"Erro ao gerar Excel: {e}")
