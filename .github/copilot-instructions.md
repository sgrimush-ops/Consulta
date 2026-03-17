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

## Convencoes de dados do dominio

- **Parquet é o formato canônico** para dados estruturados: `bdados/con5cod.parquet` (produtos), `bdados/consumo.parquet` (histórico).
- Para saidas tabulares do fluxo de squad, prefira CSV com `;` e codificacao `UTF-8`.
- Trate as filiais `015`, `016` e `050` como CDs; as demais definidas na skill de governanca como PDVs.
- Nao invente etapas, agentes ou arquivos fora dos que existem em `squads/varejo-insight/`.

## Especialização de Agentes em Parquet

Os 9 agentes têm especialização pronta em manipulação robusta de Parquet:
- **Danilo Dados**: Carrega e valida Parquets de consumo/produtos; calcula ROP sobre dados Parquet
- **Ale Governança**: Valida integridade de Parquets (schema, nulos, duplicatas); converte CSV → Parquet
- **Gabi Gôndola**: Extrai CapacidadeGondola de con5cod.parquet para otimizar facing
- **Leonardo Logística**: Usa embalagem (Emb) de con5cod.parquet para calcular volume
- **Clara Clima**: Correlaciona consumo.parquet com padrões sazonais
- **Paulo Pedidos**: Referencia código e status (Mix) de con5cod.parquet para consolidar pedidos
- **Roberta Relatórios**: Agrega dados Parquet para dashboard executivo
- **Anton Software**: Integra scripts de Parquet e otimiza pipeline de dados
- **Varejo Insight Orquestrador**: Coordena uso de ParQuets no squad, delegando validações

## Referencias

- Documentacao geral: `README.md`
- Guia de integracao de IA: `doc/AGENTES_SQUADS_SKILLS.md`
- Squad principal: `squads/varejo-insight/squad.yaml`
- **Skill de Parquet**: `.github/skills/manipulacao-robusta-parquet/SKILL.md`
- **Utilitários Parquet**: `.github/skills/manipulacao-robusta-parquet/parquet_utils.py`