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
COLUNAS_LOJAS_PEDIDO = [f"loja_{loja}" for loja in LISTA_LOJAS]

# =========================================================
# FUNÇÕES DE SEGURANÇA
# =========================================================
def make_hashes(password):
    return hashlib.sha256(password.encode()).hexdigest()

def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text

# =========================================================
# CONEXÃO DE BANCO
# =========================================================
@st.cache_resource
def get_engine():
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        st.error("Erro fatal: A variável de ambiente DATABASE_URL não foi encontrada.")
        st.stop()
        
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
        
    return create_engine(db_url, connect_args={"sslmode": "require"}, pool_size=10, max_overflow=5)

engine = get_engine()

# =========================================================
# CRIAÇÃO / MIGRAÇÃO DE TABELAS
# =========================================================
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
            
            conn.execute(text("""
                DELETE FROM contato_chamados 
                WHERE ultimo_update < :seven_days_ago
            """), {"seven_days_ago": seven_days_ago})
            
    except Exception as e:
        if "does not exist" not in str(e):
            st.error(f"Erro ao inicializar o banco de dados: {e}")

# =========================================================
# LOGIN
# =========================================================
def check_login_and_get_roles(username, password):
    with engine.connect() as conn:
        result = conn.execute(text("SELECT password, role, lojas_acesso FROM users WHERE username = :username"),
                              {"username": username.lower()})
        data = result.fetchone()

    if data:
        hashed_password, role, lojas_json = data
        if check_hashes(password, hashed_password):
            try:
                lojas = json.loads(lojas_json) if lojas_json else []
            except:
                lojas = []
            return True, role or "user", lojas
    return False, "user", []

def update_user_status(username, status):
    query = text("""UPDATE users SET ultimo_acesso = :time, status_logado = :status WHERE username = :username""")
    with engine.begin() as conn:
        conn.execute(query, {"time": datetime.now(), "status": status, "username": username.lower()})

# =========================================================
# LOGIN PAGE
# =========================================================
def login_page():
    st.title("🔐 Login do Sistema")
    username = st.text_input("Usuário:").lower()
    senha = st.text_input("Senha:", type="password")

    if st.button("Entrar", type="primary"):
        ok, role, lojas = check_login_and_get_roles(username, senha)
        if ok:
            st.session_state.update({
                "logged_in": True,
                "username": username,
                "role": role,
                "lojas_acesso": lojas
            })
            update_user_status(username, "LOGADO")
            st.rerun()
        else:
            st.error("Usuário ou senha inválidos.")
    st.stop()

# =========================================================
# FIRST RUN
# =========================================================
def check_if_first_run(engine):
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(username) FROM users"))
            return (result.scalar_one_or_none() or 0) == 0
    except Exception as e:
        if "does not exist" in str(e):
            return True
        st.error(f"Erro ao verificar contagem de usuários: {e}")
        return False

# =========================================================
# CONTAGEM DE MENSAGENS
# =========================================================
@st.cache_data(ttl=60)
def get_unread_message_count(_engine, username, role):
    try:
        if role == "admin":
            query = "SELECT COUNT(id) FROM contato_chamados WHERE status = 'Aguardando Retorno'"
            params = {}
        else:
            query = """
                SELECT COUNT(id) 
                FROM contato_chamados 
                WHERE status = 'Respondido' AND usuario_username = :username
            """
            params = {"username": username}

        with _engine.connect() as conn:
            return conn.execute(text(query), params).scalar_one_or_none() or 0
    except:
        return 0

# =========================================================
# MAIN
# =========================================================
def main():
    create_db_tables()
    
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if check_if_first_run(engine):
        st.warning("🚀 Primeiro acesso detectado. Crie o usuário administrador.")
        show_admin_page(engine=engine, base_data_path=BASE_DATA_PATH)
        st.stop()

    if not st.session_state.logged_in:
        login_page()

    st.sidebar.success(f"Logado como: {st.session_state['username']}")

    if st.sidebar.button("Logout"):
        update_user_status(st.session_state["username"], "DESLOGADO")
        st.session_state.clear()
        st.session_state.logged_in = False
        st.rerun()

    username = st.session_state["username"]
    role = st.session_state["role"]

    unread = get_unread_message_count(engine, username, role)
    contato_menu = "Contato" if unread == 0 else f"Contato ({unread}) 🔴"

    # --- MENU ---
    paginas = {
        "Home": show_home_page,
        "Consulta de Estoque CD": show_consulta_page,
        "Ofertas Atuais": show_ver_ofertas_page,
        "Alterar Senha": show_mudar_senha_page,
        contato_menu: show_contato_page,
    }

    if st.session_state.get("lojas_acesso"):
        paginas["Digitar Pedidos"] = show_pedidos_page

    if role == "mkt":
        paginas["Upload Ofertas"] = show_upload_ofertas_page

    if role == "admin":
        paginas["Aprovação de Pedidos"] = show_aprovacao_page
        paginas["Status do Usuário"] = show_status_page
        paginas["Administração"] = show_admin_page
        paginas["Atualização de Dependências"] = show_admin_tools
        if "Upload Ofertas" not in paginas:
            paginas["Upload Ofertas"] = show_upload_ofertas_page

    # Persistência da página selecionada
    if "page_key" not in st.session_state:
        st.session_state.page_key = "Home"

    def on_change():
        st.session_state.page_key = st.session_state.sidebar_choice

    st.sidebar.radio("Selecione a Página:", list(paginas.keys()),
                     key="sidebar_choice", index=list(paginas.keys()).index(st.session_state.page_key),
                     on_change=on_change)

    func = paginas[st.session_state.page_key]

    # ================================================
    # 🔥 PATCH UNIVERSAL — evita todos os TypeError e ImportErrors falsos
    # ================================================
    try:
        func(engine=engine, base_data_path=BASE_DATA_PATH)
    except TypeError:
        func()

if __name__ == "__main__":
    main()
