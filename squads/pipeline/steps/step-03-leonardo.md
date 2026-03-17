---
type: agent
agent: squads/varejo-insight/agents/leonardo-logistica
description: "Análise de Retaguarda e Excesso em Almoxarifado"
inputFile: squads/varejo-insight/output/02-gondola-ajustes.md
outputFile: squads/varejo-insight/output/03-deposito-ajustes.md
nextStep: steps/step-04-clara.md
---
### Instrução de Bloqueio Intraloja
Você acaba de receber a planilha de ROP e Gôndola \`02-gondola-ajustes.md\`.
1. Físico do Depósito: O pedido gerado cabe na recepção da filial afetada?
2. Sobras (Backroom): Modifique a recomendação de "Pedir para o CD" convertendo-a em "Tranferir do Backroom" caso o estoque de "Sobras Intralojas" ainda seja substancial, protegendo a empresa de comprar o que já comprou, mesmo que não esteja exposto (fraldas, papel higiênico, etc.).
Adicione sua validação na coluna correspondente, finalizando sua versão da Tabela Causal.
