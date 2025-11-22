# page/aprovacao_pedidos.py
import streamlit as st
import pandas as pd
from datetime import datetime
from sqlalchemy import text
from typing import Optional

# --- Página de Aprovação de Pedidos ---
def show_aprovacao_page(engine: Optional[object] = None, base_data_path: Optional[str] = None):
    st.title("✅ Aprovação de Pedidos")
    st.info("Aqui você revisa e aprova ou rejeita pedidos enviados pelos usuários.")

    if engine is None:
        st.warning("Sem conexão com o banco. Esta página ficará em modo somente leitura/demo.")
    
    # ---------- Funções auxiliares ----------
    @st.cache_data(ttl=30)
    def fetch_pending_orders(_engine):
        """Busca pedidos pendentes no banco e retorna DataFrame."""
        if _engine is None:
            # modo demo: retorna DataFrame vazio
            return pd.DataFrame()
        try:
            # Usa _engine para evitar erro de hash
            q = text("""
                SELECT id, codigo, produto, ean, embseparacao, data_pedido, usuario_pedido,
                       status_item, total_cx, status_aprovacao,
                       {cols}
                FROM pedidos_consolidados
                WHERE status_aprovacao = 'Pendente'
                ORDER BY data_pedido ASC
                LIMIT 1000
            """.format(cols=", ".join([f"loja_{l}" for l in [
                "001","002","003","004","005","006","007","008","011","012","013","014","017","018"
            ]])))
            with _engine.connect() as conn:
                df = pd.read_sql(q, conn)
            return df
        except Exception as e:
            st.error(f"Erro ao buscar pedidos pendentes: {e}")
            return pd.DataFrame()

    def update_order_status(_engine, order_ids, new_status, aprover_username=None):
        """Atualiza status_aprovacao de uma lista de pedidos. Retorna (ok, msg)."""
        if _engine is None:
            return False, "Sem conexão com banco."
        try:
            now = datetime.now()
            q = text(f"""
                UPDATE pedidos_consolidados
                SET status_aprovacao = :status, data_aprovacao = :dt_aprov, status_item = :status_item
                WHERE id = :id
            """)
            with _engine.begin() as conn:
                for oid in order_ids:
                    conn.execute(q, {
                        "status": new_status,
                        "dt_aprov": now,
                        "status_item": "Aprovado" if new_status == "Aprovado" else "Rejeitado",
                        "id": int(oid)
                    })
            return True, f"{len(order_ids)} pedido(s) atualizados para '{new_status}'."
        except Exception as e:
            return False, f"Erro ao atualizar pedidos: {e}"

    # ---------- UI: filtros e busca ----------
    st.subheader("Filtros e busca")
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        txt_busca = st.text_input("Buscar por código / produto / usuário (parte):")
    with c2:
        min_date = st.date_input("Pedidos a partir de", value=None)
    with c3:
        if st.button("🔄 Atualizar lista"):
            st.cache_data.clear()
            st.rerun()

    # ---------- Carregar pedidos pendentes ----------
    # Passando engine com underscore se a função esperasse _engine, mas aqui passamos direto
    # O st.cache_data lida com hash, se der erro de hash aqui também, mude a assinatura de fetch_pending_orders para receber _engine
    df_pending = fetch_pending_orders(engine) 

    if df_pending.empty:
        st.info("Nenhum pedido pendente (ou sem conexão).")
        return

    # Aplica busca textual se fornecida
    if txt_busca:
        mask = (
            df_pending["produto"].astype(str).str.contains(txt_busca, case=False, na=False)
        ) | (
            df_pending["codigo"].astype(str).str.contains(txt_busca, na=False)
        ) | (
            df_pending["usuario_pedido"].astype(str).str.contains(txt_busca, case=False, na=False)
        )
        df_pending = df_pending[mask]

    # Aplica filtro de data se informado
    if min_date:
        try:
            df_pending["data_pedido"] = pd.to_datetime(df_pending["data_pedido"], errors="coerce")
            df_pending = df_pending[df_pending["data_pedido"].dt.date >= min_date]
        except Exception:
            pass

    if df_pending.empty:
        st.info("Nenhum pedido corresponde aos filtros.")
        return

    st.markdown(f"**{len(df_pending)}** pedido(s) pendente(s) encontrados.")

    # ---------- Tabela resumida e seleção ----------
    st.subheader("Lista (seleção rápida)")
    # Ajusta colunas exibidas
    display_cols = ["id", "codigo", "produto", "usuario_pedido", "data_pedido", "total_cx", "status_item"]
    available_display = [c for c in display_cols if c in df_pending.columns]
    st.dataframe(df_pending[available_display].sort_values(by="data_pedido", ascending=True), use_container_width=True)

    # Checkboxes para seleção em lote
    st.markdown("Seleção em lote")
    all_ids = df_pending["id"].astype(str).tolist()
    selected_ids = st.multiselect("Selecionar pedidos por ID:", options=all_ids)

    # Ações em lote: Aprovar / Rejeitar
    st.markdown("Ações em lote")
    cola, colb = st.columns(2)
    with cola:
        if st.button("✔️ Aprovar selecionados") and selected_ids:
            ok, msg = update_order_status(engine, selected_ids, "Aprovado", aprover_username=st.session_state.get("username"))
            if ok:
                st.success(msg)
                st.cache_data.clear()  # CORREÇÃO: st.experimental_memo -> st.cache_data
                st.rerun()             # CORREÇÃO: st.experimental_rerun -> st.rerun
            else:
                st.error(msg)
    with colb:
        if st.button("✖️ Rejeitar selecionados") and selected_ids:
            ok, msg = update_order_status(engine, selected_ids, "Rejeitado", aprover_username=st.session_state.get("username"))
            if ok:
                st.success(msg)
                st.cache_data.clear()  # CORREÇÃO
                st.rerun()             # CORREÇÃO
            else:
                st.error(msg)

    # ---------- Ação por item: exibir detalhes e aprovar/rejeitar individualmente ----------
    st.markdown("---")
    st.subheader("Revisar pedido individualmente")

    # Permite selecionar um pedido para revisão detalhada
    sel_id = st.selectbox("Selecione ID do pedido para revisar:", options=[""] + all_ids)
    if sel_id:
        try:
            sel_id_int = int(sel_id)
            row = df_pending[df_pending["id"] == sel_id_int].iloc[0]
            st.markdown("### Detalhes do Pedido")
            st.write(f"**ID:** {row['id']}")
            st.write(f"**Código:** {row.get('codigo', '')} — **Produto:** {row.get('produto', '')}")
            st.write(f"**Usuário:** {row.get('usuario_pedido', '')}")
            st.write(f"**Data pedido:** {row.get('data_pedido', '')}")
            st.write(f"**Total CX:** {row.get('total_cx', '')}")
            st.write("**Distribuição por loja:**")
            loja_cols = [c for c in df_pending.columns if c.startswith("loja_")]
            if loja_cols:
                df_lojas = pd.DataFrame([{c: row.get(c, 0) for c in loja_cols}])
                st.table(df_lojas.T.rename(columns={0: "Qtd"}))
            # Botões de ação individual
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✔️ Aprovar pedido", key=f"aprovar_{sel_id}"):
                    ok, msg = update_order_status(engine, [sel_id_int], "Aprovado", aprover_username=st.session_state.get("username"))
                    if ok:
                        st.success(msg)
                        st.cache_data.clear() # CORREÇÃO
                        st.rerun()            # CORREÇÃO
                    else:
                        st.error(msg)
            with col2:
                if st.button("✖️ Rejeitar pedido", key=f"rejeitar_{sel_id}"):
                    ok, msg = update_order_status(engine, [sel_id_int], "Rejeitado", aprover_username=st.session_state.get("username"))
                    if ok:
                        st.success(msg)
                        st.cache_data.clear() # CORREÇÃO
                        st.rerun()            # CORREÇÃO
                    else:
                        st.error(msg)
        except Exception as e:
            st.error(f"Erro ao carregar pedido selecionado: {e}")

    st.markdown("---")
    st.caption("Dica: selecione múltiplos IDs para aprovar/rejeitar em lote. As ações são registradas com timestamp.")
