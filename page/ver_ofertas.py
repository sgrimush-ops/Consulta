import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import datetime

# =========================================================
# FUNÇÕES DE BANCO DE DADOS
# =========================================================

@st.cache_data(ttl=300) # Cache de 5 minutos
def get_ofertas_atuais(_engine):
    """Busca ofertas onde a data final é hoje ou no futuro."""
    today = datetime.now().date()
    query = text("""
        SELECT 
            id, 
            codigo, 
            produto, 
            oferta, 
            data_inicio, 
            data_final
        FROM ofertas
        WHERE data_final >= :today
        ORDER BY data_inicio ASC
    """)
    
    with _engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"today": today})
    return df

def show_upload_ofertas_page(engine=None, base_data_path=None):
    
    """Atualiza um único campo de uma oferta."""
    try:
        with engine.begin() as conn:
            # Proteção simples contra SQL Injection (garante que 'campo' seja seguro)
            campos_permitidos = ['oferta', 'produto', 'codigo', 'data_inicio', 'data_final']
            if campo not in campos_permitidos:
                st.error(f"Erro: Tentativa de atualizar campo inválido '{campo}'.")
                return
            
            # Formata a data corretamente se for o caso
            if "data" in campo:
                novo_valor = pd.to_datetime(novo_valor).date()
            
            query = text(f"""
                UPDATE ofertas
                SET {campo} = :valor
                WHERE id = :id_oferta
            """)
            conn.execute(query, {"valor": novo_valor, "id_oferta": id_oferta})
        
        # Limpa o cache após a edição
        get_ofertas_atuais.clear()
        
    except Exception as e:
        st.error(f"Erro ao atualizar a oferta: {e}")

def deletar_oferta_do_banco(engine, id_oferta):
    """Deleta uma oferta do banco de dados."""
    try:
        with engine.begin() as conn:
            query = text("DELETE FROM ofertas WHERE id = :id_oferta")
            conn.execute(query, {"id_oferta": id_oferta})
        
        # Limpa o cache após a deleção
        get_ofertas_atuais.clear()
        
    except Exception as e:
        st.error(f"Erro ao deletar a oferta: {e}")

# =========================================================
# INTERFACE DA PÁGINA
# =========================================================

def show_ver_ofertas_page(engine, base_data_path):
    st.title("🛒 Ofertas Atuais")
    
    role = st.session_state.get("role", "user")
    
    # Define se o usuário pode editar
    pode_editar = (role == 'admin') or (role == 'mkt')

    # MUDANÇA: Passa 'engine' como '_engine' (implícito pelo decorador @st.cache_data)
    # Na chamada, usamos o objeto engine normal.
    df_ofertas = get_ofertas_atuais(engine)
    
    if df_ofertas.empty:
        st.info("Nenhuma oferta ativa encontrada no sistema.")
        st.stop()
        
    if pode_editar:
        st.info("Como Admin/Mkt, você pode editar ou deletar ofertas diretamente na tabela abaixo.")
        st.markdown("Para **deletar**, marque a caixa 'Deletar' e clique fora da tabela.")

        # --- Visão de Edição (Admin / Mkt) ---
        
        # Adiciona a coluna de deleção
        df_ofertas["Deletar"] = False
        
        # Reordena colunas para a edição
        colunas = [
            'Deletar', 'id', 'codigo', 'produto', 'oferta', 
            'data_inicio', 'data_final'
        ]
        
        # Configuração das colunas
        config = {
            "id": st.column_config.NumberColumn("ID", disabled=True, format="%d"),
            "codigo": st.column_config.NumberColumn("Código", format="%d"),
            "produto": st.column_config.TextColumn("Produto"),
            "oferta": st.column_config.NumberColumn("Oferta (R$)", format="%.2f"),
            "data_inicio": st.column_config.DateColumn("Início", format="DD/MM/YYYY"),
            "data_final": st.column_config.DateColumn("Final", format="DD/MM/YYYY"),
            "Deletar": st.column_config.CheckboxColumn("Deletar?")
        }

        # Salva o estado atual para comparar mudanças
        if 'df_ofertas_original' not in st.session_state:
            st.session_state.df_ofertas_original = df_ofertas.copy()

        df_editado = st.data_editor(
            df_ofertas,
            column_order=colunas,
            column_config=config,
            hide_index=True,
            use_container_width=True,
            key="editor_ofertas"
        )
        
        # --- Lógica para Salvar Mudanças ---
        if df_editado is not None:
            # 1. Processar Deleções
            ids_para_deletar = df_editado[df_editado["Deletar"] == True]["id"]
            if not ids_para_deletar.empty:
                for id_oferta in ids_para_deletar:
                    deletar_oferta_do_banco(engine, id_oferta)
                st.session_state.df_ofertas_original = None # Força recarregar
                st.success(f"{len(ids_para_deletar)} oferta(s) deletada(s).")
                st.rerun()

            # 2. Processar Edições
            try:
                # Compara se houve mudança
                if not df_editado.equals(st.session_state.df_ofertas_original):
                    # Encontra linhas diferentes
                    # (Lógica simplificada: itera e compara)
                    for index, linha in df_editado.iterrows():
                        if index not in st.session_state.df_ofertas_original.index:
                            continue
                            
                        linha_original = st.session_state.df_ofertas_original.loc[index]
                        
                        # Se marcou deletar, ignora edição
                        if linha['Deletar']: continue

                        for col in ['codigo', 'produto', 'oferta', 'data_inicio', 'data_final']:
                            if linha[col] != linha_original[col]:
                                update_oferta_no_banco(engine, linha['id'], col, linha[col])
                                st.toast(f"Oferta {linha['codigo']} atualizada!", icon="✅")
                    
                    # Atualiza o estado original
                    st.session_state.df_ofertas_original = df_editado.copy()
                    # st.rerun() # Opcional: recarregar para confirmar

            except Exception:
                pass 

    else:
        # --- Visão Somente Leitura (Usuário Padrão) ---
        st.info("Você pode visualizar as ofertas atuais e usar os filtros nas colunas.")
        st.dataframe(
            df_ofertas,
            column_config={
                "id": None, # Esconde o ID
                "codigo": "Código",
                "produto": "Produto",
                "oferta": st.column_config.NumberColumn("Oferta (R$)", format="%.2f"),
                "data_inicio": st.column_config.DateColumn("Início", format="DD/MM/YYYY"),
                "data_final": st.column_config.DateColumn("Final", format="DD/MM/YYYY"),
            },
            hide_index=True,
            use_container_width=True
        )
