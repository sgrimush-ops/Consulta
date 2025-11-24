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
# CONEXÃO DE BANCO
# =========================================================
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

# =========================================================
# FUNÇÕES DE SEGURANÇA
# =========================================================
def make_hashes(password):
    return hashlib.sha256(password.encode()).hexdigest()

def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text

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

def create_db_tables():
    """Cria tabelas essenciais se não existirem."""
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
    except Exception as e:
        pass # Ignora erros de init se tabelas já existem

# =========================================================
# NAVEGAÇÃO E LOGIN
# =========================================================
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

def main():
    create_db_tables()
    
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False

    # Verifica se é primeiro acesso (sem usuários)
    try:
        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
        if count == 0:
            st.warning("Primeiro acesso. Crie o usuário admin.")
            show_admin_page(engine=engine, base_data_path=BASE_DATA_PATH)
            st.stop()
    except:
        pass

    if not st.session_state["logged_in"]:
        login_page() 

    # --- ÁREA LOGADA ---
    st.sidebar.success(f"Logado: {st.session_state['username']}")
    if st.sidebar.button("Logout"):
        update_user_status(st.session_state["username"], "DESLOGADO")
        st.session_state.clear()
        st.rerun()

    # Menu
    paginas = {
        "Home": show_home_page,
        "Consulta de Estoque CD": show_consulta_page,
        "Ofertas Atuais": show_ver_ofertas_page,
        "Alterar Senha": show_mudar_senha_page,
        "Contato": show_contato_page, 
    }

    if st.session_state.get("lojas_acesso"):
        paginas["Digitar Pedidos"] = show_pedidos_page

    if st.session_state.get("role") in ["mkt", "admin"]:
        paginas["Upload Ofertas"] = show_upload_ofertas_page
    
    if st.session_state.get("role") == "admin":
        paginas["Aprovação de Pedidos"] = show_aprovacao_page
        paginas["Status do Usuário"] = show_status_page
        paginas["Administração"] = show_admin_page
        paginas["Atualização de Dependências"] = show_admin_tools

    # Seletor de Página
    page_labels = list(paginas.keys())
    if "page_key" not in st.session_state or st.session_state.page_key not in page_labels:
        st.session_state.page_key = "Home"

    # Função para atualizar o estado quando o radio mudar
    def update_page():
        st.session_state.page_key = st.session_state.nav_radio

    st.sidebar.radio(
        "Navegação:", 
        page_labels, 
        index=page_labels.index(st.session_state.page_key),
        key="nav_radio",
        on_change=update_page
    )
    
    # --- EXECUÇÃO ---
    # Aqui está a correção: Passamos engine e base_data_path para TODAS as páginas
    # Usamos **kwargs para evitar erro se alguma página antiga não aceitar argumentos
    try:
        func = paginas[st.session_state.page_key]
        # Tenta chamar com argumentos
        try:
            func(engine=engine, base_data_path=BASE_DATA_PATH)
        except TypeError:
            # Se a função não aceitar argumentos (páginas antigas), chama sem
            func()
    except Exception as e:
        st.error(f"Erro ao carregar página: {e}")

if __name__ == "__main__":
    main()
