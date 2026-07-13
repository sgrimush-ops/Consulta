import streamlit as st
import os
from datetime import datetime
from zoneinfo import ZoneInfo


def get_query_parquet_last_update(base_data_path=None):
    """Retorna a data/hora formatada da última atualização do arquivo query.parquet (estoque)."""
    caminhos = []
    if base_data_path:
        caminhos.append(os.path.join(base_data_path, "bdados", "query.parquet"))
        caminhos.append(os.path.join(base_data_path, "query.parquet"))
    caminhos.append(os.path.join("bdados", "query.parquet"))
    caminhos.append("query.parquet")

    latest_time = None
    for caminho in caminhos:
        if os.path.exists(caminho):
            mtime = os.path.getmtime(caminho)
            if latest_time is None or mtime > latest_time:
                latest_time = mtime

    if latest_time:
        dt = datetime.fromtimestamp(latest_time, ZoneInfo("America/Sao_Paulo"))
        return dt.strftime("%d/%m/%Y às %H:%M:%S")
    return None


def show_home_page(engine, base_data_path):
    """Página inicial com atalhos por permissão e relógio (Brasília)."""

    # --- Cabeçalho + Relógio ---
    user = st.session_state.get("username", "Usuário")
    col_title, col_clock = st.columns([3, 1])
    with col_title:
        st.title(f"Bem-vindo(a), {user}!")
        st.markdown("### Painel de Controle (WMS)")
    with col_clock:
        now_brt = datetime.now(ZoneInfo("America/Sao_Paulo"))
        st.caption(f"🕒 Brasília\n{now_brt.strftime('%d/%m/%Y %H:%M:%S')}")
    st.markdown("---")

    # --- Última Atualização de Estoque (query.parquet) ---
    last_update_str = get_query_parquet_last_update(base_data_path)
    if last_update_str:
        st.info(
            f"📦 **Última Atualização do Estoque (`query.parquet`):** {last_update_str}"
        )
    else:
        st.warning("⚠️ Arquivo de estoque (`query.parquet`) ainda não foi importado no sistema.")

    # --- Coleta de Permissões ---
    role = st.session_state.get("role", "user")
    lojas_do_usuario = st.session_state.get("lojas_acesso", [])

    # --- Dicionário de Atalhos (Rótulo : Chave da Página no app.py) ---
    menu_options = {
        "📞 Contato / Chamados": "Contato",
        "🔐 Alterar Senha": "Alterar Senha",
    }

    # Atalhos específicos por perfil
    if lojas_do_usuario:
        menu_options = {
            "🧾 Pedido de Consumo": "Pedido de Consumo",
            "🧾 Pedido por Código (CD)": "Pedido por Código (CD)",
            **menu_options,
        }

    if role == "admin":
        menu_options["✅ Aprovação de Pedidos"] = "Aprovação de Pedidos"
        menu_options["👥 Status dos Usuários"] = "Status do Usuário"
        menu_options["⚙️ Administração"] = "Administração"
        menu_options["📦 Admin Uploads"] = "Admin Uploads"

    # --- Renderização dos Botões em Grade ---
    st.info("Selecione uma opção abaixo para navegar:")
    cols_per_row = 3
    items = list(menu_options.items())
    for i in range(0, len(items), cols_per_row):
        cols = st.columns(cols_per_row)
        for col, (label, page_key) in zip(cols, items[i:i+cols_per_row]):
            with col:
                if st.button(label, use_container_width=True):
                    st.session_state["page_key"] = page_key
                    st.rerun()

    # --- Rodapé ou Avisos ---
    st.markdown("---")
    if role == "admin":
        st.caption(
            "Você está logado como **Administrador**. "
            "Acesso total ao sistema."
        )
    elif lojas_do_usuario:
        st.caption(
            "Você tem acesso de vendas para as lojas: "
            + ", ".join(lojas_do_usuario)
        )
