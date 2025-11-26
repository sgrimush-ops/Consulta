import streamlit as st
from sqlalchemy import text
import hashlib
import json

# Import das lógicas das "aplicações"
from app import main_app as run_baklizi_app
from page.area_fornecedor import show_area_fornecedor
from page.admin_fornecedor import show_admin_fornecedor_page

# --- Funções de Conexão e Segurança (específicas para o login de fornecedor) ---
@st.cache_resource
def get_main_engine():
    # Esta função é uma cópia da get_engine() do app.py para tornar o main.py independente
    db_url = st.secrets["database"]["url"] # Ajustado para usar st.secrets
    if not db_url:
        st.error("Erro fatal: DATABASE_URL não encontrada.")
        st.stop()
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    return st.create_engine(db_url, connect_args={"sslmode": "require"}, pool_size=5, max_overflow=2)

def make_hashes_fornecedor(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes_fornecedor(password, hashed_text):
    return make_hashes_fornecedor(password) == hashed_text

def check_fornecedor_login(engine, username, password):
    """Verifica as credenciais na tabela de fornecedores."""
    try:
        with engine.connect() as conn:
            query = text("SELECT password, role FROM fornecedores_users WHERE username = :username")
            result = conn.execute(query, {"username": username.lower()})
            data = result.fetchone()
        
        if data:
            hashed_password, role = data
            if check_hashes_fornecedor(password, hashed_password):
                return True, role
    except Exception as e:
        st.error(f"Erro no login: {e}")
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
        st.session_state['fornecedor_logged_in'] = False # Reseta o login
        st.rerun()

def show_fornecedor_login(engine):
    """Exibe o formulário de login para fornecedores."""
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
        paginas_fornecedor["Admin Fornecedores"] = lambda: show_admin_fornecedor_page(engine)

    page_choice = st.sidebar.radio("Navegação Fornecedor:", list(paginas_fornecedor.keys()))
    
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
            # Limpa o estado da sessão para um reinício seguro
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

if __name__ == "__main__":
    main()
