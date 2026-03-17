# Research Brief: Análise de Dados para Reposição de Varejo e Dashboards Executivos

## 1. Domain Framework (Gestão de Reposição e Análise de Estoque)
O processo de análise de dados logísticos (Supply Chain Management) e controle de inventário no varejo baseia-se na sincronização entre demanda (vendas) e oferta (capacidade do CD e tempo de fornecedor).
As metodologias essenciais identificadas são:
- **Planejamento de Demanda (Demand Forecasting):** Avaliação de histórico de giro e média de vendas para calcular necessidade diária de estoque.
- **Just-in-Time (JIT) / Lean:** Trabalhar com níveis enxutos, solicitando reposição no momento mais próximo à necessidade real para reduzir *holding costs* (custos de manutenção).
- **Cálculo de Necessidade e Ponto de Pedido (ROP):** `[Consumo médio diário * Lead Time] + Estoque de Segurança`. Esse cálculo orienta a criação das ordens de compra automática.
- **Prevenção de Ruptura (Out-of-Stock/OOS):** Comparar a demanda reprimida das filiais (necessidade calculada via ROP) com o estoque atual disponível no Centro de Distribuição (CD).
- **Giro de Estoque:** `[Custo das Mercadorias / Estoque Médio]` para medir a velocidade de saída, útil para determinar o peso/importância da mercadoria no Dashboard.

## 2. Common Mistakes & Anti-Patterns na Análise de Varejo
- **Tratar todos os SKUs como iguais (Falta de Curva ABC):** Não aplicar priorização financeira resulta em perder tempo repondo itens de baixo giro enquanto a falta dos itens A (curva principal) causa prejuízos enormes.
- **Desconsiderar Lead Time na reposição:** Fazer pedidos de produtos que demoram semanas baseando-se no nível atual ("só quando zerar") causa longos períodos de ruptura.
- **Silos de Informação / Descolamento do CD:** Analisar a necessidade da filial separada do fornecimento do CD causa emissões de pedidos impossíveis de serem atendidos ("Pediram 100, mas o CD só tem 10"), frustrando as expectativas operacionais.

## 3. Executive Dashboards Best Practices
A comunicação dos resultados de reposição e métricas para a Diretoria precisa ser visual, objetiva e processável rapidamente. Dashboards eficazes focam em ações (Actionable Insights) ao invés de apenas listar dados crus.
- **Simplicidade (Menos é Mais):** Excesso de widgets e tabelas confunde executivos. Apenas as métricas chave (KPIs) devem estar em foco, destacadas com hierarquia visual.
- **Foco nos KPIs Centrais:** "Dias de Estoque Disponível (DIOH)", "Ruptura Potencial (Valor $ em Risco de Faltar)" e "Taxa de Atendimento do CD".
- **Storytelling Visual:** Agrupar dados por impacto financeiro (Oportunidades x Riscos). Gráficos limpos identificam tendências de piora de fornecedores ou filiais com anomalias de venda.
- **Recomendação Embutida:** Dashboards eficientes não apenas informam o que aconteceu ("Falta no CD"), mas recomendam atitudes ("Alerta de Compras Urgentes", "Excedente para Promoção").
