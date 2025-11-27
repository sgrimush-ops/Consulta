import streamlit as st
import pandas as pd
import hashlib
from datetime import datetime, date
import json
import os
from sqlalchemy import create_engine, text

# --- Importa as páginas ---
from page.home import show_home_page
from page.consulta_cd import show_consulta_cd_page 
from page.aprovacao_pedidos import show_aprovacao_page
from page.status_usuarios import show_status_page
from page.admin_maint import show_admin_page
from page.mudar_senha import show_mudar_senha_page
from page.contato import show_contato_page
from page.upload_ofertas import show_upload_ofertas_page
from page.ver_ofertas import show_ver_ofertas_page
from page.admin_uploads import show_admin_uploads_page 
from page.pedido_cd import show_pedidos_cd_page 
from page.gestao_promo import show_gestao_promo_page 

# =========================================================
# CONFIGURAÇÕES INICIAIS
# =========================================================
st.set_page_config(page_title="Gestão de Produtos", layout="wide")

BASE_DATA_PATH = os.environ.get("RENDER_DISK_PATH", "data")
os.makedirs(BASE_DATA_PATH, exist_ok=True) 

LISTA_LOJAS = ["001", "002", "003", "004", "005", "006", "007", "008", "011", "012", "013", "014", "017", "018"]

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
    # CORREÇÃO: Adicionando codificação explícita
    return hashlib.sha256(password.encode('utf-8')).hexdigest() 

def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text

def check_login_and_get_roles(engine, username, password):
    # A definição aqui está correta (3 argumentos)
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

def create_db_tables(engine):
    # Esta função agora aceita 1 argumento (engine)
    try:
        with engine.begin() as conn: 
            # ... comandos CREATE TABLE (os comandos estão OK)
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
                    codigo_interno TEXT NOT NULL,
                    descricao TEXT,
                    codigo_ean TEXT,
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
                    codigo_interno INTEGER NOT NULL,
                    descricao TEXT,
                    oferta NUMERIC(10, 2),
                    data_inicio DATE NOT NULL,
                    data_final DATE NOT NULL,
                    UNIQUE(codigo_interno, data_inicio, data_final)
                )
            """))
    except Exception as e:
        # Melhoria: avisa se houver erro ao criar tabelas
        st.warning(f"Aviso: Falha ao tentar criar tabelas no BD. {e}")
        pass 

# =========================================================
# NAVEGAÇÃO E LOGIN
# =========================================================
def login_page(engine):
    st.title("🔐 Login do Sistema")
    username = st.text_input("Usuário:").lower()
    senha = st.text_input("Senha:", type="password")

    if st.button("Entrar", type="primary"):
        logged_in, role, lojas = check_login_and_get_roles(engine, username, senha)
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

def main_app():
    engine = get_engine()
    create_db_tables(engine)
    
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False

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
        login_page(engine)

    # --- ÁREA LOGADA ---
    st.sidebar.success(f"Logado: {st.session_state['username']}")
    if st.sidebar.button("Logout"):
        update_user_status(st.session_state["username"], "DESLOGADO")
        st.session_state.clear()
        st.rerun()

    # Notificações
    username = st.session_state.get("username", "")
    role = st.session_state.get("role", "user")
    unread_count = get_unread_message_count(engine, username, role)
    contato_menu_label = "Contato"
    if unread_count > 0:
        contato_menu_label = f"Contato ({unread_count}) 🔴"

    # Menu
    paginas = {
        "Home": lambda: show_home_page(engine, BASE_DATA_PATH),
        "Consulta de Estoque e Mix (CD)": lambda: show_consulta_cd_page(engine, BASE_DATA_PATH), # <-- ADICIONADO
        "Ofertas Atuais": lambda: show_ver_ofertas_page(engine, BASE_DATA_PATH),
        "Alterar Senha": lambda: show_mudar_senha_page(engine, BASE_DATA_PATH),
        "Contato": lambda: show_contato_page(engine, BASE_DATA_PATH), 
    }

    if st.session_state.get("lojas_acesso"):
        # Adiciona as novas páginas de pedido no topo do sub-menu
        paginas["Pedidos de Promoção"] = lambda: show_gestao_promo_page(engine, BASE_DATA_PATH)
        paginas["Pedido por Código (CD)"] = lambda: show_pedidos_cd_page(engine, BASE_DATA_PATH)
        # "Digitar Pedidos (Legado)" foi removido junto com o arquivo pedidos.py

    if st.session_state.get("role") in ["mkt", "admin"]:
        paginas["Upload Ofertas"] = lambda: show_upload_ofertas_page(engine, BASE_DATA_PATH)
    
    if st.session_state.get("role") == "admin":
        paginas["Aprovação de Pedidos"] = lambda: show_aprovacao_page(engine, BASE_DATA_PATH)
        paginas["Status do Usuário"] = lambda: show_status_page(engine, BASE_DATA_PATH)
        paginas["Administração"] = lambda: show_admin_page(engine, BASE_DATA_PATH)
        paginas["Admin Uploads"] = lambda: show_admin_uploads_page(engine) # <-- Adicionada a nova página

    # Seletor de Página
    page_labels = list(paginas.keys())
    if "page_key" not in st.session_state or st.session_state.page_key not in page_labels:
        st.session_state.page_key = "Home"

    # Validação e ajuste da página atual
    current_key = st.session_state.page_key
    if "Contato" in current_key:
        found_contact = next((k for k in page_labels if "Contato" in k), "Home")
        if st.session_state.page_key != found_contact:
             st.session_state.page_key = found_contact
    elif st.session_state.page_key not in page_labels:
        st.session_state.page_key = "Home"

    def update_page():
        st.session_state.page_key = st.session_state.nav_radio

    try:
        current_index = page_labels.index(st.session_state.page_key)
    except ValueError:
        current_index = 0
        st.session_state.page_key = "Home"

    st.sidebar.radio(
        "Navegação:", 
        page_labels, 
        index=current_index,
        key="nav_radio",
        on_change=update_page
    )
    
    # --- EXECUÇÃO ---
    try:
        func = paginas[st.session_state.page_key]
        func()
    except Exception as e:
        st.error(f"Erro ao carregar página: {e}")

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

if __name__ == "__main__":
    main_app()