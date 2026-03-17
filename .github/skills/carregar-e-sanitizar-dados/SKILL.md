---
name: carregar-e-sanitizar-dados
description: "Use quando precisar ler planilhas ou CSVs com resiliencia, padronizar cabecalhos e gerar uma amostra saneada antes das analises do ProjetoBak."
metadata:
  type: hybrid
  version: 1.0.0
  script_path: scripts/carregar_e_sanitizar.py
  dependencies:
    - pandas
    - openpyxl
    - numpy
  categories:
    - data
    - ingestion
    - retail
---

# Skill de Carga e Sanitizacao de Dados

Use esta skill para leitura inicial de bases CSV ou Excel que precisem de padronizacao estrutural antes de entrar no fluxo de analise.

## O que a skill faz

- Detecta automaticamente CSV, XLSX e XLS.
- Remove linhas totalmente vazias.
- Remove colunas fantasmas `Unnamed`.
- Divide colunas com `:` quando necessario.
- Padroniza cabecalhos para `snake_case`.

## Como usar

1. Importe a funcao `skill_carregar_e_sanitizar`.
2. Passe o caminho do arquivo.
3. Use o retorno para decidir se a base esta pronta para a proxima etapa.

## Saida esperada

- Dicionario com status, total de linhas, colunas padronizadas e amostra.