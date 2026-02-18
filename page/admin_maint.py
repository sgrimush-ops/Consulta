import streamlit as st
from sqlalchemy import text 
import pandas as pd
import hashlib
import json
import re
from utils.timezone import now_brazil

# --- Configurações Globais ---
LISTA_LOJAS = ["001", "002", "003", "004", "005", "006", "007", "008", "011", "012", "013", "014", "017", "018"]
ROLES_DISPONIVEIS = ["user", "admin"]

# --- Funções Auxiliares de Hashing ---
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

# --- Funções de Manutenção do DB (CRUD de Usuários) ---

# MUDANÇA: Removido @st.cache_data (já estava removido, mas confirmando)
def get_all_users_details(engine):
    """Busca todos os usuários, seus roles, cargos e lojas."""
    try:
        df = pd.read_sql_query(
            text("SELECT username, role, cargo, lojas_acesso FROM users"),
            con=engine
        )
        
        def format_lojas(lojas_json):
            if not lojas_json:
                return "Nenhuma"
            try:
                lojas_list = json.loads(lojas_json)
                return ", ".join(lojas_list)
            except json.JSONDecodeError:
                return "Erro de Formato"
                
        df['lojas_acesso'] = df['lojas_acesso'].apply(format_lojas)
        df['cargo'] = df['cargo'].fillna("")
        df.rename(
            columns={
                'username': 'Usuário',
                'role': 'Role',
                'cargo': 'Cargo',
                'lojas_acesso': 'Lojas'
            },
            inplace=True
        )
        return df
        
    except Exception as e:
        st.error(f"Erro ao carregar usuários: {e}")
        return pd.DataFrame(columns=['Usuário', 'Role', 'Cargo', 'Lojas'])

def add_new_user(engine, username, password, role, cargo, lojas_acesso_list):
    """Adiciona um novo usuário completo ao DB."""
    try:
        hashed_password = make_hashes(password)
        lojas_acesso_json = json.dumps(lojas_acesso_list)
        cargo_value = cargo.strip() if cargo else None
        
        query = text("""
            INSERT INTO users (username, password, role, cargo, lojas_acesso, status_logado) 
            VALUES (:username, :password, :role, :cargo, :lojas, :status)
        """)
        params = {
            "username": username.lower(),
            "password": hashed_password,
            "role": role,
            "cargo": cargo_value,
            "lojas": lojas_acesso_json,
            "status": 'DESLOGADO'
        }
        
        with engine.begin() as conn:
            conn.execute(query, params)
        return True
    
    except Exception as e:
        if "unique constraint" in str(e) or "duplicate key" in str(e):
            st.error(f"Erro: Usuário '{username.lower()}' já existe.")
        else:
            st.error(f"Erro ao adicionar usuário: {e}")
        return False

def delete_user(engine, username):
    """Remove um usuário do DB."""
    try:
        query = text("DELETE FROM users WHERE username = :username")
        
        with engine.begin() as conn:
            result = conn.execute(query, {"username": username.lower()})
            
        return result.rowcount > 0
    except Exception as e:
        st.error(f"Erro ao deletar usuário: {e}")
        return False

def update_user_permissions(engine, username, role, cargo, lojas_acesso_list):
    """Atualiza o role, cargo e as lojas de um usuário."""
    try:
        lojas_acesso_json = json.dumps(lojas_acesso_list)
        cargo_value = cargo.strip() if cargo else None
        
        query = text("""
            UPDATE users SET role = :role, cargo = :cargo, lojas_acesso = :lojas 
            WHERE username = :username
        """)
        params = {
            "role": role,
            "cargo": cargo_value,
            "lojas": lojas_acesso_json,
            "username": username.lower()
        }
        
        with engine.begin() as conn:
            result = conn.execute(query, params)
            
        return result.rowcount > 0
    except Exception as e:
        st.error(f"Erro ao alterar permissões: {e}")
        return False

def update_user_password(engine, username, new_password):
    """Altera a senha de um usuário existente."""
    try:
        hashed_password = make_hashes(new_password)
        
        query = text("UPDATE users SET password = :password WHERE username = :username")
        params = {
            "password": hashed_password,
            "username": username.lower()
        }
        
        with engine.begin() as conn:
            result = conn.execute(query, params)
            
        return result.rowcount > 0
    except Exception as e:
        st.error(f"Erro ao alterar senha: {e}")
        return False


