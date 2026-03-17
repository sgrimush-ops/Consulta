---
name: governanca-dados-varejo
description: Skill focada em governança, limpeza e padronização de dados de varejo (CSV/Excel). Contém regras de formatação automática e um glossário de termos de negócio para garantir consistência entre squads.
type: hybrid
version: 1.0.0
script:
  path: scripts/limpeza_dados.py
  runtime: python
  dependencies:
    - pandas
    - openpyxl
categories:
  - data
  - analytics
  - retail
---

# Skill de Governança de Dados - Varejo

Esta skill centraliza o conhecimento sobre a estrutura de dados e regras de negócio da empresa, garantindo que todos os agentes tratem os arquivos da mesma forma.

## Glossário de Negócio (Sempre Consultar)

### Unidades e Filiais
- **Pontos de Venda (PDV)**: Filiais/Empresas **001, 002, 003, 004, 005, 006, 007, 008, 011, 012, 013, 014, 017, 018**.
- **Centros de Distribuição (CD)**: Filiais/Empresas **015, 016, 050**.
- **Empresas Virtuais (Não Operantes)**: Qualquer código ou nomenclatura que não conste na lista acima deve ser tratada como empresa virtual não operante.

### Termos Técnicos
- **Giro Diário**: Média de vendas por dia.
- **Ruptura**: Falta de produto em gôndola/estoque.
- **Lead Time**: Tempo entre o pedido e a chegada da mercadoria (Padrão: 4 dias).

## Regras de Ouro de Formatação

### 1. Padronização de Arquivos CSV
- **Separador**: Sempre utilizar ponto e vírgula (`;`).
- **Codificação**: Sempre utilizar `UTF-8`.
- **Decimais**: Utilizar vírgula (`,`) para visualização brasileira ou ponto (`.`) para cálculos Python internos.

### 2. Limpeza de Dados Específica
- **Colunas com ":"**: Se o arquivo CSV contiver colunas onde o conteúdo está agrupado por `:`, o sistema deve dividir esse conteúdo em colunas sequenciais (ex: `ID:DESCRIÇÃO` -> `COL_1: ID`, `COL_2: DESCRIÇÃO`).

## Operações Disponíveis

### Limpeza Automática
O script `limpeza_dados.py` pode ser invocado para:
1. Converter arquivos Excel para CSV padronizado.
2. Corrigir codificação de arquivos com caracteres corrompidos.
3. Separar automaticamente colunas que utilizam o caractere `:` como delimitador interno indesejado.

---
**Instrução para Agentes:** Antes de analisar qualquer base de dados, verifique se a Filial 015 está presente e trate-a como o Centro de Distribuição. Utilize o script de limpeza se encontrar delimitadores inconsistentes nas colunas.
