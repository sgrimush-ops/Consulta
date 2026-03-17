---
name: "Best-Practice Creator"
description: >
  Guides creation and maintenance of best-practice files for the Equipes_agentes best-practices library.
  Handles format validation, cross-references, versioning, and catalog consistency.
description_pt-BR: >
  Guia a criação e manutenção de arquivos de melhores práticas (best-practice) na biblioteca de melhores práticas do Equipes_agentes.
  Cuida de validação de formato, referências cruzadas, versionamento e consistência do catálogo.
description_es: >
  Guía la creación y mantenimiento de archivos de best-practice en la biblioteca de best-practices de Equipes_agentes.
  Maneja validación de formato, referencias cruzadas, versionamiento y consistencia del catálogo.
type: prompt
version: "2.0.0"
---

# Best-Practice Creator — Workflow

Use este workflow ao criar um novo arquivo de melhores práticas para a biblioteca `_Equipes_agentes/core/best-practices/`.

## Verificações Prévias

1. **Escanear arquivos existentes**: Leia `_Equipes_agentes/core/best-practices/_catalog.yaml`. Extraia `id`, `name`, `whenToUse`, `file` de cada entrada.
2. **Verificar sobreposições**: Garanta que o novo arquivo não duplique o escopo de `whenToUse` de uma entrada existente. Se houver sobreposição, esclareça a diferenciação antes de prosseguir.
3. **Listar skills disponíveis**: Leia todos os arquivos `skills/*/SKILL.md`. Extraia `name`, `description`, `type` de cada um — isso pode informar o conteúdo do arquivo de melhores práticas.

## Checklist de Criação

Para cada novo arquivo de melhores práticas, garanta TODOS os itens a seguir:

### Frontmatter (YAML)

- [ ] `id`: kebab-case em letras minúsculas (ex: `copywriting`)
- [ ] `name`: Nome de exibição para a listagem do catálogo (ex: `"Copywriting & Escrita Persuasiva"`)
- [ ] `whenToUse`: Multi-linha com escopo positivo E escopo negativo "NOT for: ..." referenciando outros IDs de melhores práticas
- [ ] `version`: `"1.0.0"` para novos arquivos

### Corpo (Markdown) — Todas as seções são obrigatórias

- [ ] **Core Principles**: 6+ regras de decisão específicas do domínio numeradas, cada uma com um título em negrito e explicação detalhada
- [ ] **Techniques & Frameworks**: Métodos concretos, modelos ou processos que profissionais usam nesta disciplina (ex: passos de diagnóstico, seleções de framework, padrões estruturais)
- [ ] **Quality Criteria**: 4+ critérios de verificação como lista `- [ ]` que podem ser usados para avaliar o resultado
- [ ] **Output Examples**: 2+ exemplos completos, 15+ linhas cada, realistas e NÃO com aparência de template
- [ ] **Anti-Patterns**: O Que Nunca Fazer (4+) + O Que Sempre Fazer (3+), cada um com explicação
- [ ] **Vocabulary Guidance**: Termos/frases para Sempre Usar (5+), Termos/frases para Nunca Usar (3+), Regras de Tom (2+)

### Mínimos de Qualidade

| Seção | Mínimo |
|---------|---------|
| Total de linhas do arquivo | 200+ |
| Princípios Transversais | 6+ regras numeradas |
| Técnicas e Frameworks | 3+ técnicas concretas |
| Vocabulário (Sempre Usar) | 5+ termos |
| Vocabulário (Nunca Usar) | 3+ termos |
| Exemplos de Saída | 2 completos, 15+ linhas cada |
| Anti-padrões (Nunca Fazer) | 4+ |
| Anti-padrões (Sempre Fazer) | 3+ |
| Critérios de Qualidade | 4+ itens verificáveis |

## Passos Pós-Criação

### 1. Atualizar `whenToUse` de arquivos existentes

Para cada arquivo de melhores práticas existente cujo escopo se sobreponha ao novo:
- Adicione uma linha "NOT for: {escopo-sobreposto} → See {novo-id-de-melhores-praticas}" ao `whenToUse` deles.
- Aumente a versão deles (incremento de patch).

### 2. Atualizar `_catalog.yaml`

Adicione uma nova entrada em `_Equipes_agentes/core/best-practices/_catalog.yaml` com:
- `id`: correspondente ao `id` do frontmatter
- `name`: correspondente ao `name` do frontmatter
- `whenToUse`: resumo em uma linha do escopo (apenas positivo, sem "NOT for")
- `file`: `{id}.md`

Coloque-o sob o comentário de seção apropriado (Discipline ou Platform).

### 3. Localização do arquivo

Salve em `_Equipes_agentes/core/best-practices/{id}.md`.