def _normalize_username_from_nome(nome: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]", "", str(nome).lower())
    return normalized[:30]


def get_pending_access_requests(engine):
    try:
        query = text(
            """
            SELECT
                id,
                nome,
                cargo,
                loja,
                senha_sugerida,
                username_sugerido,
                data_solicitacao
            FROM solicitacoes_acesso
            WHERE status = 'Pendente'
            ORDER BY data_solicitacao ASC
            """
        )
        df = pd.read_sql_query(query, con=engine)
        if df.empty:
            return df

        df["cargo"] = df["cargo"].fillna("")
        df["data_solicitacao"] = pd.to_datetime(
            df["data_solicitacao"], errors="coerce"
        ).dt.strftime("%d/%m/%Y %H:%M")

        df.rename(
            columns={
                "id": "ID",
                "nome": "Nome",
                "cargo": "Cargo",
                "loja": "Loja",
                "senha_sugerida": "Senha Sugerida",
                "username_sugerido": "Usuário Sugerido",
                "data_solicitacao": "Data Solicitação",
            },
            inplace=True,
        )
        df["Aprovar"] = False
        df["Reprovar"] = False
        df["Tipo"] = "🟨 Solicitação"
        return df
    except Exception as e:
        st.error(f"Erro ao carregar solicitações: {e}")
        return pd.DataFrame()


def set_request_status(engine, request_id, status, admin_username, observacao=None):
    query = text(
        """
        UPDATE solicitacoes_acesso
        SET status = :status,
            data_analise = :data_analise,
            admin_analise = :admin,
            observacao = :observacao
        WHERE id = :id
        """
    )
    with engine.begin() as conn:
        conn.execute(
            query,
            {
                "status": status,
                "data_analise": now_brazil(),
                "admin": admin_username,
                "observacao": observacao,
                "id": int(request_id),
            },
        )


def process_access_requests(engine, df_requests, admin_username):
    aprovados = 0
    reprovados = 0
    erros = []

    for _, row in df_requests.iterrows():
        request_id = row["ID"]
        aprovar = bool(row.get("Aprovar", False))
        reprovar = bool(row.get("Reprovar", False))

        if not aprovar and not reprovar:
            continue

        if aprovar and reprovar:
            erros.append(f"ID {request_id}: marque apenas Aprovar ou Reprovar.")
            continue

        if reprovar:
            try:
                set_request_status(
                    engine,
                    request_id,
                    "Reprovado",
                    admin_username,
                    "Solicitação reprovada pelo administrador.",
                )
                reprovados += 1
            except Exception as e:
                erros.append(f"ID {request_id}: erro ao reprovar ({e}).")
            continue

        username = str(row.get("Usuário Sugerido", "")).strip().lower()
        if not username:
            username = _normalize_username_from_nome(str(row.get("Nome", "")))

        if not username:
            erros.append(f"ID {request_id}: usuário sugerido inválido.")
            continue

        senha_sugerida = str(row.get("Senha Sugerida", "")).strip()
        cargo = str(row.get("Cargo", "")).strip()
        loja = str(row.get("Loja", "")).strip()

        if not senha_sugerida:
            erros.append(f"ID {request_id}: senha sugerida vazia.")
            continue

        try:
            if add_new_user(
                engine,
                username,
                senha_sugerida,
                "user",
                cargo,
                [loja] if loja else [],
            ):
                set_request_status(
                    engine,
                    request_id,
                    "Aprovado",
                    admin_username,
                    f"Usuário criado: {username}",
                )
                aprovados += 1
            else:
                erros.append(
                    f"ID {request_id}: não foi possível criar usuário '{username}'."
                )
        except Exception as e:
            erros.append(f"ID {request_id}: erro na aprovação ({e}).")

    return aprovados, reprovados, erros

# --- Lógica de Exibição da Página ---

