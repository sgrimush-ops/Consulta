import streamlit as st
import os
import pandas as pd
from datetime import datetime

# ================================================
# 🔧 ENGINE FIX — Impede crash durante import no Render
# ================================================
SUPPORTED_EXCEL_TYPES = (".xlsx", ".xlsm")
UNSUPPORTED_TYPES = (".xls",)

def safe_read_excel(uploaded_file):
    ext = uploaded_file.name.lower().split(".")[-1]

    # Impedir crash com XLS
    if uploaded_file.name.lower().endswith(".xls"):
        st.error("❌ Arquivos .xls não são suportados. Converta para .xlsx antes de enviar.")
        return None

    try:
        return pd.read_excel(uploaded_file, engine="openpyxl")
    except Exception as e:
        st.error(f"Erro ao ler Excel com openpyxl: {e}")
        return None


# ================================================
# UTILITÁRIOS
# ================================================
def get_file_info(file_path):
    """Retorna data de modificação legível do arquivo."""
    if os.path.exists(file_path):
        mod_time = os.path.getmtime(file_path)
        return datetime.fromtimestamp(mod_time).strftime('%d/%m/%Y às %H:%M:%S')
    return "Ainda não enviado"


def save_file_as_parquet(uploaded_file, target_path_no_ext):
    """Lê o arquivo Excel e salva como Parquet."""
    try:
        uploaded_file.seek(0)

        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = safe_read_excel(uploaded_file)
            if df is None:
                return False  # erro já exibido

        parquet_path = f"{target_path_no_ext}.parquet"
        df.to_parquet(parquet_path, index=False)

        return True

    except Exception as e:
        st.error(f"Erro ao converter para Parquet: {e}")
        return False


def process_automatic_upload(uploaded_file, base_path_no_ext, file_key):
    """Gerencia upload + conversão automática."""
    if uploaded_file:
        file_id = f"{uploaded_file.name}_{uploaded_file.size}"

        if st.session_state.get(f"processed_{file_key}") != file_id:

            progress_container = st.empty()
            progress_bar = progress_container.progress(0, text="Iniciando upload...")

            try:
                progress_bar.progress(30, text="Lendo arquivo e convertendo para Parquet...")

                if save_file_as_parquet(uploaded_file, base_path_no_ext):

                    progress_bar.progress(100, text="Concluído!")
                    st.session_state[f"processed_{file_key}"] = file_id

                    st.toast(f"Arquivo {file_key.upper()} otimizado com sucesso!", icon="✅")

                    st.rerun()

            except Exception as e:
                st.error(f"Erro no processamento: {e}")

            finally:
                progress_container.empty()


# ================================================
# 🔧 FUNÇÃO PRINCIPAL DA PÁGINA
# ================================================
def show_admin_tools(engine=None, base_data_path=None):
    st.title("🔧 Ferramentas de Admin — Upload de Arquivos")
    st.info("Envie arquivos .xlsx ou .xlsm. O sistema converte automaticamente para .parquet (rápido).")

    # -------------------------------
    # 1. WMS
    # -------------------------------
    st.subheader("1. WMS (Estoque CD)")

    wms_base = os.path.join(base_data_path, "WMS")
    wms_parquet = wms_base + ".parquet"

    if os.path.exists(wms_parquet):
        st.caption(f"📅 Última atualização: **{get_file_info(wms_parquet)}**")
    else:
        st.caption("⚠️ Arquivo otimizado não encontrado.")

    uploaded_wms = st.file_uploader(
        "Selecione o WMS (xlsx, xlsm)",
        type=["xlsx", "xlsm"],
        key="wms_uploader"
    )

    process_automatic_upload(uploaded_wms, wms_base, "wms")

    st.markdown("---")

    # -------------------------------
    # 2. Histórico de Solicitações
    # -------------------------------
    st.subheader("2. Histórico de Solicitações")

    hist_base = os.path.join(base_data_path, "historico_solic")
    hist_parquet = hist_base + ".parquet"

    if os.path.exists(hist_parquet):
        st.caption(f"📅 Última atualização: **{get_file_info(hist_parquet)}**")
    else:
        st.caption("⚠️ Arquivo otimizado não encontrado.")

    uploaded_hist = st.file_uploader(
        "Selecione o Histórico (xlsx, xlsm)",
        type=["xlsx", "xlsm"],
        key="hist_uploader"
    )

    process_automatic_upload(uploaded_hist, hist_base, "hist")

    st.markdown("---")

    # -------------------------------
    # 3. Mix Ativo
    # -------------------------------
    st.subheader("3. Mix Ativo")

    mix_base = os.path.join(base_data_path, "__MixAtivoSistema")
    mix_parquet = mix_base + ".parquet"

    if os.path.exists(mix_parquet):
        st.caption(f"📅 Última atualização: **{get_file_info(mix_parquet)}**")
    else:
        st.caption("⚠️ Arquivo otimizado não encontrado.")

    uploaded_mix = st.file_uploader(
        "Selecione o Mix (xlsx, xlsm)",
        type=["xlsx", "xlsm"],
        key="mix_uploader"
    )

    process_automatic_upload(uploaded_mix, mix_base, "mix")
