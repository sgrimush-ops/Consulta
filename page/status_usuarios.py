import streamlit as st
# MUDANÇA: Removido sqlite3
from sqlalchemy import text  # MUDANÇA: Adicionado import text
import pandas as pd
from datetime import datetime

# MUDANÇA: Removido DB_PATH
REFRESH_INTERVAL_MS = 5000  # auto refresh every 5s

# MUDANÇA: Removido @st.cache_data, adicionado 'engine'


def get_user_status_df(engine):
    """
    Busca usuários no DB, calcula o status (com cores) e ordena a lista.
    """
    try:
        # MUDANÇA: Usando 'engine' e 'text()'
        query = text(
            "SELECT username, ultimo_acesso, status_logado FROM users")
        df_users = pd.read_sql_query(query, con=engine)
    except Exception as e:
        st.error(f"Erro ao carregar usuários: {e}")
        return pd.DataFrame()

    if df_users.empty:
        return pd.DataFrame()

    agora = pd.to_datetime(datetime.now())

    # 1. Converte datas (coerce mantém seguro)
    df_users['ultimo_acesso_dt'] = pd.to_datetime(
        df_users['ultimo_acesso'], errors='coerce')

    # 2. Calcula o tempo em segundos; se NaT usa um valor alto (10 anos)
    tempo_total_segundos = (
        agora - df_users['ultimo_acesso_dt']
    ).dt.total_seconds().fillna(315360000)
    df_users['Tempo_Segundos'] = tempo_total_segundos

    # 3. Define Cor e Chave de Ordenação
    df_users['Sort_Key'] = 3
    df_users['Cor'] = "red"
    df_users['Status_Desc'] = "Offline (>24h)"

    # Offline < 24h
    recente_mask = df_users['Tempo_Segundos'] < 86400
    df_users.loc[recente_mask, 'Sort_Key'] = 2
    df_users.loc[recente_mask, 'Cor'] = "orange"
    df_users.loc[recente_mask, 'Status_Desc'] = "Offline (<24h)"

    # Online (somente se status_logado == LOGADO)
    online_mask = df_users['status_logado'] == 'LOGADO'
    df_users.loc[online_mask, 'Sort_Key'] = 1
    df_users.loc[online_mask, 'Cor'] = "green"
    df_users.loc[online_mask, 'Status_Desc'] = "Online"

    # 4. Formata colunas para exibição
    df_users['ultimo_acesso_str'] = (
        df_users['ultimo_acesso_dt'].dt.strftime('%Y-%m-%d %H:%M:%S')
        .fillna("Nenhuma Atividade")
    )

    def format_elapsed(seconds: float) -> str:
        if seconds >= 315360000:
            return "N/A"
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        days = hours // 24
        if days > 0:
            return f"{days}d {hours % 24}h"
        return f"{hours}h {minutes}m"

    df_users['Tempo_Formatado'] = df_users['Tempo_Segundos'].apply(
        format_elapsed)

    # 5. Ordena o DataFrame
    df_users = df_users.sort_values(
        by=['Sort_Key', 'Tempo_Segundos'], ascending=[True, True])

    return df_users

# MUDANÇA: Adicionado 'engine' e 'base_data_path'


def show_status_page(engine, base_data_path):
    """Cria a interface da página de status."""
    st.title("📊 Status dos Usuários Ativos")
    st.markdown(
        "Usuário é considerado **Online** apenas se estiver logado agora. "
        "Caso contrário, exibimos há quanto tempo saiu.")

    # Auto refresh a cada 5s enquanto nesta tela
    st_autorefresh = getattr(st, "autorefresh", None)
    if st_autorefresh:
        st_autorefresh(interval=REFRESH_INTERVAL_MS, key="status_refresh")

    # MUDANÇA: Passando 'engine'
    df_status = get_user_status_df(engine)

    st.markdown("---")

    # --- NOVO DISPLAY COM CORES ---
    # Cabeçalho da Tabela
    col1, col2, col3 = st.columns([1.5, 2, 1.5])
    col1.markdown("**Usuário**")
    col2.markdown("**Último Acesso**")
    col3.markdown("**Status**")

    st.markdown("<hr style='margin-top:0px; margin-bottom:10px;'>",
                unsafe_allow_html=True)

    if not df_status.empty:
        # Itera pelas linhas do DataFrame ordenado
        for index, row in df_status.iterrows():
            cor = row['Cor']

            # Define o texto de status
            status_texto = (
                "Online" if row['Sort_Key'] == 1
                else row['Tempo_Formatado']
            )

            col1_disp, col2_disp, col3_disp = st.columns([1.5, 2, 1.5])

            # Aplica a cor usando HTML/Markdown
            col1_disp.markdown(
                f"<span style='color: {cor};'>{row['username']}</span>",
                unsafe_allow_html=True)
            col2_disp.markdown(
                (
                    f"<span style='color: {cor};'>{row['ultimo_acesso_str']}"
                    f"</span>"
                ),
                unsafe_allow_html=True)
            col3_disp.markdown(
                f"<span style='color: {cor};'>**{status_texto}**</span>",
                unsafe_allow_html=True)

    else:
        st.info("Nenhum usuário encontrado no banco de dados.")
