---
name: "Executar Squad Varejo Insight"
description: "Executa ou adapta o fluxo da squad Varejo Insight para analises de ruptura, reposicao, gondola, deposito, sazonalidade e dashboard no ProjetoBak."
agent: "Varejo Insight Orquestrador"
argument-hint: "Descreva o objetivo, os arquivos de entrada e o passo do pipeline que deseja executar"
---

Execute a squad Varejo Insight usando apenas os artefatos existentes do projeto.

## Passos obrigatorios

1. Leia `squads/varejo-insight/squad.yaml`, `squads/varejo-insight/squad-party.csv` e `squads/varejo-insight/pipeline/pipeline.yaml`.
2. Identifique o passo do pipeline e os agentes envolvidos.
3. Se os dados estiverem sujos, use primeiro as skills de governanca e sanitizacao.
4. Gere uma resposta objetiva contendo:
   - etapa executada
   - agentes usados
   - principais achados
   - proximo passo do pipeline

Nao invente agentes, arquivos ou etapas fora do que existe no repositorio.