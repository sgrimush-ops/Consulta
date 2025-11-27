import streamlit as st
from sqlalchemy import text, create_engine
import hashlib
import os

# Import das lógicas das "aplicações"
from app import main_app as run_baklizi_app
from app import create_db_tables
from page.area_fornecedor import show_area_fornecedor
from page.admin_fornecedor import show_admin_fornecedor_page


@st.cache_resource
def get_main_engine():
    db_url = os.getenv("DATABASE_URL")

    if not db_url:
        st.error("Erro: DATABASE_URL não encontrada.")
        st.stop()

    # Substituição necessária para Postgres no Render
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    try:
        return create_engine(
            db_url,
            connect_args={"sslmode": "require"},
            pool_size=5,
            max_overflow=2
        )
    except Exception as e:
        st.error(f"Erro ao criar conexão com BD: {e}")
        st.stop()


def make_hashes_fornecedor(password):
    return hashlib.sha256(str.encode(password)).hexdigest()


def check_hashes_fornecedor(password, hashed_text):
    return make_hashes_fornecedor(password) == hashed_text


def check_fornecedor_login(engine, username, password):
    """Verifica as credenciais na tabela de fornecedores."""
    try:
        with engine.connect() as conn:
            query = text("""
                SELECT password, role
                FROM fornecedores_users
                WHERE username = :username
            """)
            result = conn.execute(query, {"username": username.lower()})
            data = result.fetchone()

        if data:
            hashed_password, role = data
            if check_hashes_fornecedor(password, hashed_password):
                return True, role
    except Exception as e:
        # Mostra o erro específico para debug
        st.error(f"Erro ao verificar credenciais: {str(e)}")
        st.exception(e)
    return False, None

# --- Lógica de Interface ---


def show_main_menu():
    """Exibe o menu principal de seleção de perfil."""
    st.title("Menu de acesso Bakizi")
    st.markdown("""
    Informe se é funcionário da empresa ou se é fornecedor/promotor.
    Caso não tenha acesso, deve solicitar ao administrador do site.
    
    **Contatos (WhatsApp):**
    - Rafael: 55 991578276
    - Alessandro: 55 996308388
    """)
    col1, col2 = st.columns(2)
    if col1.button("Sou Funcionário (Baklizi)", use_container_width=True):
        st.session_state['app_choice'] = 'baklizi'
        st.rerun()
    if col2.button("Sou Fornecedor/Promotor", use_container_width=True):
        st.session_state['app_choice'] = 'fornecedor'
        st.session_state['fornecedor_logged_in'] = False  # Reseta o login
        st.rerun()


def show_fornecedor_login(engine):
    """Exibe o formulário de login para fornecedores."""
    # Garante que a tabela existe antes do login
    from page.admin_fornecedor import create_fornecedores_table
    create_fornecedores_table(engine)

    st.title("Login de Fornecedor/Promotor")
    username = st.text_input("Usuário:", key="forn_user").lower()
    password = st.text_input("Senha:", type="password", key="forn_pass")

    if st.button("Entrar", type="primary"):
        logged_in, role = check_fornecedor_login(engine, username, password)
        if logged_in:
            st.session_state['fornecedor_logged_in'] = True
            st.session_state['fornecedor_username'] = username
            st.session_state['fornecedor_role'] = role
            st.rerun()
        else:
            st.error("Usuário ou senha de fornecedor inválidos.")


def fornecedor_area_main(engine):
    """Área principal para fornecedores logados."""
    username = st.session_state.get('fornecedor_username', '')
    role = st.session_state.get('fornecedor_role', 'fornecedor')
    st.sidebar.success(f"Logado: {username}")

    # Menu da área de fornecedor
    paginas_fornecedor = {
        "Página Inicial": lambda: show_area_fornecedor(),
    }
    if role == 'admin_fornecedor':
        # Nota: show_admin_fornecedor_page precisa do 'engine'
        paginas_fornecedor["Admin Fornecedores"] = (
            lambda: show_admin_fornecedor_page(engine)
        )

    page_choice = st.sidebar.radio(
        "Navegação Fornecedor:",
        list(paginas_fornecedor.keys())
    )

    # Executa a página escolhida
    paginas_fornecedor[page_choice]()

# --- Lógica Principal do Roteador ---


def main():
    st.set_page_config(page_title="Bakizi", layout="wide")

    if 'app_choice' not in st.session_state:
        st.session_state['app_choice'] = None

    if st.session_state['app_choice'] is None:
        show_main_menu()
    elif st.session_state['app_choice'] == 'baklizi':
        # 1. Obter o Engine.
        engine = get_main_engine()

        # 2. Criar as tabelas
        try:
            create_db_tables(engine)
        except Exception as e:
            st.error(f"Erro ao inicializar o banco de dados: {e}")
            st.stop()

        # 3. Executa o app principal
        run_baklizi_app()

    elif st.session_state['app_choice'] == 'fornecedor':
        engine = get_main_engine()
        if not st.session_state.get('fornecedor_logged_in', False):
            show_fornecedor_login(engine)
        else:
            fornecedor_area_main(engine)

    # Botão de voltar unificado
    if st.session_state.get('app_choice') is not None:
        if st.sidebar.button("Voltar ao Menu Principal"):
            st.session_state.clear()
            st.rerun()


if __name__ == "__main__":
    main()
