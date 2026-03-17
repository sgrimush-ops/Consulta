---
type: agent
agent: squads/varejo-insight/agents/danilo-dados
description: "Processamento Numérico e Base do Ponto de Pedido (ROP)"
inputFile: ~
outputFile: squads/varejo-insight/output/01-base-rop.md
nextStep: steps/step-02-gabi.md
---
### Instrução de Processamento Macro
Você receberá os caminhos para os arquivos do usuário com Estoque CD, Vendas e Estoque Filial que foram depositados na pasta raiz \`squads/varejo-insight/bd_entrada/\`.
1. Padronize as tabelas e encontre o ID comumente chaveável.
2. Calcule o Ponto de Pedido base de acordo com as regras de Resumo Logístico do domínio (Lead Time = 2).
3. Produza a Tabela Inicial listando Necessidade Numérica de Lojas x Saldo no CD disponível.
Mantenha um log rigoroso de matemática em formato Markdown. Ignore fatores de estética, seu foco é o Número Frio.
