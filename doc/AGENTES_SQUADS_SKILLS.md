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

## Skills integradas

### `governanca-dados-varejo`

Use para:

- validacao de CSV e Excel
- padronizacao de separador e encoding
- classificacao de filiais e CDs
- limpeza de colunas com delimitador interno

### `manipulacao-robusta-parquet` ⭐ **NOVO**

Use para:
- Validar integridade de arquivos Parquet (schema, nulos, duplicatas)
- Inspeccionar metadados: linhas, colunas, tipos de dados, tamanho comprimido
- Converter CSV → Parquet ou Parquet → CSV com preservação de tipos
- Mesclar múltiplos Parquets
- Otimizar leitura usando leitura de colunas parciais e push-down filters
- Trabalhar com dados canônicos: `bdados/con5cod.parquet` (produtos), `bdados/consumo.parquet` (consumo)

**Referência:** `.github/skills/manipulacao-robusta-parquet/SKILL.md`

**Script de utilidade:** `python .github/skills/manipulacao-robusta-parquet/parquet_utils.py`

**Exemplos CLI:**
```
python parquet_utils.py info bdados/con5cod.parquet        # Metadados
python parquet_utils.py validate bdados/consumo.parquet    # Integridade
python parquet_utils.py columns bdados/con5cod.parquet     # Detalhe por coluna
python parquet_utils.py csv-to-parquet dados.csv dados.parquet
```

### `carregar-e-sanitizar-dados`

Use para:

- leitura resiliente de planilhas e CSVs
- remocao de linhas vazias
- padronizacao de cabecalhos
- amostra saneada para inspecao rapida

## Agentes integrados

- `Anton Engenheiro Software`: integracao tecnica e manutencao do ecossistema
- `Ale Governanca de Dados`: qualidade de dados e padronizacao
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
- Os artefatos historicos em `.agents/` e `skills/` foram preservados como base original.