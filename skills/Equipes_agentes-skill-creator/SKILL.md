---
name: Equipes_agentes-skill-creator
description: Crie novas skills para o Equipes_agentes, modifique e melhore skills existentes e meça o desempenho das mesmas. Use quando os usuários quiserem criar uma skill para seus squads, atualizar ou otimizar uma skill existente, executar avaliações para testar uma skill ou comparar o desempenho de skills. Suporta todos os tipos de skill do Equipes_agentes: integrações MCP, scripts personalizados, híbridos e prompts comportamentais.
---

# Criador de Skills Equipes_agentes

Uma skill para criar novas skills do Equipes_agentes e melhorá-las iterativamente.

Em alto nível, o processo de criação de uma skill funciona assim:

- Decida o que você quer que a skill faça e aproximadamente como ela deve fazer
- Escreva um rascunho da skill
- Crie alguns prompts de teste e execute um agente Equipes_agentes com a skill injetada em seu contexto
- Ajude o usuário a avaliar os resultados tanto qualitativa quanto quantitativamente
  - Enquanto as execuções acontecem em segundo plano, rascunhe algumas avaliações quantitativas se não houver nenhuma. Em seguida, explique-as ao usuário (ou explique as que já existem).
  - Use o script `eval-viewer/generate_review.py` para mostrar os resultados ao usuário para inspeção, junto com as métricas quantitativas.
- Reescreva a skill com base no feedback da avaliação do usuário (e também se houver falhas gritantes evidentes nos benchmarks quantitativos).
- Repita até estar satisfeito.
- Expanda o conjunto de testes e tente novamente em maior escala.

Seu trabalho ao usar esta skill é identificar em que estágio do processo o usuário está e ajudá-lo a progredir. Por exemplo, se ele disser "Quero fazer uma skill para X", você pode ajudar a refinar a ideia, escrever o rascunho, os casos de teste, definir a avaliação, executar os prompts e repetir.

Sempre seja flexível; se o usuário preferir não fazer avaliações formais e apenas "testar no feeling", siga essa abordagem.

## Comunicando-se com o usuário

O criador de skills pode ser usado por pessoas com diferentes níveis de familiaridade técnica. Fique atento aos sinais de contexto para ajustar sua linguagem:

- Termos como "avaliação" e "benchmark" são aceitáveis, mas use com cautela.
- Para "JSON" e "assertion" (asserção), certifique-se de que o usuário entende esses termos antes de usá-los sem explicar.

Sinta-se à vontade para explicar termos brevemente se estiver em dúvida.

---

## Criando uma skill

### Capturar a Intenção

Comece entendendo o que o usuário quer. A conversa atual pode já conter um workflow que o usuário deseja capturar (ex: eles dizem "transforme isso em uma skill"). Se sim, extraia as respostas do histórico da conversa primeiro — as ferramentas usadas, a sequência de passos, correções feitas, formatos de entrada/saída observados.

1. O que esta skill deve permitir que os agentes façam?
2. Quando esta skill deve ser usada? (frases, contextos ou cenários de squad)
3. Qual é o formato de saída esperado?
4. Precisamos configurar casos de teste? Skills com saídas objetivamente verificáveis (transformações de arquivos, extração de dados, geração de código) se beneficiam de casos de teste. Skills com saídas subjetivas (estilo de escrita, arte) geralmente não precisam. Sugira o padrão apropriado, mas deixe o usuário decidir.

5. Qual é o tipo de skill?
   - **MCP** — Conecta a uma API externa via servidor MCP (ex: Canva, Apify)
   - **Script** — Executa um script personalizado (Node.js, Python, Bash)
   - **Híbrido** — Componentes de MCP e script
   - **Prompt** — Instruções comportamentais puras (sem integração externa)

Para skills MCP, pergunte também:
- Qual comando do servidor MCP? (ex: `npx -y @package/name`)
- Qual transporte? (stdio ou http)
- Se http: qual URL?
- Quais variáveis de ambiente são necessárias?
- Algum cabeçalho de autenticação?

Para skills de Script, pergunte também:
- Qual runtime? (Node.js, Python, Bash)
- Quais dependências?
- Qual o comando de invocação?

