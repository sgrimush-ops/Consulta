# Integracao de Agentes, Squads e Skills

## Objetivo

Este documento explica como os agentes, squads e skills foram adaptados para o ProjetoBak sem acoplar a aplicacao Streamlit a uma estrutura externa de IA.

## Estrutura adotada

### 1. Camada ativa no editor

- `.github/copilot-instructions.md`
- `.github/agents/`
- `.github/skills/`
- `.github/prompts/`

Essa camada existe para que o VS Code/Copilot consiga descobrir os artefatos automaticamente.

### 2. Fonte canonica do dominio

- `squads/varejo-insight/`

Essa pasta concentra a definicao principal do squad de varejo, incluindo:

- `squad.yaml`
- `squad-party.csv`
- `pipeline/pipeline.yaml`
- `pipeline/data/`
- `agents/`

## O que foi alinhado

- O `squad-party.csv` foi corrigido para apontar para `leonardo-logistica` e `roberta-relatorios`, que sao os agentes reais presentes no repositorio.
- O `pipeline/pipeline.yaml` foi corrigido para usar `step-03-leonardo.md` e `step-06-roberta.md`, que sao os arquivos existentes.
- O `squads/squad.yaml` passou a apontar corretamente para os caminhos completos do squad principal.
- Os agentes duplicados de `squads/agents/` foram removidos (canonico em `squads/varejo-insight/agents/`).

## Fontes Canonicas de Dados (Parquet)

| Arquivo | Uso | Origem |
|---|---|---|
| `bdados/con5cod.parquet` | Catalogo de produtos Consinco | Git / Admin Uploads |
| `bdados/consumo.parquet` | Historico de consumo por loja | Git / Admin Uploads |
| `bdados/ean_dun.parquet` | Mapeamento EAN/DUN por produto | **Somente Admin Uploads** |
| `bdados/query.parquet` | Embalagem de transferencia | **Somente Admin Uploads** |

- Arquivos marcados como **"Somente Admin Uploads"** nao ficam no Git.
- Use `page/admin_uploads.py` para envia-los ao disco persistente no Render.
- Variaveis de ambiente `EAN_DUN_PARQUET_PATH` e `QUERY_PARQUET_PATH` permitem sobrescrever caminhos.

## Skills integradas

### `governanca-dados-varejo`

Use para:

- validacao de CSV e Excel
- padronizacao de separador e encoding
- classificacao de filiais e CDs
- limpeza de colunas com delimitador interno

### `manipulacao-robusta-parquet`

Use para:
- Validar integridade de arquivos Parquet (schema, nulos, duplicatas)
- Inspecionar metadados: linhas, colunas, tipos de dados, tamanho comprimido
- Converter CSV → Parquet ou Parquet → CSV com preservacao de tipos
- Mesclar multiplos Parquets
- Resolver caminhos de Parquet em deploy no Render
- Trabalhar com dados canonicos: `con5cod`, `consumo`, `ean_dun`, `query`

**Referencia:** `.github/skills/manipulacao-robusta-parquet/SKILL.md`

**Script de utilidade:** `python .github/skills/manipulacao-robusta-parquet/parquet_utils.py`

### `carregar-e-sanitizar-dados`

Use para:

- leitura resiliente de planilhas e CSVs
- remocao de linhas vazias
- padronizacao de cabecalhos
- amostra saneada para inspecao rapida

## Agentes integrados

- `Anton Engenheiro Software`: integracao tecnica, manutencao do ecossistema, deploy no Render
- `Ale Governanca de Dados`: qualidade de dados, padronizacao, validacao de Parquets
- `Danilo Dados`: reposicao numerica e ROP
- `Gabi Gondola`: ajuste visual e facing
- `Leonardo Logistica`: backroom e transbordo
- `Clara Clima`: ajuste sazonal
- `Paulo Pedidos`: consolidacao de pedidos
- `Roberta Relatorios`: dashboard executivo
- `Varejo Insight Orquestrador`: coordenacao do fluxo do squad

## Como usar no VS Code

### Usar um agente diretamente

Selecione um dos agentes em `.github/agents/` quando a tarefa corresponder ao papel especializado.

### Executar o squad principal

Use o prompt `Executar Squad Varejo Insight` em `.github/prompts/` para conduzir o fluxo conforme o pipeline do squad.

### Trabalhar com dados de entrada

Antes da analise, priorize as skills em `.github/skills/` quando houver arquivos CSV ou Excel com estrutura inconsistente.

## Como usar no Streamlit

Usuarios com role `admin` possuem uma pagina exclusiva chamada `Integracao IA`.

Nela e possivel:

- conferir os agentes integrados em `.github/agents/`
- conferir as skills integradas em `.github/skills/`
- conferir o prompt do squad principal em `.github/prompts/`
- visualizar a estrutura canonica do squad `squads/varejo-insight/`
- explorar os arquivos principais da integracao com preview e download
- ver resumos curtos de agentes, skills e prompts
- validar automaticamente inconsistencias entre `squad.yaml`, `squad-party.csv` e `pipeline/pipeline.yaml`

## Limites desta integracao

- A aplicacao Streamlit nao invoca esses agentes automaticamente.
- A integracao e orientada ao uso no editor e a padronizacao de analises assistidas por IA.
- Agentes canonicos ficam em `.github/agents/` (9 agentes) e `squads/varejo-insight/agents/` (6 agentes da squad).