def show_admin_page(engine, base_data_path):
    """Cria a interface do painel de administração."""
    st.title("🛡️ Painel de Administração")
    st.markdown("Gerencie usuários, funções (roles), cargos e acesso às lojas.")
    
    if st.button("🔄 Atualizar Lista de Usuários"):
        # MUDANÇA: Removida a linha get_all_users_details.clear()
        st.rerun()

    # 1. VISUALIZAÇÃO DOS USUÁRIOS
    st.subheader("Usuários Cadastrados")
    df_users = get_all_users_details(engine)
    
    if df_users.empty:
        st.info("Nenhum usuário cadastrado.")
    else:
        sort_col_map = {
            "Nome": "Usuário",
            "Cargo": "Cargo",
            "Lojas": "Lojas",
        }
        sort_choice = st.selectbox(
            "Ordenar por:",
            list(sort_col_map.keys()),
            index=0,
            key="users_sort_choice"
        )
        sort_col = sort_col_map[sort_choice]
        df_sorted = df_users.sort_values(by=sort_col, kind="stable")
        st.dataframe(df_sorted, hide_index=True, use_container_width=True)

    st.markdown("---")

    # 2. ABAS DE AÇÃO
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Adicionar Usuário",
        "Gerenciar Acesso",
        "Alterar Senha",
        "Excluir Usuário",
        "Solicitações de Acesso",
    ])

    # --- ABA 1: Adicionar Usuário ---
    with tab1:
        st.subheader("Adicionar Novo Usuário")
        with st.form("add_user_form", clear_on_submit=True):
            new_username = st.text_input("Novo Login (Username)", key="add_user").lower()
            new_password = st.text_input("Senha Inicial", type="password", key="add_pass")
            new_role = st.selectbox("Função (Role):", ROLES_DISPONIVEIS, index=0, key="add_role")
            new_cargo = st.text_input("Cargo (ex: gerente)", key="add_cargo")
            
            new_lojas = st.multiselect(
                "Quais lojas este usuário pode acessar? (Se for admin, pode deixar em branco)", 
                LISTA_LOJAS, 
                key="add_lojas"
            )
            
            if st.form_submit_button("Criar Usuário"):
                if not (new_username and new_password):
                    st.warning("Preencha pelo menos o Login e a Senha.")
                else:
                    if add_new_user(engine, new_username, new_password, new_role, new_cargo, new_lojas):
                        st.success(f"Usuário '{new_username}' criado com sucesso!")
                        # MUDANÇA: Removida a linha get_all_users_details.clear()
                        st.rerun()

    # --- ABA 2: Gerenciar Acesso (Role e Lojas) ---
    with tab2:
        st.subheader("Gerenciar Acesso (Role, Cargo e Lojas)")
        
        if df_users.empty:
            st.info("Nenhum usuário para gerenciar.")
        else:
            user_list = df_users['Usuário'].tolist()
            current_admin = st.session_state.get('username', 'admin').lower()
            
            if current_admin in user_list:
                user_list.remove(current_admin)
            
            user_to_manage = st.selectbox("Selecione o Usuário para gerenciar:", user_list, key="manage_user_select", index=None)
            
            if user_to_manage:
                user_data = df_users[df_users['Usuário'] == user_to_manage].iloc[0]
                current_role_index = ROLES_DISPONIVEIS.index(user_data['Role']) if user_data['Role'] in ROLES_DISPONIVEIS else 0
                current_cargo = user_data.get('Cargo', "")
                
                try:
                    with engine.connect() as conn:
                        query = text("SELECT lojas_acesso FROM users WHERE username = :username")
                        result = conn.execute(query, {"username": user_to_manage.lower()})
                        lojas_json_raw = result.fetchone()
                    
                    if lojas_json_raw and lojas_json_raw[0]:
                        current_lojas = json.loads(lojas_json_raw[0])
                    else:
                        current_lojas = []
                except Exception as e:
                    current_lojas = []
                    print(f"Erro ao carregar lojas para {user_to_manage}: {e}")

                with st.form("manage_access_form"):
                    st.markdown(f"Editando **{user_to_manage}**")
                    
                    managed_role = st.selectbox(
                        "Nova Função (Role):", 
                        ROLES_DISPONIVEIS, 
                        index=current_role_index, 
                        key="manage_role"
                    )

                    managed_cargo = st.text_input(
                        "Cargo:",
                        value=current_cargo,
                        key="manage_cargo"
                    )
                    
                    managed_lojas = st.multiselect(
                        "Novas Lojas que o usuário pode acessar:", 
                        LISTA_LOJAS, 
                        default=current_lojas,
                        key="manage_lojas"
                    )
                    
                    if st.form_submit_button("Salvar Alterações de Acesso"):
                        if update_user_permissions(engine, user_to_manage, managed_role, managed_cargo, managed_lojas):
                            st.success(f"Permissões de '{user_to_manage}' atualizadas!")
                            # MUDANÇA: Removida a linha get_all_users_details.clear()
                            st.rerun()
                        else:
                            st.error("Falha ao salvar alterações.")

    # --- ABA 3: Alterar Senha ---
    with tab3:
        st.subheader("Alterar Senha de Usuário (Admin)")
        if df_users.empty:
            st.info("Nenhum usuário para gerenciar.")
        else:
            user_list_pass = df_users['Usuário'].tolist()
            user_to_update_pass = st.selectbox("Selecione o Usuário:", user_list_pass, key="update_pass_select", index=None)
            
            if user_to_update_pass:
                with st.form("update_password_form", clear_on_submit=True):
                    st.markdown(f"Alterando senha de **{user_to_update_pass}**")
                    new_pass = st.text_input("Nova Senha", type="password", key="new_pass_input")
                    
                    if st.form_submit_button("Confirmar Alteração de Senha"):
                        if new_pass:
                            if update_user_password(engine, user_to_update_pass, new_pass):
                                st.success(f"Senha do usuário '{user_to_update_pass}' alterada!")
                            else:
                                st.error("Falha ao alterar senha.")
                        else:
                            st.warning("Digite a nova senha.")

    # --- ABA 4: Excluir Usuário ---
    with tab4:
        st.subheader("Excluir Usuário")
        st.warning("ATENÇÃO: A exclusão é permanente.")
        
        if df_users.empty:
            st.info("Nenhum usuário cadastrado.")
        else:
            user_list_del = df_users['Usuário'].tolist()
            current_admin_del = st.session_state.get('username', 'admin').lower()
            
            if current_admin_del in user_list_del:
                user_list_del.remove(current_admin_del)
            
            user_to_delete = st.selectbox("Selecione o Usuário para Excluir:", user_list_del, key="delete_user_select", index=None)

            if user_to_delete:
                st.info("A exclusão é permanente. Deseja continuar?")
                confirm_delete = st.selectbox(
                    "Confirme a exclusão:",
                    ["nao", "sim"],
                    index=0,
                    key="confirm_delete_user"
                )

                if st.button(f"Confirmar Excluir {user_to_delete}", type="primary"):
                    if confirm_delete != "sim":
                        st.warning("Exclusão cancelada. Selecione 'sim' para continuar.")
                    elif delete_user(engine, user_to_delete):
                        st.success(f"Usuário '{user_to_delete}' excluído com sucesso!")
                        # MUDANÇA: Removida a linha get_all_users_details.clear()
                        st.rerun()
                    else:
                        st.error("Falha ao excluir usuário.")

    with tab5:
        st.subheader("Solicitações de Novo Acesso")
        st.caption(
            "Solicitações aparecem destacadas e podem ser aprovadas ou "
            "reprovadas. Ao aprovar, o usuário é criado no sistema."
        )

        df_requests = get_pending_access_requests(engine)

        if df_requests.empty:
            st.info("Não há solicitações pendentes no momento.")
        else:
            df_requests_edit = st.data_editor(
                df_requests,
                hide_index=True,
                use_container_width=True,
                key="admin_requests_editor",
                column_config={
                    "ID": None,
                    "Tipo": st.column_config.TextColumn(
                        "Tipo",
                        disabled=True,
                        width="small",
                    ),
                    "Nome": st.column_config.TextColumn("Nome", disabled=True),
                    "Cargo": st.column_config.TextColumn("Cargo"),
                    "Loja": st.column_config.SelectboxColumn(
                        "Loja",
                        options=LISTA_LOJAS,
                    ),
                    "Senha Sugerida": st.column_config.TextColumn("Senha Sugerida"),
                    "Usuário Sugerido": st.column_config.TextColumn("Usuário Sugerido"),
                    "Data Solicitação": st.column_config.TextColumn(
                        "Data Solicitação",
                        disabled=True,
                    ),
                    "Aprovar": st.column_config.CheckboxColumn("Aprovar", default=False),
                    "Reprovar": st.column_config.CheckboxColumn("Reprovar", default=False),
                },
            )

            if st.button("Processar Solicitações", type="primary"):
                admin_username = st.session_state.get("username", "admin")
                aprovados, reprovados, erros = process_access_requests(
                    engine,
                    df_requests_edit,
                    admin_username,
                )

                if aprovados:
                    st.success(f"{aprovados} solicitação(ões) aprovada(s).")
                if reprovados:
                    st.warning(f"{reprovados} solicitação(ões) reprovada(s).")
                if erros:
                    for erro in erros:
                        st.error(erro)
                if aprovados or reprovados:
                    st.rerun()
