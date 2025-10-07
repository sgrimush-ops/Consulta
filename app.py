# app.py
import streamlit as st
import sqlite3
import pandas as pd
#import openpyxl as xl
from page.consulta import show_consulta_page 
import hashlib

# A configuração da página deve ser a primeira chamada do Streamlit
st.set_page_config(page_title="Consulta_WMS")

# --- Funções de Segurança (Hashing) ---

def make_hashes(password):
    """Gera um hash SHA256 para a senha."""
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    """Verifica se a senha fornecida corresponde ao hash salvo."""
    return make_hashes(password) == hashed_text

# --- Função do Banco de Dados (Apenas uma e segura!) ---

def check_login(username, password):
    """
    Verifica o usuário e o HASH da senha no banco de dados.
    Esta é a única função de login e é segura.
    """
    try:
        conn = sqlite3.connect('data/database.db')
        c = conn.cursor()
        # 1. Busca o hash da senha pelo nome de usuário
        c.execute("SELECT password FROM users WHERE username = ?", (username,))
        data = c.fetchall()
        conn.close()
        
        if data:
            hashed_password_from_db = data[0][0]
            # 2. Compara o hash da senha digitada com o hash do banco
            return check_hashes(password, hashed_password_from_db)
        
        # Retorna False se o usuário não for encontrado
        return False
        
    except sqlite3.Error as e:
        st.error(f"Erro de banco de dados: {e}")
        return False

# --- Lógica Principal da Aplicação ---

def main():
    """Função principal da aplicação."""
    
    # Inicializa o estado da sessão se não existir
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
        st.session_state['username'] = ''

    # Se o usuário ESTIVER logado, mostra a página de consulta
    if st.session_state['logged_in']:
        st.sidebar.success(f"Logado como: {st.session_state['username']}")
        if st.sidebar.button("Logout"):
            st.session_state['logged_in'] = False
            st.session_state['username'] = ''
            st.rerun()
        
        show_consulta_page()

    # Se o usuário NÃO ESTIVER logado, mostra a tela de login
    else:
        st.title("Sistema de Consulta de Produtos")
        st.subheader("Área de Login")
        username = st.text_input("Nome de Usuário")
        password = st.text_input("Senha", type="password")

        if st.button("Fazer Login"):
            if check_login(username, password):
                st.session_state['logged_in'] = True
                st.session_state['username'] = username
                st.rerun()
            else:
                st.warning("Nome de usuário ou senha incorretos.")

# --- Ponto de Entrada da Aplicação ---

if __name__ == "__main__":
    main()