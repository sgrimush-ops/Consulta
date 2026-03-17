# Integracao de Agentes, Squads e Skills

Este repositorio ja esta adaptado para integrar os artefatos de agentes, squads e skills ao fluxo do projeto.

## Onde esta a integracao ativa

- `.github/copilot-instructions.md`: instrucoes globais para o agente no workspace.
- `.github/agents/`: agentes customizados prontos para descoberta no VS Code/Copilot.
- `.github/skills/`: skills operacionais para este dominio.
- `.github/prompts/executar-squad-varejo-insight.prompt.md`: prompt reutilizavel para executar a squad principal.

## Fontes canonicas do projeto

- `squads/varejo-insight/`: squad principal do dominio de reposicao, ruptura e abastecimento.
- `skills/governanca-dados-varejo/`: base original da skill de governanca de dados.
- `skills/carregar_e_sanitizar/`: base original da skill de carga e sanitizacao.
- `.agents/` e `squads/agents/`: historico/origem de agentes ja criados.

## Observacoes

- A aplicacao principal continua sendo Streamlit e nao depende desses artefatos para executar.
- A nova camada em `.github/` serve para tornar os agentes e skills descobriveis e reutilizaveis no editor.
- O squad `Varejo Insight` foi alinhado para apontar apenas para agentes e etapas que existem de fato no repositorio.

## Proximo uso esperado

No chat do VS Code, voce pode usar o prompt do squad ou selecionar diretamente os agentes especializados para analises de varejo, dados e abastecimento.
