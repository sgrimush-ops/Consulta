import streamlit as st
import pandas as pd
import os
import threading
import time
import av
import cv2
from sqlalchemy import text

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


def _normalizar_codigo_barras(valor):
    """Mantém apenas dígitos do EAN/DUN para comparação estável."""
    if pd.isna(valor):
        return ""
    return "".join(ch for ch in str(valor).strip() if ch.isdigit())


def _carregar_base_ean_dun():
    """Carrega a base EAN/DUN e retorna colunas padronizadas."""
    parquet_path = os.path.join("bdados", "ean_dun.parquet")
    if not os.path.exists(parquet_path):
        return pd.DataFrame(columns=["cod_consinco", "codigo_ean"])

    df_ean = _normalizar_nomes_colunas(pd.read_parquet(parquet_path))
    if df_ean.empty:
        return pd.DataFrame(columns=["cod_consinco", "codigo_ean"])

    colunas_lower = {str(col).strip().lower(): col for col in df_ean.columns}

    aliases_cod = [
        "cod_consinco",
        "codigoconsinco",
        "codigo produto",
        "código produto",
        "codigo_interno",
        "codigo"
    ]
    aliases_ean = [
        "codigo_ean",
        "ean",
        "ean_dun",
        "dun",
        "codigo de barras",
        "código de barras",
        "codigobarras",
        "codigo_barras"
    ]

    col_cod = next(
        (colunas_lower[a] for a in aliases_cod if a in colunas_lower),
        None
    )
    col_ean = next(
        (colunas_lower[a] for a in aliases_ean if a in colunas_lower),
        None
    )

    if not col_cod or not col_ean:
        return pd.DataFrame(columns=["cod_consinco", "codigo_ean"])

    df_ean = df_ean[[col_cod, col_ean]].copy()
    df_ean.columns = ["cod_consinco", "codigo_ean"]

    df_ean["cod_consinco"] = pd.to_numeric(
        df_ean["cod_consinco"], errors="coerce"
    )
    df_ean = df_ean.dropna(subset=["cod_consinco"]).copy()
    df_ean["cod_consinco"] = df_ean["cod_consinco"].astype(int)

    df_ean["codigo_ean"] = df_ean["codigo_ean"].apply(_normalizar_codigo_barras)
    df_ean = df_ean[df_ean["codigo_ean"] != ""].copy()

    return df_ean.drop_duplicates(subset=["cod_consinco", "codigo_ean"])


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

    # Carregar o arquivo parquet
    parquet_path = os.path.join("bdados", "con5cod.parquet")

    if not os.path.exists(parquet_path):
        st.error(f"Arquivo de dados não encontrado: {parquet_path}")
        st.stop()

    try:
        df_mix = _normalizar_nomes_colunas(pd.read_parquet(parquet_path))
        
        # Mapear colunas novas para nomes esperados
        column_mapping = {
            'codigoconsinco': 'cod_consinco',
            'Código Produto': 'cod_consinco',
            'Codigo Produto': 'cod_consinco',
            'codigo transicao': 'transicao',
            'CODACESSO': 'transicao',
            'Empresa : Produto': 'descricao',
            'Empresa: Produto': 'descricao',
            'embalagem': 'Emb',
            'EmbSeparacao': 'Emb',
            'ltmix': 'Mix',
            'capacidade': 'CapacidadeGondola',
            'CapacidadeGondola': 'CapacidadeGondola'
        }
        
        df_mix.rename(columns=column_mapping, inplace=True)
        
        # Garantir colunas essenciais
        if 'cod_consinco' not in df_mix.columns:
            raise ValueError("Coluna 'cod_consinco' não encontrada")
        if 'descricao' not in df_mix.columns:
            df_mix['descricao'] = 'SEM DESCRIÇÃO'
        if 'transicao' not in df_mix.columns:
            df_mix['transicao'] = 0
        if 'Emb' not in df_mix.columns:
            df_mix['Emb'] = 1
        if 'Mix' not in df_mix.columns:
            df_mix['Mix'] = 'A'
        if 'CapacidadeGondola' not in df_mix.columns:
            df_mix['CapacidadeGondola'] = 0
        
        df_mix['cod_consinco'] = df_mix['cod_consinco'].astype(int)
        df_mix["origem"] = "Parquet"

        # Sobrepor produtos customizados (quando existirem)
        df_custom = get_produtos_custom(engine)
        if not df_custom.empty:
            df_custom["origem"] = "Banco"
            if (
                "Emb" not in df_custom.columns
                and "embalagem" in df_custom.columns
            ):
                df_custom = df_custom.rename(columns={"embalagem": "Emb"})
            if (
                "Mix" not in df_custom.columns
                and "status_mix" in df_custom.columns
            ):
                df_custom = df_custom.rename(columns={"status_mix": "Mix"})

            # Remove do parquet os códigos que existem no banco
            df_mix = df_mix[
                ~df_mix["cod_consinco"].isin(df_custom["cod_consinco"])
            ].copy()
            df_mix = pd.concat([df_mix, df_custom], ignore_index=True)

        # Normalizações básicas
        if "cod_consinco" in df_mix.columns:
            df_mix["cod_consinco"] = pd.to_numeric(
                df_mix["cod_consinco"], errors="coerce"
            )
            df_mix = df_mix.dropna(subset=["cod_consinco"]).copy()
            df_mix["cod_consinco"] = df_mix["cod_consinco"].astype(int)
        if "Mix" in df_mix.columns:
            df_mix["Mix"] = (
                df_mix["Mix"].astype(str).str.strip().str.upper()
            )
            df_mix.loc[
                (df_mix["Mix"].isin(["NAN", "NONE", ""]))
                & (df_mix["origem"] == "Banco"),
                "Mix"
            ] = "A"
        if "Mix" in df_mix.columns:
            df_mix.loc[
                df_mix["Mix"].isin(["NAN", "NONE", ""]),
                "Mix"
            ] = None
        if "transicao" in df_mix.columns:
            df_mix["transicao"] = pd.to_numeric(
                df_mix["transicao"], errors="coerce"
            )

        # Aplicar correções de embalagens do banco de dados
        df_correcoes = get_correcoes_embalagens(engine)
        if not df_correcoes.empty:
            df_mix = df_mix.merge(
                df_correcoes,
                on="cod_consinco",
                how="left"
            )
            # Usar embalagem corrigida se existir (somente para Parquet)
            df_mix["Emb_Original"] = df_mix["Emb"]
            aplicar = (
                df_mix["embalagem_corrigida"].notna()
                & (df_mix["origem"] == "Parquet")
            )
            df_mix.loc[aplicar, "Emb"] = df_mix.loc[
                aplicar, "embalagem_corrigida"
            ]
            df_mix["Tem_Correcao"] = aplicar
            df_mix = df_mix.drop(columns=["embalagem_corrigida"])
        else:
            df_mix["Tem_Correcao"] = False

    except Exception as e:
        st.error(f"Erro ao carregar arquivo de dados: {e}")
        st.stop()

    # Carregar e anexar EAN/DUN para consulta por código de barras
    df_ean = _carregar_base_ean_dun()
    if not df_ean.empty:
        df_ean_first = df_ean.drop_duplicates(
            subset=["cod_consinco"], keep="first"
        )
        df_mix = df_mix.merge(df_ean_first, on="cod_consinco", how="left")
    else:
        df_mix["codigo_ean"] = None

    # Filtrar apenas produtos ativos
    df_mix_ativo = df_mix[df_mix["Mix"] == "A"].copy()
    
    # Exibir estatísticas
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total de Produtos no Mix", len(df_mix_ativo))
    with col2:
        st.metric("Total de Produtos (Incluindo Suspensos)", len(df_mix))
    with col3:
        produtos_suspensos = len(df_mix[df_mix['Mix'] == 'S'])
        st.metric("Produtos Suspensos", produtos_suspensos)
    
    st.markdown("---")
    
    # Tipo de busca
    st.subheader("Buscar Produto")
    tipo_busca = st.radio(
        "Tipo de busca:",
        [
            "Por Código Consinco",
            "Por Código Transição",
            "Por EAN",
            "Por Descrição"
        ],
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
                        st.info(f"**Código Transição (Antigo):** {produto['transicao']}")
                        st.info(
                            "**EAN:** "
                            f"{produto.get('codigo_ean', '-') if pd.notna(produto.get('codigo_ean')) else '-'}"
                        )
                    with col2:
                        st.info(f"**Status:** {'Ativo' if produto['Mix'] == 'A' else 'Suspenso'}")
                        
                        # Mostrar embalagem com indicador se foi corrigida
                        emb_text = f"**Embalagem:** {produto['Emb']} unidades"
                        if produto.get('Tem_Correcao', False):
                            emb_text += f" ⚠️ (Original: {produto.get('Emb_Original', produto['Emb'])})"
                        st.info(emb_text)
                    
                    # Exibir em formato de tabela também
                    st.markdown("### Detalhes Completos")
                    df_display = resultado[[
                        'cod_consinco',
                        'descricao',
                        'transicao',
                        'Mix',
                        'Emb',
                        'codigo_ean'
                    ]].copy()
                    df_display.columns = [
                        'Código Consinco',
                        'Descrição',
                        'Código Transição',
                        'Status',
                        'Embalagem',
                        'EAN'
                    ]
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
                        if (
                            status_norm not in ["A", "S"]
                            and produto.get("origem") == "Banco"
                        ):
                            status_db = get_produto_custom_status(
                                engine, produto.get("cod_consinco")
                            )
                            if status_db:
                                status_norm = (
                                    str(status_db).strip().upper()
                                )
                                produto["Mix"] = status_norm

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
                        st.info(
                            f"**Código Transição (Antigo):** {produto['transicao']}"
                        )
                        st.info(
                            "**EAN:** "
                            f"{produto.get('codigo_ean', '-') if pd.notna(produto.get('codigo_ean')) else '-'}"
                        )
                    with col2:
                        st.info(
                            "**Status:** "
                            f"{'Ativo' if produto['Mix'] == 'A' else 'Suspenso'}"
                        )
                        emb_text = (
                            f"**Embalagem:** {produto['Emb']} unidades"
                        )
                        if produto.get("Tem_Correcao", False):
                            emb_text += (
                                " ⚠️ (Original: "
                                f"{produto.get('Emb_Original', produto['Emb'])})"
                            )
                        st.info(emb_text)

                    st.markdown("### Detalhes Completos")
                    df_display = resultado[[
                        'cod_consinco',
                        'descricao',
                        'transicao',
                        'Mix',
                        'Emb',
                        'codigo_ean'
                    ]].copy()
                    df_display.columns = [
                        "Código Consinco",
                        "Descrição",
                        "Código Transição",
                        "Status",
                        "Embalagem",
                        "EAN"
                    ]
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
                        if (
                            status_norm not in ["A", "S"]
                            and produto.get("origem") == "Banco"
                        ):
                            status_db = get_produto_custom_status(
                                engine, produto.get("cod_consinco")
                            )
                            if status_db:
                                status_norm = (
                                    str(status_db).strip().upper()
                                )
                                produto["Mix"] = status_norm

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
            st.warning(
                "Leitura por câmera indisponível no ambiente atual. "
                "Use o campo manual de EAN."
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
            elif df_ean.empty:
                st.warning(
                    "⚠️ Base EAN/DUN não encontrada ou sem mapeamento válido."
                )
            else:
                codigos_encontrados = df_ean.loc[
                    df_ean["codigo_ean"] == ean_norm,
                    "cod_consinco"
                ].drop_duplicates()

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

                        df_display = resultado[[
                            'cod_consinco',
                            'descricao',
                            'transicao',
                            'Mix',
                            'Emb',
                            'codigo_ean'
                        ]].copy()
                        df_display.columns = [
                            'Código Consinco',
                            'Descrição',
                            'Código Transição',
                            'Status',
                            'Embalagem',
                            'EAN'
                        ]
                        st.dataframe(
                            df_display,
                            use_container_width=True,
                            hide_index=True
                        )
    
    else:  # Busca por descrição
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
                df_display = resultado.copy()
                df_display = df_display[[
                    'cod_consinco',
                    'descricao',
                    'transicao',
                    'Mix',
                    'Emb',
                    'codigo_ean'
                ]]
                df_display.columns = [
                    'Código Consinco',
                    'Descrição',
                    'Código Transição',
                    'Status',
                    'Embalagem',
                    'EAN'
                ]
                
                # Adicionar filtros adicionais
                st.markdown("#### Filtros Adicionais")
                col1, col2 = st.columns(2)
                
                with col1:
                    # Filtro por embalagem
                    embalagens_unicas = sorted(df_display['Embalagem'].unique())
                    filtro_emb = st.multiselect(
                        "Filtrar por Embalagem:",
                        options=embalagens_unicas,
                        default=embalagens_unicas
                    )
                
                if filtro_emb:
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
    
    # Opção de visualizar todos os produtos ativos
    st.markdown("---")
    if st.checkbox("📋 Visualizar todos os produtos do mix ativo"):
        st.markdown("### Todos os Produtos Ativos")
        
        df_display_all = df_mix_ativo.copy()
        df_display_all = df_display_all[[
            'cod_consinco',
            'descricao',
            'transicao',
            'Mix',
            'Emb',
            'codigo_ean'
        ]]
        df_display_all.columns = [
            'Código Consinco',
            'Descrição',
            'Código Transição',
            'Status',
            'Embalagem',
            'EAN'
        ]
        
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
            file_name="mix_completo_ativo.csv",
            mime="text/csv"
        )