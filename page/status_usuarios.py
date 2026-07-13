import streamlit as st
from sqlalchemy import text
import pandas as pd
from utils.timezone import now_brazil

REFRESH_INTERVAL_MS = 10000  # auto refresh a cada 10s


def delete_users_batch(engine, username_list: list[str]) -> int:
    """Exclui uma lista de usuários pelo username no DB."""
    if not username_list:
        return 0
    clean_list = [str(u).strip().lower() for u in username_list if str(u).strip()]
    if not clean_list:
        return 0

    try:
        total_deleted = 0
        with engine.begin() as conn:
            for u in clean_list:
                result = conn.execute(
                    text("DELETE FROM users WHERE LOWER(username) = :u"),
                    {"u": u}
                )
                total_deleted += result.rowcount
        return total_deleted
    except Exception as e:
        st.error(f"Erro ao excluir usuários: {e}")
        return 0


def get_user_status_df(engine) -> pd.DataFrame:
    """
    Busca usuários no DB, calcula classificações claras (incluindo Inativo 60+ dias
    e Nunca Acessou) e identifica quem é elegível para exclusão.
    """
    try:
        query = text(
            "SELECT username, empresa, cargo, ultimo_acesso, status_logado FROM users"
        )
        df_users = pd.read_sql_query(query, con=engine)
    except Exception as e:
        st.error(f"Erro ao carregar usuários: {e}")
        return pd.DataFrame()

    if df_users.empty:
        return pd.DataFrame()

    agora = pd.to_datetime(now_brazil())

    # 1. Converte datas
    df_users['ultimo_acesso_dt'] = pd.to_datetime(
        df_users['ultimo_acesso'], errors='coerce'
    )

    # 2. Calcula tempo em segundos
    df_users['Tempo_Segundos'] = (
        agora - df_users['ultimo_acesso_dt']
    ).dt.total_seconds()

    # 3. Formata string de data
    df_users['ultimo_acesso_str'] = (
        df_users['ultimo_acesso_dt'].dt.strftime('%d/%m/%Y %H:%M:%S')
        .fillna("Sem registro")
    )

    # 4. Define categorias e badges (Padrão: Nunca Acessou)
    df_users['Sort_Key'] = 5
    df_users['Categoria'] = "Nunca Acessou"
    df_users['Badge'] = "🟣 Nunca Acessou"
    df_users['Cor'] = "#9C27B0"
    df_users['Elegivel_Exclusao'] = True

    # Offline (< 60 dias) - entre 24h e 60 dias (60 * 86400 = 5184000)
    offline_mask = (
        df_users['ultimo_acesso_dt'].notna() &
        (df_users['Tempo_Segundos'] >= 86400) &
        (df_users['Tempo_Segundos'] < 5184000)
    )
    df_users.loc[offline_mask, 'Sort_Key'] = 3
    df_users.loc[offline_mask, 'Categoria'] = "Offline (< 60 dias)"
    df_users.loc[offline_mask, 'Badge'] = "⚪ Offline (< 60 dias)"
    df_users.loc[offline_mask, 'Cor'] = "#757575"
    df_users.loc[offline_mask, 'Elegivel_Exclusao'] = False

    # Inativo 60+ dias
    inativo_60d_mask = (
        df_users['ultimo_acesso_dt'].notna() &
        (df_users['Tempo_Segundos'] >= 5184000)
    )
    df_users.loc[inativo_60d_mask, 'Sort_Key'] = 4
    df_users.loc[inativo_60d_mask, 'Categoria'] = "Inativo (60+ dias)"
    df_users.loc[inativo_60d_mask, 'Badge'] = "🔴 Inativo (60+ dias)"
    df_users.loc[inativo_60d_mask, 'Cor'] = "#F44336"
    df_users.loc[inativo_60d_mask, 'Elegivel_Exclusao'] = True

    # Ativo Hoje (< 24h)
    recente_mask = (
        df_users['ultimo_acesso_dt'].notna() &
        (df_users['Tempo_Segundos'] < 86400)
    )
    df_users.loc[recente_mask, 'Sort_Key'] = 2
    df_users.loc[recente_mask, 'Categoria'] = "Ativo Hoje (< 24h)"
    df_users.loc[recente_mask, 'Badge'] = "🟡 Ativo Hoje (< 24h)"
    df_users.loc[recente_mask, 'Cor'] = "#FF9800"
    df_users.loc[recente_mask, 'Elegivel_Exclusao'] = False

    # Online (atividade nos últimos 5 minutos / 300 segundos e logado)
    online_mask = (
        (df_users['status_logado'] == 'LOGADO') &
        df_users['ultimo_acesso_dt'].notna() &
        (df_users['Tempo_Segundos'] < 300)
    )
    df_users.loc[online_mask, 'Sort_Key'] = 1
    df_users.loc[online_mask, 'Categoria'] = "Online"
    df_users.loc[online_mask, 'Badge'] = "🟢 Online"
    df_users.loc[online_mask, 'Cor'] = "#4CAF50"
    df_users.loc[online_mask, 'Elegivel_Exclusao'] = False

    def format_elapsed(row) -> str:
        if pd.isna(row['ultimo_acesso_dt']):
            return "Nunca acessou"
        seconds = row['Tempo_Segundos']
        if pd.isna(seconds) or seconds < 0:
            return "Agora"
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        days = hours // 24
        if days >= 60:
            return f"há {days} dias"
        if days > 0:
            return f"há {days}d {hours % 24}h"
        if hours > 0:
            return f"há {hours}h {minutes}m"
        return f"há {minutes}m" if minutes > 0 else "Agora"

    df_users['Tempo_Formatado'] = df_users.apply(format_elapsed, axis=1)

    # Garantir strings limpas nas colunas informativas
    df_users['empresa'] = df_users['empresa'].fillna('Baklizi')
    df_users['cargo'] = df_users['cargo'].fillna('')

    df_users = df_users.sort_values(
        by=['Sort_Key', 'Tempo_Segundos'], ascending=[True, True]
    ).reset_index(drop=True)

    return df_users


