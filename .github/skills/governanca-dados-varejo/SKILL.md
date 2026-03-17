---
name: governanca-dados-varejo
description: "Use quando precisar validar, limpar e padronizar CSV ou Excel de varejo, classificar filiais e aplicar regras de governanca de dados no ProjetoBak."
metadata:
  type: hybrid
  version: 1.0.0
  script_path: scripts/limpeza_dados.py
  dependencies:
    - pandas
  categories:
    - data
    - retail
    - quality
---

# Skill de Governanca de Dados - Varejo

Use esta skill antes de qualquer analise quando houver risco de delimitador incorreto, encoding inconsistente, colunas malformadas ou classificacao errada de filiais.

## Regras canonicas

- PDVs: `001`, `002`, `003`, `004`, `005`, `006`, `007`, `008`, `011`, `012`, `013`, `014`, `017`, `018`.
- CDs: `015`, `016`, `050`.
- Saidas operacionais devem preferir `;` e `UTF-8`.

## Quando usar

- Importacao de CSV ou Excel para analise de estoque, vendas ou abastecimento.
- Arquivos com colunas usando `:` como delimitador interno.
- Bases com encoding inconsistente ou estrutura quebrada.

## Como usar

1. Audite o arquivo de entrada.
2. Se houver problema de formato, execute `scripts/limpeza_dados.py`.
3. Reclassifique filiais segundo o glossario acima.
4. So entao siga para analise numerica ou de negocio.

## Saida esperada

- Arquivo limpo e padronizado.
- Resumo curto do que foi corrigido.