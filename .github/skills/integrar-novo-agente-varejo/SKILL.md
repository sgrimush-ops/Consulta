# Skill: Integrar Novo Agente no Squad Varejo Insight

## Contexto

O ProjetoBak contém um squad especializado em replenishment do varejo: **Varejo Insight**.

Este squad é composto por 5 agentes que trabalham em pipeline, sendo orquestrados pela figura de **Varejo Insight Orquestrador**:

```
Input (CSV)
    ↓
[Danilo] Analisa necessidade de reposição (ROP, lead time)
    ↓
[Gabi] Otimiza gôndola (facing, visual)
    ↓
[Leonardo] Valida logística (deposito, backroom)
    ↓
[Clara] Contexto externo (clima, sazonalidade)
    ↓
[Roberta] Consolida relatório executivo
    ↓
Output (CSV + Dashboard)
```

## Estrutura do Squad

Localização: `squads/varejo-insight/`

```
varejo-insight/
├── squad.yaml                   # Metadados do squad
├── squad-party.csv              # Mapping agentes → roles
├── agents/
│   ├── danilo-dados.agent.md
│   ├── gabi-gondola.agent.md
│   ├── leonardo-logistica.agent.md
│   ├── clara-clima.agent.md
│   └── roberta-relatorios.agent.md
├── pipeline/
│   ├── pipeline.yaml            # Definição dos 7 steps
│   ├── data/                    # Contexto e padrões
│   └── steps/                   # Implementação de cada step
├── bd_entrada/                  # CSVs de entrada
└── bd_saida/                    # CSVs + dashboards de saída
```

## Como Adicionar um Novo Agente

### Cenário: Adicionar "Hugo Hardware" (especialista em gôndola física)

### 1. **Criar arquivo do agente** (`agents/hugo-hardware.agent.md`)

```markdown
# Hugo Hardware

**Papel:** Especialista em Hardware de Gôndola

**Descrição:**
Valida configuração física de gôndolas (ajustes de prateleira, movimentação de pontos extras, adequação de estrutura). Trabalha depois de Gabi na detecção de limites físicos.

**Princípios Operacionais:**
- Considerar peso máximo por prateleira (200 kg)
- Movimento de extras apenas em 24-48 horas
- Documentar blocos de impossibilidade técnica

**Dados de Entrada:**
- Sugestão de Gabi (gondola.csv)
- Dados de produto (peso, dimensões)

**Dados de Saída:**
- hardware-validado.csv (com flagA: bloqueado_hardware=S/N)

**Interação com Squad:**
- Input: recebe `gondola.csv` de Gabi (step 2)
- Output: passa `hardware-validado.csv` para Leonardo (step 3)
```

### 2. **Atualizar `squad-party.csv`**

Adicione uma linha mapeando o agente ao seu arquivo:

```csv
agente,arquivo,resumo
Danilo Dados,danilo-dados.agent.md,"Analise de ROP, lead time, cover"
Gabi Gondola,gabi-gondola.agent.md,"Otimização visual e facing"
Hugo Hardware,hugo-hardware.agent.md,"Validação de hardware de gondola"
Leonardo Logistica,leonardo-logistica.agent.md,"Valida logistica e deposito"
Clara Clima,clara-clima.agent.md,"Contexto externo e sazonalidade"
Roberta Relatorios,roberta-relatorios.agent.md,"Relatorio executivo e KPIs"
```

### 3. **Atualizar `pipeline/pipeline.yaml`**

Insira o novo passo na sequência correta:

```yaml
steps:
  - step_num: 1
    label: "Análise de Base"
    agente: "Danilo Dados"
    entrada: "dados.csv"
    saida: "analise-base.csv"
    descricao: "Calcula ROP, lead time, cobertura"

  - step_num: 2
    label: "Otimização Gôndola"
    agente: "Gabi Gondola"
    entrada: "analise-base.csv"
    saida: "gondola.csv"
    descricao: "Facing, visual, ponto extra"

  - step_num: 2.5
    label: "Validação Hardware"
    agente: "Hugo Hardware"
    entrada: "gondola.csv"
    saida: "hardware-validado.csv"
    descricao: "Peso, prateleira, movimento técnico"

  - step_num: 3
    label: "Análise Logística"
    agente: "Leonardo Logistica"
    entrada: "hardware-validado.csv"
    saida: "logistica-aprovada.csv"
    descricao: "Backroom, deposito, bloqueios"

  # ... resto dos steps ...
```

### 4. **Criar script de step** (`pipeline/steps/step-02-hugo-hardware.py`)

