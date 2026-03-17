---
type: agent
agent: squads/varejo-insight/agents/clara-clima
description: "Inteligência Sazonal, Clima e Promoções"
inputFile: squads/varejo-insight/output/03-deposito-ajustes.md
outputFile: squads/varejo-insight/output/04-clima-ajustes.md
nextStep: steps/step-05-checkpoint.md
---
### Instrução de Modulação Sazonal
Você recebeu a tabela quase final de Reposição \`03-deposito-ajustes.md\`.
1. Fatores Climáticos: Analise se a previsão de tempo extremo impactará alguns dos SKUs (Ex: Chuva/Calor Extremo).
2. Elasticidade Promocional: Verifique se as curvas de preço atual propiciam agressividade na compra.
Se o SKU justificar modulação, altere a sugestão na Tabela Causal que estava vindo do Davi, justifique a queima de estoque ou expansão devido ao "Fator Clara" (Clima/Preço). Esta é a tabela analítica final do Varejo.
