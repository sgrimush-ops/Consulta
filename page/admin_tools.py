# page/admin_tools.py
import streamlit as st
import pandas as pd
import tempfile
import os
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor, Future
from pathlib import Path
import time

# ----------------------------
# Config
# ----------------------------
st.set_page_config(page_title="Ferramentas de Admin: Upload de Arquivos", layout="wide")

# Diretório persistente para os parquet gerados (ajuste conforme necessário)
OUTPUT_DIR = Path(os.getenv("PROJETOBAK_UPLOADS_DIR", "/tmp/projetobak_uploads"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Thread pool para processar uploads sem bloquear Streamlit
_executor = ThreadPoolExecutor(max_workers=3)


# ----------------------------
# Helpers
# ----------------------------
def init_state():
    if "uploads" not in st.session_state:
        # estrutura por seção: status, file_info, future, parquet_path, error
        st.session_state.uploads = {
            "wms": {"status": "idle", "filename": None, "future": None, "parquet": None, "error": None},
            "historico": {"status": "idle", "filename": None, "future": None, "parquet": None, "error": None},
            "mix": {"status": "idle", "filename": None, "future": None, "parquet": None, "error": None},
        }


def write_uploadedfile_to_disk(uploaded_file, suffix=None):
    """
    Writes a Streamlit UploadedFile to a temporary file on disk and returns the path.
    Uses streaming copy to avoid holding extra copies in Python memory.
    """
    suffix = suffix or Path(uploaded_file.name).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        # UploadedFile has .getbuffer() or .read(); we will use .seek/read in chunks
        uploaded_file.seek(0)
        chunk_size = 1024 * 1024
        while True:
            chunk = uploaded_file.read(chunk_size)
            if not chunk:
                break
            tmp.write(chunk)
        tmp_path = Path(tmp.name)
    return tmp_path


def process_excel_to_parquet(tmp_excel_path: Path, output_basename: str):
    """
    Reads an excel file from disk and writes a parquet file to OUTPUT_DIR.
    Returns the parquet path.
    """
    try:
        # Try reading with pandas
        # If .xlsm present, engine openpyxl is best effort. For enormous files, this may still be slow.
        df = pd.read_excel(tmp_excel_path, engine="openpyxl")
        parquet_path = OUTPUT_DIR / f"{output_basename}.parquet"
        # To reduce memory overhead, write directly with pandas
        df.to_parquet(parquet_path, index=False)
        return str(parquet_path)
    except MemoryError as me:
        raise
    except Exception as e:
        # propagate with traceback
        raise


def background_process(section_key: str, uploaded_file):
    """
    Function executed in background thread to:
    - write upload to disk
    - convert to parquet
    - update session_state (thread-safe via st.session_state assignments in main thread)
    NOTE: modifying st.session_state from background threads can be racey; we only store results and rely on main thread to reflect them.
    """
    # Mark started time for logging
    start_ts = time.time()
    try:
        tmp_path = write_uploadedfile_to_disk(uploaded_file)
        # we store temporary filename for debugging
        result_parquet = process_excel_to_parquet(tmp_path, output_basename=f"{section_key}_{int(start_ts)}")
        # save result into a small state file so main thread can pick it up
        st.session_state.uploads[section_key]["parquet"] = result_parquet
        st.session_state.uploads[section_key]["status"] = "done"
        st.session_state.uploads[section_key]["error"] = None
        st.session_state.uploads[section_key]["tmp_path"] = str(tmp_path)
    except MemoryError:
        st.session_state.uploads[section_key]["status"] = "error"
        st.session_state.uploads[section_key]["error"] = "MemoryError: possível estouro de memória ao processar o arquivo."
        st.session_state.uploads[section_key]["tmp_path"] = str(tmp_path) if 'tmp_path' in locals() else None
        traceback.print_exc()
    except Exception as e:
        st.session_state.uploads[section_key]["status"] = "error"
        st.session_state.uploads[section_key]["error"] = f"{type(e).__name__}: {str(e)}"
        st.session_state.uploads[section_key]["tmp_path"] = str(tmp_path) if 'tmp_path' in locals() else None
        traceback.print_exc()


def start_background(section_key: str, uploaded_file):
    """
    Submete a tarefa ao executor e guarda o Future em session_state.
    """
    st.session_state.uploads[section_key]["status"] = "processing"
    st.session_state.uploads[section_key]["filename"] = uploaded_file.name
    # submit to executor
    future: Future = _executor.submit(background_process, section_key, uploaded_file)
    st.session_state.uploads[section_key]["future"] = future


# ----------------------------
# UI
# ----------------------------
init_state()

st.title("🔧 Ferramentas de Admin: Upload de Arquivos")
st.info("Arraste os arquivos ou use 'Browse files'. O sistema processará em background e salvará Parquet em disco.")

col1, col2 = st.columns([2, 1])

with col1:
    st.header("1. WMS (Estoque CD)")
    wms_file = st.file_uploader("Selecione o WMS (xls, xlsx, xlsm)", type=["xls", "xlsx", "xlsm"], key="uploader_wms")
    if wms_file is not None:
        # botão para iniciar processamento (evita processamento automático repetido)
        if st.button("Processar WMS", key="btn_process_wms"):
            start_background("wms", wms_file)

    upload_state = st.session_state.uploads["wms"]
    if upload_state["status"] == "idle":
        st.info("Arquivo otimizado não encontrado.")
    elif upload_state["status"] == "processing":
        st.warning(f"Processando {upload_state.get('filename')}... (em background)")
        # se houver um future, mostrar se já terminou
        future = upload_state.get("future")
        if future is not None:
            if future.done():
                # result is stored directly by background_process
                if upload_state.get("status") == "done":
                    st.success(f"Processamento finalizado: {upload_state.get('parquet')}")
                elif upload_state.get("status") == "error":
                    st.error(f"Erro: {upload_state.get('error')}")
            else:
                st.progress(0.2)  # progress visual simples; não temos progresso fino sem instrumentação extra
    elif upload_state["status"] == "done":
        st.success(f"Arquivo convertido: {upload_state.get('parquet')}")
        st.write(f"Arquivo origem temporário (para debug): {upload_state.get('tmp_path')}")
    elif upload_state["status"] == "error":
        st.error(f"Erro ao processar: {upload_state.get('error')}")
        if upload_state.get("tmp_path"):
            st.write(f"Arquivo temporário em: {upload_state.get('tmp_path')}")


st.markdown("---")

with col1:
    st.header("2. Histórico de Solicitações")
    hist_file = st.file_uploader("Selecione o Histórico (xls, xlsx, xlsm)", type=["xls", "xlsx", "xlsm"], key="uploader_hist")
    if hist_file is not None:
        if st.button("Processar Histórico", key="btn_process_hist"):
            start_background("historico", hist_file)

    upload_state = st.session_state.uploads["historico"]
    if upload_state["status"] == "idle":
        st.info("Arquivo otimizado não encontrado.")
    elif upload_state["status"] == "processing":
        st.warning(f"Processando {upload_state.get('filename')}... (em background)")
        future = upload_state.get("future")
        if future is not None:
            if future.done():
                if upload_state.get("status") == "done":
                    st.success(f"Processamento finalizado: {upload_state.get('parquet')}")
                elif upload_state.get("status") == "error":
                    st.error(f"Erro: {upload_state.get('error')}")
            else:
                st.progress(0.15)
    elif upload_state["status"] == "done":
        st.success(f"Arquivo convertido: {upload_state.get('parquet')}")
        st.write(f"Arquivo origem temporário (para debug): {upload_state.get('tmp_path')}")
    elif upload_state["status"] == "error":
        st.error(f"Erro ao processar: {upload_state.get('error')}")
        if upload_state.get("tmp_path"):
            st.write(f"Arquivo temporário em: {upload_state.get('tmp_path')}")


st.markdown("---")

with col1:
    st.header("3. Mix Ativo")
    mix_file = st.file_uploader("Selecione o Mix (xls, xlsx)", type=["xls", "xlsx", "xlsm"], key="uploader_mix")
    if mix_file is not None:
        if st.button("Processar Mix", key="btn_process_mix"):
            start_background("mix", mix_file)

    upload_state = st.session_state.uploads["mix"]
    if upload_state["status"] == "idle":
        st.info("Arquivo otimizado não encontrado.")
    elif upload_state["status"] == "processing":
        st.warning(f"Processando {upload_state.get('filename')}... (em background)")
        future = upload_state.get("future")
        if future is not None:
            if future.done():
                if upload_state.get("status") == "done":
                    st.success(f"Processamento finalizado: {upload_state.get('parquet')}")
                elif upload_state.get("status") == "error":
                    st.error(f"Erro: {upload_state.get('error')}")
            else:
                st.progress(0.1)
    elif upload_state["status"] == "done":
        st.success(f"Arquivo convertido: {upload_state.get('parquet')}")
        st.write(f"Arquivo origem temporário (para debug): {upload_state.get('tmp_path')}")
    elif upload_state["status"] == "error":
        st.error(f"Erro ao processar: {upload_state.get('error')}")
        if upload_state.get("tmp_path"):
            st.write(f"Arquivo temporário em: {upload_state.get('tmp_path')}")


with col2:
    st.header("Status & Logs")
    st.write("Status atual das tarefas:")
    st.json(st.session_state.uploads)

    st.write("Local de saída (parquets):")
    st.write(str(OUTPUT_DIR))

    st.markdown("**Imagem de referência (screenshot do crash):**")
    st.write("/mnt/data/b37d9612-adab-40c9-83a2-a1ae457e2a72.png")

# ----------------------------
# Observações finais/boas práticas
# ----------------------------
st.markdown(
    """
    **Observações / próximos passos recomendados**
    - Em produção, rode este app com um worker separado para processamento (ex: enviar jobs a um serviço de fila como Celery/RQ ou a um container separado).
    - Se os arquivos forem consistentemente grandes (> 10-20MB), prefira:
       - Pré-processá-los (remover macros, salvar como .csv no cliente) ou
       - Fazer upload para um storage (S3 / Azure Blob) e processar em worker.
    - Para progresso real (porcentagem de leitura/transformação), instrumente `process_excel_to_parquet`
      para salvar checkpoints (por ex. linhas lidas) em disco, mas isso requer leitura em chunks ou conversão via csv intermediário.
    """
)
