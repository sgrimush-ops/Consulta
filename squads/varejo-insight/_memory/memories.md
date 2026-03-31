# Memórias — Varejo Insight Squad

## Aprendizados de Deploy no Render (2026-03-31)

### Parquets não estão no Git
- `ean_dun.parquet` e `query.parquet` **não são commitados** no repositório.
- Devem ser carregados via **Admin Uploads** (`page/admin_uploads.py`) para o disco persistente do Render.
- O cwd do container Render pode ser diferente do caminho local; use resolução por múltiplos candidatos.

### Resolução de Caminho
```python
# Ordem de prioridade para encontrar Parquet no Render
1. Variável de ambiente (ex.: EAN_DUN_PARQUET_PATH)
2. pathlib.Path(__file__).parent.parent / 'bdados' / arquivo
3. RENDER_DISK_PATH / 'bdados' / arquivo
4. /opt/render/project/src/bdados/ arquivo
5. cwd / 'bdados' / arquivo
```

### Imports Opcionais Obrigatórios
- `av`, `cv2`, `pyzbar`, `streamlit_webrtc` **não podem** ser importados diretamente no topo.
- Usar `try/except ImportError` com fallback gracioso — sem isso o app inteiro cai.

### apt.txt
- `libzbar0` e `ffmpeg` devem estar em `apt.txt` para pyzbar/av funcionar no build do Render.

## Consulta Mix — EAN (2026-03-31)

### Fontes
- Busca por EAN: exclusiva em `bdados/ean_dun.parquet`
  - Colunas reais: `CODIGO_PRODUTO`, `EAN_DUN` (normalizar para lower/strip antes de mapear)
  - Aceitar equivalência EAN-13 ↔ GTIN-14 na busca
- Embalagem: buscar em `bdados/query.parquet` por correspondência de `cod_consinco`
- Coluna **Código Transição** foi removida da tela (tabela antiga, não usada)

### Câmera (streamlit-webrtc + pyzbar)
- Funciona somente quando `pyzbar/libzbar0` estão disponíveis no ambiente
- Leitura em tempo real via `VideoProcessorBase` do streamlit-webrtc
- EAN detectado é persistido em `st.session_state` para preencher o campo de busca
- Fallback: campo manual de texto sempre disponível

## Limpeza de Artefatos (2026-03-31)

### Removidos
- `squads/agents/` — 6 agentes duplicados (cópias idênticas de `squads/varejo-insight/agents/`)
- `skills/gemini-api-dev/`, `skills/gemini-interactions-api/`, `skills/gemini-live-api-dev/`, `skills/vertex-ai-api-dev/` — skills de LLM externas sem uso no projeto

### Canonical após limpeza
- Agentes ativos: `.github/agents/` (9 agentes)
- Squad agents: `squads/varejo-insight/agents/` (6 agentes)
- Skills ativas: `.github/skills/` (5 skills)
