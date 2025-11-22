import os
import time
import pytz
import streamlit as st
from datetime import datetime
from sqlalchemy import create_engine

# --------------------------
# IMPORT DAS PÁGINAS
# --------------------------
from page.home import show_home_page
from page.consulta_estoq_cd import show_consulta_page
from page.pedidos import show_pedidos_page
from page.aprovacao_pedidos import show_aprovacao_page
from page.status_usuarios import show_status_page
from page.admin_maint import show_admin_page
from page.admin_tools import show_admin_tools
from page.mudar_senha import show_mudar_senha_page
from page.contato import show_contato_page
from page.upload_ofertas import show_upload_ofertas_page
from page.ver_ofertas import show_ver_ofertas_page


# ==================================
# CONFIGURAÇÃO GERAL
# ==================================
st.set_page_config(
    page_title="Projeto BAK",
    page_icon="📦",
    layout="wide"
)

# Caminho base de dados
BASE_DATA_PATH = "data"


# ==================================
# LOGIN (simples — segue o seu modelo)
# ==================================
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        with st.form("login_form"):
            username = st.text_input("Usuário")
            password = st.text_input("Senha", type="password")
            submitted = st.form_submit_button("Entrar")

        if submitted:
            if username and password:
                st.session_state.authenticated = True
                return True
            else:
                st.error("Credenciais inválidas.")
                return False
        return False

    return True


# ==================================
# CONEXÃO COM BANCO
# ==================================
def get_engine():
    conn_string = os.getenv("DATABASE_URL", None)
    if not conn_string:
        return None

    return create_engine(conn_string)


# ==================================
# NAVEGAÇÃO ENTRE PÁGINAS
# ==================================
def app_navigation(engine):
    st.sidebar.title("Navegação")

    # Páginas disponíveis
    paginas_disponiveis_labels = {
        "Home": show_home_page,
        "Consulta CD": show_consulta_page,
        "Pedidos": show_pedidos_page,
        "Aprovação de Pedidos": show_aprovacao_page,
        "Status Usuários": show_status_page,
        "Manutenção Admin": show_admin_page,
        "Ferramentas Admin": show_admin_tools,
        "Mudar Senha": show_mudar_senha_page,
        "Contato": show_contato_page,
        "Upload Ofertas": show_upload_ofertas_page,
        "Ver Ofertas": show_ver_ofertas_page,
    }

    page_list_labels = list(paginas_disponiveis_labels.keys())

    # Salva a página selecionada na sessão
    if "page_key" not in st.session_state:
        st.session_state.page_key = "Home"

    # Sidebar
    selected_page = st.sidebar.radio(
        "Selecione a Página:",
        page_list_labels,
        index=page_list_labels.index(st.session_state.page_key)
        if st.session_state.page_key in page_list_labels else 0,
        key="sidebar_page_selector"
    )

    # Atualiza estado
    st.session_state.page_key = selected_page

    # Pega função da página
    selected_page_func = paginas_disponiveis_labels[selected_page]

    # ===============================================================
    # 🔥 Patch universal — evita crash por funções sem parâmetros
    # ===============================================================
    try:
        selected_page_func(engine=engine, base_data_path=BASE_DATA_PATH)
    except TypeError:
        selected_page_func()
    except Exception as e:
        st.error(f"Erro ao renderizar a página: {e}")


# ==================================
# MAIN
# ==================================
def main():
    # Verifica login
    if not check_password():
        return

    # Cria engine do banco
    engine = get_engine()

    # Renderiza navegação
    app_navigation(engine)


# Executa app
if __name__ == "__main__":
    main()
