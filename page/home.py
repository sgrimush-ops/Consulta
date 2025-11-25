import streamlit as st

def show_home_page(engine, base_data_path):
    """Cria a interface da página inicial como um Dashboard de atalhos."""

    # --- Cabeçalho ---
    st.title(f"Bem-vindo(a), {st.session_state.get('username', 'Usuário')}!")
    st.markdown("### Painel de Controle (WMS)")
    st.markdown("---") 

    # --- Coleta de Permissões ---
    role = st.session_state.get('role', 'user')
    lojas_do_usuario = st.session_state.get('lojas_acesso', [])
    
    # --- Dicionário de Atalhos (Nome do Botão : Chave da Página) ---
    # Começa com os itens básicos que todos têm acesso
    menu_options = {
        "🔎 Consultar Estoque CD": "Consulta de Estoque CD",
        "🛒 Ofertas Atuais": "Ofertas Atuais",
        "📞 Contato / Chamados": "Contato", 
        "🔐 Alterar Senha": "Alterar Senha"
    }

    # Adiciona Digitação de Pedidos se tiver loja
    if lojas_do_usuario:
        # Inserindo no topo para destaque
        menu_options = {"📝 Digitar Pedidos": "Digitar Pedidos", **menu_options}

    # Adiciona Upload se for MKT ou Admin
    if role in ['admin', 'mkt']:
        menu_options["🚀 Upload Ofertas"] = "Upload Ofertas"

    # Adiciona Menus de Admin
    if role == 'admin':
        menu_options["✅ Aprovação de Pedidos"] = "Aprovação de Pedidos"
        menu_options["👥 Status dos Usuários"] = "Status do Usuário"
        menu_options["⚙️ Administração Geral"] = "Administração"
        menu_options["🔧 Atualizar Sistema"] = "Atualização de Dependências"

    # --- Renderização dos Botões em Grade (Grid) ---
    st.info("Selecione uma opção abaixo para navegar:")
    
    # Define quantas colunas por linha (3 fica visualmente agradável)
    cols_per_row = 3
    
    # Converte o dicionário em lista para iterar
    items = list(menu_options.items())
    
    # Cria as linhas e colunas dinamicamente
    for i in range(0, len(items), cols_per_row):
        cols = st.columns(cols_per_row)
        # Pega um pedaço da lista (batch) para preencher a linha atual
        batch = items[i:i+cols_per_row]
        
        for col, (label, page_key) in zip(cols, batch):
            with col:
                # Botão grande ocupando a largura da coluna
                if st.button(label, use_container_width=True):
                    # Lógica especial para o menu Contato (para lidar com a bolinha vermelha no app.py)
                    if page_key == "Contato":
                        # Procura a chave real no menu lateral que contém a palavra "Contato"
                        # Isso garante que se tiver "Contato (1) 🔴", o link funcione
                        for key in st.session_state.get('sidebar_radio_key', []): # Fallback se não achar
                            pass 
                        # O app.py tem uma lógica que redireciona se a string contiver "Contato"
                        st.session_state['page_key'] = "Contato" 
                    else:
                        st.session_state['page_key'] = page_key
                    
                    st.rerun()

    # --- Rodapé ou Avisos ---
    st.markdown("---")
    if role == 'admin':
        st.caption(f"Você está logado como **Administrador**. Acesso total ao sistema.")
    elif lojas_do_usuario:
        st.caption(f"Você tem acesso de vendas para as lojas: {', '.join(lojas_do_usuario)}")