Para Híbrido: faça ambos os conjuntos de perguntas.
Para Prompt: pule — vá direto para a escrita do corpo da skill.

### Entrevista e Pesquisa

Seja proativo ao perguntar sobre casos de borda, formatos de entrada/saída, arquivos de exemplo, critérios de sucesso e dependências. Espere para escrever os prompts de teste até que esta parte esteja definida.

Pesquise MCPs disponíveis se forem úteis para a pesquisa.

### Escrever o SKILL.md

Após a entrevista, gere o SKILL.md com:
- Frontmatter YAML seguindo o esquema em `references/skill-format.md`
- Corpo Markdown com instruções para os agentes

### Guia de Escrita de Skill

#### Anatomia de uma Skill

```
nome-da-skill/
├── SKILL.md (obrigatório)
│   ├── Frontmatter YAML (nome, descrição, tipo, versão)
│   └── Instruções Markdown
└── Recursos Agrupados (opcional)
    ├── scripts/    - Código executável para tarefas determinísticas
    ├── references/ - Documentos carregados no contexto conforme necessário
    └── assets/     - Arquivos usados na saída (templates, ícones, fontes)
```

#### Divulgação Progressiva

As skills usam um sistema de carregamento em três níveis:
1. **Metadados** (nome + descrição) - Sempre no contexto (~100 palavras)
2. **Corpo do SKILL.md** - No contexto sempre que a skill estiver ativa (ideal < 500 linhas)
3. **Recursos agrupados** - Conforme necessário (ilimitado)

**Padrões principais:**
- Mantenha o SKILL.md com menos de 500 linhas. Se exceder, use hierarquia com referências claras.
- Referencie arquivos claramente a partir do SKILL.md com orientação sobre quando lê-los.

#### Princípio da Ausência de Surpresa

As skills não devem conter códigos maliciosos ou conteúdos que comprometam a segurança. O conteúdo não deve surpreender o usuário em relação à sua intenção descrita.

#### Padrões de Escrita

Prefira o modo imperativo nas instruções.

**Definindo formatos de saída:**
```markdown
## Estrutura do Relatório
SEMPRE use este template exato:
# [Título]
## Resumo executivo
## Principais descobertas
## Recomendações
```

### Estilo de Escrita

Explique ao modelo **por que** as coisas são importantes em vez de apenas usar "DEVE". Use teoria da mente para tornar a skill geral e não limitada a exemplos específicos.

### Casos de Teste

Após o rascunho, crie 2-3 prompts de teste realistas. Salve-os em `evals/evals.json`.

```json
{
  "skill_name": "exemplo-skill",
  "evals": [
    {
      "id": 1,
      "prompt": "Prompt da tarefa do usuário",
      "expected_output": "Descrição do resultado esperado",
      "files": []
    }
  ]
}
```

## Executando e avaliando casos de teste

Organize os resultados em uma pasta de workspace irmã ao diretório da skill, separada por iterações (`iteration-1/`, etc.).

### Passo 1: Disparar todas as execuções

Para cada caso de teste, execute a versão "com skill" e um "baseline" (padrão comparativo).

### Passo 2: Enquanto as execuções ocorrem, rascunhe as asserções

Defina critérios quantitativos verificáveis e explique-os ao usuário.

### Passo 3: Capturar dados de tempo e tokens

Ao finalizar, salve os metadados (tokens, duração) em `timing.json`.

### Passo 4: Dar nota, agregar e lançar o visualizador

1. **Dar nota**: Use um script ou avalie manualmente cada asserção. Salve em `grading.json`.
2. **Agregar**: Execute o script de agregação para gerar o `benchmark.json`.
3. **Analisar**: Identifique padrões nos dados.
4. **Lançar o visualizador**: Use `generate_review.py` para criar a interface de revisão para o usuário.

## Melhorando a skill

1. **Generalize a partir do feedback**: Não faça correções pontuais apenas para os testes; foque na utilidade geral da skill.
2. **Mantenha o prompt enxuto**: Remova instruções que não agregam valor.
3. **Explique o porquê**: Instruções baseadas em raciocínio são mais eficazes em LLMs modernos.
4. **Evite trabalho repetido**: Se os agentes estão criando scripts semelhantes, mova esse código para `scripts/` da própria skill.