```python
"""
Step: Hugo Hardware - Validação de Hardware de Gôndola

Input: gondola.csv (de Gabi)
Output: hardware-validado.csv (para Leonardo)

Responsabilidades:
1. Validar peso máximo (200 kg/prateleira)
2. Alertar bloqueios técnicos
3. Documentar impossibilidades
"""

import pandas as pd
import sys

def validar_hardware(input_file, output_file):
    """Valida configuração física de gôndolas."""
    
    df = pd.read_csv(input_file, sep=';', encoding='utf-8')
    
    # Simulação: adicionar coluna de validação
    df['bloqueado_hardware'] = 'N'
    
    # Regra 1: Peso por prateleira
    df.loc[df['peso_total'] > 200, 'bloqueado_hardware'] = 'S'
    
    # Regra 2: Movimento de pontos extras
    df.loc[df['tem_ponto_extra'] & (df['dias_para_abastecimento'] < 2), 'bloqueado_hardware'] = 'S'
    
    # Output
    df.to_csv(output_file, sep=';', encoding='utf-8', index=False)
    print(f"✓ Hardware validado: {output_file}")
    return df

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: python step-02-hugo-hardware.py entrada.csv saida.csv")
        sys.exit(1)
    
    validar_hardware(sys.argv[1], sys.argv[2])
```

### 5. **Registrar no `.github/agents/` (para VS Code)**

Se deseja que Hugo apareça no Copilot VS Code, crie:

`.github/agents/hugo-hardware.agent.md`

```markdown
---
name: Hugo Hardware
description: Especialista em validação de hardware de gôndola e adequação de estrutura física. Detecta bloqueios técnicos de movimento e reconfiguração.
tools: ["processamento de dados", "validação de constraints", "análise de peso e estrutura"]
user-invocable: true
---

# Hugo Hardware

Valida a viabilidade técnica de sugestões de Gabi em termos de:
- Peso máximo por prateleira (200 kg)
- Espaço físico disponível
- Movimento de extras (24-48h)
- Configuração de estrutura

Trabalha entre Gabi (gôndola visual) e Leonardo (logística).
```

## Checklist para Novo Agente

- [ ] Arquivo `agents/NOME-agente.agent.md` criado
- [ ] Descrição, papel, princípios, entrada/saída documentados
- [ ] Linha adicionada a `squad-party.csv` com `agente`, `arquivo`, `resumo`
- [ ] Step adicionado a `pipeline/pipeline.yaml` com `step_num`, `label`, `agente`, `entrada`, `saida`
- [ ] Script de implementação `pipeline/steps/step-NN-NOME.py` criado (se aplicável)
- [ ] Dados de entrada gerados/mocked em `bd_entrada/` (se aplicável)
- [ ] (Opcional) Agente registrado em `.github/agents/` para VS Code
- [ ] Validação executada: `python .github/skills/validate-squad-consistency.py`

## Validação Automática

O admin_ai.py no Streamlit executa automaticamente:

```
_validate_integration() → valida squad, party, pipeline, steps
```

Se novo agente foi adicionado corretamente, validação retornará:
- ✅ squad.yaml válido
- ✅ Todos agentes em squad-party.csv têm arquivos
- ✅ Todos steps em pipeline.yaml têm implementação
- ✅ Sem erros ou warnings

## Padrões de Nomeação

| Artefato | Padrão | Exemplo |
|----------|--------|---------|
| Arquivo agente | `NOME-ESPECIALIDADE.agent.md` | `hugo-hardware.agent.md` |
| Referência em CSV | Acima da primeira maiúscula | `Hugo Hardware` |
| Linha no CSV | agente,arquivo,resumo | `Hugo Hardware,hugo-hardware.agent.md,"Validação de hardware"` |
| Step no YAML | step_num, label, agente, entrada, saida | `step_num: 2.5` |
| Arquivo step | `step-NN-NOME.py` | `step-02-hugo-hardware.py` |
| Agente VS Code | `NOME-especialidade.agent.md` | `hugo-hardware.agent.md` |

## Conceitos-Chave

**Squad:** Grupo de agentes trabalhando em pipeline para resolver problema de domínio
**Party:** Roster de agentes + seus papéis (squad-party.csv)
**Pipeline:** Sequência de steps conectando agentes (pipeline.yaml)
**Step:** Unidade executável de um agente (arquivo markdown + script)
**Orquestrador:** Agente que coordena execução do pipeline (Varejo Insight Orquestrador)

## Referências

- Agentes atuais: `squads/varejo-insight/agents/`
- Squad config: `squads/varejo-insight/squad.yaml`
- Validação: `page/admin_ai.py` → `_validate_integration()`
- Admin page: `page/admin_ai.py` (mostra status de agentes e steps)