### 4. Validação

Releia o arquivo criado e verifique:
- [ ] Todos os itens do checklist acima estão presentes
- [ ] O frontmatter YAML é processado corretamente (sem erros de sintaxe)
- [ ] `whenToUse` referencia apenas IDs de melhores práticas existentes
- [ ] Exemplos de saída são realistas, não apenas indicadores de template
- [ ] O arquivo excede 200 linhas
- [ ] A entrada correspondente existe em `_catalog.yaml`

---

# Best-Practice Updater — Workflow

Use este workflow ao atualizar arquivos de melhores práticas na biblioteca `_Equipes_agentes/core/best-practices/`.

## Regras de Versionamento (Semver)

| Tipo de Mudança | Incremento de Versão | Exemplos |
|-------------|-------------|----------|
| **Patch** (x.x.X) | Corrigir erros de digitação, ajustar redação, pequenos refinamentos | Corrigir frase de anti-padrão, corrigir termo de vocabulário |
| **Minor** (x.X.0) | Adicionar novo conteúdo, expandir capacidades | Adicionar novo princípio, novo exemplo de saída, nova técnica |
| **Major** (X.0.0) | Reescrever ou reestruturar significativamente | Reescrever princípios básicos, mudar fundamentalmente o escopo |

Sempre atualize o campo `version` no frontmatter YAML após qualquer alteração.

## Cenários de Atualização

### Quando um arquivo é removido da biblioteca

1. Obtenha o `id` do arquivo removido
2. Remova sua entrada de `_Equipes_agentes/core/best-practices/_catalog.yaml`
3. Escaneie TODOS os arquivos restantes em `_Equipes_agentes/core/best-practices/*.md`
4. Para cada arquivo, verifique se o ID removido é referenciado no `whenToUse`
   - Procure por padrões: "NOT for: ... → See {id-removido}"
5. Se encontrado, remova essa linha "NOT for"
6. Aumente a versão dos arquivos afetados (patch: x.x.X)

### Quando um novo arquivo é adicionado à biblioteca

O workflow Best-Practice Creator (acima) lida com as referências cruzadas iniciais de `whenToUse` durante a criação. Esta seção é necessária apenas se as referências cruzadas foram esquecidas ou precisam de ajuste posterior.

1. Leia o `whenToUse` do novo arquivo — identifique seu escopo
2. Escaneie arquivos existentes em busca de sobreposição de escopo
3. Adicione "NOT for: {novo-escopo} → See {novo-id}" onde apropriado
4. Aumente a versão dos arquivos afetados (patch)
5. Garanta que a nova entrada exista no `_catalog.yaml`

### Ao atualizar o conteúdo de um arquivo de melhores práticas

1. Faça as alterações de conteúdo
2. Verifique se TODAS as seções obrigatórias ainda existem:
   - [ ] Core Principles (6+ regras)
   - [ ] Techniques & Frameworks (3+ técnicas)
   - [ ] Quality Criteria (4+ itens verificáveis)
   - [ ] Output Examples (2+ exemplos completos)
   - [ ] Anti-Patterns (Nunca Fazer + Sempre Fazer)
   - [ ] Vocabulary Guidance (Sempre Usar, Nunca Usar, Regras de Tom)
3. Aumente a versão de acordo com as regras semver acima
4. Se o escopo de `whenToUse` mudou, atualize as referências cruzadas em outros arquivos e no `_catalog.yaml`

### Ao atualizar o escopo `whenToUse` de um arquivo

Esta é a mudança mais impactante — ela afeta como o Arquiteto seleciona as melhores práticas durante a criação do squad.

1. Documente o escopo antigo e o novo escopo
2. Atualize o campo `whenToUse` do arquivo
3. Escaneie o `whenToUse` de TODOS os outros arquivos em busca de referências a este ID
4. Atualize as referências cruzadas para refletir o novo escopo
5. Atualize o resumo de `whenToUse` no `_catalog.yaml`
6. Aumente a versão (minor se o escopo expandiu, patch se o escopo diminuiu)

## Checklist de Validação

Após QUALQUER atualização, verifique:

- [ ] A versão foi aumentada corretamente (patch/minor/major conforme as regras)
- [ ] Todas as seções obrigatórias continuam presentes e não vazias
- [ ] As referências cruzadas em `whenToUse` são consistentes em TODOS os arquivos
- [ ] Não há referências quebradas para IDs de melhores práticas removidos
- [ ] Exemplos de saída continuam realistas e completos
- [ ] O arquivo ainda excede o mínimo de 200 linhas
- [ ] A entrada no `_catalog.yaml` está em sincronia com o frontmatter (`id`, `name`, `whenToUse`)
