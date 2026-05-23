import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo


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
