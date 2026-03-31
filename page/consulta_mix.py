import streamlit as st
import pandas as pd
import os
import threading
import time
import unicodedata
from sqlalchemy import text

try:
    import av
except Exception:
    av = None

try:
    import cv2
except Exception:
    cv2 = None

try:
    from pyzbar.pyzbar import decode as pyzbar_decode
except Exception:
    pyzbar_decode = None

try:
    from streamlit_webrtc import (
        webrtc_streamer,
        WebRtcMode,
        RTCConfiguration,
    )
except Exception:
    webrtc_streamer = None
    WebRtcMode = None
    RTCConfiguration = None


class EANVideoProcessor:
    """Processa frames da câmera e detecta EAN/DUN em tempo real."""

    def __init__(self):
        self._lock = threading.Lock()
        self.last_ean = None
        self.last_seen_at = None

    def _set_last_ean(self, ean):
        with self._lock:
            self.last_ean = ean
            self.last_seen_at = time.time()

    def get_last_ean(self):
        with self._lock:
            return self.last_ean

    def recv(self, frame):
        if av is None or cv2 is None:
            return frame

        image = frame.to_ndarray(format="bgr24")

        if pyzbar_decode is not None:
            barcodes = pyzbar_decode(image)
            for barcode in barcodes:
                texto_lido = barcode.data.decode("utf-8", errors="ignore")
                ean = "".join(ch for ch in texto_lido if ch.isdigit())
                if ean:
                    self._set_last_ean(ean)

                x, y, w, h = barcode.rect
                cv2.rectangle(image, (x, y), (x + w, y + h), (0, 180, 0), 2)
                cv2.putText(
                    image,
                    texto_lido,
                    (x, max(20, y - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 180, 0),
                    2,
                )

        return av.VideoFrame.from_ndarray(image, format="bgr24")
def _normalizar_nomes_colunas(df):
    """Normaliza nomes de colunas vindas do parquet."""
    df = df.copy()
    df.columns = [str(col).strip() for col in df.columns]
    return df


def _normalizar_chave_coluna(nome_coluna):
    """Normaliza nome de coluna para comparação tolerante a acentos/separadores."""
    texto = unicodedata.normalize("NFKD", str(nome_coluna))
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = texto.lower().strip()
    return "".join(ch for ch in texto if ch.isalnum())


def _normalizar_codigo_barras(valor):
    """Mantém apenas dígitos do EAN/DUN para comparação estável."""
    if pd.isna(valor):
        return ""
    return "".join(ch for ch in str(valor).strip() if ch.isdigit())


def _coluna_tem_dados(df, coluna):
    """Retorna True quando a coluna existe e possui pelo menos um valor util."""
    if coluna not in df.columns:
        return False
    serie = df[coluna].astype(str).str.strip()
    return (~serie.isin(["", "nan", "None", "<NA>"])).any()


def _resolver_caminho_ean_dun(base_data_path=None):
    """Resolve o caminho do ean_dun.parquet para local e Render."""
    caminhos_arquivos = []
    caminhos_diretorios = []

    render_disk_path = os.environ.get("RENDER_DISK_PATH")
    ean_dun_env_path = os.environ.get("EAN_DUN_PARQUET_PATH")
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    if ean_dun_env_path:
        if os.path.isdir(ean_dun_env_path):
            caminhos_diretorios.append(ean_dun_env_path)
        else:
            caminhos_arquivos.append(ean_dun_env_path)

    if base_data_path:
        caminhos_diretorios.extend([
            base_data_path,
            os.path.join(base_data_path, "bdados"),
        ])

    if render_disk_path:
        caminhos_diretorios.extend([
            render_disk_path,
            os.path.join(render_disk_path, "bdados"),
            os.path.join(render_disk_path, "data"),
        ])

    caminhos_diretorios.extend([
        os.path.join(project_root, "bdados"),
        os.path.join(project_root, "data"),
        os.path.join(os.getcwd(), "bdados"),
        os.path.join(os.getcwd(), "data"),
        "bdados",
        "data",
    ])

    nomes_arquivo = [
        "ean_dun.parquet",
        "EAN_DUN.parquet",
        "ean_dun.PARQUET",
    ]

    for diretorio in caminhos_diretorios:
        for nome_arquivo in nomes_arquivo:
            caminhos_arquivos.append(os.path.join(diretorio, nome_arquivo))

    # Remove duplicados preservando ordem.
    caminhos_arquivos = list(dict.fromkeys(caminhos_arquivos))

    for caminho in caminhos_arquivos:
        if os.path.isfile(caminho):
            return os.path.abspath(caminho), caminhos_arquivos

    # Fallback para arquivos com variacao de caixa/nome no mesmo diretorio.
    for diretorio in list(dict.fromkeys(caminhos_diretorios)):
        if not os.path.isdir(diretorio):
            continue
        try:
            for nome in os.listdir(diretorio):
                if nome.lower() == "ean_dun.parquet":
                    caminho = os.path.join(diretorio, nome)
                    if os.path.isfile(caminho):
                        return os.path.abspath(caminho), caminhos_arquivos
        except Exception:
            continue

    # Fallback final: busca recursiva controlada no diretorio do projeto/disco.
    raizes_busca = [project_root]
    if render_disk_path:
        raizes_busca.append(render_disk_path)

    for raiz in list(dict.fromkeys(raizes_busca)):
        if not raiz or not os.path.isdir(raiz):
            continue
        try:
            for atual, _dirs, arquivos in os.walk(raiz):
                for nome in arquivos:
                    if nome.lower() == "ean_dun.parquet":
                        caminho = os.path.join(atual, nome)
                        return os.path.abspath(caminho), caminhos_arquivos
        except Exception:
            continue

    return None, caminhos_arquivos


def _carregar_base_ean_dun(base_data_path=None):
    """Carrega a base EAN/DUN com diagnostico de caminho e colunas."""
    caminho_encontrado, caminhos_testados = _resolver_caminho_ean_dun(base_data_path)
    diagnostico = {
        "caminho_encontrado": caminho_encontrado,
        "caminhos_testados": caminhos_testados,
        "colunas_detectadas": [],
    }

    if not caminho_encontrado:
        return pd.DataFrame(columns=["cod_consinco", "codigo_ean"]), diagnostico

    df_ean = _normalizar_nomes_colunas(pd.read_parquet(caminho_encontrado))
    diagnostico["colunas_detectadas"] = df_ean.columns.astype(str).tolist()
    if df_ean.empty:
        return pd.DataFrame(columns=["cod_consinco", "codigo_ean"]), diagnostico

    colunas_norm = {
        _normalizar_chave_coluna(col): col
        for col in df_ean.columns
    }

    aliases_cod = [
        "cod_consinco",
        "codigoconsinco",
        "codigoproduto",
        "codigointerno",
        "codproduto",
        "codigo produto",
        "código produto",
        "codigo_interno",
        "codigo"
    ]
    aliases_ean = [
        "codigo_ean",
        "ean",
        "ean_dun",
        "eandun",
        "gtin",
        "gtin13",
        "gtin14",
        "dun",
        "codigo de barras",
        "código de barras",
        "codigobarras",
        "codigo_barras"
    ]
    aliases_descricao = [
        "descricao",
        "descricaoproduto",
        "produto",
        "empresa produto",
        "empresa:produto",
    ]
    aliases_transicao = [
        "transicao",
        "codigotransicao",
        "codacesso",
        "codigoacesso",
    ]
    aliases_emb = [
        "emb",
        "embalagem",
        "embseparacao",
    ]
    aliases_mix = [
        "mix",
        "ltmix",
        "statusmix",
        "status_mix",
    ]

    col_cod = next(
        (
            colunas_norm[_normalizar_chave_coluna(a)]
            for a in aliases_cod
            if _normalizar_chave_coluna(a) in colunas_norm
        ),
        None
    )
    col_ean = next(
        (
            colunas_norm[_normalizar_chave_coluna(a)]
            for a in aliases_ean
            if _normalizar_chave_coluna(a) in colunas_norm
        ),
        None
    )

    col_descricao = next(
        (
            colunas_norm[_normalizar_chave_coluna(a)]
            for a in aliases_descricao
            if _normalizar_chave_coluna(a) in colunas_norm
        ),
        None
    )
    col_transicao = next(
        (
            colunas_norm[_normalizar_chave_coluna(a)]
            for a in aliases_transicao
            if _normalizar_chave_coluna(a) in colunas_norm
        ),
        None
    )
    col_emb = next(
        (
            colunas_norm[_normalizar_chave_coluna(a)]
            for a in aliases_emb
            if _normalizar_chave_coluna(a) in colunas_norm
        ),
        None
    )
    col_mix = next(
        (
            colunas_norm[_normalizar_chave_coluna(a)]
            for a in aliases_mix
            if _normalizar_chave_coluna(a) in colunas_norm
        ),
        None
    )

    if not col_cod or not col_ean:
        return pd.DataFrame(columns=["cod_consinco", "codigo_ean"]), diagnostico

    colunas_origem = [col_cod, col_ean]
    rename_map = {
        col_cod: "cod_consinco",
        col_ean: "codigo_ean",
    }
    if col_descricao:
        colunas_origem.append(col_descricao)
        rename_map[col_descricao] = "descricao"
    if col_transicao:
        colunas_origem.append(col_transicao)
        rename_map[col_transicao] = "transicao"
    if col_emb:
        colunas_origem.append(col_emb)
        rename_map[col_emb] = "Emb"
    if col_mix:
        colunas_origem.append(col_mix)
        rename_map[col_mix] = "Mix"

    # Remove duplicidade de colunas de origem quando aliases batem no mesmo nome.
    colunas_origem = list(dict.fromkeys(colunas_origem))

    df_ean = df_ean[colunas_origem].copy().rename(columns=rename_map)

    df_ean["cod_consinco"] = pd.to_numeric(
        df_ean["cod_consinco"], errors="coerce"
    )
    df_ean = df_ean.dropna(subset=["cod_consinco"]).copy()
    df_ean["cod_consinco"] = df_ean["cod_consinco"].astype(int)

    df_ean["codigo_ean"] = df_ean["codigo_ean"].apply(_normalizar_codigo_barras)
    df_ean = df_ean[df_ean["codigo_ean"] != ""].copy()

    if "descricao" in df_ean.columns:
        df_ean["descricao"] = df_ean["descricao"].astype(str).str.strip()
    if "transicao" in df_ean.columns:
        df_ean["transicao"] = pd.to_numeric(df_ean["transicao"], errors="coerce")
    if "Emb" in df_ean.columns:
        df_ean["Emb"] = pd.to_numeric(df_ean["Emb"], errors="coerce")
    if "Mix" in df_ean.columns:
        df_ean["Mix"] = df_ean["Mix"].astype(str).str.strip().str.upper()

    df_ean = df_ean.drop_duplicates(subset=["cod_consinco", "codigo_ean"])
    return df_ean, diagnostico


def _filtrar_codigos_por_ean(df_ean, ean_consulta):
    """Filtra codigos por equivalencia de EAN-13 e GTIN-14."""
    ean_norm = _normalizar_codigo_barras(ean_consulta)
    if not ean_norm or df_ean.empty:
        return pd.Series(dtype="int64")

    serie_ean = df_ean["codigo_ean"].astype(str)
    mascara = serie_ean == ean_norm

    # Equivalencia comum: GTIN-14 com digito indicador + EAN-13.
    if len(ean_norm) == 13:
        mascara = mascara | (
            (serie_ean.str.len() == 14)
            & (serie_ean.str[-13:] == ean_norm)
        )
    elif len(ean_norm) == 14:
        mascara = mascara | (
            (serie_ean.str.len() == 13)
            & (ean_norm[-13:] == serie_ean)
        )

    # Tolerancia adicional para bases com preenchimento por zeros a esquerda.
    ean_sem_zero = ean_norm.lstrip("0")
    if ean_sem_zero:
        mascara = mascara | (serie_ean.str.lstrip("0") == ean_sem_zero)

    return df_ean.loc[mascara, "cod_consinco"].drop_duplicates()


def get_correcoes_embalagens(engine):
    """Busca correções de embalagens do banco de dados."""
    try:
        query = text("""
            SELECT cod_consinco, embalagem_corrigida
            FROM produtos_correcoes
        """)

        with engine.connect() as conn:
            df = pd.read_sql(query, conn)

        return df
    except Exception:
        # Tabela não existe ou erro
        return pd.DataFrame()


def get_produtos_custom(engine):
    """Busca produtos customizados do banco para sobrepor ao parquet."""
    try:
        query = text("""
            SELECT cod_consinco, descricao, transicao,
                   embalagem AS Emb, status_mix AS Mix
            FROM produtos_custom
        """)
        with engine.connect() as conn:
            df = pd.read_sql(query, conn)
        return df
    except Exception:
        return pd.DataFrame()


def get_produto_custom_status(engine, cod_consinco):
    """Busca o status_mix de um produto customizado específico."""
    try:
        query = text(
            "SELECT status_mix FROM produtos_custom WHERE cod_consinco = :cod"
        )
        with engine.connect() as conn:
            return conn.execute(query, {"cod": int(cod_consinco)}).scalar()
    except Exception:
        return None


def show_consulta_mix_page(engine, base_data_path):
    """
    Página para consulta de produtos do mix ativo.
    Permite busca por código Consinco ou por descrição.
    """
    st.title("🔍 Consulta de Mix de Produtos")
    st.markdown("---")
    st.caption("Fonte ativa: ean_dun.parquet | consulta-mix-ean v4")

    # Fonte exclusiva da consulta: ean_dun.parquet
    df_ean, diag_ean = _carregar_base_ean_dun(base_data_path)
    caminho_carga = diag_ean.get("caminho_encontrado") or "nao encontrado"
    st.caption(f"Caminho efetivo da carga: {caminho_carga}")

    if df_ean.empty:
        caminhos_testados = diag_ean.get("caminhos_testados", [])
        colunas_detectadas = diag_ean.get("colunas_detectadas", [])
        st.error(
            "Base ean_dun.parquet nao encontrada ou sem mapeamento de "
            "cod_consinco/codigo_ean."
        )
        st.caption(
            "Defina EAN_DUN_PARQUET_PATH no Render com o caminho absoluto do arquivo "
            "ou garanta o arquivo em /opt/render/project/src/bdados/ean_dun.parquet."
        )
        if caminhos_testados:
            st.caption("Caminhos testados: " + " | ".join(caminhos_testados))
        if colunas_detectadas:
            st.caption(
                "Colunas lidas no arquivo: " + ", ".join(colunas_detectadas)
            )
        st.stop()

    df_mix = df_ean.copy()
    df_mix["origem"] = "EAN_DUN"

    # Garantir colunas esperadas pela tela com fallback seguro.
    if "descricao" not in df_mix.columns:
        df_mix["descricao"] = ""
    if "transicao" not in df_mix.columns:
        df_mix["transicao"] = pd.NA
    if "Emb" not in df_mix.columns:
        df_mix["Emb"] = pd.NA
    if "Mix" not in df_mix.columns:
        df_mix["Mix"] = "A"

    df_mix["Mix"] = (
        df_mix["Mix"]
        .astype(str)
        .str.strip()
        .str.upper()
        .replace({"": "A", "NAN": "A", "NONE": "A", "<NA>": "A"})
    )

    # Filtrar apenas produtos ativos
    df_mix_ativo = df_mix[df_mix["Mix"] == "A"].copy()
    if df_mix_ativo.empty:
        # Se a base nao traz mix/status, considera toda base como ativa.
        df_mix_ativo = df_mix.copy()
    
    # Exibir estatísticas
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total de Produtos no Mix", len(df_mix_ativo))
    with col2:
        st.metric("Total de Produtos (Incluindo Suspensos)", len(df_mix))
    with col3:
        produtos_suspensos = len(df_mix[df_mix['Mix'] == 'S'])
        st.metric("Produtos Suspensos", produtos_suspensos)

    st.caption(
        "Colunas detectadas na base EAN/DUN: "
        + ", ".join(df_mix.columns.astype(str).tolist())
    )
    
    st.markdown("---")
    
    # Tipo de busca (apenas campos realmente existentes na base ean_dun)
    st.subheader("Buscar Produto")
    opcoes_busca = ["Por EAN", "Por Código Consinco"]
    if _coluna_tem_dados(df_mix, "transicao"):
        opcoes_busca.append("Por Código Transição")
    if _coluna_tem_dados(df_mix, "descricao"):
        opcoes_busca.append("Por Descrição")

    tipo_busca = st.radio(
        "Tipo de busca:",
        opcoes_busca,
        horizontal=True
    )
    
    if tipo_busca == "Por Código Consinco":
        # Busca por código
        codigo_busca = st.text_input(
            "Digite o código Consinco:",
            placeholder="Ex: 10480"
        )
        
        if codigo_busca:
            try:
                codigo_int = int(codigo_busca)
                codigo_norm = str(codigo_int)
                cod_series = (
                    df_mix["cod_consinco"]
                    .astype(str)
                    .str.replace(r"\.0$", "", regex=True)
                    .str.strip()
                    .str.lstrip("0")
                )
                resultado_all = df_mix[
                    (df_mix["cod_consinco"] == codigo_int)
                    | (cod_series == codigo_norm)
                ]
                resultado = resultado_all[resultado_all["Mix"] == "A"]
                
                if not resultado.empty:
                    st.success(f"✅ Produto encontrado!")
                    
                    # Exibir informações do produto
                    produto = resultado.iloc[0]
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.info(f"**Código Consinco:** {produto['cod_consinco']}")
                        st.info(f"**Descrição:** {produto['descricao']}")
                        if "transicao" in produto.index:
                            st.info(f"**Código Transição (Antigo):** {produto['transicao']}")
                        st.info(f"**EAN:** {produto.get('codigo_ean', '-')}")
                    with col2:
                        st.info(f"**Status:** {'Ativo' if produto['Mix'] == 'A' else 'Suspenso'}")
                        if "Emb" in produto.index and pd.notna(produto["Emb"]):
                            st.info(f"**Embalagem:** {produto['Emb']} unidades")
                    
                    # Exibir em formato de tabela também
                    st.markdown("### Detalhes Completos")
                    colunas_tabela = [
                        c for c in [
                            "cod_consinco",
                            "descricao",
                            "transicao",
                            "Mix",
                            "Emb",
                            "codigo_ean",
                        ] if c in resultado.columns
                    ]
                    df_display = resultado[colunas_tabela].copy()
                    df_display = df_display.rename(columns={
                        "cod_consinco": "Código Consinco",
                        "descricao": "Descrição",
                        "transicao": "Código Transição",
                        "Mix": "Status",
                        "Emb": "Embalagem",
                        "codigo_ean": "EAN",
                    })
                    st.dataframe(df_display, use_container_width=True, hide_index=True)
                else:
                    if not resultado_all.empty:
                        produto = resultado_all.iloc[0]
                        status_raw = produto.get("Mix")
                        status_norm = (
                            str(status_raw).strip().upper()
                            if pd.notna(status_raw)
                            else None
                        )

                        if status_norm == "S":
                            status_label = "Suspenso"
                        elif status_norm == "A":
                            status_label = "Ativo"
                        else:
                            status_label = "Indefinido"

                        st.warning(
                            "⚠️ Produto encontrado, mas não está ativo. "
                            f"Status: {status_label}."
                        )
                        st.info(
                            f"Origem: {produto.get('origem', 'N/A')}"
                        )
                    else:
                        st.warning(
                            "⚠️ Produto com código "
                            f"{codigo_int} não encontrado."
                        )
            except ValueError:
                st.error("❌ Por favor, digite apenas números no código.")

    elif tipo_busca == "Por Código Transição":
        if "transicao" not in df_mix.columns:
            st.info("Base ean_dun.parquet não possui coluna de transição.")
            st.stop()
        codigo_transicao = st.text_input(
            "Digite o código de transição:",
            placeholder="Ex: 3612"
        )

        if codigo_transicao:
            try:
                codigo_int = int(codigo_transicao)
                codigo_norm = str(codigo_int)
                trans_series = (
                    df_mix["transicao"]
                    .astype(str)
                    .str.replace(r"\.0$", "", regex=True)
                    .str.strip()
                    .str.lstrip("0")
                )
                resultado_all = df_mix[
                    (df_mix["transicao"] == codigo_int)
                    | (trans_series == codigo_norm)
                ]
                resultado = resultado_all[resultado_all["Mix"] == "A"]

                if not resultado.empty:
                    st.success("✅ Produto encontrado!")
                    produto = resultado.iloc[0]

                    col1, col2 = st.columns(2)
                    with col1:
                        st.info(
                            f"**Código Consinco:** {produto['cod_consinco']}"
                        )
                        st.info(f"**Descrição:** {produto['descricao']}")
                        st.info(f"**Código Transição (Antigo):** {produto['transicao']}")
                        st.info(f"**EAN:** {produto.get('codigo_ean', '-')}")
                    with col2:
                        st.info(
                            "**Status:** "
                            f"{'Ativo' if produto['Mix'] == 'A' else 'Suspenso'}"
                        )
                        if "Emb" in produto.index and pd.notna(produto["Emb"]):
                            st.info(f"**Embalagem:** {produto['Emb']} unidades")

                    st.markdown("### Detalhes Completos")
                    colunas_tabela = [
                        c for c in [
                            "cod_consinco",
                            "descricao",
                            "transicao",
                            "Mix",
                            "Emb",
                            "codigo_ean",
                        ] if c in resultado.columns
                    ]
                    df_display = resultado[colunas_tabela].copy().rename(columns={
                        "cod_consinco": "Código Consinco",
                        "descricao": "Descrição",
                        "transicao": "Código Transição",
                        "Mix": "Status",
                        "Emb": "Embalagem",
                        "codigo_ean": "EAN",
                    })
                    st.dataframe(
                        df_display,
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    if not resultado_all.empty:
                        produto = resultado_all.iloc[0]
                        status_raw = produto.get("Mix")
                        status_norm = (
                            str(status_raw).strip().upper()
                            if pd.notna(status_raw)
                            else None
                        )

                        if status_norm == "S":
                            status_label = "Suspenso"
                        elif status_norm == "A":
                            status_label = "Ativo"
                        else:
                            status_label = "Indefinido"

                        st.warning(
                            "⚠️ Produto encontrado, mas não está ativo. "
                            f"Status: {status_label}."
                        )
                        st.info(
                            f"Origem: {produto.get('origem', 'N/A')}"
                        )
                    else:
                        st.warning(
                            "⚠️ Produto com código de transição "
                            f"{codigo_int} não encontrado."
                        )
            except ValueError:
                st.error("❌ Por favor, digite apenas números no código.")

    elif tipo_busca == "Por EAN":
        if "consulta_mix_ean_input" not in st.session_state:
            st.session_state["consulta_mix_ean_input"] = ""

        st.caption(
            "Use a câmera do celular para ler o código em tempo real "
            "ou digite o EAN manualmente."
        )

        dependencias_camera_ok = all(
            [
                av is not None,
                cv2 is not None,
                webrtc_streamer is not None,
                WebRtcMode is not None,
                RTCConfiguration is not None,
                pyzbar_decode is not None,
            ]
        )

        if dependencias_camera_ok:
            usar_camera = st.toggle(
                "Ler EAN pela câmera em tempo real",
                value=False,
                key="consulta_mix_usar_camera",
            )

            if usar_camera:
                st.info(
                    "Aponte a câmera para o código de barras; "
                    "o campo EAN será preenchido automaticamente."
                )

                rtc_config = RTCConfiguration(
                    {
                        "iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]
                    }
                )

                webrtc_ctx = webrtc_streamer(
                    key="consulta_mix_ean_reader",
                    mode=WebRtcMode.SENDRECV,
                    rtc_configuration=rtc_config,
                    media_stream_constraints={
                        "video": {
                            "facingMode": {"ideal": "environment"}
                        },
                        "audio": False,
                    },
                    video_processor_factory=EANVideoProcessor,
                    async_processing=True,
                )

                if webrtc_ctx.video_processor:
                    ean_detectado = webrtc_ctx.video_processor.get_last_ean()
                    if ean_detectado:
                        ean_norm = _normalizar_codigo_barras(ean_detectado)
                        if ean_norm and (
                            st.session_state["consulta_mix_ean_input"]
                            != ean_norm
                        ):
                            st.session_state[
                                "consulta_mix_ean_input"
                            ] = ean_norm
                        if ean_norm:
                            st.success(
                                f"EAN detectado: {ean_norm}"
                            )
        else:
            dependencias_faltantes = []
            if av is None:
                dependencias_faltantes.append("av")
            if cv2 is None:
                dependencias_faltantes.append("opencv-python-headless")
            if webrtc_streamer is None:
                dependencias_faltantes.append("streamlit-webrtc")
            if pyzbar_decode is None:
                dependencias_faltantes.append("pyzbar/libzbar")

            st.warning(
                "Leitura por câmera indisponível no ambiente atual. "
                "Use o campo manual de EAN."
            )
            if dependencias_faltantes:
                st.caption(
                    "Dependencias ausentes ou indisponiveis: "
                    + ", ".join(dependencias_faltantes)
                )

        ean_busca = st.text_input(
            "Digite o EAN lido no celular:",
            placeholder="Ex: 7894900011517",
            key="consulta_mix_ean_input",
        )

        if ean_busca:
            ean_norm = _normalizar_codigo_barras(ean_busca)
            if not ean_norm:
                st.error("❌ Informe um EAN válido (somente dígitos).")
            else:
                codigos_encontrados = _filtrar_codigos_por_ean(
                    df_ean, ean_norm
                )

                if codigos_encontrados.empty:
                    st.warning(
                        f"⚠️ EAN {ean_norm} não encontrado na base ean_dun.parquet."
                    )
                else:
                    resultado_all = df_mix[
                        df_mix["cod_consinco"].isin(codigos_encontrados)
                    ].copy()
                    resultado = resultado_all[resultado_all["Mix"] == "A"].copy()

                    if resultado.empty and not resultado_all.empty:
                        produto = resultado_all.iloc[0]
                        st.warning(
                            "⚠️ Produto encontrado pelo EAN, mas não está ativo no mix."
                        )
                        st.info(
                            f"Código Consinco: {produto.get('cod_consinco')} | "
                            f"Status: {produto.get('Mix')}"
                        )
                    elif resultado.empty:
                        st.warning(
                            "⚠️ Produto encontrado no EAN, mas sem vínculo no mix atual."
                        )
                    else:
                        st.success(
                            f"✅ Encontrado(s) {len(resultado)} produto(s) para o EAN {ean_norm}."
                        )

                        colunas_tabela = [
                            c for c in [
                                "cod_consinco",
                                "descricao",
                                "transicao",
                                "Mix",
                                "Emb",
                                "codigo_ean",
                            ] if c in resultado.columns
                        ]
                        df_display = resultado[colunas_tabela].copy().rename(columns={
                            "cod_consinco": "Código Consinco",
                            "descricao": "Descrição",
                            "transicao": "Código Transição",
                            "Mix": "Status",
                            "Emb": "Embalagem",
                            "codigo_ean": "EAN",
                        })
                        st.dataframe(
                            df_display,
                            use_container_width=True,
                            hide_index=True
                        )
    
    else:  # Busca por descrição
        if "descricao" not in df_mix_ativo.columns:
            st.info("Base ean_dun.parquet não possui coluna de descrição.")
            st.stop()
        descricao_busca = st.text_input(
            "Digite a descrição do produto:",
            placeholder="Ex: CERVEJA"
        )
        
        if descricao_busca and len(descricao_busca) >= 3:
            # Buscar produtos que contenham o termo (case-insensitive)
            mascara = df_mix_ativo['descricao'].str.contains(
                descricao_busca,
                case=False,
                na=False
            )
            resultado = df_mix_ativo[mascara].copy()
            
            if not resultado.empty:
                st.success(f"✅ Encontrado(s) {len(resultado)} produto(s)")
                
                # Renomear colunas para exibição
                colunas_tabela = [
                    c for c in [
                        "cod_consinco",
                        "descricao",
                        "transicao",
                        "Mix",
                        "Emb",
                        "codigo_ean",
                    ] if c in resultado.columns
                ]
                df_display = resultado[colunas_tabela].copy().rename(columns={
                    "cod_consinco": "Código Consinco",
                    "descricao": "Descrição",
                    "transicao": "Código Transição",
                    "Mix": "Status",
                    "Emb": "Embalagem",
                    "codigo_ean": "EAN",
                })
                
                # Adicionar filtros adicionais
                st.markdown("#### Filtros Adicionais")
                col1, col2 = st.columns(2)
                
                with col1:
                    filtro_emb = []
                    if "Embalagem" in df_display.columns:
                        embalagens_unicas = sorted(
                            [v for v in df_display["Embalagem"].dropna().unique()]
                        )
                        if embalagens_unicas:
                            filtro_emb = st.multiselect(
                                "Filtrar por Embalagem:",
                                options=embalagens_unicas,
                                default=embalagens_unicas
                            )
                
                if filtro_emb and "Embalagem" in df_display.columns:
                    df_display = df_display[df_display['Embalagem'].isin(filtro_emb)]
                
                # Exibir resultados
                st.markdown("### Resultados da Busca")
                st.dataframe(
                    df_display,
                    use_container_width=True,
                    hide_index=True,
                    height=400
                )
                
                # Opção de download
                csv = df_display.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 Baixar Resultados (CSV)",
                    data=csv,
                    file_name=f"consulta_mix_{descricao_busca}.csv",
                    mime="text/csv"
                )
            else:
                st.warning(f"⚠️ Nenhum produto encontrado com a descrição '{descricao_busca}' no mix ativo.")
        elif descricao_busca:
            st.info("ℹ️ Digite pelo menos 3 caracteres para realizar a busca.")
    
    # Opção de visualizar todos os produtos da base ean_dun
    st.markdown("---")
    if st.checkbox("📋 Visualizar todos os produtos da base EAN/DUN (exclusivo)"):
        st.markdown("### Todos os Produtos da Base EAN/DUN")
        
        df_display_all = df_mix_ativo.copy()
        colunas_tabela = [
            c for c in [
                "cod_consinco",
                "descricao",
                "transicao",
                "Mix",
                "Emb",
                "codigo_ean",
            ] if c in df_display_all.columns
        ]
        df_display_all = df_display_all[colunas_tabela].copy().rename(columns={
            "cod_consinco": "Código Consinco",
            "descricao": "Descrição",
            "transicao": "Código Transição",
            "Mix": "Status",
            "Emb": "Embalagem",
            "codigo_ean": "EAN",
        })
        
        st.dataframe(
            df_display_all,
            use_container_width=True,
            hide_index=True,
            height=500
        )
        
        # Download de todos os produtos
        csv_all = df_display_all.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 Baixar Lista Completa (CSV)",
            data=csv_all,
            file_name="base_ean_dun.csv",
            mime="text/csv"
        )