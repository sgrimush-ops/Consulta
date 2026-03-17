# Output Examples: Varejo Insight

## Exemplo 1: Sugestão de Reposição (Analista de Dados)
**Contexto:** O analista cruzou os dados do 'Estoque_Lojas.csv' com 'Vendas_Lojas.csv' e 'Estoque_CD.csv'.

```markdown
### Relatório Diário de Operações (Reposição, Gôndola e Sobras)

**Visão Geral - Top 4 Prioridades de Ação Hoje:**
As Filiais 01 e 04 estão com risco crítico de ruptura. O SKU 20560 tem sobra intraloja. O SKU 10888 teve a compra cortada por trava de limite de Gôndola.

| SKU | Categoria | Filial | Giro Diário | Ponto de Pedido (ROP) | Estoque Gôndola | Estoque Depósito (Sobras) | Decisão Sistêmica (Agentes) |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---|
| 10025 | Smartphone Pro | F-01 | 15 un | 45 un | 10 un | 0 un | **Comprar 35 un do CD** |
| 20560 | Fralda Pampers | F-04 | 4 un | 16 un | 2 un | 15 un | **Transferir Interno** (Ir ao Depósito) |
| 10888 | Shampoo 200ml | F-02 | 22 un | 88 un | 14 un | 250 un | **Overstock** (Suspender Compra) |
| 30010 | Água Mineral | F-03 | 5 un | 10 un | 8 un | 0 un | **Trava de Facing/Clima:** Comprar 50 un |

**Comentário Analítico:** A Água Mineral (30010) está acima do Ponto de Pedido padrão. Porém, o Agente Climático informa máxima histórica de 38°C para amanhã, e o Agente de Gôndola alerta esvaziamento iminente (facing quebrado). O pedido foi superdimensionado propositalmente (+50 un).
```

## Exemplo 2: Resumo Executivo para a Diretoria (Apresentador)
**Contexto:** O Agente recebeu as planilhas consolidadas e processadas do Analista.

```markdown
# 📊 Dashboard Executivo: Saúde de Estoque e Cadeia de Reposição
*Data: 14 de Março de 2026 | Resumo Logístico*

### 1. Resumo Macro (Actionable KPIs)
*   🟢 **Nível Geração de Pedidos Hoje:** 1.540 unidades despachadas para lojas.
*   🔴 **Valor Financeiro em Risco de Ruptura (Próx. 5 dias):** R$ 145.000,00 
*   ⚠️ **Eficiência do Centro de Distribuição (Fill Rate):** 89% (11% dos pedidos foram cortados por falta nas prateleiras do CD).

### 2. Oportunidades Urgentes (Top Emergências)
O CD apresenta **zeramento crítico** na Categoria de Linha Branca. As Lojas da Região Sul não conseguirão repor geladeiras neste fim de semana.
Acionar o setor de Procurement imediatamente para as categorias abaixo:

| Categoria | Filiais Afetadas | Risco Financeiro Estimado | Demanda Coberta |
|:---|:---:|:---:|:---:|
| Geladeiras Inverter | 12 | R$ 90.000,00 | 1,5 dias |
| Máquinas de Lavar 11kg | 8 | R$ 35.000,00 | 2 dias |

### 3. Excesso nas Lojas (Capital Parado) vs. Insight Promocional
O Capital de Giro encontra-se estagnado na categoria "Smartphones Básicos" da Filial 09 (140 dias de estoque).
**Histórico Promocional:** No último ano, essa mesma categoria, quando anunciada a -15% na Black Friday, gerou elasticidade de +300% em volume de saída.
**Recomendação Sistêmica:** Acionar queima de estoque emergencial a R$ 999 (-15%) com anúncios direcionados à praça da Filial 09. Prevê-se redução do estoque excedente para níveis saudáveis em 12 dias.
```
