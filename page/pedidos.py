import streamlit as st
import pandas as pd
import hashlib
from datetime import datetime, date
import json
import os
from sqlalchemy import create_engine, text

# --- Importa as páginas ---
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

# =========================================================
# CONFIGURAÇÕES INICIAIS
# =========================================================
st.set_page_config(page_title="Gestão de Produtos", layout="wide")

BASE_DATA_PATH = os.environ.get("RENDER_DISK_PATH", "data")
os.makedirs(BASE_DATA_PATH, exist_ok=True) 

LISTA_LOJAS = ["001", "002", "003", "004", "005", "006",
               "007", "008", "011", "012", "013", "014", "017", "018"]

# =========================================================
# FUNÇÕES DE SEGURANÇA E BANCO
# =========================================================
def make_hashes(password):
    return hashlib.sha256(password.encode()).hexdigest()

def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text

@st.cache_resource
def get_engine():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        st.error("Erro fatal: DATABASE_URL não encontrada.")
        st.stop()
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    return create_engine(db_url, connect_args={"sslmode": "require"}, pool_size=10, max_overflow=5)

engine = get_engine()

def create_db_tables():
    try:
        with engine.begin() as conn: 
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    password TEXT NOT NULL,
                    ultimo_acesso TIMESTAMP,
                    status_logado TEXT,
                    role TEXT DEFAULT 'user',
                    lojas_acesso TEXT
                )
            """))
            
            lojas_sql_cols = ", ".join([f"loja_{loja} INTEGER DEFAULT 0" for loja in LISTA_LOJAS])
            conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS pedidos_consolidados (
                    id SERIAL PRIMARY KEY, 
                    codigo TEXT NOT NULL,
                    produto TEXT,
                    ean TEXT,
                    embseparacao INTEGER,
                    data_pedido TIMESTAMP,
                    data_aprovacao TIMESTAMP,
                    usuario_pedido TEXT,
                    status_item TEXT,
                    status_aprovacao TEXT DEFAULT 'Pendente',
                    total_cx INTEGER,
                    {lojas_sql_cols}
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS contato_chamados (
                    id SERIAL PRIMARY KEY,
                    usuario_username TEXT REFERENCES users(username),
                    assunto TEXT,
                    data_criacao TIMESTAMP,
                    ultimo_update TIMESTAMP,
                    status TEXT DEFAULT 'Aguardando Retorno' 
                )
            """)) 
            
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS contato_mensagens (
                    id SERIAL PRIMARY KEY,
                    chamado_id INTEGER REFERENCES contato_chamados(id) ON DELETE CASCADE,
                    remetente_username TEXT,
                    mensagem TEXT,
                    data_envio TIMESTAMP
                )
            """))
            
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS ofertas (
                    id SERIAL PRIMARY KEY,
                    codigo INTEGER NOT NULL,
                    produto TEXT,
                    oferta NUMERIC(10, 2),
                    data_inicio DATE NOT NULL,
                    data_final DATE NOT NULL,
                    UNIQUE(codigo, data_inicio, data_final)
                )
            """))
            
            seven_days_ago = (datetime.now() - pd.Timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
            conn.execute(text("DELETE FROM contato_chamados WHERE ultimo_update < :seven_days_ago"), {"seven_days_ago": seven_days_ago})
            
    except Exception as e:
        if "foreign key constraint" not in str(e) and "does not exist" not in str(e):
             st.error(f"Erro ao inicializar BD: {e}")

def check_login_and_get_roles(username, password):
    with engine.connect() as conn:
        query = text("SELECT password, role, lojas_acesso FROM users WHERE username = :username")
        result = conn.execute(query, {"username": username.lower()})
        data = result.fetchone()

    if data:
        hashed_password, role, lojas_acesso_json = data
        if check_hashes(password, hashed_password):
            lojas = []
            if lojas_acesso_json:
                try:
                    lojas = json.loads(lojas_acesso_json)
                except json.JSONDecodeError:
                    lojas = []
            return True, (role or "user"), lojas
    return False, "user", []

def update_user_status(username, status):
    try:
        current_time = datetime.now()
        query = text("UPDATE users SET ultimo_acesso = :time, status_logado = :status WHERE username = :username")
        with engine.begin() as conn:
            conn.execute(query, {"time": current_time, "status": status, "username": username.lower()})
    except Exception:
        pass

def login_page():
    st.title("🔐 Login do Sistema")
    username = st.text_input("Usuário:").lower()
    senha = st.text_input("Senha:", type="password")

    if st.button("Entrar", type="primary"):
        logged_in, role, lojas = check_login_and_get_roles(username, senha)
        if logged_in:
            st.session_state["logged_in"] = True
            st.session_state["username"] = username
            st.session_state["role"] = role
            st.session_state["lojas_acesso"] = lojas
            update_user_status(username, "LOGADO")
            st.rerun()
        else:
            st.error("Usuário ou senha inválidos.")
    st.stop()

def check_if_first_run(engine):
    try:
        with engine.connect() as conn:
            query = text("SELECT COUNT(username) FROM users")
            result = conn.execute(query)
            count = result.scalar_one_or_none() or 0
        return count == 0
    except Exception:
        return True # Assume first run if table doesn't exist or error

@st.cache_data(ttl=60)
def get_unread_message_count(_engine, username, role):
    query_str = ""
    params = {}
    if role == "admin":
        query_str = "SELECT COUNT(id) FROM contato_chamados WHERE status = 'Aguardando Retorno'"
    else:
        query_str = "SELECT COUNT(id) FROM contato_chamados WHERE status = 'Respondido' AND usuario_username = :username"
        params = {"username": username}

    if not query_str: return 0

    try:
        with _engine.connect() as conn:
            result = conn.execute(text(query_str), params)
            return result.scalar_one_or_none() or 0
    except Exception:
        return 0

# =========================================================
# MAIN APP
# =========================================================
def main():
    create_db_tables()
    
    is_first_run = check_if_first_run(engine)

    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False

    if is_first_run:
        st.warning("🚀 Bem-vindo! Primeiro acesso detectado.")
        st.info("Crie o primeiro usuário administrador.")
        # Passa os argumentos explicitamente aqui também
        show_admin_page(engine=engine, base_data_path=BASE_DATA_PATH)
        st.stop() 

    if not st.session_state["logged_in"]:
        login_page() 

    # --- LOGADO ---
    st.sidebar.success(f"Logado: {st.session_state['username']}")

    if st.sidebar.button("Logout"):
        update_user_status(st.session_state["username"], "DESLOGADO")
        st.session_state.clear()
        st.session_state["logged_in"] = False
        st.rerun()

    # Notificações
    username = st.session_state.get("username", "")
    role = st.session_state.get("role", "user")
    unread_count = get_unread_message_count(engine, username, role)
    contato_menu_label = "Contato"
    if unread_count > 0:
        contato_menu_label = f"Contato ({unread_count}) 🔴"

    # Menu
    # Dicionário mapeia Nome -> Função
    paginas = {
        "Home": show_home_page,
        "Consulta de Estoque CD": show_consulta_page,
        "Ofertas Atuais": show_ver_ofertas_page,
        "Alterar Senha": show_mudar_senha_page,
        contato_menu_label: show_contato_page, 
    }

    if st.session_state.get("lojas_acesso"):
        paginas["Digitar Pedidos"] = show_pedidos_page

    if st.session_state.get("role") == "mkt":
        paginas["Upload Ofertas"] = show_upload_ofertas_page
    
    if st.session_state.get("role") == "admin":
        paginas["Aprovação de Pedidos"] = show_aprovacao_page
        paginas["Status do Usuário"] = show_status_page
        paginas["Administração"] = show_admin_page
        paginas["Atualização de Dependências"] = show_admin_tools
        if "Upload Ofertas" not in paginas:
            paginas["Upload Ofertas"] = show_upload_ofertas_page

    # Navegação
    page_labels = list(paginas.keys())

    if "page_key" not in st.session_state:
        st.session_state.page_key = "Home"
    
    # Valida se a página salva ainda é acessível
    # Se for "Contato" com ou sem notificação, ajusta
    current_key = st.session_state.page_key
    if "Contato" in current_key:
        # Tenta encontrar a label atual de contato na lista
        found_contact = next((k for k in page_labels if "Contato" in k), "Home")
        if current_key != found_contact:
            st.session_state.page_key = found_contact
    elif current_key not in page_labels:
        st.session_state.page_key = "Home"

    # Callback para sincronizar radio button com estado
    def update_sidebar():
        st.session_state.page_key = st.session_state["sidebar_selection"]

    # Encontra o índice para o radio button
    try:
        idx = page_labels.index(st.session_state.page_key)
    except ValueError:
        idx = 0

    st.sidebar.radio(
        "Navegação:", 
        page_labels, 
        index=idx,
        on_change=update_sidebar,
        key="sidebar_selection"
    )
    
    # --- EXECUÇÃO DA PÁGINA ---
    # Pega a função correspondente
    page_func = paginas[st.session_state.page_key]
    
    # Executa passando SEMPRE os argumentos padrão
    try:
        page_func(engine=engine, base_data_path=BASE_DATA_PATH)
    except TypeError as e:
        # Fallback se alguma página antiga não aceitar argumentos
        # (Isso evita o erro que você viu, mas o ideal é atualizar todas as páginas)
        st.error(f"Erro ao carregar página: {e}")
        try:
            page_func()
        except Exception as e2:
            st.error(f"Erro crítico na página: {e2}")

if __name__ == "__main__":
    main()
