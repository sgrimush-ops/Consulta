# ProjetoBak

## Contexto do projeto

- Aplicacao principal em Streamlit com entrada por `main.py` e modulo principal em `app.py`.
- As paginas ficam em `page/`.
- Utilitarios Python ficam em `utils/` e scripts operacionais em `tools/` e `scripts/`.
- A estrutura de agentes e squad do dominio de varejo fica em `squads/varejo-insight/`.

## Como trabalhar neste repositorio

- Preserve o fluxo atual da aplicacao Streamlit; integracoes de IA nao devem quebrar a navegacao nem a conexao com banco.
- Ao lidar com dados de varejo, use `squads/varejo-insight/` como fonte canonica para papeis, pipeline e artefatos de dominio.
- Ao lidar com limpeza de arquivos ou padronizacao de CSV/Excel, priorize as skills em `.github/skills/`.
- Ao trabalhar com Parquet (formato canônico de dados): consulte `.github/skills/manipulacao-robusta-parquet/` para validação, conversão e otimização.
- Em tarefas de reposicao, ruptura, gôndola, deposito, clima, compras e dashboards, prefira os agentes em `.github/agents/`.
- Em toda interacao com o usuario, responda sempre em portugues do Brasil, com linguagem clara e natural.

## Convencoes de dados do dominio

- **Parquet é o formato canônico** para dados estruturados:
  - `bdados/con5cod.parquet` — catálogo de produtos Consinco
  - `bdados/consumo.parquet` — histórico de consumo por loja
  - `bdados/ean_dun.parquet` — mapeamento EAN/DUN por produto *(carregado via Admin Uploads)*
  - `bdados/query.parquet` — embalagem de transferência por produto *(carregado via Admin Uploads)*
- Os arquivos `ean_dun.parquet` e `query.parquet` **não estão no Git**; devem ser enviados pelo Admin Uploads para o disco persistente no Render.
- Para saidas tabulares do fluxo de squad, prefira CSV com `;` e codificacao `UTF-8`.
- Trate as filiais `015`, `016` e `050` como CDs; as demais definidas na skill de governanca como PDVs.
- Nao invente etapas, agentes ou arquivos fora dos que existem em `squads/varejo-insight/`.

## Especialização de Agentes em Parquet

Os 9 agentes têm especialização pronta em manipulação robusta de Parquet:
- **Danilo Dados**: Carrega e valida Parquets de consumo/produtos; calcula ROP sobre dados Parquet
- **Ale Governança**: Valida integridade de Parquets (schema, nulos, duplicatas); converte CSV → Parquet; valida ean_dun e query
- **Gabi Gôndola**: Extrai CapacidadeGondola de con5cod.parquet para otimizar facing
- **Leonardo Logística**: Usa embalagem (Emb) de con5cod.parquet e query.parquet para calcular volume
- **Clara Clima**: Correlaciona consumo.parquet com padrões sazonais
- **Paulo Pedidos**: Referencia código e status (Mix) de con5cod.parquet para consolidar pedidos
- **Roberta Relatórios**: Agrega dados Parquet para dashboard executivo
- **Anton Software**: Integra scripts de Parquet, otimiza pipeline, gerencia deploy no Render
- **Varejo Insight Orquestrador**: Coordena uso de Parquets no squad, delegando validações

## Referencias

- Documentacao geral: `README.md`
- Guia de integracao de IA: `doc/AGENTES_SQUADS_SKILLS.md`
- Squad principal: `squads/varejo-insight/squad.yaml`
- **Skill de Parquet**: `.github/skills/manipulacao-robusta-parquet/SKILL.md`
- **Utilitários Parquet**: `.github/skills/manipulacao-robusta-parquet/parquet_utils.py`

## Guardrails de Qualidade (Anti-Falhas de Deploy)

- Em alteracoes de Python, principalmente em `app.py`, valide blocos `with`, `try/except` e `def` para evitar erro de indentacao.
- Nunca inserir chamadas fora de bloco (ex.: `bootstrap_*`) no meio de comandos `conn.execute(...)` dentro de `with engine.begin()`.
- Sempre executar validacao local antes de commit:
	- `python scripts/smoke_test.py`
	- checagem de erros estaticos no arquivo alterado
- Se houver falha de deploy com `IndentationError`, revisar primeiro o entorno da linha reportada e confirmar alinhamento por bloco logico.
- **Imports opcionais**: dependências de runtime como `av`, `cv2`, `pyzbar`, `streamlit_webrtc` devem estar em `try/except ImportError` — import direto no topo derruba o app inteiro.
- **Parquets no Render**: arquivos grandes como `ean_dun.parquet` e `query.parquet` não ficam no Git; use Admin Uploads para gravar no disco persistente e defina `EAN_DUN_PARQUET_PATH` / `QUERY_PARQUET_PATH` se necessário.
- **Resolução de caminho**: ao ler Parquet, tente múltiplos caminhos candidatos (`base_data_path`, `RENDER_DISK_PATH/bdados/`, `/opt/render/project/src/bdados/`) antes de falhar.
- **apt.txt**: libs de sistema como `libzbar0` e `ffmpeg` devem estar em `apt.txt` para serem instaladas no build do Render.
