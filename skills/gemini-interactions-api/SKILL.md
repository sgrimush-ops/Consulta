---
name: gemini-interactions-api
description: Use esta skill ao escrever código que chama a API Gemini para geração de texto, chat multi-turno, compreensão multimodal, geração de imagens, respostas em streaming, tarefas de pesquisa em segundo plano, chamada de função, saída estruturada ou migração da API generateContent antiga. Esta skill cobre a API de Interações, a forma recomendada de usar modelos e agentes Gemini em Python e TypeScript.
---

# Skill da API de Interações do Gemini

A API de Interações é uma interface unificada para interagir com modelos e agentes Gemini. É uma alternativa aprimorada ao `generateContent`.

## Principais Capacidades:
- **Estado do lado do servidor**: Histórico de conversa via `previous_interaction_id`.
- **Execução em segundo plano**: Execução de tarefas de longa duração (como Deep Research).
- **Streaming**: Recebimento de respostas incrementais via Server-Sent Events.
- **Orquestração de ferramentas**: Chamada de função, Google Search, execução de código.
- **Agentes**: Acesso a agentes integrados como o Gemini Deep Research.

## Modelos e Agentes Suportados
- **Modelos**: `gemini-3.1-pro-preview`, `gemini-3-flash-preview`, `gemini-2.5-pro`, `gemini-2.5-flash`.
- **Agentes**: `deep-research-pro-preview-12-2025` (Agente de Pesquisa Profunda).

## Exemplo de Interação (Python)
```python
from google import genai

client = genai.Client()

interaction = client.interactions.create(
    model="gemini-3-flash-preview",
    input="Conte uma piada curta sobre programação."
)
print(interaction.outputs[-1].text)
```

## Diferenças Principais
- O histórico é gerenciado pelo servidor via `previous_interaction_id`.
- Suporte nativo para tarefas assíncronas com `background=True`.
- Acesso a agentes especializados.

## Documentação Completa
- [Documentação de Interações](https://ai.google.dev/gemini-api/docs/interactions.md.txt)
- [Pesquisa Profunda (Deep Research)](https://ai.google.dev/gemini-api/docs/deep-research.md.txt)
