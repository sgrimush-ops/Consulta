import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import datetime

# =========================================================
# FUNÇÕES DE BANCO DE DADOS
# =========================================================


@st.cache_data(ttl=300)
def get_ofertas_atuais(_engine):
    """Busca ofertas onde a data final é hoje ou no futuro."""
    today = datetime.now().date()
    # CORREÇÃO: usar `codigo_interno` como nome canônico
    query = text(
        """
        SELECT 
            id, 
            codigo_interno, 
            descricao, 
            oferta, 
            data_inicio, 
            data_final
        FROM ofertas
        WHERE data_final >= :today
        ORDER BY data_inicio ASC
    """
    )

    with _engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"today": today})
    return df


def cleanup_old_ofertas(_engine, older_than_days: int = 1) -> int:
    """Remove ofertas cuja data_final é anterior a hoje - older_than_days.

    Retorna o número de linhas deletadas.
    """
    from datetime import date, timedelta

    threshold = date.today() - timedelta(days=older_than_days)
    try:
        with _engine.begin() as conn:
            delete_q = text(
                "DELETE FROM ofertas WHERE data_final < :threshold RETURNING id"
            )
            result = conn.execute(delete_q, {"threshold": threshold})
            # fetchall para garantir contagem consistente
            rows = result.fetchall()
            deleted = len(rows)
        return deleted
    except Exception:
        return 0


def update_oferta_no_banco(engine, id_oferta, campo, novo_valor):
    """Atualiza um único campo de uma oferta."""
    try:
        with engine.begin() as conn:
            # CORREÇÃO: usar `codigo_interno` como nome canônico
            campos_permitidos = [
                "oferta",
                "descricao",
                "codigo_interno",
                "data_inicio",
                "data_final",
            ]
            if campo not in campos_permitidos:
                st.error(f"Erro: Tentativa de atualizar campo inválido '{campo}'.")
                return

            if "data" in campo:
                novo_valor = pd.to_datetime(novo_valor).date()

            query = text(
                f"""
                UPDATE ofertas
                SET {campo} = :valor
                WHERE id = :id_oferta
            """
            )
            conn.execute(query, {"valor": novo_valor, "id_oferta": id_oferta})

        get_ofertas_atuais.clear()

    except Exception as e:
        st.error(f"Erro ao atualizar a oferta: {e}")


def deletar_oferta_do_banco(engine, id_oferta):
    """Deleta uma oferta do banco de dados."""
    try:
        with engine.begin() as conn:
            query = text("DELETE FROM ofertas WHERE id = :id_oferta")
            conn.execute(query, {"id_oferta": id_oferta})

        get_ofertas_atuais.clear()

    except Exception as e:
        st.error(f"Erro ao deletar a oferta: {e}")


# =========================================================
# INTERFACE DA PÁGINA
# =========================================================


def show_ver_ofertas_page(engine, base_data_path):
    st.title("🛒 Ofertas Atuais")

    role = st.session_state.get("role", "user")
    pode_editar = (role == "admin") or (role == "mkt")

    # Cleanup old offers (rotina diária): remove ofertas com data_final > 1 dia no passado
    try:
        deleted_count = cleanup_old_ofertas(engine, older_than_days=1)
        if deleted_count:
            st.info(f"Removidas {deleted_count} oferta(s) com data_final antiga.")
    except Exception:
        # não bloquear a página se cleanup falhar
        pass

    df_ofertas = get_ofertas_atuais(engine)

    if df_ofertas.empty:
        st.info("Nenhuma oferta ativa encontrada no sistema.")
        st.stop()

    if pode_editar:
        st.info(
            "Como Admin/Mkt, você pode editar ou deletar ofertas diretamente na tabela abaixo."
        )
        st.markdown(
            "Para **deletar**, marque a caixa 'Deletar' e clique fora da tabela."
        )

        df_ofertas["Deletar"] = False

        # Colunas usadas no editor (usar nomes canônicos)
        colunas = [
            "Deletar",
            "id",
            "codigo_interno",
            "descricao",
            "oferta",
            "data_inicio",
            "data_final",
        ]

        config = {
            "id": st.column_config.NumberColumn("ID", disabled=True, format="%d"),
            "codigo_interno": st.column_config.NumberColumn(
                "Cód. Interno", format="%d"
            ),
            "descricao": st.column_config.TextColumn("Descrição"),
            "oferta": st.column_config.NumberColumn("Oferta (R$)", format="%.2f"),
            "data_inicio": st.column_config.DateColumn("Início", format="DD/MM/YYYY"),
            "data_final": st.column_config.DateColumn("Final", format="DD/MM/YYYY"),
            "Deletar": st.column_config.CheckboxColumn("Deletar?"),
        }

        if "df_ofertas_original" not in st.session_state:
            st.session_state.df_ofertas_original = df_ofertas.copy()

        df_editado = st.data_editor(
            df_ofertas,
            column_order=colunas,
            column_config=config,
            hide_index=True,
            use_container_width=True,
            key="editor_ofertas",
        )

        if df_editado is not None:
            ids_para_deletar = df_editado[df_editado["Deletar"]]["id"]
            if not ids_para_deletar.empty:
                for id_oferta in ids_para_deletar:
                    deletar_oferta_do_banco(engine, id_oferta)
                st.session_state.df_ofertas_original = None
                st.success(f"{len(ids_para_deletar)} oferta(s) deletada(s).")
                st.rerun()

            try:
                mudancas = (df_editado != st.session_state.df_ofertas_original).any(
                    axis=1
                )
                linhas_mudadas = df_editado[mudancas]

                if not linhas_mudadas.empty:
                    for index, linha in linhas_mudadas.iterrows():
                        id_mudado = linha["id"]
                        original_linha = st.session_state.df_ofertas_original.loc[index]

                        for col_nome in df_editado.columns:
                            if col_nome == "Deletar" or col_nome == "id":
                                continue

                            if linha[col_nome] != original_linha[col_nome]:
                                update_oferta_no_banco(
                                    engine, id_mudado, col_nome, linha[col_nome]
                                )
                                st.success(
                                    f"Oferta ID {id_mudado} atualizada (Campo: {col_nome})."
                                )

                    st.session_state.df_ofertas_original = None
                    st.rerun()
            except Exception:
                pass

    else:
        st.info("Você pode visualizar as ofertas atuais e usar os filtros nas colunas.")
        st.dataframe(
            df_ofertas,
            column_config={
                "id": None,
                "codigo_interno": "Cód. Interno",
                "descricao": "Descrição",
                "oferta": st.column_config.NumberColumn("Oferta (R$)", format="%.2f"),
                "data_inicio": st.column_config.DateColumn(
                    "Início", format="DD/MM/YYYY"
                ),
                "data_final": st.column_config.DateColumn("Final", format="DD/MM/YYYY"),
            },
            hide_index=True,
            use_container_width=True,
        )
