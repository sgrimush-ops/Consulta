# Anti-Patterns (Erros a Evitar): Reposição e Dashboards de Varejo

## Never Do (O que nunca fazer)
1. **Sugerir Reposição Inviável:** Nunca sugerir que a filial receba "50 computadores" se o CD só tem "10 computadores". Isso gera falsas promessas logísticas e quebra a confiança no relatório.
2. **Descarga de Dados Brutos (Data Dumping):** Nunca enviar para a diretoria uma tabela com 5.000 linhas de produtos. Executivos não leem planilhas, eles leem tendências e exceções (rupturas severas ou excessos graves).
3. **Falso-Positivo de Ruptura:** Nunca considerar ruptura os itens descontinuados ou campanhas sazonais antigas (Ex: Panetones em Fevereiro). Se o item não deve mais ser vendido, ele não está "faltando".
4. **Ignorar Prazos de Fornecedor (Lead Time):** Nunca calcular a necessidade baseando-se apenas no giro do dia, sem considerar quanto tempo o fornecedor do CD leva para entregar a mercadoria.
5. **Esvaziar Gôndolas Intencionalmente:** Nunca aplicar o ROP matematicamente frio se isso resultar em prateleiras vazias (falta de Facing). A loja parecerá abandonada para o cliente.
6. **Pedir ao CD o que já está na Loja (Backroom):** Nunca emitir pedido de compra externa se o item for volumoso e estiver estocado no depósito interno da própria loja aguardando desova.
7. **Ignorar Anomalias Climáticas:** Nunca basear a previsão de vendas de repolho/sopas em uma semana que fará 35 graus, apenas porque a "média histórica do ano passado" indica alta. O clima no período promocional afeta o fluxo drasticamente.

## Always Do (O que sempre fazer)
1. **Destaque Visual de Alertas:** Sempre utilizar formatações visuais claras (ícones, negrito, etc.) ao apresentar painéis de risco financeiro ou ruptura em dashboards.
2. **Priorização ABC (Curva A):** Sempre ordinar suas tabelas de análise da mercadoria mais crítica/lucrativa para a de menor importância. O time humano atuará de cima para baixo.
3. **Oferecer Contexto de Ação (Insight):** Sempre concluir um relatório sugerindo qual setor da empresa deve agir com urgência baseado nas anomalias detectadas na data (Ex: "Aviso à equipe de Compras").
