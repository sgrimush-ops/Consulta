---
type: agent
agent: squads/varejo-insight/agents/gabi-gondola
description: "Revisão de Facing e Layout Visual (Esvaziamento de Loja)"
inputFile: squads/varejo-insight/output/01-base-rop.md
outputFile: squads/varejo-insight/output/02-gondola-ajustes.md
nextStep: steps/step-03-leonardo.md
---
### Instrução de Layout de Gôndola
Você acabou de receber o arquivo \`01-base-rop.md\` do Danilo. Nele já está preenchido o cálculo de ROP contra a Demanda e CD. Sua função é sobrepor a inteligência de Layout:
1. Revise se o Pedido Gerado deixa as prateleiras das lojas visivelmente vazias (Efeito "Piso Limpo" espanta clientes).
2. Adicione ou infle pedidos nas linhas C e B volumosas, que o Danilo pode ter cortado por "Ponto de Pedido Frio", mas que exigem "Trava Mínima de Fachada" (Facing).
Gere uma nova coluna na tabela chamada "Facing Requerido".
