# Domain Framework: Modelos de Reposição e Gestão do Varejo

## 0. Padrão Global de Dados (Sistema ERP)
- **Separador CSV:** Ponto e vírgula (`;`) mandatório em todas as entradas e saídas.
- **Codificação:** `UTF-8` (suporte a acentos e caracteres especiais).

## 1. Processo de Análise e Cruzamento de Dados (Para o Analista de Dados)
1. **Padronização:** Uniformize os identificadores de SKUs das bases da Filial e do CD.
2. **Definição de Giro de Estoque:** Calcule a Média de Vendas Diária usando o histórico recente (ex: últimos 30 dias).
3. **Cálculo de Necessidade de Loja (Ponto de Pedido):**
   - ROP = `(Consumo médio diário * Lead Time de 4 dias)` + `Estoque de Segurança`.
   - Justificativa: O ciclo entre pedido e entrega varia de 2 a 4 dias; o estoque deve blindar a loja durante este intervalo.
   - Se *Estoque Atual na Loja* <= ROP, o item necessita de reposição para não quebrar nos próximos dias.
4. **Alinhamento de Capacidade do Distribuidor:**
   - Para cada pedido gerado no passo anterior, verifique o "Estoque no Centro de Distribuição".
   - **Cenário A:** `Estoque CD` > `Pedido Sugerido` = Reposição Autorizada.
   - **Cenário B:** `Estoque CD` < `Pedido Sugerido` = Enviar o máximo disponível e alertar para *Risco Crítico de Ruptura da Cadeia*.
5. **Classificação ABC:** Itens C (pouca venda) com estoque excessivo recebem alerta de redução de compra (overstock).

## 2. Processo de Comunicação Executiva (Para o Relator de Dashboards)
1. **Compilação de Dados e Seleção de KPIs:** Resuma as milhares de linhas do analista em números globais: % de Ruptura de Estoque Imminente, Total R$ de Oportunidade de Reposição.
2. **Design Hierárquico e Ação Orientada:**
   - Topo: Resumos Macro (Como está a saúde do estoque agora?).
   - Meio: Alertas de Ação (Top 10 Produtos em ruptura no CD / Top 10 Produtos Parados na Loja).
   - Base: Detalhamento por categoria/linha de produto.
3. **Recomendações Práticas:** Conclua o dashboard sugerindo passos, e.g., "Urgente: Acionar Compras da curva A com estoque < 3 dias de cobertura".

## 3. Inteligência de Loja Física e Promoções (Agentes Especialistas)
1. **Regras de Gôndola (Visual Merchandising & Layout):**
   - *Estoque de Apresentação (Facing):* Alguns SKUs exigem um volume mínimo nas prateleiras apenas por estética, garantindo o "efeito de massa", mesmo se a média de vendas for muito baixa. Essa trava mínima (ex: m² de exposição) sempre anula o ROP baixo no caso de gôndolas esvaziadas fisicamente.
2. **Controle de Depósito (Backroom) e Transbordo:**
   - O analista focado na retaguarda/depósito da loja identifica os produtos "ocultos" de alto volume.
   - Produtos volumosos (ex: fraldas, fardos de papel, móveis) sofrem limitação física na prateleira. Se o ROP apontar necessidade, deve-se checar se já há estoque em depósito (Sobras). O repositor interno transfere para o piso _antes_ de solicitar ao CD.
3. **Inteligência Promocional e Climática:**
   - **Histórico Preço x Demanda:** Comparar preço médio atual com o praticado no último ciclo promocional. Qual foi a elasticidade (quantos % a venda subiu quando o preço caiu Y%)? Sugerir volume turbinado de compras se a redução for similar.
   - **Fator Climático:** Cruzar forecast de clima (chuvas fortes reduzem tráfego humano; calor extremo alavanca categorias de líquidos/climatização). Ajustar OTB (Open-to-Buy) de acordo com desvios sazonais de tempo.
