import os
import time
import pytz
import json
import hashlib
import streamlit as st
from datetime import datetime
from sqlalchemy import create_engine, text

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

# Caminho base de dados (Fallback)
BASE_DATA_PATH = os.getenv("RENDER_DISK_PATH", os.getenv("BASE_DATA_PATH", "data"))


# ==================================
# CONEXÃO COM BANCO
# ==================================
def get_engine():
    conn_string = os.getenv("DATABASE_URL", None)
    if not conn_string:
        st.error("❌ DATABASE_URL não configurada.")
        return None
    return create_engine(conn_string)


# ==================================
# UTILITÁRIOS DE SENHA (HASH)
# ==================================
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    if make_hashes(password) == hashed_text:
        return True
    return False


# ==================================
# LOGIN REAL (COM BANCO DE DADOS)
# ==================================
def check_password():
    """Gerencia o login, verificação no banco e estado da sessão."""
    
    # Se já estiver autenticado, retorna True direto (não mostra formulário)
    if st.session_state.get("authenticated"):
        return True

    # Exibe o formulário de login centralizado
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🔐 Acesso ao Sistema")
        with st.form("login_form"):
            username_input = st.text_input("Usuário")
            password_input = st.text_input("Senha", type="password")
            submitted = st.form_submit_button("Entrar", type="primary")

        if submitted:
            if not username_input or not password_input:
                st.warning("Por favor, preencha usuário e senha.")
                return False
            
            engine = get_engine()
            if not engine:
                return False

            try:
                # Busca o usuário no banco (Case insensitive para username)
                with engine.connect() as conn:
                    query = text("SELECT username, password, role, lojas_acesso FROM users WHERE LOWER(username) = :user")
                    result = conn.execute(query, {"user": username_input.lower()}).fetchone()

                if result:
                    db_user, db_pass, db_role, db_lojas = result
                    
                    # Verifica a senha (HASH)
                    if check_hashes(password_input, db_pass):
                        # --- LOGIN SUCESSO ---
                        st.session_state.authenticated = True
                        st.session_state.username = db_user
                        st.session_state.role = db_role
                        
                        # Carrega as lojas (JSON -> Lista)
                        try:
                            if db_lojas:
                                st.session_state.lojas_acesso = json.loads(db_lojas)
                            else:
                                st.session_state.lojas_acesso = []
                        except:
                            st.session_state.lojas_acesso = []

                        # Atualiza status para LOGADO no banco
                        with engine.begin() as conn:
                            conn.execute(
                                text("UPDATE users SET status_logado = 'LOGADO', ultimo_acesso = NOW() WHERE username = :u"),
                                {"u": db_user}
                            )
                        
                        st.success(f"Bem-vindo, {db_user}!")
                        time.sleep(0.5)
                        st.rerun() # <--- ISSO CORRIGE O BUG DA TELA DUPLA
                        return True
                    else:
                        st.error("Senha incorreta.")
                else:
                    st.error("Usuário não encontrado.")
            
            except Exception as e:
                st.error(f"Erro ao conectar ao banco: {e}")

    return False


# ==================================
# LOGOUT
# ==================================
def do_logout():
    # Atualiza status no banco (opcional, mas recomendado)
    if st.session_state.get("username"):
        try:
            engine = get_engine()
            with engine.begin() as conn:
                conn.execute(
                    text("UPDATE users SET status_logado = 'DESLOGADO' WHERE username = :u"),
                    {"u": st.session_state.username}
                )
        except:
            pass
            
    st.session_state.authenticated = False
    st.session_state.username = None
    st.session_state.role = None
    st.session_state.page_key = "Home"
    st.rerun()


# ==================================
# NAVEGAÇÃO ENTRE PÁGINAS
# ==================================
def app_navigation(engine):
    # Sidebar com informações do usuário
    with st.sidebar:
        st.title("Navegação")
        st.markdown(f"👤 **{st.session_state.get('username', 'Visitante')}**")
        st.markdown(f"🔑 *{st.session_state.get('role', 'user')}*")
        
        if st.button("Sair / Logout", type="secondary"):
            do_logout()
            
        st.markdown("---")

    # Definição das páginas e permissões
    # Dicionário: "Nome": (Função, Lista de Roles Permitidos)
    # Se Lista for None, todos acessam.
    
    all_pages = {
        "Home": (show_home_page, None),
        "Consulta CD": (show_consulta_page, None),
        "Pedidos": (show_pedidos_page, ["user", "admin", "mkt"]),
        "Aprovação de Pedidos": (show_aprovacao_page, ["admin"]),
        "Status Usuários": (show_status_page, ["admin"]),
        "Manutenção Admin": (show_admin_page, ["admin"]),
        "Ferramentas Admin": (show_admin_tools, ["admin"]),
        "Mudar Senha": (show_mudar_senha_page, None),
        "Contato": (show_contato_page, None),
        "Upload Ofertas": (show_upload_ofertas_page, ["admin", "mkt"]),
        "Ver Ofertas": (show_ver_ofertas_page, None),
    }

    # Filtra páginas baseado no Role do usuário
    user_role = st.session_state.get("role", "user")
    
    paginas_disponiveis = {}
    for nome, (func, roles) in all_pages.items():
        if roles is None or user_role in roles:
            paginas_disponiveis[nome] = func

    page_list_labels = list(paginas_disponiveis.keys())

    # Controle da seleção
    if "page_key" not in st.session_state:
        st.session_state.page_key = "Home"
    
    # Se a página salva na sessão não for permitida, volta pra Home
    if st.session_state.page_key not in page_list_labels:
        st.session_state.page_key = "Home"

    # Sidebar Radio
    selected_page = st.sidebar.radio(
        "Ir para:",
        page_list_labels,
        index=page_list_labels.index(st.session_state.page_key),
        key="sidebar_page_selector"
    )

    st.session_state.page_key = selected_page
    selected_page_func = paginas_disponiveis[selected_page]

    # Renderiza a página selecionada
    try:
        selected_page_func(engine=engine, base_data_path=BASE_DATA_PATH)
    except TypeError:
        selected_page_func()
    except Exception as e:
        st.error(f"Erro crítico na página: {e}")


# ==================================
# MAIN
# ==================================
def main():
    # 1. Verifica Login (Se falhar, o script para aqui)
    if not check_password():
        return

    # 2. Se passou, cria conexão e carrega o app
    engine = get_engine()
    app_navigation(engine)


# Executa app
if __name__ == "__main__":
    main()