def show_status_page(engine, base_data_path):
    """Página de monitoramento de status e controle/exclusão de inativos."""
    st.title("📊 Status dos Usuários Ativos e Controle de Acessos")
    st.markdown(
        "Verifique em tempo real quem está **Online** no sistema e marque rapidamente para exclusão de acesso "
        "usuários **Inativos há mais de 60 dias** ou que **Nunca Acessaram**."
    )

    df_status = get_user_status_df(engine)

    if df_status.empty:
        st.info("Nenhum usuário encontrado no banco de dados.")
        return

    # Auto refresh a cada 10s se não houver seleções ativas
    selection_key = "sel_exclusao_status"
    if selection_key not in st.session_state:
        st.session_state[selection_key] = []

    if not st.session_state[selection_key]:
        st_autorefresh = getattr(st, "autorefresh", None)
        if st_autorefresh:
            st_autorefresh(interval=REFRESH_INTERVAL_MS, key="status_refresh")

    # --- CARDS DE RESUMO (KPIs) ---
    st.markdown("### 📈 Resumo Geral do Sistema")
    c1, c2, c3, c4, c5 = st.columns(5)
    total_online = int((df_status['Categoria'] == 'Online').sum())
    total_hoje = int((df_status['Categoria'] == 'Ativo Hoje (< 24h)').sum())
    total_offline = int((df_status['Categoria'] == 'Offline (< 60 dias)').sum())
    total_inativo60 = int((df_status['Categoria'] == 'Inativo (60+ dias)').sum())
    total_nunca = int((df_status['Categoria'] == 'Nunca Acessou').sum())

    c1.metric("🟢 Online Agora", total_online)
    c2.metric("🟡 Ativos Hoje (<24h)", total_hoje)
    c3.metric("⚪ Offline (<60d)", total_offline)
    c4.metric("🔴 Inativos (60+ dias)", total_inativo60)
    c5.metric("🟣 Nunca Acessaram", total_nunca)

    st.markdown("---")

    # --- FILTRO POR CATEGORIA ---
    st.markdown("### 🔍 Lista e Seleção de Usuários")
    col_f1, col_f2 = st.columns([2, 2])

    with col_f1:
        filtro_cat = st.selectbox(
            "Filtrar exibição por categoria:",
            [
                "Todos os Usuários",
                "⚠️ Elegíveis para Exclusão (Nunca Acessaram ou Inativos 60+ dias)",
                "🟢 Online",
                "🟡 Ativo Hoje (< 24h)",
                "⚪ Offline (< 60 dias)",
                "🔴 Inativo (60+ dias)",
                "🟣 Nunca Acessou",
            ],
            index=0,
            key="filtro_categoria_status"
        )

    if filtro_cat == "⚠️ Elegíveis para Exclusão (Nunca Acessaram ou Inativos 60+ dias)":
        df_exibir = df_status[df_status['Elegivel_Exclusao'] == True].copy()
    elif filtro_cat == "🟢 Online":
        df_exibir = df_status[df_status['Categoria'] == "Online"].copy()
    elif filtro_cat == "🟡 Ativo Hoje (< 24h)":
        df_exibir = df_status[df_status['Categoria'] == "Ativo Hoje (< 24h)"].copy()
    elif filtro_cat == "⚪ Offline (< 60 dias)":
        df_exibir = df_status[df_status['Categoria'] == "Offline (< 60 dias)"].copy()
    elif filtro_cat == "🔴 Inativo (60+ dias)":
        df_exibir = df_status[df_status['Categoria'] == "Inativo (60+ dias)"].copy()
    elif filtro_cat == "🟣 Nunca Acessou":
        df_exibir = df_status[df_status['Categoria'] == "Nunca Acessou"].copy()
    else:
        df_exibir = df_status.copy()

    # --- SELEÇÃO RÁPIDA ---
    st.markdown("#### ⚡ Seleção Rápida para Exclusão")
    col_sel1, col_sel2, col_sel3, col_sel4 = st.columns(4)

    with col_sel1:
        if st.button("☑️ Marcar Elegíveis (60+ dias / Nunca)", use_container_width=True):
            elegiveis = df_status.loc[df_status['Elegivel_Exclusao'] == True, 'username'].tolist()
            st.session_state[selection_key] = sorted(list(set(st.session_state[selection_key]) | set(elegiveis)))
            st.rerun()

    with col_sel2:
        if st.button("☑️ Marcar Inativos 60+ dias", use_container_width=True):
            inativos = df_status.loc[df_status['Categoria'] == "Inativo (60+ dias)", 'username'].tolist()
            st.session_state[selection_key] = sorted(list(set(st.session_state[selection_key]) | set(inativos)))
            st.rerun()

    with col_sel3:
        if st.button("☑️ Marcar Nunca Acessaram", use_container_width=True):
            nuncas = df_status.loc[df_status['Categoria'] == "Nunca Acessou", 'username'].tolist()
            st.session_state[selection_key] = sorted(list(set(st.session_state[selection_key]) | set(nuncas)))
            st.rerun()

    with col_sel4:
        if st.button("⬜ Desmarcar Todos", use_container_width=True):
            st.session_state[selection_key] = []
            st.rerun()

    # Aplica marcações da sessão na tabela exibida
    df_exibir["Selecionar"] = df_exibir["username"].isin(st.session_state[selection_key])

    column_config = {
        "Selecionar": st.column_config.CheckboxColumn("Selecionar", default=False),
        "username": st.column_config.TextColumn("Usuário", disabled=True),
        "empresa": st.column_config.TextColumn("Empresa", disabled=True),
        "cargo": st.column_config.TextColumn("Cargo", disabled=True),
        "ultimo_acesso_str": st.column_config.TextColumn("Último Acesso", disabled=True),
        "Tempo_Formatado": st.column_config.TextColumn("Tempo Inativo", disabled=True),
        "Badge": st.column_config.TextColumn("Status / Classificação", disabled=True),
    }

    cols_table = [
        "Selecionar", "username", "empresa", "cargo",
        "ultimo_acesso_str", "Tempo_Formatado", "Badge"
    ]

    df_editado = st.data_editor(
        df_exibir[cols_table],
        column_config=column_config,
        hide_index=True,
        use_container_width=True,
        key="editor_status_acessos"
    )

    # Sincroniza escolhas do editor com st.session_state
    visiveis = df_editado["username"].tolist()
    marcados = df_editado.loc[df_editado["Selecionar"] == True, "username"].tolist()
    anteriores = set(st.session_state[selection_key])
    atualizados = (anteriores - set(visiveis)) | set(marcados)
    st.session_state[selection_key] = sorted(list(atualizados))

    # --- BARRA DE AÇÃO: EXCLUSÃO DE USUÁRIOS SELECIONADOS ---
    selecionados_atual = st.session_state[selection_key]
    if selecionados_atual:
        st.markdown("---")
        st.markdown("### 🗑️ Exclusão de Acesso de Usuários Selecionados")

        current_logged = str(st.session_state.get("username", "")).strip().lower()
        seguros = [
            u for u in selecionados_atual
            if str(u).strip().lower() not in {"ale", current_logged}
        ]

        if len(seguros) < len(selecionados_atual):
            st.warning("⚠️ Nota: O usuário administrador principal e o seu usuário logado foram automaticamente protegidos contra exclusão.")

        if not seguros:
            st.info("Nenhum usuário elegível selecionado para exclusão.")
            return

        st.markdown(
            f"**Você selecionou {len(seguros)} usuário(s) para exclusão de acesso:** "
            + ", ".join([f"`{u}`" for u in seguros])
        )

        confirmado = st.checkbox(
            f"Confirmo que desejo revogar/excluir o acesso de {len(seguros)} usuário(s) permanentemente.",
            key="check_confirm_batch_delete"
        )

        if st.button("🗑️ Excluir Usuários Selecionados", type="primary", disabled=not confirmado):
            removidos = delete_users_batch(engine, seguros)
            if removidos > 0:
                st.success(f"✅ {removidos} usuário(s) excluído(s) com sucesso!")
                st.session_state[selection_key] = []
                st.rerun()
            else:
                st.error("Não foi possível excluir os usuários selecionados.")
